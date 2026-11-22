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

Templates are stored and versioned by :mod:`templates` (``TEMPLATES``
below are the built-in defaults it starts from). Picking a template at
creation seeds the child rows.

Rules (2026-10-29):

* **Evidence-backed items** (see :func:`evidence_problem`). An item's
  ``item_key`` (its template task name, kept when the item is renamed)
  decides its rule: a consent item (:data:`CONSENT_ITEMS`) needs a
  current GDPR consent decision, an ID item (:data:`ID_ITEMS`) the
  enrolment identity check (with right to study for the UKVI item), and
  other areas can register a rule for a key (:func:`register_evidence_rule`
  — IT account, tutor group, timetable…). Without the record, ticking
  needs written ``evidence=`` (kept in its own column with who verified
  it and when — never read from the notes); the right-to-study item
  then also needs a second person (:func:`confirm_evidence`).
* **N/A** needs a reason, and is refused for ID items.
* A checklist is **Completed** only when every required item is done;
  auto-completion never touches On Hold or Cancelled lists.
* Nothing is hard-deleted once used: :func:`delete_checklist` archives,
  :func:`delete_item` refuses a done item, and every change is written to
  ``onboarding_history`` (:func:`history`).
* A checklist belongs to an academic year (and enrolment, when known):
  :func:`open_enrolment_checklist` reuses only that year's open list, and
  only one open list per learner per year can exist.
* **Sensitive items** (:data:`SENSITIVE_KEYS` — DSL contact, care,
  young carer, free meals) show only to staff who manage onboarding or
  hold safeguarding / pastoral, and reads of them are logged.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Any
from collections.abc import Callable

from education_system import paths

logger = logging.getLogger(__name__)


#: Who may change onboarding checklists; reading them is open.
WRITE_CAPABILITIES = ("admissions", "students.manage")


def _require_writer(action: str) -> None:
    """Refuse a write unless the signed-in principal (or a
    ``_guard.system_actor`` block) holds ``admissions`` or
    ``students.manage``. Nobody signed in is refused, never trusted."""
    from education_system.systems.sixth_form.domain.admissions import _guard
    _guard.require_any(WRITE_CAPABILITIES, action)


def can_write() -> bool:
    """Whether the signed-in user may change onboarding (for screens)."""
    from education_system.systems.sixth_form.domain.admissions import _guard
    return any(_guard.can(c) for c in WRITE_CAPABILITIES)

DB_PATH = paths.SIXTH_FORM_ONBOARDING_DB


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

#: Columns added after the original schema: (table, name, DDL type).
_ADDED_COLUMNS: tuple[tuple[str, str, str], ...] = (
    ("onboarding_checklists", "academic_year", "TEXT"),
    ("onboarding_checklists", "enrolment_id", "INTEGER"),
    ("onboarding_checklists", "learner_type", "TEXT"),
    ("onboarding_checklists", "status_reason", "TEXT"),
    ("onboarding_checklists", "archived_at", "TEXT"),
    ("onboarding_checklists", "archived_by", "TEXT"),
    ("onboarding_checklists", "archived_reason", "TEXT"),
    ("onboarding_items", "item_key", "TEXT"),
    ("onboarding_items", "evidence", "TEXT"),
    ("onboarding_items", "evidence_ref", "TEXT"),
    ("onboarding_items", "verified_by", "TEXT"),
    ("onboarding_items", "verified_on", "TEXT"),
    ("onboarding_items", "second_check_by", "TEXT"),
    ("onboarding_items", "second_check_on", "TEXT"),
    ("onboarding_items", "na_reason", "TEXT"),
    ("onboarding_items", "blocked_reason", "TEXT"),
    ("onboarding_items", "sensitive", "INTEGER NOT NULL DEFAULT 0"),
    ("onboarding_items", "owner_role", "TEXT"),
    ("onboarding_items", "assigned_to", "TEXT"),
    ("onboarding_items", "source", "TEXT"),
)

_HISTORY_SCHEMA = """
CREATE TABLE IF NOT EXISTS onboarding_history (
    history_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    checklist_id   INTEGER NOT NULL,
    item_id        INTEGER,
    student_id     TEXT NOT NULL,
    action         TEXT NOT NULL,
    detail         TEXT,
    changed_by     TEXT,
    changed_at     TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (checklist_id) REFERENCES onboarding_checklists(checklist_id)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_ob_hist_chk ON onboarding_history(checklist_id);
CREATE INDEX IF NOT EXISTS idx_ob_hist_student ON onboarding_history(student_id);
CREATE INDEX IF NOT EXISTS idx_ob_chk_year ON onboarding_checklists(student_id, academic_year);
"""

#: One open (not archived) checklist per learner per academic year.
_OPEN_UNIQUE = (
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_ob_open_per_year "
    "ON onboarding_checklists(student_id, COALESCE(academic_year, '')) "
    "WHERE archived_at IS NULL AND status IN "
    "('Not Started', 'In Progress', 'On Hold')")



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
    item_key: str | None = None
    evidence: str | None = None
    evidence_ref: str | None = None
    verified_by: str | None = None
    verified_on: str | None = None
    second_check_by: str | None = None
    second_check_on: str | None = None
    na_reason: str | None = None
    blocked_reason: str | None = None
    sensitive: bool = False
    owner_role: str | None = None
    assigned_to: str | None = None
    source: str | None = None

    @property
    def is_done(self) -> bool:
        return self.status in DONE_ITEM_STATUSES

    @property
    def key(self) -> str:
        """The rule key: the template task name, kept across renames."""
        return self.item_key or self.task_name

    @property
    def awaiting_second_check(self) -> bool:
        return (self.status == "In Progress" and bool(self.evidence)
                and not self.second_check_by)


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
    academic_year: str | None = None
    enrolment_id: int | None = None
    learner_type: str | None = None
    status_reason: str | None = None
    archived_at: str | None = None
    archived_by: str | None = None
    archived_reason: str | None = None

    @property
    def is_open(self) -> bool:
        return self.status in OPEN_CHECKLIST_STATUSES and not self.archived_at

    @property
    def is_archived(self) -> bool:
        return bool(self.archived_at)


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
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    _students.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        for table in ("onboarding_checklists", "onboarding_items"):
            have = {r["name"] for r in conn.execute(
                f"PRAGMA table_info({table})")}
            for t, name, ddl in _ADDED_COLUMNS:
                if t == table and name not in have:
                    conn.execute(f"ALTER TABLE {t} ADD COLUMN {name} {ddl}")
        conn.executescript(_HISTORY_SCHEMA)
        # Rule keys for items made before they existed: the task name.
        conn.execute("UPDATE onboarding_items SET item_key = task_name "
                     "WHERE item_key IS NULL")
        try:
            conn.execute(_OPEN_UNIQUE)
        except sqlite3.IntegrityError:
            logger.warning("Onboarding: a learner has two open checklists "
                           "for one year — the one-open-list rule is not "
                           "enforced until they are merged or closed")
        conn.commit()
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
        **{name: r[name] for t, name, _d in _ADDED_COLUMNS
           if t == "onboarding_checklists" and name in r.keys()},
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
        **{name: (bool(r[name]) if name == "sensitive" else r[name])
           for t, name, _d in _ADDED_COLUMNS
           if t == "onboarding_items" and name in r.keys()},
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
    from education_system.systems.sixth_form.domain.learners.students import (
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


# ── Who, history, sensitive items ─────────────────────────────────

def _actor() -> str | None:
    from education_system.systems.sixth_form.domain.admissions import _guard
    return _guard.actor()


def _log(conn: sqlite3.Connection, *, checklist_id: int, student_id: str,
         action: str, detail: str | None = None,
         item_id: int | None = None) -> None:
    conn.execute(
        "INSERT INTO onboarding_history (checklist_id, item_id, student_id, "
        "action, detail, changed_by) VALUES (?, ?, ?, ?, ?, ?)",
        (checklist_id, item_id, student_id, action, detail, _actor()))


def history(*, checklist_id: int | None = None,
            student_id: str | None = None,
            limit: int = 500) -> list[dict[str, Any]]:
    """The audit trail, newest first."""
    init_db()
    clauses, args = [], []
    if checklist_id is not None:
        clauses.append("checklist_id = ?")
        args.append(checklist_id)
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM onboarding_history {where} "  # noqa: S608 — fixed clauses
            "ORDER BY history_id DESC LIMIT ?", (*args, limit)).fetchall()
    return [dict(r) for r in rows]


