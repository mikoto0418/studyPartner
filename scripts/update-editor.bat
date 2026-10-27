@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0update-editor.ps1"
if errorlevel 1 (
  echo UPDATE FAILED. Keep the error message above.
) else (
  echo Update completed. Refresh the student page after answers show saved.
)
pause
