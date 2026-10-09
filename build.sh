#!/usr/bin/env sh
python3 -m pip install -r requirements.txt pyinstaller
python3 -m PyInstaller --noconfirm --onefile --windowed --name VideoGrabber --collect-all playwright --add-data "ui.html:." gui.py
python3 -m PyInstaller --noconfirm --onefile --console --name video-grabber-cli --collect-all playwright download_video.py
echo "Done. Executables are in the dist folder."
