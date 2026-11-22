"""School library: the catalogue, each physical copy, loans to pupils,
reservations, overdue books and reading reports.

**Catalogue.** As in the old screen, a book (title) has an ISBN, title, author,
category, year published, location, notes, an active flag and a number of
copies. Added: publisher, a subject (so departments can see their books) and a
reading level. Each copy is its own row with a barcode, so the library knows
*which* copy a pupil has. Changing a book's number of copies adds copies or
withdraws available ones (never a copy that's out).

**Loans.** Staff issue a copy (by barcode, or the next free copy of a title) to
a pupil on roll. The loan rules (:func:`settings`): loan length, how many books
a pupil can have, renewals, and whether an overdue book stops more borrowing.
"Overdue" is worked out from the due date, never stored stale. A returned copy
that someone has reserved is kept for them. Lost books (old "Mark lost") come
off the shelf count, and are put back if found.

**Reservations.** A pupil can reserve a title that has no copy free. When a
copy comes back the first pupil waiting gets it held for them for a few days;
a reserved title can't be renewed by someone else.

**Who.** The librarian (:data:`LIBRARY_EDITORS`) changes the catalogue and the
rules, writes off books and deletes loans. All staff search the catalogue and
issue, return, renew and reserve. Every change goes in ``library_audit`` and the
activity log.
"""

from __future__ import annotations

import csv
import datetime as _dt
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import LIBRARY_EDITORS, Principal
from education_system.systems.secondary.core.utilities.exports import safe_cell as _safe
from education_system.systems.secondary.core.academic_calendar.school_year import today as _today
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

CATEGORIES: tuple[str, ...] = ("Fiction", "Non-Fiction", "Reference", "Textbook",
                               "Biography", "Periodical", "Other")
LOAN_STATUSES: tuple[str, ...] = ("Out", "Returned", "Overdue", "Lost")
COPY_STATUSES: tuple[str, ...] = ("Available", "On loan", "On hold", "Lost", "Withdrawn")
HOLD_STATUSES: tuple[str, ...] = ("Waiting", "Ready", "Collected", "Cancelled", "Expired")
_ISBN_RE = re.compile(r"^[0-9X]{10}$|^[0-9]{13}$")
DEFAULTS = {"loan_days": 14, "max_loans": 3, "max_renewals": 2, "hold_days": 5,
            "block_overdue": 1}
