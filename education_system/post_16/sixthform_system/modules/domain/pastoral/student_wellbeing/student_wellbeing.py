"""Student Wellbeing data layer for the Sixth Form System.

Student-facing self-service wellbeing module. Three independent record
types:

* **Journal entries** — a per-day self-log: mood / energy / stress /
  sleep_hours on a 1-5 scale (sleep_hours is hours of sleep) plus an
  optional note and gratitude line. One entry per (student, date).
* **Goals** — personal wellbeing goals the student is working on
  (e.g. "Sleep 8 hours", "Exercise 3x/week") with a target date, a
  0-100 progress %, and a status workflow.
* **Resources** — saved help resources (URL, contact line, category)
  curated by the student so they can find them again quickly.

Distinct from the staff-facing `wellbeing` module which holds pastoral
check-ins/sessions/flags. This module is intentionally lightweight and
opinionated towards student self-care.

Cascade: deleting a student wipes all three record types.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.post_16.sixthform_system.core import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.STUDENT_WELLBEING_DB

SCORE_MIN: int = 1
SCORE_MAX: int = 5
SLEEP_MIN: float = 0.0
SLEEP_MAX: float = 24.0

GOAL_CATEGORIES: tuple[str, ...] = (
    "Sleep", "Exercise", "Nutrition", "Mindfulness", "Study Balance",
    "Social", "Screen Time", "Hobbies", "Mental Health", "Other",
)
DEFAULT_GOAL_CATEGORY: str = "Sleep"

GOAL_STATUSES: tuple[str, ...] = (
    "Active", "Paused", "Achieved", "Abandoned",
)
DEFAULT_GOAL_STATUS: str = "Active"

RESOURCE_CATEGORIES: tuple[str, ...] = (
    "Helpline", "Website", "App", "Book", "Article", "Video",
    "In-School Contact", "Local Service", "Other",
)
DEFAULT_RESOURCE_CATEGORY: str = "Website"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_URL_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://\S+$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS student_wellbeing_entries (
    entry_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id   TEXT NOT NULL,
    entry_date   TEXT NOT NULL,
    mood_score   INTEGER,
    energy_score INTEGER,
    stress_score INTEGER,
    sleep_hours  REAL,
    notes        TEXT,
    gratitude    TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    updated_at   TEXT DEFAULT (datetime('now')),
    UNIQUE(student_id, entry_date),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS student_wellbeing_goals (
    goal_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id   TEXT NOT NULL,
    title        TEXT NOT NULL,
    category     TEXT NOT NULL DEFAULT 'Sleep',
    target_date  TEXT,
    progress_pct INTEGER NOT NULL DEFAULT 0,
    status       TEXT NOT NULL DEFAULT 'Active',
    notes        TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    updated_at   TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS student_wellbeing_resources (
    resource_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id  TEXT NOT NULL,
    title       TEXT NOT NULL,
    category    TEXT NOT NULL DEFAULT 'Website',
    url         TEXT,
    contact     TEXT,
    notes       TEXT,
    created_at  TEXT DEFAULT (datetime('now')),
    updated_at  TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_swe_student ON student_wellbeing_entries(student_id);
CREATE INDEX IF NOT EXISTS idx_swe_date    ON student_wellbeing_entries(entry_date);
CREATE INDEX IF NOT EXISTS idx_swg_student ON student_wellbeing_goals(student_id);
CREATE INDEX IF NOT EXISTS idx_swg_status  ON student_wellbeing_goals(status);
CREATE INDEX IF NOT EXISTS idx_swg_target  ON student_wellbeing_goals(target_date);
CREATE INDEX IF NOT EXISTS idx_swr_student ON student_wellbeing_resources(student_id);
CREATE INDEX IF NOT EXISTS idx_swr_cat     ON student_wellbeing_resources(category);
"""


# ── Dataclasses ────────────────────────────────────────────────────

@dataclass
class JournalEntry:
    entry_id: int
    student_id: str
    entry_date: str
    mood_score: int | None
    energy_score: int | None
    stress_score: int | None
    sleep_hours: float | None
    notes: str | None
    gratitude: str | None
    created_at: str
    updated_at: str


@dataclass
class Goal:
    goal_id: int
    student_id: str
    title: str
    category: str
    target_date: str | None
    progress_pct: int
    status: str
    notes: str | None
    created_at: str
    updated_at: str

    @property
    def is_open(self) -> bool:
        return self.status in ("Active", "Paused")


