#!/bin/bash
# Quick launcher script for the Extras & Tools Launcher GUI
# Part of the University Management System

cd "$(dirname "$0")"

# Use venv Python if available
VENV_PYTHON="$(dirname "$0")/../../venv/bin/python3"
if [ -x "$VENV_PYTHON" ]; then
    "$VENV_PYTHON" launcher.py
else
    python3 launcher.py
fi
