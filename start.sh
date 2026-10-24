#!/bin/bash
cd "$(dirname "$0")"
PY="${PYTHON:-python3}"

if [ -f requirements.txt ]; then
    "$PY" -m pip install -q -r requirements.txt
fi

exec "$PY" bot.py
