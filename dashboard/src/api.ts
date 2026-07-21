export type Site = {
  id: string;
  enabled: boolean;
  sitemap_url?: string;
  sitemap_urls?: string[];
};

export type ConfigPayload = {
  sites: Site[];
};

export type ReportDetail = {
  site_id: string;
  date: string;
  error: string | null;
  is_baseline: boolean;
  new_urls: { url: string; keywords: string[] }[];
  new_keywords: string[];
};

export type ReportSummary = {
  date: string;
  site_id: string;
  error: string | null;
  is_baseline: boolean;
  new_keyword_count: number;
  new_url_count: number;
};

export type Anomaly = {
  severity: "info" | "warning" | "critical";
  code: string;
  site_id: string | null;
  message: string;
  details?: Record<string, unknown> | null;
  recorded_at?: string | null;
};

export type RunStatus = {
  status: string;
  started_at?: string | null;
  finished_at?: string | null;
  exit_code?: number | null;
  message?: string | null;
  site_results?: unknown[] | null;
  run_id?: string | null;
};

function authHeaders(): HeadersInit {
  // Set at build/dev time via VITE_DASHBOARD_TOKEN (never enter token in the UI).
  // Local `npm run dev` can instead inject DASHBOARD_TOKEN via the Vite proxy.
  const token = import.meta.env.VITE_DASHBOARD_TOKEN?.trim() || "";
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...authHeaders(),
        ...(init?.headers || {}),
      },
    });
  } catch {
    throw new Error(
      "无法连接 API（默认 http://127.0.0.1:8787）。请先在项目根目录运行：sitemap-monitor dashboard",
    );
  }
  if (!res.ok) {
    const text = (await res.text()).trim();
    if (
      res.status === 500 ||
      res.status === 502 ||
      /ECONNREFUSED|Internal Server Error/i.test(text)
    ) {
      throw new Error(
        "API 未启动或代理失败。请另开终端运行：sitemap-monitor dashboard（端口 8787）",
      );
    }
    throw new Error(text || res.statusText);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => request<{ status: string; mode: string }>("/api/health"),
  getSites: () => request<ConfigPayload>("/api/sites"),
  putSites: (body: ConfigPayload) =>
    request<ConfigPayload>("/api/sites", {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  reportDates: () => request<{ dates: string[] }>("/api/reports/dates"),
  listReports: (date?: string, site?: string) => {
    const q = new URLSearchParams();
    if (date) q.set("date", date);
    if (site) q.set("site", site);
    const suffix = q.toString() ? `?${q}` : "";
    return request<{ reports: ReportSummary[] }>(`/api/reports${suffix}`);
  },
  getReport: (date: string, site: string) =>
    request<ReportDetail>(`/api/reports?date=${encodeURIComponent(date)}&site=${encodeURIComponent(site)}`),
  triggerRun: () => request<RunStatus>("/api/run", { method: "POST" }),
  runStatus: () => request<RunStatus>("/api/run/status"),
  anomalies: () =>
    request<{ generated_at: string | null; anomalies: Anomaly[] }>("/api/anomalies"),
  clearAnomalies: () =>
    request<{ generated_at: string | null; anomalies: Anomaly[] }>("/api/anomalies", {
      method: "DELETE",
    }),
};
