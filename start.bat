@echo off
rem ---------------------------------------------------------------------------
rem  Start ccproxy on Windows.
rem  Double-click this file, or run it from cmd / PowerShell:  start.bat
rem
rem  The first run creates a local .venv and installs flask + requests into it.
rem  Nothing is installed globally, and nothing outside this folder is touched.
rem ---------------------------------------------------------------------------
setlocal
cd /d "%~dp0"

where python >nul 2>&1
if errorlevel 1 (
  echo.
  echo !! Python 3 was not found on your PATH.
  echo.
  echo    Install it from https://www.python.org/downloads/
  echo    IMPORTANT: on the first installer screen, tick
  echo       [x] Add python.exe to PATH
  echo    then close this window and run start.bat again.
  echo.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating .venv -- first run only, this takes a minute ...
  python -m venv .venv
  if errorlevel 1 goto fail
  echo Installing dependencies ...
  ".venv\Scripts\python.exe" -m pip install --upgrade pip
  if errorlevel 1 goto fail
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 goto fail
)

echo.
echo Starting ccproxy ... the exact URL is printed on the next line.
echo Press Ctrl+C to stop.
echo.

".venv\Scripts\python.exe" ccproxy.py
pause
exit /b 0

:fail
echo.
echo Setup failed. The errors are above.
echo.
pause
exit /b 1
