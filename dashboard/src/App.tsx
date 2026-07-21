import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  Anomaly,
  ConfigPayload,
  ReportDetail,
  RunStatus,
  Site,
  api,
} from "./api";

type Tab = "keywords" | "sites" | "run" | "anomalies";

const emptySite = (): Site => ({
  id: "",
  enabled: true,
  sitemap_url: "",
});

const pad = (n: number) => String(n).padStart(2, "0");

function formatTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ` +
    `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
  );
}

export default function App() {
  const [tab, setTab] = useState<Tab>("keywords");
  const [error, setError] = useState<string | null>(null);
  const [config, setConfig] = useState<ConfigPayload | null>(null);
  const [dates, setDates] = useState<string[]>([]);
  const [date, setDate] = useState("");
  const [siteId, setSiteId] = useState("");
  const [report, setReport] = useState<ReportDetail | null>(null);
  const [run, setRun] = useState<RunStatus | null>(null);
  const [anomalies, setAnomalies] = useState<Anomaly[]>([]);
  const [busy, setBusy] = useState(false);

  const wrap = useCallback(async (fn: () => Promise<void>) => {
    setError(null);
    try {
      await fn();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, []);

  const refreshCore = useCallback(async () => {
    const [sites, dateRes, status, anomalyRes] = await Promise.all([
      api.getSites(),
      api.reportDates(),
      api.runStatus(),
      api.anomalies(),
    ]);
    setConfig(sites);
    setDates(dateRes.dates);
    setRun(status);
    setAnomalies(anomalyRes.anomalies);
    if (!date && dateRes.dates[0]) setDate(dateRes.dates[0]);
    if (!siteId && sites.sites[0]) setSiteId(sites.sites[0].id);
  }, [date, siteId]);

  useEffect(() => {
    void wrap(refreshCore);
  }, [wrap, refreshCore]);

  useEffect(() => {
    if (!date || !siteId) {
      setReport(null);
      return;
    }
    void wrap(async () => {
      try {
        setReport(await api.getReport(date, siteId));
      } catch {
        setReport(null);
      }
    });
  }, [date, siteId, wrap]);

  useEffect(() => {
    if (run?.status !== "running" && run?.status !== "queued") return;
    const id = window.setInterval(() => {
      void api.runStatus().then(setRun).catch(() => undefined);
    }, 2000);
    return () => window.clearInterval(id);
  }, [run?.status]);

  const siteOptions = useMemo(() => config?.sites.map((s) => s.id) || [], [config]);

  const keywordRows = useMemo(() => {
    if (!report) return [];
    const urlsByKeyword = new Map<string, string[]>();
    for (const row of report.new_urls) {
      for (const kw of row.keywords) {
        const list = urlsByKeyword.get(kw) || [];
        if (!list.includes(row.url)) list.push(row.url);
        urlsByKeyword.set(kw, list);
      }
    }
    const ordered = report.new_keywords.length
      ? report.new_keywords
      : [...urlsByKeyword.keys()];
    return ordered.map((keyword) => ({
      keyword,
      urls: urlsByKeyword.get(keyword) || [],
    }));
  }, [report]);

  const onSaveSites = async (event: FormEvent) => {
    event.preventDefault();
    if (!config) return;
    setBusy(true);
    await wrap(async () => {
      const saved = await api.putSites(config);
      setConfig(saved);
    });
    setBusy(false);
  };

  const onRun = async () => {
    setBusy(true);
    await wrap(async () => {
      const status = await api.triggerRun();
      setRun(status);
    });
    setBusy(false);
  };

  const onClearAnomalies = async () => {
    setBusy(true);
    await wrap(async () => {
      const res = await api.clearAnomalies();
      setAnomalies(res.anomalies);
    });
    setBusy(false);
  };

  return (
    <div className="app">
      <header className="hero">
        <div className="hero-copy">
          <h1 className="brand">Sitemap Dashboard</h1>
        </div>
        <div className="toolbar">
          <button className="btn secondary" type="button" onClick={() => void wrap(refreshCore)}>
            刷新数据
          </button>
        </div>
      </header>

      {error ? <p className="error-banner">{error}</p> : null}

      <nav className="tabs" aria-label="主导航">
        {(
          [
            ["keywords", "新增关键词"],
            ["sites", "Sitemap 管理"],
            ["run", "触发抓取"],
            ["anomalies", "异常"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            className={`tab ${tab === id ? "active" : ""}`}
            onClick={() => setTab(id)}
          >
            {label}
          </button>
        ))}
      </nav>

      {tab === "keywords" ? (
        <section className="panel">
          <div className="panel-head">
            <h2>按日新增词</h2>
            {report ? (
              <div className="meta-bar">
                <span className="stat">
                  关键词 <strong>{report.is_baseline ? 0 : report.new_keywords.length}</strong>
                </span>
                {report.is_baseline ? <span className="stat">baseline</span> : null}
                {report.error ? <span className="status-pill failed">error</span> : null}
              </div>
            ) : null}
          </div>

          <div className="filters">
            <label>
              日期
              <select value={date} onChange={(e) => setDate(e.target.value)}>
                {dates.length === 0 ? <option value="">暂无报告</option> : null}
                {dates.map((d) => (
                  <option key={d} value={d}>
                    {d}
                  </option>
                ))}
              </select>
            </label>
            <label>
              站点
              <select value={siteId} onChange={(e) => setSiteId(e.target.value)}>
                {siteOptions.map((id) => (
                  <option key={id} value={id}>
                    {id}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {!report ? (
            <p className="empty">该日该站暂无报告。</p>
          ) : (
            <>
              <h3>关键词明细</h3>
              {keywordRows.length === 0 ? (
                <p className="empty">无新增关键词</p>
              ) : (
                <div className="table-wrap">
                  <table className="table">
                    <thead>
                      <tr>
                        <th>关键词</th>
                        <th>对应 URL</th>
                      </tr>
                    </thead>
                    <tbody>
                      {keywordRows.map((row) => (
                        <tr key={row.keyword}>
                          <td>
                            <span className="chip">{row.keyword}</span>
                          </td>
                          <td>
                            {row.urls.length === 0 ? (
                              <span className="muted">—</span>
                            ) : (
                              <ul className="url-list">
                                {row.urls.map((url) => (
                                  <li key={url}>
                                    <a href={url} target="_blank" rel="noreferrer">
                                      {url}
                                    </a>
                                  </li>
                                ))}
                              </ul>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </section>
      ) : null}

      {tab === "sites" ? (
        !config ? (
          <section className="panel">
            <div className="panel-head">
              <h2>Sitemap 配置</h2>
            </div>
            <p className="empty">
              尚未加载到站点配置。请确认已启动 API：
              <code className="mono"> sitemap-monitor dashboard </code>
              （端口 8787），然后点「刷新数据」。
            </p>
          </section>
        ) : (
          <section className="panel">
            <div className="panel-head">
              <h2>Sitemap 配置</h2>
              <span className="stat">
                站点 <strong>{config.sites.length}</strong>
              </span>
            </div>
            <form onSubmit={onSaveSites}>
              <div className="site-head" aria-hidden="true">
                <span>启用</span>
                <span>站点 ID</span>
                <span>Sitemap URL（多个用逗号或空格分隔）</span>
                <span></span>
              </div>
              <div className="site-list">
                {config.sites.map((site, index) => (
                  <div className="site-row" key={`${site.id}-${index}`}>
                    <label className="switch" title={site.enabled ? "已启用" : "已停用"}>
                      <input
                        type="checkbox"
                        checked={site.enabled}
                        onChange={(e) => {
                          const sites = [...config.sites];
                          sites[index] = { ...site, enabled: e.target.checked };
                          setConfig({ ...config, sites });
                        }}
                      />
                      <span className="track" />
                    </label>
                    <input
                      className="cell-id"
                      placeholder="site-id"
                      value={site.id}
                      onChange={(e) => {
                        const sites = [...config.sites];
                        sites[index] = { ...site, id: e.target.value };
                        setConfig({ ...config, sites });
                      }}
                    />
                    <input
                      className="cell-url"
                      placeholder="https://example.com/sitemap.xml"
                      value={(
                        site.sitemap_urls || (site.sitemap_url ? [site.sitemap_url] : [])
                      ).join(", ")}
                      onChange={(e) => {
                        const parts = e.target.value
                          .split(/[\s,]+/)
                          .map((x) => x.trim())
                          .filter(Boolean);
                        const sites = [...config.sites];
                        if (parts.length <= 1) {
                          sites[index] = {
                            id: site.id,
                            enabled: site.enabled,
                            sitemap_url: parts[0] || "",
                          };
                        } else {
                          sites[index] = {
                            id: site.id,
                            enabled: site.enabled,
                            sitemap_urls: parts,
                          };
                        }
                        setConfig({ ...config, sites });
                      }}
                    />
                    <button
                      type="button"
                      className="icon-btn"
                      title="删除站点"
                      aria-label="删除站点"
                      onClick={() =>
                        setConfig({
                          ...config,
                          sites: config.sites.filter((_, i) => i !== index),
                        })
                      }
                    >
                      ×
                    </button>
                  </div>
                ))}
              </div>

              <div className="footer-actions">
                <button
                  type="button"
                  className="btn secondary"
                  onClick={() =>
                    setConfig({ ...config, sites: [...config.sites, emptySite()] })
                  }
                >
                  添加站点
                </button>
                <button className="btn" type="submit" disabled={busy}>
                  保存配置
                </button>
              </div>
            </form>
          </section>
        )
      ) : null}

      {tab === "run" ? (
        <section className="panel">
          <div className="panel-head">
            <h2>主动触发抓取</h2>
            <span className={`status-pill ${run?.status || "idle"}`}>
              {run?.status || "idle"}
            </span>
          </div>
          <p className="muted" style={{ marginTop: 0 }}>
            本地会在后台直接跑一轮 monitor；Cloudflare 部署时会排队 GitHub Action。
          </p>
          <div className="footer-actions" style={{ borderTop: "none", paddingTop: 0 }}>
            <button className="btn" type="button" disabled={busy} onClick={() => void onRun()}>
              立即抓取
            </button>
          </div>
          <div className="run-grid" style={{ marginTop: "1.1rem" }}>
            <div className="run-card">
              <h3>时间线</h3>
              <p className="mono muted" style={{ margin: 0, lineHeight: 1.7 }}>
                started
                <br />
                <strong style={{ color: "var(--ink)" }}>{run?.started_at || "—"}</strong>
                <br />
                <br />
                finished
                <br />
                <strong style={{ color: "var(--ink)" }}>{run?.finished_at || "—"}</strong>
              </p>
            </div>
            <div className="run-card">
              <h3>消息</h3>
              <p className="mono" style={{ margin: 0, lineHeight: 1.6 }}>
                {run?.message || "尚无运行记录"}
              </p>
            </div>
          </div>
        </section>
      ) : null}

      {tab === "anomalies" ? (
        <section className="panel">
          <div className="panel-head">
            <h2>异常中心</h2>
            <div className="meta-bar">
              <span className="stat">
                当前 <strong>{anomalies.length}</strong>
              </span>
              <button
                className="btn secondary"
                type="button"
                disabled={busy || anomalies.length === 0}
                onClick={() => void onClearAnomalies()}
              >
                清空日志
              </button>
            </div>
          </div>
          {anomalies.length === 0 ? (
            <p className="empty" style={{ marginTop: "1rem" }}>
              暂无异常。
            </p>
          ) : (
            <div className="anomaly-list" style={{ marginTop: "1rem" }}>
              {anomalies.map((item, idx) => {
                const detail = item.details || {};
                const errorText =
                  typeof detail.error === "string" ? detail.error : undefined;
                const url = typeof detail.url === "string" ? detail.url : undefined;
                const extra = Object.entries(detail).filter(
                  ([k]) => k !== "error" && k !== "url",
                );
                return (
                  <div className="anomaly" key={`${item.code}-${idx}`}>
                    <div className="anomaly-top">
                      <span className={`sev ${item.severity}`}>
                        {item.severity} · {item.code}
                        {item.site_id ? ` · ${item.site_id}` : ""}
                      </span>
                      {item.recorded_at ? (
                        <span className="anomaly-time">{formatTime(item.recorded_at)}</span>
                      ) : null}
                    </div>
                    <div>{item.message}</div>
                    {url ? (
                      <a className="anomaly-url" href={url} target="_blank" rel="noreferrer">
                        {url}
                      </a>
                    ) : null}
                    {errorText ? <pre className="anomaly-error">{errorText}</pre> : null}
                    {extra.length > 0 ? (
                      <div className="anomaly-meta">
                        {extra.map(([k, v]) => (
                          <span key={k}>
                            {k}: {String(v)}
                          </span>
                        ))}
                      </div>
                    ) : null}
                  </div>
                );
              })}
            </div>
          )}
        </section>
      ) : null}
    </div>
  );
}
