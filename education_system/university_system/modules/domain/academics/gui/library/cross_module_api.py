"""Library → cross-module API.

Read-only helpers other GUIs can import to display a small summary of
a given student's library activity (active loans, overdue items,
outstanding fines, recent reservations) without having to know the
library schema.

All functions are best-effort — they return safe empty values on any
DB error so callers can render a "no data" panel instead of crashing.
"""
from __future__ import annotations

import logging
import sqlite3
import tkinter as tk
from dataclasses import dataclass, field
from datetime import datetime, date
from tkinter import ttk
from typing import List

from education_system.university_system.core.paths import (
    DEFAULT_DB_PATH,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data accessors
# ---------------------------------------------------------------------------
@dataclass
class LibrarySummary:
    user_id: str
    active_loans: int = 0
    overdue_loans: int = 0
    total_loans_lifetime: int = 0
    outstanding_fines: float = 0.0
    open_reservations: int = 0
    recent: List[tuple] = field(default_factory=list)
    # Each `recent` entry: (book_id, title, status, due_date, return_date)


def _conn():
    try:
        return sqlite3.connect(str(DEFAULT_DB_PATH))
    except Exception:
        logger.exception("Could not open %s", DEFAULT_DB_PATH)
        return None


def _scalar(cursor, query, params, default):
    try:
        row = cursor.execute(query, params).fetchone()
        if row is None or row[0] is None:
            return default
        return row[0]
    except Exception:
        logger.exception("scalar query failed: %s", query)
        return default


def get_library_summary(user_id) -> LibrarySummary:
    """Return a snapshot of the user's library activity. Empty/zero on
    any error or when the user has no library activity."""
    summary = LibrarySummary(user_id=str(user_id))
    if not user_id:
        return summary
    conn = _conn()
    if conn is None:
        return summary
    try:
        cur = conn.cursor()
        today = date.today().isoformat()

        summary.active_loans = _scalar(
            cur,
            "SELECT COUNT(*) FROM book_loans "
            "WHERE user_id = ? AND status = 'active'",
            (str(user_id),), 0)

        summary.overdue_loans = _scalar(
            cur,
            "SELECT COUNT(*) FROM book_loans "
            "WHERE user_id = ? "
            "AND status = 'active' "
            "AND due_date IS NOT NULL "
            "AND date(due_date) < date(?)",
            (str(user_id), today), 0)

        summary.total_loans_lifetime = _scalar(
            cur,
            "SELECT COUNT(*) FROM book_loans WHERE user_id = ?",
            (str(user_id),), 0)

        summary.outstanding_fines = float(_scalar(
            cur,
            "SELECT COALESCE(SUM(fine_amount), 0) FROM book_loans "
            "WHERE user_id = ? AND COALESCE(fine_amount, 0) > 0 "
            "AND status != 'returned'",
            (str(user_id),), 0.0) or 0.0)

        summary.open_reservations = _scalar(
            cur,
            "SELECT COUNT(*) FROM book_reservations "
            "WHERE user_id = ? AND COALESCE(status, 'pending') "
            "IN ('pending', 'active', 'ready')",
            (str(user_id),), 0)

        try:
            rows = cur.execute(
                "SELECT bl.book_id, COALESCE(b.title, ''), bl.status, "
                "bl.due_date, bl.return_date "
                "FROM book_loans bl "
                "LEFT JOIN books b ON b.book_id = bl.book_id "
                "WHERE bl.user_id = ? "
                "ORDER BY bl.checkout_date DESC LIMIT 10",
                (str(user_id),)).fetchall()
            summary.recent = [tuple(r) for r in rows]
        except Exception:
            logger.exception("recent loans lookup failed")
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return summary


# ---------------------------------------------------------------------------
# Embeddable summary widget
# ---------------------------------------------------------------------------
class LibrarySummaryFrame(ttk.LabelFrame):
    """A drop-in ttk.LabelFrame that renders a user's library activity.

    Usage from another GUI::

        from education_system.university_system.modules.domain.academics.gui.library.cross_module_api import (
            LibrarySummaryFrame,
        )
        panel = LibrarySummaryFrame(parent_frame, user_id="S12345")
        panel.pack(fill="both", expand=True)

    Pass ``on_open_library`` (callable accepting no args) to wire the
    "Open Library →" button — typical caller passes a lambda that
    invokes ``self.show_library_management()`` on the unified GUI.
    """

    def __init__(self, master, user_id, on_open_library=None, **kw):
        super().__init__(master, text=f"📚 Library activity — {user_id}",
                         padding=8, **kw)
        self.user_id = user_id
        self.on_open_library = on_open_library
        self._build()
        self.refresh()

    def _build(self):
        top = ttk.Frame(self)
        top.pack(fill="x")

        # Stats grid
        self._stat_vars = {
            k: tk.StringVar(value="—") for k in (
                "active", "overdue", "lifetime", "fines", "reservations")
        }
        labels = [
            ("Active loans",     "active"),
            ("Overdue",          "overdue"),
            ("Lifetime loans",   "lifetime"),
            ("Outstanding fines", "fines"),
            ("Open reservations", "reservations"),
        ]
        for c in range(len(labels)):
            top.columnconfigure(c, weight=1)
        for col, (label, key) in enumerate(labels):
            cell = ttk.Frame(top, padding=4)
            cell.grid(row=0, column=col, sticky="nsew", padx=2)
            ttk.Label(cell, textvariable=self._stat_vars[key],
                      font=("Arial", 14, "bold")).pack()
            ttk.Label(cell, text=label, font=("Arial", 8),
                      foreground="#555").pack()

        # Recent loans table
        ttk.Label(self, text="Recent activity",
                  font=("Arial", 9, "bold")).pack(anchor="w", pady=(8, 2))
        cols = ("book_id", "title", "status", "due", "returned")
        self._tree = ttk.Treeview(self, columns=cols, show="headings",
                                  height=6)
        for c, w in zip(cols, (80, 240, 80, 100, 100)):
            self._tree.heading(c, text=c.replace("_", " ").title())
            self._tree.column(c, width=w, anchor="w")
        self._tree.pack(fill="both", expand=True)

        # Action bar
        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(6, 0))
        ttk.Button(bar, text="🔄 Refresh",
                   command=self.refresh).pack(side="left")
        if callable(self.on_open_library):
            ttk.Button(bar, text="📚 Open Library →",
                       command=self._open_library).pack(side="right")

    def _open_library(self):
        try:
            self.on_open_library()
        except Exception:
            logger.exception("on_open_library callback failed")

    def refresh(self):
        try:
            s = get_library_summary(self.user_id)
            self._stat_vars["active"].set(str(s.active_loans))
            self._stat_vars["overdue"].set(str(s.overdue_loans))
            self._stat_vars["lifetime"].set(str(s.total_loans_lifetime))
            self._stat_vars["fines"].set(f"£{s.outstanding_fines:,.2f}")
            self._stat_vars["reservations"].set(str(s.open_reservations))
            for row in self._tree.get_children():
                self._tree.delete(row)
            for book_id, title, status, due, returned in s.recent:
                self._tree.insert("", "end", values=(
                    book_id or "",
                    (title or "")[:60],
                    status or "",
                    (due or "")[:10],
                    (returned or "")[:10],
                ))
        except Exception:
            logger.exception("LibrarySummaryFrame refresh failed")


