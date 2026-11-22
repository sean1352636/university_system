"""Tutorial / PSHE programme and personal-tutor 1:1s for the Sixth Form.

Built on the tutor groups in :mod:`domain.pastoral.tutor_groups` (groups
by year group, tutor, membership). Two halves:

**The programme**

* ``tutorial_topics`` — the planned curriculum: academic year, year
  group (12, 13 or both), term and week, PSHE strand, objectives,
  resources, and whether it is required content (RSE, Prevent, online
  safety ...) that every learner must receive.
* ``tutorial_deliveries`` — one row per topic per tutor group: planned
  date, delivered on / by, status. :func:`plan_for_groups` creates the
  rows for every group in the year group.
* ``tutorial_attendance`` — the register for a delivered session.

Reports: coverage (which groups have had which topic), sessions overdue
(the topic's week has passed and the group has not had it), and the
catch-up list of learners who missed required content.

**Personal tutor 1:1s**

* ``tutorial_meetings`` — student, tutor, date, type, discussion,
  student voice, follow-up date / done.
* ``tutorial_meeting_actions`` — agreed actions with owner, due date
  and outcome.

Reports: actions overdue, follow-ups due, and learners with no 1:1
since a date (the "who haven't I seen" list per group).

Access: planning the programme and taking registers need PASTORAL
(every tutor has it); the programme itself is readable by any staff.
1:1 records are pastoral: PASTORAL plus ``can_see_student`` (a tutor
sees their own tutees), and reads/writes are logged. Meetings and
actions reference the student with ``ON DELETE RESTRICT``.
"""

from __future__ import annotations

import datetime as _dt
import logging
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator

from education_system import paths
from education_system.systems.sixth_form.domain.pastoral import _people, _records
from education_system.systems.sixth_form.infrastructure import database as _sql

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_STUDENTS_DB
AREA = "tutorial_meetings"

TERMS: tuple[str, ...] = ("Autumn", "Spring", "Summer")
YEAR_GROUP_CHOICES: tuple[str, ...] = ("12", "13", "Both")
STRANDS: tuple[str, ...] = (
    "Health & Wellbeing", "Relationships & Sex Education",
    "Living in the Wider World", "Careers & Progression (Gatsby)",
    "Study Skills", "British Values & Prevent", "Online Safety",
    "Citizenship", "Financial Capability", "Equality & Diversity",
    "Administration", "Other",
)
DELIVERY_PLANNED = "Planned"
DELIVERY_DONE = "Delivered"
DELIVERY_STATUSES: tuple[str, ...] = (DELIVERY_PLANNED, DELIVERY_DONE,
                                      "Cancelled")
MARKS: tuple[str, ...] = ("Present", "Late", "Absent", "Excused")
MISSED_MARKS = ("Absent", "Excused")

MEETING_TYPES: tuple[str, ...] = (
    "Scheduled 1:1", "Target / progress review", "Welfare check",
    "Attendance", "Careers / UCAS", "Return to study", "Parent meeting",
    "Other",
)
ACTION_OWNERS: tuple[str, ...] = ("Student", "Tutor", "Parent / Carer",
                                  "Subject teacher", "Pastoral team",
                                  "Other")
ACTION_OPEN = "Open"
ACTION_STATUSES: tuple[str, ...] = (ACTION_OPEN, "Done", "Not done",
                                    "Cancelled")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tutorial_topics (
    topic_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    academic_year    TEXT NOT NULL,
    year_group       TEXT NOT NULL DEFAULT 'Both',
    term             TEXT NOT NULL,
    week             INTEGER NOT NULL,
    week_commencing  TEXT,
    title            TEXT NOT NULL,
    strand           TEXT NOT NULL,
    objectives       TEXT,
    resources        TEXT,
    required         INTEGER NOT NULL DEFAULT 0,
    duration_minutes INTEGER,
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    updated_at       TEXT DEFAULT (datetime('now')),
    UNIQUE (academic_year, year_group, term, week, title)
);

