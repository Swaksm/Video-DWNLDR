#!/usr/bin/env python3
"""Video Grabber - graphical app. Run: python gui.py

Starts a tiny local web server (127.0.0.1 only) and opens the UI in a Chrome/Edge app window.
"""

import asyncio
import hmac
import json
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import core

BASE = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
TOKEN = secrets.token_urlsafe(16)


class State:
    def __init__(self):
        self.lock = threading.Lock()
        self.phase, self.busy = "ready", False
        self.items, self.version, self.session = [], 0, None
        self.logs: list = []
        self.done = self.total = 0
        self.last_seen = time.monotonic()
        self.shortcuts = None  # filled lazily: {"Desktop": bool, "Start": bool}

    def log(self, s):
        with self.lock:
            self.logs.append(str(s))

    def progress(self, d, t):
        self.done, self.total = d, t


S = State()


def run_job(factory, phase, on_ok, t):
    with S.lock:
        if S.busy:
            return False
        S.busy, S.phase, S.done, S.total = True, phase, 0, 0

    def work():
        end = "ready"
        try:
            on_ok(asyncio.run(factory()))
            end = "done" if phase == "downloading" else "ready"
        except Exception as e:
            S.log(t("error", err=str(e).splitlines()[0] if str(e) else e))
            end = "error"
        with S.lock:
            S.busy, S.phase = False, end

    threading.Thread(target=work, daemon=True).start()
    return True


def api_scan(body):
    t = core.Translator(body.get("lang", "en"))
    url = str(body.get("url", "")).strip()
    if "://" not in url:
        url = "https://" + url
    if not url.lower().startswith(("http://", "https://")):
        return {"ok": False}
    wait = max(5, min(300, int(body.get("wait") or 20)))
    cdp = body.get("cdp") or None

    def finish(res):
        items, ua, cookies = res
        for i, it in enumerate(items):
            it["id"] = i
            it["name"] = core.safe_name(it["url"], it["ext"] or "mp4")
        with S.lock:
            S.items, S.session = items, (url, ua, cookies)
            S.version += 1
        if not items:
            S.log(t("none"))

    with S.lock:
        S.items, S.session = [], None
        S.version += 1
    return {"ok": run_job(lambda: core.detect(t, url, cdp, wait, S.log), "scanning", finish, t)}


def api_download(body):
    t = core.Translator(body.get("lang", "en"))
    if not S.session:
        return {"ok": False}
    ids = {int(i) for i in body.get("ids", [])}
    chosen = [it for it in S.items if it["id"] in ids]
    if not chosen:
        return {"ok": False}
    page_url, ua, cookies = S.session
    out = Path(body.get("out") or Path.home() / "Downloads").expanduser()

    async def job():
        await core.download_items(t, chosen, page_url, ua, cookies, out, S.log, S.progress)

    return {"ok": run_job(job, "downloading", lambda _r: None, t)}


def open_folder(path: str):
    p = Path(path or Path.home() / "Downloads").expanduser()
    p.mkdir(parents=True, exist_ok=True)
    if sys.platform.startswith("win"):
        os.startfile(p)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(p)])
    else:
        subprocess.Popen(["xdg-open", str(p)])


INSTALL_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Programs" / "VideoGrabber"
INSTALL_EXE = INSTALL_DIR / "VideoGrabber.exe"
CAN_INSTALL = sys.platform.startswith("win") and getattr(sys, "frozen", False)

_PS_SHORTCUTS = r"""
$ws = New-Object -ComObject WScript.Shell
$dirs = @{ Desktop = [Environment]::GetFolderPath('Desktop'); Start = (Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs') }
foreach ($k in 'Desktop', 'Start') {
  $lnk = Join-Path $dirs[$k] 'Video Grabber.lnk'
  if ($env:VG_MODE -eq 'check') { Write-Output ($k + '=' + [int](Test-Path $lnk)); continue }
  if ([Environment]::GetEnvironmentVariable('VG_' + $k) -eq '1') {
    $s = $ws.CreateShortcut($lnk)
    $s.TargetPath = $env:VG_EXE; $s.WorkingDirectory = $env:VG_DIR
    $s.IconLocation = $env:VG_EXE + ',0'; $s.Description = 'Video Grabber'; $s.Save()
  } else { Remove-Item $lnk -ErrorAction SilentlyContinue }
}
"""


