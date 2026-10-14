#!/usr/bin/env python3
"""Run the Education System from a source checkout.

This root-level entry point mirrors both supported package entry points::

    python -m education_system
    education-system

The launcher implementation lives in :mod:`education_system.launcher.main`.
Keeping this file as a small adapter ensures every launch method uses the same
argument parsing, environment setup, migrations, authentication, and system
dispatch logic.
"""

from __future__ import annotations

import sys
from pathlib import Path


# The project uses a ``src`` layout.  Add the source root when this file is run
# from an uninstalled checkout; an installed package continues to work too.
SOURCE_ROOT = Path(__file__).resolve().parent / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from education_system.launcher.main import main  # noqa: E402


__all__ = ["main"]


if __name__ == "__main__":
    main()
