import core


def test_url_ext():
    assert core.url_ext("https://x.com/a/video.MP4?token=1") == "mp4"
    assert core.url_ext("https://x.com/stream/master.m3u8") == "m3u8"
    assert core.url_ext("https://x.com/watch") == ""


def test_classify_direct_and_manifest():
    assert core.classify("https://x.com/a.mp4?t=1", "") == "direct"
    assert core.classify("https://x.com/a", "video/webm") == "direct"
    assert core.classify("https://x.com/a.mp3", "audio/mpeg") == "direct"
    assert core.classify("https://x.com/master.m3u8", "") == "manifest"
    assert core.classify("https://x.com/a", "application/dash+xml") == "manifest"
    assert core.classify("https://x.com/a", "application/vnd.apple.mpegurl") == "manifest"


def test_classify_ignores_segments_and_other_files():
    assert core.classify("https://x.com/seg-1.ts", "") is None
    assert core.classify("https://x.com/seg-1.m4s", "") is None
    assert core.classify("https://x.com/logo.png", "image/png") is None
    assert core.classify("https://x.com/app.js", "text/javascript") is None


def test_total_size_prefers_content_range():
    assert core.total_size({"content-range": "bytes 0-9/1234", "content-length": "10"}) == 1234
    assert core.total_size({"content-length": "99"}) == 99
    assert core.total_size({}) == 0


def test_human():
    assert core.human(0) == "?"
    assert core.human(512) == "512.0 B"
    assert core.human(1536) == "1.5 KB"
    assert core.human(5 * 1024**3) == "5.0 GB"


def test_safe_name():
    assert core.safe_name("https://x.com/a/my%20clip.mp4?x=1", "mp4") == "my clip.mp4"
    assert core.safe_name("https://x.com/a/stream", "mp4") == "stream.mp4"
    assert "/" not in core.safe_name("https://x.com/a%2Fb.mp4", "mp4")
    assert core.safe_name("https://x.com/", "mp4") == "video.mp4"


def test_parse_choice():
    items = ["a", "b", "c"]
    assert core.parse_choice("", items) == []
    assert core.parse_choice("all", items) == items
    assert core.parse_choice("TOUT", items) == items
    assert core.parse_choice("1,3", items) == ["a", "c"]
    assert core.parse_choice("2", items) == ["b"]
    assert core.parse_choice("4", items) is None
    assert core.parse_choice("0", items) is None
    assert core.parse_choice("abc", items) is None


def test_translations_have_same_keys():
    assert set(core.TEXTS["en"]) == set(core.TEXTS["fr"])


def test_translator_default_and_toggle():
    t = core.Translator()
    assert t.lang == "en"
    assert "Saved" in t("saved", path="x")
    t.set_lang()
    assert t.lang == "fr"
    t.set_lang("en")
    assert t.lang == "en"
    assert core.Translator("zz").lang == "en"


def test_write_netscape(tmp_path):
    f = tmp_path / "c.txt"
    core.write_netscape([{"domain": ".x.com", "path": "/", "secure": True, "expires": 12, "name": "a", "value": "b"}], f)
    lines = f.read_text().splitlines()
    assert lines[0].startswith("# Netscape")
    assert lines[1].split("\t") == [".x.com", "TRUE", "/", "TRUE", "12", "a", "b"]
