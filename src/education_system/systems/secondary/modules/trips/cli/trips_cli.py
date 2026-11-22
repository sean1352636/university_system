"""Trips & Payments in the terminal.

The old menu keeps its options in place: 1 Upcoming Trips, 2 All Trips,
3 Filter Trips, 4 View Trip, 5 New Trip, 6 Edit Trip, 7 Change Trip Status,
8 Delete Trip, 9 Bookings for Trip, 10 New Booking, 11 View Booking,
12 Edit Booking, 13 Change Booking Status, 14 Delete Booking, 15 Per-Student,
16 Consent Missing, 17 Record Payment, 18 List Payments, 19 Edit Payment,
20 Delete Payment, 21 Summary. New (after "More"): 22 Payment schedule,
23 Risk assessment, 24 Submit to EVC, 25 EVC decision, 26 Invite pupils,
27 Record consent, 28 E-mail consent requests, 29 Remission, 30 Refund,
31 Arrears, 32 Send payment reminders, 33 Refunds due, 34 Trip register on
the day, 35 Headcount and ratio, 36 Mark attendance (code V), 37 Readiness
checklist, 38 Pupil ledger, 39 History, 40 Export bookings CSV, 41 Export
payments CSV. Rules live in :mod:`modules.trips.domain.trips`.
"""

from __future__ import annotations

from typing import Any

from education_system.systems.secondary.modules.trips.domain import trips as TR
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.cli.prompts import prompts
from education_system.systems.secondary.ui.cli.prompts.prompts import pause as _pause
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt
from education_system.systems.secondary.ui.cli.prompts.prompts import yes as _yes

_ERRORS = (TR.ValidationError, TR.PermissionDenied, TR.NotFound)
_problem = prompts.problem
_int = prompts.ask_int
_pick = prompts.pick
_m = TR.money


def _ask(label: str, cur: Any = None) -> str:
    return _prompt(f"  {label}" + (f" [{cur}]" if cur not in (None, "") else "") + ": ")


def _print_trips(rows: list[TR.Trip]) -> None:
    if not rows:
        print("\n  (no trips)")
        return
    print(f"\n  {'ID':<4} {'Start':<10} {'End':<10} {'Name':<26} {'Destination':<16} "
          f"{'Year':<8} {'Cost':>8} {'Cap':>4} {'Status':<18} Approval")
    print("  " + "-" * 118)
    for t in rows:
        print(f"  {t.trip_id:<4} {t.start_date:<10} {(t.end_date or ''):<10} {t.title[:26]:<26} "
              f"{(t.destination or '')[:16]:<16} {t.year_group:<8} {_m(t.cost_pence):>8} "
              f"{(t.capacity if t.capacity is not None else ''):>4} {t.status:<18} "
              f"{TR.APPROVAL_LABELS[t.approval]}")


def _print_bookings(rows: list[TR.Booking]) -> None:
    if not rows:
        print("\n  (no bookings)")
        return
    print(f"\n  {'#':<5} {'Student':<10} {'Name':<24} {'Trip':<20} {'Status':<10} "
          f"{'Consent':<7} {'Paid':>9} {'Balance':>9} Payment")
    print("  " + "-" * 110)
    for b in rows:
        print(f"  {b.booking_id:<5} {b.admission_no:<10} {b.pupil_name[:24]:<24} "
              f"{b.trip_title[:20]:<20} {b.status:<10} {(b.consent or '-'):<7} "
              f"{_m(b.paid_pence):>9} {_m(b.balance_pence):>9} {b.payment_state}")


def _print_payments(rows: list[TR.Payment]) -> None:
    if not rows:
        print("\n  (no payments)")
        return
    print(f"\n  {'ID':<5} {'Bkg':<5} {'Paid on':<10} {'Kind':<8} {'Amount':>9} {'Method':<14} "
          f"{'Status':<9} {'Ref':<14} By")
    print("  " + "-" * 92)
    for p in rows:
        print(f"  {p.payment_id:<5} {p.booking_id:<5} {p.paid_on:<10} {p.kind:<8} "
              f"{_m(p.amount_pence):>9} {p.method:<14} {p.status:<9} "
              f"{(p.reference or '')[:14]:<14} {p.received_by or ''}")


