#!/usr/bin/env python3
"""
Video Grabber - command line.

  python download_video.py                         interactive (asks for URLs, loops)
  python download_video.py URL                     scan URL, then pick from the list
  python download_video.py URL --pick all          non-interactive: download everything found
  python download_video.py URL --pick 1,3          non-interactive: download items 1 and 3

Options: --lang en|fr  --wait 20  --out downloads  --cdp http://localhost:9222
(For the graphical version run: python gui.py)
"""

import argparse
import asyncio
import re
import sys
from pathlib import Path

import core


def show(t, items):
    print(t("found"))
    for i, it in enumerate(items, 1):
        u = it["url"] if len(it["url"]) < 95 else it["url"][:92] + "..."
        print(f" [{i}] {core.label_for(t, it):<16} {core.human(it['size']):>10}  ({t(it['source'])})  {u}")


def cli_progress(done, total):
    pct = f"{done / total * 100:5.1f}%" if total else "  ?  "
    print(f"   {pct}  {core.human(done)}", end="\r")


async def run_once(t, page_url, args, out_dir):
    items, ua, cookies = await core.detect(t, page_url, args.cdp, args.wait)
    if not items:
        print(t("none"))
        return False
    show(t, items)

    if args.pick:
        chosen = core.parse_choice(args.pick, items)
    else:
        chosen = core.parse_choice(input(t("choose")), items)
    if chosen is None:
        print(t("invalid"))
        return False
    def log(s):
        print(" " * 30, end="\r")
        print(s)

    await core.download_items(t, chosen, page_url, ua, cookies, out_dir, log=log, progress=cli_progress)
    print()
    return bool(chosen)


async def main():
    ap = argparse.ArgumentParser(description="Detect and download videos from a web page.")
    ap.add_argument("page_url", nargs="?")
    ap.add_argument("--pick", help="non-interactive: 'all' or item numbers like 1,3")
    ap.add_argument("--lang", choices=core.LANGS, default="en", help="interface language (default: en)")
    ap.add_argument("--cdp", help="attach to your Chrome, e.g. http://localhost:9222")
    ap.add_argument("--wait", type=int, default=20, help="scan duration in seconds")
    ap.add_argument("--out", default="downloads", help="output folder")
    args = ap.parse_args()

    t = core.Translator(args.lang)
    out_dir = Path(args.out)

    if args.page_url and args.pick:  # one-shot mode for scripts
        ok = await run_once(t, args.page_url, args, out_dir)
        sys.exit(0 if ok else 1)

    next_url = args.page_url
    while True:
        raw = (next_url or input(t("prompt"))).strip()
        next_url = None
        low = raw.lower()
        if low in ("q", "quit", "exit"):
            print(t("bye"))
            return
        if low == "lang" or low.startswith("lang "):
            t.set_lang(low.split()[1] if " " in low else None)
            print(t("lang_set"))
            continue
        if not raw:
            continue
        if not re.match(r"^[a-z][a-z0-9+.-]*://", raw, re.I):
            raw = "https://" + raw
        try:
            await run_once(t, raw, args, out_dir)
        except Exception as e:
            print(t("error", err=e))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, EOFError):
        print()
