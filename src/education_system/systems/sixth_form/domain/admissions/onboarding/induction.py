"""Induction sessions: booking learners and taking the register.

Two tables in the onboarding database:

* ``onboarding_induction_sessions`` — a session (title, date, start /
  end time, room, capacity, academic year, the year group it is for) and
  the onboarding task it satisfies (``task_key``, e.g. "Safeguarding
  briefing");
* ``onboarding_induction_attendance`` — one row per (session, learner):
  *Booked* until the register is taken, then *Present* / *Absent* /
  *Excused*.

Marking a learner **Present** ticks the session's task on their open
checklist (the evidence reference is ``induction:<session id>``); a mark
corrected away from Present re-opens a task ticked from that session.
Writes need ``admissions`` or ``students.manage`` (the onboarding
writers); reads are open.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Iterable

from education_system.systems.sixth_form.domain.admissions.onboarding import (
    onboarding as ob,
)

logger = logging.getLogger(__name__)

ValidationError = ob.ValidationError

SESSION_STATUSES: tuple[str, ...] = ("Scheduled", "Cancelled")
BOOKED = "Booked"
MARKS: tuple[str, ...] = ("Present", "Absent", "Excused")
ATTENDANCE_STATUSES: tuple[str, ...] = (BOOKED, *MARKS)
REF_PREFIX = "induction:"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS onboarding_induction_sessions (
    session_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    title          TEXT NOT NULL,
    session_date   TEXT NOT NULL,
    start_time     TEXT NOT NULL,
    end_time       TEXT,
    room           TEXT,
    capacity       INTEGER,
    academic_year  TEXT,
    year_group     INTEGER,
    task_key       TEXT,
    notes          TEXT,
    status         TEXT NOT NULL DEFAULT 'Scheduled',
    status_reason  TEXT,
    created_by     TEXT,
    created_at     TEXT DEFAULT (datetime('now')),
    updated_at     TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS onboarding_induction_attendance (
    attendance_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id     INTEGER NOT NULL,
    student_id     TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'Booked',
    booked_by      TEXT,
    booked_at      TEXT DEFAULT (datetime('now')),
    marked_by      TEXT,
    marked_at      TEXT,
    note           TEXT,
    UNIQUE (session_id, student_id),
    FOREIGN KEY (session_id)
        REFERENCES onboarding_induction_sessions(session_id)
        ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES students(student_id)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_ob_ind_date
    ON onboarding_induction_sessions(session_date);
CREATE INDEX IF NOT EXISTS idx_ob_ind_att_student
    ON onboarding_induction_attendance(student_id);
"""

_READY: set[str] = set()


def init_db() -> None:
    key = str(ob.DB_PATH)
    if key in _READY:
        return
    ob.init_db()
    with ob._connect() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()
    _READY.add(key)


@dataclass
class Session:
    session_id: int
    title: str
    session_date: str
    start_time: str
    end_time: str | None
    room: str | None
    capacity: int | None
    academic_year: str | None
    year_group: int | None
    task_key: str | None
    notes: str | None
    status: str
    status_reason: str | None
    created_by: str | None
    created_at: str
    updated_at: str
    booked: int = 0
    present: int = 0

    @property
    def places_left(self) -> int | None:
        return None if self.capacity is None else max(
            0, self.capacity - self.booked)

    @property
    def is_cancelled(self) -> bool:
        return self.status == "Cancelled"


@dataclass
class Attendance:
    attendance_id: int
    session_id: int
    student_id: str
    status: str
    booked_by: str | None
    booked_at: str | None
    marked_by: str | None
    marked_at: str | None
    note: str | None
    student_name: str = ""


@dataclass
class BookingResult:
    booked: list[str] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)

    def lines(self) -> list[str]:
        return ([f"{len(self.booked)} learner(s) booked"]
                + [f"{sid}: {why}" for sid, why in self.skipped])


@dataclass
class RegisterResult:
    marked: int = 0
    ticked: list[str] = field(default_factory=list)
    reopened: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    def lines(self) -> list[str]:
        out = [f"{self.marked} mark(s) saved"]
        out += [f"Task ticked: {t}" for t in self.ticked]
        out += [f"Task re-opened: {t}" for t in self.reopened]
        return out + self.problems


