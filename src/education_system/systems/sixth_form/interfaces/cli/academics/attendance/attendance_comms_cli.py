"""CLI flows for chasing and telling people about attendance.

Submenu hung off Attendance: the morning call list, the messages that go
to families, the nudges that go to staff, and the letters home.
"""

from __future__ import annotations

import logging
from datetime import date as _date, timedelta as _timedelta
from typing import Callable

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance_calling as calling,
    attendance_letters as letters,
    attendance_notifications as notifications,
    attendance_nudges as nudges,
)
from education_system.systems.sixth_form.domain.academics.attendance.attendance import (
    ValidationError,
)
from education_system.systems.sixth_form.interfaces.cli.academics.attendance.attendance_cli import (
    _input,
    _pause,
    _pick_from,
    _UserAbort,
)

logger = logging.getLogger(__name__)


def _today() -> str:
    return _date.today().isoformat()


def _week_ago() -> str:
    return (_date.today() - _timedelta(days=7)).isoformat()


def _yes(prompt: str, *, default: str = "n") -> bool:
    return _input(prompt, default=default).lower().startswith("y")


# ═══ First-day calling ══════════════════════════════════════════════

def calls_build() -> None:
    print("\n═══ Build Today's Call List ═══")
    print("\n  Unexplained absence only. Anything already explained — a")
    print("  report, approved leave, a placement — never reaches the list.")
    try:
        date_s = _input("Date (YYYY-MM-DD)", default=_today())
        result = calling.build_list(date=date_s)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except _UserAbort:
        return
    print(f"\n  {result.created} new call(s), {result.already_open} already "
          f"open, {result.skipped_explained} already explained.")
    if result.calls:
        print(f"\n    {'#':>5}  {'Priority':<9}{'Learner':<24}"
              f"{'Number':<16}Why")
        for call in result.calls[:40]:
            print(f"    {call.call_id:>5}  {call.priority:<9}"
                  f"{(call.student_name or call.student_id)[:23]:<24}"
                  f"{(call.contact_number or '—')[:15]:<16}"
                  f"{call.reason or ''}")
    _pause()


def calls_work() -> None:
    print("\n═══ Work the Call List ═══")
    try:
        date_s = _input("Date (YYYY-MM-DD)", default=_today())
    except _UserAbort:
        return
    queue = calling.call_list(date=date_s)
    if not queue:
        print("\n  ✓ Nothing outstanding. Build the list first if needed.")
        _pause()
        return

    marshal = None
    try:
        marshal = _input("Your name") or None
        for call in queue:
            print(f"\n  [{call.priority}] "
                  f"{call.student_name or call.student_id}")
            print(f"    {call.reason or ''}")
            print(f"    Ring: {call.contact_name or '?'} "
                  f"{call.contact_number or '(no number held)'}")
            raw = _input("  Outcome (Enter to skip, 'stop' to finish)",
                         default="")
            if not raw:
                continue
            if raw.lower() == "stop":
                break
            outcome = _pick_from("Outcome", list(calling.OUTCOMES),
                                 default=calling.NO_ANSWER)
            notes = _input("  Notes (optional)") or None
            if outcome in calling.CONTACT_MADE and notes:
                calling.record_explanation(call.call_id, reason_text=notes,
                                           called_by=marshal)
                print("    ✓ Logged, and filed as an absence report.")
            else:
                updated = calling.log_call(call.call_id, outcome,
                                           called_by=marshal, notes=notes)
                print(f"    ✓ {updated.state}")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
    except _UserAbort:
        print("\n  Stopped.")
    stats = calling.stats(date=date_s)
    print(f"\n  {stats.total} call(s): {stats.done} done, "
          f"{stats.open} outstanding, {stats.unreachable} unreachable "
          f"({stats.completion_rate or 0:.0f}% complete)")
    _pause()


def calls_unreachable() -> None:
    print("\n═══ Learners Nobody Could Reach ═══")
    print("\n  Repeated appearances here are a safeguarding matter long")
    print("  before they are an attendance one.")
    repeats = calling.repeat_unreachable()
    if not repeats:
        print("\n  ✓ Nobody appearing repeatedly.")
    else:
        for student_id, count in repeats:
            print(f"    {student_id:<14}unreachable {count} time(s) "
                  "in the last 30 days")
    breakdown = calling.outcome_breakdown(date_from=_week_ago())
    if breakdown:
        print("\n  Call outcomes this week:")
        for outcome, n in sorted(breakdown.items(), key=lambda kv: -kv[1]):
            print(f"    {outcome:<24}{n:>5}")
    _pause()


_CALL_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Build today's list", calls_build),
    ("Work the list",      calls_work),
    ("Unreachable learners", calls_unreachable),
]