# ---------------------------------------------------------------------------
# Reading-list panel — embeddable list of items in a single reading list
# ---------------------------------------------------------------------------
def get_reading_lists_for_creator(creator_id):
    """Return [(list_id, name, category, item_count), …] for *creator_id*.

    *creator_id* can be a course code, instructor user_id, or any other
    string the reading_lists.creator_id field uses."""
    if not creator_id:
        return []
    conn = _conn()
    if conn is None:
        return []
    try:
        rows = conn.execute(
            "SELECT rl.list_id, rl.name, rl.category, "
            "       (SELECT COUNT(*) FROM reading_list_items rli "
            "        WHERE rli.list_id = rl.list_id) AS item_count "
            "FROM reading_lists rl "
            "WHERE rl.creator_id = ? "
            "ORDER BY rl.created_date DESC", (str(creator_id),)
        ).fetchall()
        return [tuple(r) for r in rows]
    except Exception:
        logger.exception("get_reading_lists_for_creator failed")
        return []
    finally:
        try:
            conn.close()
        except Exception:
            pass


def get_reading_list_items(list_id):
    """Return [(book_id, title, author, notes, order), …] for *list_id*."""
    if not list_id:
        return []
    conn = _conn()
    if conn is None:
        return []
    try:
        rows = conn.execute(
            "SELECT rli.book_id, COALESCE(b.title, ''), "
            "       COALESCE(b.author, ''), rli.notes, rli.order_index "
            "FROM reading_list_items rli "
            "LEFT JOIN books b ON b.book_id = rli.book_id "
            "WHERE rli.list_id = ? "
            "ORDER BY COALESCE(rli.order_index, 0), rli.added_date",
            (list_id,)
        ).fetchall()
        return [tuple(r) for r in rows]
    except Exception:
        logger.exception("get_reading_list_items failed")
        return []
    finally:
        try:
            conn.close()
        except Exception:
            pass


