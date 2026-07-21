# Dashboard

Vite + React 前端（Signal Desk）。

## 开发

先启动 API：

```bash
# 可选：export DASHBOARD_TOKEN=your-secret
sitemap-monitor dashboard
```

再启动前端（若启用了 token，同一环境也要 `export DASHBOARD_TOKEN=...`，由 Vite 代理注入，**页面上无需填写**）：

```bash
npm install
npm run dev
```

## 构建

```bash
# 若 API/Worker 启用了鉴权，构建时注入同值：
# export VITE_DASHBOARD_TOKEN=your-secret
npm run build
```

产物在 `dist/`，可由 FastAPI 或 Cloudflare Worker assets 托管。
