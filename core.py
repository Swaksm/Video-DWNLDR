"""Shared engine for the CLI and the GUI: detect videos on a page and download them."""

import asyncio
import os
import re
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse, unquote

import httpx
from playwright.async_api import async_playwright

DIRECT_EXT = ("mp4", "m4v", "webm", "mkv", "mov", "avi", "flv", "wmv", "3gp", "ogv", "mpg", "mpeg", "m4a", "mp3", "aac", "ogg", "wav", "opus")
MANIFEST_EXT = ("m3u8", "mpd", "f4m", "ism")
SEGMENT_EXT = ("ts", "m4s", "cmfv", "cmfa", "aac")  # fragments: hidden from the list
MANIFEST_CT = ("mpegurl", "dash+xml", "f4m", "smooth")
EXT_RE = re.compile(r"\.([a-z0-9]{2,5})(?:[?#]|$)", re.I)

LANGS = ("en", "fr")
ALL_WORDS = ("all", "tout", "*")

TEXTS = {
    "en": {
        "lang_name": "English",
        "prompt": "\nPage URL (q = quit, lang = change language): ",
        "scan": "[i] Scanning for {n}s. Solve Cloudflare in the window if it shows up; press play if the video doesn't start.",
        "none": "[x] No video detected. Try a longer scan or press play during the scan.",
        "found": "\nVideos found:",
        "hls": "HLS/DASH stream",
        "choose": "\nNumber(s) to download (e.g. 1 or 1,3 or 'all', empty = back): ",
        "invalid": "[x] Invalid choice.",
        "http": "[x] HTTP {code} - token expired or headers refused. Scan again.",
        "saved": "[+] Saved: {path}",
        "manifest": "[i] Segmented stream -> yt-dlp",
        "ytdlp_fail": "[x] yt-dlp failed (token expired? ffmpeg missing?): {err}",
        "lang_set": "[i] Language: English",
        "error": "[x] Error: {err}",
        "bye": "Bye.",
        "source_dom": "page",
        "source_net": "network",
        "no_browser": "No browser available ({err}). Install Google Chrome or Microsoft Edge.",
        "title": "Video Grabber",
        "url_label": "Page URL",
        "scan_btn": "Scan page",
        "wait_label": "Scan (s)",
        "out_label": "Save to",
        "browse": "Browse...",
        "open_folder": "Open folder",
        "use_cdp": "Attach to my Chrome (--cdp)",
        "lang_label": "Language",
        "download_btn": "Download selected",
        "select_all": "Select all",
        "col_type": "Type",
        "col_size": "Size",
        "col_source": "Source",
        "col_url": "URL",
        "log_label": "Log",
        "ready": "Ready.",
        "scanning": "Scanning...",
        "found_n": "{n} video(s) found. Select and download.",
        "downloading": "Downloading...",
        "finished": "Finished.",
        "no_url": "Enter a page URL first.",
        "no_selection": "Select at least one video.",
        "tip": "Tip: if Cloudflare blocks the scan, solve the captcha in the browser window, then press play.",
    },
    "fr": {
        "lang_name": "Français",
        "prompt": "\nURL de la page (q = quitter, lang = changer la langue) : ",
        "scan": "[i] Analyse pendant {n}s. Résous Cloudflare dans la fenêtre s'il apparaît ; lance la lecture si la vidéo ne démarre pas.",
        "none": "[x] Aucune vidéo détectée. Essaie une analyse plus longue ou lance la lecture pendant l'analyse.",
        "found": "\nVidéos trouvées :",
        "hls": "flux HLS/DASH",
        "choose": "\nNuméro(s) à télécharger (ex: 1 ou 1,3 ou 'tout', vide = retour) : ",
        "invalid": "[x] Choix invalide.",
        "http": "[x] HTTP {code} - jeton expiré ou en-têtes refusés. Relance l'analyse.",
        "saved": "[+] Enregistré : {path}",
        "manifest": "[i] Flux segmenté -> yt-dlp",
        "ytdlp_fail": "[x] yt-dlp a échoué (jeton expiré ? ffmpeg manquant ?) : {err}",
        "lang_set": "[i] Langue : Français",
        "error": "[x] Erreur : {err}",
        "bye": "Au revoir.",
        "source_dom": "page",
        "source_net": "réseau",
        "no_browser": "Aucun navigateur disponible ({err}). Installe Google Chrome ou Microsoft Edge.",
        "title": "Video Grabber",
        "url_label": "URL de la page",
        "scan_btn": "Analyser la page",
        "wait_label": "Analyse (s)",
        "out_label": "Enregistrer dans",
        "browse": "Parcourir...",
        "open_folder": "Ouvrir le dossier",
        "use_cdp": "Utiliser mon Chrome (--cdp)",
        "lang_label": "Langue",
        "download_btn": "Télécharger la sélection",
        "select_all": "Tout sélectionner",
        "col_type": "Type",
        "col_size": "Taille",
        "col_source": "Source",
        "col_url": "URL",
        "log_label": "Journal",
        "ready": "Prêt.",
        "scanning": "Analyse...",
        "found_n": "{n} vidéo(s) trouvée(s). Sélectionne puis télécharge.",
        "downloading": "Téléchargement...",
        "finished": "Terminé.",
        "no_url": "Saisis d'abord l'URL d'une page.",
        "no_selection": "Sélectionne au moins une vidéo.",
        "tip": "Astuce : si Cloudflare bloque, résous le captcha dans la fenêtre du navigateur, puis lance la lecture.",
    },
}


