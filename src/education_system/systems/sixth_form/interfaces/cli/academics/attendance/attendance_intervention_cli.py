"""CLI flows for acting on poor attendance.

Submenu hung off Attendance: the escalation ladder and its contracts and
meetings, punctuality sanctions, the persistent-absence cohorts, the
safeguarding bridge, bursary decisions, and the rewards that stop
attendance only ever being talked about negatively.
"""

from __future__ import annotations

import logging
from datetime import date as _date, timedelta as _timedelta
from typing import Callable

from education_system.systems.sixth_form.domain.academics.attendance.attendance import (
    ValidationError,
)
from education_system.systems.sixth_form.interfaces.cli.academics.attendance.attendance_cli import (
    lazy_domain,
    _input,
    _pause,
    _pick_from,
    _UserAbort,
)

# Domain modules load on first use (see attendance_cli.lazy_domain).
bursary = lazy_domain("attendance_bursary")
cohorts = lazy_domain("attendance_cohorts")
escalation = lazy_domain("attendance_escalation")
punctuality = lazy_domain("attendance_punctuality")
rewards = lazy_domain("attendance_rewards")
safeguarding = lazy_domain("attendance_safeguarding")

logger = logging.getLogger(__name__)


def _today() -> str:
    return _date.today().isoformat()


def _term_ago() -> str:
    return (_date.today() - _timedelta(days=42)).isoformat()


def _yes(prompt: str, *, default: str = "n") -> bool:
    return _input(prompt, default=default).lower().startswith("y")


def _int(prompt: str) -> int:
    return int(_input(prompt, allow_empty=False))


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value:.1f}%"


# ═══ Cases and escalation ═══════════════════════════════════════════

