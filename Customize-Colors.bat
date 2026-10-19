@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoLogo -NoProfile -STA -File "%~dp0FurBrush-Color-Editor.ps1"
if errorlevel 1 pause
