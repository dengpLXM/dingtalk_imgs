#!/bin/bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$APP_DIR"

echo "[1/5] Pull latest code"
max_retries=3
retry_delay=5
attempt=1
while true; do
  echo "  -> git pull attempt ${attempt}/${max_retries}"
  if git pull --ff-only origin main; then
    break
  fi
  if [ "$attempt" -ge "$max_retries" ]; then
    echo "ERROR: git pull failed after ${max_retries} attempts"
    exit 1
  fi
  echo "  -> git pull failed, retrying in ${retry_delay}s..."
  sleep "$retry_delay"
  attempt=$((attempt + 1))
done

echo "[2/5] Prepare virtual environment"
if [ ! -d ".venv" ]; then
  if [ -x "/usr/bin/python3.11" ]; then
    PYTHON_BIN="/usr/bin/python3.11"
  elif command -v python3.11 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3.11)"
  else
    echo "ERROR: python3.11 not found. Please install Python 3.11 first."
    exit 1
  fi
  echo "  -> creating .venv with ${PYTHON_BIN}"
  "$PYTHON_BIN" -m venv .venv
fi

VENV_PYTHON=".venv/bin/python"
if [ ! -x "$VENV_PYTHON" ]; then
  echo "ERROR: ${VENV_PYTHON} not found or not executable."
  exit 1
fi
VENV_PY_VER="$("$VENV_PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if [ "$VENV_PY_VER" != "3.11" ]; then
  echo "ERROR: current .venv uses Python ${VENV_PY_VER}, but Python 3.11 is required."
  echo "       Remove .venv and rerun deploy.sh to recreate with Python 3.11."
  exit 1
fi
echo "  -> using .venv Python ${VENV_PY_VER}"

echo "[3/5] Install Python dependencies"
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

echo "[4/5] Ensure Playwright Chromium is installed"
.venv/bin/playwright install chromium

echo "[5/5] Restart service"
systemctl restart dingtalk-msg
systemctl status dingtalk-msg --no-pager
