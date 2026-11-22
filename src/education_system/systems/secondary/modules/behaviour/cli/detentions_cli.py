"""Detentions in the terminal.

The old menu keeps its options in place: 1 Schedule detention, 2 List
detentions, 3 View detention, 4 Edit detention, 5 Mark attended / missed /
excused, 6 Reschedule, 7 Daily register, 8 Pupil summary, 9 Cohort summary,
10 Delete detention. New: 11 Schedule for several pupils, 12 Book into a
session, 13 Notice home, 14 Sessions, 15 Add / edit session, 16 Cancel
session, 17 Move pupils to another session, 18 Session register, 19 Missed
to follow up, 20 Reports, 21 History, 22 Export CSV. Rules live in
:mod:`modules.behaviour.domain.detentions`.
"""

from __future__ import annotations

from typing import Any

from education_system.systems.secondary.modules.behaviour.domain import detentions as DT
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.cli.prompts import prompts
from education_system.systems.secondary.ui.cli.prompts.prompts import pause as _pause
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt
from education_system.systems.secondary.ui.cli.prompts.prompts import yes as _yes

_ERRORS = (DT.ValidationError, DT.PermissionDenied, DT.NotFound)
_problem = prompts.problem
_int = prompts.ask_int
_pick = prompts.pick


def _table(rows: list[DT.Detention]) -> None:
    if not rows:
        print("  (no detentions)")
        return
    print(f"  {'ID':<4} {'Date':<10} {'Time':<5} {'Pupil':<24} {'Yr':<3} {'Type':<13} "
          f"{'Min':<4} {'Supervisor':<16} {'Status':<11} Reason")
    for d in rows:
        print(f"  {d.detention_id:<4} {d.detention_date:<10} {(d.start_time or '-'):<5} "
              f"{d.pupil_name[:24]:<24} {d.pupil_year:<3} {d.detention_type[:13]:<13} "
              f"{d.duration_min:<4} {(d.supervisor or '-')[:16]:<16} {d.status:<11} "
              f"{d.reason[:30]}")


def _details(current: DT.Detention | None = None) -> dict[str, Any]:
    """The old questions; Enter keeps the current value (or the default)."""
    def ask(label: str, cur: Any) -> str:
        return _prompt(f"  {label}" + (f" [{cur}]" if cur not in (None, "") else "") + ": ")

    out: dict[str, Any] = {}
    for key, label, cur in (("detention_date", "Date (YYYY-MM-DD)",
                             current.detention_date if current else ""),
                            ("start_time", "Start time (HH:MM, blank ok)",
                             current.start_time if current else ""),
                            ("duration_min", "Duration in minutes",
                             current.duration_min if current else DT.DEFAULT_DURATION)):
        v = ask(label, cur)
        if v:
            out[key] = v
    t = _pick("Type", DT.DETENTION_TYPES, current.detention_type if current else
              DT.DEFAULT_TYPE)
    if t:
        out["detention_type"] = t
    for key, label, cur in (("location", "Location", current.location if current else ""),
                            ("supervisor", "Supervisor", current.supervisor if current else ""),
                            ("reason", "Reason", current.reason if current else ""),
                            ("set_by", "Set by", current.set_by if current else ""),
                            ("related_entry_id", "Behaviour incident ID (blank ok)",
                             current.related_entry_id if current else ""),
                            ("notes", "Notes", current.notes if current else "")):
        v = ask(label, cur)
        if v:
            out[key] = v
    return out


def _detention() -> DT.Detention | None:
    did = _int("  Detention ID: ")
    return DT.get(did) if did else None


def _pupil() -> P.Pupil | None:
    ref = _prompt("  Pupil ID / admission no.: ")
    p = DT._pupil(ref) if ref else None
    if ref and p is None:
        print("  No such pupil.")
    return p


def _confirm(data: dict[str, Any], principal: Principal, pupils: list[Any] | None = None
             ) -> bool:
    try:
        warnings = DT.check(data, actor=principal, pupils=pupils)
    except _ERRORS:
        return True
    for w in warnings:
        print(f"  ! {w}")
    return not warnings or _yes("  Set it anyway?")


def _offer_notice(done: list[DT.Detention], principal: Principal) -> None:
    if done and _yes("  E-mail a notice to the family now?"):
        _send_notice([d.detention_id for d in done], principal, "")


def _send_notice(ids: list[int], principal: Principal, note: str) -> None:
    from education_system.systems.secondary.modules.communication.domain import email_outbox as E
    res = DT.notify_parents(ids, actor=principal, note=note)
    print(f"  {res['emails']} e-mail(s) prepared.")
    for p in res["no_email"]:
        print(f"  No parent e-mail address for {p.display_name}.")
    if res["message_id"]:
        try:
            E.deliver(res["message_id"], principal=principal)
            print("  Sent.")
        except Exception as e:  # noqa: BLE001 - queued; shown to the user
            print(f"  Queued - delivery failed: {e}")


