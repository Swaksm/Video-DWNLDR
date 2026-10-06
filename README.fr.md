# video-grabber

[English](README.md) | **Français**

Colle l'URL d'une page : le script détecte les vidéos, tu choisis, il télécharge.
Gère les protections par cookies / Referer / jeton temporaire (il télécharge depuis la session du navigateur).

Formats : mp4, webm, mkv, mov, avi, flv, mp3, m4a... et flux HLS (`.m3u8`) / DASH (`.mpd`).

## Installation (une fois)

Prérequis : [Python 3.10+](https://www.python.org/downloads/) (cocher « Add to PATH » sous Windows). [ffmpeg](https://ffmpeg.org/download.html) pour les flux HLS/DASH.

**Windows** : double-clic sur `install.bat`

**Mac / Linux** :
```bash
sh install.sh
```

## Utilisation

**Windows** : double-clic sur `run.bat`, ou
```bash
python download_video.py
```

**Mac / Linux** :
```bash
sh run.sh
```

1. Colle l'URL de la page.
2. Un navigateur s'ouvre : résous le captcha Cloudflare s'il apparaît, lance la lecture si la vidéo ne démarre pas.
3. Après l'analyse (20 s), la liste s'affiche : tape un numéro (`1`), plusieurs (`1,3`) ou `tout`.
4. Les fichiers arrivent dans `downloads/`.

## Options

```bash
python download_video.py "https://site.com/page" --wait 40 --out mes_videos
```

| Option | Rôle | Défaut |
|---|---|---|
| `--wait N` | secondes d'analyse | 20 |
| `--out DOSSIER` | dossier de sortie | `downloads` |
| `--cdp URL` | se connecter à ton Chrome ouvert | — |

## Si Cloudflare bloque

Utilise ton vrai Chrome. Lance-le en mode debug :

```bash
# Windows
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir=%TEMP%\chrome-dbg

# Mac
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-dbg
```

Passe le défi à la main dans cette fenêtre, puis :
```bash
python download_video.py --cdp http://localhost:9222
```

## Problèmes courants

| Problème | Solution |
|---|---|
| `playwright` introuvable | utiliser `python -m playwright install chromium` |
| Aucune vidéo détectée | `--wait 40` et cliquer sur lecture pendant l'analyse |
| Erreur 403 / 404 | jeton expiré : relancer et choisir plus vite |
| Flux HLS/DASH échoue | installer ffmpeg |

## Avertissement

À utiliser uniquement pour du contenu que tu as le droit de télécharger. Tu es responsable du respect des conditions d'utilisation des sites et des droits d'auteur.

## Licence

[MIT](LICENSE)
