@echo off
rem Removes Video Grabber (shortcuts, Settings entry, app settings, installed exe). Downloaded videos are not touched.
echo Uninstalling Video Grabber...
taskkill /f /im VideoGrabber.exe >nul 2>&1
powershell -NoProfile -Command ^
 "$k='HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\VideoGrabber';" ^
 "$d=(Get-ItemProperty -LiteralPath $k -ErrorAction SilentlyContinue).InstallLocation; if(-not $d){$d=Join-Path $env:LOCALAPPDATA 'Programs\VideoGrabber'};" ^
 "$desk=[Environment]::GetFolderPath('Desktop'); $start=Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs';" ^
 "Remove-Item -LiteralPath (Join-Path $desk 'Video Grabber.lnk') -ErrorAction SilentlyContinue;" ^
 "Remove-Item -LiteralPath (Join-Path $start 'Video Grabber.lnk') -ErrorAction SilentlyContinue;" ^
 "Remove-Item -LiteralPath $k -ErrorAction SilentlyContinue;" ^
 "Remove-Item -LiteralPath (Join-Path $env:APPDATA 'VideoGrabber') -Recurse -ErrorAction SilentlyContinue;" ^
 "Start-Sleep 1; Remove-Item -LiteralPath (Join-Path $d 'VideoGrabber.exe') -ErrorAction SilentlyContinue;" ^
 "if((Test-Path -LiteralPath $d) -and -not (Get-ChildItem -LiteralPath $d -Force)){Remove-Item -LiteralPath $d}"
echo Done. Your downloaded videos were not touched.
pause