# ── Old options ──────────────────────────────────────────────────────

def _new(principal: Principal) -> None:
    p = _pupil()
    if p is None:
        return
    data = {"pupil_id": p.pupil_id, **_details()}
    if not _confirm(data, principal):
        return
    d = DT.create(data, actor=principal)
    print(f"\n  Scheduled #{d.detention_id} for {d.pupil_name} on {d.when}.")
    _offer_notice([d], principal)


def _list(_principal: Principal) -> None:
    y = _prompt("  Year (Enter = all): ")
    ref = _prompt("  Pupil ID / admission no. (Enter = all): ")
    p = DT._pupil(ref) if ref else None
    if ref and p is None:
        print("  No such pupil.")
        return
    t = _pick("Type (Enter = all)", DT.DETENTION_TYPES)
    st = _pick("Status (Enter = all)", DT.DETENTION_STATUSES)
    _table(DT.list_detentions(year_group=y or None, pupil_id=p.pupil_id if p else None,
                              detention_type=t, status=st, limit=200))


def _view(_principal: Principal) -> None:
    d = _detention()
    if d is None:
        return
    print(f"\n  #{d.detention_id}  {d.pupil_name} ({d.admission_no}) Year {d.pupil_year} "
          f"{d.form_group or ''}")
    for label, value in (("When", f"{d.when}, {d.duration_min} min"),
                         ("Type", d.detention_type), ("Location", d.location),
                         ("Supervisor", d.supervisor), ("Reason", d.reason),
                         ("Set by", d.set_by), ("Status", d.status),
                         ("Session", f"#{d.session_id}" if d.session_id else None),
                         ("Behaviour incident", f"#{d.related_entry_id}"
                          if d.related_entry_id else None),
                         ("Rescheduled from", f"#{d.rescheduled_from}"
                          if d.rescheduled_from else None),
                         ("Rescheduled to", f"#{d.rescheduled_to}" if d.rescheduled_to
                          else None),
                         ("Marked", f"{d.marked_at} by {d.marked_by}" if d.marked_at else None),
                         ("Family told", d.parents_notified_at), ("Notes", d.notes)):
        if value:
            print(f"    {label + ':':<20} {value}")


def _edit(principal: Principal) -> None:
    d = _detention()
    if d is None:
        return
    if not DT.can_edit(principal, d):
        print("  Only the person who set it (while it's scheduled) or the detentions lead can "
              "change it. Use 5 or 6.")
        return
    d = DT.update(d.detention_id, _details(d), actor=principal)
    print(f"  Saved #{d.detention_id}.")


def _set_status(principal: Principal) -> None:
    d = _detention()
    if d is None:
        return
    print(f"  {d.pupil_name} on {d.when} - currently {d.status}")
    st = _pick("New status", DT.REGISTER_STATUSES)
    if not st:
        return
    note = _prompt("  Note (optional): ")
    d = DT.set_status(d.detention_id, st, actor=principal, note=note or None)
    print(f"  #{d.detention_id} is now {d.status}.")


def _reschedule(principal: Principal) -> None:
    d = _detention()
    if d is None:
        return
    print(f"  Currently {d.when}, {d.detention_type}, status {d.status}")
    sessions = DT.list_sessions(upcoming=True)
    sid = None
    if sessions and _yes("  Book into a session?"):
        for s in sessions:
            print(f"    {s.session_id:>4}) {s.label}"
                  + (f" ({s.places_left} left)" if s.places_left is not None else ""))
        sid = _int("  Session ID: ")
    new_date = None if sid else _prompt("  New date (YYYY-MM-DD): ")
    start = None if sid else (_prompt("  New start time (Enter = same): ") or None)
    new = DT.reschedule(d.detention_id, actor=principal, new_date=new_date or None,
                        new_start_time=start, session_id=sid)
    print(f"  Rescheduled #{d.detention_id} → #{new.detention_id} on {new.when}.")


def _register(principal: Principal) -> None:
    day = _prompt(f"  Date [{DT._today().isoformat()}]: ") or DT._today().isoformat()
    t = _pick("Type (Enter = all)", DT.DETENTION_TYPES)
    rows = DT.daily_register(day, detention_type=t)
    _table(rows)
    _take_register(rows, principal)


