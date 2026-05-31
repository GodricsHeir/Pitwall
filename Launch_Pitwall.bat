@echo off
TITLE PitWall Analytics Launcher
COLOR 0A

:: Set the current directory to where this .bat file is located
cd /d "%~dp0"

:: Check if .venv exists and activate it
if exist ".venv\Scripts\activate.bat" (
    echo [*] Activating .venv...
    call ".venv\Scripts\activate.bat"
) else (
    echo [!] .venv not found in this folder! 
    echo Please ensure the folder is named .venv
    pause
    exit /b
)

:: Run streamlit using the direct path to ensure it uses the venv's streamlit
echo [*] Launching PitWall Analytics...
".venv\Scripts\streamlit.exe" run main.py

:: If it fails, keep the window open to see the error
pause