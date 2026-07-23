"""Key / access-card management for housing assignments.

Lists active and revoked cards linked to housing assignments
(`access_cards` rows whose notes reference an assignment_id). Lets
admins issue a fresh card for an assignment and revoke an existing one
explicitly — the move-out workflow also auto-revokes via
``extras.revoke_cards``.
"""

from __future__ import annotations

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


def show_keys(gui_instance) -> None:
    gui_instance.clear_content()
    parent = gui_instance.content_frame

    ttk.Label(parent, text="Keys & Access Cards",
              font=("Arial", 14, "bold")).pack(anchor="w", padx=8,
                                                pady=(8, 4))
    ttk.Label(parent,
              text=("Cards linked to housing assignments. Active rows "
                    "are issued; revoked rows are kept for audit. "
                    "Issuing here writes to the Facility Management "
                    "`access_cards` table — no parallel store."),
              wraplength=820, foreground="#555").pack(anchor="w", padx=8,
                                                        pady=(0, 6))

    # ── Filter bar ──
    bar = ttk.Frame(parent)
    bar.pack(fill="x", padx=8, pady=4)
    status_var = tk.StringVar(value="active")
    ttk.Label(bar, text="Status:").pack(side="left")
    ttk.Combobox(bar, textvariable=status_var, state="readonly", width=12,
                 values=["active", "revoked", "(all)"]).pack(side="left",
                                                              padx=4)
    ttk.Label(bar, text="Building:").pack(side="left", padx=(12, 4))
    building_var = tk.StringVar()
    bcombo = ttk.Combobox(bar, textvariable=building_var,
                           state="readonly", width=28)
    bar_buildings = _load_buildings()
    bcombo['values'] = ["(any)"] + [b[1] for b in bar_buildings]
    bcombo.current(0)
    bcombo.pack(side="left")
    ttk.Button(bar, text="Apply",
               command=lambda: reload()).pack(side="left", padx=8)

    # ── Table ──
    cols = ("card_number", "student", "building", "issue_date",
            "expiry_date", "status", "assignment")
    tree = ttk.Treeview(parent, columns=cols, show="headings", height=14)
    for k, lbl, w in [
        ("card_number", "Card #", 130),
        ("student", "Student", 220),
        ("building", "Building", 200),
        ("issue_date", "Issued", 110),
        ("expiry_date", "Expires", 110),
        ("status", "Status", 90),
        ("assignment", "Assignment", 150),
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
        bsel = bcombo.current()
        b_id = bar_buildings[bsel - 1][0] if bsel > 0 else None
        sql = '''
            SELECT ac.card_number, ac.user_id, ac.user_name,
                   ac.issue_date, ac.expiry_date, ac.status, ac.notes,
                   ac.buildings_access
            FROM access_cards ac
            WHERE ac.notes LIKE 'Housing assignment%'
        '''
        args: list = []
        if s != "(all)":
            sql += " AND ac.status = ?"
            args.append(s)
        if b_id:
            sql += " AND ac.buildings_access = ?"
            args.append(b_id)
        sql += " ORDER BY ac.created_at DESC"
        try:
            conn = get_connection()
            try:
                rows = conn.execute(sql, args).fetchall()
            finally:
                conn.close()
        except sqlite3.Error as e:
            logger.exception("Keys list failed")
            messagebox.showerror("Keys", f"Could not load cards:\n\n{e}",
                                  parent=gui_instance.root)
            return

        building_name = _building_id_to_name()
        for (cnum, sid, sname, issue, expiry, stat, notes,
             bld_id) in rows:
            asg = ''
            if notes and 'Housing assignment' in notes:
                # notes format: 'Housing assignment ASG-xxx | revoked: …'
                try:
                    asg = notes.split('Housing assignment', 1)[1].strip(
                        ' :|').split(' ', 1)[0]
                except Exception:
                    pass
            tree.insert("", "end", iid=cnum, values=(
                cnum,
                f"{sname or ''} ({sid or ''})",
                building_name.get(bld_id or '', ''),
                issue or '—', expiry or '—', stat, asg,
            ))
        summary_var.set(f"{len(rows)} card(s)")

    # ── Action bar ──
    act = ttk.Frame(parent)
    act.pack(fill="x", padx=8, pady=(0, 6))
    ttk.Button(act, text="Issue for assignment…",
               command=lambda: _issue(gui_instance, reload)).pack(side="left")
    ttk.Button(act, text="Revoke selected",
               command=lambda: _revoke_selected(tree, gui_instance, reload)).pack(
        side="left", padx=4)

    reload()


def _building_id_to_name() -> dict:
    try:
        conn = get_connection()
        try:
            return {b: n for b, n in conn.execute(
                "SELECT building_id, building_name FROM housing_buildings")}
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("Could not load building name map")
        return {}


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


def _list_assignments() -> list[tuple[str, str]]:
    try:
        conn = get_connection()
        try:
            return [(r[0], r[1]) for r in conn.execute('''
                SELECT a.assignment_id,
                       a.assignment_id || ' · '
                       || s.first_name || ' ' || s.last_name
                       || ' (Room ' || r.room_number || ', '
                       || b.building_name || ')'
                FROM housing_assignments a
                JOIN students s ON s.student_id = a.student_id
                JOIN housing_rooms r ON r.room_id = a.room_id
                JOIN housing_buildings b ON b.building_id = r.building_id
                WHERE a.status IN ('Active', 'Pending')
                ORDER BY b.building_name, r.room_number
            ''')]
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("Could not list assignments")
        return []


def _issue(gui_instance, on_done):
    asgs = _list_assignments()
    if not asgs:
        messagebox.showinfo("Issue card",
                            "No active or pending assignments.",
                            parent=gui_instance.root)
        return
    dlg = tk.Toplevel(gui_instance.root)
    dlg.title("Issue access card")
    dlg.geometry("560x180")
    dlg.transient(gui_instance.root)
    body = ttk.Frame(dlg, padding=10)
    body.pack(fill="both", expand=True)

    ttk.Label(body, text="Assignment:").grid(row=0, column=0, sticky="e")
    pick_var = tk.StringVar()
    combo = ttk.Combobox(body, textvariable=pick_var, state="readonly",
                          width=64)
    combo['values'] = [a[1] for a in asgs]
    combo.current(0)
    combo.grid(row=0, column=1, sticky="w", pady=2)

    ttk.Label(body, text="Expiry (YYYY-MM-DD, optional):").grid(row=1,
                                                                  column=0,
                                                                  sticky="e")
    exp_var = tk.StringVar()
    ttk.Entry(body, textvariable=exp_var, width=18).grid(row=1, column=1,
                                                            sticky="w")

    def go():
        i = combo.current()
        if i < 0:
            return
        asg_id = asgs[i][0]
        who = (gui_instance.auth.current_user.get('username')
                if gui_instance.auth and gui_instance.auth.current_user
                else 'housing-admin')
        cnum = extras.issue_card(asg_id, issued_by=who,
                                  expiry_date=exp_var.get().strip() or None)
        if not cnum:
            messagebox.showerror("Issue card",
                                  "Failed to issue card (see logs).",
                                  parent=dlg)
            return
        log_activity(f"Access card {cnum} issued for {asg_id}")
        dlg.destroy()
        on_done()
        messagebox.showinfo("Issue card",
                             f"Card {cnum} issued.",
                             parent=gui_instance.root)

    bar = ttk.Frame(body)
    bar.grid(row=2, column=0, columnspan=2, sticky="e", pady=(12, 0))
    ttk.Button(bar, text="Cancel", command=dlg.destroy).pack(side="right",
                                                              padx=4)
    ttk.Button(bar, text="Issue", command=go).pack(side="right")


def _revoke_selected(tree, gui_instance, on_done):
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Revoke", "Select a card first.",
                            parent=gui_instance.root)
        return
    # tree iid is card_number, but extras.revoke_cards keys on assignment_id.
    # Pull assignment id from the row.
    try:
        asg = tree.item(sel, 'values')[6]
    except Exception:
        asg = None
    if not asg:
        messagebox.showwarning("Revoke",
                                "Card is not linked to an assignment "
                                "(no assignment id in notes).",
                                parent=gui_instance.root)
        return
    reason = simpledialog.askstring("Revoke card",
                                     "Reason (e.g. lost, replaced):",
                                     parent=gui_instance.root)
    if reason is None:
        return
    n = extras.revoke_cards(asg, reason=reason or "Manual")
    log_activity(f"Revoked {n} card(s) for {asg} (reason={reason!r})")
    on_done()
    messagebox.showinfo("Revoke", f"Revoked {n} card(s).",
                         parent=gui_instance.root)
