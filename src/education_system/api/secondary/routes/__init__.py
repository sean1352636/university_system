"""Secondary School REST route blueprints, registered by the unified server.

For now only the generated main-menu routes (``routes/menu/``, one per
sidebar entry, answering 501 until backed by a service). Add hand-written
resource blueprints to ``ALL_BLUEPRINTS`` as they are built.
"""

from education_system.api.secondary.routes.menu import MENU_BLUEPRINTS

ALL_BLUEPRINTS = tuple(MENU_BLUEPRINTS)

__all__ = ["ALL_BLUEPRINTS"]