_LIMITS = {"loan_days": (1, 120, "Loan length"), "max_loans": (1, 20, "Books per pupil"),
           "max_renewals": (0, 10, "Renewals"), "hold_days": (1, 30, "Days a reservation is "
                                                                     "kept"),
           "block_overdue": (0, 1, "Block borrowing when overdue")}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS library_books (
    book_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    isbn            TEXT UNIQUE,
    title           TEXT NOT NULL,
    author          TEXT,
    publisher       TEXT,
    category        TEXT NOT NULL DEFAULT 'Fiction',
    year_published  INTEGER,
    subject_id      INTEGER REFERENCES subjects (subject_id),
    reading_level   TEXT,
    location        TEXT,
    is_active       INTEGER NOT NULL DEFAULT 1,
    notes           TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    created_by      TEXT,
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by      TEXT
);
CREATE TABLE IF NOT EXISTS library_copies (
    copy_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id      INTEGER NOT NULL REFERENCES library_books (book_id) ON DELETE CASCADE,
    barcode      TEXT NOT NULL UNIQUE COLLATE NOCASE,
    status       TEXT NOT NULL DEFAULT 'Available' CHECK (status IN
                 ('Available', 'On loan', 'On hold', 'Lost', 'Withdrawn')),
    acquired_on  TEXT,
    notes        TEXT,
    updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_library_copies_book ON library_copies (book_id);
CREATE TABLE IF NOT EXISTS library_loans (
    loan_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    copy_id        INTEGER NOT NULL REFERENCES library_copies (copy_id),
    book_id        INTEGER NOT NULL REFERENCES library_books (book_id),
    pupil_id       INTEGER NOT NULL REFERENCES pupils (pupil_id),
    loan_date      TEXT NOT NULL,
    due_date       TEXT NOT NULL,
    returned_date  TEXT,
    status         TEXT NOT NULL DEFAULT 'Out' CHECK (status IN ('Out', 'Returned', 'Lost')),
    renewals       INTEGER NOT NULL DEFAULT 0,
    notes          TEXT,
    issued_by      TEXT,
    returned_by    TEXT,
    updated_at     TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_library_loans_pupil ON library_loans (pupil_id);
CREATE INDEX IF NOT EXISTS ix_library_loans_status ON library_loans (status);
CREATE TABLE IF NOT EXISTS library_holds (
    hold_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id     INTEGER NOT NULL REFERENCES library_books (book_id) ON DELETE CASCADE,
    pupil_id    INTEGER NOT NULL REFERENCES pupils (pupil_id),
    status      TEXT NOT NULL DEFAULT 'Waiting' CHECK (status IN
                ('Waiting', 'Ready', 'Collected', 'Cancelled', 'Expired')),
    copy_id     INTEGER REFERENCES library_copies (copy_id),
    placed_at   TEXT NOT NULL DEFAULT (datetime('now')),
    ready_on    TEXT,
    expires_on  TEXT,
    placed_by   TEXT
);
CREATE TABLE IF NOT EXISTS library_settings (
    key    TEXT PRIMARY KEY,
    value  INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS library_audit (
    audit_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id   INTEGER,
    pupil_id  INTEGER,
    action    TEXT NOT NULL CHECK (action IN (
        'create', 'update', 'active', 'delete', 'copies', 'copy', 'lend', 'return', 'renew',
        'lost', 'found', 'loan_delete', 'hold', 'hold_cancel', 'settings', 'remind')),
    actor     TEXT NOT NULL,
    detail    TEXT,
    at        TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

database.register_schema("library", _SCHEMA)

ValidationError = P.ValidationError
PermissionDenied = P.PermissionDenied
NotFound = P.NotFound


# ── Records ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Book:
    book_id: int
    isbn: str | None
    title: str
    author: str | None
    publisher: str | None
    category: str
    year_published: int | None
    subject_id: int | None
    reading_level: str | None
    location: str | None
    is_active: bool
    notes: str | None
    created_at: str
    created_by: str | None
    updated_at: str
    updated_by: str | None
    copies_total: int = 0
    copies_available: int = 0
    on_loan: int = 0
    waiting: int = 0
    subject_code: str | None = None

    @property
    def copies_label(self) -> str:
        return f"{self.copies_available}/{self.copies_total}"


@dataclass(frozen=True)
class Copy:
    copy_id: int
    book_id: int
    barcode: str
    status: str
    acquired_on: str | None
    notes: str | None
    updated_at: str
    holder: str | None = None
    due_date: str | None = None


@dataclass(frozen=True)
class Loan:
    loan_id: int
    copy_id: int
    book_id: int
    pupil_id: int
    loan_date: str
    due_date: str
    returned_date: str | None
    status: str
    renewals: int
    notes: str | None
    issued_by: str | None
    returned_by: str | None
    updated_at: str
    barcode: str = ""
    book_title: str = ""
    book_author: str | None = None
    pupil_name: str = ""
    admission_no: str = ""
    year_group: int = 0
    form_group: str | None = None

    @property
    def is_out(self) -> bool:
        return self.status == "Out"

    @property
    def days_overdue(self) -> int:
        if not self.is_out:
            return 0
        return max(0, (_today() - _dt.date.fromisoformat(self.due_date)).days)

    @property
    def shown_status(self) -> str:
        """Out loans past their due date show as Overdue (the old status)."""
        return "Overdue" if self.days_overdue else self.status


@dataclass(frozen=True)
class Hold:
    hold_id: int
    book_id: int
    pupil_id: int
    status: str
    copy_id: int | None
    placed_at: str
    ready_on: str | None
    expires_on: str | None
    placed_by: str | None
    book_title: str = ""
    pupil_name: str = ""
    admission_no: str = ""
    barcode: str | None = None


_BOOK_SELECT = """
SELECT b.*, s.code AS subject_code,
       (SELECT COUNT(*) FROM library_copies c WHERE c.book_id = b.book_id
         AND c.status IN ('Available', 'On loan', 'On hold')) AS copies_total,
       (SELECT COUNT(*) FROM library_copies c WHERE c.book_id = b.book_id
         AND c.status = 'Available') AS copies_available,
       (SELECT COUNT(*) FROM library_copies c WHERE c.book_id = b.book_id
         AND c.status = 'On loan') AS on_loan,
       (SELECT COUNT(*) FROM library_holds h WHERE h.book_id = b.book_id
         AND h.status = 'Waiting') AS waiting
FROM library_books b LEFT JOIN subjects s ON s.subject_id = b.subject_id
"""
_LOAN_SELECT = """
SELECT l.*, c.barcode, b.title AS book_title, b.author AS book_author,
       p.legal_last_name, p.legal_first_name, p.preferred_name, p.admission_no,
       p.year_group, p.form_group
FROM library_loans l JOIN library_copies c USING (copy_id)
JOIN library_books b ON b.book_id = l.book_id JOIN pupils p ON p.pupil_id = l.pupil_id
"""
_HOLD_SELECT = """
SELECT h.*, b.title AS book_title, c.barcode, p.legal_last_name, p.legal_first_name,
       p.preferred_name, p.admission_no
FROM library_holds h JOIN library_books b USING (book_id) JOIN pupils p USING (pupil_id)
LEFT JOIN library_copies c ON c.copy_id = h.copy_id
"""
_LOAN_BASE = ("loan_id", "copy_id", "book_id", "pupil_id", "loan_date", "due_date",
              "returned_date", "status", "renewals", "notes", "issued_by", "returned_by",
              "updated_at")
_HOLD_BASE = ("hold_id", "book_id", "pupil_id", "status", "copy_id", "placed_at", "ready_on",
              "expires_on", "placed_by")


def _name(r) -> str:
    return f"{r['legal_last_name']}, {r['preferred_name'] or r['legal_first_name']}"


def _book(r) -> Book:
    d = {k: r[k] for k in Book.__dataclass_fields__}
    d["is_active"] = bool(d["is_active"])
    return Book(**d)


def _loan(r) -> Loan:
    return Loan(**{k: r[k] for k in _LOAN_BASE}, barcode=r["barcode"],
                book_title=r["book_title"], book_author=r["book_author"],
                pupil_name=_name(r), admission_no=r["admission_no"],
                year_group=r["year_group"], form_group=r["form_group"])


def _hold(r) -> Hold:
    return Hold(**{k: r[k] for k in _HOLD_BASE}, book_title=r["book_title"],
                pupil_name=_name(r), admission_no=r["admission_no"], barcode=r["barcode"])


# ── Helpers ──────────────────────────────────────────────────────────

def is_editor(actor: Principal) -> bool:
    return actor.role in LIBRARY_EDITORS


def _require_editor(actor: Principal, action: str, target: Any = None) -> None:
    if not is_editor(actor):
        activity_log.record(action, target=target, outcome="denied", principal=actor)
        raise PermissionDenied("Only the librarian can do this.")


def _require_staff(actor: Principal, action: str, target: Any = None) -> None:
    if not actor.is_staff:
        activity_log.record(action, target=target, outcome="denied", principal=actor)
        raise PermissionDenied("Only school staff can use the library desk.")


def _audit(conn, action: str, actor: Principal, *, book_id: int | None = None,
           pupil_id: int | None = None, detail: dict | None = None) -> None:
    conn.execute("INSERT INTO library_audit (book_id, pupil_id, action, actor, detail) "
                 "VALUES (?, ?, ?, ?, ?)",
                 (book_id, pupil_id, action, actor.username or "unknown",
                  json.dumps(detail, default=str, sort_keys=True) if detail else None))


def _date(value: Any, label: str, problems: list[str]) -> _dt.date | None:
    if value in (None, ""):
        return None
    if isinstance(value, _dt.date):
        return value
    try:
        return _dt.date.fromisoformat(str(value).strip())
    except ValueError:
        problems.append(f"{label} must be a date (YYYY-MM-DD)")
        return None


def clean_isbn(value: Any) -> str | None:
    """Digits (and a final X) only; '978-0-14-...' -> '978014...'."""
    s = re.sub(r"[\s-]", "", str(value or "")).upper()
    return s or None


def isbn_ok(isbn: str) -> bool:
    if not _ISBN_RE.match(isbn):
        return False
    if len(isbn) == 10:
        total = sum((10 - i) * (10 if ch == "X" else int(ch)) for i, ch in enumerate(isbn))
        return "X" not in isbn[:9] and total % 11 == 0
    total = sum(int(ch) * (1 if i % 2 == 0 else 3) for i, ch in enumerate(isbn))
    return total % 10 == 0


# ── Settings ─────────────────────────────────────────────────────────

def settings() -> dict[str, int]:
    with database.connect() as conn:
        saved = dict(conn.execute("SELECT key, value FROM library_settings").fetchall())
    return {k: int(saved.get(k, v)) for k, v in DEFAULTS.items()}


def set_settings(changes: dict[str, Any], *, actor: Principal) -> dict[str, int]:
    _require_editor(actor, "library.settings")
    problems, clean = [], {}
    for k, v in changes.items():
        if k not in DEFAULTS:
            problems.append(f"Unknown setting {k}")
            continue
        lo, hi, label = _LIMITS[k]
        try:
            n = int(v) if not isinstance(v, bool) else int(v)
        except (TypeError, ValueError):
            n = lo - 1
        if not lo <= n <= hi:
            problems.append(f"{label} must be from {lo} to {hi}")
        clean[k] = n
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        conn.executemany("INSERT INTO library_settings (key, value) VALUES (?, ?) ON CONFLICT "
                         "(key) DO UPDATE SET value = excluded.value", list(clean.items()))
        _audit(conn, "settings", actor, detail=clean)
    activity_log.record("library.settings", principal=actor)
    return settings()


# ── Catalogue ────────────────────────────────────────────────────────

def get_book(book_id: int) -> Book:
    with database.connect() as conn:
        r = conn.execute(_BOOK_SELECT + " WHERE b.book_id = ?", (int(book_id),)).fetchone()
    if r is None:
        raise NotFound(f"No book #{book_id}")
    return _book(r)


def list_books(*, active_only: bool = False, category: str | None = None,
               available_only: bool = False, query: str | None = None,
               subject_id: int | None = None) -> list[Book]:
    """The old 'List / search books' (title, author or ISBN)."""
    sql, where, params = _BOOK_SELECT, [], []
    if active_only:
        where.append("b.is_active = 1")
    if category:
        if category not in CATEGORIES:
            raise ValidationError([f"Category must be one of {', '.join(CATEGORIES)}"])
        where.append("b.category = ?")
        params.append(category)
    if subject_id:
        where.append("b.subject_id = ?")
        params.append(int(subject_id))
    for term in (query or "").split():
        where.append("(b.title LIKE ? OR b.author LIKE ? OR b.isbn LIKE ? OR EXISTS (SELECT 1 "
                     "FROM library_copies c WHERE c.book_id = b.book_id AND c.barcode = ?))")
        params += [f"%{term}%", f"%{term}%", f"%{clean_isbn(term)}%", term]
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY b.title COLLATE NOCASE, b.book_id"
    with database.connect() as conn:
        rows = [_book(r) for r in conn.execute(sql, params)]
    return [b for b in rows if b.copies_available > 0] if available_only else rows


EDITABLE_FIELDS = ("isbn", "title", "author", "publisher", "category", "year_published",
                   "subject_id", "reading_level", "location", "notes")


def _clean_book(data: dict[str, Any], current: Book | None) -> dict[str, Any]:
    problems: list[str] = []
    unknown = set(data) - set(EDITABLE_FIELDS) - {"copies_total"}
    if unknown:
        problems.append(f"Unknown field(s): {', '.join(sorted(unknown))}")
    merged = {k: getattr(current, k) for k in EDITABLE_FIELDS} if current else {}
    merged.update({k: v for k, v in data.items() if k != "copies_total"})
    out: dict[str, Any] = {}
    out["title"] = P._clean_text(merged.get("title"), 200)
    if not out["title"]:
        problems.append("Title is required")
    isbn = clean_isbn(merged.get("isbn"))
    if isbn and not isbn_ok(isbn):
        problems.append("ISBN must be a valid 10- or 13-digit ISBN")
    out["isbn"] = isbn
    cat = P._clean_text(merged.get("category"), 20) or "Fiction"
    match = next((c for c in CATEGORIES if c.lower() == cat.lower()), None)
    if match is None:
        problems.append(f"Category must be one of {', '.join(CATEGORIES)}")
    out["category"] = match or cat
    yp = merged.get("year_published")
    out["year_published"] = None
    if yp not in (None, ""):
        try:
            out["year_published"] = int(str(yp).strip())
        except ValueError:
            out["year_published"] = 0
        if not 1450 <= out["year_published"] <= _today().year + 1:
            problems.append(f"Year published must be from 1450 to {_today().year + 1}")
    sid = merged.get("subject_id")
    out["subject_id"] = None
    if sid not in (None, ""):
        try:
            out["subject_id"] = S.get(int(sid)).subject_id
        except (ValueError, S.NotFound):
            problems.append("Choose a subject from the list")
    for k, n in (("author", 150), ("publisher", 100), ("reading_level", 30),
                 ("location", 60), ("notes", 2000)):
        out[k] = P._clean_text(merged.get(k), n)
    if problems:
        raise ValidationError(problems)
    return out


def _copies_wanted(data: dict[str, Any], default: int | None) -> int | None:
    v = data.get("copies_total")
    if v in (None, ""):
        return default
    try:
        n = int(str(v).strip())
    except ValueError:
        n = -1
    if not 0 <= n <= 500:
        raise ValidationError(["Copies must be a whole number from 0 to 500"])
    return n


def _next_barcodes(conn, n: int) -> list[str]:
    row = conn.execute("SELECT MAX(CAST(substr(barcode, 2) AS INTEGER)) FROM library_copies "
                       "WHERE barcode GLOB 'L[0-9]*'").fetchone()
    start = (row[0] or 0) + 1
    return [f"L{start + i:06d}" for i in range(n)]


def create_book(data: dict[str, Any], *, actor: Principal) -> Book:
    """The old 'Add book'. ``copies_total`` copies are made (default 1)."""
    _require_editor(actor, "library.create")
    clean = _clean_book(data, None)
    copies = _copies_wanted(data, 1) or 0
    with database.connect() as conn:
        if clean["isbn"]:
            dup = conn.execute("SELECT book_id FROM library_books WHERE isbn = ?",
                               (clean["isbn"],)).fetchone()
            if dup:
                raise ValidationError([f"ISBN {clean['isbn']} is already book #{dup[0]} - "
                                       "add copies to it instead"])
        cols = list(clean)
        bid = conn.execute(
            f"INSERT INTO library_books ({', '.join(cols)}, created_by, updated_by) "  # nosec B608 - columns from _clean_book
            f"VALUES ({', '.join('?' * len(cols))}, ?, ?)",
            (*clean.values(), actor.username, actor.username)).lastrowid
        codes = _next_barcodes(conn, copies)
        conn.executemany("INSERT INTO library_copies (book_id, barcode, acquired_on) VALUES "
                         "(?, ?, ?)", [(bid, b, _today().isoformat()) for b in codes])
        _audit(conn, "create", actor, book_id=bid, detail={"copies": copies})
    activity_log.record("library.create", target=f"book:{bid}", principal=actor)
    return get_book(bid)


def update_book(book_id: int, changes: dict[str, Any], *, actor: Principal
                ) -> tuple[Book, list[str]]:
    """The old 'Edit book'. A new number of copies adds copies or withdraws
    available ones. Returns (book, notes)."""
    b = get_book(book_id)
    _require_editor(actor, "library.update", f"book:{b.book_id}")
    clean = _clean_book(changes, b)
    diff = {k: v for k, v in clean.items() if getattr(b, k) != v}
    want = _copies_wanted(changes, None)
    notes: list[str] = []
    if diff:
        with database.connect() as conn:
            if "isbn" in diff and diff["isbn"] and conn.execute(
                    "SELECT 1 FROM library_books WHERE isbn = ? AND book_id != ?",
                    (diff["isbn"], b.book_id)).fetchone():
                raise ValidationError([f"ISBN {diff['isbn']} belongs to another book"])
            sets = ", ".join(f"{k} = ?" for k in diff)
            conn.execute(f"UPDATE library_books SET {sets}, updated_at = datetime('now'), "  # nosec B608 - keys from _clean_book
                         "updated_by = ? WHERE book_id = ?",
                         (*diff.values(), actor.username, b.book_id))
            _audit(conn, "update", actor, book_id=b.book_id, detail={"fields": sorted(diff)})
        activity_log.record("library.update", target=f"book:{b.book_id}", principal=actor,
                            fields=sorted(diff))
    if want is not None and want != b.copies_total:
        if want > b.copies_total:
            add_copies(b.book_id, want - b.copies_total, actor=actor)
            notes.append(f"Added {want - b.copies_total} cop(ies)")
        else:
            gone = b.copies_total - want
            if gone > b.copies_available:
                raise ValidationError([f"Only {b.copies_available} cop(ies) are on the shelf "
                                       f"- {b.copies_total - b.copies_available} are out or "
                                       "held, so copies can't go below "
                                       f"{b.copies_total - b.copies_available}"])
            for c in [c for c in list_copies(b.book_id) if c.status == "Available"][-gone:]:
                set_copy_status(c.copy_id, "Withdrawn", actor=actor)
            notes.append(f"Withdrew {gone} cop(ies)")
    return get_book(b.book_id), notes


def toggle_active(book_id: int, *, actor: Principal) -> Book:
    b = get_book(book_id)
    _require_editor(actor, "library.active", f"book:{b.book_id}")
    with database.connect() as conn:
        conn.execute("UPDATE library_books SET is_active = ?, updated_at = datetime('now'), "
                     "updated_by = ? WHERE book_id = ?",
                     (0 if b.is_active else 1, actor.username, b.book_id))
        _audit(conn, "active", actor, book_id=b.book_id, detail={"active": not b.is_active})
    activity_log.record("library.active", target=f"book:{b.book_id}", principal=actor)
    return get_book(b.book_id)


def delete_book(book_id: int, *, actor: Principal) -> Book:
    """Only a book that has never been lent; otherwise make it inactive."""
    b = get_book(book_id)
    _require_editor(actor, "library.delete", f"book:{b.book_id}")
    with database.connect() as conn:
        n = conn.execute("SELECT COUNT(*) FROM library_loans WHERE book_id = ?",
                         (b.book_id,)).fetchone()[0]
        if n:
            raise ValidationError([f"'{b.title}' has {n} loan(s) on record - make it inactive "
                                   "instead"])
        conn.execute("DELETE FROM library_holds WHERE book_id = ?", (b.book_id,))
        conn.execute("DELETE FROM library_copies WHERE book_id = ?", (b.book_id,))
        conn.execute("DELETE FROM library_books WHERE book_id = ?", (b.book_id,))
        _audit(conn, "delete", actor, book_id=b.book_id, detail={"title": b.title})
    activity_log.record("library.delete", target=f"book:{b.book_id}", principal=actor)
    return b


def history(book_id: int, *, limit: int = 300) -> list[dict[str, Any]]:
    with database.connect() as conn:
        return [{"at": r["at"], "actor": r["actor"], "action": r["action"],
                 "pupil_id": r["pupil_id"], "detail": json.loads(r["detail"] or "{}")}
                for r in conn.execute("SELECT * FROM library_audit WHERE book_id = ? ORDER BY "
                                      "audit_id DESC LIMIT ?", (int(book_id), int(limit)))]


# ── Copies ───────────────────────────────────────────────────────────

def list_copies(book_id: int) -> list[Copy]:
    with database.connect() as conn:
        rows = conn.execute(
            "SELECT c.*, (SELECT p.legal_last_name || ', ' || COALESCE(p.preferred_name, "
            "p.legal_first_name) FROM library_loans l JOIN pupils p USING (pupil_id) WHERE "
            "l.copy_id = c.copy_id AND l.status = 'Out') AS holder, (SELECT l.due_date FROM "
            "library_loans l WHERE l.copy_id = c.copy_id AND l.status = 'Out') AS due_date "
            "FROM library_copies c WHERE c.book_id = ? ORDER BY c.copy_id", (int(book_id),)
        ).fetchall()
    return [Copy(**{k: r[k] for k in Copy.__dataclass_fields__}) for r in rows]


def find_copy(barcode: str) -> Copy | None:
    with database.connect() as conn:
        r = conn.execute("SELECT copy_id, book_id FROM library_copies WHERE barcode = ?",
                         ((barcode or "").strip(),)).fetchone()
    if r is None:
        return None
    return next(c for c in list_copies(r["book_id"]) if c.copy_id == r["copy_id"])


def add_copies(book_id: int, n: int, *, actor: Principal,
               barcodes: list[str] | None = None) -> list[Copy]:
    b = get_book(book_id)
    _require_editor(actor, "library.copies", f"book:{b.book_id}")
    codes = [c.strip() for c in (barcodes or []) if c and c.strip()]
    n = len(codes) if codes else int(n)
    if not 1 <= n <= 500:
        raise ValidationError(["Add from 1 to 500 copies"])
    problems = [f"Barcode '{c}' is too long" for c in codes if len(c) > 30]
    if len({c.lower() for c in codes}) != len(codes):
        problems.append("The same barcode is listed twice")
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        taken = [c for c in codes if conn.execute(
            "SELECT 1 FROM library_copies WHERE barcode = ?", (c,)).fetchone()]
        if taken:
            raise ValidationError([f"Barcode {', '.join(taken)} is already used"])
        codes = codes or _next_barcodes(conn, n)
        conn.executemany("INSERT INTO library_copies (book_id, barcode, acquired_on) VALUES "
                         "(?, ?, ?)", [(b.book_id, c, _today().isoformat()) for c in codes])
        _audit(conn, "copies", actor, book_id=b.book_id, detail={"added": len(codes)})
    activity_log.record("library.copies", target=f"book:{b.book_id}", principal=actor)
    _serve_holds(b.book_id, actor)
    return [c for c in list_copies(b.book_id) if c.barcode in codes]


def set_copy_status(copy_id: int, status: str, *, actor: Principal,
                    note: str | None = None) -> Copy:
    """Withdraw a copy, or put a withdrawn / lost one back on the shelf. Loans
    and holds move a copy themselves."""
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM library_copies WHERE copy_id = ?",
                         (int(copy_id),)).fetchone()
    if r is None:
        raise NotFound(f"No copy #{copy_id}")
    _require_editor(actor, "library.copy", f"book:{r['book_id']}")
    if status not in ("Available", "Withdrawn"):
        raise ValidationError(["A copy can be withdrawn or put back as Available"])
    if r["status"] in ("On loan", "On hold"):
        raise ValidationError([f"Copy {r['barcode']} is {r['status'].lower()} - return it "
                               "or cancel the reservation first"])
    if r["status"] == status:
        return next(c for c in list_copies(r["book_id"]) if c.copy_id == r["copy_id"])
    with database.connect() as conn:
        conn.execute("UPDATE library_copies SET status = ?, notes = COALESCE(?, notes), "
                     "updated_at = datetime('now') WHERE copy_id = ?",
                     (status, P._clean_text(note, 300), r["copy_id"]))
        _audit(conn, "copy", actor, book_id=r["book_id"],
               detail={"barcode": r["barcode"], "from": r["status"], "to": status})
    if status == "Available":
        _serve_holds(r["book_id"], actor)
    return next(c for c in list_copies(r["book_id"]) if c.copy_id == r["copy_id"])


# ── Loans ────────────────────────────────────────────────────────────

def get_loan(loan_id: int) -> Loan:
    with database.connect() as conn:
        r = conn.execute(_LOAN_SELECT + " WHERE l.loan_id = ?", (int(loan_id),)).fetchone()
    if r is None:
        raise NotFound(f"No loan #{loan_id}")
    return _loan(r)


def list_loans(*, status: str | None = None, pupil_id: int | None = None,
               book_id: int | None = None, year_group: int | None = None,
               form_group: str | None = None) -> list[Loan]:
    """The old 'List loans'. Status 'Overdue' = out and past the due date."""
    sql, where, params = _LOAN_SELECT, [], []
    if status:
        if status not in LOAN_STATUSES:
            raise ValidationError([f"Status must be one of {', '.join(LOAN_STATUSES)}"])
        if status == "Overdue":
            where.append("l.status = 'Out' AND l.due_date < ?")
            params.append(_today().isoformat())
        else:
            where.append("l.status = ?")
            params.append(status)
    for col, val in (("l.pupil_id", pupil_id), ("l.book_id", book_id),
                     ("p.year_group", year_group), ("p.form_group", form_group)):
        if val not in (None, ""):
            where.append(f"{col} = ?")
            params.append(val)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY l.loan_date DESC, l.loan_id DESC"
    with database.connect() as conn:
        return [_loan(r) for r in conn.execute(sql, params)]


def pupil_loans(pupil_id: int) -> list[Loan]:
    """The old 'Pupil loan history'."""
    return list_loans(pupil_id=pupil_id)


def can_borrow(pupil_id: int) -> tuple[bool, list[str]]:
    """Whether the pupil may take another book, and why not."""
    p = P.get_pupil(int(pupil_id))
    if p is None:
        raise NotFound("No such pupil")
    rules = settings()
    out = [x for x in list_loans(pupil_id=p.pupil_id, status="Out")]
    why = []
    if p.roll_status != "on_roll":
        why.append(f"{p.display_name} isn't on roll")
    if len(out) >= rules["max_loans"]:
        why.append(f"{p.display_name} already has {len(out)} book(s) - the limit is "
                   f"{rules['max_loans']}")
    late = [x for x in out if x.days_overdue]
    if late and rules["block_overdue"]:
        why.append(f"{p.display_name} has {len(late)} overdue book(s): "
                   + ", ".join(x.book_title for x in late))
    return not why, why


def _pick_copy(book: Book, pupil_id: int) -> Copy | None:
    copies = list_copies(book.book_id)
    held = _ready_hold(book.book_id, pupil_id)
    if held and held.copy_id:
        return next((c for c in copies if c.copy_id == held.copy_id), None)
    return next((c for c in copies if c.status == "Available"), None)


def _ready_hold(book_id: int, pupil_id: int) -> Hold | None:
    with database.connect() as conn:
        r = conn.execute(_HOLD_SELECT + " WHERE h.book_id = ? AND h.pupil_id = ? AND "
                         "h.status IN ('Waiting', 'Ready') ORDER BY h.hold_id",
                         (int(book_id), int(pupil_id))).fetchone()
    return _hold(r) if r else None


def lend(pupil_id: int, *, actor: Principal, barcode: str | None = None,
         book_id: int | None = None, loan_date: Any = None, due_date: Any = None,
         notes: str | None = None, override: bool = False) -> Loan:
    """The old 'Lend book': a copy by barcode, or the next copy of a title.
    The librarian can ``override`` the loan limits."""
    _require_staff(actor, "library.lend")
    problems: list[str] = []
    copy: Copy | None = None
    if barcode:
        copy = find_copy(barcode)
        if copy is None:
            raise NotFound(f"No copy with barcode {barcode}")
        book = get_book(copy.book_id)
    elif book_id:
        book = get_book(book_id)
    else:
        raise ValidationError(["Scan a barcode or choose a book"])
    p = P.get_pupil(int(pupil_id))
    if p is None:
        raise NotFound("No such pupil")
    if not book.is_active:
        problems.append(f"'{book.title}' is inactive - re-activate it first")
    hold = _ready_hold(book.book_id, p.pupil_id)
    if copy is None:
        copy = _pick_copy(book, p.pupil_id)
        if copy is None or copy.status not in ("Available", "On hold"):
            problems.append(f"'{book.title}' has no copy on the shelf - reserve it instead")
    if copy is not None and copy.status == "On hold" and not (hold and hold.copy_id ==
                                                              copy.copy_id):
        problems.append(f"Copy {copy.barcode} is kept for another pupil's reservation")
    elif copy is not None and copy.status not in ("Available", "On hold"):
        problems.append(f"Copy {copy.barcode} is {copy.status.lower()}")
    ok, why = can_borrow(p.pupil_id)
    if not ok:
        if override and is_editor(actor) and p.roll_status == "on_roll":
            pass
        else:
            problems += why
    rules = settings()
    start = _date(loan_date, "Loan date", problems) or _today()
    if start > _today():
        problems.append("The loan date can't be in the future")
    due = _date(due_date, "Due date", problems) or start + _dt.timedelta(
        days=rules["loan_days"])
    if due < start:
        problems.append("The due date can't be before the loan date")
    if problems:
        raise ValidationError(problems)
    assert copy is not None
    with database.connect() as conn:
        lid = conn.execute(
            "INSERT INTO library_loans (copy_id, book_id, pupil_id, loan_date, due_date, notes, "
            "issued_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (copy.copy_id, book.book_id, p.pupil_id, start.isoformat(), due.isoformat(),
             P._clean_text(notes, 500), actor.username)).lastrowid
        conn.execute("UPDATE library_copies SET status = 'On loan', updated_at = "
                     "datetime('now') WHERE copy_id = ?", (copy.copy_id,))
        released = hold is not None and hold.status == "Ready" and bool(hold.copy_id) \
            and hold.copy_id != copy.copy_id
        if released:
            # They took a different copy: the one kept for them goes back.
            conn.execute("UPDATE library_copies SET status = 'Available', updated_at = "
                         "datetime('now') WHERE copy_id = ?", (hold.copy_id,))
        if hold:
            conn.execute("UPDATE library_holds SET status = 'Collected', copy_id = ? WHERE "
                         "hold_id = ?", (copy.copy_id, hold.hold_id))
        _audit(conn, "lend", actor, book_id=book.book_id, pupil_id=p.pupil_id,
               detail={"barcode": copy.barcode, "due": due.isoformat(),
                       "override": bool(override and not ok)})
    activity_log.record("library.lend", target=f"book:{book.book_id}", principal=actor)
    if released:
        _serve_holds(book.book_id, actor)
    return get_loan(lid)


def _serve_holds(book_id: int, actor: Principal) -> list[Hold]:
    """Keep free copies for the pupils waiting longest."""
    rules = settings()
    with database.connect() as conn:
        waiting = [r["hold_id"] for r in conn.execute(
            "SELECT hold_id FROM library_holds WHERE book_id = ? AND status = 'Waiting' "
            "ORDER BY placed_at, hold_id", (int(book_id),))]
        free = [r["copy_id"] for r in conn.execute(
            "SELECT copy_id FROM library_copies WHERE book_id = ? AND status = 'Available' "
            "ORDER BY copy_id", (int(book_id),))]
        served = list(zip(waiting, free))
        expires = (_today() + _dt.timedelta(days=rules["hold_days"])).isoformat()
        for hid, cid in served:
            conn.execute("UPDATE library_holds SET status = 'Ready', copy_id = ?, ready_on = ?, "
                         "expires_on = ? WHERE hold_id = ?",
                         (cid, _today().isoformat(), expires, hid))
            conn.execute("UPDATE library_copies SET status = 'On hold', updated_at = "
                         "datetime('now') WHERE copy_id = ?", (cid,))
    if not served:
        return []
    ids = {h for h, _c in served}
    return [h for h in list_holds(book_id=book_id) if h.hold_id in ids]


def return_loan(loan_id: int, *, actor: Principal, returned_date: Any = None,
                notes: str | None = None) -> tuple[Loan, Hold | None]:
    """The old 'Return'. A lost book that turns up is returned the same way.
    Returns (loan, the reservation the copy is now kept for, if any)."""
    _require_staff(actor, "library.return")
    loan = get_loan(loan_id)
    if loan.status == "Returned":
        raise ValidationError([f"Loan #{loan.loan_id} was already returned on "
                               f"{loan.returned_date}"])
    problems: list[str] = []
    day = _date(returned_date, "Returned date", problems) or _today()
    if day > _today():
        problems.append("The return date can't be in the future")
    if day.isoformat() < loan.loan_date:
        problems.append("The return date can't be before the loan date")
    if problems:
        raise ValidationError(problems)
    found = loan.status == "Lost"
    with database.connect() as conn:
        conn.execute("UPDATE library_loans SET status = 'Returned', returned_date = ?, "
                     "returned_by = ?, notes = COALESCE(?, notes), updated_at = datetime('now') "
                     "WHERE loan_id = ?", (day.isoformat(), actor.username,
                                           P._clean_text(notes, 500), loan.loan_id))
        conn.execute("UPDATE library_copies SET status = 'Available', updated_at = "
                     "datetime('now') WHERE copy_id = ?", (loan.copy_id,))
        _audit(conn, "found" if found else "return", actor, book_id=loan.book_id,
               pupil_id=loan.pupil_id, detail={"barcode": loan.barcode,
                                               "days_late": max(0, (day - _dt.date.fromisoformat(
                                                   loan.due_date)).days)})
    activity_log.record("library.return", target=f"book:{loan.book_id}", principal=actor)
    served = _serve_holds(loan.book_id, actor)
    hold = next((h for h in served if h.copy_id == loan.copy_id), None)
    return get_loan(loan.loan_id), hold


def return_by_barcode(barcode: str, *, actor: Principal) -> tuple[Loan, Hold | None]:
    copy = find_copy(barcode)
    if copy is None:
        raise NotFound(f"No copy with barcode {barcode}")
    with database.connect() as conn:
        r = conn.execute("SELECT loan_id FROM library_loans WHERE copy_id = ? AND status IN "
                         "('Out', 'Lost') ORDER BY loan_id DESC", (copy.copy_id,)).fetchone()
    if r is None:
        raise ValidationError([f"Copy {copy.barcode} isn't out on loan"])
    return return_loan(r[0], actor=actor)


def renew(loan_id: int, *, actor: Principal) -> Loan:
    _require_staff(actor, "library.renew")
    loan = get_loan(loan_id)
    rules = settings()
    problems = []
    if loan.status != "Out":
        problems.append(f"Loan #{loan.loan_id} is {loan.status} - only books that are out can "
                        "be renewed")
    if loan.renewals >= rules["max_renewals"]:
        problems.append(f"Already renewed {loan.renewals} time(s) - the limit is "
                        f"{rules['max_renewals']}")
    if get_book(loan.book_id).waiting:
        problems.append(f"Another pupil has reserved '{loan.book_title}' - it must come back")
    if problems:
        raise ValidationError(problems)
    due = max(_today(), _dt.date.fromisoformat(loan.due_date)) + _dt.timedelta(
        days=rules["loan_days"])
    with database.connect() as conn:
        conn.execute("UPDATE library_loans SET due_date = ?, renewals = renewals + 1, "
                     "updated_at = datetime('now') WHERE loan_id = ?",
                     (due.isoformat(), loan.loan_id))
        _audit(conn, "renew", actor, book_id=loan.book_id, pupil_id=loan.pupil_id,
               detail={"due": due.isoformat()})
    activity_log.record("library.renew", target=f"book:{loan.book_id}", principal=actor)
    return get_loan(loan.loan_id)


def mark_lost(loan_id: int, *, actor: Principal, notes: str | None = None) -> Loan:
    """The old 'Mark lost'. The copy comes off the shelf count."""
    loan = get_loan(loan_id)
    _require_editor(actor, "library.lost", f"book:{loan.book_id}")
    if loan.status != "Out":
        raise ValidationError([f"Loan #{loan.loan_id} is {loan.status} - only books that are "
                               "out can be marked lost"])
    with database.connect() as conn:
        conn.execute("UPDATE library_loans SET status = 'Lost', notes = COALESCE(?, notes), "
                     "updated_at = datetime('now') WHERE loan_id = ?",
                     (P._clean_text(notes, 500), loan.loan_id))
        conn.execute("UPDATE library_copies SET status = 'Lost', updated_at = datetime('now') "
                     "WHERE copy_id = ?", (loan.copy_id,))
        _audit(conn, "lost", actor, book_id=loan.book_id, pupil_id=loan.pupil_id,
               detail={"barcode": loan.barcode})
    activity_log.record("library.lost", target=f"book:{loan.book_id}", principal=actor)
    return get_loan(loan.loan_id)


def delete_loan(loan_id: int, *, actor: Principal) -> Loan:
    """Remove a loan entered by mistake (the copy goes back on the shelf)."""
    loan = get_loan(loan_id)
    _require_editor(actor, "library.loan_delete", f"book:{loan.book_id}")
    with database.connect() as conn:
        conn.execute("DELETE FROM library_loans WHERE loan_id = ?", (loan.loan_id,))
        if loan.status in ("Out", "Lost"):
            conn.execute("UPDATE library_copies SET status = 'Available', updated_at = "
                         "datetime('now') WHERE copy_id = ?", (loan.copy_id,))
        _audit(conn, "loan_delete", actor, book_id=loan.book_id, pupil_id=loan.pupil_id,
               detail={"barcode": loan.barcode, "status": loan.status})
    activity_log.record("library.loan_delete", target=f"book:{loan.book_id}", principal=actor)
    if loan.status in ("Out", "Lost"):
        _serve_holds(loan.book_id, actor)
    return loan


# ── Reservations ─────────────────────────────────────────────────────

def list_holds(*, book_id: int | None = None, pupil_id: int | None = None,
               active_only: bool = True) -> list[Hold]:
    sql, where, params = _HOLD_SELECT, [], []
    if active_only:
        where.append("h.status IN ('Waiting', 'Ready')")
    if book_id:
        where.append("h.book_id = ?")
        params.append(int(book_id))
    if pupil_id:
        where.append("h.pupil_id = ?")
        params.append(int(pupil_id))
    if where:
        sql += " WHERE " + " AND ".join(where)
    with database.connect() as conn:
        return [_hold(r) for r in conn.execute(sql + " ORDER BY h.status = 'Ready' DESC, "
                                               "h.placed_at, h.hold_id", params)]


def reserve(book_id: int, pupil_id: int, *, actor: Principal) -> Hold:
    _require_staff(actor, "library.hold")
    b = get_book(book_id)
    p = P.get_pupil(int(pupil_id))
    if p is None:
        raise NotFound("No such pupil")
    problems = []
    if not b.is_active:
        problems.append(f"'{b.title}' is inactive")
    if p.roll_status != "on_roll":
        problems.append(f"{p.display_name} isn't on roll")
    if b.copies_available:
        problems.append(f"'{b.title}' has a copy on the shelf - lend it instead")
    if b.copies_total == 0:
        problems.append(f"The library has no copies of '{b.title}'")
    if _ready_hold(b.book_id, p.pupil_id):
        problems.append(f"{p.display_name} has already reserved '{b.title}'")
    if any(x.book_id == b.book_id for x in list_loans(pupil_id=p.pupil_id, status="Out")):
        problems.append(f"{p.display_name} already has '{b.title}'")
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        hid = conn.execute("INSERT INTO library_holds (book_id, pupil_id, placed_by) VALUES "
                           "(?, ?, ?)", (b.book_id, p.pupil_id, actor.username)).lastrowid
        _audit(conn, "hold", actor, book_id=b.book_id, pupil_id=p.pupil_id)
    activity_log.record("library.hold", target=f"book:{b.book_id}", principal=actor)
    return next(h for h in list_holds(book_id=b.book_id) if h.hold_id == hid)


def cancel_hold(hold_id: int, *, actor: Principal, expired: bool = False) -> Hold:
    _require_staff(actor, "library.hold_cancel")
    with database.connect() as conn:
        r = conn.execute(_HOLD_SELECT + " WHERE h.hold_id = ?", (int(hold_id),)).fetchone()
    if r is None:
        raise NotFound(f"No reservation #{hold_id}")
    h = _hold(r)
    if h.status not in ("Waiting", "Ready"):
        raise ValidationError([f"That reservation is already {h.status.lower()}"])
    with database.connect() as conn:
        conn.execute("UPDATE library_holds SET status = ? WHERE hold_id = ?",
                     ("Expired" if expired else "Cancelled", h.hold_id))
        if h.status == "Ready" and h.copy_id:
            conn.execute("UPDATE library_copies SET status = 'Available', updated_at = "
                         "datetime('now') WHERE copy_id = ?", (h.copy_id,))
        _audit(conn, "hold_cancel", actor, book_id=h.book_id, pupil_id=h.pupil_id,
               detail={"expired": expired})
    if h.status == "Ready":
        _serve_holds(h.book_id, actor)
    return next(x for x in list_holds(book_id=h.book_id, active_only=False)
                if x.hold_id == h.hold_id)


def expire_holds(*, actor: Principal) -> int:
    """Release copies kept past their collection date to the next pupil."""
    late = [h for h in list_holds() if h.status == "Ready" and h.expires_on
            and h.expires_on < _today().isoformat()]
    for h in late:
        cancel_hold(h.hold_id, actor=actor, expired=True)
    return len(late)


# ── Reports ──────────────────────────────────────────────────────────

def overview() -> dict[str, Any]:
    """The old header: titles, active, copies, on the shelf, loans by status."""
    with database.connect() as conn:
        total, active = conn.execute("SELECT COUNT(*), COALESCE(SUM(is_active), 0) FROM "
                                     "library_books").fetchone()
        copies = dict(conn.execute("SELECT status, COUNT(*) FROM library_copies GROUP BY "
                                   "status").fetchall())
        loans = dict(conn.execute("SELECT status, COUNT(*) FROM library_loans GROUP BY "
                                  "status").fetchall())
        overdue = conn.execute("SELECT COUNT(*) FROM library_loans WHERE status = 'Out' AND "
                               "due_date < ?", (_today().isoformat(),)).fetchone()[0]
        holds = conn.execute("SELECT COUNT(*) FROM library_holds WHERE status IN "
                             "('Waiting', 'Ready')").fetchone()[0]
    out_now = loans.get("Out", 0)
    return {"books_total": total, "books_active": active,
            "copies_total": sum(copies.get(s, 0) for s in ("Available", "On loan", "On hold")),
            "copies_avail": copies.get("Available", 0),
            "loans": {"Out": out_now - overdue, "Returned": loans.get("Returned", 0),
                      "Overdue": overdue, "Lost": loans.get("Lost", 0)},
            "holds": holds}


def overdue(*, year_group: int | None = None, form_group: str | None = None
            ) -> list[Loan]:
    """Out and past due, most overdue first."""
    rows = list_loans(status="Overdue", year_group=year_group, form_group=form_group)
    return sorted(rows, key=lambda x: (-x.days_overdue, x.pupil_name.lower()))


def reminder_body(loans: list[Loan]) -> str:
    lines = "\n".join(f"  • {x.book_title} - due {x.due_date}" for x in loans)
    return ("Dear {contact_name},\n\n"
            "Our records show that {pupil_first_name} has library book(s) overdue:\n\n"
            f"{lines}\n\nPlease help {{pupil_first_name}} return them to the school library "
            "as soon as possible, or let us know if they've been lost.\n\nThank you,\n"
            "School Library")


def remind_overdue(*, actor: Principal, pupil_ids: list[int] | None = None
                   ) -> dict[str, Any]:
    """E-mail each family with an overdue book (one message per pupil, listing
    their books). Returns {'sent': [message ids], 'no_email': [names]}."""
    _require_staff(actor, "library.remind")
    from education_system.systems.secondary.modules.communication.domain import email_outbox as E
    late = overdue()
    by_pupil: dict[int, list[Loan]] = {}
    for x in late:
        if pupil_ids is None or x.pupil_id in pupil_ids:
            by_pupil.setdefault(x.pupil_id, []).append(x)
    if not by_pupil:
        raise ValidationError(["No overdue books to write about"])
    sent, no_email = [], []
    for pid, loans in by_pupil.items():
        try:
            res = E.send_message("Overdue library book" + ("s" if len(loans) > 1 else ""),
                                 reminder_body(loans),
                                 E.Audience(kind="pupils", pupil_ids=[pid]), actor=actor)
        except E.ValidationError:
            no_email.append(loans[0].pupil_name)
            continue
        sent.append(res.message_id)
        no_email += [p.display_name for p in res.pupils_without_email]
    with database.connect() as conn:
        _audit(conn, "remind", actor, detail={"pupils": len(by_pupil), "sent": len(sent)})
    activity_log.record("library.remind", principal=actor, pupils=len(by_pupil))
    return {"sent": sent, "no_email": no_email}


def popular(*, days: int = 365, limit: int = 20) -> list[tuple[Book, int]]:
    since = (_today() - _dt.timedelta(days=days)).isoformat()
    with database.connect() as conn:
        rows = conn.execute("SELECT book_id, COUNT(*) AS n FROM library_loans WHERE "
                            "loan_date >= ? GROUP BY book_id ORDER BY n DESC, book_id LIMIT ?",
                            (since, int(limit))).fetchall()
    return [(get_book(r["book_id"]), r["n"]) for r in rows]


def reading_report(*, days: int = 365, year_group: int | None = None) -> dict[str, Any]:
    """Who borrows: per year group, FSM, and pupils who haven't borrowed."""
    since = (_today() - _dt.timedelta(days=days)).isoformat()
    pupils = P.list_pupils(year_group=year_group)
    with database.connect() as conn:
        counts = Counter(dict(conn.execute(
            "SELECT pupil_id, COUNT(*) FROM library_loans WHERE loan_date >= ? GROUP BY "
            "pupil_id", (since,)).fetchall()))

    def pct(group: list[P.Pupil]) -> float | None:
        return round(sum(1 for p in group if counts[p.pupil_id]) * 100 / len(group), 1) \
            if group else None
    years = sorted({p.year_group for p in pupils})
    return {"pupils": len(pupils), "borrowers": sum(1 for p in pupils if counts[p.pupil_id]),
            "loans": sum(counts[p.pupil_id] for p in pupils), "all_pct": pct(pupils),
            "fsm_pct": pct([p for p in pupils if p.fsm_eligible]),
            "by_year": {y: pct([p for p in pupils if p.year_group == y]) for y in years},
            "top_readers": sorted(((p, counts[p.pupil_id]) for p in pupils
                                   if counts[p.pupil_id]),
                                  key=lambda t: (-t[1], t[0].legal_last_name))[:20],
            "non_borrowers": [p for p in pupils if not counts[p.pupil_id]]}


def for_pupil(pupil_id: int) -> dict[str, Any]:
    """Books out now and reservations (for the pupil profile)."""
    out = list_loans(pupil_id=pupil_id, status="Out")
    return {"out": out, "overdue": [x for x in out if x.days_overdue],
            "holds": list_holds(pupil_id=pupil_id),
            "total": len(pupil_loans(pupil_id))}


def export_catalogue(path: str | Path, *, actor: Principal) -> int:
    _require_staff(actor, "library.export")
    rows = list_books()
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["Book ID", "ISBN", "Title", "Author", "Publisher", "Category", "Year",
                    "Subject", "Reading level", "Location", "Copies", "On shelf", "On loan",
                    "Reserved", "Active"])
        for b in rows:
            w.writerow([_safe(x) for x in (
                b.book_id, b.isbn, b.title, b.author, b.publisher, b.category,
                b.year_published, b.subject_code, b.reading_level, b.location, b.copies_total,
                b.copies_available, b.on_loan, b.waiting, "Yes" if b.is_active else "No")])
    activity_log.record("library.export", principal=actor, rows=len(rows))
    return len(rows)


def export_overdue(path: str | Path, *, actor: Principal) -> int:
    _require_staff(actor, "library.export")
    rows = overdue()
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["Admission no", "Pupil", "Year", "Form", "Book", "Barcode", "Loaned",
                    "Due", "Days overdue"])
        for x in rows:
            w.writerow([_safe(v) for v in (x.admission_no, x.pupil_name, x.year_group,
                                           x.form_group, x.book_title, x.barcode, x.loan_date,
                                           x.due_date, x.days_overdue)])
    activity_log.record("library.export", principal=actor, rows=len(rows))
    return len(rows)


S.register_usage("library_books", "subject_id", "library book(s)")
