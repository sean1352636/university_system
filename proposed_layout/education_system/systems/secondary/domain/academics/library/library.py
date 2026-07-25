"""Library catalogue + loan ledger for the Secondary School System.

Two tables:

* ``library_books``  — one row per title. ``copies_total`` is the total
                        owned; ``copies_available`` is the live count
                        adjusted by loans/returns.
* ``library_loans``  — one row per pupil borrowing. Statuses: Out,
                        Returned, Overdue (computed), Lost.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import sqlite3
from collections import Counter
from dataclasses import dataclass
from typing import Any

from education_system.systems.secondary.domain.learners.pupils.pupils import (
    ValidationError, _connect as _pupils_connect,
)

logger = logging.getLogger(__name__)

CATEGORIES: tuple[str, ...] = (
    "Fiction", "Non-Fiction", "Reference", "Textbook",
    "Biography", "Periodical", "Other")
DEFAULT_CATEGORY: str = "Fiction"

LOAN_STATUSES: tuple[str, ...] = ("Out", "Returned", "Overdue", "Lost")
DEFAULT_LOAN_STATUS: str = "Out"

DEFAULT_LOAN_DAYS = 14

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ISBN_RE = re.compile(r"^[0-9Xx\-]{10,17}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS library_books (
    book_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    isbn             TEXT,
    title            TEXT NOT NULL,
    author           TEXT,
    category         TEXT NOT NULL DEFAULT 'Fiction',
    year_published   INTEGER,
    copies_total     INTEGER NOT NULL DEFAULT 1,
    copies_available INTEGER NOT NULL DEFAULT 1,
    location         TEXT,
    is_active        INTEGER NOT NULL DEFAULT 1,
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    updated_at       TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS library_loans (
    loan_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id          INTEGER NOT NULL,
    pupil_id         TEXT NOT NULL,
    loan_date        TEXT NOT NULL DEFAULT (date('now')),
    due_date         TEXT NOT NULL,
    returned_date    TEXT,
    status           TEXT NOT NULL DEFAULT 'Out',
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    updated_at       TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (book_id) REFERENCES library_books(book_id)
);

CREATE INDEX IF NOT EXISTS idx_library_isbn ON library_books(isbn);
CREATE INDEX IF NOT EXISTS idx_library_active ON library_books(is_active);
CREATE INDEX IF NOT EXISTS idx_loans_pupil ON library_loans(pupil_id);
CREATE INDEX IF NOT EXISTS idx_loans_status ON library_loans(status);
"""


@dataclass
class Book:
    book_id: int
    isbn: str | None
    title: str
    author: str | None
    category: str
    year_published: int | None
    copies_total: int
    copies_available: int
    location: str | None
    is_active: bool
    notes: str | None
    created_at: str | None = None
    updated_at: str | None = None


@dataclass
class Loan:
    loan_id: int
    book_id: int
    pupil_id: str
    loan_date: str
    due_date: str
    returned_date: str | None
    status: str
    notes: str | None
    book_title: str | None = None
    book_author: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    @property
    def days_overdue(self) -> int:
        if self.status not in ("Out", "Overdue") or not self.due_date:
            return 0
        try:
            due = _dt.date.fromisoformat(self.due_date)
            return max(0, (_dt.date.today() - due).days)
        except ValueError:
            return 0


_DB_READY = False


def _connect() -> sqlite3.Connection:
    return _pupils_connect()


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    try:
        with _connect() as conn:
            conn.executescript(_SCHEMA)
    except sqlite3.Error:
        logger.exception("Failed to initialise library tables")
        raise
    logger.info("Secondary library tables ready")
    _DB_READY = True


