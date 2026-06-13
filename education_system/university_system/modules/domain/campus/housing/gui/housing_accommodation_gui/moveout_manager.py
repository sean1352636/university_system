"""Move-out / end-of-tenancy workflow for the Housing Accommodation GUI.

One screen drives a tenant through the four sequential steps that close
out a tenancy:

    1. Pick an active assignment
    2. Final inspection      (housing_inspections, type='Move-out')
    3. Itemise deductions    (housing_deposit_deductions, status='Proposed')
    4. Finalise              (mark assignment Terminated, set
                              actual_move_out_date, free the room, and
                              promote the next waitlist entry that
                              matches the room)

Each step is its own action button with its own error handling so a
mistake at e.g. step 3 doesn't unwind step 2. The user can come back to
the same assignment and finish later.

Refund processing itself is delegated to the existing refund_manager —
this screen surfaces the *amount* and a "Issue refund…" button that
opens the regular refunds tab pre-filtered for the student.
"""

from __future__ import annotations

import datetime
import logging
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Any

from education_system.university_system.infrastructure.database.db import (
    get_connection,
)
from education_system.university_system.modules.shared.utils.simple_activity_logger import (
    log_activity, log_update,
)
from education_system.university_system.modules.domain.campus.housing.services.housing_accommodation import (
    waitlist as waitlist_service,
)
from education_system.university_system.modules.domain.campus.housing.services.housing_accommodation.common import (
    generate_id,
)

logger = logging.getLogger(__name__)


# ── Top-level entry point ──────────────────────────────────────────────

def show_moveout_workflow(gui_instance) -> None:
    """Mount the move-out workflow inside the GUI's content area."""
    gui_instance.clear_content()
    parent = gui_instance.content_frame

    header = ttk.Frame(parent)
    header.pack(fill="x", padx=8, pady=(8, 4))
    ttk.Label(header, text="Move-Out Workflow",
              font=("Arial", 14, "bold")).pack(side="left")
    ttk.Button(header, text="Refresh",
               command=lambda: show_moveout_workflow(gui_instance)).pack(
        side="right")

    # ── Step 0: pick an active assignment ──
    picker = ttk.LabelFrame(parent, text="1. Select active assignment",
                            padding=8)
    picker.pack(fill="x", padx=8, pady=4)

    assignment_var = tk.StringVar()
    combo = ttk.Combobox(picker, textvariable=assignment_var,
                         state="readonly", width=78)
    combo.pack(side="left", padx=(0, 8))

    workspace = ttk.Frame(parent)
    workspace.pack(fill="both", expand=True, padx=8, pady=4)

    rows: list[dict[str, Any]] = _load_active_assignments()
    if rows:
        combo['values'] = [_assignment_label(r) for r in rows]
    else:
        combo['values'] = ["(no active assignments)"]
        combo.configure(state="disabled")

    def _on_pick(_e=None) -> None:
        i = combo.current()
        if i < 0 or i >= len(rows):
            return
        _render_workspace(gui_instance, workspace, rows[i])

    combo.bind("<<ComboboxSelected>>", _on_pick)

    if rows:
        combo.current(0)
        _on_pick()


# ── Helpers ────────────────────────────────────────────────────────────

def _assignment_label(r: dict[str, Any]) -> str:
    return (f"{r['assignment_id']} · {r['student_name']} "
            f"({r['student_id']}) · Room {r['room_number']} "
            f"{r['building_name']}")


def _load_active_assignments() -> list[dict[str, Any]]:
    sql = '''
        SELECT a.assignment_id, a.student_id,
               s.first_name || ' ' || s.last_name AS student_name,
               a.room_id, r.room_number, b.building_id, b.building_name,
               r.room_type, r.monthly_rent,
               a.move_in_date, a.planned_move_out_date,
               a.actual_move_out_date, a.monthly_rent AS asg_rent,
               a.status
        FROM housing_assignments a
        JOIN students          s ON s.student_id  = a.student_id
        JOIN housing_rooms     r ON r.room_id     = a.room_id
        JOIN housing_buildings b ON b.building_id = r.building_id
        WHERE a.status IN ('Active', 'Pending')
          AND a.actual_move_out_date IS NULL
        ORDER BY b.building_name, r.room_number
    '''
    try:
        conn = get_connection()
        try:
            conn.row_factory = sqlite3.Row
            return [dict(r) for r in conn.execute(sql).fetchall()]
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("Failed to load active assignments")
        return []


