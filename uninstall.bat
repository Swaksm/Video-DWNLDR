@echo off
rem Removes Video Grabber (shortcuts, Settings entry, installed copy). Downloaded videos are not touched.
echo Uninstalling Video Grabber...
taskkill /f /im VideoGrabber.exe >nul 2>&1
powershell -NoProfile -Command "$d=[Environment]::GetFolderPath('Desktop'); Remove-Item -LiteralPath (Join-Path $d 'Video Grabber.lnk') -ErrorAction SilentlyContinue; Remove-Item -LiteralPath (Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Video Grabber.lnk') -ErrorAction SilentlyContinue"
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\VideoGrabber" /f >nul 2>&1
timeout /t 2 /nobreak >nul
rmdir /s /q "%LOCALAPPDATA%\Programs\VideoGrabber" >nul 2>&1
echo Done. Your downloaded videos were not touched.
pause