class Translator:
    def __init__(self, lang: str = "en"):
        self.lang = lang if lang in LANGS else "en"

    def __call__(self, key: str, **kw) -> str:
        return TEXTS[self.lang][key].format(**kw)

    def set_lang(self, code=None) -> None:
        self.lang = code if code in LANGS else LANGS[(LANGS.index(self.lang) + 1) % len(LANGS)]


def url_ext(url: str) -> str:
    u = urlparse(url)
    m = EXT_RE.search(u.path + ("?" if u.query else ""))
    return m.group(1).lower() if m else ""


def classify(url: str, ctype: str):
    """Return 'direct', 'manifest' or None."""
    ext, ctype = url_ext(url), ctype.lower()
    if ext in SEGMENT_EXT and not ctype.startswith("video/") and ext != "aac":
        return None
    if ext in MANIFEST_EXT or any(k in ctype for k in MANIFEST_CT):
        return "manifest"
    if ext in DIRECT_EXT or ctype.startswith(("video/", "audio/")):
        return "direct"
    return None


def total_size(headers: dict) -> int:
    cr = headers.get("content-range", "")
    if "/" in cr and cr.rsplit("/", 1)[1].isdigit():
        return int(cr.rsplit("/", 1)[1])
    return int(headers.get("content-length", 0) or 0)


def human(n: int) -> str:
    if not n:
        return "?"
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024 or u == "GB":
            return f"{n:.1f} {u}"
        n /= 1024


def safe_name(url: str, ext_fallback: str) -> str:
    name = unquote(Path(urlparse(url).path).name) or "video"
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    if not Path(name).suffix:
        name += "." + ext_fallback
    return name


def label_for(t, item) -> str:
    return t("hls") if item["kind"] == "manifest" else (item["ext"] or item["ctype"] or "?")


def parse_choice(raw: str, items: list):
    """'all' / '1,3' -> list of items. Empty -> []. Invalid -> None."""
    raw = raw.strip().lower()
    if not raw:
        return []
    if raw in ALL_WORDS:
        return list(items)
    try:
        nums = [int(x) for x in re.split(r"[,\s]+", raw) if x]
        if any(n < 1 for n in nums):
            return None
        return [items[n - 1] for n in nums]
    except (ValueError, IndexError):
        return None


def write_netscape(cookies: list, path: Path) -> None:
    lines = ["# Netscape HTTP Cookie File"]
    for c in cookies:
        dom = c["domain"]
        lines.append("\t".join([
            dom, "TRUE" if dom.startswith(".") else "FALSE", c.get("path", "/"),
            "TRUE" if c.get("secure") else "FALSE", str(int(c.get("expires", 0) or 0)),
            c["name"], c["value"],
        ]))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def _open_browser(p, cdp, t):
    if cdp:
        browser = await p.chromium.connect_over_cdp(cdp)
        return browser, browser.contexts[0]
    last = None
    for channel in ("chrome", "msedge", None):  # system browsers first: no extra download needed
        try:
            kw = {"headless": os.environ.get("VG_HEADLESS") == "1"}  # headless only for CI/tests
            if channel:
                kw["channel"] = channel
            browser = await p.chromium.launch(**kw)
            return browser, await browser.new_context()
        except Exception as e:
            last = e
    raise RuntimeError(t("no_browser", err=str(last).splitlines()[0]))


