"""Onboarding — induction checklists for newly enrolled students.

Once a student is enrolled (Admissions → Enrolled, or directly created
via the Students module), an Onboarding ``Checklist`` is opened against
their record to track the post-enrolment tasks: enrolment paperwork,
account & IT setup, ID card, library induction, safeguarding briefing,
PE kit, lanyard, etc.

Two tables:

* ``onboarding_checklists`` — one row per (student, template) pair.
  Holds the overall workflow status, assigned member of staff, and
  open/close dates.

* ``onboarding_items`` — 1:N child rows. Each is a single tick-box
  task with its own status, due date, completion metadata, and a flag
  for whether it's required for the parent checklist to count as
  "complete".

Templates are defined in code (``TEMPLATES`` below) — they are not
stored. Picking a template at creation seeds the child rows.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Any
from education_system.sixthform_system.core import paths
from education_system.sixthform_system.modules.domain.students.onboarding import (
    onboarding as data,
)

logger = logging.getLogger(__name__)

DB_PATH = paths.ONBOARDING_DB


CHECKLIST_STATUSES: tuple[str, ...] = (
    "Not Started", "In Progress", "Completed", "On Hold", "Cancelled",
)
DEFAULT_CHECKLIST_STATUS: str = "Not Started"
OPEN_CHECKLIST_STATUSES: tuple[str, ...] = ("Not Started", "In Progress",
                                              "On Hold")

ITEM_STATUSES: tuple[str, ...] = (
    "Pending", "In Progress", "Done", "N/A", "Blocked",
)
DEFAULT_ITEM_STATUS: str = "Pending"
DONE_ITEM_STATUSES: tuple[str, ...] = ("Done", "N/A")

CATEGORIES: tuple[str, ...] = (
    "Enrolment Paperwork",
    "Account & IT",
    "Equipment",
    "Health & Safety",
    "Wellbeing & Pastoral",
    "Academic",
    "Library & Resources",
    "Finance",
    "Other",
)
DEFAULT_CATEGORY: str = "Enrolment Paperwork"


# ── Templates ─────────────────────────────────────────────────────
# Each template is a list of (task_name, category, required) tuples.
# `required=False` means the parent checklist can still complete
# without this row being ticked.

TEMPLATES: dict[str, list[tuple[str, str, bool]]] = {
    "Standard new starter": [
        ("Enrolment form signed",        "Enrolment Paperwork", True),
        ("Photocopy of ID / passport",   "Enrolment Paperwork", True),
        ("Proof of address",             "Enrolment Paperwork", True),
        ("Parental consent (under 18)",  "Enrolment Paperwork", False),
        ("Medical / GP consent form",    "Health & Safety", True),
        ("Photo consent",                "Enrolment Paperwork", True),
        ("Acceptable-use policy signed", "Account & IT", True),
        ("Email / network account created", "Account & IT", True),
        ("Microsoft 365 logon tested",   "Account & IT", True),
        ("Student ID card issued",       "Equipment", True),
        ("Lanyard issued",               "Equipment", False),
        ("Locker assigned",              "Equipment", False),
        ("Library account activated",    "Library & Resources", True),
        ("Course textbooks issued",      "Library & Resources", True),
        ("Safeguarding briefing",        "Health & Safety", True),
        ("Fire procedure briefing",      "Health & Safety", True),
        ("Meet form tutor",              "Wellbeing & Pastoral", True),
        ("Welcome tour of building",     "Wellbeing & Pastoral", False),
        ("Timetable confirmed",          "Academic", True),
        ("Subject expectations talk",    "Academic", False),
        ("Bursary applied for",          "Finance", False),
    ],
    "Mid-year transfer": [
        ("Transfer paperwork received",     "Enrolment Paperwork", True),
        ("Previous-school records reviewed", "Academic", True),
        ("Subjects reconciled with course", "Academic", True),
        ("Account & email account created", "Account & IT", True),
        ("ID card issued",                  "Equipment", True),
        ("Safeguarding catch-up",           "Health & Safety", True),
        ("Form tutor introduction",         "Wellbeing & Pastoral", True),
        ("Library account activated",       "Library & Resources", True),
        ("Bursary reviewed",                "Finance", False),
    ],
    "International student": [
        ("Passport / visa scanned",            "Enrolment Paperwork", True),
        ("UKVI right-to-study check",          "Enrolment Paperwork", True),
        ("English language evidence",          "Academic", True),
        ("UK address confirmed",               "Enrolment Paperwork", True),
        ("UK emergency contact",               "Enrolment Paperwork", True),
        ("Acceptable-use policy signed",       "Account & IT", True),
        ("Account created",                    "Account & IT", True),
        ("ID card issued",                     "Equipment", True),
        ("Safeguarding briefing",              "Health & Safety", True),
        ("Cultural orientation session",       "Wellbeing & Pastoral", False),
        ("Buddy / peer mentor assigned",       "Wellbeing & Pastoral", False),
    ],
    "Empty (no items)": [],
}
DEFAULT_TEMPLATE: str = "Standard new starter"


_SCHEMA = """
CREATE TABLE IF NOT EXISTS onboarding_checklists (
    checklist_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id        TEXT NOT NULL,
    template_name     TEXT NOT NULL DEFAULT '',
    name              TEXT NOT NULL,
    status            TEXT NOT NULL DEFAULT 'Not Started',
    started_on        TEXT,
    due_date          TEXT,
    completed_on      TEXT,
    assigned_to       TEXT,
    notes             TEXT,
    created_at        TEXT DEFAULT (datetime('now')),
    updated_at        TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS onboarding_items (
    item_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    checklist_id      INTEGER NOT NULL,
    task_name         TEXT NOT NULL,
    category          TEXT NOT NULL DEFAULT 'Other',
    required          INTEGER NOT NULL DEFAULT 1,
    status            TEXT NOT NULL DEFAULT 'Pending',
    due_date          TEXT,
    completed_on      TEXT,
    completed_by      TEXT,
    notes             TEXT,
    sort_order        INTEGER NOT NULL DEFAULT 0,
    created_at        TEXT DEFAULT (datetime('now')),
    updated_at        TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (checklist_id) REFERENCES onboarding_checklists(checklist_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_ob_chk_student ON onboarding_checklists(student_id);
CREATE INDEX IF NOT EXISTS idx_ob_chk_status  ON onboarding_checklists(status);
CREATE INDEX IF NOT EXISTS idx_ob_item_chk    ON onboarding_items(checklist_id);
CREATE INDEX IF NOT EXISTS idx_ob_item_status ON onboarding_items(status);
CREATE INDEX IF NOT EXISTS idx_ob_item_cat    ON onboarding_items(category);
"""


@dataclass
class Item:
    item_id: int
    checklist_id: int
    task_name: str
    category: str
    required: bool
    status: str
    due_date: str | None
    completed_on: str | None
    completed_by: str | None
    notes: str | None
    sort_order: int
    created_at: str
    updated_at: str

    @property
    def is_done(self) -> bool:
        return self.status in DONE_ITEM_STATUSES


@dataclass
class Checklist:
    checklist_id: int
    student_id: str
    template_name: str
    name: str
    status: str
    started_on: str | None
    due_date: str | None
    completed_on: str | None
    assigned_to: str | None
    notes: str | None
    created_at: str
    updated_at: str

    @property
    def is_open(self) -> bool:
        return self.status in OPEN_CHECKLIST_STATUSES


@dataclass
class ChecklistDetail:
    checklist: Checklist
    items: list[Item] = field(default_factory=list)
    student_name: str = ""

    @property
    def total_items(self) -> int:
        return len(self.items)

    @property
    def done_items(self) -> int:
        return sum(1 for i in self.items if i.is_done)

    @property
    def required_total(self) -> int:
        return sum(1 for i in self.items if i.required)

    @property
    def required_done(self) -> int:
        return sum(1 for i in self.items if i.required and i.is_done)

    @property
    def percent_complete(self) -> float:
        if self.total_items == 0:
            return 0.0
        return round(100.0 * self.done_items / self.total_items, 1)

    @property
    def required_complete(self) -> bool:
        return (self.required_total > 0
                 and self.required_done == self.required_total)


@dataclass
class ChecklistRow:
    checklist: Checklist
    student_name: str
    total: int
    done: int
    required_total: int
    required_done: int


@dataclass
class Summary:
    total_checklists: int
    by_status: dict[str, int]
    open_count: int
    completed_count: int
    overdue: int                # open + due_date < today
    upcoming_due: int           # open + due_date in [today, today+window]
    items_total: int
    items_done: int
    items_overdue: int
    by_category: dict[str, int]


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
    from education_system.sixthform_system.modules.domain.students.students import (
        students as _students,
    )
    _students.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Onboarding schema ready at %s", DB_PATH)

    _DB_READY = True


def _row_chk(r: sqlite3.Row) -> Checklist:
    return Checklist(
        checklist_id=r["checklist_id"], student_id=r["student_id"],
        template_name=r["template_name"] or "", name=r["name"],
        status=r["status"], started_on=r["started_on"],
        due_date=r["due_date"], completed_on=r["completed_on"],
        assigned_to=r["assigned_to"], notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _row_item(r: sqlite3.Row) -> Item:
    return Item(
        item_id=r["item_id"], checklist_id=r["checklist_id"],
        task_name=r["task_name"], category=r["category"],
        required=bool(r["required"]), status=r["status"],
        due_date=r["due_date"], completed_on=r["completed_on"],
        completed_by=r["completed_by"], notes=r["notes"],
        sort_order=r["sort_order"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


# ── Validation ────────────────────────────────────────────────────

class ValidationError(ValueError):
    pass


_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _require(value, label: str):
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        raise ValidationError(f"{label} is required")
    return value


def _validate_date(value: Any, label: str, *,
                    required: bool = False) -> str | None:
    if value in (None, "") or (isinstance(value, str)
                                  and not value.strip()):
        if required:
            raise ValidationError(f"{label} is required")
        return None
    s = str(value).strip()
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    try:
        _dt.date.fromisoformat(s)
    except ValueError:
        raise ValidationError(f"{label} is not a real date") from None
    return s


def _validate_student(value: Any) -> str:
    sid = _require(value, "Student ID").strip()
    from education_system.sixthform_system.modules.domain.students.students import (
        students as _students,
    )
    if _students.get_student(sid) is None:
        raise ValidationError(f"No student with id {sid}")
    return sid


def _validate_chk_payload(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["student_id"] = _validate_student(payload.get("student_id"))
    out["name"] = _require(payload.get("name"), "Name").strip()
    status = (payload.get("status") or DEFAULT_CHECKLIST_STATUS).strip()
    if status not in CHECKLIST_STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(CHECKLIST_STATUSES)}")
    out["status"] = status
    out["started_on"]    = _validate_date(payload.get("started_on"),
                                              "Started on")
    out["due_date"]      = _validate_date(payload.get("due_date"),
                                              "Due date")
    out["completed_on"]  = _validate_date(payload.get("completed_on"),
                                              "Completed on")
    out["template_name"] = (payload.get("template_name") or "").strip()
    out["assigned_to"]   = (payload.get("assigned_to") or "").strip() or None
    out["notes"]         = (payload.get("notes") or "").strip() or None
    return out


def _validate_item_payload(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    cid = payload.get("checklist_id")
    if cid in (None, ""):
        raise ValidationError("Checklist id is required")
    try:
        out["checklist_id"] = int(cid)
    except (TypeError, ValueError):
        raise ValidationError("Checklist id must be a number") from None
    if get_checklist(out["checklist_id"]) is None:
        raise ValidationError(f"No checklist #{out['checklist_id']}")

    out["task_name"] = _require(payload.get("task_name"),
                                   "Task name").strip()
    category = (payload.get("category") or DEFAULT_CATEGORY).strip()
    if category not in CATEGORIES:
        raise ValidationError(
            f"Category must be one of: {', '.join(CATEGORIES)}")
    out["category"] = category
    out["required"] = bool(payload.get("required", True))
    status = (payload.get("status") or DEFAULT_ITEM_STATUS).strip()
    if status not in ITEM_STATUSES:
        raise ValidationError(
            f"Item status must be one of: {', '.join(ITEM_STATUSES)}")
    out["status"] = status
    out["due_date"]     = _validate_date(payload.get("due_date"),
                                            "Due date")
    out["completed_on"] = _validate_date(payload.get("completed_on"),
                                            "Completed on")
    out["completed_by"] = (payload.get("completed_by") or "").strip() or None
    out["notes"]        = (payload.get("notes") or "").strip() or None
    try:
        out["sort_order"] = int(payload.get("sort_order") or 0)
    except (TypeError, ValueError):
        out["sort_order"] = 0

    if out["status"] in DONE_ITEM_STATUSES and not out["completed_on"]:
        out["completed_on"] = _dt.date.today().isoformat()
    return out


# ── Checklist CRUD ────────────────────────────────────────────────

def _default_chk_name(student_id: str, template: str) -> str:
    today = _dt.date.today().isoformat()
    base = template if template and template != "Empty (no items)" else "Onboarding"
    return f"{base} — {student_id} ({today})"


def create_checklist(payload: dict[str, Any]) -> Checklist:
    init_db()
    template = (payload.get("template_name") or "").strip()
    if template and template not in TEMPLATES:
        raise ValidationError(
            f"Unknown template {template!r}. "
            f"Valid: {', '.join(TEMPLATES.keys())}")

    # Default name if caller didn't supply one.
    if not (payload.get("name") or "").strip():
        sid = (payload.get("student_id") or "").strip()
        payload = {**payload,
                   "name": _default_chk_name(sid, template)}
    p = _validate_chk_payload(payload)
    if template:
        p["template_name"] = template
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO onboarding_checklists
                   (student_id, template_name, name, status,
                    started_on, due_date, completed_on,
                    assigned_to, notes, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["student_id"], p["template_name"], p["name"], p["status"],
             p["started_on"], p["due_date"], p["completed_on"],
             p["assigned_to"], p["notes"]),
        )
        cid = cur.lastrowid

        # Seed items from the template (if any).
        if template and TEMPLATES.get(template):
            for order, (task, cat, required) in enumerate(
                    TEMPLATES[template]):
                conn.execute(
                    """INSERT INTO onboarding_items
                           (checklist_id, task_name, category, required,
                            status, sort_order)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (cid, task, cat, 1 if required else 0,
                     DEFAULT_ITEM_STATUS, order),
                )
        conn.commit()
    out = get_checklist(cid)
    assert out is not None
    logger.info("Created checklist #%d for %s (template=%s, %d items)",
                cid, p["student_id"], template or "(none)",
                len(TEMPLATES.get(template, []) if template else []))
    return out


def get_checklist(checklist_id: int) -> Checklist | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM onboarding_checklists WHERE checklist_id = ?",
            (checklist_id,)).fetchone()
        return _row_chk(r) if r else None


def list_checklists(
    *,
    student_id: str | None = None,
    status: str | None = None,
    open_only: bool = False,
    overdue_only: bool = False,
    assigned_to: str | None = None,
) -> list[Checklist]:
    init_db()
    clauses, args = [], []
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if status:
        if status not in CHECKLIST_STATUSES:
            raise ValidationError(
                f"Status must be one of: "
                f"{', '.join(CHECKLIST_STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if open_only:
        ph = ",".join("?" * len(OPEN_CHECKLIST_STATUSES))
        clauses.append(f"status IN ({ph})")
        args.extend(OPEN_CHECKLIST_STATUSES)
    if overdue_only:
        today = _dt.date.today().isoformat()
        ph = ",".join("?" * len(OPEN_CHECKLIST_STATUSES))
        clauses.append(
            f"due_date IS NOT NULL AND due_date < ? "
            f"AND status IN ({ph})")
        args.append(today)
        args.extend(OPEN_CHECKLIST_STATUSES)
    if assigned_to:
        clauses.append("assigned_to LIKE ?")
        args.append(f"%{assigned_to.strip()}%")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM onboarding_checklists {where} "
           "ORDER BY CASE status "
           "  WHEN 'In Progress' THEN 0 "
           "  WHEN 'Not Started' THEN 1 "
           "  WHEN 'On Hold'     THEN 2 "
           "  WHEN 'Completed'   THEN 3 "
           "  WHEN 'Cancelled'   THEN 4 "
           "  ELSE 5 END, "
           "due_date IS NULL, due_date ASC, checklist_id DESC")
    with _connect() as conn:
        return [_row_chk(r) for r in conn.execute(sql, args).fetchall()]


def list_checklists_with_detail(**kwargs) -> list[ChecklistRow]:
    rows = list_checklists(**kwargs)
    if not rows:
        return []
    from education_system.sixthform_system.modules.domain.students.students import (
        students as _students,
    )
    names = {s.student_id: s.full_name for s in _students.list_students()}
    out: list[ChecklistRow] = []
    with _connect() as conn:
        for c in rows:
            tot = conn.execute(
                "SELECT COUNT(*) FROM onboarding_items "
                "WHERE checklist_id = ?",
                (c.checklist_id,)).fetchone()[0]
            done = conn.execute(
                f"SELECT COUNT(*) FROM onboarding_items "
                f"WHERE checklist_id = ? AND status IN "
                f"({','.join('?' * len(DONE_ITEM_STATUSES))})",
                (c.checklist_id, *DONE_ITEM_STATUSES)).fetchone()[0]
            req_tot = conn.execute(
                "SELECT COUNT(*) FROM onboarding_items "
                "WHERE checklist_id = ? AND required = 1",
                (c.checklist_id,)).fetchone()[0]
            req_done = conn.execute(
                f"SELECT COUNT(*) FROM onboarding_items "
                f"WHERE checklist_id = ? AND required = 1 "
                f"AND status IN "
                f"({','.join('?' * len(DONE_ITEM_STATUSES))})",
                (c.checklist_id, *DONE_ITEM_STATUSES)).fetchone()[0]
            out.append(ChecklistRow(
                checklist=c,
                student_name=names.get(c.student_id, "(unknown)"),
                total=tot, done=done,
                required_total=req_tot, required_done=req_done,
            ))
    return out


def get_checklist_detail(checklist_id: int) -> ChecklistDetail | None:
    init_db()
    c = get_checklist(checklist_id)
    if c is None:
        return None
    items = list_items(checklist_id=checklist_id)
    from education_system.sixthform_system.modules.domain.students.students import (
        students as _students,
    )
    student = _students.get_student(c.student_id)
    name = student.full_name if student else "(unknown)"
    return ChecklistDetail(checklist=c, items=items, student_name=name)


def update_checklist(checklist_id: int,
                     payload: dict[str, Any]) -> Checklist:
    init_db()
    existing = get_checklist(checklist_id)
    if existing is None:
        raise ValidationError(f"No checklist #{checklist_id}")
    merged = {
        "student_id":    existing.student_id,
        "template_name": existing.template_name,
        "name":          payload.get("name", existing.name),
        "status":        payload.get("status", existing.status),
        "started_on":    payload.get("started_on", existing.started_on),
        "due_date":      payload.get("due_date", existing.due_date),
        "completed_on":  payload.get("completed_on",
                                     existing.completed_on),
        "assigned_to":   payload.get("assigned_to", existing.assigned_to),
        "notes":         payload.get("notes", existing.notes),
    }
    p = _validate_chk_payload(merged)
    if p["status"] == "Completed" and not p["completed_on"]:
        p["completed_on"] = _dt.date.today().isoformat()
    with _connect() as conn:
        conn.execute(
            """UPDATE onboarding_checklists SET
                   name = ?, status = ?, started_on = ?, due_date = ?,
                   completed_on = ?, assigned_to = ?, notes = ?,
                   updated_at = datetime('now')
               WHERE checklist_id = ?""",
            (p["name"], p["status"], p["started_on"], p["due_date"],
             p["completed_on"], p["assigned_to"], p["notes"],
             checklist_id),
        )
        conn.commit()
    out = get_checklist(checklist_id)
    assert out is not None
    logger.info("Updated checklist #%d (status=%s)",
                checklist_id, out.status)
    return out


def set_checklist_status(checklist_id: int, status: str) -> Checklist:
    return update_checklist(checklist_id, {"status": status})


def delete_checklist(checklist_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM onboarding_checklists WHERE checklist_id = ?",
            (checklist_id,))
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted checklist #%d (cascade: items)",
                        checklist_id)
            return True
        return False


