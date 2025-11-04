from __future__ import annotations

import logging

from . import restaurant_context as ctx
from university_system.modules.core.services.restaurant_misc.restaurant_context import view_user_activity_logs

def user_management():
    """User management functionality"""
    
    if not ctx.auth or not ctx.auth.current_user:
        print("You must be logged in to manage users.")
        return

    if not ctx.auth.check_permission('admin'):
        print("You don't have permission to manage users.")
        return

    try:
        print("\n" + "="*50)
        print("USER MANAGEMENT")
        print("="*50)

        print("\nOptions:")
        print("1. View all users")
        print("2. Create new user")
        print("3. Update user")
        print("4. Deactivate user")
        print("5. Reset password")
        print("6. User activity logs")
        print("7. Return to system settings")

        choice = input("Choose an option (1-7): ")

        if choice == '1':
            ctx.auth.view_all_users()
        elif choice == '2':
            ctx.auth.register_user()
        elif choice == '3':
            ctx.auth.update_user()
        elif choice == '4':
            ctx.auth.deactivate_user()
        elif choice == '5':
            ctx.auth.reset_user_password()
        elif choice == '6':
            view_user_activity_logs()
        elif choice == '7':
            return
        else:
            print("Invalid choice.")

    except Exception as e:
        logging.error(f"Error in user_management: {e}")
        print(f"An error occurred: {e}")
