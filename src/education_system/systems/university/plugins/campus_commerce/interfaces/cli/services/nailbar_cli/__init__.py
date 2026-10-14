"""
Nail Bar CLI for University Management System

Provides comprehensive nail bar/salon services including treatments, appointments,
technicians management, and reporting with finance and email integration.

Split into cohesive modules; this package is the public surface. Optional
integrations (auth, email, finance, activity logging) are resolved here and read
back through this module at call time, so patching ``nailbar_cli.get_auth`` or
``nailbar_cli.EMAIL_AVAILABLE`` affects every submodule.
"""

import logging

# Import centralized database and authentication
from education_system.systems.university.infrastructure.database.db import get_connection, transaction
from education_system.systems.university.infrastructure.shared_context import get_auth

# Import nailbar core services (or the fallback schema)
from .schema import init_nailbar_db, NAIL_TREATMENTS, NAILBAR_CORE_AVAILABLE

# Import email service
try:
    from education_system.systems.university.infrastructure.email.email_service import send_email  # noqa: F401
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False

# Import finance integration
try:
    from education_system.systems.university.domains.finance.infrastructure.finance_integration import (
        record_payment_to_finance,  # noqa: F401
        process_student_finance_account_payment,  # noqa: F401
    )
    FINANCE_AVAILABLE = True
except ImportError:
    FINANCE_AVAILABLE = False

# Import activity logger
try:
    from education_system.systems.university.infrastructure.activity_logger import log_activity
    ACTIVITY_LOGGER_AVAILABLE = True
except ImportError:
    ACTIVITY_LOGGER_AVAILABLE = False

    def log_activity(action, entity, **kwargs):
        pass

logger = logging.getLogger(__name__)

# Submodules read the seams above off this package at call time, so they must be
# imported only once those names exist.
from .helpers import (  # noqa: E402
    format_currency, format_date, generate_booking_ref, generate_receipt_number,
    get_current_user, is_staff, print_header, print_subheader,
)
from .treatments import (  # noqa: E402
    add_treatment, update_treatment, view_treatments,
    view_treatments_by_category,
)
from .technicians import (  # noqa: E402
    manage_technician_schedule, technician_performance, view_technicians,
)
from .appointments import (  # noqa: E402
    book_appointment, cancel_appointment, view_my_appointments,
)
from .payments import complete_appointment, view_payment_history  # noqa: E402
from .reports import (  # noqa: E402
    customer_retention_stats, daily_schedule_report,
    popular_treatments_analysis, revenue_report,
)
from .menu import launch_nailbar_cli, nailbar_menu, staff_menu  # noqa: E402

__all__ = [
    # utilities
    'print_header', 'print_subheader', 'get_current_user', 'is_staff',
    'generate_booking_ref', 'generate_receipt_number', 'format_currency',
    'format_date',
    # treatments
    'view_treatments', 'view_treatments_by_category', 'add_treatment',
    'update_treatment',
    # technicians
    'view_technicians', 'technician_performance', 'manage_technician_schedule',
    # appointments
    'book_appointment', 'view_my_appointments', 'cancel_appointment',
    # payments
    'complete_appointment', 'view_payment_history',
    # reports
    'daily_schedule_report', 'revenue_report', 'popular_treatments_analysis',
    'customer_retention_stats',
    # menus / entry point
    'staff_menu', 'nailbar_menu', 'launch_nailbar_cli',
    # schema + integration state
    'init_nailbar_db', 'NAIL_TREATMENTS', 'NAILBAR_CORE_AVAILABLE',
    'EMAIL_AVAILABLE', 'FINANCE_AVAILABLE', 'ACTIVITY_LOGGER_AVAILABLE',
    'log_activity', 'get_auth', 'get_connection', 'transaction', 'logger',
]


if __name__ == "__main__":
    nailbar_menu()
