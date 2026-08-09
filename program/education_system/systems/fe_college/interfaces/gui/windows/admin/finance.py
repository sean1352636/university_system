"""Admin finance — fees, payments, bursaries and funding allocations.

Four tabs rather than four screens, because the questions are related: what is
owed, what has been paid, what support has been awarded, and how the college is
delivering against its allocation.
"""

from __future__ import annotations

import logging
from datetime import date
from tkinter import ttk

from education_system.systems.fe_college.config import (
    BURSARY_TYPES,
    FEE_TYPES,
    FUNDING_SOURCES,
    PAYMENT_METHODS,
)
from education_system.systems.fe_college.domain.finance.bursaries import (
    BURSARY_STATUSES,
    Bursary,
)
from education_system.systems.fe_college.domain.finance.fees import FEE_STATUSES, Fee
from education_system.systems.fe_college.domain.finance.funding import FundingAllocation
from education_system.systems.fe_college.domain.finance.payments import Payment
from education_system.systems.fe_college.domain.students.models import ValidationError
from education_system.systems.fe_college.infrastructure.persistence.repositories import (
    finance_repository as finance_repo,
)
from education_system.systems.fe_college.interfaces.gui import widgets as w

logger = logging.getLogger(__name__)

TITLE = "Finance"


def open_window(host) -> None:
    Screen(host)


