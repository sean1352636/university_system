"""``python -m education_system.systems.alternative_provision [--cli]``

There is no standalone login: this hands over to the unified launcher with
the Alternative Provision system pre-selected, which shows the shared sign-in first.
"""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    mode = "--cli" if "--cli" in args else "--gui"
    sys.argv = [sys.argv[0], "--alternativeprovision", mode]
    from education_system.launcher.main import main as launcher_main
    launcher_main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
