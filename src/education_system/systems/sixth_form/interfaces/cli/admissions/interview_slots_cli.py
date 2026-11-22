"""Admissions CLI: interview rooms, slots, bookings and the day sheet.

Rooms used to be free text in ``admissions_interview_rooms.json`` next to
the admissions DB. They now live in :mod:`interviews`; the old file's
room names are imported (once — names already listed, active or not,
are skipped) and the file itself is left where it is.
"""

from __future__ import annotations

from datetime import date as _date
from datetime import timedelta as _timedelta

from education_system.systems.sixth_form.domain.admissions import (
    admissions as data,
    admissions_comms as comms,
    interviews,
)
from education_system.systems.sixth_form.domain.admissions.admissions import (
    Applicant,
)
from education_system.systems.sixth_form.interfaces.cli.admissions._common import (
    ROOMS_FILE,
    _UserAbort,
    _attempt,
    _input,
    _load_json,
    _pause,
    _pick_applicant,
    _pick_from,
    _run_submenu,
    _show_messages,
    _yes,
)


def import_legacy_rooms() -> int:
    """Copy the room names from the old side file into the rooms list."""
    legacy = _load_json(ROOMS_FILE, {})
    names = set(legacy.values()) if isinstance(legacy, dict) else set(legacy)
    if not names:
        return 0
    ok, n = _attempt(interviews.import_room_names, sorted(names))
    if ok and n:
        print(f"  ✓ Imported {n} room name(s) from {ROOMS_FILE} "
              "(the file is left in place).")
    return n if ok else 0


# ── Rooms ──────────────────────────────────────────────────────────

def _pick_room(*, optional: bool = True) -> int | None:
    rooms = interviews.list_rooms()
    opts = (["(no room)"] if optional else []) + [
        f"#{r.room_id} {r.name}"
        + (f" (holds {r.capacity})" if r.capacity else "") for r in rooms]
    if not rooms and not optional:
        print("    No interview rooms — add one first.")
        raise _UserAbort
    got = _pick_from("Room", opts, default="(no room)" if optional else None)
    return None if got == "(no room)" else int(got.split()[0].lstrip("#"))


def list_rooms_flow() -> None:
    import_legacy_rooms()
    print("\n═══ Interview Rooms ═══")
    rows = interviews.list_rooms(active_only=False)
    if not rows:
        print("  (none)")
    for r in rows:
        print(f"    #{r.room_id:<4} {r.name:<24} capacity "
              f"{r.capacity or '—':<4} room-booking "
              f"{r.resource_id or '—':<5} {'' if r.active else '(removed)'}")
    _pause()


def add_room_flow() -> None:
    name = _input("Room name", allow_empty=False)
    cap = _input("Capacity (blank = no limit)")
    resource = None
    linked = interviews.room_booking_rooms()
    if linked and _yes("Link it to a room-booking room (clash checks "
                       "against lessons/bookings)?"):
        labels = [f"{rid} {nm}" for rid, nm in linked]
        resource = int(_pick_from("Room-booking room", labels).split()[0])
    notes = _input("Notes")
    ok, r = _attempt(interviews.add_room, name,
                     capacity=int(cap) if cap.isdigit() else None,
                     resource_id=resource, notes=notes or None)
    if ok:
        print(f"  ✓ Room #{r.room_id} {r.name}")
    _pause()


def remove_room_flow() -> None:
    rid = _pick_room(optional=False)
    if _yes("Remove this room from the list (kept for history)?"):
        ok, _ = _attempt(interviews.remove_room, rid)
        if ok:
            print("  ✓ Removed")
    _pause()


def import_rooms_flow() -> None:
    if not import_legacy_rooms():
        print(f"  Nothing new to import from {ROOMS_FILE}.")
    _pause()


# ── Slots ──────────────────────────────────────────────────────────

def _slot_line(s: interviews.Slot) -> str:
    state = (f"{s.booked}/{s.capacity} booked" if s.status == "Open"
             else f"{s.status}: {s.cancel_reason or ''}")
    return (f"#{s.slot_id:<4} {s.label:<40} panel {s.panel_label[:28]:<28} "
            f"{state}")


