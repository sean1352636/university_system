"""Suspensions & exclusions in the terminal.

The old Disciplinary menu keeps its options in place: 1 New case, 2 List
cases, 3 View case + events, 4 Edit case, 5 Set status, 6 Delete case,
7 Add event, 8 Delete event, 9 Cohort summary. New: 10 Steps and deadlines,
11 Due across the school, 12 Out of school today, 13 Notice home,
14 Family told another way, 15 Governors / local authority told,
16 Governors' decision, 17 Independent review, 18 Mark the registers,
19 Take off roll, 20 Withdraw case, 21 Pupil summary, 22 Reports,
23 History, 24 Export CSV. Rules live in :mod:`modules.behaviour.domain.exclusions`.
"""

from __future__ import annotations

from typing import Any

from education_system.systems.secondary.modules.behaviour.domain import exclusions as EX
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.cli.prompts import prompts
from education_system.systems.secondary.ui.cli.prompts.prompts import pause as _pause
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt
from education_system.systems.secondary.ui.cli.prompts.prompts import yes as _yes

_ERRORS = (EX.ValidationError, EX.PermissionDenied, EX.NotFound)
_problem = prompts.problem
_int = prompts.ask_int
_pick = prompts.pick


def _table(rows: list[EX.Case]) -> None:
    if not rows:
        print("  (no cases)")
        return
    print(f"  {'ID':<4} {'Start':<10} {'Pupil':<24} {'Yr':<3} {'Type':<22} {'Sev':<8} "
          f"{'Days':<4} {'Status':<10} Reason")
    for c in rows:
        print(f"  {c.case_id:<4} {c.start_date:<10} {c.pupil_name[:24]:<24} {c.pupil_year:<3} "
              f"{c.case_type[:22]:<22} {c.severity:<8} "
              f"{(str(c.days) if c.days is not None else '-'):<4} {c.status:<10} "
              f"{c.reason[:30]}")


def _ask(label: str, cur: Any) -> str:
    return _prompt(f"  {label}" + (f" [{cur}]" if cur not in (None, "") else "") + ": ")


def _details(current: EX.Case | None = None) -> dict[str, Any]:
    """The old questions; Enter keeps the current value (or the default)."""
    out: dict[str, Any] = {}
    t = _pick("Type", EX.CASE_TYPES, current.case_type if current else EX.DEFAULT_TYPE)
    if t:
        out["case_type"] = t
    s = _pick("Severity", EX.SEVERITIES, current.severity if current else EX.DEFAULT_SEVERITY)
    if s:
        out["severity"] = s
    for key, label in (("incident_date", "Incident date (YYYY-MM-DD)"),
                       ("start_date", "Start date (YYYY-MM-DD)"),
                       ("end_date", "End date (last day out; blank for permanent)"),
                       ("days", "Days (blank = count school days)"),
                       ("reason", "Reason"), ("decision_maker", "Decision maker")):
        v = _ask(label, getattr(current, key) if current else "")
        if v:
            out[key] = v
    if (out.get("case_type") or (current.case_type if current else "")) in EX.FORMAL:
        cat = _pick("Reason category", EX.REASON_CATEGORIES,
                    current.reason_category if current else None)
        if cat:
            out["reason_category"] = cat
    for key, label in (("return_date", "Return date"), ("provision_from",
                                                        "Education from (date, day 6+)"),
                       ("provision_details", "Where / what education"),
                       ("reintegration_date", "Reintegration meeting date"),
                       ("related_entry_id", "Behaviour incident ID (blank ok)"),
                       ("notes", "Notes")):
        v = _ask(label, getattr(current, key) if current else "")
        if v:
            out[key] = v
    return out


def _case() -> EX.Case | None:
    cid = _int("  Case ID: ")
    return EX.get(cid) if cid else None


def _warn(data: dict[str, Any], principal: Principal, case_id: int | None = None) -> bool:
    try:
        warnings = EX.check(data, actor=principal, case_id=case_id)
    except _ERRORS:
        return True
    for w in warnings:
        print(f"  ! {w}")
    return not warnings or _yes("  Save anyway?")


