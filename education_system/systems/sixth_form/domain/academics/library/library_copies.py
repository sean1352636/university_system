"""Per-copy inventory register (items 28, 37, 40, 41, 43).

This is an *adjunct* to the ``copies_total`` / ``copies_available``
counters on ``library_books`` — those remain the source of truth for
lending availability. ``library_copies`` records each physical item so
the library can track barcodes, condition and acquisition, run a
stock-take, and weed individual copies. Barcode-issued loans carry the
``copy_id`` (see ``library.issue``) so a scanned return finds the exact
loan.
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

COPY_CONDITIONS: tuple[str, ...] = (
    "New", "Good", "Worn", "Damaged", "Withdrawn",
)
COPY_STATUSES: tuple[str, ...] = (
    "Available", "On Loan", "Withdrawn", "Lost", "Missing",
)


@dataclass
class Copy:
    copy_id: int
    book_id: int
    barcode: str | None
    condition: str
    status: str
    acquired_on: str | None
    notes: str | None
    created_at: str
    updated_at: str


def _row(r) -> Copy:
    return Copy(
        copy_id=r["copy_id"], book_id=r["book_id"],
        barcode=r["barcode"], condition=r["condition"],
        status=r["status"], acquired_on=r["acquired_on"],
        notes=r["notes"], created_at=r["created_at"],
        updated_at=r["updated_at"])


def _today() -> str:
    return _dt.date.today().isoformat()


def add_copy(book_id: int, *, barcode: str | None = None,
             condition: str = "Good",
             acquired_on: str | None = None,
             notes: str | None = None) -> Copy:
    _lib.init_db()
    if _lib.get_book(book_id) is None:
        raise ValidationError(f"No book #{book_id}")
    if condition not in COPY_CONDITIONS:
        raise ValidationError(
            f"Condition must be one of: {', '.join(COPY_CONDITIONS)}")
    bc = (barcode or "").strip() or None
    with _lib._connect() as conn:
        if bc and conn.execute(
                "SELECT 1 FROM library_copies WHERE barcode = ?",
                (bc,)).fetchone():
            raise ValidationError(f"Barcode {bc} is already in use")
        cur = conn.execute(
            "INSERT INTO library_copies "
            "(book_id, barcode, condition, status, acquired_on, "
            " notes, created_at, updated_at) "
            "VALUES (?, ?, ?, 'Available', ?, ?, "
            "        datetime('now'), datetime('now'))",
            (int(book_id), bc, condition, acquired_on or _today(),
             (notes or "").strip() or None))
        cid = cur.lastrowid
        conn.execute(
            "INSERT INTO library_copy_condition_history "
            "(copy_id, condition, changed_on, note) "
            "VALUES (?, ?, ?, 'Initial')",
            (cid, condition, _today()))
        conn.commit()
    logger.info("Added copy #%d to book #%d (barcode=%s)",
                cid, book_id, bc)
    out = get_copy(cid)
    assert out is not None
    return out


def get_copy(copy_id: int) -> Copy | None:
    _lib.init_db()
    with _lib._connect() as conn:
        r = conn.execute(
            "SELECT * FROM library_copies WHERE copy_id = ?",
            (copy_id,)).fetchone()
    return _row(r) if r else None


def find_by_barcode(barcode: str) -> Copy | None:
    _lib.init_db()
    bc = (barcode or "").strip()
    if not bc:
        return None
    with _lib._connect() as conn:
        r = conn.execute(
            "SELECT * FROM library_copies WHERE barcode = ?",
            (bc,)).fetchone()
    return _row(r) if r else None


def list_copies(*, book_id: int | None = None,
                status: str | None = None,
                condition: str | None = None) -> list[Copy]:
    _lib.init_db()
    clauses, args = [], []
    if book_id is not None:
        clauses.append("book_id = ?")
        args.append(int(book_id))
    if status:
        clauses.append("status = ?")
        args.append(status)
    if condition:
        clauses.append("condition = ?")
        args.append(condition)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _lib._connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM library_copies {where} "
            "ORDER BY book_id, copy_id", args).fetchall()
    return [_row(r) for r in rows]


def set_condition(copy_id: int, condition: str, *,
                  note: str | None = None) -> Copy:
    copy = get_copy(copy_id)
    if copy is None:
        raise ValidationError(f"No copy #{copy_id}")
    if condition not in COPY_CONDITIONS:
        raise ValidationError(
            f"Condition must be one of: {', '.join(COPY_CONDITIONS)}")
    new_status = "Withdrawn" if condition == "Withdrawn" else copy.status
    with _lib._connect() as conn:
        conn.execute(
            "UPDATE library_copies SET condition = ?, status = ?, "
            "updated_at = datetime('now') WHERE copy_id = ?",
            (condition, new_status, copy_id))
        conn.execute(
            "INSERT INTO library_copy_condition_history "
            "(copy_id, condition, changed_on, note) "
            "VALUES (?, ?, ?, ?)",
            (copy_id, condition, _today(),
             (note or "").strip() or None))
        conn.commit()
    out = get_copy(copy_id)
    assert out is not None
    return out


def condition_history(copy_id: int) -> list[dict]:
    _lib.init_db()
    with _lib._connect() as conn:
        rows = conn.execute(
            "SELECT condition, changed_on, note "
            "FROM library_copy_condition_history "
            "WHERE copy_id = ? ORDER BY history_id", (copy_id,)
        ).fetchall()
    return [{"condition": r["condition"], "changed_on": r["changed_on"],
             "note": r["note"]} for r in rows]


def withdraw_copy(copy_id: int, *, reason: str) -> Copy:
    """Weed a single physical copy (item 38, per-copy).

    Marks it Withdrawn and, if it was an available copy, reduces the
    book's total/available counters to match."""
    if not (reason or "").strip():
        raise ValidationError("A reason is required to withdraw a copy")
    copy = get_copy(copy_id)
    if copy is None:
        raise ValidationError(f"No copy #{copy_id}")
    if copy.status == "Withdrawn":
        raise ValidationError("Copy is already withdrawn")
    was_available = copy.status == "Available"
    set_condition(copy_id, "Withdrawn", note=f"Withdrawn: {reason}")
    if was_available:
        with _lib._connect() as conn:
            conn.execute(
                "UPDATE library_books SET "
                "copies_total = MAX(0, copies_total - 1), "
                "copies_available = MAX(0, copies_available - 1), "
                "updated_at = datetime('now') WHERE book_id = ?",
                (copy.book_id,))
            conn.commit()
    logger.info("Withdrew copy #%d (book #%d): %s",
                copy_id, copy.book_id, reason)
    out = get_copy(copy_id)
    assert out is not None
    return out