class ReadingListPanel(ttk.LabelFrame):
    """Embed in any GUI to show reading lists for a course / creator.

    Two-pane: left selector listing the creator's reading lists, right
    pane shows the selected list's items.

    Usage::

        from education_system.university_system.modules.domain.academics.gui.library.cross_module_api import (
            ReadingListPanel,
        )
        panel = ReadingListPanel(parent_frame, creator_id="CS101")
        panel.pack(fill="both", expand=True)
    """

    def __init__(self, master, creator_id, **kw):
        super().__init__(
            master,
            text=f"📖 Reading lists — {creator_id}",
            padding=8, **kw)
        self.creator_id = creator_id
        self._build()
        self.refresh()

    def _build(self):
        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(0, weight=1)

        # Left: list of reading lists
        left = ttk.LabelFrame(body, text="Lists", padding=4)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self._lists_tree = ttk.Treeview(
            left, columns=("name", "category", "items"),
            show="headings", height=10)
        for c, w in zip(("name", "category", "items"), (180, 100, 50)):
            self._lists_tree.heading(c, text=c.title())
            self._lists_tree.column(c, width=w, anchor="w")
        self._lists_tree.pack(fill="both", expand=True)
        self._lists_tree.bind("<<TreeviewSelect>>", self._on_select_list)

        # Right: items in the selected list
        right = ttk.LabelFrame(body, text="Items", padding=4)
        right.grid(row=0, column=1, sticky="nsew")
        self._items_tree = ttk.Treeview(
            right, columns=("book_id", "title", "author", "notes"),
            show="headings", height=10)
        for c, w in zip(("book_id", "title", "author", "notes"),
                        (80, 230, 150, 180)):
            self._items_tree.heading(c, text=c.title())
            self._items_tree.column(c, width=w, anchor="w")
        self._items_tree.pack(fill="both", expand=True)

        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(6, 0))
        ttk.Button(bar, text="🔄 Refresh",
                   command=self.refresh).pack(side="left")

    def _on_select_list(self, _evt=None):
        sel = self._lists_tree.selection()
        if not sel:
            return
        try:
            list_id = self._lists_tree.item(sel[0]).get("tags", [None])[0]
        except Exception:
            return
        if list_id is None:
            return
        for row in self._items_tree.get_children():
            self._items_tree.delete(row)
        for book_id, title, author, notes, _order in (
                get_reading_list_items(int(list_id))):
            self._items_tree.insert("", "end", values=(
                book_id or "",
                (title or "")[:60],
                (author or "")[:40],
                (notes or "")[:60],
            ))

    def refresh(self):
        for row in self._lists_tree.get_children():
            self._lists_tree.delete(row)
        for row in self._items_tree.get_children():
            self._items_tree.delete(row)
        rows = get_reading_lists_for_creator(self.creator_id)
        if not rows:
            self._lists_tree.insert("", "end",
                values=("(no reading lists)", "", ""))
            return
        for list_id, name, category, count in rows:
            self._lists_tree.insert(
                "", "end",
                values=((name or "")[:60], category or "", count or 0),
                tags=(str(list_id),))
