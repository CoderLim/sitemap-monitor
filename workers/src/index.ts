import { Hono } from "hono";
import { cors } from "hono/cors";
import yaml from "js-yaml";

type Env = {
  DASHBOARD_TOKEN?: string;
  ACCESS_PASSWORD?: string;
  GITHUB_TOKEN: string;
  GITHUB_REPO: string;
  GITHUB_BRANCH?: string;
  WORKFLOW_FILE?: string;
  ASSETS?: Fetcher;
};

type Site = {
  id: string;
  enabled?: boolean;
  sitemap_url?: string;
  sitemap_urls?: string[];
};

type AppConfig = {
  interval: string;
  user_agent: string;
  timeout_seconds: number;
  sites: Site[];
};

const app = new Hono<{ Bindings: Env }>();

app.use("*", cors());

app.use("/api/*", async (c, next) => {
  const token = (c.env.DASHBOARD_TOKEN || c.env.ACCESS_PASSWORD || "").trim();
  if (token) {
    const auth = c.req.header("Authorization") || "";
    if (auth !== `Bearer ${token}`) {
      return c.json({ detail: "unauthorized" }, 401);
    }
  }
  await next();
});

app.get("/api/health", (c) => c.json({ status: "ok", mode: "cloudflare" }));

app.get("/api/sites", async (c) => {
  const cfg = await readConfig(c.env);
  return c.json(cfg);
});

app.put("/api/sites", async (c) => {
  const body = (await c.req.json()) as { sites: Site[] };
  await writeGithubFile(
    c.env,
    "config.yaml",
    yaml.dump({ sites: body.sites }, { lineWidth: -1, noRefs: true }),
    "chore: update sites via dashboard",
  );
  return c.json({ sites: body.sites });
});

app.get("/api/reports/dates", async (c) => {
  const files = await listGithubDir(c.env, "reports");
  const dates = new Set<string>();
  for (const name of files) {
    const m = name.match(/^(\d{4}-\d{2}-\d{2})-.+\.json$/);
    if (m) dates.add(m[1]);
  }
  return c.json({ dates: [...dates].sort().reverse() });
});

app.get("/api/reports", async (c) => {
  const date = c.req.query("date");
  const site = c.req.query("site");
  if (date && site) {
    const text = await readGithubFile(c.env, `reports/${date}-${site}.json`);
    if (!text) return c.json({ detail: "report not found" }, 404);
    return c.json(JSON.parse(text));
  }
  const files = await listGithubDir(c.env, "reports");
  const reports = [];
  for (const name of files) {
    const m = name.match(/^(\d{4}-\d{2}-\d{2})-(.+)\.json$/);
    if (!m) continue;
    if (date && m[1] !== date) continue;
    if (site && m[2] !== site) continue;
    const text = await readGithubFile(c.env, `reports/${name}`);
    if (!text) continue;
    const payload = JSON.parse(text);
    reports.push({
      date: m[1],
      site_id: m[2],
      error: payload.error ?? null,
      is_baseline: Boolean(payload.is_baseline),
      new_keyword_count: (payload.new_keywords || []).length,
      new_url_count: (payload.new_urls || []).length,
    });
  }
  reports.sort((a, b) => (a.date < b.date ? 1 : -1));
  return c.json({ reports });
});

app.post("/api/run", async (c) => {
  const repo = c.env.GITHUB_REPO;
  const workflow = c.env.WORKFLOW_FILE || "monitor.yml";
  const branch = c.env.GITHUB_BRANCH || "main";
  const res = await githubFetch(
    c.env,
    `/repos/${repo}/actions/workflows/${workflow}/dispatches`,
    {
      method: "POST",
      body: JSON.stringify({ ref: branch }),
    },
  );
  if (!res.ok && res.status !== 204) {
    const text = await res.text();
    return c.json({ detail: text || "failed to dispatch workflow" }, 502);
  }
  const status = {
    status: "queued",
    started_at: new Date().toISOString(),
    message: "GitHub Actions workflow_dispatch accepted",
    run_id: null,
  };
  await writeGithubFile(
    c.env,
    "data/.last_run.json",
    JSON.stringify(status, null, 2) + "\n",
    "chore: queue monitor run via dashboard",
  );
  return c.json(status);
});

