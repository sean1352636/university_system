"""Budgets screen (new in the rebuild - there was no budgets window before).

A financial-year picker over seven tabs:

* **Cost centres** - cost centres (name, type, holder, budget, committed,
  spent, remaining) and the selected centre's budget lines (code,
  description, allocation, virements, budget, committed, spent, remaining,
  % used; over-budget lines red, past the warning amber), with New / Edit /
  Delete centre and line, Profile…, Raise order…, Add spend…, Virement…,
  History and the CSV exports.
* **My budgets** - the cost centres the signed-in person holds.
* **Orders** (commitments), **Spend** and **Virements** - each with its
  actions; virements are approved by the "from" budget's holder (their own
  requests too) or by another budget editor.
* **Variance** - the monthly profile against actual spend, by line, cost
  centre or the whole year.
* **Years & settings** - financial years (new, close / reopen, roll forward)
  and the year-start month and warning percentage.

The rules are in :mod:`modules.finance.domain.budgets`.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Any

from education_system.platform.delivery.gui.parented_dialogs import filedialog, messagebox
from education_system.systems.secondary.modules.finance.domain import budgets as B
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.gui.components import widgets as W

logger = logging.getLogger(__name__)
_ERRORS = W.ERRORS
_form = W.form_dialog
_TAGS = {**W.STANDARD_TAGS, "over": {"background": "#fde2e2"},
         "warn": {"background": "#fff4d6"}}
_LINE_COLUMNS = [("code", "Code", 90), ("desc", "Description", 200),
                 ("alloc", "Allocation", 95), ("vin", "Vired in", 85), ("vout", "Vired out", 85),
                 ("budget", "Budget", 95), ("committed", "Committed", 95),
                 ("spent", "Spent", 95), ("remaining", "Remaining", 95), ("used", "Used", 55)]


def _tree(parent, columns, height: int = 10, select: str = "browse") -> ttk.Treeview:
    return W.tree(parent, columns, height=height, select=select,
                  stretch={"desc", "name", "description", "reason"}, tags=_TAGS)


def _holders() -> list[str]:
    try:
        return [f"{s['display_name']} ({s['username']})" for s in accounts.staff_logins()]
    except Exception:  # noqa: BLE001 - the holder can still be typed
        return []


def _holder_label(username: str | None) -> str:
    if not username:
        return ""
    return f"{B.staff_name(username)} ({username})"


def _pos_values(p: B.Position) -> tuple:
    return (p.code, p.description, B.money(p.allocation), B.money(p.virements_in),
            B.money(p.virements_out), B.money(p.budget), B.money(p.committed),
            B.money(p.spent), B.money(p.remaining), f"{p.used_percent}%")


class BudgetsPage:
    TABS = ("Cost centres", "My budgets", "Orders", "Spend", "Virements", "Variance",
            "Years & settings")

    def __init__(self, parent: ttk.Frame, *, principal: Principal, state: dict) -> None:
        self.parent, self.principal, self.state = parent, principal, state
        self.editor = B.is_editor(principal)
        activity_log.record("budgets.view")
        head = ttk.Frame(parent)
        head.pack(fill="x")
        ttk.Label(head, text="Budgets", font=("", 16, "bold")).pack(side="left")
        ttk.Label(head, text="   Financial year:").pack(side="left")
        self.year = tk.StringVar(value=state.get("year") or B.current_year_label() or "")
        self.year_box = ttk.Combobox(head, textvariable=self.year, state="readonly", width=10)
        self.year_box.pack(side="left", padx=4)
        self.year_box.bind("<<ComboboxSelected>>", lambda _e: self.refresh_all())
        self.summary_var = tk.StringVar()
        ttk.Label(parent, textvariable=self.summary_var, foreground="#666").pack(
            anchor="w", pady=(2, 6))
        self.book = ttk.Notebook(parent)
        self.book.pack(fill="both", expand=True)
        self.tabs = {n: ttk.Frame(self.book, padding=8) for n in self.TABS}
        for n, f in self.tabs.items():
            self.book.add(f, text=n)
        self._built: set[str] = set()
        self._years()
        default = "Cost centres" if self.editor else "My budgets"
        start = state.get("tab") if state.get("tab") in self.TABS else (
            default if default in self.TABS else self.TABS[0])
        self.book.select(self.TABS.index(start))
        self.book.bind("<<NotebookTabChanged>>", self._on_tab)
        self._on_tab()

    # ── helpers ──────────────────────────────────────────────────────

    def _top(self):
        return self.parent.winfo_toplevel()

    def _err(self, title: str, e: Exception) -> None:
        messagebox.showerror(title, W.problems(e), parent=self._top())

    def _info(self, title: str, text: str) -> None:
        messagebox.showinfo(title, text, parent=self._top())

    def _button(self, bar, text: str, command, enabled: bool = True) -> ttk.Button:
        b = ttk.Button(bar, text=text, command=command)
        if not enabled:
            b.state(["disabled"])
        b.pack(side="left", padx=2)
        return b

    def _years(self) -> None:
        labels = [y.year_label for y in B.list_years()]
        self.year_box.configure(values=labels)
        if self.year.get() not in labels:
            self.year.set(B.current_year_label() or "")

    def _on_tab(self, _e=None) -> None:
        name = self.TABS[self.book.index(self.book.select())]
        self.state["tab"] = name
        if name not in self._built:
            self._built.add(name)
            getattr(self, "_build_" + self._key(name))(self.tabs[name])
        getattr(self, "refresh_" + self._key(name))()
        self._header()

    @staticmethod
    def _key(name: str) -> str:
        return {"Cost centres": "centres", "My budgets": "mine", "Orders": "orders",
                "Spend": "spend", "Virements": "virements", "Variance": "variance",
                "Years & settings": "years"}[name]

    def refresh_all(self) -> None:
        self.state["year"] = self.year.get()
        for name in self._built:
            getattr(self, "refresh_" + self._key(name))()
        self._header()

    def _header(self) -> None:
        y = self.year.get()
        if not y:
            self.summary_var.set("No financial year yet - add one under Years & settings.")
            return
        try:
            ps = B.positions(y, actor=self.principal)
            over = B.overspends(y, actor=self.principal)
            year = B.get_year(y)
        except _ERRORS:
            return
        self.summary_var.set(
            f"{year.year_label} ({year.start_date} to {year.end_date}, {year.status})    "
            f"Budget: {B.money(sum(p.budget for p in ps))}    "
            f"Committed: {B.money(sum(p.committed for p in ps))}    "
            f"Spent: {B.money(sum(p.spent for p in ps))}    "
            f"Remaining: {B.money(sum(p.remaining for p in ps))}    "
            f"Over budget: {sum(1 for _p, s in over if s == 'over')}    "
            f"Warnings: {sum(1 for _p, s in over if s == 'warn')}")

    def _line_choices(self) -> dict[str, int]:
        """'CODE - Centre: description' -> line id, for lines this person sees."""
        return {f"{ln.code} - {ln.centre_name}: {ln.description}": ln.line_id
                for ln in B.list_lines(year=self.year.get() or None, actor=self.principal)}

    def _insert_pos(self, tree: ttk.Treeview, p: B.Position, warn: int) -> None:
        state = p.state(warn)
        tree.insert("", "end", iid=str(p.line_id), values=_pos_values(p),
                    tags=(state,) if state != "ok" else ())

    # ── Cost centres ─────────────────────────────────────────────────

    def _build_centres(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        for text, cmd in (("New centre…", self.new_centre), ("Edit centre…", self.edit_centre),
                          ("Delete centre", self.delete_centre)):
            self._button(bar, text, cmd, self.editor)
        ttk.Label(bar, text="  Type:").pack(side="left")
        self.kind = tk.StringVar(value=self.state.get("kind", ""))
        cb = ttk.Combobox(bar, textvariable=self.kind, values=("", *B.CENTRE_KINDS),
                          state="readonly", width=12)
        cb.pack(side="left", padx=4)
        cb.bind("<<ComboboxSelected>>", lambda _e: self.refresh_centres())
        self._button(bar, "Refresh", self.refresh_all)
        self.centre_tree = _tree(tab, [("name", "Cost centre", 200), ("kind", "Type", 100),
                                       ("holder", "Holder", 160), ("budget", "Budget", 100),
                                       ("committed", "Committed", 100),
                                       ("spent", "Spent", 100), ("remaining", "Remaining", 100),
                                       ("active", "Active", 60)], height=8)
        self.centre_tree.bind("<<TreeviewSelect>>", lambda _e: self.refresh_lines())
        bar2 = ttk.Frame(tab)
        bar2.pack(fill="x", pady=(8, 4))
        for text, cmd in (("New line…", self.new_line), ("Edit line…", self.edit_line),
                          ("Delete line", self.delete_line), ("Profile…", self.edit_profile)):
            self._button(bar2, text, cmd, self.editor)
        self._button(bar2, "Raise order…", lambda: self.raise_order(self._sel_line()))
        self._button(bar2, "Add spend…", lambda: self.add_spend(self._sel_line()), self.editor)
        self._button(bar2, "Virement…", lambda: self.request_virement(self._sel_line()))
        bar3 = ttk.Frame(tab)
        bar3.pack(fill="x", pady=(0, 4))
        self._button(bar3, "History", self.history)
        self._button(bar3, "Export CSV…", self.export)
        self._button(bar3, "Export transactions…", self.export_transactions)
        self.line_tree = _tree(tab, _LINE_COLUMNS, height=8)
        self.line_tree.bind("<Double-1>", lambda _e: self.edit_line() if self.editor else None)
        self.centres: dict[str, B.CostCentre] = {}

    def refresh_centres(self) -> None:
        keep = self.centre_tree.selection()
        self.state["kind"] = self.kind.get()
        self.centre_tree.delete(*self.centre_tree.get_children())
        self.centres = {}
        y = self.year.get()
        if y:
            try:
                rows = B.list_centres(y, actor=self.principal, kind=self.kind.get() or None)
                totals = {t["centre_id"]: t for t in B.centre_totals(y, actor=self.principal)}
            except _ERRORS as e:
                self._err("Budgets", e)
                return
            for c in rows:
                self.centres[str(c.centre_id)] = c
                t = totals.get(c.centre_id, {"budget": 0, "committed": 0, "spent": 0,
                                             "remaining": 0, "over": 0})
                tags = ("over",) if t["over"] else (("muted",) if not c.active else ())
                self.centre_tree.insert("", "end", iid=str(c.centre_id), tags=tags, values=(
                    c.name, c.kind, _holder_label(c.holder), B.money(t["budget"]),
                    B.money(t["committed"]), B.money(t["spent"]), B.money(t["remaining"]),
                    "yes" if c.active else "no"))
        if keep and self.centre_tree.exists(keep[0]):
            self.centre_tree.selection_set(keep[0])
        self.refresh_lines()

    def refresh_lines(self) -> None:
        self.line_tree.delete(*self.line_tree.get_children())
        c = self._sel_centre(quiet=True)
        if c is None:
            return
        warn = B.settings()["warn_percent"]
        for p in B.positions(c.year_label, centre_id=c.centre_id):
            self._insert_pos(self.line_tree, p, warn)

    def _sel_centre(self, quiet: bool = False) -> B.CostCentre | None:
        sel = self.centre_tree.selection()
        if not sel:
            if not quiet:
                self._info("Budgets", "Select a cost centre first.")
            return None
        return self.centres[sel[0]]

    def _sel_line(self) -> int | None:
        sel = self.line_tree.selection() if "Cost centres" in self._built else ()
        return int(sel[0]) if sel else None

    def _centre_fields(self, c: B.CostCentre | None) -> list:
        return [("name", "Name*", c.name if c else "", None),
                ("kind", "Type", c.kind if c else B.DEFAULT_KIND, B.CENTRE_KINDS),
                ("holder", "Budget holder", _holder_label(c.holder) if c else "",
                 ("edit", ["", *_holders()])),
                ("active", "Active", bool(c.active) if c else True, "check"),
                ("notes", "Notes", c.notes if c else "", "text")]

    def new_centre(self) -> None:
        def save(v):
            B.create_centre({**v, "year": self.year.get()}, actor=self.principal)
            self.refresh_all()
        _form(self.parent, f"New cost centre - {self.year.get()}", self._centre_fields(None),
              save, note="Departments, pastoral, premises, trips, CPD ... The holder sees "
                         "this cost centre and approves its expense claims.")

    def edit_centre(self) -> None:
        c = self._sel_centre()
        if c is None:
            return

        def save(v):
            if v["holder"] == _holder_label(c.holder):
                v.pop("holder")
            B.update_centre(c.centre_id, v, actor=self.principal)
            self.refresh_all()
        _form(self.parent, f"Edit {c.name}", self._centre_fields(c), save)

    def delete_centre(self) -> None:
        c = self._sel_centre()
        if c and messagebox.askyesno("Delete cost centre", f"Delete {c.name} and its lines?",
                                     parent=self._top()):
            try:
                B.delete_centre(c.centre_id, actor=self.principal)
            except _ERRORS as e:
                self._err("Delete cost centre", e)
                return
            self.refresh_all()

    def _line_fields(self, ln: B.Line | None) -> list:
        return [("code", "Code*", ln.code if ln else "", None),
                ("description", "Description*", ln.description if ln else "", None),
                ("allocation", "Allocation (£)", B.pounds(ln.allocation_pence) if ln else "0",
                 None),
                ("notes", "Notes", ln.notes if ln else "", "text")]

    def new_line(self) -> None:
        c = self._sel_centre()
        if c is None:
            return

        def save(v):
            B.create_line(c.centre_id, v, actor=self.principal)
            self.refresh_all()
        _form(self.parent, f"New budget line - {c.name}", self._line_fields(None), save,
              note="Codes are unique within the year (e.g. MAT-RES).")

    def edit_line(self) -> None:
        lid = self._sel_line()
        if lid is None:
            self._info("Budgets", "Select a budget line first.")
            return
        ln = B.get_line(lid)

        def save(v):
            B.update_line(ln.line_id, v, actor=self.principal)
            self.refresh_all()
        _form(self.parent, f"Edit line {ln.code}", self._line_fields(ln), save)

    def delete_line(self) -> None:
        lid = self._sel_line()
        if lid is None:
            self._info("Budgets", "Select a budget line first.")
            return
        ln = B.get_line(lid)
        if messagebox.askyesno("Delete line", f"Delete budget line {ln.code}?",
                               parent=self._top()):
            try:
                B.delete_line(ln.line_id, actor=self.principal)
            except _ERRORS as e:
                self._err("Delete line", e)
                return
            self.refresh_all()

    def edit_profile(self) -> None:
        lid = self._sel_line()
        if lid is None:
            self._info("Profile", "Select a budget line first.")
            return
        ln = B.get_line(lid)
        ms = B.months(ln.year_label)
        cur = B.profile(lid)
        fields = [(f"m{i}", B.month_name(m), B.pounds(cur[i]), None) for i, m in enumerate(ms)]
        fields.append(("even", "Clear - spread evenly", False, "check"))

        def save(v):
            B.set_profile(lid, None if v["even"] else [v[f"m{i}"] for i in range(12)],
                          actor=self.principal)
            self.refresh_all()
        _form(self.parent, f"Monthly profile - {ln.code}", fields, save,
              note="How the budget is expected to be spent through the year. The amounts "
                   "are kept as proportions, so the profile follows the budget after a "
                   "virement.")

    def history(self) -> None:
        lid = self._sel_line()
        c = self._sel_centre(quiet=True)
        rows = B.history(line_id=lid) if lid else (B.history(centre_id=c.centre_id) if c else
                                                   B.history(year=self.year.get()))
        W.text_window(self.parent, "Budget history", "\n".join(
            f"{h['at']}  {h['actor']:<12} {h['action']:<18} "
            + ", ".join(f"{k}={v}" for k, v in h["detail"].items()) for h in rows)
            or "No changes recorded.")

    def _save_csv(self, name: str) -> str:
        return filedialog.asksaveasfilename(parent=self._top(), defaultextension=".csv",
                                            filetypes=[("CSV", "*.csv")], initialfile=name)

    def export(self) -> None:
        c = self._sel_centre(quiet=True)
        path = self._save_csv(f"budgets_{self.year.get()}.csv")
        if path:
            try:
                n = B.export_csv(path, actor=self.principal, year=self.year.get(),
                                 centre_id=c.centre_id if c else None)
            except _ERRORS as e:
                self._err("Export", e)
                return
            self._info("Export", f"Exported {n} budget line(s).")

    def export_transactions(self) -> None:
        c = self._sel_centre(quiet=True)
        path = self._save_csv(f"budget_transactions_{self.year.get()}.csv")
        if path:
            try:
                n = B.export_transactions_csv(path, actor=self.principal, year=self.year.get(),
                                              centre_id=c.centre_id if c else None)
            except _ERRORS as e:
                self._err("Export", e)
                return
            self._info("Export", f"Exported {n} row(s).")

    # ── shared money forms ───────────────────────────────────────────

    def _with_warnings(self, line_id: int, amount: Any) -> None:
        """Ask about an overspend first; "No" keeps the form open."""
        problems: list[str] = []
        n = B.to_pence(amount, "Amount", problems)
        if problems or not n or n < 0:
            return
        warnings = B.check_spend(line_id, n)
        if warnings and not messagebox.askyesno("Budgets", "\n\n".join(warnings)
                                                + "\n\nGo ahead?", parent=self._top()):
            raise B.ValidationError(["Not saved yet - change the amount, or Save again and "
                                     "answer Yes"])

    def raise_order(self, line_id: int | None = None) -> None:
        choices = self._line_choices()
        if not choices:
            self._info("Raise order", "No budget lines you can order against in this year.")
            return
        first = next((k for k, v in choices.items() if v == line_id), "")

        def save(v):
            lid = choices.get(v.pop("line"))
            if lid is None:
                raise B.ValidationError(["Choose the budget line"])
            self._with_warnings(lid, v["amount"])
            B.add_commitment(lid, v, actor=self.principal)
            self.refresh_all()
        _form(self.parent, "Raise order (commitment)", [
            ("line", "Budget line", first, list(choices)),
            ("description", "Description*", "", None), ("supplier", "Supplier", "", None),
            ("order_ref", "Order ref", "", None), ("amount", "Amount (£)*", "", None),
            ("raised_on", "Order date (blank = today)", "", None)], save,
            note="An order counts against the budget until it is paid or cancelled.")

    def add_spend(self, line_id: int | None = None) -> None:
        choices = self._line_choices()
        if not choices:
            self._info("Add spend", "No budget lines in this year.")
            return
        first = next((k for k, v in choices.items() if v == line_id), "")

        def save(v):
            lid = choices.get(v.pop("line"))
            if lid is None:
                raise B.ValidationError(["Choose the budget line"])
            self._with_warnings(lid, v["amount"])
            B.add_spend(lid, v, actor=self.principal)
            self.refresh_all()
        _form(self.parent, "Add spend", [
            ("line", "Budget line", first, list(choices)),
            ("description", "Description*", "", None), ("supplier", "Supplier", "", None),
            ("reference", "Invoice / reference", "", None),
            ("amount", "Amount (£, negative = refund)*", "", None),
            ("spend_date", "Date (blank = today)", "", None)], save)

    def request_virement(self, line_id: int | None = None) -> None:
        mine = self._line_choices()
        everything = {f"{ln.code} - {ln.centre_name}: {ln.description}": ln.line_id
                      for ln in B.list_lines(year=self.year.get() or None)}
        if not mine:
            self._info("Virement", "No budget lines you can move money from in this year.")
            return
        first = next((k for k, v in mine.items() if v == line_id), "")

        def save(v):
            B.request_virement({"from_line_id": mine.get(v["from"]),
                                "to_line_id": everything.get(v["to"]),
                                "amount": v["amount"], "reason": v["reason"]},
                               actor=self.principal)
            self.refresh_all()
        _form(self.parent, "Request a virement", [
            ("from", "From line", first, list(mine)), ("to", "To line", "", list(everything)),
            ("amount", "Amount (£)*", "", None), ("reason", "Reason*", "", "text")], save,
            note="Another budget editor approves it; the money moves only then.")

    # ── My budgets ───────────────────────────────────────────────────

    def _build_mine(self, tab) -> None:
        ttk.Label(tab, text="The cost centres you hold.", foreground="#555").pack(anchor="w")
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=4)
        self._button(bar, "Raise order…", lambda: self.raise_order(self._mine_line()))
        self._button(bar, "Virement…", lambda: self.request_virement(self._mine_line()))
        self.mine_tree = _tree(tab, [("centre", "Cost centre", 160), *_LINE_COLUMNS],
                               height=14)

    def _mine_line(self) -> int | None:
        sel = self.mine_tree.selection()
        return int(sel[0]) if sel and sel[0].isdigit() else None

    def refresh_mine(self) -> None:
        self.mine_tree.delete(*self.mine_tree.get_children())
        warn = B.settings()["warn_percent"]
        try:
            groups = B.my_centres(self.principal, self.year.get() or None)
        except _ERRORS as e:
            self._err("My budgets", e)
            return
        for g in groups:
            c = g["centre"]
            self.mine_tree.insert("", "end", iid=f"c{c.centre_id}", values=(
                c.name, "", "Total", "", "", "", B.money(g["budget"]), B.money(g["committed"]),
                B.money(g["spent"]), B.money(g["remaining"]), ""),
                tags=("over",) if g["remaining"] < 0 else ("muted",))
            for p in g["lines"]:
                st = p.state(warn)
                self.mine_tree.insert("", "end", iid=str(p.line_id),
                                      values=("", *_pos_values(p)),
                                      tags=(st,) if st != "ok" else ())
        if not groups:
            self.mine_tree.insert("", "end", iid="none", values=(
                "You don't hold a cost centre this year.", *[""] * 10))

    # ── Orders ───────────────────────────────────────────────────────

    def _build_orders(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self.order_status = tk.StringVar(value="Open")
        ttk.Label(bar, text="Status:").pack(side="left")
        cb = ttk.Combobox(bar, textvariable=self.order_status,
                          values=("", *B.COMMITMENT_STATUSES), state="readonly", width=10)
        cb.pack(side="left", padx=4)
        cb.bind("<<ComboboxSelected>>", lambda _e: self.refresh_orders())
        self._button(bar, "Raise order…", self.raise_order)
        self._button(bar, "Paid (settle)…", self.settle_order, self.editor)
        self._button(bar, "Cancel order", self.cancel_order)
        self.order_tree = _tree(tab, [("id", "Id", 50), ("date", "Date", 90),
                                      ("code", "Code", 90), ("centre", "Cost centre", 140),
                                      ("description", "Description", 220),
                                      ("supplier", "Supplier", 120), ("ref", "Order ref", 90),
                                      ("amount", "Amount", 90), ("status", "Status", 80)],
                                height=16)

    def refresh_orders(self) -> None:
        self.order_tree.delete(*self.order_tree.get_children())
        for m in B.list_commitments(year=self.year.get() or None,
                                    status=self.order_status.get() or None,
                                    actor=self.principal):
            self.order_tree.insert("", "end", iid=str(m.commitment_id),
                                   tags=("muted",) if m.status != "Open" else (), values=(
                m.commitment_id, m.raised_on, m.code, m.centre_name, m.description,
                m.supplier or "", m.order_ref or "", B.money(m.amount_pence), m.status))

    def _sel_order(self) -> B.Commitment | None:
        sel = self.order_tree.selection()
        if not sel:
            self._info("Orders", "Select an order first.")
            return None
        return B.get_commitment(int(sel[0]))

    def settle_order(self) -> None:
        m = self._sel_order()
        if m is None:
            return

        def save(v):
            B.settle_commitment(m.commitment_id, actor=self.principal, amount=v["amount"],
                                paid_on=v["paid_on"] or None, reference=v["reference"] or None)
            self.refresh_all()
        _form(self.parent, f"Order #{m.commitment_id} paid", [
            ("amount", "Amount paid (£)", B.pounds(m.amount_pence), None),
            ("paid_on", "Paid on (blank = today)", "", None),
            ("reference", "Invoice / reference", m.order_ref or "", None)], save,
            note="The order stops being a commitment and becomes spend.")

    def cancel_order(self) -> None:
        m = self._sel_order()
        if m and messagebox.askyesno("Cancel order", f"Cancel order #{m.commitment_id} "
                                     f"({B.money(m.amount_pence)})?", parent=self._top()):
            try:
                B.cancel_commitment(m.commitment_id, actor=self.principal)
            except _ERRORS as e:
                self._err("Cancel order", e)
                return
            self.refresh_all()

    # ── Spend ────────────────────────────────────────────────────────

    def _build_spend(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self.spend_source = tk.StringVar()
        ttk.Label(bar, text="Source:").pack(side="left")
        cb = ttk.Combobox(bar, textvariable=self.spend_source, values=("", *B.SPEND_SOURCES),
                          state="readonly", width=14)
        cb.pack(side="left", padx=4)
        cb.bind("<<ComboboxSelected>>", lambda _e: self.refresh_spend())
        self._button(bar, "Add spend…", self.add_spend, self.editor)
        self._button(bar, "Delete entry", self.delete_spend, self.editor)
        self.spend_tree = _tree(tab, [("id", "Id", 50), ("date", "Date", 90),
                                      ("code", "Code", 90), ("centre", "Cost centre", 140),
                                      ("description", "Description", 240),
                                      ("supplier", "Supplier", 120), ("ref", "Reference", 100),
                                      ("amount", "Amount", 90), ("source", "Source", 100)],
                                height=16)

    def refresh_spend(self) -> None:
        self.spend_tree.delete(*self.spend_tree.get_children())
        for s in B.list_spend(year=self.year.get() or None,
                              source=self.spend_source.get() or None, actor=self.principal):
            self.spend_tree.insert("", "end", iid=str(s.spend_id),
                                   tags=("good",) if s.amount_pence < 0 else (), values=(
                s.spend_id, s.spend_date, s.code, s.centre_name, s.description,
                s.supplier or "", s.reference or "", B.money(s.amount_pence),
                s.source.replace("_", " ")))

    def delete_spend(self) -> None:
        sel = self.spend_tree.selection()
        if not sel:
            self._info("Spend", "Select an entry first.")
            return
        if messagebox.askyesno("Delete entry", "Delete the selected spend entry?",
                               parent=self._top()):
            try:
                B.delete_spend(int(sel[0]), actor=self.principal)
            except _ERRORS as e:
                self._err("Delete entry", e)
                return
            self.refresh_all()

    # ── Virements ────────────────────────────────────────────────────

    def _build_virements(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self.vir_status = tk.StringVar(value="Pending")
        ttk.Label(bar, text="Status:").pack(side="left")
        cb = ttk.Combobox(bar, textvariable=self.vir_status, values=("", *B.VIREMENT_STATUSES),
                          state="readonly", width=10)
        cb.pack(side="left", padx=4)
        cb.bind("<<ComboboxSelected>>", lambda _e: self.refresh_virements())
        self._button(bar, "Request…", self.request_virement)
        can_decide = self.editor or B.holds_any(self.principal)   # holders decide their own
        self._button(bar, "Approve", lambda: self.decide("Approved"), can_decide)
        self._button(bar, "Reject…", lambda: self.decide("Rejected"), can_decide)
        self._button(bar, "Cancel", self.cancel_virement)
        self.vir_tree = _tree(tab, [("id", "Id", 50), ("from", "From", 100), ("to", "To", 100),
                                    ("amount", "Amount", 90), ("reason", "Reason", 260),
                                    ("status", "Status", 80), ("by", "Asked by", 100),
                                    ("decided", "Decided by", 100), ("note", "Note", 180)],
                              height=16)

    def refresh_virements(self) -> None:
        self.vir_tree.delete(*self.vir_tree.get_children())
        for v in B.list_virements(self.year.get() or None, status=self.vir_status.get() or None,
                                  actor=self.principal):
            tag = {"Pending": ("warn",), "Approved": ("good",)}.get(v.status, ("muted",))
            self.vir_tree.insert("", "end", iid=str(v.virement_id), tags=tag, values=(
                v.virement_id, v.from_code, v.to_code, B.money(v.amount_pence), v.reason,
                v.status, v.requested_by, v.decided_by or "", v.decision_note or ""))

    def _sel_virement(self) -> int | None:
        sel = self.vir_tree.selection()
        if not sel:
            self._info("Virements", "Select a virement first.")
            return None
        return int(sel[0])

    def decide(self, decision: str) -> None:
        vid = self._sel_virement()
        if vid is None:
            return

        def save(v):
            B.decide_virement(vid, decision, actor=self.principal, note=v["note"])
            self.refresh_all()
        _form(self.parent, f"{'Approve' if decision == 'Approved' else 'Reject'} virement "
                           f"#{vid}", [("note", "Note" + (" (required)" if decision ==
                                                          "Rejected" else ""), "", "text")],
              save, note="You can't decide a virement you asked for.")

    def cancel_virement(self) -> None:
        vid = self._sel_virement()
        if vid is not None:
            try:
                B.cancel_virement(vid, actor=self.principal)
            except _ERRORS as e:
                self._err("Cancel virement", e)
                return
            self.refresh_all()

    # ── Variance ─────────────────────────────────────────────────────

    def _build_variance(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self.var_scope = tk.StringVar(value="(whole year)")
        ttk.Label(bar, text="Show:").pack(side="left")
        self.var_box = ttk.Combobox(bar, textvariable=self.var_scope, state="readonly",
                                    width=50)
        self.var_box.pack(side="left", padx=4)
        self.var_box.bind("<<ComboboxSelected>>", lambda _e: self.refresh_variance())
        ttk.Label(tab, text="Variance = profile - actual: negative means spending ahead of "
                            "the profile.", foreground="#555").pack(anchor="w")
        self.var_tree = _tree(tab, [("month", "Month", 90), ("profiled", "Profiled", 100),
                                    ("actual", "Actual", 100), ("variance", "Variance", 100),
                                    ("cp", "To date: profiled", 120),
                                    ("ca", "To date: actual", 120),
                                    ("cv", "To date: variance", 120)], height=13)
        self._var_keys: dict[str, tuple[str, int] | None] = {}

    def refresh_variance(self) -> None:
        y = self.year.get()
        keys: dict[str, tuple[str, int] | None] = {"(whole year)": None}
        if y:
            for c in B.list_centres(y, actor=self.principal):
                keys[f"Cost centre: {c.name}"] = ("centre", c.centre_id)
            for ln in B.list_lines(year=y, actor=self.principal):
                keys[f"Line: {ln.code} - {ln.description}"] = ("line", ln.line_id)
        self._var_keys = keys
        self.var_box.configure(values=list(keys))
        if self.var_scope.get() not in keys:
            self.var_scope.set("(whole year)")
        self.var_tree.delete(*self.var_tree.get_children())
        if not y:
            return
        pick = keys[self.var_scope.get()]
        try:
            rows = B.variance(y, actor=self.principal,
                              centre_id=pick[1] if pick and pick[0] == "centre" else None,
                              line_id=pick[1] if pick and pick[0] == "line" else None)
        except _ERRORS as e:
            self._err("Variance", e)
            return
        for r in rows:
            self.var_tree.insert("", "end", tags=("bad",) if r["cum_variance"] < 0 else (),
                                 values=(B.month_name(r["month"]), B.money(r["profiled"]),
                                         B.money(r["actual"]), B.money(r["variance"]),
                                         B.money(r["cum_profiled"]), B.money(r["cum_actual"]),
                                         B.money(r["cum_variance"])))

    # ── Years & settings ─────────────────────────────────────────────

    def _build_years(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        for text, cmd in (("New year…", self.new_year), ("Close year", lambda: self.status(
                "Closed")), ("Reopen year", lambda: self.status("Open")),
                ("Roll forward…", self.roll_forward), ("Settings…", self.edit_settings)):
            self._button(bar, text, cmd, self.editor)
        self.settings_var = tk.StringVar()
        ttk.Label(tab, textvariable=self.settings_var, foreground="#555").pack(anchor="w")
        self.year_tree = _tree(tab, [("label", "Year", 90), ("start", "Starts", 100),
                                     ("end", "Ends", 100), ("status", "Status", 80),
                                     ("by", "Set up by", 120)], height=10)

    def refresh_years(self) -> None:
        s = B.settings()
        start = next((k for k, v in B.YEAR_START_PRESETS.items()
                      if v == s["year_start_month"]), f"month {s['year_start_month']}")
        self.settings_var.set(f"New years start: {start}.    Warn when {s['warn_percent']}% of a "
                              "line is committed or spent.")
        self.year_tree.delete(*self.year_tree.get_children())
        for y in B.list_years():
            self.year_tree.insert("", "end", iid=y.year_label,
                                  tags=("muted",) if not y.is_open else (),
                                  values=(y.year_label, y.start_date, y.end_date, y.status,
                                          y.created_by or ""))

    def _sel_year(self) -> str | None:
        sel = self.year_tree.selection()
        if not sel:
            self._info("Years", "Select a year first.")
            return None
        return sel[0]

    def new_year(self) -> None:
        def save(v):
            y = B.create_year(v["start"] or None, actor=self.principal)
            self._years()
            self.year.set(y.year_label)
            self.refresh_all()
        _form(self.parent, "New financial year", [
            ("start", "Calendar year it starts in (blank = this one)", "", None)], save,
            note="It starts on the month in Settings (April for maintained schools, "
                 "September for academies).")

    def status(self, st: str) -> None:
        y = self._sel_year()
        if y and messagebox.askyesno("Years", f"{'Close' if st == 'Closed' else 'Reopen'} "
                                     f"{y}?", parent=self._top()):
            try:
                B.set_year_status(y, st, actor=self.principal)
            except _ERRORS as e:
                self._err("Years", e)
                return
            self.refresh_all()

    def roll_forward(self) -> None:
        y = self._sel_year() or None
        if y is None:
            return

        def save(v):
            r = B.roll_forward(y, actor=self.principal, uplift_percent=v["uplift"] or 0,
                               include_profiles=bool(v["profiles"]))
            self._years()
            self.year.set(r["year"])
            self.refresh_all()
            self._info("Roll forward", f"{r['year']}: {r['centres']} cost centre(s), "
                                       f"{r['lines']} line(s) copied."
                       + (f"\nSkipped (already there): {', '.join(r['skipped'])}"
                          if r["skipped"] else ""))
        _form(self.parent, f"Roll {y} forward", [
            ("uplift", "Uplift allocations by (%)", "0", None),
            ("profiles", "Copy monthly profiles", True, "check")], save,
            note="Active cost centres (with their holders) and lines are copied into the next "
                 "year. Orders and spend are not.")

    def edit_settings(self) -> None:
        s = B.settings()
        presets = list(B.YEAR_START_PRESETS)
        cur = next((k for k, v in B.YEAR_START_PRESETS.items()
                    if v == s["year_start_month"]), str(s["year_start_month"]))

        def save(v):
            B.set_settings({"year_start_month": v["start"], "warn_percent": v["warn"]},
                           actor=self.principal)
            self.refresh_all()
        _form(self.parent, "Budget settings", [
            ("start", "Financial year starts", cur, ("edit", presets)),
            ("warn", "Warn at (% used)", s["warn_percent"], None)], save,
            note="Changing the start month affects years created from now on.")


class MyBudgetsPage(BudgetsPage):
    """A budget holder's own view (no finance-office tabs)."""
    TABS = ("My budgets", "Orders", "Virements", "Variance")


def draw_my_budgets(parent: ttk.Frame, *, principal: Principal, state: dict) -> MyBudgetsPage:
    return MyBudgetsPage(parent, principal=principal, state=state)


def draw_budgets(parent: ttk.Frame, *, principal: Principal, state: dict) -> BudgetsPage:
    return BudgetsPage(parent, principal=principal, state=state)
