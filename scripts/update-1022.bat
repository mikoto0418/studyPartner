@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0update-1022.ps1"
if errorlevel 1 (
  echo UPDATE FAILED. Read the message above. Do not delete database volumes.
) else (
  echo Update completed. Refresh the teacher page.
)
pause
