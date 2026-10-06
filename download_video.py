#!/usr/bin/env python3
"""
Colle l'URL d'une page -> le script détecte toutes les vidéos (mp4, webm, mkv, mov,
m3u8/HLS, mpd/DASH, flv, ts...), te les liste, tu choisis, il télécharge avec les
cookies / Referer / User-Agent de la session navigateur.

Installation:
  pip install playwright httpx yt-dlp
  playwright install chromium

Usage:
  python download_video.py                      (demande l'URL)
  python download_video.py <url> [--cdp http://localhost:9222] [--wait 20] [--out dossier]

--cdp : se connecte à ton Chrome déjà ouvert (utile contre Cloudflare). Lance-le avec:
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
SEGMENT_EXT = ("ts", "m4s", "cmfv", "cmfa", "aac")  # fragments: ignorés dans la liste

EXT_RE = re.compile(r"\.([a-z0-9]{2,5})(?:[?#]|$)", re.I)
MANIFEST_CT = ("mpegurl", "dash+xml", "f4m", "smooth")


def url_ext(url: str) -> str:
    m = EXT_RE.search(urlparse(url).path + ("?" if urlparse(url).query else ""))
    return m.group(1).lower() if m else ""


def classify(url: str, ctype: str):
    """Retourne 'direct', 'manifest' ou None."""
    ext, ctype = url_ext(url), ctype.lower()
    if ext in SEGMENT_EXT and not ctype.startswith("video/") and ext != "aac":
        return None
    if ext in MANIFEST_EXT or any(k in ctype for k in MANIFEST_CT):
        return "manifest"
    if ext in DIRECT_EXT or ctype.startswith(("video/", "audio/")) or ctype == "application/octet-stream" and ext in DIRECT_EXT:
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
    for u in ("o", "Ko", "Mo", "Go"):
        if n < 1024 or u == "Go":
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


async def detect(page_url: str, cdp, wait: int):
    found: dict[str, dict] = {}

    async with async_playwright() as p:
        if cdp:
            browser = await p.chromium.connect_over_cdp(cdp)
            context = browser.contexts[0]
        else:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context()
        page = await context.new_page()

        def add(url, kind, size=0, ctype="", source="réseau"):
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
        print(f"[i] Analyse pendant {wait}s. Si Cloudflare s'affiche, résous-le dans la fenêtre ; "
              "lance la lecture de la vidéo si elle ne démarre pas seule.")

        for _ in range(wait):
            await asyncio.sleep(1)
            for fr in page.frames:  # <video>/<source>/<a> dans la page et les iframes
                try:
                    urls = await fr.evaluate(
                        "() => [...document.querySelectorAll('video,source,audio,a[href]')]"
                        ".map(e => e.currentSrc || e.src || e.href).filter(Boolean)")
                except Exception:
                    continue
                for u in urls:
                    kind = classify(u, "")
                    if kind:
                        add(u, kind, source="DOM")

        ua = await page.evaluate("navigator.userAgent")
        cookies = await context.cookies()
        await page.close()
        if not cdp:
            await browser.close()
    return list(found.values()), ua, cookies


async def dl_direct(item, headers, cookies, out_dir: Path):
    jar = httpx.Cookies()
    for c in cookies:
        jar.set(c["name"], c["value"], domain=c["domain"], path=c.get("path", "/"))
    dest = out_dir / safe_name(item["url"], item["ext"] or "mp4")
    async with httpx.AsyncClient(follow_redirects=True, cookies=jar, timeout=None) as client:
        async with client.stream("GET", item["url"], headers={**headers, "Range": "bytes=0-"}) as r:
            if r.status_code not in (200, 206):
                print(f"[x] HTTP {r.status_code} - jeton expiré ou en-têtes refusés. Relance le script.")
                return
            total, done = item["size"] or total_size(dict(r.headers)), 0
            with open(dest, "wb") as f:
                async for chunk in r.aiter_bytes(1 << 16):
                    f.write(chunk)
                    done += len(chunk)
                    pct = f"{done / total * 100:5.1f}%" if total else "  ?  "
                    print(f"   {pct}  {human(done)}", end="\r")
    print(f"\n[+] Enregistré : {dest}")


def dl_manifest(item, headers, cookies, out_dir: Path):
    cj = Path(tempfile.gettempdir()) / "dlvideo_cookies.txt"
    write_netscape(cookies, cj)
    cmd = [sys.executable, "-m", "yt_dlp", "--cookies", str(cj),
           "--user-agent", headers["User-Agent"], "--referer", headers["Referer"],
           "-o", str(out_dir / "%(title,id)s.%(ext)s"), "--merge-output-format", "mp4", item["url"]]
    print("[i] Flux segmenté -> yt-dlp")
    try:
        subprocess.run(cmd, check=True)
    except FileNotFoundError:
        print("[x] yt-dlp introuvable : pip install yt-dlp (et installe ffmpeg).")
    except subprocess.CalledProcessError:
        print("[x] yt-dlp a échoué (jeton expiré ? ffmpeg manquant ?).")
    finally:
        cj.unlink(missing_ok=True)


def choose(items):
    print("\nVidéos trouvées :")
    for i, it in enumerate(items, 1):
        label = "flux HLS/DASH" if it["kind"] == "manifest" else (it["ext"] or it["ctype"] or "?")
        u = it["url"] if len(it["url"]) < 95 else it["url"][:92] + "..."
        print(f" [{i}] {label:<14} {human(it['size']):>10}  ({it['source']})  {u}")
    raw = input("\nNuméro(s) à télécharger (ex: 1 ou 1,3 ou 'tout', vide = quitter) : ").strip().lower()
    if not raw:
        return []
    if raw in ("tout", "all", "*"):
        return items
    try:
        return [items[int(x) - 1] for x in re.split(r"[,\s]+", raw) if x]
    except (ValueError, IndexError):
        print("[x] Choix invalide.")
        return []


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("page_url", nargs="?")
    ap.add_argument("--cdp")
    ap.add_argument("--wait", type=int, default=20, help="secondes d'analyse")
    ap.add_argument("--out", default="downloads")
    a = ap.parse_args()

    page_url = a.page_url or input("URL de la page : ").strip()
    out_dir = Path(a.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    items, ua, cookies = await detect(page_url, a.cdp, a.wait)
    if not items:
        print("[x] Aucune vidéo détectée. Augmente --wait, ou lance la lecture manuellement pendant l'analyse.")
        return
    items.sort(key=lambda x: (x["kind"] != "direct", -x["size"]))

    headers = {"User-Agent": ua, "Referer": page_url, "Accept": "*/*"}
    for it in choose(items):
        print(f"\n[->] {it['url'][:100]}")
        if it["kind"] == "manifest":
            dl_manifest(it, headers, cookies, out_dir)
        else:
            await dl_direct(it, headers, cookies, out_dir)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[x] Annulé")
