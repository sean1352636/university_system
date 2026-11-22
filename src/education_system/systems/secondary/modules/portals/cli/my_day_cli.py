"""The staff portal ("My Day") in the terminal. Read from :mod:`modules.portals.domain.my_day`."""

from __future__ import annotations

from education_system.systems.secondary.modules.portals.domain import my_day as MD
from education_system.systems.secondary.core.exceptions import errors
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.ui.cli.prompts.prompts import ask, pick, problem, prompt


def show(principal: Principal) -> None:
    from education_system.systems.secondary.modules.curriculum.domain import timetable as TT
    d = MD.day(principal)
    print(f"\n── My Day · {d['day']:%A %d %B %Y}" + (f" · {d['label']}" if d["label"] else "")
          + " ──")
    times = {p.period: p for p in TT.periods()}
    print("\n  My lessons today:")
    for x, taken in d["lessons"]:
        p = times.get(x.period)
        print(f"    {(p.label if p else 'P' + str(x.period)):<7} {x.group_code:<10} "
              f"{x.subject_name[:20]:<20} {x.room or '':<6} "
              + ("register taken" if taken else "REGISTER NOT TAKEN"))
    if not d["lessons"]:
        print("    none")
    if d["registers"]:
        print("\n  My form:")
        for r in d["registers"]:
            f = r["form"]
            print(f"    {f.year_group}{f.name} {r['session']}: " + (
                "complete" if r["complete"] else f"{r['marked']}/{r['on_roll']} marked"))
    for c in d.get("suspended") or []:
        print(f"    Out today: {c.pupil_name} - {c.case_type.lower()} ({c.period})")
    for b in d.get("trips") or []:
        print(f"    Away on a trip: {b.pupil_name} - {b.trip_title}")
    cv = d["cover"]
    if cv["doing"] or cv["mine"]:
        print("\n  Cover (next 7 days):")
        for c in cv["doing"]:
            print(f"    Covering {c.date} P{c.period} {c.group_code} for {c.absent_name}")
        for c in cv["mine"]:
            print(f"    Your lesson {c.date} P{c.period} {c.group_code}: "
                  f"{c.cover_name or 'not arranged yet'}" + ("" if c.work_set else
                                                             " - set the work"))
    m = d["marking"]
    print("\n  Marking and data to enter:")
    lines = ([f"Homework: {t.title} ({t.for_label}) - {n} to mark" for t, n in m["homework"]]
             + [f"Gradebook: {a.name} ({a.for_label}) - {n} to mark" for a, n in m["gradebook"]]
             + [f"{pt.name}: {r['group'].code} {r['done']}/{r['pupils']}" for pt, r in
                m["points"]]
             + [f"Mock {s.name}: {p.label} - {n} to mark" for s, p, n in m["mocks"]])
    for line in lines or ["nothing waiting"]:
        print("    " + line)
    if d["homework_set"]:
        print("\n  Homework I've set, due soon:")
        for t in d["homework_set"]:
            print(f"    {t.due_date} {t.for_label} {t.subject_code}: {t.title}")
    if d.get("detentions"):
        print(f"\n  Detention to supervise today: {len(d['detentions'])} pupil(s)")
    if d["clubs"]:
        print("\n  My clubs today: " + ", ".join(f"{c.name} {c.time_label}" for c in d["clubs"]))
    if d["events"]:
        print("\n  Events this week:")
        for e in d["events"]:
            print(f"    {e.start_date} {e.title}")
    if d["children"]:
        print("\n  Your children here: " + ", ".join(p.display_name for p in d["children"])
              + " (P on the main menu opens the parent portal)")
    _linked(d)
    _actions(principal, d)


