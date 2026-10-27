@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-interview.ps1" %*
if errorlevel 1 (
  echo Startup failed. See the error above.
  pause
  exit /b 1
)
pause