def _take_register(rows: list[DT.Detention], principal: Principal) -> None:
    todo = [r for r in rows if r.status == "Scheduled"]
    if not todo or not _yes("\n  Take the register now?"):
        return
    marks: dict[int, str] = {}
    for r in todo:
        v = _prompt(f"  {r.pupil_name[:30]:<30} A)ttended M)issed E)xcused Enter=skip: ").lower()
        st = {"a": "Attended", "m": "Missed", "e": "Excused"}.get(v[:1])
        if st:
            marks[r.detention_id] = st
    if marks:
        DT.mark_register(marks, actor=principal)
        print(f"  Recorded {len(marks)}.")
        missed = [i for i, s in marks.items() if s == "Missed"]
        if missed and _yes("  E-mail the families of those who missed?"):
            _send_notice(missed, principal, "")


def _pupil_summary(_principal: Principal) -> None:
    p = _pupil()
    if p is None:
        return
    s = DT.pupil_summary(p.pupil_id, academic_year=DT.current_year())
    print(f"\n  {p.display_name} ({p.admission_no}) - {DT.current_year()}")
    print(f"  Total: {s['total']}")
    print(f"  Attended: {s['attended']}    Missed: {s['missed']}    Excused: {s['excused']}"
          f"    Scheduled: {s['scheduled']}")
    print(f"  Minutes served: {s['minutes_served']}")
    for r in s["upcoming"]:
        print(f"    coming up: {r.when} {r.detention_type} - {r.reason[:50]}")


def _summary(_principal: Principal) -> None:
    y = _prompt("  Year (Enter = all): ")
    s = DT.cohort_summary(year_group=y or None, academic_year=DT.current_year())
    print(f"\n  Total: {s['total']} ({s['pupils']} pupils)")
    print(f"  Attended: {s['attended']}   Missed: {s['missed']}   "
          f"Minutes served: {s['minutes_served']}"
          + (f"   Attendance {s['attendance_pct']}%" if s["attendance_pct"] is not None
             else ""))
    print("  By type:   " + ", ".join(f"{k} {v}" for k, v in s["by_type"].items()))
    print("  By status: " + ", ".join(f"{k} {v}" for k, v in s["by_status"].items()))


def _delete(principal: Principal) -> None:
    d = _detention()
    if d is None:
        return
    if not _yes(f"  Delete #{d.detention_id} ({d.pupil_name}, {d.detention_date})? Others can "
                "set it to Cancelled instead."):
        return
    DT.delete(d.detention_id, actor=principal)
    print("  Deleted.")


# ── New options ──────────────────────────────────────────────────────

def _new_many(principal: Principal) -> None:
    form = _prompt("  Form (e.g. 10A): ").upper()
    pupils = P.list_pupils(form_group=form) if form else []
    if not pupils:
        print("  No pupils on roll in that form.")
        return
    for i, p in enumerate(pupils, 1):
        print(f"    {i:>2}) {p.display_name} ({p.admission_no})")
    picked = _prompt("  Numbers, comma separated: ")
    ids = [pupils[int(x) - 1].pupil_id for x in picked.replace(" ", "").split(",")
           if x.isdigit() and 1 <= int(x) <= len(pupils)]
    if not ids:
        return
    data = _details()
    if not _confirm(data, principal, ids):
        return
    done = DT.set_many(ids, data, actor=principal)
    print(f"  Scheduled {len(done)} detentions.")
    _offer_notice(done, principal)


def _book(principal: Principal) -> None:
    sessions = DT.list_sessions(upcoming=True)
    if not sessions:
        print("  No upcoming sessions (the detentions lead adds them: option 15).")
        return
    _sessions(principal)
    sid = _int("  Session ID: ")
    p = _pupil() if sid else None
    if p is None:
        return
    data = {"pupil_id": p.pupil_id, "session_id": sid,
            "reason": _prompt("  Reason: "),
            "related_entry_id": _prompt("  Behaviour incident ID (blank ok): ")}
    if not _confirm(data, principal):
        return
    d = DT.create(data, actor=principal)
    print(f"  Booked #{d.detention_id} on {d.when}.")
    _offer_notice([d], principal)


def _notice(principal: Principal) -> None:
    raw = _prompt("  Detention IDs, comma separated: ")
    ids = [int(x) for x in raw.replace(" ", "").split(",") if x.isdigit()]
    if ids:
        _send_notice(ids, principal, _prompt("  Extra message (optional): "))


def _sessions(_principal: Principal) -> None:
    rows = DT.list_sessions(upcoming=True)
    if not rows:
        print("  (no upcoming sessions)")
    for s in rows:
        print(f"  {s.session_id:>4}) {s.label:<44} {s.duration_min} min · "
              f"{s.supervisor or 'no supervisor'} · booked {s.booked}"
              + (f"/{s.capacity}" if s.capacity else ""))


