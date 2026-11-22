"""Counselling Service screens. The panel loads on first use (PEP 562): its
modules import ``common`` from this package."""

from __future__ import annotations

__all__ = ["CounsellingServicePanel", "open_window"]


def __getattr__(name):
    if name in __all__:
        from education_system.systems.university.domains.student_support.interfaces.gui.wellbeing.counselling_service import (
            panel,
        )
        return getattr(panel, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
