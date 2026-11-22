"""Trips & Payments: arrears and reminders, the day itself, families, summary and export.

Part of :mod:`modules.trips.domain.trips`, which re-exports everything here -
import it from there (trips.invite ...), not from this module.
"""

from __future__ import annotations

from collections import Counter
import csv
import datetime as _dt
import math
from pathlib import Path
from typing import Any

from education_system.systems.secondary.modules.trips.domain.trips import (  # noqa: F401
    _NON_PAYMENT,
    APPROVAL_LABELS,
    BOOKING_STATUSES,
    CONSENT_CHOICES,
    DEFAULT_BOOKING_STATUS,
    PAYING_STATUSES,
    PLACE_STATUSES,
    RELEASED,
    Booking,
    Trip,
    ValidationError,
    _audit,
    _choice,
    _date,
    _deny,
    _flag,
    _pupil,
    _require_editor,
    _require_staff,
    _staff_name,
    _text,
    can_run_day,
    due_by,
    get,
    get_booking,
    is_editor,
    list_bookings,
    list_payments,
    list_trips,
    money,
    plain,
    schedule,
)
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.core.utilities.exports import safe_cell as _safe
from education_system.systems.secondary.core.academic_calendar.school_year import today as _today
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

# ── Arrears and reminders ────────────────────────────────────────────

def arrears(trip_id: int | None = None, *, today: _dt.date | None = None) -> list[dict[str, Any]]:
    """Families behind the payment plan: {'booking', 'due_pence',
    'behind_pence', 'voluntary'}, most behind first."""
    day = (today or _today()).isoformat()
    trips = {t.trip_id: t for t in (list_trips() if trip_id is None else [get(trip_id)])
             if t.status != "Cancelled"}
    out = []
    for b in list_bookings(trip_id):
        t = trips.get(b.trip_id)
        if t is None or b.status not in PAYING_STATUSES or t.status == "Completed" and \
                b.balance_pence <= 0:
            continue
        due = due_by(t, day, remission_pence=b.remission_pence)
        behind = due - b.paid_pence
        if behind > 0:
            out.append({"booking": b, "due_pence": due, "behind_pence": behind,
                        "balance_pence": b.balance_pence, "voluntary": t.is_voluntary})
    return sorted(out, key=lambda x: (-x["behind_pence"], x["booking"].pupil_name))


def _send(kind: str, label: str, template_name: str, items: list[tuple[Booking, dict]],
          actor: Principal) -> dict[str, Any]:
    from education_system.systems.secondary.modules.communication.domain import email_outbox as E
    from education_system.systems.secondary.modules.communication.domain import email_templates
    from education_system.systems.secondary.modules.pupils.domain import contacts as C
    template = email_templates.load_template(template_name)
    contacts = C.emailable_for_pupils(sorted({b.pupil_id for b, _v in items}))
    letters, sent, no_email = [], [], []
    for b, values in items:
        to = [(x.email, x.full_name) for x in contacts.get(b.pupil_id, [])
              if x.email and x.parental_responsibility]
        if not to:
            no_email.append(b)
            continue
        sent.append(b)
        for address, name in to:
            subject, body = template.render({"recipient_name": name, **values,
                                             "sender_name": _staff_name(actor)})
            letters.append((address, name, subject, body))
    if not letters:
        return {"message_id": None, "emails": 0, "sent": [], "no_email": no_email}
    mid = E.save_prepared(kind, label, label, "(one letter per contact)", letters, actor=actor)
    return {"message_id": mid, "emails": len(letters), "sent": sent, "no_email": no_email}


def _first(b: Booking) -> str:
    return b.pupil_name.split(", ", 1)[-1]


