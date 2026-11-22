"""Searchable dropdowns for the identifiers the library GUI asks for.

Several screens used to want a book, student or user ID typed in by
hand, which meant knowing an opaque code like ``CM-123456789964`` before
you could do anything, and mistyping it produced "not found" rather than
a correction. These build a combobox of real rows instead, labelled with
something a person recognises and carrying the ID underneath.

The combobox stays editable and filters as you type: a readonly list is
unusable once a library holds a few thousand books, and typing "python"
to narrow it is faster than scrolling either way.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk

logger = logging.getLogger(__name__)


def _connect():
    """Open a library DB connection, or None when unavailable."""
    try:
        from education_system.systems.university.infrastructure.database.db import (
            get_connection,
        )
        return get_connection()
    except Exception:
        logger.debug("Library DB unavailable for picker", exc_info=True)
        return None


def _fetch(sql, params=()):
    conn = _connect()
    if conn is None:
        return []
    try:
        return conn.execute(sql, params).fetchall()
    except Exception:
        logger.debug("Picker query failed: %s", sql, exc_info=True)
        return []
    finally:
        try:
            conn.close()
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)


def book_choices(only_available=False, on_loan_only=False):
    """[(book_id, 'B1 — Title by Author')] for the books dropdown."""
    sql = ("SELECT book_id, COALESCE(title,''), COALESCE(author,'') "
           "FROM books")
    if only_available:
        sql += " WHERE COALESCE(status,'available') = 'available'"
    elif on_loan_only:
        sql = ("SELECT DISTINCT b.book_id, COALESCE(b.title,''), COALESCE(b.author,'') "
               "FROM books b JOIN book_loans l ON l.book_id = b.book_id "
               "WHERE l.status IN ('active','overdue')")
    sql += " ORDER BY title COLLATE NOCASE"
    out = []
    for book_id, title, author in _fetch(sql):
        label = f"{book_id} — {title}" if title else str(book_id)
        if author:
            label += f" by {author}"
        out.append((str(book_id), label))
    return out


def student_choices():
    """[(student_id, 'S12345 — First Last (Course)')]."""
    rows = _fetch(
        "SELECT student_id, COALESCE(first_name,''), COALESCE(last_name,''), "
        "       COALESCE(course, COALESCE(program,'')) "
        "FROM students "
        "WHERE COALESCE(is_active, 1) = 1 "
        "ORDER BY last_name COLLATE NOCASE, first_name COLLATE NOCASE")
    out = []
    for sid, first, last, course in rows:
        name = " ".join(p for p in (first, last) if p) or "(no name)"
        label = f"{sid} — {name}"
        if course:
            label += f" ({course})"
        out.append((str(sid), label))
    return out


def user_choices():
    """[(user_id, 'username — First Last (role)')] for library card holders."""
    rows = _fetch(
        "SELECT id, COALESCE(username,''), COALESCE(first_name,''), "
        "       COALESCE(last_name,''), COALESCE(role,'') "
        "FROM users WHERE COALESCE(service_account, 0) = 0 "
        "ORDER BY username COLLATE NOCASE")
    out = []
    for uid, username, first, last, role in rows:
        name = " ".join(p for p in (first, last) if p)
        label = username or str(uid)
        if name:
            label += f" — {name}"
        if role:
            label += f" ({role})"
        out.append((str(uid), label))
    return out


def borrower_choices():
    """Everyone who can hold a loan, students and staff users alike."""
    seen, out = set(), []
    for value, label in student_choices() + user_choices():
        if value not in seen:
            seen.add(value)
            out.append((value, label))
    return out


class IdPicker:
    """An editable, type-to-filter combobox over ``(value, label)`` pairs.

    ``get()`` returns the selected underlying ID. Typing a raw ID that
    isn't in the list still returns it verbatim, so an operator who
    knows the code — or a row the query missed — is never locked out.
    """

    def __init__(self, parent, choices, width=42, empty_label=None,
                 on_select=None):
        self.choices = list(choices)
        self._by_label = {label: value for value, label in self.choices}
        self._by_value = {value: label for value, label in self.choices}
        self._on_select = on_select
        self.var = tk.StringVar()

        self.combo = ttk.Combobox(parent, textvariable=self.var, width=width)
        self.combo["values"] = [label for _v, label in self.choices]
        if not self.choices and empty_label:
            self.var.set(empty_label)
            self.combo.configure(state="disabled")

        self.combo.bind("<KeyRelease>", self._filter)
        self.combo.bind("<<ComboboxSelected>>", self._selected)

    # -- Tk passthroughs so callers can lay it out like any widget --
    def grid(self, **kw):
        self.combo.grid(**kw)
        return self

    def pack(self, **kw):
        self.combo.pack(**kw)
        return self

    def _filter(self, event):
        # Navigation keys must not re-filter, or opening the dropdown with
        # the arrow keys immediately narrows it to whatever was typed.
        if event.keysym in ("Up", "Down", "Return", "Escape", "Tab",
                            "Left", "Right"):
            return
        typed = self.var.get().strip().lower()
        if not typed:
            self.combo["values"] = [label for _v, label in self.choices]
            return
        self.combo["values"] = [
            label for _v, label in self.choices if typed in label.lower()
        ] or [label for _v, label in self.choices]

    def _selected(self, _event=None):
        if callable(self._on_select):
            try:
                self._on_select(self.get())
            except Exception:
                logger.exception("Picker on_select callback failed")

    def get(self):
        """The selected ID, or whatever raw text was typed."""
        text = self.var.get().strip()
        if text in self._by_label:
            return self._by_label[text]
        # A label may have been typed in full, or an ID pasted directly.
        if text in self._by_value:
            return text
        return text.split(" — ")[0].strip() if " — " in text else text

    def set(self, value):
        """Select by underlying ID."""
        if value is None:
            return
        self.var.set(self._by_value.get(str(value), str(value)))


def attach_picker(parent, kind, **kw):
    """Convenience factory: ``kind`` is book / student / user / borrower."""
    loaders = {
        "book": book_choices,
        "available_book": lambda: book_choices(only_available=True),
        "loaned_book": lambda: book_choices(on_loan_only=True),
        "student": student_choices,
        "user": user_choices,
        "borrower": borrower_choices,
    }
    loader = loaders.get(kind)
    if loader is None:
        raise ValueError(f"Unknown picker kind: {kind!r}")
    empty = {
        "book": "No books in the catalogue",
        "available_book": "No books available",
        "loaned_book": "No books currently on loan",
        "student": "No students found",
        "user": "No users found",
        "borrower": "No borrowers found",
    }[kind]
    return IdPicker(parent, loader(), empty_label=empty, **kw)
