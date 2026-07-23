# Keyword Date Ranges Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single-day date dropdown with three shared quick ranges (1 / 7 / 30 days) on Keywords and Trends, aggregating and deduping new keywords client-side.

**Architecture:** Pure helpers in `keywordRange.ts` compute the date window from the latest report date and build first-seen keyword rows. `App.tsx` loads reports for those dates in parallel via existing APIs, then drives both tabs from shared `range` + `siteId` state. No backend changes.

**Tech Stack:** React 19, TypeScript, Vite; Vitest for pure-function unit tests; existing `/api/reports*` endpoints.

**Spec:** `docs/superpowers/specs/2026-07-23-keyword-date-ranges-design.md`

---

## File map

| File | Responsibility |
|------|----------------|
| `dashboard/src/keywordRange.ts` | Range types, date-window filter, keyword-row build + dedupe |
| `dashboard/src/keywordRange.test.ts` | Unit tests for the helpers above |
| `dashboard/package.json` | Add `vitest` + `test` script |
| `dashboard/src/App.tsx` | Shared range UI + multi-day fetch + table/Trends wiring |
| `dashboard/src/styles.css` | Range segment control + filters layout |
| `README.md` | One-line feature description update |

---

### Task 1: Pure helpers + failing tests

**Files:**
- Create: `dashboard/src/keywordRange.ts`
- Create: `dashboard/src/keywordRange.test.ts`
- Modify: `dashboard/package.json`

- [ ] **Step 1: Add Vitest**

In `dashboard/`:

```bash
npm install -D vitest
```

Update `dashboard/package.json` scripts:

```json
"scripts": {
  "dev": "vite",
  "build": "vite build",
  "build:cf": "vite build",
  "preview": "vite preview",
  "test": "vitest run"
}
```

- [ ] **Step 2: Write failing tests**

Create `dashboard/src/keywordRange.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import {
  datesInRange,
  buildKeywordRows,
  type ReportLike,
} from "./keywordRange";

describe("datesInRange", () => {
  const dates = ["2026-07-22", "2026-07-21", "2026-07-15", "2026-07-01"];

  it("returns only the latest day for 1d", () => {
    expect(datesInRange(dates, "1d")).toEqual(["2026-07-22"]);
  });

  it("returns days within 7 calendar days ending at latest", () => {
    expect(datesInRange(dates, "7d")).toEqual([
      "2026-07-22",
      "2026-07-21",
      "2026-07-15",
    ]);
  });

  it("returns days within 30 calendar days ending at latest", () => {
    expect(datesInRange(dates, "30d")).toEqual(dates);
  });

  it("returns empty when there are no dates", () => {
    expect(datesInRange([], "7d")).toEqual([]);
  });
});

describe("buildKeywordRows", () => {
  const reports: ReportLike[] = [
    {
      site_id: "poki",
      date: "2026-07-22",
      new_keywords: ["alpha", "beta"],
      new_urls: [
        { url: "https://poki.com/a", keywords: ["alpha"] },
        { url: "https://poki.com/b", keywords: ["beta"] },
      ],
    },
    {
      site_id: "poki",
      date: "2026-07-21",
      new_keywords: ["alpha", "gamma"],
      new_urls: [
        { url: "https://poki.com/a-old", keywords: ["alpha"] },
        { url: "https://poki.com/g", keywords: ["gamma"] },
      ],
    },
    {
      site_id: "y8",
      date: "2026-07-21",
      new_keywords: ["alpha"],
      new_urls: [{ url: "https://y8.com/a", keywords: ["alpha"] }],
    },
  ];

  it("keeps first-seen date per site+keyword and that day's urls", () => {
    const rows = buildKeywordRows(reports);
    // Sorted by firstDate, then site, then keyword
    expect(rows).toEqual([
      {
        keyword: "alpha",
        site: "poki",
        firstDate: "2026-07-21",
        urls: ["https://poki.com/a-old"],
      },
      {
        keyword: "gamma",
        site: "poki",
        firstDate: "2026-07-21",
        urls: ["https://poki.com/g"],
      },
      {
        keyword: "alpha",
        site: "y8",
        firstDate: "2026-07-21",
        urls: ["https://y8.com/a"],
      },
      {
        keyword: "beta",
        site: "poki",
        firstDate: "2026-07-22",
        urls: ["https://poki.com/b"],
      },
    ]);
  });

  it("falls back to urls-derived keywords when new_keywords is empty", () => {
    const rows = buildKeywordRows([
      {
        site_id: "poki",
        date: "2026-07-22",
        new_keywords: [],
        new_urls: [{ url: "https://poki.com/x", keywords: ["from-url"] }],
      },
    ]);
    expect(rows).toEqual([
      {
        keyword: "from-url",
        site: "poki",
        firstDate: "2026-07-22",
        urls: ["https://poki.com/x"],
      },
    ]);
  });
});
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `npm --prefix dashboard test`

Expected: FAIL (module `./keywordRange` not found, or exports missing).

- [ ] **Step 4: Implement helpers**

Create `dashboard/src/keywordRange.ts`:

```ts
/** Date-window filter and first-seen keyword aggregation for the dashboard. */

