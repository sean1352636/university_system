"""CLI handlers for bulk operations in the Secondary School System."""

from __future__ import annotations

import functools
import logging
from pathlib import Path
from typing import Callable

from education_system.systems.secondary.domain.learners.bulk_operations import (
    bulk_operations as data,
)
from education_system.systems.secondary.domain.learners.bulk_operations.bulk_operations import (
    BulkResult, BULK_UPDATABLE, IMPORT_COLUMNS, REQUIRED_COLUMNS,
)
from education_system.systems.secondary.domain.learners.pupils.pupils import (
    ValidationError, YEAR_GROUPS,
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
        except Exception as e:
            logger.exception("%s failed", func.__name__)
            print(f"  Error: {e}")
            print("  See logs for details.")
    return wrapper


def _print_result(result: BulkResult, *, limit: int = 10) -> None:
    print(f"\n  Processed: {result.processed}")
    print(f"  Succeeded: {result.succeeded}")
    print(f"  Failed:    {result.failed}")
    if result.created_ids:
        head = ", ".join(result.created_ids[:5])
        more = "" if len(result.created_ids) <= 5 else f", … (+{len(result.created_ids) - 5} more)"
        print(f"  Created:   {head}{more}")
    if result.errors:
        shown = result.errors[:limit]
        print(f"\n  First {len(shown)} error(s):")
        for err in shown:
            label = err.raw.get("pupil_id") or f"row {err.row_number}"
            print(f"    - {label}: {err.message}")
        if len(result.errors) > limit:
            print(f"    … (+{len(result.errors) - limit} more — see logs)")


@_safe
def open_bulk_operations() -> None:
    logger.debug("CLI: open_bulk_operations")
    while True:
        print("\n  ── Bulk Operations ──")
        print("   1) Import pupils from CSV")
        print("   2) Export pupils to CSV")
        print("   3) Bulk update field")
        print("   4) Bulk delete pupils")
        print("   5) Show CSV format help")
        print("   0) Back")
        choice = _prompt("  Select: ")
        if choice == "0" or choice == "":
            return
        actions = {
            "1": _import_csv,
            "2": _export_csv,
            "3": _bulk_update,
            "4": _bulk_delete,
            "5": _show_format,
        }
        action = actions.get(choice)
        if action is None:
            print("  Invalid selection.")
            continue
        action()


@_safe
def _import_csv() -> None:
    print("\n  ── Import Pupils from CSV ──")
    print(f"  Required columns: {', '.join(REQUIRED_COLUMNS)}")
    print(f"  Optional columns: "
          f"{', '.join(c for c in IMPORT_COLUMNS if c not in REQUIRED_COLUMNS)}")
    raw_path = _prompt("  CSV path: ")
    if not raw_path:
        return
    path = Path(raw_path).expanduser()
    result = data.import_pupils_csv(path)
    _print_result(result)
    _prompt("\n  Press Enter to continue...")


@_safe
def _export_csv() -> None:
    print("\n  ── Export Pupils to CSV ──")
    raw_path = _prompt("  Output CSV path: ")
    if not raw_path:
        return
    path = Path(raw_path).expanduser()
    count = data.export_pupils_csv(path)
    print(f"  Wrote {count} pupil(s) to {path}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _bulk_update() -> None:
    print("\n  ── Bulk Update Field ──")
    print(f"  Allowed fields: {', '.join(BULK_UPDATABLE)}")
    field = _prompt("  Field: ").strip().lower()
    if not field:
        return
    if field not in BULK_UPDATABLE:
        print(f"  Field must be one of: {', '.join(BULK_UPDATABLE)}")
        return
    if field == "year_group":
        print(f"  Allowed values: {', '.join(YEAR_GROUPS)}")
    elif field == "send_status":
        print("  Allowed values: yes, no, or blank to clear")
    value = _prompt("  New value: ")
    raw_ids = _prompt("  Pupil IDs (comma-separated): ")
    if not raw_ids:
        return
    ids = [pid.strip() for pid in raw_ids.split(",") if pid.strip()]
    if not ids:
        print("  No pupil ids supplied.")
        return
    confirm = _prompt(
        f"  Apply {field} = {value!r} to {len(ids)} pupil(s)? (y/N): "
    )
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    result = data.bulk_update(ids, field, value)
    _print_result(result)
    _prompt("\n  Press Enter to continue...")


@_safe
def _bulk_delete() -> None:
    print("\n  ── Bulk Delete Pupils ──")
    raw_ids = _prompt("  Pupil IDs (comma-separated): ")
    if not raw_ids:
        return
    ids = [pid.strip() for pid in raw_ids.split(",") if pid.strip()]
    if not ids:
        print("  No pupil ids supplied.")
        return
    confirm = _prompt(f"  Delete {len(ids)} pupil(s)? Type 'DELETE' to confirm: ")
    if confirm != "DELETE":
        print("  Cancelled.")
        return
    result = data.bulk_delete(ids)
    _print_result(result)
    _prompt("\n  Press Enter to continue...")


@_safe
def _show_format() -> None:
    print("\n  ── CSV Import Format ──")
    print("  - UTF-8 encoded with a header row")
    print(f"  - Required columns: {', '.join(REQUIRED_COLUMNS)}")
    print(f"  - Optional columns: "
          f"{', '.join(c for c in IMPORT_COLUMNS if c not in REQUIRED_COLUMNS)}")
    print(f"  - Year group values: {', '.join(YEAR_GROUPS)}")
    print("  - Date of birth: YYYY-MM-DD")
    print("  - send_status: yes / no / blank")
    print("  - pupil_id and email are generated automatically")
    _prompt("\n  Press Enter to continue...")


_DISPATCH = {"Bulk Operations": open_bulk_operations}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching bulk_operations CLI label: %s", label)
    handler()
    return True
