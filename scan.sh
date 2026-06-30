#!/bin/bash
# Double-click or run: ./scan.sh
cd "$(dirname "$0")"
source .venv/bin/activate
python main.py "$@"
