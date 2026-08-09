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

from .sync.chat_rooms import _sync_module_chat_rooms

from .sync.atas import _resync_atas_after_module_change

def reassign_modules(self, student_id, module_type, cursor=None):
    """Reassign modules for a student"""
    should_close_conn = cursor is None

    try:
        if cursor is None:
            conn = get_db_connection()
            cursor = conn.cursor()

        # Import modules
        from education_system.systems.university.domain.academics.services.modules import (
            optional_module_1, optional_module_2, optional_module_3, optional_module_4,
            CS_optional_module_1, CS_optional_module_2, CS_optional_module_3, CS_optional_module_4,
            DS_optional_module_1, DS_optional_module_2, DS_optional_module_3, DS_optional_module_4
        )

        # Map module_type to the actual DB module_type value
        db_type_map = {'optional': 'optional', 'CS': 'CS_optional', 'DS': 'DS_optional'}
        db_module_type = db_type_map.get(module_type, module_type)

        # Snapshot the modules being removed so we can drop the student
        # from the corresponding chat rooms after the swap.
        cursor.execute('''
            SELECT module_code FROM student_modules
            WHERE student_id = ? AND module_code IN (
                SELECT module_code FROM modules WHERE module_type = ?
            )
        ''', (student_id, db_module_type))
        removed_codes = [row[0] for row in cursor.fetchall()]

        # Delete existing modules of this type
        cursor.execute('''
            DELETE FROM student_modules
            WHERE student_id = ? AND module_code IN (
                SELECT module_code FROM modules WHERE module_type = ?
            )
        ''', (student_id, db_module_type))

        # Select new modules
        if module_type == 'optional':
            available_modules = [optional_module_1, optional_module_2, optional_module_3, optional_module_4]
        elif module_type == 'CS':
            available_modules = [CS_optional_module_1, CS_optional_module_2, CS_optional_module_3, CS_optional_module_4]
        elif module_type == 'DS':
            available_modules = [DS_optional_module_1, DS_optional_module_2, DS_optional_module_3, DS_optional_module_4]
        else:
            return

        selected_modules = random.sample(available_modules, 2)

        # Insert new modules
        for module in selected_modules:
            cursor.execute('''
                INSERT INTO student_modules (student_id, module_code, enrollment_date, status)
                VALUES (?, ?, ?, ?)
            ''', (student_id, module['code'], datetime.now().strftime('%Y-%m-%d'), 'enrolled'))

        if should_close_conn:
            conn.commit()
            conn.close()

        # Sync chat-room memberships and notify the student. Net of what
        # actually changed: skip codes present in both old and new sets.
        added_codes = [m['code'] for m in selected_modules]
        removed_set = set(removed_codes) - set(added_codes)
        added_set = set(added_codes) - set(removed_codes)
        try:
            _sync_module_chat_rooms(student_id, list(removed_set), list(added_set))
        except Exception as e:
            logger.warning(f"reassign_modules: chat-room sync failed for {student_id}: {e}")

        # Re-evaluate ATAS clearance requirements: open new pending rows
        # for restricted modules the student has just been enrolled on,
        # close rows for restricted modules they have just dropped, and
        # flip the visa record's atas_required flag accordingly.
        # No-op if the student doesn't have a visa record on file.
        try:
            _resync_atas_after_module_change(
                student_id, list(removed_set), list(added_set),
            )
        except Exception as e:
            logger.warning(f"reassign_modules: ATAS resync failed for {student_id}: {e}")

        messagebox.showinfo(_t("common.success"), _t("student.reassign_modules_success", module_type=module_type))

    except Exception as e:
        messagebox.showerror(_t("common.error"), _t("student.failed_reassign_modules", error=str(e)))
