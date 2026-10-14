"""CLI flow for Transition to School (Nursery System)."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.systems.nursery.domain.progression.transitions import (
    transitions as data,
)
from education_system.systems.nursery.domain.progression.transitions.transitions import (
    STATUSES,
    ValidationError,
)

logger = logging.getLogger(__name__)


def _prompt(msg: str) -> str:
    try:
        return input(msg).strip()
    except (EOFError, KeyboardInterrupt):
        return ""


def _safe(func: Callable[..., None]) -> Callable[..., None]:
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValidationError as e:
            print(f"  Validation error: {e}")
        except Exception as e:  # noqa: BLE001
            logger.exception("%s failed", func.__name__)
            print(f"  Error: {e}")
            print("  See logs for details.")
    return wrapper


def _yn(v: bool) -> str:
    return "Yes" if v else "No"


def _print_table(rows: list[data.Transition]) -> None:
    if not rows:
        print("  (no transitions)")
        return
    print(f"  {'ID':<8} {'Child':<22} {'Destination school':<26} "
          f"{'Start':<12} {'Report':<7} {'Status'}")
    print(f"  {'-'*8} {'-'*22} {'-'*26} {'-'*12} {'-'*7} {'-'*11}")
    for t in rows:
        print(f"  {t.transition_id:<8} {(t.child_name or '-')[:22]:<22} "
              f"{(t.destination_school or '-')[:26]:<26} "
              f"{(t.expected_start or '-'):<12} "
              f"{_yn(t.transition_report_sent):<7} {t.status}")


def _print_detail(t: data.Transition) -> None:
    print(f"\n  ── Transition {t.transition_id} ──")
    print(f"  Child:             {t.child_name or '-'} ({t.pupil_id})")
    print(f"  Room:              {t.room or '-'}")
    print(f"  Destination:       {t.destination_school or '-'}")
    print(f"  Expected start:    {t.expected_start or '-'}")
    print(f"  Report sent:       {_yn(t.transition_report_sent)}"
          f" ({t.report_sent_date or '-'})")
    print(f"  Teacher visit:     {_yn(t.teacher_visit)}")
    print(f"  Activities:        {t.activities or '-'}")
    print(f"  Status:            {t.status}")
    print(f"  Notes:             {t.notes or '-'}")


def _show_children() -> None:
    try:
        choices = data.list_pupil_choices()
    except Exception:
        logger.exception("Could not load child choices")
        return
    if choices:
        print("  Children:")
        for _id, label in choices:
            print(f"    {label}")


def _collect_fields(existing: data.Transition | None = None,
                    *, pupil_id: str | None = None) -> dict[str, str]:
    def ask(label: str, current=None) -> str:
        cur = "" if current is None else str(current)
        suffix = f" [{cur}]" if cur else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else cur

    def ask_yn(label: str, current: bool | None) -> str:
        cur = ("y" if current else "n") if current is not None else None
        return ask(label + " (y/n)", cur)

    fields: dict[str, str] = {}
    if pupil_id is not None:
        fields["pupil_id"] = pupil_id
    fields["destination_school"] = ask("Destination school",
                                       existing.destination_school if existing else None)
    fields["expected_start"]     = ask("Expected start (YYYY-MM-DD)",
                                       existing.expected_start if existing else None)
    fields["transition_report_sent"] = ask_yn(
        "Transition report sent?",
        existing.transition_report_sent if existing else None)
    fields["report_sent_date"]   = ask("Report sent date (YYYY-MM-DD)",
                                       existing.report_sent_date if existing else None)
    fields["teacher_visit"]      = ask_yn(
        "Reception teacher visit done?",
        existing.teacher_visit if existing else None)
    fields["activities"]         = ask("Transition activities",
                                       existing.activities if existing else None)
    fields["notes"]              = ask("Notes", existing.notes if existing else None)
    if existing is not None:
        fields["status"] = ask(f"Status ({'/'.join(STATUSES)})", existing.status)
    return fields


@_safe
def open_manager() -> None:
    logger.debug("CLI: transitions open_manager")
    while True:
        counts = data.counts_by_status()
        print("\n  ── Transition to School ──")
        if counts:
            print("  Totals: " + "  ".join(
                f"{k}={v}" for k, v in sorted(counts.items())))
        _print_table(data.list_transitions())
        print("\n   A) Add    V) View    E) Edit    D) Delete")
        print("   S) Set status    N) Notify schools (email transfer details)")
        print("   0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in ("0", ""):
            return
        if choice == "a":
            open_add()
        elif choice == "n":
            open_notify()
        elif choice == "v":
            tid = _prompt("  Transition ID: ")
            t = data.get_transition(tid)
            if t is None:
                print("  No transition with that ID.")
            else:
                _print_detail(t)
                _prompt("  Press Enter to continue...")
        elif choice == "e":
            open_edit()
        elif choice == "d":
            open_delete()
        elif choice == "s":
            open_set_status()
        else:
            print("  Invalid selection.")


@_safe
def open_add() -> None:
    print("\n  ── Add Transition ──")
    _show_children()
    pid = _prompt("  Child ID: ")
    if not pid:
        print("  Cancelled.")
        return
    fields = _collect_fields(pupil_id=pid)
    t = data.create_transition(fields)
    print(f"\n  Created transition {t.transition_id} for {t.child_name} "
          f"→ {t.destination_school or '(school TBC)'}.")


@_safe
def open_edit() -> None:
    tid = _prompt("  Transition ID: ")
    if not tid:
        print("  Cancelled.")
        return
    existing = data.get_transition(tid)
    if existing is None:
        print("  No transition with that ID.")
        return
    print("  Press Enter to keep the existing value.")
    fields = _collect_fields(existing)
    t = data.update_transition(tid, fields)
    print(f"\n  Updated transition {t.transition_id}.")


@_safe
def open_delete() -> None:
    tid = _prompt("  Transition ID to delete: ")
    if not tid:
        print("  Cancelled.")
        return
    if data.get_transition(tid) is None:
        print("  No transition with that ID.")
        return
    if _prompt(f"  Delete transition {tid}? (y/N): ").lower() != "y":
        print("  Cancelled.")
        return
    if data.delete_transition(tid):
        print(f"  Deleted transition {tid}.")
    else:
        print("  Could not delete (already removed?).")


@_safe
def open_set_status() -> None:
    tid = _prompt("  Transition ID: ")
    if not tid:
        print("  Cancelled.")
        return
    if data.get_transition(tid) is None:
        print("  No transition with that ID.")
        return
    status = _prompt(f"  New status ({'/'.join(STATUSES)}): ").lower()
    t = data.set_status(tid, status)
    print(f"  Transition {t.transition_id} is now {t.status}.")


@_safe
def open_notify() -> None:
    """Send the transfer details to both the nursery admin and primary school."""
    tid = _prompt("  Transition ID: ")
    if not tid:
        print("  Cancelled.")
        return
    t = data.get_transition(tid)
    if t is None:
        print("  No transition with that ID.")
        return
    if not t.destination_school:
        print("  Add the destination primary school before sending "
              "(use Edit).")
        return

    print(f"\n  Sending transfer details for {t.child_name or t.pupil_id} "
          f"→ {t.destination_school}.")
    nursery_admin_name = _prompt("  Nursery admin name [Nursery Admin]: ") \
        or "Nursery Admin"
    nursery_admin_email = _prompt("  Nursery admin email: ")
    primary_school_name = _prompt(
        f"  Primary school contact name [{t.destination_school}]: ") \
        or t.destination_school
    primary_school_email = _prompt("  Primary school email: ")
    if not nursery_admin_email or not primary_school_email:
        print("  Both email addresses are required — cancelled.")
        return

    msgs = data.notify_transfer(
        tid,
        nursery_admin_name=nursery_admin_name,
        nursery_admin_email=nursery_admin_email,
        primary_school_name=primary_school_name,
        primary_school_email=primary_school_email,
    )
    print(f"  Sent {len(msgs)} notification(s):")
    for m in msgs:
        print(f"    {m.message_id} → {m.to_name} <{m.to_address}>")


_DISPATCH = {"Transition to School": open_manager}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching transitions CLI label: %s", label)
    handler()
    return True


def run(auth=None) -> None:
    open_manager()