export type RangeKey = "1d" | "7d" | "30d";

export const RANGE_OPTIONS: { key: RangeKey; label: string }[] = [
  { key: "1d", label: "最近一天" },
  { key: "7d", label: "最近一周" },
  { key: "30d", label: "最近一个月" },
];

export const RANGE_DAYS: Record<RangeKey, number> = {
  "1d": 1,
  "7d": 7,
  "30d": 30,
};

export type ReportLike = {
  site_id: string;
  date: string;
  new_keywords: string[];
  new_urls: { url: string; keywords: string[] }[];
};

export type KeywordRow = {
  keyword: string;
  site: string;
  firstDate: string;
  urls: string[];
};

/** Keep dates that fall in [latest-(N-1) days, latest]. `allDates` is newest-first. */
export function datesInRange(allDates: string[], range: RangeKey): string[] {
  if (allDates.length === 0) return [];
  const end = allDates[0];
  const n = RANGE_DAYS[range];
  const endMs = Date.parse(`${end}T00:00:00Z`);
  if (Number.isNaN(endMs)) return [];
  const start = new Date(endMs - (n - 1) * 86_400_000)
    .toISOString()
    .slice(0, 10);
  return allDates.filter((d) => d >= start && d <= end);
}

function urlsByKeyword(
  newUrls: { url: string; keywords: string[] }[],
): Map<string, string[]> {
  const map = new Map<string, string[]>();
  for (const row of newUrls) {
    for (const kw of row.keywords) {
      const list = map.get(kw) || [];
      if (!list.includes(row.url)) list.push(row.url);
      map.set(kw, list);
    }
  }
  return map;
}

/**
 * One row per site+keyword; keep earliest `date` and that day's URLs.
 * Output order: ascending firstDate, then site, then keyword.
 */
