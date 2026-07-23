"""Tk GUI for the deposit lifecycle: ledger / refund / disputes / TDP / interest / state log.

Each tab is a thin form over the same backend queries the CLI uses; the CLI's
interactive functions can't be reused directly because they call input(). Where
useful, this module imports the non-interactive helpers (state machine,
interest math, TDP deadline calc) so behaviour matches across surfaces.
"""

import datetime as _dt
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from education_system.post_18.university_system.infrastructure.database.db import get_connection
from education_system.post_18.university_system.modules.domain.campus.housing.services.housing_accommodation.common import generate_id
from education_system.post_18.university_system.modules.domain.campus.housing.services.housing_accommodation import (
    deposit_state as _ds,
    interest as _interest,
    tdp as _tdp,
)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def show_deposits(gui_instance):
    """Render the deposits panel into the host GUI's content frame."""
    gui_instance.clear_content()

    header = ttk.Frame(gui_instance.content_frame)
    header.pack(fill='x', pady=(0, 10))
    ttk.Label(header, text="Deposit Management",
              font=('Arial', 16, 'bold')).pack(side='left', padx=(0, 20))

    notebook = ttk.Notebook(gui_instance.content_frame)
    notebook.pack(fill='both', expand=True)

    for label, builder in [
        ("Ledger",        _build_ledger_tab),
        ("Process Refund", _build_refund_tab),
        ("Disputes",      _build_disputes_tab),
        ("TDP",           _build_tdp_tab),
        ("Interest",      _build_interest_tab),
        ("State Log",     _build_state_log_tab),
    ]:
        frame = ttk.Frame(notebook, padding="10")
        notebook.add(frame, text=label)
        builder(gui_instance, frame)


# ---------------------------------------------------------------------------
# Tab 1 — Ledger
# ---------------------------------------------------------------------------

def _build_ledger_tab(gui_instance, parent):
    cols = ('assignment_id', 'student', 'room', 'held', 'state',
            'tdp', 'accrued')
    tree = ttk.Treeview(parent, columns=cols, show='headings', height=18)
    for c, txt, w in [
        ('assignment_id', 'Assignment', 140),
        ('student',       'Student',    160),
        ('room',          'Room',       140),
        ('held',          'Held (£)',   90),
        ('state',         'State',      140),
        ('tdp',           'TDP',        120),
        ('accrued',       'Interest £', 90),
    ]:
        tree.heading(c, text=txt)
        tree.column(c, width=w, anchor='w')
    tree.pack(fill='both', expand=True)

    def refresh():
        for i in tree.get_children():
            tree.delete(i)
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute('''
                SELECT a.assignment_id, s.first_name || ' ' || s.last_name,
                       r.room_number || ' / ' || b.building_name,
                       COALESCE(SUM(CASE WHEN p.status='Completed' THEN p.amount ELSE 0 END), 0),
                       a.deposit_state, a.tdp_scheme,
                       COALESCE(a.deposit_interest_accrued, 0)
                FROM housing_assignments a
                JOIN students s ON a.student_id = s.student_id
                JOIN housing_rooms r ON a.room_id = r.room_id
                JOIN housing_buildings b ON r.building_id = b.building_id
                LEFT JOIN payments p ON p.reference_id = a.assignment_id
                                     AND p.source_type = 'housing'
                                     AND p.payment_type = 'Deposit'
                GROUP BY a.assignment_id
                HAVING COALESCE(SUM(CASE WHEN p.status='Completed' THEN p.amount ELSE 0 END), 0) > 0
                    OR a.deposit_state IS NOT NULL
                ORDER BY a.assignment_id
            ''')
            for aid, name, room, held, state, tdp, accrued in cur.fetchall():
                tree.insert('', tk.END, values=(
                    aid, name, room, f"{held:,.2f}",
                    state or '—', tdp or 'Unprotected', f"{accrued:,.2f}",
                ))
        finally:
            conn.close()

    btns = ttk.Frame(parent)
    btns.pack(fill='x', pady=(8, 0))
    ttk.Button(btns, text="Refresh", command=refresh).pack(side='left')
    refresh()


# ---------------------------------------------------------------------------
# Tab 2 — Process Refund
# ---------------------------------------------------------------------------