def case_open() -> None:
    print("\n═══ Open a Case ═══")
    try:
        student_id = _input("Student ID", allow_empty=False)
        suggested = escalation.suggest_stage(student_id)
        if suggested:
            print(f"\n  The ladder suggests: {suggested}")
        stage = _pick_from("Stage", list(escalation.STAGES),
                           default=suggested or escalation.TUTOR_CONVERSATION)
        case = escalation.open_case(
            student_id, stage=stage, owner=_input("Owner") or None,
            opened_by=_input("Opened by") or None,
            summary=_input("Summary (optional)") or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    print(f"\n  ✓ Case #{case.case_id}: {case.label}")
    print(f"    Review by {case.review_on}.")
    _pause()


def case_overdue() -> None:
    print("\n═══ Cases Past Their Review Date ═══")
    print("\n  The most useful list here: a case with an owner and a date")
    print("  that has slipped looks like somebody is dealing with it.")
    rows = escalation.overdue_reviews()
    if not rows:
        print("\n  ✓ Every open case is within its review date.")
        _pause()
        return
    print(f"\n    {'#':>5}  {'Learner':<24}{'Stage':<24}{'Owner':<16}Review")
    for case in rows[:40]:
        print(f"    {case.case_id:>5}  "
              f"{(case.student_name or case.student_id)[:23]:<24}"
              f"{case.stage[:23]:<24}{(case.owner or '—')[:15]:<16}"
              f"{case.review_on}")
    try:
        if not _yes("\n  Escalate one? (y/N)"):
            return
        case_id = _int("Case #")
        case = escalation.escalate(
            case_id, actor=_input("Escalated by") or None,
            owner=_input("New owner (optional)") or None,
            note=_input("Note (optional)") or None)
        print(f"\n  ✓ Now at {case.stage}, review by {case.review_on}.")
    except ValueError:
        print("\n  ✗ Case # must be a number.")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
    except _UserAbort:
        print("\n  Cancelled.")
    _pause()


def case_contract() -> None:
    print("\n═══ Attendance Contract ═══")
    print("\n  Record what the college will do as well as what the learner")
    print("  will — a contract without support is a warning with a")
    print("  signature line, and it does not work.")
    try:
        student_id = _input("Student ID", allow_empty=False)
        target = float(_input("Target attendance %", default="90"))
        start = _input("From (YYYY-MM-DD)", default=_today())
        end = _input("To (YYYY-MM-DD)", allow_empty=False)
        contract = escalation.create_contract(
            student_id, target_pct=target, start_date=start, end_date=end,
            terms=_input("What the learner agrees to") or None,
            support=_input("What the college will do") or None,
            signed_by_staff=_input("Staff signature") or None)
    except ValueError:
        print("\n  ✗ Target must be a number.")
        _pause()
        return
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    print(f"\n  ✓ #{contract.contract_id}: {contract.label}")
    _pause()


def case_contract_review() -> None:
    print("\n═══ Contracts Due Review ═══")
    due = escalation.contracts_due_review()
    if not due:
        print("\n  ✓ Nothing due.")
    else:
        for contract in due:
            progress = escalation.contract_progress(contract.contract_id)
            state = "on track" if progress.on_track else "not on track"
            print(f"    #{contract.contract_id:<5}{contract.student_id:<12}"
                  f"{progress.label:<40}{state}")
    effectiveness = escalation.contract_effectiveness()
    if effectiveness.get("contracts"):
        print(f"\n  Across {effectiveness['contracts']} settled contract(s): "
              f"{effectiveness.get('met_rate', 0)}% met, average change "
              f"{effectiveness.get('average_change')} points.")
    try:
        if due and _yes("\n  Close one now? (y/N)"):
            contract_id = _int("Contract #")
            out = escalation.close_contract(
                contract_id, note=_input("Note (optional)") or None)
            print(f"\n  ✓ Closed as {out.state} ({_pct(out.outcome_pct)}).")
    except ValueError:
        print("\n  ✗ Contract # must be a number.")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
    except _UserAbort:
        pass
    _pause()


def case_meeting() -> None:
    print("\n═══ Log a Meeting ═══")
    try:
        student_id = _input("Student ID", allow_empty=False)
        case = escalation.open_case_for(student_id)
        meeting = escalation.log_meeting(
            student_id, _input("Date", default=_today()),
            kind=_pick_from("Kind", list(escalation.MEETING_KINDS),
                            default=escalation.MEETING_KINDS[0]),
            case_id=case.case_id if case else None,
            attendees=_input("Who was there") or None,
            notes=_input("Notes") or None,
            actions=_input("Actions agreed") or None,
            outcome=_input("Outcome") or None,
            next_review=_input("Next review (YYYY-MM-DD, optional)") or None,
            recorded_by=_input("Recorded by") or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    print(f"\n  ✓ Meeting #{meeting.meeting_id} recorded.")
    if meeting.next_review:
        print(f"    Case review moved to {meeting.next_review}.")
    _pause()


def case_file() -> None:
    print("\n═══ Case File ═══")
    try:
        student_id = _input("Student ID", allow_empty=False)
        file = escalation.case_file(student_id)
    except _UserAbort:
        return
    print(f"\n  {student_id}: {_pct(file['current_percentage'])} "
          f"(ladder suggests {file['suggested_stage'] or 'no action'})")
    for case in file["cases"]:
        print(f"\n    Case #{case.case_id} — {case.stage} [{case.state}]")
        for entry in escalation.stage_history(case.case_id):
            print(f"      {entry.entered_on}  {entry.stage} "
                  f"({entry.entered_by or '?'}) {entry.note or ''}")
    for contract in file["contracts"]:
        print(f"\n    Contract: {contract.label}")
    for meeting in file["meetings"][:10]:
        print(f"    Meeting {meeting.date} ({meeting.kind}): "
              f"{meeting.outcome or meeting.notes or ''}")
    _pause()


_CASE_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Open a case",          case_open),
    ("Overdue reviews",      case_overdue),
    ("New contract",         case_contract),
    ("Contracts due review", case_contract_review),
    ("Log a meeting",        case_meeting),
    ("Case file",            case_file),
]


# ═══ Punctuality ════════════════════════════════════════════════════

def punctual_league() -> None:
    print("\n═══ Punctuality ═══")
    print("\n  Counted in minutes of teaching missed, which is the figure")
    print("  that makes the case.")
    try:
        window = int(_input("Window (days)", default="28"))
        rows = punctuality.league(window_days=window)
    except ValueError:
        print("\n  ✗ Window must be a number.")
        _pause()
        return
    except _UserAbort:
        return
    if not rows:
        print("\n  ✓ No lateness recorded.")
        _pause()
        return
    print(f"\n    {'Learner':<24}{'Late':>5}{'After close':>12}"
          f"{'Hours lost':>11}{'Avg':>7}")
    for entry in rows[:30]:
        print(f"    {(entry.student_name or entry.student_id)[:23]:<24}"
              f"{entry.late:>5}{entry.after_close:>12}"
              f"{entry.hours_lost:>11}"
              f"{(entry.average_minutes or 0):>6.0f}m")
    summary = punctuality.college_summary(window_days=window)
    print(f"\n  College: {summary['late_marks']} late mark(s), "
          f"{summary['hours_lost']}h lost "
          f"(~{summary['teaching_days_lost']} teaching days)")
    print(f"  {summary['after_register_closed']} arrival(s) after the "
          "register closed — present in the room, absent in the data.")
    _pause()


def punctual_patterns() -> None:
    print("\n═══ When Lateness Happens ═══")
    print("\n  Period 1 lateness is transport; period 5 is lunch; Monday")
    print("  is the weekend. They need different answers.")
    try:
        student_id = _input("Student ID (blank = whole college)") or None
        insight = punctuality.patterns(student_id=student_id)
    except _UserAbort:
        return
    from education_system.systems.sixth_form.domain.academics.timetable.timetable import (  # noqa: E501
        day_name,
    )
    if insight.by_weekday:
        print("\n  By day:")
        for day, n in sorted(insight.by_weekday.items()):
            print(f"    {day_name(day):<6}{n:>5}")
    if insight.by_period:
        print("\n  By period:")
        for period, n in sorted(insight.by_period.items()):
            print(f"    P{period:<5}{n:>5}")
        share = insight.first_period_share
        if share is not None:
            print(f"\n  Period 1 is {share:.0f}% of all lateness.")
    if not (insight.by_weekday or insight.by_period):
        print("\n  No lateness recorded in the window.")
    _pause()


def punctual_sweep() -> None:
    print("\n═══ Raise Punctuality Triggers ═══")
    try:
        preview = punctuality.sweep(dry_run=True)
        print(f"\n  {preview.checked} learner(s) checked; "
              f"{preview.raised} trigger(s) would be raised "
              f"({preview.skipped_existing} already open).")
        if preview.raised and _yes("\n  Raise them? (y/N)"):
            result = punctuality.sweep(dry_run=False)
            print(f"\n  ✓ {result.raised} raised.")
            for trigger in result.triggers[:20]:
                print(f"    {trigger.label}")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
    except _UserAbort:
        print("\n  Cancelled.")
    _pause()


def punctual_outstanding() -> None:
    print("\n═══ Outstanding Sanctions ═══")
    rows = punctuality.outstanding()
    if not rows:
        print("\n  ✓ Nothing outstanding.")
        _pause()
        return
    for trigger in rows[:40]:
        print(f"    #{trigger.trigger_id:<5}{trigger.label}")
    try:
        if not _yes("\n  Update one? (y/N)"):
            return
        trigger_id = _int("Trigger #")
        action = _pick_from("What happened",
                            ["Served", "Missed", "Waived"], default="Served")
        if action == "Served":
            punctuality.serve(trigger_id,
                              actioned_by=_input("Recorded by") or None)
        elif action == "Missed":
            punctuality.mark_missed(trigger_id,
                                    note=_input("Note") or None)
        else:
            punctuality.waive(trigger_id,
                              reason=_input("Reason", allow_empty=False))
        print("\n  ✓ Updated.")
    except ValueError:
        print("\n  ✗ Trigger # must be a number.")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
    except _UserAbort:
        print("\n  Cancelled.")
    _pause()


_PUNCTUAL_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Punctuality league",   punctual_league),
    ("When lateness happens", punctual_patterns),
    ("Raise triggers",       punctual_sweep),
    ("Outstanding sanctions", punctual_outstanding),
]


