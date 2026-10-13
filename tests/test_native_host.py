import io
import json
import struct
import subprocess
import sys
from pathlib import Path

import native_host
import installer
from conftest import SiteHandler

ROOT = Path(__file__).resolve().parent.parent


def frame(obj):
    data = json.dumps(obj).encode()
    return struct.pack("<I", len(data)) + data


def test_message_framing_roundtrip():
    buf = io.BytesIO()
    native_host.write_msg(buf, {"type": "ping", "x": "é"})
    buf.seek(0)
    assert native_host.read_msg(buf) == {"type": "ping", "x": "é"}
    assert native_host.read_msg(buf) is None  # browser closed the pipe


def test_ping_and_bad_request():
    out = []
    native_host.handle({"type": "ping"}, out.append)
    native_host.handle({"type": "download", "url": "file:///etc/passwd"}, out.append)
    native_host.handle({"type": "nope"}, out.append)
    assert out[0] == {"type": "pong", "version": installer.VERSION}
    assert out[1]["type"] == "error" and out[2]["type"] == "error"


def test_download_sends_referer_and_cookies(site, tmp_path, clip_bytes):
    SiteHandler.referers.clear()
    out = []
    native_host.handle({
        "type": "download", "url": site + "/ref.mp4", "out": str(tmp_path), "referer": "https://host.example/page",
        "cookies": [{"domain": "127.0.0.1", "path": "/", "secure": False, "expires": 0, "name": "sid", "value": "abc"}],
    }, out.append)
    assert out[-1]["type"] == "done", out
    assert Path(out[-1]["path"]).read_bytes() == clip_bytes
    assert SiteHandler.referers and SiteHandler.referers[-1] == ("https://host.example/page", "sid=abc")
    assert not list(Path(native_host.tempfile.gettempdir()).glob("vg_cookies_*.txt"))  # cookie file removed


def test_download_error_is_reported(site, tmp_path):
    out = []
    native_host.handle({"type": "download", "url": site + "/missing.mp4", "out": str(tmp_path)}, out.append)
    assert out[-1]["type"] == "error"


def test_host_process_speaks_the_protocol():
    # Same launch the browser does: script + extension origin, JSON over stdin/stdout.
    p = subprocess.run([sys.executable, str(ROOT / "native_host.py"), "chrome-extension://x/"],
                       input=frame({"type": "ping"}), capture_output=True, timeout=60)
    assert native_host.read_msg(io.BytesIO(p.stdout)) == {"type": "pong", "version": installer.VERSION}


def test_host_manifest_allows_only_our_extension(tmp_path):
    m = native_host.host_manifest(tmp_path / "VideoGrabber.exe")
    assert m["name"] == "com.videograbber.host" and m["type"] == "stdio"
    assert m["allowed_origins"] == ["chrome-extension://ipeifcoegkmffiplbmmdidgpcojbejfk/"]


def test_extension_key_matches_host_id():
    import base64
    import hashlib
    key = json.loads((ROOT / "extension" / "manifest.json").read_text())["key"]
    digest = hashlib.sha256(base64.b64decode(key)).hexdigest()[:32]
    assert "".join("abcdefghijklmnop"[int(c, 16)] for c in digest) == native_host.EXTENSION_ID


def test_posix_register_and_unregister(tmp_path, monkeypatch):
    monkeypatch.setattr(installer, "IS_WIN", False)
    monkeypatch.setattr(native_host, "POSIX_DIRS", {sys.platform: [str(tmp_path / "chrome")], "linux": [str(tmp_path / "chrome")]})
    native_host.register(tmp_path / "host.sh", tmp_path)
    f = tmp_path / "chrome" / "NativeMessagingHosts" / "com.videograbber.host.json"
    assert json.loads(f.read_text())["path"] == str(tmp_path / "host.sh")
    native_host.unregister(tmp_path)
    assert not f.exists()
