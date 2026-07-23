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

def _auto_join_module_chat_rooms(student_id, email_address, first_name, last_name, module_codes):
    """Create (if missing) one chat room per enrolled module, add the new
    student to each, and email them the resulting list. Best-effort; never
    raises to caller."""
    if not module_codes:
        return

    # Ensure a room exists for every module and add the student. The shared
    # helper creates any missing room (auto-generated modules have none seeded)
    # so the student is always joined to one room per module they study.
    from education_system.post_18.university_system.modules.domain.academics.services.admissions_selection.module_chat import (
        ensure_module_chat_rooms_and_join,
    )

    joined = ensure_module_chat_rooms_and_join(student_id, module_codes)

    if not joined or not email_address:
        return

    rooms_list = "\n".join(f"  • {code} — {name}" for code, name in joined)
    try:
        from education_system.post_18.university_system.infrastructure.email.email_service import send_template_email
        send_template_email(
            "chat_room_auto_joined",
            email_address,
            {
                "first_name": first_name or "",
                "last_name": last_name or "",
                "student_id": student_id,
                "module_count": str(len(joined)),
                "rooms_list": rooms_list,
            },
        )
    except Exception as e:
        logger.warning(f"auto-join: failed to send chat-room email to {email_address}: {e}")


def _resolve_module_name(cursor, code, fallback_desc=None):
    """Return a human-readable module name for a code, with fallbacks."""
    if fallback_desc:
        return fallback_desc
    cursor.execute("SELECT module_name FROM modules WHERE module_code = ?", (code,))
    row = cursor.fetchone()
    return (row[0] if row and row[0] else code)


def _sync_module_chat_rooms(student_id, removed_codes, added_codes):
    """Drop the student from chat rooms for ``removed_codes`` and add them
    to chat rooms for ``added_codes`` (creating any room that doesn't exist
    yet). Emails the student a summary of the change. Best-effort; never
    raises."""
    if not removed_codes and not added_codes:
        return

    # Delegate the DB work to the shared helper, which removes the student
    # from dropped-module rooms and ensures+joins rooms for added modules
    # (creating missing ones — auto-generated modules have no seeded room).
    from education_system.post_18.university_system.modules.domain.academics.services.admissions_selection.module_chat import (
        sync_student_module_chat_rooms,
    )
    removed_pairs, added_pairs = sync_student_module_chat_rooms(
        student_id, removed_codes, added_codes)

    if not removed_pairs and not added_pairs:
        return

    # Look up the student's contact details for the summary email.
    student_email = first_name = last_name = None
    conn = get_db_connection()
    if conn:
        try:
            srow = conn.execute(
                "SELECT email_address, first_name, last_name "
                "FROM students WHERE student_id = ?",
                (student_id,),
            ).fetchone()
            if srow:
                student_email, first_name, last_name = srow[0], srow[1], srow[2]
        finally:
            try:
                conn.close()
            except Exception:
                pass

    if not student_email:
        return

    def _fmt(pairs):
        return "\n".join(f"  • {c} — {n}" for c, n in pairs) if pairs else "  (none)"

    try:
        from education_system.post_18.university_system.infrastructure.email.email_service import send_template_email
        send_template_email(
            "chat_room_membership_changed",
            student_email,
            {
                "first_name": first_name or "",
                "last_name": last_name or "",
                "student_id": student_id,
                "added_count": str(len(added_pairs)),
                "added_list": _fmt(added_pairs),
                "removed_count": str(len(removed_pairs)),
                "removed_list": _fmt(removed_pairs),
            },
        )
    except Exception as e:
        logger.warning(f"chat-sync: failed to send membership-change email to {student_email}: {e}")


