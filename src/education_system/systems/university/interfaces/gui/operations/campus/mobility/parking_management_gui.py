"""
Backward-compatible shim for parking_management_gui.

This module has been split into the parking_management package.
All public symbols are re-exported here for backward compatibility.
"""
# Re-export everything from the new package so existing imports continue to work.
# e.g. "from education_system.systems.university.interfaces.gui.operations.campus.mobility.parking_management_gui import ParkingManagementGUI"
from education_system.systems.university.infrastructure.database.db import DEFAULT_DB_PATH  # noqa: F401
from education_system.systems.university.infrastructure.database.db import sqlite3  # noqa: F401

# Re-export conditional imports that tests may patch on this module
try:
    from education_system.systems.university.infrastructure.database.db import get_connection  # noqa: F401
    from education_system.systems.university.infrastructure.database.db import transaction  # noqa: F401
except ImportError:
    pass

try:
    from education_system.systems.university.infrastructure.shared_context import get_auth as get_centralized_auth  # noqa: F401
except ImportError:
    pass

try:
    from education_system.systems.university.infrastructure.utils.activity_logger import log_activity  # noqa: F401
except ImportError:
    pass

from tkinter import messagebox, filedialog  # noqa: F401

from education_system.systems.university.interfaces.gui.operations.campus.mobility.parking_management import (  # noqa: F401
    ParkingManagementGUI,
    PermitDialog,
    VehicleDialog,
    ViolationDialog,
    LotDialog,
    ExportDialog,
    PaymentDialog,
    RefundDialog,
    run_console_interface,
    main,
)

# Re-export constants and service functions
from education_system.systems.university.interfaces.gui.operations.campus.mobility.parking_management import (  # noqa: F401
    PARKING_ZONES, PERMIT_TYPES, VEHICLE_TYPES,
    TEMPLATE_AVAILABLE, PARKING_MANAGEMENT_AVAILABLE,
)
