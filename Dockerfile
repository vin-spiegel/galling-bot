FROM python:3.13-slim

# xvfb + Playwright 시스템 의존성
RUN apt-get update && \
    apt-get install -y --no-install-recommends xvfb xauth && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    playwright install chromium --with-deps

COPY . .

CMD ["xvfb-run", "--auto-servernum", "python", "src/run_once.py"]
