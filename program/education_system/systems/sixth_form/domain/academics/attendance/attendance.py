"""Attendance data layer for the Sixth Form System.

One row per ``(slot, student, date)`` triple, recording whether the
student was Present / Late / Absent / Authorised. Built so that staff
can "take the register" for a class group: load the roster, mark
each student, save once.

The headline operations are:

* ``register_view(slot_id, date)`` — returns the roster joined to any
  existing records, so the GUI/CLI can render a fillable register.
* ``save_register(slot_id, date, records)`` — upserts every entry in
  one transaction; missing entries leave existing rows untouched.
* ``summary_for_student`` / ``summary_for_group`` — present-rate stats.

Cascades: deleting a slot or a student wipes their attendance rows.

The register *lifecycle* — draft/submitted state, undo snapshots, bulk
marking, arrival/departure stamps — lives next door in
:mod:`attendance_register`. This module stays the plain data layer, but
every write here routes through that module first so a submitted
register cannot be edited by the back door and every save is undoable.

The row carries more than a status. Alongside it sit the *statutory
mark code* and its absence reason (:mod:`attendance_codes`), who
authorised the absence and where an off-site learner actually was
(:mod:`attendance_authorisation`), the amendment trail and the void
flag (:mod:`attendance_audit`), and which AM/PM session the mark falls
in (:mod:`attendance_sessions`). Those modules own the vocabularies and
the operations; this one owns the columns, so a database opened by any
one of them has the full shape.

**Voided rows still exist.** ``UNIQUE(slot_id, student_id, date)`` means
a voided mark keeps its place, so every read here filters ``voided = 0``
by default and re-marking the same student clears the void rather than
colliding with it.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass
from typing import Any
from education_system import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_ATTENDANCE_DB

STATUSES: tuple[str, ...] = (
    "Present", "Late", "Absent", "Authorised",
)
DEFAULT_STATUS: str = "Present"
ATTENDING_STATUSES: tuple[str, ...] = ("Present", "Late")

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS attendance_records (
    record_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    slot_id      INTEGER NOT NULL,
    student_id   TEXT NOT NULL,
    date         TEXT NOT NULL,
    status       TEXT NOT NULL,
    minutes_late INTEGER,
    notes        TEXT,
    arrival_time   TEXT,
    departure_time TEXT,
    code         TEXT,
    reason_id    INTEGER,
    session      TEXT,
    authorised_by      TEXT,
    authorised_at      TEXT,
    authorisation_note TEXT,
    is_offsite       INTEGER NOT NULL DEFAULT 0,
    offsite_location TEXT,
    data_source  TEXT NOT NULL DEFAULT 'manual',
    voided       INTEGER NOT NULL DEFAULT 0,
    voided_by    TEXT,
    voided_at    TEXT,
    void_reason  TEXT,
    recorded_at  TEXT DEFAULT (datetime('now')),
    UNIQUE(slot_id, student_id, date),
    FOREIGN KEY (slot_id)    REFERENCES timetable_slots(slot_id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES students(student_id)     ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_att_slot    ON attendance_records(slot_id);
CREATE INDEX IF NOT EXISTS idx_att_student ON attendance_records(student_id);
CREATE INDEX IF NOT EXISTS idx_att_date    ON attendance_records(date);
"""

