"""Audit report by date range — the GUI face of CLI core menu option 21.

``generate_audit_report(start, end)`` in
``finance.domain.reporting.revenue_analytics.reports`` prints a fixed-width
report and offers a CSV export. This dialog renders the same text (via
``format_audit_report``) into a text pane and writes the same CSV (via
``export_audit_report_csv``) to a path the user picks, so the two interfaces
cannot drift. It hangs off the audit-log dialog in ``compliance.py``.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from tkinter import filedialog, ttk
from tkinter.scrolledtext import ScrolledText
import tkinter as tk

from education_system.platform.delivery.gui.parented_dialogs import make_toplevel, messagebox
from education_system.systems.university.infrastructure.i18n import get_text as _t


def _valid_date(text):
    try:
        datetime.strptime(text, '%Y-%m-%d')
        return True
    except ValueError:
        return False


def open_audit_report_dialog(parent, start_date=None, end_date=None):
    """Open the date-range audit report window above *parent*.

    *start_date*/*end_date* seed the form (``YYYY-MM-DD``); they default to
    the last 30 days. Returns the Toplevel so callers can test or wait on it.
    """
    win = make_toplevel(parent)
    win.title(_t('gui.finance.audit_report.title', default="Audit report"))
    win.geometry("1000x600")

    form = ttk.LabelFrame(win, text=_t('gui.finance.audit_report.range', default="Date range"),
                          padding=10)
    form.pack(fill='x', padx=15, pady=(15, 5))
    start_var = tk.StringVar(
        value=start_date or (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
    end_var = tk.StringVar(value=end_date or datetime.now().strftime('%Y-%m-%d'))
    ttk.Label(form, text=_t('gui.finance.audit_report.start', default="Start date (YYYY-MM-DD):")
              ).grid(row=0, column=0, padx=5, pady=5, sticky='e')
    ttk.Entry(form, textvariable=start_var, width=12).grid(row=0, column=1, padx=5, pady=5)
    ttk.Label(form, text=_t('gui.finance.audit_report.end', default="End date (YYYY-MM-DD):")
              ).grid(row=0, column=2, padx=5, pady=5, sticky='e')
    ttk.Entry(form, textvariable=end_var, width=12).grid(row=0, column=3, padx=5, pady=5)

    state = {'rows': [], 'start': None, 'end': None}

    # Action bar before the expanding text pane so it keeps its space.
    actions = ttk.Frame(win)
    actions.pack(fill='x', padx=15, pady=(5, 15), side='bottom')
    status = ttk.Label(actions, text=_t('gui.finance.audit_report.hint',
                                        default="Choose a range and press Generate."))
    status.pack(side='left')
    ttk.Button(actions, text=_t('common.close', default="Close"), command=win.destroy
               ).pack(side='right')
    export_btn = ttk.Button(actions, text=_t('gui.finance.audit_report.export',
                                             default="Export CSV…"), state='disabled')
    export_btn.pack(side='right', padx=5)

    pane = ScrolledText(win, wrap='none', font=('Courier', 9), state='disabled')
    pane.pack(fill='both', expand=True, padx=15, pady=5)

    def generate():
        start, end = start_var.get().strip(), end_var.get().strip()
        if not (_valid_date(start) and _valid_date(end)):
            messagebox.showwarning(
                _t('gui.finance.audit_report.title', default="Audit report"),
                _t('gui.finance.audit_report.bad_dates', default="Enter both dates as YYYY-MM-DD."),
                parent=win)
            return
        from education_system.systems.university.domains.finance.domain.reporting.revenue_analytics.reports import (
            fetch_audit_entries, format_audit_report,
        )
        try:
            rows = fetch_audit_entries(start, end)
            text = format_audit_report(start, end, rows)
        except Exception as exc:
            messagebox.showerror(
                _t('gui.finance.audit_report.failed', default="Audit report failed"),
                str(exc), parent=win)
            return
        state.update(rows=rows, start=start, end=end)
        pane.configure(state='normal')
        pane.delete('1.0', 'end')
        pane.insert('1.0', text.lstrip('\n'))
        pane.configure(state='disabled')
        status.config(text=f"{len(rows)} audit entr{'y' if len(rows) == 1 else 'ies'} "
                           f"between {start} and {end}")
        export_btn.configure(state='normal' if rows else 'disabled')

    def export():
        if not state['rows']:
            return
        path = filedialog.asksaveasfilename(
            parent=win, defaultextension='.csv',
            initialfile=f"audit_report_{state['start']}_to_{state['end']}.csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not path:
            return
        from education_system.systems.university.domains.finance.domain.reporting.revenue_analytics.reports import (
            export_audit_report_csv,
        )
        try:
            export_audit_report_csv(state['rows'], path)
        except OSError as exc:
            messagebox.showerror(
                _t('gui.finance.audit_report.failed', default="Audit report failed"),
                str(exc), parent=win)
            return
        status.config(text=f"Audit report exported to {path}")

    export_btn.configure(command=export)
    ttk.Button(form, text=_t('gui.finance.audit_report.generate', default="Generate"),
               command=generate).grid(row=0, column=4, padx=10, pady=5)
    win.bind('<Escape>', lambda _e: win.destroy())
    return win


__all__ = ["open_audit_report_dialog"]
