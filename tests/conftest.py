import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

CLIP = b"\x00\x01video-bytes" * 5000
PAGE = b'<html><body><video src="clip.mp4" autoplay muted></video></body></html>'


class SiteHandler(BaseHTTPRequestHandler):
    """Test site: /  -> page with a video, /clip.mp4 -> open video, /secret.mp4 -> needs Referer + cookie + UA."""

    def log_message(self, *a):
        pass

    def _send(self, code, body=b"", ctype="text/plain"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/":
            self._send(200, PAGE, "text/html")
        elif self.path == "/clip.mp4":
            self._send(200, CLIP, "video/mp4")
        elif self.path == "/secret.mp4":
            ok = (
                self.headers.get("Referer") == "https://host.example/page"
                and "sid=abc" in self.headers.get("Cookie", "")
                and self.headers.get("User-Agent") == "TestUA/1.0"
            )
            self._send(200, CLIP, "video/mp4") if ok else self._send(403)
        else:
            self._send(404)


@pytest.fixture(scope="session")
def site():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), SiteHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


@pytest.fixture
def clip_bytes():
    return CLIP
