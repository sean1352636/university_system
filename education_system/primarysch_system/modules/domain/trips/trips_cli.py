"""CLI flows for Primary School Trips & Payments."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable
from education_system.primarysch_system.modules.domain import _pupils_bridge as students
from education_system.primarysch_system.modules.domain import _pupils_bridge as student_data
from education_system.primarysch_system.modules.domain.trips import trips as data
from education_system.primarysch_system.modules.domain.trips.trips import (
    BOOKING_STATUSES,
    Booking,
    CURRENCY_SYMBOL,
    DEFAULT_BOOKING_STATUS,
    DEFAULT_METHOD,
    DEFAULT_PAYMENT_STATUS,
    DEFAULT_TRIP_STATUS,
    DEFAULT_YEAR_GROUP,
    PAYMENT_METHODS,
    PAYMENT_STATES,
    PAYMENT_STATUSES,
    Payment,
    TRIP_STATUSES,
    Trip,
    ValidationError,
    YEAR_GROUPS,
)

logger = logging.getLogger(__name__)


class _UserAbort(Exception):
    pass


# ── Prompt helpers ─────────────────────────────────────────────────

def _input(prompt: str, *, default: str = "",
            allow_empty: bool = True) -> str:
    suffix = f" [{default}]" if default else ""
    try:
        raw = input(f"  {prompt}{suffix}: ")
    except (EOFError, KeyboardInterrupt):
        print()
        raise _UserAbort
    s = raw.strip()
    if s.lower() == "cancel":
        raise _UserAbort
    if not s:
        if default:
            return default
        if not allow_empty:
            print("    Value is required.")
            return _input(prompt, default=default, allow_empty=False)
        return ""
    return s


def _pause() -> None:
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


def _pick_from(label: str, options: list[str],
                default: str | None = None) -> str:
    print(f"\n  {label}:")
    for i, opt in enumerate(options, 1):
        marker = " *" if opt == default else "  "
        print(f"    {marker}{i:>2}) {opt}")
    while True:
        raw = _input(f"  Pick #1..{len(options)}", default=default or "")
        if default and raw == default:
            return default
        if not raw.isdigit():
            print("    Enter a number (or 'cancel').")
            continue
        n = int(raw)
        if not (1 <= n <= len(options)):
            print("    Out of range.")
            continue
        return options[n - 1]


def _yes_no(prompt: str, default: bool = False) -> bool:
    raw = _input(f"{prompt} (y/n)", default="y" if default else "n")
    return raw.lower() in ("y", "yes")


def _pick_student() -> str:
    students = student_data.list_students()
    if not students:
        print("    No students.")
        raise _UserAbort
    print("\n  Students:")
    for i, s in enumerate(students, 1):
        print(f"    {i:>3}) {s.student_id}  {s.full_name}")
    while True:
        raw = _input(f"  Pick #1..{len(students)} (or student ID)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(students):
                return students[n - 1].student_id
            continue
        m = next((s for s in students
                   if s.student_id.lower() == raw.lower()), None)
        if m:
            return m.student_id
        print("    No matching student.")


def _pick_trip() -> Trip:
    trips = data.list_trips()
    if not trips:
        print("    No trips. Create one first.")
        raise _UserAbort
    print("\n  Trips:")
    for i, t in enumerate(trips, 1):
        print(f"    {i:>3}) #{t.trip_id}  {t.start_date}  "
              f"{t.name}  ({t.status})")
    while True:
        raw = _input(f"  Pick #1..{len(trips)} (or trip ID)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(trips):
                return trips[n - 1]
            t = next((t for t in trips if t.trip_id == n), None)
            if t:
                return t
            print("    Not a listed index or ID.")
            continue
        print("    Enter a number.")


def _money(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{CURRENCY_SYMBOL}{v:.2f}"


# ── Print helpers ──────────────────────────────────────────────────

def _print_trips(rows: list[Trip]) -> None:
    if not rows:
        print("\n  (no trips)")
        return
    print()
    print(f"  {'#':>4}  {'Start':<10}  {'End':<10}  "
          f"{'Name':<30}  {'Year':<6}  "
          f"{'Cost':>8}  {'Cap':>4}  Status")
    print("  " + "-" * 100)
    for t in rows:
        print(f"  {t.trip_id:>4}  {t.start_date:<10}  "
              f"{(t.end_date or '—'):<10}  {t.name[:30]:<30}  "
              f"{t.year_group[:6]:<6}  "
              f"{_money(t.cost_per_place):>8}  "
              f"{(t.capacity if t.capacity is not None else '—'):>4}  "
              f"{t.status}")
    print(f"\n  {len(rows)} trip(s).")


def _print_booking_views(rows: list[data.BookingView]) -> None:
    if not rows:
        print("\n  (no bookings)")
        return
    print()
    print(f"  {'#':>4}  {'Trip':>4}  {'Student':<10}  "
          f"{'Name':<22}  {'Booked':<10}  "
          f"{'Status':<11}  C  {'Paid':>9}  {'Bal':>9}  Payment")
    print("  " + "-" * 110)
    paid_t = bal_t = 0.0
    for v in rows:
        b = v.booking
        consent = "Y" if b.consent_received else "."
        paid_t += v.paid
        bal_t  += v.balance if v.is_active else 0
        print(f"  {b.booking_id:>4}  {b.trip_id:>4}  "
              f"{b.student_id:<10}  {v.student_name[:22]:<22}  "
              f"{b.booking_date:<10}  {b.status:<11}  {consent}  "
              f"{_money(v.paid):>9}  {_money(v.balance):>9}  "
              f"{v.payment_state}")
    print(f"\n  {len(rows)} booking(s).  "
          f"Paid {_money(round(paid_t, 2))}, "
          f"active balance {_money(round(bal_t, 2))}.")


def _print_payments(rows: list[Payment]) -> None:
    if not rows:
        print("\n  (no payments)")
        return
    print()
    print(f"  {'#':>4}  {'Bkg':>4}  {'Paid on':<10}  "
          f"{'Amount':>9}  {'Method':<14}  {'Status':<10}  Ref")
    print("  " + "-" * 88)
    cleared = 0.0
    for p in rows:
        if p.status == "Cleared":
            cleared += p.amount
        print(f"  {p.payment_id:>4}  {p.booking_id:>4}  "
              f"{p.paid_on:<10}  {_money(p.amount):>9}  "
              f"{p.method:<14}  {p.status:<10}  "
              f"{p.reference or '—'}")
    print(f"\n  {len(rows)} payment(s).  "
          f"Cleared total: {_money(round(cleared, 2))}")


# ── Trip flows ────────────────────────────────────────────────────

def list_upcoming() -> None:
    print("\n═══ Upcoming Trips ═══")
    today = _date.today().isoformat()
    _print_trips(data.list_trips(open_only=True, date_from=today))
    _trip_action_loop()


def list_all() -> None:
    print("\n═══ All Trips ═══")
    _print_trips(data.list_trips())
    _trip_action_loop()


def filter_trips() -> None:
    print("\n═══ Filter Trips ═══")
    try:
        yg = _input(f"Year group ({'/'.join(YEAR_GROUPS)})") or None
        status = _input(f"Status ({'/'.join(TRIP_STATUSES)})") or None
        df = _input("From (YYYY-MM-DD, optional)") or None
        dt = _input("To (YYYY-MM-DD, optional)") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.list_trips(year_group=yg, status=status,
                                 date_from=df, date_to=dt)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_trips(rows)
    _trip_action_loop()


def view_trip(trip_id: int | None = None) -> None:
    print("\n═══ View Trip ═══")
    try:
        if trip_id is None:
            trip = _pick_trip()
        else:
            trip = data.get_trip(trip_id)
            if trip is None:
                print(f"  ✗ No trip #{trip_id}")
                _pause()
                return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    tv = data.view_trip(trip.trip_id)
    print()
    print(f"    Trip ID       : #{trip.trip_id}")
    print(f"    Name          : {trip.name}")
    print(f"    Destination   : {trip.destination or '—'}")
    print(f"    Dates         : {trip.start_date}"
          + (f" → {trip.end_date}" if trip.end_date else ""))
    print(f"    Year group    : {trip.year_group}")
    print(f"    Cost / place  : {_money(trip.cost_per_place)}")
    print(f"    Deposit       : {_money(trip.deposit)}")
    print(f"    Capacity      : {trip.capacity or '—'}")
    print(f"    Payment due   : {trip.payment_due or '—'}")
    print(f"    Status        : {trip.status}")
    print(f"    Lead staff    : {trip.lead_staff_id or '—'}")
    print()
    print(f"    Active bookings : {tv.total_active}"
          + (f"  ({tv.capacity_used_pct}% of capacity)"
              if tv.capacity_used_pct is not None else ""))
    print(f"    Confirmed       : {tv.confirmed}")
    print(f"    Interested      : {tv.interested}")
    print(f"    Waitlist        : {tv.waitlist}")
    print(f"    Cancelled       : {tv.cancelled}")
    print()
    print(f"    Charged (active): {_money(tv.total_charged)}")
    print(f"    Paid            : {_money(tv.total_paid)}")
    print(f"    Outstanding     : {_money(tv.total_balance)}")
    if trip.description:
        print("\n    Description:")
        for line in trip.description.splitlines() or [""]:
            print(f"      {line}")
    if trip.notes:
        print("\n    Notes:")
        for line in trip.notes.splitlines() or [""]:
            print(f"      {line}")
    _pause()


def _trip_form(existing: Trip | None) -> dict[str, Any]:
    is_edit = existing is not None
    p: dict[str, Any] = {}
    p["name"] = _input(
        "Trip name",
        default=existing.name if is_edit else "",
        allow_empty=False)
    p["destination"] = _input(
        "Destination",
        default=(existing.destination or "") if is_edit else "")
    p["start_date"] = _input(
        "Start date (YYYY-MM-DD)",
        default=existing.start_date if is_edit
        else _date.today().isoformat(), allow_empty=False)
    p["end_date"] = _input(
        "End date (optional)",
        default=(existing.end_date or "") if is_edit else "")
    p["year_group"] = _pick_from(
        "Year group", list(YEAR_GROUPS),
        default=existing.year_group if is_edit else DEFAULT_YEAR_GROUP)
    p["cost_per_place"] = _input(
        f"Cost per place ({CURRENCY_SYMBOL})",
        default=f"{existing.cost_per_place:.2f}" if is_edit else "0.00",
        allow_empty=False)
    p["deposit"] = _input(
        f"Deposit ({CURRENCY_SYMBOL})",
        default=f"{existing.deposit:.2f}" if is_edit else "0.00",
        allow_empty=False)
    p["capacity"] = _input(
        "Capacity (optional)",
        default=str(existing.capacity)
                if is_edit and existing.capacity is not None
                else "")
    p["payment_due"] = _input(
        "Payment due (optional)",
        default=(existing.payment_due or "") if is_edit else "")
    p["status"] = _pick_from(
        "Status", list(TRIP_STATUSES),
        default=existing.status if is_edit else DEFAULT_TRIP_STATUS)
    p["lead_staff_id"] = _input(
        "Lead staff (staff ID, optional)",
        default=(existing.lead_staff_id or "") if is_edit else "")
    p["description"] = _input(
        "Description (single line)",
        default=(existing.description or "") if is_edit else "")
    p["notes"] = _input(
        "Notes (optional)",
        default=(existing.notes or "") if is_edit else "")
    return p


def new_trip() -> None:
    print("\n═══ New Trip ═══")
    try:
        payload = _trip_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        t = data.create_trip(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created trip #{t.trip_id} ({t.name})")
    _pause()


def edit_trip(trip_id: int | None = None) -> None:
    print("\n═══ Edit Trip ═══")
    try:
        if trip_id is None:
            trip = _pick_trip()
        else:
            trip = data.get_trip(trip_id)
            if trip is None:
                print(f"  ✗ No trip #{trip_id}")
                _pause()
                return
        payload = _trip_form(trip)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_trip(trip.trip_id, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated #{trip.trip_id}")
    _pause()


def set_trip_status_flow(trip_id: int | None = None) -> None:
    print("\n═══ Change Trip Status ═══")
    try:
        if trip_id is None:
            trip = _pick_trip()
        else:
            trip = data.get_trip(trip_id)
            if trip is None:
                print(f"  ✗ No trip #{trip_id}")
                _pause()
                return
        new = _pick_from("New status", list(TRIP_STATUSES),
                            default=trip.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_trip_status(trip.trip_id, new)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{trip.trip_id} → {new}")
    _pause()


def delete_trip_flow(trip_id: int | None = None) -> None:
    print("\n═══ Delete Trip ═══")
    print("  ⚠ This deletes all bookings and payments for the trip.")
    try:
        if trip_id is None:
            trip = _pick_trip()
        else:
            trip = data.get_trip(trip_id)
            if trip is None:
                print(f"  ✗ No trip #{trip_id}")
                _pause()
                return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete #{trip.trip_id} ({trip.name})? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_trip(trip.trip_id):
        print(f"\n  ✓ Deleted #{trip.trip_id}")
    _pause()


# ── Booking flows ─────────────────────────────────────────────────

def list_bookings_for_trip() -> None:
    print("\n═══ Bookings for Trip ═══")
    try:
        trip = _pick_trip()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_booking_views(
        data.list_booking_views(trip_id=trip.trip_id))
    _booking_action_loop()


def new_booking() -> None:
    print("\n═══ New Booking ═══")
    try:
        trip = _pick_trip()
        print(f"\n  Trip #{trip.trip_id}  {trip.name}  "
              f"({trip.start_date}, {_money(trip.cost_per_place)})")
        sid = _pick_student()
        status = _pick_from("Status", list(BOOKING_STATUSES),
                              default=DEFAULT_BOOKING_STATUS)
        consent = _yes_no("Consent received?", default=False)
        medical = _input("Medical note (optional)")
        dietary = _input("Dietary note (optional)")
        notes = _input("Notes (optional)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        b = data.create_booking(trip.trip_id, {
            "student_id": sid, "status": status,
            "consent_received": consent,
            "medical_note": medical, "dietary_note": dietary,
            "notes": notes,
        })
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Booking #{b.booking_id} created ({sid} → "
          f"#{trip.trip_id}, {status})")
    _pause()


def view_booking(booking_id: int | None = None) -> None:
    print("\n═══ View Booking ═══")
    try:
        bid = booking_id if booking_id is not None else int(
            _input("Booking ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    v = data.view_booking(bid)
    if v is None:
        print(f"  ✗ No booking #{bid}")
        _pause()
        return
    b = v.booking
    t = v.trip
    print()
    print(f"    Booking #{b.booking_id}  →  trip #{t.trip_id} "
          f"({t.name})")
    print(f"    Student      : {b.student_id}  {v.student_name}")
    print(f"    Booked       : {b.booking_date}")
    print(f"    Status       : {b.status}")
    print(f"    Consent      : "
          f"{'Yes' if b.consent_received else 'No'}"
          + (f"  ({b.consent_note})" if b.consent_note else ""))
    print(f"    Medical      : {b.medical_note or '—'}")
    print(f"    Dietary      : {b.dietary_note or '—'}")
    print()
    print(f"    Cost         : {_money(t.cost_per_place)}")
    print(f"    Deposit      : {_money(t.deposit)}")
    print(f"    Paid         : {_money(v.paid)}")
    print(f"    Balance      : {_money(v.balance)}")
    print(f"    Payment state: {v.payment_state}")
    if b.notes:
        print("\n    Notes:")
        for line in b.notes.splitlines() or [""]:
            print(f"      {line}")
    print(f"\n  Payments ({v.payment_count}):")
    _print_payments(data.list_payments(booking_id=bid))
    _pause()


def _booking_form(existing: Booking) -> dict[str, Any]:
    p: dict[str, Any] = {}
    p["status"] = _pick_from(
        "Status", list(BOOKING_STATUSES),
        default=existing.status)
    p["consent_received"] = _yes_no(
        "Consent received?", default=existing.consent_received)
    p["consent_note"] = _input(
        "Consent note", default=existing.consent_note or "")
    p["medical_note"] = _input(
        "Medical note", default=existing.medical_note or "")
    p["dietary_note"] = _input(
        "Dietary note", default=existing.dietary_note or "")
    p["notes"] = _input(
        "Notes", default=existing.notes or "")
    return p


def edit_booking(booking_id: int | None = None) -> None:
    print("\n═══ Edit Booking ═══")
    try:
        bid = booking_id if booking_id is not None else int(
            _input("Booking ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    existing = data.get_booking(bid)
    if existing is None:
        print(f"  ✗ No booking #{bid}")
        _pause()
        return
    try:
        payload = _booking_form(existing)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_booking(bid, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated #{bid}")
    _pause()


def set_booking_status_flow(booking_id: int | None = None) -> None:
    print("\n═══ Change Booking Status ═══")
    try:
        bid = booking_id if booking_id is not None else int(
            _input("Booking ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    existing = data.get_booking(bid)
    if existing is None:
        print(f"  ✗ No booking #{bid}")
        _pause()
        return
    try:
        new = _pick_from("New status", list(BOOKING_STATUSES),
                            default=existing.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_booking_status(bid, new)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{bid} → {new}")
    _pause()


def delete_booking_flow(booking_id: int | None = None) -> None:
    print("\n═══ Delete Booking ═══")
    print("  ⚠ This also deletes payments against the booking.")
    try:
        bid = booking_id if booking_id is not None else int(
            _input("Booking ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    if data.get_booking(bid) is None:
        print(f"  ✗ No booking #{bid}")
        _pause()
        return
    if _input(f"Delete booking #{bid}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_booking(bid):
        print(f"\n  ✓ Deleted #{bid}")
    _pause()


# ── Payment flows ─────────────────────────────────────────────────

def add_payment_flow(booking_id: int | None = None) -> None:
    print("\n═══ Record Payment ═══")
    try:
        bid = booking_id if booking_id is not None else int(
            _input("Booking ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    v = data.view_booking(bid)
    if v is None:
        print(f"  ✗ No booking #{bid}")
        _pause()
        return
    print(f"\n  Booking #{bid}  trip {v.trip.name}")
    print(f"    Cost   : {_money(v.trip.cost_per_place)}")
    print(f"    Paid   : {_money(v.paid)}")
    print(f"    Balance: {_money(v.balance)}")
    today = _date.today().isoformat()
    try:
        amount = _input(
            f"Amount ({CURRENCY_SYMBOL})",
            default=(f"{v.balance:.2f}" if v.balance > 0 else ""),
            allow_empty=False)
        paid_on = _input("Paid on", default=today, allow_empty=False)
        method = _pick_from("Method", list(PAYMENT_METHODS),
                              default=DEFAULT_METHOD)
        status = _pick_from("Status", list(PAYMENT_STATUSES),
                              default=DEFAULT_PAYMENT_STATUS)
        ref = _input("Reference (optional)")
        by = _input("Recorded by (optional)")
        notes = _input("Notes (optional)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        p = data.add_payment(bid, {
            "amount": amount, "paid_on": paid_on,
            "method": method, "status": status,
            "reference": ref, "recorded_by": by, "notes": notes,
        })
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Recorded #{p.payment_id} ({_money(p.amount)})")
    _pause()


def list_payments_flow() -> None:
    print("\n═══ List Payments ═══")
    try:
        tid = _input("Trip ID (optional)") or None
        sid = _input("Student ID (optional)") or None
        method = _input("Method (optional)") or None
        df = _input("From (YYYY-MM-DD, optional)") or None
        dt = _input("To (YYYY-MM-DD, optional)") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.list_payments(
            trip_id=int(tid) if tid else None,
            student_id=sid, method=method,
            date_from=df, date_to=dt)
    except (ValidationError, ValueError) as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_payments(rows)
    _pause()


def edit_payment_flow() -> None:
    print("\n═══ Edit Payment ═══")
    try:
        pid = int(_input("Payment ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    existing = data.get_payment(pid)
    if existing is None:
        print(f"  ✗ No payment #{pid}")
        _pause()
        return
    try:
        amount = _input(
            f"Amount ({CURRENCY_SYMBOL})",
            default=f"{existing.amount:.2f}", allow_empty=False)
        paid_on = _input("Paid on", default=existing.paid_on,
                          allow_empty=False)
        method = _pick_from("Method", list(PAYMENT_METHODS),
                              default=existing.method)
        status = _pick_from("Status", list(PAYMENT_STATUSES),
                              default=existing.status)
        ref = _input("Reference", default=existing.reference or "")
        by = _input("Recorded by", default=existing.recorded_by or "")
        notes = _input("Notes", default=existing.notes or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_payment(pid, {
            "amount": amount, "paid_on": paid_on, "method": method,
            "status": status, "reference": ref,
            "recorded_by": by, "notes": notes,
        })
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated payment #{pid}")
    _pause()


def delete_payment_flow() -> None:
    print("\n═══ Delete Payment ═══")
    try:
        pid = int(_input("Payment ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    if data.get_payment(pid) is None:
        print(f"  ✗ No payment #{pid}")
        _pause()
        return
    if _input(f"Delete payment #{pid}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_payment(pid):
        print(f"\n  ✓ Deleted #{pid}")
    _pause()


def per_student_flow() -> None:
    print("\n═══ Per-Student Bookings ═══")
    try:
        sid = _pick_student()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    student = student_data.get_student(sid)
    print(f"\n  {student.student_id}  {student.full_name}")
    _print_booking_views(data.list_booking_views(student_id=sid))
    _booking_action_loop()


def consent_missing_flow() -> None:
    print("\n═══ Consent Missing ═══")
    rows = data.list_booking_views(active_only=True)
    rows = [v for v in rows if not v.booking.consent_received]
    _print_booking_views(rows)
    _booking_action_loop()


# ── Summary ──────────────────────────────────────────────────────

def summary() -> None:
    print("\n═══ Trips Summary ═══")
    s = data.summary()
    print(f"\n  Trips                : {s.total_trips}")
    print(f"  Upcoming             : {s.upcoming_trips}")
    print(f"  Open for booking     : {s.open_for_booking}")
    print(f"  Completed            : {s.completed}")
    print(f"  Cancelled            : {s.cancelled}")
    if s.next_trip:
        t = s.next_trip
        print(f"\n  Next: #{t.trip_id}  {t.start_date}  "
              f"{t.name}  ({t.status})")
    print(f"\n  Bookings (total)     : {s.total_bookings}")
    print(f"  Active bookings      : {s.active_bookings}")
    print(f"  Waitlist             : {s.waitlist_count}")
    print(f"  Consent missing      : {s.consent_missing}")
    print()
    print(f"  Charged (active)     : {_money(s.total_charged)}")
    print(f"  Paid                 : {_money(s.total_paid)}")
    print(f"  Outstanding          : {_money(s.total_outstanding)}")
    print(f"  Overdue balance      : {_money(s.overdue_balance)}")
    print("\n  Trips by status:")
    for ts in TRIP_STATUSES:
        n = s.by_trip_status.get(ts, 0)
        if n:
            print(f"    {ts:<22} : {n}")
    print("\n  Bookings by status:")
    for bs in BOOKING_STATUSES:
        n = s.by_booking_status.get(bs, 0)
        if n:
            print(f"    {bs:<14} : {n}")
    print("\n  Payment states (active bookings):")
    for ps in PAYMENT_STATES:
        n = s.by_payment_state.get(ps, 0)
        if n:
            print(f"    {ps:<10} : {n}")
    print("\n  Payments by method:")
    for m in PAYMENT_METHODS:
        v = s.by_method.get(m, 0.0)
        if v:
            print(f"    {m:<18} : {_money(v)}")
    if s.top_trips_by_revenue:
        print("\n  Top trips by revenue:")
        for tid, name, rev in s.top_trips_by_revenue:
            print(f"    #{tid:<3}  {name[:30]:<30}  {_money(rev)}")
    _pause()


# ── Action loops ──────────────────────────────────────────────────

def _trip_action_loop() -> None:
    print()
    print("  Actions:  V) View   E) Edit   B) Bookings   "
          "S) Status   D) Delete   (Enter to go back)")
    while True:
        try:
            choice = input("  Action: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not choice:
            return
        if choice not in ("v", "e", "b", "s", "d"):
            print("    Pick V, E, B, S, D, or Enter.")
            continue
        try:
            raw = _input("Trip ID", allow_empty=False)
        except _UserAbort:
            return
        try:
            tid = int(raw)
        except ValueError:
            print("    Trip ID must be a whole number.")
            continue
        if choice == "v":
            view_trip(tid)
        elif choice == "e":
            edit_trip(tid)
        elif choice == "b":
            t = data.get_trip(tid)
            if t is None:
                print(f"  ✗ No trip #{tid}")
                _pause()
            else:
                _print_booking_views(
                    data.list_booking_views(trip_id=tid))
                _booking_action_loop()
        elif choice == "s":
            set_trip_status_flow(tid)
        elif choice == "d":
            delete_trip_flow(tid)
        return


def _booking_action_loop() -> None:
    print()
    print("  Actions:  V) View   E) Edit   P) Add payment   "
          "S) Status   D) Delete   (Enter to go back)")
    while True:
        try:
            choice = input("  Action: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not choice:
            return
        if choice not in ("v", "e", "p", "s", "d"):
            print("    Pick V, E, P, S, D, or Enter.")
            continue
        try:
            raw = _input("Booking ID", allow_empty=False)
        except _UserAbort:
            return
        try:
            bid = int(raw)
        except ValueError:
            print("    Booking ID must be a whole number.")
            continue
        if choice == "v":
            view_booking(bid)
        elif choice == "e":
            edit_booking(bid)
        elif choice == "p":
            add_payment_flow(bid)
        elif choice == "s":
            set_booking_status_flow(bid)
        elif choice == "d":
            delete_booking_flow(bid)
        return


# ── Submenu ───────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Upcoming Trips",       list_upcoming),
    ("All Trips",            list_all),
    ("Filter Trips",         filter_trips),
    ("View Trip",            view_trip),
    ("New Trip",             new_trip),
    ("Edit Trip",            edit_trip),
    ("Change Trip Status",   set_trip_status_flow),
    ("Delete Trip",          delete_trip_flow),
    ("Bookings for Trip",    list_bookings_for_trip),
    ("New Booking",          new_booking),
    ("View Booking",         view_booking),
    ("Edit Booking",         edit_booking),
    ("Change Booking Status", set_booking_status_flow),
    ("Delete Booking",       delete_booking_flow),
    ("Per-Student",          per_student_flow),
    ("Consent Missing",      consent_missing_flow),
    ("Record Payment",       add_payment_flow),
    ("List Payments",        list_payments_flow),
    ("Edit Payment",         edit_payment_flow),
    ("Delete Payment",       delete_payment_flow),
    ("Summary",              summary),
]


def run() -> None:
    while True:
        print("\n── Trips & Payments ──")
        for i, (label, _) in enumerate(_MENU, 1):
            print(f"  {i:>2}) {label}")
        print("   0) Back")
        try:
            choice = input("  Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if choice == "0":
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(_MENU)):
            print("  Invalid selection.")
            continue
        _, handler = _MENU[int(choice) - 1]
        try:
            handler()
        except _UserAbort:
            print("\n  Cancelled.")
        except Exception as e:
            logger.exception("Trips CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Trips & Payments":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Trips CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