def _linked(d: dict) -> None:
    """The linked areas: safeguarding, absence, announcements, expenses,
    parents' evenings, attendance / wellbeing, SEND and medical."""
    sg = d.get("safeguarding")
    if sg:
        print(f"\n  Safeguarding: {sg['new']} new ({sg['urgent']} urgent), "
              f"{sg['overdue']} overdue")
    ab = d.get("absence") or {}
    if any(ab.values()):
        print("\n  My absence:")
        for r in ab.get("off_now") or []:
            print(f"    {r.absence_type}: {r.dates_label} ({r.status})")
        for q in ab.get("requests") or []:
            print(f"    Request: {q.absence_type} {q.dates_label} - {q.status}")
        for r in ab.get("rtw_due") or []:
            print(f"    Return-to-work meeting still to hold ({r.dates_label})")
    an = d.get("announcements") or {}
    if an.get("active"):
        unread = {a.announcement_id for a in an.get("unread") or []}
        ack = {a.announcement_id for a in an.get("to_acknowledge") or []}
        print("\n  Announcements:")
        for a in an["active"][:6]:
            print(f"    [{a.announcement_id}] " + ("* " if a.announcement_id in unread else "")
                  + a.title + ("  (please acknowledge)" if a.announcement_id in ack else ""))
    ex = d.get("expenses") or {}
    if ex.get("to_approve") or ex.get("to_fix") or ex.get("overspends"):
        print("\n  Expenses and budgets:")
        for c in ex.get("to_approve") or []:
            print(f"    To approve: {c.claim_ref} {c.claimant_name or c.claimant_id} "
                  f"{c.title} {c.total}")
        for c in ex.get("to_fix") or []:
            print(f"    My claim {c.claim_ref} {c.title}: {c.status.lower()}")
        for p, state in ex.get("overspends") or []:
            print(f"    Budget {p.code} {p.description}: {state}")
    for e, t in d.get("parents_evenings") or []:
        print(f"\n  Parents' evening: {e.event_date} {e.name} {e.start_time}-{e.end_time}"
              + (f" room {t.room}" if t.room else ""))
    ps = d.get("pastoral") or {}
    if ps.get("attendance_cases") or ps.get("wellbeing_follow_ups"):
        print("\n  Attendance and wellbeing:")
        for c in ps.get("attendance_cases") or []:
            print(f"    Attendance: {c.pupil_name} - {c.stage}")
        for w in ps.get("wellbeing_follow_ups") or []:
            print(f"    Wellbeing follow-up: {w.pupil_name} (due {w.follow_up_date})")
    nd = d.get("needs") or {}
    if nd.get("send") or nd.get("medical"):
        print("\n  My pupils' needs:")
        for m in nd.get("medical") or []:
            print(f"    {m['pupil_name']}: " + ", ".join(m["conditions"] + m["allergies"]))
        for x in nd.get("send") or []:
            print(f"    {x['pupil_name']} ({x['stage']}) {x['needs']}")
    ld = d.get("leads_due") or {}
    rows = [*(("SEND", x) for x in ld.get("send") or []),
            *(("Medical", x) for x in ld.get("medical") or [])]
    if rows or ld.get("pp_without_activities"):
        print("\n  SEND, medical and pupil premium to do:")
        for area, x in rows[:15]:
            print(f"    {area}: {x['due']} {x['item']}" + (" (OVERDUE)" if x["overdue"] else ""))
        if ld.get("pp_without_activities"):
            print(f"    Pupil premium: {ld['pp_without_activities']} pupil(s) with no "
                  "activity recorded")


def _actions(principal: Principal, d: dict) -> None:
    from education_system.systems.secondary.modules.communication.domain import announcements as AN
    from education_system.systems.secondary.modules.staff.domain import staff_absence as SA
    ack = {a.announcement_id: a for a in (d.get("announcements") or {}).get(
        "to_acknowledge") or []}
    active = {a.announcement_id: a for a in (d.get("announcements") or {}).get("active") or []}
    while True:
        choice = prompt("\n  S report sickness · R request absence · A <id> read an "
                        "announcement · Enter to go back: ").strip().upper()
        if not choice:
            return
        try:
            if choice == "S":
                rec, covers = SA.report_sickness(
                    actor=principal, start_date=ask("First day off (blank = today)") or None,
                    expected_return=ask("Expected back (date, optional)") or None,
                    reason=ask("Reason (optional)") or None)
                print(f"  Recorded {rec.dates_label}; {covers} lesson(s) need cover.")
            elif choice == "R":
                types = [t for t in SA.ABSENCE_TYPES if t not in SA.SICKNESS_TYPES]
                q = SA.request_absence({"absence_type": pick("Type", types, types[0]),
                                        "start_date": ask("First day", required=True),
                                        "end_date": ask("Last day (blank = same day)"),
                                        "reason": ask("Reason")}, actor=principal)
                print(f"  Request sent: {q.absence_type} {q.dates_label}.")
            elif choice.startswith("A") and choice[1:].strip().isdigit():
                aid = int(choice[1:].strip())
                a = active.get(aid)
                if a is None:
                    print("  No such announcement here.")
                    continue
                print(f"\n  {a.title}\n\n{a.body}\n")
                AN.mark_read(aid, principal)
                if aid in ack and prompt("  Type YES to confirm you have read and understood "
                                         "it: ").strip().upper() == "YES":
                    AN.acknowledge(aid, principal)
                    print("  Acknowledged.")
            else:
                print("  Choose S, R or A <id>.")
        except (errors.ValidationError, errors.PermissionDenied, errors.NotFound) as e:
            problem(e)
