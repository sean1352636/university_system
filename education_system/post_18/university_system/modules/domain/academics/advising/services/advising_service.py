"""Advising service — database operations and business logic for the academic advising portal."""

import logging
from datetime import datetime

from education_system.post_18.university_system.infrastructure.database.db import get_connection

logger = logging.getLogger(__name__)


def init_db():
    """Create advising tables if they do not exist."""
    with get_connection() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS advising_appointments (
            appointment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            advisor_id TEXT NOT NULL,
            appointment_date TEXT NOT NULL,
            appointment_time TEXT NOT NULL,
            duration_minutes INTEGER DEFAULT 30,
            appointment_type TEXT DEFAULT 'general',
            topic TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            status TEXT DEFAULT 'scheduled'
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS advisors (
            advisor_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            department TEXT DEFAULT '',
            email TEXT DEFAULT '',
            office TEXT DEFAULT '',
            specialization TEXT DEFAULT '',
            available_days TEXT DEFAULT 'Mon,Tue,Wed,Thu,Fri',
            available_hours TEXT DEFAULT '09:00-17:00'
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS degree_plans (
            plan_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            advisor_id TEXT,
            plan_name TEXT NOT NULL,
            target_graduation TEXT,
            total_credits_required INTEGER DEFAULT 120,
            credits_completed INTEGER DEFAULT 0,
            notes TEXT DEFAULT '',
            created_date TEXT DEFAULT (date('now')),
            last_updated TEXT DEFAULT (date('now')),
            status TEXT DEFAULT 'active'
        )""")


# ---------------------------------------------------------------------------
# Advisors
# ---------------------------------------------------------------------------

def get_all_advisors():
    """Return all advisors ordered by name."""
    with get_connection() as conn:
        return conn.execute("SELECT * FROM advisors ORDER BY name").fetchall()


def get_advisor_count():
    """Return the number of advisors in the database."""
    with get_connection() as conn:
        return conn.execute("SELECT COUNT(*) FROM advisors").fetchone()[0]


def seed_sample_advisors():
    """Insert sample advisor rows when the table is empty."""
    sample = [
        ("ADV001", "Dr. Sarah Johnson", "Computer Science", "s.johnson@uni.edu", "B210", "Software Engineering"),
        ("ADV002", "Prof. Michael Chen", "Data Science", "m.chen@uni.edu", "C305", "Machine Learning"),
        ("ADV003", "Dr. Emily Williams", "Mathematics", "e.williams@uni.edu", "A118", "Applied Mathematics"),
    ]
    with get_connection() as conn:
        for s in sample:
            conn.execute(
                "INSERT INTO advisors (advisor_id, name, department, email, office, specialization) VALUES (?,?,?,?,?,?)",
                s,
            )
        conn.commit()


# ---------------------------------------------------------------------------
# Appointments
# ---------------------------------------------------------------------------

def get_appointments(student_id, status_filter=None):
    """Return appointments for *student_id*, optionally filtered by status.

    Parameters
    ----------
    student_id : str
    status_filter : str or None
        Pass ``None`` or ``"All"`` for no filter, otherwise a status string
        such as ``"scheduled"``, ``"completed"``, or ``"cancelled"``.

    Returns
    -------
    list[sqlite3.Row]
    """
    with get_connection() as conn:
        query = "SELECT * FROM advising_appointments WHERE student_id = ?"
        params = [student_id]
        if status_filter and status_filter != "All":
            query += " AND status = ?"
            params.append(status_filter)
        query += " ORDER BY appointment_date DESC, appointment_time DESC"
        return conn.execute(query, params).fetchall()


def schedule_appointment(
    student_id,
    advisor_id,
    appointment_date,
    appointment_time,
    duration_minutes=30,
    appointment_type="general",
    topic="",
    notes="",
):
    """Insert a new advising appointment.

    Raises
    ------
    ValueError
        If the date or time format is invalid.
    """
    # Validate date
    try:
        datetime.strptime(appointment_date, "%Y-%m-%d")
    except ValueError:
        raise ValueError("Invalid date format. Use YYYY-MM-DD.")
    # Validate time
    try:
        datetime.strptime(appointment_time, "%H:%M")
    except ValueError:
        raise ValueError("Invalid time format. Use HH:MM.")

    with get_connection() as conn:
        conn.execute(
            """INSERT INTO advising_appointments
                (student_id, advisor_id, appointment_date, appointment_time,
                 duration_minutes, appointment_type, topic, notes, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'scheduled')""",
            (student_id, advisor_id, appointment_date, appointment_time,
             int(duration_minutes), appointment_type, topic, notes),
        )
        conn.commit()


def cancel_appointment(appointment_id):
    """Mark an appointment as cancelled.  Returns True if updated, False otherwise."""
    with get_connection() as conn:
        cur = conn.execute(
            "UPDATE advising_appointments SET status='cancelled' WHERE appointment_id=? AND status != 'cancelled'",
            (appointment_id,),
        )
        conn.commit()
        return cur.rowcount > 0


# ---------------------------------------------------------------------------
# Degree plans
# ---------------------------------------------------------------------------

def get_active_degree_plan(student_id):
    """Return the most recent active degree plan for *student_id*, or ``None``."""
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM degree_plans WHERE student_id = ? AND status = 'active' ORDER BY created_date DESC LIMIT 1",
            (student_id,),
        ).fetchone()


def get_completed_credits(student_id):
    """Look up the total completed credits for a student from the student_modules/modules tables.

    Returns 0 when the tables do not exist or no completed modules are found.
    """
    with get_connection() as conn:
        try:
            row = conn.execute(
                "SELECT COALESCE(SUM(m.credits), 0) FROM student_modules sm "
                "JOIN modules m ON sm.module_code = m.module_code "
                "WHERE sm.student_id = ? AND sm.status = 'completed'",
                (student_id,),
            ).fetchone()
            return row[0] if row else 0
        except Exception:
            return 0


def create_degree_plan(
    student_id,
    plan_name,
    target_graduation=None,
    total_credits_required=120,
    credits_completed=None,
    notes="",
):
    """Insert a new degree plan.

    If *credits_completed* is ``None`` the value is looked up automatically via
    :func:`get_completed_credits`.
    """
    if not plan_name:
        raise ValueError("Plan name is required.")
    if credits_completed is None:
        credits_completed = get_completed_credits(student_id)
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO degree_plans
                (student_id, plan_name, target_graduation, total_credits_required,
                 credits_completed, notes)
                VALUES (?, ?, ?, ?, ?, ?)""",
            (student_id, plan_name, target_graduation or None,
             int(total_credits_required), credits_completed, notes),
        )
        conn.commit()
