"""CLI flows for the Primary School Policy register."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable

from education_system.systems.primary.domain.governance.policies import policies as data
from education_system.systems.primary.domain.governance.policies.policies import (
    CATEGORIES,
    DEFAULT_CATEGORY,
    DEFAULT_REVIEW_CYCLE,
    DEFAULT_STATUS,
    DERIVED_STATUSES,
    Policy,
    PolicyView,
    REVIEW_CYCLES,
    STATUSES,
    ValidationError,
)

logger = logging.getLogger(__name__)


class _UserAbort(Exception):
    pass


def _input(prompt: str, *, default: str = "",
            allow_empty: bool = True) -> str:
    suffix = f" [{default}]" if default else ""
    try:
        raw = input(f"  {prompt}{suffix}: ")
    except (EOFError, KeyboardInterrupt):
        print()
        raise _UserAbort
    s = raw.strip()
    if s.lower() == "cancel":
        raise _UserAbort
    if not s:
        if default:
            return default
        if not allow_empty:
            print("    Value is required.")
            return _input(prompt, default=default, allow_empty=False)
        return ""
    return s


def _pause() -> None:
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


def _pick(label: str, options: list[str],
           default: str | None = None) -> str:
    print(f"\n  {label}:")
    for i, opt in enumerate(options, 1):
        marker = " *" if opt == default else "  "
        print(f"    {marker}{i:>2}) {opt}")
    while True:
        raw = _input(f"  Pick #1..{len(options)}", default=default or "")
        if default and raw == default:
            return default
        if not raw.isdigit():
            print("    Enter a number (or 'cancel').")
            continue
        n = int(raw)
        if 1 <= n <= len(options):
            return options[n - 1]
        print("    Out of range.")


# ── Print helpers ──────────────────────────────────────────────────

def _print_views(views: list[PolicyView]) -> None:
    if not views:
        print("\n  (no policies)")
        return
    print()
    print(f"  {'#':>4}  {'Category':<14}  {'Title':<30}  "
          f"{'Ver.':<6}  {'Next':<10}  {'Status':<14}")
    print("  " + "-" * 86)
    for v in views:
        p = v.policy
        nxt = p.next_review or "—"
        print(f"  {p.policy_id:>4}  {p.category[:14]:<14}  "
              f"{p.title[:30]:<30}  {p.version[:6]:<6}  "
              f"{nxt:<10}  {v.derived_status:<14}")
    print(f"\n  {len(views)} policy(ies).")


def _print_summary() -> None:
    try:
        s = data.summary()
    except Exception as e:
        logger.exception("policies summary failed")
        print(f"  ✗ {e}")
        return
    print(f"\n  Total policies        : {s.total}")
    print(f"  Overdue review        : {s.overdue}")
    print(f"  Due within 30 days    : {s.due_soon}")
    print(f"  No review date set    : {s.no_review_date}")
    print(f"  Total revisions logged: {s.total_revisions}")
    print("\n  By category:")
    for c in CATEGORIES:
        print(f"    {c:<18}  {s.by_category.get(c, 0):>4}")
    print("\n  By status:")
    for st in DERIVED_STATUSES:
        print(f"    {st:<18}  {s.by_status.get(st, 0):>4}")


# ── Flows ──────────────────────────────────────────────────────────

def list_all() -> None:
    print("\n═══ Policy Register ═══")
    _print_views(data.list_views())
    _pause()


def list_overdue() -> None:
    print("\n═══ Policies — Overdue review ═══")
    _print_views(data.list_views(overdue_only=True))
    _pause()


def filter_policies() -> None:
    print("\n═══ Filter Policies ═══  (blank = skip)")
    try:
        cat = _input(f"Category ({'/'.join(CATEGORIES)})")
        status = _input(f"Status ({'/'.join(STATUSES)})")
        owner = _input("Owner contains")
        query = _input("Title/summary contains")
        overdue = _input("Overdue only? (y/n)", default="n").lower() in ("y", "yes")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    kwargs: dict[str, Any] = {"overdue_only": overdue}
    if cat:
        if cat not in CATEGORIES:
            print(f"  ✗ Category must be one of {', '.join(CATEGORIES)}.")
            _pause()
            return
        kwargs["category"] = cat
    if status:
        if status not in STATUSES:
            print(f"  ✗ Status must be one of {', '.join(STATUSES)}.")
            _pause()
            return
        kwargs["status"] = status
    if owner:
        kwargs["owner"] = owner
    if query:
        kwargs["query"] = query
    try:
        _print_views(data.list_views(**kwargs))
    except ValidationError as e:
        print(f"  ✗ {e}")
    _pause()


def view_policy_flow() -> None:
    print("\n═══ View Policy ═══")
    try:
        pid = int(_input("Policy ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("  ✗ Policy ID must be a number.")
        _pause()
        return
    v = data.view_policy(pid)
    if v is None:
        print(f"  ✗ No policy #{pid}")
        _pause()
        return
    p = v.policy
    print(f"\n  #{p.policy_id}  {p.category} — {p.title}")
    print(f"  Owner          : {p.owner or '—'}")
    print(f"  Version        : {p.version}")
    print(f"  Stored status  : {p.status}")
    print(f"  Derived status : {v.derived_status}")
    print(f"  Review cycle   : {p.review_cycle}")
    print(f"  Approved on    : {p.approved_on or '—'}")
    print(f"  Next review    : {p.next_review or '—'}")
    if v.days_until_review is not None:
        if v.days_until_review < 0:
            print(f"  Overdue by     : {-v.days_until_review} day(s)")
        else:
            print(f"  Due in         : {v.days_until_review} day(s)")
    print(f"  Document ref   : {p.document_ref or '—'}")
    print(f"  Revisions      : {v.revisions_count}")
    print(f"  Created/upd.   : {p.created_at} / {p.updated_at}")
    if p.summary:
        print(f"\n  Summary:\n    {p.summary}")
    revisions = data.list_revisions(pid)
    if revisions:
        print("\n  Revisions:")
        print(f"    {'#':>4}  {'Date':<10}  {'Ver':<6}  "
              f"{'Approved by':<18}  Changes")
        print("    " + "-" * 70)
        for r in revisions:
            changes = (r.changes or "")[:36]
            print(f"    {r.revision_id:>4}  {r.revised_on:<10}  "
                  f"{r.version[:6]:<6}  "
                  f"{(r.approved_by or '—')[:18]:<18}  {changes}")
    _pause()


def new_policy_flow() -> None:
    print("\n═══ New Policy ═══")
    try:
        title = _input("Title", allow_empty=False)
        category = _pick("Category", list(CATEGORIES), default=DEFAULT_CATEGORY)
        version = _input("Version", default="1.0")
        owner = _input("Owner (optional)")
        status = _pick("Status", list(STATUSES), default=DEFAULT_STATUS)
        cycle = _pick("Review cycle", list(REVIEW_CYCLES),
                       default=DEFAULT_REVIEW_CYCLE)
        approved = _input("Approved on YYYY-MM-DD (optional)")
        next_review = _input("Next review YYYY-MM-DD (optional)")
        summary = _input("Summary (optional)")
        doc = _input("Document ref (optional)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        p = data.create_policy({
            "title": title, "category": category, "version": version,
            "owner": owner, "status": status, "review_cycle": cycle,
            "approved_on": approved or None,
            "next_review": next_review or None,
            "summary": summary or None,
            "document_ref": doc or None,
        })
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created #{p.policy_id} — {p.title} (v{p.version})")
    _pause()


def edit_policy_flow() -> None:
    print("\n═══ Edit Policy ═══")
    try:
        pid = int(_input("Policy ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("  ✗ Policy ID must be a number.")
        _pause()
        return
    existing = data.get_policy(pid)
    if existing is None:
        print(f"  ✗ No policy #{pid}")
        _pause()
        return
    print(f"\n  Editing #{pid} — {existing.title}")
    print("  (Enter to keep existing)")
    try:
        title = _input("Title", default=existing.title)
        category = _pick("Category", list(CATEGORIES),
                           default=existing.category)
        version = _input("Version", default=existing.version)
        owner = _input("Owner", default=existing.owner or "")
        status = _pick("Status", list(STATUSES), default=existing.status)
        cycle = _pick("Review cycle", list(REVIEW_CYCLES),
                       default=existing.review_cycle)
        approved = _input("Approved on",
                           default=existing.approved_on or "")
        next_review = _input("Next review",
                              default=existing.next_review or "")
        summary = _input("Summary", default=existing.summary or "")
        doc = _input("Document ref", default=existing.document_ref or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        p = data.update_policy(pid, {
            "title": title, "category": category, "version": version,
            "owner": owner, "status": status, "review_cycle": cycle,
            "approved_on": approved or None,
            "next_review": next_review or None,
            "summary": summary or None,
            "document_ref": doc or None,
        })
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated #{p.policy_id}")
    _pause()


def add_revision_flow() -> None:
    print("\n═══ Add Revision ═══")
    try:
        pid = int(_input("Policy ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("  ✗ Policy ID must be a number.")
        _pause()
        return
    existing = data.get_policy(pid)
    if existing is None:
        print(f"  ✗ No policy #{pid}")
        _pause()
        return
    try:
        version = _input("New version", default=existing.version)
        when = _input("Revised on YYYY-MM-DD",
                       default=_date.today().isoformat())
        by = _input("Revised by (optional)")
        approved_by = _input("Approved by (blank = not yet approved)")
        changes = _input("Changes / notes (optional)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = data.add_revision(pid, {
            "version": version, "revised_on": when,
            "revised_by": by or None,
            "approved_by": approved_by or None,
            "changes": changes or None,
        })
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    note = " (also promoted policy to Approved)" if approved_by else ""
    print(f"\n  ✓ Added revision #{r.revision_id} (v{r.version}){note}")
    _pause()


def delete_policy_flow() -> None:
    print("\n═══ Delete Policy ═══")
    try:
        pid = int(_input("Policy ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("  ✗ Policy ID must be a number.")
        _pause()
        return
    existing = data.get_policy(pid)
    if existing is None:
        print(f"  ✗ No policy #{pid}")
        _pause()
        return
    confirm = _input(
        f"Delete '#{pid} — {existing.title}' and all its revisions? "
        f"Type 'yes'", default="no")
    if confirm.lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_policy(pid):
        print(f"\n  ✓ Deleted #{pid}")
    _pause()


def summary_flow() -> None:
    print("\n═══ Policy Summary ═══")
    _print_summary()
    _pause()


# ── Submenu dispatch ───────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Summary",           summary_flow),
    ("List All",          list_all),
    ("List Overdue",      list_overdue),
    ("Filter / Search",   filter_policies),
    ("View Policy",       view_policy_flow),
    ("New Policy",        new_policy_flow),
    ("Edit Policy",       edit_policy_flow),
    ("Add Revision",      add_revision_flow),
    ("Delete Policy",     delete_policy_flow),
]


def run() -> None:
    while True:
        print("\n── Policies ──")
        for i, (label, _) in enumerate(_MENU, 1):
            print(f"  {i:>2}) {label}")
        print("   0) Back")
        try:
            choice = input("  Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if choice == "0":
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(_MENU)):
            print("  Invalid selection.")
            continue
        _, handler = _MENU[int(choice) - 1]
        try:
            handler()
        except _UserAbort:
            print("\n  Cancelled.")
        except Exception as e:
            logger.exception("Policies CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Policies":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Policies CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
