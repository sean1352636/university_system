"""Cross-building vacancy board for the Housing Accommodation GUI.

Live view over ``housing_rooms`` filtered to ``status='Available'`` and
joined with their building. Differs from the static Room Availability
report by being interactive — filter by building, room type, rent
ceiling, accessibility, then sort any column. Refresh re-runs the query
so the board reflects the latest state after move-outs / new bookings.
"""

from __future__ import annotations

import logging
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox

from education_system.university_system.infrastructure.database.db import (
    get_connection,
)

logger = logging.getLogger(__name__)


def show_vacancy_board(gui_instance) -> None:
    """Mount the vacancy board in the GUI's content area."""
    gui_instance.clear_content()
    parent = gui_instance.content_frame

    # ── Header ──
    header = ttk.Frame(parent)
    header.pack(fill="x", padx=8, pady=(8, 4))
    ttk.Label(header, text="Vacancy Board — Available Rooms",
              font=("Arial", 14, "bold")).pack(side="left")

    # ── Filters ──
    filters = ttk.LabelFrame(parent, text="Filters", padding=6)
    filters.pack(fill="x", padx=8, pady=4)

    ttk.Label(filters, text="Building:").grid(row=0, column=0, sticky="e",
                                                padx=4, pady=2)
    building_var = tk.StringVar()
    building_combo = ttk.Combobox(filters, textvariable=building_var,
                                    state="readonly", width=30)
    building_combo.grid(row=0, column=1, sticky="w", padx=4)
    buildings = _load_buildings()
    building_combo['values'] = ["(any)"] + [b[1] for b in buildings]
    building_combo.current(0)

    ttk.Label(filters, text="Room type:").grid(row=0, column=2, sticky="e",
                                                  padx=4)
    type_var = tk.StringVar()
    type_combo = ttk.Combobox(filters, textvariable=type_var,
                                state="readonly", width=18)
    type_combo['values'] = ["(any)"] + _load_room_types()
    type_combo.grid(row=0, column=3, sticky="w", padx=4)
    type_combo.current(0)

    ttk.Label(filters, text="Max rent (£):").grid(row=0, column=4,
                                                     sticky="e", padx=4)
    rent_var = tk.StringVar()
    ttk.Entry(filters, textvariable=rent_var, width=10).grid(
        row=0, column=5, sticky="w", padx=4)

    access_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(filters, text="Accessible only",
                    variable=access_var).grid(row=0, column=6, padx=8)

    # ── Table ──
    cols = ("building", "room_number", "floor", "room_type", "rent",
            "accessible", "occupancy")
    headings = [
        ("building", "Building", 220),
        ("room_number", "Room", 80),
        ("floor", "Floor", 60),
        ("room_type", "Type", 110),
        ("rent", "Monthly Rent", 110),
        ("accessible", "Accessible", 90),
        ("occupancy", "Occupancy", 100),
    ]
    table_frame = ttk.Frame(parent)
    table_frame.pack(fill="both", expand=True, padx=8, pady=4)
    tree = ttk.Treeview(table_frame, columns=cols, show="headings", height=18)

    # Track sort state per column.
    sort_state: dict[str, bool] = {c: False for c in cols}

    def make_sorter(col_key: str):
        def _sort():
            sort_state[col_key] = not sort_state[col_key]
            items = [(tree.set(k, col_key), k) for k in tree.get_children('')]
            def _key(pair):
                v = pair[0]
                # Numeric coercion for rent / floor / occupancy.
                stripped = v.lstrip('£').replace(',', '').split('/', 1)[0].strip()
                try:
                    return (0, float(stripped))
                except ValueError:
                    return (1, v.lower())
            items.sort(key=_key, reverse=sort_state[col_key])
            for i, (_, k) in enumerate(items):
                tree.move(k, '', i)
        return _sort

    for key, label, w in headings:
        tree.heading(key, text=label, command=make_sorter(key))
        tree.column(key, width=w, anchor="w")

    sb = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y")
    tree.pack(side="left", fill="both", expand=True)

    # ── Status line ──
    summary_var = tk.StringVar()
    ttk.Label(parent, textvariable=summary_var,
              foreground="#666").pack(anchor="w", padx=8, pady=(0, 6))

    def reload() -> None:
        for it in tree.get_children():
            tree.delete(it)

        bsel = building_combo.current()
        b_id = buildings[bsel - 1][0] if bsel > 0 else None
        rt = type_var.get() if type_combo.current() > 0 else None
        try:
            max_rent = float(rent_var.get().strip()) if rent_var.get().strip() else None
        except ValueError:
            messagebox.showwarning("Vacancy board",
                                    "Max rent must be numeric.",
                                    parent=gui_instance.root)
            return
        accessible_only = access_var.get()

        sql = '''
            SELECT b.building_name, r.room_number, r.floor_number,
                   r.room_type, r.monthly_rent, r.is_accessible,
                   r.current_occupants, r.max_occupants, r.room_id, b.building_id
            FROM housing_rooms r
            JOIN housing_buildings b ON b.building_id = r.building_id
            WHERE r.status = 'Available'
        '''
        args: list = []
        if b_id:
            sql += " AND r.building_id = ?"
            args.append(b_id)
        if rt:
            sql += " AND r.room_type = ?"
            args.append(rt)
        if max_rent is not None:
            sql += " AND r.monthly_rent <= ?"
            args.append(max_rent)
        if accessible_only:
            sql += " AND r.is_accessible = 1"
        sql += " ORDER BY b.building_name, r.room_number"

        try:
            conn = get_connection()
            try:
                rows = conn.execute(sql, args).fetchall()
            finally:
                conn.close()
        except sqlite3.Error as e:
            logger.exception("Vacancy board query failed")
            messagebox.showerror("Vacancy board",
                                  f"Could not query rooms:\n\n{e}",
                                  parent=gui_instance.root)
            return

        for (bname, rnum, floor, rtype, rent, is_acc,
             cur_occ, max_occ, room_id, _bid) in rows:
            tree.insert("", "end", iid=room_id, values=(
                bname, rnum, floor if floor is not None else "—",
                rtype,
                f"£{float(rent or 0):,.2f}",
                "Yes" if is_acc else "No",
                f"{cur_occ or 0}/{max_occ or 0}",
            ))
        summary_var.set(
            f"{len(rows)} available room"
            f"{'' if len(rows) == 1 else 's'} matching filters")
        logger.debug("Vacancy board: %d rows (building=%s, type=%s, "
                     "max_rent=%s, accessible=%s)",
                     len(rows), b_id, rt, max_rent, accessible_only)

    ttk.Button(filters, text="Apply",
               command=reload).grid(row=0, column=7, padx=8)
    ttk.Button(header, text="Refresh", command=reload).pack(side="right")

    reload()


# ── Helpers ────────────────────────────────────────────────────────────

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
        logger.exception("Failed to load buildings for vacancy filters")
        return []


def _load_room_types() -> list[str]:
    try:
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT DISTINCT room_type FROM housing_rooms "
                "WHERE room_type IS NOT NULL ORDER BY room_type").fetchall()
            return [r[0] for r in rows]
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("Failed to load room types")
        return []
