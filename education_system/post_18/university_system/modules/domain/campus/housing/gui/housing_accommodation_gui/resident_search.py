"""Cross-building resident search.

A single search box that returns matching current residents across
every housing building, joined with their room, building, and contact
details. Searches the student's name, student_id, email, and room
number. Default filter is ``Active`` assignments only; flip a toggle to
include Pending / Terminated history.

Double-clicking a row pre-fills the refunds tab for that student
(consistent with the move-out workflow's "Issue refund…" shortcut).
"""

from __future__ import annotations

import logging
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox

from education_system.post_18.university_system.infrastructure.database.db import (
    get_connection,
)

logger = logging.getLogger(__name__)


def show_resident_search(gui_instance) -> None:
    gui_instance.clear_content()
    parent = gui_instance.content_frame

    ttk.Label(parent, text="Cross-Building Resident Search",
              font=("Arial", 14, "bold")).pack(anchor="w", padx=8,
                                                pady=(8, 4))

    # ── Search bar ──
    bar = ttk.Frame(parent)
    bar.pack(fill="x", padx=8, pady=4)
    ttk.Label(bar,
              text="Name / student ID / email / room number:").pack(
        side="left", padx=(0, 4))
    query_var = tk.StringVar()
    entry = ttk.Entry(bar, textvariable=query_var, width=46)
    entry.pack(side="left", padx=(0, 8))

    active_only_var = tk.BooleanVar(value=True)
    ttk.Checkbutton(bar, text="Active only",
                    variable=active_only_var).pack(side="left", padx=4)
    ttk.Button(bar, text="Search", command=lambda: run()).pack(side="left",
                                                                 padx=4)
    ttk.Button(bar, text="Clear",
               command=lambda: (query_var.set(""), run())).pack(
        side="left", padx=4)

    # ── Results ──
    cols = ("student_id", "name", "email", "building", "room",
            "room_type", "status", "assignment")
    tree = ttk.Treeview(parent, columns=cols, show="headings", height=18)
    for k, lbl, w in [
        ("student_id", "Student ID", 100),
        ("name", "Name", 220),
        ("email", "Email", 220),
        ("building", "Building", 200),
        ("room", "Room", 80),
        ("room_type", "Room type", 100),
        ("status", "Status", 90),
        ("assignment", "Assignment", 130),
    ]:
        tree.heading(k, text=lbl)
        tree.column(k, width=w, anchor="w")
    tree.pack(fill="both", expand=True, padx=8, pady=4)

    summary_var = tk.StringVar(value="Type a query and press Enter.")
    ttk.Label(parent, textvariable=summary_var,
              foreground="#666").pack(anchor="w", padx=8, pady=(0, 6))

    def run() -> None:
        q = query_var.get().strip()
        active_only = active_only_var.get()
        for it in tree.get_children():
            tree.delete(it)
        try:
            sql, args = _build_query(q, active_only)
            conn = get_connection()
            try:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(sql, args).fetchall()
            finally:
                conn.close()
        except sqlite3.Error as e:
            logger.exception("Resident search query failed")
            messagebox.showerror("Search",
                                  f"Search failed:\n\n{e}",
                                  parent=gui_instance.root)
            return
        for r in rows:
            tree.insert("", "end", iid=r['assignment_id'], values=(
                r['student_id'], r['name'],
                r['email_address'] or "—",
                r['building_name'], r['room_number'],
                r['room_type'], r['status'],
                r['assignment_id'],
            ))
        summary_var.set(f"{len(rows)} match(es)"
                        + (" — Active only" if active_only else " — all statuses"))
        logger.debug("Resident search '%s' (active_only=%s) -> %d row(s)",
                     q, active_only, len(rows))

    def on_dbl(_e=None) -> None:
        sel = tree.focus()
        if not sel:
            return
        try:
            student_id = tree.item(sel, 'values')[0]
        except Exception:
            return
        try:
            gui_instance.show_refunds()
            if hasattr(gui_instance, 'refund_search_var'):
                gui_instance.refund_search_var.set(student_id)
        except Exception as e:
            logger.exception("Could not open refunds from search")
            messagebox.showerror("Refunds",
                                  f"Could not open refunds:\n\n{e}",
                                  parent=gui_instance.root)

    tree.bind("<Double-1>", on_dbl)
    entry.bind("<Return>", lambda _e: run())
    entry.focus_set()

    run()


# ── Query builder ──────────────────────────────────────────────────────

def _build_query(q: str, active_only: bool) -> tuple[str, list]:
    sql = '''
        SELECT a.assignment_id, a.student_id,
               s.first_name || ' ' || s.last_name AS name,
               s.email_address,
               b.building_name, r.room_number, r.room_type,
               a.status
        FROM housing_assignments a
        JOIN students          s ON s.student_id  = a.student_id
        JOIN housing_rooms     r ON r.room_id     = a.room_id
        JOIN housing_buildings b ON b.building_id = r.building_id
    '''
    clauses: list[str] = []
    args: list = []
    if active_only:
        clauses.append("a.status = 'Active'")
    if q:
        like = f"%{q}%"
        clauses.append(
            "(s.first_name LIKE ? OR s.last_name LIKE ? "
            "OR (s.first_name || ' ' || s.last_name) LIKE ? "
            "OR s.student_id LIKE ? OR s.email_address LIKE ? "
            "OR r.room_number LIKE ?)")
        args.extend([like, like, like, like, like, like])
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY b.building_name, r.room_number, s.last_name"
    return sql, args