class Screen:
    def __init__(self, host):
        self.host = host
        self.ctl = host.ctl
        host.clear_content()
        parent = host.content_frame

        w.page_header(
            parent, TITLE,
            "Fees charged and collected, bursary awards, and delivery against "
            "the funding allocation.",
            actions=[("↻ Refresh", self.refresh)],
        )

        self.totals_holder = ttk.Frame(parent)
        self.totals_holder.pack(fill="x")

        notebook = ttk.Notebook(parent)
        notebook.pack(fill="both", expand=True, pady=(4, 0))

        self.fees_tab = ttk.Frame(notebook, padding=8)
        self.payments_tab = ttk.Frame(notebook, padding=8)
        self.bursaries_tab = ttk.Frame(notebook, padding=8)
        self.funding_tab = ttk.Frame(notebook, padding=8)
        notebook.add(self.fees_tab, text="Fees")
        notebook.add(self.payments_tab, text="Payments")
        notebook.add(self.bursaries_tab, text="Bursaries")
        notebook.add(self.funding_tab, text="Funding")

        self._build_fees()
        self._build_payments()
        self._build_bursaries()
        self._build_funding()
        self.refresh()

    # ── Tabs ───────────────────────────────────────────────────────────────

    def _build_fees(self) -> None:
        self.fee_filters = w.FilterBar(
            self.fees_tab, self._refresh_fees, search=False,
            filters=[("status", "Status", FEE_STATUSES)],
        )
        self.fees_table = w.DataTable(self.fees_tab, [
            ("student", "Learner", 160),
            ("id", "ID", 90),
            ("type", "Type", 100),
            ("description", "Description", 220),
            ("amount", "Charged", 90, "e"),
            ("paid", "Paid", 90, "e"),
            ("balance", "Balance", 90, "e"),
            ("due", "Due", 95),
            ("status", "Status", 90),
        ], height=13)
        w.button_bar(self.fees_tab, [
            ("Raise a fee", self.raise_fee),
            ("Record payment", self.record_payment),
            ("Waive", self.waive_fee),
        ])

    def _build_payments(self) -> None:
        self.payments_table = w.DataTable(self.payments_tab, [
            ("date", "Paid on", 100),
            ("student", "Learner", 160),
            ("amount", "Amount", 100, "e"),
            ("method", "Method", 130),
            ("reference", "Reference", 140),
            ("status", "Status", 100),
            ("note", "Note", 220),
        ], height=15)
        w.button_bar(self.payments_tab, [("Reverse a payment", self.reverse_payment)])

    def _build_bursaries(self) -> None:
        self.bursaries_table = w.DataTable(self.bursaries_tab, [
            ("student", "Learner", 170),
            ("type", "Type", 150),
            ("status", "Status", 100),
            ("awarded", "Awarded", 95, "e"),
            ("paid", "Paid", 95, "e"),
            ("balance", "Balance", 95, "e"),
            ("condition", "Attendance condition", 150),
            ("meets", "Meets it", 80),
        ], height=13)
        w.button_bar(self.bursaries_tab, [
            ("+ New award", self.new_bursary),
            ("Approve", self.approve_bursary),
        ])

    def _build_funding(self) -> None:
        self.funding_table = w.DataTable(self.funding_tab, [
            ("source", "Funding stream", 220),
            ("year", "Year", 90),
            ("allocated", "Allocated", 120, "e"),
            ("earned", "Earned", 120, "e"),
            ("variance", "Variance", 120, "e"),
            ("delivery", "Delivery", 90, "e"),
            ("status", "Position", 240),
        ], height=8)
        w.button_bar(self.funding_tab, [("Set allocation", self.set_allocation)])

        self.funding_report_table = w.DataTable(self.funding_tab, [
            ("course", "Course", 95),
            ("title", "Title", 240),
            ("band", "Band", 165),
            ("starts", "Starts", 60, "e"),
            ("retained", "Retained", 70, "e"),
            ("income", "Est. income", 110, "e"),
            ("lost", "Lost to withdrawal", 130, "e"),
        ], height=8)

    # ── Data ───────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        try:
            totals = self._refresh_totals()
            self._refresh_fees()
            self._refresh_payments()
            self._refresh_bursaries()
            self._refresh_funding()
        except Exception as exc:
            logger.exception("Could not load FE College finance data")
            w.error(self.host, TITLE, f"Could not load finance data: {exc}")
            return
        self.host.set_status(
            f"{w.money(totals['charged'])} charged · "
            f"{w.money(totals['paid'])} collected · "
            f"{w.money(totals['outstanding'])} outstanding"
        )

    def _refresh_totals(self) -> dict[str, float]:
        w.clear(self.totals_holder)
        totals = finance_repo.outstanding_totals()
        bursaries = finance_repo.bursary_totals()
        collected = (
            round((totals["charged"] - totals["waived"] - totals["outstanding"])
                  / (totals["charged"] - totals["waived"]) * 100, 1)
            if totals["charged"] - totals["waived"] > 0 else None
        )
        w.kpi_row(self.totals_holder, [
            ("Charged", w.money(totals["charged"]), "all fees raised", "plain"),
            ("Collected", w.money(totals["paid"]),
             f"{w.pct(collected)} of what is due", "good"),
            ("Outstanding", w.money(totals["outstanding"]),
             "still owed", "warn" if totals["outstanding"] > 0 else "good"),
            ("Waived", w.money(totals["waived"]), "written off or waived", "muted"),
            ("Bursaries", w.money(bursaries["awarded"]),
             f"{bursaries['learners']} learner(s) · {w.money(bursaries['paid'])} paid",
             "plain"),
        ])
        return totals

    def _refresh_fees(self) -> None:
        filters = self.fee_filters.values()
        fees = finance_repo.list_fees(**filters)
        learners = {s.student_id: s for s in self.ctl.students.search()}
        rows = []
        for fee in fees:
            learner = learners.get(fee.student_id)
            overdue = fee.is_overdue()
            rows.append({
                "student": learner.full_name if learner else fee.student_id,
                "id": fee.student_id,
                "type": fee.fee_type,
                "description": fee.description or "—",
                "amount": w.money(fee.amount),
                "paid": w.money(fee.amount_paid),
                "balance": w.money(fee.balance),
                "due": w.when(fee.due_date),
                "status": fee.status,
                "_tone": "bad" if overdue else ("good" if fee.status == "paid" else "plain"),
                "_obj": fee,
            })
        self.fees_table.set_rows(rows)
        self.fee_filters.set_count(len(rows), "fee")

    def _refresh_payments(self) -> None:
        payments = finance_repo.list_payments()
        learners = {s.student_id: s for s in self.ctl.students.search()}
        self.payments_table.set_rows([
            {
                "date": w.when(p.paid_on),
                "student": (
                    learners[p.student_id].full_name
                    if p.student_id in learners else p.student_id
                ),
                "amount": w.money(p.signed_amount if p.is_reversal else p.amount),
                "method": p.method,
                "reference": p.reference or "—",
                "status": "reversal" if p.is_reversal else p.status,
                "note": p.note or "—",
                "_tone": "bad" if p.is_reversal else "plain",
                "_obj": p,
            }
            for p in payments
        ])

    def _refresh_bursaries(self) -> None:
        bursaries = finance_repo.list_bursaries()
        learners = {s.student_id: s for s in self.ctl.students.search()}
        rows = []
        for b in bursaries:
            attendance = self.ctl.attendance.for_student(b.student_id)
            meets = b.meets_condition(attendance.attendance_pct)
            rows.append({
                "student": (
                    learners[b.student_id].full_name
                    if b.student_id in learners else b.student_id
                ),
                "type": b.bursary_type,
                "status": b.status,
                "awarded": w.money(b.amount_awarded),
                "paid": w.money(b.amount_paid),
                "balance": w.money(b.balance),
                "condition": (
                    "none (statutory)" if b.is_statutory
                    else f"{b.attendance_condition_pct:g}%"
                ),
                "meets": w.yes_no(meets),
                "_tone": "good" if meets else "warn",
                "_obj": b,
            })
        self.bursaries_table.set_rows(rows)

    def _refresh_funding(self) -> None:
        allocations = finance_repo.list_allocations()
        self.funding_table.set_rows([
            {
                "source": a.funding_source,
                "year": a.academic_year,
                "allocated": w.money(a.allocated),
                "earned": w.money(a.earned),
                "variance": w.money(a.variance),
                "delivery": w.pct(a.delivery_pct),
                "status": a.status,
                "_tone": "good" if "on plan" in a.status else "warn",
                "_obj": a,
            }
            for a in allocations
        ])
        self.funding_report_table.set_rows([
            {
                "course": r["course_id"],
                "title": r["title"],
                "band": r["band"],
                "starts": r["starts"],
                "retained": r["retained"],
                "income": w.money(r["estimated_income"]),
                "lost": w.money(r["lost_to_withdrawal"]),
                "_tone": "warn" if r["lost_to_withdrawal"] > 0 else "plain",
            }
            for r in self.ctl.reports.funding_report()
        ])

    # ── Actions ────────────────────────────────────────────────────────────

    def _pick_learner(self, title: str) -> str | None:
        learners = self.ctl.students.search()
        if not learners:
            w.info(self.host, title, "There are no learners on roll.")
            return None
        options = [f"{s.student_id} — {s.full_name}" for s in learners]
        result = w.ask(self.host, title, [("learner", "Learner", "choice", options)])
        return result["learner"].split(" — ")[0] if result else None

    def raise_fee(self) -> None:
        student_id = self._pick_learner("Raise a fee")
        if student_id is None:
            return
        courses = [""] + [c.course_id for c in self.ctl.courses.list_all()]
        result = w.ask(self.host, f"Raise a fee — {student_id}", [
            ("fee_type", "Type", "choice", FEE_TYPES),
            ("amount", "Amount (£)", "float"),
            ("description", "Description", "text"),
            ("course_id", "Course", "choice", courses),
            ("due_date", "Due date", "date"),
        ], initial={"fee_type": FEE_TYPES[0],
                    "due_date": date.today().isoformat()})
        if result is None:
            return
        try:
            finance_repo.raise_fee(Fee(
                fee_id=None,
                student_id=student_id,
                fee_type=result["fee_type"],
                amount=result["amount"],
                description=result["description"],
                course_id=result["course_id"],
                academic_year=self.ctl.academic_year,
                due_date=result["due_date"],
                raised_on=date.today(),
            ))
        except ValidationError as exc:
            w.error(self.host, "Raise a fee", str(exc))
            return
        self.refresh()

    def record_payment(self) -> None:
        fee = self.fees_table.require_selection("a fee")
        if fee is None:
            return
        if fee.balance <= 0:
            w.info(self.host, "Record payment",
                   "That fee has nothing left to pay.")
            return
        result = w.ask(self.host, f"Payment against {fee.fee_type} fee", [
            ("amount", "Amount (£)", "float"),
            ("method", "Method", "choice", PAYMENT_METHODS),
            ("reference", "Reference", "text"),
            ("paid_on", "Paid on", "date"),
        ], initial={"amount": fee.balance, "method": PAYMENT_METHODS[0],
                    "paid_on": date.today().isoformat()})
        if result is None:
            return
        try:
            finance_repo.record_payment(Payment(
                payment_id=None,
                fee_id=fee.fee_id,
                student_id=fee.student_id,
                amount=result["amount"],
                method=result["method"],
                reference=result["reference"],
                paid_on=result["paid_on"],
                received_by=self.ctl.staff_id,
            ))
        except ValidationError as exc:
            w.error(self.host, "Record payment", str(exc))
            return
        self.refresh()

    def reverse_payment(self) -> None:
        payment = self.payments_table.require_selection("a payment")
        if payment is None:
            return
        if payment.is_reversal:
            w.info(self.host, "Reverse", "That row is already a reversal.")
            return
        result = w.ask(self.host, "Reverse a payment", [
            ("amount", "Amount to reverse (£)", "float"),
            ("note", "Reason", "text"),
        ], initial={"amount": payment.amount})
        if result is None:
            return
        try:
            finance_repo.record_payment(Payment(
                payment_id=None,
                fee_id=payment.fee_id,
                student_id=payment.student_id,
                amount=result["amount"],
                method=payment.method,
                paid_on=date.today(),
                received_by=self.ctl.staff_id,
                is_reversal=True,
                note=result["note"],
            ))
        except ValidationError as exc:
            w.error(self.host, "Reverse", str(exc))
            return
        self.refresh()

    def waive_fee(self) -> None:
        fee = self.fees_table.require_selection("a fee")
        if fee is None:
            return
        result = w.ask(self.host, "Waive a fee", [
            ("waiver_reason", "Reason for waiving", "text"),
        ])
        if result is None:
            return
        fee.status = "waived"
        fee.waiver_reason = result["waiver_reason"]
        try:
            finance_repo.update_fee(fee)
        except ValidationError as exc:
            w.error(self.host, "Waive", str(exc))
            return
        self.refresh()

    def new_bursary(self) -> None:
        student_id = self._pick_learner("New bursary award")
        if student_id is None:
            return
        result = w.ask(self.host, f"Bursary — {student_id}", [
            ("bursary_type", "Type", "choice", BURSARY_TYPES),
            ("amount_awarded", "Amount (£)", "float"),
            ("attendance_condition_pct", "Attendance condition (%)", "float"),
            ("evidence", "Evidence", "text"),
            ("notes", "Notes", "multiline"),
        ], initial={"bursary_type": BURSARY_TYPES[0],
                    "attendance_condition_pct": 90.0})
        if result is None:
            return
        try:
            finance_repo.save_bursary(Bursary(
                bursary_id=None,
                student_id=student_id,
                bursary_type=result["bursary_type"],
                status="applied",
                amount_awarded=result["amount_awarded"],
                academic_year=self.ctl.academic_year,
                attendance_condition_pct=result["attendance_condition_pct"],
                applied_on=date.today(),
                evidence=result["evidence"],
                notes=result["notes"],
            ))
        except ValidationError as exc:
            w.error(self.host, "Bursary", str(exc))
            return
        self.refresh()

    def approve_bursary(self) -> None:
        bursary = self.bursaries_table.require_selection("a bursary")
        if bursary is None:
            return
        if not self.ctl.staff_id:
            w.warn(self.host, "Approve bursary",
                   "Your account is not linked to a staff record, so the "
                   "approval could not be attributed. Link it in Users first.")
            return
        result = w.ask(self.host, "Approve bursary", [
            ("status", "Decision", "choice", list(BURSARY_STATUSES)),
            ("amount_awarded", "Amount awarded (£)", "float"),
        ], initial={"status": "approved", "amount_awarded": bursary.amount_awarded})
        if result is None:
            return
        bursary.status = result["status"]
        bursary.amount_awarded = result["amount_awarded"]
        bursary.decided_on = date.today()
        bursary.decided_by = self.ctl.staff_id
        try:
            finance_repo.save_bursary(bursary)
        except ValidationError as exc:
            w.error(self.host, "Approve bursary", str(exc))
            return
        self.refresh()

    def set_allocation(self) -> None:
        result = w.ask(self.host, "Funding allocation", [
            ("funding_source", "Funding stream", "choice", FUNDING_SOURCES),
            ("academic_year", "Academic year", "text"),
            ("allocated", "Allocated (£)", "float"),
            ("earned", "Earned to date (£)", "float"),
            ("learner_count", "Learners", "int"),
            ("notes", "Notes", "multiline"),
        ], initial={"academic_year": self.ctl.academic_year})
        if result is None:
            return
        try:
            finance_repo.save_allocation(FundingAllocation(
                allocation_id=None, **result
            ))
        except ValidationError as exc:
            w.error(self.host, "Funding allocation", str(exc))
            return
        self.refresh()


__all__ = ["TITLE", "Screen", "open_window"]