def pick_slot(*, available_only: bool = True) -> interviews.Slot:
    rows = interviews.list_slots(available_only=available_only,
                                 date_from=_date.today().isoformat())
    if not rows:
        print("    No open interview slots" + (" with places" if
                                               available_only else "") + ".")
        raise _UserAbort
    labels = [_slot_line(s) for s in rows]
    got = _pick_from("Slot", labels)
    return rows[labels.index(got)]


def _slot_form(old: interviews.Slot | None = None) -> dict:
    d = {
        "slot_date": _input("Date (YYYY-MM-DD)", default=old.slot_date if old
                            else (_date.today() + _timedelta(days=7)).isoformat(),
                            allow_empty=False),
        "start_time": _input("Start (HH:MM)", default=old.start_time if old
                             else "09:00", allow_empty=False),
        "end_time": _input("End (HH:MM)", default=old.end_time if old
                           else "09:30", allow_empty=False),
        "panel": _input("Panel (comma-separated names)",
                        default=old.panel_label if old else "",
                        allow_empty=False),
        "capacity": _input("Applicants per slot",
                           default=str(old.capacity) if old else "1"),
    }
    d["room_id"] = _pick_room()
    d["notes"] = _input("Notes", default=(old.notes or "") if old else "")
    return d


def _warn_clashes(d: dict, exclude: int | None = None) -> bool:
    """Show clashes; True when it is fine to go on."""
    try:
        rep = interviews.find_clashes(
            slot_date=d["slot_date"], start_time=d["start_time"],
            end_time=d["end_time"], room_id=d["room_id"],
            panel=[p.strip() for p in d["panel"].split(",") if p.strip()],
            exclude_slot_id=exclude)
    except ValueError:
        return True  # the save reports the bad value
    if rep:
        print(f"  ⚠ Clash: {rep.message()}")
        return False
    return True


def list_slots_flow() -> None:
    print("\n═══ Interview Slots ═══")
    frm = _input("From (YYYY-MM-DD)", default=_date.today().isoformat())
    to = _input("To (blank = any)") or None
    cancelled = _yes("Include cancelled?")
    rows = interviews.list_slots(date_from=frm, date_to=to,
                                 include_cancelled=cancelled)
    for s in rows:
        print("  " + _slot_line(s))
    if not rows:
        print("  (none)")
    _pause()


def create_slot_flow() -> None:
    import_legacy_rooms()
    print("\n═══ New Interview Slot ═══")
    d = _slot_form()
    if not _warn_clashes(d):
        print("  The slot cannot be saved with a clash; change the time, "
              "room or panel.")
        _pause()
        return
    ok, s = _attempt(interviews.create_slot, d)
    if ok:
        print(f"  ✓ Slot #{s.slot_id} {s.label}")
    _pause()


def edit_slot_flow() -> None:
    s = pick_slot(available_only=False)
    d = _slot_form(s)
    _warn_clashes(d, exclude=s.slot_id)
    ok, s2 = _attempt(interviews.update_slot, s.slot_id, d)
    if ok:
        print(f"  ✓ Slot #{s2.slot_id} {s2.label}")
    _pause()


def cancel_slot_flow() -> None:
    s = pick_slot(available_only=False)
    if s.booked:
        print(f"  {s.booked} applicant(s) booked — their interviews are "
              "cancelled too.")
    reason = _input("Reason", allow_empty=False)
    if not _yes(f"Cancel slot #{s.slot_id}?"):
        raise _UserAbort
    ok, affected = _attempt(interviews.cancel_slot, s.slot_id, reason=reason)
    if ok:
        print(f"  ✓ Cancelled; affected: {', '.join(affected) or 'nobody'}")
    _pause()


