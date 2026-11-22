"""Student Union academic support: peer tutoring, workshops, study groups, resources.

The Academic screens in the Student Union GUI read and write through this
module. It builds on the tables the SU CLI already uses
(``services/support.py``) rather than inventing new stores:

* tutoring  -> ``tutoring_offers`` + ``tutoring_requests``; booked and
  completed sessions (with ratings) live in ``su_tutoring_sessions``
* workshops -> union events in ``unified_events`` (``source_type='union'``)
  that are workshops, registrations in ``unified_event_registrations``
* study groups -> ``study_groups`` + ``study_group_members`` (shared with
  Study Hub); sessions in ``su_study_group_sessions`` and shared
  materials in ``su_study_group_materials``
* resources -> ``shared_resources``; one rating per person in
  ``su_resource_ratings`` with ``shared_resources.rating`` kept as the mean

Every function takes an open connection; callers own commit/close except
where a function says it commits. Owner ids come from
``identity.current_student_id`` (``user:<username>`` for accounts without a
student record). Tables with a foreign key to ``students`` (tutoring offers,
shared resources) refuse those stand-in ids, and :class:`NoStudentRecord`
says so plainly.
"""

from __future__ import annotations

import logging
import os
import shutil
from datetime import datetime
from pathlib import Path

from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.domains.student_life.domain.student_life.student_union.calendar_bridge import (
    mirror as _mirror_to_calendar,
)
from education_system.systems.university.domains.student_life.domain.student_life.student_union.identity import (
    is_fallback,
)

logger = logging.getLogger(__name__)

WORKSHOP_CATEGORIES = (
    'Study Skills', 'Time Management', 'Writing Skills', 'Research Skills',
    'Test Strategies', 'Note-Taking', 'Critical Thinking',
)
RESOURCE_TYPES = ('Notes', 'Textbooks', 'Practice Problems', 'Study Guides',
                  'Past Exams', 'Slides', 'Other')
PRACTICE_TYPES = ('practice problems', 'past exams', 'practice', 'past exam',
                  'past papers', 'mock exam')
PREVIEW_CHARS = 4000


class AcademicHubError(Exception):
    """A rule was broken (full group, duplicate request, ...)."""


class NoStudentRecord(AcademicHubError):
    """The signed-in account has no student record for an FK-bound table."""


def _now() -> str:
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def _rows(cursor) -> list[dict]:
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, tuple(r))) for r in cursor.fetchall()]


def _one(cursor) -> dict | None:
    row = cursor.fetchone()
    if row is None:
        return None
    return dict(zip([d[0] for d in cursor.description], tuple(row)))


def _require_student(owner_id: str | None, what: str) -> None:
    if not owner_id:
        raise AcademicHubError("You must be signed in to do that.")
    if is_fallback(owner_id):
        raise NoStudentRecord(
            f"Your account has no student record, so it cannot {what}. "
            "Only students can do this.")


_NAME_SQL = ("COALESCE(NULLIF(TRIM(COALESCE({a}.first_name,'') || ' ' || "
             "COALESCE({a}.last_name,'')), ''), "
             "CASE WHEN {col} LIKE 'user:%' THEN substr({col}, 6) ELSE {col} END, "
             "'Unknown')")


def _name(alias: str, col: str) -> str:
    return _NAME_SQL.format(a=alias, col=col)


# --------------------------------------------------------------------------
# Schema
# --------------------------------------------------------------------------

