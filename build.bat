@echo off
python -m pip install -r requirements.txt pyinstaller
python -m PyInstaller --noconfirm --onefile --windowed --icon icon.ico --name VideoGrabber --collect-all playwright --add-data "ui.html;." gui.py
python -m PyInstaller --noconfirm --onefile --console --icon icon.ico --name video-grabber-cli --collect-all playwright download_video.py
echo.
echo Done. Executables are in the dist folder.
pause
