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

# Load the real launcher without executing its ``if __name__ == '__main__'``
# block.  Pytest imports this compatibility module while collecting
# ``test_run.py``; eagerly running the launcher there would pass pytest's own
# command-line arguments to argparse and abort collection.
_run_name = "run" if __name__ != "__main__" else "_education_system_program_run"
_namespace = runpy.run_path(str(_PROGRAM / "run.py"), run_name=_run_name)
globals().update({
    name: value for name, value in _namespace.items()
    if name not in {"__name__", "__file__", "__package__", "__spec__"}
})
main = _namespace["main"]

if __name__ == "__main__":
    main()