def mark_missing(copy_id: int, *, missing: bool = True) -> Copy:
    """Flag/clear a copy as missing during a stock-take (item 37)."""
    copy = get_copy(copy_id)
    if copy is None:
        raise ValidationError(f"No copy #{copy_id}")
    target = "Missing" if missing else "Available"
    _lib_set_status(copy_id, target)
    return get_copy(copy_id)  # type: ignore[return-value]


def _lib_set_status(copy_id: int, status: str) -> None:
    with _lib._connect() as conn:
        conn.execute(
            "UPDATE library_copies SET status = ?, "
            "updated_at = datetime('now') WHERE copy_id = ?",
            (status, copy_id))
        conn.commit()


# ── Withdrawal at the title level (item 38) ───────────────────────

def withdraw_book(book_id: int, *, reason: str) -> "_lib.Book":
    if not (reason or "").strip():
        raise ValidationError("A reason is required to withdraw a book")
    book = _lib.get_book(book_id)
    if book is None:
        raise ValidationError(f"No book #{book_id}")
    note = f"Withdrawn: {reason}"
    if book.notes:
        note = f"{book.notes} | {note}"
    out = _lib.update_book(book_id, {"status": "Withdrawn",
                                     "notes": note})
    for c in list_copies(book_id=book_id):
        if c.status != "Withdrawn":
            set_condition(c.copy_id, "Withdrawn",
                          note=f"Title withdrawn: {reason}")
    logger.info("Withdrew book #%d: %s", book_id, reason)
    return out


# ── Barcode circulation (item 43) ─────────────────────────────────

def issue_by_barcode(barcode: str, student_id: str, **kwargs) -> "_lib.Loan":
    copy = find_by_barcode(barcode)
    if copy is None:
        raise ValidationError(f"No copy with barcode {barcode}")
    if copy.status not in ("Available",):
        raise ValidationError(
            f"Copy {barcode} is not available (status={copy.status})")
    return _lib.issue(copy.book_id, student_id, copy_id=copy.copy_id,
                      **kwargs)


def return_by_barcode(barcode: str, **kwargs) -> "_lib.Loan":
    copy = find_by_barcode(barcode)
    if copy is None:
        raise ValidationError(f"No copy with barcode {barcode}")
    # Prefer the loan tied to this exact copy.
    active = [l for l in _lib.list_loans(book_id=copy.book_id,
                                         active_only=True)]
    by_copy = [l for l in active if l.copy_id == copy.copy_id]
    if by_copy:
        return _lib.return_loan(by_copy[0].loan_id, **kwargs)
    if len(active) == 1:
        return _lib.return_loan(active[0].loan_id, **kwargs)
    raise ValidationError(
        f"Barcode {barcode}: {len(active)} copies of this title are "
        "out — return by loan id to disambiguate")


# ── Stock-take / audit (item 37) ──────────────────────────────────

def stock_take_report() -> list[dict]:
    """Reconcile each book's counters against its registered copies.

    Flags books where the live copies counter and the per-copy register
    disagree, or where copies are missing — the working list for a
    physical shelf audit."""
    _lib.init_db()
    out: list[dict] = []
    for b in _lib.list_books():
        copies = list_copies(book_id=b.book_id)
        active = [c for c in copies if c.status != "Withdrawn"]
        missing = sum(1 for c in copies if c.status == "Missing")
        on_loan = sum(1 for c in copies if c.status == "On Loan")
        discrepancy = (len(active) != b.copies_total) if active else False
        out.append({
            "book_id": b.book_id, "title": b.title,
            "copies_total": b.copies_total,
            "copies_available": b.copies_available,
            "registered": len(active), "missing": missing,
            "on_loan": on_loan,
            "discrepancy": discrepancy or missing > 0,
        })
    return out
