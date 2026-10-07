#!/usr/bin/env python3
"""
Paste a page URL -> the script detects all videos (mp4, webm, mkv, mov, HLS, DASH, flv, ts...),
lists them, you pick, it downloads with the cookies / Referer / User-Agent of the browser session.
When it's done you can scan another page without restarting.

Install:
  pip install playwright httpx yt-dlp
  playwright install chromium

Usage:
  python download_video.py [url] [--lang en|fr] [--cdp http://localhost:9222] [--wait 20] [--out folder]

--cdp: attach to your already-open Chrome (useful against Cloudflare). Start it with:
  Windows: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" --remote-debugging-port=9222 --user-data-dir=%TEMP%\\chrome-dbg
  Mac:     /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-dbg
"""

import argparse
import asyncio
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse, unquote

import httpx
from playwright.async_api import async_playwright

DIRECT_EXT = ("mp4", "m4v", "webm", "mkv", "mov", "avi", "flv", "wmv", "3gp", "ogv", "mpg", "mpeg", "m4a", "mp3", "aac", "ogg", "wav", "opus")
MANIFEST_EXT = ("m3u8", "mpd", "f4m", "ism")
SEGMENT_EXT = ("ts", "m4s", "cmfv", "cmfa", "aac")  # fragments: hidden from the list

EXT_RE = re.compile(r"\.([a-z0-9]{2,5})(?:[?#]|$)", re.I)
MANIFEST_CT = ("mpegurl", "dash+xml", "f4m", "smooth")

LANGS = ("en", "fr")
TEXTS = {
    "en": {
        "prompt": "\nPage URL (q = quit, lang = change language): ",
        "scan": "[i] Scanning for {n}s. Solve Cloudflare in the window if it shows up; press play if the video doesn't start.",
        "none": "[x] No video detected. Try a longer scan (--wait 40) or press play during the scan.",
        "found": "\nVideos found:",
        "hls": "HLS/DASH stream",
        "choose": "\nNumber(s) to download (e.g. 1 or 1,3 or 'all', empty = back): ",
        "invalid": "[x] Invalid choice.",
        "http": "[x] HTTP {code} - token expired or headers refused. Scan again.",
        "saved": "[+] Saved: {path}",
        "manifest": "[i] Segmented stream -> yt-dlp",
        "no_ytdlp": "[x] yt-dlp not found: pip install yt-dlp (and install ffmpeg).",
        "ytdlp_fail": "[x] yt-dlp failed (token expired? ffmpeg missing?).",
        "lang_set": "[i] Language: English",
        "error": "[x] Error: {err}",
        "bye": "Bye.",
        "source_dom": "page",
        "source_net": "network",
    },
    "fr": {
        "prompt": "\nURL de la page (q = quitter, lang = changer la langue) : ",
        "scan": "[i] Analyse pendant {n}s. Résous Cloudflare dans la fenêtre s'il apparaît ; lance la lecture si la vidéo ne démarre pas.",
        "none": "[x] Aucune vidéo détectée. Essaie une analyse plus longue (--wait 40) ou lance la lecture pendant l'analyse.",
        "found": "\nVidéos trouvées :",
        "hls": "flux HLS/DASH",
        "choose": "\nNuméro(s) à télécharger (ex: 1 ou 1,3 ou 'tout', vide = retour) : ",
        "invalid": "[x] Choix invalide.",
        "http": "[x] HTTP {code} - jeton expiré ou en-têtes refusés. Relance l'analyse.",
        "saved": "[+] Enregistré : {path}",
        "manifest": "[i] Flux segmenté -> yt-dlp",
        "no_ytdlp": "[x] yt-dlp introuvable : pip install yt-dlp (et installe ffmpeg).",
        "ytdlp_fail": "[x] yt-dlp a échoué (jeton expiré ? ffmpeg manquant ?).",
        "lang_set": "[i] Langue : Français",
        "error": "[x] Erreur : {err}",
        "bye": "Au revoir.",
        "source_dom": "page",
        "source_net": "réseau",
    },
}
ALL_WORDS = ("all", "tout", "*")


class UI:
    def __init__(self, lang: str):
        self.lang = lang if lang in LANGS else "en"

    def t(self, key: str, **kw) -> str:
        return TEXTS[self.lang][key].format(**kw)

    def set_lang(self, code: str | None) -> None:
        if code in LANGS:
            self.lang = code
        else:
            self.lang = LANGS[(LANGS.index(self.lang) + 1) % len(LANGS)]
        print(self.t("lang_set"))


def url_ext(url: str) -> str:
    m = EXT_RE.search(urlparse(url).path + ("?" if urlparse(url).query else ""))
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


