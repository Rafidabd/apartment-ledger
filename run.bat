@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Setting up Apartment Ledger for the first time...
  py -3 -m venv .venv
  if errorlevel 1 (echo Python 3 was not found. Install Python from python.org & pause & exit /b 1)
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 (echo Flask installation failed. Check your internet connection. & pause & exit /b 1)
)
echo.
echo Open http://127.0.0.1:5000 in your browser.
echo Keep this window open while using the app. Press Ctrl+C to stop.
echo.
start "" http://127.0.0.1:5000
".venv\Scripts\python.exe" app.py
pause
