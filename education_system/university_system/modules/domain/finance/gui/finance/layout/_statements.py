"""Periodic student statement runs tab."""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import date

from education_system.university_system.core.i18n import get_text as _


class StatementsMixin:
    """📑 Statements tab — batch month-end statement generator."""

    def create_statements_tab(self):
        frame = tk.Frame(self.content_frame, bg='white')
        self.tab_frames['statements'] = frame

        # Toolbar
        toolbar = ttk.Frame(frame)
        toolbar.pack(fill='x', padx=10, pady=10)
        ttk.Label(
            toolbar,
            text=_("finance_gui.statements.title", default="📑 Student Statements"),
            font=('Arial', 14, 'bold'),
        ).pack(side='left')

        # Run selector
        ttk.Label(toolbar, text=_("finance_gui.statements.run", default="Run:")
                  ).pack(side='left', padx=(20, 5))
        run_var = tk.StringVar()
        run_combo = ttk.Combobox(toolbar, textvariable=run_var, width=42, state='readonly')
        run_combo.pack(side='left', padx=5)

        # Filter: only-with-balance
        only_balance_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            toolbar,
            text=_("finance_gui.statements.only_with_balance", default="Only outstanding"),
            variable=only_balance_var,
            command=lambda: reload_lines(),
        ).pack(side='left', padx=20)

        # Right side actions
        ttk.Button(toolbar, text=_("finance_gui.statements.init",
                                    default="Init Schema"),
                   command=self._statements_init_action).pack(side='right', padx=5)
        ttk.Button(toolbar, text=_("finance_gui.statements.run_now",
                                    default="Run Statements…"),
                   command=lambda: self._statements_run_action(reload_runs)
                   ).pack(side='right', padx=5)

        # Table
        table_frame = ttk.Frame(frame)
        table_frame.pack(fill='both', expand=True, padx=10, pady=10)
        columns = ('StatementID', 'Student', 'Opening',
                   'Charges', 'Payments', 'Refunds', 'Closing')
        tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=22)
        widths = {'StatementID': 80, 'Student': 140, 'Opening': 110,
                  'Charges': 110, 'Payments': 110, 'Refunds': 100, 'Closing': 130}
        anchors = {'StatementID': 'center', 'Student': 'w',
                   'Opening': 'e', 'Charges': 'e', 'Payments': 'e',
                   'Refunds': 'e', 'Closing': 'e'}
        for c in columns:
            tree.heading(c, text=c)
            tree.column(c, width=widths[c], anchor=anchors[c])
        vsb = ttk.Scrollbar(table_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        # Bottom: summary
        summary = ttk.Frame(frame)
        summary.pack(fill='x', padx=10, pady=5)
        summary_label = ttk.Label(summary, text="—", font=('Arial', 10, 'bold'))
        summary_label.pack(side='left')
        ttk.Button(summary, text=_("common.refresh", default="Refresh"),
                   command=lambda: reload_lines()).pack(side='right', padx=5)

        self._statements_runs = []

        def reload_runs():
            from education_system.university_system.modules.domain.finance.statements import list_runs
            try:
                runs = list_runs()
            except Exception:
                runs = []
                summary_label.config(text="⚠ schema not initialised: click 'Init Schema'")
            self._statements_runs = runs
            run_combo['values'] = [
                f"#{r['run_id']} — period end {r['period_end']} "
                f"({r['total_students']} students, {r['total_with_balance']} outstanding)"
                for r in runs
            ]
            if runs and not run_var.get():
                run_combo.current(0)
            reload_lines()

        def _selected_run_id():
            idx = run_combo.current()
            if 0 <= idx < len(self._statements_runs):
                return self._statements_runs[idx]['run_id']
            return None

        def reload_lines(*_a):
            for iid in tree.get_children():
                tree.delete(iid)
            rid = _selected_run_id()
            if rid is None:
                summary_label.config(text="No run selected")
                return
            from education_system.university_system.modules.domain.finance.statements import list_statements
            try:
                stmts = list_statements(rid, only_with_balance=only_balance_var.get())
            except Exception as e:
                summary_label.config(text=f"⚠ {e}")
                return
            total_outstanding = 0.0
            for s in stmts:
                closing = float(s['closing_balance'])
                tag = 'outstanding' if abs(closing) >= 0.01 else 'clear'
                tree.insert('', 'end', values=(
                    s['statement_id'], s['student_id'],
                    f"£{s['opening_balance']:,.2f}",
                    f"£{s['charges_in_period']:,.2f}",
                    f"£{s['payments_in_period']:,.2f}",
                    f"£{s['refunds_in_period']:,.2f}",
                    f"£{closing:,.2f}",
                ), tags=(tag,))
                if abs(closing) >= 0.01:
                    total_outstanding += closing
            tree.tag_configure('outstanding', background='#fff8e1')
            tree.tag_configure('clear', background='white')
            summary_label.config(
                text=f"Run #{rid}: {len(stmts)} statement(s) shown • "
                     f"Total outstanding: £{total_outstanding:,.2f}"
            )

        run_combo.bind('<<ComboboxSelected>>', reload_lines)

        self._statements_reload_runs = reload_runs
        reload_runs()

    # --- actions ---

    def _statements_init_action(self):
        from education_system.university_system.modules.domain.finance.statements import init_statements
        try:
            init_statements()
            messagebox.showinfo("Statements",
                                "Schema initialised. You can now run statements.")
            if hasattr(self, '_statements_reload_runs'):
                self._statements_reload_runs()
        except Exception as e:
            messagebox.showerror("Init failed", str(e))

    def _statements_run_action(self, reload_runs):
        # Default period_end = today
        today = date.today().isoformat()
        period_end = simpledialog.askstring(
            "Run statements",
            "Period end date (YYYY-MM-DD):",
            initialvalue=today,
        )
        if not period_end:
            return
        period_start = simpledialog.askstring(
            "Run statements",
            "Period start date (YYYY-MM-DD)\n(blank = beginning of time):",
            initialvalue='',
        )

        from education_system.university_system.modules.domain.finance.statements import run_statements_batch
        from education_system.university_system.infrastructure.shared_context import get_auth
        try:
            auth = get_auth()
            user = (auth.current_user.get('username', 'admin')
                    if auth and getattr(auth, 'current_user', None) else 'admin')
        except Exception:
            user = 'admin'

        try:
            result = run_statements_batch(
                period_end, generated_by=user,
                period_start=period_start or None,
            )
        except Exception as e:
            messagebox.showerror("Run failed", str(e))
            return

        messagebox.showinfo(
            "Run complete",
            f"Run #{result['run_id']}\n"
            f"Statements generated: {result['total_students']}\n"
            f"With outstanding balance: {result['total_with_balance']}"
        )
        reload_runs()
