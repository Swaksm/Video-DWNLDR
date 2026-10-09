# video-grabber

**English** | [Français](README.fr.md)

Paste a page URL: the tool detects its videos, you pick, it downloads.
Works with cookie / Referer / temporary-token protection (it downloads from inside the browser session).

Formats: mp4, webm, mkv, mov, avi, flv, mp3, m4a... plus HLS (`.m3u8`) and DASH (`.mpd`) streams.

Two ways to use it: a **graphical app** or the **command line**.

## Quick start (no Python needed)

1. Download `VideoGrabber.exe` (GUI) or `video-grabber-cli.exe` (command line) from the [Releases](../../releases) page.
2. Run it. Needs Google Chrome or Microsoft Edge installed (already the case on Windows).

## Graphical app

Double-click `VideoGrabber.exe` (or run `python gui.py`).

1. Paste the page URL and click **Scan page**.
2. A browser opens: solve the Cloudflare captcha if it shows up, press play if the video doesn't start.
3. Select one or more videos in the list, click **Download selected**.
4. Top right: switch language (EN / FR) and light / dark theme. Scan as many pages as you want, the window stays open.

The app runs locally (nothing is sent anywhere) and opens in its own Chrome/Edge window.

## Shortcuts and uninstall (Windows)

The first time you open `VideoGrabber.exe` it offers to add a **Start menu** entry and a **desktop shortcut** (button "Shortcuts" at the top to do it later). The app is copied to `%LOCALAPPDATA%\Programs\VideoGrabber`, no admin rights needed.

To uninstall: **Settings > Apps > Installed apps > Video Grabber > Uninstall**, or run `VideoGrabber.exe --uninstall`, or double-click `uninstall.bat`. Your downloaded videos are never deleted.

## Command line

```bash
video-grabber-cli.exe                              # interactive, asks for URLs in a loop
video-grabber-cli.exe "https://site.com/page"      # scan, then pick from the list
video-grabber-cli.exe "https://site.com/page" --pick all    # no questions: download everything
video-grabber-cli.exe "https://site.com/page" --pick 1,3    # download items 1 and 3
```

From source, replace `video-grabber-cli.exe` with `python download_video.py`.
In interactive mode: paste a URL to scan again, `lang` switches English/French, `q` quits.

| Option | Purpose | Default |
|---|---|---|
| `--pick all\|1,3` | non-interactive download | ask |
| `--wait N` | scan duration in seconds | 20 |
| `--out DIR` | output folder | `downloads` |
| `--lang en\|fr` | interface language | `en` |
| `--cdp URL` | attach to your running Chrome | — |

## Run from source

Requirements: [Python 3.10+](https://www.python.org/downloads/) (tick "Add to PATH" on Windows). [ffmpeg](https://ffmpeg.org/download.html) for HLS/DASH streams.

```bash
pip install -r requirements.txt
python gui.py                 # graphical app
python download_video.py      # command line
```

Windows shortcuts: `install.bat` then `run.bat`. Mac / Linux: `sh install.sh` then `sh run.sh`.

## Build the executables

```bash
build.bat        # Windows
sh build.sh      # Mac / Linux
```

Results are in `dist/` (`VideoGrabber`, `video-grabber-cli`).

## Tests

```bash
pip install pytest
python -m pytest
```

The same tests run on GitHub Actions (Linux + Windows) on every push; the workflow also builds the Windows executables.

## If Cloudflare blocks you

Use your real Chrome. Start it in debug mode:

```bash
# Windows
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir=%TEMP%\chrome-dbg

# Mac
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-dbg
```

Pass the challenge by hand in that window, then tick **Attach to my Chrome** in the app, or use `--cdp http://localhost:9222` in the CLI.

## Troubleshooting

| Problem | Fix |
|---|---|
| No video detected | increase scan time and press play during the scan |
| 403 / 404 error | token expired: scan again and download faster |
| HLS/DASH download fails | install ffmpeg |
| "No browser available" | install Google Chrome or Microsoft Edge |

## Disclaimer

Only use this for content you are allowed to download. You are responsible for complying with site terms of service and copyright law.

## License

[MIT](LICENSE)
