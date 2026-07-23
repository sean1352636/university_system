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

def _ensure_shared_auth_user(username, password, display_name, email):
    """Create the user in the central shared auth.db if not already present.

    Login, forgot-password and MFA all read from auth.db, so a student that
    only exists in student_records.db cannot log in. Idempotent: a duplicate
    username comes back as a benign "already exists" and is treated as
    success."""
    from education_system.shared.auth.core import UserAuth as SharedUserAuth
    from education_system.shared.auth.exceptions import AuthError as SharedAuthError

    shared_auth = SharedUserAuth()
    try:
        return shared_auth.create_user(
            username=username,
            password=password,
            display_name=display_name,
            email=email,
            systems=[("university", "student")],
        )
    except SharedAuthError as e:
        # Existing username — that's fine, the row is there.
        if "already exists" in str(e).lower():
            return None
        raise


def _purge_user_from_all_chat_rooms(user_id):
    """Remove the user from every chat room and delete every message they
    have sent. Used during student deletion. Best-effort; never raises."""
    if not user_id:
        return
    conn = get_db_connection()
    if not conn:
        logger.warning("chat-purge: no DB connection")
        return
    try:
        cursor = conn.cursor()
        # Order matters only loosely (no FK from messages to members).
        cursor.execute("DELETE FROM chat_messages WHERE sender_id = ?", (user_id,))
        msgs = cursor.rowcount
        cursor.execute("DELETE FROM chat_room_members WHERE user_id = ?", (user_id,))
        members = cursor.rowcount
        # Invitations for or by this user, if the table exists.
        try:
            cursor.execute(
                "DELETE FROM chat_room_invitations WHERE user_id = ? OR invited_by = ?",
                (user_id, user_id),
            )
        except sqlite3.OperationalError:
            pass  # table might not exist on minimal installs
        conn.commit()
        logger.info(
            f"chat-purge: user_id={user_id} → removed {members} memberships, "
            f"deleted {msgs} messages"
        )
    except Exception as e:
        logger.warning(f"chat-purge: failed for user_id={user_id}: {e}")
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        try:
            conn.close()
        except Exception:
            pass


