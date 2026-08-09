#!/usr/bin/env python3
"""Root entry point — delegates to src/education_system/__main__.py.

The application tree lives under src/ so the repository root stays legible.
This shim keeps the documented `python run.py` working from the root; the real
launcher, and the `education-system` console script, both resolve to
education_system.__main__. Prefer `python -m education_system`; this shim is a
compatibility layer and is scheduled for removal.
"""
import runpy
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent / "src"
sys.path.insert(0, str(_SRC))

# Load the real launcher without executing its ``if __name__ == '__main__'``
# block.  Pytest imports this compatibility module while collecting
# ``test_run.py``; eagerly running the launcher there would pass pytest's own
# command-line arguments to argparse and abort collection.
_run_name = "run" if __name__ != "__main__" else "_education_system_program_run"
_namespace = runpy.run_path(
    str(_SRC / "education_system" / "__main__.py"), run_name=_run_name
)
globals().update({
    name: value for name, value in _namespace.items()
    if name not in {"__name__", "__file__", "__package__", "__spec__"}
})
main = _namespace["main"]

if __name__ == "__main__":
    main()
