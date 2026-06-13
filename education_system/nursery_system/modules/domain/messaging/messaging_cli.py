"""CLI flow for Parent Messaging (Nursery System)."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.nursery_system.modules.domain.messaging import (
    messaging as data,
)
from education_system.nursery_system.modules.domain.messaging.messaging import (
    CHANNELS,
    DIRECTIONS,
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


def _print_table(rows: list[data.Message]) -> None:
    if not rows:
        print("  (no messages)")
        return
    print(f"  {'ID':<8} {'Child':<20} {'Dir':<10} {'Channel':<10} "
          f"{'Subject':<24} {'Date':<12} {'Status'}")
    print(f"  {'-'*8} {'-'*20} {'-'*10} {'-'*10} {'-'*24} {'-'*12} {'-'*8}")
    for m in rows:
        print(f"  {m.message_id:<8} {(m.child_name or '-')[:20]:<20} "
              f"{m.direction[:10]:<10} {(m.channel or '-')[:10]:<10} "
              f"{m.subject[:24]:<24} {(m.message_date or '-')[:12]:<12} "
              f"{m.status}")


def _print_detail(m: data.Message) -> None:
    print(f"\n  ── Parent message {m.message_id} ──")
    print(f"  Child:        {m.child_name or '-'} ({m.pupil_id})")
    print(f"  Direction:    {m.direction}")
    print(f"  Channel:      {m.channel or '-'}")
    print(f"  Subject:      {m.subject}")
    print(f"  Body:         {m.body or '-'}")
    print(f"  Date:         {m.message_date or '-'}")
    print(f"  Staff:        {m.staff_name or '-'}")
    print(f"  Status:       {m.status}")


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


def _collect_fields(existing: data.Message | None = None,
                    *, pupil_id: str | None = None) -> dict[str, str]:
    def ask(label: str, current=None) -> str:
        cur = "" if current is None else str(current)
        suffix = f" [{cur}]" if cur else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else cur

    fields: dict[str, str] = {}
    if pupil_id is not None:
        fields["pupil_id"] = pupil_id

    fields["direction"] = ask(
        f"Direction ({'/'.join(DIRECTIONS)})",
        existing.direction if existing else "outgoing")
    fields["channel"] = ask(
        f"Channel ({'/'.join(CHANNELS)}) [optional]",
        existing.channel if existing else None)
    fields["subject"] = ask("Subject", existing.subject if existing else None)
    fields["body"] = ask("Body [optional]", existing.body if existing else None)
    fields["message_date"] = ask(
        "Message date (YYYY-MM-DD) [optional]",
        existing.message_date if existing else None)
    fields["staff_id"] = ask(
        "Staff ID [optional]", existing.staff_id if existing else None)
    fields["status"] = ask(
        f"Status ({'/'.join(STATUSES)})",
        existing.status if existing else "sent")
    return fields


@_safe
def open_manager() -> None:
    logger.debug("CLI: messaging open_manager")
    while True:
        print("\n  ── Parent Messaging ──")
        _print_table(data.list_messages())
        print("\n   A) Add message    V) View    E) Edit    D) Delete")
        print("   M) Messages for a child    0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in ("0", ""):
            return
        if choice == "a":
            open_add()
        elif choice == "v":
            mid = _prompt("  Message ID: ")
            m = data.get_message(mid)
            if m is None:
                print("  No message with that ID.")
            else:
                _print_detail(m)
                _prompt("  Press Enter to continue...")
        elif choice == "e":
            open_edit()
        elif choice == "d":
            open_delete()
        elif choice == "m":
            pid = _prompt("  Child ID: ")
            _print_table(data.list_messages(pupil_id=pid))
            _prompt("  Press Enter to continue...")
        else:
            print("  Invalid selection.")


@_safe
def open_add() -> None:
    print("\n  ── Add Parent Message ──")
    _show_children()
    pid = _prompt("  Child ID: ")
    if not pid:
        print("  Cancelled.")
        return
    fields = _collect_fields(pupil_id=pid)
    m = data.create_message(fields)
    print(f"\n  Added message {m.message_id} ('{m.subject}') for "
          f"{m.child_name or pid}.")


@_safe
def open_edit() -> None:
    mid = _prompt("  Message ID: ")
    if not mid:
        print("  Cancelled.")
        return
    existing = data.get_message(mid)
    if existing is None:
        print("  No message with that ID.")
        return
    print("  Press Enter to keep the existing value.")
    fields = _collect_fields(existing)
    m = data.update_message(mid, fields)
    print(f"\n  Updated message {m.message_id}.")


@_safe
def open_delete() -> None:
    mid = _prompt("  Message ID to delete: ")
    if not mid:
        print("  Cancelled.")
        return
    existing = data.get_message(mid)
    if existing is None:
        print("  No message with that ID.")
        return
    if _prompt(f"  Delete '{existing.subject}' ({mid})? (y/N): ").lower() != "y":
        print("  Cancelled.")
        return
    if data.delete_message(mid):
        print(f"  Deleted message {mid}.")
    else:
        print("  Could not delete (already removed?).")


_DISPATCH = {"Parent Messaging": open_manager}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching messaging CLI label: %s", label)
    handler()
    return True


def run(auth=None) -> None:
    open_manager()
