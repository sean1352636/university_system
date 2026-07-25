"""To-Do data layer for the Primary School System.

A lightweight personal / shared task list. Each task has:

* a title and optional description
* an owner (free-text — typically a username) plus optional assignee
* a status: ``Open``, ``In Progress``, ``Blocked``, ``Done``, ``Cancelled``
* a priority: ``Low``, ``Normal``, ``High``, ``Urgent``
* a category tag (free-text, e.g. "Admissions", "Pastoral")
* an optional due date (YYYY-MM-DD)
* completed-at timestamp (set when status moves to Done)
"""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass
from datetime import date as _date
from typing import Any

from education_system.systems.primary.infrastructure import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.TODO_DB

STATUSES: tuple[str, ...] = (
    "Open", "In Progress", "Blocked", "Done", "Cancelled",
)
DEFAULT_STATUS: str = "Open"
OPEN_STATUSES: tuple[str, ...] = ("Open", "In Progress", "Blocked")

PRIORITIES: tuple[str, ...] = ("Low", "Normal", "High", "Urgent")
DEFAULT_PRIORITY: str = "Normal"

MAX_TITLE_LEN: int = 200
MAX_CATEGORY_LEN: int = 60
MAX_OWNER_LEN: int = 60

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS todos (
    todo_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    title        TEXT NOT NULL,
    description  TEXT,
    owner        TEXT NOT NULL DEFAULT '',
    assignee     TEXT,
    status       TEXT NOT NULL DEFAULT 'Open',
    priority     TEXT NOT NULL DEFAULT 'Normal',
    category     TEXT,
    due_date     TEXT,
    completed_at TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    updated_at   TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_todos_status   ON todos(status);
CREATE INDEX IF NOT EXISTS idx_todos_owner    ON todos(owner);
CREATE INDEX IF NOT EXISTS idx_todos_assignee ON todos(assignee);
CREATE INDEX IF NOT EXISTS idx_todos_due      ON todos(due_date);
"""


@dataclass
class Todo:
    todo_id: int
    title: str
    description: str | None
    owner: str
    assignee: str | None
    status: str
    priority: str
    category: str | None
    due_date: str | None
    completed_at: str | None
    created_at: str
    updated_at: str

    @property
    def is_open(self) -> bool:
        return self.status in OPEN_STATUSES

    @property
    def is_overdue(self) -> bool:
        if not self.due_date or not self.is_open:
            return False
        return self.due_date < _date.today().isoformat()


@dataclass
class Summary:
    total: int
    open: int
    in_progress: int
    blocked: int
    done: int
    cancelled: int
    overdue: int
    due_today: int
    due_within_7d: int
    by_priority: dict[str, int]
    by_owner: dict[str, int]
    by_category: dict[str, int]


# ── DB plumbing ────────────────────────────────────────────────────

class ValidationError(ValueError):
    pass


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
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("To-do schema ready at %s", DB_PATH)

    _DB_READY = True


def _row(r: sqlite3.Row) -> Todo:
    return Todo(
        todo_id=r["todo_id"], title=r["title"],
        description=r["description"], owner=r["owner"],
        assignee=r["assignee"], status=r["status"],
        priority=r["priority"], category=r["category"],
        due_date=r["due_date"], completed_at=r["completed_at"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


# ── Validation ────────────────────────────────────────────────────

def _require(v, label: str):
    if v in (None, "") or (isinstance(v, str) and not v.strip()):
        raise ValidationError(f"{label} is required")
    return v


def _validate_date(v: Any, label: str) -> str | None:
    if v in (None, "") or (isinstance(v, str) and not v.strip()):
        return None
    s = str(v).strip()
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    return s


def _validate_payload(d: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    title = _require(d.get("title"), "Title").strip()
    if len(title) > MAX_TITLE_LEN:
        raise ValidationError(
            f"Title must be {MAX_TITLE_LEN} characters or fewer")
    out["title"] = title

    desc = (d.get("description") or "").strip()
    out["description"] = desc or None

    owner = (d.get("owner") or "").strip()
    if len(owner) > MAX_OWNER_LEN:
        raise ValidationError(
            f"Owner must be {MAX_OWNER_LEN} characters or fewer")
    out["owner"] = owner

    assignee = (d.get("assignee") or "").strip()
    if len(assignee) > MAX_OWNER_LEN:
        raise ValidationError(
            f"Assignee must be {MAX_OWNER_LEN} characters or fewer")
    out["assignee"] = assignee or None

    status = (d.get("status") or DEFAULT_STATUS).strip()
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    out["status"] = status

    pri = (d.get("priority") or DEFAULT_PRIORITY).strip()
    if pri not in PRIORITIES:
        raise ValidationError(
            f"Priority must be one of: {', '.join(PRIORITIES)}")
    out["priority"] = pri

    cat = (d.get("category") or "").strip()
    if len(cat) > MAX_CATEGORY_LEN:
        raise ValidationError(
            f"Category must be {MAX_CATEGORY_LEN} characters or fewer")
    out["category"] = cat or None

    out["due_date"] = _validate_date(d.get("due_date"), "Due date")
    return out


# ── CRUD ──────────────────────────────────────────────────────────

def create_todo(d: dict[str, Any]) -> Todo:
    init_db()
    p = _validate_payload(d)
    completed_at: str | None = None
    if p["status"] == "Done":
        completed_at = _date.today().isoformat()
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO todos
                 (title, description, owner, assignee, status, priority,
                  category, due_date, completed_at,
                  created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["title"], p["description"], p["owner"], p["assignee"],
             p["status"], p["priority"], p["category"], p["due_date"],
             completed_at),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_todo(new_id)
    assert out is not None
    logger.info("Created todo #%d %r (%s)", new_id, p["title"], p["status"])
    return out


def get_todo(todo_id: int) -> Todo | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM todos WHERE todo_id=?", (todo_id,)).fetchone()
    return _row(r) if r else None


def list_todos(
    *,
    status: str | None = None,
    owner: str | None = None,
    assignee: str | None = None,
    priority: str | None = None,
    category: str | None = None,
    open_only: bool = False,
    overdue_only: bool = False,
    due_on: str | None = None,
    due_by: str | None = None,
) -> list[Todo]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if status:
        if status not in STATUSES:
            raise ValidationError(
                f"Status must be one of: {', '.join(STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if owner:
        clauses.append("owner = ?")
        args.append(owner.strip())
    if assignee:
        clauses.append("assignee = ?")
        args.append(assignee.strip())
    if priority:
        if priority not in PRIORITIES:
            raise ValidationError(
                f"Priority must be one of: {', '.join(PRIORITIES)}")
        clauses.append("priority = ?")
        args.append(priority)
    if category:
        clauses.append("category = ?")
        args.append(category.strip())
    if open_only:
        placeholders = ",".join("?" for _ in OPEN_STATUSES)
        clauses.append(f"status IN ({placeholders})")
        args.extend(OPEN_STATUSES)
    if overdue_only:
        today = _date.today().isoformat()
        clauses.append("due_date IS NOT NULL")
        clauses.append("due_date < ?")
        args.append(today)
        placeholders = ",".join("?" for _ in OPEN_STATUSES)
        clauses.append(f"status IN ({placeholders})")
        args.extend(OPEN_STATUSES)
    if due_on:
        d = _validate_date(due_on, "due_on")
        clauses.append("due_date = ?")
        args.append(d)
    if due_by:
        d = _validate_date(due_by, "due_by")
        clauses.append("due_date IS NOT NULL")
        clauses.append("due_date <= ?")
        args.append(d)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM todos {where} "
           "ORDER BY "
           "CASE status WHEN 'Done' THEN 1 WHEN 'Cancelled' THEN 1 "
           "            ELSE 0 END, "
           "CASE priority WHEN 'Urgent' THEN 0 "
           "              WHEN 'High'   THEN 1 "
           "              WHEN 'Normal' THEN 2 "
           "              ELSE 3 END, "
           "COALESCE(due_date, '9999-12-31') ASC, "
           "todo_id DESC")
    with _connect() as conn:
        return [_row(r) for r in conn.execute(sql, args).fetchall()]


def search_todos(q: str) -> list[Todo]:
    init_db()
    q = (q or "").strip()
    if not q:
        return list_todos()
    like = f"%{q}%"
    with _connect() as conn:
        rows = conn.execute(
            """SELECT * FROM todos
                WHERE title LIKE ? OR description LIKE ?
                    OR category LIKE ? OR owner LIKE ?
                    OR assignee LIKE ?
                ORDER BY todo_id DESC""",
            (like, like, like, like, like)).fetchall()
    return [_row(r) for r in rows]


def update_todo(todo_id: int, d: dict[str, Any]) -> Todo:
    init_db()
    existing = get_todo(todo_id)
    if existing is None:
        raise ValidationError(f"No todo with id {todo_id}")
    merged = {
        "title":       d.get("title", existing.title),
        "description": d.get("description", existing.description),
        "owner":       d.get("owner", existing.owner),
        "assignee":    d.get("assignee", existing.assignee),
        "status":      d.get("status", existing.status),
        "priority":    d.get("priority", existing.priority),
        "category":    d.get("category", existing.category),
        "due_date":    d.get("due_date", existing.due_date),
    }
    p = _validate_payload(merged)
    if p["status"] == "Done":
        completed_at = existing.completed_at or _date.today().isoformat()
    else:
        completed_at = None
    with _connect() as conn:
        conn.execute(
            """UPDATE todos SET
                 title=?, description=?, owner=?, assignee=?, status=?,
                 priority=?, category=?, due_date=?, completed_at=?,
                 updated_at=datetime('now')
               WHERE todo_id=?""",
            (p["title"], p["description"], p["owner"], p["assignee"],
             p["status"], p["priority"], p["category"], p["due_date"],
             completed_at, todo_id),
        )
        conn.commit()
    out = get_todo(todo_id)
    assert out is not None
    logger.info("Updated todo #%d (status=%s)", todo_id, out.status)
    return out


def set_status(todo_id: int, status: str) -> Todo:
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    return update_todo(todo_id, {"status": status})


def mark_done(todo_id: int) -> Todo:
    return set_status(todo_id, "Done")


def reopen(todo_id: int) -> Todo:
    return set_status(todo_id, "Open")


def delete_todo(todo_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM todos WHERE todo_id=?", (todo_id,))
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted todo #%d", todo_id)
            return True
        return False


def clear_completed(*, owner: str | None = None) -> int:
    """Remove Done/Cancelled todos. Returns the number deleted."""
    init_db()
    args: list[Any] = []
    sql = "DELETE FROM todos WHERE status IN ('Done', 'Cancelled')"
    if owner:
        sql += " AND owner = ?"
        args.append(owner.strip())
    with _connect() as conn:
        cur = conn.execute(sql, args)
        conn.commit()
        n = cur.rowcount
    if n:
        logger.info("Cleared %d completed todo(s)", n)
    return n


# ── Summary ──────────────────────────────────────────────────────

def summary(*, owner: str | None = None) -> Summary:
    init_db()
    today = _date.today()
    today_s = today.isoformat()
    import datetime as _dt
    cutoff = (today + _dt.timedelta(days=7)).isoformat()

    args: list[Any] = []
    sql = "SELECT * FROM todos"
    if owner:
        sql += " WHERE owner = ?"
        args.append(owner.strip())
    with _connect() as conn:
        rows = [_row(r) for r in conn.execute(sql, args).fetchall()]

    by_pri = {p: 0 for p in PRIORITIES}
    by_owner: dict[str, int] = {}
    by_cat: dict[str, int] = {}
    open_n = in_prog = blocked = done_n = cancelled = 0
    overdue_n = due_today = due_7d = 0
    for t in rows:
        by_pri[t.priority] = by_pri.get(t.priority, 0) + 1
        o = t.owner or "(none)"
        by_owner[o] = by_owner.get(o, 0) + 1
        if t.category:
            by_cat[t.category] = by_cat.get(t.category, 0) + 1
        if t.status == "Open":
            open_n += 1
        elif t.status == "In Progress":
            in_prog += 1
        elif t.status == "Blocked":
            blocked += 1
        elif t.status == "Done":
            done_n += 1
        elif t.status == "Cancelled":
            cancelled += 1
        if t.is_open and t.due_date:
            if t.due_date < today_s:
                overdue_n += 1
            elif t.due_date == today_s:
                due_today += 1
            elif t.due_date <= cutoff:
                due_7d += 1
    return Summary(
        total=len(rows), open=open_n, in_progress=in_prog, blocked=blocked,
        done=done_n, cancelled=cancelled,
        overdue=overdue_n, due_today=due_today, due_within_7d=due_7d,
        by_priority=by_pri, by_owner=by_owner, by_category=by_cat,
    )
