@echo off
TITLE Formula Lab Launcher
COLOR 0E

echo [1] Setting working directory...
cd /d "%~dp0"
echo Directory: %CD%

echo.
echo [2] Locating Virtual Environment...
if not exist ".venv\Scripts\python.exe" (
    echo [X] ERROR: Could not find Python inside the .venv folder.
    echo Are you sure the virtual environment is installed correctly?
    goto :keep_open
)
echo [*] Virtual Environment found.

echo.
echo [3] Launching App...
".venv\Scripts\python.exe" -m streamlit run main.py

:keep_open
echo.
echo ===================================================
echo [!] The application stopped. Read the error above.
echo ===================================================
cmd /k