#!/bin/sh
# macOS/Linux/Git Bash 실행 스크립트: sh scripts/start.sh
set -eu
cd "$(dirname "$0")/.."

if [ -x .venv/bin/python ]; then PY=.venv/bin/python
elif [ -x .venv/Scripts/python.exe ]; then PY=.venv/Scripts/python.exe
else
  python3 -m venv .venv 2>/dev/null || python -m venv .venv
  if [ -x .venv/bin/python ]; then PY=.venv/bin/python; else PY=.venv/Scripts/python.exe; fi
fi
[ -f .env ] || cp .env.example .env
"$PY" -m pip install -q -r requirements.txt

PORT=$(sed -n 's/^PORT=\([0-9]*\).*/\1/p' .env)
exec "$PY" -m uvicorn app.main:app --reload --host 127.0.0.1 --port "${PORT:-8000}"
