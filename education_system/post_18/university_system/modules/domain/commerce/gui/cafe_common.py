"""Shared helpers for the cafe system GUI mixins.

These were previously defined directly in :mod:`cafe_system_gui`, but
the seven mixin modules (cafe_inventory, cafe_menu, cafe_orders,
cafe_pos, cafe_refunds, cafe_reports, cafe_user_service) need them
*and* are imported by `cafe_system_gui` itself, which produced a
circular import. Extracting the helpers into this leaf module breaks
the cycle: both `cafe_system_gui` and the mixins import from here, and
nothing here imports from any of them.
"""

from __future__ import annotations

from education_system.post_18.university_system.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH


# ---------------------------------------------------------------------------
# Optional integrations — same try/except blocks that used to live in
# cafe_system_gui.py.  Defined here so the mixins can read the flags
# without importing from cafe_system_gui.
# ---------------------------------------------------------------------------

try:
    from education_system.post_18.university_system.modules.shared.utils.finance_integration import (  # noqa: F401
        process_student_finance_account_payment,
        get_student_finance_account_balance,
        get_student_info,
        record_payment_to_finance,
    )
    FINANCE_ACCOUNT_AVAILABLE = True
except ImportError:
    FINANCE_ACCOUNT_AVAILABLE = False
    print("Warning: Student finance account integration not available")

try:
    from education_system.post_18.university_system.infrastructure.email.email_service import send_email  # noqa: F401
    EMAIL_SERVICE_AVAILABLE = True
except ImportError:
    EMAIL_SERVICE_AVAILABLE = False
    print("Warning: Email service not available")


# ---------------------------------------------------------------------------
# Database connection helper
# ---------------------------------------------------------------------------

def get_db_connection():
    """Return a SQLite connection to the cafe database, or ``None`` on error."""
    try:
        return sqlite3.connect(str(DEFAULT_DB_PATH))
    except (sqlite3.Error, OSError) as exc:
        print(f"Database connection error: {exc}")
        return None


__all__ = [
    "FINANCE_ACCOUNT_AVAILABLE",
    "EMAIL_SERVICE_AVAILABLE",
    "get_db_connection",
]
