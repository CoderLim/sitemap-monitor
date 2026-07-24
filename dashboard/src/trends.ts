/** Chunk keywords and build Google Trends explore URLs. */

/** Fixed baseline term prepended to every Trends compare link. */
export const TRENDS_BASELINE = "gpts";

/** Google Trends allows 5 terms; we use baseline + up to 4 keywords. */
export const TRENDS_KEYWORD_CHUNK = 4;

export function chunkKeywords(
  keywords: string[],
  size = TRENDS_KEYWORD_CHUNK,
): string[][] {
  if (size < 1) throw new Error("chunk size must be >= 1");
  const chunks: string[][] = [];
  for (let i = 0; i < keywords.length; i += size) {
    chunks.push(keywords.slice(i, i + size));
  }
  return chunks;
}

/** https://trends.google.com/trends/explore?date=&q=gpts,a,b,c,d */
export function googleTrendsUrl(keywords: string[]): string {
  const q = [TRENDS_BASELINE, ...keywords]
    .map((kw) => encodeURIComponent(kw))
    .join(",");
  return `https://trends.google.com/trends/explore?date=&q=${q}`;
}
