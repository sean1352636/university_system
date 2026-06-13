"""
Parking Management GUI package.

Split from the monolithic parking_management_gui.py into logical modules.
All public symbols are re-exported here for backward compatibility.
"""
from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH  # noqa: F401

import tkinter as tk  # noqa: F401
from tkinter import ttk, messagebox, simpledialog, filedialog  # noqa: F401
from tkinter.scrolledtext import ScrolledText  # noqa: F401
from education_system.university_system.infrastructure.database.db import sqlite3  # noqa: F401
from datetime import datetime, timedelta  # noqa: F401
import logging  # noqa: F401
import threading  # noqa: F401
import os  # noqa: F401
import sys  # noqa: F401

# i18n
from education_system.university_system.core.i18n import (
    init_i18n,
    get_text as _t,
    get_current_language,
)
from education_system.university_system.modules.shared.utils.gui_language_selector import (
    show_gui_language_selector,
    create_language_menu_button,
)

# Email templates (optional)
try:
    from education_system.university_system.infrastructure.email.template_utils import render_template
    TEMPLATE_AVAILABLE = True
except ImportError:
    TEMPLATE_AVAILABLE = False
    render_template = None

# Compatibility layer (optional)
try:
    from education_system.university_system.modules.domain.campus.mobility.services.parking_compatibility import (
        set_gui_mode, get_function_output, validate_gui_data,
        get_user_permissions, format_console_output_for_gui,
        execute_console_function_with_params, cleanup_compatibility_layer
    )
    COMPATIBILITY_AVAILABLE = True
except ImportError:
    COMPATIBILITY_AVAILABLE = False

# Infrastructure imports (independent of service layer)
from education_system.university_system.infrastructure.database.db import get_connection  # noqa: F401
from education_system.university_system.infrastructure.auth import UserAuth  # noqa: F401
from education_system.university_system.infrastructure.shared_context import get_auth  # noqa: F401

# Parking management service functions
try:
    from education_system.university_system.modules.domain.campus.mobility.services.parking_management import (
        init_db, set_auth, PARKING_ZONES, PERMIT_TYPES, VEHICLE_TYPES,
        create_parking_permit, view_parking_permit, update_parking_permit, delete_parking_permit,
        register_vehicle, view_vehicle, update_vehicle, delete_vehicle,
        record_violation, generate_compliance_report, generate_revenue_report,
        generate_user_activity_report, export_users,
        view_violations, update_violation, delete_violation,
        view_parking_lots, add_parking_lot, update_parking_lot, delete_parking_lot,
        generate_permit_report, generate_violation_report, generate_analytics_dashboard,
        export_permits, export_vehicles, export_violations, export_parking_lots
    )
    PARKING_MANAGEMENT_AVAILABLE = True
except ImportError as e:
    PARKING_MANAGEMENT_AVAILABLE = False
    print(f"Warning: Could not import parking management modules: {e}")
    PARKING_ZONES = {
        'A': {'name': 'Faculty/Staff', 'hourly_rate': 0, 'annual_fee': 250},
        'B': {'name': 'Commuter Students', 'hourly_rate': 0, 'annual_fee': 180},
        'C': {'name': 'Resident Students', 'hourly_rate': 0, 'annual_fee': 220},
        'V': {'name': 'Visitor', 'hourly_rate': 2.50, 'annual_fee': 0},
        'H': {'name': 'Handicap Accessible', 'hourly_rate': 0, 'annual_fee': 150},
        'M': {'name': 'Metered', 'hourly_rate': 1.75, 'annual_fee': 0},
        'R': {'name': 'Reserved', 'hourly_rate': 0, 'annual_fee': 350},
    }
    PERMIT_TYPES = ['Annual', 'Semester', 'Monthly', 'Daily', 'Temporary']
    VEHICLE_TYPES = ['Sedan', 'SUV', 'Truck', 'Motorcycle', 'Compact', 'Van']

# Public API
from education_system.university_system.modules.domain.campus.mobility.gui.parking_management.main_gui import ParkingManagementGUI, run_console_interface, main
from education_system.university_system.modules.domain.campus.mobility.gui.parking_management.dialogs.permit_dialog import PermitDialog
from education_system.university_system.modules.domain.campus.mobility.gui.parking_management.dialogs.vehicle_dialog import VehicleDialog
from education_system.university_system.modules.domain.campus.mobility.gui.parking_management.dialogs.violation_dialog import ViolationDialog
from education_system.university_system.modules.domain.campus.mobility.gui.parking_management.dialogs.lot_dialog import LotDialog
from education_system.university_system.modules.domain.campus.mobility.gui.parking_management.dialogs.export_dialog import ExportDialog
from education_system.university_system.modules.domain.campus.mobility.gui.parking_management.dialogs.payment_dialog import PaymentDialog
from education_system.university_system.modules.domain.campus.mobility.gui.parking_management.dialogs.refund_dialog import RefundDialog

__all__ = [
    'ParkingManagementGUI', 'run_console_interface', 'main',
    'PermitDialog', 'VehicleDialog', 'ViolationDialog', 'LotDialog',
    'ExportDialog', 'PaymentDialog', 'RefundDialog',
]