def ensure_schema(conn) -> None:
    """Create the tables this module owns (idempotent) and commit."""
    conn.executescript('''
    CREATE TABLE IF NOT EXISTS tutoring_offers (
        offer_id INTEGER PRIMARY KEY AUTOINCREMENT,
        tutor_id TEXT,
        subject TEXT,
        topic TEXT,
        hourly_rate REAL,
        availability TEXT,
        experience_level TEXT,
        description TEXT,
        rating REAL DEFAULT 0.0,
        total_sessions INTEGER DEFAULT 0,
        status TEXT DEFAULT 'available',
        FOREIGN KEY (tutor_id) REFERENCES students (student_id)
    );
    CREATE TABLE IF NOT EXISTS tutoring_requests (
        request_id INTEGER PRIMARY KEY AUTOINCREMENT,
        offer_id INTEGER NOT NULL,
        requester_id TEXT NOT NULL,
        tutor_id TEXT NOT NULL,
        subject TEXT,
        message TEXT,
        status TEXT DEFAULT 'pending',
        created_at TEXT NOT NULL,
        FOREIGN KEY (offer_id) REFERENCES tutoring_offers (offer_id)
    );
    CREATE TABLE IF NOT EXISTS su_tutoring_sessions (
        session_id INTEGER PRIMARY KEY AUTOINCREMENT,
        request_id INTEGER,
        offer_id INTEGER NOT NULL,
        tutor_id TEXT NOT NULL,
        tutee_id TEXT NOT NULL,
        scheduled_at TEXT NOT NULL,
        duration_minutes INTEGER,
        location TEXT,
        status TEXT NOT NULL DEFAULT 'scheduled',
        rating INTEGER CHECK (rating IS NULL OR rating BETWEEN 1 AND 5),
        review TEXT,
        created_at TEXT NOT NULL,
        completed_at TEXT,
        FOREIGN KEY (request_id) REFERENCES tutoring_requests (request_id),
        FOREIGN KEY (offer_id) REFERENCES tutoring_offers (offer_id)
    );
    CREATE INDEX IF NOT EXISTS idx_su_tutoring_sessions_tutor
        ON su_tutoring_sessions (tutor_id);
    CREATE INDEX IF NOT EXISTS idx_su_tutoring_sessions_tutee
        ON su_tutoring_sessions (tutee_id);
    CREATE TABLE IF NOT EXISTS study_groups (
        group_id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_id TEXT NOT NULL,
        group_name TEXT NOT NULL,
        creator_id TEXT NOT NULL,
        max_members INTEGER DEFAULT 6,
        current_members INTEGER DEFAULT 1,
        meeting_schedule TEXT,
        location TEXT,
        is_virtual BOOLEAN DEFAULT 1,
        status TEXT DEFAULT 'Active',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        description TEXT, topic TEXT, study_date TEXT, organizer_id TEXT
    );
    CREATE TABLE IF NOT EXISTS study_group_members (
        membership_id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id INTEGER NOT NULL,
        student_id TEXT NOT NULL,
        role TEXT DEFAULT 'Member',
        joined_at TEXT DEFAULT CURRENT_TIMESTAMP,
        contribution_score INTEGER DEFAULT 0,
        attendance_count INTEGER DEFAULT 0,
        FOREIGN KEY (group_id) REFERENCES study_groups(group_id) ON DELETE CASCADE,
        UNIQUE(group_id, student_id)
    );
    CREATE TABLE IF NOT EXISTS su_study_group_sessions (
        session_id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id INTEGER NOT NULL,
        session_at TEXT NOT NULL,
        location TEXT,
        agenda TEXT,
        created_by TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (group_id) REFERENCES study_groups (group_id) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_su_study_group_sessions_group
        ON su_study_group_sessions (group_id, session_at);
    CREATE TABLE IF NOT EXISTS shared_resources (
        resource_id INTEGER PRIMARY KEY AUTOINCREMENT,
        uploader_id TEXT,
        resource_title TEXT,
        resource_type TEXT,
        subject TEXT,
        file_path TEXT,
        description TEXT,
        upload_date TEXT,
        downloads INTEGER DEFAULT 0,
        rating REAL DEFAULT 0.0,
        FOREIGN KEY (uploader_id) REFERENCES students (student_id)
    );
    CREATE TABLE IF NOT EXISTS su_study_group_materials (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id INTEGER NOT NULL,
        resource_id INTEGER NOT NULL,
        shared_by TEXT,
        shared_at TEXT NOT NULL,
        FOREIGN KEY (group_id) REFERENCES study_groups (group_id) ON DELETE CASCADE,
        FOREIGN KEY (resource_id) REFERENCES shared_resources (resource_id),
        UNIQUE (group_id, resource_id)
    );
    CREATE TABLE IF NOT EXISTS su_resource_ratings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        resource_id INTEGER NOT NULL,
        rater_id TEXT NOT NULL,
        rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
        rated_at TEXT NOT NULL,
        FOREIGN KEY (resource_id) REFERENCES shared_resources (resource_id),
        UNIQUE (resource_id, rater_id)
    );
    ''')
    conn.commit()


def display_name(conn, owner_id: str | None) -> str:
    """Human name for an owner id (student name, username, or the id)."""
    if not owner_id:
        return 'Unknown'
    if is_fallback(owner_id):
        return owner_id.split(':', 1)[1]
    row = conn.execute(
        "SELECT first_name, last_name FROM students WHERE student_id = ?",
        (owner_id,)).fetchone()
    if row and (row[0] or row[1]):
        return f"{row[0] or ''} {row[1] or ''}".strip()
    return str(owner_id)


# --------------------------------------------------------------------------
# Peer tutoring
# --------------------------------------------------------------------------

def tutoring_subjects(conn) -> list[str]:
    rows = conn.execute(
        "SELECT DISTINCT subject FROM tutoring_offers "
        "WHERE subject IS NOT NULL AND TRIM(subject) != '' ORDER BY subject").fetchall()
    return [r[0] for r in rows]


def list_tutor_offers(conn, subject: str | None = None) -> list[dict]:
    """Available offers with ratings/session counts from real sessions."""
    sql = f'''
        SELECT t.offer_id, t.tutor_id, {_name('s', 't.tutor_id')} AS tutor_name,
               t.subject, t.topic, t.hourly_rate, t.availability,
               t.experience_level, t.description, t.status,
               (SELECT AVG(rating) FROM su_tutoring_sessions x
                 WHERE x.tutor_id = t.tutor_id AND x.rating IS NOT NULL) AS avg_rating,
               (SELECT COUNT(*) FROM su_tutoring_sessions x
                 WHERE x.tutor_id = t.tutor_id AND x.status = 'completed') AS sessions_done
        FROM tutoring_offers t
        LEFT JOIN students s ON s.student_id = t.tutor_id
        WHERE t.status = 'available'
    '''
    params: list = []
    if subject:
        sql += " AND t.subject = ?"
        params.append(subject)
    sql += " ORDER BY t.subject, tutor_name"
    return _rows(conn.execute(sql, params))


