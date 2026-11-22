"""Wellbeing in the terminal.

The old menu keeps its options in place: 1 Log check-in, 2 List check-ins,
3 View check-in, 4 Edit check-in, 5 Set status, 6 Pupil summary, 7 Cohort
summary, 8 Pupils with low ratings, 9 Delete check-in. New: 10 Caseload,
11 Follow-ups, 12 New referral, 13 List referrals, 14 Update referral,
15 Referrals by service, 16 New support plan, 17 List support plans,
18 Review support plan, 19 Surveys, 20 New / change survey, 21 Survey
results, 22 Trend, 23 History, 24 Export CSV. Rules live in
:mod:`modules.wellbeing.domain.wellbeing`.
"""

from __future__ import annotations

from typing import Any

from education_system.systems.secondary.modules.wellbeing.domain import wellbeing as WB
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.cli.prompts import prompts
from education_system.systems.secondary.ui.cli.prompts.prompts import pause as _pause
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt
from education_system.systems.secondary.ui.cli.prompts.prompts import yes as _yes

_ERRORS = (WB.ValidationError, WB.PermissionDenied, WB.NotFound)
_problem = prompts.problem
_int = prompts.ask_int
_pick = prompts.pick
BANNER = ("  Worried a pupil is at risk of harm? Use 'Report a Safeguarding Concern' - don't "
          "only record it here.")


def _r(v: Any) -> str:
    return "-" if v is None else str(v)


def _table(rows: list[WB.CheckIn]) -> None:
    if not rows:
        print("  (no check-ins)")
        return
    print(f"  {'ID':<5} {'Date':<10} {'Pupil':<24} {'Yr':<3} {'Source':<16} {'M':<2} {'C':<2} "
          f"{'N':<2} {'Avg':<5} {'Act':<4} Status")
    for c in rows:
        print(f"  {c.checkin_id:<5} {c.checkin_date:<10} {c.pupil_name[:24]:<24} "
              f"{c.pupil_year:<3} {c.source[:16]:<16} {_r(c.mood_rating):<2} "
              f"{_r(c.confidence_rating):<2} {_r(c.connection_rating):<2} "
              f"{_r(c.average_rating):<5} {'yes' if c.action_needed else '':<4} {c.status}"
              + ("  !SAFEGUARDING" if c.safeguarding_flag else ""))


def _ask(label: str, cur: Any) -> str:
    return _prompt(f"  {label}" + (f" [{cur}]" if cur not in (None, "") else "") + ": ")


