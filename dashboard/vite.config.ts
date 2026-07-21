import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import fs from "node:fs";
import path from "node:path";

/** Load key=value pairs from a dotenv file without overriding existing env. */
function loadDotenvFile(filePath: string): Record<string, string> {
  if (!fs.existsSync(filePath)) return {};
  const out: Record<string, string> = {};
  for (const raw of fs.readFileSync(filePath, "utf8").split("\n")) {
    const line = raw.trim();
    if (!line || line.startsWith("#") || !line.includes("=")) continue;
    const idx = line.indexOf("=");
    const key = line.slice(0, idx).trim();
    let value = line.slice(idx + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    if (key) out[key] = value;
  }
  return out;
}

function resolveDashboardToken(mode: string, cwd: string): string {
  const env = loadEnv(mode, cwd, "");
  const fromEnv =
    env.DASHBOARD_TOKEN ||
    env.ACCESS_PASSWORD ||
    process.env.DASHBOARD_TOKEN ||
    process.env.ACCESS_PASSWORD ||
    "";
  if (fromEnv.trim()) return fromEnv.trim();

  // Reuse sibling link-master/.env.local (same ACCESS_PASSWORD)
  const sibling = path.resolve(cwd, "../../link-master/.env.local");
  const siblingAlt = path.resolve(cwd, "../link-master/.env.local");
  const file = fs.existsSync(sibling)
    ? sibling
    : fs.existsSync(siblingAlt)
      ? siblingAlt
      : "";
  if (!file) return "";
  const parsed = loadDotenvFile(file);
  return (parsed.DASHBOARD_TOKEN || parsed.ACCESS_PASSWORD || "").trim();
}

export default defineConfig(({ mode }) => {
  const dashboardToken = resolveDashboardToken(mode, process.cwd());

  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        "/api": {
          target: "http://127.0.0.1:8787",
          configure: (proxy) => {
            proxy.on("proxyReq", (proxyReq) => {
              if (dashboardToken) {
                proxyReq.setHeader("Authorization", `Bearer ${dashboardToken}`);
              }
            });
          },
        },
      },
    },
    build: {
      outDir: "dist",
      emptyOutDir: true,
    },
  };
});
