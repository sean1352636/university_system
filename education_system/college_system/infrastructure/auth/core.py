"""College system authentication - delegates to shared auth module.

This module re-exports the shared UserAuth so that existing college
system code (``from education_system.college_system.infrastructure.auth.core
import UserAuth``) continues to work without changes.

When launched via the universal login, the ``UserAuth`` instance from
the shared module is passed in directly.  When launched standalone
(e.g. via ``python -m education_system.college_system``), a local
``UserAuth`` is created that authenticates against the shared auth DB.
"""

from education_system.shared.auth.core import UserAuth  # noqa: F401
from education_system.shared.auth.exceptions import AuthError  # noqa: F401
