const FR = (navigator.language || "").toLowerCase().startsWith("fr");
const T = FR ? {
  found: (n) => n + " vidéo(s)", download: "Télécharger", working: "En cours...", saved: "Enregistré", failed: "Échec",
  empty_t: "Aucune vidéo détectée", empty_s: "Lance la lecture de la vidéo, puis rouvre ce menu.", stream: "Flux",
  hint: "Les flux HLS/DASH et YouTube passent par l'application Video Grabber.", app: "Envoyer à l'appli",
  page: "Télécharger cette page avec l'appli", appMissing: "Installe l'appli Video Grabber (1.5 ou plus) pour utiliser ce bouton.",
} : {
  found: (n) => n + " video(s)", download: "Download", working: "Downloading...", saved: "Saved", failed: "Failed",
  empty_t: "No video detected", empty_s: "Press play on the video, then open this menu again.", stream: "Stream",
  hint: "HLS/DASH streams and YouTube go through the Video Grabber app.", app: "Send to app",
  page: "Download this page with the app", appMissing: "Install the Video Grabber app (1.5 or later) to use this button.",
};

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

const buttons = new Map(); // video url -> its button, updated by progress messages

function finish(btn, ok, error) {
  btn.textContent = ok ? T.saved : T.failed;
  btn.classList.add(ok ? "ok" : "err");
  if (error === "app-missing") document.getElementById("hint").textContent = T.appMissing;
  else if (error) btn.title = error;
}

// Hand a URL to the desktop app (yt-dlp); progress comes back as messages.
async function toApp(btn, url, referer) {
  btn.disabled = true;
  btn.textContent = T.working;
  buttons.set(url, btn);
  const r = await chrome.runtime.sendMessage({ type: "send-to-app", url, referer });
  if (!r || !r.ok) finish(btn, false, r && r.error);
}

chrome.runtime.onMessage.addListener((msg) => {
  const btn = msg && buttons.get(msg.url);
  if (!btn) return;
  if (msg.type === "progress") btn.textContent = msg.total ? Math.floor((msg.done / msg.total) * 100) + " %" : human(msg.done);
  if (msg.type === "fetched") finish(btn, msg.ok, msg.error);
  if (msg.type === "done") finish(btn, true);
  if (msg.type === "error") finish(btn, false, msg.error);
});

const AUDIO_EXT = ["mp3", "m4a", "aac", "ogg", "wav", "opus"];

// Video: first frame as a thumbnail, plays muted on hover. Audio: a play button.
// Falls back to a plain tag when the server refuses the popup's request (no page Referer).
function preview(it, stream) {
  const tag = el("span", "tag" + (stream ? " stream" : ""), stream ? T.stream : it.ext || "?");
  if (stream) return tag;
  if (AUDIO_EXT.includes(it.ext) || (it.ctype || "").startsWith("audio/")) {
    const audio = new Audio(it.url);
    const play = el("button", "play", "▶");
    play.onclick = () => (audio.paused ? audio.play().catch(() => (play.disabled = true)) : audio.pause());
    audio.onplay = () => (play.textContent = "❚❚");
    audio.onpause = audio.onended = () => (play.textContent = "▶");
    return play;
  }
  const v = el("video", "thumb");
  v.muted = true;
  v.preload = "metadata";
  v.src = it.url + "#t=0.5";
  v.onmouseenter = () => v.play().catch(() => {});
  v.onmouseleave = () => v.pause();
  v.onerror = () => v.replaceWith(tag);
  return v;
}

async function main() {
  const param = Number(new URLSearchParams(location.search).get("tab"));
  const tab = param ? await chrome.tabs.get(param) : (await chrome.tabs.query({ active: true, currentWindow: true }))[0];
  const k = "tab:" + tab.id;
  const items = (await chrome.storage.session.get(k))[k] || [];
  items.sort((a, b) => (a.kind !== "direct") - (b.kind !== "direct") || b.size - a.size);

  document.getElementById("count").textContent = T.found(items.length);
  const list = document.getElementById("list");
  if (!items.length) {
    const e = el("div", "empty");
    e.append(el("b", "", T.empty_t), T.empty_s);
    list.append(e);
  }
  for (const it of items) {
    const row = el("div", "item");
    const stream = it.kind === "manifest";
    row.append(preview(it, stream));
    const name = el("div", "name");
    name.title = it.url;
    const label = (stream ? T.stream : it.ext || "?").toUpperCase();
    name.append(el("b", "", safeName(it.url, it.ext || "mp4")), el("small", "", label + " · " + human(it.size)));
    row.append(name);
    const btn = el("button", stream ? "ghost" : "", stream ? T.app : T.download);
    btn.onclick = async () => {
      if (stream) return toApp(btn, it.url, tab.url);
      btn.disabled = true;
      btn.textContent = T.working;
      buttons.set(it.url, btn);
      const r = await chrome.runtime.sendMessage({ type: "download", url: it.url, referer: tab.url, filename: safeName(it.url, it.ext || "mp4") });
      if (!r || !r.ok) finish(btn, false, r && r.error);
    };
    row.append(btn);
    list.append(row);
  }
  if (items.some((i) => i.kind === "manifest")) document.getElementById("hint").textContent = T.hint;
  const pageBtn = document.getElementById("pageBtn");
  if (/^https?:/.test(tab.url || "")) {
    pageBtn.textContent = T.page;
    pageBtn.hidden = false;
    pageBtn.onclick = () => toApp(pageBtn, tab.url, tab.url);
  }
}

main();
