"""SQLite schema and bootstrap for the Nursery System.

Creates the shared ``nursery.db`` with ``pupils`` (the children on roll) and
``staff`` tables. Column shapes follow the Early Years / EYFS domain and stay
compatible with the cross-system superadmin dashboard, which counts the
``pupils`` and ``staff`` tables via ``shared/admin_portal/admin_service.py``.

``init_db()`` is idempotent (``CREATE TABLE IF NOT EXISTS``) and is called on
every nursery launch from ``cli_main.run`` / ``gui_main.run``.
"""

from __future__ import annotations

import datetime as _dt
import logging
import sqlite3

from education_system.paths import NURSERY_DB, ensure_nursery_directories
from education_system.systems.nursery.infrastructure.schema.children_staff import (
    _migrate_pupils,
    PUPILS_PARITY_COLUMNS,
    _PUPILS_SCHEMA,
    _ROOMS_SCHEMA,
    _STAFF_SCHEMA,
)
from education_system.systems.nursery.infrastructure.schema.admissions import (
    _ADMISSIONS_SCHEMA,
    _ENROLMENTS_SCHEMA,
    _FUNDED_HOURS_SCHEMA,
    _LEAVERS_SCHEMA,
    _SETTLING_IN_SCHEMA,
    _TRANSITIONS_SCHEMA,
)
from education_system.systems.nursery.infrastructure.schema.workforce import (
    _PFA_SCHEMA,
    _ROTA_SCHEMA,
    _STAFF_PAY_SCHEMA,
    _TRAINING_SCHEMA,
)
from education_system.systems.nursery.infrastructure.schema.finance import (
    _DISCOUNTS_SCHEMA,
    _FUNDING_CLAIMS_SCHEMA,
    _INVOICES_SCHEMA,
    _PAYMENTS_SCHEMA,
    _VOUCHERS_SCHEMA,
)
from education_system.systems.nursery.infrastructure.schema.parents import (
    _CONSENTS_SCHEMA,
    _DAILY_UPDATES_SCHEMA,
    _EMERGENCY_CONTACTS_SCHEMA,
    _FORM_SUBMISSIONS_SCHEMA,
    _FORM_TEMPLATES_SCHEMA,
    _NEWSLETTERS_SCHEMA,
    _PARENT_CONTACTS_SCHEMA,
    _PARENT_MEETINGS_SCHEMA,
    _PARENT_MESSAGES_SCHEMA,
    _PARENT_REQUESTS_SCHEMA,
)
from education_system.systems.nursery.infrastructure.schema.care import (
    _ACCIDENT_SCHEMA,
    _ATTENDANCE_SCHEMA,
    _BOTTLE_FEEDS_SCHEMA,
    _DAILY_DIARY_SCHEMA,
    _DIETARY_SCHEMA,
    _EXISTING_INJURIES_SCHEMA,
    _MEALS_SCHEMA,
    _MEDICATION_LOG_SCHEMA,
    _SIGN_IN_OUT_SCHEMA,
    _SLEEP_LOG_SCHEMA,
    _TOILETING_LOG_SCHEMA,
)
from education_system.systems.nursery.infrastructure.schema.eyfs import (
    _COHORT_TRACKING_SCHEMA,
    _CURRICULUM_PLANNING_SCHEMA,
    _DEVELOPMENT_TRACKING_SCHEMA,
    _EFFECTIVE_LEARNING_SCHEMA,
    _EVIDENCE_SCHEMA,
    _EYFS_PROFILE_SCHEMA,
    _LEARNING_JOURNEYS_SCHEMA,
    _NEXT_STEPS_SCHEMA,
    _OBSERVATIONS_SCHEMA,
    _PROGRESS_CHECK_2YR_SCHEMA,
)
from education_system.systems.nursery.infrastructure.schema.bookings import (
    _BOOKING_PATTERNS_SCHEMA,
    _CLOSURES_SCHEMA,
    _COLLECTORS_SCHEMA,
    _LATE_COLLECTIONS_SCHEMA,
    _SESSION_BOOKINGS_SCHEMA,
)
from education_system.systems.nursery.infrastructure.schema.operations import (
    _MENU_INGREDIENTS_SCHEMA,
    _MENU_PLAN_SCHEMA,
    _PURCHASE_ORDER_LINES_SCHEMA,
    _PURCHASE_ORDERS_SCHEMA,
    _STOCK_ITEMS_SCHEMA,
    _STOCK_MOVEMENTS_SCHEMA,
    _SUPPLIERS_SCHEMA,
)
from education_system.systems.nursery.infrastructure.demo_seed import (
    _DEMO_ADMISSIONS,
    _DEMO_PUPILS,
    _DEMO_ROOMS,
    _DEMO_STAFF,
    _last_weekdays,
    _seed_attendance,
    _seed_demo_data,
)

