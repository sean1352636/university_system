"""Waitlist management screen for the Housing Accommodation GUI.

Surfaces the rows backed by ``services.housing_accommodation.waitlist``:

- list current Waiting / Promoted / Removed entries with filters
- add an application to the queue
- remove an entry
- promote the next candidate that matches an available room

Auto-promotion also runs from the move-out workflow when a room frees
up, so this screen is mostly for inspecting state and handling edge
cases (skip-queue, manual prioritisation, removing stale entries).
"""

from __future__ import annotations

import logging
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from education_system.university_system.infrastructure.database.db import (
    get_connection,
)
from education_system.university_system.modules.domain.campus.housing.services.housing_accommodation import (
    waitlist as svc,
)

logger = logging.getLogger(__name__)


def show_waitlist(gui_instance) -> None:
    """Mount the waitlist screen in the GUI's content area."""
    gui_instance.clear_content()
    parent = gui_instance.content_frame

    # ── Header + filter bar ──
    header = ttk.Frame(parent)
    header.pack(fill="x", padx=8, pady=(8, 4))
    ttk.Label(header, text="Housing Waitlist",
              font=("Arial", 14, "bold")).pack(side="left")
    ttk.Button(header, text="Refresh",
               command=lambda: show_waitlist(gui_instance)).pack(side="right")

    filters = ttk.LabelFrame(parent, text="Filters", padding=6)
    filters.pack(fill="x", padx=8, pady=4)

    status_var = tk.StringVar(value="Waiting")
    ttk.Label(filters, text="Status:").pack(side="left")
    ttk.Combobox(filters, textvariable=status_var,
                 values=["Waiting", "Promoted", "Removed", "(all)"],
                 state="readonly", width=12).pack(side="left", padx=(4, 12))

    building_var = tk.StringVar()
    ttk.Label(filters, text="Building:").pack(side="left")
    building_combo = ttk.Combobox(filters, textvariable=building_var,
                                   width=28, state="readonly")
    building_combo.pack(side="left", padx=(4, 12))
    buildings = _load_buildings()
    building_combo['values'] = ["(any)"] + [b[1] for b in buildings]
    building_combo.current(0)

    room_type_var = tk.StringVar()
    ttk.Label(filters, text="Room type:").pack(side="left")
    ttk.Entry(filters, textvariable=room_type_var,
              width=14).pack(side="left", padx=(4, 12))

    # ── Table ──
    cols = ("waitlist_id", "student", "building", "room_type",
            "priority", "status", "added_at", "assignment")
    tree = ttk.Treeview(parent, columns=cols, show="headings", height=14)
    for c, label, w in [
        ("waitlist_id", "Waitlist ID", 130),
        ("student", "Student", 220),
        ("building", "Building", 180),
        ("room_type", "Room type", 90),
        ("priority", "Priority", 70),
        ("status", "Status", 90),
        ("added_at", "Added", 150),
        ("assignment", "Assignment", 130),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True, padx=8, pady=4)

    summary_var = tk.StringVar()
    ttk.Label(parent, textvariable=summary_var,
              foreground="#666").pack(anchor="w", padx=8)

    def reload() -> None:
        for it in tree.get_children():
            tree.delete(it)
        s = status_var.get()
        bsel = building_combo.current()
        b_id = buildings[bsel - 1][0] if bsel > 0 else None
        rt = room_type_var.get().strip() or None
        try:
            rows = svc.list_waitlist(
                status=(None if s == "(all)" else s),
                building_id=b_id, room_type=rt)
        except Exception as e:
            logger.exception("Waitlist load failed")
            messagebox.showerror("Waitlist",
                                 f"Could not load waitlist:\n\n{e}",
                                 parent=gui_instance.root)
            return
        for r in rows:
            tree.insert("", "end", iid=r['waitlist_id'], values=(
                r['waitlist_id'],
                f"{r['student_name']} ({r['student_id']})",
                r['building_name'],
                r['room_type'] or "(any)",
                r['priority'], r['status'],
                r['added_at'],
                r['promoted_to_assignment_id'] or "—",
            ))
        summary_var.set(f"{len(rows)} entr{'y' if len(rows) == 1 else 'ies'}")

    ttk.Button(filters, text="Apply", command=reload).pack(side="left")

    # ── Actions ──
    actions = ttk.Frame(parent)
    actions.pack(fill="x", padx=8, pady=4)
    ttk.Button(actions, text="Add application…",
               command=lambda: _add_dialog(gui_instance, reload)).pack(
        side="left")
    ttk.Button(actions, text="Remove selected",
               command=lambda: _remove_selected(tree, gui_instance, reload)).pack(
        side="left", padx=4)
    ttk.Button(actions, text="Promote next available…",
               command=lambda: _promote_dialog(gui_instance, reload)).pack(
        side="left", padx=4)

    reload()


# ── Internals ──────────────────────────────────────────────────────────

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
        logger.exception("Failed to load buildings for waitlist filters")
        return []


