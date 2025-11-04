from __future__ import annotations

from university_system.infrastructure.auth.user_authentication import UserAuth
from . import restaurant_context as ctx
from university_system.modules.core.services.restaurant_misc.restaurant_context import (
    DATABASE_FILE,
    display_auth_menu,
    display_main_menu,
    init_db,
    set_auth,
)

def main():
    """Main function to run the restaurant management system"""
    
    # Initialize database
    if not init_db():
        print("Failed to initialize database. Exiting...")
        return

    # Initialize authentication
    ctx.auth = UserAuth(DATABASE_FILE)
    set_auth(ctx.auth)

    # Display login menu
    while True:
        if not ctx.auth.current_user:
            if not display_auth_menu():
                print("Goodbye!")
                return
        else:
            # Main menu after login
            display_main_menu()
