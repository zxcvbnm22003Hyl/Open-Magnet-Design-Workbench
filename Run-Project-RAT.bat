@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup_project_rat_runtime.ps1" -WorkspaceRoot "%~dp0" -Launch
if errorlevel 1 pause
