@echo off
rem Run ccproxy's offline tests. No real API key is needed -- the suite starts
rem its own mock upstream.
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo .venv not found. Run start.bat once first -- it creates it.
  pause
  exit /b 1
)

".venv\Scripts\python.exe" test_offline.py %*
pause