app.get("/api/run/status", async (c) => {
  const text = await readGithubFile(c.env, "data/.last_run.json");
  if (!text) return c.json({ status: "idle" });
  return c.json(JSON.parse(text));
});

app.get("/api/anomalies", async (c) => {
  // Anomalies are auto-recorded after each fetch (committed to data/.anomalies.json).
  const stored = await readGithubFile(c.env, "data/.anomalies.json");
  if (stored) {
    return c.json(JSON.parse(stored));
  }
  // Fallback before the first run: local (non-network) checks.
  const anomalies = await computeAnomalies(c.env, false);
  return c.json({ generated_at: null, anomalies });
});

app.delete("/api/anomalies", async (c) => {
  const ts = new Date().toISOString();
  const payload = { generated_at: ts, anomalies: [] as unknown[] };
  await writeGithubFile(
    c.env,
    "data/.anomalies.json",
    JSON.stringify(payload, null, 2) + "\n",
    "chore: clear anomaly log via dashboard",
  );
  return c.json(payload);
});

app.all("*", async (c) => {
  if (c.env.ASSETS) return c.env.ASSETS.fetch(c.req.raw);
  return c.text("Dashboard assets not configured", 404);
});

export default app;

async function readConfig(env: Env): Promise<AppConfig> {
  const text = await readGithubFile(env, "config.yaml");
  if (!text) throw new Error("config.yaml not found in repo");
  return yaml.load(text) as AppConfig;
}

async function computeAnomalies(env: Env, checkSitemaps: boolean) {
  const cfg = await readConfig(env);
  const anomalies: Array<Record<string, unknown>> = [];
  const dataFiles = await listGithubDir(env, "data");
  const reportFiles = await listGithubDir(env, "reports");

  const latestBySite = new Map<string, { date: string; name: string }>();
  for (const name of reportFiles) {
    const m = name.match(/^(\d{4}-\d{2}-\d{2})-(.+)\.json$/);
    if (!m) continue;
    const prev = latestBySite.get(m[2]);
    if (!prev || m[1] > prev.date) latestBySite.set(m[2], { date: m[1], name });
  }

  for (const site of cfg.sites || []) {
    if (site.enabled === false) continue;
    const snapName = `${site.id}.json`;
    if (!dataFiles.includes(snapName)) {
      anomalies.push({
        severity: "warning",
        code: "missing_snapshot",
        site_id: site.id,
        message: `Enabled site '${site.id}' has no data/${snapName} snapshot yet`,
      });
    } else {
      const meta = await githubFileMeta(env, `data/${snapName}`);
      if (meta && meta.size >= 10 * 1024 * 1024) {
        anomalies.push({
          severity: "critical",
          code: "snapshot_too_large",
          site_id: site.id,
          message: `Snapshot ${snapName} is ${(meta.size / (1024 * 1024)).toFixed(1)} MB (limit 10 MB)`,
          details: { bytes: meta.size },
        });
      } else if (meta && meta.size >= 5 * 1024 * 1024) {
        anomalies.push({
          severity: "warning",
          code: "snapshot_large",
          site_id: site.id,
          message: `Snapshot ${snapName} is ${(meta.size / (1024 * 1024)).toFixed(1)} MB (warn at 5 MB)`,
          details: { bytes: meta.size },
        });
      }
    }

    const latest = latestBySite.get(site.id);
    if (latest) {
      const text = await readGithubFile(env, `reports/${latest.name}`);
      if (text) {
        const payload = JSON.parse(text);
        if (payload.error) {
          anomalies.push({
            severity: "critical",
            code: "last_run_error",
            site_id: site.id,
            message: `Latest report for '${site.id}' (${latest.date}) has an error`,
            details: { error: payload.error, date: latest.date },
          });
        }
      }
    }

    if (checkSitemaps) {
      const urls =
        site.sitemap_urls ||
        (site.sitemap_url ? [site.sitemap_url] : []);
      for (const url of urls) {
        try {
          const res = await fetch(url, {
            headers: { "User-Agent": cfg.user_agent || "sitemap-monitor/0.1" },
          });
          if (!res.ok) {
            anomalies.push({
              severity: "critical",
              code: "sitemap_unreachable",
              site_id: site.id,
              message: `Sitemap probe failed: ${url}`,
              details: { url, error: `HTTP ${res.status}` },
            });
            continue;
          }
          const text = await res.text();
          const locCount = (text.match(/<loc>/gi) || []).length;
          if (locCount === 0) {
            anomalies.push({
              severity: "warning",
              code: "sitemap_empty",
              site_id: site.id,
              message: `Sitemap returned zero locs: ${url}`,
              details: { url },
            });
          }
        } catch (err) {
          anomalies.push({
            severity: "critical",
            code: "sitemap_unreachable",
            site_id: site.id,
            message: `Sitemap probe failed: ${url}`,
            details: { url, error: String(err) },
          });
        }
      }
    }
  }

  return anomalies;
}

