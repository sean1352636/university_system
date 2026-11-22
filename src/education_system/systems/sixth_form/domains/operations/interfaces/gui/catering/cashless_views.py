"""Tkinter screens for Sixth Form cashless catering and biometric consent.

* :func:`open_cashless_catering_window` — the office window: Till,
  Accounts, Transactions, Low Balance, Leavers, Biometric Consent
  (register, consents, objections, templates to delete, audit),
  Settings and Summary.
* :func:`open_till_window` — the till on its own (for the serving-counter
  machine).

The till identifies the learner by card, PIN, a staff lookup, or a
biometric reader match; a biometric match without current consent is
refused by the domain and the operator is told to use the card or PIN.
"""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import messagebox
from typing import Any

from education_system.systems.sixth_form.domains.operations.domain.catering import (
    biometric_consent as bio,
)
from education_system.systems.sixth_form.domains.operations.domain.catering import (
    cashless as data,
)
from education_system.systems.sixth_form.interfaces.gui.operations._ops_ui import (
    Field,
    SummaryTab,
    TableTab,
    form_dialog,
    make_window,
    option_key,
    student_options,
)

logger = logging.getLogger(__name__)

_ACCOUNT_TAGS = {
    "low": ("#fff7e6", "#7a5800"),
    "closed": ("#eeeeee", "#444444"),
    "left": ("#ffd1d1", "#8c0d0d"),
}
_TXN_TAGS = {
    data.TOPUP: ("#e6f7e6", "#0d6b2a"),
    data.REFUND: ("#e6f0ff", "#1a3f8c"),
    data.VOID: ("#eeeeee", "#444444"),
    "voided": ("#eeeeee", "#888888"),
}
_BIO_TAGS = {"allowed": ("#e6f7e6", "#0d6b2a"),
             "refused": ("#ffd1d1", "#8c0d0d")}


def _warn(parent: tk.Misc, fn) -> Any:
    """Validation problems as a warning; permission problems as an error."""
    try:
        return fn()
    except ValueError as e:
        messagebox.showwarning("Cashless catering", str(e), parent=parent)
    except PermissionError as e:
        messagebox.showerror("Cashless catering", str(e), parent=parent)
    return None


def _w(win: tk.Misc, fn):
    return lambda tab: _warn(win, lambda: fn(tab))


# ── Till ────────────────────────────────────────────────────────────