def send_reminders(*, actor: Principal, trip_id: int | None = None,
                   booking_ids: list[int] | None = None) -> dict[str, Any]:
    """E-mail families who are behind (all, one trip, or chosen bookings). A
    voluntary contribution is worded as a request, never a debt.
    Returns {'message_id', 'emails', 'sent', 'no_email'}; run deliver next."""
    _require_editor(actor, "remind")
    rows = arrears(trip_id)
    if booking_ids:
        wanted = {int(x) for x in booking_ids}
        rows = [r for r in rows if r["booking"].booking_id in wanted]
    if not rows:
        raise ValidationError(["Nobody is behind with payments"])
    items = []
    for r in rows:
        b = r["booking"]
        t = get(b.trip_id)
        nxt = next((x for x in schedule(t) if x["due"] and x["due"] > _today().isoformat()),
                   None)
        if r["voluntary"]:
            intro = (f"Thank you for your support for {t.title}. We are asking families for a "
                     f"voluntary contribution of {money(b.charge_pence)} towards the cost.")
            policy = ("The contribution is voluntary: no pupil will be left out of the trip "
                      "because their family cannot contribute. If paying is difficult, "
                      "please talk to the school office in confidence - help may be "
                      "available.")
            what = "Contribution requested so far"
        else:
            intro = f"This is a reminder about payment for {t.title} ({t.period})."
            policy = ("If paying is difficult, please contact the school office in "
                      "confidence: our remissions policy may be able to help.")
            what = "Due so far"
        details = (f"{what}: {money(r['due_pence'])}\nReceived: {money(b.paid_pence)}\n"
                   f"Outstanding now: {money(r['behind_pence'])}\n"
                   f"Total {'requested' if r['voluntary'] else 'cost'}: "
                   f"{money(b.charge_pence)}")
        if nxt:
            details += f"\nNext: {nxt['label']} by {nxt['due']}"
        items.append((b, {"pupil_name": _first(b), "trip_title": t.title, "intro": intro,
                          "details": details, "policy": policy}))
    res = _send("trip_reminder", "Trip payment reminder", "trip_payment_reminder", items, actor)
    if res["sent"]:
        with database.connect() as conn:
            for b in res["sent"]:
                conn.execute("UPDATE trip_bookings SET last_reminder_at = datetime('now') "
                             "WHERE booking_id = ?", (b.booking_id,))
                _audit(conn, "remind", actor, trip_id=b.trip_id, booking_id=b.booking_id,
                       pupil_id=b.pupil_id)
    activity_log.record("trips.remind", principal=actor, emails=res["emails"])
    return res


def send_consent_requests(trip_id: int, *, actor: Principal,
                          booking_ids: list[int] | None = None) -> dict[str, Any]:
    """E-mail the trip details and ask for consent (and medical / dietary
    information) from families who haven't given it."""
    t = get(trip_id)
    _require_editor(actor, "consent_request", f"trip:{t.trip_id}")
    if not t.approved:
        raise ValidationError(["The trip must be approved by the EVC before families are "
                               "asked"])
    rows = [b for b in list_bookings(trip_id, consent_missing=True)
            if b.status in PAYING_STATUSES | {"Waitlist"}]
    if booking_ids:
        rows = [b for b in rows if b.booking_id in {int(x) for x in booking_ids}]
    if not rows:
        raise ValidationError(["Every family on the trip has answered"])
    times = " - ".join(x for x in (t.depart_time, t.return_time) if x)
    sched = "\n".join(f"  {x['label']}: {money(x['amount_pence'])} by {x['due'] or '-'}"
                      for x in schedule(t))
    charge = ("We are asking for a voluntary contribution. No pupil will be left out because "
              "their family cannot contribute." if t.is_voluntary else
              f"Charge ({t.charge_basis or 'see notes'}).")
    items = []
    for b in rows:
        details = (f"Where: {t.destination or '-'}\nWhen: {t.period}"
                   + (f" ({times})" if times else "") + f"\nLeader: {t.leader or '-'}"
                   + (f"\nCost: {money(b.charge_pence or t.cost_pence)}\n{charge}"
                      if t.cost_pence else "\nThere is no cost.")
                   + (f"\nPayment plan:\n{sched}" if t.cost_pence else ""))
        items.append((b, {"pupil_name": _first(b), "trip_title": t.title,
                          "details": details,
                          "reply_by": t.consent_due or t.start_date}))
    res = _send("trip_consent", "Trip consent request", "trip_consent_request", items, actor)
    with database.connect() as conn:
        _audit(conn, "consent_request", actor, trip_id=t.trip_id, emails=res["emails"])
    activity_log.record("trips.consent_request", target=f"trip:{t.trip_id}", principal=actor,
                        emails=res["emails"])
    return res


