"""Compatibility wrapper for the relocated POS GUI.

Prefer importing :class:`POSTabMixin` from
``education_system.systems.university.plugins.campus_commerce.interfaces.gui.bakery_shop.pos``.
"""

from education_system.systems.university.plugins.campus_commerce.interfaces.gui.bakery_shop.pos import (
    POSTabMixin,
)

__all__ = ["POSTabMixin"]