def _save_session(principal: Principal) -> None:
    sid = _int("  Session ID to change (Enter = add a new one): ")
    cur = DT.get_session(sid) if sid else None
    data: dict[str, Any] = {}
    for key, label, val in (("session_date", "Date (YYYY-MM-DD)", cur.session_date if cur
                             else ""),
                            ("start_time", "Start time HH:MM", cur.start_time if cur else ""),
                            ("duration_min", "Duration in minutes", cur.duration_min if cur
                             else 60),
                            ("location", "Location", cur.location if cur else ""),
                            ("supervisor", "Supervisor", cur.supervisor if cur else ""),
                            ("capacity", "Capacity (blank = no limit)", cur.capacity if cur
                             else ""),
                            ("notes", "Notes", cur.notes if cur else "")):
        v = _prompt(f"  {label}" + (f" [{val}]" if val not in (None, "") else "") + ": ")
        if v:
            data[key] = v
    t = _pick("Type", DT.DETENTION_TYPES, cur.detention_type if cur else DT.DEFAULT_TYPE)
    if t:
        data["detention_type"] = t
    s = DT.save_session(data, actor=principal, session_id=sid)
    print(f"  Saved session #{s.session_id}: {s.label}")


def _cancel_session(principal: Principal) -> None:
    sid = _int("  Session ID: ")
    if sid and _yes(f"  Cancel session #{sid}?"):
        DT.cancel_session(sid, actor=principal)
        print("  Cancelled.")


def _move(principal: Principal) -> None:
    frm = _int("  Move pupils from session ID: ")
    to = _int("  ...to session ID: ") if frm else None
    if to:
        print(f"  Moved {DT.move_session(frm, to, actor=principal)} pupil(s).")


def _session_register(principal: Principal) -> None:
    sid = _int("  Session ID: ")
    if not sid:
        return
    s = DT.get_session(sid)
    print(f"\n  {s.label}")
    rows = DT.session_register(sid)
    _table(rows)
    _take_register(rows, principal)


def _follow_up(principal: Principal) -> None:
    rows = DT.missed_to_follow_up()
    print("\n  Missed, not yet rescheduled or excused:")
    _table(rows)
    print(f"\n  Missed {DT.MISSED_CONCERN}+ this term:")
    for c in DT.concerns():
        print(f"    {c['pupil_name']} ({c['admission_no']}) Year {c['year_group']}: "
              f"{c['missed']}")
    if rows and _yes("\n  Reschedule one now?"):
        _reschedule(principal)


def _reports(_principal: Principal) -> None:
    by = _pick("Group by", ("type", "reason", "staff", "weekday", "year"), "type") or "type"
    print(f"\n  {'Group':<26} {'Total':>6} {'Attended':>9} {'Missed':>7} {'Minutes':>8} "
          f"{'Pupils':>7}")
    for g in DT.analysis(by=by, academic_year=DT.current_year()):
        print(f"  {g['group'][:26]:<26} {g['total']:>6} {g['attended']:>9} {g['missed']:>7} "
              f"{g['minutes']:>8} {g['pupils']:>7}")


def _history(_principal: Principal) -> None:
    d = _detention()
    if d is None:
        return
    for h in DT.history(d.detention_id) or []:
        print(f"  {h['at']}  {h['actor']:<12} {h['action']:<11} "
              + ", ".join(f"{k}={v}" for k, v in h["detail"].items()))


def _export(principal: Principal) -> None:
    path = _prompt("  Save CSV to (e.g. detentions.csv): ")
    if path:
        print(f"  Exported {DT.export_csv(path, actor=principal)} detention(s).")


_OPTIONS = {"1": _new, "2": _list, "3": _view, "4": _edit, "5": _set_status,
            "6": _reschedule, "7": _register, "8": _pupil_summary, "9": _summary,
            "10": _delete, "11": _new_many, "12": _book, "13": _notice, "14": _sessions,
            "15": _save_session, "16": _cancel_session, "17": _move, "18": _session_register,
            "19": _follow_up, "20": _reports, "21": _history, "22": _export}


def menu(principal: Principal) -> None:
    while True:
        activity_log.record("detentions.view")
        print("\n  ── Detentions ──")
        print("    1) Schedule detention\n    2) List detentions\n    3) View detention"
              "\n    4) Edit detention\n    5) Mark attended / missed / excused"
              "\n    6) Reschedule\n    7) Daily register\n    8) Pupil summary"
              "\n    9) Cohort summary\n   10) Delete detention")
        print("  More")
        print("   11) Schedule for several pupils\n   12) Book into a session"
              "\n   13) Notice home\n   14) Sessions\n   15) Add / edit session"
              "\n   16) Cancel session\n   17) Move pupils to another session"
              "\n   18) Session register\n   19) Missed to follow up\n   20) Reports"
              "\n   21) History\n   22) Export CSV")
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