def day_sheet_flow() -> None:
    day = _input("Day (YYYY-MM-DD)", default=_date.today().isoformat())
    print(f"\n═══ Interview Day Sheet — {day} ═══")
    sheet = interviews.day_sheet(day)
    if not sheet:
        print("  (no open slots)")
    for s, bookings in sheet:
        print(f"\n  {s.start_time}–{s.end_time}  {s.room_name or 'no room'}"
              f"  panel: {s.panel_label}  ({s.booked}/{s.capacity})")
        for b in bookings:
            a = data.get_applicant(b.applicant_id)
            print(f"      {b.applicant_id}  "
                  f"{a.full_name if a else '?':<24} [{b.status}]"
                  + (f"  {a.phone or ''}" if a else ""))
        if not bookings:
            print("      (no bookings)")
    _pause()


# ── Bookings ───────────────────────────────────────────────────────

def book_applicant(a: Applicant) -> bool:
    """Book *a* into a slot (or move their booking). True if booked."""
    current = interviews.active_booking(a.applicant_id)
    s = pick_slot()
    if current:
        reason = _input(f"Moving from slot #{current.slot_id} — reason")
        ok, _ = _attempt(interviews.reschedule, a.applicant_id, s.slot_id,
                         reason=reason or None)
    else:
        ok, _ = _attempt(interviews.book, a.applicant_id, s.slot_id)
    if ok:
        print(f"  ✓ {a.applicant_id} booked into {s.label}")
        if _yes("  E-mail the interview invitation?"):
            send_invite(a.applicant_id)
    return ok


def send_invite(aid: str) -> None:
    parents = _yes("  Copy to parents/carers?")
    ok, msgs = _attempt(comms.send_interview_invite, aid,
                        include_parents=parents)
    if ok:
        _show_messages(msgs)


def book_flow() -> None:
    a = _pick_applicant()
    book_applicant(a)
    _pause()


def slot_bookings_flow() -> None:
    s = pick_slot(available_only=False)
    rows = interviews.slot_bookings(s.slot_id, active_only=False)
    print(f"\n  Slot #{s.slot_id} {s.label}")
    for b in rows:
        print(f"    booking #{b.booking_id} {b.applicant_id} [{b.status}] "
              f"by {b.booked_by or '—'} {b.booked_at[:16]}"
              + (f" — {b.reason}" if b.reason else ""))
    if not rows:
        print("    (no bookings)")
    _pause()


def cancel_booking_flow() -> None:
    a = _pick_applicant()
    b = interviews.active_booking(a.applicant_id)
    if b is None:
        print("  This applicant has no booked slot.")
        _pause()
        return
    reason = _input("Reason")
    ok, _ = _attempt(interviews.cancel_booking, b.booking_id,
                     reason=reason or None)
    if ok:
        print("  ✓ Booking cancelled (interview cancelled)")
    _pause()


def booking_history_flow() -> None:
    a = _pick_applicant()
    print(f"\n═══ Interview Bookings — {a.applicant_id} {a.full_name} ═══")
    rows = interviews.booking_history(a.applicant_id)
    for b in rows:
        where = b.slot.label if b.slot else f"slot #{b.slot_id}"
        print(f"    #{b.booking_id} {where}  [{b.status}]  booked "
              f"{b.booked_at[:16]} by {b.booked_by or '—'}"
              + (f"; ended {b.ended_at[:16]} by {b.ended_by or '—'}"
                 if b.ended_at else "")
              + (f" — {b.reason}" if b.reason else ""))
    if not rows:
        print("    (no bookings)")
    _pause()


MENU = [
    ("Day sheet", day_sheet_flow),
    ("List slots", list_slots_flow),
    ("New slot (clash-checked)", create_slot_flow),
    ("Edit slot", edit_slot_flow),
    ("Cancel slot", cancel_slot_flow),
    ("Slot bookings", slot_bookings_flow),
    ("─" * 6, lambda: None),
    ("Book an applicant into a slot", book_flow),
    ("Cancel an applicant's booking", cancel_booking_flow),
    ("Applicant booking history", booking_history_flow),
    ("─" * 6, lambda: None),
    ("Rooms", list_rooms_flow),
    ("Add room", add_room_flow),
    ("Remove room", remove_room_flow),
    ("Import rooms from the old side file", import_rooms_flow),
]


def run() -> None:
    _run_submenu("Interview Slots & Rooms", MENU)
