"""CLI handlers for newsletters."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.primarysch_system.modules.domain.newsletters import (
    newsletters as data,
)
from education_system.primarysch_system.modules.domain.newsletters.newsletters import (
    AUDIENCE_CHOICES, AUDIENCE_LABELS, STATUSES, STATUS_LABELS,
)
from education_system.primarysch_system.modules.domain.pupils.pupils import (
    ValidationError, YEAR_GROUPS,
)

logger = logging.getLogger(__name__)


def _prompt(msg: str) -> str:
    try:
        return input(msg).strip()
    except (EOFError, KeyboardInterrupt):
        return ""


def _prompt_multiline(label: str, default: str = "") -> str:
    print(f"  {label} (end with a blank line; leave blank to keep default):")
    if default:
        first = default.splitlines()[0] if default else ""
        more = " (...)" if "\n" in default else ""
        print(f"  [default: {first[:60]}{more}]")
    lines: list[str] = []
    while True:
        try:
            line = input("  > ")
        except (EOFError, KeyboardInterrupt):
            break
        if line == "":
            break
        lines.append(line)
    if not lines:
        return default
    return "\n".join(lines)


def _safe(func: Callable[..., None]) -> Callable[..., None]:
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValidationError as e:
            print(f"  Validation error: {e}")
        except Exception as e:
            logger.exception("%s failed", func.__name__)
            print(f"  Error: {e}")
            print("  See logs for details.")
    return wrapper


def _print_table(rows: list) -> None:
    if not rows:
        print("  (no newsletters)")
        return
    print(f"  {'#':<5} {'AcYr':<9} {'Iss':<4} {'Title':<32} "
          f"{'Audience':<14} {'Status':<10} {'Issue date':<11} "
          f"{'Published':<11}")
    print(f"  {'-'*5} {'-'*9} {'-'*4} {'-'*32} {'-'*14} {'-'*10} "
          f"{'-'*11} {'-'*11}")
    for n in rows:
        iss = "-" if n.issue_number is None else str(n.issue_number)
        aud = n.audience
        if n.audience == "year_group" and n.target_year_group:
            aud = f"year_{n.target_year_group}"
        print(f"  {n.newsletter_id:<5} {n.academic_year:<9} {iss:<4} "
              f"{n.title[:32]:<32} {aud[:14]:<14} {n.status:<10} "
              f"{(n.issue_date or '-'):<11} "
              f"{(n.published_on or '-'):<11}")


@_safe
def open_newsletters() -> None:
    logger.debug("CLI: open_newsletters")
    while True:
        print("\n  -- Newsletters --")
        try:
            s = data.summary()
        except Exception:
            s = {"total": 0, "by_status": {st: 0 for st in STATUSES},
                 "academic_years": 0}
        print(f"  Total: {s['total']}   " + "   ".join(
            f"{st}: {s['by_status'].get(st, 0)}" for st in STATUSES))
        print("\n   1) List all")
        print("   2) Filter / search")
        print("   3) View newsletter")
        print("   4) Suggest next issue number")
        print("   5) Create newsletter (draft)")
        print("   6) Update draft")
        print("   7) Publish")
        print("   8) Revert to draft")
        print("   9) Archive")
        print("  10) Delete")
        print("  11) Show audience / status meanings")
        print("   0) Back")
        choice = _prompt("  Select: ")
        if choice == "0" or choice == "":
            return
        actions = {
            "1": _list_all,
            "2": _filter,
            "3": _view,
            "4": _next_number,
            "5": _create,
            "6": _update,
            "7": _publish,
            "8": _revert,
            "9": _archive,
            "10": _delete,
            "11": _show_help,
        }
        action = actions.get(choice)
        if action is None:
            print("  Invalid selection.")
            continue
        action()


@_safe
def _list_all() -> None:
    rows = data.list_newsletters()
    print(f"\n  {len(rows)} newsletter(s):")
    _print_table(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def _filter() -> None:
    ay = _prompt("  Academic year (blank for any): ").strip() or None
    print(f"  Statuses: {', '.join(STATUSES)} (blank for any)")
    st = _prompt("  Status: ").strip().lower() or None
    print(f"  Audiences: {', '.join(AUDIENCE_CHOICES)} (blank for any)")
    aud = _prompt("  Audience: ").strip().lower() or None
    print(f"  Year groups: {', '.join(YEAR_GROUPS)} (blank for any)")
    tyg = _prompt("  Target year group: ").strip() or None
    q = _prompt("  Search title/body/author (blank): ").strip() or None
    rows = data.list_newsletters(academic_year=ay, status=st,
                                 audience=aud, target_year_group=tyg,
                                 search=q)
    print(f"\n  {len(rows)} newsletter(s):")
    _print_table(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def _view() -> None:
    raw = _prompt("  Newsletter ID: ")
    if not raw or not raw.isdigit():
        return
    rec = data.get(int(raw))
    if rec is None:
        print(f"  No newsletter #{raw}")
        return
    print(f"\n  -- Newsletter #{rec.newsletter_id} --")
    iss = "-" if rec.issue_number is None else f"#{rec.issue_number}"
    print(f"  {rec.academic_year}  issue {iss}  ({rec.status})")
    print(f"  Title:        {rec.title}")
    aud = rec.audience
    if rec.audience == "year_group" and rec.target_year_group:
        aud = f"year_group ({rec.target_year_group})"
    print(f"  Audience:     {aud}")
    print(f"  Author:       {rec.authored_by or '-'}")
    print(f"  Issue date:   {rec.issue_date or '-'}")
    print(f"  Published on: {rec.published_on or '-'}")
    print(f"\n  Body:\n    {(rec.body or '-')}")
    if rec.notes:
        print(f"\n  Notes:\n    {rec.notes}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _next_number() -> None:
    ay = _prompt("  Academic year: ")
    if not ay:
        return
    n = data.next_issue_number(ay)
    print(f"  Next free issue number for {ay}: {n}")
    _prompt("\n  Press Enter to continue...")


def _collect(defaults: dict | None = None) -> dict:
    d = defaults or {}
    print(f"  (Audiences: {', '.join(AUDIENCE_CHOICES)})")
    out: dict = {}
    out["title"]         = _prompt(f"  Title [{d.get('title','')}]: ") or d.get("title", "")
    iss_def = "" if d.get("issue_number") in (None, "") else str(d["issue_number"])
    out["issue_number"]  = _prompt(f"  Issue number (optional) [{iss_def}]: ") or iss_def
    out["academic_year"] = _prompt(f"  Academic year (e.g. 2025-26) [{d.get('academic_year','')}]: ") or d.get("academic_year", "")
    out["issue_date"]    = _prompt(f"  Issue date YYYY-MM-DD [{d.get('issue_date','')}]: ") or d.get("issue_date", "")
    out["audience"]      = _prompt(f"  Audience [{d.get('audience','whole_school')}]: ") or d.get("audience", "whole_school")
    out["target_year_group"] = _prompt(f"  Target year group (if year_group) [{d.get('target_year_group','')}]: ") or d.get("target_year_group", "")
    out["authored_by"]   = _prompt(f"  Authored by [{d.get('authored_by','')}]: ") or d.get("authored_by", "")
    out["body"]          = _prompt_multiline("Body", d.get("body", "") or "")
    out["notes"]         = _prompt(f"  Notes [{d.get('notes','')}]: ") or d.get("notes", "")
    return out


@_safe
def _create() -> None:
    print("\n  -- Create Newsletter (draft) --")
    payload = _collect()
    payload["status"] = "draft"
    rec = data.create(payload)
    print(f"  Created draft #{rec.newsletter_id}: {rec.title}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _update() -> None:
    raw = _prompt("  Newsletter ID to edit: ")
    if not raw or not raw.isdigit():
        return
    existing = data.get(int(raw))
    if existing is None:
        print(f"  No newsletter #{raw}")
        return
    if existing.is_published:
        print("  Published — revert to draft first.")
        return
    defaults = {
        "title": existing.title,
        "issue_number": existing.issue_number,
        "academic_year": existing.academic_year,
        "issue_date": existing.issue_date or "",
        "audience": existing.audience,
        "target_year_group": existing.target_year_group or "",
        "body": existing.body or "",
        "authored_by": existing.authored_by or "",
        "notes": existing.notes or "",
    }
    payload = _collect(defaults)
    payload["status"] = existing.status
    rec = data.update(int(raw), payload)
    print(f"  Updated #{rec.newsletter_id}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _publish() -> None:
    raw = _prompt("  Newsletter ID to publish: ")
    if not raw or not raw.isdigit():
        return
    pub_on = _prompt("  Published on YYYY-MM-DD (blank for today): ")
    rec = data.publish(int(raw), published_on=pub_on or None)
    print(f"  Newsletter #{rec.newsletter_id} published on {rec.published_on}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _revert() -> None:
    raw = _prompt("  Newsletter ID to revert to draft: ")
    if not raw or not raw.isdigit():
        return
    rec = data.revert_to_draft(int(raw))
    print(f"  Newsletter #{rec.newsletter_id} -> {rec.status}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _archive() -> None:
    raw = _prompt("  Newsletter ID to archive: ")
    if not raw or not raw.isdigit():
        return
    rec = data.archive(int(raw))
    print(f"  Newsletter #{rec.newsletter_id} -> {rec.status}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _delete() -> None:
    raw = _prompt("  Newsletter ID to delete: ")
    if not raw or not raw.isdigit():
        return
    confirm = _prompt(f"  Delete newsletter #{raw}? Type 'DELETE' to confirm: ")
    if confirm != "DELETE":
        print("  Cancelled.")
        return
    ok = data.delete(int(raw))
    print(f"  {'Deleted' if ok else 'No such newsletter'}: #{raw}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _show_help() -> None:
    print("\n  -- Audiences --")
    for a in AUDIENCE_CHOICES:
        print(f"   {a:<14} {AUDIENCE_LABELS[a]}")
    print("\n  -- Statuses --")
    for s in STATUSES:
        print(f"   {s:<10} {STATUS_LABELS[s]}")
    _prompt("\n  Press Enter to continue...")


_DISPATCH = {"Newsletters": open_newsletters}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching newsletters CLI label: %s", label)
    handler()
    return True
