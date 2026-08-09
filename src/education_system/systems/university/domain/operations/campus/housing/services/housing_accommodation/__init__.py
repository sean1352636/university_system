"""Housing Accommodation Management - Package

This package was refactored from a single module into multiple sub-modules
for maintainability. All public functions are re-exported here for backward
compatibility.
"""

from education_system.systems.university.domain.operations.campus.housing.services.housing_accommodation.common import set_auth, generate_id
from education_system.systems.university.domain.operations.campus.housing.services.housing_accommodation.database import init_housing_db
from education_system.systems.university.domain.operations.campus.housing.services.housing_accommodation.buildings import (
    create_building, create_rooms_for_building, view_building,
    update_building, delete_building,
)
from education_system.systems.university.domain.operations.campus.housing.services.housing_accommodation.applications import (
    create_application, select_student, process_application, view_application,
)
from education_system.systems.university.domain.operations.campus.housing.services.housing_accommodation.assignments import view_assignment, update_assignment_status
from education_system.systems.university.domain.operations.campus.housing.services.housing_accommodation.maintenance import (
    create_maintenance_request, view_maintenance_requests,
    update_maintenance_request,
)
from education_system.systems.university.domain.operations.campus.housing.services.housing_accommodation.payments import record_payment, view_payment_history
from education_system.systems.university.domain.operations.campus.housing.services.housing_accommodation.inventory import manage_inventory
from education_system.systems.university.domain.operations.campus.housing.services.housing_accommodation.inspections import create_inspection, view_inspections
from education_system.systems.university.domain.operations.campus.housing.services.housing_accommodation.reports import (
    generate_occupancy_report, generate_financial_report,
    export_housing_data, search_housing_records,
    check_room_availability, maintenance_summary,
    upcoming_moveouts_report, display_reports_menu,
)
from education_system.systems.university.domain.operations.campus.housing.services.housing_accommodation.menus import (
    display_housing_accommodation_menu,
    display_building_menu, display_application_menu,
    display_assignment_menu, display_maintenance_menu,
    display_payment_menu, display_inspection_menu,
)
