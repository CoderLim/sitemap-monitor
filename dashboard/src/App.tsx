import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  Anomaly,
  ConfigPayload,
  ReportDetail,
  RunStatus,
  Site,
  api,
} from "./api";
import { chunkKeywords, googleTrendsUrl } from "./trends";

type Tab = "keywords" | "trends" | "sites" | "run" | "anomalies";

const ALL_SITES = "__all__";

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

function LoadingBlock({ label = "加载中…" }: { label?: string }) {
  return (
    <div className="loading-block" role="status" aria-live="polite">
      <span className="loading-spinner" aria-hidden="true" />
      <span>{label}</span>
    </div>
  );
}

export default function App() {
  const [tab, setTab] = useState<Tab>("keywords");
  const [error, setError] = useState<string | null>(null);
  const [config, setConfig] = useState<ConfigPayload | null>(null);
  const [dates, setDates] = useState<string[]>([]);
  const [date, setDate] = useState("");
  const [siteId, setSiteId] = useState(ALL_SITES);
  const [reports, setReports] = useState<ReportDetail[]>([]);
  const [run, setRun] = useState<RunStatus | null>(null);
  const [anomalies, setAnomalies] = useState<Anomaly[]>([]);
  const [busy, setBusy] = useState(false);
  const [booting, setBooting] = useState(true);
  const [reportsLoading, setReportsLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [copiedKeyword, setCopiedKeyword] = useState<string | null>(null);

  const flash = useCallback((message: string) => {
    setNotice(message);
    window.setTimeout(() => setNotice(null), 3000);
  }, []);

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
  }, [date]);

  useEffect(() => {
    void wrap(async () => {
      try {
        await refreshCore();
      } finally {
        setBooting(false);
      }
    });
  }, [wrap, refreshCore]);

  useEffect(() => {
    if (!date) {
      setReports([]);
      setReportsLoading(false);
      return;
    }
    let cancelled = false;
    setReportsLoading(true);
    void wrap(async () => {
      try {
        if (siteId === ALL_SITES) {
          const { reports: summaries } = await api.listReports(date);
          const details = await Promise.all(
            summaries.map((s) =>
              api.getReport(date, s.site_id).catch(() => null),
            ),
          );
          if (!cancelled) {
            setReports(details.filter((d): d is ReportDetail => d !== null));
          }
        } else {
          try {
            const detail = await api.getReport(date, siteId);
            if (!cancelled) setReports([detail]);
          } catch {
            if (!cancelled) setReports([]);
          }
        }
      } finally {
        if (!cancelled) setReportsLoading(false);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [date, siteId, wrap]);

  const onRefresh = async () => {
    setRefreshing(true);
    await wrap(async () => {
      try {
        await refreshCore();
      } finally {
        setRefreshing(false);
      }
    });
  };
  useEffect(() => {
    if (run?.status !== "running" && run?.status !== "queued") return;
    const id = window.setInterval(() => {
      void api.runStatus().then(setRun).catch(() => undefined);
    }, 2000);
    return () => window.clearInterval(id);
  }, [run?.status]);

  const siteOptions = useMemo(() => config?.sites.map((s) => s.id) || [], [config]);

  const keywordRows = useMemo(() => {
    const rows: { keyword: string; site: string; urls: string[] }[] = [];
    for (const report of reports) {
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
      for (const keyword of ordered) {
        rows.push({
          keyword,
          site: report.site_id,
          urls: urlsByKeyword.get(keyword) || [],
        });
      }
    }
    return rows;
  }, [reports]);

  const totalKeywords = keywordRows.length;
  const showSiteColumn = siteId === ALL_SITES;
  const hasReports = reports.length > 0;

  const trendsGroups = useMemo(() => {
    const unique = [...new Set(keywordRows.map((row) => row.keyword))];
    return chunkKeywords(unique, 5).map((keywords, index) => ({
      index: index + 1,
      keywords,
      url: googleTrendsUrl(keywords),
      label: keywords.join(", "),
    }));
  }, [keywordRows]);

  const copyText = useCallback(
    async (text: string, okMessage: string) => {
      try {
        if (navigator.clipboard?.writeText) {
          await navigator.clipboard.writeText(text);
        } else {
          const area = document.createElement("textarea");
          area.value = text;
          area.setAttribute("readonly", "");
          area.style.position = "fixed";
          area.style.left = "-9999px";
          document.body.appendChild(area);
          area.select();
          const ok = document.execCommand("copy");
          document.body.removeChild(area);
          if (!ok) throw new Error("execCommand copy failed");
        }
        flash(okMessage);
        return true;
      } catch {
        setError("复制失败，请检查浏览器剪贴板权限");
        return false;
      }
    },
    [flash],
  );

  const onCopyKeyword = async (keyword: string) => {
    const ok = await copyText(keyword, `已复制：${keyword}`);
    if (!ok) return;
    setCopiedKeyword(keyword);
    window.setTimeout(() => {
      setCopiedKeyword((current) => (current === keyword ? null : current));
    }, 1500);
  };

  const onCopyAllKeywords = async () => {
    const unique = [...new Set(keywordRows.map((row) => row.keyword))];
    if (unique.length === 0) return;
    await copyText(unique.join("\n"), `已复制 ${unique.length} 个关键词`);
  };

  const onSaveSites = async (event: FormEvent) => {
    event.preventDefault();
    if (!config) return;
    setBusy(true);
    await wrap(async () => {
      const saved = await api.putSites(config);
      setConfig(saved);
      flash("配置已保存到 config.yaml");
    });
    setBusy(false);
  };

  const onRun = async () => {
    setBusy(true);
    await wrap(async () => {
      const status = await api.triggerRun();
      setRun(status);
      flash("已开始抓取");
    });
    setBusy(false);
  };

  const onClearAnomalies = async () => {
    setBusy(true);
    await wrap(async () => {
      const res = await api.clearAnomalies();
      setAnomalies(res.anomalies);
      flash("异常日志已清空");
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
          <button
            className="btn secondary"
            type="button"
            disabled={booting || refreshing}
            onClick={() => void onRefresh()}
          >
            {refreshing ? "刷新中…" : "刷新数据"}
          </button>
        </div>
      </header>

      {error ? <p className="error-banner">{error}</p> : null}
      {notice ? <p className="notice-banner">{notice}</p> : null}

      <nav className="tabs" aria-label="主导航">
        {(
          [
            ["keywords", "新增关键词"],
            ["trends", "Google Trends"],
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
            {hasReports && !booting && !reportsLoading ? (
              <div className="meta-bar">
                <span className="stat">
                  关键词 <strong>{totalKeywords}</strong>
                </span>
                {keywordRows.length > 0 ? (
                  <button
                    className="btn secondary"
                    type="button"
                    onClick={() => void onCopyAllKeywords()}
                  >
                    复制全部
                  </button>
                ) : null}
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
                <option value={ALL_SITES}>全部</option>
                {siteOptions.map((id) => (
                  <option key={id} value={id}>
                    {id}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {!date && booting ? (
            <LoadingBlock label="正在加载报告…" />
          ) : booting || reportsLoading ? (
            <LoadingBlock label="正在加载关键词…" />
          ) : !hasReports ? (
            <p className="empty">该日暂无报告。</p>
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
                        {showSiteColumn ? <th>站点</th> : null}
                        <th>对应 URL</th>
                      </tr>
                    </thead>
                    <tbody>
                      {keywordRows.map((row) => (
                        <tr key={`${row.site}-${row.keyword}`}>
                          <td>
                            <button
                              type="button"
                              className={`chip chip-copy${
                                copiedKeyword === row.keyword ? " copied" : ""
                              }`}
                              title={
                                copiedKeyword === row.keyword ? "已复制" : "点击复制"
                              }
                              aria-label={`复制 ${row.keyword}`}
                              onClick={() => void onCopyKeyword(row.keyword)}
                            >
                              {row.keyword}
                            </button>
                          </td>
                          {showSiteColumn ? (
                            <td>
                              <span className="mono muted">{row.site}</span>
                            </td>
                          ) : null}
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

      {tab === "trends" ? (
        <section className="panel">
          <div className="panel-head">
            <h2>Google Trends</h2>
            {hasReports && !booting && !reportsLoading ? (
              <div className="meta-bar">
                <span className="stat">
                  分组 <strong>{trendsGroups.length}</strong>
                </span>
                <span className="stat">
                  关键词 <strong>{totalKeywords}</strong>
                </span>
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
                <option value={ALL_SITES}>全部</option>
                {siteOptions.map((id) => (
                  <option key={id} value={id}>
                    {id}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {!date && booting ? (
            <LoadingBlock label="正在加载报告…" />
          ) : booting || reportsLoading ? (
            <LoadingBlock label="正在加载关键词…" />
          ) : !hasReports ? (
            <p className="empty">该日暂无报告。</p>
          ) : trendsGroups.length === 0 ? (
            <p className="empty">无新增关键词，无法生成 Trends 链接。</p>
          ) : (
            <div className="trends-block">
              <p className="muted trends-hint">
                每 5 个关键词一组，点击打开 Trends 对比热度。
              </p>
              <ol className="trends-list">
                {trendsGroups.map((group) => (
                  <li key={group.index}>
                    <a
                      className="trends-link"
                      href={group.url}
                      target="_blank"
                      rel="noreferrer"
                      title={group.label}
                    >
                      <span className="trends-index">
                        第 {group.index} 组 · {group.keywords.length} 词
                      </span>
                      <span className="trends-preview mono">{group.label}</span>
                    </a>
                  </li>
                ))}
              </ol>
            </div>
          )}
        </section>
      ) : null}

      {tab === "sites" ? (
        booting ? (
          <section className="panel">
            <div className="panel-head">
              <h2>Sitemap 配置</h2>
            </div>
            <LoadingBlock label="正在加载站点配置…" />
          </section>
        ) : !config ? (
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
            {!booting ? (
              <span className={`status-pill ${run?.status || "idle"}`}>
                {run?.status || "idle"}
              </span>
            ) : null}
          </div>
          {booting ? (
            <LoadingBlock label="正在加载运行状态…" />
          ) : (
            <>
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
            </>
          )}
        </section>
      ) : null}

      {tab === "anomalies" ? (
        <section className="panel">
          <div className="panel-head">
            <h2>异常中心</h2>
            {!booting ? (
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
            ) : null}
          </div>
          {booting ? (
            <LoadingBlock label="正在加载异常日志…" />
          ) : anomalies.length === 0 ? (
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
