"""CLI flows for absence intake and approval.

Submenu hung off Attendance, over the five ways an absence becomes
explained: a report from home, a learner's self-certification, a planned
leave request, the evidence behind it, and an appeal against a mark.
"""

from __future__ import annotations

import logging
from datetime import date as _date, timedelta as _timedelta
from typing import Callable

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance_absence_reports as reports,
    attendance_appeals as appeals,
    attendance_evidence as evidence,
    attendance_leave as leave,
)
from education_system.systems.sixth_form.domain.academics.attendance.attendance import (
    ValidationError,
)
from education_system.systems.sixth_form.domain.academics.attendance.attendance_cli import (
    _input,
    _pause,
    _pick_from,
    _UserAbort,
)

logger = logging.getLogger(__name__)


def _today() -> str:
    return _date.today().isoformat()


def _month_ago() -> str:
    return (_date.today() - _timedelta(days=30)).isoformat()


def _yes(prompt: str, *, default: str = "n") -> bool:
    return _input(prompt, default=default).lower().startswith("y")


def _int(prompt: str) -> int:
    return int(_input(prompt, allow_empty=False))


# ═══ Absence reports ════════════════════════════════════════════════

def report_take() -> None:
    print("\n═══ Take an Absence Report ═══")
    print("\n  Somebody has rung in. This records the claim; coding it is")
    print("  a separate decision made from the queue.")
    try:
        student_id = _input("Student ID", allow_empty=False)
        date_from = _input("Absent from (YYYY-MM-DD)", default=_today())
        date_to = _input("Absent to (blank = same day)") or None
        channel = _pick_from("How did it arrive", list(reports.CHANNELS),
                             default=reports.PHONE)
        who = _pick_from("Who reported it", list(reports.REPORTERS),
                         default=reports.PARENT)
        name = _input("Reporter name (optional)") or None
        reason = _input("Reason given") or None
        message = _input("Anything else they said (optional)") or None
        report = reports.report_absence(
            student_id, date_from, date_to=date_to, channel=channel,
            reported_by=who, reporter_name=name, reason_text=reason,
            message=message)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    print(f"\n  ✓ #{report.report_id} logged: {report.label}")
    print("    It is waiting in the queue to be coded.")
    _pause()


def report_queue() -> None:
    print("\n═══ Absence Report Queue ═══")
    queue = reports.queue()
    if not queue:
        print("\n  ✓ Nothing waiting.")
        _pause()
        return
    print(f"\n  {len(queue)} report(s) waiting:\n")
    print(f"    {'#':>5}  {'Dates':<24}{'Learner':<24}{'Via':<10}Reason")
    for report in queue[:40]:
        print(f"    {report.report_id:>5}  {report.span:<24}"
              f"{(report.student_name or report.student_id)[:23]:<24}"
              f"{report.channel:<10}{report.reason_text or '—'}")
    if len(queue) > 40:
        print(f"    … and {len(queue) - 40} more.")

    try:
        if not _yes("\n  Decide one now? (y/N)"):
            return
        report_id = _int("Report #")
        accept = _yes("Accept it? (Y/n)", default="y")
        if accept:
            code = _input("Code to apply", default=reports.DEFAULT_ACCEPT_CODE)
            who = _input("Decided by") or None
            result = reports.accept(report_id, code=code, decided_by=who)
            print(f"\n  ✓ {result.marks_written} mark(s) written across "
                  f"{len(result.dates)} day(s).")
            if result.skipped:
                print(f"    {len(result.skipped)} day(s) skipped "
                      "(closed, or no lessons).")
        else:
            reason = _input("Why is it not accepted?", allow_empty=False)
            reports.reject(report_id, reason=reason,
                           decided_by=_input("Decided by") or None)
            print("\n  ✓ Rejected, and the reason recorded.")
    except ValueError:
        print("\n  ✗ Report # must be a number.")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
    except _UserAbort:
        print("\n  Cancelled.")
    _pause()


