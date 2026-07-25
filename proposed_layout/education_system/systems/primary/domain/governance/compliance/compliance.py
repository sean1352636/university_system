"""Compliance register for the Primary School System.

A single ``compliance_items`` table tracking everything that needs a
periodic review or sign-off: policy renewals, mandatory training,
inspection follow-ups, GDPR retention reviews, safeguarding audits.

Each item has:

* ``category``    — Policy / Training / Inspection / Data / Safeguarding
                    / Health & Safety / Finance / Other.
* ``status``      — stored value; ``view_item`` / ``list_views``
                    expose a *derived* status that flips items to
                    "Overdue" when ``next_review`` is in the past.
* ``frequency``   — Once / Monthly / Termly / Annual / Biennial.
* ``due_date``    — when the item must be actioned by.
* ``last_review`` — when the item was last signed off (sets the clock
                    for the next review when frequency is recurring).
* ``next_review`` — when the next review falls; auto-bumped on
                    sign-off via :func:`mark_reviewed`.

Cascades: items are independent (no FKs into other tables).
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.systems.primary.infrastructure import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.COMPLIANCE_DB

CATEGORIES: tuple[str, ...] = (
    "Policy", "Training", "Inspection", "Data",
    "Safeguarding", "Health & Safety", "Finance", "Other",
)
STATUSES: tuple[str, ...] = (
    "Compliant", "Action required", "In progress", "Withdrawn",
)
DERIVED_STATUSES: tuple[str, ...] = (*STATUSES, "Overdue")
DEFAULT_STATUS: str = "Action required"

FREQUENCIES: tuple[str, ...] = (
    "Once", "Monthly", "Termly", "Annual", "Biennial",
)
DEFAULT_FREQUENCY: str = "Annual"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS compliance_items (
    item_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    category     TEXT NOT NULL,
    title        TEXT NOT NULL,
    owner        TEXT,
    status       TEXT NOT NULL DEFAULT 'Action required',
    frequency    TEXT NOT NULL DEFAULT 'Annual',
    due_date     TEXT,
    last_review  TEXT,
    next_review  TEXT,
    notes        TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    updated_at   TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_comp_category ON compliance_items(category);
CREATE INDEX IF NOT EXISTS idx_comp_status   ON compliance_items(status);
CREATE INDEX IF NOT EXISTS idx_comp_next     ON compliance_items(next_review);
"""


# ── Result types ───────────────────────────────────────────────────

@dataclass
class Item:
    item_id: int
    category: str
    title: str
    owner: str | None
    status: str
    frequency: str
    due_date: str | None
    last_review: str | None
    next_review: str | None
    notes: str | None
    created_at: str
    updated_at: str


@dataclass
class ItemView:
    item: Item
    derived_status: str   # "Overdue" if next_review/due_date is past, else stored
    days_until_due: int | None


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
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Compliance schema ready at %s", DB_PATH)

    _DB_READY = True


def _row(r: sqlite3.Row) -> Item:
    return Item(
        item_id=r["item_id"],
        category=r["category"],
        title=r["title"],
        owner=r["owner"],
        status=r["status"],
        frequency=r["frequency"],
        due_date=r["due_date"],
        last_review=r["last_review"],
        next_review=r["next_review"],
        notes=r["notes"],
        created_at=r["created_at"],
        updated_at=r["updated_at"],
    )


# ── Validation ─────────────────────────────────────────────────────

class ValidationError(ValueError):
    """Raised for invalid compliance input."""


def _validate_date(value: Any, label: str, *,
                    required: bool = False) -> str | None:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        if required:
            raise ValidationError(f"{label} is required")
        return None
    s = str(value).strip()
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    return s


def _validate_status(value: Any) -> str:
    s = (value or "").strip()
    if s not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    return s


def _validate_category(value: Any) -> str:
    s = (value or "").strip()
    if s not in CATEGORIES:
        raise ValidationError(
            f"Category must be one of: {', '.join(CATEGORIES)}")
    return s


def _validate_frequency(value: Any) -> str:
    s = (value or "").strip()
    if s not in FREQUENCIES:
        raise ValidationError(
            f"Frequency must be one of: {', '.join(FREQUENCIES)}")
    return s


