VENV = galling-bot
PYTHON = $(VENV)/Scripts/python.exe
PIP = $(PYTHON) -m pip

ifeq ($(OS),Windows_NT)
	PYTHON = $(VENV)/Scripts/python.exe
else
	PYTHON = $(VENV)/bin/python
endif

.PHONY: install run once setup playwright clean

setup: ## 가상환경 생성 + 의존성 + Playwright 설치
	py -m venv $(VENV) || python3 -m venv $(VENV)
	$(PIP) install --upgrade pip -q
	$(PIP) install -r requirements.txt -q
	$(PYTHON) -m playwright install chromium
	@echo "Setup complete."

install: ## 의존성만 설치
	$(PIP) install -r requirements.txt -q

playwright: ## Playwright 브라우저 설치
	$(PYTHON) -m playwright install chromium

run: ## 봇 실행 (무한루프)
	$(PYTHON) src/main.py

once: ## 1회 실행 (글 1개 + 댓글 N개 → 종료)
	$(PYTHON) src/run_once.py

clean: ## 가상환경 삭제
	rm -rf $(VENV)

help: ## 명령어 목록
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  make %-12s %s\n", $$1, $$2}'
