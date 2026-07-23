"""Timetable data layer for the Sixth Form System.

Each timetable slot pins a class group to a (day, period) cell with an
optional room override. The same group can't be in two cells at once
(UNIQUE constraint), and the data layer also enforces a hard room
clash (same room, same day, same period). Student and teacher clashes
are reported as **warnings** alongside the create/update result so the
caller can surface them without blocking — staff sometimes need to
record a known clash temporarily.

The view-side weekly grid is built by `weekly_grid(...)`, which returns
the 5×6 matrix keyed by (day, period).
"""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Any
from education_system.post_16.sixthform_system.core import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.TIMETABLE_DB

DAYS: tuple[str, ...] = ("Mon", "Tue", "Wed", "Thu", "Fri")
DAY_NUMBERS: tuple[int, ...] = (1, 2, 3, 4, 5)
PERIODS: tuple[int, ...] = (1, 2, 3, 4, 5, 6)

# Suggested default times for each period (UK sixth-form layout).
# Used to pre-fill the form; staff can still override per slot.
DEFAULT_PERIOD_TIMES: dict[int, tuple[str, str]] = {
    1: ("09:00", "09:55"),
    2: ("09:55", "10:50"),
    3: ("11:10", "12:05"),  # break 10:50-11:10
    4: ("12:05", "13:00"),
    5: ("14:00", "14:55"),  # lunch 13:00-14:00
    6: ("14:55", "15:50"),
}

