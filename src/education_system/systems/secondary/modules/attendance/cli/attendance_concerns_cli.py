"""Attendance concerns in the terminal.

The old menu keeps its options in place: 1 New concern, 2 List concerns,
3 View concern, 4 Edit concern, 5 Set status, 6 Close concern, 7 Cohort
summary, 8 Delete concern. New: 9 Add note, 10 Next stage, 11 Letter home,
12 Review, 13 Refer to the local authority, 14 LA outcome, 15 Children missing
education, 16 Trend, 17 From the registers, 18 Reviews due, 19 Penalty
threshold / CME watch, 20 Dashboard, 21 History, 22 Export CSV, 23 Update %
from the registers. Rules live in :mod:`modules.attendance.domain.attendance_concerns`.
"""

from __future__ import annotations

from typing import Any

from education_system.systems.secondary.modules.attendance.domain import attendance_concerns as AC
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.cli.prompts import prompts
from education_system.systems.secondary.ui.cli.prompts.prompts import pause as _pause
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt
from education_system.systems.secondary.ui.cli.prompts.prompts import yes as _yes

_ERRORS = (AC.ValidationError, AC.PermissionDenied, AC.NotFound)
_problem = prompts.problem
_int = prompts.ask_int
_pick = prompts.pick


def _pct(v: float | None) -> str:
    return f"{v:.1f}" if v is not None else "-"


def _table(rows: list[AC.Concern]) -> None:
    if not rows:
        print("  (no concerns)")
        return
    print(f"  {'ID':<5} {'Pupil':<24} {'Yr':<3} {'AY':<8} {'Type':<20} {'Att%':<6} "
          f"{'Status':<10} {'Review':<10} Stage")
    for c in rows:
        print(f"  {c.concern_id:<5} {c.pupil_name[:24]:<24} {c.pupil_year:<3} "
              f"{c.academic_year:<8} {c.concern_type[:20]:<20} {_pct(c.attendance_pct):<6} "
              f"{c.status:<10} {(c.next_review_date or '-'):<10} {c.stage_no}. {c.stage}"
              + (" CME" if c.cme else ""))


def _ask(label: str, cur: Any) -> str:
    return _prompt(f"  {label}" + (f" [{cur}]" if cur not in (None, "") else "") + ": ")


