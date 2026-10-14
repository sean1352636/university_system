"""Periodic student statement runs tab.

Mirrors the Student Statement Runs CLI
(``finance/interfaces/cli/statements/``): initialise the schema, generate a
run for a period, list runs, list the statements in a run, and view one
student's statement. Everything goes through the service in
``finance.domain.statements``; this module only draws it.
"""

from education_system.systems.university.infrastructure.i18n import get_text as _t

import tkinter as tk
from tkinter import ttk
from datetime import date

from education_system.platform.delivery.gui.parented_dialogs import messagebox
from education_system.systems.university.infrastructure.i18n import get_text as _

RUN_COLUMNS = ('run_id', 'period_start', 'period_end', 'total_students',
               'total_with_balance', 'generated_by', 'generated_at', 'status')
RUN_HEADINGS = {'run_id': 'Run', 'period_start': 'Period start',
                'period_end': 'Period end', 'total_students': 'Students',
                'total_with_balance': 'With balance', 'generated_by': 'By',
                'generated_at': 'Generated', 'status': 'Status'}
RUN_WIDTHS = {'run_id': 60, 'period_start': 110, 'period_end': 110,
              'total_students': 80, 'total_with_balance': 100,
              'generated_by': 110, 'generated_at': 150, 'status': 90}

STATEMENT_COLUMNS = ('StatementID', 'Student', 'Opening', 'Charges',
                     'Payments', 'Refunds', 'Closing')
STATEMENT_WIDTHS = {'StatementID': 80, 'Student': 140, 'Opening': 110,
                    'Charges': 110, 'Payments': 110, 'Refunds': 100,
                    'Closing': 130}
STATEMENT_ANCHORS = {'StatementID': 'center', 'Student': 'w', 'Opening': 'e',
                     'Charges': 'e', 'Payments': 'e', 'Refunds': 'e',
                     'Closing': 'e'}

# The fields the CLI's "view one student's statement" prints, in its order.
STATEMENT_DETAIL_FIELDS = (
    ('period_start', 'Period start'), ('period_end', 'Period end'),
    ('opening_balance', 'Opening balance'), ('charges_in_period', 'Charges in period'),
    ('payments_in_period', 'Payments in period'), ('refunds_in_period', 'Refunds in period'),
    ('closing_balance', 'Closing balance'),
)


def _money(value):
    return f"£{float(value or 0):,.2f}"


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
    """A headings-only Treeview with a vertical scrollbar, gridded into *parent*."""
    tree = ttk.Treeview(parent, columns=columns, show='headings', height=height,
                        selectmode='browse')
    vsb = ttk.Scrollbar(parent, orient='vertical', command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)
    tree.grid(row=0, column=0, sticky='nsew')
    vsb.grid(row=0, column=1, sticky='ns')
    parent.grid_rowconfigure(0, weight=1)
    parent.grid_columnconfigure(0, weight=1)
    return tree


