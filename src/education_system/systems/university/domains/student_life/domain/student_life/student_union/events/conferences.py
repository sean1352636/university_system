"""Student Union academic conferences.

A conference is a Student Union event: one ``unified_events`` row with
``source_type = 'union'`` and ``event_type = 'conference'``. Attendee
registration is the ordinary ``unified_event_registrations`` row, so a
conference shows up in every union event list, the attendance tools and
the calendar exactly like any other union event.

What only conferences have — the programme (sessions), invited speakers,
paper / presentation / poster submissions with their review decisions,
the research Q&A, presentation feedback and awards — lives in the
``su_conference_*`` tables created by :func:`ensure_schema`.

Every function takes an open sqlite connection and commits its own
write; nothing here imports tkinter or the university ``shell`` package.
"""

from __future__ import annotations

import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional

logger = logging.getLogger(__name__)

EVENT_TYPE = "conference"
SOURCE_TYPE = "union"

CONFERENCE_STATUSES = ("planning", "call_for_papers", "open", "closed",
                       "completed", "cancelled")
#: Statuses in which attendees may still register.
REGISTRATION_OPEN = ("upcoming", "planning", "call_for_papers", "open")
#: Statuses in which submissions are still accepted.
SUBMISSIONS_OPEN = ("upcoming", "planning", "call_for_papers", "open")

SUBMISSION_KINDS = ("paper", "presentation", "poster")
SUBMISSION_STATUSES = ("submitted", "under_review", "accepted", "rejected",
                       "revisions_requested")
SESSION_TYPES = ("keynote", "parallel", "poster", "workshop", "break", "panel")
SPEAKER_STATUSES = ("invited", "confirmed", "declined")
ATTENDEE_TYPES = ("student", "staff", "external")


class ConferenceError(ValueError):
    """A conference action was refused for a reason the user should see."""


