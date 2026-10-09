# video-grabber

[English](README.md) | **Français**

Colle l'URL d'une page : l'outil détecte les vidéos, tu choisis, il télécharge.
Gère les protections par cookies / Referer / jeton temporaire (il télécharge depuis la session du navigateur).

Formats : mp4, webm, mkv, mov, avi, flv, mp3, m4a... et flux HLS (`.m3u8`) / DASH (`.mpd`).

Deux façons de l'utiliser : une **application graphique** ou la **ligne de commande**.

## Démarrage rapide (sans Python)

1. Télécharge `VideoGrabber.exe` (interface graphique) ou `video-grabber-cli.exe` (ligne de commande) depuis la page [Releases](../../releases).
2. Lance-le. Il faut Google Chrome ou Microsoft Edge (déjà présent sous Windows).

## Application graphique

Double-clic sur `VideoGrabber.exe` (ou `python gui.py`).

1. Colle l'URL de la page et clique sur **Analyser la page**.
2. Un navigateur s'ouvre : résous le captcha Cloudflare s'il apparaît, lance la lecture si la vidéo ne démarre pas.
3. Sélectionne une ou plusieurs vidéos dans la liste, clique sur **Télécharger la sélection**.
4. Change la langue (English / Français) en haut à droite. Tu peux analyser autant de pages que tu veux, la fenêtre reste ouverte.

## Ligne de commande

```bash
video-grabber-cli.exe                              # interactif, demande des URL en boucle
video-grabber-cli.exe "https://site.com/page"      # analyse, puis choix dans la liste
video-grabber-cli.exe "https://site.com/page" --pick all    # sans question : tout télécharger
video-grabber-cli.exe "https://site.com/page" --pick 1,3    # télécharger les éléments 1 et 3
```

Depuis les sources, remplace `video-grabber-cli.exe` par `python download_video.py`.
En mode interactif : colle une URL pour relancer une analyse, `lang` bascule anglais/français, `q` quitte.

| Option | Rôle | Défaut |
|---|---|---|
| `--pick all\|1,3` | téléchargement sans question | demande |
| `--wait N` | secondes d'analyse | 20 |
| `--out DOSSIER` | dossier de sortie | `downloads` |
| `--lang en\|fr` | langue de l'interface | `en` |
| `--cdp URL` | se connecter à ton Chrome ouvert | — |

## Lancer depuis les sources

Prérequis : [Python 3.10+](https://www.python.org/downloads/) (cocher « Add to PATH » sous Windows). [ffmpeg](https://ffmpeg.org/download.html) pour les flux HLS/DASH.

```bash
pip install -r requirements.txt
python gui.py                 # application graphique
python download_video.py      # ligne de commande
```

Raccourcis Windows : `install.bat` puis `run.bat`. Mac / Linux : `sh install.sh` puis `sh run.sh`.

## Construire les exécutables

```bash
build.bat        # Windows
sh build.sh      # Mac / Linux
```

Les résultats sont dans `dist/` (`VideoGrabber`, `video-grabber-cli`).

## Si Cloudflare bloque

Utilise ton vrai Chrome. Lance-le en mode debug :

```bash
# Windows
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir=%TEMP%\chrome-dbg

# Mac
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-dbg
```

Passe le défi à la main dans cette fenêtre, puis coche **Utiliser mon Chrome** dans l'application, ou utilise `--cdp http://localhost:9222` en ligne de commande.

## Problèmes courants

| Problème | Solution |
|---|---|
| Aucune vidéo détectée | augmenter la durée d'analyse et lancer la lecture pendant l'analyse |
| Erreur 403 / 404 | jeton expiré : relancer l'analyse et télécharger plus vite |
| Flux HLS/DASH échoue | installer ffmpeg |
| « Aucun navigateur disponible » | installer Google Chrome ou Microsoft Edge |

## Avertissement

À utiliser uniquement pour du contenu que tu as le droit de télécharger. Tu es responsable du respect des conditions d'utilisation des sites et des droits d'auteur.

## Licence

[MIT](LICENSE)