def _build_refund_tab(gui_instance, parent):
    ctx = {
        'assignment_id': None,
        'deposit_held': 0.0,
        'tenant_interest': 0.0,
        'interest_policy': None,
        'inspection_id': None,
        'new_deductions': [],   # local-only until Post
    }

    # Selection row
    sel = ttk.LabelFrame(parent, text="Select assignment", padding="8")
    sel.pack(fill='x', pady=(0, 8))
    combo = ttk.Combobox(sel, width=70, state='readonly')
    combo.grid(row=0, column=0, padx=4, sticky='w')

    def load_candidates():
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute('''
                SELECT a.assignment_id, a.student_id,
                       s.first_name || ' ' || s.last_name,
                       SUM(p.amount), a.deposit_state
                FROM payments p
                JOIN housing_assignments a ON p.reference_id = a.assignment_id
                JOIN students s ON a.student_id = s.student_id
                WHERE p.source_type='housing' AND p.payment_type='Deposit'
                  AND p.status='Completed'
                GROUP BY a.assignment_id
                HAVING SUM(p.amount) > 0
                ORDER BY a.assignment_id
            ''')
            rows = cur.fetchall()
        finally:
            conn.close()
        items = []
        for aid, sid, name, held, state in rows:
            if _ds.is_terminal(state):
                continue
            items.append(f"{aid}  |  {name} ({sid})  |  £{held:,.2f}  |  {state or 'Held'}")
        combo['values'] = items
        return rows

    candidates = load_candidates()

    # Summary frame
    summary = ttk.LabelFrame(parent, text="Refund summary", padding="8")
    summary.pack(fill='x', pady=(0, 8))
    held_var = tk.StringVar(value="£0.00")
    deductions_var = tk.StringVar(value="£0.00")
    interest_var = tk.StringVar(value="£0.00 (—)")
    refund_var = tk.StringVar(value="£0.00")
    for i, (lbl, var) in enumerate([
        ("Deposit held:",   held_var),
        ("Total deductions:", deductions_var),
        ("Interest:",       interest_var),
        ("Refund to student:", refund_var),
    ]):
        ttk.Label(summary, text=lbl).grid(row=i, column=0, sticky='w', padx=4, pady=2)
        ttk.Label(summary, textvariable=var, font=('Arial', 10, 'bold')).grid(
            row=i, column=1, sticky='w', padx=4)

    # Inspection memo
    inspection_lbl = ttk.Label(summary, text="", foreground='#555', wraplength=480, justify='left')
    inspection_lbl.grid(row=0, column=2, rowspan=4, sticky='nw', padx=20)

    # Deductions tree
    ded_frame = ttk.LabelFrame(parent, text="Deductions (proposed + new)", padding="8")
    ded_frame.pack(fill='both', expand=True, pady=(0, 8))
    cols = ('source', 'description', 'amount', 'ack_status', 'dispute')
    ded_tree = ttk.Treeview(ded_frame, columns=cols, show='headings', height=8)
    for c, t, w in [('source', 'Source', 120), ('description', 'Description', 320),
                    ('amount', 'Amount £', 90), ('ack_status', 'Acknowledgement', 130),
                    ('dispute', 'Dispute', 200)]:
        ded_tree.heading(c, text=t)
        ded_tree.column(c, width=w)
    ded_tree.pack(fill='both', expand=True, side='left')

    def _refresh_summary():
        proposed_total = 0.0
        existing_disputed = 0
        for iid in ded_tree.get_children():
            v = ded_tree.item(iid, 'values')
            try:
                proposed_total += float(v[2])
            except (ValueError, IndexError):
                pass
            if v[3] == 'Disputed':
                existing_disputed += 1
        held = ctx['deposit_held']
        capped = min(proposed_total, held)
        ti = ctx['tenant_interest']
        refund = round(held - capped + ti, 2)
        held_var.set(f"£{held:,.2f}")
        deductions_var.set(f"£{capped:,.2f}" +
                           (f"  (raw £{proposed_total:,.2f} — capped at held)"
                            if proposed_total > held else ""))
        policy = ctx['interest_policy'] or '—'
        interest_var.set(f"£{ti:,.2f} (policy: {policy})")
        refund_var.set(f"£{refund:,.2f}")
        post_btn.config(state=('disabled' if existing_disputed > 0 else 'normal'))

    def _load_assignment_data(assignment_id):
        ctx['assignment_id'] = assignment_id
        ctx['new_deductions'] = []
        for iid in ded_tree.get_children():
            ded_tree.delete(iid)

        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute('''
                SELECT COALESCE(SUM(amount), 0) FROM payments
                WHERE source_type='housing' AND payment_type='Deposit'
                  AND status='Completed' AND reference_id = ?
            ''', (assignment_id,))
            ctx['deposit_held'] = float(cur.fetchone()[0] or 0)

            # Accrue interest to today, then read totals + policy.
            today = _dt.date.today().isoformat()
            cur.execute(
                'SELECT deposit_interest_rate, deposit_interest_last_accrual_date, room_id '
                'FROM housing_assignments WHERE assignment_id = ?',
                (assignment_id,),
            )
            row = cur.fetchone()
            rate = float(row[0] or 0)
            last = row[1]
            room_id = row[2]
            if rate > 0:
                last_accrual = last or _interest._first_deposit_date(cur, assignment_id)
                if last_accrual:
                    actor = gui_instance.auth.current_user.get('username', 'housing')
                    _interest._accrue_one(cur, assignment_id, rate, last_accrual,
                                          today, ctx['deposit_held'], created_by=actor)
                    conn.commit()
            accrued, policy = _interest.accrued_interest_for(cur, assignment_id)
            ctx['interest_policy'] = policy
            ctx['tenant_interest'] = round(accrued, 2) if (
                policy == 'Tenant' and accrued > 0
            ) else 0.0

            # Inspection memo.
            cur.execute('''
                SELECT inspection_id, inspection_date, status, findings, action_required
                FROM housing_inspections
                WHERE room_id = ? AND inspection_type = 'Move-out'
                ORDER BY inspection_date DESC LIMIT 1
            ''', (room_id,))
            ins = cur.fetchone()
            if ins:
                ctx['inspection_id'] = ins[0]
                msg = (f"Move-out inspection {ins[1]} ({ins[2]})\n"
                       f"Findings: {ins[3] or '—'}\n"
                       f"Action: {ins[4] or '—'}")
            else:
                ctx['inspection_id'] = None
                msg = "No Move-out inspection on record."
            inspection_lbl.config(text=msg)

            # Proposed deductions (existing rows).
            cur.execute('''
                SELECT deduction_id, description, amount,
                       acknowledgement_status, dispute_reason
                FROM housing_deposit_deductions
                WHERE assignment_id = ? AND status = 'Proposed'
                ORDER BY created_at
            ''', (assignment_id,))
            for ded_id, desc, amt, ack, reason in cur.fetchall():
                ded_tree.insert('', tk.END, iid=f"existing:{ded_id}",
                                values=('Inspection', desc, f"{float(amt):.2f}",
                                        ack or 'Pending', reason or ''))
        finally:
            conn.close()
        _refresh_summary()

    def on_combo(_evt=None):
        text = combo.get()
        if not text:
            return
        aid = text.split('|', 1)[0].strip()
        _load_assignment_data(aid)
    combo.bind('<<ComboboxSelected>>', on_combo)

    # Action buttons
    actions = ttk.Frame(parent)
    actions.pack(fill='x')

    def add_deduction():
        if not ctx['assignment_id']:
            messagebox.showwarning("Select assignment", "Pick an assignment first.")
            return
        desc = simpledialog.askstring("New deduction", "Description:", parent=parent)
        if not desc:
            return
        amt_str = simpledialog.askstring("New deduction", f"Amount for '{desc}' (£):",
                                         parent=parent)
        if not amt_str:
            return
        try:
            amt = float(amt_str)
            if amt <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid", "Amount must be a positive number.")
            return
        ctx['new_deductions'].append((desc, amt))
        ded_tree.insert('', tk.END,
                        values=('New', desc, f"{amt:.2f}", 'Pending', ''))
        _refresh_summary()

    def post_refund():
        if not ctx['assignment_id']:
            messagebox.showwarning("Select assignment", "Pick an assignment first.")
            return
        # Compute totals.
        deductions_amounts = []
        for iid in ded_tree.get_children():
            v = ded_tree.item(iid, 'values')
            try:
                deductions_amounts.append((v[1], float(v[2])))
            except (ValueError, IndexError):
                continue
        total_ded = sum(a for _, a in deductions_amounts)
        held = ctx['deposit_held']
        capped = min(total_ded, held)
        ti = ctx['tenant_interest']
        refund = round(held - capped + ti, 2)
        if not messagebox.askyesno(
            "Confirm refund",
            f"Post refund for {ctx['assignment_id']}?\n\n"
            f"Held:        £{held:,.2f}\n"
            f"Deductions:  £{capped:,.2f}\n"
            f"Interest:    £{ti:,.2f}\n"
            f"Refund:      £{refund:,.2f}",
        ):
            return

        actor = gui_instance.auth.current_user.get('username', 'housing')
        ts = _dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn = get_connection()
        try:
            cur = conn.cursor()

            # Re-check terminal state at post time.
            current = _ds.current_state(cur, ctx['assignment_id'])
            if _ds.is_terminal(current):
                messagebox.showerror("Already terminal",
                                     f"State is {current}; cannot re-refund.")
                return

            # Re-check for open disputes.
            cur.execute('''
                SELECT COUNT(*) FROM housing_deposit_deductions
                WHERE assignment_id = ? AND status = 'Proposed'
                  AND acknowledgement_status = 'Disputed'
            ''', (ctx['assignment_id'],))
            if (cur.fetchone()[0] or 0) > 0:
                messagebox.showerror(
                    "Open disputes",
                    "Unresolved disputes exist — resolve them on the Disputes tab first.",
                )
                return

            # Primary deposit payment row id (for linkage).
            cur.execute('''
                SELECT source_payment_id FROM payments
                WHERE source_type='housing' AND payment_type='Deposit'
                  AND status='Completed' AND reference_id = ?
                ORDER BY payment_date LIMIT 1
            ''', (ctx['assignment_id'],))
            row = cur.fetchone()
            primary_deposit_id = row[0] if row else None

            # Flip existing proposed rows to Applied.
            cur.execute('''
                UPDATE housing_deposit_deductions
                SET status='Applied', applied_at=?, deposit_payment_id=?
                WHERE assignment_id=? AND status='Proposed'
            ''', (ts, primary_deposit_id, ctx['assignment_id']))

            # Insert any new deductions as Applied immediately.
            for desc, amt in ctx['new_deductions']:
                cur.execute('''
                    INSERT INTO housing_deposit_deductions
                    (deduction_id, assignment_id, deposit_payment_id, inspection_id,
                     description, amount, status, acknowledgement_status,
                     created_by, created_at, applied_at)
                    VALUES (?, ?, ?, ?, ?, ?, 'Applied', 'Acknowledged', ?, ?, ?)
                ''', (generate_id('DED'), ctx['assignment_id'], primary_deposit_id,
                      ctx['inspection_id'], desc, amt, actor, ts, ts))

            # Mark deposit payment rows.
            if refund > 0 and capped == 0:
                new_status = 'Refunded'
            elif refund > 0:
                new_status = 'Partially Refunded'
            else:
                new_status = 'Forfeited'
            cur.execute('''
                UPDATE payments SET status=?, updated_at=?
                WHERE source_type='housing' AND payment_type='Deposit' AND reference_id=?
            ''', (new_status, ts, ctx['assignment_id']))

            # Lifecycle transition.
            try:
                _ds.transition(cur, ctx['assignment_id'], new_status,
                               reason=f"refund (GUI): deductions £{capped:,.2f}, "
                                      f"refund £{refund:,.2f}",
                               actor=actor)
            except _ds.IllegalTransition as e:
                messagebox.showerror("State machine error", str(e))
                conn.rollback()
                return

            conn.commit()

            # Post GL journal.
            try:
                from education_system.post_18.university_system.modules.domain.campus.housing.services.housing_accommodation.deposits import (
                    _post_refund_journal,
                )
                jid = _post_refund_journal(held, capped, refund, ctx['assignment_id'],
                                           actor, tenant_interest=ti)
                if jid:
                    print(f"GL journal {jid} posted for {ctx['assignment_id']}.")
            except Exception as exc:
                messagebox.showwarning(
                    "GL post failed",
                    f"Operational records saved but the GL journal failed:\n{exc}\n\n"
                    f"Re-post via finance tools.",
                )

            messagebox.showinfo(
                "Refund posted",
                f"State: {new_status}\nRefund: £{refund:,.2f}",
            )
            # Reset the form.
            combo.set('')
            for iid in ded_tree.get_children():
                ded_tree.delete(iid)
            ctx['assignment_id'] = None
            ctx['deposit_held'] = 0.0
            ctx['tenant_interest'] = 0.0
            ctx['new_deductions'] = []
            inspection_lbl.config(text="")
            _refresh_summary()
            load_candidates()
        finally:
            conn.close()

    ttk.Button(actions, text="Add Deduction", command=add_deduction).pack(side='left', padx=4)
    post_btn = ttk.Button(actions, text="Post Refund", command=post_refund)
    post_btn.pack(side='left', padx=4)
    ttk.Button(actions, text="Reload Candidates",
               command=lambda: load_candidates()).pack(side='left', padx=4)


