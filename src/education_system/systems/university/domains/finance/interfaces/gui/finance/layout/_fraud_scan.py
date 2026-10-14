"""One-shot payment fraud scan for the Fraud Investigations tab.

The CLI core menu's option 20 calls ``detect_payment_fraud()``; the GUI runs
the same scan through ``scan_payments_for_fraud()`` (the data half of that
function) in a worker thread, because the scan lazily imports scikit-learn
and ``security_automation`` itself drags in flask + cryptography — neither
belongs on the Tk thread or at import time.
"""

from __future__ import annotations

import queue
import threading
from tkinter import ttk

from education_system.platform.delivery.gui.parented_dialogs import make_toplevel, messagebox
from education_system.systems.university.infrastructure.i18n import get_text as _t

RESULT_COLUMNS = ('payment_id', 'student_id', 'name', 'amount', 'payment_method',
                  'payment_date', 'risk')
RESULT_HEADINGS = {'payment_id': 'Payment', 'student_id': 'Student', 'name': 'Name',
                   'amount': 'Amount', 'payment_method': 'Method',
                   'payment_date': 'Date', 'risk': 'Risk'}
RESULT_WIDTHS = {'payment_id': 80, 'student_id': 100, 'name': 180, 'amount': 100,
                 'payment_method': 100, 'payment_date': 110, 'risk': 70}


def _run_scan(auth):
    """Worker-thread body: bind the user for the audit rows, then scan."""
    from education_system.systems.university.domains.finance.domain.core import (
        security_automation,
    )
    if auth is not None:
        security_automation.set_finance_auth(auth)
    return security_automation.scan_payments_for_fraud()


class FraudScanMixin:
    """Adds ``_fraud_run_scan`` to the operations layout mixin."""

    def _fraud_run_scan(self, refresh):
        """Run the scan in a thread with a busy indicator; show the flagged payments."""
        busy = make_toplevel(self.root)
        busy.title(_t('gui.finance.fraud_scan.running', default="Fraud scan"))
        busy.resizable(False, False)
        ttk.Label(busy, text=_t('gui.finance.fraud_scan.running_text',
                                default="Scoring the last 30 days of payments…"),
                  padding=15).pack()
        bar = ttk.Progressbar(busy, mode='indeterminate', length=260)
        bar.pack(padx=15, pady=(0, 15))
        bar.start(12)
        busy.protocol('WM_DELETE_WINDOW', lambda: None)
        busy.grab_set()

        # The worker never touches Tk: it drops its outcome on a queue and the
        # Tk thread polls for it, so no Tcl call ever comes from another thread.
        outcome = queue.Queue(maxsize=1)

        def worker():
            try:
                outcome.put(('result', _run_scan(getattr(self.gui, 'auth', None))))
            except Exception as exc:  # surfaced on the Tk thread below
                outcome.put(('error', exc))

        def poll():
            try:
                kind, payload = outcome.get_nowait()
            except queue.Empty:
                self.root.after(200, poll)
                return
            bar.stop()
            busy.grab_release()
            busy.destroy()
            if kind == 'error':
                messagebox.showerror(
                    _t('gui.finance.fraud_scan.failed', default="Fraud scan failed"),
                    str(payload), parent=self.root)
                return
            self._fraud_show_results(payload, refresh)

        threading.Thread(target=worker, name='finance-fraud-scan', daemon=True).start()
        self.root.after(200, poll)

    def _fraud_show_results(self, result, refresh):
        if result['insufficient']:
            messagebox.showinfo(
                _t('gui.finance.fraud_scan.title', default="Fraud scan"),
                _t('gui.finance.fraud_scan.insufficient',
                   default="Insufficient payment data for fraud detection "
                           "(fewer than 10 completed payments in the last 30 days)."),
                parent=self.root)
            return

        win = make_toplevel(self.root)
        win.title(_t('gui.finance.fraud_scan.title', default="Fraud scan"))
        win.geometry("860x460")
        ttk.Label(
            win, font=('Arial', 11, 'bold'), padding=(10, 10, 10, 0),
            text=f"Payments analysed: {result['analyzed']}   •   "
                 f"Suspicious payments flagged: {result['flagged']}",
        ).pack(anchor='w')
        ttk.Label(win, padding=(10, 0),
                  text=_t('gui.finance.fraud_scan.review',
                          default="Payments currently flagged for manual review "
                                  "(highest risk first):")).pack(anchor='w')

        # Action bar before the expanding table so it keeps its space.
        actions = ttk.Frame(win)
        actions.pack(fill='x', padx=10, pady=8, side='bottom')
        ttk.Button(actions, text=_t('common.close', default="Close"),
                   command=win.destroy).pack(side='right')
        ttk.Button(actions, text=_t('gui.finance.fraud_scan.open_case',
                                    default="Open case for selected"),
                   command=lambda: self._fraud_open_case(tree, refresh, win)
                   ).pack(side='right', padx=5)

        table = ttk.Frame(win)
        table.pack(fill='both', expand=True, padx=10)
        tree = ttk.Treeview(table, columns=RESULT_COLUMNS, show='headings', selectmode='browse')
        for c in RESULT_COLUMNS:
            tree.heading(c, text=RESULT_HEADINGS[c])
            tree.column(c, width=RESULT_WIDTHS[c], anchor='e' if c in ('amount', 'risk') else 'w')
        vsb = ttk.Scrollbar(table, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side='right', fill='y')
        tree.pack(fill='both', expand=True)
        self._fraud_scores = {}
        for p in result['suspicious']:
            self._fraud_scores[p['payment_id']] = float(p['fraud_score'] or 0)
            tree.insert('', 'end', iid=str(p['payment_id']), values=(
                p['payment_id'], p['student_id'],
                f"{p['first_name']} {p['last_name']}".strip(),
                f"£{float(p['amount'] or 0):,.2f}", p['payment_method'],
                p['payment_date'], f"{float(p['fraud_score'] or 0) * 100:.1f}%",
            ))

    def _fraud_open_case(self, tree, refresh, parent):
        sel = tree.selection()
        if not sel:
            messagebox.showwarning(
                _t('gui.finance.fraud_scan.title', default="Fraud scan"),
                _t('gui.finance.fraud_scan.select_first', default="Select a flagged payment first."),
                parent=parent)
            return
        payment_id = int(sel[0])
        score = self._fraud_scores.get(payment_id, 0.0)
        try:
            self._ops().create_fraud_case(payment_id, score, "Flagged by fraud scan")
        except Exception as exc:
            messagebox.showerror("Unable to save", str(exc), parent=parent)
            return
        refresh()
        messagebox.showinfo(
            _t('gui.finance.fraud_scan.title', default="Fraud scan"),
            f"Case opened for payment {payment_id} (risk {score * 100:.1f}%).",
            parent=parent)


__all__ = ["FraudScanMixin"]
