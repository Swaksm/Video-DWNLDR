importScripts("detect.js");

const key = (tabId) => "tab:" + tabId;
let queue = Promise.resolve(); // serialize storage updates: requests arrive in bursts

async function getItems(tabId) {
  const k = key(tabId);
  return (await chrome.storage.session.get(k))[k] || [];
}

async function setItems(tabId, items) {
  await chrome.storage.session.set({ [key(tabId)]: items });
  try {
    await chrome.action.setBadgeText({ tabId, text: items.length ? String(items.length) : "" });
  } catch (e) {} // tab may already be closed
}

async function onHeaders(d) {
  if (d.type === "main_frame") return setItems(d.tabId, []); // new page: start a fresh list
  if (d.statusCode !== 200 && d.statusCode !== 206) return;
  const h = {};
  for (const x of d.responseHeaders || []) h[x.name.toLowerCase()] = x.value || "";
  const kind = classify(d.url, h["content-type"]);
  const size = totalSize(h);
  if (!kind || isNoise(kind, size)) return;
  const items = await getItems(d.tabId);
  if (items.some((i) => i.url === d.url)) return;
  items.push({ url: d.url, kind, ext: urlExt(d.url), size, ctype: h["content-type"] || "" });
  await setItems(d.tabId, items);
}

chrome.webRequest.onHeadersReceived.addListener(
  (d) => {
    if (d.tabId < 0 || d.url.startsWith("blob:") || d.url.startsWith("data:")) return;
    queue = queue.then(() => onHeaders(d)).catch(() => {});
  },
  { urls: ["<all_urls>"] },
  ["responseHeaders"]
);

chrome.tabs.onRemoved.addListener((tabId) => chrome.storage.session.remove(key(tabId)));
chrome.runtime.onInstalled.addListener(() => chrome.action.setBadgeBackgroundColor({ color: "#35479E" }));

// Many media servers refuse a request without the page's Referer. chrome.downloads never sends
// one (DNR rules don't apply to it, and its `headers` option rejects Referer), but an extension
// fetch() does. So: an offscreen document fetches the file with a short-lived Referer rule, turns
// it into a blob URL, and chrome.downloads saves that. Event-driven, so a long fetch survives the
// service worker going to sleep.
async function ensureOffscreen() {
  if ((await chrome.runtime.getContexts({ contextTypes: ["OFFSCREEN_DOCUMENT"] })).length) return;
  await chrome.offscreen.createDocument({ url: "offscreen.html", reasons: ["BLOBS"], justification: "Build the downloaded video file" });
}

async function download({ url, referer, filename }) {
  const ruleId = 1 + Math.floor(Math.random() * 1e9);
  if (referer) {
    await chrome.declarativeNetRequest.updateSessionRules({
      addRules: [{
        id: ruleId,
        priority: 1,
        action: { type: "modifyHeaders", requestHeaders: [{ header: "referer", operation: "set", value: referer }] },
        condition: { requestDomains: [new URL(url).hostname], tabIds: [chrome.tabs.TAB_ID_NONE] },
      }],
    });
  }
  await chrome.storage.session.set({ ["job:" + url]: { ruleId: referer ? ruleId : 0, filename } });
  await ensureOffscreen();
  chrome.runtime.sendMessage({ target: "offscreen", type: "fetch", url });
  return { ok: true };
}

async function onFetched({ url, ok, blobUrl }) {
  const k = "job:" + url;
  const job = (await chrome.storage.session.get(k))[k];
  if (!job) return;
  await chrome.storage.session.remove(k);
  if (job.ruleId) await chrome.declarativeNetRequest.updateSessionRules({ removeRuleIds: [job.ruleId] });
  if (!ok) return;
  const id = await chrome.downloads.download({ url: blobUrl, filename: job.filename, conflictAction: "uniquify" });
  await chrome.storage.session.set({ ["dl:" + id]: blobUrl });
}

chrome.downloads.onChanged.addListener(async (delta) => {
  const state = delta.state && delta.state.current;
  if (state !== "complete" && state !== "interrupted") return;
  const k = "dl:" + delta.id;
  const blobUrl = (await chrome.storage.session.get(k))[k];
  if (!blobUrl) return;
  await chrome.storage.session.remove(k);
  chrome.runtime.sendMessage({ target: "offscreen", type: "revoke", blobUrl }).catch(() => {});
});

chrome.runtime.onMessage.addListener((msg, _sender, reply) => {
  if (!msg || msg.target === "offscreen") return;
  if (msg.type === "download") {
    download(msg).then(reply, (e) => reply({ ok: false, error: String(e && e.message || e) }));
    return true; // async reply
  }
  if (msg.type === "fetched") onFetched(msg);
});
