"""Student self-service menu for the Sixth Form System CLI.

Terminal counterpart of :mod:`...interfaces.gui.portals.student_portal_gui`
and the same rule: the learner sees only their own record. Every read
passes ``principal.student_id`` to
:mod:`...parent_portal.learner_view`; no student id is ever typed in.

Every prompt goes through the CLI idle-timeout reader, so a terminal
left signed in logs itself out like the staff menu does.

Options 13 onwards (My plan, exams, projects & placements, library,
surveys, wellbeing & help, study planner) live in
:mod:`._learner_sections_cli`.
"""

from __future__ import annotations

import datetime as _dt
import logging
from typing import Any, Callable

from education_system.systems.sixth_form import SYSTEM_NAME
from education_system.systems.sixth_form.domain.operations.communications.parent_portal import (
    learner_view as lv,
)
from education_system.systems.sixth_form.interfaces.cli.idle_timeout import (
    SessionTimeoutError,
    timed_input,
    timeout_minutes,
)

logger = logging.getLogger(__name__)

_RULE = "─" * 76


class _UserAbort(Exception):
    """Ctrl-C / EOF at a prompt — unwind to the menu."""


def _input(prompt: str, default: str = "") -> str:
    try:
        raw = timed_input(f"  {prompt}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        raise _UserAbort
    return raw or default


def _pause() -> None:
    try:
        timed_input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


def _d(v: Any) -> str:
    return "—" if v in (None, "") else str(v)


def _money(v: Any) -> str:
    return "—" if v is None else f"£{float(v):,.2f}"


def _head(title: str) -> None:
    print(f"\n  {_RULE}\n  {title}\n  {_RULE}")


# ── Screens ─────────────────────────────────────────────────────────

def _timetable(sid: str, _p) -> None:
    _head("My timetable")
    rows = lv.timetable(sid)
    if not rows:
        print("  You have no timetabled lessons yet.")
        return
    day = None
    for s in rows:
        if s["day_name"] != day:
            day = s["day_name"]
            print(f"\n  {day}")
        print(f"    P{s['period']} {s['start_time']}-{s['end_time']}  "
              f"{s['subject'][:26]:<28}{_d(s['room']):<10}{_d(s['teacher'])}")


def _attendance(sid: str, p) -> None:
    att = lv.attendance(sid)
    c = att["counts"]
    _head("My attendance")
    print(f"  This year {_d(att['overall_percentage'])}%   last {att['days']} days "
          f"{_d(att['percentage'])}%")
    print(f"  Present {c['Present']} · Late {c['Late']} · Absent {c['Absent']} · "
          f"Authorised {c['Authorised']}")
    try:
        from education_system.systems.sixth_form.domain.academics.attendance import (
            attendance_absence_reports as _abs,
        )
        print(f"  Self-certification: {_abs.self_cert_status(sid).label}")
    except Exception:
        logger.debug("Self-cert status unavailable", exc_info=True)
    print(f"\n  {'Date':<12}{'Sess':<8}{'Subject':<26}{'Mark':<12}{'Code':<6}Late")
    print("  " + "-" * 70)
    for m in att["marks"][:40]:
        print(f"  {m['date']:<12}{_d(m['session']):<8}{m['subject'][:24]:<26}"
              f"{m['status']:<12}{_d(m['code']):<6}{_d(m['minutes_late'] or None)}")
    if len(att["marks"]) > 40:
        print(f"  ... and {len(att['marks']) - 40} more")


def _report_absence(sid: str, p) -> None:
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance_absence_reports as _abs,
    )
    _head("Report an absence")
    try:
        print(f"  {_abs.self_cert_status(sid).label}")
    except Exception:
        pass
    today = _dt.date.today().isoformat()
    date_from = _input("First day (YYYY-MM-DD)", today)
    date_to = _input("Last day (YYYY-MM-DD)", date_from)
    reason = _input("Reason")
    message = _input("Message (optional)")
    mode = _input("S)elf-certify illness, or O)ffice to decide", "o").lower()
    kwargs = {"date_to": date_to, "reason_text": reason or None,
              "message": message or None}
    try:
        if mode.startswith("s"):
            rep = _abs.self_certify_for(p, date_from, **kwargs)
        else:
            rep = _abs.report_absence_for(p, None, date_from, **kwargs)
    except Exception as e:          # ValidationError / AccessDenied
        print(f"\n  ✗ {e}")
        return
    print(f"\n  ✓ Received — {rep.span} ({rep.state}).")
    print("\n  Your absence reports:")
    for r in _abs.portal_history(p)[:10]:
        print(f"    {r.span:<26}{_d(r.reason_text)[:30]:<32}{r.state}")


