"""
CLI Main Entry Point - Orchestrator

This is the main entry point for the CLI system. It coordinates all CLI modules
and provides the main() function that starts the application.
"""

# Import from modular components
from .imports import (
    logger, init_i18n, get_auth, set_auth, UserAuth,
    set_global_auth, cleanup_database_connections
)

# Import managers
from .database_manager import (
    silent_integrity_check, fix_parent_portal_database,
    init_all_databases, init_auth_for_modules
)

from .auth_manager import (
    initialize_security_modules, ensure_user_in_communication_system,
    ensure_default_users_exist_once
)

from .menu_router import display_menu

from .chatbot_integration import setup_chatbot_permissions

from .ai_tools_integration import (
    integrate_ai_detector_with_main,
    integrate_plagiarism_checker_with_main
)

from .integration_manager import ensure_communication_integration_on_startup

from .utils import cleanup_connections

# Import integrations
from .imports import (
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
                from university_system.infrastructure.auth.mfa_integration import integrate_mfa_with_auth
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


def main():
    """
    Main entry point for the CLI application.

    This function is called when the CLI is started. It performs initial setup
    and then displays the main menu.
    """
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

    # Display main menu
    try:
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
