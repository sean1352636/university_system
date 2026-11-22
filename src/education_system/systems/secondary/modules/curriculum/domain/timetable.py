"""The school timetable: when each teaching group is taught, where, and by whom.

A lesson puts a teaching group (this year's, open) in a slot - week of the
cycle, day (Mon-Fri) and period. The teacher and room come from the group
unless the lesson names its own (a split class, a lab lesson).

School settings (``timetable_settings`` / ``timetable_periods``):

* The periods of the day with their times (a default five-period day until
  they're set). Times are HH:MM, each period ends after it starts, and
  periods don't overlap.
* A one- or two-week cycle (Week A / Week B). Week A starts again each
  academic year (counting school weeks from the Monday of the week containing
  1 September) or each term - :func:`week_for`.

Rules:

* A group has at most one lesson in a slot, in a period that exists, in a
  week of the cycle.
* Clashes - the same teacher, the same room, or the same pupil in two places
  at once - are refused unless ``allow_clash`` (a sports hall shared by two
  PE groups); :func:`clashes` lists every clash, including ones made later by
  moving pupils between groups.
* :func:`requirements` compares each group's lessons with what the
  curriculum plan (or the group) asks for.
* :func:`lessons_on` gives a real date's lessons, using the academic
  calendar: no lessons on weekends, holidays or closures.

Every change goes in ``timetable_audit`` and the activity log (ids and counts).
"""

from __future__ import annotations

import datetime as _dt
import json
import re
from dataclasses import dataclass
from typing import Any

from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.modules.curriculum.domain import teaching_groups as TG
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import TIMETABLE_EDITORS, Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

DAYS: tuple[str, ...] = ("Mon", "Tue", "Wed", "Thu", "Fri")
DAY_NAMES: tuple[str, ...] = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")
MAX_PERIODS = 10
WEEK_LABELS = {1: "Week A", 2: "Week B"}
DEFAULT_PERIODS: tuple[tuple[int, str, str, str], ...] = (
    (1, "P1", "08:50", "09:50"), (2, "P2", "09:50", "10:50"), (3, "P3", "11:10", "12:10"),
    (4, "P4", "12:10", "13:10"), (5, "P5", "13:55", "14:55"),
)
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS timetable_periods (
    period     INTEGER PRIMARY KEY CHECK (period BETWEEN 1 AND 10),
    label      TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS timetable_settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);