def _grades(sid: str, _p) -> None:
    _head("My subjects")
    for a in lv.learning_aims(sid):
        print(f"  {a['subject'][:28]:<30}{a['qualification_type']:<16}"
              f"{_d(a['awarding_body']):<12}{a['status']}")
    _head("Grades")
    print("  Predicted grades show once shared with you on a published report.")
    print(f"\n  {'Subject':<28}{'Working':<10}{'Target':<9}{'Aspire':<9}"
          f"{'Predicted':<11}Progress")
    for g in lv.grades(sid):
        print(f"  {g['subject'][:26]:<28}{_d(g['current']):<10}{_d(g['target']):<9}"
              f"{_d(g['aspirational']):<9}{_d(g['predicted']):<11}{_d(g['status'])}")


def _results(sid: str, _p) -> None:
    _head("Released exam results")
    rows = lv.released_results(sid)
    if not rows:
        print("  No exam results have been released to you yet.")
        return
    for r in rows:
        print(f"  {r['season']} {r['year']:<6} {r['subject'][:24]:<26}"
              f"{_d(r['paper'])[:24]:<26}{r['grade']:<8}{_d(r['marks'])}")


def _work(sid: str, _p) -> None:
    _head("Work set and due")
    rows = lv.coursework(sid)
    if not rows:
        print("  Nothing has been set for you.")
        return
    for r in rows:
        state = "OVERDUE" if r["overdue"] else r["status"]
        print(f"  {_d(r['due_date']):<12}{r['kind']:<11}{_d(r['subject'])[:18]:<20}"
              f"{r['title'][:30]:<32}{state:<12}{_d(r['mark'])}")


def _reports(sid: str, _p) -> None:
    from education_system.systems.sixth_form.domain.assessment.report_cards import (
        report_cards as _rc,
    )
    while True:
        cards = lv.report_cards(sid)
        _head("My reports")
        if not cards:
            print("  No reports have been published to you yet.")
            return
        for i, c in enumerate(cards, 1):
            print(f"  {i:>3}) {c['period']:<30} published {_d(c['published_at'])}")
        pick = _input("Open which (number), or Enter to go back")
        if not pick:
            return
        if not pick.isdigit() or not 1 <= int(pick) <= len(cards):
            print("  Not a valid option.")
            continue
        card_id = cards[int(pick) - 1]["card_id"]
        print()
        for line in lv.report_card_text(sid, card_id).splitlines():
            print(f"  {line}")
        fmt = _input("Save a copy? h)tml / p)df / Enter for no").lower()
        if fmt in ("h", "p"):
            try:
                card = _rc.published_card(sid, card_id)
                path = _rc.render(card.card_id, fmt="html" if fmt == "h" else "pdf")
                print(f"  ✓ Saved to {path}")
            except _rc.ValidationError as e:
                print(f"  ✗ {e}")


def _ucas(sid: str, _p) -> None:
    _head("UCAS")
    u = lv.ucas(sid)
    if u is None:
        print("  You have no UCAS application on record.")
        return
    print(f"  Cycle {u['cycle_year']} · {u['status']} · UCAS ID {_d(u['ucas_id'])} · "
          f"submitted {_d(u['submitted_at'])}")
    d = u.get("deadline")
    if d:
        print(f"  Deadline {d['deadline']} ({d['reason']}); college internal deadline "
              f"{d['internal_date']} — {d['days_to_internal']} days · {d['state']}")
    if u.get("results_embargoed"):
        print("  Your results have not been released yet — results-day outcomes on your")
        print("  Firm and Insurance choices are held back until they are.")
    print("\n  Choices")
    for c in u["choices"]:
        print(f"   {c['order']}. {c['university'][:26]:<28}{c['course'][:28]:<30}"
              f"{c['decision']:<14}{_d(c['final'])}")
        if c["offer"]:
            print(f"      Offer: {c['offer']}")
        for cond in c.get("conditions") or ():
            print(f"      • {cond}")
        when = [f"reply by {c['reply_by']}" if c.get("reply_by") else "",
                f"decided {c['decision_date']}" if c.get("decision_date") else ""]
        if any(when):
            print(f"      ({'; '.join(w for w in when if w)})")
    _print_tracker(u.get("tracker"))
    p = u.get("pipeline")
    if p:
        print(f"\n  Steps — {p['percent']}% complete")
        for s in p["stages"]:
            print(f"    {s['label'][:40]:<42}{s['status']:<14}{_d(s['due_date'])}")