#: Item keys whose task (name and notes) is sensitive: who sees them is
#: limited and reads are logged.
SENSITIVE_KEYS: frozenset[str] = frozenset({
    "DSL to contact feeder school (reference request)",
    "Looked-after: virtual school / PEP contact",
    "Care leaver: support plan and bursary",
    "Young carer: support conversation",
    "Free meals: eligibility check",
})
RESTRICTED = "(restricted task)"


def _can_see_sensitive() -> bool:
    from education_system.systems.sixth_form.domain.admissions import _guard
    return can_write() or _guard.can("safeguarding") or _guard.can("pastoral")


def _is_sensitive_key(key: str) -> bool:
    return key in SENSITIVE_KEYS or key.startswith(
        ("Looked-after", "Care leaver", "Young carer", "Free meals"))


def _visible_items(items: list[Item], student_id: str | None) -> list[Item]:
    """Mask sensitive items for readers without the rights; log the
    reads of those who have them."""
    sens = [i for i in items if i.sensitive]
    if not sens:
        return items
    if not _can_see_sensitive():
        for i in sens:
            i.task_name = RESTRICTED
            i.notes = i.evidence = i.na_reason = i.blocked_reason = None
        return items
    try:
        from education_system.systems.sixth_form.domain.governance.user_management import (
            access,
        )
        access.log_sensitive_access(
            access.current(), "onboarding", "view sensitive tasks",
            student_id=student_id,
            record_ref=",".join(str(i.item_id) for i in sens))
    except Exception:  # noqa: BLE001 — logging never blocks a read
        logger.exception("sensitive onboarding read not logged")
    return items


# ── Checklist CRUD ────────────────────────────────────────────────

def _default_chk_name(student_id: str, template: str) -> str:
    today = _dt.date.today().isoformat()
    base = template if template and template != "Empty (no items)" else "Onboarding"
    return f"{base} — {student_id} ({today})"


