@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\bootstrap_project_rat_workspace.ps1" -WorkspaceRoot "%~dp0"
if errorlevel 1 pause
