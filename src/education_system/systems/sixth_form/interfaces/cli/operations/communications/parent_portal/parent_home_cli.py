"""Parent-facing CLI for the Sixth Form System.

The terminal counterpart of :mod:`.parent_home_gui`, and the same rule
applies: a parent must never reach the staff menu, so the launcher sends
the ``parent`` role here instead of ``cli_main``.

Read-only throughout — there is nothing a parent can change from this
menu except their own password.
"""

from __future__ import annotations

import logging

from education_system.systems.sixth_form import SYSTEM_NAME
from education_system.systems.sixth_form.domain.operations.communications.parent_portal import (
    parent_portal as data,
)

logger = logging.getLogger(__name__)

_RULE = "─" * 72


class _UserAbort(Exception):
    """Ctrl-C / EOF at a prompt — unwind to the menu loop."""


def _input(prompt: str, default: str = "") -> str:
    try:
        raw = input(f"  {prompt}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        raise _UserAbort
    return raw or default


def _pause() -> None:
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


def _fmt(value, dash: str = "—") -> str:
    return dash if value in (None, "") else str(value)


# ── Screens ──────────────────────────────────────────────────────────

def _print_overview(account) -> list[dict]:
    children = data.linked_students(account.account_id)
    print(f"\n  {SYSTEM_NAME} — Parent Portal")
    print(f"  Signed in as {account.full_name} ({account.username})")
    print(f"  {_RULE}")

    if not children:
        print("\n  No students are linked to your account yet.")
        print("  The college office links each parent account to their child's")
        print("  record — please contact them if you were expecting someone here.")
        return []

    print(f"\n  {'#':>3}  {'Student':<28}{'ID':<12}{'Relationship':<16}")
    print("  " + "-" * 62)
    for i, c in enumerate(children, 1):
        print(f"  {i:>3}  {c['full_name'][:26]:<28}{c['student_id']:<12}"
              f"{c['relationship']:<16}")
    return children


def _print_child(account, student_id: str) -> None:
    try:
        d = data.child_detail(account.account_id, student_id)
    except data.ValidationError as exc:
        print(f"\n  ✗ {exc}")
        return
    except Exception:
        logger.exception("Could not build detail for %s", student_id)
        print("\n  This student's information could not be loaded just now.")
        return

    print(f"\n  {_RULE}")
    print(f"  {d['full_name']}  ({d['student_id']} · {d['status']})")
    print(f"  {_RULE}")

    att_pct = d.get("attendance_pct")
    window = (d.get("attendance") or {}).get("days")
    beh = d.get("behaviour_30d") or {}
    print("\n  Attendance     " + ("—" if att_pct is None
                                   else f"{att_pct}%  (last {window} days)"))
    print(f"  Standing       {_fmt(d.get('risk_band'))}")
    print(f"  Behaviour 30d  +{beh.get('positive', 0)} / -{beh.get('negative', 0)}")
    ucas = d.get("ucas")
    if ucas:
        print(f"  UCAS progress  {ucas['percent']}%  "
              f"({ucas['complete']} of {ucas['total']} steps)")

    _print_subjects(d.get("subjects") or [])
    _print_attendance(d.get("attendance") or {})
    _print_behaviour(d.get("behaviour") or [])
    _print_coursework(d.get("coursework"))


def _print_subjects(subjects: list[dict]) -> None:
    if not subjects:
        return
    print("\n  Subjects")
    print(f"  {'Subject':<24}{'Predicted':<11}{'Target':<9}{'Mock':<9}"
          f"{'Forecast':<11}{'On target':<10}")
    print("  " + "-" * 74)
    for s in subjects:
        on_target = ("—" if s.get("on_target") is None
                     else ("yes" if s["on_target"] else "NO"))
        print(f"  {s['subject'][:22]:<24}{_fmt(s.get('predicted')):<11}"
              f"{_fmt(s.get('target')):<9}{_fmt(s.get('latest_mock')):<9}"
              f"{_fmt(s.get('forecast')):<11}{on_target:<10}")


def _print_attendance(att: dict) -> None:
    counts = att.get("counts") or {}
    print(f"\n  Attendance — last {att.get('days', 30)} days")
    if not counts:
        print("    No attendance has been recorded in this period.")
        return
    print("    " + "   ".join(f"{k}: {v}" for k, v in sorted(counts.items())))

    absences = att.get("absences") or []
    if not absences:
        print("    Full attendance — nothing missed.")
        return
    print(f"\n    {'Date':<14}{'Status':<16}{'Minutes late':<14}")
    print("    " + "-" * 44)
    for a in absences[:20]:
        late = a.get("minutes_late")
        print(f"    {a['date']:<14}{a['status']:<16}"
              f"{('—' if late in (None, 0) else str(late)):<14}")
    if len(absences) > 20:
        print(f"    ... and {len(absences) - 20} more")


def _print_behaviour(entries: list[dict]) -> None:
    print("\n  Behaviour record")
    if not entries:
        print("    Nothing recorded.")
        return
    print(f"    {'Date':<13}{'Type':<11}{'Category':<18}{'Pts':>4}  Details")
    print("    " + "-" * 78)
    for e in entries:
        detail = (e.get("description") or "")[:36]
        print(f"    {_fmt(e['date']):<13}{_fmt(e['type']):<11}"
              f"{_fmt(e['category'])[:16]:<18}{e.get('points') or 0:>4}  {detail}")


def _print_coursework(work) -> None:
    if not work:
        return
    print("\n  Coursework")
    summary = work.get("summary")
    if isinstance(summary, dict) and summary:
        print("    " + "   ·   ".join(
            f"{k.replace('_', ' ').capitalize()}: {v}" for k, v in summary.items()))
    recent = work.get("recent") or []
    if not recent:
        print("    Nothing set recently.")
        return
    print(f"\n    {'Assignment':<30}{'Subject':<18}{'Due':<12}{'Status':<14}{'Mark':<10}")
    print("    " + "-" * 84)
    for r in recent:
        marks, max_marks = r.get("marks"), r.get("max_marks")
        if r.get("grade"):
            mark = str(r["grade"])
        elif marks is None:
            mark = "—"
        else:
            mark = f"{marks}/{max_marks}" if max_marks else str(marks)
        print(f"    {_fmt(r.get('title'))[:28]:<30}{_fmt(r.get('subject'))[:16]:<18}"
              f"{_fmt(r.get('due_date')):<12}{_fmt(r.get('state'))[:12]:<14}{mark:<10}")


def _email_portal(account) -> None:
    """Browse everything the college has emailed this parent."""
    if not account.email:
        print("\n  There is no email address on your account, so there is")
        print("  nothing to show here. Contact the college office to add one.")
        return

    while True:
        inbox = data.parent_messages(account.account_id)
        print(f"\n  {_RULE}")
        print(f"  My Email — delivered to {account.email}")
        print(f"  {_RULE}")

        if not inbox:
            print("\n  No email yet. Messages the college sends you will appear")
            print("  here as well as in your own inbox.")
            return

        print(f"\n  {'#':>3}  {'Sent':<18}{'From':<26}{'Subject':<40}")
        print("  " + "-" * 88)
        for i, m in enumerate(inbox, 1):
            sender = (m["from_name"] or m["from_address"] or "—")[:24]
            print(f"  {i:>3}  {(m['sent_at'] or '')[:16]:<18}{sender:<26}"
                  f"{m['subject'][:38]:<40}")

        choice = _input("Open which (number), or Enter to go back")
        if not choice:
            return
        if not (choice.isdigit() and 1 <= int(choice) <= len(inbox)):
            print("\n  Not a valid option.")
            continue
        _print_message(account, inbox[int(choice) - 1]["message_id"])
        _pause()


def _print_message(account, message_id: int) -> None:
    try:
        msg = data.parent_message(account.account_id, message_id)
    except data.ValidationError as exc:
        print(f"\n  ✗ {exc}")
        return
    except Exception:
        logger.exception("Could not open message %s", message_id)
        print("\n  This message could not be opened.")
        return

    sender = msg["from_name"] or msg["from_address"] or "The college"
    print(f"\n  {_RULE}")
    print(f"  {msg['subject']}")
    print(f"  From: {sender}")
    print(f"  Sent: {_fmt(msg['sent_at'])}")
    print(f"  {_RULE}\n")
    for line in (msg["body"] or "").splitlines():
        print(f"  {line}")


def _change_password(auth) -> None:
    from education_system.platform.delivery.cli import change_password_cli
    change_password_cli.run(auth)


# ── Menu loop ────────────────────────────────────────────────────────

def run(auth, account) -> int:
    """Run the parent menu for an already-authenticated parent."""
    while True:
        try:
            children = _print_overview(account)

            print("\n  Options")
            if children:
                print("    1-N  View a student in full")
            print("    e    My email")
            print("    p    Change my password")
            print("    q    Log out")

            choice = _input("Choose").lower()
            if choice in ("q", "quit", "exit", "logout"):
                break
            if choice == "e":
                _email_portal(account)
                _pause()
                continue
            if choice == "p":
                try:
                    _change_password(auth)
                except Exception:
                    logger.exception("Password change failed")
                    print("\n  Password change is unavailable — please contact "
                          "the college office.")
                _pause()
                continue
            if choice.isdigit() and children and 1 <= int(choice) <= len(children):
                _print_child(account, children[int(choice) - 1]["student_id"])
                _pause()
                continue
            if choice:
                print("\n  Not a valid option.")
                _pause()
        except _UserAbort:
            break

    from education_system import switch
    try:
        auth.logout()
    except Exception:
        logger.debug("Logout on the shared session failed", exc_info=True)
    switch.request_logout("cli")
    print("\n  Signed out. Goodbye.\n")
    return 0