def _validate_payload(data: dict[str, Any], *, partial: bool = False) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if "category" in data or not partial:
        out["category"] = _validate_category(data.get("category"))
    if "title" in data or not partial:
        title = (data.get("title") or "").strip()
        if not title:
            raise ValidationError("Title is required")
        if len(title) > 200:
            raise ValidationError("Title must be 200 chars or fewer")
        out["title"] = title
    if "owner" in data:
        owner = (data.get("owner") or "").strip() or None
        if owner and len(owner) > 100:
            raise ValidationError("Owner must be 100 chars or fewer")
        out["owner"] = owner
    if "status" in data or not partial:
        out["status"] = _validate_status(
            data.get("status") or DEFAULT_STATUS)
    if "frequency" in data or not partial:
        out["frequency"] = _validate_frequency(
            data.get("frequency") or DEFAULT_FREQUENCY)
    if "due_date" in data:
        out["due_date"] = _validate_date(data.get("due_date"), "Due date")
    if "last_review" in data:
        out["last_review"] = _validate_date(
            data.get("last_review"), "Last review")
    if "next_review" in data:
        out["next_review"] = _validate_date(
            data.get("next_review"), "Next review")
    if "notes" in data:
        notes = (data.get("notes") or "").strip() or None
        if notes and len(notes) > 1000:
            raise ValidationError("Notes must be 1000 chars or fewer")
        out["notes"] = notes
    return out


# ── Frequency helpers ──────────────────────────────────────────────

_FREQ_DAYS: dict[str, int] = {
    "Once": 0,
    "Monthly": 30,
    "Termly": 120,
    "Annual": 365,
    "Biennial": 730,
}


def _bump(date_s: str, frequency: str) -> str | None:
    """Return ``date_s`` + frequency interval (ISO date), or None for 'Once'."""
    days = _FREQ_DAYS.get(frequency, 0)
    if days <= 0:
        return None
    try:
        d = _dt.date.fromisoformat(date_s)
    except ValueError:
        return None
    return (d + _dt.timedelta(days=days)).isoformat()


# ── CRUD ───────────────────────────────────────────────────────────

