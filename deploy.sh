#!/bin/bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$APP_DIR"

echo "[1/5] Pull latest code"
git pull --ff-only origin main

echo "[2/5] Prepare virtual environment"
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

echo "[3/5] Install Python dependencies"
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

echo "[4/5] Ensure Playwright Chromium is installed"
.venv/bin/playwright install chromium

echo "[5/5] Restart service"
systemctl restart dingtalk-msg
systemctl status dingtalk-msg --no-pager
