"""Expense Claims screen.

The old window's tabs are kept in their order - Open, Awaiting Payment, Paid,
All and Summary - each claims tab with its filter bar (Claimant, ID,
Category, Status on All, Title; Apply, New), its claims table (ID, Ref,
Claimant, Title, Category, Submitted, Status, Lines, Total) with the status
colours, the Lines table below (ID, Incurred, Category, Description,
Supplier, Qty, Unit, VAT, Gross) and its buttons (Edit, Add line, Edit line,
Delete line, Submit, Review, Approve, Reject, Pay, Cancel, Status, Delete
claim, Refresh). The claim and line dialogs keep the old fields.

Added: a Budget code column and field, Reopen, Attach receipt, Notify
claimant, History and Export CSV buttons (each disabled when it can't be used
on the selected claim), and the tabs My claims, Approval queue, Payment runs
and Settings (mileage rate, receipt threshold, category limits). The rules are
in :mod:`modules.finance.domain.expense_claims`.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Any

from education_system.platform.delivery.gui.parented_dialogs import filedialog, messagebox
from education_system.systems.secondary.modules.finance.domain import budgets as B
from education_system.systems.secondary.modules.finance.domain import expense_claims as X
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.gui.components import widgets as W

logger = logging.getLogger(__name__)
_ERRORS = W.ERRORS
_form = W.form_dialog
_STATUS_TAGS = {"Draft": ("#fff7e6", "#7a5800"), "Submitted": ("#e6f0ff", "#1a3f8c"),
                "Under Review": ("#e6f0ff", "#1a3f8c"), "Approved": ("#d6ffd6", "#0d6b2a"),
                "Rejected": ("#ffd1d1", "#8c0d0d"), "Paid": ("#e6f7e6", "#0d6b2a"),
                "Cancelled": ("#dddddd", "#444444")}
_COLUMNS = [("id", "Id", 50), ("ref", "Ref", 120), ("claimant", "Claimant", 170),
            ("title", "Title", 230), ("category", "Category", 120), ("budget", "Budget", 90),
            ("submitted", "Submitted", 90), ("status", "Status", 95), ("lines", "Lines", 50),
            ("total", "Total", 90)]
_LINE_COLUMNS = [("id", "Id", 50), ("incurred", "Incurred", 90), ("category", "Category", 120),
                 ("description", "Description", 220), ("supplier", "Supplier", 120),
                 ("qty", "Qty", 60), ("unit", "Unit", 80), ("vat", "Vat", 70),
                 ("gross", "Gross", 80), ("receipt", "Receipt", 90)]
#: The old buttons in their order, then the new ones: (label, action needed).
_ACTIONS = (("Edit", "edit"), ("Add line", "lines"), ("Edit line", "lines"),
            ("Delete line", "lines"), ("Submit", "submit"), ("Review", "review"),
            ("Approve", "approve"), ("Reject", "reject"), ("Pay", "pay"), ("Cancel", "cancel"),
            ("Status", "status"), ("Delete claim", "delete"), ("Refresh", None))
_MORE = (("Reopen", "reopen"), ("Attach receipt…", "lines"), ("Notify claimant", "notify"),
         ("History", "history"), ("Export CSV…", None))


def _tree(parent, columns, height: int = 12, select: str = "browse") -> ttk.Treeview:
    t = W.tree(parent, columns, height=height, select=select,
               stretch={"title", "description", "claimant"}, tags=W.STANDARD_TAGS)
    for status, (bg, fg) in _STATUS_TAGS.items():
        t.tag_configure(status, background=bg, foreground=fg)
    return t


def _staff_choices() -> list[str]:
    try:
        return [s["username"] for s in accounts.staff_logins()]
    except Exception:  # noqa: BLE001 - a typed id still works
        return []


def _code_choices(current: X.Claim | None = None) -> tuple[list[str], dict[str, int]]:
    codes = B.codes_for_claims()
    labels = {c["label"]: c["line_id"] for c in codes}
    if current and current.budget_line_id and current.budget_line_id not in labels.values():
        ln = B.get_line(current.budget_line_id)
        labels[f"{ln.code} - {ln.centre_name}: {ln.description} ({ln.year_label})"] = ln.line_id
    return ["", *labels], labels


def _code_label(c: X.Claim | None, labels: dict[str, int]) -> str:
    if not c or not c.budget_line_id:
        return ""
    return next((k for k, v in labels.items() if v == c.budget_line_id), "")


class ExpenseClaimsPage:
    TABS = ("Open", "Awaiting Payment", "Paid", "All", "Summary", "My claims",
            "Approval queue", "Payment runs", "Settings")
    _SCOPES = {"Open": "open", "Awaiting Payment": "awaiting", "Paid": "paid", "All": "all",
               "My claims": "mine", "Approval queue": "queue"}

    def __init__(self, parent: ttk.Frame, *, principal: Principal, state: dict) -> None:
        self.parent, self.principal, self.state = parent, principal, state
        self.approver = X.is_approver(principal)
        activity_log.record("expenses.view")
        ttk.Label(parent, text="Expense Claims", font=("", 16, "bold")).pack(anchor="w")
        self.summary_var = tk.StringVar()
        ttk.Label(parent, textvariable=self.summary_var, foreground="#666").pack(
            anchor="w", pady=(0, 6))
        self.book = ttk.Notebook(parent)
        self.book.pack(fill="both", expand=True)
        self.tabs = {n: ttk.Frame(self.book, padding=8) for n in self.TABS}
        for n, f in self.tabs.items():
            self.book.add(f, text=n)
        self.views: dict[str, Any] = {}
        start = state.get("tab") if state.get("tab") in self.TABS else self.TABS[0]
        self.book.select(self.TABS.index(start))
        self.book.bind("<<NotebookTabChanged>>", self._on_tab)
        self._on_tab()

    def _top(self):
        return self.parent.winfo_toplevel()

    def _on_tab(self, _e=None) -> None:
        name = self.TABS[self.book.index(self.book.select())]
        self.state["tab"] = name
        if name not in self.views:
            tab = self.tabs[name]
            if name in self._SCOPES:
                self.views[name] = ClaimsTab(self, tab, self._SCOPES[name])
            elif name == "Summary":
                self.views[name] = SummaryTab(self, tab)
            elif name == "Payment runs":
                self.views[name] = PaymentRunsTab(self, tab)
            else:
                self.views[name] = SettingsTab(self, tab)
        self.views[name].refresh()
        self._header()

    def refresh_all(self) -> None:
        for v in self.views.values():
            v.refresh()
        self._header()

    def _header(self) -> None:
        try:
            s = X.summary(actor=self.principal)
            queue = X.awaiting_my_approval(self.principal)
        except _ERRORS:
            return
        self.summary_var.set(
            f"Claims: {s.total_claims}    Open: {s.drafts + s.submitted + s.under_review}    "
            f"Awaiting payment: {s.approved} ({X.money(s.awaiting_payment_value)})    "
            f"Paid: {X.money(s.paid_value)}    Waiting for you: {queue}")

    # ── shared dialogs and notices ───────────────────────────────────

    def info(self, title: str, text: str) -> None:
        messagebox.showinfo(title, text, parent=self._top())

    def error(self, title: str, e: Exception) -> None:
        messagebox.showerror(title, W.problems(e), parent=self._top())

    def offer_notice(self, c: X.Claim) -> None:
        if c.claimant_type != "Staff" or "notify" not in X.allowed_actions(self.principal, c):
            return
        if messagebox.askyesno("Expense Claims", f"E-mail {c.claimant_name or c.claimant_id} "
                               f"that the claim is {c.status.lower()}?", parent=self._top()):
            self.send_notice(c)

    def send_notice(self, c: X.Claim) -> None:
        try:
            mid = X.notify_claimant(c.claim_id, actor=self.principal)
        except _ERRORS as e:
            self.error("Notify claimant", e)
            return
        if not mid:
            self.info("Notify claimant", "The claimant has no e-mail address on their login.")
            return
        from education_system.systems.secondary.modules.communication.gui import email_views

        def done(_report, error) -> None:
            try:
                self.info("Notify claimant", "Queued - delivery failed: " + str(error)
                          if error else "Sent.")
            except tk.TclError:
                pass
        email_views.deliver_in_background(self.parent, mid, self.principal, done)


class ClaimsTab:
    """One claims list: the old Open / Awaiting / Paid / All tabs, plus
    My claims and the Approval queue."""

    def __init__(self, page: ExpenseClaimsPage, tab: ttk.Frame, scope: str) -> None:
        self.page, self.scope, self.principal = page, scope, page.principal
        self.rows: dict[str, X.Claim] = {}
        self.line_rows: dict[str, X.ClaimLine] = {}
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self.ctype, self.cid = tk.StringVar(), tk.StringVar()
        self.cat, self.status, self.title = tk.StringVar(), tk.StringVar(), tk.StringVar()
        if scope not in ("mine", "queue"):
            ttk.Label(bar, text="Claimant:").pack(side="left")
            ttk.Combobox(bar, textvariable=self.ctype, values=("", *X.CLAIMANT_TYPES),
                         state="readonly", width=11).pack(side="left", padx=(2, 6))
            ttk.Label(bar, text="ID:").pack(side="left")
            ttk.Entry(bar, textvariable=self.cid, width=10).pack(side="left", padx=(2, 6))
        ttk.Label(bar, text="Category:").pack(side="left")
        ttk.Combobox(bar, textvariable=self.cat, values=("", *X.CATEGORIES), state="readonly",
                     width=16).pack(side="left", padx=(2, 6))
        if scope in ("all", "mine"):
            ttk.Label(bar, text="Status:").pack(side="left")
            ttk.Combobox(bar, textvariable=self.status, values=("", *X.CLAIM_STATUSES),
                         state="readonly", width=12).pack(side="left", padx=(2, 6))
        ttk.Label(bar, text="Title:").pack(side="left")
        ttk.Entry(bar, textvariable=self.title, width=14).pack(side="left", padx=(2, 6))
        ttk.Button(bar, text="Apply", command=self.refresh).pack(side="left", padx=2)
        ttk.Button(bar, text="New", command=self.new).pack(side="left", padx=2)
        if scope == "queue":
            ttk.Label(tab, text="Claims waiting for your decision: your cost centres' claims, "
                                "or all of them for the finance office. Never your own.",
                      foreground="#555").pack(anchor="w")
        paned = ttk.PanedWindow(tab, orient="vertical")
        paned.pack(fill="both", expand=True, pady=4)
        top, bottom = ttk.Frame(paned), ttk.Frame(paned)
        paned.add(top, weight=3)
        paned.add(bottom, weight=2)
        self.tree = _tree(top, _COLUMNS)
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._on_select())
        self.tree.bind("<Double-Button-1>", lambda _e: self.view())
        ttk.Label(bottom, text="Lines").pack(anchor="w", pady=(0, 2))
        self.lines = _tree(bottom, _LINE_COLUMNS, height=6)
        self.lines.bind("<Double-Button-1>", lambda _e: self.edit_line())
        self.buttons: dict[str, tuple[ttk.Button, str | None]] = {}
        handlers = {"Edit": self.edit, "Add line": self.add_line, "Edit line": self.edit_line,
                    "Delete line": self.delete_line, "Submit": self.submit,
                    "Review": self.review, "Approve": self.approve, "Reject": self.reject,
                    "Pay": self.pay, "Cancel": self.cancel, "Status": self.set_status,
                    "Delete claim": self.delete, "Refresh": self.refresh,
                    "Reopen": self.reopen, "Attach receipt…": self.attach_receipt,
                    "Notify claimant": self.notify, "History": self.history,
                    "Export CSV…": self.export}
        for group in (_ACTIONS, _MORE):
            actions = ttk.Frame(tab)
            actions.pack(fill="x", pady=(2, 0))
            for label, need in group:
                b = ttk.Button(actions, text=label, command=handlers[label])
                b.pack(side="left", padx=2)
                self.buttons[label] = (b, need)
            if group is _ACTIONS:
                self.count = ttk.Label(actions, text="")
                self.count.pack(side="right")
        self._on_select()

    # ── list ─────────────────────────────────────────────────────────

    def _load(self) -> list[X.Claim]:
        p = self.principal
        if self.scope == "mine":
            rows = X.my_claims(p, status=self.status.get() or None)
        elif self.scope == "queue":
            rows = X.approval_queue(p)
        else:
            rows = X.list_claims(scope=None if self.scope == "all" else self.scope,
                                 claimant_type=self.ctype.get() or None,
                                 claimant_id=self.cid.get().strip() or None,
                                 status=self.status.get() or None, actor=p)
        cat, title = self.cat.get(), self.title.get().strip().lower()
        return [c for c in rows if (not cat or c.category == cat)
                and (not title or title in c.title.lower())]

    def refresh(self) -> None:
        keep = self.tree.selection()
        try:
            rows = self._load()
        except _ERRORS as e:
            self.page.error("Expense Claims", e)
            return
        self.tree.delete(*self.tree.get_children())
        self.rows = {}
        for c in rows:
            self.rows[str(c.claim_id)] = c
            self.tree.insert("", "end", iid=str(c.claim_id), tags=(c.status,), values=(
                c.claim_id, c.claim_ref, c.claimant_name or c.claimant_id, c.title, c.category,
                c.budget_code or "", c.submitted_on or "", c.status, c.line_count, c.total))
        self.count.config(text=f"{len(rows)} claim(s)")
        if keep and self.tree.exists(keep[0]):
            self.tree.selection_set(keep[0])
        self._on_select()

    def _claim(self) -> X.Claim | None:
        sel = self.tree.selection()
        return self.rows.get(sel[0]) if sel else None

    def _on_select(self) -> None:
        c = self._claim()
        allowed = X.allowed_actions(self.principal, c) if c else set()
        for _label, (b, need) in self.buttons.items():
            b.state(["!disabled"] if need is None or need in allowed else ["disabled"])
        self.lines.delete(*self.lines.get_children())
        self.line_rows = {}
        if c is None:
            return
        for ln in X.lines_for_claim(c.claim_id):
            self.line_rows[str(ln.line_id)] = ln
            qty = f"{ln.mileage_miles:g} mi" if ln.mileage_miles is not None else ln.quantity
            unit = (f"{ln.mileage_rate_pence}p/mi" if ln.mileage_rate_pence else
                    X.money(ln.unit_pence))
            self.lines.insert("", "end", iid=str(ln.line_id), values=(
                ln.line_id, ln.incurred_on, ln.category, ln.description or "",
                ln.supplier or "", qty, unit, X.money(ln.vat_pence), X.money(ln.gross_pence),
                "yes" if ln.has_receipt else ("n/a" if ln.category == X.MILEAGE else "-")))

    def _after(self, c: X.Claim | None = None) -> None:
        self.page.refresh_all()
        if c is not None and self.tree.exists(str(c.claim_id)):
            self.tree.selection_set(str(c.claim_id))

    def _run(self, title: str, fn, *args, **kw) -> X.Claim | None:
        try:
            out = fn(*args, actor=self.principal, **kw)
        except _ERRORS as e:
            self.page.error(title, e)
            return None
        self._after(out if isinstance(out, X.Claim) else None)
        return out

    # ── claim dialog ─────────────────────────────────────────────────

    def _fields(self, c: X.Claim | None) -> tuple[list, dict[str, int]]:
        choices, labels = _code_choices(c)
        fields: list = []
        if self.page.approver:
            fields += [("claim_ref", "Claim ref (blank = automatic)", c.claim_ref if c else "",
                        None),
                       ("claimant_type", "Claimant type*",
                        c.claimant_type if c else X.DEFAULT_CLAIMANT_TYPE, X.CLAIMANT_TYPES),
                       ("claimant_id", "Claimant id* (staff login)",
                        c.claimant_id if c else self.principal.username,
                        ("edit", _staff_choices()))]
        fields += [
            ("claimant_name", "Claimant name", c.claimant_name if c else "", None),
            ("department", "Department", c.department if c else "", None),
            ("title", "Title*", c.title if c else "", None),
            ("category", "Category*", c.category if c else X.DEFAULT_CATEGORY, X.CATEGORIES),
            ("payment_method", "Payment method*",
             c.payment_method if c else X.DEFAULT_PAYMENT_METHOD, X.PAYMENT_METHODS),
            ("purpose", "Purpose", c.purpose if c else "", None),
            ("incurred_from", "Incurred from", c.incurred_from if c else "", None),
            ("incurred_to", "Incurred to", c.incurred_to if c else "", None),
            ("budget_code", "Budget code (cost centre)", _code_label(c, labels), choices),
            ("receipts_attached", "Receipts attached", bool(c.receipts_attached) if c else
             False, "check"),
            ("description", "Description", c.description if c else "", "text"),
            ("notes", "Notes", c.notes if c else "", "text")]
        return fields, labels

    def new(self) -> None:
        fields, labels = self._fields(None)

        def save(v):
            v["budget_line_id"] = labels.get(v.pop("budget_code"), None)
            c = X.create_claim({k: x for k, x in v.items() if x not in ("", None)},
                               actor=self.principal)
            self._after(c)
        _form(self.page.parent, "New claim", fields, save,
              note="Dates are YYYY-MM-DD. Add the lines next, then Submit.")

    def edit(self) -> None:
        c = self._claim()
        if c is None:
            return
        fields, labels = self._fields(c)

        def save(v):
            v["budget_line_id"] = labels.get(v.pop("budget_code"), None)
            X.update_claim(c.claim_id, v, actor=self.principal)
            self._after(c)
        _form(self.page.parent, f"Edit claim {c.claim_ref}", fields, save,
              note=f"Status: {c.status}" + (f" - rejected: {c.rejection_reason}"
                                             if c.rejection_reason else ""))

    def view(self) -> None:
        c = self._claim()
        if c is None:
            return
        if "edit" in X.allowed_actions(self.principal, c):
            self.edit()
            return
        lines = [f"{c.claim_ref} - {c.title}", ""]
        for label, v in (("Claimant", f"{c.claimant_type}: {c.claimant_name or ''} "
                                      f"({c.claimant_id})"),
                         ("Department", c.department), ("Category", c.category),
                         ("Budget code", f"{c.budget_code} ({c.centre_name})"
                          if c.budget_code else None),
                         ("Purpose", c.purpose),
                         ("Incurred", f"{c.incurred_from or '?'} to {c.incurred_to or '?'}"),
                         ("Submitted", c.submitted_on),
                         ("Approved", f"{c.approved_on} by {c.approved_by}"
                          if c.approved_on else None),
                         ("Rejected", f"{c.rejected_on}: {c.rejection_reason}"
                          if c.rejected_on else None),
                         ("Paid", f"{c.paid_on} ({c.payment_method}, {c.payment_reference})"
                          if c.paid_on else None),
                         ("Status", c.status), ("Lines / total", f"{c.line_count} / {c.total}"),
                         ("Description", c.description), ("Notes", c.notes)):
            if v:
                lines.append(f"{label + ':':<16} {v}")
        W.text_window(self.page.parent, f"Claim {c.claim_ref}", "\n".join(lines))

    # ── lines ────────────────────────────────────────────────────────

    def _line_fields(self, ln: X.ClaimLine | None) -> list:
        return [
            ("incurred_on", "Incurred on*", ln.incurred_on if ln else "", None),
            ("category", "Category*", ln.category if ln else (
                self._claim().category if self._claim() else X.DEFAULT_CATEGORY), X.CATEGORIES),
            ("description", "Description*", ln.description if ln else "", None),
            ("supplier", "Supplier", ln.supplier if ln else "", None),
            ("receipt_ref", "Receipt ref", ln.receipt_ref if ln else "", None),
            ("receipt_path", "Receipt file", ln.receipt_path if ln else "", None),
            ("quantity", "Quantity", ln.quantity if ln else "1", None),
            ("unit_amount", "Unit amount (£)", X.pounds(ln.unit_pence) if ln and
             ln.mileage_miles is None else "", None),
            ("mileage_miles", "Mileage miles", f"{ln.mileage_miles:g}" if ln and
             ln.mileage_miles is not None else "", None),
            ("vat_amount", "VAT amount (£)", X.pounds(ln.vat_pence) if ln else "0", None),
            ("notes", "Notes", ln.notes if ln else "", "text")]

    def _line_note(self) -> str:
        s = X.settings()
        lim = X.limits()
        return (f"Mileage: enter the miles - paid at {s['mileage_rate_pence']}p a mile, no VAT. "
                f"Receipts are needed for other lines over {X.money(s['receipt_over_pence'])}."
                + (" Limits per claim: " + ", ".join(f"{k} {X.money(v)}" for k, v in
                                                     lim.items()) if lim else ""))

    def add_line(self) -> None:
        c = self._claim()
        if c is None:
            return

        def save(v):
            X.add_line(c.claim_id, v, actor=self.principal)
            self._after(c)
        _form(self.page.parent, f"Add line - {c.claim_ref}", self._line_fields(None), save,
              note=self._line_note())

    def _line(self, title: str) -> X.ClaimLine | None:
        sel = self.lines.selection()
        if not sel:
            self.page.info(title, "Select a line first.")
            return None
        return self.line_rows[sel[0]]

    def edit_line(self) -> None:
        c = self._claim()
        ln = self._line("Edit line") if c else None
        if ln is None:
            return
        if "lines" not in X.allowed_actions(self.principal, c):
            self.page.info("Edit line", "Lines can only be changed on a draft claim.")
            return

        def save(v):
            X.update_line(ln.line_id, v, actor=self.principal)
            self._after(c)
        _form(self.page.parent, f"Edit line #{ln.line_id}", self._line_fields(ln), save,
              note=self._line_note())

    def delete_line(self) -> None:
        c = self._claim()
        ln = self._line("Delete line") if c else None
        if ln and messagebox.askyesno("Delete line", f"Delete line #{ln.line_id}?",
                                      parent=self.page._top()):
            try:
                X.delete_line(ln.line_id, actor=self.principal)
            except _ERRORS as e:
                self.page.error("Delete line", e)
                return
            self._after(c)

    def attach_receipt(self) -> None:
        c = self._claim()
        ln = self._line("Attach receipt") if c else None
        if ln is None:
            return
        path = filedialog.askopenfilename(
            parent=self.page._top(), title="Receipt file",
            filetypes=[("Receipts", "*.pdf *.png *.jpg *.jpeg *.heic"), ("All files", "*")])
        if path:
            self._run("Attach receipt", X.update_line, ln.line_id, {"receipt_path": path})

    # ── workflow ─────────────────────────────────────────────────────

    def submit(self) -> None:
        c = self._claim()
        if c and messagebox.askyesno("Submit", f"Submit {c.claim_ref} ({c.total}) for "
                                     "approval?", parent=self.page._top()):
            self._run("Submit", X.submit, c.claim_id)

    def review(self) -> None:
        c = self._claim()
        if c:
            self._run("Review", X.begin_review, c.claim_id)

    def approve(self) -> None:
        c = self._claim()
        if c is None:
            return
        warnings = X.approval_warnings(c.claim_id)
        if not messagebox.askyesno(
                "Approve", "\n\n".join([*warnings, f"Approve {c.claim_ref} for {c.total}? "
                                                   f"It is charged to {c.budget_code}."]),
                parent=self.page._top()):
            return
        done = self._run("Approve", X.approve, c.claim_id)
        if done:
            self.page.offer_notice(done)

    def reject(self) -> None:
        c = self._claim()
        if c is None:
            return

        def save(v):
            done = X.reject(c.claim_id, actor=self.principal, reason=v["reason"])
            self._after(done)
            self.page.offer_notice(done)
        _form(self.page.parent, f"Reject {c.claim_ref}", [
            ("reason", "Reason (required)", "", "text")], save,
            note="The claimant sees the reason and can reopen the claim to fix it.")

    def pay(self) -> None:
        c = self._claim()
        if c is None:
            return

        def save(v):
            done = X.pay(c.claim_id, actor=self.principal,
                         payment_reference=v["payment_reference"], paid_on=v["paid_on"] or None,
                         payment_method=v["payment_method"])
            self._after(done)
            self.page.offer_notice(done)
        _form(self.page.parent, f"Pay {c.claim_ref} ({c.total})", [
            ("payment_method", "Payment method", c.payment_method, X.PAYMENT_METHODS),
            ("payment_reference", "Payment reference*", c.payment_reference or "", None),
            ("paid_on", "Paid on (blank = today)", "", None)], save,
            note="To pay many claims at once, use Payment runs.")

    def cancel(self) -> None:
        c = self._claim()
        if c is None:
            return

        def save(v):
            X.cancel(c.claim_id, actor=self.principal, reason=v["reason"])
            self._after(c)
        _form(self.page.parent, f"Cancel {c.claim_ref}", [
            ("reason", "Why (optional)", "", "text")], save,
            note="An approved claim's spend is taken off the budget again."
            if c.status == "Approved" else None)

    def reopen(self) -> None:
        c = self._claim()
        if c:
            self._run("Reopen", X.reopen, c.claim_id)

    def set_status(self) -> None:
        c = self._claim()
        if c is None:
            return

        def save(v):
            X.set_status(c.claim_id, v["status"], actor=self.principal,
                         reason=v["reason"] or None,
                         payment_reference=v["payment_reference"] or None)
            self._after(c)
        _form(self.page.parent, f"Status - {c.claim_ref}", [
            ("status", "Status", c.status, X.CLAIM_STATUSES),
            ("reason", "Reason / note (Rejected, Cancelled)", "", "text"),
            ("payment_reference", "Payment reference (Paid)", "", None)], save,
            note="The change goes through the proper step, so the claimant still can't "
                 "approve or pay their own claim and approval still posts to the budget.")

    def delete(self) -> None:
        c = self._claim()
        if c and messagebox.askyesno("Delete claim", f"Delete {c.claim_ref} and its lines?",
                                     parent=self.page._top()):
            try:
                X.delete_claim(c.claim_id, actor=self.principal)
            except _ERRORS as e:
                self.page.error("Delete claim", e)
                return
            self._after()

    def notify(self) -> None:
        c = self._claim()
        if c:
            self.page.send_notice(c)

    def history(self) -> None:
        c = self._claim()
        if c is None:
            return
        W.text_window(self.page.parent, f"History - {c.claim_ref}", "\n".join(
            f"{h['at']}  {h['actor']:<12} {h['action']:<12} "
            + ", ".join(f"{k}={v}" for k, v in h["detail"].items())
            for h in X.history(c.claim_id)) or "No changes recorded.")

    def export(self) -> None:
        path = filedialog.asksaveasfilename(parent=self.page._top(), defaultextension=".csv",
                                            filetypes=[("CSV", "*.csv")],
                                            initialfile="expense_claims.csv")
        if not path:
            return
        try:
            n = X.export_csv(path, actor=self.principal,
                             scope=self.scope if self.scope in X.SCOPES else None,
                             category=self.cat.get() or None, status=self.status.get() or None)
        except _ERRORS as e:
            self.page.error("Export", e)
            return
        self.page.info("Export", f"Exported {n} claim(s).")


class SummaryTab:
    def __init__(self, page: ExpenseClaimsPage, tab: ttk.Frame) -> None:
        self.page = page
        bar = ttk.Frame(tab)
        bar.pack(fill="x")
        ttk.Button(bar, text="Refresh", command=self.refresh).pack(side="left")
        self.text = tk.Text(tab, wrap="none", font=("TkFixedFont", 10))
        self.text.pack(fill="both", expand=True, pady=(6, 0))

    def refresh(self) -> None:
        try:
            s = X.summary(actor=self.page.principal)
        except _ERRORS as e:
            self.page.error("Summary", e)
            return
        out = ["Expense Claims Summary", "=" * 60, "",
               f"Total claims        : {s.total_claims}",
               f"Drafts              : {s.drafts}", f"Submitted           : {s.submitted}",
               f"Under review        : {s.under_review}", f"Approved            : {s.approved}",
               f"Paid                : {s.paid}", f"Rejected            : {s.rejected}",
               f"Cancelled           : {s.cancelled}",
               f"Distinct claimants  : {s.distinct_claimants}", "",
               f"Total value         : {X.money(s.total_value)}",
               f"Awaiting payment    : {X.money(s.awaiting_payment_value)}",
               f"Paid value          : {X.money(s.paid_value)}"]
        for title, data in (("By category", s.by_category),
                            ("By claimant type", s.by_claimant_type),
                            ("By status", s.by_status),
                            ("By payment method", s.by_payment_method)):
            out += ["", f"{title}:"] + [f"  {k:<22}: {n}" for k, n in sorted(data.items())]
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("end", "\n".join(out))
        self.text.configure(state="disabled")


class PaymentRunsTab:
    def __init__(self, page: ExpenseClaimsPage, tab: ttk.Frame) -> None:
        self.page, self.principal = page, page.principal
        ttk.Label(tab, text="Approved claims ready to pay (your own are left out - someone "
                            "else pays them).", font=("", 11, "bold")).pack(anchor="w")
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=4)
        self.method = tk.StringVar()
        ttk.Label(bar, text="Method:").pack(side="left")
        cb = ttk.Combobox(bar, textvariable=self.method, values=("", *X.PAYMENT_METHODS),
                          state="readonly", width=12)
        cb.pack(side="left", padx=(2, 8))
        cb.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        self.b_sel = ttk.Button(bar, text="Pay selected…", command=lambda: self.run(True))
        self.b_all = ttk.Button(bar, text="Pay all listed…", command=lambda: self.run(False))
        for b in (self.b_sel, self.b_all):
            b.pack(side="left", padx=2)
            if not page.approver:
                b.state(["disabled"])
        self.total = ttk.Label(bar, text="")
        self.total.pack(side="right")
        self.tree = _tree(tab, [("id", "Id", 50), ("ref", "Ref", 120),
                                ("claimant", "Claimant", 200), ("method", "Method", 90),
                                ("budget", "Budget", 90), ("approved", "Approved", 90),
                                ("total", "Total", 90)], height=9, select="extended")
        ttk.Label(tab, text="Past runs", font=("", 11, "bold")).pack(anchor="w", pady=(8, 2))
        bar2 = ttk.Frame(tab)
        bar2.pack(fill="x")
        b = ttk.Button(bar2, text="Export again…", command=self.export_again)
        b.pack(side="left")
        if not page.approver:
            b.state(["disabled"])
        self.runs = _tree(tab, [("ref", "Run", 90), ("date", "Paid on", 90),
                                ("claims", "Claims", 60), ("total", "Total", 100),
                                ("file", "File", 200), ("by", "By", 100)], height=6)
        self.rows: dict[str, X.Claim] = {}

    def refresh(self) -> None:
        self.tree.delete(*self.tree.get_children())
        self.runs.delete(*self.runs.get_children())
        self.rows = {}
        if not self.page.approver:
            self.total.config(text="Payment runs are for the finance office.")
            return
        m = self.method.get()
        rows = [c for c in X.payable(self.principal) if not m or c.payment_method == m]
        for c in rows:
            self.rows[str(c.claim_id)] = c
            self.tree.insert("", "end", iid=str(c.claim_id), tags=("Approved",), values=(
                c.claim_id, c.claim_ref, c.claimant_name or c.claimant_id, c.payment_method,
                c.budget_code or "", c.approved_on or "", c.total))
        self.total.config(text=f"{len(rows)} claim(s), "
                               f"{X.money(sum(c.total_pence for c in rows))}")
        for r in X.list_payment_runs():
            self.runs.insert("", "end", iid=str(r.run_id), values=(
                r.reference, r.run_date, r.claims, X.money(r.total_pence), r.file_name or "",
                r.created_by or ""))

    def run(self, selected: bool) -> None:
        ids = [int(i) for i in self.tree.selection()] if selected else list(map(int, self.rows))
        if not ids:
            self.page.info("Payment run", "Nothing to pay.")
            return
        total = sum(self.rows[str(i)].total_pence for i in ids)
        path = filedialog.asksaveasfilename(parent=self.page._top(), defaultextension=".csv",
                                            filetypes=[("CSV", "*.csv")],
                                            initialfile="payment_run.csv")
        if not path or not messagebox.askyesno(
                "Payment run", f"Pay {len(ids)} claim(s), {X.money(total)}, and mark them "
                               "paid?", parent=self.page._top()):
            return
        try:
            r = X.payment_run(path, actor=self.principal, claim_ids=ids)
        except _ERRORS as e:
            self.page.error("Payment run", e)
            return
        self.page.refresh_all()
        self.page.info("Payment run", f"Run {r['reference']}: {r['claims']} claim(s), "
                                      f"{X.money(r['total_pence'])}. File saved for the bank.")

    def export_again(self) -> None:
        sel = self.runs.selection()
        if not sel:
            self.page.info("Export again", "Select a run first.")
            return
        path = filedialog.asksaveasfilename(parent=self.page._top(), defaultextension=".csv",
                                            filetypes=[("CSV", "*.csv")],
                                            initialfile="payment_run.csv")
        if path:
            try:
                n = X.export_payment_run(int(sel[0]), path, actor=self.principal)
            except _ERRORS as e:
                self.page.error("Export again", e)
                return
            self.page.info("Export again", f"Exported {n} claim(s).")


class SettingsTab:
    def __init__(self, page: ExpenseClaimsPage, tab: ttk.Frame) -> None:
        self.page, self.principal = page, page.principal
        self.var = tk.StringVar()
        ttk.Label(tab, textvariable=self.var, justify="left").pack(anchor="w")
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=6)
        for text, cmd in (("Change rates…", self.change), ("Set limit…", self.limit)):
            b = ttk.Button(bar, text=text, command=cmd)
            b.pack(side="left", padx=2)
            if not page.approver:
                b.state(["disabled"])
        ttk.Label(tab, text="Limits per claim, by category").pack(anchor="w")
        self.tree = _tree(tab, [("category", "Category", 200), ("limit", "Limit", 120)],
                          height=10)

    def refresh(self) -> None:
        s = X.settings()
        self.var.set(f"Mileage rate: {s['mileage_rate_pence']}p a mile (HMRC: "
                     f"{X.HMRC_MILEAGE_PENCE}p)\nReceipts needed for lines over: "
                     f"{X.money(s['receipt_over_pence'])}")
        self.tree.delete(*self.tree.get_children())
        for cat, n in sorted(X.limits().items()):
            self.tree.insert("", "end", values=(cat, X.money(n)))

    def change(self) -> None:
        s = X.settings()

        def save(v):
            X.set_settings({"mileage_rate_pence": v["rate"], "receipt_over_pence": v["over"]},
                           actor=self.principal)
            self.refresh()
        _form(self.page.parent, "Expense settings", [
            ("rate", "Mileage rate (pence a mile)", s["mileage_rate_pence"], None),
            ("over", "Receipts needed over (£)", X.pounds(s["receipt_over_pence"]), None)],
            save, note="New mileage lines use the new rate; lines already entered keep "
                       "theirs.")

    def limit(self) -> None:
        def save(v):
            X.set_limit(v["category"], v["limit"], actor=self.principal)
            self.refresh()
        _form(self.page.parent, "Category limit", [
            ("category", "Category", X.DEFAULT_CATEGORY, X.CATEGORIES),
            ("limit", "Limit per claim (£, blank = none)", "", None)], save)


class MyExpenseClaimsPage(ExpenseClaimsPage):
    """Every member of staff's own view: their claims, and the claims waiting
    for them as a cost centre holder."""
    TABS = ("My claims", "Approval queue")


def draw_my_expense_claims(parent: ttk.Frame, *, principal: Principal, state: dict
                           ) -> MyExpenseClaimsPage:
    return MyExpenseClaimsPage(parent, principal=principal, state=state)


def draw_expense_claims(parent: ttk.Frame, *, principal: Principal, state: dict
                        ) -> ExpenseClaimsPage:
    return ExpenseClaimsPage(parent, principal=principal, state=state)
