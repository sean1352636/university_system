"""Trips tab: refunds (Refunded / Part refunded / Refund due), paying a
place from a bursary award, and trip costing for department budgets.
Added to ``build_trips_notebook`` after the original tabs."""

from __future__ import annotations

import tkinter as tk
from datetime import date as _date
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import messagebox

from education_system.systems.sixth_form.domains.finance.domain.trips import (
    trips as t,
)
from education_system.systems.sixth_form.domains.finance.interfaces.gui import (
    _widgets as w,
)


def add_refunds_tab(nb: ttk.Notebook) -> "RefundsTab":
    return RefundsTab(nb)


class RefundsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Refunds & Bursary")
        bar = w.button_bar(self.frame, [
            ("Refresh", self.refresh),
            ("Record Refund…", self.refund),
            ("Pay Place from Bursary…", self.from_bursary),
            ("Trip Costing…", self.costing),
        ])
        self.due_only = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar, text="Refunds due only", variable=self.due_only,
                        command=self.refresh).pack(side="left", padx=10)
        self.summary = ttk.Label(self.frame, text="")
        self.summary.pack(fill="x", padx=10)
        pane = ttk.PanedWindow(self.frame, orient="vertical")
        pane.pack(fill="both", expand=True, padx=8, pady=8)
        top = ttk.Frame(pane)
        pane.add(top, weight=3)
        self.bookings = w.Table(top, [
            ("Booking", 60), ("Trip", 200), ("Student", 80), ("Name", 160),
            ("Status", 90), ("Paid", 80), ("Refunded", 80), ("Balance", 80),
            ("Still owed", 80), ("State", 100)], height=12)
        self.bookings.pack(fill="both", expand=True)
        low = ttk.LabelFrame(pane, text="Refunds recorded")
        pane.add(low, weight=2)
        w.button_bar(low, [("Remove Selected Refund (recorded in error)…",
                            self.remove)])
        self.refunds = w.Table(low, [
            ("#", 50), ("Booking", 60), ("Date", 90), ("Amount", 80),
            ("Method", 130), ("Payment", 60), ("Reason", 300), ("By", 100),
            ("Ref", 120)], height=6)
        self.refunds.pack(fill="both", expand=True, padx=4, pady=4)
        self.refresh()

    def refresh(self) -> None:
        views = (t.refunds_due() if self.due_only.get()
                 else [v for v in t.list_booking_views()
                       if v.paid > 0 or v.refunded > 0])
        self.bookings.set_rows(
            [(v.booking.booking_id, v.trip.name, v.booking.student_id,
              v.student_name, v.booking.status, w.money(v.paid),
              w.money(v.refunded), w.money(v.balance),
              w.money(v.refund_due) if v.refund_due else "", v.payment_state)
             for v in views],
            alert=lambda r: r[9] in ("Refund due", "Part refunded"))
        s = t.summary()
        self.summary.configure(
            text=f"Refunds due: {s.refunds_due_count} "
                 f"({w.money(s.refunds_due_value)}) · refunded to date "
                 f"{w.money(s.total_refunded)} · places paid from bursaries "
                 f"{w.money(s.bursary_funded)}")
        self.refunds.set_rows(
            [(r.refund_id, r.booking_id, r.refunded_on, w.money(r.amount),
              r.method, r.payment_id or "", r.reason, r.refunded_by,
              r.reference or "") for r in t.list_refunds()])

    def refund(self) -> None:
        bid = w.need_selection(self.frame, self.bookings)
        v = t.view_booking(bid) if bid is not None else None
        if v is None:
            return
        pays = t.list_payments(booking_id=bid)
        pay_opts = [""] + [
            f"{p.payment_id} — {w.money(p.amount)} {p.method} {p.paid_on}"
            + (" (bursary)" if t.bursary_link(p.payment_id)[0] else "")
            for p in pays]
        f = w.ask_form(self.frame, f"Refund — booking #{bid}", [
            ("amount", "Amount", "entry",
             f"{max(v.paid - v.refunded, 0):.2f}", None),
            ("method", "Method", "combo", t.DEFAULT_REFUND_METHOD,
             t.REFUND_METHODS),
            ("payment", "Against payment (required for Return to bursary)",
             "combo", "", pay_opts),
            ("on", "Date", "entry", _date.today().isoformat(), None),
            ("reason", "Reason", "entry", "", None),
            ("ref", "Reference", "entry", "", None)],
            note=f"{v.student_name} · {v.trip.name} · paid "
                 f"{w.money(v.paid)}, refunded {w.money(v.refunded)}. "
                 "'Return to bursary' must refund the whole bursary payment "
                 "and reverses its bursary disbursement.")
        if not f:
            return
        pid = (f["payment"] or "").split(" — ", 1)[0] or None
        if w.call(self.frame, lambda: t.add_refund(bid, {
                "amount": f["amount"], "method": f["method"],
                "payment_id": pid, "refunded_on": f["on"],
                "reason": f["reason"], "refunded_by": w.actor() or "unknown",
                "reference": f["ref"]}), done="Refund recorded.") is not None:
            self.refresh()

    def remove(self) -> None:
        rid = w.need_selection(self.frame, self.refunds)
        if rid is None:
            return
        f = w.ask_form(self.frame, f"Remove refund #{rid}",
                       [("why", "Why (recorded in error because…)", "entry",
                         "", None)])
        if f and w.call(self.frame, lambda: t.delete_refund(
                rid, reason=f["why"] or "", by=w.actor()),
                done="Refund removed.") is not None:
            self.refresh()

    def from_bursary(self) -> None:
        if self.due_only.get():
            self.due_only.set(False)
            self.refresh()
        bid = w.need_selection(self.frame, self.bookings)
        v = t.view_booking(bid) if bid is not None else None
        if v is None:
            return
        from education_system.systems.sixth_form.domains.finance.domain.bursaries import (
            bursaries,
        )
        awards = [a for a in bursaries.list_views(
            student_id=v.booking.student_id)
            if a.app.is_approved and a.remaining > 0]
        if not awards:
            messagebox.showinfo("No bursary", f"{v.student_name} has no "
                                "approved bursary with money left.",
                                parent=self.frame)
            return
        opts = [f"{a.app.application_id} — {a.app.bursary_type} "
                f"({w.money(a.remaining)} left)" for a in awards]
        f = w.ask_form(self.frame, f"Pay booking #{bid} from a bursary", [
            ("award", "Bursary award", "combo", opts[0], opts),
            ("amount", "Amount", "entry", f"{v.balance:.2f}", None)],
            note=f"{v.student_name} · {v.trip.name} · balance "
                 f"{w.money(v.balance)}")
        if not f:
            return
        aid = int((f["award"] or "0").split(" — ", 1)[0])
        if w.call(self.frame, lambda: t.fund_from_bursary(
                bid, aid, amount=w.num(f["amount"]),
                recorded_by=w.actor() or "unknown"),
                done="Paid from bursary.") is not None:
            self.refresh()

    def costing(self) -> None:
        from education_system.systems.sixth_form.domain.staff.departments import (
            department_budgets as db,
        )
        trips = t.list_trips()
        if not trips:
            return
        depts = w.call(self.frame, db.list_departments) or []
        topts = [f"{x.trip_id} — {x.name}" for x in trips]
        dopts = [""] + [f"{i} — {n}" for i, n in depts]
        f = w.ask_form(self.frame, "Trip costing", [
            ("trip", "Trip", "combo", topts[0], topts),
            ("dept", "Department", "combo", "", dopts),
            ("cost", "Cost to the college of running it", "entry", "",
             None)],
            note="Used for department budget-vs-spend. Learner payments "
                 "and receipts count as income against it.")
        if not f:
            return
        tid = int((f["trip"] or "0").split(" — ", 1)[0])
        did = (f["dept"] or "").split(" — ", 1)[0] or None
        if w.call(self.frame, lambda: t.set_trip_costing(
                tid, department_id=did, running_cost=f["cost"]),
                done="Costing saved.") is not None:
            self.refresh()
