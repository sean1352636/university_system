"""
Housing Accommodation GUI Module

This module provides the graphical user interface for the housing accommodation system.
It has been refactored into smaller, manageable components for better maintainability.

Main Components:
- HousingGUI: Main GUI class (from main_gui.py)
- Email notifications: email_notifications.py
- Finance integration: finance_integration.py

For backward compatibility, all public functions are re-exported from this module.
"""

# Import the main GUI class
from education_system.university_system.modules.domain.campus.housing.gui.housing_accommodation_gui.main_gui import HousingGUI
from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.modules.domain.campus.housing.services.accommodation.db import init_accommodation_db

# Import the HousingFinanceManager class
try:
    from education_system.university_system.modules.domain.campus.housing.gui.housing_accommodation_gui.finance_integration import HousingFinanceManager
except ImportError:
    # Fallback if file doesn't exist yet
    HousingFinanceManager = None

# Import email functions
from education_system.university_system.modules.domain.campus.housing.gui.housing_accommodation_gui.email_notifications import (
    send_housing_email,
    send_maintenance_email
)

# Import original backend functions for backward compatibility
from education_system.university_system.modules.domain.campus.housing.services.housing_accommodation import (
    init_housing_db,
    generate_id,
    set_auth,
    select_student as orig_select_student,
    create_building as orig_create_building,
    view_building as orig_view_building,
    update_building as orig_update_building,
    delete_building as orig_delete_building,
    create_rooms_for_building as orig_create_rooms_for_building,
    create_application as orig_create_application,
    process_application as orig_process_application,
    view_application as orig_view_application,
    view_assignment as orig_view_assignment,
    update_assignment_status as orig_update_assignment_status,
    create_maintenance_request as orig_create_maintenance_request,
    view_maintenance_requests as orig_view_maintenance_requests,
    update_maintenance_request as orig_update_maintenance_request,
    record_payment as orig_record_payment,
    view_payment_history as orig_view_payment_history,
    manage_inventory as orig_manage_inventory,
    create_inspection as orig_create_inspection,
    view_inspections as orig_view_inspections,
    generate_occupancy_report as orig_generate_occupancy_report,
    generate_financial_report as orig_generate_financial_report,
    export_housing_data as orig_export_housing_data,
    search_housing_records as orig_search_housing_records,
    check_room_availability as orig_check_room_availability,
    maintenance_summary as orig_maintenance_summary,
    upcoming_moveouts_report as orig_upcoming_moveouts_report,
    display_housing_accommodation_menu as orig_display_housing_accommodation_menu,
    display_reports_menu as orig_display_reports_menu,
    display_building_menu as orig_display_building_menu,
    display_application_menu as orig_display_application_menu,
    display_assignment_menu as orig_display_assignment_menu,
    display_maintenance_menu as orig_display_maintenance_menu,
    display_payment_menu as orig_display_payment_menu,
    display_inspection_menu as orig_display_inspection_menu
)

# Create aliases for backward compatibility
orig_init_housing_db = init_housing_db
orig_generate_id = generate_id
orig_set_auth = set_auth

# Define menu launcher function for backward compatibility
def display_housing_accommodation_menu_gui(auth_instance=None):
    """
    Launch the Housing Accommodation GUI.

    This function provides backward compatibility with the old interface.
    """
    housing_gui = HousingGUI(auth_instance)
    housing_gui.root.mainloop()

# Export all public symbols
__all__ = [
    # Main GUI class
    'HousingGUI',
    'HousingFinanceManager',

    # Email functions
    'send_housing_email',
    'send_maintenance_email',

    # GUI launcher
    'display_housing_accommodation_menu_gui',

    # Backend functions (with orig_ prefix for clarity)
    'orig_init_housing_db',
    'orig_generate_id',
    'orig_set_auth',
    'orig_select_student',
    'orig_create_building',
    'orig_view_building',
    'orig_update_building',
    'orig_delete_building',
    'orig_create_rooms_for_building',
    'orig_create_application',
    'orig_process_application',
    'orig_view_application',
    'orig_view_assignment',
    'orig_update_assignment_status',
    'orig_create_maintenance_request',
    'orig_view_maintenance_requests',
    'orig_update_maintenance_request',
    'orig_record_payment',
    'orig_view_payment_history',
    'orig_manage_inventory',
    'orig_create_inspection',
    'orig_view_inspections',
    'orig_generate_occupancy_report',
    'orig_generate_financial_report',
    'orig_export_housing_data',
    'orig_search_housing_records',
    'orig_check_room_availability',
    'orig_maintenance_summary',
    'orig_upcoming_moveouts_report',
    'orig_display_housing_accommodation_menu',
    'orig_display_reports_menu',
    'orig_display_building_menu',
    'orig_display_application_menu',
    'orig_display_assignment_menu',
    'orig_display_maintenance_menu',
    'orig_display_payment_menu',
    'orig_display_inspection_menu',

    # Direct aliases (for code that doesn't use orig_ prefix)
    'init_housing_db',
    'generate_id',
    'set_auth',
]