def _trip() -> TR.Trip | None:
    tid = _int("  Trip ID: ")
    return TR.get(tid) if tid else None


def _booking() -> TR.Booking | None:
    bid = _int("  Booking ID: ")
    return TR.get_booking(bid) if bid else None


# ── Trips (old 1-8) ──────────────────────────────────────────────────

def _upcoming(_p: Principal) -> None:
    _print_trips(TR.list_trips(upcoming=True))


def _all(_p: Principal) -> None:
    _print_trips(TR.list_trips())


def _filter(_p: Principal) -> None:
    year = _pick("Year group (blank = all)", TR.YEAR_GROUPS)
    status = _pick("Status (blank = all)", TR.TRIP_STATUSES)
    _print_trips(TR.list_trips(year_group=year or None, status=status or None,
                               open_only=_yes("  Open only?"),
                               search=_prompt("  Search (blank = any): ") or None))


def _show_trip(t: TR.Trip) -> None:
    print(f"\n  Trip #{t.trip_id} - {t.title}")
    for label, v in (("Destination", t.destination), ("Dates", t.period),
                     ("Times", " - ".join(x for x in (t.depart_time, t.return_time) if x)),
                     ("Year group", t.year_group), ("Group", t.group_label), ("Type", t.flags),
                     ("Leader", t.leader), ("Staff", ", ".join(t.staff_names)),
                     ("Ratio", f"1:{t.pupils_per_adult}"), ("Capacity", t.capacity),
                     ("Places", f"{t.places_taken} taken, {t.waiting} waiting"),
                     ("Cost", _m(t.cost_pence)), ("Charging", t.charging),
                     ("Charge basis", t.charge_basis), ("Deposit", _m(t.deposit_pence)
                                                         if t.deposit_pence else None),
                     ("Payment due", t.payment_due), ("Consent due", t.consent_due),
                     ("Status", t.status), ("EVC", TR.APPROVAL_LABELS[t.approval]),
                     ("Approval note", t.approval_note),
                     ("Risk assessment", t.risk_file or ("text" if t.risk_assessment else None)),
                     ("Reviewed", t.risk_reviewed_on and f"{t.risk_reviewed_by} "
                                                         f"{t.risk_reviewed_on}"),
                     ("Description", t.description), ("Notes", t.notes)):
        if v not in (None, ""):
            print(f"    {label + ':':<17} {v}")
    print("    Payment plan:")
    for x in TR.schedule(t):
        print(f"      {x['label']:<14} {x['due'] or '-':<10} {_m(x['amount_pence']):>9}")


def _view(_p: Principal) -> None:
    t = _trip()
    if t:
        _show_trip(t)


