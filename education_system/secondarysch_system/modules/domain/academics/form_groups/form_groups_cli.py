"""CLI handlers for form groups."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.secondarysch_system.modules.domain.academics.form_groups import (
    form_groups as data,
)
from education_system.secondarysch_system.modules.domain.pupils.pupils.pupils import (
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


def _print_table(rows: list[data.FormGroup],
                 counts: dict[int, int]) -> None:
    if not rows:
        print("  (no form groups)")
        return
    print(f"  {'ID':<5} {'Year':<5} {'Name':<10} {'Tutor':<22} "
          f"{'Room':<10} {'Pupils':<7}")
    print(f"  {'-'*5} {'-'*5} {'-'*10} {'-'*22} {'-'*10} {'-'*7}")
    for f in rows:
        print(f"  {f.form_id:<5} {f.year_group:<5} {f.name:<10} "
              f"{(f.form_tutor or '-'):<22} {(f.room or '-'):<10} "
              f"{counts.get(f.form_id, 0):<7}")


@_safe
def open_form_groups() -> None:
    logger.debug("CLI: open_form_groups")
    while True:
        rows = data.list_all()
        counts = data.pupil_counts()
        print("\n  ── Form Groups ──")
        print(f"  {len(rows)} form group(s) configured.")
        _print_table(rows, counts)
        print("\n   1) New form group")
        print("   2) List by year")
        print("   3) Edit form group")
        print("   4) Delete form group")
        print("   0) Back")
        choice = _prompt("  Select: ")
        if choice in ("0", ""):
            return
        actions = {
            "1": _new,
            "2": _list_by_year,
            "3": _edit,
            "4": _delete,
        }
        handler = actions.get(choice)
        if handler is None:
            print("  Invalid selection.")
            continue
        handler()


def _collect(existing: data.FormGroup | None = None) -> dict[str, str]:
    def ask(label: str, current: str | None) -> str:
        suffix = f" [{current}]" if current else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else (current or "")
    f: dict[str, str] = {}
    f["name"]       = ask("Form name (e.g. 7A)",
                          existing.name if existing else None)
    f["year_group"] = ask(f"Year group ({'/'.join(YEAR_GROUPS)})",
                          existing.year_group if existing else None)
    f["form_tutor"] = ask("Form tutor",
                          existing.form_tutor if existing else None)
    f["room"]       = ask("Room",
                          existing.room if existing else None)
    f["notes"]      = ask("Notes",
                          existing.notes if existing else None)
    return f


@_safe
def _new() -> None:
    print("\n  ── New Form Group ──")
    fields = _collect()
    rec = data.create(fields)
    print(f"  Created form #{rec.form_id} {rec.name} (Year {rec.year_group})")


@_safe
def _list_by_year() -> None:
    yg = _prompt(f"  Year ({'/'.join(YEAR_GROUPS)}) — blank for all: ")
    rows = data.list_all(year_group=yg or None)
    counts = data.pupil_counts()
    print(f"\n  {len(rows)} form group(s):")
    _print_table(rows, counts)
    _prompt("\n  Press Enter to continue...")


@_safe
def _edit() -> None:
    fid = _prompt("  Form ID: ")
    if not fid:
        return
    try:
        form_id = int(fid)
    except ValueError:
        print("  Form ID must be a number.")
        return
    existing = data.get(form_id)
    if existing is None:
        print("  No form group with that ID.")
        return
    print("  Press Enter to keep existing value.")
    fields = _collect(existing)
    rec = data.update(form_id, fields)
    print(f"  Updated form #{rec.form_id} {rec.name} "
          f"(Year {rec.year_group})")


@_safe
def _delete() -> None:
    fid = _prompt("  Form ID: ")
    if not fid:
        return
    try:
        form_id = int(fid)
    except ValueError:
        print("  Form ID must be a number.")
        return
    existing = data.get(form_id)
    if existing is None:
        print("  No form group with that ID.")
        return
    confirm = _prompt(
        f"  Delete form {existing.name} (Year {existing.year_group})? "
        f"(y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    if data.delete(form_id):
        print(f"  Deleted form {existing.name}.")
    else:
        print("  Could not delete.")


_DISPATCH = {"Form Groups": open_form_groups}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching form_groups CLI label: %s", label)
    handler()
    return True
