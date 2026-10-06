@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0FE\scripts\Start-Android-Preview.ps1"
if errorlevel 1 pause