def _new(principal: Principal) -> None:
    ref = _prompt("  Pupil ID / admission no.: ")
    data = {"pupil_id": ref, **_details()}
    if not _warn(data, principal):
        return
    c = EX.create_case(data, actor=principal)
    print(f"  Created case #{c.case_id}: {c.case_type}, {c.period}"
          + (f", {c.days} school day(s)" if c.days is not None else ""))
    if c.is_formal and _yes("  E-mail the notice to the family now?"):
        _send(principal, c)


def _list(_principal: Principal) -> None:
    year = _prompt("  Year group (blank = all): ")
    ctype = _pick("Type (blank = all)", EX.CASE_TYPES)
    status = _pick("Status (blank = all)", EX.CASE_STATUSES)
    _table(EX.list_cases(year_group=year or None, case_type=ctype or None,
                         status=status or None))


def _show(c: EX.Case) -> None:
    print(f"\n  Case #{c.case_id} - {c.pupil_name} ({c.admission_no}), Year {c.pupil_year}")
    for label, v in (("Type", c.case_type), ("Severity", c.severity),
                     ("Incident", c.incident_date), ("Period", c.period),
                     ("Days", c.days), ("Reason", c.reason), ("Category", c.reason_category),
                     ("Decided by", c.decision_maker), ("Status", c.status),
                     ("Appeal decision", c.appeal_decision), ("Return", c.return_date),
                     ("Family told", c.parents_notified_at),
                     ("Governors told", c.governors_notified_at),
                     ("LA told", c.la_notified_at), ("Education from", c.provision_from),
                     ("Reintegration", c.reintegration_date),
                     ("Governors' decision", c.governors_decision),
                     ("Review", c.review_outcome or c.review_requested_date),
                     ("Off roll", c.off_roll_date), ("Notes", c.notes)):
        if v not in (None, ""):
            print(f"    {label + ':':<20} {v}")


def _events(c: EX.Case) -> None:
    ev = EX.list_events(c.case_id)
    print("\n  Events:" if ev else "\n  (no events)")
    for e in ev:
        print(f"    #{e.event_id:<4} {e.event_date} {e.event_type:<20} "
              f"{(e.participants or '')[:20]:<20} {e.summary[:50]}")


def _view(_principal: Principal) -> None:
    c = _case()
    if c:
        _show(c)
        _events(c)


def _edit(principal: Principal) -> None:
    c = _case()
    if c is None:
        return
    _show(c)
    changes = _details(c)
    if not changes:
        print("  Nothing changed.")
        return
    if not _warn(changes, principal, c.case_id):
        return
    EX.update_case(c.case_id, changes, actor=principal)
    print("  Saved.")


def _set_status(principal: Principal) -> None:
    c = _case()
    if c is None:
        return
    st = _pick("Status", EX.CASE_STATUSES, c.status)
    appeal = _ask("Appeal decision (if Appealed/Overturned)", c.appeal_decision) \
        if st in ("Appealed", "Overturned") else None
    EX.set_status(c.case_id, st or c.status, actor=principal, appeal_decision=appeal)
    print("  Status saved.")


def _delete(principal: Principal) -> None:
    c = _case()
    if c and _yes(f"  Delete case #{c.case_id} and its events?"):
        EX.delete_case(c.case_id, actor=principal)
        print("  Deleted.")


def _add_event(principal: Principal) -> None:
    c = _case()
    if c is None:
        return
    data: dict[str, Any] = {"case_id": c.case_id,
                            "event_type": _pick("Event type", EX.EVENT_TYPES,
                                                EX.DEFAULT_EVENT_TYPE)}
    for key, label in (("event_date", "Date (blank = today)"), ("participants", "Participants"),
                       ("summary", "Summary"), ("outcome", "Outcome"),
                       ("follow_up", "Follow-up"), ("notes", "Notes")):
        data[key] = _prompt(f"  {label}: ")
    e = EX.add_event(data, actor=principal)
    print(f"  Added event #{e.event_id}.")


