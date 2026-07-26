#!/usr/bin/env python3
"""Root entry point — delegates to program/run.py.

The application tree lives under program/ so the repository root stays legible.
This shim keeps the documented `python run.py` working from the root; the real
launcher, and the `education-system` console script, both resolve to
program/run.py.
"""
import runpy
import sys
from pathlib import Path

_PROGRAM = Path(__file__).resolve().parent / "program"
sys.path.insert(0, str(_PROGRAM))
runpy.run_path(str(_PROGRAM / "run.py"), run_name="__main__")
