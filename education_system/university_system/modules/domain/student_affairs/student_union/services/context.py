"""Backwards-compatible alias for union_context.

Tests and legacy code reference ``context`` but the module was renamed
to ``union_context``.  Re-export everything so both names work.
"""

from education_system.university_system.modules.domain.student_affairs.student_union.services.union_context import *  # noqa: F401,F403
from education_system.university_system.modules.domain.student_affairs.student_union.services.union_context import auth  # noqa: F401
