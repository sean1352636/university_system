"""Report a Safeguarding Concern in the terminal - every member of staff.

1 Report a concern (the old "Raise concern" for staff, with the child's own
words, body map, immediate action and the urgent question), 2 My reports
(status only), 3 Add information to a report, 4 Who to contact.
Rules: :func:`modules.safeguarding.domain.safeguarding.report_concern`.
"""

from __future__ import annotations

from education_system.systems.secondary.modules.safeguarding.domain import safeguarding as SG
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.cli.prompts import prompts
from education_system.systems.secondary.ui.cli.prompts.prompts import pause as _pause
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt
from education_system.systems.secondary.ui.cli.prompts.prompts import yes as _yes

_ERRORS = (SG.ValidationError, SG.PermissionDenied, SG.NotFound)
_DANGER = ("  If a child is in immediate danger, call 999 and then speak to the DSL in person."
           "\n  Write what the child said in their own words; don't ask leading questions.")


def _team() -> None:
    team = SG.team()
    if not team:
        print("  No safeguarding lead is set up yet - tell the headteacher.")
    for m in team:
        print(f"  {m['name']} ({m['team_role']})" + (f"  phone {m['phone']}" if m["phone"]
                                                    else "")
              + (f"  {m['email']}" if m["email"] else ""))


def _report(principal: Principal) -> None:
    print(_DANGER)
    data = {"pupil_id": _prompt("  Pupil admission no. (or ID): "),
            "category": prompts.pick("Kind of concern (blank if unsure)",
                                     SG.CONCERN_CATEGORIES) or "",
            "incident_date": _prompt("  Date it happened (YYYY-MM-DD, blank = today): "),
            "incident_time": _prompt("  Time (HH:MM, blank ok): "),
            "location": _prompt("  Where: "),
            "description": _prompt("  What you saw or heard: "),
            "child_words": _prompt("  What the child said, in their own words: "),
            "body_map": _prompt("  Any injury - where on the body, size, colour: "),
            "immediate_action": _prompt("  What you did straight away: "),
            "people_involved": _prompt("  Anyone else involved or who saw it: "),
            "immediate_danger": _yes("  Is the child in immediate danger / is this urgent?")}
    rep, alert = SG.report_concern(data, actor=principal)
    print(f"\n  Thank you. Concern #{rep.concern_id} has gone to the DSL.")
    if not rep.urgent:
        return
    if alert.get("message_id"):
        from education_system.systems.secondary.modules.communication.domain import (
            email_outbox as E,
        )
        try:
            E.deliver(alert["message_id"], principal=principal)
            print(f"  URGENT: {alert['emails']} member(s) of the safeguarding team e-mailed.")
        except Exception as e:  # noqa: BLE001 - the alert stays in the outbox
            print(f"  URGENT alert saved in the outbox but not sent ({e}) - phone the DSL.")
        print("  Now find the DSL in person:")
        _team()
        return
    print("  URGENT: nobody on the safeguarding team has an e-mail address. PHONE THE DSL NOW:")
    for m in alert.get("phone", []):
        print(f"    {m['name']} ({m['team_role']}): {m['phone'] or 'no phone recorded'}")
    who = _prompt("  Once you've spoken to them - who did you speak to? ")
    if who:
        SG.record_phoned(rep.concern_id, actor=principal, who=who)
        print("  Recorded.")


def _mine(principal: Principal) -> None:
    rows = SG.my_reports(actor=principal)
    if not rows:
        print("  You haven't reported any concerns.")
        return
    print(f"  {'No.':<5} {'Reported':<10} {'Pupil':<28} {'Kind':<24} {'!':<2} Status")
    for r in rows:
        print(f"  {r.concern_id:<5} {r.raised_date:<10} {r.pupil_name[:28]:<28} "
              f"{r.category[:24]:<24} {'!' if r.urgent else '':<2} {r.status}")


def _add(principal: Principal) -> None:
    cid = prompts.ask_int("  Concern no.: ")
    if cid:
        SG.add_information(cid, _prompt("  What you have since seen or heard: "),
                           actor=principal)
        print("  Added - the DSL can see it.")


def _contact(_principal: Principal) -> None:
    _team()
    print(_DANGER)


_OPTIONS = {"1": _report, "2": _mine, "3": _add, "4": _contact}


def menu(principal: Principal) -> None:
    while True:
        activity_log.record("safeguarding.report_view")
        print("\n  ── Report a Safeguarding Concern ──")
        print("    1) Report a concern\n    2) My reports\n    3) Add information to a report"
              "\n    4) Who to contact\n    0) Back")
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
            prompts.problem(e)
        _pause()