# ═══ Cohorts ════════════════════════════════════════════════════════

def cohort_bands() -> None:
    print("\n═══ Attendance Bands ═══")
    try:
        window = int(_input("Window (days)", default="42"))
    except ValueError:
        window = 42
    except _UserAbort:
        return
    bands = cohorts.all_bands(window_days=window)
    for band in cohorts.BANDS:
        entry = bands[band]
        print(f"\n  {entry.label}")
        for member in entry.members[:15]:
            print(f"    {member.label}")
        if entry.size > 15:
            print(f"    … and {entry.size - 15} more.")
    _pause()


def cohort_recovery() -> None:
    print("\n═══ What It Would Take ═══")
    print("\n  Sometimes the honest answer is that this year the target is")
    print("  arithmetically out of reach — better said in October.")
    try:
        student_id = _input("Student ID", allow_empty=False)
        remaining = int(_input("Sessions left this year", default="0")) or None
        recovery = cohorts.sessions_to_reach(student_id,
                                             sessions_remaining=remaining)
    except ValueError:
        print("\n  ✗ That needs to be a number.")
        _pause()
        return
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except _UserAbort:
        return
    print(f"\n  {recovery.label}")
    print(f"    Currently {recovery.current_pct:.1f}% "
          f"({recovery.attended}/{recovery.sessions} sessions)")
    _pause()


