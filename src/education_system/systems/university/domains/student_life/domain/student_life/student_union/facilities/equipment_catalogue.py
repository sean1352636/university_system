"""Read side of the Student Union equipment store, plus reservations.

The equipment itself lives in ``union_equipment`` and loans in
``equipment_checkouts`` (both owned by ``student_union_core``; check-out
and return are written by ``facility_management`` and the checkout
dialogs). This module is what the browse / search / details screens use
to look at that data, and it owns the one thing those tables cannot
hold: a request to borrow an item on future dates
(``su_equipment_reservations``) and a saved search
(``su_equipment_saved_searches``).

Every function takes an open connection and leaves commit to the
caller, except the writers, which commit their own row.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Iterable, Optional

# availability_status values the SU writes, and how screens label them.
STATUS_LABELS = {
    "available": "Available",
    "checked_out": "Checked Out",
    "maintenance": "Maintenance",
    "reserved": "Reserved",
    "retired": "Retired",
}
_LABEL_TO_STATUS = {v.lower(): k for k, v in STATUS_LABELS.items()}

RESERVATION_OPEN = ("pending", "approved")


def ensure_schema(conn) -> None:
    """Create the reservation and saved-search tables if missing."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS su_equipment_reservations (
            reservation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            equipment_id INTEGER NOT NULL,
            requester_id TEXT NOT NULL,
            pickup_date TEXT NOT NULL,
            return_date TEXT NOT NULL,
            purpose TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            decided_by TEXT,
            decided_at TEXT,
            FOREIGN KEY (equipment_id) REFERENCES union_equipment (equipment_id)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_su_equipment_reservations_item "
        "ON su_equipment_reservations (equipment_id, status)"
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS su_equipment_saved_searches (
            search_id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id TEXT NOT NULL,
            keyword TEXT,
            category TEXT,
            status TEXT,
            condition_status TEXT,
            created_at TEXT NOT NULL
        )
        """
    )


def status_label(status: Optional[str]) -> str:
    return STATUS_LABELS.get((status or "").lower(), (status or "Unknown").replace("_", " ").title())


def status_from_label(label: Optional[str]) -> Optional[str]:
    """Map a combobox label back to the stored value; None for 'any'."""
    if not label:
        return None
    key = label.strip().lower()
    if key in ("all", "any", "all status", "all statuses"):
        return None
    return _LABEL_TO_STATUS.get(key, key.replace(" ", "_"))


def _is_any(value: Optional[str]) -> bool:
    return not value or value.strip().lower() in ("all", "any", "all categories")


def categories(conn) -> list[str]:
    rows = conn.execute(
        "SELECT DISTINCT category FROM union_equipment "
        "WHERE category IS NOT NULL AND TRIM(category) <> '' ORDER BY category"
    ).fetchall()
    return [r[0] for r in rows]


def conditions(conn) -> list[str]:
    rows = conn.execute(
        "SELECT DISTINCT condition_status FROM union_equipment "
        "WHERE condition_status IS NOT NULL AND TRIM(condition_status) <> '' "
        "ORDER BY condition_status"
    ).fetchall()
    return [r[0] for r in rows]


def search(conn, *, keyword: Optional[str] = None, category: Optional[str] = None,
           status: Optional[str] = None, condition: Optional[str] = None) -> list[dict]:
    """Equipment matching the filters, with its most recent checkout date.

    ``category``/``condition`` accept the combobox 'All'/'Any' values;
    ``status`` is a stored value (use :func:`status_from_label`).
    """
    clauses, params = [], []
    if keyword and keyword.strip():
        like = f"%{keyword.strip()}%"
        clauses.append(
            "(e.equipment_name LIKE ? OR e.description LIKE ? "
            "OR e.serial_number LIKE ? OR e.category LIKE ?)"
        )
        params += [like, like, like, like]
    if not _is_any(category):
        clauses.append("e.category = ?")
        params.append(category)
    if status:
        clauses.append("LOWER(e.availability_status) = ?")
        params.append(status.lower())
    if not _is_any(condition):
        clauses.append("LOWER(e.condition_status) = ?")
        params.append(condition.lower())
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    # db-audit: ignore[DBW001] - clauses are fixed literals, values bound
    rows = conn.execute(
        f"""
        SELECT e.equipment_id, e.equipment_name, e.category, e.condition_status,
               e.location, e.availability_status,
               (SELECT MAX(c.checkout_date) FROM equipment_checkouts c
                 WHERE c.equipment_id = e.equipment_id) AS last_checkout
        FROM union_equipment e
        {where}
        ORDER BY e.category, e.equipment_name
        """,
        params,
    ).fetchall()
    keys = ("equipment_id", "name", "category", "condition", "location",
            "status", "last_checkout")
    return [dict(zip(keys, tuple(r))) for r in rows]


def _person_name(conn, owner_id: Optional[str]) -> str:
    if not owner_id:
        return "Unknown"
    owner_id = str(owner_id)
    if owner_id.startswith("user:"):
        return owner_id[len("user:"):]
    row = conn.execute(
        "SELECT first_name, last_name FROM students WHERE student_id = ?", (owner_id,)
    ).fetchone()
    if row and (row[0] or row[1]):
        return f"{row[0] or ''} {row[1] or ''}".strip()
    return owner_id


def details(conn, equipment_id: int) -> Optional[dict]:
    """Everything the details screen shows for one item, or None."""
    row = conn.execute(
        """
        SELECT equipment_id, equipment_name, category, description, serial_number,
               purchase_date, condition_status, location, availability_status,
               maintenance_due, replacement_cost
        FROM union_equipment WHERE equipment_id = ?
        """,
        (equipment_id,),
    ).fetchone()
    if not row:
        return None
    keys = ("equipment_id", "name", "category", "description", "serial_number",
            "purchase_date", "condition", "location", "status",
            "maintenance_due", "replacement_cost")
    info = dict(zip(keys, tuple(row)))
    info["times_borrowed"] = conn.execute(
        "SELECT COUNT(*) FROM equipment_checkouts WHERE equipment_id = ?",
        (equipment_id,),
    ).fetchone()[0]
    info["history"] = checkout_history(conn, equipment_id, limit=10)
    info["last_checkout"] = info["history"][0] if info["history"] else None
    info["reservations"] = open_reservations(conn, equipment_id)
    return info


def checkout_history(conn, equipment_id: int, limit: int = 10) -> list[dict]:
    rows = conn.execute(
        """
        SELECT checkout_id, borrower_id, checkout_date, expected_return,
               actual_return, condition_out, condition_in, status
        FROM equipment_checkouts
        WHERE equipment_id = ?
        ORDER BY checkout_date DESC
        LIMIT ?
        """,
        (equipment_id, int(limit)),
    ).fetchall()
    out = []
    for r in rows:
        rec = dict(zip(("checkout_id", "borrower_id", "checkout_date", "expected_return",
                        "actual_return", "condition_out", "condition_in", "status"),
                       tuple(r)))
        rec["borrower"] = _person_name(conn, rec["borrower_id"])
        rec["days"] = _days_between(rec["checkout_date"], rec["actual_return"])
        rec["late"] = _was_late(rec["expected_return"], rec["actual_return"])
        out.append(rec)
    return out


def _parse_day(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "")[:19]).date()
    except ValueError:
        try:
            return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
        except ValueError:
            return None


def _days_between(start: Optional[str], end: Optional[str]) -> Optional[int]:
    a, b = _parse_day(start), _parse_day(end)
    if a and b:
        return max((b - a).days, 0)
    return None


def _was_late(expected: Optional[str], actual: Optional[str]) -> Optional[bool]:
    e, a = _parse_day(expected), _parse_day(actual)
    if e and a:
        return a > e
    return None


def open_reservations(conn, equipment_id: int) -> list[dict]:
    ensure_schema(conn)
    rows = conn.execute(
        """
        SELECT reservation_id, requester_id, pickup_date, return_date, purpose, status
        FROM su_equipment_reservations
        WHERE equipment_id = ? AND status IN ('pending', 'approved')
          AND return_date >= date('now')
        ORDER BY pickup_date
        """,
        (equipment_id,),
    ).fetchall()
    return [dict(zip(("reservation_id", "requester_id", "pickup_date", "return_date",
                      "purpose", "status"), tuple(r))) for r in rows]


def _validate_dates(pickup: str, return_date: str) -> tuple[date, date]:
    try:
        p = datetime.strptime(pickup.strip(), "%Y-%m-%d").date()
        r = datetime.strptime(return_date.strip(), "%Y-%m-%d").date()
    except (AttributeError, ValueError):
        raise ValueError("Dates must be in YYYY-MM-DD format.")
    if p < date.today():
        raise ValueError("The pickup date cannot be in the past.")
    if r < p:
        raise ValueError("The return date must be on or after the pickup date.")
    return p, r


def reserve(conn, *, equipment_id: int, requester_id: str, pickup_date: str,
            return_date: str, purpose: str = "") -> int:
    """Record a reservation request and return its id.

    Refuses dates that overlap another open reservation for the item, or
    that start before a current loan is due back. Raises ``ValueError``
    with a message fit to show the user.
    """
    if not requester_id:
        raise ValueError("You must be signed in to reserve equipment.")
    ensure_schema(conn)
    p, r = _validate_dates(pickup_date, return_date)
    item = conn.execute(
        "SELECT equipment_name, availability_status FROM union_equipment "
        "WHERE equipment_id = ?",
        (equipment_id,),
    ).fetchone()
    if not item:
        raise ValueError("That equipment no longer exists.")
    if (item[1] or "").lower() in ("retired",):
        raise ValueError(f"{item[0]} has been retired and cannot be reserved.")

    clash = conn.execute(
        """
        SELECT pickup_date, return_date FROM su_equipment_reservations
        WHERE equipment_id = ? AND status IN ('pending', 'approved')
          AND NOT (return_date < ? OR pickup_date > ?)
        LIMIT 1
        """,
        (equipment_id, p.isoformat(), r.isoformat()),
    ).fetchone()
    if clash:
        raise ValueError(
            f"{item[0]} is already requested from {clash[0]} to {clash[1]}. "
            "Choose dates outside that window."
        )
    loan = conn.execute(
        """
        SELECT expected_return FROM equipment_checkouts
        WHERE equipment_id = ? AND actual_return IS NULL
          AND COALESCE(status, 'checked_out') = 'checked_out'
        ORDER BY checkout_date DESC LIMIT 1
        """,
        (equipment_id,),
    ).fetchone()
    due = _parse_day(loan[0]) if loan else None
    if due and p <= due:
        raise ValueError(
            f"{item[0]} is on loan until {due.isoformat()}. "
            "Choose a pickup date after it is due back."
        )

    cur = conn.execute(
        """
        INSERT INTO su_equipment_reservations
            (equipment_id, requester_id, pickup_date, return_date, purpose,
             status, created_at)
        VALUES (?, ?, ?, ?, ?, 'pending', ?)
        """,
        (equipment_id, requester_id, p.isoformat(), r.isoformat(),
         (purpose or "").strip() or None, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    )
    conn.commit()
    return cur.lastrowid


def my_reservations(conn, requester_id: str) -> list[dict]:
    ensure_schema(conn)
    rows = conn.execute(
        """
        SELECT r.reservation_id, e.equipment_name, r.pickup_date, r.return_date,
               r.status, r.purpose
        FROM su_equipment_reservations r
        JOIN union_equipment e ON e.equipment_id = r.equipment_id
        WHERE r.requester_id = ?
        ORDER BY r.pickup_date DESC
        """,
        (requester_id,),
    ).fetchall()
    return [dict(zip(("reservation_id", "equipment", "pickup_date", "return_date",
                      "status", "purpose"), tuple(r))) for r in rows]


def save_search(conn, *, owner_id: str, keyword: str = "", category: str = "",
                status: str = "", condition: str = "") -> int:
    if not owner_id:
        raise ValueError("You must be signed in to save a search.")
    ensure_schema(conn)
    norm = [(v or "").strip() or None for v in (keyword, category, status, condition)]
    norm = [None if v and v.lower() in ("any", "all", "all categories", "all status") else v
            for v in norm]
    existing = conn.execute(
        """
        SELECT search_id FROM su_equipment_saved_searches
        WHERE owner_id = ? AND keyword IS ? AND category IS ? AND status IS ?
          AND condition_status IS ?
        """,
        (owner_id, *norm),
    ).fetchone()
    if existing:
        return existing[0]
    cur = conn.execute(
        """
        INSERT INTO su_equipment_saved_searches
            (owner_id, keyword, category, status, condition_status, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (owner_id, *norm, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    )
    conn.commit()
    return cur.lastrowid


def saved_searches(conn, owner_id: str) -> list[dict]:
    ensure_schema(conn)
    rows = conn.execute(
        "SELECT search_id, keyword, category, status, condition_status, created_at "
        "FROM su_equipment_saved_searches WHERE owner_id = ? ORDER BY created_at DESC",
        (owner_id,),
    ).fetchall()
    return [dict(zip(("search_id", "keyword", "category", "status", "condition",
                      "created_at"), tuple(r))) for r in rows]


def with_any(values: Iterable[str], first: str) -> tuple[str, ...]:
    """Combobox values: the 'any' entry followed by the real ones."""
    return (first, *values)


__all__ = [
    "ensure_schema", "categories", "conditions", "search", "details",
    "checkout_history", "open_reservations", "reserve", "my_reservations",
    "save_search", "saved_searches", "status_label", "status_from_label",
    "with_any", "STATUS_LABELS",
]
