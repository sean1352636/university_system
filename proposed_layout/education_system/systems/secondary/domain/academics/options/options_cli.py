"""CLI handlers for the GCSE options process."""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable

from education_system.systems.secondary.domain.academics.options import (
    options as data,
)
from education_system.systems.secondary.domain.academics.options.options import (
    ROUND_STATUSES,
)
from education_system.systems.secondary.domain.academics.subjects import (
    subjects as subjects_data,
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


def _print_rounds(rows: list[data.OptionRound]) -> None:
    if not rows:
        print("  (no rounds)")
        return
    print(f"  {'ID':<4} {'Name':<30} {'Yr':<3} {'Status':<7} "
          f"{'Opens':<10} {'Closes':<10} {'Picks':<5} {'Res':<3}")
    print(f"  {'-'*4} {'-'*30} {'-'*3} {'-'*7} {'-'*10} {'-'*10} "
          f"{'-'*5} {'-'*3}")
    for r in rows:
        print(f"  {r.round_id:<4} {r.name[:30]:<30} {r.year_group:<3} "
              f"{r.status:<7} {(r.opens_on or '-'):<10} "
              f"{(r.closes_on or '-'):<10} "
              f"{r.choices_required:<5} {r.reserves_required:<3}")


@_safe
def open_options() -> None:
    logger.debug("CLI: open_options")
    while True:
        rows = data.list_rounds()
        print("\n  ── Options Process ──")
        _print_rounds(rows)
        print("\n   1) New round")
        print("   2) View / edit round")
        print("   3) Manage round subjects")
        print("   4) Submit pupil choices")
        print("   5) View pupil choices")
        print("   6) Submission summary")
        print("   7) Set round status")
        print("   8) Delete round")
        print("   0) Back")
        choice = _prompt("  Select: ")
        if choice in ("0", ""):
            return
        actions = {
            "1": _new_round,
            "2": _edit_round,
            "3": _manage_subjects,
            "4": _submit_choices,
            "5": _view_choices,
            "6": _summary,
            "7": _set_status,
            "8": _delete_round,
        }
        handler = actions.get(choice)
        if handler is None:
            print("  Invalid selection.")
            continue
        handler()


def _collect_round(existing: data.OptionRound | None = None
                   ) -> dict[str, Any]:
    def ask(label: str, current) -> str:
        suffix = f" [{current}]" if current not in (None, "") else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else (str(current) if current not in (None, "") else "")
    f: dict[str, Any] = {}
    f["name"]              = ask("Name (e.g. Year 9→10 GCSE 2025/26)",
                                 existing.name if existing else None)
    f["year_group"]        = ask(f"Year group ({'/'.join(YEAR_GROUPS)})",
                                 existing.year_group if existing else "9")
    f["status"]            = ask(f"Status ({'/'.join(ROUND_STATUSES)})",
                                 existing.status if existing else "Draft")
    f["opens_on"]          = ask("Opens on (YYYY-MM-DD)",
                                 existing.opens_on if existing else None)
    f["closes_on"]         = ask("Closes on (YYYY-MM-DD)",
                                 existing.closes_on if existing else None)
    f["choices_required"]  = ask("Primary choices required",
                                 existing.choices_required if existing else 4)
    f["reserves_required"] = ask("Reserves required",
                                 existing.reserves_required if existing else 1)
    f["notes"]             = ask("Notes",
                                 existing.notes if existing else None)
    return f


@_safe
def _new_round() -> None:
    print("\n  ── New Options Round ──")
    fields = _collect_round()
    rec = data.create_round(fields)
    print(f"  Created round #{rec.round_id} {rec.name}")


def _ask_round_id(label: str = "Round ID") -> int | None:
    rid = _prompt(f"  {label}: ")
    if not rid:
        return None
    try:
        return int(rid)
    except ValueError:
        print(f"  {label} must be a number.")
        return None


@_safe
def _edit_round() -> None:
    rid = _ask_round_id()
    if rid is None:
        return
    existing = data.get_round(rid)
    if existing is None:
        print("  No round with that ID.")
        return
    print("  Press Enter to keep existing value.")
    fields = _collect_round(existing)
    rec = data.update_round(rid, fields)
    print(f"  Updated round #{rec.round_id} {rec.name} (status {rec.status})")


@_safe
def _set_status() -> None:
    rid = _ask_round_id()
    if rid is None:
        return
    existing = data.get_round(rid)
    if existing is None:
        print("  No round with that ID.")
        return
    print(f"  Current status: {existing.status}")
    print(f"  Allowed: {', '.join(ROUND_STATUSES)}")
    new = _prompt("  New status: ")
    if not new:
        return
    rec = data.set_round_status(rid, new)
    print(f"  Round #{rec.round_id} status -> {rec.status}")


@_safe
def _delete_round() -> None:
    rid = _ask_round_id()
    if rid is None:
        return
    existing = data.get_round(rid)
    if existing is None:
        print("  No round with that ID.")
        return
    confirm = _prompt(
        f"  Delete round '{existing.name}' "
        f"and all linked subjects + pupil choices? (y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    if data.delete_round(rid):
        print(f"  Deleted round #{rid}.")
    else:
        print("  Could not delete.")


@_safe
def _manage_subjects() -> None:
    rid = _ask_round_id()
    if rid is None:
        return
    rnd = data.get_round(rid)
    if rnd is None:
        print("  No round with that ID.")
        return
    while True:
        current = data.list_round_subjects(rid)
        print(f"\n  ── Subjects in round '{rnd.name}' ──")
        if not current:
            print("  (none assigned yet)")
        else:
            for s in current:
                print(f"  #{s.subject_id:<4} {s.code:<8} {s.name}")
        print("\n   1) Add subject (from catalogue)")
        print("   2) Remove subject")
        print("   0) Back")
        choice = _prompt("  Select: ")
        if choice in ("0", ""):
            return
        if choice == "1":
            print("\n  Active subjects in catalogue:")
            avail = subjects_data.list_all(active_only=True)
            already = {s.subject_id for s in current}
            avail = [s for s in avail if s.subject_id not in already]
            if not avail:
                print("  (no more active subjects to add)")
                continue
            for s in avail:
                print(f"  #{s.subject_id:<4} {s.code:<8} {s.name} "
                      f"({s.qualification})")
            sid = _prompt("  Subject ID to add: ")
            if not sid:
                continue
            try:
                data.add_round_subject(rid, int(sid))
                print("  Added.")
            except ValueError:
                print("  Subject ID must be a number.")
        elif choice == "2":
            sid = _prompt("  Subject ID to remove: ")
            if not sid:
                continue
            try:
                data.remove_round_subject(rid, int(sid))
                print("  Removed.")
            except ValueError:
                print("  Subject ID must be a number.")
        else:
            print("  Invalid selection.")


@_safe
def _submit_choices() -> None:
    rid = _ask_round_id()
    if rid is None:
        return
    rnd = data.get_round(rid)
    if rnd is None:
        print("  No round with that ID.")
        return
    print(f"  Round '{rnd.name}' — status {rnd.status}")
    print(f"  Needs {rnd.choices_required} primary + "
          f"{rnd.reserves_required} reserve choices.")
    pupil_id = _prompt("  Pupil ID: ")
    if not pupil_id:
        return
    avail = data.list_round_subjects(rid)
    if not avail:
        print("  Round has no subjects configured.")
        return
    print("\n  Available subjects:")
    for s in avail:
        print(f"  #{s.subject_id:<4} {s.code:<8} {s.name}")
    print(f"\n  Enter {rnd.choices_required} primary subject IDs, "
          f"comma-separated:")
    primary_raw = _prompt("  Primary: ")
    print(f"  Enter {rnd.reserves_required} reserve subject ID(s), "
          f"comma-separated:")
    reserve_raw = _prompt("  Reserves: ")

    def _parse(raw: str) -> list[int]:
        if not raw:
            return []
        try:
            return [int(x.strip()) for x in raw.split(",") if x.strip()]
        except ValueError:
            raise ValidationError(
                "Subject IDs must be whole numbers, comma-separated") from None

    primary = _parse(primary_raw)
    reserves = _parse(reserve_raw)
    saved = data.submit_pupil_choices(rid, pupil_id, primary, reserves)
    print(f"  Saved {len(saved)} pick(s) for {pupil_id}.")


@_safe
def _view_choices() -> None:
    rid = _ask_round_id()
    if rid is None:
        return
    rnd = data.get_round(rid)
    if rnd is None:
        print("  No round with that ID.")
        return
    pupil_id = _prompt("  Pupil ID: ")
    if not pupil_id:
        return
    rows = data.get_pupil_choices(rid, pupil_id)
    if not rows:
        print("  (no choices submitted)")
        return
    print(f"\n  Choices for pupil {pupil_id} in round '{rnd.name}':")
    for c in rows:
        subj = subjects_data.get(c.subject_id)
        tag = "RESERVE" if c.is_reserve else "PRIMARY"
        print(f"   #{c.rank:<2} [{tag:<7}] "
              f"{subj.code if subj else '?'} — "
              f"{subj.name if subj else '(unknown subject)'}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _summary() -> None:
    rid = _ask_round_id()
    if rid is None:
        return
    summary = data.submission_summary(rid)
    rnd = summary["round"]
    print(f"\n  ── Summary: {rnd.name} ──")
    print(f"  Status: {rnd.status}    "
          f"Pupils submitted: {summary['pupils_submitted']}    "
          f"Complete: {summary['pupils_complete']}    "
          f"Partial: {summary['pupils_partial']}")
    print("\n  Subject pick counts:")
    print(f"  {'Code':<8} {'Name':<28} {'Primary':<8} {'Reserve':<8}")
    print(f"  {'-'*8} {'-'*28} {'-'*8} {'-'*8}")
    for s in summary["subject_picks"]:
        print(f"  {s['code']:<8} {s['name'][:28]:<28} "
              f"{s['primary']:<8} {s['reserve']:<8}")
    _prompt("\n  Press Enter to continue...")


_DISPATCH = {"Options Process": open_options}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching options CLI label: %s", label)
    handler()
    return True
