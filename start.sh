#!/bin/bash
cd "$(dirname "$0")"
if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt -q
fi
echo "Starting DingTalk Stats Reporter at http://localhost:8765"
.venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8765 --reload