def _insert_item(conn: sqlite3.Connection, checklist_id: int, *,
                 task: str, category: str, required: bool, order: int,
                 due_date: str | None = None, key: str | None = None,
                 sensitive: bool | None = None,
                 owner_role: str | None = None,
                 source: str = "template") -> int:
    key = key or task
    cur = conn.execute(
        """INSERT INTO onboarding_items
               (checklist_id, task_name, category, required, status,
                due_date, sort_order, item_key, sensitive, owner_role,
                source)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (checklist_id, task, category if category in CATEGORIES else "Other",
         1 if required else 0, DEFAULT_ITEM_STATUS, due_date, order, key,
         1 if (sensitive if sensitive is not None
               else _is_sensitive_key(key)) else 0,
         owner_role, source))
    return cur.lastrowid


def _templates():
    from education_system.systems.sixth_form.domain.admissions.onboarding import (
        templates,
    )
    return templates


def _academic_year_default(enrolment_id: Any) -> tuple[str | None, int | None]:
    """(academic year, enrolment id) for a new checklist."""
    from education_system.systems.sixth_form.domain.admissions.enrolments import (
        enrolments as _enrolments,
    )
    if enrolment_id not in (None, ""):
        e = _enrolments.get_enrolment(int(enrolment_id))
        if e is None:
            raise ValidationError(f"No enrolment #{enrolment_id}")
        return e.academic_year, e.enrolment_id
    return _enrolments.current_academic_year(), None


def create_checklist(payload: dict[str, Any], *,
                     extra_items: list[tuple[str, str, bool]] | None = None
                     ) -> Checklist:
    """Create a checklist (seeded from its template, plus ``extra_items``
    — all in one transaction). ``payload`` may carry ``academic_year``
    and ``enrolment_id`` (default: the enrolment's year, else the current
    academic year) and ``learner_type``. Refused when the learner already
    has an open checklist for that year."""
    _require_writer("creating onboarding checklists")
    init_db()
    template = (payload.get("template_name") or "").strip()

    # Default name if caller didn't supply one.
    if not (payload.get("name") or "").strip():
        sid = (payload.get("student_id") or "").strip()
        payload = {**payload,
                   "name": _default_chk_name(sid, template)}
    p = _validate_chk_payload(payload)
    if template:
        p["template_name"] = template
    if p["status"] not in ("Not Started", "In Progress"):
        raise ValidationError("A new checklist starts Not Started or In Progress")
    year, eid = _academic_year_default(payload.get("enrolment_id"))
    year = (payload.get("academic_year") or "").strip() or year
    tv, seeded = (_templates().items_for(
        template, started_on=p["started_on"], enrolment_id=eid)
        if template else (None, []))
    try:
        with _connect() as conn:
            cur = conn.execute(
                """INSERT INTO onboarding_checklists
                       (student_id, template_name, name, status,
                        started_on, due_date, completed_on,
                        assigned_to, notes, created_at, updated_at,
                        academic_year, enrolment_id, learner_type)
                   VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?,
                           datetime('now'), datetime('now'), ?, ?, ?)""",
                (p["student_id"], p["template_name"], p["name"], p["status"],
                 p["started_on"], p["due_date"], p["assigned_to"],
                 p["notes"], year, eid,
                 (payload.get("learner_type") or "").strip() or None),
            )
            cid = cur.lastrowid
            names: set[str] = set()
            order = 0
            for row in seeded:
                _insert_item(conn, cid, order=order, **row)
                names.add(row["task"])
                order += 1
            if tv is not None:
                _templates().record_use(conn, cid, template, tv)
            for task, cat, required in (extra_items or []):
                if task in names:
                    # The extra wins on "required" (e.g. bursary interest).
                    if required:
                        conn.execute(
                            "UPDATE onboarding_items SET required = 1 "
                            "WHERE checklist_id = ? AND task_name = ?",
                            (cid, task))
                    continue
                _insert_item(conn, cid, task=task, category=cat,
                             required=required, order=order,
                             due_date=p["due_date"], source="extra")
                names.add(task)
                order += 1
            _log(conn, checklist_id=cid, student_id=p["student_id"],
                 action="Created",
                 detail=f"{template or 'no template'}, {year}, "
                        f"{len(names)} task(s)")
            conn.commit()
    except sqlite3.IntegrityError as e:
        if "ux_ob_open_per_year" in str(e) or "UNIQUE" in str(e):
            raise ValidationError(
                f"{p['student_id']} already has an open onboarding checklist "
                f"for {year} — use that one") from e
        raise
    out = get_checklist(cid)
    assert out is not None
    logger.info("Created checklist #%d for %s (template=%s, %s, %d items)",
                cid, p["student_id"], template or "(none)", year, len(names))
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
    academic_year: str | None = None,
    include_archived: bool = False,
    archived_only: bool = False,
) -> list[Checklist]:
    init_db()
    clauses, args = [], []
    if archived_only:
        clauses.append("archived_at IS NOT NULL")
    elif not include_archived:
        clauses.append("archived_at IS NULL")
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if academic_year:
        clauses.append("academic_year = ?")
        args.append(academic_year)
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


def _names_for(conn: sqlite3.Connection, ids: set[str]) -> dict[str, str]:
    if not ids:
        return {}
    ph = ",".join("?" * len(ids))
    try:
        rows = conn.execute(
            f"SELECT student_id, first_name, middle_name, last_name "  # noqa: S608 — placeholders
            f"FROM students WHERE student_id IN ({ph})", tuple(ids)).fetchall()
    except sqlite3.Error:
        return {}
    return {r["student_id"]: " ".join(
        x for x in (r["first_name"], r["middle_name"], r["last_name"]) if x)
        for r in rows}


def list_checklists_with_detail(**kwargs) -> list[ChecklistRow]:
    """Checklists with their item counts — one counting query and one
    name lookup for the whole list."""
    rows = list_checklists(**kwargs)
    if not rows:
        return []
    done_ph = ",".join("?" * len(DONE_ITEM_STATUSES))
    ids = [c.checklist_id for c in rows]
    counts: dict[int, tuple[int, int, int, int]] = {}
    with _connect() as conn:
        for chunk_start in range(0, len(ids), 500):
            chunk = ids[chunk_start:chunk_start + 500]
            ph = ",".join("?" * len(chunk))
            for r in conn.execute(
                    f"""SELECT checklist_id, COUNT(*) AS tot,
                           SUM(status IN ({done_ph})) AS done,
                           SUM(required = 1) AS req_tot,
                           SUM(required = 1 AND status IN ({done_ph}))
                               AS req_done
                        FROM onboarding_items
                        WHERE checklist_id IN ({ph})
                        GROUP BY checklist_id""",  # noqa: S608 — placeholders
                    (*DONE_ITEM_STATUSES, *DONE_ITEM_STATUSES, *chunk)):
                counts[r["checklist_id"]] = (r["tot"], r["done"] or 0,
                                             r["req_tot"] or 0,
                                             r["req_done"] or 0)
        names = _names_for(conn, {c.student_id for c in rows})
    out: list[ChecklistRow] = []
    for c in rows:
        tot, done, req_tot, req_done = counts.get(c.checklist_id, (0, 0, 0, 0))
        out.append(ChecklistRow(
            checklist=c, student_name=names.get(c.student_id, "(unknown)"),
            total=tot, done=done, required_total=req_tot,
            required_done=req_done))
    return out


def get_checklist_detail(checklist_id: int) -> ChecklistDetail | None:
    init_db()
    c = get_checklist(checklist_id)
    if c is None:
        return None
    items = list_items(checklist_id=checklist_id)
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    student = _students.get_student(c.student_id)
    name = student.full_name if student else "(unknown)"
    return ChecklistDetail(checklist=c, items=items, student_name=name)


def _completion_problem(checklist_id: int) -> str | None:
    """Why the checklist can't be Completed (None = it can)."""
    with _connect() as conn:
        r = conn.execute(
            f"""SELECT SUM(required = 1) AS req,
                   SUM(required = 1 AND status IN
                       ({','.join('?' * len(DONE_ITEM_STATUSES))})) AS done
                FROM onboarding_items WHERE checklist_id = ?""",  # noqa: S608
            (*DONE_ITEM_STATUSES, checklist_id)).fetchone()
    req, done = (r["req"] or 0), (r["done"] or 0)
    if req == 0:
        return ("This checklist has no required tasks — add them, or cancel "
                "the checklist with a reason")
    if done < req:
        return (f"{req - done} required task(s) are still open — finish them "
                "or mark them N/A with a reason first")
    return None


def update_checklist(checklist_id: int,
                     payload: dict[str, Any]) -> Checklist:
    """Change a checklist. Completed needs every required task done;
    Cancelled and On Hold need a ``status_reason``."""
    _require_writer("changing onboarding checklists")
    init_db()
    existing = get_checklist(checklist_id)
    if existing is None:
        raise ValidationError(f"No checklist #{checklist_id}")
    if existing.is_archived:
        raise ValidationError(
            f"Checklist #{checklist_id} is archived; restore it first")
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
    reason = (payload.get("status_reason") or "").strip() or None
    if p["status"] != existing.status:
        if p["status"] == "Completed":
            problem = _completion_problem(checklist_id)
            if problem:
                raise ValidationError(problem)
        if p["status"] in ("Cancelled", "On Hold") and not reason:
            raise ValidationError(
                f"Say why the checklist is {p['status'].lower()}")
    if p["status"] == "Completed" and not p["completed_on"]:
        p["completed_on"] = _dt.date.today().isoformat()
    if p["status"] != "Completed":
        p["completed_on"] = None
    changes = [f"{k}: {getattr(existing, k) or '—'} → {p[k] or '—'}"
               for k in ("name", "status", "started_on", "due_date",
                         "assigned_to") if getattr(existing, k) != p[k]]
    if p["notes"] != existing.notes:
        changes.append("notes changed")
    try:
        with _connect() as conn:
            conn.execute(
                """UPDATE onboarding_checklists SET
                       name = ?, status = ?, started_on = ?, due_date = ?,
                       completed_on = ?, assigned_to = ?, notes = ?,
                       status_reason = ?, updated_at = datetime('now')
                   WHERE checklist_id = ?""",
                (p["name"], p["status"], p["started_on"], p["due_date"],
                 p["completed_on"], p["assigned_to"], p["notes"],
                 reason if p["status"] != existing.status
                 else existing.status_reason, checklist_id),
            )
            if changes:
                _log(conn, checklist_id=checklist_id,
                     student_id=existing.student_id, action="Updated",
                     detail="; ".join(changes)
                     + (f" ({reason})" if reason else ""))
            conn.commit()
    except sqlite3.IntegrityError as e:
        raise ValidationError(
            f"{existing.student_id} already has another open checklist for "
            f"{existing.academic_year or 'this year'}") from e
    out = get_checklist(checklist_id)
    assert out is not None
    logger.info("Updated checklist #%d (status=%s)",
                checklist_id, out.status)
    return out