# ── Validation ──────────────────────────────────────────────────────

_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _text(v: Any) -> str | None:
    s = (v or "").strip() if isinstance(v, str) else (
        str(v).strip() if v is not None else "")
    return s or None


def _validate(p: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["title"] = _text(p.get("title"))
    if not out["title"]:
        raise ValidationError("Title is required")
    day = _text(p.get("session_date"))
    try:
        _dt.date.fromisoformat(day or "")
    except ValueError:
        raise ValidationError("Session date must be YYYY-MM-DD") from None
    out["session_date"] = day
    for k, label, req in (("start_time", "Start time", True),
                          ("end_time", "End time", False)):
        t = _text(p.get(k))
        if t is None and not req:
            out[k] = None
            continue
        if not t or not _TIME_RE.match(t):
            raise ValidationError(f"{label} must be HH:MM")
        out[k] = t
    if out["end_time"] and out["end_time"] <= out["start_time"]:
        raise ValidationError("End time must be after the start time")
    cap = p.get("capacity")
    if cap in (None, ""):
        out["capacity"] = None
    else:
        try:
            out["capacity"] = int(cap)
        except (TypeError, ValueError):
            raise ValidationError("Capacity must be a whole number") from None
        if out["capacity"] < 1:
            raise ValidationError("Capacity must be at least 1")
    yg = p.get("year_group")
    if yg in (None, ""):
        out["year_group"] = None
    else:
        try:
            out["year_group"] = int(yg)
        except (TypeError, ValueError):
            raise ValidationError("Year group must be 12 or 13") from None
        if out["year_group"] not in (12, 13):
            raise ValidationError("Year group must be 12 or 13")
    key = _text(p.get("task_key"))
    if key and (key in ob.ID_ITEMS or key in ob.CONSENT_ITEMS):
        raise ValidationError(f"'{key}' is proved by its own record, not by "
                              "attending a session")
    out["task_key"] = key
    out["room"] = _text(p.get("room"))
    out["notes"] = _text(p.get("notes"))
    year = _text(p.get("academic_year"))
    if year is None:
        from education_system.systems.sixth_form.domain.admissions.enrolments import (
            enrolments as _enr,
        )
        year = _enr.academic_year_for_date(out["session_date"])
    out["academic_year"] = year
    return out


# ── Sessions ────────────────────────────────────────────────────────

_SESSION_SELECT = """
SELECT s.*,
  (SELECT COUNT(*) FROM onboarding_induction_attendance a
    WHERE a.session_id = s.session_id) AS booked,
  (SELECT COUNT(*) FROM onboarding_induction_attendance a
    WHERE a.session_id = s.session_id AND a.status = 'Present') AS present
FROM onboarding_induction_sessions s"""


def _row(r: Any) -> Session:
    return Session(**{k: r[k] for k in r.keys()})


def get_session(session_id: int) -> Session | None:
    init_db()
    with ob._connect() as conn:
        r = conn.execute(f"{_SESSION_SELECT} WHERE s.session_id = ?",
                         (int(session_id),)).fetchone()
    return _row(r) if r else None


def _require_session(session_id: int) -> Session:
    s = get_session(session_id)
    if s is None:
        raise ValidationError(f"No induction session #{session_id}")
    return s


def list_sessions(*, academic_year: str | None = None,
                  year_group: int | None = None,
                  upcoming_only: bool = False,
                  include_cancelled: bool = False) -> list[Session]:
    init_db()
    clauses, args = [], []
    if academic_year:
        clauses.append("s.academic_year = ?")
        args.append(academic_year)
    if year_group is not None:
        clauses.append("(s.year_group IS NULL OR s.year_group = ?)")
        args.append(int(year_group))
    if upcoming_only:
        clauses.append("s.session_date >= ?")
        args.append(_dt.date.today().isoformat())
    if not include_cancelled:
        clauses.append("s.status != 'Cancelled'")
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    with ob._connect() as conn:
        return [_row(r) for r in conn.execute(
            f"{_SESSION_SELECT}{where} "  # noqa: S608 — fixed clauses
            "ORDER BY s.session_date, s.start_time", args).fetchall()]


def create_session(payload: dict[str, Any]) -> Session:
    ob._require_writer("adding induction sessions")
    init_db()
    p = _validate(payload)
    with ob._connect() as conn:
        cur = conn.execute(
            "INSERT INTO onboarding_induction_sessions (title, session_date, "
            "start_time, end_time, room, capacity, academic_year, year_group, "
            "task_key, notes, created_by) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (p["title"], p["session_date"], p["start_time"], p["end_time"],
             p["room"], p["capacity"], p["academic_year"], p["year_group"],
             p["task_key"], p["notes"], ob._actor()))
        conn.commit()
        new_id = cur.lastrowid
    _register_key(p["task_key"])
    return _require_session(new_id)