_TRACK_MARK = {"done": "[x]", "current": "[>]", "pending": "[ ]", "held": "[~]",
               "n/a": " - "}
_TRACK_TEXT = {"done": "done", "current": "next", "pending": "not yet",
               "held": "held (results embargo)", "n/a": "not applicable"}


def _print_tracker(steps) -> None:
    """The move-to-university tracker (shared with the parent portal CLI)."""
    if not steps:
        return
    print("\n  Your move to university")
    for s in steps:
        print(f"    {_TRACK_MARK.get(s['state'], '   ')} {s['label']:<24}"
              f"{_TRACK_TEXT.get(s['state'], s['state']):<24}{_d(s.get('date')):<12}"
              f"{s.get('detail') or ''}")


def _bursary(sid: str, _p) -> None:
    _head("Bursary")
    apps = lv.bursaries(sid)
    if not apps:
        print("  You have no bursary applications.")
        return
    for a in apps:
        print(f"\n  {a['type']} ({_d(a['academic_year'])}) — {a['status']}")
        print(f"    Applied {a['applied']} · awarded {_money(a['awarded'])} · "
              f"paid {_money(a['paid'])} · still to pay {_money(a['remaining'])}")
        for pmt in a["payments"]:
            print(f"      paid {pmt['date']}  {_money(pmt['amount'])}  "
                  f"{pmt['method']} ({pmt['status']})")
        for s in a["schedule"]:
            print(f"      due  {s['due_date']}  {_money(s['amount'])}  {s['state']}")


def _trips(sid: str, _p) -> None:
    _head("My trips")
    rows = lv.trips(sid)
    if not rows:
        print("  You are not booked on any trips.")
        return
    for t in rows:
        print(f"  {t['trip'][:28]:<30}{t['start_date']:<12}{t['booking_status']:<12}"
              f"consent {'given' if t['consent'] else 'NEEDED':<8} "
              f"paid {_money(t['paid'])} / balance {_money(t['balance'])}")
    print("\n  Consent is given by a parent or guardian from the parent portal.")


def _messages(sid: str, _p) -> None:
    me = lv.student_identity(sid)
    address = me.get("email")
    _head("Announcements")
    anns = lv.announcements("students")
    if not anns:
        print("  No current announcements.")
    for a in anns[:10]:
        print(f"  {'*' if a['pinned'] else ' '} {a['title']} [{a['priority']}]")
        if a["summary"]:
            print(f"      {a['summary'][:100]}")
    while True:
        inbox = lv.messages_to(address)
        _head(f"Messages to {_d(address)}")
        if not inbox:
            print("  No messages yet.")
            return
        for i, m in enumerate(inbox, 1):
            print(f"  {i:>3}) {(m['sent_at'] or '')[:16]:<18}"
                  f"{(m['from_name'] or m['from_address'] or '—')[:22]:<24}"
                  f"{m['subject'][:40]}")
        pick = _input("Open which (number), or Enter to go back")
        if not pick:
            return
        if pick.isdigit() and 1 <= int(pick) <= len(inbox):
            try:
                m = lv.message_for(address, inbox[int(pick) - 1]["message_id"])
            except LookupError as e:
                print(f"  ✗ {e}")
                continue
            print(f"\n  {m['subject']}\n  From: {m['from_name'] or m['from_address']}"
                  f"\n  Sent: {_d(m['sent_at'])}\n")
            for line in (m["body"] or "").splitlines():
                print(f"  {line}")
            _pause()


def _signouts(sid: str, p) -> None:
    _head("My sign-outs")
    rows = lv.signouts(sid)
    if not rows:
        print("  No sign-outs recorded.")
    for s in rows:
        print(f"  {s['date']:<12}out {s['out']:<7}back {_d(s['back']):<7}"
              f"{s['reason'][:20]:<22}{s['state']}")
    while True:
        _head("My sign-out requests")
        reqs = lv.signout_requests(sid)
        if not reqs:
            print("  No requests. Ask ahead and a member of staff approves it;")
            print("  then sign out at reception as usual.")
        for i, r in enumerate(reqs, 1):
            back = f" back {r['expected_back']}" if r["expected_back"] else ""
            print(f"  {i:>2}. {r['date']} {r['leave_time']}{back:<11} "
                  f"{r['reason'][:22]:<24}{r['state']}"
                  + (f" — {r['decision_note']}" if r["decision_note"] else ""))
        pick = _input("R)equest to leave site, C)ancel a request, Enter to go back").lower()
        if not pick:
            return
        if pick.startswith("r"):
            _request_signout(sid, p)
        elif pick.startswith("c"):
            open_reqs = [r for r in reqs if r["open"]]
            if not open_reqs:
                print("  Nothing open to cancel.")
                continue
            n = _input("Cancel which (number)")
            if n.isdigit() and 1 <= int(n) <= len(reqs) and reqs[int(n) - 1]["open"]:
                try:
                    lv.cancel_signout_request(sid, reqs[int(n) - 1]["request_id"],
                                              by=p.username)
                    print("  ✓ Cancelled.")
                except Exception as e:
                    print(f"  ✗ {e}")


