"""The "Pay" dialog for the parent portal and the student portal.

``open_pay_dialog(parent, payer_kind, payer_id, *, auth=None)``

* ``payer_kind="parent"``, ``payer_id`` = the parent-portal account id —
  lists fees, trip balances and catering top-ups for every linked child;
* ``payer_kind="student"``, ``payer_id`` = the signed-in student's id —
  their own items only.

Everything is checked again in the domain (``online_payments``): the
signed-in principal must *be* this payer. The parent portal window does
not set ``access.current()`` itself, so pass its ``auth`` and the dialog
binds the principal from it when none is bound yet.

Card payments open the provider's hosted page in the browser; because
the desktop app cannot receive the provider's callback, the payer clicks
**Check status** afterwards (and the dialog checks once by itself when
it is reopened). When online payment is not set up the dialog says so
plainly and the Pay button stays disabled — nothing pretends to work.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import messagebox
from typing import Any

from education_system.platform.delivery.gui import window_sizing
from education_system.systems.sixth_form.domains.finance.domain.online_payments import (
    online_payments as op,
)
from education_system.systems.sixth_form.interfaces.gui._ui import (
    grab_when_viewable,
)
from education_system.systems.sixth_form.domains.finance.interfaces.gui.online_payments._common import (
    open_link,
    run_in_background,
    warn_errors,
)

logger = logging.getLogger(__name__)

_MUTED = "#7f8c8d"
_STATUS_TAGS = {
    op.PENDING: ("#fff7e6", "#7a5800"),
    op.PAID: ("#e6f7e6", "#0d6b2a"),
    op.FAILED: ("#ffd1d1", "#8c0d0d"),
    op.CANCELLED: ("#eeeeee", "#444444"),
    op.REFUNDED: ("#e6f0ff", "#1a3f8c"),
}


def _bind_principal(auth: Any) -> None:
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    if auth is not None and not access.current().username:
        access.set_current(access.from_auth(auth))


def _tree(parent: tk.Misc, cols: list[tuple[str, str, int]],
          height: int = 8) -> ttk.Treeview:
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True)
    tree = ttk.Treeview(frame, columns=[c[0] for c in cols], show="headings",
                        height=height, selectmode="browse")
    for key, title, width in cols:
        tree.heading(key, text=title)
        tree.column(key, width=width, anchor="w")
    sb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=sb.set)
    tree.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")
    return tree


class PayDialog:
    def __init__(self, parent: Any, payer_kind: str, payer_id: Any,
                 auth: Any = None) -> None:
        _bind_principal(auth)
        self.payer_kind = payer_kind
        self.payer_id = payer_id
        master = getattr(parent, "root", parent)
        self.win = tk.Toplevel(master) if master is not None else tk.Tk()
        self.win.title("Pay online")
        window_sizing.fit(self.win, "1100x720", (900, 600))
        if master is not None:
            self.win.transient(master.winfo_toplevel())
        self.items: dict[str, op.PayableItem] = {}
        self._busy = False
        self._build()
        self.refresh(check_pending=True)
        grab_when_viewable(self.win)

    # ── Layout ──────────────────────────────────────────────────────
    def _build(self) -> None:
        w = self.win
        top = ttk.Frame(w, padding=(12, 10, 12, 4))
        top.pack(fill="x")
        ttk.Label(top, text="Pay online", font=("", 14, "bold")).pack(anchor="w")
        self.state_var = tk.StringVar()
        self.state_lbl = tk.Label(top, textvariable=self.state_var,
                                  justify="left", anchor="w", wraplength=1000,
                                  padx=8, pady=6)
        self.state_lbl.pack(fill="x", pady=(6, 0))

        # Bottom bars first so they stay visible on short screens.
        bottom = ttk.Frame(w, padding=(12, 4, 12, 10))
        bottom.pack(side="bottom", fill="x")
        self.status_var = tk.StringVar(value="")
        ttk.Label(bottom, textvariable=self.status_var,
                  foreground=_MUTED).pack(side="left")
        ttk.Button(bottom, text="Close", command=w.destroy).pack(side="right")

        body = ttk.Frame(w, padding=(12, 4, 12, 4))
        body.pack(fill="both", expand=True)

        ttk.Label(body, text="What you can pay", font=("", 11, "bold")
                  ).pack(anchor="w")
        pay_bar = ttk.Frame(body)
        pay_bar.pack(side="top", fill="x", pady=(2, 4))
        ttk.Label(pay_bar, text="Amount £").pack(side="left")
        self.amount = ttk.Entry(pay_bar, width=10)
        self.amount.pack(side="left", padx=(2, 8))
        self.pay_btn = ttk.Button(pay_bar, text="Pay by card…",
                                  command=self._pay)
        self.pay_btn.pack(side="left")
        self.history_btn = ttk.Button(pay_bar, text="Catering history…",
                                      command=self._catering_history)
        self.history_btn.pack(side="left", padx=6)
        ttk.Label(pay_bar, text="Pick an item; you can pay part of a balance.",
                  foreground=_MUTED).pack(side="left", padx=8)
        items_frame = ttk.Frame(body)
        items_frame.pack(fill="both", expand=True)
        self.items_tree = _tree(items_frame, [
            ("student", "Student", 170), ("item", "Item", 360),
            ("owed", "Owed", 90), ("due", "Due", 90),
            ("progress", "In progress", 120)], height=7)
        self.items_tree.bind("<<TreeviewSelect>>", self._on_item)

        ttk.Label(body, text="Your payments", font=("", 11, "bold")
                  ).pack(anchor="w", pady=(10, 0))
        req_bar = ttk.Frame(body)
        req_bar.pack(side="top", fill="x", pady=(2, 4))
        ttk.Button(req_bar, text="Check status",
                   command=self._check_selected).pack(side="left")
        ttk.Button(req_bar, text="Open payment page again",
                   command=self._reopen).pack(side="left", padx=6)
        ttk.Button(req_bar, text="Try again",
                   command=self._retry).pack(side="left")
        ttk.Button(req_bar, text="Cancel payment",
                   command=self._cancel).pack(side="left", padx=6)
        ttk.Button(req_bar, text="Refresh",
                   command=lambda: self.refresh(check_pending=True)
                   ).pack(side="left")
        req_frame = ttk.Frame(body)
        req_frame.pack(fill="both", expand=True)
        self.req_tree = _tree(req_frame, [
            ("ref", "Reference", 120), ("date", "Started", 130),
            ("student", "Student", 150), ("item", "Item", 260),
            ("amount", "Amount", 80), ("status", "Status", 90),
            ("note", "Note", 240)], height=7)
        for tag, (bg, fg) in _STATUS_TAGS.items():
            self.req_tree.tag_configure(tag, background=bg, foreground=fg)

    # ── Data ────────────────────────────────────────────────────────
    def _set_busy(self, on: bool) -> None:
        self._busy = on
        self.win.configure(cursor="watch" if on else "")
        self.status_var.set("Contacting the payment provider…" if on else "")

    def refresh(self, check_pending: bool = False) -> None:
        st = op.provider_state()
        self.state_var.set(st.message)
        self.state_lbl.configure(
            background="#e6f7e6" if st.ready else "#fff1e0",
            foreground="#0d6b2a" if st.ready else "#7a3e00")
        self.pay_btn.configure(state="normal" if st.ready else "disabled")
        self._load()
        if check_pending and st.ready and any(
                r.status == op.PENDING for r in self._requests):
            run_in_background(
                self.win,
                lambda: op.check_pending(payer_kind=self.payer_kind,
                                         payer_id=self.payer_id),
                lambda counts: self._after_check(counts),
                busy=self._set_busy)

    def _after_check(self, counts: dict[str, int]) -> None:
        self._load()
        if counts.get("paid"):
            self.status_var.set(f"{counts['paid']} payment(s) confirmed.")

    def _load(self) -> None:
        self.items = {}
        self._requests: list[op.PaymentRequest] = []
        for t in (self.items_tree, self.req_tree):
            t.delete(*t.get_children())
        items = warn_errors(self.win, lambda: op.payable_items(
            self.payer_kind, self.payer_id)) or []
        for it in items:
            self.items[it.key] = it
            self.items_tree.insert("", "end", iid=it.key, values=(
                it.student_name, it.description,
                "any amount" if it.balance_pence is None
                else op.money(it.balance_pence),
                it.due_date or "", it.pending_reference or ""))
        self._requests = warn_errors(self.win, lambda: op.requests_for_payer(
            self.payer_kind, self.payer_id)) or []
        for r in self._requests:
            note = r.failure_reason or ""
            if r.status == op.PAID:
                note = f"Paid {r.paid_at or ''}".strip()
            elif r.status == op.PENDING and not r.is_offline:
                note = "Waiting — click Check status after paying"
            if r.refunded_pence:
                note = f"Refunded {op.money(r.refunded_pence)}"
            self.req_tree.insert("", "end", iid=str(r.request_id), values=(
                r.reference, r.created_at[:16], r.student_name or r.student_id,
                r.description, op.money(r.amount_pence), r.status, note),
                tags=(r.status,))
        if not items:
            self.status_var.set("Nothing to pay at the moment.")

    def _on_item(self, _e: Any = None) -> None:
        it = self._selected_item(quiet=True)
        if it is None:
            return
        self.amount.delete(0, "end")
        if it.balance_pence is not None:
            self.amount.insert(0, f"{it.balance_pence / 100:.2f}")
        self.history_btn.configure(
            state="normal" if it.item_kind == op.KIND_CATERING else "disabled")

    def _selected_item(self, quiet: bool = False) -> op.PayableItem | None:
        sel = self.items_tree.selection()
        if not sel:
            if not quiet:
                messagebox.showwarning("Pay online", "Pick something to pay.",
                                       parent=self.win)
            return None
        return self.items.get(sel[0])

    def _selected_request(self) -> op.PaymentRequest | None:
        sel = self.req_tree.selection()
        if not sel:
            messagebox.showwarning("Pay online", "Pick one of your payments.",
                                   parent=self.win)
            return None
        return next((r for r in self._requests
                     if str(r.request_id) == sel[0]), None)

    # ── Actions ─────────────────────────────────────────────────────
    def _pay(self) -> None:
        if self._busy:
            return
        it = self._selected_item()
        if it is None:
            return
        amount = self.amount.get().strip()
        if not amount:
            messagebox.showwarning("Pay online", "Enter the amount to pay.",
                                   parent=self.win)
            return
        try:
            pence = op.to_pence(amount)
        except ValueError as e:
            messagebox.showwarning("Pay online", str(e), parent=self.win)
            return
        if not messagebox.askyesno(
                "Pay online",
                f"Pay {op.money(pence)} for {it.student_name}:\n"
                f"{it.description}?\n\nYour browser will open the secure "
                "card payment page.", parent=self.win):
            return

        def start() -> op.PaymentRequest:
            return op.start_payment(
                self.payer_kind, self.payer_id, it.item_kind, amount=amount,
                target_id=it.target_id, student_id=it.student_id)

        def done(req: op.PaymentRequest) -> None:
            self._load()
            if req.checkout_url:
                open_link(self.win, req.checkout_url)
                messagebox.showinfo(
                    "Pay online",
                    f"Payment {req.reference} has opened in your browser.\n\n"
                    "When you have finished paying, come back here and click "
                    "Check status. Nothing is taken until you complete the "
                    "card page.", parent=self.win)

        run_in_background(self.win, start, done, busy=self._set_busy)

    def _check_selected(self) -> None:
        r = self._selected_request()
        if r is None or self._busy:
            return

        def done(out: op.PaymentRequest) -> None:
            self._load()
            msg = {op.PAID: f"{out.reference} is paid — thank you. A receipt "
                            "has been issued.",
                   op.FAILED: f"{out.reference} was not paid: "
                              f"{out.failure_reason or 'failed'}.",
                   op.PENDING: f"{out.reference} has not been paid yet."
                   }.get(out.status, f"{out.reference} is {out.status}.")
            messagebox.showinfo("Payment status", msg, parent=self.win)

        run_in_background(self.win, lambda: op.check_status(r.request_id),
                          done, busy=self._set_busy)

    def _reopen(self) -> None:
        r = self._selected_request()
        if r is None:
            return
        if r.status != op.PENDING or not r.checkout_url:
            messagebox.showwarning(
                "Pay online", f"{r.reference} is {r.status}; there is no "
                "payment page to open.", parent=self.win)
            return
        open_link(self.win, r.checkout_url)

    def _retry(self) -> None:
        r = self._selected_request()
        if r is None or self._busy:
            return

        def done(out: op.PaymentRequest) -> None:
            self._load()
            if out.checkout_url:
                open_link(self.win, out.checkout_url)

        run_in_background(self.win, lambda: op.retry_checkout(r.request_id),
                          done, busy=self._set_busy)

    def _cancel(self) -> None:
        r = self._selected_request()
        if r is None or self._busy:
            return
        if r.status != op.PENDING:
            messagebox.showwarning("Pay online",
                                   f"{r.reference} is {r.status}.",
                                   parent=self.win)
            return
        if not messagebox.askyesno("Cancel payment",
                                   f"Cancel {r.reference}?", parent=self.win):
            return
        run_in_background(
            self.win, lambda: op.cancel(r.request_id, reason="Cancelled by payer"),
            lambda _out: self._load(), busy=self._set_busy)

    def _catering_history(self) -> None:
        it = self._selected_item()
        if it is None or it.item_kind != op.KIND_CATERING:
            return
        from education_system.systems.sixth_form.domains.operations.domain.catering import (
            cashless,
        )
        res = warn_errors(self.win, lambda: cashless.statement_for_payer(
            self.payer_kind, self.payer_id, it.student_id))
        if res is None:
            return
        balance, txns = res
        dlg = tk.Toplevel(self.win)
        dlg.title(f"Catering — {it.student_name}")
        window_sizing.fit(dlg, "820x520", (600, 400))
        dlg.transient(self.win)
        ttk.Label(dlg, text=f"Balance: {cashless.money(balance)}",
                  font=("", 12, "bold"), padding=8).pack(anchor="w")
        ttk.Button(dlg, text="Close", command=dlg.destroy).pack(
            side="bottom", anchor="e", padx=8, pady=8)
        frame = ttk.Frame(dlg, padding=(8, 0))
        frame.pack(fill="both", expand=True)
        tree = _tree(frame, [("at", "When", 140), ("type", "Type", 90),
                             ("amount", "Amount", 90), ("free", "Free meal", 90),
                             ("items", "Details", 340)], height=14)
        for t in txns:
            tree.insert("", "end", values=(
                t.at[:16], t.txn_type + (" (voided)" if t.voided else ""),
                cashless.money(t.amount_pence),
                cashless.money(t.free_meal_pence) if t.free_meal_pence else "",
                t.items or t.method or ""))


def open_pay_dialog(parent: Any, payer_kind: str, payer_id: Any, *,
                    auth: Any = None) -> PayDialog:
    """Open the Pay dialog for a parent (account id) or a student (id)."""
    return PayDialog(parent, payer_kind, payer_id, auth=auth)
