"""CLI for trip refunds, bursary-funded places and trip costing.
Reached from the Trips menu (see ``trips_cli._MENU``)."""

from __future__ import annotations

from datetime import date as _date

from education_system.systems.sixth_form.domains.finance.domain.trips import (
    trips as t,
)
from education_system.systems.sixth_form.domains.finance.interfaces.cli import (
    _prompts as ui,
)


def _who() -> str:
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    return access.current().username or ui.ask("Your name", required=True)


@ui.handler
def refunds_due() -> None:
    rows = t.refunds_due()
    ui.table(("Booking", "Trip", "Student", "Name", "Status", "Paid",
              "Refunded", "Still owed", "State"),
             [(v.booking.booking_id, v.trip.name[:22], v.booking.student_id,
               v.student_name[:20], v.booking.status, ui.money(v.paid),
               ui.money(v.refunded), ui.money(v.refund_due), v.payment_state)
              for v in rows], empty="(no refunds due)")
    print(f"\n  {ui.money(sum(v.refund_due for v in rows))} owed back across "
          f"{len(rows)} booking(s).")


@ui.handler
def record_refund() -> None:
    bid = ui.ask_int("Booking #")
    v = t.view_booking(bid)
    if v is None:
        raise t.ValidationError(f"No booking #{bid}")
    print(f"  {v.student_name} · {v.trip.name} · paid {ui.money(v.paid)} · "
          f"refunded {ui.money(v.refunded)} · {v.payment_state}")
    pays = t.list_payments(booking_id=bid)
    ui.table(("Payment", "Date", "Amount", "Method", "Bursary"),
             [(p.payment_id, p.paid_on, ui.money(p.amount), p.method,
               "#%s" % t.bursary_link(p.payment_id)[0]
               if t.bursary_link(p.payment_id)[0] else "")
              for p in pays], empty="(no payments)")
    method = ui.pick("Refund method", list(t.REFUND_METHODS),
                     default=t.DEFAULT_REFUND_METHOD)
    payment_id = None
    if method == "Return to bursary":
        payment_id = ui.ask_int("Bursary-funded payment #")
    else:
        payment_id = ui.ask_int("Against payment # (blank = none)",
                                required=False)
    default_amt = max(round(v.paid - v.refunded, 2), 0.0) or None
    if method == "Return to bursary" and payment_id:
        p = t.get_payment(payment_id)
        default_amt = p.amount if p else default_amt
    r = t.add_refund(bid, {
        "amount": ui.ask_money("Amount", default=default_amt),
        "method": method, "payment_id": payment_id,
        "refunded_on": ui.ask("Date", default=_date.today().isoformat()),
        "reason": ui.ask("Reason", required=True),
        "refunded_by": _who(),
        "reference": ui.ask("Reference") or None,
    })
    nv = t.view_booking(bid)
    print(f"\n  ✓ Refund #{r.refund_id} recorded — booking now "
          f"{nv.payment_state if nv else '?'}.")


@ui.handler
def list_refunds() -> None:
    trip_id = ui.ask_int("Trip # (blank = all)", required=False)
    rows = t.list_refunds(trip_id=trip_id)
    ui.table(("#", "Booking", "Date", "Amount", "Method", "Reason", "By"),
             [(r.refund_id, r.booking_id, r.refunded_on, ui.money(r.amount),
               r.method, r.reason[:30], r.refunded_by) for r in rows],
             empty="(no refunds)")


@ui.handler
def delete_refund() -> None:
    rid = ui.ask_int("Refund #")
    if ui.yes_no("Remove this refund (recorded in error)?"):
        if t.delete_refund(rid, reason=ui.ask("Why", required=True),
                           by=_who()):
            print("\n  ✓ Removed.")


@ui.handler
def pay_from_bursary() -> None:
    from education_system.systems.sixth_form.domains.finance.domain.bursaries import (
        bursaries,
    )
    bid = ui.ask_int("Booking #")
    v = t.view_booking(bid)
    if v is None:
        raise t.ValidationError(f"No booking #{bid}")
    awards = [a for a in bursaries.list_views(student_id=v.booking.student_id)
              if a.app.is_approved and a.remaining > 0]
    print(f"  {v.student_name} · {v.trip.name} · balance "
          f"{ui.money(v.balance)}")
    ui.table(("Award", "Type", "Year", "Awarded", "Remaining"),
             [(a.app.application_id, a.app.bursary_type, a.app.academic_year,
               ui.money(a.app.amount_awarded), ui.money(a.remaining))
              for a in awards], empty="(no approved award with money left)")
    if not awards:
        return
    app_id = ui.ask_int("Award #", default=awards[0].app.application_id)
    p = t.fund_from_bursary(bid, app_id,
                            amount=ui.ask_money("Amount", default=v.balance),
                            recorded_by=_who())
    print(f"\n  ✓ {ui.money(p.amount)} paid from bursary #{app_id}.")


@ui.handler
def trip_costing() -> None:
    from education_system.systems.sixth_form.domain.staff.departments import (
        department_budgets as db,
    )
    tid = ui.ask_int("Trip #")
    dept, cost = t.trip_costing(tid)
    depts = db.list_departments()
    names = [n for _i, n in depts]
    cur = next((n for i, n in depts if i == dept), None)
    pick = ui.pick("Department", names, default=cur, allow_none=True)
    t.set_trip_costing(
        tid, department_id=next((i for i, n in depts if n == pick), None),
        running_cost=ui.ask_money("Cost to the college of running it",
                                  default=cost, required=False))
    print("\n  ✓ Costing saved.")


MENU = [
    ("Refunds Due", refunds_due),
    ("Record Refund", record_refund),
    ("List Refunds", list_refunds),
    ("Remove Refund (recorded in error)", delete_refund),
    ("Pay a Place from a Bursary", pay_from_bursary),
    ("Trip Costing (department, running cost)", trip_costing),
]


def run() -> None:
    ui.menu("Trip Refunds & Bursary Funding", MENU)
