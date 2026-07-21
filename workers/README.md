# Cloudflare Worker API

与本地 FastAPI 同契约的 `/api/*`，数据经 GitHub Contents API；`POST /api/run` 触发 `workflow_dispatch`。

## Secrets（与 link-master 共用）

```bash
# 推荐：从仓库根目录一键写入（读 env 或 ../link-master/.env.local）
npm run cf:secrets

# 或在本目录：
npm run secrets
# 等价于手动：
# npx wrangler secret put ACCESS_PASSWORD
# npx wrangler secret put GITHUB_TOKEN
```

Vars 在 [`wrangler.toml`](wrangler.toml)：`GITHUB_REPO`、`GITHUB_BRANCH`、`WORKFLOW_FILE`。

## Deploy

```bash
# 仓库根目录（推荐）
npm run cf:deploy

# 或在本目录：构建前端 + 部署
npm run deploy:full
# 仅部署 Worker
npm run deploy
```