def cohort_snapshot() -> None:
    print("\n═══ Cohort Snapshots ═══")
    print("\n  Take one each half term; movement between them is how you")
    print("  know whether anything is working.")
    snapshots = cohorts.list_snapshots()
    for snapshot in snapshots[:10]:
        bands = cohorts.snapshot_bands(snapshot["snapshot_id"])
        print(f"    #{snapshot['snapshot_id']:<4}{snapshot['taken_on']:<12}"
              + ", ".join(f"{k}={v}" for k, v in bands.items()))
    try:
        if _yes("\n  Take one now? (y/N)"):
            snapshot_id = cohorts.take_snapshot(
                label=_input("Label (optional)") or None,
                taken_by=_input("Taken by") or None)
            print(f"\n  ✓ Snapshot #{snapshot_id} taken.")
        if len(snapshots) >= 2 and _yes("  Compare two? (y/N)"):
            first = _int("From snapshot #")
            second = _int("To snapshot #")
            summary = cohorts.movement_summary(first, second)
            print(f"\n  {summary['moved']} learner(s) changed band: "
                  f"{summary['improved']} improved, "
                  f"{summary['worsened']} worsened.")
            print(f"  Persistent absence: {summary['persistent_before']} → "
                  f"{summary['persistent_after']} "
                  f"({summary['net_change']:+d})")
    except ValueError:
        print("\n  ✗ Snapshot # must be a number.")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
    except _UserAbort:
        pass
    _pause()


_COHORT_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Bands",              cohort_bands),
    ("Recovery arithmetic", cohort_recovery),
    ("Snapshots & movement", cohort_snapshot),
]


# ═══ Safeguarding ═══════════════════════════════════════════════════