def create_tutor_offer(conn, tutor_id, *, subject, topic='', hourly_rate=0.0,
                       availability='', experience_level='Intermediate',
                       description='') -> int:
    """Insert a tutoring offer and commit."""
    _require_student(tutor_id, "offer tutoring")
    subject = (subject or '').strip()
    if not subject:
        raise AcademicHubError("Subject is required.")
    try:
        rate = float(hourly_rate or 0)
    except (TypeError, ValueError):
        raise AcademicHubError("Hourly rate must be a number.")
    if rate < 0:
        raise AcademicHubError("Hourly rate cannot be negative.")
    try:
        cur = conn.execute('''
            INSERT INTO tutoring_offers (tutor_id, subject, topic, hourly_rate,
                availability, experience_level, description, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'available')
        ''', (tutor_id, subject, topic, rate, availability, experience_level,
              description))
    except sqlite3.IntegrityError:
        conn.rollback()
        raise NoStudentRecord(
            "Your account is not linked to a student record, so it cannot "
            "be listed as a tutor.")
    conn.commit()
    return cur.lastrowid


def request_tutoring(conn, offer_id: int, requester_id, message: str = '',
                     proposed_time: str = '') -> int:
    """Ask a tutor for a session (one pending request per offer). Commits."""
    if not requester_id:
        raise AcademicHubError("You must be signed in to request tutoring.")
    offer = _one(conn.execute(
        "SELECT offer_id, tutor_id, subject, status FROM tutoring_offers "
        "WHERE offer_id = ?", (offer_id,)))
    if not offer:
        raise AcademicHubError("That tutoring offer no longer exists.")
    if offer['tutor_id'] == requester_id:
        raise AcademicHubError("You cannot request a session with yourself.")
    if offer['status'] != 'available':
        raise AcademicHubError("This tutor is not taking requests right now.")
    dup = conn.execute(
        "SELECT 1 FROM tutoring_requests WHERE offer_id = ? AND requester_id = ? "
        "AND status = 'pending'", (offer_id, requester_id)).fetchone()
    if dup:
        raise AcademicHubError("You already have a pending request with this tutor.")
    text = (message or '').strip()
    if proposed_time and proposed_time.strip():
        text = f"Proposed time: {proposed_time.strip()}\n{text}".strip()
    cur = conn.execute('''
        INSERT INTO tutoring_requests (offer_id, requester_id, tutor_id, subject,
                                       message, status, created_at)
        VALUES (?, ?, ?, ?, ?, 'pending', ?)
    ''', (offer_id, requester_id, offer['tutor_id'] or '', offer['subject'],
          text, _now()))
    conn.commit()
    return cur.lastrowid


def requests_for_tutor(conn, tutor_id) -> list[dict]:
    return _rows(conn.execute(f'''
        SELECT r.request_id, r.offer_id, r.requester_id,
               {_name('s', 'r.requester_id')} AS requester_name,
               r.subject, r.message, r.status, r.created_at
        FROM tutoring_requests r
        LEFT JOIN students s ON s.student_id = r.requester_id
        WHERE r.tutor_id = ? AND r.status = 'pending'
        ORDER BY r.created_at
    ''', (tutor_id,)))


def my_requests(conn, requester_id) -> list[dict]:
    return _rows(conn.execute(f'''
        SELECT r.request_id, r.subject, r.status, r.created_at,
               {_name('s', 'r.tutor_id')} AS tutor_name
        FROM tutoring_requests r
        LEFT JOIN students s ON s.student_id = r.tutor_id
        WHERE r.requester_id = ? ORDER BY r.created_at DESC
    ''', (requester_id,)))


def accept_request(conn, request_id: int, tutor_id, scheduled_at: str,
                   location: str = '') -> int:
    """Tutor accepts a pending request and books the session. Commits."""
    _parse_dt(scheduled_at)
    req = _one(conn.execute(
        "SELECT * FROM tutoring_requests WHERE request_id = ?", (request_id,)))
    if not req or req['tutor_id'] != tutor_id:
        raise AcademicHubError("That request is not addressed to you.")
    if req['status'] != 'pending':
        raise AcademicHubError("That request has already been answered.")
    conn.execute("UPDATE tutoring_requests SET status = 'accepted' WHERE request_id = ?",
                 (request_id,))
    cur = conn.execute('''
        INSERT INTO su_tutoring_sessions (request_id, offer_id, tutor_id, tutee_id,
            scheduled_at, location, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, 'scheduled', ?)
    ''', (request_id, req['offer_id'], tutor_id, req['requester_id'],
          scheduled_at.strip(), location, _now()))
    session_id = cur.lastrowid
    conn.commit()
    _mirror_to_calendar(
        name=f"SU Peer Tutoring: {req['subject'] or 'session'}",
        kind="tutoring_session", date=scheduled_at.strip()[:10],
        start_time=scheduled_at.strip()[11:16] or None,
        location=location or None,
        description="Student Union peer tutoring session",
        created_by=tutor_id, source_table="su_tutoring_sessions",
        source_id=session_id, conn=conn)
    return session_id