def _details(cur: AC.Concern | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    t = _pick("Concern type", AC.CONCERN_TYPES, cur.concern_type if cur else AC.DEFAULT_TYPE)
    if t:
        out["concern_type"] = t
    lv = _pick("Level (blank = from attendance)", AC.CONCERN_LEVELS,
               cur.level if cur else None)
    if lv:
        out["level"] = lv
    for key, label in (("attendance_pct", "Attendance % (blank = from registers)"),
                       ("threshold_pct", "Threshold %"), ("target_pct", "Target %"),
                       ("opened_date", "Opened (YYYY-MM-DD)"),
                       ("next_review_date", "Next review (YYYY-MM-DD)"),
                       ("key_worker", "Key worker"), ("intervention", "Intervention"),
                       ("parent_contact", "Parent contact"), ("notes", "Notes")):
        v = _ask(label, getattr(cur, key) if cur else "")
        if v:
            out[key] = v
    return out


def _concern() -> AC.Concern | None:
    cid = _int("  Concern ID: ")
    return AC.get(cid) if cid else None


def _new(principal: Principal) -> None:
    data: dict[str, Any] = {"pupil_id": _prompt("  Pupil ID / admission no.: ")}
    ay = _prompt("  Academic year (e.g. 2025/26, blank = from opened date): ")
    if ay:
        data["academic_year"] = ay
    data.update(_details())
    for w in AC.check(data, actor=principal):
        print(f"  ! {w}")
    c = AC.create(data, actor=principal)
    print(f"  Created concern #{c.concern_id}: {c.pupil_name} - {c.concern_type}, "
          f"{_pct(c.attendance_pct)}%")


def _list(_principal: Principal) -> None:
    ay = _prompt("  Academic year (blank = all): ")
    status = _pick("Status (blank = all)", AC.CONCERN_STATUSES)
    year = _prompt("  Year group (blank = all): ")
    _table(AC.list_concerns(academic_year=ay or None, status=status or None,
                            year_group=year or None,
                            open_only=_yes("  Open only?")))


def _show(c: AC.Concern) -> None:
    print(f"\n  ── Concern #{c.concern_id} ──")
    for label, v in (("Pupil", f"{c.pupil_name} ({c.admission_no}), Year {c.pupil_year}"),
                     ("Year", c.academic_year), ("Type", c.concern_type), ("Level", c.level),
                     ("Attendance", f"{_pct(c.attendance_pct)}%   (threshold "
                                    f"{c.threshold_pct:g}%"
                                    + (f", target {c.target_pct:g}%)" if c.target_pct else ")")),
                     ("Stage", f"{c.stage_no}. {c.stage} ({c.stage_date or '-'})"),
                     ("Opened", c.opened_date), ("Next review", c.next_review_date),
                     ("Closed", c.closed_date), ("Status", c.status),
                     ("Key worker", c.key_worker), ("Intervention", c.intervention),
                     ("Parent ctc", c.parent_contact), ("Meeting", c.meeting_date),
                     ("Support plan", c.support_plan),
                     ("CME", f"yes (LA told {c.cme_reported_date or '-'})" if c.cme else None),
                     ("LA referral", f"{c.la_referral_type} {c.la_referral_date}"
                      if c.la_referral_date else None),
                     ("LA outcome", c.la_outcome), ("Notes", c.notes)):
        if v not in (None, ""):
            print(f"  {label + ':':<14} {v}")
    acts = AC.list_actions(c.concern_id)
    print("\n  Timeline:" if acts else "\n  (no timeline)")
    for a in acts:
        print(f"    #{a.action_id:<4} {a.action_date} {a.action_type:<14} {a.summary[:70]}")


def _view(_principal: Principal) -> None:
    c = _concern()
    if c:
        _show(c)


def _edit(principal: Principal) -> None:
    c = _concern()
    if c is None:
        return
    _show(c)
    changes = _details(c)
    if not changes:
        print("  Nothing changed.")
        return
    AC.update(c.concern_id, changes, actor=principal)
    print(f"  Updated concern #{c.concern_id}.")


def _set_status(principal: Principal) -> None:
    c = _concern()
    if c is None:
        return
    print(f"  Current: {c.status}")
    st = _pick("Status", AC.CONCERN_STATUSES, c.status)
    c = AC.set_status(c.concern_id, st or c.status, actor=principal)
    print(f"  Status now: {c.status}")


def _close(principal: Principal) -> None:
    c = _concern()
    if c is None:
        return
    c = AC.close(c.concern_id, _prompt("  Closed date (YYYY-MM-DD, blank = today): ") or None,
                 actor=principal, reason=_prompt("  Why (blank ok): "))
    print(f"  Closed concern #{c.concern_id} on {c.closed_date}.")


def _summary(_principal: Principal) -> None:
    s = AC.cohort_summary(academic_year=_prompt("  Academic year (blank = all): ") or None)
    print(f"\n  Total: {s['total']}   Open: {s['open']}   Pupils: {s['pupils']}   CME: "
          f"{s['cme']}   LA referrals: {s['referrals']}")
    if s["avg_attendance"] is not None:
        print(f"  Avg attendance: {s['avg_attendance']:.2f}%")
    for key in ("by_status", "by_type", "by_level", "by_stage"):
        print(f"  {key[3:].title() + ':':<10} " + ", ".join(f"{k} {v}"
                                                           for k, v in s[key].items()))


def _delete(principal: Principal) -> None:
    c = _concern()
    if c and _yes(f"  Delete concern #{c.concern_id} ({c.pupil_name})?"):
        AC.delete(c.concern_id, actor=principal)
        print(f"  Deleted concern #{c.concern_id}.")
    elif c:
        print("  Cancelled.")


def _note(principal: Principal) -> None:
    c = _concern()
    if c is None:
        return
    types = AC.ACTION_TYPES if AC.is_editor(principal) else AC.NOTE_TYPES
    a = AC.add_note(c.concern_id, {"action_type": _pick("Type", types, "Note"),
                                   "action_date": _prompt("  Date (blank = today): "),
                                   "summary": _prompt("  Summary: "),
                                   "outcome": _prompt("  Outcome (blank ok): ")},
                    actor=principal)
    print(f"  Added #{a.action_id}.")


def _stage(principal: Principal) -> None:
    c = _concern()
    if c is None:
        return
    later = [s for s in AC.STAGES[c.stage_no:] if s != AC.REFERRAL]
    print(f"  Now at: {c.stage}")
    st = _pick("Move to", later, later[0] if later else None)
    if not st:
        return
    meeting = _prompt("  Meeting date (blank ok): ") if st == AC.MEETING else ""
    plan = _prompt("  Support plan (blank ok): ") if st == AC.MEETING else ""
    c = AC.advance_stage(c.concern_id, st, actor=principal, note=_prompt("  Note (blank ok): "),
                         meeting_date=meeting or None, support_plan=plan,
                         leave_in_term_time=st == AC.NOTICE and _yes("  Leave in term time?"))
    print(f"  Now at: {c.stage} ({c.status}).")


def _letter(principal: Principal) -> None:
    from education_system.systems.secondary.modules.communication.domain import email_outbox as E
    c = _concern()
    if c is None:
        return
    key = _pick("Letter", tuple(AC.LETTERS), "letter_1") or "letter_1"
    meeting = _prompt("  Meeting date (blank ok): ") if key == "meeting" else ""
    res = AC.send_letter(c.concern_id, key, actor=principal,
                         note=_prompt("  Extra message (blank ok): "),
                         meeting_date=meeting or None)
    if not res["emails"]:
        print("  No contact with parental responsibility has an e-mail address - post it and "
              "add a note (option 9).")
        return
    print(f"  Letter saved for {res['emails']} contact(s).")
    try:
        E.deliver(res["message_id"], principal=principal)
        print("  Sent.")
    except Exception as e:  # noqa: BLE001 - the letter stays in the outbox
        print(f"  Saved in the outbox; not sent yet ({e}).")


def _review(principal: Principal) -> None:
    c = _concern()
    if c is None:
        return
    st = _pick("Status (blank = from the target)", AC.CONCERN_STATUSES)
    r = AC.record_review(c.concern_id, actor=principal, summary=_prompt("  Summary: "),
                         status=st or None,
                         next_review_date=_prompt("  Next review (blank = 4 weeks): ") or None)
    print(f"  Since opening: {_pct(r['since'])}%   This year: {_pct(r['year'])}%   "
          f"{'Target met' if r['met'] else 'Below target'}   Status: {r['concern'].status}")


def _refer(principal: Principal) -> None:
    c = _concern()
    if c is None:
        return
    t = AC.penalty_threshold(c.pupil_id)
    print(f"  {t['sessions']} unauthorised session(s) since {t['from']} "
          f"({'threshold met' if t['met'] else 'threshold not met'}).")
    kind = _pick("Referral for", AC.REFERRAL_TYPES, AC.REFERRAL_TYPES[0])
    c = AC.refer_to_la(c.concern_id, kind or "", actor=principal,
                       note=_prompt("  Note (blank ok): "),
                       leave_in_term_time=_yes("  Leave in term time?"))
    print(f"  Referred ({c.la_referral_type}). Status: {c.status}.")


def _la_outcome(principal: Principal) -> None:
    c = _concern()
    if c is None:
        return
    out = _pick("Outcome", AC.LA_OUTCOMES)
    AC.record_la_outcome(c.concern_id, out or "", actor=principal,
                         note=_prompt("  Note (blank ok): "))
    print("  Recorded.")


def _cme(principal: Principal) -> None:
    c = _concern()
    if c is None:
        return
    print(f"  {AC.unexplained_run(c.pupil_id)} consecutive school day(s) of unexplained "
          "absence.")
    flag = _yes("  Flag as a child missing education?")
    c = AC.set_cme(c.concern_id, flag, actor=principal,
                   reported_date=(_prompt("  Local authority told on (blank ok): ") or None)
                   if flag else None, notes=_prompt("  Notes (blank ok): "))
    print(f"  CME: {'yes' if c.cme else 'no'}.")


def _trend(_principal: Principal) -> None:
    p = AC._pupil(_prompt("  Pupil ID / admission no.: "))
    if p is None:
        print("  No such pupil.")
        return
    for w in AC.weekly_trend(p.pupil_id, weeks=16):
        print(f"  w/c {w['week']}  {w['pct']:5.1f}%  {'#' * int(w['pct'] // 5):<20} "
              f"{w['attended']}/{w['possible']}")
    t = AC.penalty_threshold(p.pupil_id)
    print(f"  Unauthorised sessions in {AC.PENALTY_WEEKS} school weeks: {t['sessions']}")


def _candidates(principal: Principal) -> None:
    rows = AC.candidates(year_group=_prompt("  Year group (blank = all): ") or None)
    if not rows:
        print("  No persistent or severe absentees without a case.")
        return
    for i, (p, s) in enumerate(rows, 1):
        print(f"  {i:>3}) {p.display_name[:26]:<26} Y{p.year_group:<3} "
              f"{_pct(s.attendance_pct):>5}%  {s.band}")
    pick = _prompt("  Open cases for (numbers, comma-separated; 'all'; blank = none): ")
    if not pick:
        return
    chosen = rows if pick.lower() == "all" else [
        rows[int(x) - 1] for x in pick.replace(" ", "").split(",")
        if x.isdigit() and 1 <= int(x) <= len(rows)]
    res = AC.open_from_attendance([p.pupil_id for p, _s in chosen], actor=principal)
    print(f"  Opened {len(res['created'])} case(s).")
    for s in res["skipped"]:
        print(f"   • {s}")


def _due(_principal: Principal) -> None:
    rows = AC.due_reviews()
    if not rows:
        print("  No reviews due.")
    for c in rows:
        print(f"  {(c.next_review_date or '-'):<10} {'OVERDUE' if c.review_overdue else '':<8}"
              f" #{c.concern_id:<4} {c.pupil_name[:24]:<24} {c.stage}")


def _watch(_principal: Principal) -> None:
    print("\n  Penalty-notice threshold met:")
    for c, t in AC.penalty_watch() or []:
        print(f"    #{c.concern_id:<4} {c.pupil_name[:24]:<24} {t['sessions']} sessions since "
              f"{t['from']}  ({c.stage})")
    print("\n  Possibly missing education:")
    for p, n in AC.cme_watch():
        print(f"    {p.display_name[:28]:<28} {n} school days unexplained")


def _dashboard(_principal: Principal) -> None:
    d = AC.dashboard()
    by = d["by_form"] if _pick("By", ("year", "form"), "year") == "form" else d["by_year"]
    print(f"\n  {'Group':<12} {'Pupils':>6} {'Att%':>6} {'PA':>4} {'SA':>4} {'Open':>5}")
    for g in [*by, d["school"]]:
        print(f"  {str(g['group']):<12} {g['pupils']:>6} {_pct(g['pct']):>6} "
              f"{g['persistent']:>4} {g['severe']:>4} {g['open']:>5}")


def _history(_principal: Principal) -> None:
    c = _concern()
    if c is None:
        return
    for h in AC.history(c.concern_id):
        print(f"  {h['at']}  {h['actor']:<12} {h['action']:<12} "
              + ", ".join(f"{k}={v}" for k, v in h["detail"].items()))


def _export(principal: Principal) -> None:
    path = _prompt("  Save CSV to (e.g. attendance_concerns.csv): ")
    if path:
        print(f"  Exported {AC.export_csv(path, actor=principal)} case(s).")


def _refresh(principal: Principal) -> None:
    print(f"  Updated {AC.refresh_figures(actor=principal)} open case(s).")


_OPTIONS = {"1": _new, "2": _list, "3": _view, "4": _edit, "5": _set_status, "6": _close,
            "7": _summary, "8": _delete, "9": _note, "10": _stage, "11": _letter,
            "12": _review, "13": _refer, "14": _la_outcome, "15": _cme, "16": _trend,
            "17": _candidates, "18": _due, "19": _watch, "20": _dashboard, "21": _history,
            "22": _export, "23": _refresh}


def menu(principal: Principal) -> None:
    while True:
        activity_log.record("attendance_concerns.view")
        print("\n  ── Attendance Concerns ──")
        print("   1) New concern\n   2) List concerns\n   3) View concern\n   4) Edit concern"
              "\n   5) Set status\n   6) Close concern\n   7) Cohort summary"
              "\n   8) Delete concern")
        print("  More")
        print("   9) Add note\n  10) Next stage\n  11) Letter home\n  12) Review"
              "\n  13) Refer to the local authority\n  14) LA outcome"
              "\n  15) Children missing education\n  16) Trend\n  17) From the registers"
              "\n  18) Reviews due\n  19) Penalty threshold / CME watch\n  20) Dashboard"
              "\n  21) History\n  22) Export CSV\n  23) Update % from the registers")
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
