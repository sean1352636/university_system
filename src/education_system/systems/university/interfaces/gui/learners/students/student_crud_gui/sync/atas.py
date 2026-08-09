# Auto-generated module (split from student_crud_gui.py)
import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import logging
import random
import secrets
import json
import csv
from education_system.systems.university.infrastructure.database.db import sqlite3
from datetime import datetime
from education_system.systems.university.interfaces.gui.shell.main._tk_callback_filter import install_clean_close as _install_clean_close

from education_system.systems.university.infrastructure.i18n import get_text as _t
from education_system.systems.university.infrastructure.database.db import get_db_connection, get_connection, transaction
from education_system.systems.university.infrastructure.sql_safety import (
    validate_table_name,
    validate_column_name,
    SQLIdentifierError,
)

logger = logging.getLogger("education_system.systems.university.interfaces.gui.learners.students.student_crud_gui")

try:
    from education_system.systems.university.infrastructure.activity_logger import log_activity
    ACTIVITY_LOGGER_AVAILABLE = True
except ImportError:
    ACTIVITY_LOGGER_AVAILABLE = False

def _resync_atas_after_module_change(student_id, removed_codes, added_codes):
    """When an international student's modules change, keep the ATAS picture
    aligned with what they're now enrolled on.

    For each newly-added module that matches an ATAS-restricted prefix:
      - open a pending ``atas_clearances`` row (idempotent — skipped if a
        non-withdrawn row for that (student, module) already exists).

    For each removed module that matches an ATAS-restricted prefix:
      - mark its existing pending/cleared row as ``withdrawn`` (we keep the
        history rather than deleting, so a re-enrolment stays auditable).

    Then flip the visa record's ``atas_required`` flag to reflect whether
    the student now needs ATAS for *any* current module.

    No-op when the student has no visa record on file (i.e. not flagged
    international). Best-effort; failures only log."""
    from education_system.systems.university.domain.governance.compliance.international_compliance.services import (
        visa_service as vs,
    )

    visa = vs.get_visa_record(student_id)
    if not visa:
        return  # Domestic student or no record yet — nothing to re-evaluate.

    added_atas = [c for c in (added_codes or []) if vs.is_atas_required_for_module(c)]
    removed_atas = [c for c in (removed_codes or []) if vs.is_atas_required_for_module(c)]

    conn = get_db_connection()
    if not conn:
        logger.warning("ATAS resync: no DB connection")
        return
    try:
        cursor = conn.cursor()
        for code in added_atas:
            cursor.execute(
                "SELECT 1 FROM atas_clearances "
                "WHERE student_id = ? AND module_code = ? AND status != 'withdrawn' "
                "LIMIT 1",
                (student_id, code),
            )
            if cursor.fetchone():
                continue
            cursor.execute(
                """INSERT INTO atas_clearances (
                    student_id, module_code, certificate_number,
                    issued_on, expires_on, status, notes
                ) VALUES (?, ?, NULL, NULL, NULL, 'pending', ?)""",
                (student_id, code,
                 f"Auto-opened on module reassignment ({code} added)"),
            )
        for code in removed_atas:
            cursor.execute(
                "UPDATE atas_clearances SET status = 'withdrawn', "
                "notes = COALESCE(notes, '') || ? "
                "WHERE student_id = ? AND module_code = ? AND status != 'withdrawn'",
                (f" | Auto-withdrawn on module reassignment ({code} dropped)",
                 student_id, code),
            )
        conn.commit()
    finally:
        try:
            conn.close()
        except Exception:
            pass

    # Flip the visa-record flag based on the current enrolment, not just
    # the diff — a student can have remaining ATAS modules even after
    # dropping one.
    still_required = bool(vs.atas_required_for_student_modules(student_id))
    if bool(visa.get("atas_required")) != still_required:
        rec = vs.VisaRecord(
            student_id=student_id,
            nationality=visa.get("nationality"),
            passport_number=visa.get("passport_number"),
            passport_expiry=visa.get("passport_expiry"),
            visa_type=visa.get("visa_type") or "student_route",
            visa_number=visa.get("visa_number"),
            visa_start_date=visa.get("visa_start_date"),
            visa_expiry_date=visa.get("visa_expiry_date"),
            brp_number=visa.get("brp_number"),
            brp_expiry_date=visa.get("brp_expiry_date"),
            sponsor_licence_ref=visa.get("sponsor_licence_ref"),
            atas_required=still_required,
            status=visa.get("status") or "pending",
            notes=visa.get("notes"),
        )
        vs.upsert_visa_record(rec)
    logger.info(
        "ATAS resync sid=%s: opened=%s withdrawn=%s flag=%s",
        student_id, added_atas, removed_atas, still_required,
    )


