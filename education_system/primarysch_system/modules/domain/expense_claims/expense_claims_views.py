"""Tkinter views for Primary School Expense Claims."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, ttk

from education_system.shared import branding
from education_system.primarysch_system.modules.domain.expense_claims import (
    expense_claims as data,
)
from education_system.primarysch_system.modules.domain.expense_claims.expense_claims import (
    CATEGORIES,
    CLAIM_STATUSES,
    CLAIMANT_TYPES,
    Claim,
    ClaimLine,
    DEFAULT_CATEGORY,
    DEFAULT_CLAIM_STATUS,
    DEFAULT_CLAIMANT_TYPE,
    DEFAULT_PAYMENT_METHOD,
    PAYMENT_METHODS,
    ValidationError,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)

_STATUS_TAGS = {
    "Draft":        ("#fff7e6", "#7a5800"),
    "Submitted":    ("#e6f0ff", "#1a3f8c"),
    "Under Review": ("#e6f0ff", "#1a3f8c"),
    "Approved":     ("#d6ffd6", "#0d6b2a"),
    "Rejected":     ("#ffd1d1", "#8c0d0d"),
    "Paid":         ("#e6f7e6", "#0d6b2a"),
    "Cancelled":    ("#dddddd", "#444444"),
}


def open_expense_claims_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Expense Claims — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    ClaimsTab(nb, scope="open",     label="Open")
    ClaimsTab(nb, scope="awaiting", label="Awaiting Payment")
    ClaimsTab(nb, scope="paid",     label="Paid")
    ClaimsTab(nb, scope="all",      label="All")
    SummaryTab(nb)


class ClaimsTab:
    def __init__(self, nb: ttk.Notebook, *,
                 scope: str, label: str) -> None:
        self.scope = scope
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text=label)
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Claimant:").pack(side="left")
        self.f_ct = ttk.Combobox(
            bar, values=("",) + CLAIMANT_TYPES,
            state="readonly", width=12)
        self.f_ct.current(0)
        self.f_ct.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="ID:").pack(side="left")
        self.f_cid = ttk.Entry(bar, width=12)
        self.f_cid.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Category:").pack(side="left")
        self.f_cat = ttk.Combobox(
            bar, values=("",) + CATEGORIES,
            state="readonly", width=18)
        self.f_cat.current(0)
        self.f_cat.pack(side="left", padx=(2, 8))
        if self.scope == "all":
            ttk.Label(bar, text="Status:").pack(side="left")
            self.f_status = ttk.Combobox(
                bar, values=("",) + CLAIM_STATUSES,
                state="readonly", width=14)
            self.f_status.current(0)
            self.f_status.pack(side="left", padx=(2, 8))
        else:
            self.f_status = None
        ttk.Label(bar, text="Title:").pack(side="left")
        self.f_title = ttk.Entry(bar, width=16)
        self.f_title.pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left",
                                                 padx=4)
        ttk.Button(bar, text="New",
                    command=self._new).pack(side="left",
                                              padx=(16, 0))

        paned = ttk.PanedWindow(self.frame, orient="vertical")
        paned.pack(fill="both", expand=True, padx=8, pady=4)

        top = ttk.Frame(paned)
        paned.add(top, weight=3)
        cols = ("id", "ref", "claimant", "title",
                "category", "submitted", "status",
                "lines", "total")
        self.tree = ttk.Treeview(top, columns=cols,
                                   show="headings",
                                   selectmode="browse")
        widths = {"id": 50, "ref": 130, "claimant": 200,
                   "title": 280, "category": 130,
                   "submitted": 110, "status": 110,
                   "lines": 60, "total": 110}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c],
                              anchor=("center"
                                       if c in ("id", "lines")
                                       else "e"
                                       if c == "total"
                                       else "w"))
        vsb = ttk.Scrollbar(top, orient="vertical",
                              command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        for status, (bg, fg) in _STATUS_TAGS.items():
            self.tree.tag_configure(status, background=bg,
                                       foreground=fg)
        self.tree.bind("<<TreeviewSelect>>",
                         lambda _e: self._show_lines())
        self.tree.bind("<Double-Button-1>",
                         lambda _e: self._edit())

        bottom = ttk.Frame(paned)
        paned.add(bottom, weight=2)
        ttk.Label(bottom, text="Lines").pack(
            anchor="w", padx=4, pady=(0, 2))
        lcols = ("id", "incurred", "category", "description",
                  "supplier", "qty", "unit", "vat", "gross")
        self.lines = ttk.Treeview(bottom, columns=lcols,
                                       show="headings",
                                       selectmode="browse",
                                       height=8)
        lwidths = {"id": 50, "incurred": 100, "category": 130,
                    "description": 260, "supplier": 140,
                    "qty": 60, "unit": 90, "vat": 90,
                    "gross": 100}
        for c in lcols:
            self.lines.heading(c, text=c.title())
            self.lines.column(c, width=lwidths[c],
                                anchor=("center"
                                         if c in ("id", "qty")
                                         else "e"
                                         if c in ("unit", "vat",
                                                    "gross")
                                         else "w"))
        lvsb = ttk.Scrollbar(bottom, orient="vertical",
                                  command=self.lines.yview)
        self.lines.configure(yscrollcommand=lvsb.set)
        self.lines.pack(side="left", fill="both", expand=True)
        lvsb.pack(side="right", fill="y")

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 8))
        for label, cmd in (
                ("Edit",         self._edit),
                ("Add line",     self._add_line),
                ("Edit line",    self._edit_line),
                ("Delete line",  self._delete_line),
                ("Submit",       self._submit),
                ("Review",       self._review),
                ("Approve",      self._approve),
                ("Reject",       self._reject),
                ("Pay",          self._pay),
                ("Cancel",       self._cancel),
                ("Status",       self._set_status),
                ("Delete claim", self._delete),
                ("Refresh",      self.refresh),
        ):
            ttk.Button(actions, text=label,
                        command=cmd).pack(side="left", padx=4)
        self.count = ttk.Label(actions, text="")
        self.count.pack(side="right")

    def _filters(self) -> dict:
        f: dict = {}
        if self.f_ct.get():
            f["claimant_type"] = self.f_ct.get()
        if self.f_cid.get().strip():
            f["claimant_id"] = self.f_cid.get().strip()
        if self.f_cat.get():
            f["category"] = self.f_cat.get()
        if self.f_status is not None and self.f_status.get():
            f["status"] = self.f_status.get()
        if self.f_title.get().strip():
            f["title_like"] = self.f_title.get().strip()
        if self.scope == "open":
            f["open_only"] = True
        elif self.scope == "awaiting":
            f["awaiting_payment_only"] = True
        elif self.scope == "paid":
            f["paid_only"] = True
        return f

    def refresh(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        for iid in self.lines.get_children():
            self.lines.delete(iid)
        try:
            rows = data.list_claims(**self._filters())
        except ValidationError as e:
            messagebox.showerror("Expense Claims", str(e),
                                    parent=self.frame)
            return
        for c in rows:
            clm = (f"{c.claimant_type}: {c.claimant_id}"
                    + (f" ({c.claimant_name})"
                        if c.claimant_name else ""))
            self.tree.insert(
                "", "end", iid=str(c.claim_id),
                values=(c.claim_id, c.claim_ref, clm,
                         c.title, c.category,
                         c.submitted_on or "—",
                         c.status, c.line_count,
                         f"£{c.total_amount:,.2f}"),
                tags=(c.status,))
        self.count.config(text=f"{len(rows)} claim(s)")

    def _show_lines(self) -> None:
        for iid in self.lines.get_children():
            self.lines.delete(iid)
        sel = self.tree.selection()
        if not sel:
            return
        for ln in data.lines_for_claim(int(sel[0])):
            self.lines.insert(
                "", "end", iid=str(ln.line_id),
                values=(ln.line_id, ln.incurred_on,
                         ln.category, ln.description or "—",
                         ln.supplier or "—",
                         f"{ln.quantity:.1f}",
                         f"£{ln.unit_amount:,.2f}",
                         f"£{ln.vat_amount:,.2f}",
                         f"£{ln.gross_amount:,.2f}"))

    def _selected(self) -> Claim | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Expense Claims",
                                  "Select a claim first.",
                                  parent=self.frame)
            return None
        return data.get_claim(int(sel[0]))

    def _selected_line(self) -> ClaimLine | None:
        sel = self.lines.selection()
        if not sel:
            messagebox.showinfo("Expense Claims",
                                  "Select a line first.",
                                  parent=self.frame)
            return None
        return data.get_line(int(sel[0]))

    def _new(self) -> None:
        if ClaimEditor(self.frame).result is not None:
            self.refresh()

    def _edit(self) -> None:
        c = self._selected()
        if c and ClaimEditor(
                self.frame, claim=c).result is not None:
            self.refresh()

    def _add_line(self) -> None:
        c = self._selected()
        if not c:
            return
        if LineEditor(self.frame,
                          claim_id=c.claim_id).result is not None:
            self.refresh()
            self._show_lines()

    def _edit_line(self) -> None:
        ln = self._selected_line()
        if ln and LineEditor(
                self.frame, claim_id=ln.claim_id,
                line=ln).result is not None:
            self.refresh()
            self._show_lines()

    def _delete_line(self) -> None:
        ln = self._selected_line()
        if not ln:
            return
        if not messagebox.askyesno(
                "Expense Claims",
                f"Delete line #{ln.line_id}?",
                parent=self.frame):
            return
        data.delete_line(ln.line_id)
        self.refresh()
        self._show_lines()

    def _run(self, action, *args, **kwargs) -> None:
        c = self._selected()
        if not c:
            return
        try:
            action(c.claim_id, *args, **kwargs)
        except ValidationError as e:
            messagebox.showerror("Expense Claims", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _submit(self) -> None:
        self._run(data.submit)

    def _review(self) -> None:
        self._run(data.begin_review)

    def _approve(self) -> None:
        c = self._selected()
        if not c:
            return
        by = _prompt_text(self.frame, "Approved by",
                            initial=c.approved_by or "")
        try:
            data.approve(c.claim_id, approved_by=by or None)
        except ValidationError as e:
            messagebox.showerror("Expense Claims", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _reject(self) -> None:
        c = self._selected()
        if not c:
            return
        reason = _prompt_text(self.frame, "Rejection reason",
                                initial=c.rejection_reason
                                          or "")
        try:
            data.reject(c.claim_id, reason=reason or None)
        except ValidationError as e:
            messagebox.showerror("Expense Claims", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _pay(self) -> None:
        c = self._selected()
        if not c:
            return
        ref = _prompt_text(self.frame, "Payment reference",
                             initial=c.payment_reference
                                       or "")
        try:
            data.pay(c.claim_id,
                        payment_reference=ref or None)
        except ValidationError as e:
            messagebox.showerror("Expense Claims", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _cancel(self) -> None:
        self._run(data.cancel)

    def _set_status(self) -> None:
        c = self._selected()
        if not c:
            return
        new = _prompt_choice(self.frame, "New status",
                                list(CLAIM_STATUSES),
                                default=c.status)
        if not new:
            return
        try:
            data.set_status(c.claim_id, new)
        except ValidationError as e:
            messagebox.showerror("Expense Claims", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _delete(self) -> None:
        c = self._selected()
        if not c:
            return
        if not messagebox.askyesno(
                "Expense Claims",
                f"Delete claim #{c.claim_id}?",
                parent=self.frame):
            return
        data.delete_claim(c.claim_id)
        self.refresh()


class SummaryTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Summary")
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="left")
        self.text = tk.Text(self.frame, wrap="word",
                              font=("TkFixedFont", 10))
        self.text.pack(fill="both", expand=True, padx=8,
                          pady=(4, 8))
        self.refresh()

    def refresh(self) -> None:
        s = data.summary()
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("end", "Expense Claims Summary\n")
        self.text.insert("end", "=" * 60 + "\n\n")
        self.text.insert("end",
                            f"Total claims         : {s.total_claims}\n"
                            f"Drafts               : {s.drafts}\n"
                            f"Submitted            : {s.submitted}\n"
                            f"Under review         : {s.under_review}\n"
                            f"Approved             : {s.approved}\n"
                            f"Paid                 : {s.paid}\n"
                            f"Rejected             : {s.rejected}\n"
                            f"Cancelled            : {s.cancelled}\n"
                            f"Distinct claimants   : {s.distinct_claimants}\n\n"
                            f"Total value          : £{s.total_value:,.2f}\n"
                            f"Awaiting payment     : £{s.awaiting_payment_value:,.2f}\n"
                            f"Paid value           : £{s.paid_value:,.2f}\n\n")
        self.text.insert("end", "By category:\n")
        for k in CATEGORIES:
            n = s.by_category.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<22}: {n}\n")
        self.text.insert("end", "\nBy claimant type:\n")
        for k in CLAIMANT_TYPES:
            n = s.by_claimant_type.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<14}: {n}\n")
        self.text.insert("end", "\nBy status:\n")
        for k in CLAIM_STATUSES:
            n = s.by_status.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<14}: {n}\n")
        self.text.insert("end", "\nBy payment method:\n")
        for k in PAYMENT_METHODS:
            n = s.by_payment_method.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<14}: {n}\n")
        self.text.config(state="disabled")


# ── Editors ──────────────────────────────────────────────

class ClaimEditor:
    def __init__(self, parent, *,
                 claim: Claim | None = None) -> None:
        self.claim = claim
        self.result: Claim | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(
            f"Edit claim #{claim.claim_id}"
            if claim else "New claim")
        self.win.geometry("860x720")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        self._build()
        if claim:
            self._load()
        self.win.wait_window()

    def _build(self) -> None:
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        body.grid_columnconfigure(3, weight=1)
        self.vars: dict[str, tk.Variable] = {}
        self.bools: dict[str, tk.BooleanVar] = {}
        self.texts: dict[str, tk.Text] = {}

        def entry(row, col, label, key, width=22):
            ttk.Label(body, text=label).grid(
                row=row, column=col, sticky="w",
                padx=4, pady=2)
            v = tk.StringVar()
            self.vars[key] = v
            ttk.Entry(body, textvariable=v, width=width).grid(
                row=row, column=col + 1, sticky="ew",
                padx=4, pady=2)

        def combo(row, col, label, key, values, width=22):
            ttk.Label(body, text=label).grid(
                row=row, column=col, sticky="w",
                padx=4, pady=2)
            v = tk.StringVar()
            self.vars[key] = v
            ttk.Combobox(body, textvariable=v, values=values,
                          state="readonly", width=width).grid(
                row=row, column=col + 1, sticky="ew",
                padx=4, pady=2)

        entry(0, 0, "Claim ref*", "claim_ref")
        combo(0, 2, "Status*", "status", CLAIM_STATUSES)
        combo(1, 0, "Claimant type*", "claimant_type",
                 CLAIMANT_TYPES)
        entry(1, 2, "Claimant id*", "claimant_id")
        entry(2, 0, "Claimant name", "claimant_name")
        entry(2, 2, "Department", "department")
        entry(3, 0, "Title*", "title", width=48)
        combo(4, 0, "Category*", "category", CATEGORIES)
        combo(4, 2, "Payment method*", "payment_method",
                 PAYMENT_METHODS)
        entry(5, 0, "Purpose", "purpose", width=48)
        entry(6, 0, "Incurred from", "incurred_from")
        entry(6, 2, "Incurred to", "incurred_to")

        flags = ttk.LabelFrame(body, text="Flags")
        flags.grid(row=7, column=0, columnspan=4,
                      sticky="ew", padx=4, pady=(8, 4))
        v = tk.BooleanVar()
        self.bools["receipts_attached"] = v
        ttk.Checkbutton(flags, text="Receipts attached",
                          variable=v).grid(
            row=0, column=0, sticky="w", padx=6, pady=4)

        row = 8
        for key, label, h in (
                ("description", "Description", 4),
                ("notes",       "Notes", 3),
        ):
            ttk.Label(body, text=label).grid(
                row=row, column=0, sticky="nw",
                padx=4, pady=(6, 2))
            t = tk.Text(body, height=h, width=72, wrap="word")
            t.grid(row=row, column=1, columnspan=3,
                     sticky="ew", padx=4, pady=(6, 2))
            self.texts[key] = t
            row += 1

        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="right",
                                               padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")

        self.vars["claimant_type"].set(DEFAULT_CLAIMANT_TYPE)
        self.vars["category"].set(DEFAULT_CATEGORY)
        self.vars["payment_method"].set(DEFAULT_PAYMENT_METHOD)
        self.vars["status"].set(DEFAULT_CLAIM_STATUS)

    def _load(self) -> None:
        c = self.claim
        assert c is not None
        for key in ("claim_ref", "claimant_type",
                     "claimant_id", "claimant_name",
                     "department", "title", "category",
                     "payment_method", "purpose",
                     "incurred_from", "incurred_to",
                     "status"):
            self.vars[key].set(getattr(c, key) or "")
        self.bools["receipts_attached"].set(
            c.receipts_attached)
        for k in self.texts:
            self.texts[k].delete("1.0", "end")
            self.texts[k].insert("1.0", getattr(c, k) or "")

    def _save(self) -> None:
        payload: dict = {}
        for k, v in self.vars.items():
            payload[k] = v.get().strip()
        for k, b in self.bools.items():
            payload[k] = b.get()
        for k, t in self.texts.items():
            payload[k] = t.get("1.0", "end").rstrip()
        try:
            if self.claim:
                self.result = data.update_claim(
                    self.claim.claim_id, payload)
            else:
                self.result = data.create_claim(payload)
        except ValidationError as exc:
            messagebox.showerror("Expense Claims", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


class LineEditor:
    def __init__(self, parent, *,
                 claim_id: int,
                 line: ClaimLine | None = None) -> None:
        self.claim_id = claim_id
        self.line = line
        self.result: ClaimLine | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(
            f"Edit line #{line.line_id}"
            if line else f"New line for claim #{claim_id}")
        self.win.geometry("720x600")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        self._build()
        if line:
            self._load()
        self.win.wait_window()

    def _build(self) -> None:
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        body.grid_columnconfigure(3, weight=1)
        self.vars: dict[str, tk.Variable] = {}
        self.texts: dict[str, tk.Text] = {}

        def entry(row, col, label, key, width=22):
            ttk.Label(body, text=label).grid(
                row=row, column=col, sticky="w",
                padx=4, pady=2)
            v = tk.StringVar()
            self.vars[key] = v
            ttk.Entry(body, textvariable=v, width=width).grid(
                row=row, column=col + 1, sticky="ew",
                padx=4, pady=2)

        def combo(row, col, label, key, values, width=22):
            ttk.Label(body, text=label).grid(
                row=row, column=col, sticky="w",
                padx=4, pady=2)
            v = tk.StringVar()
            self.vars[key] = v
            ttk.Combobox(body, textvariable=v, values=values,
                          state="readonly", width=width).grid(
                row=row, column=col + 1, sticky="ew",
                padx=4, pady=2)

        entry(0, 0, "Incurred on*", "incurred_on")
        combo(0, 2, "Category*", "category", CATEGORIES)
        entry(1, 0, "Description", "description", width=48)
        entry(2, 0, "Supplier", "supplier")
        entry(2, 2, "Receipt ref", "receipt_ref")
        entry(3, 0, "Quantity", "quantity")
        entry(3, 2, "Unit amount (£)", "unit_amount")
        entry(4, 0, "Mileage miles", "mileage_miles")
        entry(4, 2, "Mileage rate (£/mile)",
                 "mileage_rate")
        entry(5, 0, "VAT amount (£)", "vat_amount")

        ttk.Label(body, text="Notes").grid(
            row=6, column=0, sticky="nw",
            padx=4, pady=(6, 2))
        t = tk.Text(body, height=4, width=60, wrap="word")
        t.grid(row=6, column=1, columnspan=3, sticky="ew",
                  padx=4, pady=(6, 2))
        self.texts["notes"] = t

        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="right",
                                               padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")

        self.vars["category"].set(DEFAULT_CATEGORY)
        self.vars["quantity"].set("1")
        self.vars["unit_amount"].set("0")
        self.vars["vat_amount"].set("0")

    def _load(self) -> None:
        ln = self.line
        assert ln is not None
        for key in ("incurred_on", "category", "description",
                     "supplier", "receipt_ref"):
            self.vars[key].set(getattr(ln, key) or "")
        self.vars["quantity"].set(str(ln.quantity))
        self.vars["unit_amount"].set(str(ln.unit_amount))
        self.vars["mileage_miles"].set(
            str(ln.mileage_miles or ""))
        self.vars["mileage_rate"].set(
            str(ln.mileage_rate or ""))
        self.vars["vat_amount"].set(str(ln.vat_amount))
        self.texts["notes"].delete("1.0", "end")
        self.texts["notes"].insert("1.0", ln.notes or "")

    def _save(self) -> None:
        payload: dict = {}
        for k, v in self.vars.items():
            payload[k] = v.get().strip()
        for k, t in self.texts.items():
            payload[k] = t.get("1.0", "end").rstrip()
        try:
            if self.line:
                self.result = data.update_line(
                    self.line.line_id, payload)
            else:
                self.result = data.add_line(self.claim_id,
                                                    payload)
        except ValidationError as exc:
            messagebox.showerror("Expense Claims", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


def _prompt_text(parent, title: str, *,
                  initial: str = "") -> str | None:
    win = tk.Toplevel(parent)
    win.title(title); win.geometry("420x140")
    win.transient(parent); win.after_idle(win.grab_set)
    ttk.Label(win, text=title).pack(anchor="w", padx=8, pady=8)
    var = tk.StringVar(value=initial)
    ttk.Entry(win, textvariable=var).pack(fill="x", padx=8)
    result: dict = {"value": None}

    def ok() -> None:
        result["value"] = var.get().strip()
        win.destroy()

    bar = ttk.Frame(win)
    bar.pack(fill="x", padx=8, pady=12)
    ttk.Button(bar, text="OK", command=ok).pack(side="right",
                                                    padx=4)
    ttk.Button(bar, text="Cancel",
                command=win.destroy).pack(side="right")
    win.wait_window()
    return result["value"]


def _prompt_choice(parent, title: str, options: list[str], *,
                    default: str | None = None) -> str | None:
    win = tk.Toplevel(parent)
    win.title(title); win.geometry("360x140")
    win.transient(parent); win.after_idle(win.grab_set)
    ttk.Label(win, text=title).pack(anchor="w", padx=8, pady=8)
    var = tk.StringVar(
        value=default or (options[0] if options else ""))
    ttk.Combobox(win, textvariable=var, values=options,
                  state="readonly").pack(fill="x", padx=8)
    result: dict = {"value": None}

    def ok() -> None:
        result["value"] = var.get()
        win.destroy()

    bar = ttk.Frame(win)
    bar.pack(fill="x", padx=8, pady=12)
    ttk.Button(bar, text="OK", command=ok).pack(side="right",
                                                    padx=4)
    ttk.Button(bar, text="Cancel",
                command=win.destroy).pack(side="right")
    win.wait_window()
    return result["value"]


__all__ = ["open_expense_claims_window"]
