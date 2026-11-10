#!/usr/bin/env sh
set -e
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
  .venv/bin/python -m pip install -r requirements.txt
fi
echo 'Open http://127.0.0.1:5000 in a browser. Stop with Ctrl+C.'
exec .venv/bin/python app.py
