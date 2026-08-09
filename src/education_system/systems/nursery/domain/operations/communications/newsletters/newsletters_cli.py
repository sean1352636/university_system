"""CLI flow for Newsletters (Nursery System)."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.systems.nursery.domain.operations.communications.newsletters import (
    newsletters as data,
)
from education_system.systems.nursery.domain.operations.communications.newsletters.newsletters import (
    AUDIENCES,
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


def _print_table(rows: list[data.Newsletter]) -> None:
    if not rows:
        print("  (no newsletters)")
        return
    print(f"  {'ID':<8} {'Title':<30} {'Issue date':<12} "
          f"{'Audience':<18} {'Status':<10} {'Author'}")
    print(f"  {'-'*8} {'-'*30} {'-'*12} {'-'*18} {'-'*10} {'-'*20}")
    for n in rows:
        print(f"  {n.newsletter_id:<8} {n.title[:30]:<30} "
              f"{(n.issue_date or '-'):<12} "
              f"{(n.audience or '-')[:18]:<18} "
              f"{n.status:<10} "
              f"{(n.author_name or n.author or '-')[:20]}")


def _print_detail(n: data.Newsletter) -> None:
    print(f"\n  ── Newsletter {n.newsletter_id} ──")
    print(f"  Title:          {n.title}")
    print(f"  Issue date:     {n.issue_date or '-'}")
    print(f"  Audience:       {n.audience or '-'}")
    print(f"  Status:         {n.status}")
    print(f"  Author:         {n.author_name or n.author or '-'}")
    print(f"  Published date: {n.published_date or '-'}")
    print(f"  Body:\n    {(n.body or '').replace(chr(10), chr(10) + '    ')}")


def _collect_fields(existing: data.Newsletter | None = None) -> dict[str, str]:
    def ask(label: str, current=None) -> str:
        cur = "" if current is None else str(current)
        suffix = f" [{cur}]" if cur else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else cur

    fields: dict[str, str] = {}
    fields["title"]      = ask("Title",
                               existing.title if existing else None)
    fields["issue_date"] = ask("Issue date (YYYY-MM-DD, optional)",
                               existing.issue_date if existing else None)
    print(f"  Audiences: {', '.join(AUDIENCES)}")
    fields["audience"]   = ask("Audience (optional)",
                               existing.audience if existing else None)
    print(f"  Statuses: {', '.join(STATUSES)}")
    fields["status"]     = ask("Status",
                               existing.status if existing else "draft")
    fields["body"]       = ask("Body (newsletter content)",
                               existing.body if existing else None)
    # Author — show staff list then ask for ID
    try:
        staff = data.list_staff_choices()
    except Exception:
        staff = []
    if staff:
        print("  Staff:")
        for sid, lbl in staff:
            print(f"    {lbl}")
    fields["author"] = ask("Author (staff ID, optional)",
                           existing.author if existing else None)
    fields["published_date"] = ask("Published date (YYYY-MM-DD, optional)",
                                   existing.published_date if existing else None)
    return fields


@_safe
def open_manager() -> None:
    logger.debug("CLI: newsletters open_manager")
    while True:
        print("\n  ── Newsletters ──")
        _print_table(data.list_newsletters())
        print("\n   A) Add    V) View    E) Edit    D) Delete    P) Publish    0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in ("0", ""):
            return
        if choice == "a":
            open_add()
        elif choice == "v":
            nid = _prompt("  Newsletter ID: ")
            n = data.get_newsletter(nid)
            if n is None:
                print("  No newsletter with that ID.")
            else:
                _print_detail(n)
                _prompt("  Press Enter to continue...")
        elif choice == "e":
            open_edit()
        elif choice == "d":
            open_delete()
        elif choice == "p":
            open_publish()
        else:
            print("  Invalid selection.")


@_safe
def open_add() -> None:
    print("\n  ── Add Newsletter ──")
    fields = _collect_fields()
    n = data.create_newsletter(fields)
    print(f"\n  Added newsletter {n.newsletter_id} — {n.title}.")


@_safe
def open_edit() -> None:
    nid = _prompt("  Newsletter ID: ")
    if not nid:
        print("  Cancelled.")
        return
    existing = data.get_newsletter(nid)
    if existing is None:
        print("  No newsletter with that ID.")
        return
    print("  Press Enter to keep the existing value.")
    fields = _collect_fields(existing)
    n = data.update_newsletter(nid, fields)
    print(f"\n  Updated newsletter {n.newsletter_id}.")


@_safe
def open_delete() -> None:
    nid = _prompt("  Newsletter ID to delete: ")
    if not nid:
        print("  Cancelled.")
        return
    existing = data.get_newsletter(nid)
    if existing is None:
        print("  No newsletter with that ID.")
        return
    if _prompt(f"  Delete '{existing.title}' ({nid})? (y/N): ").lower() != "y":
        print("  Cancelled.")
        return
    if data.delete_newsletter(nid):
        print(f"  Deleted newsletter {nid}.")
    else:
        print("  Could not delete (already removed?).")


@_safe
def open_publish() -> None:
    nid = _prompt("  Newsletter ID to publish: ")
    if not nid:
        print("  Cancelled.")
        return
    existing = data.get_newsletter(nid)
    if existing is None:
        print("  No newsletter with that ID.")
        return
    if existing.status == "published":
        print(f"  Newsletter {nid} is already published.")
        return
    pub_date = _prompt("  Published date (YYYY-MM-DD, leave blank to use issue date): ")
    n = data.publish_newsletter(nid, pub_date or None)
    print(f"\n  Published newsletter {n.newsletter_id} — {n.title}.")


_DISPATCH = {"Newsletters": open_manager}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching newsletters CLI label: %s", label)
    handler()
    return True


def run(auth=None) -> None:
    open_manager()