def _request_signout(sid: str, p) -> None:
    reasons = lv.signout_reasons()
    for i, r in enumerate(reasons, 1):
        print(f"    {i}. {r}")
    n = _input("Reason (number)", "2")
    if not (n.isdigit() and 1 <= int(n) <= len(reasons)):
        print("  ✗ Pick a number from the list.")
        return
    reason = reasons[int(n) - 1]
    date = _input("Date (YYYY-MM-DD)", _dt.date.today().isoformat())
    leave = _input("Leaving at (HH:MM)")
    detail = _input("Detail (who / why)")
    back = "" if reason == "Early leave" else _input("Back by (HH:MM, blank if not sure)")
    aware = _input("Does a parent/carer know? y/N", "n").lower().startswith("y")
    try:
        out = lv.request_signout(sid, reason=reason, date=date, leave_time=leave,
                                 detail=detail or None, expected_back=back or None,
                                 parent_aware=aware, requested_by=p.username)
        print(f"  ✓ Request #{out['request_id']} sent — {out['state']}.")
    except Exception as e:
        print(f"  ✗ {e}")


def _change_password(auth) -> None:
    from education_system.platform.delivery.cli import change_password_cli
    change_password_cli.run(auth)


def _mfa(auth) -> None:
    from education_system.platform.delivery.cli import mfa_setup_cli
    mfa_setup_cli.open_mfa(auth=auth)


_MENU: list[tuple[str, Callable[[str, Any], None]]] = [
    ("My timetable", _timetable),
    ("My attendance", _attendance),
    ("Report an absence / self-certify", _report_absence),
    ("My subjects and grades", _grades),
    ("Released exam results", _results),
    ("Work due (assignments & homework)", _work),
    ("My reports", _reports),
    ("UCAS application", _ucas),
    ("Bursary", _bursary),
    ("Trips", _trips),
    ("Messages & announcements", _messages),
    ("My sign-outs & requests", _signouts),
]


def _menu() -> list[tuple[str, Callable[[str, Any], None]]]:
    """The twelve original options, then the learner-only screens."""
    from education_system.systems.sixth_form.interfaces.cli.portals import (
        _learner_sections_cli,
    )
    return _MENU + _learner_sections_cli.MENU


def run(shared_auth, principal) -> int:
    """Run the student menu for an already-authenticated learner."""
    from education_system import switch
    sid = principal.student_id
    if not sid:
        raise ValueError("The student portal needs a principal with a student_id")
    try:
        me = lv.student_identity(sid)
        name = me["full_name"]
    except Exception:
        name = principal.username
    menu = _menu()
    while True:
        try:
            print(f"\n=== {SYSTEM_NAME} — Student Portal ===")
            print(f"Signed in: {name} ({sid})")
            for i, (label, _) in enumerate(menu, 1):
                print(f"  {i:2d}) {label}")
            print("   P) Change my password")
            print("   M) Multi-factor authentication")
            print("   L) Logout")
            choice = _input("Select").lower()
            if choice in ("l", "q", "logout", "quit"):
                break
            if choice == "p":
                _change_password(shared_auth)
                _pause()
                continue
            if choice == "m":
                _mfa(shared_auth)
                continue
            if choice.isdigit() and 1 <= int(choice) <= len(menu):
                label, handler = menu[int(choice) - 1]
                try:
                    handler(sid, principal)
                except _UserAbort:
                    print("\n  Cancelled.")
                except SessionTimeoutError:
                    raise
                except Exception:
                    logger.exception("Student portal %s failed for %s", label, sid)
                    print(f"\n  {label} could not be loaded just now.")
                _pause()
                continue
            if choice:
                print("  Not a valid option.")
        except _UserAbort:
            break
        except SessionTimeoutError:
            print(f"\n[!] Signed out after {timeout_minutes()} minute(s) of inactivity. "
                  "Please sign in again to continue.")
            logger.info("Idle logout for student=%s", sid)
            break
    try:
        shared_auth.logout()
    except Exception:
        logger.debug("Logout on the shared session failed", exc_info=True)
    switch.request_logout("cli")
    print("\n  Signed out. Goodbye.\n")
    return 0
