import asyncio

import pytest

import core

T = core.Translator("en")
HEADERS = {"User-Agent": "TestUA/1.0", "Referer": "https://host.example/page", "Accept": "*/*"}
COOKIES = [{"name": "sid", "value": "abc", "domain": "127.0.0.1", "path": "/"}]


def item(url):
    return {"url": url, "kind": "direct", "size": 0, "ctype": "video/mp4", "ext": "mp4", "source": "source_net"}


def test_download_with_referer_cookie_and_ua(site, tmp_path, clip_bytes):
    dest = asyncio.run(core.dl_direct(T, item(site + "/secret.mp4"), HEADERS, COOKIES, tmp_path, log=lambda s: None))
    assert dest == tmp_path / "secret.mp4"
    assert dest.read_bytes() == clip_bytes


def test_download_rejected_without_cookie(site, tmp_path):
    logs = []
    dest = asyncio.run(core.dl_direct(T, item(site + "/secret.mp4"), HEADERS, [], tmp_path, log=logs.append))
    assert dest is None
    assert any("403" in s for s in logs)
    assert not (tmp_path / "secret.mp4").exists()


def test_progress_reaches_total(site, tmp_path, clip_bytes):
    seen = []
    asyncio.run(core.dl_direct(T, item(site + "/clip.mp4"), HEADERS, [], tmp_path, log=lambda s: None,
                               progress=lambda d, t: seen.append((d, t))))
    assert seen[-1][0] == len(clip_bytes)


def test_download_items_creates_output_dir(site, tmp_path, clip_bytes):
    out = tmp_path / "nested" / "dir"
    asyncio.run(core.download_items(T, [item(site + "/clip.mp4")], "https://host.example/page", "TestUA/1.0", [], out,
                                    log=lambda s: None))
    assert (out / "clip.mp4").read_bytes() == clip_bytes


@pytest.mark.browser
def test_detect_finds_video_on_page(site, monkeypatch):
    monkeypatch.setenv("VG_HEADLESS", "1")
    try:
        items, ua, cookies = asyncio.run(core.detect(T, site + "/", None, 3, log=lambda s: None))
    except RuntimeError as e:  # no usable browser on this machine
        pytest.skip(str(e))
    assert [i["url"] for i in items] == [site + "/clip.mp4"]
    assert items[0]["kind"] == "direct" and items[0]["ext"] == "mp4"
    assert "Mozilla" in ua