CREATE TABLE IF NOT EXISTS tutorial_deliveries (
    delivery_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id       INTEGER NOT NULL,
    tutor_group_id INTEGER,
    group_name     TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'Planned',
    planned_date   TEXT,
    delivered_on   TEXT,
    delivered_by   TEXT,
    notes          TEXT,
    created_at     TEXT DEFAULT (datetime('now')),
    updated_at     TEXT DEFAULT (datetime('now')),
    UNIQUE (topic_id, tutor_group_id),
    FOREIGN KEY (topic_id) REFERENCES tutorial_topics(topic_id)
        ON DELETE RESTRICT,
    FOREIGN KEY (tutor_group_id) REFERENCES tutor_groups(tutor_group_id)
        ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS tutorial_attendance (
    delivery_id INTEGER NOT NULL,
    student_id  TEXT NOT NULL,
    mark        TEXT NOT NULL,
    note        TEXT,
    PRIMARY KEY (delivery_id, student_id),
    FOREIGN KEY (delivery_id) REFERENCES tutorial_deliveries(delivery_id)
        ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES students(student_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS tutorial_meetings (
    meeting_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id        TEXT NOT NULL,
    tutor_staff_id    TEXT,
    tutor_name        TEXT,
    meeting_date      TEXT NOT NULL,
    meeting_type      TEXT NOT NULL,
    duration_minutes  INTEGER,
    discussion        TEXT NOT NULL,
    student_voice     TEXT,
    follow_up_date    TEXT,
    follow_up_done_on TEXT,
    follow_up_notes   TEXT,
    created_by        TEXT,
    created_at        TEXT DEFAULT (datetime('now')),
    updated_at        TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id)
        ON DELETE RESTRICT,
    FOREIGN KEY (tutor_staff_id) REFERENCES staff(staff_id)
        ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS tutorial_meeting_actions (
    action_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    meeting_id   INTEGER NOT NULL,
    student_id   TEXT NOT NULL,
    action       TEXT NOT NULL,
    owner        TEXT NOT NULL DEFAULT 'Student',
    due_date     TEXT,
    status       TEXT NOT NULL DEFAULT 'Open',
    completed_on TEXT,
    notes        TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    updated_at   TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (meeting_id) REFERENCES tutorial_meetings(meeting_id)
        ON DELETE RESTRICT,
    FOREIGN KEY (student_id) REFERENCES students(student_id)
        ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_tut_topic_year ON tutorial_topics(academic_year);
CREATE INDEX IF NOT EXISTS idx_tut_del_group  ON tutorial_deliveries(tutor_group_id);
CREATE INDEX IF NOT EXISTS idx_tut_att_stu    ON tutorial_attendance(student_id);
CREATE INDEX IF NOT EXISTS idx_tut_meet_stu   ON tutorial_meetings(student_id);
CREATE INDEX IF NOT EXISTS idx_tut_meet_date  ON tutorial_meetings(meeting_date);
CREATE INDEX IF NOT EXISTS idx_tut_act_due    ON tutorial_meeting_actions(status, due_date);
"""


class ValidationError(ValueError):
    pass


# ── Shapes ──────────────────────────────────────────────────────────

@dataclass
class Topic:
    topic_id: int
    academic_year: str
    year_group: str
    term: str
    week: int
    week_commencing: str | None
    title: str
    strand: str
    objectives: str | None
    resources: str | None
    required: bool
    duration_minutes: int | None
    notes: str | None
    created_at: str | None
    updated_at: str | None

    @property
    def label(self) -> str:
        return (f"{self.academic_year} Y{self.year_group} {self.term} "
                f"wk{self.week}: {self.title}")

    def applies_to(self, year_group: int | str) -> bool:
        return self.year_group == "Both" or str(year_group) == self.year_group


@dataclass
class Delivery:
    delivery_id: int
    topic_id: int
    tutor_group_id: int | None
    group_name: str
    status: str
    planned_date: str | None
    delivered_on: str | None
    delivered_by: str | None
    notes: str | None
    created_at: str | None
    updated_at: str | None
    topic_title: str | None = None
    present: int = 0
    marked: int = 0


@dataclass
class RegisterLine:
    student_id: str
    student_name: str
    mark: str | None
    note: str | None


@dataclass
class Meeting:
    meeting_id: int
    student_id: str
    tutor_staff_id: str | None
    tutor_name: str | None
    meeting_date: str
    meeting_type: str
    duration_minutes: int | None
    discussion: str
    student_voice: str | None
    follow_up_date: str | None
    follow_up_done_on: str | None
    follow_up_notes: str | None
    created_by: str | None
    created_at: str | None
    updated_at: str | None

    @property
    def follow_up_due(self) -> bool:
        return bool(self.follow_up_date and not self.follow_up_done_on
                    and self.follow_up_date <= _records.today())


@dataclass
class MeetingAction:
    action_id: int
    meeting_id: int
    student_id: str
    action: str
    owner: str
    due_date: str | None
    status: str
    completed_on: str | None
    notes: str | None
    created_at: str | None
    updated_at: str | None

    @property
    def overdue(self) -> bool:
        return bool(self.status == ACTION_OPEN and self.due_date
                    and self.due_date < _records.today())


_C = _records.Col

TOPIC_SPEC = _records.TableSpec(
    table="tutorial_topics", id_col="topic_id", row_type=Topic,
    label="Tutorial topic",
    order_by="academic_year DESC, CASE term WHEN 'Autumn' THEN 1 "
             "WHEN 'Spring' THEN 2 ELSE 3 END, week, year_group, title",
    cols=(
        _C("academic_year", "Academic year (2026/27)", required=True),
        _C("year_group", "Year group", "choice", choices=YEAR_GROUP_CHOICES,
           required=True, default="Both"),
        _C("term", "Term", "choice", choices=TERMS, required=True),
        _C("week", "Week of term", "int", required=True, min_value=1,
           max_value=16),
        _C("week_commencing", "Week commencing", "date"),
        _C("title", "Topic", required=True),
        _C("strand", "PSHE strand", "choice", choices=STRANDS, required=True),
        _C("objectives", "Learning objectives", "multiline", listed=False),
        _C("resources", "Resources (links, packs)", "multiline",
           listed=False),
        _C("required", "Required content (catch-up if missed)", "bool"),
        _C("duration_minutes", "Minutes", "int", min_value=5,
           max_value=240, listed=False),
        _C("notes", "Notes", "multiline", listed=False),
    ))

DELIVERY_SPEC = _records.TableSpec(
    table="tutorial_deliveries", id_col="delivery_id", row_type=Delivery,
    label="Tutorial session", order_by="planned_date, group_name",
    cols=(
        _C("topic_id", "Topic #", "int", required=True, fixed=True),
        _C("tutor_group_id", "Tutor group #", "int", fixed=True),
        _C("group_name", "Tutor group", fixed=True, hidden=True),
        _C("status", "Status", "choice", choices=DELIVERY_STATUSES,
           default=DELIVERY_PLANNED),
        _C("planned_date", "Planned for", "date"),
        _C("delivered_on", "Delivered on", "date"),
        _C("delivered_by", "Delivered by"),
        _C("notes", "Notes", "multiline", listed=False),
    ))

MEETING_SPEC = _records.TableSpec(
    table="tutorial_meetings", id_col="meeting_id", row_type=Meeting,
    label="1:1 meeting", order_by="meeting_date DESC, meeting_id DESC",
    cols=(
        _C("student_id", "Student", "student", required=True, fixed=True),
        _C("tutor_staff_id", "Tutor (staff)"),
        _C("tutor_name", "Tutor", hidden=True),
        _C("meeting_date", "Date", "date", required=True,
           default=_records.today),
        _C("meeting_type", "Type", "choice", choices=MEETING_TYPES,
           required=True, default="Scheduled 1:1"),
        _C("duration_minutes", "Minutes", "int", min_value=1,
           max_value=240, listed=False),
        _C("discussion", "Discussion", "multiline", required=True),
        _C("student_voice", "Student voice", "multiline", listed=False),
        _C("follow_up_date", "Follow up by", "date"),
        _C("follow_up_done_on", "Followed up on", "date"),
        _C("follow_up_notes", "Follow-up notes", "multiline", listed=False),
        _C("created_by", "Recorded by", hidden=True),
    ))

ACTION_SPEC = _records.TableSpec(
    table="tutorial_meeting_actions", id_col="action_id",
    row_type=MeetingAction, label="Agreed action",
    order_by="status <> 'Open', due_date IS NULL, due_date, action_id",
    cols=(
        _C("meeting_id", "Meeting #", "int", required=True, fixed=True),
        _C("student_id", "Student", "student", fixed=True, hidden=True),
        _C("action", "Action", "multiline", required=True),
        _C("owner", "Owner", "choice", choices=ACTION_OWNERS,
           required=True, default="Student"),
        _C("due_date", "Due", "date"),
        _C("status", "Status", "choice", choices=ACTION_STATUSES,
           default=ACTION_OPEN),
        _C("completed_on", "Completed on", "date"),
        _C("notes", "Notes", "multiline", listed=False),
    ))


# ── DB plumbing ─────────────────────────────────────────────────────

@contextmanager
def _connect() -> Iterator[_sql.Connection]:
    paths.ensure_sixth_form_directories()
    conn = _sql.connect(str(DB_PATH))
    conn.row_factory = _sql.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    from education_system.systems.sixth_form.domain.staff import staff as _staff
    _students.init_db()
    _staff.init_db()
    _tg().init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Tutorial programme schema ready at %s", DB_PATH)
    _DB_READY = True


def _tg():
    from education_system.systems.sixth_form.domain.pastoral.tutor_groups import (
        tutor_groups as _t,
    )
    return _t


def _access():
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    return access


def _require(cap: str, action: str) -> Any:
    a = _access()
    p = a.current()
    p.require(getattr(a, cap), action)
    return p


def _guard(action: str, student_id: str | None = None,
           ref: str | None = None) -> Any:
    return _records.guard("PASTORAL", AREA, action, student_id=student_id,
                          record_ref=ref)


def _validate_year(v: str) -> str:
    s = (v or "").strip()
    try:
        a, b = s.split("/")
        ok = len(a) == 4 and len(b) == 2 and (int(a) + 1) % 100 == int(b)
    except ValueError:
        ok = False
    if not ok:
        raise ValidationError(
            "Academic year must look like 2026/27 (consecutive years)")
    return s


def current_academic_year(today: _dt.date | None = None) -> str:
    d = today or _dt.date.today()
    start = d.year if d.month >= 9 else d.year - 1
    return f"{start}/{(start + 1) % 100:02d}"


# ── Topics ──────────────────────────────────────────────────────────

def _topic_rules(p: dict[str, Any]) -> None:
    p["academic_year"] = _validate_year(p["academic_year"])
    p["title"] = p["title"].strip()


def create_topic(data: dict[str, Any]) -> Topic:
    init_db()
    p = _records.validate(TOPIC_SPEC, data, error=ValidationError)
    _topic_rules(p)
    _require("PASTORAL", "plan the tutorial programme")
    with _connect() as conn:
        try:
            new_id = _records.insert(conn, TOPIC_SPEC, p)
        except _sql.IntegrityError:
            raise ValidationError(
                "That topic is already planned for the same week") from None
        return _records.fetch(conn, TOPIC_SPEC, new_id)


def get_topic(topic_id: int) -> Topic | None:
    init_db()
    with _connect() as conn:
        return _records.fetch(conn, TOPIC_SPEC, int(topic_id))


def list_topics(*, academic_year: str | None = None,
                year_group: str | None = None, term: str | None = None,
                strand: str | None = None,
                required_only: bool = False) -> list[Topic]:
    init_db()
    where, args = [], []
    if year_group and year_group != "Both":
        where.append("year_group IN (?, 'Both')")
        args.append(str(year_group))
    if required_only:
        where.append("required = 1")
    with _connect() as conn:
        return _records.select(
            conn, TOPIC_SPEC,
            equals={"academic_year": academic_year, "term": term,
                    "strand": strand,
                    "year_group": "Both" if year_group == "Both" else None},
            where=where, args=args)


def update_topic(topic_id: int, data: dict[str, Any]) -> Topic:
    init_db()
    existing = get_topic(topic_id)
    if existing is None:
        raise ValidationError(f"No topic #{topic_id}")
    p = _records.validate(TOPIC_SPEC, data, error=ValidationError,
                          existing=existing)
    _topic_rules(p)
    _require("PASTORAL", "plan the tutorial programme")
    with _connect() as conn:
        try:
            _records.update(conn, TOPIC_SPEC, topic_id, p)
        except _sql.IntegrityError:
            raise ValidationError(
                "That topic is already planned for the same week") from None
        return _records.fetch(conn, TOPIC_SPEC, topic_id)


def delete_topic(topic_id: int) -> bool:
    init_db()
    _require("PASTORAL", "plan the tutorial programme")
    with _connect() as conn:
        n = conn.execute("SELECT COUNT(*) FROM tutorial_deliveries "
                         "WHERE topic_id = ? AND status = 'Delivered'",
                         (topic_id,)).fetchone()[0]
        if n:
            raise ValidationError(
                f"This topic has been delivered to {n} group(s); it is "
                "part of the record and cannot be deleted")
        conn.execute("DELETE FROM tutorial_deliveries WHERE topic_id = ?",
                     (topic_id,))
        return _records.delete(conn, TOPIC_SPEC, topic_id)


def copy_programme(from_year: str, to_year: str) -> int:
    """Roll a year's programme forward (week-commencing dates cleared).
    Topics already in *to_year* are skipped. Returns topics copied."""
    init_db()
    src, dst = _validate_year(from_year), _validate_year(to_year)
    if src == dst:
        raise ValidationError("Choose a different year to copy into")
    _require("PASTORAL", "plan the tutorial programme")
    n = 0
    with _connect() as conn:
        for t in _records.select(conn, TOPIC_SPEC,
                                 equals={"academic_year": src}):
            vals = {c: getattr(t, c) for c in TOPIC_SPEC.names}
            vals.update(academic_year=dst, week_commencing=None,
                        required=int(t.required))
            try:
                _records.insert(conn, TOPIC_SPEC, vals)
                n += 1
            except _sql.IntegrityError:
                continue
    logger.info("Copied %d tutorial topic(s) %s -> %s", n, src, dst)
    return n


# ── Deliveries + registers ──────────────────────────────────────────

def _delivery_row(r: Any) -> Delivery:
    d = _records.to_row(DELIVERY_SPEC, r)
    keys = set(r.keys())
    if "topic_title" in keys:
        d.topic_title = r["topic_title"]
        d.present = r["present"] or 0
        d.marked = r["marked"] or 0
    return d


_DELIVERY_SELECT = (
    "SELECT d.*, t.title AS topic_title, "
    "(SELECT COUNT(*) FROM tutorial_attendance a WHERE a.delivery_id = "
    "d.delivery_id AND a.mark IN ('Present','Late')) AS present, "
    "(SELECT COUNT(*) FROM tutorial_attendance a WHERE a.delivery_id = "
    "d.delivery_id) AS marked "
    "FROM tutorial_deliveries d JOIN tutorial_topics t "
    "ON t.topic_id = d.topic_id")


def plan_for_groups(topic_id: int, *, group_ids: list[int] | None = None,
                    planned_date: str | None = None) -> list[Delivery]:
    """Create a planned session of *topic_id* for each tutor group in
    its year group (or just *group_ids*). Groups that already have it
    are skipped."""
    init_db()
    topic = get_topic(topic_id)
    if topic is None:
        raise ValidationError(f"No topic #{topic_id}")
    date = _records.check_date(planned_date, "Planned for", ValidationError) \
        or topic.week_commencing
    _require("PASTORAL", "plan tutorial sessions")
    groups = [g for g in _tg().list_groups()
              if topic.applies_to(g.year_group)
              and (group_ids is None or g.tutor_group_id in group_ids)]
    if not groups:
        raise ValidationError("No tutor groups in that year group")
    made = []
    with _connect() as conn:
        for g in groups:
            try:
                new_id = _records.insert(conn, DELIVERY_SPEC, {
                    "topic_id": topic.topic_id,
                    "tutor_group_id": g.tutor_group_id,
                    "group_name": g.name, "status": DELIVERY_PLANNED,
                    "planned_date": date, "delivered_on": None,
                    "delivered_by": None, "notes": None})
            except _sql.IntegrityError:
                continue
            made.append(new_id)
    return [get_delivery(i) for i in made]


def get_delivery(delivery_id: int) -> Delivery | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(_DELIVERY_SELECT + " WHERE d.delivery_id = ?",
                         (int(delivery_id),)).fetchone()
    return _delivery_row(r) if r else None


def list_deliveries(*, topic_id: int | None = None,
                    tutor_group_id: int | None = None,
                    academic_year: str | None = None,
                    status: str | None = None) -> list[Delivery]:
    init_db()
    where, args = [], []
    for col, v in (("d.topic_id", topic_id),
                   ("d.tutor_group_id", tutor_group_id),
                   ("t.academic_year", academic_year), ("d.status", status)):
        if v not in (None, ""):
            where.append(f"{col} = ?")
            args.append(v)
    sql = _DELIVERY_SELECT + (" WHERE " + " AND ".join(where) if where
                              else "")
    sql += (" ORDER BY COALESCE(d.delivered_on, d.planned_date, "
            "t.week_commencing), d.group_name")
    with _connect() as conn:
        return [_delivery_row(r) for r in conn.execute(sql, args)]


def update_delivery(delivery_id: int, data: dict[str, Any]) -> Delivery:
    init_db()
    existing = get_delivery(delivery_id)
    if existing is None:
        raise ValidationError(f"No tutorial session #{delivery_id}")
    p = _records.validate(DELIVERY_SPEC, data, error=ValidationError,
                          existing=existing)
    if p["status"] == DELIVERY_DONE and not p["delivered_on"]:
        p["delivered_on"] = _records.today()
    if p["delivered_on"] and p["delivered_on"] > _records.today():
        raise ValidationError("Delivered on cannot be in the future")
    if p["status"] != DELIVERY_DONE:
        p["delivered_on"] = None
    _require("PASTORAL", "record tutorial sessions")
    with _connect() as conn:
        _records.update(conn, DELIVERY_SPEC, delivery_id, p)
    return get_delivery(delivery_id)


def delete_delivery(delivery_id: int) -> bool:
    init_db()
    _require("PASTORAL", "plan tutorial sessions")
    with _connect() as conn:
        if conn.execute("SELECT 1 FROM tutorial_attendance WHERE "
                        "delivery_id = ?", (delivery_id,)).fetchone():
            raise ValidationError(
                "A register has been taken for this session; cancel it "
                "instead of deleting it")
        return _records.delete(conn, DELIVERY_SPEC, delivery_id)


def register_for(delivery_id: int) -> list[RegisterLine]:
    """The session register: current group members plus anyone already
    marked (e.g. a learner who has since moved group)."""
    init_db()
    d = get_delivery(delivery_id)
    if d is None:
        raise ValidationError(f"No tutorial session #{delivery_id}")
    with _connect() as conn:
        marks = {r["student_id"]: (r["mark"], r["note"]) for r in
                 conn.execute("SELECT student_id, mark, note FROM "
                              "tutorial_attendance WHERE delivery_id = ?",
                              (delivery_id,))}
    members = (_tg().list_members(d.tutor_group_id)
               if d.tutor_group_id else [])
    names = _people.student_names()
    ids = list(dict.fromkeys([*members, *marks]))
    out = [RegisterLine(s, names.get(s, "(unknown)"),
                        *marks.get(s, (None, None))) for s in ids]
    out.sort(key=lambda r: r.student_name)
    return out


def save_register(delivery_id: int, marks: dict[str, str], *,
                  notes: dict[str, str] | None = None,
                  delivered_on: str | None = None,
                  delivered_by: str | None = None) -> Delivery:
    """Record the register and mark the session delivered."""
    init_db()
    d = get_delivery(delivery_id)
    if d is None:
        raise ValidationError(f"No tutorial session #{delivery_id}")
    if d.status == "Cancelled":
        raise ValidationError("This session was cancelled")
    for sid, m in marks.items():
        if m not in MARKS:
            raise ValidationError(f"Mark for {sid} must be one of: "
                                  f"{', '.join(MARKS)}")
        if not _people.student_exists(sid):
            raise ValidationError(f"No student with id {sid}")
    on = _records.check_date(delivered_on, "Delivered on",
                             ValidationError) or d.delivered_on \
        or _records.today()
    if on > _records.today():
        raise ValidationError("Delivered on cannot be in the future")
    p = _require("PASTORAL", "take tutorial registers")
    by = (delivered_by or "").strip() or d.delivered_by \
        or p.staff_name or p.username
    notes = notes or {}
    with _connect() as conn:
        for sid, m in marks.items():
            conn.execute(
                "INSERT INTO tutorial_attendance (delivery_id, student_id, "
                "mark, note) VALUES (?, ?, ?, ?) ON CONFLICT(delivery_id, "
                "student_id) DO UPDATE SET mark = excluded.mark, "
                "note = excluded.note",
                (delivery_id, sid, m, (notes.get(sid) or "").strip() or None))
        conn.execute(
            "UPDATE tutorial_deliveries SET status = 'Delivered', "
            "delivered_on = ?, delivered_by = ?, updated_at = "
            "datetime('now') WHERE delivery_id = ?", (on, by, delivery_id))
    return get_delivery(delivery_id)


# ── Programme reports ───────────────────────────────────────────────

@dataclass
class CoverageRow:
    topic: Topic
    by_group: dict[str, str] = field(default_factory=dict)

    @property
    def delivered(self) -> int:
        return sum(1 for s in self.by_group.values() if s == DELIVERY_DONE)


def coverage(academic_year: str, *, year_group: str | None = None
             ) -> tuple[list[str], list[CoverageRow]]:
    """(group names, one row per topic with each group's status:
    Delivered / Planned / Cancelled / "—" not planned)."""
    init_db()
    year = _validate_year(academic_year)
    groups = [g for g in _tg().list_groups()
              if not year_group or year_group == "Both"
              or str(g.year_group) == str(year_group)]
    names = [g.name for g in sorted(groups, key=lambda g: (g.year_group,
                                                            g.name))]
    by_topic: dict[int, dict[str, str]] = {}
    for d in list_deliveries(academic_year=year):
        by_topic.setdefault(d.topic_id, {})[d.group_name] = d.status
    gy = {g.name: g.year_group for g in groups}
    rows = []
    for t in list_topics(academic_year=year, year_group=year_group):
        statuses = by_topic.get(t.topic_id, {})
        rows.append(CoverageRow(t, {
            n: (statuses.get(n, "—") if t.applies_to(gy[n]) else "n/a")
            for n in names}))
    return names, rows


@dataclass
class OverdueSession:
    topic: Topic
    group_name: str
    status: str
    delivery_id: int | None


def overdue_sessions(academic_year: str | None = None) -> list[OverdueSession]:
    """Topics whose week has passed that a group has not had."""
    init_db()
    year = _validate_year(academic_year or current_academic_year())
    today = _records.today()
    names, rows = coverage(year)
    dels = {(d.topic_id, d.group_name): d for d in
            list_deliveries(academic_year=year)}
    out = []
    for row in rows:
        due = row.topic.week_commencing
        if not due or due > today:
            continue
        for g, status in row.by_group.items():
            if status in (DELIVERY_DONE, "n/a", "Cancelled"):
                continue
            d = dels.get((row.topic.topic_id, g))
            out.append(OverdueSession(row.topic, g,
                                      "Not planned" if status == "—"
                                      else status,
                                      d.delivery_id if d else None))
    return out


@dataclass
class CatchUpRow:
    student_id: str
    student_name: str
    topic_id: int
    topic_title: str
    strand: str
    group_name: str
    session_date: str | None
    mark: str


def catch_up_list(academic_year: str | None = None) -> list[CatchUpRow]:
    """Learners marked Absent / Excused for a required topic who have
    not been marked present at another session of the same topic."""
    init_db()
    year = _validate_year(academic_year or current_academic_year())
    names = _people.student_names()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT a.student_id, a.mark, t.topic_id, t.title, t.strand, "
            "d.group_name, d.delivered_on FROM tutorial_attendance a "
            "JOIN tutorial_deliveries d ON d.delivery_id = a.delivery_id "
            "JOIN tutorial_topics t ON t.topic_id = d.topic_id "
            "WHERE t.academic_year = ? AND t.required = 1 "
            "AND a.mark IN ('Absent','Excused') AND NOT EXISTS ("
            "  SELECT 1 FROM tutorial_attendance a2 JOIN "
            "  tutorial_deliveries d2 ON d2.delivery_id = a2.delivery_id "
            "  WHERE d2.topic_id = t.topic_id AND a2.student_id = "
            "  a.student_id AND a2.mark IN ('Present','Late')) "
            "ORDER BY t.title, d.group_name", (year,)).fetchall()
    return [CatchUpRow(r["student_id"], names.get(r["student_id"], "?"),
                       r["topic_id"], r["title"], r["strand"],
                       r["group_name"], r["delivered_on"], r["mark"])
            for r in rows]


def student_programme(student_id: str,
                      academic_year: str | None = None) -> list[tuple[Any, ...]]:
    """(topic label, group, date, mark) for every session the learner
    was on the register for."""
    init_db()
    year = _validate_year(academic_year or current_academic_year())
    with _connect() as conn:
        return [tuple(r) for r in conn.execute(
            "SELECT t.term || ' wk' || t.week || ': ' || t.title, "
            "d.group_name, d.delivered_on, a.mark FROM tutorial_attendance a "
            "JOIN tutorial_deliveries d ON d.delivery_id = a.delivery_id "
            "JOIN tutorial_topics t ON t.topic_id = d.topic_id "
            "WHERE a.student_id = ? AND t.academic_year = ? "
            "ORDER BY d.delivered_on", (student_id, year))]


# ── 1:1 meetings ────────────────────────────────────────────────────

def _meeting_rules(p: dict[str, Any]) -> None:
    if p["meeting_date"] > _records.today():
        raise ValidationError("A meeting record cannot be dated in the "
                              "future; book it as a follow-up instead")
    p["tutor_staff_id"] = _people.check_staff(
        p["tutor_staff_id"], "Tutor", ValidationError)
    if p["tutor_staff_id"]:
        p["tutor_name"] = _people.staff_name(p["tutor_staff_id"])
    if p["follow_up_date"] and p["follow_up_date"] < p["meeting_date"]:
        raise ValidationError("Follow up by cannot be before the meeting")
    if p["follow_up_done_on"] and p["follow_up_done_on"] < p["meeting_date"]:
        raise ValidationError("Followed up on cannot be before the meeting")


def create_meeting(data: dict[str, Any], *,
                   actions: list[dict[str, Any]] | None = None) -> Meeting:
    init_db()
    data = dict(data)
    if not data.get("tutor_staff_id"):
        data["tutor_staff_id"] = _people.current_staff_id()
    p = _records.validate(MEETING_SPEC, data, error=ValidationError,
                          student_exists=_people.student_exists)
    _meeting_rules(p)
    for a in actions or ():
        if not str(a.get("action") or "").strip():
            raise ValidationError("Each agreed action needs a description")
        due = _records.check_date(a.get("due_date"), "Action due",
                                  ValidationError)
        if due and due < p["meeting_date"]:
            raise ValidationError("An action cannot be due before the meeting")
    actor = _guard("record 1:1 meeting", p["student_id"])
    p["tutor_name"] = p["tutor_name"] or actor.staff_name or actor.username
    p["created_by"] = actor.staff_name or actor.username
    with _connect() as conn:
        new_id = _records.insert(conn, MEETING_SPEC, p)
    for a in actions or ():
        add_action({**a, "meeting_id": new_id})
    return get_meeting(new_id)


def get_meeting(meeting_id: int) -> Meeting | None:
    init_db()
    with _connect() as conn:
        m = _records.fetch(conn, MEETING_SPEC, int(meeting_id))
    if m is not None:
        _guard("view 1:1 meeting", m.student_id, f"tut_meet:{meeting_id}")
    return m


def list_meetings(*, student_id: str | None = None,
                  tutor_staff_id: str | None = None,
                  date_from: str | None = None, date_to: str | None = None,
                  follow_up_due_only: bool = False) -> list[Meeting]:
    init_db()
    _guard("list 1:1 meetings", student_id)
    where, args = [], []
    if date_from:
        where.append("meeting_date >= ?")
        args.append(_records.check_date(date_from, "From", ValidationError))
    if date_to:
        where.append("meeting_date <= ?")
        args.append(_records.check_date(date_to, "To", ValidationError))
    if follow_up_due_only:
        where.append("follow_up_date IS NOT NULL AND follow_up_done_on IS "
                     "NULL AND follow_up_date <= ?")
        args.append(_records.today())
    with _connect() as conn:
        rows = _records.select(
            conn, MEETING_SPEC,
            equals={"student_id": student_id,
                    "tutor_staff_id": _people.id_of(tutor_staff_id)},
            where=where, args=args)
    return _records.visible_filter("PASTORAL", rows)


def update_meeting(meeting_id: int, data: dict[str, Any]) -> Meeting:
    init_db()
    with _connect() as conn:
        existing = _records.fetch(conn, MEETING_SPEC, meeting_id)
    if existing is None:
        raise ValidationError(f"No meeting #{meeting_id}")
    p = _records.validate(MEETING_SPEC, data, error=ValidationError,
                          existing=existing)
    _meeting_rules(p)
    _guard("update 1:1 meeting", existing.student_id,
           f"tut_meet:{meeting_id}")
    with _connect() as conn:
        _records.update(conn, MEETING_SPEC, meeting_id, p)
    return get_meeting(meeting_id)


def complete_follow_up(meeting_id: int, *, on: str | None = None,
                       notes: str | None = None) -> Meeting:
    return update_meeting(meeting_id, {
        "follow_up_done_on": on or _records.today(),
        "follow_up_notes": notes})


def delete_meeting(meeting_id: int) -> bool:
    init_db()
    with _connect() as conn:
        existing = _records.fetch(conn, MEETING_SPEC, meeting_id)
        if existing is None:
            return False
    _guard("delete 1:1 meeting", existing.student_id,
           f"tut_meet:{meeting_id}")
    with _connect() as conn:
        n = conn.execute("SELECT COUNT(*) FROM tutorial_meeting_actions "
                         "WHERE meeting_id = ?", (meeting_id,)).fetchone()[0]
        if n:
            raise ValidationError(
                f"This meeting has {n} agreed action(s); delete those "
                "first if it really was entered by mistake")
        return _records.delete(conn, MEETING_SPEC, meeting_id)


# ── Agreed actions ──────────────────────────────────────────────────

def _action_rules(p: dict[str, Any]) -> None:
    if p["status"] == ACTION_OPEN:
        p["completed_on"] = None
    elif not p["completed_on"]:
        p["completed_on"] = _records.today()


def add_action(data: dict[str, Any]) -> MeetingAction:
    init_db()
    p = _records.validate(ACTION_SPEC, data, error=ValidationError)
    with _connect() as conn:
        m = _records.fetch(conn, MEETING_SPEC, p["meeting_id"])
    if m is None:
        raise ValidationError(f"No meeting #{p['meeting_id']}")
    if p["due_date"] and p["due_date"] < m.meeting_date:
        raise ValidationError("Due date cannot be before the meeting")
    _action_rules(p)
    _guard("add 1:1 action", m.student_id, f"tut_meet:{m.meeting_id}")
    p["student_id"] = m.student_id
    with _connect() as conn:
        new_id = _records.insert(conn, ACTION_SPEC, p)
        return _records.fetch(conn, ACTION_SPEC, new_id)


def update_action(action_id: int, data: dict[str, Any]) -> MeetingAction:
    init_db()
    with _connect() as conn:
        existing = _records.fetch(conn, ACTION_SPEC, action_id)
    if existing is None:
        raise ValidationError(f"No action #{action_id}")
    p = _records.validate(ACTION_SPEC, data, error=ValidationError,
                          existing=existing)
    _action_rules(p)
    _guard("update 1:1 action", existing.student_id, f"tut_act:{action_id}")
    with _connect() as conn:
        _records.update(conn, ACTION_SPEC, action_id, p)
        return _records.fetch(conn, ACTION_SPEC, action_id)


def complete_action(action_id: int, *, status: str = "Done",
                    notes: str | None = None) -> MeetingAction:
    if status == ACTION_OPEN:
        raise ValidationError("Choose how the action ended")
    payload: dict[str, Any] = {"status": status,
                               "completed_on": _records.today()}
    if notes:
        payload["notes"] = notes
    return update_action(action_id, payload)


def delete_action(action_id: int) -> bool:
    init_db()
    with _connect() as conn:
        existing = _records.fetch(conn, ACTION_SPEC, action_id)
        if existing is None:
            return False
    _guard("delete 1:1 action", existing.student_id, f"tut_act:{action_id}")
    with _connect() as conn:
        return _records.delete(conn, ACTION_SPEC, action_id)


def list_actions(*, meeting_id: int | None = None,
                 student_id: str | None = None, open_only: bool = False,
                 overdue_only: bool = False) -> list[MeetingAction]:
    init_db()
    _guard("list 1:1 actions", student_id)
    where, args = [], []
    if open_only or overdue_only:
        where.append("status = 'Open'")
    if overdue_only:
        where.append("due_date IS NOT NULL AND due_date < ?")
        args.append(_records.today())
    with _connect() as conn:
        rows = _records.select(
            conn, ACTION_SPEC,
            equals={"meeting_id": meeting_id, "student_id": student_id},
            where=where, args=args)
    return _records.visible_filter("PASTORAL", rows)


@dataclass
class NotSeenRow:
    student_id: str
    student_name: str
    group_name: str
    tutor: str | None
    last_meeting: str | None


def students_not_seen(*, since: str, tutor_group_id: int | None = None
                      ) -> list[NotSeenRow]:
    """Current tutor-group members with no 1:1 on or after *since*."""
    init_db()
    day = _records.check_date(since, "Since", ValidationError)
    if not day:
        raise ValidationError("Since is required")
    _guard("view learners without a 1:1")
    tg = _tg()
    groups = [g for g in tg.list_groups()
              if tutor_group_id is None or g.tutor_group_id == tutor_group_id]
    names = _people.student_names()
    with _connect() as conn:
        last = {r[0]: r[1] for r in conn.execute(
            "SELECT student_id, MAX(meeting_date) FROM tutorial_meetings "
            "GROUP BY student_id")}
    out = []
    for g in groups:
        for sid in tg.list_members(g.tutor_group_id):
            seen = last.get(sid)
            if seen and seen >= day:
                continue
            out.append(NotSeenRow(sid, names.get(sid, "(unknown)"), g.name,
                                  g.tutor, seen))
    out.sort(key=lambda r: (r.group_name, r.last_meeting or "",
                            r.student_name))
    return _records.visible_filter("PASTORAL", out)
