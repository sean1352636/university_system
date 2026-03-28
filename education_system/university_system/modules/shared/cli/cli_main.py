"""
CLI Main Entry Point - Orchestrator

This is the main entry point for the CLI system. It coordinates all CLI modules
and provides the main() function that starts the application.
"""

# Import from modular components
from education_system.university_system.modules.shared.cli.imports import (
    logger, init_i18n, get_auth, set_auth, UserAuth,
    set_global_auth, cleanup_database_connections
)

# Import managers
from education_system.university_system.modules.shared.cli.database_manager import (
    silent_integrity_check, fix_parent_portal_database,
    init_all_databases, init_auth_for_modules
)

from education_system.university_system.modules.shared.cli.auth_manager import (
    initialize_security_modules, ensure_user_in_communication_system,
    ensure_default_users_exist_once
)

from education_system.university_system.modules.shared.cli.menu_router import display_menu

from education_system.university_system.modules.shared.cli.chatbot_integration import setup_chatbot_permissions

from education_system.university_system.modules.shared.cli.ai_tools_integration import (
    integrate_ai_detector_with_main,
    integrate_plagiarism_checker_with_main
)

from education_system.university_system.modules.shared.cli.integration_manager import ensure_communication_integration_on_startup

from education_system.university_system.modules.shared.cli.utils import cleanup_connections

import getpass

# Import integrations
from education_system.university_system.modules.shared.cli.imports import (
    init_assignment_system, add_assignment_permissions,
    init_trip_db, setup_trip_permissions, set_trip_auth, integrate_trip_management_with_main,
    init_housing_db, set_accommodation_auth,
    set_calendar_auth, ensure_calendar_permissions,
    integrate_parent_portal_with_main,
    init_shop_db, setup_shop_permissions, set_shop_auth,
    init_charity_shop_db, setup_charity_shop_permissions, set_charity_shop_auth,
    init_cafe_db, setup_cafe_permissions, set_cafe_auth,
    init_takeaway_db, setup_takeaway_permissions, set_takeaway_auth,
    init_grocery_db, setup_grocery_permissions, set_grocery_auth,
    init_staff_hr_db, setup_staff_hr_permissions, set_staff_hr_auth,
    add_finance_permissions, student_union_core,
    MFA_INTEGRATION_AVAILABLE,
)


def initialize_system() -> bool:
    """
    Initialize the entire CLI system.

    This function orchestrates the initialization of all system components:
    - Database initialization
    - Authentication system
    - Security modules
    - Default users
    - External integrations
    - Chatbot and AI tools

    Returns:
        bool: True if initialization successful, False otherwise
    """
    try:
        logger.info("Starting CLI system initialization...")

        # Step 1: Initialize core database
        logger.info("Initializing databases...")
        if not init_all_databases():
            logger.error("Database initialization failed")
            return False

        # Step 2: Initialize authentication system
        logger.info("Initializing authentication...")
        global auth
        auth = get_auth()
        if auth is None:
            auth = UserAuth()
            set_auth(auth)
        set_global_auth(auth)

        # Step 3: Initialize authentication for all modules
        logger.info("Initializing module authentication...")
        init_auth_for_modules()

        # Step 4: Set up authentication for various subsystems
        set_trip_auth(auth)
        set_accommodation_auth(auth)
        set_calendar_auth(auth)
        set_shop_auth(auth)
        set_charity_shop_auth(auth)
        set_cafe_auth(auth)
        set_takeaway_auth(auth)
        set_grocery_auth(auth)
        set_staff_hr_auth(auth)

        # Step 5: Ensure default users exist
        logger.info("Ensuring default users exist...")
        ensure_default_users_exist_once()

        # Step 6: Initialize security modules
        logger.info("Initializing security modules...")
        initialize_security_modules()

        # Step 7: Set up permissions for all features
        logger.info("Setting up permissions...")
        add_assignment_permissions(auth)
        setup_trip_permissions(auth)
        ensure_calendar_permissions(auth)
        add_finance_permissions(auth)
        setup_shop_permissions(auth)
        setup_charity_shop_permissions(auth)
        setup_cafe_permissions(auth)
        setup_takeaway_permissions(auth)
        setup_grocery_permissions(auth)
        setup_staff_hr_permissions(auth)
        setup_chatbot_permissions()

        # Step 8: Initialize external integrations
        logger.info("Initializing integrations...")
        integrate_trip_management_with_main()
        integrate_parent_portal_with_main()
        student_union_core.init_student_union_db()

        # Step 9: Ensure communication integration
        logger.info("Setting up communication integration...")
        ensure_communication_integration_on_startup()

        # Step 10: Initialize AI tools (non-critical)
        logger.info("Initializing AI tools...")
        try:
            integrate_ai_detector_with_main()
        except Exception as e:
            logger.warning(f"AI detector initialization failed: {e}")

        try:
            integrate_plagiarism_checker_with_main()
        except Exception as e:
            logger.warning(f"Plagiarism checker initialization failed: {e}")

        # Step 11: MFA integration if available
        if MFA_INTEGRATION_AVAILABLE:
            try:
                from education_system.university_system.infrastructure.auth.mfa_integration import integrate_mfa_with_auth
                integrate_mfa_with_auth(auth)
                logger.info("MFA integration successful")
            except Exception as e:
                logger.warning(f"MFA integration failed: {e}")

        logger.info("CLI system initialization complete")
        return True

    except Exception as e:
        logger.error(f"System initialization failed: {e}", exc_info=True)
        print(f"System initialization failed: {e}")
        return False