def create_item(data: dict[str, Any]) -> Item:
    init_db()
    cleaned = _validate_payload(data, partial=False)
    # If next_review wasn't supplied but last_review + frequency are, derive.
    if not cleaned.get("next_review") and cleaned.get("last_review"):
        bumped = _bump(cleaned["last_review"], cleaned["frequency"])
        if bumped:
            cleaned["next_review"] = bumped
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO compliance_items
                (category, title, owner, status, frequency,
                 due_date, last_review, next_review, notes)
               VALUES (:category, :title, :owner, :status, :frequency,
                       :due_date, :last_review, :next_review, :notes)""",
            {
                "category":    cleaned["category"],
                "title":       cleaned["title"],
                "owner":       cleaned.get("owner"),
                "status":      cleaned["status"],
                "frequency":   cleaned["frequency"],
                "due_date":    cleaned.get("due_date"),
                "last_review": cleaned.get("last_review"),
                "next_review": cleaned.get("next_review"),
                "notes":       cleaned.get("notes"),
            })
        item_id = cur.lastrowid
        conn.commit()
    out = get_item(item_id)
    assert out is not None
    logger.info("Created compliance item #%d (%s)", item_id, cleaned["title"])
    return out


def get_item(item_id: int) -> Item | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM compliance_items WHERE item_id = ?",
            (item_id,)).fetchone()
        return _row(r) if r else None


def list_items(
    *,
    category: str | None = None,
    status: str | None = None,
    owner: str | None = None,
    overdue_only: bool = False,
    query: str | None = None,
) -> list[Item]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if category:
        clauses.append("category = ?")
        args.append(_validate_category(category))
    if status:
        if status not in STATUSES:
            raise ValidationError(
                f"Status must be one of: {', '.join(STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if owner:
        clauses.append("owner LIKE ?")
        args.append(f"%{owner.strip()}%")
    if overdue_only:
        today = _dt.date.today().isoformat()
        clauses.append(
            "((next_review IS NOT NULL AND next_review < ?) "
            "OR (next_review IS NULL AND due_date IS NOT NULL AND due_date < ?)) "
            "AND status NOT IN ('Withdrawn')")
        args.extend([today, today])
    if query:
        like = f"%{query.strip()}%"
        clauses.append("(title LIKE ? OR notes LIKE ? OR owner LIKE ?)")
        args.extend([like, like, like])
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM compliance_items {where} "
           "ORDER BY COALESCE(next_review, due_date, '9999-12-31') ASC, "
           "        item_id ASC")
    with _connect() as conn:
        return [_row(r) for r in conn.execute(sql, args).fetchall()]


def update_item(item_id: int, data: dict[str, Any]) -> Item:
    init_db()
    existing = get_item(item_id)
    if existing is None:
        raise ValidationError(f"No compliance item #{item_id}")
    cleaned = _validate_payload(data, partial=True)
    if not cleaned:
        return existing
    sets = ", ".join(f"{k} = :{k}" for k in cleaned)
    cleaned["item_id"] = item_id
    with _connect() as conn:
        conn.execute(
            f"UPDATE compliance_items SET {sets}, "
            "updated_at = datetime('now') WHERE item_id = :item_id",
            cleaned)
        conn.commit()
    out = get_item(item_id)
    assert out is not None
    logger.info("Updated compliance item #%d", item_id)
    return out


def delete_item(item_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM compliance_items WHERE item_id = ?",
            (item_id,))
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted compliance item #%d", item_id)
            return True
        return False


def mark_reviewed(item_id: int, *,
                   reviewed_on: str | None = None,
                   notes: str | None = None) -> Item:
    """Stamp ``last_review`` (default today), bump ``next_review`` by
    the item's frequency, and flip status to 'Compliant'."""
    init_db()
    existing = get_item(item_id)
    if existing is None:
        raise ValidationError(f"No compliance item #{item_id}")
    today = reviewed_on or _dt.date.today().isoformat()
    last = _validate_date(today, "Reviewed on", required=True)
    assert last is not None
    nxt = _bump(last, existing.frequency)
    return update_item(item_id, {
        "last_review": last,
        "next_review": nxt,
        "status": "Compliant",
        **({"notes": notes} if notes is not None else {}),
    })


# ── Views ──────────────────────────────────────────────────────────

def _view(item: Item, today: _dt.date) -> ItemView:
    derived = item.status
    days: int | None = None
    target = item.next_review or item.due_date
    if target:
        try:
            t = _dt.date.fromisoformat(target)
            days = (t - today).days
            if days < 0 and item.status not in ("Withdrawn",):
                derived = "Overdue"
        except ValueError:
            pass
    return ItemView(item=item, derived_status=derived, days_until_due=days)


def view_item(item_id: int) -> ItemView | None:
    item = get_item(item_id)
    if item is None:
        return None
    return _view(item, _dt.date.today())


def list_views(**kwargs) -> list[ItemView]:
    today = _dt.date.today()
    return [_view(i, today) for i in list_items(**kwargs)]


# ── Summary ────────────────────────────────────────────────────────

@dataclass
class Summary:
    total: int
    by_category: dict[str, int]
    by_status: dict[str, int]      # derived status (Overdue included)
    overdue: int
    due_soon: int                  # within 30 days, not yet overdue
    no_review_date: int


def summary(*, due_soon_days: int = 30) -> Summary:
    init_db()
    views = list_views()
    by_cat: dict[str, int] = {c: 0 for c in CATEGORIES}
    by_status: dict[str, int] = {s: 0 for s in DERIVED_STATUSES}
    overdue = 0
    due_soon = 0
    no_review = 0
    for v in views:
        by_cat[v.item.category] = by_cat.get(v.item.category, 0) + 1
        by_status[v.derived_status] = by_status.get(v.derived_status, 0) + 1
        if v.derived_status == "Overdue":
            overdue += 1
        elif v.days_until_due is not None and 0 <= v.days_until_due <= due_soon_days:
            due_soon += 1
        if not (v.item.next_review or v.item.due_date):
            no_review += 1
    return Summary(
        total=len(views),
        by_category=by_cat,
        by_status=by_status,
        overdue=overdue,
        due_soon=due_soon,
        no_review_date=no_review,
    )