def decline_request(conn, request_id: int, tutor_id) -> None:
    cur = conn.execute(
        "UPDATE tutoring_requests SET status = 'declined' "
        "WHERE request_id = ? AND tutor_id = ? AND status = 'pending'",
        (request_id, tutor_id))
    if cur.rowcount == 0:
        raise AcademicHubError("That request is not pending for you.")
    conn.commit()


def my_sessions(conn, owner_id) -> list[dict]:
    """Sessions where the user is tutor or tutee, newest first."""
    return _rows(conn.execute(f'''
        SELECT x.session_id, x.tutor_id, x.tutee_id, x.scheduled_at,
               x.duration_minutes, x.location, x.status, x.rating, x.review,
               o.subject,
               {_name('st', 'x.tutor_id')} AS tutor_name,
               {_name('se', 'x.tutee_id')} AS tutee_name,
               CASE WHEN x.tutor_id = ? THEN 'Tutor' ELSE 'Tutee' END AS my_role
        FROM su_tutoring_sessions x
        LEFT JOIN tutoring_offers o ON o.offer_id = x.offer_id
        LEFT JOIN students st ON st.student_id = x.tutor_id
        LEFT JOIN students se ON se.student_id = x.tutee_id
        WHERE x.tutor_id = ? OR x.tutee_id = ?
        ORDER BY x.scheduled_at DESC
    ''', (owner_id, owner_id, owner_id)))


def complete_session(conn, session_id: int, tutor_id, duration_minutes) -> None:
    try:
        minutes = int(duration_minutes)
    except (TypeError, ValueError):
        raise AcademicHubError("Duration must be a whole number of minutes.")
    if minutes <= 0:
        raise AcademicHubError("Duration must be positive.")
    cur = conn.execute('''
        UPDATE su_tutoring_sessions SET status = 'completed',
               duration_minutes = ?, completed_at = ?
        WHERE session_id = ? AND tutor_id = ? AND status = 'scheduled'
    ''', (minutes, _now(), session_id, tutor_id))
    if cur.rowcount == 0:
        raise AcademicHubError("Only the tutor can complete a scheduled session.")
    row = conn.execute("SELECT offer_id FROM su_tutoring_sessions WHERE session_id = ?",
                       (session_id,)).fetchone()
    _refresh_offer_stats(conn, row[0])
    conn.commit()


def cancel_session(conn, session_id: int, owner_id) -> None:
    cur = conn.execute('''
        UPDATE su_tutoring_sessions SET status = 'cancelled'
        WHERE session_id = ? AND (tutor_id = ? OR tutee_id = ?) AND status = 'scheduled'
    ''', (session_id, owner_id, owner_id))
    if cur.rowcount == 0:
        raise AcademicHubError("That session cannot be cancelled.")
    conn.commit()


def rate_session(conn, session_id: int, tutee_id, rating, review: str = '') -> None:
    try:
        stars = int(rating)
    except (TypeError, ValueError):
        raise AcademicHubError("Rating must be 1-5.")
    if not 1 <= stars <= 5:
        raise AcademicHubError("Rating must be 1-5.")
    cur = conn.execute('''
        UPDATE su_tutoring_sessions SET rating = ?, review = ?
        WHERE session_id = ? AND tutee_id = ? AND status = 'completed'
    ''', (stars, (review or '').strip(), session_id, tutee_id))
    if cur.rowcount == 0:
        raise AcademicHubError("You can only rate completed sessions you attended.")
    row = conn.execute("SELECT offer_id FROM su_tutoring_sessions WHERE session_id = ?",
                       (session_id,)).fetchone()
    _refresh_offer_stats(conn, row[0])
    conn.commit()


def _refresh_offer_stats(conn, offer_id) -> None:
    """Keep the legacy offer columns the CLI shows in step with sessions."""
    conn.execute('''
        UPDATE tutoring_offers SET
            total_sessions = (SELECT COUNT(*) FROM su_tutoring_sessions
                              WHERE offer_id = ? AND status = 'completed'),
            rating = COALESCE((SELECT AVG(rating) FROM su_tutoring_sessions
                               WHERE offer_id = ? AND rating IS NOT NULL), 0)
        WHERE offer_id = ?
    ''', (offer_id, offer_id, offer_id))


def tutor_reviews(conn, tutor_id) -> list[dict]:
    return _rows(conn.execute(f'''
        SELECT x.rating, x.review, x.completed_at, o.subject,
               {_name('s', 'x.tutee_id')} AS tutee_name
        FROM su_tutoring_sessions x
        LEFT JOIN tutoring_offers o ON o.offer_id = x.offer_id
        LEFT JOIN students s ON s.student_id = x.tutee_id
        WHERE x.tutor_id = ? AND x.rating IS NOT NULL
        ORDER BY x.completed_at DESC
    ''', (tutor_id,)))


