"""Small Tk helpers shared by the Student Union Academic screens.

Connections, the signed-in owner id and a parented form dialog, so the
tutoring / study group / resource windows stay thin over
``student_union.services.academic_hub``.
"""

from __future__ import annotations

import logging
import tkinter as tk
from contextlib import contextmanager
from tkinter import ttk, messagebox, scrolledtext

from education_system.systems.university.infrastructure.database.db import get_connection
from education_system.systems.university.domains.student_life.domain.student_life.student_union.identity import (
    current_student_id,
)
from education_system.systems.university.domains.student_life.domain.student_life.student_union.services import (
    academic_hub as hub,
)

logger = logging.getLogger(__name__)

_schema_ready = False


@contextmanager
def hub_conn():
    """Open a connection with the academic hub tables in place."""
    global _schema_ready
    conn = get_connection()
    try:
        if not _schema_ready:
            hub.ensure_schema(conn)
            _schema_ready = True
        yield conn
    finally:
        conn.close()


def owner_id(conn, auth) -> str | None:
    return current_student_id(conn.cursor(), auth)


def report_error(parent, exc: Exception, title: str = "Error") -> None:
    """Show a rule violation plainly, anything else as a failure."""
    if isinstance(exc, hub.AcademicHubError):
        messagebox.showwarning(title if title != "Error" else "Not possible",
                               str(exc), parent=parent)
    else:
        logger.exception("academic hub action failed")
        messagebox.showerror(title, f"Something went wrong: {exc}", parent=parent)


def fill_tree(tree: ttk.Treeview, rows, empty_text: str) -> None:
    """Replace the tree contents; show one greyed row when there is nothing."""
    tree.delete(*tree.get_children())
    if not rows:
        cols = tree['columns']
        tree.insert('', 'end', iid='__empty__',
                    values=(empty_text,) + ('',) * (len(cols) - 1), tags=('empty',))
        tree.tag_configure('empty', foreground='grey')
        return
    for iid, values in rows:
        tree.insert('', 'end', iid=str(iid), values=values)


def selected_id(tree: ttk.Treeview):
    sel = tree.selection()
    if not sel or sel[0] == '__empty__':
        return None
    try:
        return int(sel[0])
    except ValueError:
        return sel[0]


def ask_form(parent, title: str, fields, submit_text: str = "Save"):
    """Modal form parented to ``parent``.

    ``fields`` is a list of ``(key, label, kind, options, default)`` where
    kind is ``entry``, ``text``, ``combo`` (editable), ``choice``
    (readonly) or ``spin`` (options = (from, to)). Returns a dict or None.
    """
    win = tk.Toplevel(parent)
    win.title(title)
    win.transient(parent)
    win.grab_set()
    frame = ttk.Frame(win)
    frame.pack(fill='both', expand=True, padx=15, pady=15)
    getters = {}
    for row, (key, label, kind, options, default) in enumerate(fields):
        ttk.Label(frame, text=label).grid(row=row, column=0, sticky='nw', pady=4)
        if kind == 'text':
            w = scrolledtext.ScrolledText(frame, width=45, height=4, wrap=tk.WORD)
            if default:
                w.insert('1.0', default)
            getters[key] = lambda w=w: w.get('1.0', 'end-1c').strip()
        elif kind in ('combo', 'choice'):
            var = tk.StringVar(value=default or '')
            w = ttk.Combobox(frame, textvariable=var, width=43, values=list(options or ()),
                             state='readonly' if kind == 'choice' else 'normal')
            getters[key] = lambda v=var: v.get().strip()
        elif kind == 'spin':
            lo, hi = options
            w = ttk.Spinbox(frame, from_=lo, to=hi, width=10)
            w.set(default if default is not None else lo)
            getters[key] = lambda w=w: w.get().strip()
        else:
            var = tk.StringVar(value=default or '')
            w = ttk.Entry(frame, textvariable=var, width=46)
            getters[key] = lambda v=var: v.get().strip()
        w.grid(row=row, column=1, sticky='ew', padx=(10, 0), pady=4)
    frame.columnconfigure(1, weight=1)
    result = {}

    def submit():
        result.update({k: g() for k, g in getters.items()})
        win.destroy()

    btns = ttk.Frame(frame)
    btns.grid(row=len(fields), column=0, columnspan=2, sticky='ew', pady=(10, 0))
    ttk.Button(btns, text=submit_text, command=submit).pack(side='left')
    ttk.Button(btns, text="Cancel", command=win.destroy).pack(side='right')
    parent.wait_window(win)
    return result or None


def show_list(parent, title: str, columns, rows, empty_text: str, actions=()):
    """Read-only list window with optional ``(label, callback(tree, win))`` buttons."""
    win = tk.Toplevel(parent)
    win.title(title)
    win.geometry("900x450")
    win.transient(parent)
    win.grab_set()
    frame = ttk.Frame(win)
    frame.pack(fill='both', expand=True, padx=10, pady=10)
    btns = ttk.Frame(frame)
    btns.pack(side='bottom', fill='x', pady=(8, 0))
    tree = ttk.Treeview(frame, columns=columns, show='headings', height=14)
    for col in columns:
        tree.heading(col, text=col)
        tree.column(col, width=max(90, 880 // len(columns)))
    tree.pack(fill='both', expand=True)
    fill_tree(tree, rows, empty_text)
    for label, cb in actions:
        ttk.Button(btns, text=label, command=lambda cb=cb: cb(tree, win)).pack(
            side='left', padx=(0, 8))
    ttk.Button(btns, text="Close", command=win.destroy).pack(side='right')
    return win, tree


def stars(value) -> str:
    return f"{float(value):.1f}/5" if value else "No ratings"