logger = logging.getLogger(__name__)


def connect() -> sqlite3.Connection:
    """Open a connection to the nursery DB, creating the data dir if needed."""
    ensure_nursery_directories()
    conn = sqlite3.connect(str(NURSERY_DB))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """Create the nursery tables if they don't exist (idempotent)."""
    conn = connect()
    try:
        conn.executescript(_STAFF_SCHEMA)
        conn.executescript(_PUPILS_SCHEMA)
        _migrate_pupils(conn)
        conn.executescript(_ROOMS_SCHEMA)
        conn.executescript(_ADMISSIONS_SCHEMA)
        conn.executescript(_ENROLMENTS_SCHEMA)
        conn.executescript(_FUNDED_HOURS_SCHEMA)
        conn.executescript(_SETTLING_IN_SCHEMA)
        conn.executescript(_TRANSITIONS_SCHEMA)
        conn.executescript(_LEAVERS_SCHEMA)
        conn.executescript(_ROTA_SCHEMA)
        conn.executescript(_TRAINING_SCHEMA)
        conn.executescript(_PFA_SCHEMA)
        conn.executescript(_INVOICES_SCHEMA)
        conn.executescript(_PAYMENTS_SCHEMA)
        conn.executescript(_FUNDING_CLAIMS_SCHEMA)
        conn.executescript(_VOUCHERS_SCHEMA)
        conn.executescript(_DISCOUNTS_SCHEMA)
        conn.executescript(_PARENT_CONTACTS_SCHEMA)
        conn.executescript(_EMERGENCY_CONTACTS_SCHEMA)
        conn.executescript(_CONSENTS_SCHEMA)
        conn.executescript(_PARENT_MESSAGES_SCHEMA)
        conn.executescript(_DAILY_UPDATES_SCHEMA)
        conn.executescript(_NEWSLETTERS_SCHEMA)
        conn.executescript(_PARENT_MEETINGS_SCHEMA)
        conn.executescript(_EYFS_PROFILE_SCHEMA)
        conn.executescript(_DEVELOPMENT_TRACKING_SCHEMA)
        conn.executescript(_OBSERVATIONS_SCHEMA)
        conn.executescript(_LEARNING_JOURNEYS_SCHEMA)
        conn.executescript(_NEXT_STEPS_SCHEMA)
        conn.executescript(_PROGRESS_CHECK_2YR_SCHEMA)
        conn.executescript(_EFFECTIVE_LEARNING_SCHEMA)
        conn.executescript(_CURRICULUM_PLANNING_SCHEMA)
        conn.executescript(_COHORT_TRACKING_SCHEMA)
        conn.executescript(_EVIDENCE_SCHEMA)
        conn.executescript(_ATTENDANCE_SCHEMA)
        conn.executescript(_ACCIDENT_SCHEMA)
        conn.executescript(_SIGN_IN_OUT_SCHEMA)
        conn.executescript(_DAILY_DIARY_SCHEMA)
        conn.executescript(_SLEEP_LOG_SCHEMA)
        conn.executescript(_TOILETING_LOG_SCHEMA)
        conn.executescript(_MEALS_SCHEMA)
        conn.executescript(_BOTTLE_FEEDS_SCHEMA)
        conn.executescript(_DIETARY_SCHEMA)
        conn.executescript(_EXISTING_INJURIES_SCHEMA)
        conn.executescript(_MEDICATION_LOG_SCHEMA)
        conn.executescript(_BOOKING_PATTERNS_SCHEMA)
        conn.executescript(_SESSION_BOOKINGS_SCHEMA)
        conn.executescript(_CLOSURES_SCHEMA)
        conn.executescript(_COLLECTORS_SCHEMA)
        conn.executescript(_LATE_COLLECTIONS_SCHEMA)
        conn.executescript(_PARENT_REQUESTS_SCHEMA)
        conn.executescript(_FORM_TEMPLATES_SCHEMA)
        conn.executescript(_FORM_SUBMISSIONS_SCHEMA)
        conn.executescript(_SUPPLIERS_SCHEMA)
        conn.executescript(_STOCK_ITEMS_SCHEMA)
        conn.executescript(_STOCK_MOVEMENTS_SCHEMA)
        conn.executescript(_PURCHASE_ORDERS_SCHEMA)
        conn.executescript(_PURCHASE_ORDER_LINES_SCHEMA)
        conn.executescript(_STAFF_PAY_SCHEMA)
        conn.executescript(_MENU_PLAN_SCHEMA)
        conn.executescript(_MENU_INGREDIENTS_SCHEMA)
        conn.commit()
        _seed_demo_data(conn)
    finally:
        conn.close()
    logger.debug("Nursery database ready at %s", NURSERY_DB)
