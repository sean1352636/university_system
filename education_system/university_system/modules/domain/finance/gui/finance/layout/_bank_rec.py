"""Bank reconciliation tab. Admin/staff: import a CSV statement, run the
auto-matcher, and clear the unmatched-exception queue with manual matches."""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinter.simpledialog import askinteger

from education_system.university_system.modules.shared.utils.i18n import get_text as _


class BankRecMixin:
    """🏦 Bank Rec tab — statement import + match queue."""

    def create_bank_rec_tab(self):
        frame = tk.Frame(self.content_frame, bg='white')
        self.tab_frames['bank_rec'] = frame

        # Header
        toolbar = ttk.Frame(frame)
        toolbar.pack(fill='x', padx=10, pady=10)
        ttk.Label(
            toolbar,
            text=_("finance_gui.bank_rec.title", default="🏦 Bank Reconciliation"),
            font=('Arial', 14, 'bold'),
        ).pack(side='left')

        # Statement selector
        ttk.Label(toolbar, text=_("finance_gui.bank_rec.statement",
                                   default="Statement:")).pack(side='left', padx=(20, 5))
        statement_var = tk.StringVar()
        statement_combo = ttk.Combobox(toolbar, textvariable=statement_var,
                                        width=40, state='readonly')
        statement_combo.pack(side='left', padx=5)

        # Status filter
        ttk.Label(toolbar, text=_("finance_gui.bank_rec.status_filter",
                                   default="Status:")).pack(side='left', padx=(20, 5))
        status_var = tk.StringVar(value='unmatched')
        status_combo = ttk.Combobox(
            toolbar, textvariable=status_var, width=14, state='readonly',
            values=('all', 'unmatched', 'matched_auto', 'matched_manual', 'discarded'),
        )
        status_combo.pack(side='left', padx=5)

        # Action buttons
        ttk.Button(toolbar, text=_("finance_gui.bank_rec.init",
                                    default="Init Schema"),
                   command=self._bank_rec_init_action).pack(side='right', padx=5)
        ttk.Button(toolbar, text=_("finance_gui.bank_rec.import",
                                    default="Import CSV…"),
                   command=lambda: self._bank_rec_import_action(reload_statements)
                   ).pack(side='right', padx=5)
        ttk.Button(toolbar, text=_("finance_gui.bank_rec.auto_match",
                                    default="Auto-match"),
                   command=lambda: self._bank_rec_automatch_action(statement_var, reload_lines)
                   ).pack(side='right', padx=5)

        # Lines table
        table_frame = ttk.Frame(frame)
        table_frame.pack(fill='both', expand=True, padx=10, pady=10)
        columns = ('LineID', 'No', 'Date', 'Amount', 'Description', 'Reference',
                   'Status', 'Match')
        tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=22)
        widths = {'LineID': 60, 'No': 40, 'Date': 100, 'Amount': 100,
                  'Description': 280, 'Reference': 150,
                  'Status': 110, 'Match': 110}
        anchors = {'LineID': 'center', 'No': 'center', 'Date': 'center',
                   'Amount': 'e', 'Description': 'w', 'Reference': 'w',
                   'Status': 'center', 'Match': 'center'}
        for c in columns:
            tree.heading(c, text=c)
            tree.column(c, width=widths[c], anchor=anchors[c])
        vsb = ttk.Scrollbar(table_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        # Bottom action row
        bottom = ttk.Frame(frame)
        bottom.pack(fill='x', padx=10, pady=5)

        summary_label = ttk.Label(bottom, text="—", font=('Arial', 10, 'bold'))
        summary_label.pack(side='left')

        ttk.Button(bottom, text=_("finance_gui.bank_rec.manual_match",
                                   default="Manual match…"),
                   command=lambda: self._bank_rec_manual_match_action(tree, reload_lines)
                   ).pack(side='right', padx=5)
        ttk.Button(bottom, text=_("finance_gui.bank_rec.discard",
                                   default="Discard"),
                   command=lambda: self._bank_rec_discard_action(tree, reload_lines)
                   ).pack(side='right', padx=5)
        ttk.Button(bottom, text=_("finance_gui.bank_rec.unmatch",
                                   default="Unmatch"),
                   command=lambda: self._bank_rec_unmatch_action(tree, reload_lines)
                   ).pack(side='right', padx=5)
        ttk.Button(bottom, text=_("common.refresh", default="Refresh"),
                   command=lambda: reload_lines()).pack(side='right', padx=5)

        # State holders
        self._bank_rec_statements = []  # list of dicts

        def reload_statements():
            from education_system.university_system.modules.domain.finance.bank_rec import list_statements
            try:
                rows = list_statements()
            except Exception as e:
                rows = []
                summary_label.config(text=f"⚠ schema not initialised: click 'Init Schema'")
            self._bank_rec_statements = rows
            statement_combo['values'] = [
                f"#{r['statement_id']} — {r['account_name']} ({r['lines']} lines, {r['unmatched']} unmatched)"
                for r in rows
            ]
            if rows and not statement_var.get():
                statement_combo.current(0)
            reload_lines()

        def _selected_statement_id():
            idx = statement_combo.current()
            if 0 <= idx < len(self._bank_rec_statements):
                return self._bank_rec_statements[idx]['statement_id']
            return None

        def reload_lines(*_a):
            for iid in tree.get_children():
                tree.delete(iid)
            sid = _selected_statement_id()
            if sid is None:
                summary_label.config(text="No statement selected")
                return
            from education_system.university_system.modules.domain.finance.bank_rec import list_lines
            try:
                lines = list_lines(sid, status_filter=status_var.get())
            except Exception as e:
                summary_label.config(text=f"⚠ {e}")
                return
            n = 0
            unmatched = 0
            for r in lines:
                amount = float(r['amount'])
                amt_str = f"£{amount:,.2f}"
                match_str = ''
                if r['matched_payment_id']:
                    match_str = f"PAY {r['matched_payment_id']}"
                elif r['matched_refund_id']:
                    match_str = f"REF {r['matched_refund_id']}"
                tag = r['status']
                tree.insert('', 'end', values=(
                    r['line_id'], r['line_no'], r['txn_date'], amt_str,
                    (r['description'] or '')[:70], r['reference'] or '',
                    r['status'], match_str,
                ), tags=(tag,))
                n += 1
                if r['status'] == 'unmatched':
                    unmatched += 1
            tree.tag_configure('unmatched',      background='#fff8e1')
            tree.tag_configure('matched_auto',   background='#e8f5e9')
            tree.tag_configure('matched_manual', background='#e3f2fd')
            tree.tag_configure('discarded',      background='#eeeeee')
            summary_label.config(
                text=f"Statement #{sid}: {n} line(s) shown ({unmatched} unmatched)"
            )

        statement_combo.bind('<<ComboboxSelected>>', reload_lines)
        status_combo.bind('<<ComboboxSelected>>', reload_lines)

        # Stash for action handlers + initial load
        self._bank_rec_reload_lines = reload_lines
        self._bank_rec_reload_statements = reload_statements
        self._bank_rec_statement_var = statement_var
        self._bank_rec_tree = tree
        reload_statements()

    # --- Action handlers (kept as instance methods so they're easier
    #     to override / introspect) ---

    def _bank_rec_init_action(self):
        from education_system.university_system.modules.domain.finance.bank_rec import init_bank_rec
        try:
            init_bank_rec()
            messagebox.showinfo("Bank Rec",
                "Schema initialised. You can now import a CSV statement.")
            if hasattr(self, '_bank_rec_reload_statements'):
                self._bank_rec_reload_statements()
        except Exception as e:
            messagebox.showerror("Init failed", str(e))

    def _bank_rec_import_action(self, reload_statements):
        path = filedialog.askopenfilename(
            title="Import bank statement CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not path:
            return
        from tkinter import simpledialog
        account_name = simpledialog.askstring(
            "Account",
            "Bank account name (e.g. 'Operating Account'):",
        )
        if not account_name:
            return

        from education_system.university_system.modules.domain.finance.bank_rec import import_csv
        from education_system.university_system.infrastructure.shared_context import get_auth
        try:
            auth = get_auth()
            user = (auth.current_user.get('username', 'admin')
                    if auth and getattr(auth, 'current_user', None) else 'admin')
        except Exception:
            user = 'admin'

        result = import_csv(path, account_name=account_name, imported_by=user)
        msg = f"Statement #{result['statement_id']}: imported {result['lines_imported']} line(s)."
        if result['errors']:
            msg += f"\n\nErrors ({len(result['errors'])}):\n" + "\n".join(
                str(e) for e in result['errors'][:8]
            )
            if len(result['errors']) > 8:
                msg += f"\n… and {len(result['errors']) - 8} more."
        messagebox.showinfo("Import complete", msg)
        reload_statements()

    def _bank_rec_automatch_action(self, statement_var, reload_lines):
        from education_system.university_system.modules.domain.finance.bank_rec import auto_match_statement
        # Pull statement_id off the dropdown selection
        idx = -1
        for i, s in enumerate(getattr(self, '_bank_rec_statements', [])):
            if statement_var.get().startswith(f"#{s['statement_id']} "):
                idx = i
                break
        if idx == -1:
            messagebox.showwarning("Auto-match", "Select a statement first.")
            return
        sid = self._bank_rec_statements[idx]['statement_id']
        try:
            summary = auto_match_statement(sid)
        except Exception as e:
            messagebox.showerror("Auto-match failed", str(e))
            return
        msg = (f"Scanned: {summary['scanned']}\n"
               f"Auto-matched: {summary['matched']}\n"
               f"Ambiguous (left for review): {summary['ambiguous']}\n"
               f"Errors: {len(summary['errors'])}")
        messagebox.showinfo("Auto-match complete", msg)
        if hasattr(self, '_bank_rec_reload_statements'):
            self._bank_rec_reload_statements()
        reload_lines()

    def _bank_rec_selected_line(self):
        sel = self._bank_rec_tree.selection()
        if not sel:
            messagebox.showwarning("Bank Rec", "Select a line first.")
            return None
        return self._bank_rec_tree.item(sel[0])['values']

    def _bank_rec_manual_match_action(self, tree, reload_lines):
        values = self._bank_rec_selected_line()
        if values is None:
            return
        line_id = int(values[0])
        amount_str = values[3]  # "£12.34"
        try:
            amount = float(amount_str.replace('£', '').replace(',', ''))
        except ValueError:
            amount = 0.0

        # Ask whether this is a payment or refund match, then for the id
        kind = 'payment' if amount > 0 else 'refund'
        target_id = askinteger(
            "Manual match",
            f"Line amount {amount_str}.\n\n"
            f"Enter {kind}_id to match this line to:",
        )
        if not target_id:
            return

        from education_system.university_system.modules.domain.finance.bank_rec import manual_match
        from education_system.university_system.infrastructure.shared_context import get_auth
        try:
            auth = get_auth()
            user = (auth.current_user.get('username', 'admin')
                    if auth and getattr(auth, 'current_user', None) else 'admin')
        except Exception:
            user = 'admin'
        try:
            kwargs = {'payment_id': target_id} if kind == 'payment' else {'refund_id': target_id}
            manual_match(line_id, by=user, **kwargs)
        except Exception as e:
            messagebox.showerror("Match failed", str(e))
            return
        if hasattr(self, '_bank_rec_reload_statements'):
            self._bank_rec_reload_statements()
        reload_lines()

    def _bank_rec_unmatch_action(self, tree, reload_lines):
        values = self._bank_rec_selected_line()
        if values is None:
            return
        line_id = int(values[0])
        if not messagebox.askyesno("Unmatch", f"Reset line {line_id} to 'unmatched'?"):
            return
        from education_system.university_system.modules.domain.finance.bank_rec import unmatch
        try:
            unmatch(line_id)
        except Exception as e:
            messagebox.showerror("Unmatch failed", str(e))
            return
        if hasattr(self, '_bank_rec_reload_statements'):
            self._bank_rec_reload_statements()
        reload_lines()

    def _bank_rec_discard_action(self, tree, reload_lines):
        values = self._bank_rec_selected_line()
        if values is None:
            return
        line_id = int(values[0])
        from tkinter import simpledialog
        reason = simpledialog.askstring(
            "Discard",
            "Reason (e.g. 'bank fee', 'interest', 'irrelevant'):",
        )
        from education_system.university_system.modules.domain.finance.bank_rec import discard
        from education_system.university_system.infrastructure.shared_context import get_auth
        try:
            auth = get_auth()
            user = (auth.current_user.get('username', 'admin')
                    if auth and getattr(auth, 'current_user', None) else 'admin')
        except Exception:
            user = 'admin'
        try:
            discard(line_id, reason=reason or '', by=user)
        except Exception as e:
            messagebox.showerror("Discard failed", str(e))
            return
        if hasattr(self, '_bank_rec_reload_statements'):
            self._bank_rec_reload_statements()
        reload_lines()