# ---------------------------------------------------------------------------
# Tab 3 — Disputes
# ---------------------------------------------------------------------------

def _build_disputes_tab(gui_instance, parent):
    cols = ('deduction_id', 'student', 'description', 'amount', 'reason')
    tree = ttk.Treeview(parent, columns=cols, show='headings', height=14)
    for c, t, w in [('deduction_id', 'Deduction', 160), ('student', 'Student', 180),
                    ('description', 'Description', 240), ('amount', 'Amount £', 90),
                    ('reason', 'Dispute reason', 320)]:
        tree.heading(c, text=t)
        tree.column(c, width=w)
    tree.pack(fill='both', expand=True)

    def refresh():
        for i in tree.get_children():
            tree.delete(i)
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute('''
                SELECT d.deduction_id, s.first_name || ' ' || s.last_name,
                       d.description, d.amount, d.dispute_reason
                FROM housing_deposit_deductions d
                JOIN housing_assignments a ON d.assignment_id = a.assignment_id
                JOIN students s ON a.student_id = s.student_id
                WHERE d.status='Proposed' AND d.acknowledgement_status='Disputed'
                ORDER BY d.created_at
            ''')
            for ded_id, name, desc, amt, reason in cur.fetchall():
                tree.insert('', tk.END, iid=ded_id,
                            values=(ded_id, name, desc, f"{float(amt):.2f}", reason or ''))
        finally:
            conn.close()

    def resolve():
        sel = tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Pick a dispute first.")
            return
        ded_id = sel[0]
        action_win = tk.Toplevel(parent)
        action_win.title("Resolve dispute")
        action_win.transient(parent.winfo_toplevel())
        ttk.Label(action_win, text="Action:").grid(row=0, column=0, sticky='w', padx=8, pady=4)
        action_var = tk.StringVar(value='Uphold')
        ttk.OptionMenu(action_win, action_var, 'Uphold', 'Uphold', 'Reduce', 'Waive').grid(
            row=0, column=1, sticky='w', padx=8, pady=4)
        ttk.Label(action_win, text="New amount (Reduce only):").grid(
            row=1, column=0, sticky='w', padx=8, pady=4)
        amt_entry = ttk.Entry(action_win, width=12)
        amt_entry.grid(row=1, column=1, sticky='w', padx=8, pady=4)
        ttk.Label(action_win, text="Notes:").grid(row=2, column=0, sticky='nw', padx=8, pady=4)
        notes_entry = tk.Text(action_win, width=40, height=4)
        notes_entry.grid(row=2, column=1, padx=8, pady=4)

        def commit():
            action = action_var.get()
            actor = gui_instance.auth.current_user.get('username', 'staff')
            ts = _dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            notes = notes_entry.get('1.0', 'end').strip() or None
            conn = get_connection()
            try:
                cur = conn.cursor()
                cur.execute(
                    'SELECT amount, assignment_id FROM housing_deposit_deductions '
                    'WHERE deduction_id = ?', (ded_id,))
                row = cur.fetchone()
                if not row:
                    messagebox.showerror("Missing", "Deduction no longer exists.")
                    return
                current_amt, aid = float(row[0]), row[1]

                if action == 'Uphold':
                    new_amt = current_amt
                    cur.execute('''
                        UPDATE housing_deposit_deductions
                        SET acknowledgement_status='Resolved',
                            dispute_resolution_notes=?,
                            dispute_resolved_by=?, dispute_resolved_at=?
                        WHERE deduction_id=?
                    ''', (notes, actor, ts, ded_id))
                elif action == 'Reduce':
                    try:
                        new_amt = float(amt_entry.get())
                    except ValueError:
                        messagebox.showerror("Invalid", "Enter a valid amount.")
                        return
                    if new_amt < 0 or new_amt >= current_amt:
                        messagebox.showerror("Invalid",
                                             "New amount must be lower than the current.")
                        return
                    cur.execute('''
                        UPDATE housing_deposit_deductions
                        SET amount=?, acknowledgement_status='Resolved',
                            dispute_resolution_notes=?,
                            dispute_resolved_by=?, dispute_resolved_at=?
                        WHERE deduction_id=?
                    ''', (new_amt, notes, actor, ts, ded_id))
                else:  # Waive
                    cur.execute('''
                        UPDATE housing_deposit_deductions
                        SET amount=0, status='Waived',
                            acknowledgement_status='Resolved',
                            dispute_resolution_notes=?,
                            dispute_resolved_by=?, dispute_resolved_at=?
                        WHERE deduction_id=?
                    ''', (notes or 'Waived', actor, ts, ded_id))

                # Reconcile lifecycle state.
                try:
                    _ds.reconcile_from_deductions(cur, aid, actor=actor)
                except Exception:
                    pass
                conn.commit()
            finally:
                conn.close()
            action_win.destroy()
            refresh()
            messagebox.showinfo("Resolved", f"Dispute {ded_id} resolved.")

        ttk.Button(action_win, text="Resolve", command=commit).grid(
            row=3, column=0, columnspan=2, pady=8)

    btns = ttk.Frame(parent)
    btns.pack(fill='x', pady=(8, 0))
    ttk.Button(btns, text="Resolve Selected", command=resolve).pack(side='left', padx=4)
    ttk.Button(btns, text="Refresh", command=refresh).pack(side='left', padx=4)
    refresh()