def _powershell(**env):
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", _PS_SHORTCUTS],
                       env={**os.environ, **env}, capture_output=True, text=True, timeout=30,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return r.stdout


def shortcut_status():
    if not CAN_INSTALL:
        return {"Desktop": False, "Start": False}
    out = _powershell(VG_MODE="check")
    return {k: v == "1" for k, v in (line.strip().split("=") for line in out.splitlines() if "=" in line)}


def api_shortcuts(body):
    if not CAN_INSTALL:
        return {"ok": False}
    want_desktop, want_start = bool(body.get("desktop")), bool(body.get("start"))
    exe = Path(sys.executable).resolve()
    if (want_desktop or want_start) and exe != INSTALL_EXE.resolve():
        INSTALL_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(exe, INSTALL_EXE)  # shortcuts must survive the user deleting the downloaded file
    target = INSTALL_EXE if INSTALL_EXE.exists() else exe
    _powershell(VG_DESKTOP="1" if want_desktop else "0", VG_START="1" if want_start else "0",
                VG_EXE=str(target), VG_DIR=str(target.parent))
    S.shortcuts = shortcut_status()
    return {"ok": True}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def allowed(self, need_token=True):
        if self.headers.get("Host", "").split(":")[0] not in ("127.0.0.1", "localhost"):
            return False  # blocks DNS-rebinding
        return not need_token or hmac.compare_digest(self.headers.get("X-Token", ""), TOKEN)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/" and self.allowed(False):
            html = (BASE / "ui.html").read_text(encoding="utf-8").replace("__TOKEN__", TOKEN)
            return self.send(200, html, "text/html")
        if u.path == "/api/state" and self.allowed():
            S.last_seen = time.monotonic()
            since = int(parse_qs(u.query).get("since", ["0"])[0])
            with S.lock:
                payload = {
                    "phase": S.phase, "busy": S.busy, "version": S.version,
                    "items": [{k: it[k] for k in ("id", "kind", "ext", "size", "source", "url", "name")} for it in S.items],
                    "logs": S.logs[since:], "next": len(S.logs), "done": S.done, "total": S.total,
                    "default_out": str(Path.home() / "Downloads"),
                    "can_install": CAN_INSTALL, "shortcuts": S.shortcuts,
                }
            return self.send(200, json.dumps(payload))
        self.send(404, "{}")

    def do_POST(self):
        if not self.allowed():
            return self.send(403, "{}")
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            route = urlparse(self.path).path
            if route == "/api/scan":
                res = api_scan(body)
            elif route == "/api/download":
                res = api_download(body)
            elif route == "/api/shortcuts":
                res = api_shortcuts(body)
            elif route == "/api/open-folder":
                open_folder(body.get("out", ""))
                res = {"ok": True}
            else:
                return self.send(404, "{}")
            self.send(200, json.dumps(res))
        except Exception as e:
            self.send(500, json.dumps({"ok": False, "error": str(e)}))


def find_browser():
    paths = []
    if sys.platform.startswith("win"):
        for env in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
            base = os.environ.get(env)
            if base:
                paths += [Path(base, "Google/Chrome/Application/chrome.exe"), Path(base, "Microsoft/Edge/Application/msedge.exe")]
    elif sys.platform == "darwin":
        paths += [Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
                  Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge")]
    else:
        paths += [Path(p) for n in ("google-chrome", "chromium", "chromium-browser", "microsoft-edge") if (p := shutil.which(n))]
    return next((str(p) for p in paths if p.exists()), None)


def main():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    threading.Thread(target=server.serve_forever, daemon=True).start()
    threading.Thread(target=lambda: setattr(S, "shortcuts", shortcut_status()), daemon=True).start()

    browser = find_browser()
    if browser:
        profile = tempfile.mkdtemp(prefix="videograbber_ui_")
        try:
            subprocess.Popen([browser, f"--app={url}", "--window-size=1000,860", f"--user-data-dir={profile}",
                              "--no-first-run", "--no-default-browser-check"]).wait()
        finally:
            shutil.rmtree(profile, ignore_errors=True)
        return

    webbrowser.open(url)  # fallback: exit once the tab stops polling
    print(f"Video Grabber: {url}")
    try:
        while time.monotonic() - S.last_seen < 90:
            time.sleep(2)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
