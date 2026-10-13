// Fetches a video with the browser's cookies (the background adds the page Referer) and hands
// back a blob URL for chrome.downloads, which is not available here.
async function grab(url) {
  try {
    const r = await fetch(url, { credentials: "include" });
    if (!r.ok) return { ok: false, error: "HTTP " + r.status };
    const total = Number(r.headers.get("content-length")) || 0;
    const reader = r.body.getReader();
    const parts = [];
    let done = 0, last = 0;
    for (;;) {
      const { value, done: end } = await reader.read();
      if (end) break;
      parts.push(value);
      done += value.length;
      if (Date.now() - last > 300) {
        last = Date.now();
        chrome.runtime.sendMessage({ type: "progress", url, done, total }).catch(() => {});
      }
    }
    const blob = new Blob(parts, { type: r.headers.get("content-type") || "application/octet-stream" });
    return { ok: true, blobUrl: URL.createObjectURL(blob) };
  } catch (e) {
    return { ok: false, error: String(e && e.message || e) };
  }
}

chrome.runtime.onMessage.addListener((msg) => {
  if (!msg || msg.target !== "offscreen") return;
  if (msg.type === "fetch") grab(msg.url).then((res) => chrome.runtime.sendMessage({ type: "fetched", url: msg.url, ...res }));
  if (msg.type === "revoke") URL.revokeObjectURL(msg.blobUrl);
});