# ---------------------------------------------------------------------------
# Tab 4 — TDP
# ---------------------------------------------------------------------------

def _build_tdp_tab(gui_instance, parent):
    sub = ttk.Notebook(parent)
    sub.pack(fill='both', expand=True)

    # Compliance report
    report_frame = ttk.Frame(sub, padding="8")
    sub.add(report_frame, text="Compliance Report")
    report_cols = ('assignment', 'student', 'held', 'state', 'scheme', 'deadline', 'days')
    rtree = ttk.Treeview(report_frame, columns=report_cols, show='headings', height=16)
    for c, t, w in [('assignment', 'Assignment', 140), ('student', 'Student', 180),
                    ('held', 'Held £', 90), ('state', 'State', 130),
                    ('scheme', 'Scheme', 120), ('deadline', 'Deadline', 110),
                    ('days', 'Days', 90)]:
        rtree.heading(c, text=t)
        rtree.column(c, width=w)
    rtree.tag_configure('overdue', foreground='#b00020')
    rtree.tag_configure('protected', foreground='#0a7a2f')
    rtree.pack(fill='both', expand=True)

    def refresh_report():
        for i in rtree.get_children():
            rtree.delete(i)
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute('''
                SELECT a.assignment_id, s.first_name || ' ' || s.last_name,
                       COALESCE(SUM(CASE WHEN p.status='Completed' THEN p.amount END), 0),
                       a.tdp_scheme, a.tdp_protected_at,
                       a.tdp_prescribed_info_sent_at, a.tdp_deadline,
                       a.tdp_exempt_reason
                FROM housing_assignments a
                JOIN students s ON a.student_id = s.student_id
                JOIN payments p ON p.reference_id = a.assignment_id
                  AND p.source_type='housing' AND p.payment_type='Deposit'
                GROUP BY a.assignment_id
                HAVING COALESCE(SUM(CASE WHEN p.status='Completed' THEN p.amount END), 0) > 0
                ORDER BY a.tdp_deadline
            ''')
            for aid, name, held, scheme, protected, info_sent, deadline, exempt in cur.fetchall():
                state, delta = _tdp._classify(scheme, protected, info_sent, deadline)
                days_text = ''
                tag = ()
                if state == 'Overdue':
                    days_text = f"{-delta} late"
                    tag = ('overdue',)
                elif state == 'Pending':
                    days_text = f"{delta} left"
                elif state == 'Protected':
                    tag = ('protected',)
                rtree.insert('', tk.END,
                             values=(aid, name, f"{float(held):,.2f}", state,
                                     scheme or 'Unprotected',
                                     deadline or '—', days_text), tags=tag)
        finally:
            conn.close()

    rbtns = ttk.Frame(report_frame)
    rbtns.pack(fill='x', pady=(8, 0))
    ttk.Button(rbtns, text="Refresh", command=refresh_report).pack(side='left')
    refresh_report()

    # Record protection
    rec_frame = ttk.Frame(sub, padding="8")
    sub.add(rec_frame, text="Record Protection")

    form_combo = ttk.Combobox(rec_frame, width=70, state='readonly')
    form_combo.grid(row=0, column=0, columnspan=4, sticky='w', padx=4, pady=4)

    def load_rec_candidates():
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute('''
                SELECT a.assignment_id, s.first_name || ' ' || s.last_name,
                       SUM(p.amount), a.tdp_scheme
                FROM payments p
                JOIN housing_assignments a ON p.reference_id = a.assignment_id
                JOIN students s ON a.student_id = s.student_id
                WHERE p.source_type='housing' AND p.payment_type='Deposit'
                  AND p.status='Completed'
                GROUP BY a.assignment_id
                HAVING SUM(p.amount) > 0
                ORDER BY a.assignment_id
            ''')
            rows = cur.fetchall()
        finally:
            conn.close()
        form_combo['values'] = [
            f"{aid}  |  {name}  |  £{held:,.2f}  |  {scheme or 'Unprotected'}"
            for aid, name, held, scheme in rows
        ]
    load_rec_candidates()

    fields = {}
    for i, (label, key, default) in enumerate([
        ("Scheme:", 'scheme', 'DPS'),
        ("Reference:", 'ref', ''),
        ("Protected on (YYYY-MM-DD):", 'protected_at', _dt.date.today().isoformat()),
        ("Prescribed info sent (YYYY-MM-DD):", 'info_sent', _dt.date.today().isoformat()),
        ("Exemption reason (if Exempt):", 'exempt', ''),
        ("Interest rate % (optional):", 'rate', ''),
        ("Interest policy:", 'policy', ''),
    ], start=1):
        ttk.Label(rec_frame, text=label).grid(row=i, column=0, sticky='w', padx=4, pady=2)
        if key == 'scheme':
            cb = ttk.Combobox(rec_frame, values=_tdp.TDP_SCHEMES, state='readonly', width=20)
            cb.set(default)
            cb.grid(row=i, column=1, sticky='w', padx=4, pady=2)
            fields[key] = cb
        elif key == 'policy':
            cb = ttk.Combobox(rec_frame, values=['', 'Tenant', 'Landlord', 'Scheme'],
                              state='readonly', width=20)
            cb.grid(row=i, column=1, sticky='w', padx=4, pady=2)
            fields[key] = cb
        else:
            e = ttk.Entry(rec_frame, width=30)
            if default:
                e.insert(0, default)
            e.grid(row=i, column=1, sticky='w', padx=4, pady=2)
            fields[key] = e

    def submit():
        text = form_combo.get()
        if not text:
            messagebox.showwarning("Select assignment", "Pick one first.")
            return
        aid = text.split('|', 1)[0].strip()
        scheme = fields['scheme'].get()
        ts = _dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        actor = gui_instance.auth.current_user.get('username', 'housing')

        conn = get_connection()
        try:
            cur = conn.cursor()

            # Compute deadline if missing.
            first_dep = _tdp._first_deposit_date(cur, aid)
            deadline = _tdp._compute_deadline(first_dep) if first_dep else None

            rate_text = fields['rate'].get().strip()
            policy = fields['policy'].get().strip() or None
            try:
                rate = float(rate_text) if rate_text else None
            except ValueError:
                messagebox.showerror("Invalid", "Interest rate must be numeric.")
                return

            if scheme == 'Exempt':
                reason = fields['exempt'].get().strip()
                if not reason:
                    messagebox.showerror("Required", "Exemption reason required.")
                    return
                cur.execute('''
                    UPDATE housing_assignments
                    SET tdp_scheme='Exempt', tdp_exempt_reason=?,
                        tdp_scheme_reference=NULL, tdp_protected_at=NULL,
                        tdp_prescribed_info_sent_at=NULL,
                        deposit_interest_rate=COALESCE(?, deposit_interest_rate),
                        deposit_interest_policy=COALESCE(?, deposit_interest_policy),
                        updated_at=?
                    WHERE assignment_id=?
                ''', (reason, rate, policy, ts, aid))
            else:
                ref = fields['ref'].get().strip()
                if not ref:
                    messagebox.showerror("Required", "Scheme reference required.")
                    return
                protected_at = fields['protected_at'].get().strip()
                info_sent = fields['info_sent'].get().strip()
                try:
                    _dt.datetime.strptime(protected_at, '%Y-%m-%d')
                    _dt.datetime.strptime(info_sent, '%Y-%m-%d')
                except ValueError:
                    messagebox.showerror("Invalid", "Dates must be YYYY-MM-DD.")
                    return
                # Warn if past deadline.
                if deadline and protected_at > deadline:
                    days_late = (_dt.datetime.strptime(protected_at, '%Y-%m-%d').date()
                                 - _dt.datetime.strptime(deadline, '%Y-%m-%d').date()).days
                    if not messagebox.askyesno(
                        "Past deadline",
                        f"Protection date is {days_late} day(s) past the 30-day "
                        f"deadline ({deadline}).\n\n"
                        f"Continue and accept penalty exposure?",
                    ):
                        return
                cur.execute('''
                    UPDATE housing_assignments
                    SET tdp_scheme=?, tdp_scheme_reference=?,
                        tdp_protected_at=?, tdp_prescribed_info_sent_at=?,
                        tdp_deadline=COALESCE(tdp_deadline, ?),
                        tdp_exempt_reason=NULL,
                        deposit_interest_rate=COALESCE(?, deposit_interest_rate),
                        deposit_interest_policy=COALESCE(?, deposit_interest_policy),
                        updated_at=?
                    WHERE assignment_id=?
                ''', (scheme, ref, protected_at, info_sent, deadline,
                      rate, policy, ts, aid))
            conn.commit()
        finally:
            conn.close()
        messagebox.showinfo("Recorded", f"TDP recorded for {aid}.")
        load_rec_candidates()
        refresh_report()

    ttk.Button(rec_frame, text="Save", command=submit).grid(row=9, column=0,
                                                            sticky='w', padx=4, pady=10)


