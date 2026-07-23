"""Visitor / guest-pass management (staff view).

Lists every guest-pass request, lets staff Approve / Deny / Cancel,
and accepts new requests on behalf of a resident (useful when the
front desk is logging an in-person request).
"""

from __future__ import annotations

import datetime
import logging
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from education_system.post_18.university_system.infrastructure.database.db import (
    get_connection,
)
from education_system.post_18.university_system.modules.shared.utils.simple_activity_logger import (
    log_activity,
)
from education_system.post_18.university_system.modules.domain.campus.housing.services.housing_accommodation import (
    extras,
)

logger = logging.getLogger(__name__)


def show_guests(gui_instance) -> None:
    extras.init_extras_schemas()
    gui_instance.clear_content()
    parent = gui_instance.content_frame

    ttk.Label(parent, text="Guest / Visitor Passes",
              font=("Arial", 14, "bold")).pack(anchor="w", padx=8,
                                                pady=(8, 4))

    # ── Filter bar ──
    bar = ttk.Frame(parent)
    bar.pack(fill="x", padx=8, pady=4)
    status_var = tk.StringVar(value="Pending")
    ttk.Label(bar, text="Status:").pack(side="left")
    ttk.Combobox(bar, textvariable=status_var, state="readonly", width=12,
                 values=["Pending", "Approved", "Denied", "Cancelled",
                         "(all)"]).pack(side="left", padx=4)
    ttk.Button(bar, text="Apply",
               command=lambda: reload()).pack(side="left", padx=8)
    ttk.Button(bar, text="New request…",
               command=lambda: _new_request(gui_instance,
                                              reload)).pack(side="right")

    cols = ("pass_id", "student", "guest", "dates", "overnight",
            "status", "decision")
    tree = ttk.Treeview(parent, columns=cols, show="headings", height=14)
    for k, lbl, w in [
        ("pass_id", "Pass ID", 130),
        ("student", "Resident", 220),
        ("guest", "Guest", 220),
        ("dates", "Dates", 180),
        ("overnight", "Overnight", 80),
        ("status", "Status", 90),
        ("decision", "Decision by", 150),
    ]:
        tree.heading(k, text=lbl)
        tree.column(k, width=w, anchor="w")
    tree.pack(fill="both", expand=True, padx=8, pady=4)

    summary_var = tk.StringVar()
    ttk.Label(parent, textvariable=summary_var,
              foreground="#666").pack(anchor="w", padx=8)

    def reload() -> None:
        for it in tree.get_children():
            tree.delete(it)
        s = status_var.get()
        rows = extras.list_guest_passes(
            status=(None if s == "(all)" else s))
        for r in rows:
            tree.insert("", "end", iid=r['pass_id'], values=(
                r['pass_id'],
                f"{r['student_name']} ({r['student_id']}) · "
                f"Room {r['room_number']} {r['building_name']}",
                r['guest_name'] + (f" ({r['guest_relation']})"
                                   if r.get('guest_relation') else ''),
                f"{r['start_date']} → {r['end_date']}",
                "Yes" if r['overnight'] else "No",
                r['status'],
                f"{r.get('decision_by') or ''} "
                f"{r.get('decision_at') or ''}".strip() or '—',
            ))
        summary_var.set(f"{len(rows)} pass(es)")

    act = ttk.Frame(parent)
    act.pack(fill="x", padx=8, pady=(0, 6))

    def _do(label: str, action):
        sel = tree.focus()
        if not sel:
            messagebox.showinfo("Guests", "Select a pass first.",
                                 parent=gui_instance.root)
            return
        who = (gui_instance.auth.current_user.get('username')
                if gui_instance.auth and gui_instance.auth.current_user
                else 'housing-admin')
        try:
            ok = action(sel, who)
        except Exception as e:
            logger.exception("%s pass failed", label)
            messagebox.showerror(label, str(e),
                                  parent=gui_instance.root)
            return
        if not ok:
            messagebox.showwarning(label,
                                    "No change — already terminal or "
                                    "wrong state.",
                                    parent=gui_instance.root)
            return
        log_activity(f"{label} guest pass {sel} ({who})")
        reload()

    ttk.Button(act, text="Approve",
               command=lambda: _do(
                   "Approve",
                   lambda pid, who: extras.decide_guest_pass(
                       pid, approved=True, decision_by=who))).pack(side="left")
    ttk.Button(act, text="Deny",
               command=lambda: _do(
                   "Deny",
                   lambda pid, who: extras.decide_guest_pass(
                       pid, approved=False, decision_by=who))).pack(side="left",
                                                                     padx=4)
    ttk.Button(act, text="Cancel",
               command=lambda: _do(
                   "Cancel",
                   lambda pid, who: extras.cancel_guest_pass(
                       pid, by=who))).pack(side="left", padx=4)

    reload()