def update_session(session_id: int, payload: dict[str, Any]) -> Session:
    ob._require_writer("changing induction sessions")
    s = _require_session(session_id)
    if s.is_cancelled:
        raise ValidationError("The session is cancelled")
    merged = {k: payload.get(k, getattr(s, k)) for k in (
        "title", "session_date", "start_time", "end_time", "room",
        "capacity", "academic_year", "year_group", "task_key", "notes")}
    p = _validate(merged)
    if p["capacity"] is not None and p["capacity"] < s.booked:
        raise ValidationError(f"{s.booked} learner(s) are booked — the "
                              "capacity cannot be below that")
    with ob._connect() as conn:
        conn.execute(
            "UPDATE onboarding_induction_sessions SET title=?, session_date=?, "
            "start_time=?, end_time=?, room=?, capacity=?, academic_year=?, "
            "year_group=?, task_key=?, notes=?, updated_at=datetime('now') "
            "WHERE session_id=?",
            (p["title"], p["session_date"], p["start_time"], p["end_time"],
             p["room"], p["capacity"], p["academic_year"], p["year_group"],
             p["task_key"], p["notes"], int(session_id)))
        conn.commit()
    _register_key(p["task_key"])
    return _require_session(session_id)


def cancel_session(session_id: int, *, reason: str) -> Session:
    """Cancel a session (kept, with the reason; its register stays)."""
    ob._require_writer("cancelling induction sessions")
    s = _require_session(session_id)
    why = ob._min_text(reason, "The reason for cancelling")
    if s.present:
        raise ValidationError("The register has learners marked present — "
                              "the session took place")
    with ob._connect() as conn:
        conn.execute("UPDATE onboarding_induction_sessions SET status = "
                     "'Cancelled', status_reason = ?, updated_at = "
                     "datetime('now') WHERE session_id = ?",
                     (why, int(session_id)))
        conn.commit()
    return _require_session(session_id)


# ── Booking ─────────────────────────────────────────────────────────

def _live_enrolment(student_id: str, year: str | None) -> Any:
    from education_system.systems.sixth_form.domain.admissions.enrolments import (
        enrolments as _enr,
    )
    for e in _enr.list_enrolments(student_id=student_id, academic_year=year):
        if e.is_live:
            return e
    return None


def _clash(conn: Any, s: Session, student_id: str) -> str | None:
    rows = conn.execute(
        "SELECT x.* FROM onboarding_induction_sessions x JOIN "
        "onboarding_induction_attendance a ON a.session_id = x.session_id "
        "WHERE a.student_id = ? AND x.session_date = ? AND x.status != "
        "'Cancelled' AND x.session_id != ?",
        (student_id, s.session_date, s.session_id)).fetchall()
    end = s.end_time or s.start_time
    for r in rows:
        other_end = r["end_time"] or r["start_time"]
        if r["start_time"] <= end and s.start_time <= other_end:
            return f"already booked on '{r['title']}' at {r['start_time']}"
    return None