class TillFrame:
    """Identify → charge; also cash top-ups and voids of today's sales."""

    def __init__(self, parent: tk.Misc, on_change=None) -> None:
        self.on_change = on_change or (lambda: None)
        self.frame = ttk.Frame(parent, padding=10)
        self.ident: data.Identification | None = None
        f = self.frame

        top = ttk.Frame(f)
        top.pack(fill="x")
        ttk.Label(top, text="Till:").pack(side="left")
        self.till = ttk.Entry(top, width=12)
        self.till.insert(0, "Till 1")
        self.till.pack(side="left", padx=(2, 16))
        ttk.Label(top, text="Identify by:").pack(side="left")
        self.method = ttk.Combobox(top, values=list(data.ID_METHODS),
                                   state="readonly", width=13)
        self.method.set(data.ID_CARD)
        self.method.pack(side="left", padx=(2, 8))
        self.method.bind("<<ComboboxSelected>>", lambda _e: self._method_changed())
        self.card_lbl = ttk.Label(top, text="Card number:")
        self.card_lbl.pack(side="left")
        self.card = ttk.Entry(top, width=16)
        self.card.pack(side="left", padx=(2, 8))
        self.card.bind("<Return>", lambda _e: self.identify())
        self.student = ttk.Combobox(top, values=student_options(), width=36)
        self.pin_lbl = ttk.Label(top, text="PIN:")
        self.pin = ttk.Entry(top, width=8, show="•")
        self.pin.bind("<Return>", lambda _e: self.identify())
        self.ident_btn = ttk.Button(top, text="Identify", command=self.identify)
        self.ident_btn.pack(side="left", padx=4)
        ttk.Button(top, text="Clear", command=self.clear).pack(side="left")

        self.who = tk.Label(f, text="No learner identified", anchor="w",
                            justify="left", font=("", 12, "bold"),
                            background="#f4f6f7", padx=10, pady=8)
        self.who.pack(fill="x", pady=(10, 6))
        self.note = ttk.Label(f, text=(
            "Biometric identification is only accepted with current written "
            "consent. Card and PIN are always available instead."),
            foreground="#7f8c8d")
        self.note.pack(anchor="w")

        sale = ttk.LabelFrame(f, text="Sale", padding=8)
        sale.pack(fill="x", pady=8)
        ttk.Label(sale, text="Total £").grid(row=0, column=0, sticky="w")
        self.amount = ttk.Entry(sale, width=10)
        self.amount.grid(row=0, column=1, sticky="w", padx=(2, 12))
        self.amount.bind("<Return>", lambda _e: self.charge())
        ttk.Label(sale, text="Items").grid(row=0, column=2, sticky="w")
        self.items = ttk.Entry(sale, width=44)
        self.items.grid(row=0, column=3, sticky="w", padx=(2, 12))
        self.free = tk.BooleanVar(value=True)
        ttk.Checkbutton(sale, text="Use free meal allowance",
                        variable=self.free).grid(row=0, column=4, sticky="w")
        ttk.Button(sale, text="Charge", command=self.charge).grid(
            row=0, column=5, padx=8)
        ttk.Label(sale, text="Cash top-up £").grid(row=1, column=0,
                                                    sticky="w", pady=(8, 0))
        self.topup = ttk.Entry(sale, width=10)
        self.topup.grid(row=1, column=1, sticky="w", padx=(2, 12), pady=(8, 0))
        ttk.Button(sale, text="Take cash top-up", command=self.cash_topup
                   ).grid(row=1, column=2, columnspan=2, sticky="w",
                          pady=(8, 0))

        bar = ttk.Frame(f)
        bar.pack(side="bottom", fill="x", pady=(6, 0))
        ttk.Button(bar, text="Void selected", command=self.void).pack(side="left")
        ttk.Button(bar, text="Refresh", command=self.load).pack(side="left",
                                                                 padx=6)
        self.total_lbl = ttk.Label(bar, text="")
        self.total_lbl.pack(side="right")

        ttk.Label(f, text="Today on this till", font=("", 10, "bold")
                  ).pack(anchor="w")
        table = ttk.Frame(f)
        table.pack(fill="both", expand=True)
        cols = [("id", "#", 50), ("at", "Time", 70), ("sid", "Student", 90),
                ("name", "Name", 160), ("type", "Type", 80),
                ("gross", "Total", 80), ("free", "Free meal", 80),
                ("charged", "From balance", 90), ("idm", "Identified by", 100),
                ("items", "Items", 260)]
        self.tree = ttk.Treeview(table, columns=[c[0] for c in cols],
                                 show="headings", selectmode="browse")
        for k, t, wd in cols:
            self.tree.heading(k, text=t)
            self.tree.column(k, width=wd, anchor="w")
        sb = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        for tag, (bg, fg) in _TXN_TAGS.items():
            self.tree.tag_configure(tag, background=bg, foreground=fg)
        self.load()

    def _method_changed(self) -> None:
        m = self.method.get()
        for w in (self.card_lbl, self.card, self.student, self.pin_lbl,
                  self.pin):
            w.pack_forget()
        before = self.ident_btn
        if m == data.ID_CARD:
            self.card_lbl.pack(side="left", before=before)
            self.card.pack(side="left", padx=(2, 8), before=before)
        else:
            self.student.pack(side="left", padx=(2, 8), before=before)
            if m == data.ID_PIN:
                self.pin_lbl.pack(side="left", before=before)
                self.pin.pack(side="left", padx=(2, 8), before=before)
        self.clear(keep_method=True)

    def clear(self, keep_method: bool = False) -> None:
        self.ident = None
        self.who.configure(text="No learner identified", background="#f4f6f7",
                           foreground="black")
        for e in (self.card, self.pin, self.amount, self.items, self.topup):
            e.delete(0, "end")
        if not keep_method:
            self.student.set("")
        self.free.set(True)

    def identify(self) -> None:
        m = self.method.get()
        value = (self.card.get() if m == data.ID_CARD
                 else option_key(self.student.get()) or self.student.get())
        try:
            self.ident = data.identify(m, value, pin=self.pin.get())
        except ValueError as e:
            self.ident = None
            self.who.configure(text=str(e), background="#ffd1d1",
                               foreground="#8c0d0d")
            self.pin.delete(0, "end")
            return
        except PermissionError as e:
            messagebox.showerror("Till", str(e), parent=self.frame)
            return
        self.pin.delete(0, "end")
        self._show_learner()
        self.amount.focus_set()

    def _show_learner(self) -> None:
        if self.ident is None:
            return
        sid = self.ident.student_id
        bal = data.balance_pence(sid)
        allowance, why = data.free_meal_today(sid)
        acct = data.get_account(sid)
        low = bal < data.threshold_pence(acct)
        text = (f"{self.ident.student_name} ({sid}) — identified by "
                f"{self.ident.method}"
                + (f" {self.ident.card_number}" if self.ident.card_number else "")
                + f"\nBalance {data.money(bal)}"
                + (" (low)" if low else "")
                + (f"   ·   {why}" if why else ""))
        if acct is not None and not acct.is_open:
            text += "\nACCOUNT CLOSED"
        self.who.configure(text=text, background="#fff7e6" if low else "#e6f7e6",
                           foreground="black")

    def charge(self) -> None:
        if self.ident is None:
            messagebox.showwarning("Till", "Identify the learner first.",
                                   parent=self.frame)
            return
        ident = self.ident
        t = _warn(self.frame, lambda: data.purchase(
            ident.student_id, self.amount.get(), id_method=ident.method,
            items=self.items.get(), till=self.till.get(),
            use_free_meal=self.free.get(), card_number=ident.card_number))
        if t is None:
            return
        msg = f"Charged {data.money(-t.amount_pence)}"
        if t.free_meal_pence:
            msg += f" (free meal {data.money(t.free_meal_pence)})"
        self.amount.delete(0, "end")
        self.items.delete(0, "end")
        self._show_learner()
        self.who.configure(text=self.who.cget("text") + f"\n✓ {msg}")
        self.load()
        self.on_change()

    def cash_topup(self) -> None:
        if self.ident is None:
            messagebox.showwarning("Till", "Identify the learner first.",
                                   parent=self.frame)
            return
        ident = self.ident
        t = _warn(self.frame, lambda: data.cash_topup(
            ident.student_id, self.topup.get(), till=self.till.get()))
        if t is None:
            return
        self.topup.delete(0, "end")
        self._show_learner()
        self.load()
        self.on_change()

    def void(self) -> None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Till", "Select a transaction.",
                                   parent=self.frame)
            return
        reason = form_dialog(self.frame, "Void transaction",
                             [Field("reason", "Reason", required=True)])
        if not reason:
            return
        if _warn(self.frame, lambda: data.void_transaction(
                int(sel[0]), reason=reason["reason"])) is not None:
            self._show_learner()
            self.load()
            self.on_change()

    def load(self) -> None:
        self.tree.delete(*self.tree.get_children())
        today = _dt.date.today().isoformat()
        rows = _warn(self.frame, lambda: data.list_transactions(
            date_from=today, date_to=today,
            till=self.till.get().strip() or None)) or []
        total = 0
        for t in rows:
            if t.txn_type == data.PURCHASE and not t.voided:
                total += t.gross_pence
            tag = "voided" if t.voided else t.txn_type
            self.tree.insert("", "end", iid=str(t.txn_id), values=(
                t.txn_id, t.at[11:16], t.student_id, t.student_name,
                t.txn_type, data.money(t.gross_pence) if t.gross_pence else "",
                data.money(t.free_meal_pence) if t.free_meal_pence else "",
                data.money(-t.amount_pence) if t.txn_type == data.PURCHASE
                else data.money(t.amount_pence), t.id_method or t.method or "",
                t.items or t.note or ""), tags=(tag,))
        self.total_lbl.configure(text=f"Sales today: {data.money(total)}")