# ── On the day ───────────────────────────────────────────────────────

def ratio_check(trip_id: int | Trip) -> dict[str, Any]:
    """Adults against pupils (going, or confirmed if the register isn't
    taken): {'pupils', 'staff', 'per_adult', 'needed', 'ok'}."""
    t = trip_id if isinstance(trip_id, Trip) else get(trip_id)
    rows = list_bookings(t.trip_id)
    went = [b for b in rows if b.departed and not b.returned]
    n = len(went) if any(b.departed for b in rows) else sum(
        1 for b in rows if b.status in PLACE_STATUSES)
    staff = len(t.staff_names)
    needed = max(1, math.ceil(n / t.pupils_per_adult)) if n else 0
    if (t.residential or t.overseas) and n:
        needed = max(needed, 2)     # never one adult alone overnight / abroad
    return {"pupils": n, "staff": staff, "per_adult": t.pupils_per_adult, "needed": needed,
            "ok": staff >= needed}


def _register(trip_id: int, booking_ids: list[int], field: str, actor: Principal,
              value: bool) -> int:
    t = get(trip_id)
    if not can_run_day(actor, t):
        _deny(actor, field, f"trip:{t.trip_id}", "Only the trip leader or the finance office "
                                                 "can take the trip register.")
    problems = []
    today = _today().isoformat()
    if not t.approved:
        problems.append("The trip hasn't been approved")
    if t.status == "Cancelled":
        problems.append("The trip is cancelled")
    if not t.start_date <= today <= t.last_day:
        problems.append(f"The trip register is taken on the day ({t.period})")
    rows = {b.booking_id: b for b in list_bookings(trip_id)}
    for bid in booking_ids:
        b = rows.get(int(bid))
        if b is None:
            problems.append(f"Booking #{bid} isn't on this trip")
        elif field == "departed" and value and b.status not in PLACE_STATUSES:
            problems.append(f"{b.pupil_name} doesn't have a confirmed place")
        elif field == "departed" and value and not b.consent_received:
            problems.append(f"No consent for {b.pupil_name}")
        elif field == "returned" and value and not b.departed:
            problems.append(f"{b.pupil_name} wasn't marked as departing")
    if problems:
        raise ValidationError(problems)
    n = 0
    with database.connect() as conn:
        for bid in booking_ids:
            b = rows[int(bid)]
            if bool(getattr(b, field)) == value:
                continue
            status = b.status
            if field == "departed":
                status = "Attended" if value else "Confirmed"
            conn.execute(f"UPDATE trip_bookings SET {field} = ?, {field}_at = ?, status = ?, "
                         "updated_at = datetime('now') WHERE booking_id = ?",
                         (int(value), _dt.datetime.now().isoformat(timespec="minutes")
                          if value else None, status, b.booking_id))
            n += 1
        _audit(conn, field if value else f"un{field}", actor, trip_id=t.trip_id, count=n)
    activity_log.record(f"trips.{field}", target=f"trip:{t.trip_id}", principal=actor, count=n)
    return n


def mark_departed(trip_id: int, booking_ids: list[int], *, actor: Principal,
                  departed: bool = True) -> int:
    """Tick pupils onto the coach (they become Attended). Needs consent."""
    return _register(trip_id, booking_ids, "departed", actor, departed)


def mark_returned(trip_id: int, booking_ids: list[int], *, actor: Principal,
                  returned: bool = True) -> int:
    return _register(trip_id, booking_ids, "returned", actor, returned)


def headcount(trip_id: int) -> dict[str, Any]:
    """The day's count: places, departed, returned, still out, not gone."""
    rows = [b for b in list_bookings(trip_id) if b.status in PLACE_STATUSES]
    went = [b for b in rows if b.departed]
    return {"places": len(rows), "departed": len(went),
            "returned": sum(1 for b in went if b.returned),
            "still_out": [b for b in went if not b.returned],
            "not_departed": [b for b in rows if not b.departed],
            "ratio": ratio_check(trip_id)}