def sg_sweep() -> None:
    print("\n═══ Safeguarding Sweep ═══")
    print("\n  Looks for consecutive unexplained absence with no contact —")
    print("  the pattern that matters. Raises flags for a person to read.")
    try:
        preview = safeguarding.sweep(dry_run=True)
        print(f"\n  {preview.checked} learner(s) checked; "
              f"{preview.raised} alert(s) would be raised.")
        if preview.raised and _yes("\n  Raise them? (y/N)"):
            result = safeguarding.sweep(
                dry_run=False, raised_by=_input("Raised by") or None)
            print(f"\n  ✓ {result.summary}")
            for alert in result.alerts[:20]:
                print(f"    {alert.label}")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
    except _UserAbort:
        print("\n  Cancelled.")
    _pause()


def sg_open() -> None:
    print("\n═══ Open Safeguarding Alerts ═══")
    rows = safeguarding.open_alerts()
    if not rows:
        print("\n  ✓ No open alerts.")
        _pause()
        return
    for alert in rows[:40]:
        print(f"    #{alert.alert_id:<5}{alert.label}")
        if alert.detail:
            print(f"          {alert.detail}")
    unack = safeguarding.unacknowledged()
    if unack:
        print(f"\n  ⚠ {len(unack)} alert(s) nobody has looked at.")
    try:
        if not _yes("\n  Update one? (y/N)"):
            return
        alert_id = _int("Alert #")
        action = _pick_from("Action",
                            ["Acknowledge", "Record what was done", "Close"],
                            default="Acknowledge")
        who = _input("Your name", allow_empty=False)
        if action == "Acknowledge":
            safeguarding.acknowledge(alert_id, by=who)
        elif action == "Record what was done":
            safeguarding.mark_actioned(
                alert_id, by=who, note=_input("What was done",
                                              allow_empty=False))
        else:
            safeguarding.close_alert(
                alert_id, by=who,
                outcome=_input("Outcome", allow_empty=False))
        print("\n  ✓ Updated.")
    except ValueError:
        print("\n  ✗ Alert # must be a number.")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
    except _UserAbort:
        print("\n  Cancelled.")
    _pause()


def sg_cme() -> None:
    print("\n═══ Children Missing Education ═══")
    print("\n  A referral is a serious step, and always a person's")
    print("  decision. This is the list to work through, not act on.")
    candidates = safeguarding.referral_candidates()
    if candidates:
        print(f"\n  {len(candidates)} learner(s) at the referral threshold:")
        for run in candidates:
            print(f"    {run.label}")
    else:
        print("\n  ✓ Nobody at the referral threshold.")
    existing = safeguarding.list_referrals()
    if existing:
        print("\n  Referrals on file:")
        for referral in existing[:15]:
            print(f"    #{referral.referral_id:<5}{referral.student_id:<12}"
                  f"{referral.state:<20}{referral.days_missing} day(s)")
    try:
        if candidates and _yes("\n  Raise a referral? (y/N)"):
            referral = safeguarding.raise_cme_referral(
                _input("Student ID", allow_empty=False),
                raised_by=_input("Raised by", allow_empty=False),
                local_authority=_input("Local authority") or None,
                narrative=_input("Narrative") or None)
            print(f"\n  ✓ Referral #{referral.referral_id} drafted.")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
    except _UserAbort:
        print("\n  Cancelled.")
    _pause()


_SG_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Run the sweep",   sg_sweep),
    ("Open alerts",     sg_open),
    ("CME referrals",   sg_cme),
]


# ═══ Bursary ════════════════════════════════════════════════════════

def bursary_assess() -> None:
    print("\n═══ Assess a Payment Run ═══")
    print("\n  Recommendations only. Nothing is held until somebody says so.")
    try:
        period_from = _input("Period from (YYYY-MM-DD)", allow_empty=False)
        period_to = _input("Period to (YYYY-MM-DD)", default=_today())
        result = bursary.assess(period_from=period_from, period_to=period_to)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except _UserAbort:
        return
    print(f"\n  {result.summary}")
    if result.to_hold:
        print("\n  Recommended holds:")
        for assessment in result.to_hold[:30]:
            print(f"    {assessment.label}")
    try:
        if not _yes("\n  Commit this run? (y/N)"):
            print("\n  Nothing committed.")
            _pause()
            return
        pay_only = _yes("  Commit payments only, leaving holds for review? "
                        "(Y/n)", default="y")
        counts = bursary.apply_run(
            result, decided_by=_input("Decided by", allow_empty=False),
            pay_only=pay_only)
        print(f"\n  ✓ {counts.get(bursary.PAY, 0)} paid, "
              f"{counts.get(bursary.HOLD, 0)} held.")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
    except _UserAbort:
        print("\n  Cancelled.")
    _pause()


