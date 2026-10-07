# video-grabber

**English** | [Français](README.fr.md)

Paste a page URL: the script detects its videos, you pick one, it downloads.
Works with cookie / Referer / temporary-token protection (it downloads from inside the browser session).

Formats: mp4, webm, mkv, mov, avi, flv, mp3, m4a... plus HLS (`.m3u8`) and DASH (`.mpd`) streams.

## Install (once)

Requirements: [Python 3.10+](https://www.python.org/downloads/) (tick "Add to PATH" on Windows). [ffmpeg](https://ffmpeg.org/download.html) for HLS/DASH streams.

**Windows**: double-click `install.bat`

**Mac / Linux**:
```bash
sh install.sh
```

## Usage

**Windows**: double-click `run.bat`, or
```bash
python download_video.py
```

**Mac / Linux**:
```bash
sh run.sh
```

1. Paste the page URL.
2. A browser opens: solve the Cloudflare captcha if it shows up, and start playback if the video doesn't start by itself.
3. After the scan (20 s), the list is shown: type a number (`1`), several (`1,3`) or `all`.
4. Files are saved in `downloads/`.
5. The window stays open: paste another URL to scan again, `lang` switches English/French, `q` quits.

## Options

```bash
python download_video.py "https://site.com/page" --wait 40 --out my_videos
```

| Option | Purpose | Default |
|---|---|---|
| `--wait N` | scan duration in seconds | 20 |
| `--out DIR` | output folder | `downloads` |
| `--lang en\|fr` | interface language | `en` |
| `--cdp URL` | attach to your running Chrome | — |

## If Cloudflare blocks you

Use your real Chrome. Start it in debug mode:

```bash
# Windows
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir=%TEMP%\chrome-dbg

# Mac
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-dbg
```

Pass the challenge by hand in that window, then:
```bash
python download_video.py --cdp http://localhost:9222
```

## Troubleshooting

| Problem | Fix |
|---|---|
| `playwright` not found | use `python -m playwright install chromium` |
| No video detected | use `--wait 40` and press play during the scan |
| 403 / 404 error | token expired: rerun and pick faster |
| HLS/DASH download fails | install ffmpeg |

## Disclaimer

Only use this for content you are allowed to download. You are responsible for complying with site terms of service and copyright law.

## License

[MIT](LICENSE)
