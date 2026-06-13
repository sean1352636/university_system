"""
Parking Management Package

Refactored from a single parking_management.py into separate modules.
This __init__.py re-exports all public names for backwards compatibility.
"""

# Constants
from education_system.university_system.modules.domain.campus.mobility.services.parking_management.constants import PARKING_ZONES, PERMIT_TYPES, VEHICLE_TYPES

# Models
from education_system.university_system.modules.domain.campus.mobility.services.parking_management.models import ParkingPermit, Vehicle, ParkingViolation

# Core (DB init, auth)
from education_system.university_system.modules.domain.campus.mobility.services.parking_management.core import set_auth, init_db, logger, get_connection

# Activity logging
try:
    from education_system.university_system.core.activity_logger import log_activity
except ImportError:
    def log_activity(*args, **kwargs):
        pass

# Helpers
from education_system.university_system.modules.domain.campus.mobility.services.parking_management.helpers import get_file_path

# Permits
from education_system.university_system.modules.domain.campus.mobility.services.parking_management.permits import (
    create_parking_permit, view_parking_permit,
    update_parking_permit, delete_parking_permit,
    display_permit_details,
)

# Vehicles
from education_system.university_system.modules.domain.campus.mobility.services.parking_management.vehicles import (
    register_vehicle, view_vehicle,
    update_vehicle, delete_vehicle,
    display_vehicle_details,
)

# Violations
from education_system.university_system.modules.domain.campus.mobility.services.parking_management.violations import (
    record_violation, view_violations,
    update_violation, delete_violation,
    display_violation_details,
)

# Lots
from education_system.university_system.modules.domain.campus.mobility.services.parking_management.lots import (
    view_parking_lots, add_parking_lot,
    update_parking_lot, delete_parking_lot,
    update_available_spaces,
)

# Reports
from education_system.university_system.modules.domain.campus.mobility.services.parking_management.reports import (
    generate_permit_report, generate_violation_report,
    generate_compliance_report, generate_analytics_dashboard,
    generate_revenue_report, generate_user_activity_report,
)

# Exports
from education_system.university_system.modules.domain.campus.mobility.services.parking_management.exports import (
    export_permits, export_vehicles,
    export_violations, export_parking_lots,
    export_users, export_data,
)

# Menus
from education_system.university_system.modules.domain.campus.mobility.services.parking_management.menus import (
    display_permit_menu, display_vehicle_menu,
    display_violation_menu, display_lot_menu,
    display_export_menu, display_reports_menu,
    display_parking_menu,
    pay_violation_fine, check_lot_availability,
    generate_occupancy_report,
)

# Alias used by database_manager
init_parking_db = init_db


def __getattr__(name):
    """Dynamic attribute lookup for mutable module-level state."""
    if name == 'auth':
        from education_system.university_system.modules.domain.campus.mobility.services.parking_management import core
        return core.auth
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
