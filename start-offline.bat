@echo off
cd /d "%~dp0"
if exist ".1022-five-question-updated" goto start
if not exist "1022-images.tar" (
  echo Missing 1022-images.tar. Copy the image archive into this folder.
  pause
  exit /b 1
)
docker load -i "1022-images.tar"
if errorlevel 1 (
  echo Image import failed. Start Docker Desktop in Linux container mode first.
  pause
  exit /b 1
)
:start
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-interview.ps1" -Offline
if errorlevel 1 (
  echo Startup failed. See the error above.
  pause
  exit /b 1
)
pause