def bursary_held() -> None:
    print("\n═══ Held Payments ═══")
    held = bursary.held_payments()
    if not held:
        print("\n  ✓ Nothing held.")
        _pause()
        return
    print(f"\n  £{bursary.held_total():.2f} across {len(held)} payment(s):\n")
    for payment in held[:40]:
        print(f"    #{payment.payment_id:<5}{payment.label}")
    try:
        action = _pick_from("Action", ["Release one", "Release on recovery",
                                       "Nothing"], default="Nothing")
        if action == "Release one":
            bursary.release(_int("Payment #"),
                            released_by=_input("Released by",
                                               allow_empty=False))
            print("\n  ✓ Released.")
        elif action == "Release on recovery":
            released = bursary.release_on_recovery(
                date_from=_input("Measure from (YYYY-MM-DD)",
                                 allow_empty=False),
                date_to=_input("Measure to", default=_today()),
                released_by=_input("Released by", allow_empty=False))
            print(f"\n  ✓ {len(released)} payment(s) released on recovery.")
    except ValueError:
        print("\n  ✗ Payment # must be a number.")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
    except _UserAbort:
        print("\n  Cancelled.")
    _pause()


def bursary_exempt() -> None:
    print("\n═══ Exemptions ═══")
    print("\n  A learner whose attendance is poor because they cannot")
    print("  afford the bus is exactly who should not lose travel money.")
    try:
        student_id = _input("Student ID", allow_empty=False)
        existing = bursary.list_exemptions(student_id=student_id)
        for exemption in existing:
            print(f"    {exemption.reason} from {exemption.start_date}"
                  + (f" to {exemption.end_date}" if exemption.end_date else ""))
        if not _yes("\n  Add an exemption? (y/N)"):
            return
        exemption = bursary.add_exemption(
            student_id,
            reason=_pick_from("Reason", list(bursary.EXEMPTION_REASONS),
                              default="Hardship"),
            detail=_input("Detail (optional)") or None,
            end_date=_input("Until (YYYY-MM-DD, blank = open-ended)") or None,
            granted_by=_input("Granted by") or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    print(f"\n  ✓ Exempt: {exemption.reason}")
    _pause()


def bursary_impact() -> None:
    print("\n═══ Does Holding Money Work? ═══")
    report = bursary.impact_report()
    if not report["holds_reviewed"]:
        print("\n  Not enough released holds to say yet.")
    else:
        print(f"\n  Across {report['holds_reviewed']} released hold(s): "
              f"{report['improved']} improved, {report['worsened']} got worse")
        print(f"  Improvement rate: {report['improvement_rate']}%")
        if (report["improvement_rate"] or 0) < 50:
            print("\n  ⚠ Worth reviewing the policy.")
    _pause()


_BURSARY_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Assess a payment run", bursary_assess),
    ("Held payments",        bursary_held),
    ("Exemptions",           bursary_exempt),
    ("Does it work?",        bursary_impact),
]


# ═══ Rewards ════════════════════════════════════════════════════════

def rewards_nominate() -> None:
    print("\n═══ Nominate Rewards ═══")
    try:
        period_from = _input("From (YYYY-MM-DD)", default=_term_ago())
        period_to = _input("To (YYYY-MM-DD)", default=_today())
        label = _input("Period label (optional)") or None
        result = rewards.nominate(period_from=period_from,
                                  period_to=period_to)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except _UserAbort:
        return
    print(f"\n  {result.summary}")
    for candidate in result.candidates[:40]:
        print(f"    {candidate.label}")
    try:
        if result.candidates and _yes("\n  Record these nominations? (y/N)"):
            stored = rewards.record_all(
                result, period_label=label,
                nominated_by=_input("Nominated by") or None)
            print(f"\n  ✓ {len(stored)} nomination(s) recorded.")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
    except _UserAbort:
        pass
    _pause()