@dataclass
class Resource:
    resource_id: int
    student_id: str
    title: str
    category: str
    url: str | None
    contact: str | None
    notes: str | None
    created_at: str
    updated_at: str


@dataclass
class EntryRow:
    entry: JournalEntry
    student_name: str


@dataclass
class GoalRow:
    goal: Goal
    student_name: str


@dataclass
class ResourceRow:
    resource: Resource
    student_name: str


# ── DB plumbing ────────────────────────────────────────────────────

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
    from education_system.post_16.sixthform_system.modules.domain.students.students import (
        students as _students,
    )
    _students.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Student wellbeing schema ready at %s", DB_PATH)

    _DB_READY = True


def _row_entry(r: sqlite3.Row) -> JournalEntry:
    return JournalEntry(
        entry_id=r["entry_id"], student_id=r["student_id"],
        entry_date=r["entry_date"],
        mood_score=r["mood_score"], energy_score=r["energy_score"],
        stress_score=r["stress_score"], sleep_hours=r["sleep_hours"],
        notes=r["notes"], gratitude=r["gratitude"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _row_goal(r: sqlite3.Row) -> Goal:
    return Goal(
        goal_id=r["goal_id"], student_id=r["student_id"],
        title=r["title"], category=r["category"],
        target_date=r["target_date"], progress_pct=r["progress_pct"],
        status=r["status"], notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _row_resource(r: sqlite3.Row) -> Resource:
    return Resource(
        resource_id=r["resource_id"], student_id=r["student_id"],
        title=r["title"], category=r["category"], url=r["url"],
        contact=r["contact"], notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


# ── Validation ────────────────────────────────────────────────────

class ValidationError(ValueError):
    """Raised for any invalid student-wellbeing input."""


def _require(value: Any, label: str) -> Any:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        raise ValidationError(f"{label} is required")
    return value


def _validate_date(value: Any, label: str, *, required: bool = False) -> str | None:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        if required:
            raise ValidationError(f"{label} is required")
        return None
    s = str(value).strip()
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    return s


def _validate_score(value: Any, label: str) -> int | None:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        return None
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{label} must be a whole number 1-5") from None
    if n < SCORE_MIN or n > SCORE_MAX:
        raise ValidationError(f"{label} must be between 1 and 5")
    return n


def _validate_sleep(value: Any) -> float | None:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        return None
    try:
        h = float(value)
    except (TypeError, ValueError):
        raise ValidationError("Sleep hours must be a number") from None
    if h < SLEEP_MIN or h > SLEEP_MAX:
        raise ValidationError("Sleep hours must be between 0 and 24")
    return round(h, 2)


def _validate_student(value: Any) -> str:
    sid = str(_require(value, "Student ID")).strip()
    from education_system.post_16.sixthform_system.modules.domain.students.students import (
        students as _students,
    )
    if _students.get_student(sid) is None:
        raise ValidationError(f"No student with id {sid}")
    return sid


# ── Journal entries ─────────────────────────────────────────────────

def _validate_entry_payload(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["student_id"] = _validate_student(data.get("student_id"))
    out["entry_date"] = _validate_date(
        data.get("entry_date"), "Entry date", required=True)
    out["mood_score"]   = _validate_score(data.get("mood_score"), "Mood")
    out["energy_score"] = _validate_score(data.get("energy_score"), "Energy")
    out["stress_score"] = _validate_score(data.get("stress_score"), "Stress")
    out["sleep_hours"]  = _validate_sleep(data.get("sleep_hours"))
    notes     = (data.get("notes") or "").strip() or None
    gratitude = (data.get("gratitude") or "").strip() or None
    score_fields = (out["mood_score"], out["energy_score"],
                     out["stress_score"], out["sleep_hours"])
    if all(v is None for v in score_fields) and notes is None and gratitude is None:
        raise ValidationError(
            "Provide at least one score, a sleep value, or a note/gratitude line")
    out["notes"]     = notes
    out["gratitude"] = gratitude
    return out


def create_entry(data: dict[str, Any]) -> JournalEntry:
    init_db()
    try:
        p = _validate_entry_payload(data)
    except ValidationError as e:
        logger.warning("create_entry validation failed: %s", e)
        raise
    with _connect() as conn:
        try:
            cur = conn.execute(
                """INSERT INTO student_wellbeing_entries
                       (student_id, entry_date, mood_score, energy_score,
                        stress_score, sleep_hours, notes, gratitude,
                        created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?,
                           datetime('now'), datetime('now'))""",
                (p["student_id"], p["entry_date"], p["mood_score"],
                 p["energy_score"], p["stress_score"], p["sleep_hours"],
                 p["notes"], p["gratitude"]),
            )
        except sqlite3.IntegrityError as e:
            raise ValidationError(
                f"An entry for {p['student_id']} on {p['entry_date']} "
                "already exists — edit it instead.") from e
        conn.commit()
        new_id = cur.lastrowid
    out = get_entry(new_id)
    assert out is not None
    logger.info(
        "Created student-wellbeing entry #%d for %s on %s",
        new_id, p["student_id"], p["entry_date"],
    )
    return out


def get_entry(entry_id: int) -> JournalEntry | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM student_wellbeing_entries WHERE entry_id = ?",
            (entry_id,),
        ).fetchone()
        return _row_entry(r) if r else None


def get_entry_for(student_id: str, entry_date: str) -> JournalEntry | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            """SELECT * FROM student_wellbeing_entries
                  WHERE student_id = ? AND entry_date = ?""",
            (student_id.strip(), entry_date.strip()),
        ).fetchone()
        return _row_entry(r) if r else None


def list_entries(
    *,
    student_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    low_mood: int | None = None,
    high_stress: int | None = None,
) -> list[JournalEntry]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if date_from:
        clauses.append("entry_date >= ?")
        args.append(_validate_date(date_from, "date_from"))
    if date_to:
        clauses.append("entry_date <= ?")
        args.append(_validate_date(date_to, "date_to"))
    if low_mood is not None:
        clauses.append("mood_score IS NOT NULL AND mood_score <= ?")
        args.append(low_mood)
    if high_stress is not None:
        clauses.append("stress_score IS NOT NULL AND stress_score >= ?")
        args.append(high_stress)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM student_wellbeing_entries {where} "
           "ORDER BY entry_date DESC, entry_id DESC")
    with _connect() as conn:
        return [_row_entry(r) for r in conn.execute(sql, args).fetchall()]


def list_entries_with_detail(**kwargs) -> list[EntryRow]:
    rows = list_entries(**kwargs)
    if not rows:
        return []
    from education_system.post_16.sixthform_system.modules.domain.students.students import (
        students as _students,
    )
    names = {s.student_id: s.full_name for s in _students.list_students()}
    return [EntryRow(entry=e,
                      student_name=names.get(e.student_id, "(unknown)"))
            for e in rows]


def update_entry(entry_id: int, data: dict[str, Any]) -> JournalEntry:
    init_db()
    existing = get_entry(entry_id)
    if existing is None:
        raise ValidationError(f"No entry with id {entry_id}")
    p = _validate_entry_payload({
        "student_id":   existing.student_id,
        "entry_date":   data.get("entry_date", existing.entry_date),
        "mood_score":   data.get("mood_score", existing.mood_score),
        "energy_score": data.get("energy_score", existing.energy_score),
        "stress_score": data.get("stress_score", existing.stress_score),
        "sleep_hours":  data.get("sleep_hours", existing.sleep_hours),
        "notes":        data.get("notes", existing.notes),
        "gratitude":    data.get("gratitude", existing.gratitude),
    })
    with _connect() as conn:
        try:
            conn.execute(
                """UPDATE student_wellbeing_entries SET
                       entry_date = ?, mood_score = ?, energy_score = ?,
                       stress_score = ?, sleep_hours = ?,
                       notes = ?, gratitude = ?,
                       updated_at = datetime('now')
                   WHERE entry_id = ?""",
                (p["entry_date"], p["mood_score"], p["energy_score"],
                 p["stress_score"], p["sleep_hours"],
                 p["notes"], p["gratitude"], entry_id),
            )
        except sqlite3.IntegrityError as e:
            raise ValidationError(
                f"Another entry for {p['student_id']} on {p['entry_date']} "
                "already exists.") from e
        conn.commit()
    out = get_entry(entry_id)
    assert out is not None
    logger.info("Updated student-wellbeing entry #%d", entry_id)
    return out


def delete_entry(entry_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM student_wellbeing_entries WHERE entry_id = ?",
            (entry_id,),
        )
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted student-wellbeing entry #%d", entry_id)
            return True
        return False


# ── Goals ──────────────────────────────────────────────────────────

def _validate_goal_payload(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["student_id"] = _validate_student(data.get("student_id"))
    out["title"] = _require(data.get("title"), "Title").strip()
    if len(out["title"]) > 120:
        raise ValidationError("Title must be 120 characters or fewer")
    category = (data.get("category") or DEFAULT_GOAL_CATEGORY).strip()
    if category not in GOAL_CATEGORIES:
        raise ValidationError(
            f"Category must be one of: {', '.join(GOAL_CATEGORIES)}")
    out["category"] = category
    out["target_date"] = _validate_date(
        data.get("target_date"), "Target date")

    pct = data.get("progress_pct", 0)
    if pct in (None, ""):
        pct = 0
    try:
        pct = int(pct)
    except (TypeError, ValueError):
        raise ValidationError("Progress must be a number 0-100") from None
    if pct < 0 or pct > 100:
        raise ValidationError("Progress must be between 0 and 100")
    out["progress_pct"] = pct

    status = (data.get("status") or DEFAULT_GOAL_STATUS).strip()
    if status not in GOAL_STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(GOAL_STATUSES)}")
    out["status"] = status
    out["notes"] = (data.get("notes") or "").strip() or None
    return out


def create_goal(data: dict[str, Any]) -> Goal:
    init_db()
    try:
        p = _validate_goal_payload(data)
    except ValidationError as e:
        logger.warning("create_goal validation failed: %s", e)
        raise
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO student_wellbeing_goals
                   (student_id, title, category, target_date, progress_pct,
                    status, notes, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["student_id"], p["title"], p["category"], p["target_date"],
             p["progress_pct"], p["status"], p["notes"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_goal(new_id)
    assert out is not None
    logger.info(
        "Created student-wellbeing goal #%d for %s (%s, %s)",
        new_id, p["student_id"], p["category"], p["status"],
    )
    return out


def get_goal(goal_id: int) -> Goal | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM student_wellbeing_goals WHERE goal_id = ?",
            (goal_id,),
        ).fetchone()
        return _row_goal(r) if r else None


def list_goals(
    *,
    student_id: str | None = None,
    category: str | None = None,
    status: str | None = None,
    open_only: bool = False,
) -> list[Goal]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if category:
        if category not in GOAL_CATEGORIES:
            raise ValidationError(
                f"Category must be one of: {', '.join(GOAL_CATEGORIES)}")
        clauses.append("category = ?")
        args.append(category)
    if status:
        if status not in GOAL_STATUSES:
            raise ValidationError(
                f"Status must be one of: {', '.join(GOAL_STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if open_only:
        clauses.append("status IN ('Active', 'Paused')")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM student_wellbeing_goals {where} "
           "ORDER BY status IN ('Achieved','Abandoned'), "
           "target_date IS NULL, target_date, goal_id DESC")
    with _connect() as conn:
        return [_row_goal(r) for r in conn.execute(sql, args).fetchall()]


def list_goals_with_detail(**kwargs) -> list[GoalRow]:
    rows = list_goals(**kwargs)
    if not rows:
        return []
    from education_system.post_16.sixthform_system.modules.domain.students.students import (
        students as _students,
    )
    names = {s.student_id: s.full_name for s in _students.list_students()}
    return [GoalRow(goal=g,
                     student_name=names.get(g.student_id, "(unknown)"))
            for g in rows]


def update_goal(goal_id: int, data: dict[str, Any]) -> Goal:
    init_db()
    existing = get_goal(goal_id)
    if existing is None:
        raise ValidationError(f"No goal with id {goal_id}")
    p = _validate_goal_payload({
        "student_id":   existing.student_id,
        "title":        data.get("title", existing.title),
        "category":     data.get("category", existing.category),
        "target_date":  data.get("target_date", existing.target_date),
        "progress_pct": data.get("progress_pct", existing.progress_pct),
        "status":       data.get("status", existing.status),
        "notes":        data.get("notes", existing.notes),
    })
    with _connect() as conn:
        conn.execute(
            """UPDATE student_wellbeing_goals SET
                   title = ?, category = ?, target_date = ?,
                   progress_pct = ?, status = ?, notes = ?,
                   updated_at = datetime('now')
               WHERE goal_id = ?""",
            (p["title"], p["category"], p["target_date"],
             p["progress_pct"], p["status"], p["notes"], goal_id),
        )
        conn.commit()
    out = get_goal(goal_id)
    assert out is not None
    logger.info("Updated student-wellbeing goal #%d (status=%s, %d%%)",
                goal_id, out.status, out.progress_pct)
    return out


def mark_goal_achieved(goal_id: int) -> Goal:
    return update_goal(goal_id, {"status": "Achieved", "progress_pct": 100})


def delete_goal(goal_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM student_wellbeing_goals WHERE goal_id = ?",
            (goal_id,),
        )
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted student-wellbeing goal #%d", goal_id)
            return True
        return False


# ── Resources ──────────────────────────────────────────────────────

def _validate_resource_payload(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["student_id"] = _validate_student(data.get("student_id"))
    out["title"] = _require(data.get("title"), "Title").strip()
    if len(out["title"]) > 120:
        raise ValidationError("Title must be 120 characters or fewer")
    category = (data.get("category") or DEFAULT_RESOURCE_CATEGORY).strip()
    if category not in RESOURCE_CATEGORIES:
        raise ValidationError(
            f"Category must be one of: {', '.join(RESOURCE_CATEGORIES)}")
    out["category"] = category

    url = (data.get("url") or "").strip() or None
    if url is not None and not _URL_RE.match(url):
        raise ValidationError(
            "URL must look like http://... or https://... (or another scheme)")
    out["url"] = url
    out["contact"] = (data.get("contact") or "").strip() or None
    if out["url"] is None and out["contact"] is None:
        raise ValidationError("Provide a URL or a contact line")
    out["notes"] = (data.get("notes") or "").strip() or None
    return out


def create_resource(data: dict[str, Any]) -> Resource:
    init_db()
    try:
        p = _validate_resource_payload(data)
    except ValidationError as e:
        logger.warning("create_resource validation failed: %s", e)
        raise
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO student_wellbeing_resources
                   (student_id, title, category, url, contact, notes,
                    created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["student_id"], p["title"], p["category"],
             p["url"], p["contact"], p["notes"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_resource(new_id)
    assert out is not None
    logger.info("Created student-wellbeing resource #%d for %s (%s)",
                new_id, p["student_id"], p["category"])
    return out


def get_resource(resource_id: int) -> Resource | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM student_wellbeing_resources WHERE resource_id = ?",
            (resource_id,),
        ).fetchone()
        return _row_resource(r) if r else None


def list_resources(
    *,
    student_id: str | None = None,
    category: str | None = None,
    title_like: str | None = None,
) -> list[Resource]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if category:
        if category not in RESOURCE_CATEGORIES:
            raise ValidationError(
                f"Category must be one of: {', '.join(RESOURCE_CATEGORIES)}")
        clauses.append("category = ?")
        args.append(category)
    if title_like:
        clauses.append("title LIKE ?")
        args.append(f"%{title_like.strip()}%")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM student_wellbeing_resources {where} "
           "ORDER BY category, title")
    with _connect() as conn:
        return [_row_resource(r) for r in conn.execute(sql, args).fetchall()]


def list_resources_with_detail(**kwargs) -> list[ResourceRow]:
    rows = list_resources(**kwargs)
    if not rows:
        return []
    from education_system.post_16.sixthform_system.modules.domain.students.students import (
        students as _students,
    )
    names = {s.student_id: s.full_name for s in _students.list_students()}
    return [ResourceRow(resource=r,
                         student_name=names.get(r.student_id, "(unknown)"))
            for r in rows]


def update_resource(resource_id: int, data: dict[str, Any]) -> Resource:
    init_db()
    existing = get_resource(resource_id)
    if existing is None:
        raise ValidationError(f"No resource with id {resource_id}")
    p = _validate_resource_payload({
        "student_id": existing.student_id,
        "title":      data.get("title", existing.title),
        "category":   data.get("category", existing.category),
        "url":        data.get("url", existing.url),
        "contact":    data.get("contact", existing.contact),
        "notes":      data.get("notes", existing.notes),
    })
    with _connect() as conn:
        conn.execute(
            """UPDATE student_wellbeing_resources SET
                   title = ?, category = ?, url = ?, contact = ?, notes = ?,
                   updated_at = datetime('now')
               WHERE resource_id = ?""",
            (p["title"], p["category"], p["url"], p["contact"],
             p["notes"], resource_id),
        )
        conn.commit()
    out = get_resource(resource_id)
    assert out is not None
    logger.info("Updated student-wellbeing resource #%d", resource_id)
    return out


def delete_resource(resource_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM student_wellbeing_resources WHERE resource_id = ?",
            (resource_id,),
        )
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted student-wellbeing resource #%d", resource_id)
            return True
        return False


# ── Summaries ─────────────────────────────────────────────────────

@dataclass
class StudentSummary:
    student_id: str
    entry_count: int
    goal_count_open: int
    goal_count_achieved: int
    resource_count: int
    latest_entry_date: str | None
    latest_mood: int | None
    latest_energy: int | None
    latest_stress: int | None
    latest_sleep_hours: float | None
    avg_mood: float | None
    avg_energy: float | None
    avg_stress: float | None
    avg_sleep_hours: float | None


def per_student_summary(student_id: str) -> StudentSummary:
    entries = list_entries(student_id=student_id)
    goals = list_goals(student_id=student_id)
    resources = list_resources(student_id=student_id)

    def _avg(nums: list[float | int | None]) -> float | None:
        vals = [n for n in nums if n is not None]
        if not vals:
            return None
        return round(sum(vals) / len(vals), 1)

    latest = entries[0] if entries else None
    return StudentSummary(
        student_id=student_id,
        entry_count=len(entries),
        goal_count_open=sum(1 for g in goals if g.is_open),
        goal_count_achieved=sum(1 for g in goals if g.status == "Achieved"),
        resource_count=len(resources),
        latest_entry_date=latest.entry_date if latest else None,
        latest_mood=latest.mood_score if latest else None,
        latest_energy=latest.energy_score if latest else None,
        latest_stress=latest.stress_score if latest else None,
        latest_sleep_hours=latest.sleep_hours if latest else None,
        avg_mood=_avg([e.mood_score for e in entries]),
        avg_energy=_avg([e.energy_score for e in entries]),
        avg_stress=_avg([e.stress_score for e in entries]),
        avg_sleep_hours=_avg([e.sleep_hours for e in entries]),
    )


@dataclass
class Summary:
    total_entries: int
    total_goals: int
    goals_active: int
    goals_paused: int
    goals_achieved: int
    goals_abandoned: int
    total_resources: int
    by_goal_category: dict[str, int]
    by_resource_category: dict[str, int]
    low_mood_count: int            # entries with mood <= 2
    high_stress_count: int         # entries with stress >= 4
    students_engaged: int          # distinct students with any record


def summary(
    *,
    low_mood_threshold: int = 2,
    high_stress_threshold: int = 4,
) -> Summary:
    init_db()
    entries = list_entries()
    goals = list_goals()
    resources = list_resources()

    by_goal = {c: 0 for c in GOAL_CATEGORIES}
    active = paused = achieved = abandoned = 0
    for g in goals:
        by_goal[g.category] = by_goal.get(g.category, 0) + 1
        if g.status == "Active":
            active += 1
        elif g.status == "Paused":
            paused += 1
        elif g.status == "Achieved":
            achieved += 1
        elif g.status == "Abandoned":
            abandoned += 1

    by_res = {c: 0 for c in RESOURCE_CATEGORIES}
    for r in resources:
        by_res[r.category] = by_res.get(r.category, 0) + 1

    low_mood = sum(1 for e in entries
                    if e.mood_score is not None
                    and e.mood_score <= low_mood_threshold)
    high_stress = sum(1 for e in entries
                       if e.stress_score is not None
                       and e.stress_score >= high_stress_threshold)

    engaged = ({e.student_id for e in entries}
               | {g.student_id for g in goals}
               | {r.student_id for r in resources})

    return Summary(
        total_entries=len(entries),
        total_goals=len(goals),
        goals_active=active,
        goals_paused=paused,
        goals_achieved=achieved,
        goals_abandoned=abandoned,
        total_resources=len(resources),
        by_goal_category=by_goal,
        by_resource_category=by_res,
        low_mood_count=low_mood,
        high_stress_count=high_stress,
        students_engaged=len(engaged),
    )