def mark_attendance(trip_id: int, *, actor: Principal) -> dict[str, int]:
    """Code V (educational visit) on the AM and PM registers for the trip's
    school days, up to today, for each pupil who departed. Marks already on
    the register (other than N) are kept."""
    from education_system.systems.secondary.modules.attendance.domain import attendance as AT
    t = get(trip_id)
    _require_editor(actor, "attendance", f"trip:{t.trip_id}")
    today = _today().isoformat()
    if t.start_date > today:
        raise ValidationError([f"The trip starts on {t.start_date} - nothing to mark yet"])
    went = [b for b in list_bookings(trip_id) if b.departed]
    if not went:
        raise ValidationError(["Nobody has been marked as departing - take the trip register "
                               "first"])
    last = min(t.last_day, today)
    saved = skipped = 0
    for b in went:
        a, s = AT.record_range(b.pupil_id, t.start_date, last, "V", actor=actor,
                               notes=f"Trip #{t.trip_id}")
        saved, skipped = saved + a, skipped + s
    with database.connect() as conn:
        conn.execute("UPDATE trips SET attendance_marked_at = datetime('now') WHERE trip_id = ?",
                     (t.trip_id,))
        _audit(conn, "attendance", actor, trip_id=t.trip_id, saved=saved, skipped=skipped)
    activity_log.record("trips.attendance", target=f"trip:{t.trip_id}", principal=actor,
                        saved=saved)
    return {"saved": saved, "skipped": skipped, "pupils": len(went)}


def readiness(trip_id: int) -> list[dict[str, Any]]:
    """The pre-departure checklist: {'item', 'ok', 'note'}. Unpaid voluntary
    contributions are shown but never stop a pupil going."""
    t = get(trip_id)
    rows = [b for b in list_bookings(trip_id) if b.status in PLACE_STATUSES]
    no_consent = [b for b in rows if not b.consent_received]
    r = ratio_check(t)
    behind = [x for x in arrears(trip_id) if x["booking"].status in PLACE_STATUSES]
    out = [
        {"item": "EVC approval", "ok": t.approved, "note": APPROVAL_LABELS[t.approval]},
        {"item": "Risk assessment reviewed",
         "ok": bool((t.risk_assessment or t.risk_file) and t.risk_reviewed_on),
         "note": f"{t.risk_reviewed_by or '-'} {t.risk_reviewed_on or ''}".strip()},
        {"item": "Consent from every family", "ok": not no_consent,
         "note": f"{len(no_consent)} missing" if no_consent else f"{len(rows)} in"},
        {"item": "Staff:pupil ratio", "ok": r["ok"],
         "note": f"{r['staff']} adult(s) for {r['pupils']} pupil(s); 1:{r['per_adult']} needs "
                 f"{r['needed']}"},
        {"item": "Medical / dietary notes read", "ok": True,
         "note": f"{sum(1 for b in rows if b.medical_note)} medical, "
                 f"{sum(1 for b in rows if b.dietary_note)} dietary"},
        {"item": "Payments", "ok": not behind or t.is_voluntary,
         "note": (f"{len(behind)} behind" + (" (voluntary - never stops a pupil going)"
                                             if t.is_voluntary else "")) if behind
         else "up to date"},
    ]
    return out


# ── Families ─────────────────────────────────────────────────────────

def for_family(pupil_id: int) -> list[dict[str, Any]]:
    """What the portal shows: this pupil's current and upcoming trips (not
    cancelled, approved) with consent, cost, paid, balance and next payment."""
    today = _today().isoformat()
    out = []
    for b in list_bookings(pupil_id=pupil_id):
        t = get(b.trip_id)
        if not t.approved or t.status == "Cancelled" or t.last_day < today or \
                b.status in RELEASED:
            continue
        nxt = next((x for x in schedule(t) if x["due"] and x["due"] >= today
                    and x["cumulative_pence"] > b.paid_pence), None)
        out.append({"trip": t.title, "destination": t.destination, "dates": t.period,
                    "depart_time": t.depart_time, "return_time": t.return_time,
                    "status": b.status, "consent": b.consent or "Not given",
                    "consent_due": t.consent_due, "charging": t.charging,
                    "cost": money(b.charge_pence), "paid": money(b.paid_pence),
                    "balance": money(max(0, b.balance_pence)),
                    "balance_pence": max(0, b.balance_pence),
                    "next_due": f"{nxt['label']} by {nxt['due']}" if nxt else None})
    return out


