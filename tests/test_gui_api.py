import http.client
import json
import threading
from http.server import ThreadingHTTPServer

import pytest

import gui


@pytest.fixture(scope="module")
def ui():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), gui.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv.server_address[1]
    srv.shutdown()


def call(port, method, path, headers=None, body=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    h = dict(headers or {})
    payload = json.dumps(body) if body is not None else None
    if payload:
        h["Content-Type"] = "application/json"
    conn.request(method, path, body=payload, headers=h)
    r = conn.getresponse()
    data = r.read().decode()
    conn.close()
    return r.status, data


def test_index_serves_ui_with_token(ui):
    status, html = call(ui, "GET", "/")
    assert status == 200
    assert gui.TOKEN in html and "__TOKEN__" not in html
    assert "Video Grabber" in html


def test_state_requires_token(ui):
    assert call(ui, "GET", "/api/state")[0] == 403
    assert call(ui, "GET", "/api/state", {"X-Token": "wrong"})[0] == 403


def test_state_with_token(ui):
    status, data = call(ui, "GET", "/api/state?since=0", {"X-Token": gui.TOKEN})
    state = json.loads(data)
    assert status == 200
    assert state["phase"] == "ready" and state["items"] == [] and state["busy"] is False


def test_post_requires_token(ui):
    assert call(ui, "POST", "/api/scan", body={"url": "https://x.com"})[0] == 403
    assert call(ui, "POST", "/api/download", {"X-Token": "wrong"}, {"ids": [0]})[0] == 403


def test_foreign_host_header_is_rejected(ui):
    # protects against DNS rebinding: a web page on another domain must not reach the API
    status, _ = call(ui, "GET", "/api/state", {"X-Token": gui.TOKEN, "Host": "evil.example"})
    assert status == 403
    assert call(ui, "GET", "/", {"Host": "evil.example"})[0] == 403


def test_download_without_scan_is_refused(ui):
    status, data = call(ui, "POST", "/api/download", {"X-Token": gui.TOKEN}, {"ids": [0], "lang": "en"})
    assert status == 200 and json.loads(data)["ok"] is False


def test_unknown_route(ui):
    assert call(ui, "POST", "/api/nope", {"X-Token": gui.TOKEN}, {})[0] == 404
