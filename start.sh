#!/bin/bash

# 스크립트 실행 디렉토리로 이동
cd "$(dirname "$0")"

# 가상환경 디렉토리 설정
VENV_DIR="./galling-bot"

# OS 감지 (Windows Git Bash / MSYS / Cygwin vs Unix)
case "$(uname -s)" in
    MINGW*|MSYS*|CYGWIN*)
        VENV_BIN="$VENV_DIR/Scripts"
        PYTHON_BIN="py"
        ;;
    *)
        VENV_BIN="$VENV_DIR/bin"
        PYTHON_BIN="python3"
        ;;
esac

# 가상환경이 이미 설정되어 있는지 확인
if [ ! -f "$VENV_BIN/python" ] && [ ! -f "$VENV_BIN/python.exe" ]; then
    echo "Setting up virtual environment..."
    $PYTHON_BIN -m venv "$VENV_DIR"
    if [ $? -ne 0 ]; then
        echo "Failed to create virtual environment."
        exit 1
    fi
    echo "Virtual environment created."
fi

# 가상환경 활성화
source "$VENV_BIN/activate"

# 필요한 패키지 설치
if [ -f "requirements.txt" ]; then
    echo "Installing dependencies..."
    pip install -r requirements.txt -q
    if [ $? -ne 0 ]; then
        echo "Error occurred during dependency installation."
        deactivate
        exit 1
    fi
else
    echo "No requirements.txt found, skipping dependency installation."
fi

# Playwright Chromium 설치 보장
echo "Ensuring Playwright Chromium is installed..."
python -m playwright install chromium
if [ $? -ne 0 ]; then
    echo "Failed to install Playwright Chromium."
    deactivate
    exit 1
fi

# Python 스크립트 실행
echo "Starting the bot..."
python src/main.py
if [ $? -ne 0 ]; then
    echo "Error occurred while running the Python script."
    deactivate
    exit 1
fi

# 가상환경 비활성화
deactivate