class StatementsMixin:
    """📑 Statements tab — batch month-end statement generator."""

    def create_statements_tab(self):
        frame = tk.Frame(self.content_frame, bg='white')
        self.tab_frames['statements'] = frame

        toolbar = ttk.Frame(frame)
        toolbar.pack(fill='x', padx=10, pady=10)
        ttk.Label(
            toolbar,
            text=_("finance_gui.statements.title", default="📑 Student Statements"),
            font=('Arial', 14, 'bold'),
        ).pack(side='left')

        only_balance_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            toolbar,
            text=_("finance_gui.statements.only_with_balance", default="Only outstanding"),
            variable=only_balance_var,
            command=lambda: self._statements_reload_lines(),
        ).pack(side='left', padx=20)

        ttk.Button(toolbar, text=_("finance_gui.statements.init", default="Init Schema"),
                   command=self._statements_init_action).pack(side='right', padx=5)
        ttk.Button(toolbar, text=_("finance_gui.statements.run_now",
                                   default="Run Statements…"),
                   command=lambda: self._statements_run_action(self._statements_reload_runs)
                   ).pack(side='right', padx=5)
        ttk.Button(toolbar, text=_("common.refresh", default="Refresh"),
                   command=lambda: self._statements_reload_runs()).pack(side='right', padx=5)

        paned = ttk.PanedWindow(frame, orient='vertical')
        paned.pack(fill='both', expand=True, padx=10, pady=(0, 10))

        runs_box = ttk.LabelFrame(
            paned, text=_("finance_gui.statements.runs", default="Statement runs"))
        paned.add(runs_box, weight=1)
        runs_tree = _scrolled_tree(runs_box, RUN_COLUMNS, height=7)
        for c in RUN_COLUMNS:
            runs_tree.heading(c, text=RUN_HEADINGS[c])
            runs_tree.column(c, width=RUN_WIDTHS[c], anchor='center')

        stmts_box = ttk.LabelFrame(
            paned, text=_("finance_gui.statements.statements_in_run",
                          default="Statements in selected run"))
        paned.add(stmts_box, weight=3)

        # Action bar first so it keeps its space when the table expands.
        actions = ttk.Frame(stmts_box)
        actions.pack(fill='x', padx=5, pady=5, side='bottom')
        summary_label = ttk.Label(actions, text="—", font=('Arial', 10, 'bold'))
        summary_label.pack(side='left')
        ttk.Button(actions, text=_("finance_gui.statements.view", default="View statement…"),
                   command=lambda: self._statements_view_action()).pack(side='right', padx=5)

        table_frame = ttk.Frame(stmts_box)
        table_frame.pack(fill='both', expand=True, padx=5, pady=5)
        tree = _scrolled_tree(table_frame, STATEMENT_COLUMNS, height=14)
        for c in STATEMENT_COLUMNS:
            tree.heading(c, text=c)
            tree.column(c, width=STATEMENT_WIDTHS[c], anchor=STATEMENT_ANCHORS[c])
        tree.tag_configure('outstanding', background='#fff8e1')
        tree.tag_configure('clear', background='white')

        self._statements_runs = []
        self._statements_runs_tree = runs_tree
        self._statements_tree = tree
        self._statements_only_balance_var = only_balance_var
        self._statements_summary_label = summary_label

        runs_tree.bind('<<TreeviewSelect>>', lambda _e: self._statements_reload_lines())
        tree.bind('<Double-1>', lambda _e: self._statements_view_action())

        self._statements_reload_runs()

    # --- loading ---

    def _statements_reload_runs(self):
        from education_system.systems.university.domains.finance.domain.statements import list_runs
        runs_tree = self._statements_runs_tree
        previous = self._statements_selected_run_id()
        runs_tree.delete(*runs_tree.get_children())
        try:
            runs = list_runs()
        except Exception:
            runs = []
            self._statements_summary_label.config(text=_t(
                'gui.finance.finance.layout.statements.text.schema_not_initialised_click_init_schema',
                default="⚠ schema not initialised: click 'Init Schema'"))
        self._statements_runs = runs
        for r in runs:
            values = [r.get(c) if r.get(c) is not None else '' for c in RUN_COLUMNS]
            values[1] = values[1] or '(beginning)'
            values[6] = str(values[6])[:19]
            runs_tree.insert('', 'end', iid=str(r['run_id']), values=values)
        if runs:
            keep = str(previous) if previous in {r['run_id'] for r in runs} else str(runs[0]['run_id'])
            runs_tree.selection_set(keep)
            runs_tree.focus(keep)
        self._statements_reload_lines()

    def _statements_selected_run_id(self):
        runs_tree = getattr(self, '_statements_runs_tree', None)
        if runs_tree is None:
            return None
        sel = runs_tree.selection()
        if not sel:
            return None
        try:
            return int(sel[0])
        except ValueError:
            return None

    def _statements_reload_lines(self):
        tree = self._statements_tree
        tree.delete(*tree.get_children())
        rid = self._statements_selected_run_id()
        if rid is None:
            self._statements_summary_label.config(text=_t(
                'gui.finance.finance.layout.statements.text.no_run_selected',
                default="No run selected"))
            return
        from education_system.systems.university.domains.finance.domain.statements import list_statements
        try:
            stmts = list_statements(rid, only_with_balance=self._statements_only_balance_var.get())
        except Exception as e:
            self._statements_summary_label.config(text=f"⚠ {e}")
            return
        total_outstanding = 0.0
        for s in stmts:
            closing = float(s['closing_balance'] or 0)
            outstanding = abs(closing) >= 0.01
            tree.insert('', 'end', iid=str(s['statement_id']), values=(
                s['statement_id'], s['student_id'],
                _money(s['opening_balance']), _money(s['charges_in_period']),
                _money(s['payments_in_period']), _money(s['refunds_in_period']),
                _money(closing),
            ), tags=('outstanding' if outstanding else 'clear',))
            if outstanding:
                total_outstanding += closing
        self._statements_summary_label.config(
            text=f"Run #{rid}: {len(stmts)} statement(s) shown • "
                 f"Total outstanding: £{total_outstanding:,.2f}"
        )

    # --- actions ---

    def _statements_init_action(self):
        from education_system.systems.university.domains.finance.domain.statements import init_statements
        try:
            init_statements()
            messagebox.showinfo(
                _t('gui.finance.finance.layout.statements.dialogs.statements', default="Statements"),
                _t('gui.finance.finance.layout.statements.dialogs.schema_initialised_you_can_now_run_statements',
                   default="Schema initialised. You can now run statements."))
            if hasattr(self, '_statements_runs_tree'):
                self._statements_reload_runs()
        except Exception as e:
            messagebox.showerror(
                _t('gui.finance.finance.layout.statements.dialogs.init_failed', default="Init failed"),
                str(e))

    def _statements_run_action(self, reload_runs):
        """Ask for the run parameters the CLI prompts for, then generate the run."""
        from education_system.platform.delivery.gui.form_dialog import Field, ask_form
        values = ask_form(self.root, _t(
            'gui.finance.finance.layout.statements.dialogs.run_statements',
            default="Run statements"), [
            Field('period_end', _t('gui.finance.finance.layout.statements.dialogs.period_end',
                                   default="Period end (YYYY-MM-DD)"),
                  default=date.today().isoformat()),
            Field('period_start', _t('gui.finance.finance.layout.statements.dialogs.period_start',
                                     default="Period start (YYYY-MM-DD, blank = beginning of time)"),
                  optional=True),
        ])
        if not values:
            return

        from education_system.systems.university.domains.finance.domain.statements import run_statements_batch
        try:
            result = run_statements_batch(
                values['period_end'], generated_by=_current_username(),
                period_start=values.get('period_start') or None,
            )
        except Exception as e:
            messagebox.showerror(
                _t('gui.finance.finance.layout.statements.dialogs.run_failed', default="Run failed"),
                str(e))
            return

        messagebox.showinfo(
            _t('gui.finance.finance.layout.statements.dialogs.run_complete', default="Run complete"),
            f"Run #{result['run_id']}\n"
            f"Statements generated: {result['total_students']}\n"
            f"With outstanding balance: {result['total_with_balance']}"
        )
        reload_runs()

    def _statements_view_action(self):
        """Open the detail dialog for the selected statement (CLI option 5)."""
        rid = self._statements_selected_run_id()
        sel = self._statements_tree.selection()
        if rid is None or not sel:
            messagebox.showwarning(
                _t('gui.finance.finance.layout.statements.dialogs.statements', default="Statements"),
                _t('gui.finance.finance.layout.statements.dialogs.select_a_statement_first',
                   default="Select a statement first."))
            return
        student_id = self._statements_tree.item(sel[0])['values'][1]
        from education_system.systems.university.domains.finance.domain.statements import get_statement
        try:
            stmt = get_statement(rid, student_id)
        except Exception as e:
            messagebox.showerror(
                _t('gui.finance.finance.layout.statements.dialogs.view_failed', default="View failed"),
                str(e))
            return
        if not stmt:
            messagebox.showinfo(
                _t('gui.finance.finance.layout.statements.dialogs.statements', default="Statements"),
                f"No statement for student {student_id} in run {rid}.")
            return
        self._statements_show_detail(stmt)

    def _statements_show_detail(self, stmt):
        from education_system.platform.delivery.gui.parented_dialogs import make_toplevel
        win = make_toplevel(self.root)
        win.title(f"Statement #{stmt['statement_id']} — run {stmt['run_id']}, "
                  f"student {stmt['student_id']}")
        win.resizable(False, False)
        body = ttk.Frame(win, padding=15)
        body.pack(fill='both', expand=True)
        ttk.Label(body, text=f"Student {stmt['student_id']}  •  Run #{stmt['run_id']}",
                  font=('Arial', 12, 'bold')).grid(row=0, column=0, columnspan=2,
                                                   sticky='w', pady=(0, 10))
        for row, (key, label) in enumerate(STATEMENT_DETAIL_FIELDS, start=1):
            value = stmt.get(key)
            if value is None:
                text = '-'
            elif key.startswith('period'):
                text = str(value)
            else:
                text = _money(value)
            ttk.Label(body, text=label + ':').grid(row=row, column=0, sticky='e', padx=(0, 10), pady=2)
            weight = 'bold' if key == 'closing_balance' else 'normal'
            ttk.Label(body, text=text, font=('Arial', 10, weight)).grid(row=row, column=1, sticky='w', pady=2)
        ttk.Button(body, text=_("common.close", default="Close"), command=win.destroy).grid(
            row=len(STATEMENT_DETAIL_FIELDS) + 1, column=0, columnspan=2, pady=(12, 0))
        win.bind('<Escape>', lambda _e: win.destroy())
        win.grab_set()