def login_prompt(auth) -> bool:
    """Show login prompt using shared auth. Returns True if login succeeds."""
    from education_system.shared.auth.core import UserAuth as SharedAuth
    from education_system.shared.cli.login_cli import cli_login_prompt

    shared = SharedAuth()
    result = cli_login_prompt(shared)
    if result is None:
        return False

    user_info, _ = result

    # Determine university role from systems list
    role = "student"
    for s in user_info.get("systems", []):
        if s["system_key"] == "university":
            role = s["role"]
            break

    # Look up university-specific permissions
    permissions = []
    try:
        permissions = auth.permission_manager.get_user_permissions(
            user_info["user_id"]
        )
    except Exception:
        pass

    # Fall back to role-based permissions from constants if DB lookup returned nothing
    if not permissions:
        from education_system.university_system.infrastructure.auth.core_utils.constants import PERMISSIONS
        permissions = list(PERMISSIONS.get(role, []))

    # Build current_user in university format
    user_dict = {
        "id": user_info["user_id"],
        "user_id": user_info["user_id"],
        "username": user_info["username"],
        "display_name": user_info.get("display_name", user_info["username"]),
        "email": user_info.get("email", ""),
        "role": role,
        "permissions": permissions,
        "password_reset_required": 0,
        "student_id": None,
        "systems": user_info.get("systems", []),
    }
    auth.current_user = user_dict
    from datetime import datetime
    auth.last_activity = datetime.now()

    display = user_info.get("display_name", user_info["username"])
    print(f"\n  Welcome, {display}! (Role: {role})")
    logger.info("CLI login: user '%s' (role=%s)", user_info["username"], role)
    return True


def main(user_info=None, role=None, shared_auth=None):
    """
    Main entry point for the CLI application.

    This function is called when the CLI is started. It performs initial setup
    and then displays the main menu.

    If *user_info* and *role* are provided (from universal login), the
    login dialog is skipped.
    """
    import sys

    # Perform silent integrity check first
    silent_integrity_check()
    fix_parent_portal_database()

    # Initialize i18n (internationalization) system
    init_i18n()

    # Initialize system cleanly
    if not initialize_system():
        print("System initialization failed. Exiting.")
        return

    print("System initialized successfully.")

    # Initialize auth and start the main menu
    global auth
    auth = get_auth()
    if auth is None:
        # Create if doesn't exist
        auth = UserAuth()
        set_auth(auth)
    set_global_auth(auth)  # Set as global auth for all modules

    # If pre-authenticated, inject credentials into the auth object
    if user_info and role and shared_auth:
        display = user_info.get("display_name", user_info.get("username", "User"))

        # Look up university-specific permissions
        permissions = []
        try:
            permissions = auth.permission_manager.get_user_permissions(
                user_info.get("user_id")
            )
        except Exception:
            pass

        # Fall back to role-based permissions from constants if DB lookup returned nothing
        if not permissions:
            from education_system.university_system.infrastructure.auth.core_utils.constants import PERMISSIONS
            permissions = list(PERMISSIONS.get(role, []))

        auth.current_user = {
            "id": user_info.get("user_id"),
            "user_id": user_info.get("user_id"),
            "username": user_info.get("username"),
            "display_name": display,
            "email": user_info.get("email", ""),
            "role": role,
            "permissions": permissions,
            "password_reset_required": 0,
            "student_id": None,
            "systems": user_info.get("systems", []),
        }
        from datetime import datetime
        auth.last_activity = datetime.now()
        print(f"\n  Welcome, {display}! (Role: {role})")
    else:
        # Standard login using shared auth (same as other systems)
        if not login_prompt(auth):
            sys.exit(1)

    # Route students to the dedicated Student Portal CLI; everyone else
    # gets the full management menu.
    current_role = ''
    if auth and auth.current_user:
        current_role = (auth.current_user.get('role') or '').lower()

    try:
        if current_role == 'student':
            from education_system.university_system.modules.shared.cli.student_portal_cli import run_student_portal
            run_student_portal()
        else:
            display_menu()
    finally:
        # Clean up on exit
        cleanup_connections()
        cleanup_database_connections()


# Global auth instance (for backward compatibility)
auth = None


if __name__ == "__main__":
    main()


__all__ = [
    'main',
    'initialize_system',
    'auth',
]
