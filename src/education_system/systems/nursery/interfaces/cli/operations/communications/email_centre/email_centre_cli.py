"""CLI flow for the Email / Messaging centre (Nursery System).

Behind the "Email / Messaging" menu label: a message log with compose, view,
send, search, template-send and delete — the CLI counterpart of
``email_centre_views.py``. Every handler is wrapped by :func:`_safe` so a domain
or DB error is logged and reported without tearing down the menu loop.
"""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.systems.nursery.domain.operations.communications.email_centre import (
    email_centre as data,
)
from education_system.systems.nursery.domain.operations.communications.email_centre import (
    email_templates,
)
from education_system.systems.nursery.domain.operations.communications.email_centre.email_centre import (
    CATEGORIES,
    CHANNELS,
    DIRECTIONS,
    PRIORITIES,
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
        except email_templates.TemplateError as e:
            print(f"  Template error: {e}")
        except Exception as e:  # noqa: BLE001
            logger.exception("%s failed", func.__name__)
            print(f"  Error: {e}")
            print("  See logs for details.")
    return wrapper


def _print_table(rows: list[data.EmailMessage]) -> None:
    if not rows:
        print("  (no messages)")
        return
    print(f"  {'ID':<9} {'Dir':<9} {'To':<26} {'Subject':<26} "
          f"{'Cat':<11} {'Status'}")
    print(f"  {'-'*9} {'-'*9} {'-'*26} {'-'*26} {'-'*11} {'-'*8}")
    for m in rows:
        to = m.to_address or m.to_name or (m.child_name or "-")
        print(f"  {m.message_id:<9} {m.direction[:9]:<9} {to[:26]:<26} "
              f"{m.subject[:26]:<26} {m.category[:11]:<11} {m.status}")


def _print_detail(m: data.EmailMessage) -> None:
    print(f"\n  ── Email message {m.message_id} ──")
    print(f"  Direction:  {m.direction}   Channel: {m.channel}   "
          f"Priority: {m.priority}")
    print(f"  Category:   {m.category}    Status: {m.status}")
    print(f"  From:       {m.from_name or '-'} <{m.from_address or '-'}>")
    print(f"  To:         {m.to_name or '-'} <{m.to_address or '-'}>")
    if m.child_name:
        print(f"  Child:      {m.child_name} ({m.pupil_id})")
    if m.staff_name:
        print(f"  Handled by: {m.staff_name} ({m.staff_id})")
    print(f"  Subject:    {m.subject}")
    print(f"  Sent at:    {m.sent_at or '-'}")
    print(f"  Created:    {m.created_at or '-'}")
    print("  ── Body ──")
    print("  " + (m.body or "(empty)").replace("\n", "\n  "))


def _show_children() -> None:
    try:
        choices = data.list_pupil_choices()
    except Exception:
        logger.exception("Could not load child choices")
        return
    if choices:
        print("  Children on roll:")
        for _id, label in choices:
            print(f"    {label}")


def _ask(label: str, current: str | None = None) -> str:
    cur = "" if current is None else str(current)
    suffix = f" [{cur}]" if cur else ""
    v = _prompt(f"  {label}{suffix}: ")
    return v if v else cur


def _collect_fields(existing: data.EmailMessage | None = None) -> dict[str, str]:
    fields: dict[str, str] = {}
    fields["direction"] = _ask(
        f"Direction ({'/'.join(DIRECTIONS)})",
        existing.direction if existing else "Outgoing")
    fields["channel"] = _ask(
        f"Channel ({'/'.join(CHANNELS)})",
        existing.channel if existing else "Email")
    fields["category"] = _ask(
        f"Category ({'/'.join(CATEGORIES)})",
        existing.category if existing else "General")
    fields["priority"] = _ask(
        f"Priority ({'/'.join(PRIORITIES)})",
        existing.priority if existing else "Normal")
    fields["subject"] = _ask("Subject", existing.subject if existing else None)
    fields["body"] = _ask("Body [optional]", existing.body if existing else None)
    fields["to_name"] = _ask("To name [optional]",
                             existing.to_name if existing else None)
    fields["to_address"] = _ask("To address [optional]",
                                existing.to_address if existing else None)
    fields["from_name"] = _ask("From name [optional]",
                               existing.from_name if existing else None)
    fields["from_address"] = _ask("From address [optional]",
                                  existing.from_address if existing else None)
    fields["pupil_id"] = _ask("Child ID [optional]",
                              existing.pupil_id if existing else None)
    fields["staff_id"] = _ask("Staff ID [optional]",
                              existing.staff_id if existing else None)
    fields["status"] = _ask(
        f"Status ({'/'.join(STATUSES)})",
        existing.status if existing else "Draft")
    return fields


@_safe
def open_manager(auth=None) -> None:
    logger.debug("CLI: email_centre open_manager")
    while True:
        s = data.summary()
        print("\n  ── Email / Messaging ──")
        print(f"  {s.total} message(s) · {s.sent} sent · {s.drafts} draft(s) · "
              f"{s.incoming} incoming · {s.failed} failed")
        _print_table(data.list_messages())
        print("\n   C) Compose    V) View    S) Send (deliver draft)")
        print("   T) Send from template    F) Filter    /) Search")
        print("   E) Edit    D) Delete    X) Cross-System Email    0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in ("0", ""):
            return
        if choice == "c":
            open_compose()
        elif choice == "v":
            _view()
        elif choice == "s":
            _send()
        elif choice == "t":
            open_send_template()
        elif choice == "f":
            _filter()
        elif choice == "/":
            _search()
        elif choice == "e":
            open_edit()
        elif choice == "d":
            open_delete()
        elif choice == "x":
            _open_cross_system(auth)
        else:
            print("  Invalid selection.")


def _open_cross_system(auth=None) -> None:
    """Hand off to the shared inter-system messaging CLI (same feature the GUI
    surfaces as the Cross-System Email tab)."""
    from education_system.systems.nursery.domain.operations.communications.email_centre import (
        cross_system_cli,
    )
    cross_system_cli.open_manager(auth=auth)


def _view() -> None:
    mid = _prompt("  Message ID: ")
    m = data.get_message(mid)
    if m is None:
        print("  No message with that ID.")
    else:
        _print_detail(m)
    _prompt("  Press Enter to continue...")


@_safe
def open_compose() -> None:
    print("\n  ── Compose message ──")
    _show_children()
    fields = _collect_fields()
    m = data.create_message(fields)
    print(f"\n  Created message {m.message_id} ('{m.subject}', {m.status}).")
    if m.status != "Sent" and m.direction == "Outgoing" and \
            _prompt("  Send it now? (y/N): ").lower() == "y":
        data.send_message(m.message_id)
        print(f"  Sent {m.message_id}.")


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
def _send() -> None:
    mid = _prompt("  Message ID to send: ")
    if not mid:
        print("  Cancelled.")
        return
    m = data.send_message(mid)
    print(f"  Sent {m.message_id} to {m.to_address or '-'}.")


@_safe
def open_send_template() -> None:
    print("\n  ── Send from template ──")
    names = email_templates.list_templates()
    if not names:
        print("  No templates available.")
        return
    print("  Templates: " + ", ".join(names))
    name = _prompt("  Template name: ")
    if not name:
        print("  Cancelled.")
        return
    to_address = _prompt("  To address: ")
    to_name = _prompt("  To name [optional]: ")
    pupil_id = _prompt("  Child ID [optional]: ")
    print("  Enter context values for {{placeholders}} (blank line to finish).")
    print("  Format: key=value")
    context: dict[str, str] = {}
    while True:
        line = _prompt("    ")
        if not line:
            break
        if "=" in line:
            k, _, v = line.partition("=")
            context[k.strip()] = v.strip()
        else:
            print("    (use key=value)")
    m = email_templates.send_from_template(
        name, context, to_name=to_name or None, to_address=to_address or None,
        pupil_id=pupil_id or None)
    print(f"\n  Sent template '{name}' as {m.message_id}.")
    _print_detail(m)
    _prompt("  Press Enter to continue...")


@_safe
def _filter() -> None:
    direction = _prompt(f"  Direction ({'/'.join(DIRECTIONS)}) [blank=all]: ") or None
    status = _prompt(f"  Status ({'/'.join(STATUSES)}) [blank=all]: ") or None
    _print_table(data.list_messages(direction=direction or None,
                                    status=status or None))
    _prompt("  Press Enter to continue...")


@_safe
def _search() -> None:
    q = _prompt("  Search (subject / body / address): ")
    _print_table(data.search_messages(q))
    _prompt("  Press Enter to continue...")


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


def dispatch(label: str, auth=None) -> bool:
    if label != "Email / Messaging":
        return False
    logger.debug("Dispatching email-centre CLI label: %s", label)
    open_manager(auth=auth)
    return True


def run(auth=None) -> None:
    open_manager(auth=auth)