_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS su_conference_speakers (
        speaker_id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        email TEXT,
        institution TEXT,
        topic TEXT,
        status TEXT NOT NULL DEFAULT 'invited',
        invited_by TEXT,
        invited_at TEXT NOT NULL,
        FOREIGN KEY (event_id) REFERENCES unified_events (event_id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS su_conference_sessions (
        session_id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        session_type TEXT NOT NULL DEFAULT 'parallel',
        starts_at TEXT NOT NULL,
        ends_at TEXT,
        location TEXT,
        speaker_id INTEGER,
        notes TEXT,
        FOREIGN KEY (event_id) REFERENCES unified_events (event_id) ON DELETE CASCADE,
        FOREIGN KEY (speaker_id) REFERENCES su_conference_speakers (speaker_id) ON DELETE SET NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS su_conference_submissions (
        submission_id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER NOT NULL,
        kind TEXT NOT NULL DEFAULT 'paper',
        title TEXT NOT NULL,
        abstract TEXT,
        track TEXT,
        author_id TEXT NOT NULL,
        author_name TEXT,
        file_path TEXT,
        status TEXT NOT NULL DEFAULT 'submitted',
        decision_note TEXT,
        decided_by TEXT,
        decided_at TEXT,
        session_id INTEGER,
        submitted_at TEXT NOT NULL,
        FOREIGN KEY (event_id) REFERENCES unified_events (event_id) ON DELETE CASCADE,
        FOREIGN KEY (session_id) REFERENCES su_conference_sessions (session_id) ON DELETE SET NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS su_conference_questions (
        question_id INTEGER PRIMARY KEY AUTOINCREMENT,
        submission_id INTEGER NOT NULL,
        parent_id INTEGER,
        author_id TEXT NOT NULL,
        author_name TEXT,
        body TEXT NOT NULL,
        is_anonymous INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        FOREIGN KEY (submission_id) REFERENCES su_conference_submissions (submission_id) ON DELETE CASCADE,
        FOREIGN KEY (parent_id) REFERENCES su_conference_questions (question_id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS su_conference_feedback (
        feedback_id INTEGER PRIMARY KEY AUTOINCREMENT,
        submission_id INTEGER NOT NULL,
        reviewer_id TEXT NOT NULL,
        rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
        content_rating INTEGER CHECK (content_rating BETWEEN 1 AND 5),
        skills_rating INTEGER CHECK (skills_rating BETWEEN 1 AND 5),
        visuals_rating INTEGER CHECK (visuals_rating BETWEEN 1 AND 5),
        qa_rating INTEGER CHECK (qa_rating BETWEEN 1 AND 5),
        comments TEXT,
        created_at TEXT NOT NULL,
        UNIQUE (submission_id, reviewer_id),
        FOREIGN KEY (submission_id) REFERENCES su_conference_submissions (submission_id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS su_conference_awards (
        award_id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER NOT NULL,
        submission_id INTEGER NOT NULL,
        award_name TEXT NOT NULL,
        prize TEXT,
        awarded_by TEXT,
        awarded_at TEXT NOT NULL,
        FOREIGN KEY (event_id) REFERENCES unified_events (event_id) ON DELETE CASCADE,
        FOREIGN KEY (submission_id) REFERENCES su_conference_submissions (submission_id) ON DELETE CASCADE
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_su_conf_sub_event ON su_conference_submissions(event_id)",
    "CREATE INDEX IF NOT EXISTS idx_su_conf_sess_event ON su_conference_sessions(event_id)",
    "CREATE INDEX IF NOT EXISTS idx_su_conf_q_sub ON su_conference_questions(submission_id)",
)


def ensure_schema(conn) -> None:
    """Create the conference tables if they are missing (idempotent)."""
    for stmt in _SCHEMA:
        conn.execute(stmt)
    conn.commit()


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _rows(cursor) -> list[dict]:
    cols = [d[0] for d in cursor.description or ()]
    return [dict(zip(cols, r)) for r in cursor.fetchall()]


def _one(cursor) -> Optional[dict]:
    cols = [d[0] for d in cursor.description or ()]
    row = cursor.fetchone()
    return dict(zip(cols, row)) if row else None


def _check_date(value: str, label: str) -> str:
    value = (value or "").strip()
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        raise ConferenceError(f"{label} must be a date in YYYY-MM-DD format.")
    return value


def _check_time(value: str | None, label: str) -> str | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        datetime.strptime(value, "%H:%M")
    except ValueError:
        raise ConferenceError(f"{label} must be a time in HH:MM format.")
    return value


# --------------------------------------------------------------------------
# Conferences
# --------------------------------------------------------------------------

_CONF_SELECT = """
    SELECT e.event_id, e.title, e.description,
           COALESCE(e.event_date, substr(e.start_datetime, 1, 10)) AS start_date,
           substr(e.end_datetime, 1, 10) AS end_date,
           COALESCE(e.start_time, substr(e.start_datetime, 12, 5)) AS start_time,
           e.location, e.max_capacity, e.status, e.organizer_id,
           e.organizer_name, e.created_by, e.created_at,
           (SELECT COUNT(*) FROM su_conference_submissions s
             WHERE s.event_id = e.event_id) AS submissions,
           (SELECT COUNT(*) FROM su_conference_submissions s
             WHERE s.event_id = e.event_id AND s.kind = 'paper') AS papers,
           (SELECT COUNT(*) FROM su_conference_speakers sp
             WHERE sp.event_id = e.event_id AND sp.status != 'declined') AS speakers,
           (SELECT COUNT(*) FROM unified_event_registrations r
             WHERE r.event_id = e.event_id
               AND COALESCE(r.attendance_status, 'registered') != 'cancelled') AS registrations
    FROM unified_events e
    WHERE e.source_type = 'union' AND e.event_type = 'conference'
"""


def create_conference(conn, *, title: str, start_date: str,
                      end_date: str | None = None, start_time: str | None = None,
                      end_time: str | None = None, location: str | None = None,
                      description: str | None = None, capacity: int | None = None,
                      status: str = "planning", organizer_id: str | None = None,
                      organizer_name: str | None = None) -> int:
    """Create a conference as a union event and mirror it to the calendar."""
    title = (title or "").strip()
    if not title:
        raise ConferenceError("A conference needs a name.")
    start_date = _check_date(start_date, "Start date")
    end_date = _check_date(end_date, "End date") if (end_date or "").strip() else start_date
    if end_date < start_date:
        raise ConferenceError("The end date is before the start date.")
    start_time = _check_time(start_time, "Start time")
    end_time = _check_time(end_time, "End time")
    if status not in CONFERENCE_STATUSES:
        raise ConferenceError(f"Unknown conference status '{status}'.")
    if capacity is not None and capacity < 0:
        raise ConferenceError("Capacity cannot be negative.")

    start_dt = f"{start_date} {start_time or '00:00'}"
    end_dt = f"{end_date} {end_time or '23:59'}"
    cur = conn.execute(
        """
        INSERT INTO unified_events (
            source_type, title, description, event_type, event_category,
            start_datetime, end_datetime, event_date, start_time, end_time,
            location, organizer_id, organizer_name, organizer_type,
            max_capacity, registration_required, status, created_by, created_at
        ) VALUES ('union', ?, ?, 'conference', 'Academic Conference',
                  ?, ?, ?, ?, ?, ?, ?, ?, 'student_union', ?, 1, ?, ?, ?)
        """,
        (title, description, start_dt, end_dt, start_date, start_time, end_time,
         location, organizer_id, organizer_name, capacity or None, status,
         organizer_id, _now()),
    )
    event_id = cur.lastrowid
    conn.commit()

    try:
        from education_system.systems.university.domains.student_life.domain.student_life.student_union.calendar_bridge import (
            mirror,
        )
        kwargs: dict[str, Any] = {}
        if end_date != start_date:
            kwargs.update(date_start=start_date, date_end=end_date)
        else:
            kwargs.update(date=start_date)
        mirror(name=f"SU Conference: {title}", kind="conference",
               description=description or "Student Union academic conference",
               start_time=start_time, end_time=end_time, location=location,
               created_by=organizer_id, organizer=organizer_name,
               source_table="unified_events", source_id=event_id, conn=conn,
               **kwargs)
    except Exception as exc:  # pragma: no cover - the conference is saved
        logger.debug("conference calendar mirror failed: %s", exc)
    return event_id


def update_conference(conn, event_id: int, **fields) -> None:
    """Update a conference's details (only the fields given)."""
    current = get_conference(conn, event_id)
    if not current:
        raise ConferenceError("That conference no longer exists.")
    title = (fields.get("title", current["title"]) or "").strip()
    if not title:
        raise ConferenceError("A conference needs a name.")
    start_date = _check_date(fields.get("start_date", current["start_date"]), "Start date")
    end_raw = fields.get("end_date", current["end_date"]) or start_date
    end_date = _check_date(end_raw, "End date")
    if end_date < start_date:
        raise ConferenceError("The end date is before the start date.")
    start_time = _check_time(fields.get("start_time", current["start_time"]), "Start time")
    status = fields.get("status", current["status"])
    if status not in CONFERENCE_STATUSES and status != "upcoming":
        raise ConferenceError(f"Unknown conference status '{status}'.")
    capacity = fields.get("capacity", current["max_capacity"])
    if capacity is not None and int(capacity) < 0:
        raise ConferenceError("Capacity cannot be negative.")
    conn.execute(
        """
        UPDATE unified_events
           SET title = ?, description = ?, location = ?, max_capacity = ?,
               status = ?, event_date = ?, start_time = ?,
               start_datetime = ?, end_datetime = ?, updated_at = ?
         WHERE event_id = ? AND source_type = 'union' AND event_type = 'conference'
        """,
        (title, fields.get("description", current["description"]),
         fields.get("location", current["location"]), capacity or None, status,
         start_date, start_time, f"{start_date} {start_time or '00:00'}",
         f"{end_date} 23:59", _now(), event_id),
    )
    conn.commit()


def list_conferences(conn, *, upcoming_only: bool = False,
                     include_cancelled: bool = False) -> list[dict]:
    sql = _CONF_SELECT
    params: list[Any] = []
    if upcoming_only:
        sql += " AND COALESCE(substr(e.end_datetime, 1, 10), e.event_date) >= date('now')"
    if not include_cancelled:
        sql += " AND COALESCE(e.status, '') != 'cancelled'"
    sql += " ORDER BY start_date, e.title"
    return _rows(conn.execute(sql, params))


def get_conference(conn, event_id: int) -> Optional[dict]:
    return _one(conn.execute(_CONF_SELECT + " AND e.event_id = ?", (event_id,)))


def _require_conference(conn, event_id: int) -> dict:
    conf = get_conference(conn, event_id)
    if not conf:
        raise ConferenceError("That conference no longer exists.")
    return conf


# --------------------------------------------------------------------------
# Registration (unified_event_registrations)
# --------------------------------------------------------------------------

def register(conn, event_id: int, user_id: str, *, attendee_name: str | None = None,
             user_type: str = "student") -> int:
    """Register an attendee. Refuses duplicates, full and closed conferences."""
    if not user_id:
        raise ConferenceError("You must be signed in to register.")
    conf = _require_conference(conn, event_id)
    if (conf["status"] or "planning") not in REGISTRATION_OPEN:
        raise ConferenceError(
            f"Registration for '{conf['title']}' is not open (status: {conf['status']}).")
    if user_type not in ATTENDEE_TYPES:
        user_type = "student"
    existing = conn.execute(
        """SELECT registration_id, COALESCE(attendance_status, 'registered')
             FROM unified_event_registrations WHERE event_id = ? AND user_id = ?""",
        (event_id, user_id)).fetchone()
    if existing and existing[1] != "cancelled":
        raise ConferenceError(f"You are already registered for '{conf['title']}'.")
    cap = conf["max_capacity"] or 0
    if cap and conf["registrations"] >= cap:
        raise ConferenceError(f"'{conf['title']}' is full ({cap} places).")
    now = _now()
    if existing:
        conn.execute(
            """UPDATE unified_event_registrations
                  SET attendance_status = 'registered', status = 'registered',
                      registration_date = ?, attendee_name = ?, user_type = ?
                WHERE registration_id = ?""",
            (now, attendee_name, user_type, existing[0]))
        conn.commit()
        return existing[0]
    cur = conn.execute(
        """INSERT INTO unified_event_registrations
               (event_id, user_id, user_type, registration_date,
                attendance_status, status, attendee_name, created_at)
           VALUES (?, ?, ?, ?, 'registered', 'registered', ?, ?)""",
        (event_id, user_id, user_type, now, attendee_name, now))
    conn.commit()
    return cur.lastrowid


def registrations(conn, event_id: int) -> list[dict]:
    """Attendees, with the track of any submission they made to this conference."""
    return _rows(conn.execute(
        """
        SELECT r.registration_id, r.user_id,
               COALESCE(r.attendee_name, r.user_id) AS name,
               COALESCE(r.user_type, 'student') AS user_type,
               r.registration_date,
               (SELECT s.track FROM su_conference_submissions s
                 WHERE s.event_id = r.event_id AND s.author_id = r.user_id
                   AND s.track IS NOT NULL AND s.track != ''
                 ORDER BY s.submitted_at LIMIT 1) AS track
          FROM unified_event_registrations r
         WHERE r.event_id = ?
           AND COALESCE(r.attendance_status, 'registered') != 'cancelled'
         ORDER BY r.registration_date DESC
        """, (event_id,)))


def registration_stats(conn, event_id: int) -> dict:
    conf = _require_conference(conn, event_id)
    regs = registrations(conn, event_id)
    by_type: dict[str, int] = {}
    by_track: dict[str, int] = {}
    for r in regs:
        by_type[r["user_type"]] = by_type.get(r["user_type"], 0) + 1
        if r["track"]:
            by_track[r["track"]] = by_track.get(r["track"], 0) + 1
    return {"total": len(regs), "capacity": conf["max_capacity"] or 0,
            "by_type": by_type, "by_track": by_track}


def registrant_contacts(conn, event_id: int) -> list[tuple[str, str]]:
    """(name, email) for every current registrant that has an address."""
    from education_system.systems.university.domains.student_life.domain.student_life.student_union.identity import (
        contact_email,
    )
    cur = conn.cursor()
    out = []
    for r in registrations(conn, event_id):
        email = contact_email(cur, r["user_id"])
        if email:
            out.append((r["name"], email))
    return out


# --------------------------------------------------------------------------
# Submissions (papers, presentations, posters)
# --------------------------------------------------------------------------

def submit(conn, event_id: int, *, kind: str, title: str, author_id: str,
           author_name: str | None = None, abstract: str | None = None,
           track: str | None = None, file_path: str | None = None) -> int:
    if not author_id:
        raise ConferenceError("You must be signed in to submit.")
    if kind not in SUBMISSION_KINDS:
        raise ConferenceError(f"Unknown submission type '{kind}'.")
    title = (title or "").strip()
    if not title:
        raise ConferenceError("A submission needs a title.")
    conf = _require_conference(conn, event_id)
    if (conf["status"] or "planning") not in SUBMISSIONS_OPEN:
        raise ConferenceError(
            f"'{conf['title']}' is not accepting submissions (status: {conf['status']}).")
    dup = conn.execute(
        """SELECT 1 FROM su_conference_submissions
            WHERE event_id = ? AND author_id = ? AND kind = ? AND lower(title) = lower(?)""",
        (event_id, author_id, kind, title)).fetchone()
    if dup:
        raise ConferenceError(f"You have already submitted '{title}' to this conference.")
    cur = conn.execute(
        """INSERT INTO su_conference_submissions
               (event_id, kind, title, abstract, track, author_id, author_name,
                file_path, status, submitted_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'submitted', ?)""",
        (event_id, kind, title, (abstract or "").strip() or None,
         (track or "").strip() or None, author_id, author_name, file_path, _now()))
    conn.commit()
    return cur.lastrowid


def attach_file(conn, submission_id: int, file_path: str) -> None:
    conn.execute("UPDATE su_conference_submissions SET file_path = ? WHERE submission_id = ?",
                 (file_path, submission_id))
    conn.commit()


def store_upload(source: str, event_id: int, submission_id: int,
                 base_dir: Path | None = None) -> str:
    """Copy an uploaded file under the university upload directory."""
    if base_dir is None:
        from education_system import paths
        base_dir = Path(paths.UNIVERSITY_UPLOAD_DIR) / "student_union" / "conferences"
    src = Path(source)
    if not src.is_file():
        raise ConferenceError(f"File not found: {source}")
    dest_dir = Path(base_dir) / str(event_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{submission_id}_{src.name}"
    shutil.copy2(src, dest)
    return str(dest)


_SUB_SELECT = """
    SELECT s.submission_id, s.event_id, e.title AS conference, s.kind, s.title,
           s.abstract, s.track, s.author_id, s.author_name, s.file_path, s.status,
           s.decision_note, s.decided_by, s.decided_at, s.session_id,
           s.submitted_at, ss.title AS session_title, ss.starts_at AS session_starts,
           ss.location AS session_location,
           (SELECT COUNT(*) FROM su_conference_feedback f
             WHERE f.submission_id = s.submission_id) AS feedback_count,
           (SELECT AVG(f.rating) FROM su_conference_feedback f
             WHERE f.submission_id = s.submission_id) AS avg_rating,
           (SELECT COUNT(*) FROM su_conference_questions q
             WHERE q.submission_id = s.submission_id AND q.parent_id IS NULL) AS questions
      FROM su_conference_submissions s
      JOIN unified_events e ON e.event_id = s.event_id
      LEFT JOIN su_conference_sessions ss ON ss.session_id = s.session_id
     WHERE 1 = 1
"""


def list_submissions(conn, *, event_id: int | None = None,
                     kind: str | Iterable[str] | None = None,
                     author_id: str | None = None,
                     statuses: Iterable[str] | None = None) -> list[dict]:
    sql = _SUB_SELECT
    params: list[Any] = []
    if event_id is not None:
        sql += " AND s.event_id = ?"
        params.append(event_id)
    if kind:
        kinds = [kind] if isinstance(kind, str) else list(kind)
        sql += " AND s.kind IN (" + ",".join("?" for _ in kinds) + ")"
        params.extend(kinds)
    if author_id:
        sql += " AND s.author_id = ?"
        params.append(author_id)
    if statuses:
        st = list(statuses)
        sql += " AND s.status IN (" + ",".join("?" for _ in st) + ")"
        params.extend(st)
    sql += " ORDER BY s.submitted_at DESC"
    return _rows(conn.execute(sql, params))


def get_submission(conn, submission_id: int) -> Optional[dict]:
    return _one(conn.execute(_SUB_SELECT + " AND s.submission_id = ?", (submission_id,)))


def decide(conn, submission_id: int, status: str, *, decided_by: str | None,
           note: str | None = None) -> dict:
    """Record a review decision. Returns the updated submission."""
    if status not in ("under_review", "accepted", "rejected", "revisions_requested"):
        raise ConferenceError(f"'{status}' is not a review decision.")
    sub = get_submission(conn, submission_id)
    if not sub:
        raise ConferenceError("That submission no longer exists.")
    if sub["status"] == status:
        raise ConferenceError(f"'{sub['title']}' is already {status.replace('_', ' ')}.")
    conn.execute(
        """UPDATE su_conference_submissions
              SET status = ?, decision_note = ?, decided_by = ?, decided_at = ?
            WHERE submission_id = ?""",
        (status, (note or "").strip() or None, decided_by, _now(), submission_id))
    conn.commit()
    return get_submission(conn, submission_id)


def author_email(conn, submission: dict) -> str | None:
    from education_system.systems.university.domains.student_life.domain.student_life.student_union.identity import (
        contact_email,
    )
    return contact_email(conn.cursor(), submission.get("author_id"))


# --------------------------------------------------------------------------
# Speakers and sessions
# --------------------------------------------------------------------------

def invite_speaker(conn, event_id: int, *, name: str, email: str | None = None,
                   institution: str | None = None, topic: str | None = None,
                   invited_by: str | None = None) -> int:
    name = (name or "").strip()
    if not name:
        raise ConferenceError("A speaker needs a name.")
    email = (email or "").strip() or None
    if email and "@" not in email:
        raise ConferenceError("That e-mail address does not look right.")
    _require_conference(conn, event_id)
    if email and conn.execute(
            "SELECT 1 FROM su_conference_speakers WHERE event_id = ? AND lower(email) = lower(?)",
            (event_id, email)).fetchone():
        raise ConferenceError(f"{email} has already been invited to this conference.")
    cur = conn.execute(
        """INSERT INTO su_conference_speakers
               (event_id, name, email, institution, topic, status, invited_by, invited_at)
           VALUES (?, ?, ?, ?, ?, 'invited', ?, ?)""",
        (event_id, name, email, (institution or "").strip() or None,
         (topic or "").strip() or None, invited_by, _now()))
    conn.commit()
    return cur.lastrowid


def set_speaker_status(conn, speaker_id: int, status: str) -> None:
    if status not in SPEAKER_STATUSES:
        raise ConferenceError(f"Unknown speaker status '{status}'.")
    conn.execute("UPDATE su_conference_speakers SET status = ? WHERE speaker_id = ?",
                 (status, speaker_id))
    conn.commit()


def list_speakers(conn, event_id: int | None = None) -> list[dict]:
    sql = """
        SELECT sp.speaker_id, sp.event_id, e.title AS conference, sp.name, sp.email,
               sp.institution, sp.topic, sp.status, sp.invited_at,
               (SELECT group_concat(ss.title, ', ') FROM su_conference_sessions ss
                 WHERE ss.speaker_id = sp.speaker_id) AS sessions
          FROM su_conference_speakers sp
          JOIN unified_events e ON e.event_id = sp.event_id
    """
    params: tuple = ()
    if event_id is not None:
        sql += " WHERE sp.event_id = ?"
        params = (event_id,)
    sql += " ORDER BY sp.status, sp.name"
    return _rows(conn.execute(sql, params))


def add_session(conn, event_id: int, *, title: str, session_type: str,
                date: str, start_time: str, end_time: str | None = None,
                location: str | None = None, speaker_id: int | None = None,
                notes: str | None = None) -> int:
    title = (title or "").strip()
    if not title:
        raise ConferenceError("A session needs a title.")
    if session_type not in SESSION_TYPES:
        raise ConferenceError(f"Unknown session type '{session_type}'.")
    conf = _require_conference(conn, event_id)
    date = _check_date(date, "Session date")
    start = _check_time(start_time, "Start time")
    if not start:
        raise ConferenceError("A session needs a start time.")
    end = _check_time(end_time, "End time")
    if end and end <= start:
        raise ConferenceError("The session ends before it starts.")
    first = conf["start_date"] or date
    last = conf["end_date"] or first
    if not (first <= date <= last):
        raise ConferenceError(
            f"The session date is outside the conference ({first} to {last}).")
    if speaker_id is not None and not conn.execute(
            "SELECT 1 FROM su_conference_speakers WHERE speaker_id = ? AND event_id = ?",
            (speaker_id, event_id)).fetchone():
        raise ConferenceError("That speaker is not on this conference.")
    cur = conn.execute(
        """INSERT INTO su_conference_sessions
               (event_id, title, session_type, starts_at, ends_at, location,
                speaker_id, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (event_id, title, session_type, f"{date} {start}",
         f"{date} {end}" if end else None, (location or "").strip() or None,
         speaker_id, (notes or "").strip() or None))
    conn.commit()
    return cur.lastrowid


def list_sessions(conn, event_id: int, *, session_type: str | None = None) -> list[dict]:
    sql = """
        SELECT ss.session_id, ss.title, ss.session_type, ss.starts_at, ss.ends_at,
               ss.location, ss.notes, sp.name AS speaker_name,
               sp.institution AS speaker_institution
          FROM su_conference_sessions ss
          LEFT JOIN su_conference_speakers sp ON sp.speaker_id = ss.speaker_id
         WHERE ss.event_id = ?
    """
    params: list[Any] = [event_id]
    if session_type:
        sql += " AND ss.session_type = ?"
        params.append(session_type)
    sql += " ORDER BY ss.starts_at, ss.title"
    sessions = _rows(conn.execute(sql, params))
    for s in sessions:
        s["submissions"] = _rows(conn.execute(
            """SELECT submission_id, kind, title, author_name, track
                 FROM su_conference_submissions
                WHERE session_id = ? ORDER BY title""", (s["session_id"],)))
    return sessions


def schedule_text(conn, event_id: int) -> str:
    """The programme as plain text, grouped by day ('' when there is none)."""
    conf = _require_conference(conn, event_id)
    sessions = list_sessions(conn, event_id)
    if not sessions:
        return ""
    lines = [f"CONFERENCE SCHEDULE - {conf['title']}", "=" * 80, ""]
    day = None
    for s in sessions:
        d = s["starts_at"][:10]
        if d != day:
            day = d
            try:
                label = datetime.strptime(d, "%Y-%m-%d").strftime("%A, %d %B %Y")
            except ValueError:
                label = d
            lines += ["", f"{label}", "-" * 40]
        end = f" - {s['ends_at'][11:16]}" if s["ends_at"] else ""
        lines.append(f"{s['starts_at'][11:16]}{end}  {s['title']} "
                     f"[{s['session_type'].title()}]")
        if s["speaker_name"]:
            inst = f" ({s['speaker_institution']})" if s["speaker_institution"] else ""
            lines.append(f"{'':15}Speaker: {s['speaker_name']}{inst}")
        if s["location"]:
            lines.append(f"{'':15}Location: {s['location']}")
        for sub in s["submissions"]:
            by = f" ({sub['author_name']})" if sub["author_name"] else ""
            lines.append(f"{'':15}* {sub['title']}{by}")
    return "\n".join(lines) + "\n"


def assign_to_session(conn, submission_id: int, session_id: int, *,
                      author_id: str | None = None) -> None:
    """Place a submission in a session (an author may only move their own)."""
    sub = get_submission(conn, submission_id)
    if not sub:
        raise ConferenceError("That submission no longer exists.")
    if author_id is not None and sub["author_id"] != author_id:
        raise ConferenceError("You can only register your own submissions for a session.")
    if sub["status"] != "accepted":
        raise ConferenceError(f"'{sub['title']}' has not been accepted yet.")
    sess = conn.execute("SELECT event_id FROM su_conference_sessions WHERE session_id = ?",
                        (session_id,)).fetchone()
    if not sess or sess[0] != sub["event_id"]:
        raise ConferenceError("That session is not part of this conference.")
    conn.execute("UPDATE su_conference_submissions SET session_id = ? WHERE submission_id = ?",
                 (session_id, submission_id))
    conn.commit()


# --------------------------------------------------------------------------
# Q&A
# --------------------------------------------------------------------------

def ask(conn, submission_id: int, *, author_id: str, body: str,
        author_name: str | None = None, anonymous: bool = False,
        parent_id: int | None = None) -> int:
    if not author_id:
        raise ConferenceError("You must be signed in to post.")
    body = (body or "").strip()
    if not body:
        raise ConferenceError("Write something first.")
    if not get_submission(conn, submission_id):
        raise ConferenceError("That presentation no longer exists.")
    if parent_id is not None:
        parent = conn.execute(
            "SELECT submission_id FROM su_conference_questions WHERE question_id = ?",
            (parent_id,)).fetchone()
        if not parent or parent[0] != submission_id:
            raise ConferenceError("That question no longer exists.")
    cur = conn.execute(
        """INSERT INTO su_conference_questions
               (submission_id, parent_id, author_id, author_name, body,
                is_anonymous, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (submission_id, parent_id, author_id, author_name, body,
         1 if anonymous else 0, _now()))
    conn.commit()
    return cur.lastrowid


def list_questions(conn, event_id: int | None = None) -> list[dict]:
    sql = """
        SELECT q.question_id, q.submission_id, s.title AS topic, q.body,
               CASE WHEN q.is_anonymous = 1 THEN 'Anonymous'
                    ELSE COALESCE(q.author_name, q.author_id) END AS asker,
               q.created_at,
               (SELECT COUNT(*) FROM su_conference_questions a
                 WHERE a.parent_id = q.question_id) AS answers
          FROM su_conference_questions q
          JOIN su_conference_submissions s ON s.submission_id = q.submission_id
         WHERE q.parent_id IS NULL
    """
    params: tuple = ()
    if event_id is not None:
        sql += " AND s.event_id = ?"
        params = (event_id,)
    sql += " ORDER BY q.created_at DESC"
    return _rows(conn.execute(sql, params))


def thread(conn, question_id: int) -> tuple[Optional[dict], list[dict]]:
    sel = """SELECT q.question_id, q.body, q.created_at,
                    CASE WHEN q.is_anonymous = 1 THEN 'Anonymous'
                         ELSE COALESCE(q.author_name, q.author_id) END AS author
               FROM su_conference_questions q"""
    question = _one(conn.execute(sel + " WHERE q.question_id = ?", (question_id,)))
    answers = _rows(conn.execute(sel + " WHERE q.parent_id = ? ORDER BY q.created_at",
                                 (question_id,)))
    return question, answers


# --------------------------------------------------------------------------
# Feedback
# --------------------------------------------------------------------------

def give_feedback(conn, submission_id: int, *, reviewer_id: str, rating: int,
                  content: int | None = None, skills: int | None = None,
                  visuals: int | None = None, qa: int | None = None,
                  comments: str | None = None) -> None:
    """Record (or replace) one reviewer's feedback on a presentation."""
    if not reviewer_id:
        raise ConferenceError("You must be signed in to give feedback.")
    for label, v in (("Rating", rating), ("Content", content), ("Skills", skills),
                     ("Visuals", visuals), ("Q&A", qa)):
        if v is not None and not (1 <= int(v) <= 5):
            raise ConferenceError(f"{label} must be between 1 and 5.")
    sub = get_submission(conn, submission_id)
    if not sub:
        raise ConferenceError("That presentation no longer exists.")
    if sub["author_id"] == reviewer_id:
        raise ConferenceError("You cannot give feedback on your own work.")
    conn.execute(
        """INSERT INTO su_conference_feedback
               (submission_id, reviewer_id, rating, content_rating, skills_rating,
                visuals_rating, qa_rating, comments, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT (submission_id, reviewer_id) DO UPDATE SET
               rating = excluded.rating, content_rating = excluded.content_rating,
               skills_rating = excluded.skills_rating,
               visuals_rating = excluded.visuals_rating,
               qa_rating = excluded.qa_rating, comments = excluded.comments,
               created_at = excluded.created_at""",
        (submission_id, reviewer_id, int(rating), content, skills, visuals, qa,
         (comments or "").strip() or None, _now()))
    conn.commit()


def feedback_stats(conn, *, event_id: int | None = None,
                   author_id: str | None = None) -> dict:
    """Averages over feedback, optionally for one conference or one author."""
    where, params = ["1 = 1"], []
    if event_id is not None:
        where.append("s.event_id = ?")
        params.append(event_id)
    if author_id is not None:
        where.append("s.author_id = ?")
        params.append(author_id)
    w = " AND ".join(where)
    totals = _one(conn.execute(
        f"""SELECT COUNT(*) AS responses, AVG(f.rating) AS avg_rating,
                   AVG(f.content_rating) AS content, AVG(f.skills_rating) AS skills,
                   AVG(f.visuals_rating) AS visuals, AVG(f.qa_rating) AS qa
              FROM su_conference_feedback f
              JOIN su_conference_submissions s ON s.submission_id = f.submission_id
             WHERE {w}""", params))  # db-audit: ignore[DBW001] - fixed fragments
    top = _rows(conn.execute(
        f"""SELECT s.title, AVG(f.rating) AS avg_rating, COUNT(*) AS responses
              FROM su_conference_feedback f
              JOIN su_conference_submissions s ON s.submission_id = f.submission_id
             WHERE {w}
             GROUP BY s.submission_id ORDER BY avg_rating DESC, responses DESC
             LIMIT 5""", params))  # db-audit: ignore[DBW001] - fixed fragments
    comments = _rows(conn.execute(
        f"""SELECT s.title, f.rating, f.comments, f.created_at
              FROM su_conference_feedback f
              JOIN su_conference_submissions s ON s.submission_id = f.submission_id
             WHERE {w} AND f.comments IS NOT NULL
             ORDER BY f.created_at DESC LIMIT 20""", params))  # db-audit: ignore[DBW001] - fixed fragments
    totals["top"] = top
    totals["comments"] = comments
    return totals


# --------------------------------------------------------------------------
# Awards and analytics
# --------------------------------------------------------------------------

def grant_award(conn, submission_id: int, *, award_name: str,
                prize: str | None = None, awarded_by: str | None = None) -> int:
    award_name = (award_name or "").strip()
    if not award_name:
        raise ConferenceError("An award needs a name.")
    sub = get_submission(conn, submission_id)
    if not sub:
        raise ConferenceError("That submission no longer exists.")
    if sub["status"] != "accepted":
        raise ConferenceError("Only accepted work can receive an award.")
    if conn.execute(
            """SELECT 1 FROM su_conference_awards
                WHERE event_id = ? AND lower(award_name) = lower(?)""",
            (sub["event_id"], award_name)).fetchone():
        raise ConferenceError(f"'{award_name}' has already been awarded at this conference.")
    cur = conn.execute(
        """INSERT INTO su_conference_awards
               (event_id, submission_id, award_name, prize, awarded_by, awarded_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (sub["event_id"], submission_id, award_name,
         (prize or "").strip() or None, awarded_by, _now()))
    conn.commit()
    return cur.lastrowid


def list_awards(conn, event_id: int | None = None) -> list[dict]:
    sql = """
        SELECT a.award_id, a.event_id, e.title AS conference, a.award_name, a.prize,
               a.awarded_at, s.title AS submission_title, s.author_name, s.track, s.kind
          FROM su_conference_awards a
          JOIN unified_events e ON e.event_id = a.event_id
          JOIN su_conference_submissions s ON s.submission_id = a.submission_id
    """
    params: tuple = ()
    if event_id is not None:
        sql += " WHERE a.event_id = ?"
        params = (event_id,)
    sql += " ORDER BY e.title, a.awarded_at"
    return _rows(conn.execute(sql, params))


def analytics(conn, event_id: int) -> dict:
    conf = _require_conference(conn, event_id)
    subs = list_submissions(conn, event_id=event_id)
    by_status: dict[str, int] = {}
    by_kind: dict[str, int] = {}
    for s in subs:
        by_status[s["status"]] = by_status.get(s["status"], 0) + 1
        by_kind[s["kind"]] = by_kind.get(s["kind"], 0) + 1
    decided = by_status.get("accepted", 0) + by_status.get("rejected", 0)
    acceptance = (by_status.get("accepted", 0) / decided * 100) if decided else None
    stats = registration_stats(conn, event_id)
    fill = (stats["total"] / stats["capacity"] * 100) if stats["capacity"] else None
    fb = feedback_stats(conn, event_id=event_id)
    return {
        "conference": conf, "submissions": len(subs), "by_status": by_status,
        "by_kind": by_kind, "acceptance_rate": acceptance,
        "registrations": stats["total"], "capacity": stats["capacity"],
        "fill_rate": fill, "speakers": conf["speakers"],
        "sessions": len(list_sessions(conn, event_id)),
        "feedback_responses": fb["responses"], "avg_rating": fb["avg_rating"],
        "awards": len(list_awards(conn, event_id)),
    }


__all__ = [
    "ConferenceError", "ensure_schema", "create_conference", "update_conference",
    "list_conferences", "get_conference", "register", "registrations",
    "registration_stats", "registrant_contacts", "submit", "attach_file",
    "store_upload", "list_submissions", "get_submission", "decide",
    "author_email", "invite_speaker", "set_speaker_status", "list_speakers",
    "add_session", "list_sessions", "schedule_text", "assign_to_session", "ask",
    "list_questions", "thread", "give_feedback", "feedback_stats", "grant_award",
    "list_awards", "analytics", "CONFERENCE_STATUSES", "SUBMISSION_KINDS",
    "SESSION_TYPES", "ATTENDEE_TYPES", "SPEAKER_STATUSES",
]
