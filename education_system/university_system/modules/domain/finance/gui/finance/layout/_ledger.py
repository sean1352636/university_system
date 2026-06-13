"""General Ledger tabs: Trial Balance + Journals."""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date

from education_system.university_system.core.i18n import get_text as _


class LedgerMixin:
    """Trial Balance and Journals tabs (read-only views over gl_* tables).

    Posting and seeding are exposed as buttons on the Trial Balance tab so
    finance staff can bootstrap and re-run backfill without leaving the GUI.
    """

    # --- Trial Balance ---------------------------------------------------

    def create_trial_balance_tab(self):
        frame = tk.Frame(self.content_frame, bg='white')
        self.tab_frames['trial_balance'] = frame

        toolbar = ttk.Frame(frame)
        toolbar.pack(fill='x', padx=10, pady=10)
        ttk.Label(toolbar, text=_("finance_gui.ledger.trial_balance_title", default="📊 Trial Balance"),
                  font=('Arial', 14, 'bold')).pack(side='left')

        # Date range
        ttk.Label(toolbar, text=_("finance_gui.ledger.from", default="From:")).pack(side='left', padx=(20, 5))
        start_var = tk.StringVar(value='')
        ttk.Entry(toolbar, textvariable=start_var, width=12).pack(side='left', padx=2)
        ttk.Label(toolbar, text=_("finance_gui.ledger.to", default="To:")).pack(side='left', padx=(10, 5))
        end_var = tk.StringVar(value='')
        ttk.Entry(toolbar, textvariable=end_var, width=12).pack(side='left', padx=2)

        ttk.Button(toolbar, text=_("finance_gui.ledger.init", default="Init / Seed Ledger"),
                   command=self._init_ledger_action).pack(side='right', padx=5)
        ttk.Button(toolbar, text=_("finance_gui.ledger.backfill", default="Backfill from Ops"),
                   command=self._backfill_action).pack(side='right', padx=5)

        # Table
        table_frame = ttk.Frame(frame)
        table_frame.pack(fill='both', expand=True, padx=10, pady=10)
        columns = ('Code', 'Name', 'Type', 'Debit', 'Credit', 'Balance')
        tb_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=25)
        widths = {'Code': 70, 'Name': 280, 'Type': 90, 'Debit': 110, 'Credit': 110, 'Balance': 130}
        anchors = {'Code': 'w', 'Name': 'w', 'Type': 'center', 'Debit': 'e', 'Credit': 'e', 'Balance': 'e'}
        for col in columns:
            tb_tree.heading(col, text=col)
            tb_tree.column(col, width=widths[col], anchor=anchors[col])
        vsb = ttk.Scrollbar(table_frame, orient='vertical', command=tb_tree.yview)
        tb_tree.configure(yscrollcommand=vsb.set)
        tb_tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        # Totals + reload
        bottom = ttk.Frame(frame)
        bottom.pack(fill='x', padx=10, pady=5)
        totals_label = ttk.Label(bottom, text="—", font=('Arial', 10, 'bold'))
        totals_label.pack(side='left')

        def reload_tb(*_a):
            from education_system.university_system.modules.domain.finance.ledger import trial_balance
            for iid in tb_tree.get_children():
                tb_tree.delete(iid)
            try:
                rows = trial_balance(
                    start_date=start_var.get().strip() or None,
                    end_date=end_var.get().strip() or None,
                )
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load trial balance: {e}")
                return
            total_dr = total_cr = 0.0
            for r in rows:
                tb_tree.insert('', 'end', values=(
                    r['account_code'], r['account_name'], r['account_type'],
                    f"£{r['debit_total']:,.2f}",
                    f"£{r['credit_total']:,.2f}",
                    f"£{r['balance']:,.2f}",
                ))
                total_dr += r['debit_total']; total_cr += r['credit_total']
            diff = total_dr - total_cr
            balance_indicator = "✓ balanced" if abs(diff) < 0.01 else f"⚠ diff £{diff:,.2f}"
            totals_label.config(
                text=f"Accounts: {len(rows)} | Dr Total: £{total_dr:,.2f} | "
                     f"Cr Total: £{total_cr:,.2f} | {balance_indicator}"
            )

        ttk.Button(bottom, text=_("common.refresh", default="Refresh"),
                   command=reload_tb).pack(side='right', padx=5)

        self._tb_reload = reload_tb  # exposed so backfill/init can refresh
        reload_tb()

    # --- Journals --------------------------------------------------------

    def create_journals_tab(self):
        frame = tk.Frame(self.content_frame, bg='white')
        self.tab_frames['journals'] = frame

        toolbar = ttk.Frame(frame)
        toolbar.pack(fill='x', padx=10, pady=10)
        ttk.Label(toolbar, text=_("finance_gui.ledger.journals_title", default="📒 Journals"),
                  font=('Arial', 14, 'bold')).pack(side='left')

        ttk.Label(toolbar, text=_("finance_gui.ledger.source", default="Source:")).pack(side='left', padx=(20, 5))
        source_var = tk.StringVar(value='all')
        ttk.Combobox(
            toolbar, textvariable=source_var, width=14, state='readonly',
            values=('all', 'payment', 'refund', 'fee_assignment', 'manual'),
        ).pack(side='left', padx=2)

        # Table
        table_frame = ttk.Frame(frame)
        table_frame.pack(fill='both', expand=True, padx=10, pady=10)
        columns = ('ID', 'Date', 'Period', 'Source', 'SrcID', 'Entity', 'Description', 'Amount', 'Posted By')
        j_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=25)
        widths = {'ID': 60, 'Date': 100, 'Period': 60, 'Source': 110, 'SrcID': 60,
                  'Entity': 60, 'Description': 320, 'Amount': 110, 'Posted By': 100}
        anchors = {'ID': 'center', 'Date': 'center', 'Period': 'center', 'Source': 'w',
                   'SrcID': 'center', 'Entity': 'center', 'Description': 'w',
                   'Amount': 'e', 'Posted By': 'w'}
        for col in columns:
            j_tree.heading(col, text=col)
            j_tree.column(col, width=widths[col], anchor=anchors[col])
        vsb = ttk.Scrollbar(table_frame, orient='vertical', command=j_tree.yview)
        j_tree.configure(yscrollcommand=vsb.set)
        j_tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        def reload_journals(*_a):
            from education_system.university_system.modules.domain.finance.ledger.reports import journals_list
            for iid in j_tree.get_children():
                j_tree.delete(iid)
            try:
                rows = journals_list(
                    source_type=None if source_var.get() == 'all' else source_var.get(),
                )
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load journals: {e}")
                return
            for r in rows:
                j_tree.insert('', 'end', values=(
                    r['journal_id'], r['journal_date'], r['period_id'],
                    r['source_type'], r['source_id'] or '',
                    r['entity_id'], r['description'],
                    f"£{r['amount']:,.2f}", r['posted_by'],
                ))

        def open_journal(_event=None):
            sel = j_tree.selection()
            if not sel:
                return
            jid = j_tree.item(sel[0])['values'][0]
            self._show_journal_lines(jid)

        j_tree.bind('<Double-1>', open_journal)

        bottom = ttk.Frame(frame)
        bottom.pack(fill='x', padx=10, pady=5)
        ttk.Label(
            bottom,
            text=_("finance_gui.ledger.double_click_hint",
                   default="Double-click a journal to view its lines."),
            foreground='#666',
        ).pack(side='left')
        ttk.Button(bottom, text=_("common.refresh", default="Refresh"),
                   command=reload_journals).pack(side='right', padx=5)

        source_var.trace('w', reload_journals)
        reload_journals()

    def _show_journal_lines(self, journal_id):
        from education_system.university_system.modules.domain.finance.ledger.reports import journal_lines
        win = tk.Toplevel(self.root)
        win.title(f"Journal {journal_id}")
        win.geometry("700x400")

        ttk.Label(win, text=f"Journal #{journal_id}", font=('Arial', 12, 'bold')).pack(pady=10)

        cols = ('Account', 'Name', 'Debit', 'Credit', 'Memo')
        tree = ttk.Treeview(win, columns=cols, show='headings')
        widths = {'Account': 80, 'Name': 200, 'Debit': 100, 'Credit': 100, 'Memo': 220}
        anchors = {'Account': 'w', 'Name': 'w', 'Debit': 'e', 'Credit': 'e', 'Memo': 'w'}
        for c in cols:
            tree.heading(c, text=c)
            tree.column(c, width=widths[c], anchor=anchors[c])
        tree.pack(fill='both', expand=True, padx=10, pady=10)

        lines = journal_lines(journal_id)
        total_dr = total_cr = 0.0
        for ln in lines:
            tree.insert('', 'end', values=(
                ln['account_code'], ln['account_name'],
                f"£{ln['debit']:,.2f}" if ln['debit'] else '',
                f"£{ln['credit']:,.2f}" if ln['credit'] else '',
                ln['memo'] or '',
            ))
            total_dr += ln['debit']; total_cr += ln['credit']
        ttk.Label(
            win,
            text=f"Dr Total: £{total_dr:,.2f}    Cr Total: £{total_cr:,.2f}    "
                 f"{'✓ balanced' if abs(total_dr - total_cr) < 0.01 else '⚠ unbalanced'}",
            font=('Arial', 10, 'bold'),
        ).pack(pady=10)

    # --- Bootstrap actions -----------------------------------------------

    def _init_ledger_action(self):
        from education_system.university_system.modules.domain.finance.ledger import init_ledger
        try:
            init_ledger()
            messagebox.showinfo(
                "Ledger initialized",
                "Schema ensured, default entity and chart of accounts seeded, "
                "and periods created for the current fiscal year.",
            )
            if hasattr(self, '_tb_reload'):
                self._tb_reload()
        except Exception as e:
            messagebox.showerror("Init failed", str(e))

    def _backfill_action(self):
        from education_system.university_system.modules.domain.finance.ledger import backfill
        if not messagebox.askyesno(
            "Backfill",
            "Replay all payments, refunds, and fee assignments into the ledger?\n\n"
            "Already-posted rows are skipped automatically. Safe to re-run.",
        ):
            return
        try:
            summary = backfill(posted_by='gui_backfill')
        except Exception as e:
            messagebox.showerror("Backfill failed", str(e))
            return
        msg = f"Posted: {summary['posted']}\nErrors: {len(summary['errors'])}"
        if summary['errors']:
            sample = "\n".join(f"  [{st}] {sid}: {err[:80]}"
                               for st, sid, err in summary['errors'][:10])
            msg += f"\n\nFirst errors:\n{sample}"
        messagebox.showinfo("Backfill complete", msg)
        if hasattr(self, '_tb_reload'):
            self._tb_reload()

    # --- Period close --------------------------------------------------

    def create_period_close_tab(self):
        """Period close & lock tab — admin-only.

        Lists every gl_period with status (open/closed/locked), the count
        of journals posted into it, and per-row actions to close, reopen
        (closed only), or lock. Posting into a closed/locked period is
        blocked at the ledger layer (PeriodClosedError); this tab is the
        UI for triggering those state transitions.
        """
        frame = tk.Frame(self.content_frame, bg='white')
        self.tab_frames['period_close'] = frame

        toolbar = ttk.Frame(frame)
        toolbar.pack(fill='x', padx=10, pady=10)
        ttk.Label(
            toolbar,
            text=_("finance_gui.ledger.period_close_title", default="🔒 Period Close & Lock"),
            font=('Arial', 14, 'bold'),
        ).pack(side='left')

        # Table
        table_frame = ttk.Frame(frame)
        table_frame.pack(fill='both', expand=True, padx=10, pady=10)
        columns = ('PeriodID', 'FY', 'P#', 'Start', 'End', 'Status', 'Journals',
                   'ClosedAt', 'ClosedBy')
        tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=18)
        widths = {'PeriodID': 70, 'FY': 60, 'P#': 40, 'Start': 100, 'End': 100,
                  'Status': 80, 'Journals': 80, 'ClosedAt': 150, 'ClosedBy': 100}
        anchors = {'PeriodID': 'center', 'FY': 'center', 'P#': 'center',
                   'Start': 'center', 'End': 'center', 'Status': 'center',
                   'Journals': 'e', 'ClosedAt': 'w', 'ClosedBy': 'w'}
        for c in columns:
            tree.heading(c, text=c)
            tree.column(c, width=widths[c], anchor=anchors[c])
        vsb = ttk.Scrollbar(table_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        # Action buttons (operate on selected row)
        action_frame = ttk.Frame(frame)
        action_frame.pack(fill='x', padx=10, pady=5)

        def _selected_period():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning(
                    _("common.warning", default="Warning"),
                    _("finance_gui.ledger.no_period_selected",
                      default="Select a period row first."),
                )
                return None, None
            values = tree.item(sel[0])['values']
            return int(values[0]), values[5]  # period_id, status

        def _resolve_user():
            try:
                from education_system.university_system.infrastructure.shared_context import get_auth
                auth = get_auth()
                if auth and getattr(auth, 'current_user', None):
                    return auth.current_user.get('username', 'admin')
            except Exception:
                pass
            return 'admin'

        def reload_periods(*_a):
            from education_system.university_system.modules.domain.finance.ledger import list_periods
            for iid in tree.get_children():
                tree.delete(iid)
            try:
                rows = list_periods()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load periods: {e}")
                return
            for r in rows:
                tag = r['status']  # open/closed/locked → tag for color
                tree.insert('', 'end', values=(
                    r['period_id'], r['fiscal_year'], r['period_no'],
                    r['start_date'], r['end_date'], r['status'],
                    r['journal_count'],
                    r['closed_at'] or '', r['closed_by'] or '',
                ), tags=(tag,))
            tree.tag_configure('open', background='white')
            tree.tag_configure('closed', background='#fff8e1')   # amber
            tree.tag_configure('locked', background='#ffebee')   # red

        def close_action():
            from education_system.university_system.modules.domain.finance.ledger import close_period
            from education_system.university_system.modules.domain.finance.ledger.periods import PeriodStateError
            pid, status = _selected_period()
            if pid is None:
                return
            if status != 'open':
                messagebox.showwarning("Cannot close", f"Period status is '{status}'; only 'open' periods can be closed.")
                return
            if not messagebox.askyesno("Confirm close",
                                      f"Close period {pid}?\n\nPosting into this period "
                                      "will be rejected until it is reopened."):
                return
            try:
                close_period(pid, closed_by=_resolve_user())
            except (PeriodStateError, Exception) as e:
                messagebox.showerror("Close failed", str(e))
                return
            messagebox.showinfo("Closed", f"Period {pid} is now closed.")
            reload_periods()

        def reopen_action():
            from education_system.university_system.modules.domain.finance.ledger import reopen_period
            from education_system.university_system.modules.domain.finance.ledger.periods import PeriodStateError
            pid, status = _selected_period()
            if pid is None:
                return
            if status == 'locked':
                messagebox.showwarning("Cannot reopen",
                                      f"Period {pid} is locked. Only superseding journals in a "
                                      "later period can correct entries here.")
                return
            if status == 'open':
                return
            if not messagebox.askyesno("Confirm reopen",
                                      f"Reopen period {pid}? Posting will be allowed again."):
                return
            try:
                reopen_period(pid)
            except (PeriodStateError, Exception) as e:
                messagebox.showerror("Reopen failed", str(e))
                return
            reload_periods()

        def lock_action():
            from education_system.university_system.modules.domain.finance.ledger import lock_period
            pid, status = _selected_period()
            if pid is None:
                return
            if status == 'locked':
                return
            if not messagebox.askyesno("Confirm lock",
                                      f"Lock period {pid}?\n\nThis cannot be reversed. After "
                                      "locking, only superseding journals in a later period can "
                                      "correct entries."):
                return
            try:
                lock_period(pid, locked_by=_resolve_user())
            except Exception as e:
                messagebox.showerror("Lock failed", str(e))
                return
            messagebox.showinfo("Locked", f"Period {pid} is now locked.")
            reload_periods()

        ttk.Button(action_frame, text=_("finance_gui.ledger.close_period", default="Close"),
                   command=close_action).pack(side='left', padx=5)
        ttk.Button(action_frame, text=_("finance_gui.ledger.reopen_period", default="Reopen"),
                   command=reopen_action).pack(side='left', padx=5)
        ttk.Button(action_frame, text=_("finance_gui.ledger.lock_period", default="Lock"),
                   command=lock_action).pack(side='left', padx=5)
        ttk.Button(action_frame, text=_("common.refresh", default="Refresh"),
                   command=reload_periods).pack(side='right', padx=5)

        # Help text
        help_frame = ttk.Frame(frame)
        help_frame.pack(fill='x', padx=10, pady=(0, 10))
        ttk.Label(
            help_frame,
            text=("Open → Closed: posting into the period is rejected. Reversible by admin.\n"
                  "Closed → Locked: stronger close (e.g. after external audit). Cannot be reversed."),
            foreground='#666',
        ).pack(side='left')

        reload_periods()
