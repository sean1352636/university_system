"""
Integration Modules

This module contains integration code for connecting the authentication
system with other modules and external services.

Modules
-------
- chatbot_integration: Chatbot authentication features
- module_permissions: Module-specific permission setup
"""

from .chatbot_integration import (
    test_chatbot_integration,
    create_sample_chatbot_data,
)

from .module_permissions import (
    initialize_complete_system,
    init_trip_db,
    setup_trip_permissions,
    set_trip_auth,
    integrate_trip_management_with_main,
    add_finance_permissions,
    fix_alumni_permissions,
    get_health_role_permissions,
    add_calendar_permissions,
    setup_ai_detector_permissions,
    verify_ai_detector_setup,
    add_ai_detector_permissions_to_database,
    add_plagiarism_permissions,
)

__all__ = [
    # Chatbot integration
    'test_chatbot_integration',
    'create_sample_chatbot_data',

    # Module permissions
    'initialize_complete_system',
    'init_trip_db',
    'setup_trip_permissions',
    'set_trip_auth',
    'integrate_trip_management_with_main',
    'add_finance_permissions',
    'fix_alumni_permissions',
    'get_health_role_permissions',
    'add_calendar_permissions',
    'setup_ai_detector_permissions',
    'verify_ai_detector_setup',
    'add_ai_detector_permissions_to_database',
    'add_plagiarism_permissions',
]
