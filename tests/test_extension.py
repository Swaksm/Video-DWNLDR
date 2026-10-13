"""Loads extension/ into Playwright's Chromium (branded Chrome ignores --load-extension)."""

import time
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

from conftest import SiteHandler

EXT = str(Path(__file__).resolve().parent.parent / "extension")
pytestmark = pytest.mark.browser


@pytest.fixture(scope="module")
def ext(tmp_path_factory):
    with sync_playwright() as p:
        try:
            ctx = p.chromium.launch_persistent_context(
                str(tmp_path_factory.mktemp("profile")), channel="chromium", headless=True,
                args=[f"--disable-extensions-except={EXT}", f"--load-extension={EXT}"],
            )
        except Exception as e:  # Playwright's Chromium not installed
            pytest.skip(str(e).splitlines()[0])
        sw = ctx.service_workers[0] if ctx.service_workers else ctx.wait_for_event("serviceworker")
        yield ctx, sw
        ctx.close()


def wait_for(fn, timeout=10):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        value = fn()
        if value:
            return value
        time.sleep(0.2)
    return fn()


def tab_items(sw, url):
    return sw.evaluate(
        """async (url) => {
            const [tab] = await chrome.tabs.query({ url: url + '*' });
            if (!tab) return null;
            const k = 'tab:' + tab.id;
            return { tabId: tab.id, items: (await chrome.storage.session.get(k))[k] || [] };
        }""",
        url,
    )


def test_detects_video_in_background(ext, site):
    ctx, sw = ext
    page = ctx.new_page()
    page.goto(site + "/")
    state = wait_for(lambda: (r := tab_items(sw, site + "/")) and r["items"] and r)
    assert [i["url"] for i in state["items"]] == [site + "/clip.mp4"]
    assert state["items"][0]["kind"] == "direct" and state["items"][0]["ext"] == "mp4"
    page.close()


def test_popup_lists_video(ext, site):
    ctx, sw = ext
    page = ctx.new_page()
    page.goto(site + "/")
    state = wait_for(lambda: (r := tab_items(sw, site + "/")) and r["items"] and r)
    ext_id = sw.url.split("/")[2]
    popup = ctx.new_page()
    popup.goto(f"chrome-extension://{ext_id}/popup.html?tab={state['tabId']}")
    popup.wait_for_selector(".item")
    assert popup.locator(".item b").first.text_content() == "clip.mp4"
    button = popup.locator("button").first
    assert button.text_content() in ("Download", "Télécharger")
    button.click()
    popup.wait_for_function("() => document.querySelector('button').classList.contains('ok')", timeout=15000)
    assert button.text_content() in ("Saved", "Enregistré")
    popup.close()
    page.close()


def test_download_sends_referer_and_cookies_and_saves_file(ext, site, clip_bytes):
    ctx, sw = ext
    ctx.add_cookies([{"name": "sid", "value": "abc", "url": site}])
    SiteHandler.referers.clear()
    result = sw.evaluate(
        "(a) => download({ url: a.url, referer: a.ref, filename: 'ref.mp4' })",
        {"url": site + "/ref.mp4", "ref": "https://host.example/page"},
    )
    assert result["ok"], result
    assert wait_for(lambda: SiteHandler.referers) == [("https://host.example/page", "sid=abc")]
    # Playwright renames downloads to a GUID, so match on the blob URL instead of the file name.
    item = wait_for(lambda: sw.evaluate(
        "async () => (await chrome.downloads.search({ state: 'complete' })).find(d => d.url.startsWith('blob:'))"))
    assert item and item["bytesReceived"] == len(clip_bytes), sw.evaluate("() => chrome.downloads.search({})")
    rules = sw.evaluate("() => chrome.declarativeNetRequest.getSessionRules()")
    assert rules == []  # the temporary Referer rule is cleaned up