def _trip_form(cur: TR.Trip | None) -> dict[str, Any]:
    """The old questions in order, then the new ones; Enter keeps the value."""
    out: dict[str, Any] = {}
    g = (lambda k: getattr(cur, k) if cur else None)
    for key, label in (("title", "Trip name"), ("destination", "Destination"),
                       ("start_date", "Start date (YYYY-MM-DD)"),
                       ("end_date", "End date (optional)")):
        v = _ask(label, g(key))
        if v:
            out[key] = v
    y = _pick("Year group", TR.YEAR_GROUPS, g("year_group") or TR.DEFAULT_YEAR_GROUP)
    if y:
        out["year_group"] = y
    for key, label in (("cost_pence", "Cost per place (£)"), ("deposit_pence", "Deposit (£)")):
        v = _ask(label, TR.plain(g(key)) if cur else "0.00")
        if v:
            out[key] = v
    for key, label in (("capacity", "Capacity (optional)"),
                       ("payment_due", "Payment due (optional)")):
        v = _ask(label, g(key))
        if v:
            out[key] = v
    if cur is None:
        s = _pick("Status", TR.TRIP_STATUSES, TR.DEFAULT_TRIP_STATUS)
        if s:
            out["status"] = s
    for key, label in (("leader", "Lead staff"), ("description", "Description (single line)"),
                       ("notes", "Notes (optional)"), ("depart_time", "Depart time (HH:MM)"),
                       ("return_time", "Return time (HH:MM)"),
                       ("staff", "Accompanying staff (comma list)"),
                       ("deposit_due", "Deposit due"), ("consent_due", "Consent due"),
                       ("ratio", "Pupils per adult (blank = default)")):
        v = _ask(label, g(key))
        if v:
            out[key] = v
    c = _pick("Charging", TR.CHARGING, g("charging") or TR.VOLUNTARY)
    if c:
        out["charging"] = c
    if (c or g("charging")) == TR.CHARGEABLE:
        b = _pick("Charge basis", TR.CHARGE_BASES, g("charge_basis"))
        if b:
            out["charge_basis"] = b
    for key in ("residential", "overseas", "adventurous"):
        v = _ask(f"{key.title()}? (y/n)", "y" if g(key) else "n")
        if v:
            out[key] = v.lower().startswith("y")
    return out


def _new(principal: Principal) -> None:
    t = TR.create_trip(_trip_form(None), actor=principal)
    print(f"  Created trip #{t.trip_id} (draft - add the risk assessment and submit to the EVC).")


def _edit(principal: Principal) -> None:
    t = _trip()
    if t is None:
        return
    changes = _trip_form(t)
    if not changes:
        print("  Nothing changed.")
        return
    done = TR.update_trip(t.trip_id, changes, actor=principal)
    print("  Saved." + (" It has gone back to the EVC for approval." if t.approved and
                        not done.approved else ""))


def _status(principal: Principal) -> None:
    t = _trip()
    if t is None:
        return
    s = _pick("New status", TR.TRIP_STATUSES, t.status)
    TR.set_trip_status(t.trip_id, s or t.status, actor=principal)
    print("  Status saved.")
    if s == "Cancelled" and TR.refunds_due(t.trip_id):
        print(f"  {len(TR.refunds_due(t.trip_id))} booking(s) hold money - record refunds "
              "(option 30).")


def _delete(principal: Principal) -> None:
    print("  This deletes all bookings and payments for the trip.")
    t = _trip()
    if t and _yes(f"  Delete trip #{t.trip_id} ({t.title})?"):
        TR.delete_trip(t.trip_id, actor=principal)
        print("  Deleted.")


# ── Bookings (old 9-16) ──────────────────────────────────────────────

def _bookings_for_trip(_p: Principal) -> None:
    t = _trip()
    if t:
        _print_bookings(TR.list_bookings(t.trip_id))


def _new_booking(principal: Principal) -> None:
    t = _trip()
    if t is None:
        return
    data: dict[str, Any] = {"pupil_id": _prompt("  Student (ID / admission no.): "),
                            "booking_date": _prompt("  Booking date (blank = today): "),
                            "status": _pick("Status", TR.BOOKING_STATUSES,
                                            TR.DEFAULT_BOOKING_STATUS)}
    if _yes("  Consent received?"):
        data["consent"] = "Yes"
    for key, label in (("consent_note", "Consent note"), ("medical_note", "Medical note"),
                       ("dietary_note", "Dietary note"), ("notes", "Notes")):
        data[key] = _prompt(f"  {label}: ")
    b = TR.create_booking(t.trip_id, data, actor=principal)
    print(f"  Booking #{b.booking_id}: {b.status}"
          + (" (the trip is full)" if b.status == "Waitlist" else ""))


