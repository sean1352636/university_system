"""Acquisitions: suppliers, purchase suggestions / orders, and budgets
(items 34, 35, 36, 39).

An acquisition flows Suggested -> Approved -> Ordered -> Received ->
Catalogued (or Rejected). Cataloguing creates the actual library book
and links it back via ``book_id``. Budgets are per subject-area /
academic-year; spend is computed from acquisitions that have been
ordered or beyond.
"""

from __future__ import annotations

import datetime as _dt
import logging
from dataclasses import dataclass

from education_system.systems.sixth_form.domain.academics.library import (
    library as _lib,
)

logger = logging.getLogger(__name__)

ValidationError = _lib.ValidationError

ACQ_STATUSES: tuple[str, ...] = (
    "Suggested", "Approved", "Ordered", "Received",
    "Catalogued", "Rejected",
)
# Statuses that represent committed spend against a budget.
SPEND_STATUSES: tuple[str, ...] = ("Ordered", "Received", "Catalogued")


def _notify(method: str, *args) -> None:
    """Best-effort call into the sixth-form email system."""
    try:
        from education_system.systems.sixth_form.domain.academics.library import (
            library_notifications as _n,
        )
        getattr(_n, method)(*args)
    except Exception:
        logger.debug("Notification %s skipped", method, exc_info=True)


@dataclass
class Supplier:
    supplier_id: int
    name: str
    contact: str | None
    email: str | None
    phone: str | None
    notes: str | None


@dataclass
class Acquisition:
    acq_id: int
    title: str
    isbn: str | None
    subject_area: str | None
    supplier_id: int | None
    status: str
    quantity: int
    unit_cost: float
    requested_by: str | None
    requested_on: str | None
    academic_year: str | None
    book_id: int | None
    notes: str | None

    @property
    def total_cost(self) -> float:
        return round(self.quantity * self.unit_cost, 2)


# ── Suppliers (item 39) ───────────────────────────────────────────

def add_supplier(name: str, *, contact: str | None = None,
                 email: str | None = None, phone: str | None = None,
                 notes: str | None = None) -> Supplier:
    _lib.init_db()
    if not (name or "").strip():
        raise ValidationError("Supplier name is required")
    with _lib._connect() as conn:
        if conn.execute("SELECT 1 FROM library_suppliers WHERE name = ?",
                        (name.strip(),)).fetchone():
            raise ValidationError(f"Supplier {name!r} already exists")
        cur = conn.execute(
            "INSERT INTO library_suppliers "
            "(name, contact, email, phone, notes, created_at) "
            "VALUES (?, ?, ?, ?, ?, datetime('now'))",
            (name.strip(), (contact or "").strip() or None,
             (email or "").strip() or None,
             (phone or "").strip() or None,
             (notes or "").strip() or None))
        conn.commit()
        sid = cur.lastrowid
    out = get_supplier(sid)
    assert out is not None
    return out


def get_supplier(supplier_id: int) -> Supplier | None:
    _lib.init_db()
    with _lib._connect() as conn:
        r = conn.execute(
            "SELECT * FROM library_suppliers WHERE supplier_id = ?",
            (supplier_id,)).fetchone()
    if r is None:
        return None
    return Supplier(
        supplier_id=r["supplier_id"], name=r["name"],
        contact=r["contact"], email=r["email"], phone=r["phone"],
        notes=r["notes"])


def list_suppliers() -> list[Supplier]:
    _lib.init_db()
    with _lib._connect() as conn:
        rows = conn.execute(
            "SELECT * FROM library_suppliers ORDER BY name").fetchall()
    return [Supplier(
        supplier_id=r["supplier_id"], name=r["name"],
        contact=r["contact"], email=r["email"], phone=r["phone"],
        notes=r["notes"]) for r in rows]


# ── Acquisitions (items 34, 35) ───────────────────────────────────

def _row_acq(r) -> Acquisition:
    return Acquisition(
        acq_id=r["acq_id"], title=r["title"], isbn=r["isbn"],
        subject_area=r["subject_area"], supplier_id=r["supplier_id"],
        status=r["status"], quantity=r["quantity"],
        unit_cost=r["unit_cost"], requested_by=r["requested_by"],
        requested_on=r["requested_on"],
        academic_year=r["academic_year"], book_id=r["book_id"],
        notes=r["notes"])


def suggest(title: str, *, isbn: str | None = None,
            subject_area: str | None = None, quantity: int = 1,
            unit_cost: float = 0.0, supplier_id: int | None = None,
            requested_by: str | None = None,
            academic_year: str | None = None,
            notes: str | None = None) -> Acquisition:
    """Add a purchase suggestion (item 34)."""
    _lib.init_db()
    if not (title or "").strip():
        raise ValidationError("Title is required")
    if int(quantity) <= 0:
        raise ValidationError("Quantity must be at least 1")
    if float(unit_cost) < 0:
        raise ValidationError("Unit cost cannot be negative")
    with _lib._connect() as conn:
        cur = conn.execute(
            "INSERT INTO library_acquisitions "
            "(title, isbn, subject_area, supplier_id, status, "
            " quantity, unit_cost, requested_by, requested_on, "
            " academic_year, notes, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, 'Suggested', ?, ?, ?, ?, ?, ?, "
            "        datetime('now'), datetime('now'))",
            (title.strip(), (isbn or "").strip() or None,
             (subject_area or "").strip() or None, supplier_id,
             int(quantity), round(float(unit_cost), 2),
             (requested_by or "").strip() or None,
             _dt.date.today().isoformat(),
             (academic_year or "").strip() or None,
             (notes or "").strip() or None))
        conn.commit()
        aid = cur.lastrowid
    logger.info("Acquisition suggestion #%d: %r", aid, title)
    out = get_acquisition(aid)
    assert out is not None
    return out


