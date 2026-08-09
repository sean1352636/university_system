"""E-resources: borrowable digital links with unlimited access
(item 49).

An e-resource is just a catalogue book with ``item_type == 'E-Resource'``
whose access URL is held in the book's ``location`` field. Unlike a
physical loan, access is unlimited and doesn't touch the copies
counters — :func:`access` simply records who opened it (for usage
stats) and returns the URL.
"""

from __future__ import annotations

import datetime as _dt
import logging

from education_system.systems.sixth_form.domain.academics.library import (
    library as _lib,
)

logger = logging.getLogger(__name__)

ValidationError = _lib.ValidationError
ERESOURCE_TYPE = "E-Resource"


def list_eresources() -> list["_lib.Book"]:
    return _lib.list_books(item_type=ERESOURCE_TYPE)


def access(book_id: int, student_id: str | None = None) -> str:
    """Record an e-resource access and return its URL.

    Does not create a loan or change availability — e-resources have
    unlimited concurrent access."""
    _lib.init_db()
    book = _lib.get_book(book_id)
    if book is None:
        raise ValidationError(f"No book #{book_id}")
    if book.item_type != ERESOURCE_TYPE:
        raise ValidationError(
            f"Book #{book_id} is not an e-resource")
    url = (book.location or "").strip()
    if not url:
        raise ValidationError(
            "This e-resource has no access URL set "
            "(store it in the item's Location field)")
    with _lib._connect() as conn:
        conn.execute(
            "INSERT INTO library_eresource_access "
            "(book_id, student_id, accessed_at) "
            "VALUES (?, ?, ?)",
            (int(book_id), (student_id or "").strip() or None,
             _dt.datetime.now().isoformat(timespec="seconds")))
        conn.commit()
    logger.info("E-resource #%d accessed by %s",
                book_id, student_id or "(anon)")
    return url


def access_count(book_id: int) -> int:
    _lib.init_db()
    with _lib._connect() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM library_eresource_access "
            "WHERE book_id = ?", (int(book_id),)).fetchone()[0]


def usage() -> list[dict]:
    """Access counts per e-resource, most-used first."""
    _lib.init_db()
    with _lib._connect() as conn:
        rows = conn.execute(
            "SELECT b.book_id, b.title, "
            "COUNT(a.access_id) AS n FROM library_books b "
            "LEFT JOIN library_eresource_access a "
            "ON a.book_id = b.book_id "
            "WHERE b.item_type = ? GROUP BY b.book_id "
            "ORDER BY n DESC, b.title", (ERESOURCE_TYPE,)).fetchall()
    return [{"book_id": r["book_id"], "title": r["title"],
             "accesses": r["n"]} for r in rows]
