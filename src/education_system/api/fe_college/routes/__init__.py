"""HTTP routes for the FE College system.

The resource modules beside this file are still empty placeholders, so the
main-menu routes generated from the GUI/CLI navigation are this system's
whole API surface for now. Every one answers 501 until it is backed by a
service — which is the point: the gap is addressable and countable rather
than invisible.
"""

from education_system.api.fe_college.routes.menu import MENU_BLUEPRINTS

ALL_BLUEPRINTS = tuple(MENU_BLUEPRINTS)

__all__ = ["ALL_BLUEPRINTS"]