async def detect(ui: UI, page_url: str, cdp, wait: int):
    found: dict[str, dict] = {}

    async with async_playwright() as p:
        if cdp:
            browser = await p.chromium.connect_over_cdp(cdp)
            context = browser.contexts[0]
        else:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context()
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
            print(ui.t("scan", n=wait))

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
    return list(found.values()), ua, cookies


async def dl_direct(ui: UI, item, headers, cookies, out_dir: Path):
    jar = httpx.Cookies()
    for c in cookies:
        jar.set(c["name"], c["value"], domain=c["domain"], path=c.get("path", "/"))
    dest = out_dir / safe_name(item["url"], item["ext"] or "mp4")
    async with httpx.AsyncClient(follow_redirects=True, cookies=jar, timeout=None) as client:
        async with client.stream("GET", item["url"], headers={**headers, "Range": "bytes=0-"}) as r:
            if r.status_code not in (200, 206):
                print(ui.t("http", code=r.status_code))
                return
            total, done = item["size"] or total_size(dict(r.headers)), 0
            with open(dest, "wb") as f:
                async for chunk in r.aiter_bytes(1 << 16):
                    f.write(chunk)
                    done += len(chunk)
                    pct = f"{done / total * 100:5.1f}%" if total else "  ?  "
                    print(f"   {pct}  {human(done)}", end="\r")
    print()
    print(ui.t("saved", path=dest))


def dl_manifest(ui: UI, item, headers, cookies, out_dir: Path):
    cj = Path(tempfile.gettempdir()) / "dlvideo_cookies.txt"
    write_netscape(cookies, cj)
    cmd = [sys.executable, "-m", "yt_dlp", "--cookies", str(cj),
           "--user-agent", headers["User-Agent"], "--referer", headers["Referer"],
           "-o", str(out_dir / "%(title,id)s.%(ext)s"), "--merge-output-format", "mp4", item["url"]]
    print(ui.t("manifest"))
    try:
        subprocess.run(cmd, check=True)
    except FileNotFoundError:
        print(ui.t("no_ytdlp"))
    except subprocess.CalledProcessError:
        print(ui.t("ytdlp_fail"))
    finally:
        cj.unlink(missing_ok=True)


def choose(ui: UI, items):
    print(ui.t("found"))
    for i, it in enumerate(items, 1):
        label = ui.t("hls") if it["kind"] == "manifest" else (it["ext"] or it["ctype"] or "?")
        u = it["url"] if len(it["url"]) < 95 else it["url"][:92] + "..."
        print(f" [{i}] {label:<16} {human(it['size']):>10}  ({ui.t(it['source'])})  {u}")
    raw = input(ui.t("choose")).strip().lower()
    if not raw:
        return []
    if raw in ALL_WORDS:
        return items
    try:
        return [items[int(x) - 1] for x in re.split(r"[,\s]+", raw) if x]
    except (ValueError, IndexError):
        print(ui.t("invalid"))
        return []


async def run_once(ui: UI, page_url: str, args, out_dir: Path) -> None:
    items, ua, cookies = await detect(ui, page_url, args.cdp, args.wait)
    if not items:
        print(ui.t("none"))
        return
    items.sort(key=lambda x: (x["kind"] != "direct", -x["size"]))

    headers = {"User-Agent": ua, "Referer": page_url, "Accept": "*/*"}
    for it in choose(ui, items):
        print(f"\n[->] {it['url'][:100]}")
        if it["kind"] == "manifest":
            dl_manifest(ui, it, headers, cookies, out_dir)
        else:
            await dl_direct(ui, it, headers, cookies, out_dir)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("page_url", nargs="?")
    ap.add_argument("--lang", choices=LANGS, default="en", help="interface language (default: en)")
    ap.add_argument("--cdp")
    ap.add_argument("--wait", type=int, default=20, help="scan duration in seconds")
    ap.add_argument("--out", default="downloads")
    args = ap.parse_args()

    ui = UI(args.lang)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    next_url = args.page_url
    while True:
        raw = (next_url or input(ui.t("prompt"))).strip()
        next_url = None
        low = raw.lower()
        if low in ("q", "quit", "exit"):
            print(ui.t("bye"))
            return
        if low == "lang" or low.startswith("lang "):
            ui.set_lang(low.split()[1] if " " in low else None)
            continue
        if not raw:
            continue
        if not re.match(r"^[a-z][a-z0-9+.-]*://", raw, re.I):
            raw = "https://" + raw
        try:
            await run_once(ui, raw, args, out_dir)
        except Exception as e:
            print(ui.t("error", err=e))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, EOFError):
        print()
