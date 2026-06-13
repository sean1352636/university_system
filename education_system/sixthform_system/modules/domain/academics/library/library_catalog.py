"""Catalogue helpers: ISBN auto-fill (item 21) and normalised tags
(item 24).

ISBN lookup is deliberately offline and pluggable. The default resolver
reads a JSON map (``data/library/isbn_catalogue.json``) keyed by
normalised ISBN; deployments that want a live service can swap in their
own resolver via :func:`set_isbn_resolver`. Nothing here makes network
calls.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
import re
from typing import Any, Callable

from education_system.sixthform_system.core import paths
from education_system.sixthform_system.modules.domain.academics.library import (
    library as _lib,
)

logger = logging.getLogger(__name__)

ValidationError = _lib.ValidationError

_ISBN_DB = paths.DATA_DIR / "library" / "isbn_catalogue.json"


def _normalise_isbn(isbn: str) -> str:
    return re.sub(r"[^0-9X]", "", (isbn or "").upper())


def _offline_resolver(isbn: str) -> dict[str, Any] | None:
    """Default resolver: look the ISBN up in a local JSON file."""
    if not _ISBN_DB.is_file():
        return None
    try:
        with open(_ISBN_DB, encoding="utf-8") as f:
            catalogue = json.load(f)
    except (OSError, json.JSONDecodeError):
        logger.warning("ISBN catalogue at %s is unreadable", _ISBN_DB)
        return None
    return catalogue.get(_normalise_isbn(isbn))


_RESOLVER: Callable[[str], dict[str, Any] | None] = _offline_resolver


def set_isbn_resolver(fn: Callable[[str], dict[str, Any] | None]) -> None:
    """Override the ISBN resolver (e.g. with a live lookup service)."""
    global _RESOLVER
    _RESOLVER = fn


def lookup_isbn(isbn: str) -> dict[str, Any] | None:
    """Return book fields for an ISBN, or ``None`` if unknown.

    The result is a partial ``create_book`` payload (title, author,
    publisher, publication_year, isbn) that the caller can review before
    saving."""
    norm = _normalise_isbn(isbn)
    if len(norm) not in (10, 13):
        raise ValidationError("ISBN must be 10 or 13 digits")
    data = _RESOLVER(isbn)
    if not data:
        return None
    out = {k: data[k] for k in
           ("title", "author", "publisher", "publication_year")
           if k in data}
    out["isbn"] = isbn.strip()
    return out


def create_book_from_isbn(isbn: str, **overrides) -> "_lib.Book":
    """Look an ISBN up and create the book, applying any overrides.

    Raises ``ValidationError`` if the ISBN can't be resolved."""
    found = lookup_isbn(isbn)
    if not found:
        raise ValidationError(f"No catalogue entry for ISBN {isbn}")
    found.update(overrides)
    return _lib.create_book(found)


# ── Tags ──────────────────────────────────────────────────────────

def _normalise_tag(name: str) -> str:
    return re.sub(r"\s+", " ", (name or "").strip()).lower()


def _tag_id(conn, name: str, *, create: bool = False) -> int | None:
    norm = _normalise_tag(name)
    if not norm:
        return None
    row = conn.execute(
        "SELECT tag_id FROM library_tags WHERE name = ?",
        (norm,)).fetchone()
    if row:
        return row["tag_id"]
    if not create:
        return None
    cur = conn.execute(
        "INSERT INTO library_tags (name) VALUES (?)", (norm,))
    return cur.lastrowid


def add_tag(book_id: int, name: str) -> None:
    _lib.init_db()
    if _lib.get_book(book_id) is None:
        raise ValidationError(f"No book #{book_id}")
    if not _normalise_tag(name):
        raise ValidationError("Tag cannot be empty")
    with _lib._connect() as conn:
        tid = _tag_id(conn, name, create=True)
        conn.execute(
            "INSERT OR IGNORE INTO library_book_tags "
            "(book_id, tag_id) VALUES (?, ?)", (int(book_id), tid))
        conn.commit()


def remove_tag(book_id: int, name: str) -> None:
    _lib.init_db()
    with _lib._connect() as conn:
        tid = _tag_id(conn, name)
        if tid is None:
            return
        conn.execute(
            "DELETE FROM library_book_tags "
            "WHERE book_id = ? AND tag_id = ?", (int(book_id), tid))
        conn.commit()


