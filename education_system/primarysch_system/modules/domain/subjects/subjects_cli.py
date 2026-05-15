"""CLI handlers for the subjects catalogue."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.primarysch_system.modules.domain.subjects import (
    subjects as data,
)
from education_system.primarysch_system.modules.domain.subjects.subjects import (
    KEY_STAGES, QUALIFICATIONS,
)
from education_system.primarysch_system.modules.domain.pupils.pupils import (
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
        except Exception as e:
            logger.exception("%s failed", func.__name__)
            print(f"  Error: {e}")
            print("  See logs for details.")
    return wrapper


def _print_table(rows: list[data.Subject]) -> None:
    if not rows:
        print("  (no subjects)")
        return
    print(f"  {'ID':<5} {'Code':<8} {'Name':<28} {'KS':<5} "
          f"{'Qual':<6} {'Dept':<14} {'Core':<5} {'Active':<6}")
    print(f"  {'-'*5} {'-'*8} {'-'*28} {'-'*5} {'-'*6} {'-'*14} {'-'*5} {'-'*6}")
    for s in rows:
        print(f"  {s.subject_id:<5} {s.code:<8} {s.name[:28]:<28} "
              f"{s.key_stage:<5} {s.qualification:<6} "
              f"{(s.department or '-')[:14]:<14} "
              f"{('Y' if s.is_core else 'N'):<5} "
              f"{('Y' if s.is_active else 'N'):<6}")


@_safe
def open_subjects() -> None:
    logger.debug("CLI: open_subjects")
    while True:
        c = data.counts()
        print("\n  ── Subjects ──")
        print(f"  Total: {c['total']}   Active: {c['active']}   "
              f"Inactive: {c['inactive']}   Core: {c['core']}")
        print("\n   1) New subject")
        print("   2) List subjects")
        print("   3) View subject")
        print("   4) Edit subject")
        print("   5) Toggle active")
        print("   6) Delete subject")
        print("   0) Back")
        choice = _prompt("  Select: ")
        if choice in ("0", ""):
            return
        actions = {
            "1": _new,
            "2": _list,
            "3": _view,
            "4": _edit,
            "5": _toggle,
            "6": _delete,
        }
        handler = actions.get(choice)
        if handler is None:
            print("  Invalid selection.")
            continue
        handler()


def _collect(existing: data.Subject | None = None) -> dict[str, str]:
    def ask(label: str, current: str | None) -> str:
        suffix = f" [{current}]" if current else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else (current or "")
    f: dict[str, str] = {}
    f["code"] = ask("Code (2–8 chars, e.g. MATH)",
                    existing.code if existing else None)
    f["name"] = ask("Display name",
                    existing.name if existing else None)
    f["key_stage"] = ask(f"Key stage ({'/'.join(KEY_STAGES)})",
                         existing.key_stage if existing else "Both")
    f["qualification"] = ask(
        f"Qualification ({'/'.join(QUALIFICATIONS)})",
        existing.qualification if existing else "GCSE")
    f["department"] = ask("Department",
                          existing.department if existing else None)
    core_cur = "y" if (existing and existing.is_core) else "n"
    f["is_core"] = ask("Core/compulsory? (y/n)", core_cur)
    f["notes"] = ask("Notes",
                     existing.notes if existing else None)
    # Normalise booleans
    f["is_core"] = "1" if f["is_core"].lower().startswith("y") else "0"
    return f


@_safe
def _new() -> None:
    print("\n  ── New Subject ──")
    fields = _collect()
    rec = data.create({**fields, "is_core": bool(int(fields["is_core"]))})
    print(f"  Created subject #{rec.subject_id} {rec.code} — {rec.name}")


@_safe
def _list() -> None:
    print(f"\n  Filter — key stage ({'/'.join(KEY_STAGES)}), blank for all.")
    ks = _prompt("  Key stage: ") or None
    print(f"  Filter — qualification ({'/'.join(QUALIFICATIONS)}), blank for all.")
    qual = _prompt("  Qualification: ") or None
    only_active = _prompt("  Active only? (y/N): ").lower().startswith("y")
    rows = data.list_all(key_stage=ks, qualification=qual,
                         active_only=only_active)
    print(f"\n  {len(rows)} subject(s):")
    _print_table(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def _view() -> None:
    sid = _prompt("  Subject ID: ")
    if not sid:
        return
    try:
        subject_id = int(sid)
    except ValueError:
        print("  Subject ID must be a number.")
        return
    s = data.get(subject_id)
    if s is None:
        print("  No subject with that ID.")
        return
    print(f"\n  ── Subject #{s.subject_id} ──")
    print(f"  Code:           {s.code}")
    print(f"  Name:           {s.name}")
    print(f"  Key stage:      {s.key_stage}")
    print(f"  Qualification:  {s.qualification}")
    print(f"  Department:     {s.department or '-'}")
    print(f"  Core:           {'Yes' if s.is_core else 'No'}")
    print(f"  Active:         {'Yes' if s.is_active else 'No'}")
    print(f"  Notes:          {s.notes or '-'}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _edit() -> None:
    sid = _prompt("  Subject ID: ")
    if not sid:
        return
    try:
        subject_id = int(sid)
    except ValueError:
        print("  Subject ID must be a number.")
        return
    existing = data.get(subject_id)
    if existing is None:
        print("  No subject with that ID.")
        return
    print("  Press Enter to keep existing value.")
    fields = _collect(existing)
    rec = data.update(subject_id, {
        **fields, "is_core": bool(int(fields["is_core"]))})
    print(f"  Updated subject #{rec.subject_id} {rec.code}")


@_safe
def _toggle() -> None:
    sid = _prompt("  Subject ID: ")
    if not sid:
        return
    try:
        subject_id = int(sid)
    except ValueError:
        print("  Subject ID must be a number.")
        return
    rec = data.toggle_active(subject_id)
    print(f"  Subject {rec.code} is now "
          f"{'active' if rec.is_active else 'inactive'}.")


@_safe
def _delete() -> None:
    sid = _prompt("  Subject ID: ")
    if not sid:
        return
    try:
        subject_id = int(sid)
    except ValueError:
        print("  Subject ID must be a number.")
        return
    existing = data.get(subject_id)
    if existing is None:
        print("  No subject with that ID.")
        return
    confirm = _prompt(
        f"  Delete subject {existing.code} ({existing.name})? (y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    if data.delete(subject_id):
        print(f"  Deleted subject {existing.code}.")
    else:
        print("  Could not delete.")


_DISPATCH = {"Subjects (KS3 / GCSE)": open_subjects}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching subjects CLI label: %s", label)
    handler()
    return True
