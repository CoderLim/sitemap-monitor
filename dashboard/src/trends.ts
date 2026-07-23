/** Chunk keywords and build Google Trends explore URLs. */

export function chunkKeywords(keywords: string[], size = 5): string[][] {
  if (size < 1) throw new Error("chunk size must be >= 1");
  const chunks: string[][] = [];
  for (let i = 0; i < keywords.length; i += size) {
    chunks.push(keywords.slice(i, i + size));
  }
  return chunks;
}

/** https://trends.google.com/trends/explore?date=&q=a,b,c,d,e */
export function googleTrendsUrl(keywords: string[]): string {
  const q = keywords.map((kw) => encodeURIComponent(kw)).join(",");
  return `https://trends.google.com/trends/explore?date=&q=${q}`;
}