def set_checklist_status(checklist_id: int, status: str, *,
                         reason: str | None = None) -> Checklist:
    _require_writer("changing onboarding checklists")
    return update_checklist(checklist_id, {"status": status,
                                           "status_reason": reason})


def archive_checklist(checklist_id: int, *, reason: str) -> bool:
    """Take a checklist out of every list without losing it."""
    _require_writer("archiving onboarding checklists")
    init_db()
    c = get_checklist(checklist_id)
    if c is None or c.is_archived:
        return False
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError("Say why the checklist is being archived")
    with _connect() as conn:
        conn.execute(
            "UPDATE onboarding_checklists SET archived_at = datetime('now'), "
            "archived_by = ?, archived_reason = ?, updated_at = datetime('now') "
            "WHERE checklist_id = ?", (_actor(), reason, checklist_id))
        _log(conn, checklist_id=checklist_id, student_id=c.student_id,
             action="Archived", detail=reason)
        conn.commit()
    logger.info("Archived checklist #%d", checklist_id)
    return True


def delete_checklist(checklist_id: int, *, reason: str = "Deleted") -> bool:
    """"Delete" from the screens: archives (see :func:`archive_checklist`)."""
    _require_writer("deleting onboarding checklists")
    return archive_checklist(checklist_id, reason=reason)


def restore_checklist(checklist_id: int) -> Checklist:
    _require_writer("restoring onboarding checklists")
    init_db()
    c = get_checklist(checklist_id)
    if c is None:
        raise ValidationError(f"No checklist #{checklist_id}")
    if not c.is_archived:
        return c
    try:
        with _connect() as conn:
            conn.execute(
                "UPDATE onboarding_checklists SET archived_at = NULL, "
                "archived_by = NULL, archived_reason = NULL, "
                "updated_at = datetime('now') WHERE checklist_id = ?",
                (checklist_id,))
            _log(conn, checklist_id=checklist_id, student_id=c.student_id,
                 action="Restored", detail=c.archived_reason)
            conn.commit()
    except sqlite3.IntegrityError as e:
        raise ValidationError(
            f"{c.student_id} has another open checklist for "
            f"{c.academic_year or 'this year'} — close it first") from e
    out = get_checklist(checklist_id)
    assert out is not None
    return out


# ── Item CRUD ─────────────────────────────────────────────────────

def create_item(payload: dict[str, Any]) -> Item:
    """Add a task. It always starts open: a task created as Done or N/A
    is created, then put through the same evidence rules as a tick."""
    _require_writer("adding onboarding tasks")
    init_db()
    p = _validate_item_payload(payload)
    chk = get_checklist(p["checklist_id"])
    assert chk is not None
    if chk.is_archived:
        raise ValidationError(f"Checklist #{chk.checklist_id} is archived")
    wanted = p["status"]
    with _connect() as conn:
        # Auto-assign sort_order to end of list if not provided.
        if not p["sort_order"]:
            max_o = conn.execute(
                "SELECT COALESCE(MAX(sort_order), 0) "
                "FROM onboarding_items WHERE checklist_id = ?",
                (p["checklist_id"],)).fetchone()[0]
            p["sort_order"] = (max_o or 0) + 1
        new_id = _insert_item(
            conn, p["checklist_id"], task=p["task_name"],
            category=p["category"], required=p["required"],
            order=p["sort_order"], due_date=p["due_date"],
            key=(payload.get("item_key") or "").strip() or None,
            sensitive=payload.get("sensitive"),
            owner_role=(payload.get("owner_role") or "").strip() or None,
            source=(payload.get("source") or "manual"))
        if p["notes"] or payload.get("assigned_to"):
            conn.execute("UPDATE onboarding_items SET notes = ?, "
                         "assigned_to = ? WHERE item_id = ?",
                         (p["notes"], (payload.get("assigned_to") or "")
                          .strip() or None, new_id))
        _log(conn, checklist_id=chk.checklist_id, student_id=chk.student_id,
             item_id=new_id, action="Task added", detail=p["task_name"])
        conn.commit()
    if wanted not in (DEFAULT_ITEM_STATUS,):
        try:
            set_item_status(new_id, wanted,
                            completed_by=p["completed_by"],
                            evidence=payload.get("evidence"),
                            reason=payload.get("na_reason")
                            or payload.get("blocked_reason"))
        except ValidationError:
            # Refused: the task is not left behind half-made.
            with _connect() as conn:
                conn.execute("DELETE FROM onboarding_items WHERE item_id = ?",
                             (new_id,))
                _log(conn, checklist_id=chk.checklist_id,
                     student_id=chk.student_id, action="Task removed",
                     detail=f"{p['task_name']} (not added: {wanted} refused)")
                conn.commit()
            raise
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
    if r is None:
        return None
    item = _row_item(r)
    if item.sensitive:
        _visible_items([item], _student_for_item(item))
    return item


def _get_item_raw(item_id: int) -> Item | None:
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
        items = [_row_item(r) for r in conn.execute(sql, args).fetchall()]
    sid = None
    if checklist_id is not None and any(i.sensitive for i in items):
        c = get_checklist(checklist_id)
        sid = c.student_id if c else None
    return _visible_items(items, sid)


#: Item fields an ordinary edit may change. Status goes through
#: :func:`set_item_status`, which applies the evidence rules.
_EDITABLE = ("task_name", "category", "required", "due_date", "notes",
             "sort_order", "owner_role", "assigned_to")