# ── Summary and export ───────────────────────────────────────────────

def summary() -> dict[str, Any]:
    """The old Summary tab, in pence."""
    today = _today().isoformat()
    trips = list_trips()
    by_ts = Counter(t.status for t in trips)
    live = [t for t in trips if t.start_date >= today and t.status != "Cancelled"]
    books = list_bookings()
    active = [b for b in books if b.is_active]
    pays = [p for p in list_payments() if p.status == "Cleared"]
    by_method: Counter[str] = Counter()
    for p in pays:
        by_method[p.method] += p.signed_pence
    by_trip: Counter[int] = Counter()
    for b in books:
        by_trip[b.trip_id] += b.paid_pence
    names = {t.trip_id: t.title for t in trips}
    overdue = sum(x["behind_pence"] for x in arrears())
    return {"total_trips": len(trips), "upcoming_trips": len(live),
            "open_for_booking": by_ts.get("Open for Booking", 0),
            "completed": by_ts.get("Completed", 0), "cancelled": by_ts.get("Cancelled", 0),
            "awaiting_approval": sum(1 for t in trips if t.approval == "submitted"),
            "next_trip": min(live, key=lambda t: t.start_date) if live else None,
            "total_bookings": len(books), "active_bookings": len(active),
            "waitlist_count": sum(1 for b in books if b.status == "Waitlist"),
            "consent_missing": sum(1 for b in active if not b.consent_received),
            "total_charged": sum(b.charge_pence for b in active),
            "total_paid": sum(b.paid_pence for b in active),
            "total_outstanding": sum(max(0, b.balance_pence) for b in active),
            "total_remitted": sum(b.remission_pence for b in active),
            "overdue_balance": overdue,
            "by_trip_status": dict(by_ts),
            "by_booking_status": dict(Counter(b.status for b in books)),
            "by_payment_state": dict(Counter(b.payment_state for b in active)),
            "by_method": {k: v for k, v in by_method.items() if v},
            "top_trips_by_revenue": [(tid, names.get(tid, "?"), v)
                                     for tid, v in by_trip.most_common(10) if v > 0]}


def export_bookings_csv(path: str | Path, *, actor: Principal, trip_id: int | None = None
                        ) -> int:
    _require_staff(actor, "export")
    rows = list_bookings(trip_id)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["booking", "trip", "trip_title", "admission_no", "pupil", "year", "form",
                    "status", "consent", "consent_date", "medical", "dietary", "charging",
                    "cost", "remission", "remission_reason", "charge", "paid", "balance",
                    "state", "departed", "returned"])
        for b in rows:
            w.writerow([b.booking_id, b.trip_id, _safe(b.trip_title), _safe(b.admission_no),
                        _safe(b.pupil_name), b.pupil_year, _safe(b.form_group), b.status,
                        b.consent or "", b.consent_date or "", _safe(b.medical_note),
                        _safe(b.dietary_note), b.charging, plain(b.cost_pence),
                        plain(b.remission_pence), b.remission_reason or "",
                        plain(b.charge_pence), plain(b.paid_pence), plain(b.balance_pence),
                        b.payment_state, b.departed, b.returned])
    activity_log.record("trips.export", principal=actor, rows=len(rows))
    return len(rows)


def export_payments_csv(path: str | Path, *, actor: Principal, **filters: Any) -> int:
    _require_staff(actor, "export")
    rows = list_payments(**filters)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["payment", "booking", "trip", "trip_title", "pupil", "kind", "paid_on",
                    "amount", "method", "status", "reference", "received_by", "notes"])
        for p in rows:
            w.writerow([p.payment_id, p.booking_id, p.trip_id, _safe(p.trip_title),
                        _safe(p.pupil_name), p.kind, p.paid_on, plain(p.amount_pence),
                        p.method, p.status, _safe(p.reference), _safe(p.received_by),
                        _safe(p.notes)])
    activity_log.record("trips.export_payments", principal=actor, rows=len(rows))
    return len(rows)