def report_self_certify() -> None:
    print("\n═══ Self-Certification ═══")
    print("\n  A learner declares their own absence. Coded immediately,")
    print("  and capped per term.")
    try:
        student_id = _input("Student ID", allow_empty=False)
        status = reports.self_cert_status(student_id)
        print(f"\n  {status.label} — {status.remaining} day(s) left.")
        if status.exhausted:
            print("\n  ✗ Cap reached. This needs authorising by staff.")
            _pause()
            return
        date_from = _input("Absent from (YYYY-MM-DD)", default=_today())
        date_to = _input("Absent to (blank = same day)") or None
        reason = _input("Reason", default="Illness")
        report = reports.self_certify(student_id, date_from,
                                      date_to=date_to, reason_text=reason)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    print(f"\n  ✓ Self-certified and coded ({report.days} day(s)).")
    _pause()


def report_channels() -> None:
    print("\n═══ How Reports Arrive ═══")
    try:
        date_from = _input("From (YYYY-MM-DD)", default=_month_ago())
        date_to = _input("To (YYYY-MM-DD)", default=_today())
    except _UserAbort:
        return
    breakdown = reports.channel_breakdown(date_from=date_from,
                                          date_to=date_to)
    if not breakdown:
        print("\n  No reports in that window.")
    else:
        total = sum(breakdown.values())
        print()
        for channel, n in sorted(breakdown.items(), key=lambda kv: -kv[1]):
            print(f"    {channel:<14}{n:>5}  ({100.0 * n / total:.0f}%)")
    heavy = reports.self_certification_report(date_from=date_from,
                                              date_to=date_to)
    if heavy:
        print(f"\n  {len(heavy)} learner(s) have self-certified:")
        for status in heavy[:15]:
            flag = "  ← at cap" if status.exhausted else ""
            print(f"    {status.student_id:<12}{status.label}{flag}")
    _pause()


_REPORT_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Take a report",        report_take),
    ("Queue / decide",       report_queue),
    ("Self-certification",   report_self_certify),
    ("How reports arrive",   report_channels),
]


# ═══ Leave ══════════════════════════════════════════════════════════

def leave_request() -> None:
    print("\n═══ Request Planned Leave ═══")
    try:
        student_id = _input("Student ID", allow_empty=False)
        kind = _pick_from("Kind", list(leave.KINDS),
                          default=leave.DEFAULT_KIND)
        print(f"\n  {leave.describe_kind(kind)}")
        date_from = _input("From (YYYY-MM-DD)", allow_empty=False)
        date_to = _input("To (blank = same day)") or None
        detail = _input("Detail (optional)") or None
        destination = _input("Where (optional)") or None
        request = leave.request_leave(
            student_id, date_from, date_to=date_to, kind=kind, detail=detail,
            destination=destination,
            requested_by=_input("Requested by") or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    print(f"\n  ✓ #{request.request_id}: {request.label}")
    if request.short_notice:
        print(f"    ⚠ {request.notice_days} day(s) notice — the college "
              f"asks for {leave.NOTICE_DAYS}.")
    allowance = leave.leave_used(student_id)
    if request.counts_against_allowance:
        print(f"    Discretionary leave used this year: "
              f"{allowance.used_days}/{allowance.allowance} day(s).")
    _pause()


def leave_pending() -> None:
    print("\n═══ Leave Requests Awaiting a Decision ═══")
    pending = leave.pending()
    if not pending:
        print("\n  ✓ Nothing waiting.")
        _pause()
        return
    print(f"\n    {'#':>5}  {'Dates':<24}{'Learner':<22}{'Kind':<22}Notice")
    for request in pending:
        notice = ("—" if request.notice_days is None
                  else f"{request.notice_days}d")
        flag = " ⚠" if request.short_notice else ""
        print(f"    {request.request_id:>5}  {request.span:<24}"
              f"{(request.student_name or request.student_id)[:21]:<22}"
              f"{request.kind[:21]:<22}{notice}{flag}")

    try:
        if not _yes("\n  Decide one now? (y/N)"):
            return
        request_id = _int("Request #")
        clashes = leave.clashes(request_id)
        if clashes:
            print("\n  ⚠ Already in the diary:")
            for clash in clashes:
                print(f"      {clash.label}")
        if _yes("  Approve it? (Y/n)", default="y"):
            who = _input("Approved by", allow_empty=False)
            ignore = bool(clashes) and _yes("  Approve over the clash? (y/N)")
            result = leave.approve(request_id, decided_by=who,
                                   ignore_clashes=ignore)
            print(f"\n  ✓ Approved: {result.marks_written} mark(s) written.")
        else:
            leave.decline(request_id,
                          reason=_input("Reason", allow_empty=False),
                          decided_by=_input("Decided by") or None)
            print("\n  ✓ Declined.")
    except ValueError:
        print("\n  ✗ Request # must be a number.")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
    except _UserAbort:
        print("\n  Cancelled.")
    _pause()


def leave_upcoming() -> None:
    print("\n═══ Upcoming Approved Leave ═══")
    try:
        days = _int_default("Look ahead (days)", 14)
    except _UserAbort:
        return
    rows = leave.upcoming(days=days)
    if not rows:
        print("\n  Nothing approved in that window.")
    else:
        for request in rows:
            print(f"    {request.span:<24}{request.student_id:<12}"
                  f"{request.kind}")
    breakdown = leave.kind_breakdown()
    if breakdown:
        print("\n  Days approved this year by kind:")
        for kind, days_used in sorted(breakdown.items(),
                                      key=lambda kv: -kv[1]):
            print(f"    {kind:<26}{days_used:>4}")
    _pause()


def _int_default(prompt: str, default: int) -> int:
    raw = _input(prompt, default=str(default))
    try:
        return int(raw)
    except ValueError:
        return default


_LEAVE_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Request leave",   leave_request),
    ("Awaiting decision", leave_pending),
    ("Upcoming leave",  leave_upcoming),
]