def book(session_id: int, student_ids: Iterable[str]) -> BookingResult:
    """Book learners on a session. A learner is skipped (with the reason)
    when the session is full or cancelled, already booked, not on roll,
    in a different year group from the session's audience, or booked on
    another session at the same time."""
    ob._require_writer("booking induction sessions")
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    s = _require_session(session_id)
    res = BookingResult()
    if s.is_cancelled:
        raise ValidationError("The session is cancelled")
    left = s.places_left
    with ob._connect() as conn:
        for raw in student_ids:
            sid = (raw or "").strip()
            if not sid:
                continue
            st = _students.get_student(sid)
            if st is None:
                res.skipped.append((sid, "no such student"))
                continue
            if not st.on_roll:
                res.skipped.append((sid, f"not on roll ({st.status})"))
                continue
            if conn.execute("SELECT 1 FROM onboarding_induction_attendance "
                            "WHERE session_id = ? AND student_id = ?",
                            (s.session_id, sid)).fetchone():
                res.skipped.append((sid, "already booked"))
                continue
            if s.year_group is not None:
                e = _live_enrolment(sid, s.academic_year)
                if e is None or e.year_group != s.year_group:
                    res.skipped.append((sid, f"not enrolled in Year "
                                             f"{s.year_group} in "
                                             f"{s.academic_year}"))
                    continue
            clash = _clash(conn, s, sid)
            if clash:
                res.skipped.append((sid, clash))
                continue
            if left is not None and left <= 0:
                res.skipped.append((sid, "the session is full"))
                continue
            conn.execute(
                "INSERT INTO onboarding_induction_attendance (session_id, "
                "student_id, booked_by) VALUES (?, ?, ?)",
                (s.session_id, sid, ob._actor()))
            res.booked.append(sid)
            if left is not None:
                left -= 1
        conn.commit()
    return res


def book_cohort(session_id: int) -> BookingResult:
    """Book every learner with a live enrolment in the session's year (and
    year group, if it has one) who is not booked yet."""
    from education_system.systems.sixth_form.domain.admissions.enrolments import (
        enrolments as _enr,
    )
    s = _require_session(session_id)
    have = {a.student_id for a in register(session_id)}
    ids = sorted({e.student_id for e in _enr.list_enrolments(
        academic_year=s.academic_year, year_group=s.year_group)
        if e.is_live and e.student_id not in have})
    return book(session_id, ids)


def unbook(session_id: int, student_id: str) -> bool:
    """Take a learner off a session (only before they are marked)."""
    ob._require_writer("booking induction sessions")
    init_db()
    with ob._connect() as conn:
        r = conn.execute("SELECT status FROM onboarding_induction_attendance "
                         "WHERE session_id = ? AND student_id = ?",
                         (int(session_id), student_id)).fetchone()
        if r is None:
            return False
        if r["status"] != BOOKED:
            raise ValidationError(f"{student_id} is already marked "
                                  f"{r['status']} — correct the mark instead")
        conn.execute("DELETE FROM onboarding_induction_attendance WHERE "
                     "session_id = ? AND student_id = ?",
                     (int(session_id), student_id))
        conn.commit()
    return True


def register(session_id: int) -> list[Attendance]:
    """The session's register, by learner name."""
    init_db()
    with ob._connect() as conn:
        rows = conn.execute(
            "SELECT * FROM onboarding_induction_attendance WHERE "
            "session_id = ?", (int(session_id),)).fetchall()
        names = ob._names_for(conn, {r["student_id"] for r in rows})
    out = [Attendance(**{k: r[k] for k in r.keys()},
                      student_name=names.get(r["student_id"], ""))
           for r in rows]
    return sorted(out, key=lambda a: (a.student_name, a.student_id))


def learner_sessions(student_id: str) -> list[tuple[Session, Attendance]]:
    """Every session the learner is booked on, with their mark."""
    init_db()
    with ob._connect() as conn:
        rows = conn.execute(
            "SELECT * FROM onboarding_induction_attendance WHERE "
            "student_id = ?", (student_id,)).fetchall()
    out = []
    for r in rows:
        s = get_session(r["session_id"])
        if s is not None:
            out.append((s, Attendance(**{k: r[k] for k in r.keys()})))
    return sorted(out, key=lambda t: (t[0].session_date, t[0].start_time))


# ── Register ────────────────────────────────────────────────────────

def _matching_items(student_id: str, key: str) -> list[ob.Item]:
    out = []
    for c in ob.list_checklists(student_id=student_id, open_only=True):
        out += [i for i in ob.list_items(checklist_id=c.checklist_id)
                if i.key == key]
    return out