def update_item(item_id: int, payload: dict[str, Any]) -> Item:
    """Edit a task's details. A ``status`` in the payload is handed to
    :func:`set_item_status` (with ``evidence`` / ``na_reason`` /
    ``blocked_reason`` / ``completed_by``), so the evidence rules always
    apply; notes are free text and never count as evidence. Renaming a
    task keeps its rule (``item_key``)."""
    _require_writer("changing onboarding tasks")
    init_db()
    existing = _get_item_raw(item_id)
    if existing is None:
        raise ValidationError(f"No item #{item_id}")
    merged = {
        "checklist_id": existing.checklist_id,
        "task_name":    payload.get("task_name", existing.task_name),
        "category":     payload.get("category", existing.category),
        "required":     payload.get("required", existing.required),
        "status":       existing.status,
        "due_date":     payload.get("due_date", existing.due_date),
        "completed_on": existing.completed_on,
        "completed_by": existing.completed_by,
        "notes":        payload.get("notes", existing.notes),
        "sort_order":   payload.get("sort_order", existing.sort_order),
    }
    p = _validate_item_payload(merged)
    if existing.sensitive and existing.task_name != p["task_name"] \
            and p["task_name"] == RESTRICTED:
        p["task_name"] = existing.task_name      # masked copy sent back
    owner = payload.get("owner_role", existing.owner_role)
    assignee = payload.get("assigned_to", existing.assigned_to)
    changes = [f"{k}: {getattr(existing, k)} → {p[k]}"
               for k in ("task_name", "category", "required", "due_date")
               if getattr(existing, k) != p[k]]
    if p["notes"] != existing.notes:
        changes.append("notes changed")
    if owner != existing.owner_role or assignee != existing.assigned_to:
        changes.append(f"owner {existing.owner_role or '—'}/"
                       f"{existing.assigned_to or '—'} → {owner or '—'}/"
                       f"{assignee or '—'}")
    chk = get_checklist(existing.checklist_id)
    assert chk is not None
    with _connect() as conn:
        conn.execute(
            """UPDATE onboarding_items SET
                   task_name = ?, category = ?, required = ?,
                   due_date = ?, notes = ?, sort_order = ?,
                   owner_role = ?, assigned_to = ?,
                   updated_at = datetime('now')
               WHERE item_id = ?""",
            (p["task_name"], p["category"], 1 if p["required"] else 0,
             p["due_date"], p["notes"], p["sort_order"],
             (owner or "").strip() or None,
             (assignee or "").strip() or None, item_id),
        )
        if changes:
            _log(conn, checklist_id=chk.checklist_id,
                 student_id=chk.student_id, item_id=item_id,
                 action="Task edited", detail="; ".join(changes))
        conn.commit()
    status = payload.get("status")
    if status is not None and status != existing.status:
        return set_item_status(
            item_id, status, completed_by=payload.get("completed_by"),
            evidence=payload.get("evidence"),
            reason=payload.get("na_reason") or payload.get("blocked_reason"))
    if "required" in payload and bool(payload["required"]) != existing.required:
        _maybe_auto_complete(existing.checklist_id)
    out = get_item(item_id)
    assert out is not None
    return out


def _min_text(value: str | None, label: str, n: int = 5) -> str:
    v = (value or "").strip()
    if len(v.replace(" ", "")) < n:
        raise ValidationError(f"{label} must say something real "
                              f"(at least {n} characters)")
    return v


def set_item_status(item_id: int, status: str, *,
                     completed_by: str | None = None,
                     evidence: str | None = None,
                     reason: str | None = None) -> Item:
    """Move a task to ``status``, applying the rules:

    * **Done** on an evidence-backed task needs its record on file (the
      record reference is kept in ``evidence_ref``) or written
      ``evidence`` saying where the proof is (kept with who verified it
      and when). For a task that needs a second check (right to study)
      written evidence leaves it *In Progress* until
      :func:`confirm_evidence` by someone else.
    * **N/A** needs ``reason`` (why it does not apply) and is refused for
      ID tasks.
    * **Blocked** needs ``reason``.
    * Re-opening (Pending / In Progress) clears completion and evidence;
      the history keeps them.
    """
    _require_writer("changing onboarding tasks")
    init_db()
    item = _get_item_raw(item_id)
    if item is None:
        raise ValidationError(f"No item #{item_id}")
    if status not in ITEM_STATUSES:
        raise ValidationError(
            f"Item status must be one of: {', '.join(ITEM_STATUSES)}")
    chk = get_checklist(item.checklist_id)
    assert chk is not None
    if chk.is_archived:
        raise ValidationError(f"Checklist #{chk.checklist_id} is archived")
    today = _dt.date.today().isoformat()
    who = completed_by or _actor()
    fields: dict[str, Any] = {"status": status}
    detail = status
    if status in ("Done", "N/A"):
        fields.update(blocked_reason=None)
    if status == "Done":
        fields["na_reason"] = None
        ref, problem = evidence_check(item)
        if ref:
            fields.update(evidence_ref=ref, evidence=None, verified_by=who,
                          verified_on=today, completed_on=today,
                          completed_by=who)
            detail = f"Done (record {ref})"
        elif evidence and evidence.strip():
            ev = _min_text(evidence, "Evidence")
            fields.update(evidence=ev, evidence_ref=None, verified_by=who,
                          verified_on=today, second_check_by=None,
                          second_check_on=None)
            if needs_second_check(item):
                fields.update(status="In Progress", completed_on=None,
                              completed_by=None)
                detail = f"Evidence recorded, awaiting second check: {ev}"
            else:
                fields.update(completed_on=today, completed_by=who)
                detail = f"Done (evidence: {ev})"
        elif problem:
            raise ValidationError(problem)
        else:
            fields.update(completed_on=today, completed_by=who)
    elif status == "N/A":
        if item.key in ID_ITEMS:
            raise ValidationError(
                f"'{item.task_name}' can't be N/A — an ID / right-to-study "
                "check always applies. Record it, or remove the task if it "
                "was added in error.")
        fields.update(na_reason=_min_text(reason, "The reason it doesn't "
                                                  "apply"),
                      completed_on=today, completed_by=who)
        detail = f"N/A: {fields['na_reason']}"
    elif status == "Blocked":
        fields.update(blocked_reason=_min_text(reason, "What is blocking it"))
        detail = f"Blocked: {fields['blocked_reason']}"
    if status in ("Pending", "In Progress", "Blocked"):
        fields.update(completed_on=None, completed_by=None, evidence=None,
                      evidence_ref=None, verified_by=None, verified_on=None,
                      second_check_by=None, second_check_on=None,
                      na_reason=None)
        if status != "Blocked":
            fields["blocked_reason"] = None
    cols = ", ".join(f"{k} = ?" for k in fields)
    with _connect() as conn:
        conn.execute(
            f"UPDATE onboarding_items SET {cols}, "  # noqa: S608 — fixed column names
            "updated_at = datetime('now') WHERE item_id = ?",
            (*fields.values(), item_id))
        _log(conn, checklist_id=chk.checklist_id, student_id=chk.student_id,
             item_id=item_id, action="Status",
             detail=f"{item.status} → {detail}")
        if chk.status == "Not Started" and fields["status"] != "Pending":
            conn.execute("UPDATE onboarding_checklists SET status = "
                         "'In Progress', updated_at = datetime('now') "
                         "WHERE checklist_id = ?", (chk.checklist_id,))
        conn.commit()
    _maybe_auto_complete(item.checklist_id)
    out = get_item(item_id)
    assert out is not None
    return out