# ═══ Notifications ══════════════════════════════════════════════════

def notify_absence() -> None:
    print("\n═══ Queue Same-Day Absence Alerts ═══")
    print("\n  One message per learner, not one per lesson.")
    try:
        date_s = _input("Date (YYYY-MM-DD)", default=_today())
        channel = _pick_from("Channel", list(notifications.CHANNELS),
                             default=notifications.SMS)
        result = notifications.queue_absence_alerts(date=date_s,
                                                    channel=channel)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except _UserAbort:
        return
    print(f"\n  {result.summary}")
    if result.no_recipient:
        print(f"\n  ⚠ No contact details for: "
              f"{', '.join(result.no_recipient[:10])}")
    print("\n  Nothing has been sent — use 'Send the queue'.")
    _pause()


def notify_statements() -> None:
    print("\n═══ Queue Weekly Statements ═══")
    print("\n  Dull by design. A message that only arrives when something")
    print("  is wrong is a letter; one that arrives every Friday is")
    print("  information.")
    try:
        date_s = _input("Any date in the week", default=_today())
        channel = _pick_from("Channel", list(notifications.CHANNELS),
                             default=notifications.EMAIL)
        also_student = _yes("Send to the learner as well? (Y/n)", default="y")
        result = notifications.queue_weekly_statements(
            date=date_s, channel=channel, also_student=also_student)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except _UserAbort:
        return
    print(f"\n  {result.summary}")
    _pause()


def notify_queue() -> None:
    print("\n═══ Notification Queue ═══")
    pending = notifications.list_notifications(state=notifications.QUEUED,
                                               limit=50)
    print(f"\n  {notifications.pending_count()} message(s) queued.")
    for message in pending[:25]:
        print(f"    {message.kind:<20}"
              f"{(message.recipient_name or message.recipient or '?')[:26]:<28}"
              f"{message.channel}")
    if not pending:
        _pause()
        return
    try:
        if _yes("\n  Preview one? (y/N)"):
            print("\n" + "-" * 60)
            print(pending[0].body)
            print("-" * 60)
        if _yes("\n  Cancel the whole queue? (y/N)"):
            n = notifications.cancel_queued()
            print(f"\n  ✓ {n} message(s) cancelled.")
    except _UserAbort:
        pass
    _pause()


def notify_send() -> None:
    print("\n═══ Send the Queue ═══")
    print(f"\n  {notifications.pending_count()} message(s) waiting.")
    try:
        if not _yes("  Send now? (y/N)"):
            print("\n  Nothing sent.")
            _pause()
            return
        result = notifications.dispatch_due()
    except _UserAbort:
        return
    print(f"\n  ✓ {result.sent} sent, {result.failed} failed.")
    for error in result.errors[:10]:
        print(f"    ✗ {error}")
    _pause()


def notify_unreachable() -> None:
    print("\n═══ Learners With No Contact Route ═══")
    print("\n  No usable number, no email, no guardian receiving")
    print("  communications. Worth fixing before something is urgent.")
    rows = notifications.unreachable_learners()
    if not rows:
        print("\n  ✓ Everybody is contactable.")
    else:
        print(f"\n  {len(rows)} learner(s):")
        for student_id in rows[:50]:
            print(f"    {student_id}")
    _pause()


_NOTIFY_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Queue absence alerts",   notify_absence),
    ("Queue weekly statements", notify_statements),
    ("Review the queue",       notify_queue),
    ("Send the queue",         notify_send),
    ("Unreachable learners",   notify_unreachable),
]


# ═══ Register nudges ════════════════════════════════════════════════

def nudge_sweep() -> None:
    print("\n═══ Chase Missing Registers ═══")
    print("\n  Raises nudges, escalates old ones, and closes any register")
    print("  that has since been taken.")
    try:
        notify = _yes("Send digests as well? (y/N)")
        result = nudges.sweep(notify=notify)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except _UserAbort:
        return
    print(f"\n  {result.summary}")
    _pause()


def nudge_outstanding() -> None:
    print("\n═══ Outstanding Registers ═══")
    for stage in nudges.STAGES:
        count = nudges.open_count(stage=stage)
        if count:
            print(f"\n  {stage}: {count}")
    sheet = nudges.chase_sheet()
    if not sheet:
        print("\n  ✓ Nothing outstanding.")
        _pause()
        return
    print()
    for line in sheet[:60]:
        print(f"  {line}")
    _pause()


