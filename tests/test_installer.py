import json
import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

import gui
import installer
from test_gui_api import call


def test_install_dir_is_always_a_videograbber_subfolder(tmp_path):
    assert installer.resolve_install_dir(tmp_path) == tmp_path / "VideoGrabber"
    assert installer.resolve_install_dir(tmp_path / "VideoGrabber") == tmp_path / "VideoGrabber"
    assert installer.resolve_install_dir(tmp_path / "videograbber") == tmp_path / "videograbber"
    assert installer.resolve_install_dir("") == installer.DEFAULT_DIR
    assert installer.resolve_install_dir(None) == installer.DEFAULT_DIR


def test_install_dir_must_be_absolute():
    with pytest.raises(ValueError):
        installer.resolve_install_dir("relative/path")


def test_not_installed_by_default_off_windows():
    if not installer.IS_WIN:
        assert installer.installed_dir() is None
        assert installer.shortcut_status() == {"Desktop": False, "Start": False}
        assert installer.pick_folder() == ""


@pytest.fixture
def ui(tmp_path, monkeypatch):
    monkeypatch.setattr(gui, "SETTINGS_FILE", tmp_path / "settings.json")
    srv = ThreadingHTTPServer(("127.0.0.1", 0), gui.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv.server_address[1]
    srv.shutdown()


H = {"X-Token": gui.TOKEN}


def test_settings_roundtrip_and_whitelist(ui, tmp_path):
    assert call(ui, "POST", "/api/settings", H, {"lang": "fr", "theme": "dark", "evil": "x"})[0] == 200
    saved = json.loads((tmp_path / "settings.json").read_text())
    assert saved == {"lang": "fr", "theme": "dark"}
    _, html = call(ui, "GET", "/")
    assert '"lang": "fr"' in html and "__SETTINGS__" not in html


def test_settings_require_token(ui):
    assert call(ui, "POST", "/api/settings", {}, {"lang": "fr"})[0] == 403


def test_settings_file_corrupt_is_ignored(ui, tmp_path):
    (tmp_path / "settings.json").write_text("{not json")
    assert gui.load_settings() == {}
    assert call(ui, "GET", "/")[0] == 200


def test_state_exposes_install_info(ui):
    _, data = call(ui, "GET", "/api/state?since=0", H)
    inst = json.loads(data)["install"]
    assert {"can", "dir", "default_dir", "shortcuts"} <= set(inst)
    assert inst["default_dir"] == str(installer.DEFAULT_DIR)


def test_install_refused_when_not_a_packaged_windows_app(ui):
    status, data = call(ui, "POST", "/api/install", H, {"dir": str(Path.home()), "desktop": True, "start": True})
    assert status == 200 and json.loads(data)["ok"] is False


@pytest.mark.skipif(sys.platform.startswith("win"), reason="no folder dialog needed off Windows")
def test_pick_folder_off_windows_returns_empty(ui):
    status, data = call(ui, "POST", "/api/pick-folder", H, {"initial": ""})
    assert status == 200 and json.loads(data)["path"] == ""