def confirm_evidence(item_id: int, *, note: str | None = None) -> Item:
    """Second check of written evidence (right to study): a different
    person from the one who recorded it confirms, and the task is done."""
    _require_writer("confirming onboarding evidence")
    item = _get_item_raw(item_id)
    if item is None:
        raise ValidationError(f"No item #{item_id}")
    if not item.awaiting_second_check:
        raise ValidationError(f"'{item.task_name}' is not waiting for a "
                              "second check")
    who = _actor()
    if who and who == item.verified_by:
        raise ValidationError("The second check must be made by someone "
                              "other than the person who recorded the "
                              "evidence")
    chk = get_checklist(item.checklist_id)
    assert chk is not None
    today = _dt.date.today().isoformat()
    with _connect() as conn:
        conn.execute(
            "UPDATE onboarding_items SET status = 'Done', completed_on = ?, "
            "completed_by = ?, second_check_by = ?, second_check_on = ?, "
            "updated_at = datetime('now') WHERE item_id = ?",
            (today, item.verified_by, who, today, item_id))
        _log(conn, checklist_id=chk.checklist_id, student_id=chk.student_id,
             item_id=item_id, action="Second check",
             detail="Evidence confirmed" + (f": {note.strip()}"
                                            if note and note.strip() else ""))
        conn.commit()
    _maybe_auto_complete(item.checklist_id)
    out = get_item(item_id)
    assert out is not None
    return out


def tick(item_id: int, *,
          completed_by: str | None = None,
          evidence: str | None = None) -> Item:
    _require_writer("ticking onboarding tasks")
    return set_item_status(item_id, "Done", completed_by=completed_by,
                           evidence=evidence)


def untick(item_id: int) -> Item:
    _require_writer("changing onboarding tasks")
    return set_item_status(item_id, "Pending")


def delete_item(item_id: int) -> bool:
    """Remove a task added in error. A task that has been done, marked
    N/A or given evidence is part of the record — re-open or mark it N/A
    instead."""
    _require_writer("deleting onboarding tasks")
    init_db()
    existing = _get_item_raw(item_id)
    if existing is None:
        return False
    if existing.is_done or existing.evidence or existing.evidence_ref:
        raise ValidationError(
            f"'{existing.task_name}' has been completed — it stays on the "
            "record. Re-open it or mark it N/A with a reason instead.")
    chk = get_checklist(existing.checklist_id)
    assert chk is not None
    with _connect() as conn:
        conn.execute("DELETE FROM onboarding_items WHERE item_id = ?",
                     (item_id,))
        _log(conn, checklist_id=chk.checklist_id, student_id=chk.student_id,
             action="Task removed", detail=existing.task_name)
        conn.commit()
    logger.info("Deleted item #%d", item_id)
    _maybe_auto_complete(existing.checklist_id)
    return True


def _maybe_auto_complete(checklist_id: int) -> None:
    """If all required items are done, mark an *active* checklist (Not
    Started / In Progress) Completed; if a Completed one has a required
    item re-opened, put it back In Progress. On Hold and Cancelled lists
    are never changed here."""
    c = get_checklist(checklist_id)
    if c is None or c.is_archived:
        return
    problem = _completion_problem(checklist_id)
    with _connect() as conn:
        if problem is None and c.status in ("Not Started", "In Progress"):
            conn.execute(
                "UPDATE onboarding_checklists SET status = 'Completed', "
                "completed_on = ?, updated_at = datetime('now') "
                "WHERE checklist_id = ?",
                (_dt.date.today().isoformat(), checklist_id))
            _log(conn, checklist_id=checklist_id, student_id=c.student_id,
                 action="Completed", detail="every required task done")
        elif problem is not None and c.status == "Completed":
            try:
                conn.execute(
                    "UPDATE onboarding_checklists SET status = 'In Progress', "
                    "completed_on = NULL, updated_at = datetime('now') "
                    "WHERE checklist_id = ?", (checklist_id,))
            except sqlite3.IntegrityError:
                logger.warning("Checklist #%d not re-opened: the learner has "
                               "another open list this year", checklist_id)
                return
            _log(conn, checklist_id=checklist_id, student_id=c.student_id,
                 action="Re-opened", detail="a required task re-opened")
        else:
            return
        conn.commit()


def close_for_leaver(student_id: str, day: str) -> list[str]:
    """The learner left: their open checklists are cancelled (reason
    kept). Used by the enrolment leaver steps; never raises."""
    out: list[str] = []
    try:
        for c in list_checklists(student_id=student_id, open_only=True):
            with _connect() as conn:
                conn.execute(
                    "UPDATE onboarding_checklists SET status = 'Cancelled', "
                    "status_reason = ?, updated_at = datetime('now') "
                    "WHERE checklist_id = ?",
                    (f"Learner left on {day}", c.checklist_id))
                _log(conn, checklist_id=c.checklist_id, student_id=student_id,
                     action="Cancelled", detail=f"learner left on {day}")
                conn.commit()
            out.append(f"Onboarding checklist '{c.name}' cancelled (left)")
    except Exception as exc:  # noqa: BLE001 — reported by the caller
        logger.exception("Closing onboarding for leaver %s", student_id)
        out.append(f"Onboarding checklists not closed: {exc}")
    return out


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


# ── Enrolment checklist (opened from admissions / cross-system intake) ──

#: Task added when a student arrives with no subjects chosen yet (a
#: cross-system intake without choices, or a conversion with none).
CHOOSE_SUBJECTS_TASK: str = "Choose subjects / programme of study"
#: Task added when a feeder-school reference asked the college to contact
#: the Designated Safeguarding Lead. Deliberately carries no detail.
CONTACT_DSL_TASK: str = "DSL to contact feeder school (reference request)"