def mark_register(session_id: int, marks: dict[str, str], *,
                  note: str | None = None) -> RegisterResult:
    """Save marks (student id -> Present / Absent / Excused) for booked
    learners. Present ticks the session's onboarding task on the learner's
    open checklist; a mark changed away from Present re-opens a task
    ticked from this session. The session must have started."""
    ob._require_writer("taking induction registers")
    s = _require_session(session_id)
    if s.is_cancelled:
        raise ValidationError("The session is cancelled")
    if s.session_date > _dt.date.today().isoformat():
        raise ValidationError("The register can be taken on or after the "
                              f"session date ({s.session_date})")
    for sid, mark in marks.items():
        if mark not in MARKS:
            raise ValidationError(f"{sid}: mark must be one of "
                                  f"{', '.join(MARKS)}")
    res = RegisterResult()
    now = _dt.datetime.now().isoformat(sep=" ", timespec="seconds")
    changed: list[tuple[str, str, str]] = []
    with ob._connect() as conn:
        for sid, mark in marks.items():
            r = conn.execute(
                "SELECT status FROM onboarding_induction_attendance WHERE "
                "session_id = ? AND student_id = ?",
                (s.session_id, sid)).fetchone()
            if r is None:
                res.problems.append(f"{sid}: not booked on this session")
                continue
            conn.execute(
                "UPDATE onboarding_induction_attendance SET status = ?, "
                "marked_by = ?, marked_at = ?, note = COALESCE(?, note) "
                "WHERE session_id = ? AND student_id = ?",
                (mark, ob._actor(), now, _text(note), s.session_id, sid))
            res.marked += 1
            changed.append((sid, r["status"], mark))
        conn.commit()
    if not s.task_key:
        return res
    ref = f"{REF_PREFIX}{s.session_id}"
    for sid, before, mark in changed:
        try:
            for item in _matching_items(sid, s.task_key):
                if mark == "Present" and not item.is_done:
                    ob.set_item_status(item.item_id, "Done")
                    res.ticked.append(f"{sid}: {item.task_name}")
                elif mark != "Present" and before == "Present" and \
                        item.is_done and item.evidence_ref == ref:
                    ob.set_item_status(item.item_id, "Pending")
                    res.reopened.append(f"{sid}: {item.task_name}")
        except Exception as exc:  # noqa: BLE001 — the marks are saved
            logger.exception("Induction task for %s", sid)
            res.problems.append(f"{sid}: task not updated — {exc}")
    return res


# ── Evidence rule ───────────────────────────────────────────────────

def attended(student_id: str, task_key: str) -> Session | None:
    """The latest session for *task_key* the learner was present at."""
    init_db()
    with ob._connect() as conn:
        r = conn.execute(
            "SELECT s.session_id FROM onboarding_induction_sessions s JOIN "
            "onboarding_induction_attendance a ON a.session_id = s.session_id "
            "WHERE a.student_id = ? AND s.task_key = ? AND a.status = "
            "'Present' ORDER BY s.session_date DESC, s.start_time DESC "
            "LIMIT 1", (student_id, task_key)).fetchone()
    return get_session(r["session_id"]) if r else None


def _rule(previous):
    def rule(sid: str, item: Any):
        s = attended(sid, item.key)
        if s is not None:
            return True, f"{REF_PREFIX}{s.session_id}", ""
        if previous is not None:
            return previous(sid, item)
        return None, None, ""      # briefed some other way: staff's word
    rule._induction = True  # type: ignore[attr-defined]
    return rule


def _register_key(key: str | None) -> None:
    if not key:
        return
    ob._load_evidence_sources()      # record rules first: kept as fallback
    prev = ob.EVIDENCE_RULES.get(key)
    if prev is not None and getattr(prev, "_induction", False):
        return
    ob.register_evidence_rule(key, _rule(prev))


def register_rules() -> None:
    """Attendance at a session counts for its task key (keeps any other
    rule for that key as the fallback)."""
    try:
        init_db()
        with ob._connect() as conn:
            keys = [r[0] for r in conn.execute(
                "SELECT DISTINCT task_key FROM onboarding_induction_sessions "
                "WHERE task_key IS NOT NULL").fetchall()]
    except Exception:  # noqa: BLE001
        logger.exception("Induction task keys not read")
        return
    for k in keys:
        _register_key(k)