def _new_request(gui_instance, on_done):
    asgs = _load_active_assignments()
    if not asgs:
        messagebox.showinfo("New request",
                            "No active assignments.",
                            parent=gui_instance.root)
        return
    dlg = tk.Toplevel(gui_instance.root)
    dlg.title("New guest pass request")
    dlg.geometry("520x340")
    dlg.transient(gui_instance.root)
    body = ttk.Frame(dlg, padding=10)
    body.pack(fill="both", expand=True)

    grid_row = 0

    def row(label, widget):
        nonlocal grid_row
        ttk.Label(body, text=label).grid(row=grid_row, column=0, sticky="e",
                                            padx=(0, 6), pady=2)
        widget.grid(row=grid_row, column=1, sticky="w", pady=2)
        grid_row += 1

    asg_var = tk.StringVar()
    asg_combo = ttk.Combobox(body, textvariable=asg_var, state="readonly",
                              width=46)
    asg_combo['values'] = [a[1] for a in asgs]
    asg_combo.current(0)
    row("Resident assignment:", asg_combo)

    name_var = tk.StringVar()
    row("Guest name:", ttk.Entry(body, textvariable=name_var, width=46))

    relation_var = tk.StringVar()
    row("Relation (e.g. parent):", ttk.Entry(body, textvariable=relation_var,
                                              width=46))

    id_type_var = tk.StringVar()
    row("ID type:",
        ttk.Combobox(body, textvariable=id_type_var, state="readonly",
                     width=20,
                     values=["", "Passport", "Driving licence",
                             "National ID", "Other"]))

    id_ref_var = tk.StringVar()
    row("ID reference:", ttk.Entry(body, textvariable=id_ref_var, width=46))

    start_var = tk.StringVar(value=datetime.date.today().isoformat())
    row("Start date (YYYY-MM-DD):",
        ttk.Entry(body, textvariable=start_var, width=14))

    end_var = tk.StringVar(value=datetime.date.today().isoformat())
    row("End date (YYYY-MM-DD):",
        ttk.Entry(body, textvariable=end_var, width=14))

    overnight_var = tk.BooleanVar(value=False)
    row("Overnight stay:",
        ttk.Checkbutton(body, variable=overnight_var))

    def submit():
        i = asg_combo.current()
        if i < 0:
            return
        who = (gui_instance.auth.current_user.get('username')
                if gui_instance.auth and gui_instance.auth.current_user
                else 'housing-admin')
        pid = extras.request_guest_pass(
            asgs[i][0],
            guest_name=name_var.get().strip(),
            guest_relation=relation_var.get().strip() or None,
            id_type=id_type_var.get() or None,
            id_reference=id_ref_var.get().strip() or None,
            start_date=start_var.get().strip(),
            end_date=end_var.get().strip(),
            overnight=overnight_var.get(),
            requested_by=who)
        if not pid:
            messagebox.showerror("Guest pass",
                                  "Could not create request (see logs).",
                                  parent=dlg)
            return
        log_activity(f"Guest pass {pid} requested for {asgs[i][0]} "
                     f"({name_var.get().strip()})")
        dlg.destroy()
        on_done()

    bar = ttk.Frame(body)
    bar.grid(row=grid_row, column=0, columnspan=2, sticky="e", pady=(12, 0))
    ttk.Button(bar, text="Cancel", command=dlg.destroy).pack(side="right",
                                                              padx=4)
    ttk.Button(bar, text="Submit", command=submit).pack(side="right")


def _load_active_assignments() -> list[tuple[str, str]]:
    try:
        conn = get_connection()
        try:
            return [(r[0], r[1]) for r in conn.execute('''
                SELECT a.assignment_id,
                       a.assignment_id || ' · '
                       || s.first_name || ' ' || s.last_name
                       || ' · Room ' || r.room_number
                       || ' · ' || b.building_name
                FROM housing_assignments a
                JOIN students s ON s.student_id = a.student_id
                JOIN housing_rooms r ON r.room_id = a.room_id
                JOIN housing_buildings b ON b.building_id = r.building_id
                WHERE a.status = 'Active'
                ORDER BY b.building_name, r.room_number
            ''')]
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("Could not list active assignments for guests")
        return []