def tutoring_hours(conn, tutor_id) -> dict:
    row = conn.execute('''
        SELECT COUNT(*), COALESCE(SUM(duration_minutes), 0), AVG(rating),
               COUNT(DISTINCT tutee_id)
        FROM su_tutoring_sessions WHERE tutor_id = ? AND status = 'completed'
    ''', (tutor_id,)).fetchone()
    upcoming = conn.execute(
        "SELECT COUNT(*) FROM su_tutoring_sessions WHERE tutor_id = ? AND status = 'scheduled'",
        (tutor_id,)).fetchone()[0]
    return {'sessions': row[0], 'hours': (row[1] or 0) / 60.0,
            'avg_rating': row[2], 'students': row[3], 'upcoming': upcoming}


# --------------------------------------------------------------------------
# Workshops (union events)
# --------------------------------------------------------------------------

_WORKSHOP_WHERE = '''
    ue.source_type = 'union' AND (
        LOWER(COALESCE(ue.event_type, '')) = 'workshop'
        OR LOWER(COALESCE(ue.event_category, '')) LIKE '%workshop%'
        OR ue.event_category IN ({cats}))
'''.format(cats=", ".join("'" + c + "'" for c in WORKSHOP_CATEGORIES))


def list_workshops(conn, category: str | None = None) -> list[dict]:
    """Upcoming SU workshops with seats taken from real registrations."""
    sql = f'''
        SELECT ue.event_id, ue.title, ue.description,
               COALESCE(ue.event_category, ue.event_type) AS category,
               COALESCE(ue.event_date, substr(ue.start_datetime, 1, 10)) AS event_date,
               COALESCE(ue.start_time, substr(ue.start_datetime, 12, 5)) AS start_time,
               COALESCE(ue.end_time, substr(ue.end_datetime, 12, 5)) AS end_time,
               ue.location, ue.max_capacity,
               (SELECT COUNT(*) FROM unified_event_registrations r
                 WHERE r.event_id = ue.event_id
                   AND COALESCE(r.attendance_status, '') != 'cancelled') AS registered
        FROM unified_events ue
        WHERE {_WORKSHOP_WHERE}
          AND COALESCE(ue.status, '') NOT IN ('cancelled', 'deleted')
          AND COALESCE(ue.event_date, substr(ue.start_datetime, 1, 10), '9999') >= date('now')
    '''  # db-audit: ignore[DBW001] - constant category list
    params: list = []
    if category:
        sql += " AND ue.event_category = ?"
        params.append(category)
    sql += " ORDER BY event_date, start_time"
    return _rows(conn.execute(sql, params))


def workshop_categories(conn) -> list[str]:
    rows = conn.execute(f'''
        SELECT DISTINCT ue.event_category FROM unified_events ue
        WHERE {_WORKSHOP_WHERE} AND ue.event_category IS NOT NULL
        ORDER BY 1''').fetchall()  # db-audit: ignore[DBW001] - constant category list
    return [r[0] for r in rows]


def register_for_workshop(conn, event_id: int, owner_id, attendee_name: str = '') -> int:
    if not owner_id:
        raise AcademicHubError("You must be signed in to register.")
    ev = _one(conn.execute(
        "SELECT title, max_capacity FROM unified_events WHERE event_id = ?", (event_id,)))
    if not ev:
        raise AcademicHubError("That workshop no longer exists.")
    if conn.execute(
            "SELECT 1 FROM unified_event_registrations WHERE event_id = ? AND user_id = ? "
            "AND COALESCE(attendance_status, '') != 'cancelled'",
            (event_id, owner_id)).fetchone():
        raise AcademicHubError("You are already registered for this workshop.")
    taken = conn.execute(
        "SELECT COUNT(*) FROM unified_event_registrations WHERE event_id = ? "
        "AND COALESCE(attendance_status, '') != 'cancelled'", (event_id,)).fetchone()[0]
    if ev['max_capacity'] and taken >= int(ev['max_capacity']):
        raise AcademicHubError("This workshop is full.")
    cur = conn.execute('''
        INSERT INTO unified_event_registrations (event_id, user_id, user_type,
            registration_date, attendance_status, student_id, attendee_name)
        VALUES (?, ?, 'student', ?, 'registered', ?, ?)
    ''', (event_id, owner_id, _now(), owner_id, attendee_name or None))
    conn.commit()
    return cur.lastrowid


def my_workshops(conn, owner_id) -> list[dict]:
    return _rows(conn.execute(f'''
        SELECT ue.event_id, ue.title,
               COALESCE(ue.event_date, substr(ue.start_datetime, 1, 10)) AS event_date,
               r.attendance_status, r.registration_date
        FROM unified_event_registrations r
        JOIN unified_events ue ON ue.event_id = r.event_id
        WHERE r.user_id = ? AND {_WORKSHOP_WHERE}
        ORDER BY event_date DESC
    ''', (owner_id,)))  # db-audit: ignore[DBW001] - constant category list


