"""Student ID service — database operations and business logic for digital student ID cards."""

import hashlib
import json
import logging
from datetime import datetime

from education_system.systems.university.infrastructure.database.db import get_connection

logger = logging.getLogger(__name__)


def init_db():
    """Create the student_id_cards table if it does not exist."""
    with get_connection() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS student_id_cards (
            card_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL UNIQUE,
            card_number TEXT NOT NULL,
            issue_date TEXT DEFAULT (date('now')),
            expiry_date TEXT,
            status TEXT DEFAULT 'active',
            photo_path TEXT DEFAULT '',
            qr_data TEXT DEFAULT ''
        )""")


# ---------------------------------------------------------------------------
# Card helpers
# ---------------------------------------------------------------------------

def _generate_card_number(student_id, salt=""):
    """Return a deterministic card number string like ``UNI-A1B2C3D4``."""
    return "UNI-" + hashlib.sha256((student_id + salt).encode()).hexdigest()[:8].upper()


def _generate_qr_data(student_id, card_number):
    """Return a JSON string suitable for encoding as a QR code."""
    return json.dumps({"student_id": student_id, "card": card_number, "type": "student_id"})


# ---------------------------------------------------------------------------
# Student info
# ---------------------------------------------------------------------------

def get_student_details(student_id):
    """Look up student demographic info from the ``students`` table.

    Returns a dict with keys: ``name``, ``email``, ``course``, ``department``, ``year``.
    Missing fields default to ``'N/A'``.
    """
    info = {
        "name": "N/A",
        "email": "N/A",
        "course": "N/A",
        "department": "N/A",
        "year": "N/A",
    }
    with get_connection() as conn:
        try:
            row = conn.execute(
                "SELECT * FROM students WHERE student_id = ? OR username = ?",
                (student_id, student_id),
            ).fetchone()
        except Exception:
            return info
        if not row:
            return info
        keys = row.keys() if hasattr(row, "keys") else []
        if "full_name" in keys:
            info["name"] = row["full_name"]
        elif "name" in keys:
            info["name"] = row["name"]
        if "email" in keys:
            info["email"] = row["email"]
        if "course" in keys:
            info["course"] = row["course"]
        if "department" in keys:
            info["department"] = row["department"]
        if "year_of_study" in keys:
            info["year"] = str(row["year_of_study"])
        elif "year" in keys:
            info["year"] = str(row["year"])
    return info


# ---------------------------------------------------------------------------
# Card CRUD
# ---------------------------------------------------------------------------

def get_card(student_id):
    """Return the card row for *student_id*, or ``None``."""
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM student_id_cards WHERE student_id = ?", (student_id,)
        ).fetchone()


def get_or_create_card(student_id):
    """Return the card row, auto-generating one if it does not exist.

    Returns a dict with keys: ``card_number``, ``issue_date``, ``expiry_date``, ``status``.
    """
    with get_connection() as conn:
        card = conn.execute(
            "SELECT * FROM student_id_cards WHERE student_id = ?", (student_id,)
        ).fetchone()
        if card:
            return {
                "card_number": card["card_number"],
                "issue_date": card["issue_date"],
                "expiry_date": card["expiry_date"] or "",
                "status": card["status"],
            }
        # Auto-generate
        card_num = _generate_card_number(student_id)
        qr_data = _generate_qr_data(student_id, card_num)
        conn.execute(
            "INSERT OR IGNORE INTO student_id_cards (student_id, card_number, expiry_date, qr_data) "
            "VALUES (?, ?, date('now', '+4 years'), ?)",
            (student_id, card_num, qr_data),
        )
        conn.commit()
        return {
            "card_number": card_num,
            "issue_date": datetime.now().strftime("%Y-%m-%d"),
            "expiry_date": str(datetime.now().year + 4) + datetime.now().strftime("-%m-%d"),
            "status": "active",
        }


def report_lost_card(student_id):
    """Mark the current card as lost, delete it, and issue a replacement.

    Returns the new card number string.
    """
    new_num = _generate_card_number(student_id, salt=str(datetime.now()))
    qr_data = _generate_qr_data(student_id, new_num)
    with get_connection() as conn:
        conn.execute(
            "UPDATE student_id_cards SET status='lost' WHERE student_id=?", (student_id,)
        )
        conn.execute(
            "DELETE FROM student_id_cards WHERE student_id=?", (student_id,)
        )
        conn.execute(
            "INSERT INTO student_id_cards (student_id, card_number, expiry_date, qr_data) "
            "VALUES (?, ?, date('now', '+4 years'), ?)",
            (student_id, new_num, qr_data),
        )
        conn.commit()
    return new_num