def _show_booking(b: TR.Booking) -> None:
    print(f"\n  Booking #{b.booking_id} - {b.pupil_name} ({b.admission_no}) on {b.trip_title}")
    for label, v in (("Booked", b.booking_date), ("Status", b.status),
                     ("Consent", f"{b.consent or 'not given'} {b.consent_date or ''} "
                                 f"{b.consent_by or ''}".strip()),
                     ("Consent note", b.consent_note), ("Medical", b.medical_note),
                     ("Dietary", b.dietary_note), ("Charging", b.charging),
                     ("Cost", _m(b.cost_pence)),
                     ("Remission", b.remission_pence and f"{_m(b.remission_pence)} "
                                                         f"({b.remission_reason})"),
                     ("Asked for", _m(b.charge_pence)), ("Paid", _m(b.paid_pence)),
                     ("Balance", _m(b.balance_pence)), ("Payment", b.payment_state),
                     ("Notes", b.notes)):
        if v not in (None, "", 0):
            print(f"    {label + ':':<14} {v}")
    _print_payments(TR.list_payments(booking_id=b.booking_id))


def _view_booking(_p: Principal) -> None:
    b = _booking()
    if b:
        _show_booking(b)


def _edit_booking(principal: Principal) -> None:
    b = _booking()
    if b is None:
        return
    changes: dict[str, Any] = {}
    for key, label in (("booking_date", "Booking date"), ("consent_note", "Consent note"),
                       ("medical_note", "Medical note"), ("dietary_note", "Dietary note"),
                       ("notes", "Notes")):
        v = _ask(label, getattr(b, key))
        if v:
            changes[key] = "" if v == prompts.CLEAR else v
    c = _ask("Consent (Yes/No)", b.consent)
    if c:
        changes["consent"] = c
    TR.update_booking(b.booking_id, changes, actor=principal)
    print("  Saved.")


def _booking_status(principal: Principal) -> None:
    b = _booking()
    if b is None:
        return
    s = _pick("New status", TR.BOOKING_STATUSES, b.status)
    reason = _prompt("  Reason (needed to cancel / withdraw): ") if s in TR.RELEASED else ""
    done, promoted = TR.set_booking_status(b.booking_id, s or b.status, actor=principal,
                                           reason=reason)
    print(f"  {done.pupil_name}: {done.status}.")
    if promoted:
        print(f"  The place went to {promoted.pupil_name} (first on the waiting list).")


def _delete_booking(principal: Principal) -> None:
    print("  This also deletes payments against the booking.")
    b = _booking()
    if b and _yes(f"  Delete {b.pupil_name}'s booking?"):
        TR.delete_booking(b.booking_id, actor=principal)
        print("  Deleted.")


def _per_student(_p: Principal) -> None:
    p = TR._pupil(_prompt("  Student (ID / admission no.): "))
    if p is None:
        print("  No matching student.")
        return
    print(f"\n  {p.admission_no}  {p.display_name}")
    _print_bookings(TR.trips_for_pupil(p.pupil_id))


def _consent_missing(_p: Principal) -> None:
    tid = _int("  Trip ID (blank = all): ")
    _print_bookings(TR.consent_missing(tid))


# ── Payments (old 17-21) ─────────────────────────────────────────────

