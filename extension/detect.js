// Same detection rules as core.py, so the extension and the app agree on what a video is.
const DIRECT_EXT = ["mp4", "m4v", "webm", "mkv", "mov", "avi", "flv", "wmv", "3gp", "ogv", "mpg", "mpeg", "m4a", "mp3", "aac", "ogg", "wav", "opus"];
const MANIFEST_EXT = ["m3u8", "mpd", "f4m", "ism"];
const SEGMENT_EXT = ["ts", "m4s", "cmfv", "cmfa", "aac"];
const MANIFEST_CT = ["mpegurl", "dash+xml", "f4m", "smooth"];

function urlExt(url) {
  try {
    const m = /\.([a-z0-9]{2,5})$/i.exec(new URL(url).pathname);
    return m ? m[1].toLowerCase() : "";
  } catch (e) {
    return "";
  }
}

function classify(url, ctype) {
  const ext = urlExt(url);
  ctype = (ctype || "").toLowerCase();
  if (SEGMENT_EXT.includes(ext) && !ctype.startsWith("video/") && ext !== "aac") return null;
  if (MANIFEST_EXT.includes(ext) || MANIFEST_CT.some((k) => ctype.includes(k))) return "manifest";
  if (DIRECT_EXT.includes(ext) || ctype.startsWith("video/") || ctype.startsWith("audio/")) return "direct";
  return null;
}

function totalSize(headers) {
  const cr = headers["content-range"] || "";
  const total = cr.split("/").pop();
  if (cr.includes("/") && /^\d+$/.test(total)) return Number(total);
  return Number(headers["content-length"] || 0) || 0;
}

function human(n) {
  if (!n) return "?";
  const units = ["B", "KB", "MB", "GB"];
  let i = 0;
  while (n >= 1024 && i < units.length - 1) { n /= 1024; i++; }
  return n.toFixed(1) + " " + units[i];
}

function safeName(url, extFallback) {
  let name = "";
  try {
    name = decodeURIComponent(new URL(url).pathname.split("/").pop() || "");
  } catch (e) {}
  name = (name || "video").replace(/[<>:"/\\|?*\x00-\x1f]/g, "_");
  if (!/\.[^.]+$/.test(name)) name += "." + (extFallback || "mp4");
  return name;
}

if (typeof module !== "undefined") module.exports = { urlExt, classify, totalSize, human, safeName };
