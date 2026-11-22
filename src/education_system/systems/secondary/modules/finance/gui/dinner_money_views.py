"""Dinner Money screen (new - there was no dinner money in the old system).

Tabs:

* **Accounts** - every pupil's balance (filters: year, form, search, FSM,
  overdrawn); Top up, Meal at the till, Adjust, Refund balance, Write off,
  Dietary needs, Statement, E-mail statement, Open pupil, History, Export.
* **Register** - the day's meal register for a meal type: tick who had a
  meal (FSM, allergies / dietary flag and balance shown), Save, Charge the
  register.
* **Transactions** - the ledger with filters; Void a line; Export.
* **Arrears & alerts** - overdrawn accounts (debt letters), low balances
  (alerts) and leavers holding a balance.
* **Cash-up** - the day's takings by method and by person, meals served;
  takings over a date range.
* **Prices** - meal types, price, FSM cover; the low-balance level.
* **Year end** - carry balances forward into the next school year.

The rules are in :mod:`modules.finance.domain.dinner_money`.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

from education_system.platform.delivery.gui.parented_dialogs import filedialog, messagebox
from education_system.systems.secondary.modules.finance.domain import dinner_money as DM
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.gui.components import widgets as W

logger = logging.getLogger(__name__)
YEARS = ("7", "8", "9", "10", "11")
_ERRORS = W.ERRORS
_problems = W.problems
_text_window = W.text_window
_form = W.form_dialog
_m = DM.money


def _tree(parent, columns, height: int = 16, select: str = "extended") -> ttk.Treeview:
    return W.tree(parent, columns, height=height, select=select,
                  stretch={"pupil", "needs", "notes"}, tags=W.STANDARD_TAGS)


class DinnerMoneyPage:
    TABS = ("Accounts", "Register", "Transactions", "Arrears & alerts", "Cash-up", "Prices",
            "Year end")

    def __init__(self, parent: ttk.Frame, *, principal: Principal, state: dict,
                 open_pupil: Callable[[int], None] | None = None) -> None:
        self.parent, self.principal, self.state = parent, principal, state
        self.open_pupil = open_pupil
        self.editor = DM.is_editor(principal)
        activity_log.record("dinner_money.view")
        ttk.Label(parent, text="Dinner Money", font=("", 16, "bold")).pack(anchor="w")
        self.summary_var = tk.StringVar()
        ttk.Label(parent, textvariable=self.summary_var, foreground="#666").pack(
            anchor="w", pady=(0, 6))
        self.book = ttk.Notebook(parent)
        self.book.pack(fill="both", expand=True)
        self.tabs = {n: ttk.Frame(self.book, padding=8) for n in self.TABS}
        for n, f in self.tabs.items():
            self.book.add(f, text=n)
        self._built: set[str] = set()
        start = state.get("tab") if state.get("tab") in self.TABS else "Accounts"
        self.book.select(self.TABS.index(start))
        self.book.bind("<<NotebookTabChanged>>", self._on_tab)
        self._on_tab()

    # ── helpers ──────────────────────────────────────────────────────

    def _top(self):
        return self.parent.winfo_toplevel()

    def _err(self, title: str, e: Exception) -> None:
        messagebox.showerror(title, _problems(e), parent=self._top())

    def _info(self, title: str, text: str) -> None:
        messagebox.showinfo(title, text, parent=self._top())

    def _button(self, bar, text: str, command, editor_only: bool = False,
                side: str = "left") -> None:
        b = ttk.Button(bar, text=text, command=command)
        if editor_only and not self.editor:
            b.state(["disabled"])
        b.pack(side=side, padx=2)

    def _run(self, title: str, fn, *a, **kw) -> Any:
        try:
            return fn(*a, **kw)
        except _ERRORS as e:
            self._err(title, e)
            return None

    def _views(self) -> dict[str, tuple[Callable, Callable]]:
        return {"Accounts": (self._build_accounts, self.refresh_accounts),
                "Register": (self._build_register, self.refresh_register),
                "Transactions": (self._build_txns, self.refresh_txns),
                "Arrears & alerts": (self._build_arrears, self.refresh_arrears),
                "Cash-up": (self._build_cash, self.refresh_cash),
                "Prices": (self._build_prices, self.refresh_prices),
                "Year end": (self._build_year_end, self.refresh_year_end)}

    def _on_tab(self, _e=None) -> None:
        name = self.TABS[self.book.index(self.book.select())]
        self.state["tab"] = name
        build, refresh = self._views()[name]
        if name not in self._built:
            self._built.add(name)
            build(self.tabs[name])
        refresh()

    def _refresh_all(self) -> None:
        for name, (_b, fn) in self._views().items():
            if name in self._built:
                fn()

    def _summary(self) -> None:
        s = DM.summary()
        self.summary_var.set(f"Pupils: {s['pupils']}    FSM: {s['fsm']}    In credit: "
                             f"{_m(s['credit_pence'])}    Owed: {_m(s['debt_pence'])} "
                             f"({s['overdrawn']} overdrawn)    Low (< {_m(s['low_level'])}): "
                             f"{s['low']}    Dietary / allergy flags: {s['needs']}")

    def _deliver(self, title: str, res: dict[str, Any]) -> None:
        extra = ""
        if res.get("no_email"):
            extra += f"\nNo e-mail address for {len(res['no_email'])} pupil(s)."
        if res.get("skipped"):
            extra += f"\nSkipped {len(res['skipped'])} written to in the last week."
        if not res.get("message_id"):
            self._info(title, "Nothing sent." + extra)
            return
        from education_system.systems.secondary.modules.communication.gui import email_views

        def done(_report, error) -> None:
            try:
                self._info(title, f"{res['emails']} e-mail(s) prepared.{extra}"
                           + (f"\n\nQueued - delivery failed: {error}" if error else "\n\nSent."))
            except tk.TclError:
                pass
        email_views.deliver_in_background(self.parent, res["message_id"], self.principal, done)

    # ── Accounts ─────────────────────────────────────────────────────

    def _build_accounts(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self.a_year = tk.StringVar(value=self.state.get("year", ""))
        self.a_form = tk.StringVar(value=self.state.get("form", ""))
        self.a_search = tk.StringVar()
        self.a_fsm = tk.StringVar(value="")
        self.a_owing = tk.BooleanVar(value=False)
        ttk.Label(bar, text="Year:").pack(side="left")
        ttk.Combobox(bar, textvariable=self.a_year, values=["", *YEARS], state="readonly",
                     width=4).pack(side="left", padx=(2, 6))
        ttk.Label(bar, text="Form:").pack(side="left")
        ttk.Entry(bar, textvariable=self.a_form, width=6).pack(side="left", padx=(2, 6))
        ttk.Label(bar, text="Search:").pack(side="left")
        e = ttk.Entry(bar, textvariable=self.a_search, width=16)
        e.pack(side="left", padx=(2, 6))
        e.bind("<Return>", lambda _e: self.refresh_accounts())
        ttk.Label(bar, text="FSM:").pack(side="left")
        ttk.Combobox(bar, textvariable=self.a_fsm, values=["", "FSM", "Not FSM"],
                     state="readonly", width=8).pack(side="left", padx=(2, 6))
        ttk.Checkbutton(bar, text="Overdrawn", variable=self.a_owing).pack(side="left")
        self._button(bar, "Apply", self.refresh_accounts)
        bar2 = ttk.Frame(tab)
        bar2.pack(fill="x", pady=(0, 4))
        for text, cmd, lead in (("Top up…", self.top_up, True),
                                ("Meal at the till…", self.till, True),
                                ("Adjust…", self.adjust, True),
                                ("Refund balance…", self.refund, True),
                                ("Write off…", self.write_off, True),
                                ("Dietary needs…", self.needs, True)):
            self._button(bar2, text, cmd, lead)
        bar3 = ttk.Frame(tab)
        bar3.pack(fill="x", pady=(0, 4))
        for text, cmd, lead in (("Statement", self.statement, False),
                                ("E-mail statement", self.email_statement, True),
                                ("Open pupil", self._open_pupil, False),
                                ("History", self.history, False),
                                ("Export CSV…", self.export_balances, False)):
            self._button(bar3, text, cmd, lead)
        self.a_tree = _tree(tab, [("pupil", "Pupil", 220), ("year", "Yr", 40),
                                  ("form", "Form", 60), ("fsm", "FSM", 50),
                                  ("balance", "Balance", 90), ("last", "Last top-up", 100),
                                  ("needs", "Dietary / allergies", 260)], select="browse")
        self.a_tree.bind("<Double-1>", lambda _e: self.statement())
        self.a_rows: dict[str, DM.Account] = {}

    def refresh_accounts(self) -> None:
        self.state.update(year=self.a_year.get(), form=self.a_form.get())
        fsm = {"FSM": True, "Not FSM": False}.get(self.a_fsm.get())
        rows = DM.accounts(year_group=self.a_year.get() or None,
                           form_group=self.a_form.get().strip() or None,
                           search=self.a_search.get(), fsm=fsm)
        if self.a_owing.get():
            rows = [a for a in rows if a.balance_pence < 0]
        low = DM.low_balance_threshold()
        self.a_tree.delete(*self.a_tree.get_children())
        self.a_rows = {}
        for a in rows:
            self.a_rows[str(a.pupil_id)] = a
            tag = "bad" if a.balance_pence < 0 else ("warn" if a.balance_pence < low and
                                                     not a.fsm else "")
            self.a_tree.insert("", "end", iid=str(a.pupil_id), tags=(tag,), values=(
                f"{a.pupil_name} ({a.admission_no})", a.year_group, a.form_group or "",
                "Yes" if a.fsm else "", _m(a.balance_pence), a.last_top_up or "",
                a.needs_flag))
        self._summary()

    def _account(self, title: str) -> DM.Account | None:
        sel = self.a_tree.selection()
        if not sel:
            self._info(title, "Select a pupil first.")
            return None
        return DM.account(int(sel[0]))

    def top_up(self) -> None:
        a = self._account("Top up")
        if a is None:
            return

        def save(v):
            DM.top_up(a.pupil_id, v["amount"], actor=self.principal, method=v["method"],
                      day=v["day"] or None, reference=v["reference"], notes=v["notes"])
            self._refresh_all()
        _form(self.parent, f"Top up - {a.pupil_name} (balance {_m(a.balance_pence)})", [
            ("amount", "Amount (£)", "", None),
            ("method", "Method", DM.DEFAULT_METHOD, DM.METHODS),
            ("day", "Date (blank = today)", "", None),
            ("reference", "Reference (cheque / online / transfer)", "", None),
            ("notes", "Notes", "", None)], save)

    def till(self) -> None:
        a = self._account("Meal at the till")
        if a is None:
            return
        types = [p.meal_type for p in DM.list_prices(active_only=True)]

        def save(v):
            r = DM.record_meal(a.pupil_id, v["meal"], actor=self.principal, day=v["day"] or None)
            self._refresh_all()
            self._info("Meal", ("Free school meal recorded." if r["fsm"] else
                                f"Charged {_m(r['price_pence'])}.")
                       + f" Balance now {_m(r['balance_pence'])}.")
        _form(self.parent, f"Meal - {a.pupil_name}", [
            ("meal", "Meal", types[0] if types else "", types),
            ("day", "Date (blank = today)", "", None)], save,
            note=(f"ALLERGY / DIET: {a.needs_flag}" if a.needs_flag else
                  "A meal is never refused for a low balance."))

    def adjust(self) -> None:
        a = self._account("Adjust")
        if a is None:
            return

        def save(v):
            DM.adjust(a.pupil_id, v["amount"], actor=self.principal, reason=v["reason"],
                      day=v["day"] or None)
            self._refresh_all()
        _form(self.parent, f"Adjust - {a.pupil_name}", [
            ("amount", "Amount (£, -1.20 takes money off)", "", None),
            ("reason", "Why (required)", "", None), ("day", "Date (blank = today)", "", None)],
            save)

    def refund(self) -> None:
        a = self._account("Refund balance")
        if a is None:
            return

        def save(v):
            DM.refund_balance(a.pupil_id, actor=self.principal, method=v["method"],
                              reference=v["reference"], notes=v["notes"],
                              amount=v["amount"] or None)
            self._refresh_all()
        _form(self.parent, f"Refund - {a.pupil_name} (balance {_m(a.balance_pence)})", [
            ("amount", "Amount (£, blank = whole balance)", "", None),
            ("method", "Method", "Bank transfer", DM.METHODS),
            ("reference", "Reference", "", None), ("notes", "Notes", "", None)], save)

    def write_off(self) -> None:
        a = self._account("Write off")
        if a is None:
            return

        def save(v):
            DM.write_off(a.pupil_id, actor=self.principal, reason=v["reason"])
            self._refresh_all()
        _form(self.parent, f"Write off - {a.pupil_name} (balance {_m(a.balance_pence)})",
              [("reason", "Why (required)", "", "text")], save)

    def needs(self) -> None:
        a = self._account("Dietary needs")
        if a is None:
            return
        cur = DM.get_needs(a.pupil_id)

        def save(v):
            DM.set_needs(a.pupil_id, actor=self.principal, **v)
            self._refresh_all()
        _form(self.parent, f"Dietary needs - {a.pupil_name}", [
            ("dietary", "Dietary requirements", cur["dietary"] or "", None),
            ("allergies", "Allergies", cur["allergies"] or "", None),
            ("notes", "Notes", cur["notes"] or "", "text")], save,
            note="Shown on the meal register and at the till.")

    def statement(self) -> None:
        a = self._account("Statement")
        if a is None:
            return

        def save(v):
            s = DM.statement(a.pupil_id, date_from=v["from"] or None, date_to=v["to"] or None)
            _text_window(self.parent, f"Statement - {a.pupil_name}", DM.statement_text(s),
                         save_name=f"meals-{a.admission_no}.txt")
        _form(self.parent, f"Statement - {a.pupil_name}", [
            ("from", "From (blank = start)", "", None), ("to", "To (blank = today)", "", None)],
            save)

    def email_statement(self) -> None:
        a = self._account("E-mail statement")
        if a is None:
            return

        def save(v):
            res = DM.email_statement(a.pupil_id, actor=self.principal,
                                     date_from=v["from"] or None, date_to=v["to"] or None)
            self._deliver("E-mail statement", res)
        _form(self.parent, f"E-mail statement - {a.pupil_name}", [
            ("from", "From (blank = start)", "", None), ("to", "To (blank = today)", "", None)],
            save)

    def _open_pupil(self) -> None:
        sel = self.a_tree.selection()
        if sel and self.open_pupil:
            self.open_pupil(int(sel[0]))

    def history(self) -> None:
        sel = self.a_tree.selection()
        rows = DM.history(int(sel[0]) if sel else None)
        _text_window(self.parent, "History", "\n".join(
            f"{h['at']}  {h['actor']:<12} {h['action']:<16} pupil {h['pupil_id'] or '-'}  "
            + ", ".join(f"{k}={v}" for k, v in h["detail"].items()) for h in rows)
            or "No changes recorded.")

    def export_balances(self) -> None:
        path = filedialog.asksaveasfilename(parent=self._top(), defaultextension=".csv",
                                            filetypes=[("CSV", "*.csv")],
                                            initialfile="meal-balances.csv")
        if path:
            n = self._run("Export", DM.export_csv, path, actor=self.principal,
                          year_group=self.a_year.get() or None)
            if n is not None:
                self._info("Export", f"Exported {n} account(s).")

    # ── Register ─────────────────────────────────────────────────────

    def _build_register(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self.r_day = tk.StringVar(value=DM._today().isoformat())
        self.r_meal = tk.StringVar(value=self.state.get("meal", DM.DEFAULT_MEAL))
        self.r_year = tk.StringVar(value=self.state.get("r_year", ""))
        self.r_form = tk.StringVar(value="")
        ttk.Label(bar, text="Date:").pack(side="left")
        ttk.Entry(bar, textvariable=self.r_day, width=11).pack(side="left", padx=(2, 6))
        ttk.Label(bar, text="Meal:").pack(side="left")
        self.r_meal_box = ttk.Combobox(bar, textvariable=self.r_meal, state="readonly",
                                       width=12)
        self.r_meal_box.pack(side="left", padx=(2, 6))
        ttk.Label(bar, text="Year:").pack(side="left")
        ttk.Combobox(bar, textvariable=self.r_year, values=["", *YEARS], state="readonly",
                     width=4).pack(side="left", padx=(2, 6))
        ttk.Label(bar, text="Form:").pack(side="left")
        ttk.Entry(bar, textvariable=self.r_form, width=6).pack(side="left", padx=(2, 6))
        self._button(bar, "Load", self.refresh_register)
        bar2 = ttk.Frame(tab)
        bar2.pack(fill="x", pady=(0, 4))
        self._button(bar2, "Had a meal", lambda: self._tick(True))
        self._button(bar2, "No meal", lambda: self._tick(False))
        self._button(bar2, "Save register", self.save_register)
        self._button(bar2, "Charge register", self.charge_register, True)
        self.r_count = tk.StringVar()
        ttk.Label(bar2, textvariable=self.r_count, foreground="#555").pack(side="left", padx=10)
        self.r_tree = _tree(tab, [("had", "Meal", 50), ("pupil", "Pupil", 220),
                                  ("form", "Form", 60), ("fsm", "FSM", 50),
                                  ("price", "Price", 70), ("charged", "Charged", 70),
                                  ("balance", "Balance", 80),
                                  ("needs", "Dietary / allergies", 260)])
        self.r_tree.tag_configure("allergy", foreground="#b00000")
        self.r_tree.bind("<Double-1>", lambda _e: self._toggle())
        self.r_ticked: set[int] = set()
        self.r_rows: dict[str, DM.RegisterRow] = {}

    def refresh_register(self) -> None:
        types = [p.meal_type for p in DM.list_prices(active_only=True)]
        self.r_meal_box.configure(values=types)
        if types and self.r_meal.get() not in types:
            self.r_meal.set(types[0])
        self.state.update(meal=self.r_meal.get(), r_year=self.r_year.get())
        self.r_tree.delete(*self.r_tree.get_children())
        self.r_rows = {}
        try:
            rows = DM.register(self.r_day.get().strip() or None, self.r_meal.get(),
                               year_group=self.r_year.get() or None,
                               form_group=self.r_form.get().strip() or None)
        except ValueError:
            self.r_count.set("Date must be YYYY-MM-DD")
            return
        self.r_ticked = {r.pupil_id for r in rows if r.had_meal}
        for r in rows:
            self.r_rows[str(r.pupil_id)] = r
            self.r_tree.insert("", "end", iid=str(r.pupil_id), values=self._reg_values(r),
                               tags=self._reg_tags(r))
        self._count()
        self._summary()

    def _reg_values(self, r: DM.RegisterRow) -> tuple:
        return ("✓" if r.pupil_id in self.r_ticked else "", f"{r.pupil_name} ({r.admission_no})",
                r.form_group or "", "Yes" if r.fsm else "", _m(r.price_pence),
                "Yes" if r.charged else "", _m(r.balance_pence), r.needs)

    def _reg_tags(self, r: DM.RegisterRow) -> tuple:
        tags = ["allergy"] if "ALLERGY" in r.needs else []
        if r.balance_pence < 0:
            tags.append("bad")
        return tuple(tags)

    def _count(self) -> None:
        self.r_count.set(f"{len(self.r_ticked)} of {len(self.r_rows)} ticked "
                         f"(not saved until Save register)")

    def _tick(self, had: bool) -> None:
        for iid in self.r_tree.selection():
            r = self.r_rows[iid]
            (self.r_ticked.add if had else self.r_ticked.discard)(r.pupil_id)
            self.r_tree.item(iid, values=self._reg_values(r))
        self._count()

    def _toggle(self) -> None:
        sel = self.r_tree.selection()
        if sel:
            self._tick(int(sel[0]) not in self.r_ticked)

    def save_register(self) -> None:
        res = self._run("Save register", DM.save_register, self.r_day.get().strip() or None,
                        self.r_meal.get(), sorted(self.r_ticked), actor=self.principal,
                        scope=[int(x) for x in self.r_rows])
        if res:
            self.refresh_register()
            self._info("Save register", f"Added {res['added']}, took off {res['removed']}.")

    def charge_register(self) -> None:
        if not messagebox.askyesno("Charge register", f"Charge every uncharged "
                                   f"{self.r_meal.get()} on {self.r_day.get()}? (Save the "
                                   "register first.)", parent=self._top()):
            return
        res = self._run("Charge register", DM.charge_register, self.r_day.get().strip() or None,
                        self.r_meal.get(), actor=self.principal)
        if res:
            self._refresh_all()
            self._info("Charge register", f"Charged {res['charged']} meal(s), "
                                          f"{_m(res['total_pence'])}; {res['fsm']} free school "
                                          "meal(s) recorded.")

    # ── Transactions ─────────────────────────────────────────────────

    def _build_txns(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self.t_vars = {k: tk.StringVar() for k in ("pupil", "kind", "method", "from", "to")}
        for label, key, values, width in (("Pupil:", "pupil", None, 10),
                                          ("Kind:", "kind", ["", *DM.KINDS], 14),
                                          ("Method:", "method", ["", *DM.METHODS], 12),
                                          ("From:", "from", None, 11), ("To:", "to", None, 11)):
            ttk.Label(bar, text=label).pack(side="left")
            if values:
                ttk.Combobox(bar, textvariable=self.t_vars[key], values=values,
                             state="readonly", width=width).pack(side="left", padx=(2, 6))
            else:
                ttk.Entry(bar, textvariable=self.t_vars[key], width=width).pack(
                    side="left", padx=(2, 6))
        self._button(bar, "Apply", self.refresh_txns)
        bar2 = ttk.Frame(tab)
        bar2.pack(fill="x", pady=(0, 4))
        self._button(bar2, "Void…", self.void, True)
        self._button(bar2, "Export CSV…", self.export_txns)
        self.t_tree = _tree(tab, [("id", "Id", 60), ("date", "Date", 90),
                                  ("pupil", "Pupil", 200), ("kind", "Kind", 110),
                                  ("amount", "Amount", 80), ("what", "Meal / method", 110),
                                  ("ref", "Reference", 110), ("by", "By", 90),
                                  ("notes", "Notes", 200)], select="browse")
        self.t_total = tk.StringVar()
        ttk.Label(tab, textvariable=self.t_total).pack(anchor="w")

    def _txn_filters(self) -> dict[str, Any]:
        f = {k: v.get().strip() for k, v in self.t_vars.items()}
        pupil = DM._pupil(f["pupil"]) if f["pupil"] else None
        return {"pupil_id": pupil.pupil_id if pupil else (-1 if f["pupil"] else None),
                "kind": f["kind"] or None, "method": f["method"] or None,
                "date_from": f["from"] or None, "date_to": f["to"] or None}

    def refresh_txns(self) -> None:
        rows = DM.transactions(**self._txn_filters(), limit=2000)
        self.t_tree.delete(*self.t_tree.get_children())
        for t in rows:
            self.t_tree.insert("", "end", iid=str(t.txn_id), tags=("muted",) if t.voided else (),
                               values=(t.txn_id, t.txn_date, f"{t.pupil_name} ({t.admission_no})",
                                       t.kind + (" (void)" if t.voided else ""),
                                       _m(t.amount_pence), t.meal_type or t.method or "",
                                       t.reference or "", t.created_by or "",
                                       t.void_reason or t.notes or ""))
        self.t_total.set(f"{len(rows)} line(s)    Net: {_m(sum(t.counts for t in rows))}")

    def void(self) -> None:
        sel = self.t_tree.selection()
        if not sel:
            self._info("Void", "Select a line first.")
            return
        t = DM.get_txn(int(sel[0]))

        def save(v):
            DM.void(t.txn_id, actor=self.principal, reason=v["reason"])
            self._refresh_all()
        _form(self.parent, f"Void line #{t.txn_id} ({t.kind} {_m(t.amount_pence)})",
              [("reason", "Why (required)", "", None)], save,
              note="The line stays on record but no longer counts.")

    def export_txns(self) -> None:
        path = filedialog.asksaveasfilename(parent=self._top(), defaultextension=".csv",
                                            filetypes=[("CSV", "*.csv")],
                                            initialfile="meal-ledger.csv")
        if path:
            f = self._txn_filters()
            n = self._run("Export", DM.export_csv, path, actor=self.principal,
                          kind="transactions", pupil_id=f["pupil_id"], txn_kind=f["kind"],
                          method=f["method"], date_from=f["date_from"], date_to=f["date_to"])
            if n is not None:
                self._info("Export", f"Exported {n} line(s).")

    # ── Arrears & alerts ─────────────────────────────────────────────

    def _build_arrears(self, tab) -> None:
        ttk.Label(tab, text="Overdrawn accounts", font=("", 11, "bold")).pack(anchor="w")
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(2, 2))
        self._button(bar, "Debt letters to selected", lambda: self.letters("debt", True), True)
        self._button(bar, "Debt letters to all", lambda: self.letters("debt", False), True)
        self._button(bar, "Refresh", self.refresh_arrears, side="right")
        self.d_tree = _tree(tab, [("pupil", "Pupil", 240), ("year", "Yr", 40),
                                  ("balance", "Balance", 90), ("last", "Last letter", 140)],
                            height=7)
        self.low_label = tk.StringVar()
        ttk.Label(tab, textvariable=self.low_label, font=("", 11, "bold")).pack(
            anchor="w", pady=(8, 0))
        bar2 = ttk.Frame(tab)
        bar2.pack(fill="x", pady=(2, 2))
        self._button(bar2, "Alert selected", lambda: self.letters("low", True), True)
        self._button(bar2, "Alert all", lambda: self.letters("low", False), True)
        self.l_tree = _tree(tab, [("pupil", "Pupil", 240), ("year", "Yr", 40),
                                  ("balance", "Balance", 90), ("last", "Last alert", 140)],
                            height=6)
        ttk.Label(tab, text="Leavers holding a balance (refund credit, write off debt on "
                            "Accounts)", font=("", 11, "bold")).pack(anchor="w", pady=(8, 0))
        self.v_tree = _tree(tab, [("pupil", "Pupil", 240), ("balance", "Balance", 90)],
                            height=4)

    def _last(self, pupil_id: int, kind: str) -> str:
        return next((x["sent_at"][:16] for x in DM.last_letters(pupil_id) if x["kind"] == kind),
                    "")

    def refresh_arrears(self) -> None:
        self.d_tree.delete(*self.d_tree.get_children())
        for a in DM.arrears():
            self.d_tree.insert("", "end", iid=str(a.pupil_id), values=(
                f"{a.pupil_name} ({a.admission_no})", a.year_group, _m(a.balance_pence),
                self._last(a.pupil_id, "debt")))
        self.low_label.set(f"Low balances (below {_m(DM.low_balance_threshold())}, not FSM)")
        self.l_tree.delete(*self.l_tree.get_children())
        for a in DM.low_balance():
            self.l_tree.insert("", "end", iid=str(a.pupil_id), values=(
                f"{a.pupil_name} ({a.admission_no})", a.year_group, _m(a.balance_pence),
                self._last(a.pupil_id, "low_balance")))
        self.v_tree.delete(*self.v_tree.get_children())
        for a in DM.leavers_with_balance():
            self.v_tree.insert("", "end", values=(f"{a.pupil_name} ({a.admission_no})",
                                                  _m(a.balance_pence)))
        self._summary()

    def letters(self, kind: str, selected: bool) -> None:
        tree = self.d_tree if kind == "debt" else self.l_tree
        ids = [int(x) for x in tree.selection()] if selected else None
        if selected and not ids:
            self._info("Letters", "Select pupils first.")
            return
        fn = DM.send_debt_letters if kind == "debt" else DM.send_low_balance_alerts
        res = self._run("Letters", fn, actor=self.principal, pupil_ids=ids)
        if res:
            self.refresh_arrears()
            self._deliver("Letters", res)

    # ── Cash-up ──────────────────────────────────────────────────────

    def _build_cash(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self.c_day = tk.StringVar(value=DM._today().isoformat())
        ttk.Label(bar, text="Day:").pack(side="left")
        ttk.Entry(bar, textvariable=self.c_day, width=11).pack(side="left", padx=(2, 6))
        self._button(bar, "Cash-up", self.refresh_cash)
        self._button(bar, "Takings over a range…", self.takings)
        self.c_text = tk.Text(tab, wrap="none", font=("TkFixedFont", 10), height=24,
                              state="disabled")
        self.c_text.pack(fill="both", expand=True)

    def refresh_cash(self) -> None:
        try:
            text = DM.cash_up_text(DM.cash_up(self.c_day.get().strip() or None))
        except ValueError as e:
            text = f"Date must be YYYY-MM-DD ({e})"
        self.c_text.configure(state="normal")
        self.c_text.delete("1.0", "end")
        self.c_text.insert("1.0", text)
        self.c_text.configure(state="disabled")

    def takings(self) -> None:
        def save(v):
            rows = DM.takings(v["from"], v["to"])
            lines = [f"{'Day':<12}" + "".join(f"{m:>14}" for m in DM.METHODS)
                     + f"{'Net':>12}{'Meals':>7}"]
            for r in rows:
                lines.append(f"{r['day']:<12}" + "".join(
                    f"{_m(r['by_method'].get(m, 0)):>14}" for m in DM.METHODS)
                    + f"{_m(r['net_pence']):>12}{r['meals']:>7}")
            lines.append(f"{'Total':<12}" + " " * 14 * len(DM.METHODS)
                         + f"{_m(sum(r['net_pence'] for r in rows)):>12}"
                         f"{sum(r['meals'] for r in rows):>7}")
            _text_window(self.parent, "Takings", "\n".join(lines), size="980x480",
                         save_name="meal-takings.txt")
        today = DM._today().isoformat()
        _form(self.parent, "Takings", [("from", "From", today[:8] + "01", None),
                                       ("to", "To", today, None)], save)

    # ── Prices ───────────────────────────────────────────────────────

    def _build_prices(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self._button(bar, "Set price…", self.set_price, True)
        self._button(bar, "Low-balance level…", self.set_low, True)
        self.p_tree = _tree(tab, [("meal", "Meal type", 160), ("price", "Price", 90),
                                  ("fsm", "Covered by FSM", 120), ("active", "In use", 70),
                                  ("by", "Set by", 120), ("at", "When", 150)],
                            select="browse", height=8)
        self.p_tree.bind("<Double-1>", lambda _e: self.set_price())
        self.p_low = tk.StringVar()
        ttk.Label(tab, textvariable=self.p_low).pack(anchor="w", pady=(6, 0))

    def refresh_prices(self) -> None:
        self.p_tree.delete(*self.p_tree.get_children())
        for p in DM.list_prices():
            self.p_tree.insert("", "end", iid=p.meal_type, values=(
                p.meal_type, _m(p.price_pence), "Yes" if p.fsm_covered else "No",
                "Yes" if p.active else "No", p.updated_by or "", p.updated_at))
        self.p_low.set(f"Low-balance alert below {_m(DM.low_balance_threshold())}")

    def set_price(self) -> None:
        sel = self.p_tree.selection()
        cur = DM.get_price(sel[0]) if sel else None

        def save(v):
            DM.set_price(v["meal"], v["price"], actor=self.principal,
                         fsm_covered=v["fsm"], active=v["active"])
            self._refresh_all()
        _form(self.parent, "Meal price", [
            ("meal", "Meal type", cur.meal_type if cur else DM.DEFAULT_MEAL,
             ("edit", DM.MEAL_TYPES)),
            ("price", "Price (£)", DM.plain(cur.price_pence) if cur else "", None),
            ("fsm", "Covered by free school meals", bool(cur.fsm_covered) if cur else True,
             "check"),
            ("active", "In use", bool(cur.active) if cur else True, "check")], save)

    def set_low(self) -> None:
        def save(v):
            DM.set_low_balance_threshold(v["amount"], actor=self.principal)
            self._refresh_all()
        _form(self.parent, "Low-balance level", [
            ("amount", "Alert below (£)", DM.plain(DM.low_balance_threshold()), None)], save)

    # ── Year end ─────────────────────────────────────────────────────

    def _build_year_end(self, tab) -> None:
        ttk.Label(tab, text="At the end of the school year every on-roll balance is carried "
                            "into the next year (two lines that net to zero, so each year's "
                            "statement starts with what was brought forward). Leavers are "
                            "refunded or written off instead.", wraplength=760,
                  foreground="#555", justify="left").pack(anchor="w", pady=(0, 6))
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self.y_year = tk.StringVar(value=DM.current_year())
        ttk.Label(bar, text="School year:").pack(side="left")
        ttk.Entry(bar, textvariable=self.y_year, width=9).pack(side="left", padx=(2, 6))
        self._button(bar, "Carry forward…", self.year_end, True)
        self.y_tree = _tree(tab, [("year", "School year", 100), ("on", "Closed on", 100),
                                  ("by", "By", 120), ("pupils", "Balances carried", 120)],
                            select="browse", height=6)

    def refresh_year_end(self) -> None:
        self.y_tree.delete(*self.y_tree.get_children())
        for r in DM.year_ends():
            self.y_tree.insert("", "end", values=(r["academic_year"], r["closed_on"],
                                                  r["closed_by"] or "", r["pupils"]))

    def year_end(self) -> None:
        year = self.y_year.get().strip()
        if not messagebox.askyesno("Year end", f"Carry every balance from {year} into the "
                                   "next school year? This is done once.", parent=self._top()):
            return
        r = self._run("Year end", DM.year_end, year, actor=self.principal)
        if r:
            self._refresh_all()
            self._info("Year end", f"Carried {r['pupils']} balance(s): credit "
                                   f"{_m(r['credit_pence'])}, debt {_m(r['debt_pence'])}.\n"
                                   f"{len(r['leavers'])} leaver(s) still hold a balance.")


def draw_dinner_money(parent: ttk.Frame, *, principal: Principal, state: dict,
                      open_pupil: Callable[[int], None] | None = None) -> DinnerMoneyPage:
    return DinnerMoneyPage(parent, principal=principal, state=state, open_pupil=open_pupil)