def _moveout_inspection(assignment_room_id: str) -> dict[str, Any] | None:
    """Return the latest move-out inspection for the room, if any."""
    try:
        conn = get_connection()
        try:
            conn.row_factory = sqlite3.Row
            row = conn.execute('''
                SELECT * FROM housing_inspections
                WHERE room_id = ? AND inspection_type = 'Move-out'
                ORDER BY inspection_date DESC, created_at DESC
                LIMIT 1
            ''', (assignment_room_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("Failed to load move-out inspection for room %s",
                         assignment_room_id)
        return None


def _deductions_for(assignment_id: str) -> list[dict[str, Any]]:
    try:
        conn = get_connection()
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute('''
                SELECT deduction_id, description, amount, status,
                       inspection_id, created_at, applied_at
                FROM housing_deposit_deductions
                WHERE assignment_id = ?
                ORDER BY created_at
            ''', (assignment_id,)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("Failed to load deductions for %s", assignment_id)
        return []


def _held_deposit(assignment_id: str) -> float:
    try:
        conn = get_connection()
        try:
            cur = conn.execute('''
                SELECT COALESCE(SUM(amount), 0) FROM payments
                WHERE reference_id = ?
                  AND source_type = 'housing'
                  AND payment_type = 'Deposit'
                  AND status = 'Completed'
            ''', (assignment_id,))
            return float(cur.fetchone()[0] or 0)
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("Failed to read held deposit for %s", assignment_id)
        return 0.0


# ── Workspace renderer ─────────────────────────────────────────────────

def _render_workspace(gui_instance, parent: ttk.Frame,
                      assignment: dict[str, Any]) -> None:
    for w in parent.winfo_children():
        w.destroy()

    held = _held_deposit(assignment['assignment_id'])
    deductions = _deductions_for(assignment['assignment_id'])
    total_ded = sum(float(d['amount'] or 0) for d in deductions
                    if d['status'] != 'Withdrawn')
    refundable = max(0.0, held - total_ded)
    inspection = _moveout_inspection(assignment['room_id'])

    # ── Summary banner ──
    summary = ttk.LabelFrame(parent, text="Tenancy", padding=8)
    summary.pack(fill="x", pady=(4, 8))
    rows = [
        ("Assignment", assignment['assignment_id']),
        ("Student", f"{assignment['student_name']} ({assignment['student_id']})"),
        ("Room", f"{assignment['room_number']} · "
         f"{assignment['building_name']} · {assignment['room_type']}"),
        ("Move-in / planned move-out",
         f"{assignment['move_in_date']} → {assignment['planned_move_out_date']}"),
        ("Held deposit", f"£{held:,.2f}"),
        ("Proposed/applied deductions", f"£{total_ded:,.2f}"),
        ("Refundable", f"£{refundable:,.2f}"),
    ]
    for i, (lbl, val) in enumerate(rows):
        ttk.Label(summary, text=f"{lbl}:",
                  foreground="#666").grid(row=i, column=0, sticky="e", padx=4)
        ttk.Label(summary, text=val).grid(row=i, column=1, sticky="w", padx=4)

    # ── Step 2: Move-out inspection ──
    insp = ttk.LabelFrame(parent, text="2. Final inspection", padding=8)
    insp.pack(fill="x", pady=4)

    if inspection:
        ttk.Label(insp,
                  text=(f"Inspection {inspection['inspection_id']} on "
                        f"{inspection['inspection_date']} — "
                        f"status: {inspection['status']}")).pack(anchor="w")
        ttk.Label(insp, text="Findings:",
                  foreground="#666").pack(anchor="w", pady=(4, 0))
        body = tk.Text(insp, height=4, width=80)
        body.insert("1.0", inspection.get('findings') or "")
        body.configure(state="disabled")
        body.pack(anchor="w")
    else:
        ttk.Label(insp,
                  text="No move-out inspection recorded yet.").pack(anchor="w")

    ttk.Button(insp,
               text=("Edit inspection…" if inspection
                     else "Record move-out inspection…"),
               command=lambda: _open_inspection_dialog(
                   gui_instance, assignment, inspection,
                   on_done=lambda: _render_workspace(
                       gui_instance, parent, assignment))
               ).pack(anchor="e", pady=(4, 0))

    # ── Step 3: Deductions ──
    ded = ttk.LabelFrame(parent, text="3. Damages & deductions", padding=8)
    ded.pack(fill="both", expand=False, pady=4)

    cols = ("desc", "amount", "status")
    tree = ttk.Treeview(ded, columns=cols, show="headings", height=5)
    tree.heading("desc", text="Description")
    tree.heading("amount", text="Amount")
    tree.heading("status", text="Status")
    tree.column("desc", width=420)
    tree.column("amount", width=100, anchor="e")
    tree.column("status", width=120)
    for d in deductions:
        tree.insert("", "end", iid=d['deduction_id'],
                    values=(d['description'], f"£{float(d['amount']):,.2f}",
                            d['status']))
    tree.pack(fill="x")

    btns = ttk.Frame(ded)
    btns.pack(fill="x", pady=(4, 0))
    ttk.Button(btns, text="Add deduction…",
               command=lambda: _open_deduction_dialog(
                   gui_instance, assignment, inspection,
                   on_done=lambda: _render_workspace(
                       gui_instance, parent, assignment))).pack(side="left")
    ttk.Button(btns, text="Withdraw selected",
               command=lambda: _withdraw_selected(
                   tree, gui_instance, assignment,
                   on_done=lambda: _render_workspace(
                       gui_instance, parent, assignment))).pack(side="left",
                                                                 padx=4)

    # ── Step 4: Finalise ──
    fin = ttk.LabelFrame(parent, text="4. Finalise move-out", padding=8)
    fin.pack(fill="x", pady=4)
    ttk.Label(fin,
              text=(f"Refundable to student: £{refundable:,.2f}. "
                    "Finalising will mark the assignment Terminated, "
                    "set today as the move-out date, and free the room. "
                    "Any matching waitlist entry will be auto-promoted.")
              ).pack(anchor="w")
    row = ttk.Frame(fin)
    row.pack(fill="x", pady=(4, 0))
    ttk.Button(row, text="Issue refund…",
               command=lambda: _open_refunds(gui_instance, assignment)).pack(
        side="left")
    ttk.Button(row, text="Finalise move-out",
               command=lambda: _finalise(
                   gui_instance, assignment,
                   on_done=lambda: show_moveout_workflow(gui_instance))).pack(
        side="right")


# ── Inspection dialog ──────────────────────────────────────────────────

def _open_inspection_dialog(gui_instance, assignment, existing, *, on_done):
    dlg = tk.Toplevel(gui_instance.root)
    dlg.title("Move-out inspection")
    dlg.geometry("520x360")
    dlg.transient(gui_instance.root)

    body = ttk.Frame(dlg, padding=10)
    body.pack(fill="both", expand=True)

    ttk.Label(body, text="Inspector:").grid(row=0, column=0, sticky="e")
    inspector_var = tk.StringVar(
        value=(existing or {}).get('inspector')
        or (gui_instance.auth.current_user.get('username')
            if gui_instance.auth and gui_instance.auth.current_user else ''))
    ttk.Entry(body, textvariable=inspector_var, width=40).grid(
        row=0, column=1, sticky="w", pady=2)

    ttk.Label(body, text="Date (YYYY-MM-DD):").grid(row=1, column=0, sticky="e")
    date_var = tk.StringVar(
        value=(existing or {}).get('inspection_date')
        or datetime.date.today().isoformat())
    ttk.Entry(body, textvariable=date_var, width=20).grid(
        row=1, column=1, sticky="w", pady=2)

    ttk.Label(body, text="Status:").grid(row=2, column=0, sticky="e")
    status_var = tk.StringVar(value=(existing or {}).get('status') or 'Passed')
    ttk.Combobox(body, textvariable=status_var,
                 values=['Passed', 'Issues found', 'Failed'],
                 state="readonly", width=18).grid(row=2, column=1, sticky="w")

    ttk.Label(body, text="Findings:").grid(row=3, column=0, sticky="ne", pady=4)
    findings = tk.Text(body, height=8, width=50)
    if existing and existing.get('findings'):
        findings.insert("1.0", existing['findings'])
    findings.grid(row=3, column=1, sticky="w", pady=4)

    def save():
        try:
            now = datetime.datetime.now().isoformat(timespec='seconds')
            conn = get_connection()
            try:
                cur = conn.cursor()
                if existing:
                    cur.execute('''
                        UPDATE housing_inspections
                        SET inspector=?, inspection_date=?, status=?,
                            findings=?, updated_at=?
                        WHERE inspection_id=?
                    ''', (inspector_var.get().strip(),
                          date_var.get().strip(),
                          status_var.get().strip(),
                          findings.get("1.0", "end").strip(),
                          now, existing['inspection_id']))
                    log_update('housing_inspections',
                               existing['inspection_id'],
                               'Move-out inspection updated')
                else:
                    iid = generate_id('INS')
                    cur.execute('''
                        INSERT INTO housing_inspections
                        (inspection_id, room_id, inspector, inspection_date,
                         inspection_type, status, findings, action_required,
                         follow_up_date, created_at, updated_at)
                        VALUES (?, ?, ?, ?, 'Move-out', ?, ?, NULL, NULL,
                                ?, ?)
                    ''', (iid, assignment['room_id'],
                          inspector_var.get().strip(),
                          date_var.get().strip(),
                          status_var.get().strip(),
                          findings.get("1.0", "end").strip(),
                          now, now))
                    log_activity(f"Move-out inspection {iid} recorded for "
                                 f"assignment {assignment['assignment_id']}")
                conn.commit()
            finally:
                conn.close()
            dlg.destroy()
            on_done()
        except sqlite3.Error as e:
            logger.exception("Inspection save failed")
            messagebox.showerror("Inspection",
                                 f"Could not save inspection:\n\n{e}",
                                 parent=dlg)

    bar = ttk.Frame(body)
    bar.grid(row=4, column=0, columnspan=2, sticky="e", pady=(10, 0))
    ttk.Button(bar, text="Cancel", command=dlg.destroy).pack(side="right",
                                                              padx=4)
    ttk.Button(bar, text="Save", command=save).pack(side="right")


# ── Deduction dialog ───────────────────────────────────────────────────

def _open_deduction_dialog(gui_instance, assignment, inspection, *, on_done):
    dlg = tk.Toplevel(gui_instance.root)
    dlg.title("Add deduction")
    dlg.geometry("460x220")
    dlg.transient(gui_instance.root)

    body = ttk.Frame(dlg, padding=10)
    body.pack(fill="both", expand=True)

    ttk.Label(body, text="Description:").grid(row=0, column=0, sticky="e")
    desc_var = tk.StringVar()
    ttk.Entry(body, textvariable=desc_var, width=46).grid(
        row=0, column=1, sticky="w", pady=2)

    ttk.Label(body, text="Amount (£):").grid(row=1, column=0, sticky="e")
    amt_var = tk.StringVar()
    ttk.Entry(body, textvariable=amt_var, width=16).grid(
        row=1, column=1, sticky="w", pady=2)

    if inspection:
        ttk.Label(body,
                  text=(f"Will be linked to inspection "
                        f"{inspection['inspection_id']}"),
                  foreground="#666").grid(row=2, column=0, columnspan=2,
                                           sticky="w", pady=(8, 0))
    else:
        ttk.Label(body,
                  text="No move-out inspection on file yet — record one first.",
                  foreground="#a00").grid(row=2, column=0, columnspan=2,
                                           sticky="w", pady=(8, 0))

    def save():
        desc = desc_var.get().strip()
        if not desc:
            messagebox.showwarning("Add deduction", "Description is required.",
                                   parent=dlg)
            return
        try:
            amount = float(amt_var.get().strip())
            if amount <= 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Add deduction",
                                   "Amount must be a positive number.",
                                   parent=dlg)
            return
        try:
            now = datetime.datetime.now().isoformat(timespec='seconds')
            who = (gui_instance.auth.current_user.get('username')
                   if gui_instance.auth and gui_instance.auth.current_user
                   else 'housing')
            did = generate_id('DED')
            conn = get_connection()
            try:
                conn.execute('''
                    INSERT INTO housing_deposit_deductions
                    (deduction_id, assignment_id, deposit_payment_id,
                     inspection_id, description, amount, status,
                     created_by, created_at)
                    VALUES (?, ?, NULL, ?, ?, ?, 'Proposed', ?, ?)
                ''', (did, assignment['assignment_id'],
                      (inspection or {}).get('inspection_id'),
                      desc, amount, who, now))
                conn.commit()
            finally:
                conn.close()
            log_activity(f"Deduction {did} proposed for assignment "
                         f"{assignment['assignment_id']} (£{amount:.2f})")
            dlg.destroy()
            on_done()
        except sqlite3.Error as e:
            logger.exception("Deduction insert failed")
            messagebox.showerror("Add deduction",
                                 f"Could not save deduction:\n\n{e}",
                                 parent=dlg)

    bar = ttk.Frame(body)
    bar.grid(row=3, column=0, columnspan=2, sticky="e", pady=(12, 0))
    ttk.Button(bar, text="Cancel", command=dlg.destroy).pack(side="right",
                                                              padx=4)
    ttk.Button(bar, text="Save", command=save).pack(side="right")


def _withdraw_selected(tree, gui_instance, assignment, *, on_done):
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Withdraw deduction",
                            "Select a deduction first.",
                            parent=gui_instance.root)
        return
    if not messagebox.askyesno("Withdraw deduction",
                               f"Withdraw deduction {sel}?",
                               parent=gui_instance.root):
        return
    try:
        now = datetime.datetime.now().isoformat(timespec='seconds')
        conn = get_connection()
        try:
            conn.execute('''
                UPDATE housing_deposit_deductions
                SET status='Withdrawn', applied_at=?
                WHERE deduction_id=? AND status='Proposed'
            ''', (now, sel))
            conn.commit()
        finally:
            conn.close()
        log_activity(f"Deduction {sel} withdrawn from assignment "
                     f"{assignment['assignment_id']}")
        on_done()
    except sqlite3.Error as e:
        logger.exception("Withdraw deduction failed")
        messagebox.showerror("Withdraw deduction",
                             f"Could not withdraw:\n\n{e}",
                             parent=gui_instance.root)


# ── Finalise ───────────────────────────────────────────────────────────

def _finalise(gui_instance, assignment, *, on_done):
    msg = (f"Finalise move-out for {assignment['student_name']} "
           f"in room {assignment['room_number']}?\n\n"
           "• Assignment status -> Terminated\n"
           "• actual_move_out_date -> today\n"
           "• Room freed (status='Available', occupants - 1)\n"
           "• Any matching waitlist entry will be promoted automatically.\n\n"
           "Issue any refund BEFORE finalising.")
    if not messagebox.askyesno("Finalise move-out", msg,
                               parent=gui_instance.root):
        return
    now = datetime.datetime.now().isoformat(timespec='seconds')
    today = datetime.date.today().isoformat()
    promotion_summary = None
    try:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute('''
                UPDATE housing_assignments
                   SET status='Terminated',
                       actual_move_out_date=?,
                       updated_at=?
                 WHERE assignment_id=?
            ''', (today, now, assignment['assignment_id']))
            cur.execute('''
                UPDATE housing_rooms
                   SET status='Available',
                       current_occupants = MAX(0, current_occupants - 1),
                       updated_at=?
                 WHERE room_id=?
            ''', (now, assignment['room_id']))
            conn.commit()
        finally:
            conn.close()

        log_update('housing_assignments', assignment['assignment_id'],
                   f"Move-out finalised on {today}")
        logger.info("Move-out finalised for assignment %s",
                    assignment['assignment_id'])

        # Auto-revoke any active access cards tied to this assignment.
        try:
            from education_system.university_system.modules.domain.campus.housing.services.housing_accommodation import (
                extras as _extras,
            )
            n = _extras.revoke_cards(assignment['assignment_id'],
                                      reason="Move-out finalised")
            if n:
                logger.info("Move-out: revoked %d access card(s) for %s",
                            n, assignment['assignment_id'])
        except Exception:
            logger.exception("Move-out: card revoke failed for %s",
                             assignment['assignment_id'])

        # Try to fill the freed room from the waitlist.
        try:
            promotion_summary = waitlist_service.promote_room_to_next(
                assignment['room_id'],
                default_rent=float(assignment.get('asg_rent') or 0),
                created_by=(gui_instance.auth.current_user.get('username')
                            if gui_instance.auth and gui_instance.auth.current_user
                            else 'system'),
            )
        except Exception:
            logger.exception("Waitlist auto-promotion failed for room %s",
                             assignment['room_id'])

        if promotion_summary:
            messagebox.showinfo(
                "Move-out finalised",
                ("Move-out finalised.\n\n"
                 f"Waitlist promoted: student {promotion_summary['student_id']} "
                 f"-> assignment {promotion_summary['assignment_id']} "
                 "(status Pending — complete paperwork to activate)."),
                parent=gui_instance.root)
        else:
            messagebox.showinfo("Move-out finalised",
                                "Move-out finalised. Room is now Available.",
                                parent=gui_instance.root)
        on_done()
    except sqlite3.Error as e:
        logger.exception("Finalise failed")
        messagebox.showerror("Finalise move-out",
                             f"Could not finalise move-out:\n\n{e}",
                             parent=gui_instance.root)


def _open_refunds(gui_instance, assignment):
    try:
        gui_instance.show_refunds()
        # Best-effort: pre-fill the search box for this student.
        if hasattr(gui_instance, 'refund_search_var'):
            gui_instance.refund_search_var.set(assignment['student_id'])
    except Exception as e:
        logger.exception("Could not open refunds tab")
        messagebox.showerror("Refunds",
                             f"Could not open refunds tab:\n\n{e}",
                             parent=gui_instance.root)
