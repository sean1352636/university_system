#!/usr/bin/env python3
"""Package entry point, so ``python -m education_system`` works.

Deliberately thin: the launcher itself — ``main()`` and its argument parsing —
lives in :mod:`education_system.launcher.main`, which the console script and
the deprecated root ``run.py`` shim also target. Keeping the implementation out
of this module means there is exactly one launcher, and importing it does not
depend on how the process was started.
"""

from education_system.launcher.main import main

if __name__ == "__main__":
    main()