# ═══ Evidence ═══════════════════════════════════════════════════════

def evidence_record() -> None:
    print("\n═══ Record Evidence ═══")
    print("\n  'Sighted' is the honest answer for a card handed over the")
    print("  counter and given straight back.")
    try:
        student_id = _input("Student ID", allow_empty=False)
        kind = _pick_from("Kind", list(evidence.EVIDENCE_KINDS),
                          default=evidence.FIT_NOTE)
        custody = _pick_from("Held or sighted", list(evidence.CUSTODY),
                             default=evidence.SIGHTED)
        covers_from = _input("Covers from (YYYY-MM-DD, optional)") or None
        covers_to = _input("Covers to (optional)") or None
        description = _input("Description (optional)") or None
        received_by = _input("Received by") or None
        record_id = _input("Attach to record ID (optional)") or None
        item = evidence.record_evidence(
            student_id, kind=kind, custody=custody,
            record_id=int(record_id) if record_id else None,
            covers_from=covers_from, covers_to=covers_to,
            description=description, received_by=received_by)
    except ValueError:
        print("\n  ✗ Record ID must be a number.")
        _pause()
        return
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    print(f"\n  ✓ #{item.evidence_id}: {item.label}")
    _pause()


def evidence_outstanding() -> None:
    print("\n═══ Evidence Outstanding ═══")
    rows = evidence.outstanding()
    if not rows:
        print("\n  ✓ Nothing outstanding.")
        _pause()
        return
    print(f"\n  {len(rows)} promise(s) of evidence:\n")
    print(f"    {'#':>5}  {'Absence':<12}{'Learner':<22}{'Due':<12}Status")
    for requirement in rows[:40]:
        status = ("OVERDUE" if requirement.is_overdue()
                  else f"{requirement.days_left()}d left")
        print(f"    {requirement.requirement_id:>5}  {requirement.date:<12}"
              f"{(requirement.student_name or requirement.student_id)[:21]:<22}"
              f"{requirement.due_on:<12}{status}")
    overdue = [r for r in rows if r.is_overdue()]
    if overdue:
        print(f"\n  ⚠ {len(overdue)} overdue.")
    _pause()


def evidence_enforce() -> None:
    print("\n═══ Enforce Overdue Evidence ═══")
    print("\n  Recodes marks whose promised evidence never arrived. A")
    print("  college that asks for evidence and never checks has no policy.")
    try:
        preview = evidence.enforce_overdue(dry_run=True)
        print(f"\n  {preview.checked} overdue requirement(s); "
              f"{preview.recoded} would be recoded to "
              f"{evidence.UNMET_CODE}.")
        if not preview.checked:
            _pause()
            return
        for requirement in preview.requirements[:20]:
            print(f"    {requirement.label}")
        if not _yes("\n  Apply? (y/N)"):
            print("\n  Nothing changed.")
            _pause()
            return
        result = evidence.enforce_overdue(
            dry_run=False, actor=_input("Actioned by") or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    print(f"\n  ✓ {result.recoded} mark(s) recoded.")
    for failure in result.failed[:10]:
        print(f"    ✗ {failure}")
    _pause()


_EVIDENCE_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Record evidence",         evidence_record),
    ("Outstanding",             evidence_outstanding),
    ("Enforce overdue",         evidence_enforce),
]