def nudge_offenders() -> None:
    print("\n═══ Who Is Missing Registers ═══")
    print("\n  For a conversation about workload as often as about")
    print("  diligence — but the conversation is easier with a number.")
    people = nudges.worst_offenders()
    slots = nudges.slot_offenders()
    if people:
        print(f"\n  {'Person':<28}Missing")
        for owner, count in people[:15]:
            print(f"    {owner[:26]:<28}{count}")
    if slots:
        print(f"\n  {'Slot':<12}Missing")
        for slot_id, count in slots[:15]:
            print(f"    #{slot_id:<11}{count}")
    if not (people or slots):
        print("\n  ✓ Nothing to report.")
    _pause()


_NUDGE_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Run the chase sweep",  nudge_sweep),
    ("Outstanding registers", nudge_outstanding),
    ("Who is missing them",  nudge_offenders),
]


# ═══ Letters ════════════════════════════════════════════════════════

def letters_due() -> None:
    print("\n═══ Letters Due ═══")
    print("\n  The ladder only climbs: a learner who had letter 2 does not")
    print("  get it again, they get letter 3 or nothing.")
    try:
        window = _input("Window (days)", default="42")
        candidates = letters.due(window_days=int(window))
    except ValueError:
        print("\n  ✗ Window must be a number.")
        _pause()
        return
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except _UserAbort:
        return
    if not candidates:
        print("\n  ✓ Nobody has earned a letter they have not had.")
        _pause()
        return
    print(f"\n  {len(candidates)} letter(s) due:\n")
    print(f"    {'Learner':<24}{'Stage':<9}{'%':>7}  Previously")
    for candidate in candidates[:40]:
        print(f"    {(candidate.student_name or candidate.student_id)[:23]:<24}"
              f"{candidate.stage_number:<9}{candidate.percentage:>6.1f}%  "
              f"{candidate.highest_sent or 'none'}")
    try:
        if not _yes("\n  Draft them now? (y/N)"):
            return
        result = letters.run(
            window_days=int(window),
            sender_name=_input("Signed by") or None,
            sender_role=_input("Role") or None,
            sender_contact=_input("Contact") or None)
    except (ValidationError, ValueError) as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except _UserAbort:
        return
    print(f"\n  ✓ {result.summary}")
    print("    Read them before issuing — Drafts, below.")
    _pause()


def letters_drafts() -> None:
    print("\n═══ Draft Letters ═══")
    drafts = letters.list_letters(state=letters.DRAFT)
    if not drafts:
        print("\n  No drafts waiting.")
        _pause()
        return
    for letter in drafts[:30]:
        print(f"    #{letter.letter_id:<5}{letter.label:<40}"
              f"{letter.recipient or '(no email)'}")
    try:
        if _yes("\n  Read one? (y/N)"):
            letter_id = int(_input("Letter #", allow_empty=False))
            letter = letters.get_letter(letter_id)
            if letter:
                print("\n" + "-" * 68)
                print(letter.subject)
                print("-" * 68)
                print(letter.body)
                print("-" * 68)
        if _yes("\n  Issue all drafts? (y/N)"):
            send = _yes("  Email them as well? (y/N)")
            n = letters.issue_all(issued_by=_input("Issued by") or None,
                                  send=send)
            print(f"\n  ✓ {n} letter(s) issued.")
    except ValueError:
        print("\n  ✗ Letter # must be a number.")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
    except _UserAbort:
        print("\n  Cancelled.")
    _pause()


def letters_templates() -> None:
    print("\n═══ Letter Templates ═══")
    for template in letters.list_templates():
        print(f"\n  {template.name} ({template.stage_key})")
        print(f"    Subject: {template.subject}")
        print(f"    Placeholders: {', '.join(sorted(template.placeholders))}")
    counts = letters.stage_counts()
    if any(counts.values()):
        print("\n  Issued this year: "
              + ", ".join(f"{k}={v}" for k, v in counts.items()))
    _pause()


_LETTER_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Letters due / draft", letters_due),
    ("Drafts / issue",      letters_drafts),
    ("Templates",           letters_templates),
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
            logger.exception("Comms CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def calling_menu() -> None:
    _run_menu("First-Day Calling", _CALL_MENU)


def notifications_menu() -> None:
    _run_menu("Notifications", _NOTIFY_MENU)


def nudges_menu() -> None:
    _run_menu("Register Nudges", _NUDGE_MENU)


def letters_menu() -> None:
    _run_menu("Attendance Letters", _LETTER_MENU)


_MENU: list[tuple[str, Callable[[], None]]] = [
    ("First-Day Calling",  calling_menu),
    ("Notifications",      notifications_menu),
    ("Register Nudges",    nudges_menu),
    ("Attendance Letters", letters_menu),
]


def run() -> None:
    _run_menu("Chasing & Communications", _MENU)