# ---------------------------------------------------------------------------
# Tab 5 — Interest
# ---------------------------------------------------------------------------

def _build_interest_tab(gui_instance, parent):
    cols = ('assignment', 'student', 'held', 'rate', 'policy', 'accrued', 'last_run')
    tree = ttk.Treeview(parent, columns=cols, show='headings', height=14)
    for c, t, w in [('assignment', 'Assignment', 140), ('student', 'Student', 180),
                    ('held', 'Held £', 90), ('rate', 'Rate %', 80),
                    ('policy', 'Policy', 100), ('accrued', 'Accrued £', 100),
                    ('last_run', 'Last run', 120)]:
        tree.heading(c, text=t)
        tree.column(c, width=w)
    tree.pack(fill='both', expand=True)

    def refresh():
        for i in tree.get_children():
            tree.delete(i)
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute('''
                SELECT a.assignment_id, s.first_name || ' ' || s.last_name,
                       COALESCE(SUM(CASE WHEN p.status='Completed' THEN p.amount END), 0),
                       a.deposit_interest_rate, a.deposit_interest_policy,
                       COALESCE(a.deposit_interest_accrued, 0),
                       a.deposit_interest_last_accrual_date
                FROM housing_assignments a
                JOIN students s ON a.student_id = s.student_id
                LEFT JOIN payments p ON p.reference_id = a.assignment_id
                                     AND p.source_type='housing'
                                     AND p.payment_type='Deposit'
                WHERE COALESCE(a.deposit_interest_rate, 0) > 0
                   OR COALESCE(a.deposit_interest_accrued, 0) > 0
                GROUP BY a.assignment_id
                ORDER BY a.assignment_id
            ''')
            for aid, name, held, rate, policy, accrued, last in cur.fetchall():
                tree.insert('', tk.END, values=(
                    aid, name, f"{float(held):,.2f}",
                    f"{float(rate or 0):.2f}",
                    policy or '—',
                    f"{float(accrued):,.2f}",
                    last or '(never)',
                ))
        finally:
            conn.close()

    def accrue_now():
        today = _dt.date.today().isoformat()
        actor = gui_instance.auth.current_user.get('username', 'housing')
        conn = get_connection()
        accrued_n = 0
        total = 0.0
        try:
            cur = conn.cursor()
            cur.execute('''
                SELECT assignment_id, deposit_interest_rate,
                       deposit_interest_last_accrual_date
                FROM housing_assignments
                WHERE COALESCE(deposit_interest_rate, 0) > 0
            ''')
            for aid, rate, last in cur.fetchall():
                # Find held principal.
                cur.execute('''
                    SELECT COALESCE(SUM(amount), 0) FROM payments
                    WHERE source_type='housing' AND payment_type='Deposit'
                      AND status='Completed' AND reference_id = ?
                ''', (aid,))
                principal = float(cur.fetchone()[0] or 0)
                if principal <= 0:
                    continue
                last_accrual = last or _interest._first_deposit_date(cur, aid)
                if not last_accrual:
                    continue
                _, amount = _interest._accrue_one(
                    cur, aid, float(rate), last_accrual, today, principal,
                    created_by=actor,
                )
                if amount > 0:
                    accrued_n += 1
                    total += amount
            conn.commit()
        finally:
            conn.close()
        if accrued_n:
            messagebox.showinfo("Accrued",
                                f"Accrued £{total:,.2f} across {accrued_n} assignment(s).")
        else:
            messagebox.showinfo("Up to date", "Nothing new to accrue.")
        refresh()

    btns = ttk.Frame(parent)
    btns.pack(fill='x', pady=(8, 0))
    ttk.Button(btns, text="Accrue Now", command=accrue_now).pack(side='left', padx=4)
    ttk.Button(btns, text="Refresh", command=refresh).pack(side='left', padx=4)
    refresh()


