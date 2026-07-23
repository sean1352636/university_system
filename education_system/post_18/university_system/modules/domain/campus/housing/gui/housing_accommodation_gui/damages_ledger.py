"""Per-room damages ledger.

Aggregates ``housing_deposit_deductions`` against the room each
assignment occupied. Two panes:

- top: room roll-up — total damages, count, last damage date
- bottom: drill-down — every deduction for the selected room

Useful for spotting recurring problems (a room that keeps generating
£200+ of damage every tenancy needs a structural fix, not another
deduction).
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


def show_damages_ledger(gui_instance) -> None:
    gui_instance.clear_content()
    parent = gui_instance.content_frame

    ttk.Label(parent, text="Damages Ledger (per room)",
              font=("Arial", 14, "bold")).pack(anchor="w", padx=8,
                                                pady=(8, 4))

    # ── Filter bar ──
    bar = ttk.Frame(parent)
    bar.pack(fill="x", padx=8, pady=4)
    ttk.Label(bar, text="Building:").pack(side="left", padx=(0, 4))
    bvar = tk.StringVar()
    bcombo = ttk.Combobox(bar, textvariable=bvar, state="readonly", width=30)
    buildings = _load_buildings()
    bcombo['values'] = ["(any)"] + [b[1] for b in buildings]
    bcombo.current(0)
    bcombo.pack(side="left", padx=(0, 12))

    ttk.Label(bar, text="Min total £:").pack(side="left", padx=(0, 4))
    min_var = tk.StringVar()
    ttk.Entry(bar, textvariable=min_var, width=10).pack(side="left",
                                                          padx=(0, 12))
    ttk.Button(bar, text="Apply",
               command=lambda: reload_rooms()).pack(side="left")

    # ── Room roll-up table ──
    cols = ("room", "building", "room_type", "count", "total",
            "last")
    rooms_tree = ttk.Treeview(parent, columns=cols, show="headings",
                                height=10)
    for k, lbl, w in [
        ("room", "Room", 100),
        ("building", "Building", 240),
        ("room_type", "Room type", 110),
        ("count", "Deductions", 100),
        ("total", "Total £", 110),
        ("last", "Most recent", 150),
    ]:
        rooms_tree.heading(k, text=lbl)
        rooms_tree.column(k, width=w, anchor="w")
    rooms_tree.pack(fill="both", expand=True, padx=8, pady=(4, 2))

    summary_var = tk.StringVar()
    ttk.Label(parent, textvariable=summary_var,
              foreground="#666").pack(anchor="w", padx=8)

    # ── Drill-down ──
    drill_label = ttk.Label(parent, text="Select a room to see its history.",
                             foreground="#666")
    drill_label.pack(anchor="w", padx=8, pady=(8, 2))

    drill_cols = ("date", "assignment", "tenant", "description",
                  "amount", "status")
    drill_tree = ttk.Treeview(parent, columns=drill_cols, show="headings",
                                height=10)
    for k, lbl, w in [
        ("date", "Date", 130),
        ("assignment", "Assignment", 130),
        ("tenant", "Tenant", 200),
        ("description", "Description", 320),
        ("amount", "Amount £", 100),
        ("status", "Status", 100),
    ]:
        drill_tree.heading(k, text=lbl)
        drill_tree.column(k, width=w, anchor="w")
    drill_tree.pack(fill="both", expand=True, padx=8, pady=(0, 6))

    # ── Behaviour ──
    room_cache: dict[str, tuple[str, str]] = {}     # iid -> (room_id, label)

    def reload_rooms() -> None:
        for it in rooms_tree.get_children():
            rooms_tree.delete(it)
        for it in drill_tree.get_children():
            drill_tree.delete(it)
        room_cache.clear()
        b_id = buildings[bcombo.current() - 1][0] if bcombo.current() > 0 \
            else None
        try:
            min_amt = float(min_var.get().strip()) if min_var.get().strip() \
                else 0.0
        except ValueError:
            messagebox.showwarning("Damages ledger",
                                    "Min total must be numeric.",
                                    parent=gui_instance.root)
            return

        sql = '''
            SELECT r.room_id, r.room_number, b.building_name, r.room_type,
                   COUNT(d.deduction_id), COALESCE(SUM(d.amount), 0),
                   MAX(d.created_at)
            FROM housing_rooms r
            JOIN housing_buildings b ON b.building_id = r.building_id
            JOIN housing_assignments a ON a.room_id = r.room_id
            JOIN housing_deposit_deductions d ON d.assignment_id = a.assignment_id
            WHERE d.status IN ('Proposed', 'Applied')
        '''
        args: list = []
        if b_id:
            sql += " AND r.building_id = ?"
            args.append(b_id)
        sql += '''
            GROUP BY r.room_id
            HAVING COALESCE(SUM(d.amount), 0) >= ?
            ORDER BY 6 DESC
        '''
        args.append(min_amt)
        try:
            conn = get_connection()
            try:
                rows = conn.execute(sql, args).fetchall()
            finally:
                conn.close()
        except sqlite3.Error as e:
            logger.exception("Damages ledger query failed")
            messagebox.showerror("Damages ledger",
                                  f"Query failed:\n\n{e}",
                                  parent=gui_instance.root)
            return

        for (room_id, room_num, bname, rtype, cnt, total, last) in rows:
            iid = room_id
            room_cache[iid] = (room_id, f"Room {room_num} · {bname}")
            rooms_tree.insert("", "end", iid=iid, values=(
                room_num, bname, rtype, cnt,
                f"£{float(total or 0):,.2f}", last or '—'))
        summary_var.set(f"{len(rows)} room(s) with damages "
                         f">= £{min_amt:.2f}")
        logger.debug("Damages ledger: %d rooms (building=%s, min=%.2f)",
                     len(rows), b_id, min_amt)

    def on_select(_e=None) -> None:
        sel = rooms_tree.focus()
        if not sel or sel not in room_cache:
            return
        room_id, lbl = room_cache[sel]
        drill_label.config(text=f"Damage history — {lbl}")
        for it in drill_tree.get_children():
            drill_tree.delete(it)
        try:
            conn = get_connection()
            try:
                rows = conn.execute('''
                    SELECT d.created_at, d.assignment_id,
                           s.first_name || ' ' || s.last_name,
                           d.description, d.amount, d.status
                    FROM housing_deposit_deductions d
                    JOIN housing_assignments a ON a.assignment_id = d.assignment_id
                    JOIN students s ON s.student_id = a.student_id
                    WHERE a.room_id = ?
                    ORDER BY d.created_at DESC
                ''', (room_id,)).fetchall()
            finally:
                conn.close()
        except sqlite3.Error as e:
            logger.exception("Drill-down failed")
            messagebox.showerror("Damages ledger",
                                  f"Drill-down failed:\n\n{e}",
                                  parent=gui_instance.root)
            return
        for d_at, asg, tenant, desc, amt, stat in rows:
            drill_tree.insert("", "end", values=(
                d_at, asg, tenant, desc,
                f"£{float(amt or 0):,.2f}", stat))

    rooms_tree.bind("<<TreeviewSelect>>", on_select)
    reload_rooms()


def _load_buildings() -> list[tuple[str, str]]:
    try:
        conn = get_connection()
        try:
            return [(r[0], r[1]) for r in conn.execute(
                "SELECT building_id, building_name "
                "FROM housing_buildings ORDER BY building_name")]
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("Could not load buildings")
        return []
