# sitemap-monitor

拉取站点 sitemap，与上次快照对比，从**新增 URL 的路径/slug**提取关键词。支持本地 CLI、本地 Dashboard，以及部署到 Cloudflare（经 GitHub token 读写仓库 + Actions 抓取）。

## 功能

- 多站点 sitemap（含 index 递归、多 URL 分片）
- URL slug → 关键词；与 `data/` 快照 diff
- 终端 + `reports/*.json`（按日，可进 git）
- **Dashboard**：按日看新增词、管理 sitemap、手动触发、异常中心
- GitHub Actions 定时/手动跑 CLI 并回写仓库
- Cloudflare Worker 提供与本地一致的 `/api/*`（PAT 仅存在服务端）

## 快速开始（CLI）

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

sitemap-monitor run
pytest
```

## 本地 Dashboard

```bash
# 终端 1：API（默认 http://127.0.0.1:8787）
sitemap-monitor dashboard

# 终端 2：前端热更新（代理到 8787）
cd dashboard && npm install && npm run dev
# 打开 http://127.0.0.1:5173
```

或先构建前端，只开一个进程（FastAPI 托管 `dashboard/dist`）：

```bash
cd dashboard && npm install && npm run build
cd .. && sitemap-monitor dashboard
# 打开 http://127.0.0.1:8787
```

可选鉴权（**不要在页面里填 token**）。与同级 [`link-master`](../link-master) 共用 **`ACCESS_PASSWORD`**：

- 启动时若未设置环境变量，会自动读取 `../link-master/.env.local`
- 也可用 `DASHBOARD_TOKEN` 覆盖（优先于 `ACCESS_PASSWORD`）

```bash
# 通常无需再 export：只要旁边有 link-master/.env.local 即可
sitemap-monitor dashboard

cd dashboard && npm run dev   # Vite 代理同样会读 link-master 的 ACCESS_PASSWORD
```

构建静态资源给 Cloudflare 时，把同一密码注入前端：

```bash
export VITE_DASHBOARD_TOKEN="$ACCESS_PASSWORD"   # 或与 Worker Secret 同值
cd dashboard && npm run build
```

Worker Secret 可设 `ACCESS_PASSWORD` 或 `DASHBOARD_TOKEN`（二选一），`GITHUB_TOKEN` 直接复用 link-master 的 GitHub PAT。


| 页面 | 能力 |
|------|------|
| 新增关键词 | 按日期 + 站点查看 `new_keywords` / `new_urls` |
| Sitemap 管理 | 编辑 `config.yaml` 站点列表并保存 |
| 触发抓取 | 后台执行 `run_monitor`，轮询 `/api/run/status` |
| 异常 | 缺快照、体积过大、过旧、最近错误；可探测 sitemap 可用性 |

## 配置

见 [`config.yaml`](config.yaml)：

| 字段 | 说明 |
|------|------|
| `sites[].id` | 站点 id → `data/<id>.json` |
| `sites[].sitemap_url` / `sitemap_urls` | 单个或多个 sitemap |
| `sites[].enabled` | 是否参与运行 |

监控频率固定 **每天一次**（北京时间 00:00 由 Actions 触发）。`user_agent` / `timeout` 使用内置默认值，无需配置。

## 输出与 Git

| 路径 | 是否建议提交 |
|------|----------------|
| `data/<site>.json` | 是（快照） |
| `data/.last_run.json` | 是（Dashboard 运行状态） |
| `reports/*.json` | 是（按日新增词，供 CF 读取） |
| `reports/*.md` | 否（已 gitignore） |

## GitHub Actions

工作流：[`.github/workflows/monitor.yml`](.github/workflows/monitor.yml)

- `schedule`：每天北京时间 00:00（cron `0 16 * * *` UTC）
- `workflow_dispatch`：Dashboard / 手动触发
- 跑完后 commit `data/*.json` 与 `reports/*.json`

## 部署到 Cloudflare

本地读写**不需要** GitHub token；上云后 Worker 用 **GitHub PAT** 读写本仓库。Dashboard 鉴权用环境变量 `DASHBOARD_TOKEN`（构建静态资源时另设同值的 `VITE_DASHBOARD_TOKEN`），不在 UI 输入。

### 1. 准备 GitHub PAT

创建 classic/fine-grained token，至少：

- `repo` 读写（Contents）
- `actions:write`（或能 `workflow_dispatch`）

### 2. 构建前端并部署 Worker

根目录 `package.json` 已封装常用脚本（会先 `dashboard` 构建再 `wrangler deploy`；构建时自动从 `ACCESS_PASSWORD` / `../link-master/.env.local` 注入前端 token）：

```bash
# 首次：安装依赖
npm --prefix dashboard install
npm --prefix workers install

# 编辑 workers/wrangler.toml 里的 GITHUB_REPO
# 写入 Worker Secrets（读 env 或 ../link-master/.env.local）
npm run cf:secrets

# 构建 Dashboard + 部署 Worker
npm run cf:deploy
```

常用脚本：

| 命令 | 作用 |
|------|------|
| `npm run cf:deploy` | 构建前端 + 部署 Worker |
| `npm run cf:deploy:worker` | 仅部署 Worker（不重建前端） |
| `npm run cf:build` | 仅构建 `dashboard/dist` |
| `npm run cf:secrets` | 写入 `GITHUB_TOKEN` / `ACCESS_PASSWORD` |
| `npm run cf:dev` | 本地 `wrangler dev` |
| `npm run cf:whoami` | 查看当前 Cloudflare 登录账号 |

`workers/wrangler.toml` 会挂载 `dashboard/dist` 为静态资源，`/api/*` 由 Worker 处理。

### 3. Token 职责

| 密钥 | 位置 | 用途 |
|------|------|------|
| `GITHUB_TOKEN` | Worker Secret | Contents API 读写 config/data/reports；dispatch Actions |
| `ACCESS_PASSWORD` / `DASHBOARD_TOKEN` | Worker Secret（与 link-master 管理密码相同）；本地可自动读 `../link-master/.env.local` | 保护 `/api` |
| `VITE_DASHBOARD_TOKEN` | 仅构建前端时（与上者同值） | 静态托管时浏览器请求自动带 Bearer |
| `GITHUB_TOKEN` | Worker Secret（复用 link-master 的 PAT） | Contents API + workflow_dispatch |

## 行为说明

1. 首次运行：baseline，不报新增
2. 之后：相对上次快照算新增 URL/关键词
3. 关键词：path 最后一段整段 slug（`-`/`_` → 空格），如 `dangerous-danny` → `dangerous danny`；过滤纯数字与过短片段
4. Gamepix 等站点若遇 Cloudflare 403，本地 CLI 会 curl 回退；Worker 探测 sitemap 用 `fetch`（可能仍被拦，以 Actions 抓取为准）

## 明确不做

- Cloudflare Access / OAuth（用环境变量 `DASHBOARD_TOKEN` / `VITE_DASHBOARD_TOKEN`）
- 在 Worker 内重写 Python 抓取
- Slack/邮件通知