# ---------------------------------------------------------------------------
# Tab 6 — State Log
# ---------------------------------------------------------------------------

def _build_state_log_tab(gui_instance, parent):
    # Top: assignments + their current state.
    top = ttk.LabelFrame(parent, text="Assignments", padding="8")
    top.pack(fill='x', pady=(0, 8))
    cols = ('assignment', 'student', 'state', 'last_change')
    state_tree = ttk.Treeview(top, columns=cols, show='headings', height=8)
    for c, t, w in [('assignment', 'Assignment', 140), ('student', 'Student', 180),
                    ('state', 'State', 180), ('last_change', 'Last change', 180)]:
        state_tree.heading(c, text=t)
        state_tree.column(c, width=w)
    state_tree.pack(fill='both', expand=True)

    # Bottom: log entries for the selected assignment.
    bottom = ttk.LabelFrame(parent, text="Transition log", padding="8")
    bottom.pack(fill='both', expand=True)
    log_cols = ('at', 'from', 'to', 'actor', 'reason')
    log_tree = ttk.Treeview(bottom, columns=log_cols, show='headings', height=12)
    for c, t, w in [('at', 'At', 160), ('from', 'From', 160), ('to', 'To', 160),
                    ('actor', 'Actor', 120), ('reason', 'Reason', 360)]:
        log_tree.heading(c, text=t)
        log_tree.column(c, width=w)
    log_tree.pack(fill='both', expand=True)

    def refresh_state():
        for i in state_tree.get_children():
            state_tree.delete(i)
        for i in log_tree.get_children():
            log_tree.delete(i)
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute('''
                SELECT a.assignment_id, s.first_name || ' ' || s.last_name,
                       a.deposit_state,
                       (SELECT MAX(created_at) FROM housing_deposit_state_log l
                        WHERE l.assignment_id = a.assignment_id)
                FROM housing_assignments a
                JOIN students s ON a.student_id = s.student_id
                WHERE a.deposit_state IS NOT NULL
                ORDER BY a.deposit_state, a.assignment_id
            ''')
            for aid, name, state, last in cur.fetchall():
                state_tree.insert('', tk.END, iid=aid,
                                  values=(aid, name, state or '—', last or '—'))
        finally:
            conn.close()

    def on_select(_evt=None):
        sel = state_tree.selection()
        for i in log_tree.get_children():
            log_tree.delete(i)
        if not sel:
            return
        aid = sel[0]
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute('''
                SELECT created_at, from_state, to_state, actor, reason
                FROM housing_deposit_state_log
                WHERE assignment_id = ?
                ORDER BY created_at
            ''', (aid,))
            for at, fr, to, actor, reason in cur.fetchall():
                log_tree.insert('', tk.END, values=(
                    at, fr or '(none)', to, actor, reason or ''))
        finally:
            conn.close()
    state_tree.bind('<<TreeviewSelect>>', on_select)

    btns = ttk.Frame(parent)
    btns.pack(fill='x', pady=(8, 0))
    ttk.Button(btns, text="Refresh", command=refresh_state).pack(side='left')
    refresh_state()


