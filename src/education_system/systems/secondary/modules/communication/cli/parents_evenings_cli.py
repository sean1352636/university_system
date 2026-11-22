"""Parents' evenings in the terminal.

The old menu keeps its options in place: 1 Upcoming events, 2 All events,
3 View event, 4 New event, 5 Edit event, 6 Change event status, 7 Delete
event, 8 Bookings for event, 9 New booking, 10 Edit booking, 11 Change
booking status, 12 Delete booking, 13 Staff schedule, 14 Pupil schedule,
15 Summary. New: 16 Teachers taking part, 17 Teachers from groups, 18 A
teacher's slots / room, 19 Add teacher, 20 Attended / missed + notes,
21 Cancel booking, 22 Invite families, 23 E-mail schedules, 24 Booking
rates, 25 Not booked yet, 26 Export CSV, 27 History, 28 My appointments.
Rules live in :mod:`modules.communication.domain.parents_evenings`.
"""

from __future__ import annotations

from typing import Any

from education_system.systems.secondary.modules.communication.domain import parents_evenings as PE
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.cli.prompts import prompts
from education_system.systems.secondary.ui.cli.prompts.prompts import pause as _pause
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt
from education_system.systems.secondary.ui.cli.prompts.prompts import yes as _yes

_ERRORS = (PE.ValidationError, PE.PermissionDenied, PE.NotFound)
_problem = prompts.problem
_int = prompts.ask_int
_pick = prompts.pick


def _events_table(rows: list[PE.Event]) -> None:
    if not rows:
        print("\n  (no events)")
        return
    print(f"\n  {'ID':<4} {'Date':<10} {'Time':<11} {'Name':<30} {'Year':<9} {'Status':<19} "
          "Slot(min)")
    for e in rows:
        print(f"  {e.event_id:<4} {e.event_date:<10} {e.times:<11} {e.name[:30]:<30} "
              f"{e.year_label:<9} {e.status:<19} {e.slot_minutes:>3}")
    print(f"\n  {len(rows)} event(s).")


def _bookings_table(rows: list[PE.Booking]) -> None:
    if not rows:
        print("\n  (no bookings)")
        return
    print(f"\n  {'#':<5} {'Slot':<6} {'Pupil':<10} {'Pupil name':<22} {'Teacher name':<20} "
          f"{'Parent':<18} Status")
    for b in rows:
        print(f"  {b.booking_id:<5} {b.slot_time:<6} {b.admission_no:<10} "
              f"{b.pupil_name[:22]:<22} {b.teacher_name[:20]:<20} "
              f"{(b.parent_name or '')[:18]:<18} {b.status}")
    print(f"\n  {len(rows)} booking(s).")


def _event() -> PE.Event | None:
    rows = PE.list_events(upcoming=True) or PE.list_events()
    for e in rows[-15:]:
        print(f"    #{e.event_id:<4} {e.event_date} {e.name} ({e.status})")
    eid = _int("  Event ID: ")
    return PE.get_event(eid) if eid else None


def _teacher(e: PE.Event, label: str = "Teacher") -> str | None:
    ts = PE.list_teachers(e.event_id)
    names = [f"{t.teacher_name} [{t.teacher_key}]" for t in ts]
    got = _pick(label, names)
    if got in names:
        return ts[names.index(got)].teacher_key
    return got or None


def _ask(label: str, cur: Any) -> str:
    return _prompt(f"  {label}" + (f" [{cur}]" if cur not in (None, "") else "") + ": ")