async function githubFetch(env: Env, path: string, init: RequestInit = {}) {
  const headers = new Headers(init.headers || {});
  headers.set("Authorization", `Bearer ${env.GITHUB_TOKEN}`);
  headers.set("Accept", "application/vnd.github+json");
  headers.set("X-GitHub-Api-Version", "2022-11-28");
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  return fetch(`https://api.github.com${path}`, { ...init, headers });
}

async function readGithubFile(env: Env, path: string): Promise<string | null> {
  const branch = env.GITHUB_BRANCH || "main";
  const res = await githubFetch(
    env,
    `/repos/${env.GITHUB_REPO}/contents/${path}?ref=${encodeURIComponent(branch)}`,
  );
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`GitHub read failed for ${path}: ${res.status}`);
  const data = (await res.json()) as { content?: string; encoding?: string };
  if (!data.content) return null;
  return decodeBase64(data.content);
}

function decodeBase64(content: string): string {
  const binary = atob(content.replace(/\n/g, ""));
  const bytes = Uint8Array.from(binary, (c) => c.charCodeAt(0));
  return new TextDecoder().decode(bytes);
}

function encodeBase64(text: string): string {
  const bytes = new TextEncoder().encode(text);
  let binary = "";
  for (const b of bytes) binary += String.fromCharCode(b);
  return btoa(binary);
}

async function githubFileMeta(
  env: Env,
  path: string,
): Promise<{ size: number } | null> {
  const branch = env.GITHUB_BRANCH || "main";
  const res = await githubFetch(
    env,
    `/repos/${env.GITHUB_REPO}/contents/${path}?ref=${encodeURIComponent(branch)}`,
  );
  if (res.status === 404) return null;
  if (!res.ok) return null;
  const data = (await res.json()) as { size?: number };
  return { size: data.size || 0 };
}

async function listGithubDir(env: Env, path: string): Promise<string[]> {
  const branch = env.GITHUB_BRANCH || "main";
  const res = await githubFetch(
    env,
    `/repos/${env.GITHUB_REPO}/contents/${path}?ref=${encodeURIComponent(branch)}`,
  );
  if (res.status === 404) return [];
  if (!res.ok) throw new Error(`GitHub list failed for ${path}: ${res.status}`);
  const data = (await res.json()) as Array<{ name: string; type: string }>;
  if (!Array.isArray(data)) return [];
  return data.filter((x) => x.type === "file").map((x) => x.name);
}

async function writeGithubFile(
  env: Env,
  path: string,
  content: string,
  message: string,
) {
  const branch = env.GITHUB_BRANCH || "main";
  const existing = await githubFetch(
    env,
    `/repos/${env.GITHUB_REPO}/contents/${path}?ref=${encodeURIComponent(branch)}`,
  );
  let sha: string | undefined;
  if (existing.ok) {
    const data = (await existing.json()) as { sha?: string };
    sha = data.sha;
  }
  const body: Record<string, string> = {
    message,
    content: encodeBase64(content),
    branch,
  };
  if (sha) body.sha = sha;
  const res = await githubFetch(env, `/repos/${env.GITHUB_REPO}/contents/${path}`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    throw new Error(`GitHub write failed for ${path}: ${await res.text()}`);
  }
}