# ---------------------------------------------------------------------------
# Move-out deduction capture (called from inspection_manager after a Move-out
# inspection completes).
# ---------------------------------------------------------------------------

def prompt_move_out_deductions(parent_widget, inspection_id, auth):
    """Dialog: itemise proposed deductions tied to a Move-out inspection.

    Pulls the inspection's room → most-recent assignment, then writes one
    housing_deposit_deductions row per entry with status='Proposed'.
    Reconciles the deposit lifecycle state on commit.
    """
    if not auth or not auth.current_user:
        return
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            'SELECT room_id, inspection_type FROM housing_inspections '
            'WHERE inspection_id = ?', (inspection_id,))
        row = cur.fetchone()
        if not row:
            return
        room_id, itype = row
        if itype != 'Move-out':
            return
        cur.execute('''
            SELECT assignment_id, student_id FROM housing_assignments
            WHERE room_id = ?
            ORDER BY CASE WHEN status='Active' THEN 0 ELSE 1 END, created_at DESC
            LIMIT 1
        ''', (room_id,))
        assn = cur.fetchone()
        if not assn:
            messagebox.showinfo("No assignment",
                                "No assignment found for this room — skipping deduction capture.")
            return
        assignment_id, student_id = assn
    finally:
        conn.close()

    if not messagebox.askyesno(
        "Capture deductions?",
        "Capture itemised deductions against the held deposit for this Move-out "
        "inspection?\n\nYou can also do this later via Deposits → Process Refund.",
        parent=parent_widget,
    ):
        return

    dialog = tk.Toplevel(parent_widget)
    dialog.title("Proposed deductions")
    dialog.geometry("560x400")
    dialog.transient(parent_widget.winfo_toplevel())

    ttk.Label(dialog, text=f"Assignment: {assignment_id}  ·  Student: {student_id}",
              font=('Arial', 10, 'bold')).pack(anchor='w', padx=10, pady=(10, 4))
    ttk.Label(dialog, foreground='#555', wraplength=520, justify='left',
              text="Each line you add becomes a Proposed deduction. The student "
                   "can acknowledge or dispute before any refund is posted.").pack(
        anchor='w', padx=10, pady=(0, 8))

    cols = ('description', 'amount')
    tree = ttk.Treeview(dialog, columns=cols, show='headings', height=8)
    tree.heading('description', text='Description')
    tree.heading('amount', text='Amount £')
    tree.column('description', width=380)
    tree.column('amount', width=100)
    tree.pack(fill='both', expand=True, padx=10, pady=(0, 8))

    pending = []

    def add_line():
        desc = simpledialog.askstring("New deduction", "Description:", parent=dialog)
        if not desc:
            return
        amt_str = simpledialog.askstring("New deduction", f"Amount for '{desc}' (£):",
                                         parent=dialog)
        if not amt_str:
            return
        try:
            amt = float(amt_str)
            if amt <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid", "Amount must be positive.", parent=dialog)
            return
        pending.append((desc, amt))
        tree.insert('', tk.END, values=(desc, f"{amt:.2f}"))

    def remove_line():
        sel = tree.selection()
        if not sel:
            return
        idx = tree.index(sel[0])
        tree.delete(sel[0])
        pending.pop(idx)

    def commit():
        if not pending:
            dialog.destroy()
            return
        ts = _dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        actor = auth.current_user.get('username', 'staff')
        conn = get_connection()
        try:
            cur = conn.cursor()
            for desc, amt in pending:
                cur.execute('''
                    INSERT INTO housing_deposit_deductions
                    (deduction_id, assignment_id, deposit_payment_id, inspection_id,
                     description, amount, status, acknowledgement_status,
                     created_by, created_at)
                    VALUES (?, ?, NULL, ?, ?, ?, 'Proposed', 'Pending', ?, ?)
                ''', (generate_id('DED'), assignment_id, inspection_id,
                      desc, amt, actor, ts))
            try:
                _ds.reconcile_from_deductions(cur, assignment_id, actor=actor)
            except Exception:
                pass
            conn.commit()
        finally:
            conn.close()
        messagebox.showinfo("Recorded",
                            f"{len(pending)} proposed deduction(s) saved.\n\n"
                            f"Process Deposit Refund (Deposits panel) to apply them.",
                            parent=parent_widget)
        dialog.destroy()

    btns = ttk.Frame(dialog)
    btns.pack(fill='x', padx=10, pady=(0, 10))
    ttk.Button(btns, text="Add", command=add_line).pack(side='left', padx=4)
    ttk.Button(btns, text="Remove selected", command=remove_line).pack(side='left', padx=4)
    ttk.Button(btns, text="Save", command=commit).pack(side='right', padx=4)
    ttk.Button(btns, text="Cancel", command=dialog.destroy).pack(side='right', padx=4)