export function buildKeywordRows(reports: ReportLike[]): KeywordRow[] {
  const best = new Map<string, KeywordRow>();

  for (const report of reports) {
    const byKw = urlsByKeyword(report.new_urls);
    const ordered =
      report.new_keywords.length > 0
        ? report.new_keywords
        : [...byKw.keys()];

    for (const keyword of ordered) {
      const key = `${report.site_id}\0${keyword}`;
      const candidate: KeywordRow = {
        keyword,
        site: report.site_id,
        firstDate: report.date,
        urls: byKw.get(keyword) || [],
      };
      const prev = best.get(key);
      if (!prev || candidate.firstDate < prev.firstDate) {
        best.set(key, candidate);
      }
    }
  }

  return [...best.values()].sort((a, b) => {
    if (a.firstDate !== b.firstDate) return a.firstDate < b.firstDate ? -1 : 1;
    if (a.site !== b.site) return a.site < b.site ? -1 : 1;
    return a.keyword < b.keyword ? -1 : a.keyword > b.keyword ? 1 : 0;
  });
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `npm --prefix dashboard test`

Expected: PASS (all tests green).

- [ ] **Step 6: Commit**

```bash
git add dashboard/package.json dashboard/package-lock.json dashboard/src/keywordRange.ts dashboard/src/keywordRange.test.ts
git commit -m "$(cat <<'EOF'
feat: add keyword date-range helpers and tests

EOF
)"
```

If the project uses `pnpm-lock.yaml` under `dashboard/` instead, stage that lockfile.

---

### Task 2: Wire App.tsx to range-based loading

**Files:**
- Modify: `dashboard/src/App.tsx`

- [ ] **Step 1: Replace date state with range; import helpers**

At top of `dashboard/src/App.tsx`, change imports and remove unused `date` state:

```tsx
import {
  RANGE_OPTIONS,
  buildKeywordRows,
  datesInRange,
  type KeywordRow,
  type RangeKey,
} from "./keywordRange";
```

Replace:

```tsx
const [dates, setDates] = useState<string[]>([]);
const [date, setDate] = useState("");
```

with:

```tsx
const [dates, setDates] = useState<string[]>([]);
const [range, setRange] = useState<RangeKey>("1d");
const [partialLoadError, setPartialLoadError] = useState(false);
```

- [ ] **Step 2: Fix `refreshCore` (no longer seeds `date`)**

```tsx
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
}, []);
```

- [ ] **Step 3: Replace the reports `useEffect` to load a date window**

```tsx
useEffect(() => {
  const windowDates = datesInRange(dates, range);
  if (windowDates.length === 0) {
    setReports([]);
    setPartialLoadError(false);
    setReportsLoading(false);
    return;
  }

  let cancelled = false;
  setReportsLoading(true);
  setPartialLoadError(false);

  void wrap(async () => {
    try {
      const settled = await Promise.all(
        windowDates.map(async (d) => {
          try {
            if (siteId === ALL_SITES) {
              const { reports: summaries } = await api.listReports(d);
              const details = await Promise.all(
                summaries.map((s) =>
                  api.getReport(d, s.site_id).then(
                    (detail) => ({ ok: true as const, detail }),
                    () => ({ ok: false as const }),
                  ),
                ),
              );
              return details;
            }
            try {
              const detail = await api.getReport(d, siteId);
              return [{ ok: true as const, detail }];
            } catch {
              return [{ ok: false as const }];
            }
          } catch {
            return [{ ok: false as const }];
          }
        }),
      );

      if (cancelled) return;

      const next: ReportDetail[] = [];
      let hadFailure = false;
      for (const batch of settled) {
        for (const item of batch) {
          if (item.ok) next.push(item.detail);
          else hadFailure = true;
        }
      }
      setReports(next);
      setPartialLoadError(hadFailure);
    } finally {
      if (!cancelled) setReportsLoading(false);
    }
  });

  return () => {
    cancelled = true;
  };
}, [dates, range, siteId, wrap]);
```

- [ ] **Step 4: Derive keyword rows from helpers**

Replace the inline `keywordRows` `useMemo` with:

```tsx
const keywordRows: KeywordRow[] = useMemo(
  () => buildKeywordRows(reports),
  [reports],
);

const windowDates = useMemo(
  () => datesInRange(dates, range),
  [dates, range],
);
const hasWindowDates = windowDates.length > 0;
const hasReports = reports.length > 0;
```

Keep `trendsGroups` / copy helpers as they are (they already use `keywordRows`).

- [ ] **Step 5: Shared filter UI (both Keywords and Trends)**

Extract a small render helper inside `App` (or inline twice identically):

```tsx
const filterBar = (
  <div className="filters">
    <div className="filter-field">
      <span className="filter-label">范围</span>
      <div className="range-seg" role="group" aria-label="时间范围">
        {RANGE_OPTIONS.map(({ key, label }) => (
          <button
            key={key}
            type="button"
            className={`range-seg-btn${range === key ? " active" : ""}`}
            aria-pressed={range === key}
            onClick={() => setRange(key)}
          >
            {label}
          </button>
        ))}
      </div>
    </div>
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
);
```

In the Keywords panel:

- Change `<h2>按日新增词</h2>` → `<h2>近期新增词</h2>`
- Replace the old date/site filters block with `{filterBar}`
- Empty states:
  - `!hasWindowDates` (and not loading): `<p className="empty">该范围内暂无报告。</p>`
  - else if `!hasReports`: same empty (or keep loading path)
  - else if `keywordRows.length === 0`: `无新增关键词`
- After filters, if `partialLoadError`:  
  `<p className="notice-banner">部分日期加载失败，已显示其余结果。</p>`
- Table header: add `<th>首次日期</th>` between site (optional) and URL
- Table body cell: `<td className="mono muted">{row.firstDate}</td>`

In the Trends panel: reuse the same `{filterBar}`, same empty/partial-error messages (no date dropdown).

Remove any remaining `date` / `setDate` references.

- [ ] **Step 6: Typecheck / build**

Run:

```bash
npm --prefix dashboard test
npm --prefix dashboard run build
```

Expected: tests PASS; Vite build succeeds.

- [ ] **Step 7: Commit**

```bash
git add dashboard/src/App.tsx
git commit -m "$(cat <<'EOF'
feat: load keywords by 1d/7d/30d range in dashboard

EOF
)"
```

---

### Task 3: Styles + README

**Files:**
- Modify: `dashboard/src/styles.css`
- Modify: `README.md`

- [ ] **Step 1: CSS for range segment + filters**

In `dashboard/src/styles.css`, update `.filters` and add range styles near it:

```css
.filters {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 14rem);
  gap: 0.85rem;
  margin-bottom: 1.15rem;
  align-items: end;
}

.filter-field {
  display: grid;
  gap: 0.4rem;
}

.filter-label {
  font-size: 0.78rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--muted);
}

.range-seg {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  padding: 0.25rem;
  border: 1px solid var(--line);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.55);
}

.range-seg-btn {
  border: none;
  border-radius: 10px;
  padding: 0.55rem 0.85rem;
  cursor: pointer;
  background: transparent;
  color: var(--ink);
  font-size: 0.88rem;
  font-weight: 600;
  font-family: inherit;
}

.range-seg-btn:hover {
  background: rgba(255, 255, 255, 0.8);
}

.range-seg-btn.active {
  background: linear-gradient(180deg, #14a975 0%, var(--signal-deep) 100%);
  color: #fff;
}
```

In the existing `@media` block that adjusts `.filters` (around the mobile rules), ensure range filters still stack:

```css
.filters {
  grid-template-columns: 1fr;
}
```

- [ ] **Step 2: README one-liner**

In `README.md` features / table:

- Change Dashboard bullet from「按日看新增词」to「按最近一天 / 一周 / 一个月看新增词」
- In the page capability table, change「按日期 + 站点查看」to「按快捷范围 + 站点查看」

- [ ] **Step 3: Build again**

Run: `npm --prefix dashboard run build`

Expected: success.

- [ ] **Step 4: Commit**

```bash
git add dashboard/src/styles.css README.md
git commit -m "$(cat <<'EOF'
style: range segment control and docs for keyword windows

EOF
)"
```

---

### Task 4: Manual verification checklist

**Files:** none (manual)

- [ ] **Step 1: Run dashboard**

```bash
# terminal 1
sitemap-monitor dashboard
# terminal 2
npm --prefix dashboard run dev
```

Open `http://127.0.0.1:5173`.

- [ ] **Step 2: Verify behavior**

- [ ] Default is「最近一天」; Keywords and Trends show the same keywords set
- [ ] Switch to「最近一周」/「最近一个月」; both tabs update together (shared `range`)
- [ ] Switch site filter; `range` stays the same
- [ ] Repeated keyword across days appears once with earliest「首次日期」
- [ ] Empty / no-new-keywords / partial-failure messaging looks right if reproducible
- [ ] 「复制全部」copies deduped keywords

- [ ] **Step 3: Final commit only if manual QA found small fixes**

If fixes were needed, commit them with a clear message (e.g. `fix: …`). Otherwise stop here — feature complete.

---

## Spec coverage (self-review)

| Spec requirement | Task |
|------------------|------|
| Shared range on Keywords + Trends | Task 2 |
| Replace date dropdown with 1d/7d/30d | Task 2 |
| Default 1d | Task 2 |
| Window from latest report date | Task 1 `datesInRange` |
| Skip missing days | Task 1 + Task 2 fetch only existing dates |
| First-seen dedupe + URLs | Task 1 `buildKeywordRows` |
| 首次日期 column | Task 2 |
| Trends from deduped list | Task 2 (existing `trendsGroups`) |
| Partial load failure notice | Task 2 |
| Empty: 该范围内暂无报告 | Task 2 |
| Frontend-only / no API change | All tasks |
| README update | Task 3 |
| Unit tests for helpers | Task 1 |

No placeholders left; types (`RangeKey`, `KeywordRow`, `ReportLike`) are consistent across tasks.
