"""Native Messaging host: the browser extension hands a page or stream URL (plus the user's cookies
for that site) to yt-dlp, which handles YouTube, HLS and DASH.

Protocol: each message is a 4-byte little-endian length followed by UTF-8 JSON, on stdin/stdout.
The browser starts one host process per download and passes the extension origin as argv[1].

  python native_host.py --register     register this script for Chrome, Edge, Opera and Chromium
  python native_host.py --unregister
"""

import json
import os
import shutil
import struct
import sys
import tempfile
import time
from pathlib import Path

import core
import installer

HOST_NAME = "com.videograbber.host"
EXTENSION_ID = "ipeifcoegkmffiplbmmdidgpcojbejfk"  # fixed by the "key" in extension/manifest.json
WIN_KEYS = [  # Opera reads Chrome's key
    r"Software\Google\Chrome\NativeMessagingHosts",
    r"Software\Microsoft\Edge\NativeMessagingHosts",
    r"Software\Chromium\NativeMessagingHosts",
]
POSIX_DIRS = {
    "darwin": ["~/Library/Application Support/Google/Chrome", "~/Library/Application Support/Microsoft Edge",
               "~/Library/Application Support/Chromium"],
    "linux": ["~/.config/google-chrome", "~/.config/microsoft-edge", "~/.config/chromium"],
}


def read_msg(stream):
    raw = stream.read(4)
    if len(raw) < 4:
        return None
    return json.loads(stream.read(struct.unpack("<I", raw)[0]).decode("utf-8"))


def write_msg(stream, obj):
    data = json.dumps(obj).encode("utf-8")
    stream.write(struct.pack("<I", len(data)) + data)
    stream.flush()


def ytdlp_options(msg, out_dir: Path, cookie_file: Path, hook):
    headers = {}
    if msg.get("referer"):
        headers["Referer"] = msg["referer"]
    if msg.get("userAgent"):
        headers["User-Agent"] = msg["userAgent"]
    opts = {
        "outtmpl": str(out_dir / "%(title).150B [%(id)s].%(ext)s"),
        # best quality needs ffmpeg to merge video + audio; without it take the best single file
        "format": "bv*+ba/b" if shutil.which("ffmpeg") else "b",
        "merge_output_format": "mp4",
        "noplaylist": True,
        "progress_hooks": [hook],
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "http_headers": headers,
    }
    if msg.get("cookies"):
        core.write_netscape(msg["cookies"], cookie_file)
        opts["cookiefile"] = str(cookie_file)
    return opts


def handle(msg, send):
    """Process one message from the extension; `send` writes a reply."""
    kind = msg.get("type")
    if kind == "ping":
        return send({"type": "pong", "version": installer.VERSION})
    if kind != "download" or not str(msg.get("url", "")).startswith(("http://", "https://")):
        return send({"type": "error", "error": "bad request"})

    import yt_dlp

    out_dir = Path(msg.get("out") or os.environ.get("VG_OUT") or Path.home() / "Downloads").expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix="vg_cookies_", suffix=".txt")
    os.close(fd)  # Windows can't delete a file that is still open
    cookie_file = Path(name)
    last = [0.0]

    def hook(d):
        if d.get("status") == "downloading" and time.monotonic() - last[0] > 0.3:
            last[0] = time.monotonic()
            send({"type": "progress", "done": d.get("downloaded_bytes") or 0,
                  "total": d.get("total_bytes") or d.get("total_bytes_estimate") or 0})

    try:
        with yt_dlp.YoutubeDL(ytdlp_options(msg, out_dir, cookie_file, hook)) as ydl:
            info = ydl.extract_info(msg["url"], download=True)
            downloads = info.get("requested_downloads") or [{}]
            path = downloads[0].get("filepath") or ydl.prepare_filename(info)
        send({"type": "done", "path": str(path)})
    except Exception as e:
        send({"type": "error", "error": (str(e).splitlines() or ["download failed"])[0]})
    finally:
        cookie_file.unlink(missing_ok=True)


def main():
    stdin = sys.stdin.buffer if sys.stdin else os.fdopen(0, "rb")
    stdout = sys.stdout.buffer if sys.stdout else os.fdopen(1, "wb")
    sys.stdout = sys.stderr  # nothing else may write to the protocol channel
    while (msg := read_msg(stdin)) is not None:
        handle(msg, lambda obj: write_msg(stdout, obj))


def host_manifest(exe: Path) -> dict:
    return {"name": HOST_NAME, "description": "Video Grabber", "path": str(exe), "type": "stdio",
            "allowed_origins": [f"chrome-extension://{EXTENSION_ID}/"]}


def register(exe: Path, folder: Path):
    """Tell the browsers where the host is. `exe` is what they launch."""
    manifest = json.dumps(host_manifest(exe), indent=2)
    if installer.IS_WIN:
        import winreg
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{HOST_NAME}.json"
        path.write_text(manifest, encoding="utf-8")
        for key in WIN_KEYS:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, f"{key}\\{HOST_NAME}") as k:
                winreg.SetValueEx(k, "", 0, winreg.REG_SZ, str(path))
        return
    for base in POSIX_DIRS.get(sys.platform, POSIX_DIRS["linux"]):
        d = Path(base).expanduser() / "NativeMessagingHosts"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{HOST_NAME}.json").write_text(manifest, encoding="utf-8")


def unregister(folder: Path):
    if installer.IS_WIN:
        import winreg
        for key in WIN_KEYS:
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, f"{key}\\{HOST_NAME}")
            except OSError:
                pass
        (folder / f"{HOST_NAME}.json").unlink(missing_ok=True)
        return
    for base in POSIX_DIRS.get(sys.platform, POSIX_DIRS["linux"]):
        (Path(base).expanduser() / "NativeMessagingHosts" / f"{HOST_NAME}.json").unlink(missing_ok=True)


def register_dev():
    """Running from source: browsers launch a small wrapper that runs this script with this Python."""
    folder = installer.DATA_DIR
    folder.mkdir(parents=True, exist_ok=True)
    script = Path(__file__).resolve()
    if installer.IS_WIN:
        wrapper = folder / "native_host.bat"
        wrapper.write_text(f'@echo off\r\n"{sys.executable}" "{script}" %*\r\n', encoding="utf-8")
    else:
        wrapper = folder / "native_host.sh"
        wrapper.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n', encoding="utf-8")
        wrapper.chmod(0o755)
    register(wrapper, folder)
    return wrapper


if __name__ == "__main__":
    if "--register" in sys.argv:
        print("Registered:", register_dev())
    elif "--unregister" in sys.argv:
        unregister(installer.DATA_DIR)
        print("Unregistered")
    else:
        main()