# ---------------------------------------------------------------------------
# Student-side dialog (called from main_gui for view_own_record users)
# ---------------------------------------------------------------------------

def show_student_deductions(gui_instance):
    """Dialog: lists the current student's Proposed deductions and lets them
    acknowledge or dispute each one. Uses the same SQL the CLI does."""
    auth = gui_instance.auth
    if not auth or not auth.current_user:
        return
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute('SELECT student_id FROM users WHERE id = ?',
                    (auth.current_user['id'],))
        row = cur.fetchone()
        if not row or not row[0]:
            messagebox.showinfo("No record",
                                "No student record linked to your account.")
            return
        student_id = row[0]
    finally:
        conn.close()

    gui_instance.clear_content()
    ttk.Label(gui_instance.content_frame, text="My Deposit Deductions",
              font=('Arial', 16, 'bold')).pack(anchor='w', pady=(0, 8))
    ttk.Label(gui_instance.content_frame, foreground='#555',
              text="Acknowledge each line or raise a dispute. Disputed lines must "
                   "be resolved by housing staff before any refund is processed.",
              wraplength=600, justify='left').pack(anchor='w', pady=(0, 8))

    cols = ('id', 'description', 'amount', 'status', 'reason', 'resolution')
    tree = ttk.Treeview(gui_instance.content_frame, columns=cols,
                        show='headings', height=12)
    for c, t, w in [('id', 'ID', 140), ('description', 'Description', 320),
                    ('amount', 'Amount £', 90), ('status', 'Status', 130),
                    ('reason', 'Your dispute', 240),
                    ('resolution', 'Staff resolution', 240)]:
        tree.heading(c, text=t)
        tree.column(c, width=w)
    tree.pack(fill='both', expand=True)

    def refresh():
        for i in tree.get_children():
            tree.delete(i)
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute('''
                SELECT d.deduction_id, d.description, d.amount,
                       d.acknowledgement_status, d.dispute_reason,
                       d.dispute_resolution_notes
                FROM housing_deposit_deductions d
                JOIN housing_assignments a ON d.assignment_id = a.assignment_id
                WHERE a.student_id = ? AND d.status='Proposed'
                ORDER BY d.created_at
            ''', (student_id,))
            for did, desc, amt, ack, reason, resolution in cur.fetchall():
                tree.insert('', tk.END, iid=did, values=(
                    did, desc, f"{float(amt):.2f}",
                    ack, reason or '', resolution or '',
                ))
        finally:
            conn.close()
    refresh()

    def _act(action):
        sel = tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Select a deduction first.")
            return
        ded_id = sel[0]
        ts = _dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute('SELECT acknowledgement_status, assignment_id '
                        'FROM housing_deposit_deductions WHERE deduction_id=?',
                        (ded_id,))
            r = cur.fetchone()
            if not r:
                return
            ack, aid = r
            if ack == 'Resolved':
                messagebox.showinfo("Resolved",
                                    "This line has already been resolved by staff.")
                return
            if action == 'ack':
                cur.execute('''
                    UPDATE housing_deposit_deductions
                    SET acknowledgement_status='Acknowledged',
                        acknowledged_at=?, dispute_reason=NULL
                    WHERE deduction_id=? AND status='Proposed'
                ''', (ts, ded_id))
            else:  # dispute
                reason = simpledialog.askstring(
                    "Reason", "Reason for dispute:", parent=gui_instance.content_frame)
                if not reason:
                    return
                cur.execute('''
                    UPDATE housing_deposit_deductions
                    SET acknowledgement_status='Disputed',
                        dispute_reason=?, acknowledged_at=NULL
                    WHERE deduction_id=? AND status='Proposed'
                ''', (reason, ded_id))
            try:
                _ds.reconcile_from_deductions(cur, aid, actor=student_id)
            except Exception:
                pass
            conn.commit()
        finally:
            conn.close()
        refresh()

    btns = ttk.Frame(gui_instance.content_frame)
    btns.pack(fill='x', pady=(8, 0))
    ttk.Button(btns, text="Acknowledge",
               command=lambda: _act('ack')).pack(side='left', padx=4)
    ttk.Button(btns, text="Dispute",
               command=lambda: _act('dispute')).pack(side='left', padx=4)
    ttk.Button(btns, text="Refresh", command=refresh).pack(side='left', padx=4)
