"""Deprecated re-export shim — the implementation moved to
``education_system.platform.kernel.sql_safety`` (ADR 0018: shared
infrastructure lifted out of the university package).

Import from the new path; this shim is kept for one release only.
"""

from education_system.platform.kernel.sql_safety import *  # noqa: F401,F403
from education_system.platform.kernel import sql_safety as _impl


def __getattr__(name):
    return getattr(_impl, name)