def _add_dialog(gui_instance, on_done):
    dlg = tk.Toplevel(gui_instance.root)
    dlg.title("Add to waitlist")
    dlg.geometry("520x220")
    dlg.transient(gui_instance.root)
    body = ttk.Frame(dlg, padding=10)
    body.pack(fill="both", expand=True)

    ttk.Label(body, text="Application ID:").grid(row=0, column=0, sticky="e")
    app_var = tk.StringVar()
    app_combo = ttk.Combobox(body, textvariable=app_var, width=46,
                              state="readonly")
    app_combo.grid(row=0, column=1, sticky="w", pady=2)

    try:
        conn = get_connection()
        try:
            apps = conn.execute('''
                SELECT a.application_id,
                       s.first_name || ' ' || s.last_name,
                       a.preferred_room_type, a.status
                FROM housing_applications a
                LEFT JOIN students s ON s.student_id = a.student_id
                WHERE a.status IN ('Pending', 'Waiting List', 'More Info Needed')
                ORDER BY a.application_date DESC
            ''').fetchall()
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("Could not load applications for waitlist picker")
        apps = []
    labels = [f"{a[0]} · {a[1]} · {a[2]} ({a[3]})" for a in apps]
    app_combo['values'] = labels or ["(no eligible applications)"]
    if labels:
        app_combo.current(0)
    else:
        app_combo.configure(state="disabled")

    ttk.Label(body, text="Priority (higher first):").grid(row=1, column=0,
                                                          sticky="e", pady=2)
    pri_var = tk.IntVar(value=0)
    ttk.Spinbox(body, from_=0, to=100, textvariable=pri_var,
                width=8).grid(row=1, column=1, sticky="w")

    ttk.Label(body, text="Notes (optional):").grid(row=2, column=0,
                                                    sticky="e", pady=2)
    notes_var = tk.StringVar()
    ttk.Entry(body, textvariable=notes_var, width=46).grid(
        row=2, column=1, sticky="w")

    def save():
        i = app_combo.current()
        if i < 0 or i >= len(apps):
            return
        try:
            wid = svc.add_to_waitlist(apps[i][0],
                                       priority=int(pri_var.get() or 0),
                                       notes=notes_var.get().strip() or None)
        except Exception as e:
            logger.exception("Add-to-waitlist failed")
            messagebox.showerror("Waitlist", f"Could not add:\n\n{e}",
                                 parent=dlg)
            return
        if not wid:
            messagebox.showerror("Waitlist", "Failed to add application "
                                              "(see logs).", parent=dlg)
            return
        dlg.destroy()
        on_done()

    bar = ttk.Frame(body)
    bar.grid(row=3, column=0, columnspan=2, sticky="e", pady=(12, 0))
    ttk.Button(bar, text="Cancel", command=dlg.destroy).pack(side="right",
                                                              padx=4)
    ttk.Button(bar, text="Add", command=save).pack(side="right")


def _remove_selected(tree, gui_instance, on_done):
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Waitlist", "Select an entry first.",
                            parent=gui_instance.root)
        return
    reason = simpledialog.askstring("Remove from waitlist",
                                     "Reason (optional):",
                                     parent=gui_instance.root)
    try:
        if svc.remove(sel, reason=reason):
            on_done()
        else:
            messagebox.showwarning("Waitlist",
                                    "Could not remove — already terminal "
                                    "or not found.",
                                    parent=gui_instance.root)
    except Exception as e:
        logger.exception("Waitlist remove failed")
        messagebox.showerror("Waitlist", f"Remove failed:\n\n{e}",
                              parent=gui_instance.root)


def _promote_dialog(gui_instance, on_done):
    """Find the first available housing_room and promote a matching
    waitlist row into it. Walks rooms in stable order so the user can
    repeat the action until no more matches remain."""
    try:
        conn = get_connection()
        try:
            rooms = conn.execute('''
                SELECT room_id, building_id, room_number, room_type
                FROM housing_rooms
                WHERE status='Available'
                ORDER BY building_id, room_number
            ''').fetchall()
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.exception("Could not list available rooms")
        messagebox.showerror("Promote", f"Could not list rooms:\n\n{e}",
                              parent=gui_instance.root)
        return

    promoted = 0
    skipped = 0
    for room_id, _bid, _rn, _rt in rooms:
        try:
            summary = svc.promote_room_to_next(
                room_id,
                created_by=(gui_instance.auth.current_user.get('username')
                            if gui_instance.auth and gui_instance.auth.current_user
                            else 'manual'))
            if summary:
                promoted += 1
            else:
                skipped += 1
        except Exception:
            logger.exception("Promotion attempt failed for room %s", room_id)
            skipped += 1

    messagebox.showinfo("Promote",
                         f"Available rooms scanned: {len(rooms)}\n"
                         f"Promoted: {promoted}\n"
                         f"No-match / skipped: {skipped}",
                         parent=gui_instance.root)
    on_done()