def rewards_confirm() -> None:
    print("\n═══ Confirm Nominations ═══")
    pending = rewards.pending_nominations()
    if not pending:
        print("\n  Nothing waiting.")
        _pause()
        return
    for award in pending[:40]:
        print(f"    #{award.award_id:<5}{award.label}")
    try:
        if _yes("\n  Confirm all? (y/N)"):
            n = rewards.confirm_all(
                awarded_by=_input("Awarded by", allow_empty=False))
            print(f"\n  ✓ {n} award(s) confirmed.")
            if _yes("  Print certificates now? (y/N)"):
                issued = rewards.issue_all(
                    issued_by=_input("Issued by") or None)
                print(f"\n  ✓ {issued} certificate(s) issued.")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
    except _UserAbort:
        print("\n  Cancelled.")
    _pause()


def rewards_honour() -> None:
    print("\n═══ Roll of Honour ═══")
    try:
        period_from = _input("From (YYYY-MM-DD)", default=_term_ago())
        period_to = _input("To (YYYY-MM-DD)", default=_today())
    except _UserAbort:
        return
    roll = rewards.roll_of_honour(period_from=period_from,
                                  period_to=period_to)
    if not roll:
        print("\n  No awards for that period.")
    for kind, awards in roll.items():
        print(f"\n  {kind} ({len(awards)}):")
        for award in awards[:20]:
            print(f"    {award.label}")
    reach = rewards.reach(period_from=period_from, period_to=period_to)
    if reach["awards"]:
        print(f"\n  Reached {reach['learners_rewarded']} of "
              f"{reach['active_learners']} learners ({reach['share']}%)")
        print(f"  {reach['reached_by_improvement']} reached only through "
              "the improvement award.")
    _pause()


_REWARD_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Nominate",        rewards_nominate),
    ("Confirm & print", rewards_confirm),
    ("Roll of honour",  rewards_honour),
]


# ── Submenu plumbing ────────────────────────────────────────────────

def _run_menu(title: str, menu: list[tuple[str, Callable[[], None]]]) -> None:
    while True:
        print(f"\n── {title} ──")
        for i, (label, _) in enumerate(menu, 1):
            print(f"  {i}) {label}")
        print("  0) Back")
        try:
            choice = input("  Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if choice == "0":
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(menu)):
            print("  Invalid selection.")
            continue
        _, handler = menu[int(choice) - 1]
        try:
            handler()
        except _UserAbort:
            print("\n  Cancelled.")
        except Exception as e:
            logger.exception("Intervention CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def cases_menu() -> None:
    _run_menu("Cases, Contracts & Meetings", _CASE_MENU)


def punctuality_menu() -> None:
    _run_menu("Punctuality", _PUNCTUAL_MENU)


def cohorts_menu() -> None:
    _run_menu("Cohorts", _COHORT_MENU)


def safeguarding_menu() -> None:
    _run_menu("Safeguarding", _SG_MENU)


def bursary_menu() -> None:
    _run_menu("Bursary", _BURSARY_MENU)


def rewards_menu() -> None:
    _run_menu("Rewards", _REWARD_MENU)


_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Cases, Contracts & Meetings", cases_menu),
    ("Punctuality",                 punctuality_menu),
    ("Cohorts (persistent absence)", cohorts_menu),
    ("Safeguarding",                safeguarding_menu),
    ("Bursary",                     bursary_menu),
    ("Rewards",                     rewards_menu),
]


def run() -> None:
    _run_menu("Intervention & Pastoral", _MENU)