def open_enrolment_checklist(
    student_id: str, *,
    template: str = DEFAULT_TEMPLATE,
    extra_tasks: list[tuple[str, str, bool]] | None = None,
    due_date: str | None = None,
    notes: str | None = None,
    assigned_to: str | None = None,
    academic_year: str | None = None,
    enrolment_id: int | None = None,
    learner_type: str | None = None,
) -> Checklist:
    """Open (or reuse) the student's onboarding checklist for one
    academic year (default: the enrolment's year, else the current one).

    Idempotent: an open checklist *for that year* is reused and only the
    missing ``extra_tasks`` are added (an extra that is required makes
    the existing task required too), so a re-run never duplicates the
    template. A new checklist and its extra tasks are written in one
    transaction.
    """
    _require_writer("opening enrolment checklists")
    init_db()
    year, eid = _academic_year_default(enrolment_id)
    year = academic_year or year
    open_rows = [c for c in list_checklists(student_id=student_id,
                                            open_only=True)
                 if (c.academic_year or year) == year]
    if not open_rows:
        try:
            return create_checklist({
                "student_id": student_id, "template_name": template,
                "status": "Not Started", "due_date": due_date,
                "started_on": _dt.date.today().isoformat(),
                "notes": notes, "assigned_to": assigned_to,
                "academic_year": year, "enrolment_id": eid,
                "learner_type": learner_type,
            }, extra_items=extra_tasks)
        except ValidationError:
            open_rows = [c for c in list_checklists(student_id=student_id,
                                                    open_only=True)
                         if (c.academic_year or year) == year]
            if not open_rows:
                raise
    chk = open_rows[0]
    have = {i.key: i for i in list_items(checklist_id=chk.checklist_id)}
    with _connect() as conn:
        order = conn.execute(
            "SELECT COALESCE(MAX(sort_order), 0) FROM onboarding_items "
            "WHERE checklist_id = ?", (chk.checklist_id,)).fetchone()[0] or 0
        added = []
        for task, category, required in (extra_tasks or []):
            existing = have.get(task)
            if existing is not None:
                if required and not existing.required:
                    conn.execute("UPDATE onboarding_items SET required = 1 "
                                 "WHERE item_id = ?", (existing.item_id,))
                continue
            order += 1
            _insert_item(conn, chk.checklist_id, task=task, category=category,
                         required=required, order=order, due_date=due_date,
                         source="extra")
            added.append(task)
        if eid and not chk.enrolment_id:
            conn.execute("UPDATE onboarding_checklists SET enrolment_id = ? "
                         "WHERE checklist_id = ?", (eid, chk.checklist_id))
        if added:
            _log(conn, checklist_id=chk.checklist_id, student_id=student_id,
                 action="Tasks added", detail=", ".join(added))
        conn.commit()
    out = get_checklist(chk.checklist_id)
    assert out is not None
    return out


# ── Consent items ↔ GDPR consent records ──────────────────────────
#
# The parental / medical / photo consent rows used to be bare tick
# boxes. They are now backed by real records in the GDPR module's
# ``gdpr_consents`` table (owned by governance/gdpr — read and written
# only through its public functions). An item counts as done when a
# current consent decision — granted *or* refused — exists for the
# student and purpose; the item keeps the record in ``evidence_ref``
# ("gdpr:<consent id>").

#: Onboarding task -> (GDPR purpose, detail marker or None). A marker
#: narrows a shared purpose to the rows this task wrote; none of the
#: current items needs one.
CONSENT_ITEMS: dict[str, tuple[str, str | None]] = {
    "Parental consent (under 18)": ("Parental Consent (under 18)", None),
    "Medical / GP consent form":   ("Medical", None),
    "Photo consent":               ("Photography / Video", None),
}
CONSENT_SOURCE: str = "Enrolment onboarding"
#: Old notes marker of a consent-backed tick (read for older rows only).
_CONSENT_NOTE_PREFIX = "GDPR consent #"
_CONSENT_REF = "gdpr:"


@dataclass
class ConsentLink:
    item: Item
    purpose: str
    consent_id: int | None
    state: str              # "Granted" / "Refused" / "Withdrawn" / "Expired" / "Missing"
    detail: str = ""


def _gdpr():
    from education_system.systems.sixth_form.domain.governance.gdpr import (
        gdpr,
    )
    return gdpr


def is_consent_item(item: Item) -> bool:
    return item.key in CONSENT_ITEMS


def _matching_consents(student_id: str, purpose: str,
                       marker: str | None) -> list[Any]:
    rows = _gdpr().list_consents(subject_ref=student_id, purpose=purpose)
    if marker:
        rows = [c for c in rows if (c.detail or "").startswith(marker)]
    return rows      # newest first (granted_date DESC)


def consent_state(student_id: str, task_name: str) -> tuple[str, Any]:
    """(state, consent-or-None) for one consent task (by its key)."""
    purpose, marker = CONSENT_ITEMS[task_name]
    rows = _matching_consents(student_id, purpose, marker)
    if not rows:
        return "Missing", None
    c = rows[0]
    if c.withdrawn_date:
        return "Withdrawn", c
    if c.expires_date and c.expires_date < _dt.date.today().isoformat():
        return "Expired", c
    return ("Granted" if c.granted else "Refused"), c


def consent_links(checklist_id: int) -> list[ConsentLink]:
    """The consent items on a checklist and their GDPR record state.
    Read-only."""
    c = get_checklist(checklist_id)
    if c is None:
        raise ValidationError(f"No checklist #{checklist_id}")
    out: list[ConsentLink] = []
    for item in list_items(checklist_id=checklist_id):
        if not is_consent_item(item):
            continue
        state, consent = consent_state(c.student_id, item.key)
        detail = ""
        if consent is not None:
            detail = (f"#{consent.consent_id} {consent.granted_date}"
                      + (f" — {consent.detail}" if consent.detail else ""))
        out.append(ConsentLink(item=item,
                               purpose=CONSENT_ITEMS[item.key][0],
                               consent_id=consent.consent_id if consent else None,
                               state=state, detail=detail))
    return out


def record_consent(item_id: int, *, granted: bool,
                   given_by: str | None = None,
                   expires_date: str | None = None,
                   recorded_by: str | None = None,
                   notes: str | None = None) -> ConsentLink:
    """Record the consent decision for a consent item in the GDPR module
    and tick the item. ``given_by`` is who gave it (e.g. the parent). If
    the tick fails the new consent record is withdrawn again, so the two
    never disagree."""
    _require_writer("recording onboarding consent")
    item = _get_item_raw(item_id)
    if item is None:
        raise ValidationError(f"No item #{item_id}")
    if not is_consent_item(item):
        raise ValidationError(f"'{item.task_name}' is not a consent item")
    chk = get_checklist(item.checklist_id)
    assert chk is not None
    if chk.is_archived:
        raise ValidationError(f"Checklist #{chk.checklist_id} is archived")
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    s = _students.get_student(chk.student_id)
    purpose, marker = CONSENT_ITEMS[item.key]
    detail_parts = [marker] if marker else []
    if given_by:
        detail_parts.append(f"given by {given_by.strip()}")
    consent = _gdpr().create_consent({
        "subject_name": s.full_name if s else chk.student_id,
        "subject_type": "Student",
        "subject_ref": chk.student_id,
        "purpose": purpose,
        "granted": bool(granted),
        "granted_date": _dt.date.today().isoformat(),
        "expires_date": expires_date,
        "source": CONSENT_SOURCE,
        "detail": " — ".join(detail_parts) or None,
        "notes": notes,
    })
    try:
        if item.is_done:
            set_item_status(item_id, "Pending")
        set_item_status(item_id, "Done", completed_by=recorded_by)
    except Exception:
        logger.exception("Consent #%d recorded but item #%d not ticked — "
                         "withdrawing the consent again",
                         consent.consent_id, item_id)
        try:
            _gdpr().withdraw_consent(
                consent.consent_id,
                notes="Recorded in error (onboarding task not updated)")
        except Exception:  # noqa: BLE001 — reported by the raise below
            logger.exception("Could not withdraw consent #%d",
                             consent.consent_id)
        raise
    logger.info("Consent item #%d (%s) recorded as GDPR consent #%d",
                item_id, item.task_name, consent.consent_id)
    return next(link for link in consent_links(item.checklist_id)
                if link.item.item_id == item_id)


