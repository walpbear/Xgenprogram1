@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoLogo -NoProfile -STA -File "%~dp0FurBrush-Splash.ps1"
if errorlevel 1 (
  echo FurBrush launcher could not start. See the message above.
  pause
)
