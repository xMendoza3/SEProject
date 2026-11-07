@echo off
REM Comparative Fiqh Explorer - one-click launcher for Windows.
REM First run: creates the environment, installs libraries, builds the database.
REM Later runs: opens the app directly.

cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo Python was not found. Install Python 3.10 or newer from python.org, then run this file again.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo [1/3] Creating the virtual environment...
    python -m venv .venv
    echo [2/3] Installing libraries, this needs internet once...
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
)

if not exist "data\fiqh.db" (
    echo [3/3] Building the database from the book files...
    ".venv\Scripts\python.exe" ingest.py
)

echo Starting the app. Close this window to stop it.
".venv\Scripts\python.exe" -m streamlit run app.py