def _event_details(current: PE.Event | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, label in (("name", "Name"), ("event_date", "Date (YYYY-MM-DD)")):
        v = _ask(label, getattr(current, key) if current else "")
        if v:
            out[key] = v
    y = _pick("Year group", PE.YEAR_CHOICES, current.year_label.replace("Year ", "")
              if current and current.year_group else "All years")
    if y:
        out["year_group"] = y
    for key, label in (("location", "Location"), ("start_time", "Start time (HH:MM)"),
                       ("end_time", "End time (HH:MM)"), ("slot_minutes", "Slot length (min)")):
        v = _ask(label, getattr(current, key) if current else "")
        if v:
            out[key] = v
    if current is None:
        st = _pick("Status", PE.EVENT_STATUSES, PE.DEFAULT_EVENT_STATUS)
        if st:
            out["status"] = st
    v = _ask("Notes", current.notes if current else "")
    if v:
        out["notes"] = v
    m = _pick("In person / online", PE.MODES, current.mode if current else PE.DEFAULT_MODE)
    if m:
        out["mode"] = m
    for key, label in (("meeting_link", "Meeting link (online)"),
                       ("break_slots", "Break slots (e.g. 17:30, 18:00)"),
                       ("booking_opens", "Families book from (date)"),
                       ("booking_closes", "Families book until (date)")):
        v = _ask(label, getattr(current, key) if current else "")
        if v:
            out[key] = "" if v == prompts.CLEAR else v
    return out


# ── The old options ──────────────────────────────────────────────────

def _upcoming(_p: Principal) -> None:
    print("\n═══ Upcoming Parents' Evenings ═══")
    _events_table(PE.list_events(upcoming=True))


def _all(_p: Principal) -> None:
    print("\n═══ Parents' Evenings ═══")
    _events_table(PE.list_events())


def _view(_p: Principal) -> None:
    e = _event()
    if e is None:
        return
    s = PE.summarize_event(e.event_id)
    print(f"\n    Event ID    : #{e.event_id}\n    Name        : {e.name}\n"
          f"    Date        : {e.event_date}\n    Time        : {e.times} "
          f"({s.total_slots} slots/teacher)\n    Year group  : {e.year_label}\n"
          f"    Where       : {e.venue}\n    Status      : {e.status}\n"
          f"    Breaks      : {', '.join(e.breaks) or '-'}\n"
          f"    Families book: {e.booking_opens or '-'} to {e.booking_closes or '-'}\n"
          f"    Teachers    : {s.teachers}   Booked: {s.bookings} of {s.capacity} "
          f"({s.fill_rate}%)")
    if e.notes:
        print(f"    Notes       : {e.notes}")


def _new_event(principal: Principal) -> None:
    e = PE.create_event(_event_details(), actor=principal)
    print(f"  Created event #{e.event_id} with {len(PE.list_teachers(e.event_id))} teacher(s) "
          "from the year's teaching groups.")


def _edit_event(principal: Principal) -> None:
    e = _event()
    if e:
        changes = _event_details(e)
        if changes:
            PE.update_event(e.event_id, changes, actor=principal)
            print("  Saved.")


def _event_status(principal: Principal) -> None:
    e = _event()
    if e:
        st = _pick("New status", PE.EVENT_STATUSES, e.status)
        PE.set_event_status(e.event_id, st or e.status, actor=principal)
        print("  Status saved.")


def _delete_event(principal: Principal) -> None:
    e = _event()
    if e and _yes(f"  Delete '{e.name}' and all its bookings?"):
        PE.delete_event(e.event_id, actor=principal)
        print("  Deleted.")


def _bookings(_p: Principal) -> None:
    e = _event()
    if e:
        _bookings_table(PE.list_bookings(event_id=e.event_id))


def _new_booking(principal: Principal) -> None:
    e = _event()
    if e is None:
        return
    p = PE._pupil(_prompt("  Pupil (admission no. or ID): "))
    if p is None:
        print("  No such pupil.")
        return
    mine = PE.teachers_for_pupil(e.event_id, p.pupil_id)
    if not mine:
        print(f"  None of {p.display_name}'s teachers is taking part.")
    for x in mine:
        t = x["teacher"]
        free = PE.free_slots(e.event_id, t.teacher_key, pupil_id=p.pupil_id)
        print(f"    {t.teacher_name:<22} [{t.teacher_key}] {', '.join(x['subjects'])}: "
              + (", ".join(free[:12]) or "no free slots"))
    key = _teacher(e)
    if not key:
        return
    b = PE.create_booking(e.event_id, {
        "pupil_id": p.pupil_id, "teacher_key": key, "slot_time": _prompt("  Slot (HH:MM): "),
        "parent_name": _prompt(f"  Parent name [{PE.parent_names(p.pupil_id)}]: ")
        or PE.parent_names(p.pupil_id), "notes": _prompt("  Notes: ")}, actor=principal)
    print(f"  Booked #{b.booking_id}: {b.slot_time} with {b.teacher_name}.")


def _booking() -> PE.Booking | None:
    bid = _int("  Booking #: ")
    return PE.get_booking(bid) if bid else None


def _edit_booking(principal: Principal) -> None:
    b = _booking()
    if b is None:
        return
    changes: dict[str, Any] = {}
    for key, label in (("slot_time", "Slot (HH:MM)"), ("parent_name", "Parent name"),
                       ("notes", "Notes"), ("teacher_notes", "Teacher notes")):
        v = _ask(label, getattr(b, key))
        if v:
            changes[key] = "" if v == prompts.CLEAR else v
    st = _pick("Status", PE.BOOKING_STATUSES, b.status)
    if st and st != b.status:
        changes["status"] = st
    if changes:
        PE.update_booking(b.booking_id, changes, actor=principal)
        print("  Saved.")


def _booking_status(principal: Principal) -> None:
    b = _booking()
    if b:
        st = _pick("New status", PE.BOOKING_STATUSES, b.status)
        PE.set_booking_status(b.booking_id, st or b.status, actor=principal)
        print("  Status saved.")


def _delete_booking(principal: Principal) -> None:
    b = _booking()
    if b and _yes(f"  Delete booking #{b.booking_id}?"):
        PE.delete_booking(b.booking_id, actor=principal)
        print("  Deleted.")


def _staff_schedule(principal: Principal) -> None:
    e = _event()
    if e is None:
        return
    key = _teacher(e, "Teacher (blank = me)") or PE.teacher_key_for(principal)
    print("\n" + PE.teacher_schedule_text(e.event_id, key))


def _pupil_schedule(_p: Principal) -> None:
    e = _event()
    if e is None:
        return
    p = PE._pupil(_prompt("  Pupil (admission no. or ID): "))
    if p is None:
        print("  No such pupil.")
        return
    rows = PE.family_schedule(e.event_id, p.pupil_id)
    print(f"\n  {p.display_name}'s family:" if rows else "\n  (no appointments)")
    for b in rows:
        print(f"    {b.slot_time}  {b.teacher_name:<22} {b.pupil_name}  [{b.status}]")


def _summary(_p: Principal) -> None:
    s = PE.summary()
    print(f"\n  Events: {s.total_events}   Upcoming: {s.upcoming_events}   Open for booking: "
          f"{s.open_for_booking}   Completed: {s.completed}   Bookings: {s.total_bookings}")
    if s.next_event:
        e = s.next_event
        print(f"  Next: #{e.event_id} {e.event_date} {e.times} {e.name} ({e.status})")
    print("  By event status: " + ", ".join(f"{k} {v}" for k, v in s.by_event_status.items()))
    print("  By booking status: " + ", ".join(f"{k} {v}"
                                              for k, v in s.by_booking_status.items()))


# ── New ──────────────────────────────────────────────────────────────

def _teachers(_p: Principal) -> None:
    e = _event()
    if e is None:
        return
    for t in PE.list_teachers(e.event_id):
        print(f"  {t.teacher_name:<24} {t.groups or '(added)':<30} room {t.room or '-':<6} "
              f"breaks {', '.join(t.break_list) or '-':<14} "
              f"{'' if t.available else 'NOT AVAILABLE'}")


def _sync(principal: Principal) -> None:
    e = _event()
    if e:
        r = PE.sync_teachers(e.event_id, actor=principal)
        print(f"  Added {r['added']}, removed {r['removed']}; {r['teachers']} taking part.")


def _teacher_slots(principal: Principal) -> None:
    e = _event()
    if e is None:
        return
    key = _teacher(e, "Teacher (blank = me)") or PE.teacher_key_for(principal)
    t = PE.get_teacher(e.event_id, key)
    print(f"  Slots: {', '.join(PE.event_slots(e))}")
    changes: dict[str, Any] = {}
    for k, label in (("room", "Room"), ("breaks", "Breaks (slot times)"), ("notes", "Notes")):
        v = _ask(label, getattr(t, k))
        if v:
            changes[k] = "" if v == prompts.CLEAR else v
    a = _pick("Taking part", ("yes", "no"), "yes" if t.available else "no")
    if a:
        changes["available"] = a
    PE.update_teacher(e.event_id, key, changes, actor=principal)
    print("  Saved.")


def _add_teacher(principal: Principal) -> None:
    e = _event()
    if e:
        t = PE.add_teacher(e.event_id, actor=principal,
                           username=_prompt("  Staff login (blank to type a name): ") or None,
                           name=_prompt("  Name (if no login): ") or None,
                           room=_prompt("  Room: ") or None)
        print(f"  Added {t.teacher_name}.")


def _attendance(principal: Principal) -> None:
    b = _booking()
    if b is None:
        return
    how = _pick("Outcome", ("Attended", "Missed"), "Attended")
    notes = _ask("Teacher notes", b.teacher_notes)
    PE.record_attendance(b.booking_id, how != "Missed", actor=principal,
                         teacher_notes=notes or None)
    print("  Recorded.")


def _cancel(principal: Principal) -> None:
    b = _booking()
    if b and _yes(f"  Cancel {b.pupil_name}'s {b.slot_time} with {b.teacher_name}?"):
        PE.cancel_booking(b.booking_id, actor=principal)
        print("  Cancelled.")


def _deliver(principal: Principal, res: dict[str, Any], what: str) -> None:
    from education_system.systems.secondary.modules.communication.domain import email_outbox as E
    missing = [p for p in res.get("no_email") or [] if p]
    if missing:
        print(f"  No e-mail for {len(missing)} pupil(s): "
              + ", ".join(p.display_name for p in missing[:10]))
    if not res.get("message_id"):
        print("  Nobody to e-mail.")
        return
    print(f"  {res['emails']} {what} saved.")
    try:
        E.deliver(res["message_id"], principal=principal)
        print("  Sent.")
    except Exception as e:  # noqa: BLE001 - the e-mails stay in the outbox
        print(f"  Saved in the outbox; not sent yet ({e}).")


def _invite(principal: Principal) -> None:
    e = _event()
    if e and _yes(f"  E-mail the invitation to the families of {e.year_label}?"):
        _deliver(principal, PE.send_invitations(e.event_id, actor=principal,
                                                note=_prompt("  Extra message (blank ok): ")),
                 "invitation(s)")


def _schedules(principal: Principal) -> None:
    e = _event()
    if e:
        _deliver(principal, PE.email_schedules(e.event_id, actor=principal,
                                               unsent_only=_yes("  Only families not sent one "
                                                                "yet?")), "schedule(s)")


def _rates(_p: Principal) -> None:
    e = _event()
    if e is None:
        return
    by = _pick("By", ("teacher", "form"), "teacher") or "teacher"
    print(f"\n  {'Group':<26} {'Pupils':>6} {'Booked':>7} {'Rate%':>6} {'Appts':>6} "
          f"{'Att':>4} {'Miss':>5}")
    for r in PE.booking_rates(e.event_id, by=by):
        print(f"  {r['group'][:26]:<26} {r['pupils']:>6} {r['booked']:>7} {r['rate']:>6} "
              f"{r['appointments']:>6} {r['attended']:>4} {r['missed']:>5}")


def _not_booked(_p: Principal) -> None:
    e = _event()
    if e:
        rows = PE.not_booked(e.event_id)
        print(f"\n  {len(rows)} pupil(s) with no appointment:")
        for p in rows:
            print(f"    {p.admission_no:<10} {p.display_name:<26} {p.form_group or ''}")


def _export(principal: Principal) -> None:
    e = _event()
    path = _prompt("  Save CSV to (e.g. parents-evening.csv): ") if e else ""
    if e and path:
        print(f"  Exported {PE.export_csv(path, actor=principal, event_id=e.event_id)} "
              "booking(s).")


def _history(_p: Principal) -> None:
    e = _event()
    if e:
        for h in PE.history(e.event_id):
            print(f"  {h['at']}  {h['actor']:<12} {h['action']:<16} "
                  + ", ".join(f"{k}={v}" for k, v in h["detail"].items()))


def _mine(principal: Principal) -> None:
    rows = PE.my_events(principal)
    if not rows:
        print("  You aren't taking part in an upcoming evening.")
    for e, t in rows:
        print("\n" + PE.teacher_schedule_text(e.event_id, t.teacher_key))


_OPTIONS = {"1": _upcoming, "2": _all, "3": _view, "4": _new_event, "5": _edit_event,
            "6": _event_status, "7": _delete_event, "8": _bookings, "9": _new_booking,
            "10": _edit_booking, "11": _booking_status, "12": _delete_booking,
            "13": _staff_schedule, "14": _pupil_schedule, "15": _summary, "16": _teachers,
            "17": _sync, "18": _teacher_slots, "19": _add_teacher, "20": _attendance,
            "21": _cancel, "22": _invite, "23": _schedules, "24": _rates, "25": _not_booked,
            "26": _export, "27": _history, "28": _mine}


def menu(principal: Principal) -> None:
    while True:
        activity_log.record("parents_evenings.view")
        print("\n  ── Parents' Evenings ──")
        print("    1) Upcoming events\n    2) All events\n    3) View event\n    4) New event"
              "\n    5) Edit event\n    6) Change event status\n    7) Delete event"
              "\n    8) Bookings for event\n    9) New booking\n   10) Edit booking"
              "\n   11) Change booking status\n   12) Delete booking\n   13) Staff schedule"
              "\n   14) Pupil schedule\n   15) Summary")
        print("  More")
        print("   16) Teachers taking part\n   17) Teachers from groups"
              "\n   18) A teacher's slots / room\n   19) Add teacher"
              "\n   20) Attended / missed + notes\n   21) Cancel booking\n   22) Invite families"
              "\n   23) E-mail schedules\n   24) Booking rates\n   25) Not booked yet"
              "\n   26) Export CSV\n   27) History\n   28) My appointments")
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
