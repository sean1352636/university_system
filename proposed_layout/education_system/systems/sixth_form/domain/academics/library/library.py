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
from education_system.systems.sixth_form.infrastructure import paths
from education_system.systems.sixth_form.domain.academics.library import (
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
    "Active", "Returned", "Returned Damaged", "Lost", "Cancelled",
)
DEFAULT_LOAN_STATUS: str = "Active"
ACTIVE_LOAN_STATUSES: tuple[str, ...] = ("Active",)
RETURNED_LOAN_STATUSES: tuple[str, ...] = ("Returned", "Returned Damaged")

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
    classification    TEXT,
    series            TEXT,
    volume            TEXT,
    cover_image_url   TEXT,
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

-- Key/value settings: per-student loan limit, fine rate + cap,
-- hold-shelf expiry days. Defaults live in SETTING_DEFAULTS.
CREATE TABLE IF NOT EXISTS library_settings (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at TEXT DEFAULT (datetime('now'))
);

-- One row per item_type: loan length, renewal cap, borrowable flag.
CREATE TABLE IF NOT EXISTS library_loan_policies (
    item_type    TEXT PRIMARY KEY,
    loan_days    INTEGER NOT NULL,
    max_renewals INTEGER NOT NULL,
    borrowable   INTEGER NOT NULL DEFAULT 1
);

-- Charges raised against students (overdue / damaged / lost / manual).
CREATE TABLE IF NOT EXISTS library_fines (
    fine_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id    TEXT NOT NULL,
    loan_id       INTEGER,
    reason        TEXT NOT NULL,
    amount        REAL NOT NULL,
    amount_paid   REAL NOT NULL DEFAULT 0,
    amount_waived REAL NOT NULL DEFAULT 0,
    status        TEXT NOT NULL DEFAULT 'Outstanding',
    note          TEXT,
    created_at    TEXT DEFAULT (datetime('now')),
    updated_at    TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (loan_id) REFERENCES library_loans(loan_id)
        ON DELETE SET NULL,
    FOREIGN KEY (student_id) REFERENCES students(student_id)
        ON DELETE CASCADE
);

-- Holds queue. Waiting -> Ready (on hold shelf) -> Collected,
-- or Cancelled / Expired.
CREATE TABLE IF NOT EXISTS library_reservations (
    reservation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id     INTEGER NOT NULL,
    student_id  TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'Waiting',
    reserved_on TEXT NOT NULL,
    ready_on    TEXT,
    expires_on  TEXT,
    notes       TEXT,
    created_at  TEXT DEFAULT (datetime('now')),
    updated_at  TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (book_id) REFERENCES library_books(book_id)
        ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES students(student_id)
        ON DELETE CASCADE
);