# Indexes over columns added after the table shipped. These cannot live
# in ``_SCHEMA``: on a legacy database ``CREATE TABLE IF NOT EXISTS`` is
# a no-op, so the index would be built before the ALTER that adds its
# column and the whole script would fail.
_LATE_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_att_code   ON attendance_records(code);
CREATE INDEX IF NOT EXISTS idx_att_voided ON attendance_records(voided);
"""


@dataclass
class AttendanceRecord:
    record_id: int
    slot_id: int
    student_id: str
    date: str
    status: str
    minutes_late: int | None
    notes: str | None
    recorded_at: str
    # Clock stamps for the lesson itself. `arrival_time` is what the
    # late minutes were derived from; `departure_time` marks an early
    # leave — the student is still Present/Late, they just went home.
    arrival_time: str | None = None
    departure_time: str | None = None
    # Statutory mark code and the reason behind it. `status` is the
    # coarse four-way bucket the rest of the system already reads;
    # `code` is the precise thing a census return needs.
    code: str | None = None
    reason_id: int | None = None
    # 'AM' / 'PM' for a statutory session mark, 'Lesson' for a period
    # register. Derived from the slot's start time when not given.
    session: str | None = None
    # Who turned this absence into an authorised one, and when.
    authorised_by: str | None = None
    authorised_at: str | None = None
    authorisation_note: str | None = None
    # The learner was elsewhere but still being taught — work placement,
    # partner college, field trip.
    is_offsite: bool = False
    offsite_location: str | None = None
    # Where the mark came from: manual, kiosk, qr, import, sync…
    data_source: str = "manual"
    # Soft delete. A voided row is kept for audit but counts for nothing.
    voided: bool = False
    voided_by: str | None = None
    voided_at: str | None = None
    void_reason: str | None = None

    @property
    def is_authorised(self) -> bool:
        """Whether somebody signed this absence off (not merely coded)."""
        return bool(self.authorised_by)


@dataclass
class RegisterEntry:
    """One row in a fillable register: a student + any existing record."""
    student_id: str
    full_name: str
    record: AttendanceRecord | None


# ── DB plumbing ──────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_sixth_form_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    # FKs target slots + students, so make sure those schemas exist too.
    from education_system.systems.sixth_form.domain.academics.timetable import timetable as _tt
    _tt.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        _ensure_columns(conn)
    logger.debug("Attendance schema ready at %s", DB_PATH)

    _DB_READY = True


# Columns added after the original table shipped, as (name, DDL type).
# ``ALTER TABLE ADD COLUMN`` needs a literal default for a NOT NULL
# column, which is why the flags carry one.
_ADDED_COLUMNS: tuple[tuple[str, str], ...] = (
    ("arrival_time",       "TEXT"),
    ("departure_time",     "TEXT"),
    ("code",               "TEXT"),
    ("reason_id",          "INTEGER"),
    ("session",            "TEXT"),
    ("authorised_by",      "TEXT"),
    ("authorised_at",      "TEXT"),
    ("authorisation_note", "TEXT"),
    ("is_offsite",         "INTEGER NOT NULL DEFAULT 0"),
    ("offsite_location",   "TEXT"),
    ("data_source",        "TEXT NOT NULL DEFAULT 'manual'"),
    ("voided",             "INTEGER NOT NULL DEFAULT 0"),
    ("voided_by",          "TEXT"),
    ("voided_at",          "TEXT"),
    ("void_reason",        "TEXT"),
)


def _ensure_columns(conn: sqlite3.Connection) -> None:
    """Add columns introduced after the original table shipped.

    ``CREATE TABLE IF NOT EXISTS`` is a no-op on an existing database,
    so a live ``sixthform.db`` would never grow the clock-stamp columns
    (or the code / authorisation / void columns that came later)
    without this.
    """
    have = {r["name"] for r in
            conn.execute("PRAGMA table_info(attendance_records)").fetchall()}
    for column, ddl in _ADDED_COLUMNS:
        if column not in have:
            conn.execute(
                f"ALTER TABLE attendance_records ADD COLUMN {column} {ddl}")
            logger.info("Added attendance_records.%s", column)
    # Safe only now that every column above exists.
    conn.executescript(_LATE_INDEXES)


def _row(r: sqlite3.Row) -> AttendanceRecord:
    keys = r.keys()

    def col(name: str, default=None):
        """Tolerate a projection (or a legacy DB) that lacks the column."""
        return r[name] if name in keys else default

    return AttendanceRecord(
        record_id=r["record_id"],
        slot_id=r["slot_id"],
        student_id=r["student_id"],
        date=r["date"],
        status=r["status"],
        minutes_late=r["minutes_late"],
        notes=r["notes"],
        recorded_at=r["recorded_at"],
        arrival_time=col("arrival_time"),
        departure_time=col("departure_time"),
        code=col("code"),
        reason_id=col("reason_id"),
        session=col("session"),
        authorised_by=col("authorised_by"),
        authorised_at=col("authorised_at"),
        authorisation_note=col("authorisation_note"),
        is_offsite=bool(col("is_offsite", 0)),
        offsite_location=col("offsite_location"),
        data_source=col("data_source", "manual") or "manual",
        voided=bool(col("voided", 0)),
        voided_by=col("voided_by"),
        voided_at=col("voided_at"),
        void_reason=col("void_reason"),
    )


# ── Validation ──────────────────────────────────────────────────────

class ValidationError(ValueError):
    """Raised for invalid attendance input."""


def _validate_date(d: str) -> str:
    d = (d or "").strip()
    if not d:
        raise ValidationError("Date is required")
    if not _DATE_RE.match(d):
        raise ValidationError("Date must be YYYY-MM-DD")
    return d


def _validate_status(s: str) -> str:
    s = (s or "").strip()
    if s not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    return s


def _validate_minutes(value, status: str) -> int | None:
    if value in (None, ""):
        return None
    try:
        m = int(value)
    except (TypeError, ValueError):
        raise ValidationError("Minutes late must be a whole number") from None
    if m < 0 or m > 1000:
        raise ValidationError("Minutes late must be between 0 and 1000")
    if m and status != "Late":
        # Non-blocking detail: allow but warn via log.
        logger.debug("minutes_late=%d set with status=%s", m, status)
    return m


# ── Roster + register view ─────────────────────────────────────────

def _resolve_group_for_slot(slot_id: int) -> int | None:
    from education_system.systems.sixth_form.domain.academics.timetable import timetable as _tt
    slot = _tt.get_slot(slot_id)
    return slot.group_id if slot else None


def register_view(slot_id: int, date: str) -> list[RegisterEntry]:
    """Return one `RegisterEntry` per student in the slot's class group,
    joined to any existing record for ``date`` (or `None`)."""
    init_db()
    date = _validate_date(date)
    group_id = _resolve_group_for_slot(slot_id)
    if group_id is None:
        raise ValidationError(f"No slot with id {slot_id}")
    from education_system.systems.sixth_form.domain.academics.class_groups import (
        class_groups as _cg,
    )
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    members = _cg.list_members(group_id)
    student_index = {s.student_id: s for s in _students.list_students()
                     if s.student_id in members}

    with _connect() as conn:
        rows = {
            r["student_id"]: _row(r)
            for r in conn.execute(
                # A voided mark is not a mark: the roster should show
                # the student as unmarked so somebody re-marks them.
                "SELECT * FROM attendance_records "
                "WHERE slot_id = ? AND date = ? AND voided = 0",
                (slot_id, date),
            ).fetchall()
        }

    out: list[RegisterEntry] = []
    for sid in members:
        student = student_index.get(sid)
        out.append(RegisterEntry(
            student_id=sid,
            full_name=student.full_name if student else "(unknown)",
            record=rows.get(sid),
        ))
    return out


def _lifecycle():
    """The register-lifecycle sibling, imported late to dodge a cycle."""
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance_register as _reg,
    )
    return _reg


def _codes():
    """The mark-code vocabulary sibling. Late-imported: it depends on
    this module, so a top-level import would close the loop."""
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance_codes as _codes_mod,
    )
    return _codes_mod


def _audit():
    """The amendment-trail sibling, late-imported for the same reason."""
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance_audit as _audit_mod,
    )
    return _audit_mod


def _sessions():
    """The AM/PM session sibling, late-imported for the same reason."""
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance_sessions as _sessions_mod,
    )
    return _sessions_mod


def _window():
    """The retro-marking policy sibling, late-imported for the same reason."""
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance_window as _window_mod,
    )
    return _window_mod


# ── Mark resolution ────────────────────────────────────────────────

def resolve_marks(
    payload: dict[str, Any],
    *,
    slot_id: int | None = None,
    fallback_status: str | None = None,
    fallback_code: str | None = None,
) -> tuple[str, str, str | None]:
    """Reconcile ``status`` and ``code`` into a consistent pair.

    Callers may give either, both, or neither:

    * **code only** — the status is derived from the code, so a `V`
      (educational visit) lands as Present without the caller thinking
      about it.
    * **status only** — the representative code for that status is
      filled in, so no row is left uncoded.
    * **both** — taken as given. They are allowed to disagree: a college
      may want `L` recorded against Present during a grace period, and
      refusing that would be more annoying than useful. The mismatch is
      logged.

    Returns ``(status, code, session)``. ``session`` is the AM/PM/Lesson
    bucket, derived from the slot's start time when not supplied.
    """
    codes = _codes()
    raw_code = payload.get("code")
    raw_status = payload.get("status")

    code = (raw_code or "").strip() if isinstance(raw_code, str) else raw_code
    status = ((raw_status or "").strip()
              if isinstance(raw_status, str) else raw_status)

    if not code and not status:
        code, status = fallback_code, fallback_status
    if not code and not status:
        # Nothing given and nothing to fall back on. Say so plainly
        # rather than letting the code validator complain about a
        # missing code the caller never mentioned.
        raise ValidationError("A mark needs either a status or a code")
    if code and not status:
        code = codes.validate_code(code)
        status = codes.status_for_code(code)
    elif status and not code:
        status = _validate_status(status)
        code = codes.default_code_for_status(status)
    else:
        code = codes.validate_code(code)
        status = _validate_status(status)
        if codes.status_for_code(code) != status:
            logger.debug("Mark code %s does not imply status %s", code, status)

    session = payload.get("session")
    if isinstance(session, str) and session.strip():
        session = _sessions().validate_session(session)
    elif slot_id is not None:
        session = _sessions().session_for_slot(slot_id)
    else:
        session = None
    return status, code, session


def _validate_flags(payload: dict[str, Any], code: str | None) -> dict[str, Any]:
    """Validate the optional non-mark fields a save may carry."""
    codes = _codes()
    out: dict[str, Any] = {}

    reason_id = payload.get("reason_id")
    out["reason_id"] = (codes.validate_reason_id(reason_id)
                        if reason_id not in (None, "") else None)

    source = payload.get("data_source")
    out["data_source"] = codes.validate_source(
        source or codes.DEFAULT_DATA_SOURCE)

    offsite = payload.get("is_offsite")
    location = payload.get("offsite_location")
    location = ((location or "").strip() or None
                if isinstance(location, str) else None)
    if offsite is None:
        # An off-site location is itself the claim that the learner was
        # off site, and so is an approved-activity code — don't make
        # callers say it twice.
        offsite = bool(location) or codes.implies_offsite(code)
    out["is_offsite"] = 1 if offsite else 0
    if not out["is_offsite"]:
        location = None
    out["offsite_location"] = location
    return out


def save_register(
    slot_id: int,
    date: str,
    entries: dict[str, dict[str, Any]],
    *,
    actor: str | None = None,
    reason: str | None = None,
    allow_retro: bool = False,
) -> int:
    """Upsert attendance records for a slot/date in one transaction.

    ``entries`` maps ``student_id`` → a payload. ``status`` and ``code``
    are interchangeable (see :func:`resolve_marks`); ``minutes_late``,
    ``notes``, ``reason_id``, ``data_source``, ``is_offsite``,
    ``offsite_location`` and ``session`` are all optional. Missing
    students are left untouched (use ``delete_record`` to remove a row
    explicitly). Returns the number of rows written.

    Refuses to write once the register has been submitted, and takes an
    undo snapshot of the prior state before touching anything.

    An old register is not an editable one. Past the window in
    :mod:`attendance_window` a save needs a ``reason``, and past the
    cutoff it is refused entirely — ``allow_retro`` is the deliberate
    override, and it is logged.

    Saving over a **voided** row un-voids it: re-marking a student is the
    clearest possible statement that the mark is live again.

    Once a register has been submitted at least once, every value this
    save actually changes is written to the amendment trail — that is
    what "post-submission change" means in
    :func:`attendance_audit.list_amendments`.
    """
    init_db()
    date = _validate_date(date)
    if _resolve_group_for_slot(slot_id) is None:
        raise ValidationError(f"No slot with id {slot_id}")
    reg = _lifecycle()
    reg.assert_unlocked(slot_id, date)
    decision = _window().assert_open(
        date, reason=reason, actor=actor, slot_id=slot_id,
        allow_retro=allow_retro, source="save_register")

    # Pre-validate all entries before touching the DB, so a single bad
    # row doesn't leave the register half-saved.
    cleaned: list[tuple[str, dict[str, Any]]] = []
    for sid, payload in entries.items():
        try:
            status, code, session = resolve_marks(payload, slot_id=slot_id)
        except ValidationError as e:
            raise ValidationError(f"{sid}: {e}") from None
        row = _validate_flags(payload, code)
        row["status"] = status
        row["code"] = code
        row["session"] = session
        row["minutes_late"] = _validate_minutes(
            payload.get("minutes_late"), status)
        row["notes"] = (payload.get("notes") or "").strip() or None
        cleaned.append((sid, row))

    # An amendment trail is only interesting once somebody has signed
    # the register off; before that, the undo buffer is the record. A
    # save that lands outside the retro-marking window counts too — it
    # is an edit to history whether or not anyone submitted it.
    session_hdr = reg.get_session(slot_id, date)
    submitted = bool(session_hdr and session_hdr.submitted_at)
    track = submitted or not decision.is_open
    before = ({r.student_id: r
               for r in list_records(slot_id=slot_id, date=date,
                                     include_voided=True)}
              if track else {})

    # Snapshot *after* validation so a rejected save leaves no undo step.
    reg.take_snapshot(slot_id, date, taken_by=actor)

    written = 0
    try:
        with _connect() as conn:
            for sid, row in cleaned:
                # UPSERT keyed on the UNIQUE(slot_id, student_id, date) constraint.
                conn.execute(
                    """INSERT INTO attendance_records
                          (slot_id, student_id, date, status, code, session,
                           minutes_late, notes, reason_id, data_source,
                           is_offsite, offsite_location)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(slot_id, student_id, date) DO UPDATE SET
                          status = excluded.status,
                          code = excluded.code,
                          session = excluded.session,
                          minutes_late = excluded.minutes_late,
                          notes = excluded.notes,
                          reason_id = excluded.reason_id,
                          data_source = excluded.data_source,
                          is_offsite = excluded.is_offsite,
                          offsite_location = excluded.offsite_location,
                          voided = 0,
                          voided_by = NULL,
                          voided_at = NULL,
                          void_reason = NULL,
                          recorded_at = datetime('now')""",
                    (slot_id, sid, date, row["status"], row["code"],
                     row["session"], row["minutes_late"], row["notes"],
                     row["reason_id"], row["data_source"],
                     row["is_offsite"], row["offsite_location"]),
                )
                written += 1
            conn.commit()
    except sqlite3.Error as e:
        logger.exception("save_register DB error")
        raise ValidationError(f"Database error: {e}") from e

    if track:
        audit = _audit()
        trail_reason = (reason or "").strip() or (
            "Amended after submission" if submitted else
            f"Retrospective edit, {decision.days_late} day(s) after the date")
        for sid, _row_payload in cleaned:
            after = get_record_for(slot_id, sid, date)
            if after is not None:
                audit.log_changes(before.get(sid), after,
                                  action="edit", actor=actor,
                                  reason=trail_reason)

    logger.info(
        "Saved register: slot #%d, %s, %d row(s)", slot_id, date, written,
    )
    reg.touch_session(slot_id, date)
    return written


# ── CRUD (individual records) ──────────────────────────────────────

def get_record(record_id: int) -> AttendanceRecord | None:
    """Fetch one row by id. Voided rows *are* returned — an explicit id
    lookup is how the audit and restore flows reach them."""
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM attendance_records WHERE record_id = ?",
            (record_id,),
        ).fetchone()
        return _row(r) if r else None


def get_record_for(slot_id: int, student_id: str,
                   date: str) -> AttendanceRecord | None:
    """Fetch the row for one student in one register, voided or not."""
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM attendance_records "
            "WHERE slot_id = ? AND student_id = ? AND date = ?",
            (slot_id, student_id, _validate_date(date)),
        ).fetchone()
        return _row(r) if r else None


def list_records(
    *,
    student_id: str | None = None,
    slot_id: int | None = None,
    group_id: int | None = None,
    date: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    status: str | None = None,
    code: str | None = None,
    data_source: str | None = None,
    offsite_only: bool = False,
    include_voided: bool = False,
    voided_only: bool = False,
) -> list[AttendanceRecord]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if voided_only:
        clauses.append("ar.voided = 1")
    elif not include_voided:
        clauses.append("ar.voided = 0")
    if code:
        clauses.append("ar.code = ?")
        args.append(_codes().validate_code(code))
    if data_source:
        clauses.append("ar.data_source = ?")
        args.append(_codes().validate_source(data_source))
    if offsite_only:
        clauses.append("ar.is_offsite = 1")
    if student_id:
        clauses.append("ar.student_id = ?")
        args.append(student_id)
    if slot_id is not None:
        clauses.append("ar.slot_id = ?")
        args.append(slot_id)
    if date:
        clauses.append("ar.date = ?")
        args.append(_validate_date(date))
    if date_from:
        clauses.append("ar.date >= ?")
        args.append(_validate_date(date_from))
    if date_to:
        clauses.append("ar.date <= ?")
        args.append(_validate_date(date_to))
    if status:
        clauses.append("ar.status = ?")
        args.append(_validate_status(status))
    if group_id is not None:
        clauses.append(
            "ar.slot_id IN (SELECT slot_id FROM timetable_slots WHERE group_id = ?)"
        )
        args.append(group_id)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (
        f"SELECT ar.* FROM attendance_records ar "
        f"{where} ORDER BY ar.date DESC, ar.slot_id, ar.student_id"
    )
    with _connect() as conn:
        return [_row(r) for r in conn.execute(sql, args).fetchall()]


def update_record(
    record_id: int,
    data: dict[str, Any],
    *,
    actor: str | None = None,
    reason: str | None = None,
    audit: bool = True,
    allow_retro: bool = False,
) -> AttendanceRecord:
    """Update one attendance row.

    Accepts ``status`` / ``code`` (reconciled by :func:`resolve_marks`),
    ``minutes_late``, ``notes``, ``reason_id``, ``session``,
    ``data_source``, ``is_offsite`` and ``offsite_location``. Anything
    absent keeps its current value.

    A targeted edit of a single row is always worth an audit entry, so
    every changed field is written to the amendment trail unless the
    caller passes ``audit=False`` — which the audit module itself does,
    to avoid logging its own writes twice.

    Subject to the retro-marking window: outside it the ``reason`` stops
    being optional. ``allow_retro`` is how the curated amendment paths
    (authorising, recoding, voiding) reach a record of any age — they
    each write their own trail entry, which is what earns them the pass.
    """
    init_db()
    existing = get_record(record_id)
    if existing is None:
        logger.warning("update_record: unknown id %d", record_id)
        raise ValidationError(f"No record with id {record_id}")
    _lifecycle().assert_unlocked(existing.slot_id, existing.date)
    _window().assert_open(existing.date, reason=reason, actor=actor,
                          slot_id=existing.slot_id, allow_retro=allow_retro,
                          source="update_record")

    status, code, session = resolve_marks(
        data, slot_id=existing.slot_id,
        fallback_status=existing.status, fallback_code=existing.code)
    if "session" not in data:
        session = existing.session or session
    minutes = _validate_minutes(
        data.get("minutes_late", existing.minutes_late), status)
    notes = (data.get("notes") if "notes" in data else existing.notes)
    notes = (notes or "").strip() or None if isinstance(notes, str) else notes

    # Fall back to what is already stored rather than to the defaults,
    # so a partial update cannot silently reset a learner's placement.
    flags = _validate_flags({
        "reason_id": data.get("reason_id", existing.reason_id),
        "data_source": data.get("data_source", existing.data_source),
        "is_offsite": data.get("is_offsite", existing.is_offsite),
        "offsite_location": data.get("offsite_location",
                                     existing.offsite_location),
    }, code)

    with _connect() as conn:
        conn.execute(
            """UPDATE attendance_records
               SET status = ?, code = ?, session = ?, minutes_late = ?,
                   notes = ?, reason_id = ?, data_source = ?,
                   is_offsite = ?, offsite_location = ?,
                   recorded_at = datetime('now')
               WHERE record_id = ?""",
            (status, code, session, minutes, notes, flags["reason_id"],
             flags["data_source"], flags["is_offsite"],
             flags["offsite_location"], record_id),
        )
        conn.commit()
    logger.info(
        "Updated attendance record #%d (student=%s, status=%s, code=%s)",
        record_id, existing.student_id, status, code,
    )
    out = get_record(record_id)
    assert out is not None
    if audit:
        _audit().log_changes(existing, out, action="edit",
                             actor=actor, reason=reason)
    return out


def delete_record(record_id: int) -> bool:
    """Hard-delete one row.

    Prefer :func:`attendance_audit.void_record` for anything that was
    ever a real mark — a deleted row leaves no trace, and registers are
    retained evidence. This stays for genuine mistakes (a mark against
    the wrong student, entered seconds ago).
    """
    init_db()
    existing = get_record(record_id)
    if existing is not None:
        _lifecycle().assert_unlocked(existing.slot_id, existing.date)
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM attendance_records WHERE record_id = ?",
            (record_id,),
        )
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted attendance record #%d", record_id)
            return True
        logger.warning("delete_record: unknown id %d", record_id)
        return False


# ── Summaries ──────────────────────────────────────────────────────

@dataclass
class AttendanceSummary:
    total:      int
    present:    int
    late:       int
    absent:     int
    authorised: int

    @property
    def attending(self) -> int:
        """Counted as attending: Present + Late."""
        return self.present + self.late

    @property
    def percentage(self) -> float | None:
        if self.total == 0:
            return None
        return round(100.0 * self.attending / self.total, 1)


def _summarize(rows: list[sqlite3.Row]) -> AttendanceSummary:
    counts = {s: 0 for s in STATUSES}
    for r in rows:
        counts[r["status"]] = r["n"]
    return AttendanceSummary(
        total=sum(counts.values()),
        present=counts["Present"],
        late=counts["Late"],
        absent=counts["Absent"],
        authorised=counts["Authorised"],
    )


def summary_for_student(
    student_id: str,
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    slot_id: int | None = None,
) -> AttendanceSummary:
    init_db()
    clauses = ["voided = 0", "student_id = ?"]
    args: list[Any] = [student_id]
    if slot_id is not None:
        clauses.append("slot_id = ?")
        args.append(slot_id)
    if date_from:
        clauses.append("date >= ?")
        args.append(_validate_date(date_from))
    if date_to:
        clauses.append("date <= ?")
        args.append(_validate_date(date_to))
    sql = (
        "SELECT status, COUNT(*) AS n FROM attendance_records "
        f"WHERE {' AND '.join(clauses)} GROUP BY status"
    )
    with _connect() as conn:
        return _summarize(conn.execute(sql, args).fetchall())


def summary_for_group(
    group_id: int,
    *,
    date_from: str | None = None,
    date_to: str | None = None,
) -> AttendanceSummary:
    init_db()
    clauses = [
        "voided = 0",
        "slot_id IN (SELECT slot_id FROM timetable_slots WHERE group_id = ?)",
    ]
    args: list[Any] = [group_id]
    if date_from:
        clauses.append("date >= ?")
        args.append(_validate_date(date_from))
    if date_to:
        clauses.append("date <= ?")
        args.append(_validate_date(date_to))
    sql = (
        "SELECT status, COUNT(*) AS n FROM attendance_records "
        f"WHERE {' AND '.join(clauses)} GROUP BY status"
    )
    with _connect() as conn:
        return _summarize(conn.execute(sql, args).fetchall())


def per_student_summary_for_group(
    group_id: int,
    *,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, AttendanceSummary]:
    """One AttendanceSummary per student in the group (over the date range)."""
    init_db()
    from education_system.systems.sixth_form.domain.academics.class_groups import class_groups as _cg
    members = _cg.list_members(group_id)
    if not members:
        return {}

    placeholders = ",".join("?" * len(members))
    clauses = [
        "voided = 0",
        f"student_id IN ({placeholders})",
        "slot_id IN (SELECT slot_id FROM timetable_slots WHERE group_id = ?)",
    ]
    args: list[Any] = [*members, group_id]
    if date_from:
        clauses.append("date >= ?")
        args.append(_validate_date(date_from))
    if date_to:
        clauses.append("date <= ?")
        args.append(_validate_date(date_to))
    sql = (
        "SELECT student_id, status, COUNT(*) AS n "
        "FROM attendance_records "
        f"WHERE {' AND '.join(clauses)} GROUP BY student_id, status"
    )
    by_student: dict[str, dict[str, int]] = {sid: {s: 0 for s in STATUSES}
                                              for sid in members}
    with _connect() as conn:
        for r in conn.execute(sql, args).fetchall():
            by_student[r["student_id"]][r["status"]] = r["n"]
    out: dict[str, AttendanceSummary] = {}
    for sid, counts in by_student.items():
        out[sid] = AttendanceSummary(
            total=sum(counts.values()),
            present=counts["Present"],
            late=counts["Late"],
            absent=counts["Absent"],
            authorised=counts["Authorised"],
        )
    return out
