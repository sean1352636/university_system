"""CLI flow for the Accident / Incident Report (Nursery System).

Lists, adds, edits, deletes and summarises the accident / incident / near-miss
register. The GUI counterpart is ``accident_report_views.py``.
"""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.nursery_system.modules.domain.accident_report import (
    accident_report as data,
)
from education_system.nursery_system.modules.domain.accident_report.accident_report import (
    RECORD_TYPES,
    SEVERITIES,
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
            print(f"  ✗ {e}")
        except Exception as e:  # noqa: BLE001
            logger.exception("%s failed", func.__name__)
            print(f"  Error: {e}")
            print("  See logs for details.")
    return wrapper


def _pick(label: str, choices: list[tuple[str, str]],
          current: str | None = None) -> str | None:
    """Numbered picker. Returns the selected id, or ``current`` on blank."""
    if not choices:
        return _prompt(f"  {label} (id): ") or current
    print(f"  {label}:")
    for i, (_id, text) in enumerate(choices, 1):
        marker = " *" if _id == current else ""
        print(f"    {i}) {text}{marker}")
    raw = _prompt(f"  Choose 1-{len(choices)} (blank = keep): ")
    if not raw:
        return current
    try:
        idx = int(raw)
    except ValueError:
        print("  Invalid selection — keeping current.")
        return current
    if 1 <= idx <= len(choices):
        return choices[idx - 1][0]
    print("  Out of range — keeping current.")
    return current


def _pick_option(label: str, options: tuple[str, ...],
                 current: str | None = None) -> str:
    suffix = f" [{current}]" if current else ""
    v = _prompt(f"  {label} ({'/'.join(options)}){suffix}: ").lower()
    return v if v else (current or "")


def _print_table(rows: list[data.AccidentRecord]) -> None:
    if not rows:
        print("  (no accident / incident records)")
        return
    print(f"  {'ID':<8} {'Date':<11} {'Child':<20} {'Type':<10} "
          f"{'Severity':<9} {'Parent':<7} {'RIDDOR':<7} {'Status'}")
    print(f"  {'-'*8} {'-'*11} {'-'*20} {'-'*10} {'-'*9} {'-'*7} {'-'*7} {'-'*8}")
    for r in rows:
        print(f"  {r.record_id:<8} {(r.occurred_date or '-'):<11} "
              f"{(r.child_name or '-')[:20]:<20} {r.record_type[:10]:<10} "
              f"{r.severity[:9]:<9} {('yes' if r.parent_informed else 'no'):<7} "
              f"{('yes' if r.riddor_reportable else 'no'):<7} {r.status}")


def _print_detail(r: data.AccidentRecord) -> None:
    print(f"\n  ── Accident / Incident {r.record_id} ──")
    print(f"  Child:           {r.child_name or '-'} ({r.pupil_id})")
    print(f"  Type:            {r.record_type}")
    print(f"  When:            {r.occurred_date or '-'} {r.occurred_time or ''}".rstrip())
    print(f"  Location:        {r.location or '-'}")
    print(f"  Description:     {r.description or '-'}")
    print(f"  Injury:          {r.injury or '-'}")
    print(f"  Body part:       {r.body_part or '-'}")
    print(f"  Treatment:       {r.treatment or '-'}")
    aider = r.first_aider_name or r.first_aider or "-"
    print(f"  First-aider:     {aider}")
    print(f"  Severity:        {r.severity}")
    print(f"  Parent informed: {'Yes' if r.parent_informed else 'No'}")
    print(f"  Parent signed:   {'Yes' if r.parent_signed else 'No'}")
    print(f"  RIDDOR:          {'Yes' if r.riddor_reportable else 'No'}")
    print(f"  Action taken:    {r.action_taken or '-'}")
    print(f"  Recorded by:     {r.recorded_by or '-'}")
    print(f"  Status:          {r.status}")
    print(f"  Notes:           {r.notes or '-'}")


def _ask(label: str, current=None) -> str:
    cur = "" if current is None else str(current)
    suffix = f" [{cur}]" if cur else ""
    v = _prompt(f"  {label}{suffix}: ")
    return v if v else cur


def _ask_bool(label: str, current: bool | None = None) -> str:
    cur = ("y" if current else "n") if current is not None else None
    return _ask(f"{label} (y/n)", cur)


def _collect_fields(existing: data.AccidentRecord | None = None,
                    *, pupil_id: str | None = None) -> dict[str, str]:
    fields: dict[str, str] = {}
    if pupil_id is not None:
        fields["pupil_id"] = pupil_id

    fields["record_type"] = _pick_option(
        "Type", RECORD_TYPES,
        existing.record_type if existing else "accident") or "accident"
    fields["occurred_date"] = _ask("Date (YYYY-MM-DD)",
                                   existing.occurred_date if existing else None)
    fields["occurred_time"] = _ask("Time (HH:MM)",
                                   existing.occurred_time if existing else None)
    fields["location"] = _ask("Location", existing.location if existing else None)
    fields["description"] = _ask("Description",
                                 existing.description if existing else None)
    fields["injury"] = _ask("Injury", existing.injury if existing else None)
    fields["body_part"] = _ask("Body part", existing.body_part if existing else None)
    fields["treatment"] = _ask("Treatment given",
                               existing.treatment if existing else None)
    try:
        staff = data.list_staff_choices()
    except Exception:
        logger.exception("Could not load staff choices")
        staff = []
    fields["first_aider"] = _pick(
        "First-aider", staff,
        existing.first_aider if existing else None) or ""
    fields["severity"] = _pick_option(
        "Severity", SEVERITIES,
        existing.severity if existing else "minor") or "minor"
    fields["parent_informed"] = _ask_bool(
        "Parent informed",
        existing.parent_informed if existing else None)
    fields["parent_signed"] = _ask_bool(
        "Parent signed",
        existing.parent_signed if existing else None)
    fields["riddor_reportable"] = _ask_bool(
        "RIDDOR-reportable",
        existing.riddor_reportable if existing else None)
    fields["action_taken"] = _ask("Action taken",
                                  existing.action_taken if existing else None)
    fields["recorded_by"] = _ask("Recorded by",
                                 existing.recorded_by if existing else None)
    fields["notes"] = _ask("Notes", existing.notes if existing else None)
    if existing is not None:
        fields["status"] = _pick_option("Status", STATUSES, existing.status)
    return fields


@_safe
def _list_records() -> None:
    _print_table(data.list_records())


@_safe
def _add_record() -> None:
    print("\n  ── Add Accident / Incident Record ──")
    pid = _pick("Child", data.list_pupil_choices())
    if not pid:
        print("  Cancelled.")
        return
    fields = _collect_fields(pupil_id=pid)
    r = data.create_record(fields)
    print(f"\n  ✓ Created record {r.record_id} for {r.child_name} "
          f"({r.record_type}).")


@_safe
def _view_record() -> None:
    rid = _prompt("  Record ID: ")
    if not rid:
        return
    r = data.get_record(rid)
    if r is None:
        print("  No record with that ID.")
        return
    _print_detail(r)
    _prompt("  Press Enter to continue...")


@_safe
def _edit_record() -> None:
    rid = _prompt("  Record ID to edit: ")
    if not rid:
        print("  Cancelled.")
        return
    existing = data.get_record(rid)
    if existing is None:
        print("  No record with that ID.")
        return
    print("  Press Enter to keep the existing value.")
    fields = _collect_fields(existing)
    r = data.update_record(rid, fields)
    print(f"\n  ✓ Updated record {r.record_id}.")


@_safe
def _delete_record() -> None:
    rid = _prompt("  Record ID to delete: ")
    if not rid:
        print("  Cancelled.")
        return
    existing = data.get_record(rid)
    if existing is None:
        print("  No record with that ID.")
        return
    confirm = _prompt(
        f"  Delete record {rid} for {existing.child_name}? (y/N): ").lower()
    if confirm != "y":
        print("  Cancelled.")
        return
    if data.delete_record(rid):
        print(f"  ✓ Deleted record {rid}.")
    else:
        print("  Could not delete (already removed?).")


@_safe
def _summary() -> None:
    s = data.summary()
    print("\n  ── Accident / Incident Summary ──")
    print(f"  Total records:    {s['total']}")
    print(f"  Open:             {s['open_count']}")
    print(f"  RIDDOR-reportable:{s['riddor_count']}")
    print(f"  Parent informed:  {s['parent_informed_count']} "
          f"({s['parent_informed_rate']}%)")
    print(f"  Last 30 days:     {s['last_30_days']}")
    if s["by_type"]:
        print("  By type:     " + "  ".join(
            f"{k}={v}" for k, v in sorted(s["by_type"].items())))
    if s["by_severity"]:
        print("  By severity: " + "  ".join(
            f"{k}={v}" for k, v in sorted(s["by_severity"].items())))


def run(auth=None) -> None:
    """Entry point for the Accident / Incident Report CLI screen."""
    while True:
        print("\n  ══ Accident / Incident Report ══")
        print("   1) List records")
        print("   2) Add record")
        print("   3) View record")
        print("   4) Edit record")
        print("   5) Delete record")
        print("   6) Summary")
        print("   0) Back")
        choice = _prompt("  Select: ")
        if choice in ("0", ""):
            return
        if choice == "1":
            _list_records()
        elif choice == "2":
            _add_record()
        elif choice == "3":
            _view_record()
        elif choice == "4":
            _edit_record()
        elif choice == "5":
            _delete_record()
        elif choice == "6":
            _summary()
        else:
            print("  Invalid selection.")


def dispatch(label: str) -> bool:
    if label != "Accident / Incident Report":
        return False
    logger.debug("Dispatching accident_report CLI label: %s", label)
    run()
    return True