# ═══ Appeals ════════════════════════════════════════════════════════

def appeal_lodge() -> None:
    print("\n═══ Lodge an Appeal ═══")
    try:
        record_id = _int("Attendance record ID")
        grounds = _pick_from("Grounds", list(appeals.GROUNDS),
                             default=appeals.WAS_PRESENT)
        statement = _input("What the learner says") or None
        appeal = appeals.lodge(record_id, grounds=grounds,
                               statement=statement,
                               submitted_by=_input("Lodged by") or None)
    except ValueError:
        print("\n  ✗ Record ID must be a number.")
        _pause()
        return
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    print(f"\n  ✓ #{appeal.appeal_id}: {appeal.label}")
    print(f"    Assigned to {appeal.assigned_to or 'nobody yet'}.")
    _pause()


def appeal_queue() -> None:
    print("\n═══ Appeals Awaiting a Decision ═══")
    queue = appeals.queue()
    if not queue:
        print("\n  ✓ Nothing waiting.")
        _pause()
        return
    print(f"\n    {'#':>5}  {'Date':<12}{'Learner':<22}{'Grounds':<26}Waiting")
    for appeal in queue:
        print(f"    {appeal.appeal_id:>5}  {appeal.date:<12}"
              f"{(appeal.student_name or appeal.student_id)[:21]:<22}"
              f"{appeal.grounds[:25]:<26}{appeal.days_waiting}d")
    try:
        if not _yes("\n  Decide one now? (y/N)"):
            return
        appeal_id = _int("Appeal #")
        if _yes("  Uphold it? (y/N)"):
            who = _input("Decided by", allow_empty=False)
            code = _input("Code to apply (blank = derive from grounds)") or None
            out = appeals.uphold(appeal_id, decided_by=who, code=code,
                                 note=_input("Note (optional)") or None)
            print(f"\n  ✓ Upheld; mark recoded to {out.outcome_code}.")
        else:
            appeals.reject(appeal_id,
                           decided_by=_input("Decided by", allow_empty=False),
                           reason=_input("Reason", allow_empty=False))
            print("\n  ✓ Rejected, and the reason recorded.")
    except ValueError:
        print("\n  ✗ Appeal # must be a number.")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
    except _UserAbort:
        print("\n  Cancelled.")
    _pause()


def appeal_stats() -> None:
    print("\n═══ Appeal Statistics ═══")
    print("\n  A high upheld rate is not a compliment to the appeals")
    print("  process — it says the marks being appealed were wrong.")
    stats = appeals.stats()
    print(f"\n  {stats.total} appeal(s): {stats.upheld} upheld, "
          f"{stats.rejected} rejected, {stats.open} open.")
    rate = stats.upheld_rate
    print(f"  Upheld rate: {'—' if rate is None else f'{rate:.1f}%'}")
    worst = appeals.by_slot()
    if worst:
        print("\n  Slots attracting successful appeals:")
        for slot_id, entry in worst[:10]:
            print(f"    slot #{slot_id:<5} {entry.total} appeal(s), "
                  f"{entry.upheld_rate or 0:.0f}% upheld")
    overdue = appeals.overdue()
    if overdue:
        print(f"\n  ⚠ {len(overdue)} appeal(s) unanswered for over 5 days.")
    _pause()


_APPEAL_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Lodge an appeal",  appeal_lodge),
    ("Queue / decide",   appeal_queue),
    ("Statistics",       appeal_stats),
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
            logger.exception("Absence CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def reports_menu() -> None:
    _run_menu("Absence Reports", _REPORT_MENU)


def leave_menu() -> None:
    _run_menu("Planned Leave", _LEAVE_MENU)


def evidence_menu() -> None:
    _run_menu("Evidence", _EVIDENCE_MENU)


def appeals_menu() -> None:
    _run_menu("Appeals", _APPEAL_MENU)


_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Absence Reports & Self-Certification", reports_menu),
    ("Planned Leave", leave_menu),
    ("Evidence",      evidence_menu),
    ("Appeals",       appeals_menu),
]


def run() -> None:
    _run_menu("Absence Intake & Approval", _MENU)
