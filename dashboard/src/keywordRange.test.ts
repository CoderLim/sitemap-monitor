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
