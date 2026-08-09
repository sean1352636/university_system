"""Entry point for ``python -m …shop_management``.

The GUI's "Switch to CLI" button launches this package as a module.
Without a ``__main__.py`` Python rejects the invocation with
"package cannot be directly executed". Delegates to
``menus.display_main_menu_extended()``, which is the existing CLI
menu loop (handles login prompt, db init, main menu).
"""

from education_system.systems.university.infrastructure.shared_context import initialize_auth
from education_system.systems.university.domain.operations.commerce.services.shop_management.menus import (
    display_main_menu_extended,
)


if __name__ == "__main__":
    initialize_auth()
    try:
        display_main_menu_extended()
    except KeyboardInterrupt:
        print("\nShop Management CLI — interrupted. Goodbye.")