# ── Evidence-backed items ─────────────────────────────────────────

#: ID items: ticking needs the enrolment identity check. Value = whether
#: a right-to-study outcome is also needed.
ID_ITEMS: dict[str, bool] = {
    "Photocopy of ID / passport": False,
    "Passport / visa scanned": False,
    "UKVI right-to-study check": True,
}
#: Items whose written evidence needs a second person's check.
SECOND_CHECK_KEYS: frozenset[str] = frozenset({"UKVI right-to-study check"})
#: Kept for callers that showed it; notes are never evidence any more.
EVIDENCE_PREFIX: str = "Evidence: "

#: Evidence rule: (student_id, item) -> (ok, record reference, message).
#: ``ok`` True = the record is on file (reference kept on the item);
#: False = it isn't (message says what is missing); None = this rule
#: can't tell (the item ticks freely).
EvidenceRule = Callable[[str, Item], "tuple[bool | None, str | None, str]"]
EVIDENCE_RULES: dict[str, EvidenceRule] = {}


def register_evidence_rule(key: str, rule: EvidenceRule) -> None:
    """Make ticking the task ``key`` depend on a real record (used by
    :mod:`evidence_sources`)."""
    EVIDENCE_RULES[key] = rule


_SOURCES_LOADED = False


def _load_evidence_sources() -> None:
    """Register the record-backed rules (:mod:`evidence_sources`, :mod:`bursary_link`; once,
    on first use, so importing this module stays light)."""
    global _SOURCES_LOADED
    if _SOURCES_LOADED:
        return
    _SOURCES_LOADED = True
    import importlib
    for mod in ("evidence_sources", "bursary_link"):
        try:
            importlib.import_module(f"{__package__}.{mod}")
        except ImportError:
            logger.debug("onboarding evidence module %s not loaded", mod)


def needs_second_check(item: Item) -> bool:
    return item.key in SECOND_CHECK_KEYS


def _student_for_item(item: Item) -> str | None:
    chk = get_checklist(item.checklist_id)
    return chk.student_id if chk else None


def _consent_rule(sid: str, item: Item) -> tuple[bool | None, str | None, str]:
    try:
        state, c = consent_state(sid, item.key)
    except Exception:  # noqa: BLE001 — treat as no record
        logger.warning("consent state unreadable for %s", sid, exc_info=True)
        state, c = "Missing", None
    if state in ("Granted", "Refused"):
        return True, f"{_CONSENT_REF}{c.consent_id}", ""
    return False, None, (f"'{item.task_name}': no current consent decision "
                         f"is on file ({state.lower()}). Record the consent, "
                         "or say where the evidence is.")


def _id_rule(sid: str, item: Item) -> tuple[bool | None, str | None, str]:
    from education_system.systems.sixth_form.domain.admissions.enrolments import (
        identity_checks as _idc,
    )
    check = _idc.get_check(sid)
    if check is None or not check.id_checked:
        return False, None, (f"'{item.task_name}': no ID check is recorded "
                             f"for {sid}. Record the ID check, or say where "
                             "the evidence is.")
    if ID_ITEMS[item.key] and not (check.right_to_study or "").startswith("Yes"):
        return False, None, (f"'{item.task_name}': the ID check has no "
                             "confirmed right to study. Record it, or say "
                             "where the evidence is.")
    return True, "idcheck", ""


def evidence_check(item: Item) -> tuple[str | None, str | None]:
    """(record reference, problem) for ticking *item*.

    A reference means the record is on file; a problem means it isn't
    and written evidence is needed; (None, None) means the task ticks
    freely."""
    sid = _student_for_item(item)
    if sid is None:
        return None, None
    _load_evidence_sources()
    if is_consent_item(item):
        rule: EvidenceRule | None = _consent_rule
    elif item.key in ID_ITEMS:
        rule = _id_rule
    else:
        rule = EVIDENCE_RULES.get(item.key)
    if rule is None:
        return None, None
    try:
        ok, ref, message = rule(sid, item)
    except Exception:  # noqa: BLE001 — an unreadable source asks for evidence
        logger.warning("evidence rule for %r failed", item.key, exc_info=True)
        ok, ref, message = False, None, (f"'{item.task_name}': the record "
                                         "could not be checked. Say where "
                                         "the evidence is.")
    if ok:
        return ref or "record", None
    if ok is None:
        return None, None
    return None, message or f"'{item.task_name}' needs evidence"


def evidence_problem(item: Item, notes: str | None = None) -> str | None:
    """Why *item* may not be ticked without written evidence (None = it
    may). *notes* is ignored: notes are free text, never evidence."""
    return evidence_check(item)[1]


def sync_consent_items(checklist_id: int) -> int:
    """Bring consent items in line with the GDPR records.

    A current decision (granted or refused) ticks the item; an item
    ticked from a consent that has since been withdrawn or has expired
    is re-opened. Items ticked with written evidence are left alone.
    Returns the number of items changed.
    """
    _require_writer("updating onboarding consent tasks")
    changed = 0
    for link in consent_links(checklist_id):
        item = link.item
        linked = ((item.evidence_ref or "").startswith(_CONSENT_REF)
                  or (item.notes or "").startswith(_CONSENT_NOTE_PREFIX))
        ref = f"{_CONSENT_REF}{link.consent_id}"
        if link.state in ("Granted", "Refused"):
            if item.is_done and (item.evidence_ref == ref or item.evidence):
                continue
            if item.is_done:
                set_item_status(item.item_id, "Pending")
            set_item_status(item.item_id, "Done")
            changed += 1
        elif linked and item.is_done:
            set_item_status(item.item_id, "Pending")
            update_item(item.item_id, {
                "notes": f"Consent {link.state.lower()} "
                         f"({link.detail}) — needs renewing"})
            changed += 1
    return changed