# ── Item CRUD ─────────────────────────────────────────────────────

def create_item(payload: dict[str, Any]) -> Item:
    init_db()
    p = _validate_item_payload(payload)
    with _connect() as conn:
        # Auto-assign sort_order to end of list if not provided.
        if not p["sort_order"]:
            max_o = conn.execute(
                "SELECT COALESCE(MAX(sort_order), 0) "
                "FROM onboarding_items WHERE checklist_id = ?",
                (p["checklist_id"],)).fetchone()[0]
            p["sort_order"] = (max_o or 0) + 1
        cur = conn.execute(
            """INSERT INTO onboarding_items
                   (checklist_id, task_name, category, required,
                    status, due_date, completed_on, completed_by,
                    notes, sort_order, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["checklist_id"], p["task_name"], p["category"],
             1 if p["required"] else 0, p["status"],
             p["due_date"], p["completed_on"], p["completed_by"],
             p["notes"], p["sort_order"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_item(new_id)
    assert out is not None
    logger.info("Created item #%d %r on checklist #%d",
                new_id, p["task_name"], p["checklist_id"])
    return out


def get_item(item_id: int) -> Item | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM onboarding_items WHERE item_id = ?",
            (item_id,)).fetchone()
        return _row_item(r) if r else None


def list_items(*, checklist_id: int | None = None,
                category: str | None = None,
                status: str | None = None,
                required_only: bool = False) -> list[Item]:
    init_db()
    clauses, args = [], []
    if checklist_id is not None:
        clauses.append("checklist_id = ?")
        args.append(checklist_id)
    if category:
        if category not in CATEGORIES:
            raise ValidationError(
                f"Category must be one of: {', '.join(CATEGORIES)}")
        clauses.append("category = ?")
        args.append(category)
    if status:
        if status not in ITEM_STATUSES:
            raise ValidationError(
                f"Status must be one of: {', '.join(ITEM_STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if required_only:
        clauses.append("required = 1")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM onboarding_items {where} "
           "ORDER BY sort_order ASC, item_id ASC")
    with _connect() as conn:
        return [_row_item(r) for r in conn.execute(sql, args).fetchall()]


def update_item(item_id: int, payload: dict[str, Any]) -> Item:
    init_db()
    existing = get_item(item_id)
    if existing is None:
        raise ValidationError(f"No item #{item_id}")
    merged = {
        "checklist_id": existing.checklist_id,
        "task_name":    payload.get("task_name", existing.task_name),
        "category":     payload.get("category", existing.category),
        "required":     payload.get("required", existing.required),
        "status":       payload.get("status", existing.status),
        "due_date":     payload.get("due_date", existing.due_date),
        "completed_on": payload.get("completed_on", existing.completed_on),
        "completed_by": payload.get("completed_by", existing.completed_by),
        "notes":        payload.get("notes", existing.notes),
        "sort_order":   payload.get("sort_order", existing.sort_order),
    }
    p = _validate_item_payload(merged)
    with _connect() as conn:
        conn.execute(
            """UPDATE onboarding_items SET
                   task_name = ?, category = ?, required = ?,
                   status = ?, due_date = ?, completed_on = ?,
                   completed_by = ?, notes = ?, sort_order = ?,
                   updated_at = datetime('now')
               WHERE item_id = ?""",
            (p["task_name"], p["category"],
             1 if p["required"] else 0, p["status"],
             p["due_date"], p["completed_on"], p["completed_by"],
             p["notes"], p["sort_order"], item_id),
        )
        conn.commit()
    _maybe_auto_complete(existing.checklist_id)
    out = get_item(item_id)
    assert out is not None
    return out


def set_item_status(item_id: int, status: str, *,
                     completed_by: str | None = None) -> Item:
    payload: dict[str, Any] = {"status": status}
    if status in DONE_ITEM_STATUSES:
        payload["completed_on"] = _dt.date.today().isoformat()
        if completed_by is not None:
            payload["completed_by"] = completed_by
    else:
        # Re-opening clears completion fields.
        payload["completed_on"] = None
        payload["completed_by"] = None
    return update_item(item_id, payload)


def tick(item_id: int, *,
          completed_by: str | None = None) -> Item:
    return set_item_status(item_id, "Done", completed_by=completed_by)


def untick(item_id: int) -> Item:
    return set_item_status(item_id, "Pending")


def delete_item(item_id: int) -> bool:
    init_db()
    existing = get_item(item_id)
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM onboarding_items WHERE item_id = ?",
            (item_id,))
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted item #%d", item_id)
            if existing is not None:
                _maybe_auto_complete(existing.checklist_id)
            return True
        return False


def _maybe_auto_complete(checklist_id: int) -> None:
    """If all required items are done, mark the checklist Completed.
    Inversely, if it was Completed but a required item re-opens,
    flip it back to In Progress."""
    detail = get_checklist_detail(checklist_id)
    if detail is None:
        return
    if (detail.required_total > 0
            and detail.required_complete
            and detail.checklist.status != "Completed"):
        try:
            update_checklist(checklist_id, {
                "status": "Completed",
                "completed_on": _dt.date.today().isoformat(),
            })
        except ValidationError:
            logger.exception("Auto-complete failed for #%d", checklist_id)
    elif (detail.checklist.status == "Completed"
            and detail.required_total > 0
            and not detail.required_complete):
        try:
            update_checklist(checklist_id, {
                "status": "In Progress",
                "completed_on": None,
            })
        except ValidationError:
            logger.exception("Auto-reopen failed for #%d", checklist_id)


# ── Summary ───────────────────────────────────────────────────────

def summary(*, upcoming_window_days: int = 14) -> Summary:
    init_db()
    today = _dt.date.today().isoformat()
    horizon = (_dt.date.today()
                + _dt.timedelta(days=upcoming_window_days)).isoformat()
    rows = list_checklists()
    by_status = {s: 0 for s in CHECKLIST_STATUSES}
    open_count = 0
    completed = 0
    overdue = 0
    upcoming = 0
    for c in rows:
        by_status[c.status] = by_status.get(c.status, 0) + 1
        if c.status in OPEN_CHECKLIST_STATUSES:
            open_count += 1
            if c.due_date:
                if c.due_date < today:
                    overdue += 1
                elif c.due_date <= horizon:
                    upcoming += 1
        if c.status == "Completed":
            completed += 1

    with _connect() as conn:
        items_total = conn.execute(
            "SELECT COUNT(*) FROM onboarding_items").fetchone()[0]
        items_done = conn.execute(
            f"SELECT COUNT(*) FROM onboarding_items "
            f"WHERE status IN "
            f"({','.join('?' * len(DONE_ITEM_STATUSES))})",
            DONE_ITEM_STATUSES).fetchone()[0]
        items_overdue = conn.execute(
            f"SELECT COUNT(*) FROM onboarding_items "
            f"WHERE due_date IS NOT NULL AND due_date < ? "
            f"AND status NOT IN "
            f"({','.join('?' * len(DONE_ITEM_STATUSES))})",
            (today, *DONE_ITEM_STATUSES)).fetchone()[0]

        by_cat: dict[str, int] = {c: 0 for c in CATEGORIES}
        for r in conn.execute(
                "SELECT category, COUNT(*) n FROM onboarding_items "
                "GROUP BY category").fetchall():
            by_cat[r["category"]] = r["n"]

    return Summary(
        total_checklists=len(rows),
        by_status=by_status,
        open_count=open_count,
        completed_count=completed,
        overdue=overdue,
        upcoming_due=upcoming,
        items_total=items_total,
        items_done=items_done,
        items_overdue=items_overdue,
        by_category=by_cat,
    )
