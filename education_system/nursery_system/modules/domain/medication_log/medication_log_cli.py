"""CLI flow for Medication Log (Nursery System)."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.nursery_system.modules.domain.medication_log import (
    medication_log as data,
)
from education_system.nursery_system.modules.domain.medication_log.medication_log import (
    ROUTES,
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


def _pick(label: str, choices: list[tuple[str, str]],
          *, allow_blank: bool = True) -> str:
    if not choices:
        return ""
    print(f"  {label}:")
    for i, (_id, text) in enumerate(choices, 1):
        print(f"    {i}) {text}")
    suffix = " (Enter to skip)" if allow_blank else ""
    raw = _prompt(f"  Select {label.lower()} #{suffix}: ")
    if not raw:
        return ""
    try:
        idx = int(raw)
    except ValueError:
        print("  Invalid selection.")
        return ""
    if 1 <= idx <= len(choices):
        return choices[idx - 1][0]
    print("  Invalid selection.")
    return ""


def _pick_option(label: str, options: tuple[str, ...], current: str | None) -> str:
    cur = current or ""
    opts = "/".join(options)
    suffix = f" [{cur}]" if cur else ""
    v = _prompt(f"  {label} ({opts}){suffix}: ")
    return v if v else cur


def _print_table(rows: list[data.MedicationRecord]) -> None:
    if not rows:
        print("  (no medication records)")
        return
    print(f"  {'ID':<8} {'Date':<11} {'Child':<20} {'Medication':<16} "
          f"{'Dose':<8} {'Route':<8} {'Cons':<5} {'Status'}")
    print(f"  {'-'*8} {'-'*11} {'-'*20} {'-'*16} {'-'*8} {'-'*8} {'-'*5} {'-'*11}")
    for r in rows:
        cons = "Yes" if r.parent_consent else "No"
        print(f"  {r.record_id:<8} {(r.administered_date or '-'):<11} "
              f"{(r.child_name or '-')[:20]:<20} {r.medication_name[:16]:<16} "
              f"{(r.dose or '-')[:8]:<8} {(r.route or '-')[:8]:<8} "
              f"{cons:<5} {r.status}")


def _print_detail(r: data.MedicationRecord) -> None:
    print(f"\n  ── Medication record {r.record_id} ──")
    print(f"  Child:           {r.child_name or '-'} ({r.pupil_id})")
    print(f"  Medication:      {r.medication_name}")
    print(f"  Dose:            {r.dose or '-'}")
    print(f"  Route:           {r.route or '-'}")
    print(f"  Reason:          {r.reason or '-'}")
    print(f"  Administered:    {r.administered_date or '-'} {r.administered_time or ''}")
    print(f"  Administered by: {r.administered_by_name or '-'}")
    print(f"  Witnessed by:    {r.witnessed_by_name or '-'}")
    print(f"  Parent consent:  {'Yes' if r.parent_consent else 'No'}")
    print(f"  Expiry date:     {r.expiry_date or '-'}")
    print(f"  Status:          {r.status}")
    print(f"  Notes:           {r.notes or '-'}")


def _collect_fields(existing: data.MedicationRecord | None = None,
                    *, pupil_id: str | None = None) -> dict[str, str]:
    def ask(label: str, current=None) -> str:
        cur = "" if current is None else str(current)
        suffix = f" [{cur}]" if cur else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else cur

    fields: dict[str, str] = {}
    if pupil_id is not None:
        fields["pupil_id"] = pupil_id
    fields["medication_name"] = ask(
        "Medication name", existing.medication_name if existing else None)
    fields["dose"] = ask("Dose", existing.dose if existing else None)
    fields["route"] = _pick_option(
        "Route", ROUTES, existing.route if existing else "Oral")
    fields["reason"] = ask("Reason", existing.reason if existing else None)
    fields["administered_date"] = ask(
        "Administered date (YYYY-MM-DD)",
        existing.administered_date if existing else None)
    fields["administered_time"] = ask(
        "Administered time (HH:MM)",
        existing.administered_time if existing else None)

    staff = data.list_staff_choices()
    by_pick = _pick("Administered by", staff)
    fields["administered_by"] = by_pick or (
        existing.administered_by if existing else "") or ""
    wit_pick = _pick("Witnessed by", staff)
    fields["witnessed_by"] = wit_pick or (
        existing.witnessed_by if existing else "") or ""

    cur_consent = ("y" if existing.parent_consent else "n") if existing else None
    fields["parent_consent"] = ask("Parent consent? (y/n)", cur_consent)
    fields["expiry_date"] = ask(
        "Expiry date (YYYY-MM-DD)", existing.expiry_date if existing else None)
    fields["status"] = _pick_option(
        "Status", STATUSES, existing.status if existing else "administered")
    fields["notes"] = ask("Notes", existing.notes if existing else None)
    return fields


@_safe
def open_manager() -> None:
    logger.debug("CLI: medication_log open_manager")
    while True:
        s = data.summary()
        print("\n  ── Medication Log ──")
        print(f"  Records: {s['records']}   Administered: {s['administered']}   "
              f"Scheduled: {s['scheduled']}   Refused: {s['refused']}   "
              f"No consent: {s['no_consent']}")
        _print_table(data.list_records())
        print("\n   L) List (filter)   A) Add   V) View   E) Edit")
        print("   D) Delete   S) Summary   0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in ("0", ""):
            return
        if choice == "l":
            open_list()
        elif choice == "a":
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
        elif choice == "s":
            _print_summary()
            _prompt("  Press Enter to continue...")
        else:
            print("  Invalid selection.")


@_safe
def open_list() -> None:
    date = _prompt("  Filter administered date (YYYY-MM-DD, Enter for all): ")
    status = _pick_option("  Filter status", STATUSES, None)
    rows = data.list_records(administered_date=date or None,
                             status=status or None)
    _print_table(rows)
    _prompt("  Press Enter to continue...")


def _print_summary() -> None:
    s = data.summary()
    print("\n  ── Medication summary ──")
    print(f"  Total records:  {s['records']}")
    print(f"  Administered:   {s['administered']}")
    print(f"  Scheduled:      {s['scheduled']}")
    print(f"  Refused:        {s['refused']}")
    print(f"  No consent:     {s['no_consent']}")


@_safe
def open_add() -> None:
    logger.debug("CLI: medication_log open_add")
    print("\n  ── Add Medication Record ──")
    pid = _pick("Child", data.list_pupil_choices(), allow_blank=False)
    if not pid:
        print("  Cancelled.")
        return
    fields = _collect_fields(pupil_id=pid)
    consent = fields.get("parent_consent", "").strip().lower()
    status = fields.get("status", "").strip().lower()
    if status == "administered" and consent not in ("y", "yes", "1", "true", "on"):
        print("  WARNING: recording an administered medicine without parent "
              "consent.")
    r = data.create_record(fields)
    print(f"\n  Created medication record {r.record_id} for {r.child_name} "
          f"({r.medication_name}).")


@_safe
def open_edit() -> None:
    logger.debug("CLI: medication_log open_edit")
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
    print(f"\n  Updated medication record {r.record_id}.")


@_safe
def open_delete() -> None:
    logger.debug("CLI: medication_log open_delete")
    rid = _prompt("  Record ID to delete: ")
    if not rid:
        print("  Cancelled.")
        return
    existing = data.get_record(rid)
    if existing is None:
        print("  No record with that ID.")
        return
    confirm = _prompt(
        f"  Delete medication record {rid} for {existing.child_name}? (y/N): "
    ).lower()
    if confirm != "y":
        print("  Cancelled.")
        return
    if data.delete_record(rid):
        print(f"  Deleted record {rid}.")
    else:
        print("  Could not delete (already removed?).")


_DISPATCH = {"Medication Log": open_manager}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching medication_log CLI label: %s", label)
    handler()
    return True


def run(auth=None) -> None:
    open_manager()