-- Normalised tags and the book<->tag join.
CREATE TABLE IF NOT EXISTS library_tags (
    tag_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name   TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS library_book_tags (
    book_id INTEGER NOT NULL,
    tag_id  INTEGER NOT NULL,
    PRIMARY KEY (book_id, tag_id),
    FOREIGN KEY (book_id) REFERENCES library_books(book_id)
        ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES library_tags(tag_id)
        ON DELETE CASCADE
);

-- Audit of notifications sent, with a dedupe key so the same
-- reminder isn't sent twice.
CREATE TABLE IF NOT EXISTS library_notifications (
    notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind           TEXT NOT NULL,
    loan_id        INTEGER,
    reservation_id INTEGER,
    fine_id        INTEGER,
    student_id     TEXT,
    dedupe_key     TEXT,
    sent_at        TEXT NOT NULL,
    created_at     TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_lf_student ON library_fines(student_id);
CREATE INDEX IF NOT EXISTS idx_lf_status  ON library_fines(status);
CREATE INDEX IF NOT EXISTS idx_lr_book    ON library_reservations(book_id);
CREATE INDEX IF NOT EXISTS idx_lr_student ON library_reservations(student_id);
CREATE INDEX IF NOT EXISTS idx_lr_status  ON library_reservations(status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_ln_dedupe
    ON library_notifications(dedupe_key)
    WHERE dedupe_key IS NOT NULL;

-- Physical copy register (adjunct to the copies_total counter): one
-- row per physical item, with its own barcode, condition and status.
CREATE TABLE IF NOT EXISTS library_copies (
    copy_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id     INTEGER NOT NULL,
    barcode     TEXT UNIQUE,
    condition   TEXT NOT NULL DEFAULT 'Good',
    status      TEXT NOT NULL DEFAULT 'Available',
    acquired_on TEXT,
    notes       TEXT,
    created_at  TEXT DEFAULT (datetime('now')),
    updated_at  TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (book_id) REFERENCES library_books(book_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS library_copy_condition_history (
    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
    copy_id    INTEGER NOT NULL,
    condition  TEXT NOT NULL,
    changed_on TEXT NOT NULL,
    note       TEXT,
    FOREIGN KEY (copy_id) REFERENCES library_copies(copy_id)
        ON DELETE CASCADE
);

-- Curated reading lists tied to a subject/course, with required vs
-- recommended items and optional links to assignments.
CREATE TABLE IF NOT EXISTS library_reading_lists (
    list_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    title         TEXT NOT NULL,
    subject       TEXT,
    course_id     INTEGER,
    owner         TEXT,
    academic_year TEXT,
    notes         TEXT,
    created_at    TEXT DEFAULT (datetime('now')),
    updated_at    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS library_reading_list_items (
    item_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    list_id       INTEGER NOT NULL,
    book_id       INTEGER NOT NULL,
    requirement   TEXT NOT NULL DEFAULT 'Recommended',
    assignment_id INTEGER,
    note          TEXT,
    UNIQUE (list_id, book_id),
    FOREIGN KEY (list_id) REFERENCES library_reading_lists(list_id)
        ON DELETE CASCADE,
    FOREIGN KEY (book_id) REFERENCES library_books(book_id)
        ON DELETE CASCADE
);

-- Teacher requests a set of copies of a title for a class by a date.
CREATE TABLE IF NOT EXISTS library_class_sets (
    set_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id      INTEGER NOT NULL,
    course_id    INTEGER,
    subject      TEXT,
    copies_needed INTEGER NOT NULL DEFAULT 1,
    needed_by    TEXT,
    status       TEXT NOT NULL DEFAULT 'Requested',
    requested_by TEXT,
    notes        TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    updated_at   TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (book_id) REFERENCES library_books(book_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS library_suppliers (
    supplier_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    contact     TEXT,
    email       TEXT,
    phone       TEXT,
    notes       TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);

-- Purchase suggestions / orders. Status flows
-- Suggested -> Approved -> Ordered -> Received -> Catalogued
-- (or Rejected). On Catalogued, book_id links the created book.
CREATE TABLE IF NOT EXISTS library_acquisitions (
    acq_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    title        TEXT NOT NULL,
    isbn         TEXT,
    subject_area TEXT,
    supplier_id  INTEGER,
    status       TEXT NOT NULL DEFAULT 'Suggested',
    quantity     INTEGER NOT NULL DEFAULT 1,
    unit_cost    REAL NOT NULL DEFAULT 0,
    requested_by TEXT,
    requested_on TEXT,
    academic_year TEXT,
    book_id      INTEGER,
    notes        TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    updated_at   TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (supplier_id) REFERENCES library_suppliers(supplier_id)
        ON DELETE SET NULL,
    FOREIGN KEY (book_id) REFERENCES library_books(book_id)
        ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS library_budgets (
    budget_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_area  TEXT NOT NULL,
    academic_year TEXT NOT NULL,
    allocated     REAL NOT NULL DEFAULT 0,
    notes         TEXT,
    UNIQUE (subject_area, academic_year)
);

-- Library study-space bookings (silent desks / group rooms), distinct
-- from the system-wide room_booking module for classrooms.
CREATE TABLE IF NOT EXISTS library_study_bookings (
    booking_id INTEGER PRIMARY KEY AUTOINCREMENT,
    space      TEXT NOT NULL,
    student_id TEXT,
    staff      TEXT,
    date       TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time   TEXT NOT NULL,
    purpose    TEXT,
    status     TEXT NOT NULL DEFAULT 'Booked',
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id)
        ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS library_eresource_access (
    access_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id     INTEGER NOT NULL,
    student_id  TEXT,
    accessed_at TEXT NOT NULL,
    FOREIGN KEY (book_id) REFERENCES library_books(book_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_lc_book   ON library_copies(book_id);
CREATE INDEX IF NOT EXISTS idx_lc_status ON library_copies(status);
CREATE INDEX IF NOT EXISTS idx_rli_list  ON library_reading_list_items(list_id);
CREATE INDEX IF NOT EXISTS idx_acq_status ON library_acquisitions(status);
CREATE INDEX IF NOT EXISTS idx_sb_space  ON library_study_bookings(space, date);
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
    classification: str | None
    series: str | None
    volume: str | None
    cover_image_url: str | None
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
    copy_id: int | None = None

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
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    _students.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        _migrate(conn)
        _seed_loan_policies(conn)
    logger.debug("Library schema ready at %s", DB_PATH)

    _DB_READY = True


# Columns added to library_books after its first release. CREATE TABLE
# IF NOT EXISTS won't add these to a pre-existing table, so patch them
# in on startup for older sixthform.db files.
_BOOK_ADDED_COLUMNS: tuple[str, ...] = (
    "classification", "series", "volume", "cover_image_url",
)


def _migrate(conn: sqlite3.Connection) -> None:
    have = {r["name"] for r in conn.execute(
        "PRAGMA table_info(library_books)").fetchall()}
    for col in _BOOK_ADDED_COLUMNS:
        if col not in have:
            conn.execute(
                f"ALTER TABLE library_books ADD COLUMN {col} TEXT")
    loan_cols = {r["name"] for r in conn.execute(
        "PRAGMA table_info(library_loans)").fetchall()}
    if "copy_id" not in loan_cols:
        conn.execute(
            "ALTER TABLE library_loans ADD COLUMN copy_id INTEGER")
    conn.commit()


def _seed_loan_policies(conn: sqlite3.Connection) -> None:
    """Insert a default policy row for any item type missing one."""
    existing = {r["item_type"] for r in conn.execute(
        "SELECT item_type FROM library_loan_policies").fetchall()}
    for itype in ITEM_TYPES:
        if itype in existing:
            continue
        days, renewals, borrowable = _DEFAULT_POLICY.get(
            itype, (DEFAULT_LOAN_DAYS, MAX_RENEWALS, 1))
        conn.execute(
            "INSERT INTO library_loan_policies "
            "(item_type, loan_days, max_renewals, borrowable) "
            "VALUES (?, ?, ?, ?)",
            (itype, days, renewals, borrowable))
    conn.commit()


# item_type -> (loan_days, max_renewals, borrowable)
_DEFAULT_POLICY: dict[str, tuple[int, int, int]] = {
    "Book":         (14, 3, 1),
    "Textbook":     (28, 5, 1),
    "Reference":    (0, 0, 0),
    "Journal":      (7, 1, 1),
    "Periodical":   (7, 1, 1),
    "Past Papers":  (14, 3, 1),
    "Audio":        (7, 2, 1),
    "Video / DVD":  (3, 1, 1),
    "E-Resource":   (0, 0, 0),
    "Equipment":    (3, 1, 1),
    "Other":        (14, 3, 1),
}


def _row_book(r: sqlite3.Row) -> Book:
    return Book(
        book_id=r["book_id"], isbn=r["isbn"], title=r["title"],
        author=r["author"], publisher=r["publisher"],
        publication_year=r["publication_year"],
        edition=r["edition"], item_type=r["item_type"],
        subject_area=r["subject_area"], keywords=r["keywords"],
        location=r["location"],
        classification=r["classification"], series=r["series"],
        volume=r["volume"], cover_image_url=r["cover_image_url"],
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
        copy_id=r["copy_id"],
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


_URL_RE = re.compile(r"^(https?://|/|\.{0,2}/)\S+$", re.IGNORECASE)


def _validate_cover_url(value: Any) -> str | None:
    if value in (None, "") or (isinstance(value, str)
                                  and not value.strip()):
        return None
    s = str(value).strip()
    if not _URL_RE.match(s):
        raise ValidationError(
            "Cover image must be a URL (http/https) or a file path")
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
    out["classification"] = (payload.get("classification")
                              or "").strip() or None
    out["series"]       = (payload.get("series")
                              or "").strip() or None
    out["volume"]       = (payload.get("volume")
                              or "").strip() or None
    out["cover_image_url"] = _validate_cover_url(
        payload.get("cover_image_url"))
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
    from education_system.systems.sixth_form.domain.learners.students import (
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
    cid = payload.get("copy_id")
    out["copy_id"] = None if cid in (None, "") else int(cid)
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
                    location, classification, series, volume,
                    cover_image_url, copies_total, copies_available,
                    status, description, notes, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       ?, ?, ?, datetime('now'), datetime('now'))""",
            (p["isbn"], p["title"], p["author"], p["publisher"],
             p["publication_year"], p["edition"], p["item_type"],
             p["subject_area"], p["keywords"], p["location"],
             p["classification"], p["series"], p["volume"],
             p["cover_image_url"], p["copies_total"],
             p["copies_available"],
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
            "keywords LIKE ? OR series LIKE ? OR classification LIKE ?)")
        args.extend([s, s, s, s, s, s])
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
        "classification":   payload.get("classification",
                                        existing.classification),
        "series":           payload.get("series", existing.series),
        "volume":           payload.get("volume", existing.volume),
        "cover_image_url":  payload.get("cover_image_url",
                                        existing.cover_image_url),
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
                   classification = ?, series = ?, volume = ?,
                   cover_image_url = ?,
                   copies_total = ?, copies_available = ?,
                   status = ?, description = ?, notes = ?,
                   updated_at = datetime('now')
               WHERE book_id = ?""",
            (p["isbn"], p["title"], p["author"], p["publisher"],
             p["publication_year"], p["edition"], p["item_type"],
             p["subject_area"], p["keywords"], p["location"],
             p["classification"], p["series"], p["volume"],
             p["cover_image_url"],
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


def _student_active_loan_count(student_id: str) -> int:
    with _connect() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM library_loans "
            "WHERE student_id = ? AND status = 'Active'",
            (student_id,)).fetchone()[0]


def issue(book_id: int, student_id: str, *,
          due_on: str | None = None,
          loaned_on: str | None = None,
          issued_by: str | None = None,
          notes: str | None = None,
          copy_id: int | None = None,
          override_blocks: bool = False) -> Loan:
    """Issue an Available copy to a student.

    Enforces the per-item-type loan policy (length, borrowable), the
    per-student concurrent-loan limit, and — unless ``override_blocks``
    is set — blocks students who have overdue items or outstanding
    fines above the configured threshold.
    """
    init_db()
    from education_system.systems.sixth_form.domain.academics.library import (
        library_settings as _settings,
        library_fines as _fines,
    )
    book = get_book(book_id)
    if book is None:
        raise ValidationError(f"No book #{book_id}")
    if not book.is_borrowable:
        raise ValidationError(
            f"Book is not borrowable "
            f"(status={book.status}, available={book.copies_available})")

    policy = _settings.get_policy(book.item_type)
    if not policy.borrowable:
        raise ValidationError(
            f"{book.item_type} items are not borrowable")

    # Per-student concurrent loan limit.
    limit = int(_settings.get_setting("loan_limit_per_student"))
    if not override_blocks and limit > 0:
        current = _student_active_loan_count(student_id)
        if current >= limit:
            raise ValidationError(
                f"Student already has {current} active loans "
                f"(limit {limit})")

    # Block on overdue items / outstanding fines (item 6).
    if not override_blocks:
        if _settings.get_setting("block_issue_on_overdue"):
            overdue = list_loans(student_id=student_id,
                                 overdue_only=True)
            if overdue:
                raise ValidationError(
                    f"Student has {len(overdue)} overdue item(s) — "
                    "resolve before issuing (or override)")
        threshold = float(
            _settings.get_setting("block_issue_fine_threshold"))
        balance = _fines.student_balance(student_id)
        if threshold >= 0 and balance > threshold:
            raise ValidationError(
                f"Student owes {balance:.2f} in fines "
                f"(limit {threshold:.2f}) — settle before issuing "
                "(or override)")

    loan_date = loaned_on or _dt.date.today().isoformat()
    if due_on is None:
        due_date = (_dt.date.fromisoformat(loan_date)
                    + _dt.timedelta(days=policy.loan_days)).isoformat()
    else:
        due_date = due_on
    loan = create_loan({
        "book_id": book_id, "student_id": student_id,
        "loaned_on": loan_date, "due_on": due_date,
        "status": "Active", "issued_by": issued_by,
        "notes": notes, "copy_id": copy_id,
    })
    _adjust_available(book_id, -1)
    if copy_id is not None:
        _set_copy_status(copy_id, "On Loan")
    _notify("notify_loan_receipt", loan)
    return loan


def _set_copy_status(copy_id: int, status: str) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE library_copies SET status = ?, "
            "updated_at = datetime('now') WHERE copy_id = ?",
            (status, copy_id))
        conn.commit()


def create_loan(payload: dict[str, Any]) -> Loan:
    init_db()
    p = _validate_loan_payload(payload)
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO library_loans
                   (book_id, student_id, loaned_on, due_on,
                    returned_on, status, renewals_count,
                    issued_by, returned_by, notes, copy_id,
                    created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["book_id"], p["student_id"], p["loaned_on"],
             p["due_on"], p["returned_on"], p["status"],
             p["renewals_count"], p["issued_by"],
             p["returned_by"], p["notes"], p["copy_id"]),
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
    from education_system.systems.sixth_form.domain.learners.students import (
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
    back = returned_on or _dt.date.today().isoformat()
    out = update_loan(loan_id, {
        "status": "Returned",
        "returned_on": back,
        "returned_by": returned_by,
    })
    _adjust_available(existing.book_id, +1)
    if existing.copy_id is not None:
        _set_copy_status(existing.copy_id, "Available")
    charged = _charge_overdue_if_late(out, back)
    _promote_next_reservation(existing.book_id)
    _notify("notify_return_receipt", out, fine_raised=charged)
    return out


def return_damaged(loan_id: int, *,
                   returned_on: str | None = None,
                   returned_by: str | None = None,
                   fee: float | None = None,
                   note: str | None = None) -> Loan:
    """Return an item flagged as damaged.

    Marks the loan ``Returned Damaged``, puts the copy back into
    circulation, charges any overdue fine, and raises a damage fee
    (defaults to the ``damaged_fee`` setting)."""
    init_db()
    existing = get_loan(loan_id)
    if existing is None:
        raise ValidationError(f"No loan #{loan_id}")
    if not existing.is_active:
        raise ValidationError(
            f"Loan is not Active (status={existing.status})")
    back = returned_on or _dt.date.today().isoformat()
    out = update_loan(loan_id, {
        "status": "Returned Damaged",
        "returned_on": back,
        "returned_by": returned_by,
    })
    _adjust_available(existing.book_id, +1)
    if existing.copy_id is not None:
        _set_copy_status(existing.copy_id, "Available")
        _flag_copy_damaged(existing.copy_id)
    overdue_amt = _charge_overdue_if_late(out, back) or 0.0
    damage_amt = _raise_damage_fee(out, fee, note) or 0.0
    _promote_next_reservation(existing.book_id)
    total = overdue_amt + damage_amt
    _notify("notify_return_receipt", out,
            fine_raised=(total or None))
    return out


def _flag_copy_damaged(copy_id: int) -> None:
    try:
        from education_system.systems.sixth_form.domain.academics.library import (
            library_copies as _copies,
        )
        _copies.set_condition(copy_id, "Damaged",
                              note="Auto-flagged on damaged return")
    except Exception:
        logger.debug("Could not flag copy #%d damaged", copy_id,
                     exc_info=True)


def _notify(method: str, *args, **kwargs) -> None:
    """Best-effort call into library_notifications (the sixth-form email
    system). Never lets a notification failure break circulation."""
    try:
        from education_system.systems.sixth_form.domain.academics.library import (
            library_notifications as _n,
        )
        getattr(_n, method)(*args, **kwargs)
    except Exception:
        logger.debug("Notification %s skipped", method, exc_info=True)


def _charge_overdue_if_late(loan: Loan, returned_on: str) -> float | None:
    try:
        from education_system.systems.sixth_form.domain.academics.library import (
            library_fines as _fines,
        )
        fine = _fines.charge_overdue(loan, returned_on)
        return fine.amount if fine else None
    except Exception:
        logger.debug("Overdue charge skipped for loan #%d",
                     loan.loan_id, exc_info=True)
        return None


def _raise_damage_fee(loan: Loan, fee: float | None,
                      note: str | None) -> float | None:
    from education_system.systems.sixth_form.domain.academics.library import (
        library_fines as _fines,
        library_settings as _settings,
    )
    amount = fee if fee is not None else float(
        _settings.get_setting("damaged_fee"))
    if amount and amount > 0:
        _fines.create_fine(
            loan.student_id, "Damaged", amount, loan_id=loan.loan_id,
            note=note or f"Damage to item on loan #{loan.loan_id}")
        return amount
    return None


def _promote_next_reservation(book_id: int) -> None:
    try:
        from education_system.systems.sixth_form.domain.academics.library import (
            library_reservations as _holds,
        )
        _holds.promote_next(book_id)
    except Exception:
        logger.debug("Reservation promotion skipped for book #%d",
                     book_id, exc_info=True)


def renew(loan_id: int, *,
           extension_days: int | None = None) -> Loan:
    init_db()
    existing = get_loan(loan_id)
    if existing is None:
        raise ValidationError(f"No loan #{loan_id}")
    if not existing.is_active:
        raise ValidationError(
            "Cannot renew a non-active loan")

    from education_system.systems.sixth_form.domain.academics.library import (
        library_settings as _settings,
        library_reservations as _holds,
    )
    book = get_book(existing.book_id)
    policy = (_settings.get_policy(book.item_type) if book else None)
    cap = policy.max_renewals if policy else MAX_RENEWALS
    if existing.renewals_count >= cap:
        raise ValidationError(
            f"Loan has hit the renewals limit ({cap})")

    # Don't let a renewal jump the queue for a title others are waiting on.
    if _holds.has_waiting(existing.book_id):
        raise ValidationError(
            "Cannot renew — another student has reserved this title")

    days = (policy.loan_days if policy and extension_days is None
            else (extension_days
                  if extension_days is not None else DEFAULT_LOAN_DAYS))
    try:
        new_due = (_dt.date.fromisoformat(existing.due_on)
                   + _dt.timedelta(days=days)).isoformat()
    except ValueError:
        raise ValidationError("Could not compute new due date") from None
    out = update_loan(loan_id, {
        "due_on": new_due,
        "renewals_count": existing.renewals_count + 1,
    })
    _notify("notify_renewal", out)
    return out


def bulk_return(loan_ids: list[int], *,
                returned_on: str | None = None,
                returned_by: str | None = None) -> dict[int, str]:
    """Return many loans at once (item 7).

    Returns a ``{loan_id: "ok" | error-message}`` map so the caller can
    report partial success — one bad id doesn't abort the rest."""
    results: dict[int, str] = {}
    for lid in loan_ids:
        try:
            return_loan(lid, returned_on=returned_on,
                        returned_by=returned_by)
            results[lid] = "ok"
        except ValidationError as e:
            results[lid] = str(e)
    return results


def bulk_renew(loan_ids: list[int], *,
               extension_days: int | None = None) -> dict[int, str]:
    """Renew many loans at once (item 7)."""
    results: dict[int, str] = {}
    for lid in loan_ids:
        try:
            renew(lid, extension_days=extension_days)
            results[lid] = "ok"
        except ValidationError as e:
            results[lid] = str(e)
    return results


def student_loan_history(student_id: str) -> list[Loan]:
    """All loans for a student, newest first (item 9)."""
    return list_loans(student_id=student_id)


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
        _raise_lost_fee(out)
    return out


def _raise_lost_fee(loan: Loan) -> None:
    from education_system.systems.sixth_form.domain.academics.library import (
        library_fines as _fines,
        library_settings as _settings,
    )
    amount = float(_settings.get_setting("lost_fee"))
    if amount and amount > 0:
        _fines.create_fine(
            loan.student_id, "Lost", amount, loan_id=loan.loan_id,
            note=f"Lost item on loan #{loan.loan_id}")


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
        "copy_id":        payload.get("copy_id", existing.copy_id),
    }
    p = _validate_loan_payload(merged)
    with _connect() as conn:
        conn.execute(
            """UPDATE library_loans SET
                   loaned_on = ?, due_on = ?, returned_on = ?,
                   status = ?, renewals_count = ?, issued_by = ?,
                   returned_by = ?, notes = ?, copy_id = ?,
                   updated_at = datetime('now')
               WHERE loan_id = ?""",
            (p["loaned_on"], p["due_on"], p["returned_on"],
             p["status"], p["renewals_count"], p["issued_by"],
             p["returned_by"], p["notes"], p["copy_id"], loan_id),
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
            "WHERE status IN ('Returned', 'Returned Damaged')"
        ).fetchone()[0]
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
