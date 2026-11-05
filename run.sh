#!/usr/bin/env bash
# AI Triathlon Trainer Server Runner

UV_BIN="/Users/kachkarda/.local/bin/uv"

if [ ! -f "$UV_BIN" ]; then
  if command -v uv >/dev/null 2>&1; then
    UV_BIN=$(command -v uv)
  else
    echo "Error: uv not found."
    exit 1
  fi
fi

cd "$(dirname "$0")"
echo "Starting AI Triathlon Trainer at http://localhost:8000 ..."
"$UV_BIN" run --python 3.12 uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
