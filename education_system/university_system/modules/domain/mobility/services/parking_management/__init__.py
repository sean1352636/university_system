"""
Parking Management Package

Refactored from a single parking_management.py into separate modules.
This __init__.py re-exports all public names for backwards compatibility.
"""

# Constants
from .constants import PARKING_ZONES, PERMIT_TYPES, VEHICLE_TYPES

# Models
from .models import ParkingPermit, Vehicle, ParkingViolation

# Core (DB init, auth)
from .core import set_auth, init_db, logger

# Helpers
from .helpers import get_file_path

# Permits
from .permits import (
    create_parking_permit, view_parking_permit,
    update_parking_permit, delete_parking_permit,
    display_permit_details,
)

# Vehicles
from .vehicles import (
    register_vehicle, view_vehicle,
    update_vehicle, delete_vehicle,
    display_vehicle_details,
)

# Violations
from .violations import (
    record_violation, view_violations,
    update_violation, delete_violation,
    display_violation_details,
)

# Lots
from .lots import (
    view_parking_lots, add_parking_lot,
    update_parking_lot, delete_parking_lot,
    update_available_spaces,
)

# Reports
from .reports import (
    generate_permit_report, generate_violation_report,
    generate_compliance_report, generate_analytics_dashboard,
    generate_revenue_report, generate_user_activity_report,
)

# Exports
from .exports import (
    export_permits, export_vehicles,
    export_violations, export_parking_lots,
    export_users, export_data,
)

# Menus
from .menus import (
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
        from . import core
        return core.auth
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
