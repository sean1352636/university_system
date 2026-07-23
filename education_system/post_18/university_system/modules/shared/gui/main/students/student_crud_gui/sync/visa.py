# Auto-generated module (split from student_crud_gui.py)
import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import logging
import random
import secrets
import json
import csv
from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from datetime import datetime
from education_system.post_18.university_system.modules.shared.gui.main._tk_callback_filter import install_clean_close as _install_clean_close

from education_system.post_18.university_system.core.i18n import get_text as _t
from education_system.post_18.university_system.infrastructure.database.db import get_db_connection, get_connection, transaction
from education_system.post_18.university_system.core.sql_safety import (
    validate_table_name,
    validate_column_name,
    SQLIdentifierError,
)

logger = logging.getLogger("education_system.post_18.university_system.modules.shared.gui.main.students.student_crud_gui")

try:
    from education_system.post_18.university_system.core.activity_logger import log_activity
    ACTIVITY_LOGGER_AVAILABLE = True
except ImportError:
    ACTIVITY_LOGGER_AVAILABLE = False

def _create_visa_record_for_new_student(student_id, email_address, first_name,
                                         nationality, passport_number,
                                         visa_expiry_date, brp_number, module_codes):
    """Create the initial Tier-4 visa record for a newly enrolled international
    student, flag ATAS modules, and email a right-to-study check reminder.

    All best-effort: a problem here must never block student creation. The
    record starts in ``status='pending'`` because we don't yet have the
    in-person right-to-study check on file."""
    from education_system.post_18.university_system.modules.domain.student_affairs.international_compliance.services import (
        visa_service as vs,
    )

    atas_codes = [c for c in (module_codes or []) if vs.is_atas_required_for_module(c)]
    rec = vs.VisaRecord(
        student_id=student_id,
        nationality=nationality,
        passport_number=passport_number,
        visa_expiry_date=visa_expiry_date,
        brp_number=brp_number,
        atas_required=bool(atas_codes),
        status="pending",
    )
    vs.upsert_visa_record(rec)
    for code in atas_codes:
        vs.record_atas_clearance(
            student_id=student_id, module_code=code,
            certificate_number=None, issued_on=None, expires_on=None,
            status="pending",
            notes=f"Auto-flagged at enrolment for {code} (ATAS-restricted prefix)",
        )
    if email_address:
        vs.notify_right_to_study_required(student_id, email_address, first_name=first_name or "")