def _row_book(r: sqlite3.Row) -> Book:
    return Book(
        book_id=r["book_id"], isbn=r["isbn"], title=r["title"],
        author=r["author"], category=r["category"],
        year_published=r["year_published"],
        copies_total=r["copies_total"],
        copies_available=r["copies_available"],
        location=r["location"], is_active=bool(r["is_active"]),
        notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _row_loan(r: sqlite3.Row) -> Loan:
    keys = r.keys()
    return Loan(
        loan_id=r["loan_id"], book_id=r["book_id"],
        pupil_id=r["pupil_id"], loan_date=r["loan_date"],
        due_date=r["due_date"], returned_date=r["returned_date"],
        status=r["status"], notes=r["notes"],
        book_title=r["book_title"] if "book_title" in keys else None,
        book_author=r["book_author"] if "book_author" in keys else None,
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _validate_date(value: Any, label: str, *,
                   required: bool = True) -> str | None:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
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


def _validate_book(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    title = (data.get("title") or "").strip()
    if not title:
        raise ValidationError("Title is required")
    if len(title) > 200:
        raise ValidationError("Title must be 200 characters or fewer")
    out["title"] = title

    isbn = (data.get("isbn") or "").strip()
    if isbn:
        if not _ISBN_RE.match(isbn):
            raise ValidationError(
                "ISBN must be 10–17 chars (digits, X or hyphens)")
    out["isbn"] = isbn or None

    cat = (data.get("category") or DEFAULT_CATEGORY).strip()
    if cat not in CATEGORIES:
        raise ValidationError(
            f"Category must be one of {', '.join(CATEGORIES)}")
    out["category"] = cat

    yp = data.get("year_published")
    if yp in (None, "") or (isinstance(yp, str) and not yp.strip()):
        out["year_published"] = None
    else:
        try:
            yr = int(yp)
        except (TypeError, ValueError):
            raise ValidationError(
                "Year published must be a whole number") from None
        if yr < 1000 or yr > 2200:
            raise ValidationError(
                "Year published must be between 1000 and 2200")
        out["year_published"] = yr

    total = data.get("copies_total", 1)
    try:
        total = int(total) if total not in (None, "") else 1
    except (TypeError, ValueError):
        raise ValidationError("Copies total must be a whole number") from None
    if total < 1 or total > 10000:
        raise ValidationError("Copies total must be between 1 and 10000")
    out["copies_total"] = total

    out["author"]   = (data.get("author") or "").strip() or None
    out["location"] = (data.get("location") or "").strip() or None
    is_active = data.get("is_active")
    out["is_active"] = True if is_active is None else bool(is_active)
    out["notes"]    = (data.get("notes") or "").strip() or None
    return out


# ── Book CRUD ────────────────────────────────────────────────────

def create_book(data: dict[str, Any]) -> Book:
    init_db()
    payload = _validate_book(data)
    try:
        with _connect() as conn:
            if payload["isbn"]:
                dup = conn.execute(
                    "SELECT book_id FROM library_books WHERE isbn = ?",
                    (payload["isbn"],),
                ).fetchone()
                if dup:
                    raise ValidationError(
                        f"A book with ISBN {payload['isbn']!r} already exists "
                        f"(#{dup['book_id']})")
            cur = conn.execute(
                """INSERT INTO library_books
                       (isbn, title, author, category, year_published,
                        copies_total, copies_available, location,
                        is_active, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (payload["isbn"], payload["title"], payload["author"],
                 payload["category"], payload["year_published"],
                 payload["copies_total"], payload["copies_total"],
                 payload["location"],
                 1 if payload["is_active"] else 0, payload["notes"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.Error:
        logger.exception("Failed to create library book")
        raise
    rec = get_book(new_id)
    assert rec is not None
    logger.info("Created library book #%d %r (copies=%d, active=%s)",
                rec.book_id, rec.title, rec.copies_total, rec.is_active)
    return rec


def get_book(book_id: int) -> Book | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                "SELECT * FROM library_books WHERE book_id = ?",
                (book_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get_book(%s) failed", book_id)
        raise
    return _row_book(r) if r else None


def list_books(*, active_only: bool = False,
               category: str | None = None,
               available_only: bool = False,
               query: str | None = None) -> list[Book]:
    init_db()
    where: list[str] = []
    params: list[Any] = []
    if active_only:
        where.append("is_active = 1")
    if available_only:
        where.append("copies_available > 0")
    if category:
        if category not in CATEGORIES:
            raise ValidationError(
                f"Category filter must be one of "
                f"{', '.join(CATEGORIES)}")
        where.append("category = ?")
        params.append(category)
    if query:
        q = f"%{query.strip()}%"
        where.append("(title LIKE ? OR author LIKE ? OR isbn LIKE ?)")
        params.extend([q, q, q])
    sql = "SELECT * FROM library_books"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY title COLLATE NOCASE"
    try:
        with _connect() as conn:
            return [_row_book(r)
                    for r in conn.execute(sql, tuple(params)).fetchall()]
    except sqlite3.Error:
        logger.exception("list_books failed")
        raise


def update_book(book_id: int, data: dict[str, Any]) -> Book:
    init_db()
    existing = get_book(book_id)
    if existing is None:
        raise ValidationError(f"No book #{book_id}")
    merged = {
        "isbn":           data.get("isbn", existing.isbn),
        "title":          data.get("title", existing.title),
        "author":         data.get("author", existing.author),
        "category":       data.get("category", existing.category),
        "year_published": data.get("year_published",
                                     existing.year_published),
        "copies_total":   data.get("copies_total", existing.copies_total),
        "location":       data.get("location", existing.location),
        "is_active":      data.get("is_active", existing.is_active),
        "notes":          data.get("notes", existing.notes),
    }
    payload = _validate_book(merged)
    # If copies_total changes, adjust copies_available by the delta
    # (clamped to >= 0). Out loans are unaffected.
    out_loans = existing.copies_total - existing.copies_available
    new_available = max(0, payload["copies_total"] - out_loans)
    try:
        with _connect() as conn:
            if payload["isbn"] and payload["isbn"] != existing.isbn:
                dup = conn.execute(
                    "SELECT book_id FROM library_books "
                    "WHERE isbn = ? AND book_id <> ?",
                    (payload["isbn"], book_id),
                ).fetchone()
                if dup:
                    raise ValidationError(
                        f"A book with ISBN {payload['isbn']!r} already exists "
                        f"(#{dup['book_id']})")
            conn.execute(
                """UPDATE library_books SET
                       isbn = ?, title = ?, author = ?, category = ?,
                       year_published = ?, copies_total = ?,
                       copies_available = ?, location = ?,
                       is_active = ?, notes = ?,
                       updated_at = datetime('now')
                   WHERE book_id = ?""",
                (payload["isbn"], payload["title"], payload["author"],
                 payload["category"], payload["year_published"],
                 payload["copies_total"], new_available,
                 payload["location"],
                 1 if payload["is_active"] else 0, payload["notes"],
                 book_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to update book #%d", book_id)
        raise
    rec = get_book(book_id)
    assert rec is not None
    logger.info("Updated book #%d %r (copies %d/%d, active=%s)",
                rec.book_id, rec.title, rec.copies_available,
                rec.copies_total, rec.is_active)
    return rec


def toggle_active(book_id: int) -> Book:
    existing = get_book(book_id)
    if existing is None:
        raise ValidationError(f"No book #{book_id}")
    return update_book(book_id, {"is_active": not existing.is_active})


def delete_book(book_id: int) -> bool:
    init_db()
    existing = get_book(book_id)
    if existing is None:
        return False
    try:
        with _connect() as conn:
            on_loan = conn.execute(
                "SELECT COUNT(*) FROM library_loans "
                "WHERE book_id = ? AND status IN ('Out', 'Overdue')",
                (book_id,),
            ).fetchone()[0]
            if on_loan:
                raise ValidationError(
                    f"{existing.title!r} has {on_loan} active loan(s) — "
                    f"return or mark lost first")
            # Drop loan history first, then the book itself (the FK
            # on loans.book_id would otherwise reject the parent delete).
            conn.execute(
                "DELETE FROM library_loans WHERE book_id = ?", (book_id,))
            cur = conn.execute(
                "DELETE FROM library_books WHERE book_id = ?", (book_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Failed to delete book #%d", book_id)
        raise
    if deleted:
        logger.info("Deleted library book #%d %r (and loan history)",
                    book_id, existing.title)
    return deleted


# ── Loans ────────────────────────────────────────────────────────

def _refresh_overdue() -> None:
    """Mark Out loans as Overdue if due_date < today."""
    today = _dt.date.today().isoformat()
    try:
        with _connect() as conn:
            conn.execute(
                "UPDATE library_loans SET status = 'Overdue', "
                "updated_at = datetime('now') "
                "WHERE status = 'Out' AND due_date < ?",
                (today,),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("_refresh_overdue failed")
        raise


def lend(book_id: int, pupil_id: str, *,
         loan_date: str | None = None,
         due_date: str | None = None,
         notes: str | None = None) -> Loan:
    init_db()
    book = get_book(book_id)
    if book is None:
        raise ValidationError(f"No book #{book_id}")
    if not book.is_active:
        raise ValidationError(
            f"{book.title!r} is inactive — re-activate first")
    if book.copies_available < 1:
        raise ValidationError(
            f"{book.title!r} has no available copies")
    pid = (pupil_id or "").strip()
    if not pid:
        raise ValidationError("Pupil ID is required")
    from education_system.systems.secondary.domain.learners.pupils import (
        pupils as pupils_data,
    )
    if pupils_data.get_pupil(pid) is None:
        raise ValidationError(f"No pupil with id {pid}")
    ldate = _validate_date(loan_date or _dt.date.today().isoformat(),
                            "Loan date")
    if due_date:
        ddate = _validate_date(due_date, "Due date")
    else:
        try:
            ddate = (_dt.date.fromisoformat(ldate)
                     + _dt.timedelta(days=DEFAULT_LOAN_DAYS)).isoformat()
        except ValueError:
            raise ValidationError("Loan date is not a real date") from None
    if ddate < ldate:
        raise ValidationError("Due date cannot be before loan date")
    try:
        with _connect() as conn:
            cur = conn.execute(
                """INSERT INTO library_loans
                       (book_id, pupil_id, loan_date, due_date,
                        status, notes)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (book_id, pid, ldate, ddate, DEFAULT_LOAN_STATUS,
                 (notes or "").strip() or None),
            )
            conn.execute(
                "UPDATE library_books SET "
                "copies_available = copies_available - 1, "
                "updated_at = datetime('now') WHERE book_id = ?",
                (book_id,),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.Error:
        logger.exception("Failed to lend book %d to %s", book_id, pid)
        raise
    rec = get_loan(new_id)
    assert rec is not None
    logger.info("Lent book #%d to pupil %s (loan #%d, due %s)",
                book_id, pid, rec.loan_id, rec.due_date)
    return rec


def return_loan(loan_id: int, *,
                returned_date: str | None = None,
                notes: str | None = None) -> Loan:
    init_db()
    loan = get_loan(loan_id)
    if loan is None:
        raise ValidationError(f"No loan #{loan_id}")
    if loan.status not in ("Out", "Overdue"):
        raise ValidationError(
            f"Loan #{loan_id} is {loan.status} — cannot return")
    rdate = _validate_date(returned_date or _dt.date.today().isoformat(),
                            "Returned date")
    try:
        with _connect() as conn:
            conn.execute(
                "UPDATE library_loans SET status = 'Returned', "
                "returned_date = ?, "
                "notes = COALESCE(?, notes), "
                "updated_at = datetime('now') WHERE loan_id = ?",
                (rdate, (notes or "").strip() or None, loan_id),
            )
            conn.execute(
                "UPDATE library_books SET "
                "copies_available = MIN(copies_total, "
                "                       copies_available + 1), "
                "updated_at = datetime('now') WHERE book_id = ?",
                (loan.book_id,),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to return loan #%d", loan_id)
        raise
    rec = get_loan(loan_id)
    assert rec is not None
    logger.info("Returned loan #%d (book #%d, pupil %s)",
                loan_id, loan.book_id, loan.pupil_id)
    return rec


def mark_lost(loan_id: int, *, notes: str | None = None) -> Loan:
    init_db()
    loan = get_loan(loan_id)
    if loan is None:
        raise ValidationError(f"No loan #{loan_id}")
    if loan.status not in ("Out", "Overdue"):
        raise ValidationError(
            f"Loan #{loan_id} is {loan.status} — cannot mark lost")
    try:
        with _connect() as conn:
            conn.execute(
                "UPDATE library_loans SET status = 'Lost', "
                "notes = COALESCE(?, notes), "
                "updated_at = datetime('now') WHERE loan_id = ?",
                ((notes or "").strip() or None, loan_id),
            )
            # Reduce copies_total AND copies_available by 1.
            book = get_book(loan.book_id)
            if book and book.copies_total > 0:
                new_total = book.copies_total - 1
                new_avail = max(0, book.copies_available)
                conn.execute(
                    "UPDATE library_books SET copies_total = ?, "
                    "copies_available = MIN(?, ?), "
                    "updated_at = datetime('now') WHERE book_id = ?",
                    (new_total, new_avail, new_total, loan.book_id),
                )
            conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to mark loan #%d lost", loan_id)
        raise
    rec = get_loan(loan_id)
    assert rec is not None
    logger.info("Marked loan #%d as Lost (book #%d, pupil %s)",
                loan_id, loan.book_id, loan.pupil_id)
    return rec


def get_loan(loan_id: int) -> Loan | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                """SELECT l.*, b.title AS book_title,
                          b.author AS book_author
                   FROM library_loans l
                   LEFT JOIN library_books b ON b.book_id = l.book_id
                   WHERE l.loan_id = ?""",
                (loan_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get_loan(%s) failed", loan_id)
        raise
    return _row_loan(r) if r else None


def list_loans(*, status: str | None = None,
               pupil_id: str | None = None,
               book_id: int | None = None,
               refresh_overdue: bool = True) -> list[Loan]:
    init_db()
    if refresh_overdue:
        _refresh_overdue()
    where: list[str] = []
    params: list[Any] = []
    if status:
        if status not in LOAN_STATUSES:
            raise ValidationError(
                f"Status filter must be one of "
                f"{', '.join(LOAN_STATUSES)}")
        where.append("l.status = ?")
        params.append(status)
    if pupil_id:
        where.append("l.pupil_id = ?")
        params.append(pupil_id.strip())
    if book_id is not None:
        where.append("l.book_id = ?")
        params.append(int(book_id))
    sql = ("""SELECT l.*, b.title AS book_title,
                     b.author AS book_author
              FROM library_loans l
              LEFT JOIN library_books b ON b.book_id = l.book_id""")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY l.loan_date DESC, l.loan_id DESC"
    try:
        with _connect() as conn:
            return [_row_loan(r)
                    for r in conn.execute(sql, tuple(params)).fetchall()]
    except sqlite3.Error:
        logger.exception("list_loans failed")
        raise


def overview() -> dict[str, Any]:
    init_db()
    _refresh_overdue()
    try:
        with _connect() as conn:
            book_row = conn.execute(
                """SELECT COUNT(*) AS total,
                          SUM(is_active) AS active,
                          SUM(copies_total) AS copies,
                          SUM(copies_available) AS available
                   FROM library_books""",
            ).fetchone()
            loan_rows = conn.execute(
                "SELECT status, COUNT(*) AS n FROM library_loans "
                "GROUP BY status",
            ).fetchall()
    except sqlite3.Error:
        logger.exception("library overview failed")
        raise
    return {
        "books_total":   int(book_row["total"] or 0),
        "books_active":  int(book_row["active"] or 0),
        "copies_total":  int(book_row["copies"] or 0),
        "copies_avail":  int(book_row["available"] or 0),
        "loans":         {s: 0 for s in LOAN_STATUSES} | {
            r["status"]: r["n"] for r in loan_rows},
    }