async def detect(t, page_url: str, cdp, wait: int, log=print):
    """Open the page, collect video URLs. Returns (items, user_agent, cookies)."""
    found: dict = {}

    async with async_playwright() as p:
        browser, context = await _open_browser(p, cdp, t)
        page = await context.new_page()
        try:
            def add(url, kind, size=0, ctype="", source="source_net"):
                if url.startswith(("blob:", "data:")) or url in found:
                    return
                found[url] = {"url": url, "kind": kind, "size": size, "ctype": ctype, "ext": url_ext(url), "source": source}

            def on_response(resp):
                if resp.status not in (200, 206):
                    return
                ctype = resp.headers.get("content-type", "")
                kind = classify(resp.url, ctype)
                if kind:
                    add(resp.url, kind, total_size(resp.headers), ctype)

            context.on("response", on_response)
            await page.goto(page_url, wait_until="domcontentloaded")
            log(t("scan", n=wait))

            for _ in range(wait):
                await asyncio.sleep(1)
                for fr in page.frames:
                    try:
                        urls = await fr.evaluate(
                            "() => [...document.querySelectorAll('video,source,audio,a[href]')]"
                            ".map(e => e.currentSrc || e.src || e.href).filter(Boolean)")
                    except Exception:
                        continue
                    for u in urls:
                        kind = classify(u, "")
                        if kind:
                            add(u, kind, source="source_dom")

            ua = await page.evaluate("navigator.userAgent")
            cookies = await context.cookies()
        finally:
            await page.close()
            if not cdp:
                await browser.close()

    items = list(found.values())
    items.sort(key=lambda x: (x["kind"] != "direct", -x["size"]))
    return items, ua, cookies


async def dl_direct(t, item, headers, cookies, out_dir: Path, log=print, progress=None):
    jar = httpx.Cookies()
    for c in cookies:
        jar.set(c["name"], c["value"], domain=c["domain"], path=c.get("path", "/"))
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / safe_name(item["url"], item["ext"] or "mp4")
    async with httpx.AsyncClient(follow_redirects=True, cookies=jar, timeout=None) as client:
        async with client.stream("GET", item["url"], headers={**headers, "Range": "bytes=0-"}) as r:
            if r.status_code not in (200, 206):
                log(t("http", code=r.status_code))
                return None
            total, done, last = item["size"] or total_size(dict(r.headers)), 0, 0.0
            with open(dest, "wb") as f:
                async for chunk in r.aiter_bytes(1 << 16):
                    f.write(chunk)
                    done += len(chunk)
                    if progress and time.monotonic() - last > 0.1:
                        progress(done, total)
                        last = time.monotonic()
            if progress:
                progress(done, total)
    log(t("saved", path=dest))
    return dest


def dl_manifest(t, item, headers, cookies, out_dir: Path, log=print, progress=None):
    import yt_dlp

    out_dir.mkdir(parents=True, exist_ok=True)
    cj = Path(tempfile.gettempdir()) / "videograbber_cookies.txt"
    write_netscape(cookies, cj)

    def hook(d):
        if progress and d.get("status") == "downloading":
            progress(d.get("downloaded_bytes") or 0, d.get("total_bytes") or d.get("total_bytes_estimate") or 0)

    opts = {
        "cookiefile": str(cj),
        "http_headers": {"User-Agent": headers["User-Agent"], "Referer": headers["Referer"]},
        "outtmpl": str(out_dir / "%(title,id)s.%(ext)s"),
        "merge_output_format": "mp4",
        "progress_hooks": [hook],
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
    }
    log(t("manifest"))
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([item["url"]])
        log(t("saved", path=out_dir))
        return True
    except Exception as e:
        log(t("ytdlp_fail", err=str(e).splitlines()[0] if str(e) else e))
        return False
    finally:
        cj.unlink(missing_ok=True)


async def download_items(t, items, page_url, ua, cookies, out_dir: Path, log=print, progress=None):
    headers = {"User-Agent": ua, "Referer": page_url, "Accept": "*/*"}
    for it in items:
        log(f"\n[->] {it['url'][:100]}")
        if it["kind"] == "manifest":
            await asyncio.to_thread(dl_manifest, t, it, headers, cookies, out_dir, log, progress)
        else:
            await dl_direct(t, it, headers, cookies, out_dir, log, progress)
