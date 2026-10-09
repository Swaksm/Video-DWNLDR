"""Per-user Windows install / uninstall: copy of the exe, shortcuts, Settings > Apps entry. No admin rights."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

VERSION = "1.3.0"
APP = "VideoGrabber"
IS_WIN = sys.platform.startswith("win")
CAN_INSTALL = IS_WIN and getattr(sys, "frozen", False)
DEFAULT_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Programs" / APP
DATA_DIR = Path(os.environ.get("APPDATA", Path.home())) / APP if IS_WIN else Path.home() / ".videograbber"
UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\VideoGrabber"
EXE_NAME = APP + ".exe"

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

_PS_SHORTCUTS = r"""
$ws = New-Object -ComObject WScript.Shell
$dirs = @{ Desktop = [Environment]::GetFolderPath('Desktop'); Start = (Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs') }
foreach ($k in 'Desktop', 'Start') {
  $lnk = Join-Path $dirs[$k] 'Video Grabber.lnk'
  if ($env:VG_MODE -eq 'check') { Write-Output ($k + '=' + [int](Test-Path -LiteralPath $lnk)); continue }
  if ([Environment]::GetEnvironmentVariable('VG_' + $k) -eq '1') {
    $s = $ws.CreateShortcut($lnk)
    $s.TargetPath = $env:VG_EXE; $s.WorkingDirectory = $env:VG_DIR
    $s.IconLocation = $env:VG_EXE + ',0'; $s.Description = 'Video Grabber'; $s.Save()
  } else { Remove-Item -LiteralPath $lnk -ErrorAction SilentlyContinue }
}
"""

_PS_PICK_FOLDER = r"""
Add-Type -AssemblyName System.Windows.Forms
$d = New-Object System.Windows.Forms.FolderBrowserDialog
$d.SelectedPath = $env:VG_INIT; $d.ShowNewFolderButton = $true
$top = New-Object System.Windows.Forms.Form -Property @{ TopMost = $true }
if ($d.ShowDialog($top) -eq 'OK') { Write-Output $d.SelectedPath }
"""


def _ps(script, **env):
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                       env={**os.environ, **env}, capture_output=True, text=True, timeout=600, creationflags=_NO_WINDOW)
    return r.stdout


def resolve_install_dir(raw) -> Path:
    """Always install into a folder named VideoGrabber, so uninstalling can never touch unrelated files."""
    p = Path(raw).expanduser() if raw else DEFAULT_DIR
    if not p.is_absolute():
        raise ValueError("install path must be absolute")
    return p if p.name.lower() == APP.lower() else p / APP


def installed_dir():
    """Install folder recorded in the registry, or None if the app is not installed."""
    if not IS_WIN:
        return None
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY) as k:
            d = Path(winreg.QueryValueEx(k, "InstallLocation")[0])
    except OSError:
        return None
    return d if (d / EXE_NAME).exists() else None


def shortcut_status():
    if not IS_WIN:
        return {"Desktop": False, "Start": False}
    out = _ps(_PS_SHORTCUTS, VG_MODE="check")
    return {k: v == "1" for k, v in (line.strip().split("=") for line in out.splitlines() if "=" in line)}


def set_shortcuts(exe: Path, desktop: bool, start: bool):
    _ps(_PS_SHORTCUTS, VG_DESKTOP="1" if desktop else "0", VG_START="1" if start else "0",
        VG_EXE=str(exe), VG_DIR=str(exe.parent))


def pick_folder(initial: str = "") -> str:
    if not IS_WIN:
        return ""
    return _ps(_PS_PICK_FOLDER, VG_INIT=initial or str(Path.home())).strip()


def _register(install_dir: Path):
    import winreg
    exe = str(install_dir / EXE_NAME)
    values = {
        "DisplayName": "Video Grabber", "DisplayVersion": VERSION, "Publisher": "Swaks",
        "DisplayIcon": exe + ",0", "InstallLocation": str(install_dir),
        "UninstallString": f'"{exe}" --uninstall', "QuietUninstallString": f'"{exe}" --uninstall --quiet',
    }
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY) as k:
        for name, val in values.items():
            winreg.SetValueEx(k, name, 0, winreg.REG_SZ, val)
        for name in ("NoModify", "NoRepair"):
            winreg.SetValueEx(k, name, 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(k, "EstimatedSize", 0, winreg.REG_DWORD, int((install_dir / EXE_NAME).stat().st_size / 1024))


def install(raw_dir, desktop: bool, start: bool) -> Path:
    """Copy the running exe into the install folder (first time), register it, create/remove shortcuts."""
    exe = Path(sys.executable).resolve()
    d = installed_dir() or resolve_install_dir(raw_dir)
    target = d / EXE_NAME
    if not target.exists() or exe != target.resolve():
        try:
            d.mkdir(parents=True, exist_ok=True)
            shutil.copy2(exe, target)
        except PermissionError:
            if not target.exists():
                raise  # an already-installed copy that is running can't be overwritten: keep it
    _register(d)
    set_shortcuts(target, desktop, start)
    return d


def _msgbox(text, flags):
    import ctypes
    return ctypes.windll.user32.MessageBoxW(0, text, "Video Grabber", flags)


def uninstall(quiet=False):
    """Remove shortcuts, Settings entry, app settings and the installed exe. Downloads are never touched."""
    import ctypes
    import winreg

    fr = (ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0xFF) == 0x0C
    if not quiet and _msgbox("Désinstaller Video Grabber ?\nTes vidéos téléchargées ne seront pas supprimées." if fr
                             else "Uninstall Video Grabber?\nYour downloaded videos will not be deleted.", 0x24) != 6:
        return
    d = installed_dir() or DEFAULT_DIR
    exe = d / EXE_NAME
    _ps(_PS_SHORTCUTS, VG_DESKTOP="0", VG_START="0")
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY)
    except OSError:
        pass
    shutil.rmtree(DATA_DIR, ignore_errors=True)
    if exe.exists() and Path(sys.executable).resolve() == exe.resolve():
        # a running exe cannot delete itself: a detached shell removes it once we exit
        subprocess.Popen(f'cmd /c ping -n 4 127.0.0.1 >nul & del /f /q "{exe}" & rmdir "{d}"', shell=True,
                         creationflags=_NO_WINDOW | subprocess.DETACHED_PROCESS)
    else:
        exe.unlink(missing_ok=True)
        try:
            d.rmdir()  # only if empty: never delete anything we did not create
        except OSError:
            pass
    if not quiet:
        _msgbox("Video Grabber a été désinstallé." if fr else "Video Grabber has been uninstalled.", 0x40)
