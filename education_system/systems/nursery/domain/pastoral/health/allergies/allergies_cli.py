"""CLI flow for Allergies & Dietary Requirements (Nursery System)."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.systems.nursery.domain.pastoral.health.allergies import (
    allergies as data,
)
from education_system.systems.nursery.domain.pastoral.health.allergies.allergies import (
    CATEGORIES,
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
            print(f"  Validation error: {e}")
        except Exception as e:  # noqa: BLE001
            logger.exception("%s failed", func.__name__)
            print(f"  Error: {e}")
            print("  See logs for details.")
    return wrapper


def _pick(label: str, options: tuple[str, ...], current: str | None = None,
          *, allow_blank: bool = False) -> str:
    print(f"  {label}:")
    for i, opt in enumerate(options, 1):
        print(f"    {i}) {opt}")
    suffix = f" [{current}]" if current else ""
    raw = _prompt(f"  Choose 1-{len(options)}{suffix}: ")
    if not raw:
        if current:
            return current
        return "" if allow_blank else options[0]
    if raw.isdigit() and 1 <= int(raw) <= len(options):
        return options[int(raw) - 1]
    if raw.lower() in options:
        return raw.lower()
    print("  (using default)")
    return current or ("" if allow_blank else options[0])


def _print_table(rows: list[data.DietaryRecord]) -> None:
    if not rows:
        print("  (no dietary records)")
        return
    print(f"  {'ID':<8} {'Child':<22} {'Category':<12} {'Allergen':<16} "
          f"{'Severity':<12} {'EpiPen':<7} {'Status'}")
    print(f"  {'-'*8} {'-'*22} {'-'*12} {'-'*16} {'-'*12} {'-'*7} {'-'*8}")
    for r in rows:
        epipen = "Yes" if r.epipen_required else "No"
        print(f"  {r.record_id:<8} {(r.child_name or '-')[:22]:<22} "
              f"{r.category[:12]:<12} {(r.allergen or '-')[:16]:<16} "
              f"{(r.severity or '-'):<12} {epipen:<7} {r.status}")


def _print_detail(r: data.DietaryRecord) -> None:
    print(f"\n  ── Dietary record {r.record_id} ──")
    print(f"  Child:           {r.child_name or '-'} ({r.pupil_id})")
    print(f"  Category:        {r.category}")
    print(f"  Allergen:        {r.allergen or '-'}")
    print(f"  Severity:        {r.severity or '-'}")
    print(f"  Reaction:        {r.reaction or '-'}")
    print(f"  Action required: {r.action_required or '-'}")
    print(f"  EpiPen required: {'Yes' if r.epipen_required else 'No'}")
    print(f"  Care-plan ref:   {r.care_plan_ref or '-'}")
    print(f"  Status:          {r.status}")
    print(f"  Notes:           {r.notes or '-'}")


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


def _collect_fields(existing: data.DietaryRecord | None = None,
                    *, pupil_id: str | None = None) -> dict[str, str]:
    def ask(label: str, current=None) -> str:
        cur = "" if current is None else str(current)
        suffix = f" [{cur}]" if cur else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else cur

    fields: dict[str, str] = {}
    if pupil_id is not None:
        fields["pupil_id"] = pupil_id
    fields["category"] = _pick("Category", CATEGORIES,
                               existing.category if existing else None)
    fields["allergen"] = ask("Allergen", existing.allergen if existing else None)
    fields["severity"] = _pick("Severity", SEVERITIES,
                               existing.severity if existing else None,
                               allow_blank=True)
    fields["reaction"] = ask("Reaction", existing.reaction if existing else None)
    fields["action_required"] = ask("Action required",
                                    existing.action_required if existing else None)
    epipen_cur = ("y" if existing.epipen_required else "n") if existing else None
    fields["epipen_required"] = ask("EpiPen required? (y/n)", epipen_cur)
    fields["care_plan_ref"] = ask("Care-plan ref",
                                  existing.care_plan_ref if existing else None)
    if existing is not None:
        fields["status"] = _pick("Status", STATUSES, existing.status)
    fields["notes"] = ask("Notes", existing.notes if existing else None)
    return fields


@_safe
def open_manager() -> None:
    logger.debug("CLI: allergies open_manager")
    f_status: str | None = None
    f_category: str | None = None
    while True:
        s = data.summary()
        scope = []
        if f_status:
            scope.append(f"status={f_status}")
        if f_category:
            scope.append(f"category={f_category}")
        scope_txt = (" — " + ", ".join(scope)) if scope else ""
        print(f"\n  ── Allergies & Dietary Requirements{scope_txt} ──")
        print(f"  Active records: {s['records']}   EpiPen children: "
              f"{s['epipen_children']}   Anaphylaxis: {s['anaphylaxis']}")
        if s["by_category"]:
            print("  By category: " + "  ".join(
                f"{k}={v}" for k, v in sorted(s["by_category"].items())))
        _print_table(data.list_records(status=f_status, category=f_category))
        print("\n   A) Add    V) View    E) Edit    D) Delete    R) Resolve/Activate")
        print("   S) Summary    F) Filter status    C) Filter category    0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in ("0", ""):
            return
        if choice == "a":
            open_add()
        elif choice == "v":
            rid = _prompt("  Record ID: ")
            r = data.get_record(rid)
            if r is None:
                print("  No record with that ID.")
            else:
                _print_detail(r)
                _prompt("  Press Enter to continue...")
        elif choice == "e":
            open_edit()
        elif choice == "d":
            open_delete()
        elif choice == "r":
            open_toggle_status()
        elif choice == "s":
            open_summary()
        elif choice == "f":
            sel = _pick("Filter status", STATUSES, allow_blank=True)
            f_status = sel or None
        elif choice == "c":
            sel = _pick("Filter category", CATEGORIES, allow_blank=True)
            f_category = sel or None
        else:
            print("  Invalid selection.")


@_safe
def open_add() -> None:
    logger.debug("CLI: allergies open_add")
    print("\n  ── Add Dietary Record ──")
    _show_children()
    pid = _prompt("  Child ID: ")
    if not pid:
        print("  Cancelled.")
        return
    fields = _collect_fields(pupil_id=pid)
    r = data.create_record(fields)
    print(f"\n  Created dietary record {r.record_id} for {r.child_name} "
          f"({r.category}).")


@_safe
def open_edit() -> None:
    logger.debug("CLI: allergies open_edit")
    rid = _prompt("  Record ID: ")
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
    print(f"\n  Updated dietary record {r.record_id}.")


@_safe
def open_delete() -> None:
    logger.debug("CLI: allergies open_delete")
    rid = _prompt("  Record ID to delete: ")
    if not rid:
        print("  Cancelled.")
        return
    existing = data.get_record(rid)
    if existing is None:
        print("  No record with that ID.")
        return
    confirm = _prompt(
        f"  Delete dietary record {rid} for {existing.child_name}? (y/N): "
    ).lower()
    if confirm != "y":
        print("  Cancelled.")
        return
    if data.delete_record(rid):
        print(f"  Deleted record {rid}.")
    else:
        print("  Could not delete (already removed?).")


@_safe
def open_toggle_status() -> None:
    rid = _prompt("  Record ID to resolve/activate: ")
    if not rid:
        print("  Cancelled.")
        return
    existing = data.get_record(rid)
    if existing is None:
        print("  No record with that ID.")
        return
    new_status = "resolved" if existing.status == "active" else "active"
    r = data.set_status(rid, new_status)
    print(f"  Record {r.record_id} is now {r.status}.")


@_safe
def open_summary() -> None:
    s = data.summary()
    print("\n  ── Allergies & Dietary Requirements summary ──")
    print(f"  Active records:   {s['records']}")
    print(f"  EpiPen children:  {s['epipen_children']}")
    print(f"  Anaphylaxis:      {s['anaphylaxis']}")
    if s["by_category"]:
        print("  By category:")
        for k, v in sorted(s["by_category"].items()):
            print(f"    {k}: {v}")
    _prompt("  Press Enter to continue...")


_DISPATCH = {"Allergies & Dietary Requirements": open_manager}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching allergies CLI label: %s", label)
    handler()
    return True


def run(auth=None) -> None:
    open_manager()