_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):[0-5]\d$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS timetable_slots (
    slot_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id   INTEGER NOT NULL,
    day        INTEGER NOT NULL,
    period     INTEGER NOT NULL,
    start_time TEXT,
    end_time   TEXT,
    room       TEXT,
    notes      TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(group_id, day, period),
    FOREIGN KEY (group_id) REFERENCES class_groups(group_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_tt_group  ON timetable_slots(group_id);
CREATE INDEX IF NOT EXISTS idx_tt_period ON timetable_slots(day, period);
CREATE INDEX IF NOT EXISTS idx_tt_room   ON timetable_slots(room);
"""


@dataclass
class TimetableSlot:
    slot_id: int
    group_id: int
    day: int
    period: int
    start_time: str | None
    end_time: str | None
    room: str | None
    notes: str | None
    created_at: str


@dataclass
class SaveResult:
    """What ``create_slot`` / ``update_slot`` returns: the saved row plus
    any non-blocking clash warnings the caller may want to display."""
    slot: TimetableSlot
    student_clashes: list[str] = field(default_factory=list)
    teacher_clashes: list[str] = field(default_factory=list)


# ── DB plumbing ──────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    # FK references class_groups, so make sure that's there too.
    from education_system.post_16.sixthform_system.modules.domain.academics.class_groups import class_groups as _cg
    _cg.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Timetable schema ready at %s", DB_PATH)

    _DB_READY = True


def _row(r: sqlite3.Row) -> TimetableSlot:
    return TimetableSlot(
        slot_id=r["slot_id"],
        group_id=r["group_id"],
        day=r["day"],
        period=r["period"],
        start_time=r["start_time"],
        end_time=r["end_time"],
        room=r["room"],
        notes=r["notes"],
        created_at=r["created_at"],
    )


# ── Display helpers ────────────────────────────────────────────────

def day_name(day: int) -> str:
    if 1 <= day <= len(DAYS):
        return DAYS[day - 1]
    return f"Day {day}"


def day_number(name: str) -> int | None:
    """Inverse of `day_name`: parses 'Mon'/'Monday' (case-insensitive)."""
    n = name.strip().lower()[:3]
    for i, d in enumerate(DAYS, 1):
        if d.lower() == n:
            return i
    return None


# ── Validation ─────────────────────────────────────────────────────

class ValidationError(ValueError):
    """Raised for any invalid slot input."""


def _require(value, label: str):
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        raise ValidationError(f"{label} is required")
    return value


def _validate_payload(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}

    gid_raw = _require(data.get("group_id"), "Class group")
    try:
        gid = int(gid_raw)
    except (TypeError, ValueError):
        raise ValidationError("Class group must be selected") from None
    from education_system.post_16.sixthform_system.modules.domain.academics.class_groups import (
        class_groups as _cg,
    )
    if _cg.get_group(gid) is None:
        raise ValidationError(f"No class group with id {gid}")
    out["group_id"] = gid

    day_raw = _require(data.get("day"), "Day")
    try:
        day = int(day_raw)
    except (TypeError, ValueError):
        # Accept 'Mon' / 'Tuesday' as well
        day = day_number(str(day_raw)) or 0
    if day not in DAY_NUMBERS:
        raise ValidationError(
            f"Day must be one of: {', '.join(DAYS)} (1..{len(DAYS)})")
    out["day"] = day

    per_raw = _require(data.get("period"), "Period")
    try:
        per = int(per_raw)
    except (TypeError, ValueError):
        raise ValidationError("Period must be a whole number") from None
    if per not in PERIODS:
        raise ValidationError(f"Period must be one of {list(PERIODS)}")
    out["period"] = per

    st = (data.get("start_time") or "").strip()
    et = (data.get("end_time")   or "").strip()
    if not st and not et:
        # Default from the standard schedule
        st, et = DEFAULT_PERIOD_TIMES.get(per, ("", ""))
    if st and not _TIME_RE.match(st):
        raise ValidationError("Start time must be HH:MM")
    if et and not _TIME_RE.match(et):
        raise ValidationError("End time must be HH:MM")
    if st and et and st >= et:
        raise ValidationError("Start time must be before end time")
    out["start_time"] = st or None
    out["end_time"]   = et or None

    out["room"]  = (data.get("room")  or "").strip() or None
    out["notes"] = (data.get("notes") or "").strip() or None
    return out


# ── Clash detection ────────────────────────────────────────────────

def _room_clash(
    conn: sqlite3.Connection, day: int, period: int, room: str | None,
    *, excluding_slot_id: int | None = None,
) -> TimetableSlot | None:
    """Return the slot already using this room at this period, if any."""
    if room is None:
        return None
    sql = ("SELECT * FROM timetable_slots "
           "WHERE day = ? AND period = ? AND room IS NOT NULL "
           "AND LOWER(room) = LOWER(?)")
    args: list[Any] = [day, period, room]
    if excluding_slot_id is not None:
        sql += " AND slot_id != ?"
        args.append(excluding_slot_id)
    row = conn.execute(sql, args).fetchone()
    return _row(row) if row else None


def _student_clashes(
    conn: sqlite3.Connection,
    group_id: int, day: int, period: int,
    *, excluding_slot_id: int | None = None,
) -> list[str]:
    """Student IDs already in another group at (day, period)."""
    sql = """
        SELECT DISTINCT s1.student_id
        FROM class_group_students s1
        JOIN class_group_students s2 ON s1.student_id = s2.student_id
                                    AND s2.group_id != s1.group_id
        JOIN timetable_slots t       ON t.group_id = s2.group_id
                                    AND t.day = ? AND t.period = ?
        WHERE s1.group_id = ?
    """
    args: list[Any] = [day, period, group_id]
    if excluding_slot_id is not None:
        sql += " AND t.slot_id != ?"
        args.append(excluding_slot_id)
    return [r["student_id"] for r in conn.execute(sql, args).fetchall()]


def _teacher_clashes(
    conn: sqlite3.Connection,
    group_id: int, day: int, period: int,
    *, excluding_slot_id: int | None = None,
) -> list[str]:
    """Teacher names already teaching another group at (day, period).

    Resolves the effective teacher (group override → course default).
    """
    from education_system.post_16.sixthform_system.modules.domain.academics.class_groups import class_groups as _cg
    from education_system.post_16.sixthform_system.modules.domain.academics.courses import courses as _crs

    target = _cg.get_group(group_id)
    if target is None:
        return []
    course = _crs.get_course(target.course_id)
    teacher = (target.teacher or
               (course.teacher if course else None))
    if not teacher:
        return []
    teacher_lc = teacher.strip().lower()

    sql = """
        SELECT cg.teacher AS gt, c.teacher AS ct
        FROM timetable_slots t
        JOIN class_groups cg ON cg.group_id = t.group_id
        JOIN courses      c  ON c.course_id = cg.course_id
        WHERE t.day = ? AND t.period = ? AND t.group_id != ?
    """
    args: list[Any] = [day, period, group_id]
    if excluding_slot_id is not None:
        sql += " AND t.slot_id != ?"
        args.append(excluding_slot_id)
    clashes: list[str] = []
    for r in conn.execute(sql, args).fetchall():
        other = (r["gt"] or r["ct"] or "").strip()
        if other and other.lower() == teacher_lc:
            clashes.append(teacher)
    return clashes


# ── CRUD ───────────────────────────────────────────────────────────

def _persist_with_clash_check(
    payload: dict[str, Any],
    *,
    update_slot_id: int | None,
) -> SaveResult:
    with _connect() as conn:
        # Hard reject: another slot already in this room at the same period.
        rc = _room_clash(
            conn, payload["day"], payload["period"], payload["room"],
            excluding_slot_id=update_slot_id,
        )
        if rc is not None:
            raise ValidationError(
                f"Room '{payload['room']}' is already booked at "
                f"{day_name(payload['day'])} P{payload['period']} "
                f"(slot #{rc.slot_id}, group #{rc.group_id})"
            )

        # Compute soft clashes BEFORE writing, so we can include them
        # in the result without showing the new row as its own clash.
        students = _student_clashes(
            conn, payload["group_id"], payload["day"], payload["period"],
            excluding_slot_id=update_slot_id,
        )
        teachers = _teacher_clashes(
            conn, payload["group_id"], payload["day"], payload["period"],
            excluding_slot_id=update_slot_id,
        )

        try:
            if update_slot_id is None:
                cur = conn.execute(
                    """INSERT INTO timetable_slots
                       (group_id, day, period, start_time, end_time, room, notes)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (payload["group_id"], payload["day"], payload["period"],
                     payload["start_time"], payload["end_time"],
                     payload["room"], payload["notes"]),
                )
                slot_id = cur.lastrowid
            else:
                conn.execute(
                    """UPDATE timetable_slots SET
                           group_id = ?, day = ?, period = ?,
                           start_time = ?, end_time = ?, room = ?, notes = ?
                       WHERE slot_id = ?""",
                    (payload["group_id"], payload["day"], payload["period"],
                     payload["start_time"], payload["end_time"],
                     payload["room"], payload["notes"], update_slot_id),
                )
                slot_id = update_slot_id
            conn.commit()
        except sqlite3.IntegrityError as e:
            if "UNIQUE" in str(e):
                raise ValidationError(
                    "This class group already has a slot at "
                    f"{day_name(payload['day'])} P{payload['period']}"
                ) from e
            logger.exception("timetable persist DB error")
            raise ValidationError(f"Database error: {e}") from e

    saved = get_slot(slot_id)
    assert saved is not None
    return SaveResult(slot=saved, student_clashes=students,
                      teacher_clashes=teachers)


def create_slot(data: dict[str, Any]) -> SaveResult:
    init_db()
    try:
        payload = _validate_payload(data)
    except ValidationError as e:
        logger.warning("create_slot validation failed: %s", e)
        raise
    result = _persist_with_clash_check(payload, update_slot_id=None)
    logger.info(
        "Created timetable slot #%d (group #%d, %s P%d, room=%s, "
        "student_clashes=%d, teacher_clashes=%d)",
        result.slot.slot_id, result.slot.group_id,
        day_name(result.slot.day), result.slot.period,
        result.slot.room or "—",
        len(result.student_clashes), len(result.teacher_clashes),
    )
    return result


def update_slot(slot_id: int, data: dict[str, Any]) -> SaveResult:
    init_db()
    if get_slot(slot_id) is None:
        logger.warning("update_slot: unknown id %d", slot_id)
        raise ValidationError(f"No slot with id {slot_id}")
    try:
        payload = _validate_payload(data)
    except ValidationError as e:
        logger.warning("update_slot(%d) validation failed: %s", slot_id, e)
        raise
    result = _persist_with_clash_check(payload, update_slot_id=slot_id)
    logger.info(
        "Updated timetable slot #%d (group #%d, %s P%d)",
        slot_id, result.slot.group_id,
        day_name(result.slot.day), result.slot.period,
    )
    return result


def get_slot(slot_id: int) -> TimetableSlot | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM timetable_slots WHERE slot_id = ?", (slot_id,)
        ).fetchone()
        return _row(r) if r else None


