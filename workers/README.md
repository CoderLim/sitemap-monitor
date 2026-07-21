# Cloudflare Worker API

与本地 FastAPI 同契约的 `/api/*`，数据经 GitHub Contents API；`POST /api/run` 触发 `workflow_dispatch`。

## Secrets（与 link-master 共用）

```bash
npx wrangler secret put ACCESS_PASSWORD   # 同 link-master 管理密码
npx wrangler secret put GITHUB_TOKEN      # 同 link-master 的 GitHub PAT
# 可选：npx wrangler secret put DASHBOARD_TOKEN
```

Vars 在 [`wrangler.toml`](wrangler.toml)：`GITHUB_REPO`、`GITHUB_BRANCH`、`WORKFLOW_FILE`。

## Deploy

```bash
cd ../dashboard && npm run build
cd ../workers && npm install && npx wrangler deploy
```
