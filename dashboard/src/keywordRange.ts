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