def _payment_data(cur: TR.Payment | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, label, val in (("amount", "Amount (£)", TR.plain(cur.amount_pence) if cur else ""),
                            ("paid_on", "Paid on (blank = today)", cur.paid_on if cur else "")):
        v = _ask(label, val)
        if v:
            out[key] = v
    m = _pick("Method", TR.PAYMENT_METHODS, cur.method if cur else TR.DEFAULT_METHOD)
    if m:
        out["method"] = m
    s = _pick("Status", TR.PAYMENT_STATUSES, cur.status if cur else TR.DEFAULT_PAYMENT_STATUS)
    if s:
        out["status"] = s
    for key, label in (("reference", "Reference"), ("recorded_by", "Recorded by"),
                       ("notes", "Notes")):
        v = _ask(label, getattr(cur, "received_by" if key == "recorded_by" else key)
                 if cur else "")
        if v:
            out[key] = v
    return out


def _add_payment(principal: Principal) -> None:
    b = _booking()
    if b is None:
        return
    print(f"  Balance: {_m(b.balance_pence)}")
    p = TR.add_payment(b.booking_id, _payment_data(), actor=principal)
    print(f"  Recorded payment #{p.payment_id}. Balance now "
          f"{_m(TR.get_booking(b.booking_id).balance_pence)}.")


def _list_payments(_p: Principal) -> None:
    tid = _int("  Trip ID (blank = all): ")
    method = _pick("Method (blank = all)", TR.PAYMENT_METHODS)
    rows = TR.list_payments(trip_id=tid, method=method or None,
                            date_from=_prompt("  From (blank = any): ") or None,
                            date_to=_prompt("  To (blank = any): ") or None)
    _print_payments(rows)
    print(f"\n  Net cleared: {_m(sum(p.signed_pence for p in rows))}")


def _edit_payment(principal: Principal) -> None:
    pid = _int("  Payment ID: ")
    if pid:
        cur = TR.get_payment(pid)
        TR.update_payment(pid, _payment_data(cur), actor=principal)
        print("  Saved.")


def _delete_payment(principal: Principal) -> None:
    pid = _int("  Payment ID: ")
    if pid and _yes(f"  Delete payment #{pid}?"):
        TR.delete_payment(pid, actor=principal)
        print("  Deleted.")


def _summary(_p: Principal) -> None:
    s = TR.summary()
    print(f"\n  Trips                : {s['total_trips']}")
    for label, key in (("Upcoming", "upcoming_trips"), ("Open for booking", "open_for_booking"),
                       ("Awaiting approval", "awaiting_approval"), ("Completed", "completed"),
                       ("Cancelled", "cancelled")):
        print(f"  {label:<21}: {s[key]}")
    if s["next_trip"]:
        t = s["next_trip"]
        print(f"\n  Next: #{t.trip_id}  {t.start_date}  {t.title}  ({t.status})")
    print(f"\n  Bookings (total)     : {s['total_bookings']}")
    for label, key in (("Active bookings", "active_bookings"), ("Waitlist", "waitlist_count"),
                       ("Consent missing", "consent_missing")):
        print(f"  {label:<21}: {s[key]}")
    print()
    for label, key in (("Charged (active)", "total_charged"), ("Paid", "total_paid"),
                       ("Outstanding", "total_outstanding"), ("Remissions", "total_remitted"),
                       ("Behind plan", "overdue_balance")):
        print(f"  {label:<21}: {_m(s[key])}")
    for title, key, fmt in (("Trips by status", "by_trip_status", str),
                            ("Bookings by status", "by_booking_status", str),
                            ("Payment states (active bookings)", "by_payment_state", str),
                            ("Payments by method", "by_method", _m)):
        print(f"\n  {title}:")
        for k, v in s[key].items():
            print(f"    {k:<22} : {fmt(v)}")
    if s["top_trips_by_revenue"]:
        print("\n  Top trips by revenue:")
        for tid, name, rev in s["top_trips_by_revenue"]:
            print(f"    #{tid:<3}  {name[:30]:<30}  {_m(rev)}")


# ── New (22+) ────────────────────────────────────────────────────────

def _schedule(principal: Principal) -> None:
    t = _trip()
    if t is None:
        return
    for x in TR.schedule(t):
        print(f"  {x['label']:<14} {x['due'] or '-':<10} {_m(x['amount_pence']):>9}")
    for i in TR.list_instalments(t.trip_id):
        print(f"    instalment #{i.instalment_id}: {i.label}")
    act = _pick("Action", ("Add instalment", "Remove instalment"))
    if act == "Add instalment":
        TR.add_instalment(t.trip_id, {"label": _prompt("  Label: "),
                                      "due_date": _prompt("  Due date: "),
                                      "amount": _prompt("  Amount (£): ")}, actor=principal)
        print("  Added.")
    elif act == "Remove instalment":
        iid = _int("  Instalment ID: ")
        if iid:
            TR.delete_instalment(iid, actor=principal)
            print("  Removed.")


def _risk(principal: Principal) -> None:
    t = _trip()
    if t is None:
        return
    TR.record_risk_assessment(
        t.trip_id, actor=principal, file_path=_ask("File path", t.risk_file) or None,
        text=_ask("Assessment text (Enter keeps)", "(recorded)" if t.risk_assessment else "")
        or None, reviewed_by=_ask("Reviewed by", t.risk_reviewed_by) or None,
        reviewed_on=_prompt("  Reviewed on (blank = today): ") or None)
    print("  Saved.")


def _submit(principal: Principal) -> None:
    t = _trip()
    if t:
        TR.submit_for_approval(t.trip_id, actor=principal,
                               note=_prompt("  Note for the EVC (blank ok): ") or None)
        print("  Submitted to the EVC.")


def _decide(principal: Principal) -> None:
    for t in TR.awaiting_approval():
        print(f"  #{t.trip_id:<4} {t.start_date} {t.title} ({t.flags}) - leader {t.leader}")
    t = _trip()
    if t is None:
        return
    dec = _pick("Decision", ("approved", "declined"))
    TR.decide_approval(t.trip_id, dec or "", actor=principal,
                       note=_prompt("  Note (needed to decline): "))
    print("  Recorded.")


def _invite(principal: Principal) -> None:
    t = _trip()
    if t is None:
        return
    r = TR.invite(t.trip_id, actor=principal,
                  year_group=_prompt("  Year group (blank = none): ") or None,
                  form_group=_prompt("  Form (blank = none): ") or None,
                  teaching_group=_prompt("  Teaching group code (blank = none): ") or None,
                  status=_pick("Add as", ("Interested", "Confirmed"), "Interested") or
                  "Interested")
    print(f"  Added {r['added']}; {r['already']} already on the trip; {r['waitlist']} waiting.")


def _consent(principal: Principal) -> None:
    b = _booking()
    if b is None:
        return
    TR.record_consent(b.booking_id, _pick("Consent", TR.CONSENT_CHOICES, "Yes") or "Yes",
                      actor=principal, day=_prompt("  Date (blank = today): ") or None,
                      by=_prompt("  Given by: "), medical_note=_prompt("  Medical needs: "),
                      dietary_note=_prompt("  Dietary requirements: "))
    print("  Recorded.")


def _deliver(res: dict[str, Any], principal: Principal) -> None:
    from education_system.systems.secondary.modules.communication.domain import email_outbox as E
    if res["no_email"]:
        print(f"  No e-mail address for {len(res['no_email'])} pupil(s).")
    if not res["message_id"]:
        return
    print(f"  {res['emails']} e-mail(s) saved.")
    try:
        E.deliver(res["message_id"], principal=principal)
        print("  Sent.")
    except Exception as e:  # noqa: BLE001 - they stay in the outbox
        print(f"  Saved in the outbox; not sent yet ({e}).")


def _consent_requests(principal: Principal) -> None:
    t = _trip()
    if t:
        _deliver(TR.send_consent_requests(t.trip_id, actor=principal), principal)


def _remission(principal: Principal) -> None:
    b = _booking()
    if b is None:
        return
    print(f"  Cost {_m(b.cost_pence)}; paid {_m(b.paid_pence)}")
    amount = _prompt("  Amount off (£, 0 to clear): ")
    reason = _pick("Reason", TR.REMISSION_REASONS) if amount not in ("", "0") else None
    TR.set_remission(b.booking_id, amount or "0", actor=principal, reason=reason)
    print("  Saved.")


def _refund(principal: Principal) -> None:
    b = _booking()
    if b is None:
        return
    print(f"  Paid: {_m(b.paid_pence)}")
    TR.refund(b.booking_id, {"amount": _prompt("  Amount (£, blank = all): "),
                             "method": _pick("Method", TR.PAYMENT_METHODS, "Bank Transfer"),
                             "reference": _prompt("  Reference: "),
                             "notes": _prompt("  Why: ")}, actor=principal)
    print("  Refund recorded.")


def _arrears(_p: Principal) -> None:
    rows = TR.arrears(_int("  Trip ID (blank = all): "))
    if not rows:
        print("  Nobody is behind.")
    for r in rows:
        b = r["booking"]
        print(f"  #{b.booking_id:<5} {b.pupil_name[:24]:<24} {b.trip_title[:22]:<22} "
              f"{'voluntary' if r['voluntary'] else 'charge':<9} due {_m(r['due_pence']):>8} "
              f"paid {_m(b.paid_pence):>8} behind {_m(r['behind_pence']):>8}")


def _remind(principal: Principal) -> None:
    tid = _int("  Trip ID (blank = all trips): ")
    ids = _prompt("  Booking IDs (comma list, blank = everyone behind): ")
    chosen = [int(x) for x in ids.replace(" ", "").split(",") if x.isdigit()] or None
    _deliver(TR.send_reminders(actor=principal, trip_id=tid, booking_ids=chosen), principal)


def _refunds_due(_p: Principal) -> None:
    found = False
    for t in TR.list_trips():
        for b in TR.refunds_due(t.trip_id):
            found = True
            print(f"  #{b.booking_id:<5} {b.pupil_name[:24]:<24} {t.title[:24]:<24} "
                  f"{b.status:<10} holds {_m(b.paid_pence)}")
    if not found:
        print("  No refunds due.")


def _register(principal: Principal) -> None:
    t = _trip()
    if t is None:
        return
    rows = [b for b in TR.list_bookings(t.trip_id) if b.status in TR.PLACE_STATUSES]
    for b in rows:
        print(f"  #{b.booking_id:<5} {b.pupil_name[:24]:<24} consent {b.consent or '-':<4} "
              f"{'OUT' if b.departed else '   '} {'BACK' if b.returned else ''}"
              + (f"  medical: {b.medical_note}" if b.medical_note else ""))
    which = _pick("Mark", ("Departed", "Returned"), "Departed")
    ids = _prompt("  Booking IDs (comma list, 'all' = everyone listed): ")
    chosen = [b.booking_id for b in rows] if ids.lower() == "all" else \
        [int(x) for x in ids.replace(" ", "").split(",") if x.isdigit()]
    fn = TR.mark_departed if which == "Departed" else TR.mark_returned
    print(f"  Marked {fn(t.trip_id, chosen, actor=principal)} pupil(s).")
    _headcount_for(t.trip_id)


def _headcount_for(trip_id: int) -> None:
    h = TR.headcount(trip_id)
    r = h["ratio"]
    print(f"\n  Places {h['places']}  Departed {h['departed']}  Returned {h['returned']}  "
          f"Still out {len(h['still_out'])}")
    for b in h["still_out"]:
        print(f"    out: {b.pupil_name}")
    print(f"  Adults {r['staff']} for {r['pupils']} pupil(s) at 1:{r['per_adult']} - needs "
          f"{r['needed']}: {'OK' if r['ok'] else 'NOT MET'}")


def _headcount(_p: Principal) -> None:
    t = _trip()
    if t:
        _headcount_for(t.trip_id)


def _attendance(principal: Principal) -> None:
    t = _trip()
    if t and _yes("  Put code V on the registers for the pupils who went?"):
        r = TR.mark_attendance(t.trip_id, actor=principal)
        print(f"  Marked {r['saved']} session(s) for {r['pupils']} pupil(s); kept "
              f"{r['skipped']} already marked.")


def _readiness(_p: Principal) -> None:
    t = _trip()
    if t:
        for c in TR.readiness(t.trip_id):
            print(f"  [{'x' if c['ok'] else ' '}] {c['item']:<32} {c['note']}")


def _ledger(_p: Principal) -> None:
    p = TR._pupil(_prompt("  Student (ID / admission no.): "))
    if p is None:
        print("  No matching student.")
        return
    led = TR.pupil_ledger(p.pupil_id)
    _print_bookings(led["bookings"])
    _print_payments(led["payments"])
    print(f"\n  Paid {_m(led['paid_pence'])}; balance {_m(led['balance_pence'])}")


def _history(_p: Principal) -> None:
    t = _trip()
    if t:
        for h in TR.history(t.trip_id):
            print(f"  {h['at']}  {h['actor']:<12} {h['action']:<16} "
                  + ", ".join(f"{k}={v}" for k, v in h["detail"].items()))


def _export_bookings(principal: Principal) -> None:
    path = _prompt("  Save CSV to (e.g. trip-bookings.csv): ")
    if path:
        n = TR.export_bookings_csv(path, actor=principal,
                                   trip_id=_int("  Trip ID (blank = all): "))
        print(f"  Exported {n} booking(s).")


def _export_payments(principal: Principal) -> None:
    path = _prompt("  Save CSV to (e.g. trip-payments.csv): ")
    if path:
        print(f"  Exported {TR.export_payments_csv(path, actor=principal)} line(s).")


_OPTIONS = {"1": _upcoming, "2": _all, "3": _filter, "4": _view, "5": _new, "6": _edit,
            "7": _status, "8": _delete, "9": _bookings_for_trip, "10": _new_booking,
            "11": _view_booking, "12": _edit_booking, "13": _booking_status,
            "14": _delete_booking, "15": _per_student, "16": _consent_missing,
            "17": _add_payment, "18": _list_payments, "19": _edit_payment,
            "20": _delete_payment, "21": _summary, "22": _schedule, "23": _risk,
            "24": _submit, "25": _decide, "26": _invite, "27": _consent,
            "28": _consent_requests, "29": _remission, "30": _refund, "31": _arrears,
            "32": _remind, "33": _refunds_due, "34": _register, "35": _headcount,
            "36": _attendance, "37": _readiness, "38": _ledger, "39": _history,
            "40": _export_bookings, "41": _export_payments}
_LABELS = ("Upcoming Trips", "All Trips", "Filter Trips", "View Trip", "New Trip", "Edit Trip",
           "Change Trip Status", "Delete Trip", "Bookings for Trip", "New Booking",
           "View Booking", "Edit Booking", "Change Booking Status", "Delete Booking",
           "Per-Student", "Consent Missing", "Record Payment", "List Payments", "Edit Payment",
           "Delete Payment", "Summary", "Payment schedule", "Risk assessment", "Submit to EVC",
           "EVC decision", "Invite pupils", "Record consent", "E-mail consent requests",
           "Remission", "Refund", "Arrears", "Send payment reminders", "Refunds due",
           "Trip register on the day", "Headcount and ratio", "Mark attendance (code V)",
           "Readiness checklist", "Pupil ledger", "History", "Export bookings CSV",
           "Export payments CSV")


def menu(principal: Principal) -> None:
    while True:
        activity_log.record("trips.view")
        print("\n  ── Trips & Payments ──")
        for i, label in enumerate(_LABELS, 1):
            if i == 22:
                print("  More")
            print(f"   {i:>2}) {label}")
        print("    0) Back")
        choice = _prompt("Select: ")
        if choice in ("0", ""):
            return
        fn = _OPTIONS.get(choice)
        if fn is None:
            print("  Invalid selection.")
            continue
        try:
            fn(principal)
        except _ERRORS as e:
            _problem(e)
        _pause()
