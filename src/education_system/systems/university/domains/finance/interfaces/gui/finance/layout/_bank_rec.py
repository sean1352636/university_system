"""Bank reconciliation tab. Admin/staff: import a CSV statement, run the
auto-matcher, and clear the unmatched-exception queue with manual matches.

Mirrors the Bank Reconciliation CLI (``finance/interfaces/cli/bank_rec/``):
a statements list on top, the selected statement's lines (with match status)
below, and the match / unmatch / discard actions acting on the selected line.
Everything goes through the service in ``finance.domain.bank_rec``.
"""

from education_system.systems.university.infrastructure.i18n import get_text as _t

import tkinter as tk
from tkinter import ttk, filedialog
from tkinter.simpledialog import askinteger, askstring

from education_system.platform.delivery.gui.parented_dialogs import messagebox
from education_system.systems.university.infrastructure.i18n import get_text as _

STATEMENT_COLUMNS = ('statement_id', 'account_name', 'period_start', 'period_end',
                     'lines', 'unmatched', 'imported_by', 'imported_at', 'source_file')
STATEMENT_HEADINGS = {'statement_id': 'ID', 'account_name': 'Account',
                      'period_start': 'Period start', 'period_end': 'Period end',
                      'lines': 'Lines', 'unmatched': 'Unmatched',
                      'imported_by': 'Imported by', 'imported_at': 'Imported at',
                      'source_file': 'Source file'}
STATEMENT_WIDTHS = {'statement_id': 50, 'account_name': 160, 'period_start': 100,
                    'period_end': 100, 'lines': 60, 'unmatched': 80,
                    'imported_by': 110, 'imported_at': 140, 'source_file': 220}

LINE_COLUMNS = ('LineID', 'No', 'Date', 'Amount', 'Description', 'Reference',
                'Status', 'Match', 'MatchedBy')
LINE_WIDTHS = {'LineID': 60, 'No': 40, 'Date': 100, 'Amount': 100,
               'Description': 260, 'Reference': 140, 'Status': 110,
               'Match': 100, 'MatchedBy': 100}
LINE_ANCHORS = {'LineID': 'center', 'No': 'center', 'Date': 'center',
                'Amount': 'e', 'Description': 'w', 'Reference': 'w',
                'Status': 'center', 'Match': 'center', 'MatchedBy': 'center'}
STATUS_FILTERS = ('all', 'unmatched', 'matched_auto', 'matched_manual', 'discarded')
STATUS_COLOURS = {'unmatched': '#fff8e1', 'matched_auto': '#e8f5e9',
                  'matched_manual': '#e3f2fd', 'discarded': '#eeeeee'}


def _current_username():
    from education_system.systems.university.infrastructure.shared_context import get_auth
    try:
        auth = get_auth()
        user = getattr(auth, 'current_user', None) if auth else None
        if isinstance(user, dict):
            return user.get('username') or user.get('name') or 'admin'
    except Exception:
        pass
    return 'admin'


def _scrolled_tree(parent, columns, height):
    tree = ttk.Treeview(parent, columns=columns, show='headings', height=height,
                        selectmode='browse')
    vsb = ttk.Scrollbar(parent, orient='vertical', command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)
    tree.grid(row=0, column=0, sticky='nsew')
    vsb.grid(row=0, column=1, sticky='ns')
    parent.grid_rowconfigure(0, weight=1)
    parent.grid_columnconfigure(0, weight=1)
    return tree


def _match_label(line):
    if line['matched_payment_id']:
        return f"PAY {line['matched_payment_id']}"
    if line['matched_refund_id']:
        return f"REF {line['matched_refund_id']}"
    return ''


