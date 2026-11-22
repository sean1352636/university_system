import logging

logger = logging.getLogger(__name__)

from education_system.systems.university.domains.health.infrastructure.health.storage import sqlite3, get_connection
from datetime import datetime, timedelta


def init_enhanced_health_db():
    """The health tables, once per database file — see
    ``infrastructure/health/health_schema`` (also applied by migration
    ``a0d2f4b6c8e1``). This module used to declare them a second time, and
    dropped ``data_retention_policies`` outright when an old layout lacked a
    column; the schema module adds the column instead."""
    from education_system.systems.university.domains.health.infrastructure.health import (
        health_schema,
    )
    try:
        health_schema.ensure()
    except sqlite3.Error as e:
        print(f"An error occurred while initializing the enhanced health database: {e}")


def ensure_student_dob_compat():
    """Kept for its callers. The date-of-birth fix now lives in the health
    schema (``health_schema._students_dob``): a database with only
    ``date_of_birth`` gains ``dob``; ``students`` is otherwise left alone —
    readers use whichever column exists (``analytics/population._dob_column``)."""
    try:
        init_enhanced_health_db()
    except Exception as e:
        # Don't crash menus if the schema can't be applied; just surface a note.
        print(f"(Schema compat) {e}")
