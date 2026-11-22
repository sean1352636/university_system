"""Fees tabs for over-19 and international learners: fee rules, learner
fee profiles, remissions/waivers, fee calculation and tuition invoices.
Added to ``build_fees_notebook`` after the original tabs."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import messagebox

from education_system.systems.sixth_form.domains.finance.domain import (
    finance_calendar as fc,
)
from education_system.systems.sixth_form.domains.finance.domain.fees import (
    fee_rules as fr,
    fees,
)
from education_system.systems.sixth_form.domains.finance.interfaces.gui import (
    _widgets as w,
)


def add_fee_rule_tabs(nb: ttk.Notebook) -> None:
    RulesTab(nb)
    InvoicesTab(nb)


def _yes(v: bool) -> str:
    return "Y" if v else "N"


class RulesTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Fee Rules & Profiles")
        ttk.Label(self.frame, text=(
            "Age is taken on 31 August before the academic year starts. "
            "Set the college's fees here — none are shipped. Check residency "
            "rules against current ESFA funding-eligibility guidance. A rule "
            "limited to an enrolment fee status (the ILR fee status) beats a "
            "general one; 19+ co-funded learners need a rule of their own. "
            "Enrolments' Funding & Fees screens use these same rules."),
            wraplength=1200).pack(fill="x", padx=10, pady=(8, 0))
        inner = ttk.Notebook(self.frame)
        inner.pack(fill="both", expand=True, padx=4, pady=4)

        f1 = ttk.Frame(inner)
        inner.add(f1, text="Fee Rules")
        w.button_bar(f1, [("Add Rule…", self.add_rule),
                          ("Edit Selected…", self.edit_rule),
                          ("Deactivate Selected", self.deactivate)])
        self.rules = w.Table(f1, [
            ("#", 40), ("Year", 70), ("Residency", 260), ("Age band", 120),
            ("Fee status", 110), ("Annual fee", 90), ("Priority", 60), ("Active", 50),
            ("Description", 300)])
        self.rules.pack(fill="both", expand=True, padx=8, pady=8)

        f2 = ttk.Frame(inner)
        inner.add(f2, text="Learner Fee Profiles")
        w.button_bar(f2, [("Set Profile…", self.set_profile)])
        self.profiles = w.Table(f2, [
            ("Student", 80), ("Name", 180), ("Residency", 300),
            ("Continuing", 80), ("EHCP", 50), ("Notes", 250), ("By", 100)])
        self.profiles.pack(fill="both", expand=True, padx=8, pady=8)

        f3 = ttk.Frame(inner)
        inner.add(f3, text="Remissions & Waivers")
        w.button_bar(f3, [("Add Remission…", self.add_remission),
                          ("Remove Selected", self.remove_remission)])
        self.rems = w.Table(f3, [
            ("#", 40), ("Student", 80), ("Year", 70), ("Type", 110),
            ("Value", 80), ("Reason", 200), ("Approved by", 110),
            ("On", 90), ("Notes", 250)])
        self.rems.pack(fill="both", expand=True, padx=8, pady=8)
        self.refresh()

    def refresh(self) -> None:
        self.rules.set_rows(
            [(r.rule_id, r.academic_year or "any",
              r.residency_category or "any", r.age_band,
              r.fee_status or "any", w.money(r.annual_fee), r.priority, _yes(r.active),
              r.description or "") for r in fr.list_rules()])
        from education_system.systems.sixth_form.domain.learners.students import (
            students,
        )
        names = {s.student_id: s.full_name for s in students.list_students()}
        self.profiles.set_rows(
            [(p.student_id, names.get(p.student_id, "?"),
              p.residency_category, _yes(p.continuing_learner),
              _yes(p.has_ehcp), p.notes or "", p.updated_by or "")
             for p in fr.list_profiles()])
        self.rems.set_rows(
            [(m.remission_id, m.student_id, m.academic_year,
              m.remission_type,
              "" if m.remission_type == "Full" else
              (f"{m.value:g}%" if m.remission_type == "Percentage"
               else w.money(m.value)), m.reason, m.approved_by,
              m.approved_on, m.notes or "") for m in fr.list_remissions()])

    def _rule_form(self, r: fr.FeeRule | None) -> dict | None:
        return w.ask_form(self.frame, "Fee rule", [
            ("academic_year", "Academic year (blank = any)", "entry",
             (r.academic_year or "") if r else "", None),
            ("residency_category", "Residency (blank = any)", "combo",
             (r.residency_category or "") if r else "",
             ["", *fr.RESIDENCY_CATEGORIES]),
            ("age_band", "Age band", "combo", r.age_band if r else "",
             fr.AGE_BANDS),
            ("fee_status", "Enrolment fee status (blank = any)", "combo",
             (r.fee_status or "") if r else "", ["", *fr.FEE_STATUSES]),
            ("annual_fee", "Annual fee (0 = free)", "entry",
             f"{r.annual_fee:.2f}" if r else "", None),
            ("description", "Description", "entry",
             (r.description or "") if r else "", None),
            ("priority", "Priority (lower wins a tie)", "entry",
             r.priority if r else 100, None),
            ("active", "Active", "check", r.active if r else True, None)])

    def add_rule(self) -> None:
        f = self._rule_form(None)
        if f and w.call(self.frame, lambda: fr.create_rule(f),
                        done="Rule added.") is not None:
            self.refresh()

    def edit_rule(self) -> None:
        rid = w.need_selection(self.frame, self.rules)
        r = fr.get_rule(rid) if rid is not None else None
        if r is None:
            return
        f = self._rule_form(r)
        if f and w.call(self.frame, lambda: fr.update_rule(rid, f),
                        done="Rule updated.") is not None:
            self.refresh()

    def deactivate(self) -> None:
        rid = w.need_selection(self.frame, self.rules)
        if rid is not None and w.call(
                self.frame, lambda: fr.deactivate_rule(rid)) is not None:
            self.refresh()

    def set_profile(self) -> None:
        f = w.ask_form(self.frame, "Learner fee profile", [
            ("student", "Student", "combo", "", w.student_choices()),
            ("res", "Residency", "combo", "", fr.RESIDENCY_CATEGORIES),
            ("cont", "Continuing a programme started before 19", "check",
             False, None),
            ("ehcp", "Has an EHCP", "check", False, None),
            ("notes", "Notes", "text", "", None)])
        if f and w.call(self.frame, lambda: fr.set_profile(
                w.student_id(f["student"]) or "",
                residency_category=f["res"] or "",
                continuing_learner=f["cont"], has_ehcp=f["ehcp"],
                notes=f["notes"], by=w.actor() or None),
                done="Profile saved.") is not None:
            self.refresh()

    def add_remission(self) -> None:
        f = w.ask_form(self.frame, "Fee remission / waiver", [
            ("student", "Student", "combo", "", w.student_choices()),
            ("year", "Academic year", "entry", fc.normalise_year(None),
             None),
            ("type", "Type", "combo", "Full", fr.REMISSION_TYPES),
            ("value", "Percentage or amount (not for Full)", "entry", "",
             None),
            ("reason", "Reason", "combo", "", fr.REMISSION_REASONS),
            ("by", "Approved by", "entry", w.actor(), None),
            ("notes", "Notes", "text", "", None)])
        if f and w.call(self.frame, lambda: fr.add_remission({
                "student_id": w.student_id(f["student"]),
                "academic_year": f["year"], "remission_type": f["type"],
                "value": f["value"], "reason": f["reason"],
                "approved_by": f["by"], "notes": f["notes"]}),
                done="Remission recorded.") is not None:
            self.refresh()

    def remove_remission(self) -> None:
        mid = w.need_selection(self.frame, self.rems)
        if mid is not None and messagebox.askyesno(
                "Remove", f"Remove remission #{mid}?", parent=self.frame):
            w.call(self.frame, lambda: fr.remove_remission(mid))
            self.refresh()


class InvoicesTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Tuition Invoices")
        bar = w.button_bar(self.frame, [
            ("Refresh", self.refresh),
            ("Calculate Fee…", self.calculate),
            ("Raise Invoice…", self.raise_one),
            ("Raise for Everyone…", self.raise_all),
            ("Pay Selected…", self.pay),
            ("Cancel Selected…", self.cancel),
        ])
        ttk.Label(bar, text="   Year").pack(side="left")
        self.year = tk.StringVar(value=fc.normalise_year(None))
        e = ttk.Entry(bar, textvariable=self.year, width=9)
        e.pack(side="left", padx=4)
        e.bind("<Return>", lambda _e: self.refresh())
        self.summary = ttk.Label(self.frame, text="")
        self.summary.pack(fill="x", padx=10)
        self.table = w.Table(self.frame, [
            ("#", 40), ("Number", 120), ("Student", 80), ("Year", 70),
            ("Age 31 Aug", 70), ("Band", 120), ("Residency", 220),
            ("Gross", 80), ("Remitted", 80), ("Net", 80), ("Paid", 80),
            ("Balance", 80), ("Status", 90), ("Issued", 90)])
        self.table.pack(fill="both", expand=True, padx=8, pady=8)
        self.refresh()

    def refresh(self) -> None:
        year = w.call(self.frame, lambda: fc.normalise_year(self.year.get()))
        if year is None:
            return
        rows = []
        for i in fr.list_invoices(academic_year=year):
            paid, bal, st = fr.invoice_balance(i)
            rows.append((i.invoice_id, i.invoice_number, i.student_id,
                         i.academic_year, i.age_on_31_aug or "",
                         i.age_band or "", i.residency_category or "",
                         w.money(i.gross_fee), w.money(i.remission_amount),
                         w.money(i.net_fee), w.money(paid), w.money(bal), st,
                         i.issued_on))
        self.table.set_rows(rows, alert=lambda r: r[12] == "Overdue")
        s = fr.summary(year)
        self.summary.configure(
            text=f"{year}: {s.invoices_issued} invoice(s) "
                 f"{w.money(s.invoiced_total)} · paid {w.money(s.paid_total)}"
                 f" · outstanding {w.money(s.outstanding_total)} · remitted "
                 f"{w.money(s.remitted_total)} · {s.profiles} profile(s), "
                 f"{s.rules} rule(s)")

    def _pick_student(self, title: str) -> str | None:
        f = w.ask_form(self.frame, title, [
            ("student", "Student", "combo", "", w.student_choices())])
        return w.student_id(f["student"]) if f else None

    def calculate(self) -> None:
        sid = self._pick_student("Calculate fee")
        if not sid:
            return
        calc = w.call(self.frame, lambda: fr.calculate_fee(
            sid, self.year.get()))
        if calc is not None:
            messagebox.showinfo(
                "Fee calculation",
                "\n".join(calc.explanation) + f"\n\nGross "
                f"{w.money(calc.gross_fee)} − remission "
                f"{w.money(calc.remission_amount)} = "
                f"{w.money(calc.net_fee)}", parent=self.frame)

    def raise_one(self) -> None:
        f = w.ask_form(self.frame, "Raise tuition invoice", [
            ("student", "Student", "combo", "", w.student_choices()),
            ("due", "Due date (blank = default)", "entry", "", None)])
        if not f:
            return
        inv = w.call(self.frame, lambda: fr.generate_invoice(
            w.student_id(f["student"]) or "", self.year.get(),
            issued_by=w.actor() or "unknown", due_date=f["due"]))
        if inv is not None:
            messagebox.showinfo("Invoice raised",
                                f"{inv.invoice_number}: "
                                f"{w.money(inv.net_fee)}", parent=self.frame)
            self.refresh()

    def raise_all(self) -> None:
        f = w.ask_form(self.frame, "Raise invoices for every profiled learner",
                       [("due", "Due date (blank = default)", "entry", "",
                         None)])
        if not f:
            return
        out = w.call(self.frame, lambda: fr.generate_invoices(
            self.year.get(), issued_by=w.actor() or "unknown",
            due_date=f["due"]))
        if out is not None:
            msg = (f"{len(out['raised'])} raised, {len(out['no_fee'])} owe "
                   f"nothing, {len(out['skipped'])} skipped")
            if out["skipped"]:
                msg += "\n\n" + "\n".join(out["skipped"][:20])
            messagebox.showinfo("Invoices", msg, parent=self.frame)
            self.refresh()

    def pay(self) -> None:
        iid = w.need_selection(self.frame, self.table)
        inv = fr.get_invoice(iid) if iid is not None else None
        if inv is None:
            return
        _p, bal, _s = fr.invoice_balance(inv)
        f = w.ask_form(self.frame, f"Pay {inv.invoice_number}", [
            ("amount", "Amount", "entry", f"{bal:.2f}", None),
            ("method", "Method", "combo", fees.PAYMENT_METHODS[0],
             fees.PAYMENT_METHODS),
            ("ref", "Reference", "entry", "", None),
            ("receipt", "Issue a receipt", "check", True, None)])
        if not f:
            return
        out = w.call(self.frame, lambda: fr.pay_invoice(
            iid, amount=w.num(f["amount"]), method=f["method"] or "",
            recorded_by=w.actor() or "unknown", reference=f["ref"],
            receipt=f["receipt"]))
        if out is not None:
            pay, rec = out
            messagebox.showinfo(
                "Paid", f"Payment #{pay.payment_id} recorded"
                + (f"; receipt {getattr(rec, 'receipt_number', '')}"
                   if rec else ""), parent=self.frame)
            self.refresh()

    def cancel(self) -> None:
        iid = w.need_selection(self.frame, self.table)
        if iid is None:
            return
        f = w.ask_form(self.frame, "Cancel invoice",
                       [("reason", "Reason", "entry", "", None)])
        if f and w.call(self.frame, lambda: fr.cancel_invoice(
                iid, reason=f["reason"] or "", by=w.actor() or "unknown"),
                done="Invoice cancelled.") is not None:
            self.refresh()
