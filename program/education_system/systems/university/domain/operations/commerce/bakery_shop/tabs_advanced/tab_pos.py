"""Compatibility wrapper for the relocated POS GUI.

Prefer importing :class:`POSTabMixin` from
``education_system.systems.university.interfaces.gui.operations.commerce.bakery_shop.pos``.
"""

from education_system.systems.university.interfaces.gui.operations.commerce.bakery_shop.pos import (
    POSTabMixin,
)

__all__ = ["POSTabMixin"]