def set_tags(book_id: int, names: list[str]) -> list[str]:
    """Replace a book's tags with ``names``; returns the stored tags."""
    _lib.init_db()
    if _lib.get_book(book_id) is None:
        raise ValidationError(f"No book #{book_id}")
    wanted = [t for t in {_normalise_tag(n) for n in names} if t]
    with _lib._connect() as conn:
        conn.execute("DELETE FROM library_book_tags WHERE book_id = ?",
                     (int(book_id),))
        for t in wanted:
            tid = _tag_id(conn, t, create=True)
            conn.execute(
                "INSERT OR IGNORE INTO library_book_tags "
                "(book_id, tag_id) VALUES (?, ?)", (int(book_id), tid))
        conn.commit()
    return tags_for_book(book_id)


def tags_for_book(book_id: int) -> list[str]:
    _lib.init_db()
    with _lib._connect() as conn:
        rows = conn.execute(
            "SELECT t.name FROM library_tags t "
            "JOIN library_book_tags bt ON bt.tag_id = t.tag_id "
            "WHERE bt.book_id = ? ORDER BY t.name", (int(book_id),)
        ).fetchall()
    return [r["name"] for r in rows]


def all_tags() -> list[tuple[str, int]]:
    """Every tag with how many books use it, most-used first."""
    _lib.init_db()
    with _lib._connect() as conn:
        rows = conn.execute(
            "SELECT t.name, COUNT(bt.book_id) AS n FROM library_tags t "
            "LEFT JOIN library_book_tags bt ON bt.tag_id = t.tag_id "
            "GROUP BY t.tag_id ORDER BY n DESC, t.name").fetchall()
    return [(r["name"], r["n"]) for r in rows]


def find_books_by_tag(name: str) -> list["_lib.Book"]:
    _lib.init_db()
    norm = _normalise_tag(name)
    with _lib._connect() as conn:
        rows = conn.execute(
            "SELECT b.* FROM library_books b "
            "JOIN library_book_tags bt ON bt.book_id = b.book_id "
            "JOIN library_tags t ON t.tag_id = bt.tag_id "
            "WHERE t.name = ? ORDER BY b.title", (norm,)).fetchall()
    return [_lib._row_book(r) for r in rows]


# ── Discovery shelves (item 26) ───────────────────────────────────

def new_arrivals(*, limit: int = 20,
                 days: int | None = None) -> list["_lib.Book"]:
    """Recently-added titles, newest first."""
    _lib.init_db()
    clauses, args = [], []
    if days is not None:
        cutoff = (_dt.date.today()
                  - _dt.timedelta(days=days)).isoformat()
        clauses.append("date(created_at) >= ?")
        args.append(cutoff)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    args.append(int(limit))
    with _lib._connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM library_books {where} "
            "ORDER BY created_at DESC, book_id DESC LIMIT ?",
            args).fetchall()
    return [_lib._row_book(r) for r in rows]


def popular(*, limit: int = 10,
            since: str | None = None) -> list[tuple["_lib.Book", int]]:
    """Most-borrowed titles, optionally since a date (loans counted by
    ``loaned_on``). Returns ``(book, loan_count)`` pairs."""
    _lib.init_db()
    clauses, args = [], []
    if since:
        clauses.append("l.loaned_on >= ?")
        args.append(since)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    args.append(int(limit))
    with _lib._connect() as conn:
        rows = conn.execute(
            "SELECT b.*, COUNT(l.loan_id) AS n FROM library_books b "
            "JOIN library_loans l ON l.book_id = b.book_id "
            f"{where} GROUP BY b.book_id "
            "ORDER BY n DESC, b.title LIMIT ?", args).fetchall()
    return [(_lib._row_book(r), r["n"]) for r in rows]


def never_borrowed() -> list["_lib.Book"]:
    """Titles that have never been on loan."""
    _lib.init_db()
    with _lib._connect() as conn:
        rows = conn.execute(
            "SELECT b.* FROM library_books b "
            "LEFT JOIN library_loans l ON l.book_id = b.book_id "
            "WHERE l.loan_id IS NULL ORDER BY b.title").fetchall()
    return [_lib._row_book(r) for r in rows]


# ── Duplicate detection (item 27) ─────────────────────────────────

def check_duplicate_isbn(isbn: str) -> list["_lib.Book"]:
    """Existing books whose ISBN matches (ignoring hyphens/case).

    Call this before adding a book so the desk can spot a title that's
    already in stock."""
    _lib.init_db()
    norm = _normalise_isbn(isbn)
    if not norm:
        return []
    out = []
    for b in _lib.list_books():
        if b.isbn and _normalise_isbn(b.isbn) == norm:
            out.append(b)
    return out