def _delete_event(principal: Principal) -> None:
    eid = _int("  Event ID: ")
    if eid and _yes(f"  Delete event #{eid}?"):
        EX.delete_event(eid, actor=principal)
        print("  Deleted.")


def _summary(_principal: Principal) -> None:
    year = _prompt("  Year group (blank = all): ")
    s = EX.cohort_summary(year_group=year or None)
    print(f"\n  Total: {s['total']}   Open: {s['open']}   Suspensions: {s['suspensions']}   "
          f"Permanent: {s['permanent']}   Pupils: {s['pupils']}   Days: {s['total_days']}")
    for key in ("by_status", "by_type", "by_severity"):
        print(f"  {key[3:].title()}: " + ", ".join(f"{k} {v}" for k, v in s[key].items()))


def _steps(_principal: Principal) -> None:
    c = _case()
    if c is None:
        return
    rows = EX.deadlines(c)
    if not rows:
        print("  No statutory steps for this case.")
    for d in rows:
        mark = "done " + d["done"][:10] if d["done"] else ("OVERDUE" if d["overdue"] else "due")
        print(f"  {d['step']:<48} {d['due'] or '':<10}  {mark}")
        if d["note"]:
            print(f"      {d['note']}")


def _due(_principal: Principal) -> None:
    rows = EX.due()
    if not rows:
        print("  Nothing outstanding.")
    for c, d in rows:
        print(f"  {d['due'] or '':<10} {'OVERDUE' if d['overdue'] else '':<8} #{c.case_id:<4} "
              f"{c.pupil_name[:22]:<22} {d['step']}")
    ready = EX.ready_for_off_roll()
    if ready:
        print("\n  Ready to take off roll: " + ", ".join(f"#{c.case_id} {c.pupil_name}"
                                                       for c in ready))


def _out_today(_principal: Principal) -> None:
    _table(EX.out_on())


def _send(principal: Principal, c: EX.Case) -> None:
    from education_system.systems.secondary.modules.communication.domain import email_outbox as E
    res = EX.notify_parents(c.case_id, actor=principal, note=_prompt("  Extra note (blank ok): "))
    if not res["emails"]:
        print("  No contact with parental responsibility has an e-mail address - tell the "
              "family another way (option 14).")
        return
    print(f"  Notice saved for {res['emails']} contact(s).")
    try:
        E.deliver(res["message_id"], principal=principal)
        print("  Sent.")
    except Exception as e:  # noqa: BLE001 - the notice stays in the outbox
        print(f"  Saved in the outbox; not sent yet ({e}).")


def _notice(principal: Principal) -> None:
    c = _case()
    if c:
        _send(principal, c)


def _told(principal: Principal) -> None:
    c = _case()
    if c is None:
        return
    how = _pick("How", ("Phone call", "Letter sent", "Meeting"), "Phone call")
    EX.record_parents_told(c.case_id, actor=principal, how=how or "Phone call",
                           day=_prompt("  Date (blank = today): ") or None)
    print("  Recorded.")


def _notified(principal: Principal) -> None:
    c = _case()
    if c is None:
        return
    who = _pick("Who was told", ("governors", "la"), "la")
    EX.record_notified(c.case_id, who or "la", actor=principal,
                       day=_prompt("  Date (blank = today): ") or None)
    print("  Recorded.")


def _governors(principal: Principal) -> None:
    c = _case()
    if c is None:
        return
    dec = _pick("Decision", EX.GOVERNOR_DECISIONS)
    c = EX.record_governors(c.case_id, decision=dec or "", actor=principal,
                            meeting_date=_prompt("  Meeting date (blank = today): ") or None,
                            note=_prompt("  Note (blank ok): "))
    print(f"  Recorded. Status: {c.status}.")
    due = EX.review_deadline(c)
    if due:
        print(f"  The family can ask for an independent review until {due}.")


