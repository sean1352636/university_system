"""Departments tab: budget lines per department per year and
budget-vs-spend (expense claims, trip running costs, receipts as
income) with overspend warnings. Added to the Departments window."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import messagebox

from education_system.systems.sixth_form.domains.finance.domain import (
    finance_calendar as fc,
)
from education_system.systems.sixth_form.domain.staff.departments import (
    department_budgets as db,
)
from education_system.systems.sixth_form.domains.finance.interfaces.gui import (
    _widgets as w,
)


def add_budget_tab(nb: ttk.Notebook) -> "BudgetsTab":
    return BudgetsTab(nb)


class BudgetsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Budget vs Spend")
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Year").pack(side="left")
        self.year = tk.StringVar(value=fc.normalise_year(None))
        ttk.Entry(bar, textvariable=self.year, width=9).pack(side="left",
                                                             padx=4)
        ttk.Label(bar, text="Department").pack(side="left")
        self.dept = tk.StringVar()
        self.dept_cb = ttk.Combobox(bar, textvariable=self.dept, width=30,
                                    state="readonly")
        self.dept_cb.pack(side="left", padx=4)
        self.dept_cb.bind("<<ComboboxSelected>>", lambda _e: self.show())
        for label, cmd in (("Show", self.refresh),
                           ("Add Line…", self.add_line),
                           ("Edit Line…", self.edit_line),
                           ("Delete Line", self.delete_line),
                           ("Copy From Year…", self.copy_year),
                           ("Sync Department Totals", self.sync)):
            ttk.Button(bar, text=label, command=cmd).pack(side="left", padx=2)
        self.warn = ttk.Label(self.frame, text="", foreground="#b00020",
                              wraplength=1300, justify="left")
        self.warn.pack(fill="x", padx=10)
        pane = ttk.PanedWindow(self.frame, orient="vertical")
        pane.pack(fill="both", expand=True, padx=8, pady=8)
        a = ttk.LabelFrame(pane, text="All departments (worst first)")
        pane.add(a, weight=2)
        self.all = w.Table(a, [("#", 40), ("Department", 220),
                               ("Budget", 100), ("Net spend", 100),
                               ("Remaining", 100), ("Used", 70),
                               ("Overspent", 70), ("Warnings", 70)],
                           height=6)
        self.all.pack(fill="both", expand=True, padx=4, pady=4)
        self.all.tree.bind("<<TreeviewSelect>>", self._pick_from_all)
        b = ttk.LabelFrame(pane, text="Selected department: lines vs spend")
        pane.add(b, weight=3)
        self.cats = w.Table(b, [("Category", 180), ("Budget", 100),
                                ("Spend", 100), ("Income", 100),
                                ("Net", 100), ("Remaining", 100),
                                ("Used", 70)], height=6)
        self.cats.pack(fill="x", padx=4, pady=4)
        self.lines = w.Table(b, [("Line #", 60), ("Category", 180),
                                 ("Amount", 100), ("Description", 300),
                                 ("By", 100)], height=4)
        self.lines.pack(fill="x", padx=4, pady=4)
        self.items = w.Table(b, [("Source", 110), ("Ref", 120),
                                 ("Date", 90), ("Category", 160),
                                 ("Description", 360), ("Amount", 90)],
                             height=6)
        self.items.pack(fill="both", expand=True, padx=4, pady=4)
        self.refresh()

    def _depts(self) -> list[tuple[int, str]]:
        return w.call(self.frame, db.list_departments) or []

    def _dept_id(self) -> int | None:
        v = self.dept.get()
        return int(v.split(" — ", 1)[0]) if v else None

    def _year(self) -> str | None:
        return w.call(self.frame, lambda: fc.normalise_year(self.year.get()))

    def refresh(self) -> None:
        self.dept_cb.configure(values=[f"{i} — {n}"
                                       for i, n in self._depts()])
        year = self._year()
        if year is None:
            return
        rows = w.call(self.frame, lambda: db.all_departments(year)) or []
        self.all.set_rows(
            [(r.department_id, r.name, w.money(r.budget),
              w.money(r.net_spend), w.money(r.remaining),
              "—" if r.utilisation_pct is None
              else f"{r.utilisation_pct:.0f}%", "YES" if r.overspent else "",
              r.warnings) for r in rows],
            alert=lambda r: r[6] == "YES")
        warns = w.call(self.frame, lambda: db.overspend_warnings(year)) or []
        self.warn.configure(text="\n".join(f"! {x}" for x in warns[:8]))
        self.show()

    def _pick_from_all(self, _e=None) -> None:
        did = self.all.selected_id()
        if did is None:
            return
        name = dict(self._depts()).get(did, "")
        self.dept.set(f"{did} — {name}")
        self.show()

    def show(self) -> None:
        did, year = self._dept_id(), self._year()
        if did is None or year is None:
            return
        rep = w.call(self.frame, lambda: db.budget_report(did, year))
        if rep is None:
            return
        self.cats.set_rows(
            [(l.category, w.money(l.budget), w.money(l.spend),
              w.money(l.income), w.money(l.net), w.money(l.remaining),
              "—" if l.utilisation_pct is None
              else f"{l.utilisation_pct:.0f}%") for l in rep.lines]
            + [("TOTAL", w.money(rep.total_budget), w.money(rep.total_spend),
                w.money(rep.total_income), w.money(rep.net_spend),
                w.money(rep.remaining),
                "—" if rep.utilisation_pct is None
                else f"{rep.utilisation_pct:.0f}%")],
            alert=lambda r: r[5].startswith("-"))
        self.lines.set_rows(
            [(l.line_id, l.category, w.money(l.amount), l.description or "",
              l.created_by or "")
             for l in db.list_lines(department_id=did, academic_year=year)])
        self.items.set_rows(
            [(i.source, i.ref, i.date or "", i.category, i.description,
              w.money(i.amount)) for i in rep.items])
        extra = rep.warnings + [f"Trip without a running cost: {u}"
                                for u in rep.uncosted_trips]
        if extra:
            self.warn.configure(text="\n".join(f"! {x}" for x in extra[:8]))

    def _need_dept(self) -> int | None:
        did = self._dept_id()
        if did is None:
            messagebox.showinfo("Department", "Choose a department first.",
                                parent=self.frame)
        return did

    def add_line(self) -> None:
        did = self._need_dept()
        if did is None:
            return
        f = w.ask_form(self.frame, "Budget line", [
            ("cat", "Category", "combo", db.BUDGET_CATEGORIES[0],
             db.BUDGET_CATEGORIES),
            ("amount", "Amount", "entry", "", None),
            ("desc", "Description", "entry", "", None)])
        if f and w.call(self.frame, lambda: db.add_line(
                did, academic_year=self.year.get(), category=f["cat"] or "",
                amount=w.num(f["amount"]), description=f["desc"],
                created_by=w.actor() or None)) is not None:
            self.refresh()

    def edit_line(self) -> None:
        lid = w.need_selection(self.frame, self.lines)
        if lid is None:
            return
        row = self.lines.selected() or []
        f = w.ask_form(self.frame, f"Budget line #{lid}", [
            ("cat", "Category", "combo", row[1] if row else "",
             db.BUDGET_CATEGORIES),
            ("amount", "Amount", "entry",
             (row[2] if row else "").replace("£", "").replace(",", ""), None),
            ("desc", "Description", "entry", row[3] if row else "", None)])
        if f and w.call(self.frame, lambda: db.update_line(
                lid, amount=w.num(f["amount"]), category=f["cat"],
                description=f["desc"])) is not None:
            self.refresh()

    def delete_line(self) -> None:
        lid = w.need_selection(self.frame, self.lines)
        if lid is not None and messagebox.askyesno(
                "Delete", f"Delete budget line #{lid}?", parent=self.frame):
            w.call(self.frame, lambda: db.delete_line(lid))
            self.refresh()

    def copy_year(self) -> None:
        did = self._need_dept()
        if did is None:
            return
        f = w.ask_form(self.frame, "Copy budget lines", [
            ("src", "Copy from year", "entry", "", None),
            ("uplift", "Uplift %", "entry", "0", None)],
            note=f"Into {self.year.get()} (which must have no lines yet).")
        if not f:
            return
        made = w.call(self.frame, lambda: db.copy_year(
            did, from_year=f["src"] or "", to_year=self.year.get(),
            uplift_pct=w.num(f["uplift"]) or 0.0,
            created_by=w.actor() or None))
        if made is not None:
            messagebox.showinfo("Copied", f"{len(made)} line(s) copied.",
                                parent=self.frame)
            self.refresh()

    def sync(self) -> None:
        year = self._year()
        if year and messagebox.askyesno(
                "Sync", f"Copy {year} line totals and net spend into each "
                "department's budget figures (shown on the other tabs)?",
                parent=self.frame):
            n = w.call(self.frame, lambda: db.sync_department_totals(year))
            if n is not None:
                messagebox.showinfo("Synced", f"{n} department(s) updated.",
                                    parent=self.frame)