def get_acquisition(acq_id: int) -> Acquisition | None:
    _lib.init_db()
    with _lib._connect() as conn:
        r = conn.execute(
            "SELECT * FROM library_acquisitions WHERE acq_id = ?",
            (acq_id,)).fetchone()
    return _row_acq(r) if r else None


def list_acquisitions(*, status: str | None = None,
                      academic_year: str | None = None
                      ) -> list[Acquisition]:
    _lib.init_db()
    clauses, args = [], []
    if status:
        clauses.append("status = ?")
        args.append(status)
    if academic_year:
        clauses.append("academic_year = ?")
        args.append(academic_year)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _lib._connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM library_acquisitions {where} "
            "ORDER BY CASE status WHEN 'Suggested' THEN 0 "
            "WHEN 'Approved' THEN 1 WHEN 'Ordered' THEN 2 "
            "WHEN 'Received' THEN 3 ELSE 4 END, acq_id DESC",
            args).fetchall()
    return [_row_acq(r) for r in rows]


def set_status(acq_id: int, status: str, *,
               supplier_id: int | None = None) -> Acquisition:
    if status not in ACQ_STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(ACQ_STATUSES)}")
    acq = get_acquisition(acq_id)
    if acq is None:
        raise ValidationError(f"No acquisition #{acq_id}")
    with _lib._connect() as conn:
        if supplier_id is not None:
            conn.execute(
                "UPDATE library_acquisitions SET status = ?, "
                "supplier_id = ?, updated_at = datetime('now') "
                "WHERE acq_id = ?", (status, supplier_id, acq_id))
        else:
            conn.execute(
                "UPDATE library_acquisitions SET status = ?, "
                "updated_at = datetime('now') WHERE acq_id = ?",
                (status, acq_id))
        conn.commit()
    logger.info("Acquisition #%d -> %s", acq_id, status)
    out = get_acquisition(acq_id)
    assert out is not None
    if status != "Suggested":
        _notify("notify_acquisition_update", out)
    return out


def approve(acq_id: int) -> Acquisition:
    return set_status(acq_id, "Approved")


def reject(acq_id: int) -> Acquisition:
    return set_status(acq_id, "Rejected")


def order(acq_id: int, *, supplier_id: int | None = None) -> Acquisition:
    return set_status(acq_id, "Ordered", supplier_id=supplier_id)


def receive(acq_id: int) -> Acquisition:
    return set_status(acq_id, "Received")


def catalogue(acq_id: int, **book_overrides) -> "_lib.Book":
    """Create the library book from a received acquisition and mark it
    Catalogued, linking the new ``book_id``."""
    acq = get_acquisition(acq_id)
    if acq is None:
        raise ValidationError(f"No acquisition #{acq_id}")
    if acq.book_id:
        raise ValidationError("Acquisition is already catalogued")
    payload = {
        "title": acq.title, "isbn": acq.isbn,
        "subject_area": acq.subject_area,
        "copies_total": acq.quantity,
        "copies_available": acq.quantity,
    }
    payload.update(book_overrides)
    book = _lib.create_book(payload)
    with _lib._connect() as conn:
        conn.execute(
            "UPDATE library_acquisitions SET status = 'Catalogued', "
            "book_id = ?, updated_at = datetime('now') "
            "WHERE acq_id = ?", (book.book_id, acq_id))
        conn.commit()
    logger.info("Acquisition #%d catalogued as book #%d",
                acq_id, book.book_id)
    _notify("notify_acquisition_update", get_acquisition(acq_id))
    return book


# ── Budgets (item 36) ─────────────────────────────────────────────

def set_budget(subject_area: str, academic_year: str,
               allocated: float, *, notes: str | None = None) -> None:
    _lib.init_db()
    if not (subject_area or "").strip():
        raise ValidationError("Subject area is required")
    if float(allocated) < 0:
        raise ValidationError("Allocation cannot be negative")
    with _lib._connect() as conn:
        conn.execute(
            "INSERT INTO library_budgets "
            "(subject_area, academic_year, allocated, notes) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(subject_area, academic_year) DO UPDATE SET "
            "allocated = excluded.allocated, notes = excluded.notes",
            (subject_area.strip(), academic_year.strip(),
             round(float(allocated), 2),
             (notes or "").strip() or None))
        conn.commit()


def budget_report(academic_year: str) -> list[dict]:
    """Per subject-area allocation vs committed spend for a year."""
    _lib.init_db()
    with _lib._connect() as conn:
        budgets = conn.execute(
            "SELECT subject_area, allocated FROM library_budgets "
            "WHERE academic_year = ?", (academic_year,)).fetchall()
        spend_rows = conn.execute(
            "SELECT subject_area, "
            "SUM(quantity * unit_cost) AS spent "
            "FROM library_acquisitions "
            "WHERE academic_year = ? AND status IN "
            "('Ordered', 'Received', 'Catalogued') "
            "GROUP BY subject_area", (academic_year,)).fetchall()
    spent = {r["subject_area"]: round(r["spent"] or 0, 2)
             for r in spend_rows}
    out = []
    seen = set()
    for b in budgets:
        sa = b["subject_area"]
        seen.add(sa)
        alloc = round(b["allocated"], 2)
        s = spent.get(sa, 0.0)
        out.append({"subject_area": sa, "allocated": alloc,
                    "spent": s, "remaining": round(alloc - s, 2)})
    # Subjects with spend but no explicit budget row.
    for sa, s in spent.items():
        if sa not in seen:
            out.append({"subject_area": sa or "(unassigned)",
                        "allocated": 0.0, "spent": s,
                        "remaining": round(-s, 2)})
    out.sort(key=lambda d: d["subject_area"])
    return out