def open_till_window(parent=None) -> None:
    data.init_db()
    bio.init_db()
    win, nb = make_window(parent, "Catering Till")
    till = TillFrame(nb)
    nb.add(till.frame, text="Till")


# ── Office window ───────────────────────────────────────────────────

def open_cashless_catering_window(parent=None) -> None:
    data.init_db()
    bio.init_db()
    win, nb = make_window(parent, "Cashless Catering")
    tabs: list = []

    def refresh_all(_x=None) -> None:
        for t in tabs:
            t.refresh()

    till = TillFrame(nb, on_change=refresh_all)
    nb.add(till.frame, text="Till")

    def sid_of(tab) -> str | None:
        return tab.selected()

    # ── Accounts ──
    def acct_rows(views):
        out = []
        for v in views:
            tag = ("left" if v.student_status == "Left" and v.balance_pence > 0
                   else "closed" if v.account_status == data.CLOSED
                   else "low" if v.is_low and v.account_status == data.OPEN
                   else "")
            out.append((v.student_id,
                        (v.student_id, v.student_name, v.student_status,
                         v.account_status, data.money(v.balance_pence),
                         data.money(v.threshold_pence),
                         "Yes" if v.has_pin else "", v.card_number or "",
                         v.biometric, v.last_activity or ""),
                        (tag,) if tag else ()))
        return out

    acct_cols = [("sid", "Student ID", 90), ("name", "Name", 170),
                 ("sstatus", "Student", 80), ("astatus", "Account", 90),
                 ("bal", "Balance", 80), ("thr", "Low below", 80),
                 ("pin", "PIN", 50), ("card", "ID card", 110),
                 ("bio", "Biometric", 260), ("last", "Last activity", 130)]

    def accounts_loader(f):
        return acct_rows(data.list_accounts(
            search=f.get("search"), low_only=bool(f.get("low")),
            include_left=bool(f.get("left")),
            with_account_only=bool(f.get("has"))))

    def open_acct(tab):
        sid = sid_of(tab)
        if sid:
            data.open_account(sid)
            refresh_all()

    def set_pin(tab):
        sid = sid_of(tab)
        if not sid:
            return
        v = form_dialog(win, "Set till PIN", [
            Field("pin", "New PIN (4–6 digits)", required=True)])
        if v:
            data.set_pin(sid, v["pin"])
            messagebox.showinfo("PIN", "PIN set. Give it to the learner "
                                "privately.", parent=win)
            refresh_all()

    def clear_pin(tab):
        sid = sid_of(tab)
        if sid and messagebox.askyesno("PIN", "Remove this learner's PIN?",
                                       parent=win):
            data.clear_pin(sid)
            refresh_all()

    def cash(tab):
        sid = sid_of(tab)
        if not sid:
            return
        v = form_dialog(win, "Cash top-up", [
            Field("amount", "Amount (£)", required=True),
            Field("note", "Note")])
        if v:
            t = data.cash_topup(sid, v["amount"], till="Office", note=v["note"])
            messagebox.showinfo("Top-up", f"Added {data.money(t.amount_pence)}"
                                + (f"; receipt #{t.receipt_id}" if t.receipt_id
                                   else ""), parent=win)
            refresh_all()

    def bursary(tab):
        sid = sid_of(tab)
        if not sid:
            return
        awards = data.meal_bursaries(sid)
        if not awards:
            messagebox.showwarning(
                "Bursary top-up", "This learner has no approved meal "
                "bursary with money left.", parent=win)
            return
        opts = [f"{a.app.application_id} — {a.app.bursary_type} "
                f"({a.app.academic_year or ''}) £{a.remaining:.2f} left"
                for a in awards]
        v = form_dialog(win, "Top up from meal bursary", [
            Field("award", "Bursary award", "combo", opts, required=True,
                  width=50),
            Field("amount", "Amount (£)", required=True),
            Field("note", "Note")])
        if v:
            data.bursary_topup(sid, int(option_key(v["award"])), v["amount"],
                               note=v["note"])
            refresh_all()

    def threshold(tab):
        sid = sid_of(tab)
        if not sid:
            return
        v = form_dialog(win, "Low-balance threshold", [
            Field("amount", "Warn below (£; blank = college default)")])
        if v is not None:
            data.set_low_balance(sid, v["amount"] or None)
            refresh_all()

    def refund(tab):
        sid = sid_of(tab)
        if not sid:
            return
        v = form_dialog(win, "Refund balance", [
            Field("method", "Method", "combo", data.REFUND_METHODS,
                  required=True),
            Field("reference", "Reference"),
            Field("reason", "Reason", required=True),
            Field("close", "Close the account", "check")])
        if v and messagebox.askyesno(
                "Refund", f"Refund the whole balance "
                f"({data.money(data.balance_pence(sid))})?", parent=win):
            data.refund_balance(sid, method=v["method"],
                                reference=v["reference"], reason=v["reason"],
                                close=v["close"])
            refresh_all()

    def statement(tab):
        sid = sid_of(tab)
        if not sid:
            return
        v = data.account_view(sid)
        rows = data.list_transactions(student_id=sid, limit=200)
        dlg = tk.Toplevel(win)
        dlg.title(f"Statement — {v.student_name}")
        dlg.transient(win)
        ttk.Button(dlg, text="Close", command=dlg.destroy).pack(
            side="bottom", anchor="e", padx=8, pady=8)
        txt = tk.Text(dlg, width=110, height=28, font=("TkFixedFont",))
        txt.pack(fill="both", expand=True, padx=8, pady=8)
        lines = [f"{v.student_name} ({sid})  Balance {data.money(v.balance_pence)}"
                 f"  Account {v.account_status}",
                 f"Biometric: {v.biometric}   {v.free_meal_today}", ""]
        lines += [f"{t.at[:16]}  {t.txn_type:<9} {data.money(t.amount_pence):>9}"
                  f"  {('free ' + data.money(t.free_meal_pence)) if t.free_meal_pence else '':<12}"
                  f" {t.method or ''} {t.id_method or ''} {t.items or t.note or ''}"
                  + ("  (voided)" if t.voided else "") for t in rows]
        txt.insert("1.0", "\n".join(lines))
        txt.configure(state="disabled")

    tabs.append(TableTab(
        nb, "Accounts", acct_cols, accounts_loader,
        filters=[Field("search", "Search", width=16),
                 Field("low", "Low balance only", "check"),
                 Field("has", "With account only", "check"),
                 Field("left", "Include leavers", "check")],
        actions=[("Open / re-open", _w(win, open_acct)),
                 ("Cash top-up", _w(win, cash)),
                 ("Bursary top-up", _w(win, bursary)),
                 ("Set PIN", _w(win, set_pin)),
                 ("Remove PIN", _w(win, clear_pin)),
                 ("Low-balance level", _w(win, threshold)),
                 ("Refund balance", _w(win, refund)),
                 ("Statement", _w(win, statement))],
        on_double=_w(win, statement), tag_colours=_ACCOUNT_TAGS))

    # ── Transactions ──
    def txn_loader(f):
        return [(t.txn_id,
                 (t.txn_id, t.at[:16], t.student_id, t.student_name,
                  t.txn_type, data.money(t.amount_pence),
                  data.money(t.gross_pence) if t.gross_pence else "",
                  data.money(t.free_meal_pence) if t.free_meal_pence else "",
                  t.method or "", t.id_method or "", t.till or "",
                  t.reference or "", t.items or t.note or "",
                  t.recorded_by or ""),
                 ("voided",) if t.voided else (t.txn_type,))
                for t in data.list_transactions(
                    student_id=f.get("student"), date_from=f.get("from"),
                    date_to=f.get("to"), txn_type=f.get("type"),
                    till=f.get("till"), limit=2000)]

    def void(tab):
        tid = tab.selected()
        if not tid:
            return
        v = form_dialog(win, "Void transaction",
                        [Field("reason", "Reason", required=True)])
        if v:
            data.void_transaction(int(tid), reason=v["reason"])
            refresh_all()

    tabs.append(TableTab(
        nb, "Transactions",
        [("id", "#", 55), ("at", "When", 120), ("sid", "Student ID", 85),
         ("name", "Name", 150), ("type", "Type", 75),
         ("amount", "Balance effect", 90), ("gross", "Sale total", 80),
         ("free", "Free meal", 75), ("method", "Method", 80),
         ("idm", "Identified by", 95), ("till", "Till", 70),
         ("ref", "Reference", 140), ("items", "Details", 200),
         ("by", "By", 90)],
        txn_loader,
        filters=[Field("student", "Student ID", width=10),
                 Field("from", "From", width=10), Field("to", "To", width=10),
                 Field("type", "Type", "combo", data.TXN_TYPES, width=10),
                 Field("till", "Till", width=10)],
        actions=[("Void", _w(win, void))], tag_colours=_TXN_TAGS))

    tabs.append(TableTab(
        nb, "Low Balance", acct_cols,
        lambda f: acct_rows(data.low_balance_list()),
        actions=[("Cash top-up", _w(win, cash)),
                 ("Bursary top-up", _w(win, bursary)),
                 ("Statement", _w(win, statement))],
        tag_colours=_ACCOUNT_TAGS))

    def leaver_refund(tab):
        sid = sid_of(tab)
        if not sid:
            return
        v = form_dialog(win, "Refund on leaving", [
            Field("method", "Method", "combo", data.REFUND_METHODS,
                  required=True),
            Field("reference", "Reference (bank / cheque)")])
        if v:
            t = data.refund_on_leaving(sid, method=v["method"],
                                       reference=v["reference"])
            messagebox.showinfo(
                "Refund on leaving",
                (f"Refunded {data.money(-t.amount_pence)}; " if t else
                 "Nothing to refund; ") + "account closed.", parent=win)
            refresh_all()

    tabs.append(TableTab(
        nb, "Leavers", acct_cols,
        lambda f: acct_rows(data.leavers_with_balance()),
        actions=[("Refund and close", _w(win, leaver_refund)),
                 ("Statement", _w(win, statement))],
        tag_colours=_ACCOUNT_TAGS))

    # ── Biometric consent ──
    def register_loader(f):
        from education_system.systems.sixth_form.domain.learners.students import (
            students as _students,
        )
        names = {s.student_id: s.full_name for s in _students.list_students()}
        out = []
        for s in bio.register(include_left=bool(f.get("left"))):
            name = names.get(s.student_id, "")
            if f.get("search") and f["search"].lower() not in (
                    s.student_id + " " + name).lower():
                continue
            if f.get("allowed") and not s.allowed:
                continue
            out.append((s.student_id,
                        (s.student_id, name,
                         "" if s.age is None else s.age,
                         "Allowed" if s.allowed else "No", s.reason,
                         s.learner_consent.given_on if s.learner_consent else "",
                         (f"{s.parent_consent.given_by_name} "
                          f"{s.parent_consent.given_on}")
                         if s.parent_consent else "",
                         ", ".join(f"{o.raised_by} {o.raised_on}"
                                   for o in s.objections),
                         "Yes" if s.enrolled else ""),
                        ("allowed",) if s.allowed else
                        (("refused",) if s.objections or s.enrolled else ())))
        return out

    def rec_consent(tab):
        sid = sid_of(tab)
        if not sid:
            return
        v = form_dialog(win, "Record written consent", [
            Field("given_by", "Given by", "combo", bio.PARTIES, required=True),
            Field("name", "Name of person consenting", required=True),
            Field("relationship", "Relationship (parent/carer)"),
            Field("form", "Written form", "combo", bio.CONSENT_FORMS,
                  required=True),
            Field("doc", "Document reference / where filed"),
            Field("on", "Date signed (YYYY-MM-DD, blank = today)")])
        if v:
            bio.record_consent(sid, given_by=v["given_by"],
                               given_by_name=v["name"],
                               relationship=v["relationship"],
                               consent_form=v["form"], document_ref=v["doc"],
                               given_on=v["on"] or None)
            refresh_all()

    def withdraw(tab):
        sid = sid_of(tab)
        if not sid:
            return
        current = bio.list_consents(student_id=sid, current_only=True)
        if not current:
            messagebox.showwarning("Withdraw", "No current consent.", parent=win)
            return
        opts = [f"{c.consent_id} — {c.given_by} {c.given_by_name} "
                f"({c.given_on})" for c in current]
        v = form_dialog(win, "Withdraw consent", [
            Field("consent", "Consent", "combo", opts, required=True, width=50),
            Field("by", "Withdrawn by", "combo", bio.PARTIES, required=True),
            Field("name", "Name", required=True),
            Field("note", "Note", "text")])
        if v:
            bio.withdraw_consent(int(option_key(v["consent"])),
                                 withdrawn_by=v["by"],
                                 withdrawn_by_name=v["name"], note=v["note"])
            _remind_delete(sid)
            refresh_all()

    def object_(tab):
        sid = sid_of(tab)
        if not sid:
            return
        v = form_dialog(win, "Record objection", [
            Field("by", "Raised by", "combo", bio.PARTIES, required=True),
            Field("name", "Name", required=True),
            Field("how", "How", "combo", bio.OBJECTION_HOW, required=True),
            Field("note", "Note", "text")])
        if v:
            bio.record_objection(sid, raised_by=v["by"], raised_by_name=v["name"],
                                 how=v["how"], note=v["note"])
            _remind_delete(sid)
            refresh_all()

    def lift(tab):
        sid = sid_of(tab)
        if not sid:
            return
        objs = bio.list_objections(student_id=sid, active_only=True)
        if not objs:
            messagebox.showwarning("Lift objection", "No active objection.",
                                   parent=win)
            return
        v = form_dialog(win, "Lift objection", [
            Field("obj", "Objection", "combo",
                  [f"{o.objection_id} — {o.raised_by} {o.raised_by_name} "
                   f"({o.raised_on})" for o in objs], required=True, width=50),
            Field("note", "How they asked for it to be lifted", required=True)])
        if v:
            bio.lift_objection(int(option_key(v["obj"])), note=v["note"])
            refresh_all()

    def enrol(tab):
        sid = sid_of(tab)
        if sid:
            bio.enrol_template(sid)
            refresh_all()

    def deleted(tab):
        sid = sid_of(tab)
        if not sid:
            return
        v = form_dialog(win, "Template deleted",
                        [Field("note", "Who deleted it / supplier reference")])
        if v is not None:
            bio.confirm_template_deleted(sid, note=v["note"])
            refresh_all()

    def _remind_delete(sid: str) -> None:
        s = bio.status_for(sid)
        if s.enrolled and not s.allowed:
            messagebox.showwarning(
                "Delete template",
                "Biometric use has stopped for this learner. Their stored "
                "template must now be deleted from the reader — confirm it "
                "under 'Templates to Delete' once done.", parent=win)

    bio_actions = [("Record consent", _w(win, rec_consent)),
                   ("Withdraw consent", _w(win, withdraw)),
                   ("Record objection", _w(win, object_)),
                   ("Lift objection", _w(win, lift)),
                   ("Template enrolled", _w(win, enrol)),
                   ("Template deleted", _w(win, deleted))]
    tabs.append(TableTab(
        nb, "Biometric Consent",
        [("sid", "Student ID", 90), ("name", "Name", 170), ("age", "Age", 45),
         ("ok", "Biometric", 70), ("reason", "Reason", 300),
         ("lc", "Learner consent", 110), ("pc", "Parent consent", 190),
         ("obj", "Objections", 180), ("enr", "Enrolled", 70)],
        register_loader,
        filters=[Field("search", "Search", width=16),
                 Field("allowed", "Allowed only", "check"),
                 Field("left", "Include leavers", "check")],
        actions=bio_actions, tag_colours=_BIO_TAGS))

    tabs.append(TableTab(
        nb, "Consent Records",
        [("id", "#", 50), ("sid", "Student ID", 90), ("name", "Name", 160),
         ("by", "Given by", 90), ("who", "Name", 150), ("rel", "Relationship", 90),
         ("form", "Form", 140), ("doc", "Document", 120), ("on", "Signed", 90),
         ("age", "Age then", 60), ("status", "Status", 80),
         ("wd", "Withdrawn", 200)],
        lambda f: [(c.consent_id,
                    (c.consent_id, c.student_id, c.student_name, c.given_by,
                     c.given_by_name, c.relationship or "", c.consent_form,
                     c.document_ref or "", c.given_on,
                     "" if c.learner_age is None else c.learner_age, c.status,
                     f"{c.withdrawn_on} by {c.withdrawn_by} {c.withdrawn_by_name}"
                     if c.withdrawn_on else ""), ())
                   for c in bio.list_consents(
                       student_id=f.get("student"),
                       current_only=bool(f.get("current")))],
        filters=[Field("student", "Student ID", width=10),
                 Field("current", "Current only", "check")],
        actions=[]))

    tabs.append(TableTab(
        nb, "Objections",
        [("id", "#", 50), ("sid", "Student ID", 90), ("name", "Name", 160),
         ("by", "Raised by", 90), ("who", "Name", 150), ("on", "Date", 90),
         ("how", "How", 120), ("status", "Status", 70), ("note", "Note", 260)],
        lambda f: [(o.objection_id,
                    (o.objection_id, o.student_id, o.student_name, o.raised_by,
                     o.raised_by_name, o.raised_on, o.how, o.status,
                     o.lifted_note if o.status == bio.LIFTED else (o.note or "")),
                    ())
                   for o in bio.list_objections(
                       active_only=bool(f.get("active")))],
        filters=[Field("active", "Active only", "check")], actions=[]))

    tabs.append(TableTab(
        nb, "Templates to Delete",
        [("sid", "Student ID", 100), ("reason", "Why it must go", 420)],
        lambda f: [(s.student_id, (s.student_id, s.reason), ("refused",))
                   for s in bio.templates_to_delete()],
        actions=[("Template deleted", _w(win, deleted))],
        tag_colours=_BIO_TAGS))

    tabs.append(TableTab(
        nb, "Biometric Audit",
        [("at", "When", 140), ("sid", "Student ID", 90),
         ("event", "Event", 150), ("detail", "Detail", 460),
         ("actor", "By", 100)],
        lambda f: [(r["log_id"], (r["at"], r["student_id"] or "", r["event"],
                                  r["detail"] or "", r["actor"] or ""), ())
                   for r in bio.audit_log(student_id=f.get("student"))],
        filters=[Field("student", "Student ID", width=10)], actions=[]))

    # ── Settings / summary ──
    def settings_render():
        cfg = data.settings()
        return [
            "Cashless catering settings", "",
            f"  Smallest top-up:       {data.money(cfg['min_topup_pence'])}",
            f"  Largest top-up:        {data.money(cfg['max_topup_pence'])}",
            f"  Balance cap:           {data.money(cfg['max_balance_pence'])}",
            f"  Low balance below:     {data.money(cfg['low_balance_pence'])}",
            f"  PIN tries before lock: {cfg['pin_max_failures']}",
            f"  PIN lock (minutes):    {cfg['pin_lock_minutes']}", "",
            f"  Learner's own biometric consent from age: "
            f"{bio.learner_consent_age()}",
            "    (18 follows the Protection of Freedoms Act 2012 s.26 for",
            "     under-18s; a learner's objection always stops biometric use.)",
        ]

    sett = SummaryTab(nb, settings_render, label="Settings")
    tabs.append(sett)

    def change_setting():
        keys = list(data.DEFAULT_SETTINGS) + ["learner_consent_age"]
        v = form_dialog(win, "Change setting", [
            Field("key", "Setting", "combo", keys, required=True, width=30),
            Field("value", "New value (money in £)", required=True)])
        if not v:
            return
        if v["key"] == "learner_consent_age":
            _warn(win, lambda: bio.set_learner_consent_age(v["value"]))
        else:
            _warn(win, lambda: data.set_setting(v["key"], v["value"]))
        refresh_all()

    ttk.Button(sett.frame.winfo_children()[0], text="Change setting…",
               command=change_setting).pack(side="left", padx=6)

    def summary_render():
        s = data.summary()
        t = s.today
        assert t is not None
        lines = [
            "Cashless catering summary", "",
            f"  Accounts:            {s.accounts} ({s.open_accounts} open)",
            f"  Money held:          {data.money(s.total_balance_pence)}",
            f"  Low balance:         {s.low_balance}",
            f"  Leavers owed:        {s.leavers_owed} "
            f"({data.money(s.leavers_owed_pence)})",
            f"  With a PIN:          {s.with_pin}", "",
            f"Till report for {t.day}",
            f"  Sales:               {t.purchases} ({data.money(t.gross_pence)})",
            f"    paid by free meals {t.free_meals} ({data.money(t.free_meal_pence)})",
            f"    from balances      {data.money(t.charged_pence)}",
            f"  Voids:               {t.voids}",
            f"  Refunds:             {data.money(t.refunds_pence)}",
            f"  Cash taken:          {data.money(t.cash_taken_pence)}",
            "  Top-ups:"]
        lines += [f"    {k:<18} {data.money(v)}"
                  for k, v in t.topups_by_method.items()]
        lines += ["  Identified by:"]
        lines += [f"    {k:<18} {v}" for k, v in t.by_id_method.items()]
        lines += [f"  Biometric refusals:  {bio.refusals_on(t.day)}"]
        if t.by_till:
            lines += ["  By till:"]
            lines += [f"    {k:<18} {data.money(v)}" for k, v in t.by_till.items()]
        return lines

    tabs.append(SummaryTab(nb, summary_render))
