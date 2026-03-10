"""Backward-compatibility shim.

The LayoutManager class has been split into mixin-based modules under the
``layout/`` package.  This file re-exports the class so that existing
imports continue to work without modification.
"""

from education_system.university_system.modules.domain.finance.gui.finance.layout._base import LayoutManager  # noqa: F401

__all__ = ["LayoutManager"]