def workshop_materials(conn, event_id: int) -> list[dict]:
    """Shared resources that name this workshop (title or event id tag)."""
    ev = conn.execute("SELECT title FROM unified_events WHERE event_id = ?",
                      (event_id,)).fetchone()
    if not ev:
        return []
    tag = f"event:{event_id}"
    return _rows(conn.execute('''
        SELECT resource_id, resource_title, resource_type, subject, file_path
        FROM shared_resources
        WHERE description LIKE ? OR (? != '' AND description LIKE ?)
           OR subject = ?
        ORDER BY upload_date DESC
    ''', (f"%{tag}%", ev[0] or '', f"%{ev[0]}%", ev[0])))


# --------------------------------------------------------------------------
# Study groups
# --------------------------------------------------------------------------

def _parse_dt(value: str) -> datetime:
    value = (value or '').strip()
    for fmt in ('%Y-%m-%d %H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise AcademicHubError("Use the date format YYYY-MM-DD HH:MM.")


def course_options(conn, owner_id=None) -> list[str]:
    """Courses seen in groups/resources plus the student's own modules."""
    seen: list[str] = []
    queries = [
        ("SELECT DISTINCT course_id FROM study_groups WHERE course_id IS NOT NULL", ()),
        ("SELECT DISTINCT subject FROM shared_resources WHERE subject IS NOT NULL", ()),
    ]
    if owner_id and not is_fallback(owner_id):
        queries.insert(0, ("SELECT DISTINCT module_code FROM student_modules "
                           "WHERE student_id = ? AND module_code IS NOT NULL", (owner_id,)))
    for sql, params in queries:
        try:
            for (val,) in conn.execute(sql, params).fetchall():
                val = str(val).strip()
                if val and val not in seen:
                    seen.append(val)
        except sqlite3.Error as exc:
            logger.debug("course option lookup failed: %s", exc)
    return sorted(seen)


def list_study_groups(conn, course: str | None = None, *, exam_prep: bool = False) -> list[dict]:
    sql = '''
        SELECT g.group_id, g.course_id, g.group_name, g.creator_id, g.max_members,
               (SELECT COUNT(*) FROM study_group_members m WHERE m.group_id = g.group_id)
                   AS members,
               g.meeting_schedule, g.location, g.status, g.description, g.topic,
               g.study_date,
               (SELECT MIN(session_at) FROM su_study_group_sessions s
                 WHERE s.group_id = g.group_id AND s.session_at >= ?) AS next_session
        FROM study_groups g
        WHERE COALESCE(g.status, 'Active') = 'Active'
    '''
    params: list = [datetime.now().strftime('%Y-%m-%d %H:%M')]
    sql += (" AND g.study_date IS NOT NULL AND g.study_date != ''" if exam_prep
            else " AND (g.study_date IS NULL OR g.study_date = '')")
    if course:
        sql += " AND g.course_id = ?"
        params.append(course)
    sql += " ORDER BY g.course_id, g.group_name"
    return _rows(conn.execute(sql, params))


def is_member(conn, group_id: int, owner_id) -> bool:
    return bool(conn.execute(
        "SELECT 1 FROM study_group_members WHERE group_id = ? AND student_id = ?",
        (group_id, owner_id)).fetchone())


def create_study_group(conn, owner_id, *, course_id, group_name, description='',
                       max_members=8, meeting_schedule='', location='',
                       exam_date: str | None = None, focus: str = '') -> int:
    """Create a group (creator joins as Admin) and commit; mirrors to calendar."""
    if not owner_id:
        raise AcademicHubError("You must be signed in to create a group.")
    course_id = (course_id or '').strip()
    group_name = (group_name or '').strip()
    if not course_id or not group_name:
        raise AcademicHubError("Course and group name are required.")
    try:
        limit = int(max_members)
    except (TypeError, ValueError):
        raise AcademicHubError("Member limit must be a number.")
    if limit < 2:
        raise AcademicHubError("A group needs room for at least 2 members.")
    if exam_date:
        _parse_dt(exam_date)
    cur = conn.execute('''
        INSERT INTO study_groups (course_id, group_name, creator_id, max_members,
            current_members, meeting_schedule, location, status, description,
            topic, study_date, organizer_id, created_at)
        VALUES (?, ?, ?, ?, 1, ?, ?, 'Active', ?, ?, ?, ?, ?)
    ''', (course_id, group_name, owner_id, limit, meeting_schedule, location,
          description, focus or None, exam_date or None, owner_id, _now()))
    group_id = cur.lastrowid
    conn.execute(
        "INSERT INTO study_group_members (group_id, student_id, role) VALUES (?, ?, 'Admin')",
        (group_id, owner_id))
    conn.commit()
    _mirror_to_calendar(
        name=f"SU Study Group: {course_id} — {group_name}", kind="study_group",
        date=exam_date or None, location=location or None,
        description=description or "Student Union study group",
        created_by=owner_id, source_table="study_groups", source_id=group_id,
        conn=conn)
    return group_id


def join_study_group(conn, group_id: int, owner_id) -> None:
    if not owner_id:
        raise AcademicHubError("You must be signed in to join a group.")
    g = _one(conn.execute(
        "SELECT max_members, status FROM study_groups WHERE group_id = ?", (group_id,)))
    if not g or (g['status'] or 'Active') != 'Active':
        raise AcademicHubError("That study group is not open.")
    if is_member(conn, group_id, owner_id):
        raise AcademicHubError("You are already a member of this group.")
    count = conn.execute("SELECT COUNT(*) FROM study_group_members WHERE group_id = ?",
                         (group_id,)).fetchone()[0]
    if g['max_members'] and count >= int(g['max_members']):
        raise AcademicHubError("This study group is full.")
    conn.execute("INSERT INTO study_group_members (group_id, student_id) VALUES (?, ?)",
                 (group_id, owner_id))
    conn.execute("UPDATE study_groups SET current_members = ? WHERE group_id = ?",
                 (count + 1, group_id))
    conn.commit()


def group_members(conn, group_id: int) -> list[dict]:
    return _rows(conn.execute(f'''
        SELECT m.student_id, m.role, m.joined_at, {_name('s', 'm.student_id')} AS name
        FROM study_group_members m LEFT JOIN students s ON s.student_id = m.student_id
        WHERE m.group_id = ? ORDER BY m.role DESC, m.joined_at
    ''', (group_id,)))


def schedule_group_session(conn, group_id: int, owner_id, session_at: str,
                           location: str = '', agenda: str = '') -> int:
    if not is_member(conn, group_id, owner_id):
        raise AcademicHubError("Only group members can schedule sessions.")
    when = _parse_dt(session_at)
    if when < datetime.now():
        raise AcademicHubError("The session must be in the future.")
    stamp = when.strftime('%Y-%m-%d %H:%M')
    cur = conn.execute('''
        INSERT INTO su_study_group_sessions (group_id, session_at, location, agenda,
                                             created_by, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (group_id, stamp, location, agenda, owner_id, _now()))
    sid = cur.lastrowid
    conn.commit()
    g = conn.execute("SELECT course_id, group_name FROM study_groups WHERE group_id = ?",
                     (group_id,)).fetchone()
    _mirror_to_calendar(
        name=f"SU Study Session: {g[0]} — {g[1]}", kind="study_group",
        date=stamp[:10], start_time=stamp[11:16], location=location or None,
        description=agenda or "Study group session", created_by=owner_id,
        source_table="su_study_group_sessions", source_id=sid, conn=conn)
    return sid


def group_sessions(conn, group_id: int) -> list[dict]:
    return _rows(conn.execute('''
        SELECT session_id, session_at, location, agenda, created_by
        FROM su_study_group_sessions WHERE group_id = ? ORDER BY session_at
    ''', (group_id,)))


def share_material(conn, group_id: int, resource_id: int, owner_id) -> None:
    if not is_member(conn, group_id, owner_id):
        raise AcademicHubError("Only group members can share materials.")
    try:
        conn.execute('''
            INSERT INTO su_study_group_materials (group_id, resource_id, shared_by, shared_at)
            VALUES (?, ?, ?, ?)
        ''', (group_id, resource_id, owner_id, _now()))
    except sqlite3.IntegrityError:
        conn.rollback()
        raise AcademicHubError("That resource is already shared with this group.")
    conn.commit()


def group_materials(conn, group_id: int) -> list[dict]:
    return _rows(conn.execute('''
        SELECT r.resource_id, r.resource_title, r.resource_type, m.shared_at
        FROM su_study_group_materials m JOIN shared_resources r ON r.resource_id = m.resource_id
        WHERE m.group_id = ? ORDER BY m.shared_at DESC
    ''', (group_id,)))


def practice_resources(conn, course: str) -> list[dict]:
    marks = ", ".join("?" for _ in PRACTICE_TYPES)
    return _rows(conn.execute(f'''
        SELECT resource_id, resource_title, resource_type, downloads, rating
        FROM shared_resources
        WHERE subject = ? AND LOWER(COALESCE(resource_type, '')) IN ({marks})
        ORDER BY rating DESC, downloads DESC
    ''', (course, *PRACTICE_TYPES)))  # db-audit: ignore[DBW001] - placeholders only


# --------------------------------------------------------------------------
# Shared resources
# --------------------------------------------------------------------------

def resource_upload_dir() -> Path:
    from education_system import paths
    target = Path(paths.UNIVERSITY_UPLOAD_DIR) / "student_union" / "resources"
    target.mkdir(parents=True, exist_ok=True)
    return target


def list_resources(conn, course: str | None = None, rtype: str | None = None) -> list[dict]:
    sql = f'''
        SELECT r.resource_id, r.resource_title, r.subject, r.resource_type,
               r.uploader_id, {_name('s', 'r.uploader_id')} AS uploader_name,
               r.upload_date, r.downloads, r.description, r.file_path,
               (SELECT AVG(rating) FROM su_resource_ratings x
                 WHERE x.resource_id = r.resource_id) AS avg_rating,
               (SELECT COUNT(*) FROM su_resource_ratings x
                 WHERE x.resource_id = r.resource_id) AS rating_count
        FROM shared_resources r LEFT JOIN students s ON s.student_id = r.uploader_id
        WHERE 1 = 1
    '''
    params: list = []
    if course:
        sql += " AND r.subject = ?"
        params.append(course)
    if rtype:
        sql += " AND LOWER(r.resource_type) = LOWER(?)"
        params.append(rtype)
    sql += " ORDER BY r.upload_date DESC"
    return _rows(conn.execute(sql, params))


def resource_types(conn) -> list[str]:
    found = [r[0] for r in conn.execute(
        "SELECT DISTINCT resource_type FROM shared_resources "
        "WHERE resource_type IS NOT NULL AND TRIM(resource_type) != ''").fetchall()]
    out = list(RESOURCE_TYPES)
    for t in found:
        if t.lower() not in (x.lower() for x in out):
            out.append(t)
    return out


def get_resource(conn, resource_id: int) -> dict | None:
    for r in list_resources(conn):
        if r['resource_id'] == resource_id:
            return r
    return None


def upload_resource(conn, owner_id, *, title, course, resource_type, source_path,
                    description='') -> int:
    """Copy a file into the uploads store and record it. Commits."""
    _require_student(owner_id, "share resources")
    title = (title or '').strip()
    if not title:
        raise AcademicHubError("Title is required.")
    if not source_path or not os.path.isfile(source_path):
        raise AcademicHubError("Choose a file to upload.")
    stamp = datetime.now().strftime('%Y%m%d%H%M%S')
    dest = resource_upload_dir() / f"{stamp}_{os.path.basename(source_path)}"
    shutil.copy2(source_path, dest)
    try:
        cur = conn.execute('''
            INSERT INTO shared_resources (uploader_id, resource_title, resource_type,
                subject, file_path, description, upload_date, downloads, rating)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0.0)
        ''', (owner_id, title, resource_type, (course or '').strip(), str(dest),
              description, _now()))
    except sqlite3.IntegrityError:
        conn.rollback()
        dest.unlink(missing_ok=True)
        raise NoStudentRecord(
            "Your account is not linked to a student record, so it cannot "
            "share resources.")
    conn.commit()
    return cur.lastrowid


def download_resource(conn, resource_id: int, dest_path: str) -> str:
    """Copy the stored file to ``dest_path`` and count the download. Commits."""
    row = conn.execute("SELECT file_path FROM shared_resources WHERE resource_id = ?",
                       (resource_id,)).fetchone()
    if not row:
        raise AcademicHubError("That resource no longer exists.")
    src = row[0]
    if not src or not os.path.isfile(src):
        raise AcademicHubError("The file for this resource is not available on this system.")
    shutil.copy2(src, dest_path)
    conn.execute("UPDATE shared_resources SET downloads = COALESCE(downloads, 0) + 1 "
                 "WHERE resource_id = ?", (resource_id,))
    conn.commit()
    return dest_path


def rate_resource(conn, resource_id: int, rater_id, rating) -> float:
    """Record (or change) one person's 1-5 rating; returns the new average."""
    if not rater_id:
        raise AcademicHubError("You must be signed in to rate.")
    try:
        stars = int(rating)
    except (TypeError, ValueError):
        raise AcademicHubError("Rating must be 1-5.")
    if not 1 <= stars <= 5:
        raise AcademicHubError("Rating must be 1-5.")
    row = conn.execute("SELECT uploader_id FROM shared_resources WHERE resource_id = ?",
                       (resource_id,)).fetchone()
    if not row:
        raise AcademicHubError("That resource no longer exists.")
    if row[0] and row[0] == rater_id:
        raise AcademicHubError("You cannot rate your own resource.")
    conn.execute('''
        INSERT INTO su_resource_ratings (resource_id, rater_id, rating, rated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT (resource_id, rater_id) DO UPDATE SET rating = excluded.rating,
            rated_at = excluded.rated_at
    ''', (resource_id, rater_id, stars, _now()))
    avg = conn.execute("SELECT AVG(rating) FROM su_resource_ratings WHERE resource_id = ?",
                       (resource_id,)).fetchone()[0] or 0.0
    conn.execute("UPDATE shared_resources SET rating = ? WHERE resource_id = ?",
                 (round(avg, 2), resource_id))
    conn.commit()
    return float(avg)


def preview_text(file_path: str | None) -> str | None:
    """First part of a text file, or None if it is missing or not text."""
    if not file_path or not os.path.isfile(file_path):
        return None
    try:
        with open(file_path, 'rb') as fh:
            raw = fh.read(PREVIEW_CHARS)
    except OSError:
        return None
    if b'\x00' in raw:
        return None
    try:
        return raw.decode('utf-8')
    except UnicodeDecodeError:
        return None


__all__ = [name for name in dir() if not name.startswith('_') and name not in (
    'annotations', 'logging', 'os', 'shutil', 'datetime', 'Path', 'sqlite3', 'logger')]
