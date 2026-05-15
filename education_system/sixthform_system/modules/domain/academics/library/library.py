"""Library — books / resources catalogue and per-student loans.

Two FK-linked tables:

* ``library_books`` — one row per title. Tracks total copies and how
  many are currently available; the available count is maintained
  automatically by the loan helpers.
* ``library_loans`` — one row per loan. Workflow:
  ``Active → Returned`` (or ``Lost``), with ``Active`` rows whose
  ``due_on`` is in the past surfacing as "Overdue" in the UI.

Cascade: deleting a book wipes its loans; deleting a student wipes
their loans.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import sqlite3
from dataclasses import dataclass
from typing import Any
from education_system.sixthform_system.core import paths
from education_system.sixthform_system.modules.domain.academics.library import (
    library as data,
)

logger = logging.getLogger(__name__)

DB_PATH = paths.LIBRARY_DB


DEFAULT_LOAN_DAYS: int = 14
MAX_RENEWALS: int = 3

ITEM_TYPES: tuple[str, ...] = (
    "Book",
    "Textbook",
    "Reference",
    "Journal",
    "Periodical",
    "Past Papers",
    "Audio",
    "Video / DVD",
    "E-Resource",
    "Equipment",
    "Other",
)
DEFAULT_ITEM_TYPE: str = "Book"

BOOK_STATUSES: tuple[str, ...] = (
    "Available", "Reserved", "Restricted", "Withdrawn", "Lost",
)
DEFAULT_BOOK_STATUS: str = "Available"

LOAN_STATUSES: tuple[str, ...] = (
    "Active", "Returned", "Lost", "Cancelled",
)
DEFAULT_LOAN_STATUS: str = "Active"
ACTIVE_LOAN_STATUSES: tuple[str, ...] = ("Active",)

_ISBN_RE = re.compile(r"^[0-9Xx\-]+$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


_SCHEMA = """
CREATE TABLE IF NOT EXISTS library_books (
    book_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    isbn              TEXT,
    title             TEXT NOT NULL,
    author            TEXT,
    publisher         TEXT,
    publication_year  INTEGER,
    edition           TEXT,
    item_type         TEXT NOT NULL DEFAULT 'Book',
    subject_area      TEXT,
    keywords          TEXT,
    location          TEXT,
    copies_total      INTEGER NOT NULL DEFAULT 1,
    copies_available  INTEGER NOT NULL DEFAULT 1,
    status            TEXT NOT NULL DEFAULT 'Available',
    description       TEXT,
    notes             TEXT,
    created_at        TEXT DEFAULT (datetime('now')),
    updated_at        TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS library_loans (
    loan_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id           INTEGER NOT NULL,
    student_id        TEXT NOT NULL,
    loaned_on         TEXT NOT NULL,
    due_on            TEXT NOT NULL,
    returned_on       TEXT,
    status            TEXT NOT NULL DEFAULT 'Active',
    renewals_count    INTEGER NOT NULL DEFAULT 0,
    issued_by         TEXT,
    returned_by       TEXT,
    notes             TEXT,
    created_at        TEXT DEFAULT (datetime('now')),
    updated_at        TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (book_id) REFERENCES library_books(book_id)
        ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES students(student_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_lb_title    ON library_books(title);
CREATE INDEX IF NOT EXISTS idx_lb_subject  ON library_books(subject_area);
CREATE INDEX IF NOT EXISTS idx_lb_status   ON library_books(status);
CREATE INDEX IF NOT EXISTS idx_ll_book     ON library_loans(book_id);
CREATE INDEX IF NOT EXISTS idx_ll_student  ON library_loans(student_id);
CREATE INDEX IF NOT EXISTS idx_ll_status   ON library_loans(status);
CREATE INDEX IF NOT EXISTS idx_ll_due      ON library_loans(due_on);
"""


@dataclass
class Book:
    book_id: int
    isbn: str | None
    title: str
    author: str | None
    publisher: str | None
    publication_year: int | None
    edition: str | None
    item_type: str
    subject_area: str | None
    keywords: str | None
    location: str | None
    copies_total: int
    copies_available: int
    status: str
    description: str | None
    notes: str | None
    created_at: str
    updated_at: str

    @property
    def is_borrowable(self) -> bool:
        return (self.status == "Available"
                and self.copies_available > 0)


@dataclass
class Loan:
    loan_id: int
    book_id: int
    student_id: str
    loaned_on: str
    due_on: str
    returned_on: str | None
    status: str
    renewals_count: int
    issued_by: str | None
    returned_by: str | None
    notes: str | None
    created_at: str
    updated_at: str

    @property
    def is_active(self) -> bool:
        return self.status in ACTIVE_LOAN_STATUSES

    @property
    def is_overdue(self) -> bool:
        if not self.is_active:
            return False
        return self.due_on < _dt.date.today().isoformat()

    @property
    def days_overdue(self) -> int:
        if not self.is_overdue:
            return 0
        try:
            due = _dt.date.fromisoformat(self.due_on)
            return (_dt.date.today() - due).days
        except ValueError:
            return 0


@dataclass
class LoanRow:
    loan: Loan
    student_name: str
    book_title: str


@dataclass
class Summary:
    total_books: int
    total_copies: int
    copies_on_loan: int
    by_status: dict[str, int]
    by_item_type: dict[str, int]
    total_loans: int
    active_loans: int
    overdue_loans: int
    returned_loans: int
    distinct_borrowers: int


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
    logger.debug("Library schema ready at %s", DB_PATH)

    _DB_READY = True


def _row_book(r: sqlite3.Row) -> Book:
    return Book(
        book_id=r["book_id"], isbn=r["isbn"], title=r["title"],
        author=r["author"], publisher=r["publisher"],
        publication_year=r["publication_year"],
        edition=r["edition"], item_type=r["item_type"],
        subject_area=r["subject_area"], keywords=r["keywords"],
        location=r["location"],
        copies_total=r["copies_total"],
        copies_available=r["copies_available"],
        status=r["status"], description=r["description"],
        notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _row_loan(r: sqlite3.Row) -> Loan:
    return Loan(
        loan_id=r["loan_id"], book_id=r["book_id"],
        student_id=r["student_id"],
        loaned_on=r["loaned_on"], due_on=r["due_on"],
        returned_on=r["returned_on"], status=r["status"],
        renewals_count=r["renewals_count"],
        issued_by=r["issued_by"], returned_by=r["returned_by"],
        notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


# ── Validation ────────────────────────────────────────────────────

class ValidationError(ValueError):
    pass


def _require(value, label: str):
    if value in (None, "") or (isinstance(value, str)
                                  and not value.strip()):
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


def _validate_int(value: Any, label: str, *,
                   min_val: int | None = None,
                   max_val: int | None = None) -> int | None:
    if value in (None, "") or (isinstance(value, str)
                                  and not value.strip()):
        return None
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{label} must be a whole number") from None
    if min_val is not None and n < min_val:
        raise ValidationError(f"{label} must be at least {min_val}")
    if max_val is not None and n > max_val:
        raise ValidationError(f"{label} must be at most {max_val}")
    return n


def _validate_isbn(value: Any) -> str | None:
    if value in (None, "") or (isinstance(value, str)
                                  and not value.strip()):
        return None
    s = str(value).strip()
    if not _ISBN_RE.match(s):
        raise ValidationError(
            "ISBN may only contain digits, X, and hyphens")
    cleaned = s.replace("-", "").upper()
    if len(cleaned) not in (10, 13):
        raise ValidationError(
            "ISBN must be 10 or 13 digits (excluding hyphens)")
    return s


def _validate_book_payload(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["title"] = _require(payload.get("title"), "Title").strip()
    out["isbn"]  = _validate_isbn(payload.get("isbn"))
    out["author"]    = (payload.get("author") or "").strip() or None
    out["publisher"] = (payload.get("publisher")
                          or "").strip() or None
    out["publication_year"] = _validate_int(
        payload.get("publication_year"), "Publication year",
        min_val=1000, max_val=2200)
    out["edition"]      = (payload.get("edition")
                              or "").strip() or None
    itype = (payload.get("item_type") or DEFAULT_ITEM_TYPE).strip()
    if itype not in ITEM_TYPES:
        raise ValidationError(
            f"Item type must be one of: {', '.join(ITEM_TYPES)}")
    out["item_type"] = itype
    out["subject_area"] = (payload.get("subject_area")
                              or "").strip() or None
    out["keywords"]     = (payload.get("keywords")
                              or "").strip() or None
    out["location"]     = (payload.get("location")
                              or "").strip() or None
    out["description"]  = (payload.get("description")
                              or "").strip() or None
    out["notes"]        = (payload.get("notes")
                              or "").strip() or None

    total = _validate_int(payload.get("copies_total"),
                            "Copies total",
                            min_val=0, max_val=10000)
    out["copies_total"] = 1 if total is None else total
    avail = payload.get("copies_available")
    if avail in (None, ""):
        out["copies_available"] = out["copies_total"]
    else:
        out["copies_available"] = _validate_int(
            avail, "Copies available", min_val=0,
            max_val=out["copies_total"])

    status = (payload.get("status") or DEFAULT_BOOK_STATUS).strip()
    if status not in BOOK_STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(BOOK_STATUSES)}")
    out["status"] = status
    return out


def _validate_loan_payload(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    bid = payload.get("book_id")
    if bid in (None, ""):
        raise ValidationError("Book id is required")
    try:
        out["book_id"] = int(bid)
    except (TypeError, ValueError):
        raise ValidationError(
            "Book id must be a number") from None
    if get_book(out["book_id"]) is None:
        raise ValidationError(f"No book #{out['book_id']}")

    sid = _require(payload.get("student_id"), "Student").strip()
    from education_system.sixthform_system.modules.domain.students.students import (
        students as _students,
    )
    if _students.get_student(sid) is None:
        raise ValidationError(f"No student with id {sid}")
    out["student_id"] = sid

    out["loaned_on"] = _validate_date(payload.get("loaned_on"),
                                          "Loaned on",
                                          required=True)
    out["due_on"]    = _validate_date(payload.get("due_on"),
                                          "Due on", required=True)
    if out["due_on"] < out["loaned_on"]:
        raise ValidationError(
            "Due date cannot be before loaned date")
    out["returned_on"] = _validate_date(
        payload.get("returned_on"), "Returned on")
    if out["returned_on"] and out["returned_on"] < out["loaned_on"]:
        raise ValidationError(
            "Returned date cannot be before loaned date")

    status = (payload.get("status") or DEFAULT_LOAN_STATUS).strip()
    if status not in LOAN_STATUSES:
        raise ValidationError(
            f"Loan status must be one of: "
            f"{', '.join(LOAN_STATUSES)}")
    out["status"] = status

    renewals = payload.get("renewals_count")
    out["renewals_count"] = (0 if renewals in (None, "")
                              else _validate_int(
                                renewals, "Renewals",
                                min_val=0, max_val=MAX_RENEWALS) or 0)

    out["issued_by"]   = (payload.get("issued_by")
                            or "").strip() or None
    out["returned_by"] = (payload.get("returned_by")
                            or "").strip() or None
    out["notes"]       = (payload.get("notes") or "").strip() or None
    return out


# ── Book CRUD ─────────────────────────────────────────────────────

def create_book(payload: dict[str, Any]) -> Book:
    init_db()
    p = _validate_book_payload(payload)
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO library_books
                   (isbn, title, author, publisher, publication_year,
                    edition, item_type, subject_area, keywords,
                    location, copies_total, copies_available, status,
                    description, notes, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["isbn"], p["title"], p["author"], p["publisher"],
             p["publication_year"], p["edition"], p["item_type"],
             p["subject_area"], p["keywords"], p["location"],
             p["copies_total"], p["copies_available"],
             p["status"], p["description"], p["notes"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_book(new_id)
    assert out is not None
    logger.info("Created book #%d %r (%d/%d copies, status=%s)",
                new_id, p["title"], p["copies_available"],
                p["copies_total"], p["status"])
    return out


def get_book(book_id: int) -> Book | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM library_books WHERE book_id = ?",
            (book_id,)).fetchone()
        return _row_book(r) if r else None


def list_books(
    *,
    search: str | None = None,
    subject_area: str | None = None,
    item_type: str | None = None,
    status: str | None = None,
    available_only: bool = False,
) -> list[Book]:
    init_db()
    clauses, args = [], []
    if search:
        s = f"%{search.strip()}%"
        clauses.append(
            "(title LIKE ? OR author LIKE ? OR isbn LIKE ? OR "
            "keywords LIKE ?)")
        args.extend([s, s, s, s])
    if subject_area:
        clauses.append("subject_area LIKE ?")
        args.append(f"%{subject_area.strip()}%")
    if item_type:
        if item_type not in ITEM_TYPES:
            raise ValidationError(
                f"Item type must be one of: {', '.join(ITEM_TYPES)}")
        clauses.append("item_type = ?")
        args.append(item_type)
    if status:
        if status not in BOOK_STATUSES:
            raise ValidationError(
                f"Status must be one of: {', '.join(BOOK_STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if available_only:
        clauses.append(
            "status = 'Available' AND copies_available > 0")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM library_books {where} "
           "ORDER BY title ASC, author ASC")
    with _connect() as conn:
        return [_row_book(r)
                for r in conn.execute(sql, args).fetchall()]


def update_book(book_id: int, payload: dict[str, Any]) -> Book:
    init_db()
    existing = get_book(book_id)
    if existing is None:
        raise ValidationError(f"No book #{book_id}")
    merged = {
        "isbn":             payload.get("isbn", existing.isbn),
        "title":            payload.get("title", existing.title),
        "author":           payload.get("author", existing.author),
        "publisher":        payload.get("publisher",
                                        existing.publisher),
        "publication_year": payload.get("publication_year",
                                        existing.publication_year),
        "edition":          payload.get("edition",
                                        existing.edition),
        "item_type":        payload.get("item_type",
                                        existing.item_type),
        "subject_area":     payload.get("subject_area",
                                        existing.subject_area),
        "keywords":         payload.get("keywords",
                                        existing.keywords),
        "location":         payload.get("location",
                                        existing.location),
        "copies_total":     payload.get("copies_total",
                                        existing.copies_total),
        "copies_available": payload.get("copies_available",
                                        existing.copies_available),
        "status":           payload.get("status", existing.status),
        "description":      payload.get("description",
                                        existing.description),
        "notes":            payload.get("notes", existing.notes),
    }
    p = _validate_book_payload(merged)

    # Keep copies_available consistent with current active loans.
    # If a caller manually edits copies_total downward but more are
    # out on loan, raise rather than silently fix it.
    on_loan = _active_loan_count(book_id)
    if p["copies_total"] < on_loan:
        raise ValidationError(
            f"Cannot reduce copies_total below currently-out loans "
            f"({on_loan})")
    if p["copies_available"] + on_loan > p["copies_total"]:
        raise ValidationError(
            f"copies_available ({p['copies_available']}) + "
            f"on-loan ({on_loan}) cannot exceed copies_total "
            f"({p['copies_total']})")

    with _connect() as conn:
        conn.execute(
            """UPDATE library_books SET
                   isbn = ?, title = ?, author = ?, publisher = ?,
                   publication_year = ?, edition = ?, item_type = ?,
                   subject_area = ?, keywords = ?, location = ?,
                   copies_total = ?, copies_available = ?,
                   status = ?, description = ?, notes = ?,
                   updated_at = datetime('now')
               WHERE book_id = ?""",
            (p["isbn"], p["title"], p["author"], p["publisher"],
             p["publication_year"], p["edition"], p["item_type"],
             p["subject_area"], p["keywords"], p["location"],
             p["copies_total"], p["copies_available"],
             p["status"], p["description"], p["notes"], book_id),
        )
        conn.commit()
    out = get_book(book_id)
    assert out is not None
    return out


def set_book_status(book_id: int, status: str) -> Book:
    return update_book(book_id, {"status": status})


def delete_book(book_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM library_books WHERE book_id = ?",
            (book_id,))
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted book #%d (cascade: loans)", book_id)
            return True
        return False


# ── Loan CRUD ─────────────────────────────────────────────────────

def _active_loan_count(book_id: int) -> int:
    init_db()
    with _connect() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM library_loans "
            "WHERE book_id = ? AND status = 'Active'",
            (book_id,)).fetchone()[0]


def issue(book_id: int, student_id: str, *,
          due_on: str | None = None,
          loaned_on: str | None = None,
          issued_by: str | None = None,
          notes: str | None = None) -> Loan:
    """Issue an Available copy to a student."""
    init_db()
    book = get_book(book_id)
    if book is None:
        raise ValidationError(f"No book #{book_id}")
    if not book.is_borrowable:
        raise ValidationError(
            f"Book is not borrowable "
            f"(status={book.status}, available={book.copies_available})")
    loan_date = loaned_on or _dt.date.today().isoformat()
    if due_on is None:
        due_date = (_dt.date.fromisoformat(loan_date)
                    + _dt.timedelta(days=DEFAULT_LOAN_DAYS)).isoformat()
    else:
        due_date = due_on
    loan = create_loan({
        "book_id": book_id, "student_id": student_id,
        "loaned_on": loan_date, "due_on": due_date,
        "status": "Active", "issued_by": issued_by,
        "notes": notes,
    })
    _adjust_available(book_id, -1)
    return loan


def create_loan(payload: dict[str, Any]) -> Loan:
    init_db()
    p = _validate_loan_payload(payload)
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO library_loans
                   (book_id, student_id, loaned_on, due_on,
                    returned_on, status, renewals_count,
                    issued_by, returned_by, notes,
                    created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["book_id"], p["student_id"], p["loaned_on"],
             p["due_on"], p["returned_on"], p["status"],
             p["renewals_count"], p["issued_by"],
             p["returned_by"], p["notes"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_loan(new_id)
    assert out is not None
    logger.info("Created loan #%d (book=%d, student=%s, due=%s)",
                new_id, p["book_id"], p["student_id"],
                p["due_on"])
    return out


def get_loan(loan_id: int) -> Loan | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM library_loans WHERE loan_id = ?",
            (loan_id,)).fetchone()
        return _row_loan(r) if r else None


def list_loans(
    *,
    book_id: int | None = None,
    student_id: str | None = None,
    status: str | None = None,
    active_only: bool = False,
    overdue_only: bool = False,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[Loan]:
    init_db()
    clauses, args = [], []
    if book_id is not None:
        clauses.append("book_id = ?")
        args.append(int(book_id))
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if status:
        if status not in LOAN_STATUSES:
            raise ValidationError(
                f"Loan status must be one of: "
                f"{', '.join(LOAN_STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if active_only:
        clauses.append("status = 'Active'")
    if overdue_only:
        today = _dt.date.today().isoformat()
        clauses.append("status = 'Active' AND due_on < ?")
        args.append(today)
    if date_from:
        clauses.append("loaned_on >= ?")
        args.append(_validate_date(date_from, "date_from"))
    if date_to:
        clauses.append("loaned_on <= ?")
        args.append(_validate_date(date_to, "date_to"))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM library_loans {where} "
           "ORDER BY CASE status WHEN 'Active' THEN 0 ELSE 1 END, "
           "due_on ASC, loan_id ASC")
    with _connect() as conn:
        return [_row_loan(r)
                for r in conn.execute(sql, args).fetchall()]


def list_loans_with_detail(**kwargs) -> list[LoanRow]:
    rows = list_loans(**kwargs)
    if not rows:
        return []
    from education_system.sixthform_system.modules.domain.students.students import (
        students as _students,
    )
    names = {s.student_id: s.full_name
              for s in _students.list_students()}
    titles: dict[int, str] = {}
    with _connect() as conn:
        for r in conn.execute(
                "SELECT book_id, title FROM library_books").fetchall():
            titles[r["book_id"]] = r["title"]
    return [LoanRow(loan=l,
                     student_name=names.get(l.student_id, "(unknown)"),
                     book_title=titles.get(l.book_id,
                                             f"#{l.book_id}"))
            for l in rows]


def _adjust_available(book_id: int, delta: int) -> None:
    init_db()
    with _connect() as conn:
        conn.execute(
            "UPDATE library_books SET "
            "copies_available = MAX(0, "
            "  MIN(copies_total, copies_available + ?)), "
            "updated_at = datetime('now') "
            "WHERE book_id = ?",
            (delta, book_id))
        conn.commit()


def return_loan(loan_id: int, *,
                 returned_on: str | None = None,
                 returned_by: str | None = None) -> Loan:
    init_db()
    existing = get_loan(loan_id)
    if existing is None:
        raise ValidationError(f"No loan #{loan_id}")
    if not existing.is_active:
        raise ValidationError(
            f"Loan is not Active (status={existing.status})")
    payload = {
        "status": "Returned",
        "returned_on": returned_on or _dt.date.today().isoformat(),
        "returned_by": returned_by,
    }
    out = update_loan(loan_id, payload)
    _adjust_available(existing.book_id, +1)
    return out


def renew(loan_id: int, *,
           extension_days: int = DEFAULT_LOAN_DAYS) -> Loan:
    init_db()
    existing = get_loan(loan_id)
    if existing is None:
        raise ValidationError(f"No loan #{loan_id}")
    if not existing.is_active:
        raise ValidationError(
            "Cannot renew a non-active loan")
    if existing.renewals_count >= MAX_RENEWALS:
        raise ValidationError(
            f"Loan has hit the renewals limit ({MAX_RENEWALS})")
    try:
        new_due = (_dt.date.fromisoformat(existing.due_on)
                   + _dt.timedelta(days=extension_days)).isoformat()
    except ValueError:
        raise ValidationError("Could not compute new due date") from None
    return update_loan(loan_id, {
        "due_on": new_due,
        "renewals_count": existing.renewals_count + 1,
    })


def mark_lost(loan_id: int) -> Loan:
    init_db()
    existing = get_loan(loan_id)
    if existing is None:
        raise ValidationError(f"No loan #{loan_id}")
    was_active = existing.is_active
    out = update_loan(loan_id, {"status": "Lost"})
    if was_active:
        # The copy is no longer in circulation — drop total too.
        with _connect() as conn:
            conn.execute(
                "UPDATE library_books SET "
                "copies_total = MAX(0, copies_total - 1), "
                "updated_at = datetime('now') "
                "WHERE book_id = ?", (existing.book_id,))
            conn.commit()
    return out


def update_loan(loan_id: int, payload: dict[str, Any]) -> Loan:
    init_db()
    existing = get_loan(loan_id)
    if existing is None:
        raise ValidationError(f"No loan #{loan_id}")
    merged = {
        "book_id":        existing.book_id,
        "student_id":     existing.student_id,
        "loaned_on":      payload.get("loaned_on",
                                       existing.loaned_on),
        "due_on":         payload.get("due_on", existing.due_on),
        "returned_on":    payload.get("returned_on",
                                       existing.returned_on),
        "status":         payload.get("status", existing.status),
        "renewals_count": payload.get("renewals_count",
                                       existing.renewals_count),
        "issued_by":      payload.get("issued_by",
                                       existing.issued_by),
        "returned_by":    payload.get("returned_by",
                                       existing.returned_by),
        "notes":          payload.get("notes", existing.notes),
    }
    p = _validate_loan_payload(merged)
    with _connect() as conn:
        conn.execute(
            """UPDATE library_loans SET
                   loaned_on = ?, due_on = ?, returned_on = ?,
                   status = ?, renewals_count = ?, issued_by = ?,
                   returned_by = ?, notes = ?,
                   updated_at = datetime('now')
               WHERE loan_id = ?""",
            (p["loaned_on"], p["due_on"], p["returned_on"],
             p["status"], p["renewals_count"], p["issued_by"],
             p["returned_by"], p["notes"], loan_id),
        )
        conn.commit()
    out = get_loan(loan_id)
    assert out is not None
    return out


def delete_loan(loan_id: int) -> bool:
    init_db()
    existing = get_loan(loan_id)
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM library_loans WHERE loan_id = ?",
            (loan_id,))
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted loan #%d", loan_id)
            if existing and existing.is_active:
                _adjust_available(existing.book_id, +1)
            return True
        return False


# ── Summary ───────────────────────────────────────────────────────

def summary() -> Summary:
    init_db()
    books = list_books()
    by_status = {s: 0 for s in BOOK_STATUSES}
    by_type = {t: 0 for t in ITEM_TYPES}
    total_copies = 0
    for b in books:
        by_status[b.status] = by_status.get(b.status, 0) + 1
        by_type[b.item_type] = by_type.get(b.item_type, 0) + 1
        total_copies += b.copies_total

    today = _dt.date.today().isoformat()
    with _connect() as conn:
        tot = conn.execute(
            "SELECT COUNT(*) FROM library_loans"
        ).fetchone()[0]
        active = conn.execute(
            "SELECT COUNT(*) FROM library_loans "
            "WHERE status = 'Active'").fetchone()[0]
        overdue = conn.execute(
            "SELECT COUNT(*) FROM library_loans "
            "WHERE status = 'Active' AND due_on < ?",
            (today,)).fetchone()[0]
        returned = conn.execute(
            "SELECT COUNT(*) FROM library_loans "
            "WHERE status = 'Returned'").fetchone()[0]
        borrowers = conn.execute(
            "SELECT COUNT(DISTINCT student_id) "
            "FROM library_loans WHERE status = 'Active'"
        ).fetchone()[0]

    copies_on_loan = sum(b.copies_total - b.copies_available
                          for b in books)

    return Summary(
        total_books=len(books),
        total_copies=total_copies,
        copies_on_loan=copies_on_loan,
        by_status=by_status,
        by_item_type=by_type,
        total_loans=tot,
        active_loans=active,
        overdue_loans=overdue,
        returned_loans=returned,
        distinct_borrowers=borrowers,
    )