def _details(cur: WB.CheckIn | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    src = _pick("Source", WB.CHECKIN_SOURCES, cur.source if cur else WB.DEFAULT_SOURCE)
    if src:
        out["source"] = src
    for key, label in (("checkin_date", "Date (blank = today)"),
                       ("mood_rating", "Mood (1-5)"), ("confidence_rating", "Confidence (1-5)"),
                       ("connection_rating", "Connection (1-5)"), ("stressors", "Stressors"),
                       ("supports", "Supports")):
        v = _ask(label, getattr(cur, key) if cur else "")
        if v:
            out[key] = v
    if _yes("  Action needed?"):
        out["action_needed"] = True
        out["action_summary"] = _ask("Action summary", cur.action_summary if cur else "")
    for key, label in (("follow_up_date", "Follow-up date"), ("follow_up_with",
                                                             "Follow-up with"),
                       ("recorded_by", "Recorded by (blank = you)"), ("notes", "Notes")):
        v = _ask(label, getattr(cur, key) if cur else "")
        if v:
            out[key] = v
    for w in WB.check_checkin(out):
        print(f"  ! {w}")
    return out


def _checkin() -> WB.CheckIn | None:
    cid = _int("  Check-in ID: ")
    return WB.get_checkin(cid) if cid else None


def _log(principal: Principal) -> None:
    print(BANNER)
    data = {"pupil_id": _prompt("  Pupil ID / admission no.: "), **_details()}
    c = WB.log_checkin(data, actor=principal)
    print(f"  Logged check-in #{c.checkin_id}.")
    if c.safeguarding_flag:
        print(f"  ! {WB.SAFEGUARDING_ADVICE}")


def _list(principal: Principal) -> None:
    year = _prompt("  Year group (blank = all): ")
    ref = _prompt("  Pupil (blank = all): ")
    p = WB._pupil(ref) if ref else None
    status = _pick("Status (blank = all)", WB.CHECKIN_STATUSES)
    _table(WB.list_checkins(actor=principal, year_group=year or None,
                            pupil_id=(p.pupil_id if p else -1) if ref else None,
                            status=status or None, action_only=_yes("  Action only?")))


def _show(c: WB.CheckIn) -> None:
    print(f"\n  ── Check-in #{c.checkin_id} ──")
    if c.safeguarding_flag:
        print(f"  ! {WB.SAFEGUARDING_ADVICE}")
    for label, v in (("Pupil", f"{c.pupil_name} ({c.admission_no}), Year {c.pupil_year}"),
                     ("Date", c.checkin_date), ("Source", c.source), ("Mood", c.mood_rating),
                     ("Confidence", c.confidence_rating), ("Connection", c.connection_rating),
                     ("Average", c.average_rating), ("Stressors", c.stressors),
                     ("Supports", c.supports),
                     ("Action", c.action_summary if c.action_needed else None),
                     ("Status", c.status), ("Follow-up", c.follow_up_date),
                     ("With", c.follow_up_with), ("Recorded by", c.recorded_by),
                     ("Notes", c.notes)):
        if v not in (None, ""):
            print(f"  {label + ':':<13} {v}")


def _view(_principal: Principal) -> None:
    c = _checkin()
    if c:
        _show(c)


def _edit(principal: Principal) -> None:
    c = _checkin()
    if c is None:
        return
    _show(c)
    changes = _details(c)
    if not changes:
        print("  Nothing changed.")
        return
    WB.update(c.checkin_id, changes, actor=principal)
    print("  Saved.")


def _status(principal: Principal) -> None:
    c = _checkin()
    if c:
        st = _pick("Status", WB.CHECKIN_STATUSES, c.status)
        print(f"  Status now: {WB.set_status(c.checkin_id, st or c.status, actor=principal).status}")


def _pupil_summary(principal: Principal) -> None:
    p = WB._pupil(_prompt("  Pupil ID / admission no.: "))
    if p is None:
        print("  No such pupil.")
        return
    s = WB.pupil_summary(p.pupil_id, actor=principal)
    print(f"\n  {p.display_name}: {s['count']} check-in(s), action needed {s['action_needed']}")
    print(f"  Averages: mood {_r(s['avg_mood'])}, confidence {_r(s['avg_confidence'])}, "
          f"connection {_r(s['avg_connection'])}")
    print("  By status: " + ", ".join(f"{k} {v}" for k, v in s["by_status"].items()))
    for r in s["referrals"] if WB.can_see_referrals(principal, p.year_group) else []:
        print(f"  Referral #{r.referral_id}: {r.service} ({r.status})")
    for w in s["plans"]:
        print(f"  Plan #{w.plan_id}: {w.status}, review {w.review_date}")


def _cohort(_principal: Principal) -> None:
    s = WB.cohort_summary(year_group=_prompt("  Year group (blank = all): ") or None)
    print(f"\n  Total: {s['total']}   Pupils: {s['pupils']}   Action needed: "
          f"{s['action_needed']}   Flagged: {s['flagged']}")
    print(f"  Averages: mood {_r(s['avg_mood'])}, confidence {_r(s['avg_confidence'])}, "
          f"connection {_r(s['avg_connection'])}")
    print("  By status: " + ", ".join(f"{k} {v}" for k, v in s["by_status"].items()))
    print("  By source: " + ", ".join(f"{k} {v}" for k, v in s["by_source"].items()))
    print(f"  Open referrals: {s['open_referrals']}   Active plans: {s['active_plans']}")


def _low(principal: Principal) -> None:
    t = _int("  Threshold (1-5) [2]: ") or WB.LOW_THRESHOLD
    got = WB.low_wellbeing(threshold=t, actor=principal)
    _table([rows[0] for rows in got.values()])


def _delete(principal: Principal) -> None:
    c = _checkin()
    if c and _yes(f"  Delete check-in #{c.checkin_id}?"):
        WB.delete(c.checkin_id, actor=principal)
        print("  Deleted.")


def _caseload(principal: Principal) -> None:
    rows = WB.caseload(actor=principal, key_adult=_prompt("  Key adult (blank = all): ") or None)
    if not rows:
        print("  Nobody on the caseload.")
    for e in rows:
        print(f"  {e['pupil_name'][:24]:<24} Y{e['year']:<3} latest {_r(e['latest']):<5} "
              f"{e['trend']:<6} follow-up {e['follow_up'] or '-':<10} "
              f"{', '.join(e['referrals']) or '-':<22} plan "
              f"{e['plan'].review_date if e['plan'] else '-'}"
              + ("  !SAFEGUARDING" if e["flagged"] else ""))


def _follow_ups(principal: Principal) -> None:
    rows = WB.follow_ups(actor=principal)
    if not rows:
        print("  No follow-ups.")
    for c in rows:
        print(f"  {c.follow_up_date} {'OVERDUE' if c.follow_up_overdue else '':<8} "
              f"#{c.checkin_id:<4} {c.pupil_name[:24]:<24} with {c.follow_up_with or '-'}")


def _new_referral(principal: Principal) -> None:
    data: dict[str, Any] = {"pupil_id": _prompt("  Pupil ID / admission no.: "),
                            "service": _pick("Service", WB.SERVICES),
                            "reason": _prompt("  Reason: "),
                            "urgency": _pick("Urgency", WB.URGENCIES, "Routine"),
                            "consent": _pick("Consent", WB.CONSENTS, WB.CONSENTS[0]),
                            "contact_name": _prompt("  Service contact (blank ok): "),
                            "checkin_id": _prompt("  From check-in ID (blank ok): ")}
    if WB.safeguarding_signs(data["reason"]):
        print(f"  ! {WB.SAFEGUARDING_ADVICE}")
    r = WB.create_referral(data, actor=principal)
    print(f"  Referral #{r.referral_id} to {r.service} saved.")


def _list_referrals(principal: Principal) -> None:
    rows = WB.list_referrals(actor=principal, open_only=_yes("  Open only?"))
    if not rows:
        print("  (no referrals)")
    for r in rows:
        print(f"  #{r.referral_id:<4} {r.referral_date} {r.pupil_name[:22]:<22} "
              f"{r.service[:24]:<24} {r.urgency:<9} {r.status:<12} {r.waiting_days:>3}d "
              f"{r.outcome or ''}")


def _update_referral(principal: Principal) -> None:
    rid = _int("  Referral ID: ")
    if not rid:
        return
    r = WB.get_referral(rid)
    changes: dict[str, Any] = {}
    st = _pick("Status", WB.REFERRAL_STATUSES, r.status)
    if st:
        changes["status"] = st
    for key, label in (("accepted_date", "Accepted on"),
                       ("first_appointment", "First appointment"),
                       ("closed_date", "Closed on"), ("outcome_notes", "Outcome notes")):
        v = _ask(label, getattr(r, key))
        if v:
            changes[key] = v
    if (st or r.status) in WB.REFERRAL_CLOSED:
        out = _pick("Outcome", WB.REFERRAL_OUTCOMES, r.outcome)
        if out:
            changes["outcome"] = out
    r = WB.update_referral(rid, changes, actor=principal)
    print(f"  Saved: {r.status}.")


def _referral_report(_principal: Principal) -> None:
    for g in WB.referral_report():
        print(f"  {g['service']:<28} {g['referrals']:>4} referred, {g['open']:>3} open, "
              f"avg wait {_r(g['avg_wait'])} days  "
              + ", ".join(f"{k} {v}" for k, v in g["outcomes"].items()))


def _new_plan(principal: Principal) -> None:
    data = {"pupil_id": _prompt("  Pupil ID / admission no.: ")}
    for key, label in (("need", "Need"), ("strategies", "Strategies (for all staff)"),
                       ("staff_actions", "Staff actions"), ("pupil_actions", "Pupil actions"),
                       ("family_actions", "Family actions"), ("key_adult", "Key adult"),
                       ("review_date", "Review date (blank = 6 weeks)")):
        data[key] = _prompt(f"  {label}: ")
    w = WB.create_plan(data, actor=principal)
    print(f"  Plan #{w.plan_id} saved; review {w.review_date}.")


def _list_plans(principal: Principal) -> None:
    rows = WB.list_plans(actor=principal, status="Active" if _yes("  Active only?") else None)
    if not rows:
        print("  (no plans)")
    for w in rows:
        print(f"  #{w.plan_id:<4} {w.pupil_name[:24]:<24} {w.status:<7} review {w.review_date}"
              f"{' DUE' if w.review_due else '':<5} {w.key_adult or '-':<14} {w.need[:40]}")


def _review_plan(principal: Principal) -> None:
    pid = _int("  Plan ID: ")
    if not pid:
        return
    close = _yes("  Close the plan?")
    w = WB.review_plan(pid, actor=principal, summary=_prompt("  How it's going: "),
                       next_review=None if close else (_prompt("  Next review (blank = 6 "
                                                               "weeks): ") or None),
                       close=close, outcome=_prompt("  Outcome: ") if close else None)
    print(f"  Saved. {w.status}, review {w.review_date}.")


def _surveys(_principal: Principal) -> None:
    for s in WB.list_surveys():
        print(f"  #{s.survey_id:<4} {s.title[:30]:<30} {s.scope:<14} {s.open_date} to "
              f"{s.close_date} {s.status}")


def _save_survey(principal: Principal) -> None:
    sid = _int("  Survey ID to change (blank = new): ")
    data = {k: _prompt(f"  {label}: ") for k, label in (
        ("title", "Title"), ("year_group", "Year group (blank = whole school)"),
        ("form_group", "Form (blank ok)"), ("open_date", "Opens (blank = today)"),
        ("close_date", "Closes (blank = a week later)"))}
    data["status"] = _pick("Status", WB.SURVEY_STATUSES, "Draft")
    s = WB.save_survey({k: v for k, v in data.items() if v} if sid else data, actor=principal,
                       survey_id=sid)
    print(f"  Survey #{s.survey_id} saved ({s.status}).")


def _survey_results(_principal: Principal) -> None:
    sid = _int("  Survey ID: ")
    if not sid:
        return
    r = WB.survey_results(sid)
    print(f"\n  {r['survey'].title}: {r['responses']} of {r['pupils']} answered "
          f"({_r(r['rate'])}%)")
    print(f"  Averages: mood {_r(r['avg_mood'])}, confidence {_r(r['avg_confidence'])}, "
          f"connection {_r(r['avg_connection'])}")
    for c in r["low"]:
        print(f"  Low: {c.pupil_name}")
    print(f"  Not answered: {len(r['missing'])}")


def _trend(_principal: Principal) -> None:
    p = WB._pupil(_prompt("  Pupil ID / admission no.: "))
    if p is None:
        print("  No such pupil.")
        return
    for d, a in WB.trend(p.pupil_id):
        print(f"  {d}  {a:4.2f}  {'#' * int(round(a * 4))}")


def _history(_principal: Principal) -> None:
    p = WB._pupil(_prompt("  Pupil ID / admission no.: "))
    for h in WB.history(pupil_id=p.pupil_id if p else None):
        print(f"  {h['at']}  {h['actor']:<12} {h['kind']:<8} {h['action']:<10} "
              + ", ".join(f"{k}={v}" for k, v in h["detail"].items()))


def _export(principal: Principal) -> None:
    path = _prompt("  Save CSV to (e.g. wellbeing.csv): ")
    if path:
        print(f"  Exported {WB.export_csv(path, actor=principal)} check-in(s).")


_OPTIONS = {"1": _log, "2": _list, "3": _view, "4": _edit, "5": _status, "6": _pupil_summary,
            "7": _cohort, "8": _low, "9": _delete, "10": _caseload, "11": _follow_ups,
            "12": _new_referral, "13": _list_referrals, "14": _update_referral,
            "15": _referral_report, "16": _new_plan, "17": _list_plans, "18": _review_plan,
            "19": _surveys, "20": _save_survey, "21": _survey_results, "22": _trend,
            "23": _history, "24": _export}


def menu(principal: Principal) -> None:
    while True:
        activity_log.record("wellbeing.view")
        print("\n  ── Wellbeing ──")
        print(BANNER)
        print("   1) Log check-in\n   2) List check-ins\n   3) View check-in\n   4) Edit check-in"
              "\n   5) Set status\n   6) Pupil summary\n   7) Cohort summary"
              "\n   8) Pupils with low ratings\n   9) Delete check-in")
        print("  More")
        print("  10) Caseload\n  11) Follow-ups\n  12) New referral\n  13) List referrals"
              "\n  14) Update referral\n  15) Referrals by service\n  16) New support plan"
              "\n  17) List support plans\n  18) Review support plan\n  19) Surveys"
              "\n  20) New / change survey\n  21) Survey results\n  22) Trend\n  23) History"
              "\n  24) Export CSV")
        print("   0) Back")
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
