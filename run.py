#!/usr/bin/env python3
"""Deprecated compatibility shim for ``python run.py``.

The launcher is package-native: use ``python -m education_system`` or the
``education-system`` console script instead. Both resolve to
:func:`education_system.launcher.main.main`, which this module simply
re-exports so existing scripts and documentation keep working.

This file is scheduled for removal after a compatibility period.
"""

import sys
import warnings
from pathlib import Path

# Support running from a source checkout without installing the project first.
# Insert src/, never src/education_system/ — the latter would put the package's
# platform/ directory on sys.path and shadow the stdlib `platform` module.
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from education_system.launcher.main import main  # noqa: E402

warnings.warn(
    "run.py is deprecated; use `python -m education_system` or the "
    "`education-system` console script instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["main"]

if __name__ == "__main__":
    main()