CREATE TABLE IF NOT EXISTS timetable_lessons (
    lesson_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id         INTEGER NOT NULL REFERENCES teaching_groups (group_id) ON DELETE CASCADE,
    week             INTEGER NOT NULL DEFAULT 1 CHECK (week IN (1, 2)),
    day              INTEGER NOT NULL CHECK (day BETWEEN 1 AND 5),
    period           INTEGER NOT NULL CHECK (period BETWEEN 1 AND 10),
    room             TEXT,
    teacher_name     TEXT,
    teacher_username TEXT,
    notes            TEXT,
    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    created_by       TEXT,
    updated_at       TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by       TEXT,
    UNIQUE (group_id, week, day, period)
);
CREATE INDEX IF NOT EXISTS ix_timetable_slot ON timetable_lessons (week, day, period);
CREATE TABLE IF NOT EXISTS timetable_audit (
    audit_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    lesson_id INTEGER,
    action    TEXT NOT NULL CHECK (action IN ('create', 'update', 'delete', 'settings',
                                              'periods', 'copy_week')),
    actor     TEXT NOT NULL,
    detail    TEXT,
    at        TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

database.register_schema("timetable", _SCHEMA)

ValidationError = P.ValidationError
PermissionDenied = P.PermissionDenied
NotFound = P.NotFound


@dataclass(frozen=True)
class Period:
    period: int
    label: str
    start_time: str
    end_time: str

    @property
    def times(self) -> str:
        return f"{self.start_time}–{self.end_time}"


@dataclass(frozen=True)
class Lesson:
    lesson_id: int
    group_id: int
    week: int
    day: int
    period: int
    room_override: str | None
    teacher_name_override: str | None
    teacher_username_override: str | None
    notes: str | None
    # From the group and subject:
    group_code: str
    year_group: int
    subject_id: int
    subject_code: str
    subject_name: str
    group_room: str | None
    group_teacher: str | None
    group_teacher_username: str | None

    @property
    def room(self) -> str | None:
        return self.room_override or self.group_room

    @property
    def teacher(self) -> str | None:
        return self.teacher_name_override or self.group_teacher

    @property
    def teacher_username(self) -> str | None:
        if self.teacher_name_override or self.teacher_username_override:
            return self.teacher_username_override
        return self.group_teacher_username

    @property
    def teacher_key(self) -> str | None:
        """Who teaches it, for clash checks: the login if known, else the name."""
        u, n = self.teacher_username, self.teacher
        return f"u:{u.lower()}" if u else (f"n:{n.lower()}" if n else None)

    @property
    def slot(self) -> tuple[int, int, int]:
        return self.week, self.day, self.period

    @property
    def slot_label(self) -> str:
        return slot_label(self.week, self.day, self.period)

    @property
    def cell(self) -> str:
        """Short text for a timetable grid cell."""
        return " · ".join(x for x in (self.subject_code, self.group_code, self.room,
                                      self.teacher) if x)


# ── Helpers ──────────────────────────────────────────────────────────

def _require(actor: Principal, action: str, target: Any = None) -> None:
    if actor.role not in TIMETABLE_EDITORS:
        activity_log.record(action, target=target, outcome="denied", principal=actor)
        raise PermissionDenied("Your account can view the timetable but not change it.")


def _audit(conn, lesson_id: int | None, action: str, actor: Principal, detail: dict) -> None:
    conn.execute("INSERT INTO timetable_audit (lesson_id, action, actor, detail) "
                 "VALUES (?, ?, ?, ?)",
                 (lesson_id, action, actor.username or "unknown",
                  json.dumps(detail, default=str, sort_keys=True)))


def slot_label(week: int, day: int, period: int) -> str:
    p = next((x for x in periods() if x.period == period), None)
    return ((f"{WEEK_LABELS[week]} " if cycle_weeks() == 2 else "")
            + f"{DAY_NAMES[day - 1]} {p.label if p else f'P{period}'}")


_SELECT = """
SELECT l.lesson_id, l.group_id, l.week, l.day, l.period, l.room AS room_override,
       l.teacher_name AS teacher_name_override,
       l.teacher_username AS teacher_username_override, l.notes,
       g.code AS group_code, g.year_group, g.subject_id, s.code AS subject_code,
       s.name AS subject_name, g.room AS group_room, g.teacher_name AS group_teacher,
       g.teacher_username AS group_teacher_username
FROM timetable_lessons l JOIN teaching_groups g USING (group_id)
JOIN subjects s ON s.subject_id = g.subject_id
"""


def _lesson(r) -> Lesson:
    return Lesson(**{k: r[k] for k in r.keys()})


# ── Settings: periods and cycle ──────────────────────────────────────

def periods() -> list[Period]:
    with database.connect() as conn:
        rows = conn.execute("SELECT * FROM timetable_periods ORDER BY period").fetchall()
    if not rows:
        return [Period(*p) for p in DEFAULT_PERIODS]
    return [Period(r["period"], r["label"], r["start_time"], r["end_time"]) for r in rows]


def set_periods(rows: list[dict[str, Any]], *, actor: Principal) -> list[Period]:
    """Replace the periods of the day. Rows: {label, start_time, end_time}, in order;
    periods are numbered 1, 2, … A period that has lessons can't be removed."""
    _require(actor, "timetable.periods")
    problems: list[str] = []
    clean: list[Period] = []
    for n, r in enumerate(rows, 1):
        label = P._clean_text(r.get("label"), 12) or f"P{n}"
        start = (r.get("start_time") or "").strip()
        end = (r.get("end_time") or "").strip()
        if not _TIME_RE.match(start) or not _TIME_RE.match(end):
            problems.append(f"Period {n}: times must be HH:MM (24-hour)")
            continue
        if end <= start:
            problems.append(f"Period {n}: it must end after it starts")
        if clean and start < clean[-1].end_time:
            problems.append(f"Period {n} starts before period {n - 1} ends")
        clean.append(Period(n, label, start, end))
    if not rows:
        problems.append("The day needs at least one period")
    if len(rows) > MAX_PERIODS:
        problems.append(f"At most {MAX_PERIODS} periods")
    with database.connect() as conn:
        used = conn.execute("SELECT MAX(period) FROM timetable_lessons").fetchone()[0]
    if used and used > len(rows):
        problems.append(f"Period {used} has lessons - move or delete them before removing it")
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        conn.execute("DELETE FROM timetable_periods")
        conn.executemany("INSERT INTO timetable_periods (period, label, start_time, end_time) "
                         "VALUES (?, ?, ?, ?)",
                         [(p.period, p.label, p.start_time, p.end_time) for p in clean])
        _audit(conn, None, "periods", actor, {"periods": len(clean)})
    activity_log.record("timetable.periods", principal=actor, periods=len(clean))
    return periods()


def _setting(key: str, default: str) -> str:
    with database.connect() as conn:
        r = conn.execute("SELECT value FROM timetable_settings WHERE key = ?", (key,)).fetchone()
    return r["value"] if r and r["value"] else default


def cycle_weeks() -> int:
    return 2 if _setting("cycle_weeks", "1") == "2" else 1


def cycle_restart() -> str:
    """"year" (Week A from the start of the year) or "term" (from each term)."""
    return "term" if _setting("cycle_restart", "year") == "term" else "year"


def set_cycle(weeks: Any, restart: str = "year", *, actor: Principal) -> None:
    _require(actor, "timetable.settings")
    problems = []
    try:
        w = int(str(weeks).strip())
    except ValueError:
        w = 0
    if w not in (1, 2):
        problems.append("The timetable cycle is 1 or 2 weeks")
    if restart not in ("year", "term"):
        problems.append("Week A restarts each year or each term")
    if w == 1:
        with database.connect() as conn:
            n = conn.execute("SELECT COUNT(*) FROM timetable_lessons WHERE week = 2"
                             ).fetchone()[0]
        if n:
            problems.append(f"{n} lesson(s) are in Week B - delete them before going to a "
                            "one-week timetable")
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        for k, v in (("cycle_weeks", str(w)), ("cycle_restart", restart)):
            conn.execute("INSERT INTO timetable_settings (key, value) VALUES (?, ?) "
                         "ON CONFLICT (key) DO UPDATE SET value = excluded.value", (k, v))
        _audit(conn, None, "settings", actor, {"cycle_weeks": w, "restart": restart})
    activity_log.record("timetable.settings", principal=actor, cycle_weeks=w, restart=restart)


def week_for(day: _dt.date) -> int:
    """Week of the cycle (1 = A, 2 = B) that *day* falls in."""
    if cycle_weeks() == 1:
        return 1
    if cycle_restart() == "term":
        from education_system.systems.secondary.modules.curriculum.domain import academic_year as AY
        term = AY.term_for(day)
        if term is not None:
            return (AY.week_of_term(day, term) - 1) % 2 + 1
    start = P.academic_year_start(day)
    monday0 = start - _dt.timedelta(days=start.weekday())
    monday = day - _dt.timedelta(days=day.weekday())
    return ((monday - monday0).days // 7) % 2 + 1


# ── Reading ──────────────────────────────────────────────────────────

def _current_where() -> tuple[str, list[Any]]:
    return " WHERE g.academic_year = ? AND g.status = 'active'", [TG.current_year()]


def get(lesson_id: int) -> Lesson:
    with database.connect() as conn:
        r = conn.execute(_SELECT + " WHERE l.lesson_id = ?", (int(lesson_id),)).fetchone()
    if r is None:
        raise NotFound(f"No lesson #{lesson_id}")
    return _lesson(r)


def list_lessons(*, year_group: int | None = None, form: str | None = None,
                 teacher: str | None = None, room: str | None = None,
                 pupil_id: int | None = None, group_id: int | None = None,
                 week: int | None = None, day: int | None = None) -> list[Lesson]:
    """This year's lessons for open groups, by week/day/period. *teacher* matches a
    login or a name; *form* keeps groups with a pupil from that form."""
    where, params = _current_where()
    sql = _SELECT + where
    if year_group is not None:
        sql += " AND g.year_group = ?"
        params.append(int(year_group))
    if group_id is not None:
        sql += " AND l.group_id = ?"
        params.append(int(group_id))
    if week is not None:
        sql += " AND l.week = ?"
        params.append(int(week))
    if day is not None:
        sql += " AND l.day = ?"
        params.append(int(day))
    if pupil_id is not None or form:
        sql += (" AND l.group_id IN (SELECT m.group_id FROM teaching_group_members m JOIN "
                "pupils p USING (pupil_id) WHERE p.roll_status = 'on_roll'")
        if pupil_id is not None:
            sql += " AND p.pupil_id = ?"
            params.append(int(pupil_id))
        if form:
            sql += " AND upper(p.form_group) = upper(?)"
            params.append(form.strip())
        sql += ")"
    sql += " ORDER BY l.week, l.day, l.period, s.name COLLATE NOCASE, g.code COLLATE NOCASE"
    with database.connect() as conn:
        rows = [_lesson(r) for r in conn.execute(sql, params)]
    if teacher:
        t = teacher.strip().lower()
        rows = [x for x in rows if (x.teacher_username or "").lower() == t
                or (x.teacher or "").lower() == t]
    if room:
        rows = [x for x in rows if (x.room or "").lower() == room.strip().lower()]
    return rows


def grid(lessons: list[Lesson]) -> dict[tuple[int, int, int], list[Lesson]]:
    out: dict[tuple[int, int, int], list[Lesson]] = {}
    for x in lessons:
        out.setdefault(x.slot, []).append(x)
    return out


def teachers() -> list[str]:
    """Teacher names (and logins) on this year's groups and lessons - for a filter."""
    names: dict[str, str] = {}
    for x in list_lessons():
        if x.teacher:
            names.setdefault(x.teacher.lower(), x.teacher)
    for g in TG.list_groups():
        if g.teacher_name:
            names.setdefault(g.teacher_name.lower(), g.teacher_name)
    return sorted(names.values(), key=str.lower)


def rooms() -> list[str]:
    names: dict[str, str] = {}
    for x in list_lessons():
        if x.room:
            names.setdefault(x.room.lower(), x.room)
    for g in TG.list_groups():
        if g.room:
            names.setdefault(g.room.lower(), g.room)
    return sorted(names.values(), key=str.lower)


def history(limit: int = 50) -> list[dict[str, Any]]:
    with database.connect() as conn:
        rows = conn.execute("SELECT * FROM timetable_audit ORDER BY audit_id DESC LIMIT ?",
                            (limit,)).fetchall()
    return [{"at": r["at"], "actor": r["actor"], "action": r["action"],
             "lesson_id": r["lesson_id"],
             "detail": json.loads(r["detail"]) if r["detail"] else {}} for r in rows]


# ── Clashes ──────────────────────────────────────────────────────────

def _members(group_id: int) -> set[int]:
    with database.connect() as conn:
        return {r[0] for r in conn.execute(
            "SELECT m.pupil_id FROM teaching_group_members m JOIN pupils p USING (pupil_id) "
            "WHERE m.group_id = ? AND p.roll_status = 'on_roll'", (group_id,))}


def _clashes_for(cand: Lesson, others: list[Lesson],
                 members: dict[int, set[int]] | None = None) -> list[str]:
    members = members if members is not None else {}
    out = []
    mine = members.get(cand.group_id)
    if mine is None:
        mine = members[cand.group_id] = _members(cand.group_id)
    for o in others:
        if o.lesson_id == cand.lesson_id or o.slot != cand.slot:
            continue
        if o.group_id == cand.group_id:
            out.append(f"{cand.group_code} already has a lesson then")
            continue
        if cand.teacher_key and o.teacher_key == cand.teacher_key:
            out.append(f"{cand.teacher} is teaching {o.group_code} then")
        if cand.room and o.room and cand.room.lower() == o.room.lower():
            out.append(f"Room {cand.room} is used by {o.group_code} then")
        theirs = members.get(o.group_id)
        if theirs is None:
            theirs = members[o.group_id] = _members(o.group_id)
        both = len(mine & theirs)
        if both:
            out.append(f"{both} pupil(s) in {cand.group_code} are also in {o.group_code}")
    return out


def clashes() -> list[tuple[Lesson, Lesson, list[str]]]:
    """Every pair of this year's lessons that clash, with the reasons."""
    lessons = list_lessons()
    by_slot = grid(lessons)
    members: dict[int, set[int]] = {}
    out = []
    for slot_lessons in by_slot.values():
        for i, a in enumerate(slot_lessons):
            for b in slot_lessons[i + 1:]:
                reasons = _clashes_for(a, [b], members)
                if reasons:
                    out.append((a, b, reasons))
    return out


# ── Requirements ─────────────────────────────────────────────────────

@dataclass(frozen=True)
class Requirement:
    info: TG.GroupInfo
    needed: int | None   # per cycle
    scheduled: int

    @property
    def status(self) -> str:
        if self.needed is None:
            return "no plan" if not self.scheduled else "ok"
        return "ok" if self.scheduled == self.needed else (
            "short" if self.scheduled < self.needed else "over")


def requirements(year_group: int | None = None) -> list[Requirement]:
    """For this year's open groups: lessons needed per cycle (group's own figure, else
    the curriculum plan, times the cycle's weeks) against lessons scheduled."""
    weeks = cycle_weeks()
    counts: dict[int, int] = {}
    for x in list_lessons(year_group=year_group):
        counts[x.group_id] = counts.get(x.group_id, 0) + 1
    return [Requirement(i, i.lessons * weeks if i.lessons else None,
                        counts.get(i.group.group_id, 0))
            for i in TG.info(TG.list_groups(year_group=year_group))]


# ── Changing lessons ─────────────────────────────────────────────────

_FIELDS = ("group_id", "week", "day", "period", "room", "teacher_name", "teacher_username",
           "notes")


def _clean(data: dict[str, Any], current: dict[str, Any] | None) -> dict[str, Any]:
    problems: list[str] = []
    unknown = set(data) - set(_FIELDS)
    if unknown:
        problems.append(f"Unknown field(s): {', '.join(sorted(unknown))}")
    merged = dict(current or {})
    merged.update(data)
    out: dict[str, Any] = {}
    try:
        g = TG.get(int(merged.get("group_id")))  # type: ignore[arg-type]
    except (TypeError, ValueError, TG.NotFound):
        g = None
        problems.append("Choose a teaching group")
    if g is not None:
        if not g.is_current:
            problems.append(f"{g.code} is from {g.academic_year} - only this year's groups "
                            "can be timetabled")
        elif not g.is_active:
            problems.append(f"{g.code} is archived")
        out["group_id"] = g.group_id

    def num(key: str, label: str, lo: int, hi: int) -> None:
        try:
            n = int(str(merged.get(key, "")).strip())
        except ValueError:
            n = 0
        if not lo <= n <= hi:
            problems.append(f"{label} must be from {lo} to {hi}")
        out[key] = n

    raw_day = str(merged.get("day", "")).strip()
    if raw_day[:3].title() in DAYS:
        merged["day"] = DAYS.index(raw_day[:3].title()) + 1
    raw_week = str(merged.get("week", "1") or "1").strip().upper()
    merged["week"] = {"A": 1, "B": 2}.get(raw_week, raw_week)
    num("week", "Week", 1, cycle_weeks())
    num("day", "Day", 1, 5)
    num("period", "Period", 1, len(periods()))
    for key, limit in (("room", 30), ("teacher_name", 100), ("teacher_username", 100),
                       ("notes", 500)):
        out[key] = P._clean_text(merged.get(key), limit)
    if out["teacher_username"]:
        login = next((t for t in TG.teacher_choices()
                      if t["username"].lower() == out["teacher_username"].lower()), None)
        if login is None:
            problems.append(f"'{out['teacher_username']}' isn't a secondary staff login")
        else:
            out["teacher_username"] = login["username"]
            out["teacher_name"] = out["teacher_name"] or login["display_name"]
    if problems:
        raise ValidationError(problems)
    return out


def _candidate(clean: dict[str, Any], lesson_id: int = 0) -> Lesson:
    g = TG.get(clean["group_id"])
    s = S.get(g.subject_id)
    return Lesson(lesson_id, g.group_id, clean["week"], clean["day"], clean["period"],
                  clean["room"], clean["teacher_name"], clean["teacher_username"],
                  clean["notes"], g.code, g.year_group, g.subject_id, s.code, s.name, g.room,
                  g.teacher_name, g.teacher_username)


def check(data: dict[str, Any], lesson_id: int | None = None) -> list[str]:
    """Clashes the lesson would cause (validating it first). Writes nothing."""
    current = None
    if lesson_id:
        x = get(lesson_id)
        current = {"group_id": x.group_id, "week": x.week, "day": x.day, "period": x.period,
                   "room": x.room_override, "teacher_name": x.teacher_name_override,
                   "teacher_username": x.teacher_username_override, "notes": x.notes}
    clean = _clean(data, current)
    cand = _candidate(clean, lesson_id or 0)
    return _clashes_for(cand, list_lessons(week=cand.week, day=cand.day))


def add_lesson(data: dict[str, Any], *, actor: Principal, allow_clash: bool = False) -> Lesson:
    _require(actor, "timetable.create")
    clean = _clean(data, None)
    cand = _candidate(clean)
    found = _clashes_for(cand, list_lessons(week=cand.week, day=cand.day))
    hard = [c for c in found if c.endswith("already has a lesson then")]
    if hard or (found and not allow_clash):
        activity_log.record("timetable.create", principal=actor, outcome="clash",
                            clashes=len(found))
        raise ValidationError(found)
    with database.connect() as conn:
        cols = list(clean)
        cur = conn.execute(
            f"INSERT INTO timetable_lessons ({', '.join(cols)}, created_by, updated_by) "  # nosec B608 - cols from _FIELDS
            f"VALUES ({', '.join('?' * len(cols))}, ?, ?)",
            (*clean.values(), actor.username, actor.username))
        lid = cur.lastrowid
        _audit(conn, lid, "create", actor, {"group_id": clean["group_id"],
                                            "slot": [cand.week, cand.day, cand.period],
                                            "clashes_allowed": len(found) or None})
    activity_log.record("timetable.create", target=f"L{lid}", principal=actor,
                        clashes_allowed=len(found) or None)
    return get(lid)


def update_lesson(lesson_id: int, changes: dict[str, Any], *, actor: Principal,
                  allow_clash: bool = False) -> Lesson:
    _require(actor, "timetable.update", f"L{lesson_id}")
    x = get(lesson_id)
    if x.group_id and not TG.get(x.group_id).is_current:
        raise ValidationError(["Past years' timetables can't be changed"])
    current = {"group_id": x.group_id, "week": x.week, "day": x.day, "period": x.period,
               "room": x.room_override, "teacher_name": x.teacher_name_override,
               "teacher_username": x.teacher_username_override, "notes": x.notes}
    clean = _clean(changes, current)
    cand = _candidate(clean, lesson_id)
    found = _clashes_for(cand, list_lessons(week=cand.week, day=cand.day))
    hard = [c for c in found if c.endswith("already has a lesson then")]
    if hard or (found and not allow_clash):
        raise ValidationError(found)
    diff = {k: {"from": current[k], "to": v} for k, v in clean.items() if current[k] != v}
    if diff:
        with database.connect() as conn:
            sets = ", ".join(f"{k} = ?" for k in diff)
            conn.execute(f"UPDATE timetable_lessons SET {sets}, updated_at = datetime('now'), "  # nosec B608 - keys from _FIELDS
                         "updated_by = ? WHERE lesson_id = ?",
                         (*(d["to"] for d in diff.values()), actor.username, lesson_id))
            _audit(conn, lesson_id, "update", actor,
                   {"fields": sorted(diff), "clashes_allowed": len(found) or None})
        activity_log.record("timetable.update", target=f"L{lesson_id}", principal=actor,
                            fields=sorted(diff))
    return get(lesson_id)


def delete_lesson(lesson_id: int, *, actor: Principal) -> None:
    _require(actor, "timetable.delete", f"L{lesson_id}")
    x = get(lesson_id)
    if not TG.get(x.group_id).is_current:
        raise ValidationError(["Past years' timetables can't be changed"])
    with database.connect() as conn:
        conn.execute("DELETE FROM timetable_lessons WHERE lesson_id = ?", (lesson_id,))
        _audit(conn, lesson_id, "delete", actor, {"group_id": x.group_id,
                                                  "slot": list(x.slot)})
    activity_log.record("timetable.delete", target=f"L{lesson_id}", principal=actor)


def copy_week(*, actor: Principal, from_week: int = 1, to_week: int = 2
              ) -> tuple[int, list[str]]:
    """Copy this year's lessons from one week of the cycle to the other, skipping any
    that would clash or already exist. Returns (copied, notes)."""
    _require(actor, "timetable.copy_week")
    if cycle_weeks() != 2:
        raise ValidationError(["Set a two-week cycle first"])
    copied, notes = 0, []
    for x in list_lessons(week=from_week):
        data = {"group_id": x.group_id, "week": to_week, "day": x.day, "period": x.period,
                "room": x.room_override, "teacher_name": x.teacher_name_override,
                "teacher_username": x.teacher_username_override, "notes": x.notes}
        try:
            add_lesson(data, actor=actor)
            copied += 1
        except ValidationError as e:
            notes.append(f"{x.group_code} {DAYS[x.day - 1]} P{x.period}: {e.problems[0]}")
    with database.connect() as conn:
        _audit(conn, None, "copy_week", actor, {"from": from_week, "to": to_week,
                                                "copied": copied})
    return copied, notes


# ── A real day ───────────────────────────────────────────────────────

def lessons_on(day: _dt.date, **filters: Any) -> tuple[list[Lesson], str]:
    """(lessons on *day*, what kind of day it is). None on non-school days."""
    from education_system.systems.secondary.modules.curriculum.domain import academic_year as AY
    info = AY.day_info(day)
    if info.year is None:
        # No calendar recorded: weekdays only, so the timetable still works.
        if day.weekday() >= 5:
            return [], "Weekend"
        label = "No academic calendar recorded"
    elif not info.is_school_day:
        return [], info.label
    else:
        label = info.label
    week = week_for(day)
    lessons = list_lessons(week=week, day=day.weekday() + 1, **filters)
    return lessons, label + (f" · {WEEK_LABELS[week]}" if cycle_weeks() == 2 else "")