def _review(principal: Principal) -> None:
    c = _case()
    if c is None:
        return
    req = _prompt("  Date the review was asked for (blank = today / as recorded): ")
    out = _pick("Outcome (blank = not heard yet)", EX.REVIEW_OUTCOMES)
    c = EX.record_review(c.case_id, actor=principal, requested_date=req or None,
                         outcome=out or None,
                         review_date=(_prompt("  Panel date: ") or None) if out else None)
    print(f"  Recorded. Status: {c.status}.")


def _attendance(principal: Principal) -> None:
    c = _case()
    if c:
        r = EX.mark_attendance(c.case_id, actor=principal)
        print(f"  Marked {r['saved']} session(s); kept {r['skipped']} already marked.")


def _off_roll(principal: Principal) -> None:
    c = _case()
    if c is None:
        return
    for p in EX.off_roll_problems(c):
        print(f"  • {p}")
    if not EX.off_roll_problems(c) and _yes(f"  Take {c.pupil_name} off roll?"):
        EX.remove_from_roll(c.case_id, actor=principal,
                            leaving_date=_prompt("  Leaving date (blank = today): ") or None)
        print("  Off roll (Enrolment & Leavers has the leaving record).")


def _withdraw(principal: Principal) -> None:
    c = _case()
    if c and _yes(f"  Withdraw case #{c.case_id}?"):
        EX.withdraw(c.case_id, actor=principal, reason=_prompt("  Why: "))
        print("  Withdrawn.")


def _pupil_summary(_principal: Principal) -> None:
    p = EX._pupil(_prompt("  Pupil ID / admission no.: "))
    if p is None:
        print("  No such pupil.")
        return
    s = EX.case_summary(p.pupil_id)
    print(f"\n  {p.display_name}: {s['suspensions']} suspension(s) this year, "
          f"{s['suspension_days']} school day(s), {s['days_left']} left of "
          f"{EX.MAX_SUSPENSION_DAYS}")
    _table(s["cases"])


def _reports(_principal: Principal) -> None:
    by = _pick("Group by", ("type", "reason", "year", "severity", "month"), "type") or "type"
    print(f"\n  {'Group':<50} {'Cases':>6} {'Days':>6} {'Pupils':>7}")
    for g in EX.analysis(by=by, academic_year=EX.current_year()):
        print(f"  {g['group'][:50]:<50} {g['cases']:>6} {g['days']:>6} {g['pupils']:>7}")


def _history(_principal: Principal) -> None:
    c = _case()
    if c is None:
        return
    for h in EX.history(c.case_id):
        print(f"  {h['at']}  {h['actor']:<12} {h['action']:<12} "
              + ", ".join(f"{k}={v}" for k, v in h["detail"].items()))


def _export(principal: Principal) -> None:
    path = _prompt("  Save CSV to (e.g. exclusions.csv): ")
    if path:
        print(f"  Exported {EX.export_csv(path, actor=principal)} case(s).")


_OPTIONS = {"1": _new, "2": _list, "3": _view, "4": _edit, "5": _set_status, "6": _delete,
            "7": _add_event, "8": _delete_event, "9": _summary, "10": _steps, "11": _due,
            "12": _out_today, "13": _notice, "14": _told, "15": _notified, "16": _governors,
            "17": _review, "18": _attendance, "19": _off_roll, "20": _withdraw,
            "21": _pupil_summary, "22": _reports, "23": _history, "24": _export}


def menu(principal: Principal) -> None:
    while True:
        activity_log.record("exclusions.view")
        print("\n  ── Suspensions & Exclusions ──")
        print("    1) New case\n    2) List cases\n    3) View case + events\n    4) Edit case"
              "\n    5) Set status\n    6) Delete case\n    7) Add event\n    8) Delete event"
              "\n    9) Cohort summary")
        print("  More")
        print("   10) Steps and deadlines\n   11) Due across the school\n   12) Out of school "
              "today\n   13) Notice home\n   14) Family told another way"
              "\n   15) Governors / local authority told\n   16) Governors' decision"
              "\n   17) Independent review\n   18) Mark the registers\n   19) Take off roll"
              "\n   20) Withdraw case\n   21) Pupil summary\n   22) Reports\n   23) History"
              "\n   24) Export CSV")
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
