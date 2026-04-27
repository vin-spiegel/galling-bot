@echo off
setlocal

cd /d "%~dp0"

set VENV_DIR=galling-bot

if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo Setting up virtual environment...
    py -m venv %VENV_DIR%
    if errorlevel 1 (
        echo Failed to create virtual environment.
        exit /b 1
    )
    echo Virtual environment created.
)

if exist "requirements.txt" (
    echo Installing dependencies...
    "%VENV_DIR%\Scripts\python.exe" -m pip install -r requirements.txt -q
    if errorlevel 1 (
        echo Error occurred during dependency installation.
        exit /b 1
    )
)

echo Ensuring Playwright Chromium is installed...
"%VENV_DIR%\Scripts\python.exe" -m playwright install chromium
if errorlevel 1 (
    echo Failed to install Playwright Chromium.
    exit /b 1
)

echo Starting the bot...
"%VENV_DIR%\Scripts\python.exe" src\main.py
if errorlevel 1 (
    echo Error occurred while running the Python script.
    exit /b 1
)

endlocal
