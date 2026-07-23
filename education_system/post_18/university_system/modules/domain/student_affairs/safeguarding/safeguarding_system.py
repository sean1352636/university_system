"""Back-compat facade. Implementation moved into the `safeguarding` package.

Historic single-module API is preserved: every function/constant and
`SafeguardingApp`/`main` remain importable from this path.
"""

from education_system.post_18.university_system.modules.domain.student_affairs.safeguarding.api import *  # noqa: F401,F403
from education_system.post_18.university_system.modules.domain.student_affairs.safeguarding.gui.app import (
    SafeguardingApp,
    main,
)  # noqa: F401

__all__ = list(
    __import__(
        "education_system.post_18.university_system.modules.domain.student_affairs.safeguarding.api",
        fromlist=["__all__"],
    ).__all__
) + ["SafeguardingApp", "main"]

if __name__ == "__main__":
    main()