class BankRecMixin:
    """🏦 Bank Rec tab — statement list + match queue."""

    def create_bank_rec_tab(self):
        frame = tk.Frame(self.content_frame, bg='white')
        self.tab_frames['bank_rec'] = frame

        toolbar = ttk.Frame(frame)
        toolbar.pack(fill='x', padx=10, pady=10)
        ttk.Label(
            toolbar,
            text=_("finance_gui.bank_rec.title", default="🏦 Bank Reconciliation"),
            font=('Arial', 14, 'bold'),
        ).pack(side='left')

        ttk.Button(toolbar, text=_("finance_gui.bank_rec.init", default="Init Schema"),
                   command=self._bank_rec_init_action).pack(side='right', padx=5)
        ttk.Button(toolbar, text=_("finance_gui.bank_rec.import", default="Import CSV…"),
                   command=lambda: self._bank_rec_import_action(self._bank_rec_reload_statements)
                   ).pack(side='right', padx=5)
        ttk.Button(toolbar, text=_("finance_gui.bank_rec.auto_match", default="Auto-match"),
                   command=lambda: self._bank_rec_automatch_action(
                       self._bank_rec_selected_statement_id, self._bank_rec_reload_lines)
                   ).pack(side='right', padx=5)
        ttk.Button(toolbar, text=_("common.refresh", default="Refresh"),
                   command=lambda: self._bank_rec_reload_statements()).pack(side='right', padx=5)

        paned = ttk.PanedWindow(frame, orient='vertical')
        paned.pack(fill='both', expand=True, padx=10, pady=(0, 10))

        stmts_box = ttk.LabelFrame(
            paned, text=_("finance_gui.bank_rec.statements", default="Imported statements"))
        paned.add(stmts_box, weight=1)
        stmt_tree = _scrolled_tree(stmts_box, STATEMENT_COLUMNS, height=6)
        for c in STATEMENT_COLUMNS:
            stmt_tree.heading(c, text=STATEMENT_HEADINGS[c])
            stmt_tree.column(c, width=STATEMENT_WIDTHS[c],
                             anchor='w' if c in ('account_name', 'source_file') else 'center')

        lines_box = ttk.LabelFrame(
            paned, text=_("finance_gui.bank_rec.lines", default="Statement lines"))
        paned.add(lines_box, weight=3)

        # Action bars first so they keep their space when the table expands.
        bottom = ttk.Frame(lines_box)
        bottom.pack(fill='x', padx=5, pady=5, side='bottom')
        summary_label = ttk.Label(bottom, text="—", font=('Arial', 10, 'bold'))
        summary_label.pack(side='left')
        for label_key, default, handler in (
            ("finance_gui.bank_rec.manual_match", "Manual match…", self._bank_rec_manual_match_action),
            ("finance_gui.bank_rec.discard", "Discard", self._bank_rec_discard_action),
            ("finance_gui.bank_rec.unmatch", "Unmatch", self._bank_rec_unmatch_action),
        ):
            ttk.Button(bottom, text=_(label_key, default=default),
                       command=lambda h=handler: h(self._bank_rec_tree, self._bank_rec_reload_lines)
                       ).pack(side='right', padx=5)

        filter_bar = ttk.Frame(lines_box)
        filter_bar.pack(fill='x', padx=5, pady=(5, 0))
        ttk.Label(filter_bar, text=_("finance_gui.bank_rec.status_filter", default="Status:")
                  ).pack(side='left', padx=(0, 5))
        status_var = tk.StringVar(value='unmatched')
        status_combo = ttk.Combobox(filter_bar, textvariable=status_var, width=14,
                                    state='readonly', values=STATUS_FILTERS)
        status_combo.pack(side='left')

        table_frame = ttk.Frame(lines_box)
        table_frame.pack(fill='both', expand=True, padx=5, pady=5)
        tree = _scrolled_tree(table_frame, LINE_COLUMNS, height=14)
        for c in LINE_COLUMNS:
            tree.heading(c, text=c)
            tree.column(c, width=LINE_WIDTHS[c], anchor=LINE_ANCHORS[c])
        for status, colour in STATUS_COLOURS.items():
            tree.tag_configure(status, background=colour)

        self._bank_rec_statements = []
        self._bank_rec_statement_tree = stmt_tree
        self._bank_rec_tree = tree
        self._bank_rec_status_var = status_var
        self._bank_rec_summary_label = summary_label

        stmt_tree.bind('<<TreeviewSelect>>', lambda _e: self._bank_rec_reload_lines())
        status_combo.bind('<<ComboboxSelected>>', lambda _e: self._bank_rec_reload_lines())

        self._bank_rec_reload_statements()

    # --- loading ---

    def _bank_rec_reload_statements(self):
        from education_system.systems.university.domains.finance.domain.bank_rec import list_statements
        stmt_tree = self._bank_rec_statement_tree
        previous = self._bank_rec_selected_statement_id()
        stmt_tree.delete(*stmt_tree.get_children())
        try:
            rows = list_statements()
        except Exception:
            rows = []
            self._bank_rec_summary_label.config(text=_t(
                'gui.finance.finance.layout.bank_rec.text.schema_not_initialised_click_init_schema',
                default="⚠ schema not initialised: click 'Init Schema'"))
        self._bank_rec_statements = rows
        for r in rows:
            values = [r.get(c) if r.get(c) is not None else '' for c in STATEMENT_COLUMNS]
            values[7] = str(values[7])[:19]
            stmt_tree.insert('', 'end', iid=str(r['statement_id']), values=values)
        if rows:
            ids = {r['statement_id'] for r in rows}
            keep = str(previous) if previous in ids else str(rows[0]['statement_id'])
            stmt_tree.selection_set(keep)
            stmt_tree.focus(keep)
        self._bank_rec_reload_lines()

    def _bank_rec_selected_statement_id(self):
        stmt_tree = getattr(self, '_bank_rec_statement_tree', None)
        if stmt_tree is None:
            return None
        sel = stmt_tree.selection()
        if not sel:
            return None
        try:
            return int(sel[0])
        except ValueError:
            return None

    def _bank_rec_reload_lines(self):
        tree = self._bank_rec_tree
        tree.delete(*tree.get_children())
        sid = self._bank_rec_selected_statement_id()
        if sid is None:
            self._bank_rec_summary_label.config(text=_t(
                'gui.finance.finance.layout.bank_rec.text.no_statement_selected',
                default="No statement selected"))
            return
        from education_system.systems.university.domains.finance.domain.bank_rec import list_lines
        try:
            lines = list_lines(sid, status_filter=self._bank_rec_status_var.get())
        except Exception as e:
            self._bank_rec_summary_label.config(text=f"⚠ {e}")
            return
        unmatched = 0
        for r in lines:
            tree.insert('', 'end', iid=str(r['line_id']), values=(
                r['line_id'], r['line_no'], r['txn_date'], f"£{float(r['amount']):,.2f}",
                (r['description'] or '')[:70], r['reference'] or '',
                r['status'], _match_label(r), r['matched_by'] or '',
            ), tags=(r['status'],))
            if r['status'] == 'unmatched':
                unmatched += 1
        self._bank_rec_summary_label.config(
            text=f"Statement #{sid}: {len(lines)} line(s) shown ({unmatched} unmatched)")

    def _bank_rec_refresh_all(self):
        if hasattr(self, '_bank_rec_statement_tree'):
            self._bank_rec_reload_statements()

    # --- Action handlers (kept as instance methods so they're easier
    #     to override / introspect) ---

    def _bank_rec_init_action(self):
        from education_system.systems.university.domains.finance.domain.bank_rec import init_bank_rec
        try:
            init_bank_rec()
            messagebox.showinfo(
                _t('gui.finance.finance.layout.bank_rec.dialogs.bank_rec', default="Bank Rec"),
                _t('gui.finance.finance.layout.bank_rec.dialogs.schema_initialised_you_can_now_import_a_csv_statement',
                   default="Schema initialised. You can now import a CSV statement."))
            self._bank_rec_refresh_all()
        except Exception as e:
            messagebox.showerror(
                _t('gui.finance.finance.layout.bank_rec.dialogs.init_failed', default="Init failed"),
                str(e))

    def _bank_rec_import_action(self, reload_statements):
        path = filedialog.askopenfilename(
            title=_t('gui.finance.finance.layout.bank_rec.dialogs.import_bank_statement_csv',
                     default="Import bank statement CSV"),
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not path:
            return
        from education_system.platform.delivery.gui.form_dialog import Field, ask_form
        values = ask_form(self.root, _t(
            'gui.finance.finance.layout.bank_rec.dialogs.import_bank_statement_csv',
            default="Import bank statement CSV"), [
            Field('account_name', _t('gui.finance.finance.layout.bank_rec.dialogs.account',
                                     default="Bank account name (e.g. 'Operating Account')")),
            Field('period_start', "Period start (YYYY-MM-DD, optional)", optional=True),
            Field('period_end', "Period end (YYYY-MM-DD, optional)", optional=True),
            Field('opening_balance', "Opening balance (optional)", kind='float', optional=True),
            Field('closing_balance', "Closing balance (optional)", kind='float', optional=True),
        ])
        if not values:
            return

        from education_system.systems.university.domains.finance.domain.bank_rec import import_csv
        try:
            result = import_csv(
                path, account_name=values['account_name'], imported_by=_current_username(),
                period_start=values.get('period_start') or None,
                period_end=values.get('period_end') or None,
                opening_balance=values.get('opening_balance'),
                closing_balance=values.get('closing_balance'))
        except Exception as e:
            messagebox.showerror(
                _t('gui.finance.finance.layout.bank_rec.dialogs.import_failed', default="Import failed"),
                str(e))
            return
        msg = f"Statement #{result['statement_id']}: imported {result['lines_imported']} line(s)."
        if result['errors']:
            msg += f"\n\nErrors ({len(result['errors'])}):\n" + "\n".join(
                str(e) for e in result['errors'][:8])
            if len(result['errors']) > 8:
                msg += f"\n… and {len(result['errors']) - 8} more."
        messagebox.showinfo(
            _t('gui.finance.finance.layout.bank_rec.dialogs.import_complete', default="Import complete"),
            msg)
        reload_statements()

    def _bank_rec_automatch_action(self, selected_statement_id, reload_lines):
        from education_system.systems.university.domains.finance.domain.bank_rec import auto_match_statement
        sid = selected_statement_id()
        if sid is None:
            messagebox.showwarning(
                _t('gui.finance.finance.layout.bank_rec.dialogs.auto_match', default="Auto-match"),
                _t('gui.finance.finance.layout.bank_rec.dialogs.select_a_statement_first',
                   default="Select a statement first."))
            return
        try:
            summary = auto_match_statement(sid)
        except Exception as e:
            messagebox.showerror(
                _t('gui.finance.finance.layout.bank_rec.dialogs.auto_match_failed',
                   default="Auto-match failed"), str(e))
            return
        msg = (f"Scanned: {summary['scanned']}\n"
               f"Auto-matched: {summary['matched']}\n"
               f"Ambiguous (left for review): {summary['ambiguous']}\n"
               f"Errors: {len(summary['errors'])}")
        messagebox.showinfo(
            _t('gui.finance.finance.layout.bank_rec.dialogs.auto_match_complete',
               default="Auto-match complete"), msg)
        self._bank_rec_refresh_all()
        reload_lines()

    def _bank_rec_selected_line(self):
        sel = self._bank_rec_tree.selection()
        if not sel:
            messagebox.showwarning(
                _t('gui.finance.finance.layout.bank_rec.dialogs.bank_rec', default="Bank Rec"),
                _t('gui.finance.finance.layout.bank_rec.dialogs.select_a_line_first',
                   default="Select a line first."))
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
            parent=self.root,
        )
        if not target_id:
            return

        from education_system.systems.university.domains.finance.domain.bank_rec import manual_match
        try:
            kwargs = {'payment_id': target_id} if kind == 'payment' else {'refund_id': target_id}
            manual_match(line_id, by=_current_username(), **kwargs)
        except Exception as e:
            messagebox.showerror(
                _t('gui.finance.finance.layout.bank_rec.dialogs.match_failed', default="Match failed"),
                str(e))
            return
        self._bank_rec_refresh_all()
        reload_lines()

    def _bank_rec_unmatch_action(self, tree, reload_lines):
        values = self._bank_rec_selected_line()
        if values is None:
            return
        line_id = int(values[0])
        if not messagebox.askyesno(
                _t('gui.finance.finance.layout.bank_rec.dialogs.unmatch', default="Unmatch"),
                f"Reset line {line_id} to 'unmatched'?"):
            return
        from education_system.systems.university.domains.finance.domain.bank_rec import unmatch
        try:
            unmatch(line_id)
        except Exception as e:
            messagebox.showerror(
                _t('gui.finance.finance.layout.bank_rec.dialogs.unmatch_failed', default="Unmatch failed"),
                str(e))
            return
        self._bank_rec_refresh_all()
        reload_lines()

    def _bank_rec_discard_action(self, tree, reload_lines):
        values = self._bank_rec_selected_line()
        if values is None:
            return
        line_id = int(values[0])
        reason = askstring(
            _t('gui.finance.finance.layout.bank_rec.dialogs.discard', default="Discard"),
            _t('gui.finance.finance.layout.bank_rec.dialogs.reason_e_g_bank_fee_interest_irrelevant',
               default="Reason (e.g. 'bank fee', 'interest', 'irrelevant'):"),
            parent=self.root,
        )
        if reason is None:
            return
        from education_system.systems.university.domains.finance.domain.bank_rec import discard
        try:
            discard(line_id, reason=reason or '', by=_current_username())
        except Exception as e:
            messagebox.showerror(
                _t('gui.finance.finance.layout.bank_rec.dialogs.discard_failed', default="Discard failed"),
                str(e))
            return
        self._bank_rec_refresh_all()
        reload_lines()
