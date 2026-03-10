"""Housing Accommodation Management - Package

This package was refactored from a single module into multiple sub-modules
for maintainability. All public functions are re-exported here for backward
compatibility.
"""

from .common import set_auth, generate_id
from .database import init_housing_db
from .buildings import (
    create_building, create_rooms_for_building, view_building,
    update_building, delete_building,
)
from .applications import (
    create_application, select_student, process_application, view_application,
)
from .assignments import view_assignment, update_assignment_status
from .maintenance import (
    create_maintenance_request, view_maintenance_requests,
    update_maintenance_request,
)
from .payments import record_payment, view_payment_history
from .inventory import manage_inventory
from .inspections import create_inspection, view_inspections
from .reports import (
    generate_occupancy_report, generate_financial_report,
    export_housing_data, search_housing_records,
    check_room_availability, maintenance_summary,
    upcoming_moveouts_report, display_reports_menu,
)
from .menus import (
    display_housing_accommodation_menu,
    display_building_menu, display_application_menu,
    display_assignment_menu, display_maintenance_menu,
    display_payment_menu, display_inspection_menu,
)
