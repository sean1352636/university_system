"""Back-compat facade. Implementation moved into the `safeguarding` package.

Historic single-module API is preserved: every function/constant and
`SafeguardingApp`/`main` remain importable from this path.
"""

from education_system.systems.university.domains.safeguarding.application.api import *  # noqa: F401,F403
from education_system.systems.university.domains.safeguarding.interfaces.gui.app import (
    SafeguardingApp,
    main,
)  # noqa: F401

__all__ = list(
    __import__(
        "education_system.systems.university.domains.safeguarding.application.api",
        fromlist=["__all__"],
    ).__all__
) + ["SafeguardingApp", "main"]

if __name__ == "__main__":
    main()
