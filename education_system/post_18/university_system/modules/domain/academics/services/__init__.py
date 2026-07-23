"""
Academic Services Package

Provides academic services including:
- Virtual classroom management
- Course evaluation
- Learning Management System (LMS)
- Plagiarism detection
- Assignment management
- Degree audit
- Attendance tracking
- Timetable management
- Parent portal
"""

# Parent portal is exposed lazily — eagerly importing it pulls in
# infrastructure.database.data_backup (which loads pandas) and adds ~4 s
# to every import of any sibling sub-package. PEP 562 ``__getattr__``
# defers that cost to the first real `services.ParentPortal` lookup.

PARENT_PORTAL_AVAILABLE: bool  # populated on first access; see below.


def __getattr__(name: str):
    global PARENT_PORTAL_AVAILABLE
    if name == "ParentPortal":
        try:
            from education_system.post_18.university_system.modules.domain.academics.services.parent_portal import (  # noqa: E501
                ParentPortal as _ParentPortal,
            )
            PARENT_PORTAL_AVAILABLE = True
        except ImportError:
            _ParentPortal = None
            PARENT_PORTAL_AVAILABLE = False
        globals()["ParentPortal"] = _ParentPortal
        return _ParentPortal
    if name == "PARENT_PORTAL_AVAILABLE":
        # Trigger the load + cache the bool in globals().
        __getattr__("ParentPortal")
        return globals()["PARENT_PORTAL_AVAILABLE"]
    raise AttributeError(
        f"module 'education_system.post_18.university_system.modules.domain."
        f"academics.services' has no attribute {name!r}")


__all__ = [
    'ParentPortal',
    'PARENT_PORTAL_AVAILABLE',
]
