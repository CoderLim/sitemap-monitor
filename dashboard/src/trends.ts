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

/** Open one browser tab per URL from a single click (user-gesture) handler. */
export function openUrlsInNewTabs(urls: string[]): number {
  if (urls.length === 0) return 0;

  const stamp = `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
  const isMac = /Mac|iPhone|iPad|iPod/.test(navigator.platform);
  let opened = 0;

  for (const [index, url] of urls.entries()) {
    const windowName = `sm_trends_${stamp}_${index}`;
    // Do not pass "noopener" here — it makes window.open return null even on
    // success, which would trigger the fallback and open each link twice.
    const tab = window.open(url, windowName);
    if (tab) {
      tab.opener = null;
      opened += 1;
      continue;
    }

    const link = document.createElement("a");
    link.href = url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    document.body.appendChild(link);
    link.dispatchEvent(
      new MouseEvent("click", {
        view: window,
        bubbles: true,
        cancelable: true,
        ...(isMac ? { metaKey: true } : { ctrlKey: true }),
      }),
    );
    document.body.removeChild(link);
    opened += 1;
  }

  return opened;
}
