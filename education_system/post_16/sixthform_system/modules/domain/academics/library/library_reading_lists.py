"""Reading lists and class-set requests (items 29, 30, 31, 33).

Reading lists are curated by teachers against a subject (and optionally
a specific ``course_id``). Each item flags whether a title is
``Required`` or ``Recommended`` (item 30) and can link to an assignment
(item 33). Class sets (item 31) let a teacher request N copies of a
title for a class by a date, which the library works through.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from education_system.post_16.sixthform_system.modules.domain.academics.library import (
    library as _lib,
)

logger = logging.getLogger(__name__)

ValidationError = _lib.ValidationError

REQUIREMENTS: tuple[str, ...] = ("Required", "Recommended")
CLASS_SET_STATUSES: tuple[str, ...] = (
    "Requested", "Reserved", "Fulfilled", "Cancelled",
)


def _notify(method: str, *args) -> None:
    """Best-effort call into the sixth-form email system."""
    try:
        from education_system.post_16.sixthform_system.modules.domain.academics.library import (
            library_notifications as _n,
        )
        getattr(_n, method)(*args)
    except Exception:
        logger.debug("Notification %s skipped", method, exc_info=True)


@dataclass
class ReadingList:
    list_id: int
    title: str
    subject: str | None
    course_id: int | None
    owner: str | None
    academic_year: str | None
    notes: str | None
    created_at: str
    updated_at: str


@dataclass
class ReadingListItem:
    item_id: int
    list_id: int
    book_id: int
    book_title: str
    requirement: str
    assignment_id: int | None
    note: str | None


@dataclass
class ClassSet:
    set_id: int
    book_id: int
    book_title: str
    course_id: int | None
    subject: str | None
    copies_needed: int
    needed_by: str | None
    status: str
    requested_by: str | None
    notes: str | None
    created_at: str


def _rl(r) -> ReadingList:
    return ReadingList(
        list_id=r["list_id"], title=r["title"], subject=r["subject"],
        course_id=r["course_id"], owner=r["owner"],
        academic_year=r["academic_year"], notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"])


# ── Reading lists ─────────────────────────────────────────────────

def create_reading_list(title: str, *, subject: str | None = None,
                         course_id: int | None = None,
                         owner: str | None = None,
                         academic_year: str | None = None,
                         notes: str | None = None) -> ReadingList:
    _lib.init_db()
    if not (title or "").strip():
        raise ValidationError("Reading-list title is required")
    with _lib._connect() as conn:
        cur = conn.execute(
            "INSERT INTO library_reading_lists "
            "(title, subject, course_id, owner, academic_year, notes, "
            " created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))",
            (title.strip(), (subject or "").strip() or None,
             course_id, (owner or "").strip() or None,
             (academic_year or "").strip() or None,
             (notes or "").strip() or None))
        conn.commit()
        lid = cur.lastrowid
    logger.info("Created reading list #%d %r", lid, title)
    out = get_reading_list(lid)
    assert out is not None
    _notify("notify_reading_list_shared", out)
    return out


def get_reading_list(list_id: int) -> ReadingList | None:
    _lib.init_db()
    with _lib._connect() as conn:
        r = conn.execute(
            "SELECT * FROM library_reading_lists WHERE list_id = ?",
            (list_id,)).fetchone()
    return _rl(r) if r else None


def list_reading_lists(*, subject: str | None = None,
                       course_id: int | None = None) -> list[ReadingList]:
    _lib.init_db()
    clauses, args = [], []
    if subject:
        clauses.append("subject = ?")
        args.append(subject.strip())
    if course_id is not None:
        clauses.append("course_id = ?")
        args.append(int(course_id))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _lib._connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM library_reading_lists {where} "
            "ORDER BY title", args).fetchall()
    return [_rl(r) for r in rows]


def delete_reading_list(list_id: int) -> bool:
    _lib.init_db()
    with _lib._connect() as conn:
        cur = conn.execute(
            "DELETE FROM library_reading_lists WHERE list_id = ?",
            (list_id,))
        conn.commit()
    return bool(cur.rowcount)


# ── List items ────────────────────────────────────────────────────

def add_item(list_id: int, book_id: int, *,
             requirement: str = "Recommended",
             assignment_id: int | None = None,
             note: str | None = None) -> ReadingListItem:
    _lib.init_db()
    if get_reading_list(list_id) is None:
        raise ValidationError(f"No reading list #{list_id}")
    if _lib.get_book(book_id) is None:
        raise ValidationError(f"No book #{book_id}")
    if requirement not in REQUIREMENTS:
        raise ValidationError(
            f"Requirement must be one of: {', '.join(REQUIREMENTS)}")
    with _lib._connect() as conn:
        conn.execute(
            "INSERT INTO library_reading_list_items "
            "(list_id, book_id, requirement, assignment_id, note) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(list_id, book_id) DO UPDATE SET "
            "requirement = excluded.requirement, "
            "assignment_id = excluded.assignment_id, "
            "note = excluded.note",
            (int(list_id), int(book_id), requirement, assignment_id,
             (note or "").strip() or None))
        conn.commit()
    items = [i for i in list_items(list_id) if i.book_id == book_id]
    return items[0]


def remove_item(list_id: int, book_id: int) -> bool:
    _lib.init_db()
    with _lib._connect() as conn:
        cur = conn.execute(
            "DELETE FROM library_reading_list_items "
            "WHERE list_id = ? AND book_id = ?",
            (int(list_id), int(book_id)))
        conn.commit()
    return bool(cur.rowcount)


def set_item_requirement(item_id: int, requirement: str) -> None:
    if requirement not in REQUIREMENTS:
        raise ValidationError(
            f"Requirement must be one of: {', '.join(REQUIREMENTS)}")
    _lib.init_db()
    with _lib._connect() as conn:
        conn.execute(
            "UPDATE library_reading_list_items SET requirement = ? "
            "WHERE item_id = ?", (requirement, int(item_id)))
        conn.commit()


def list_items(list_id: int) -> list[ReadingListItem]:
    _lib.init_db()
    with _lib._connect() as conn:
        rows = conn.execute(
            "SELECT i.*, b.title AS book_title "
            "FROM library_reading_list_items i "
            "JOIN library_books b ON b.book_id = i.book_id "
            "WHERE i.list_id = ? "
            "ORDER BY CASE i.requirement WHEN 'Required' THEN 0 "
            "ELSE 1 END, b.title", (int(list_id),)).fetchall()
    return [ReadingListItem(
        item_id=r["item_id"], list_id=r["list_id"],
        book_id=r["book_id"], book_title=r["book_title"],
        requirement=r["requirement"],
        assignment_id=r["assignment_id"], note=r["note"])
        for r in rows]


# ── Class sets (item 31) ──────────────────────────────────────────

def request_class_set(book_id: int, *, copies_needed: int,
                      course_id: int | None = None,
                      subject: str | None = None,
                      needed_by: str | None = None,
                      requested_by: str | None = None,
                      notes: str | None = None) -> ClassSet:
    _lib.init_db()
    if _lib.get_book(book_id) is None:
        raise ValidationError(f"No book #{book_id}")
    if int(copies_needed) <= 0:
        raise ValidationError("copies_needed must be at least 1")
    with _lib._connect() as conn:
        cur = conn.execute(
            "INSERT INTO library_class_sets "
            "(book_id, course_id, subject, copies_needed, needed_by, "
            " status, requested_by, notes, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, 'Requested', ?, ?, "
            "        datetime('now'), datetime('now'))",
            (int(book_id), course_id, (subject or "").strip() or None,
             int(copies_needed), (needed_by or "").strip() or None,
             (requested_by or "").strip() or None,
             (notes or "").strip() or None))
        conn.commit()
        sid = cur.lastrowid
    logger.info("Class-set request #%d: %d copies of book #%d",
                sid, copies_needed, book_id)
    out = get_class_set(sid)
    assert out is not None
    return out


def get_class_set(set_id: int) -> ClassSet | None:
    _lib.init_db()
    with _lib._connect() as conn:
        r = conn.execute(
            "SELECT s.*, b.title AS book_title "
            "FROM library_class_sets s "
            "JOIN library_books b ON b.book_id = s.book_id "
            "WHERE s.set_id = ?", (set_id,)).fetchone()
    if r is None:
        return None
    return ClassSet(
        set_id=r["set_id"], book_id=r["book_id"],
        book_title=r["book_title"], course_id=r["course_id"],
        subject=r["subject"], copies_needed=r["copies_needed"],
        needed_by=r["needed_by"], status=r["status"],
        requested_by=r["requested_by"], notes=r["notes"],
        created_at=r["created_at"])


def list_class_sets(*, status: str | None = None) -> list[ClassSet]:
    _lib.init_db()
    clause, args = "", []
    if status:
        clause = "WHERE s.status = ?"
        args.append(status)
    with _lib._connect() as conn:
        rows = conn.execute(
            "SELECT s.*, b.title AS book_title "
            "FROM library_class_sets s "
            "JOIN library_books b ON b.book_id = s.book_id "
            f"{clause} ORDER BY s.needed_by IS NULL, s.needed_by, "
            "s.set_id", args).fetchall()
    return [ClassSet(
        set_id=r["set_id"], book_id=r["book_id"],
        book_title=r["book_title"], course_id=r["course_id"],
        subject=r["subject"], copies_needed=r["copies_needed"],
        needed_by=r["needed_by"], status=r["status"],
        requested_by=r["requested_by"], notes=r["notes"],
        created_at=r["created_at"]) for r in rows]


def set_class_set_status(set_id: int, status: str) -> ClassSet:
    if status not in CLASS_SET_STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(CLASS_SET_STATUSES)}")
    if get_class_set(set_id) is None:
        raise ValidationError(f"No class set #{set_id}")
    with _lib._connect() as conn:
        conn.execute(
            "UPDATE library_class_sets SET status = ?, "
            "updated_at = datetime('now') WHERE set_id = ?",
            (status, int(set_id)))
        conn.commit()
    out = get_class_set(set_id)
    assert out is not None
    if status in ("Reserved", "Fulfilled"):
        _notify("notify_class_set_ready", out)
    return out
