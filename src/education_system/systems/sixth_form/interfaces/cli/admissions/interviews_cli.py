"""Admissions CLI: interviews — scheduling, outcomes, agenda and tools."""

from __future__ import annotations

from datetime import date as _date
from datetime import timedelta as _timedelta
from typing import Any
from education_system.systems.sixth_form.domain.admissions import (
    admissions as data,
    interviews,
)
from education_system.systems.sixth_form.domain.admissions.admissions import (
    Applicant,
    RECOMMENDATIONS,
    ValidationError,
)
from education_system.systems.sixth_form.interfaces.cli.admissions._common import (
    CONFIG_FILE,
    DEFAULT_SLOT_CAP,
    _UserAbort,
    _input,
    _load_json,
    _merge_ics,
    _pause,
    _pick_applicant,
    _pick_from,
    _store_json,
    _yes,
    _attempt,
)
from education_system.systems.sixth_form.interfaces.cli.admissions.interview_slots_cli import (
    book_applicant,
    import_legacy_rooms,
    pick_slot,
    send_invite,
)



def schedule_interview_flow() -> None:
    print("\n═══ Schedule Interview ═══")
    try:
        a = _pick_applicant()
        if interviews.list_slots(available_only=True) and _yes(
                "Book into an interview slot (room/panel/clash checks)?",
                default="y"):
            book_applicant(a)
            _pause()
            return
        date_str = _input("Interview date (YYYY-MM-DD)",
                            default=a.interview_date or "",
                            allow_empty=False)
        interviewer = _input("Interviewer",
                              default=a.interviewer or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.schedule_interview(a.applicant_id,
                                  interview_date=date_str,
                                  interviewer=interviewer or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Interview scheduled for {a.applicant_id} on {date_str}")
    if _yes("  E-mail the interview invitation?"):
        send_invite(a.applicant_id)
    _pause()


def record_interview_flow() -> None:
    print("\n═══ Record Interview Notes ═══")
    try:
        a = _pick_applicant()
        notes = _input("Interview notes")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.record_interview(a.applicant_id, interview_notes=notes)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Interview recorded for {a.applicant_id}")
    _pause()


def _capture_scorecard(a: Applicant) -> dict[str, Any]:
    existing = data.get_interview_score(a.applicant_id)

    def grade(attr: str) -> str:
        cur = getattr(existing, attr) if existing else None
        return _input(f"{attr.replace('_', ' ').title()} (1-5, blank=skip)",
                       default=str(cur) if cur else "")
    rec = _pick_from("Recommendation", ["(skip)"] + list(RECOMMENDATIONS))
    return {
        "motivation": grade("motivation") or None,
        "subject_fit": grade("subject_fit") or None,
        "attainment": grade("attainment") or None,
        "recommendation": None if rec == "(skip)" else rec,
        "scored_by": _input("Scored by") or None,
        "comments": _input("Comments") or None,
    }


# ── Interviews (items 21–28) ──────────────────────────────────────

def interviews_agenda_flow() -> None:
    print("\n═══ Interview Agenda ═══")
    rows = [a for a in data.list_applicants() if a.interview_date]
    rows.sort(key=lambda a: (a.interview_date or "",
                              a.interviewer or "", a.full_name))
    if not rows:
        print("  (no scheduled interviews)")
        _pause()
        return
    # Clash detection (item 23): same interviewer + same day.
    from collections import Counter
    slots = Counter((a.interview_date, a.interviewer)
                    for a in rows if a.interviewer)
    clashes = {k for k, n in slots.items() if n > 1}
    current = None
    for a in rows:
        if a.interview_date != current:
            current = a.interview_date
            print(f"\n  ── {a.interview_date} ──")
        flag = "  ⚠CLASH" if (a.interview_date, a.interviewer) in clashes \
            else ""
        print(f"      {a.applicant_id}  {a.full_name[:24]:<24}  "
              f"{a.interviewer or '—':<16}  [{a.status}]{flag}")
    # Interviewer workload (item 22).
    print("\n  Interviewer load:")
    load = Counter(a.interviewer or "(unassigned)" for a in rows)
    for who, n in sorted(load.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"      {who:<20} {n}")
    _pause()


def record_outcome_flow() -> None:
    print("\n═══ Record Interview Outcome ═══")
    try:
        a = _pick_applicant()
        notes = _input("Interview notes", default=a.interview_notes or "")
        do_score = _yes("Add a scorecard?", default="y")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.record_interview(a.applicant_id, interview_notes=notes or None)
        if do_score:
            vals = _capture_scorecard(a)
            data.save_interview_score(a.applicant_id, **vals)
    except (ValidationError, _UserAbort) as e:
        print(f"  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Outcome recorded for {a.applicant_id}")
    _pause()


def reschedule_flow() -> None:
    print("\n═══ Reschedule Interview ═══")
    try:
        a = _pick_applicant()
        if interviews.active_booking(a.applicant_id):
            # Booked into a slot: move the booking, not just the date.
            book_applicant(a)
            _pause()
            return
        new_date = _input("New date (YYYY-MM-DD)",
                           default=a.interview_date or "", allow_empty=False)
        reason = _input("Reason (optional)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    # Clash warning (item 23).
    clash = [x for x in data.list_applicants()
             if x.interviewer and x.interviewer == a.interviewer
             and x.interview_date == new_date
             and x.applicant_id != a.applicant_id]
    if clash and not _yes(
            f"  {a.interviewer} already has "
            f"{', '.join(x.full_name for x in clash)} on {new_date}. "
            f"Proceed?"):
        print("\n  Cancelled.")
        return
    try:
        data.reschedule_interview(a.applicant_id, new_date=new_date,
                                   reason=reason or None,
                                   interviewer=a.interviewer)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Rescheduled {a.applicant_id} to {new_date}")
    _pause()


def cancel_interview_flow() -> None:
    print("\n═══ Cancel Interview ═══")
    try:
        a = _pick_applicant()
        reason = _input("Reason (optional)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    b = interviews.active_booking(a.applicant_id)
    if b is not None:
        ok, _ = _attempt(interviews.cancel_booking, b.booking_id,
                         reason=reason or None)
    else:
        ok, _ = _attempt(data.cancel_interview, a.applicant_id,
                         reason=reason or None)
    if not ok:
        _pause()
        return
    print(f"\n  ✓ Interview cancelled for {a.applicant_id} "
          f"(returned to Under Review)")
    _pause()


def no_show_flow() -> None:
    print("\n═══ Record No-Show ═══")
    try:
        a = _pick_applicant()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    data.mark_no_show(a.applicant_id, follow_up=True)
    print(f"\n  ✓ {a.applicant_id} marked no-show (flagged for follow-up)")
    _pause()


def export_ics_flow() -> None:
    print("\n═══ Export Interview (.ics) ═══")
    try:
        a = _pick_applicant()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        ics = data.interview_to_ics(a.applicant_id)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    path = _input("Save to path", default=f"interview_{a.applicant_id}.ics")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(ics)
    print(f"  ✓ Saved to {path}")
    _pause()


# ══ Interview flows (GUI items 16–25) ═════════════════════════════

def _scheduled() -> list[Applicant]:
    rows = [a for a in data.list_applicants() if a.interview_date]
    rows.sort(key=lambda a: (a.interview_date or "", a.interviewer or "",
                             a.full_name))
    return rows


def calendar_view_flow() -> None:
    """Item 16 — month calendar of interview counts."""
    import calendar
    from collections import Counter
    print("\n═══ Interview Calendar ═══")
    ym = _input("Month (YYYY-MM)", default=_date.today().strftime("%Y-%m"))
    try:
        year, month = (int(x) for x in ym.split("-")[:2])
    except (ValueError, IndexError):
        print("  ✗ Invalid month.")
        _pause()
        return
    counts = Counter(a.interview_date[:10] for a in _scheduled()
                     if a.interview_date)
    print(f"\n  {calendar.month_name[month]} {year}")
    print("   Mon   Tue   Wed   Thu   Fri   Sat   Sun")
    for week in calendar.Calendar(firstweekday=0).monthdayscalendar(year,
                                                                    month):
        cells = []
        for day in week:
            if day == 0:
                cells.append("     ")
            else:
                iso = f"{year:04d}-{month:02d}-{day:02d}"
                n = counts.get(iso, 0)
                cells.append(f"{day:>2}·{n}" if n else f"{day:>2}  ")
        print("  " + " ".join(f"{c:<5}" for c in cells))
    _pause()


def bulk_schedule_flow() -> None:
    """Item 17 — schedule the unscheduled pool into sequential days."""
    print("\n═══ Bulk Schedule ═══")
    pool = (data.list_applicants(status="Submitted")
            + data.list_applicants(status="Under Review"))
    if not pool:
        print("  No applicants in 'Submitted' / 'Under Review'.")
        _pause()
        return
    try:
        start = _input(f"Schedule {len(pool)} applicant(s) from date "
                       f"(YYYY-MM-DD)", default=_date.today().isoformat())
        per_day = int(_input("Interviews per day",
                             default=str(DEFAULT_SLOT_CAP)))
        who = _input("Interviewer for all (blank = unset)")
    except (ValueError, _UserAbort):
        print("\n  Cancelled.")
        return
    try:
        start_d = _date.fromisoformat(start)
    except ValueError:
        print("  ✗ Invalid start date.")
        _pause()
        return
    if per_day < 1 or not _yes(f"Schedule {len(pool)}, {per_day}/day, "
                               f"from {start_d}?"):
        print("\n  Cancelled.")
        return
    ok, fail = 0, []
    for i, a in enumerate(pool):
        day = start_d + _timedelta(days=i // per_day)
        try:
            data.schedule_interview(a.applicant_id,
                                    interview_date=day.isoformat(),
                                    interviewer=who or None)
            ok += 1
        except Exception as e:  # noqa: BLE001
            fail.append(f"{a.applicant_id}: {e}")
    print(f"\n  ✓ Scheduled {ok} of {len(pool)}.")
    for f in fail[:12]:
        print(f"  ✗ {f}")
    _pause()


def send_reminders_flow() -> None:
    """Item 18 — generate interview reminders for a given day."""
    print("\n═══ Send Interview Reminders ═══")
    default = (_date.today() + _timedelta(days=1)).isoformat()
    target = _input("Reminders for date (YYYY-MM-DD)", default=default)
    due = [a for a in _scheduled()
           if a.interview_date and a.interview_date[:10] == target[:10]]
    if not due:
        print(f"  No interviews scheduled on {target}.")
        _pause()
        return
    lines = [f"Interview reminders for {target} ({len(due)})", "=" * 52, ""]
    for a in due:
        b = interviews.active_booking(a.applicant_id)
        room = (b.slot.room_name if b and b.slot and b.slot.room_name
                else "TBC")
        lines += [f"To: {a.email or '(no email on file)'}",
                  f"Subject: Your sixth-form interview on {a.interview_date}",
                  "", f"Dear {a.first_name},", "",
                  f"Reminder: interview on {a.interview_date}. Interviewer: "
                  f"{a.interviewer or 'TBC'}. Room: {room}.",
                  "", "Please arrive 10 minutes early with your ID.",
                  "", "-" * 52, ""]
    text = "\n".join(lines)
    print("\n" + text)
    if _yes("E-mail each applicant their interview invitation/reminder "
            "now (with the calendar entry)?"):
        for a in due:
            print(f"  {a.applicant_id}:")
            send_invite(a.applicant_id)
    if _yes("Save to a file?"):
        path = _input("Save to path", default=f"reminders_{target}.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"  ✓ Saved to {path}")
    _pause()


def export_all_ics_flow() -> None:
    """Item 19 — one combined .ics for every scheduled interview."""
    print("\n═══ Export All Interviews (.ics) ═══")
    rows = _scheduled()
    if not rows:
        print("  (no scheduled interviews)")
        _pause()
        return
    body, n = _merge_ics([a.applicant_id for a in rows])
    path = _input("Save to path", default="interviews.ics")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)
    print(f"  ✓ Wrote {n} interview event(s) to {path}")
    _pause()


def detect_clashes_flow() -> None:
    """Item 20 — report interviewer double-bookings."""
    print("\n═══ Detect Clashes ═══")
    from collections import Counter
    rows = _scheduled()
    slots = Counter((a.interview_date, a.interviewer)
                    for a in rows if a.interviewer)
    clashes = {k for k, v in slots.items() if v > 1}
    if not clashes:
        print("  No interviewer double-bookings.")
        _pause()
        return
    for date, who in sorted(clashes):
        members = [a for a in rows
                   if a.interview_date == date and a.interviewer == who]
        print(f"\n  {date}  {who}  ×{len(members)}")
        for a in members:
            print(f"      {a.applicant_id}  {a.full_name}")
    _pause()


def room_assignment_flow() -> None:
    """Item 21 — set the room of an interview slot (rooms are a managed
    list now; the applicant gets the room of the slot they are booked in)."""
    print("\n═══ Assign Interview Room ═══")
    import_legacy_rooms()
    a = None
    if _yes("Pick by applicant (else pick a slot)?", default="y"):
        a = _pick_applicant()
        b = interviews.active_booking(a.applicant_id)
        if b is None:
            print(f"  {a.applicant_id} is not booked into a slot; book them "
                  "first (Interviews → Slots & rooms).")
            _pause()
            return
        slot = b.slot
    else:
        slot = pick_slot(available_only=False)
    rooms = interviews.list_rooms()
    if not rooms:
        print("  No interview rooms yet — add one under Slots & rooms.")
        _pause()
        return
    labels = ["(no room)"] + [f"#{r.room_id} {r.name}" for r in rooms]
    got = _pick_from(f"Room for slot #{slot.slot_id} {slot.label}", labels)
    room_id = None if got == "(no room)" else int(got.split()[0].lstrip("#"))
    ok, s2 = _attempt(interviews.update_slot, slot.slot_id,
                      {"room_id": room_id})
    if ok:
        print(f"  ✓ Slot #{s2.slot_id} room: {s2.room_name or '(none)'}"
              + (f" — applies to everyone in it, incl. {a.applicant_id}"
                 if a else ""))
    _pause()


def panel_view_flow() -> None:
    """Item 22 — scheduled interviews grouped by interviewer."""
    print("\n═══ Interview Panels ═══")
    by_who: dict[str, list[Applicant]] = {}
    for a in _scheduled():
        by_who.setdefault(a.interviewer or "(unassigned)", []).append(a)
    if not by_who:
        print("  (no scheduled interviews)")
        _pause()
        return
    for who in sorted(by_who):
        print(f"\n  {who}  ({len(by_who[who])})")
        for a in by_who[who]:
            print(f"      {a.interview_date or '—'}  {a.applicant_id}  "
                  f"{a.full_name[:24]:<24}  [{a.status}]")
    _pause()


def no_show_report_flow() -> None:
    """Item 23 — applicants flagged for follow-up / no-show."""
    print("\n═══ No-Show / Follow-up Report ═══")
    flagged = [a for a in data.list_applicants() if a.follow_up]
    if not flagged:
        print("  (nobody currently flagged for follow-up)")
        _pause()
        return
    for a in flagged:
        print(f"    {a.applicant_id}  {a.full_name[:24]:<24}  [{a.status}]  "
              f"interview {a.interview_date or '—'}  {a.email or ''}")
    print(f"\n  {len(flagged)} flagged.")
    _pause()


def reschedule_batch_flow() -> None:
    """Item 24 — shift every interview on a day by N days."""
    print("\n═══ Reschedule a Whole Day ═══")
    day = _input("Interview date to shift (YYYY-MM-DD)",
                 default=_date.today().isoformat())
    affected = [a for a in _scheduled()
                if a.interview_date and a.interview_date[:10] == day[:10]]
    if not affected:
        print(f"  No interviews on {day}.")
        _pause()
        return
    try:
        shift = int(_input(f"Shift all {len(affected)} interview(s) by how "
                           f"many days?", default="1"))
        base = _date.fromisoformat(day[:10])
    except (ValueError, _UserAbort):
        print("\n  Cancelled.")
        return
    new_day = (base + _timedelta(days=shift)).isoformat()
    ok, fail = 0, []
    for a in affected:
        try:
            data.reschedule_interview(a.applicant_id, new_date=new_day,
                                      reason=f"Day moved {shift:+d}d",
                                      interviewer=a.interviewer)
            ok += 1
        except Exception as e:  # noqa: BLE001
            fail.append(f"{a.applicant_id}: {e}")
    print(f"\n  ✓ Moved {ok} interview(s) to {new_day}.")
    for f in fail:
        print(f"  ✗ {f}")
    _pause()


def slot_capacity_flow() -> None:
    """Item 25 — daily interview capacity vs bookings."""
    print("\n═══ Slot Capacity ═══")
    from collections import Counter
    cfg = _load_json(CONFIG_FILE, {})
    cap = int(cfg.get("daily_slot_cap", DEFAULT_SLOT_CAP))
    new = _input("Daily slot cap", default=str(cap))
    if new.isdigit() and int(new) != cap:
        cap = int(new)
        cfg["daily_slot_cap"] = cap
        _store_json(CONFIG_FILE, cfg)
    counts = Counter(a.interview_date[:10] for a in _scheduled()
                     if a.interview_date)
    slots = interviews.list_slots(date_from=_date.today().isoformat())
    if slots:
        print("\n  Interview slots (managed capacity):")
        per_day: dict[str, list[int]] = {}
        for sl in slots:
            d = per_day.setdefault(sl.slot_date, [0, 0])
            d[0] += sl.capacity
            d[1] += sl.booked
        for day in sorted(per_day):
            capd, used = per_day[day]
            print(f"    {day}   places {capd:>3}  booked {used:>3}  "
                  f"free {capd - used:>3}")
    print(f"\n  Unslotted interviews vs daily cap: {cap} (kept in "
          f"{CONFIG_FILE} — slots have their own capacity)\n")
    for day in sorted(counts):
        used = counts[day]
        free = cap - used
        flag = "  ⚠ OVER" if free < 0 else ""
        print(f"    {day}   used {used:>2}  free {free:>3}{flag}")
    if not counts:
        print("    (no interviews scheduled)")
    _pause()