def list_slots(
    *,
    group_id: int | None = None,
    day: int | None = None,
    period: int | None = None,
    room: str | None = None,
    teacher: str | None = None,
    student_id: str | None = None,
) -> list[TimetableSlot]:
    """List slots. The teacher / student_id filters resolve to a set of
    group_ids first, so they compose with the other filters."""
    init_db()

    extra_group_ids: set[int] | None = None
    if teacher:
        teacher_lc = teacher.strip().lower()
        with _connect() as conn:
            rows = conn.execute(
                """SELECT cg.group_id
                   FROM class_groups cg
                   LEFT JOIN courses c ON c.course_id = cg.course_id
                   WHERE LOWER(COALESCE(NULLIF(cg.teacher,''), c.teacher,'')) = ?""",
                (teacher_lc,),
            ).fetchall()
        extra_group_ids = {r["group_id"] for r in rows}

    if student_id:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT group_id FROM class_group_students WHERE student_id = ?",
                (student_id,),
            ).fetchall()
        their_groups = {r["group_id"] for r in rows}
        extra_group_ids = (their_groups
                           if extra_group_ids is None
                           else extra_group_ids & their_groups)

    clauses: list[str] = []
    args: list[Any] = []
    if group_id is not None:
        clauses.append("group_id = ?")
        args.append(group_id)
    if day is not None:
        clauses.append("day = ?")
        args.append(day)
    if period is not None:
        clauses.append("period = ?")
        args.append(period)
    if room:
        clauses.append("LOWER(room) = LOWER(?)")
        args.append(room.strip())
    if extra_group_ids is not None:
        if not extra_group_ids:
            return []
        placeholders = ",".join("?" * len(extra_group_ids))
        clauses.append(f"group_id IN ({placeholders})")
        args.extend(sorted(extra_group_ids))

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM timetable_slots {where} "
           "ORDER BY day, period, group_id")
    with _connect() as conn:
        return [_row(r) for r in conn.execute(sql, args).fetchall()]


def delete_slot(slot_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM timetable_slots WHERE slot_id = ?", (slot_id,)
        )
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted timetable slot #%d", slot_id)
            return True
        logger.warning("delete_slot: unknown id %d", slot_id)
        return False


# ── Weekly grid view ───────────────────────────────────────────────

def weekly_grid(
    *,
    group_id: int | None = None,
    student_id: str | None = None,
    teacher: str | None = None,
    room: str | None = None,
) -> dict[tuple[int, int], list[TimetableSlot]]:
    """Return the timetable as a `{(day, period): [slots]}` map.

    A list (not a single slot) so the renderer can show clashes for
    "All groups" / room overlaps cleanly.
    """
    slots = list_slots(group_id=group_id, student_id=student_id,
                       teacher=teacher, room=room)
    grid: dict[tuple[int, int], list[TimetableSlot]] = {}
    for s in slots:
        grid.setdefault((s.day, s.period), []).append(s)
    return grid
