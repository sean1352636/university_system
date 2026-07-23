"""CLI handlers for GCSE exam entries."""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable

from education_system.secondarysch_system.modules.domain.assessment.exam_entries import (
    exam_entries as data,
)
from education_system.secondarysch_system.modules.domain.assessment.exam_entries.exam_entries import (
    EXAM_BOARDS, TIERS, ENTRY_STATUSES,
)
from education_system.secondarysch_system.modules.domain.academics.subjects import (
    subjects as subjects_data,
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


def _print_table(rows: list[data.ExamEntry]) -> None:
    if not rows:
        print("  (no entries)")
        return
    print(f"  {'ID':<5} {'Pupil':<10} {'Yr':<3} {'Subj':<6} "
          f"{'Board':<8} {'Spec':<10} {'Tier':<10} {'Cand#':<10} "
          f"{'Status':<12} {'Fee':<6}")
    print(f"  {'-'*5} {'-'*10} {'-'*3} {'-'*6} {'-'*8} {'-'*10} {'-'*10} "
          f"{'-'*10} {'-'*12} {'-'*6}")
    for e in rows:
        fee = f"£{e.fee:g}" if e.fee is not None else "-"
        print(f"  {e.entry_id:<5} {e.pupil_id:<10} "
              f"{(e.pupil_year or '-'):<3} "
              f"{(e.subject_code or '?'):<6} {e.exam_board:<8} "
              f"{(e.spec_code or '-')[:10]:<10} {e.tier:<10} "
              f"{(e.candidate_number or '-')[:10]:<10} "
              f"{e.entry_status:<12} {fee:<6}")


@_safe
def open_exam_entries() -> None:
    logger.debug("CLI: open_exam_entries")
    while True:
        print("\n  ── GCSE Exam Entries ──")
        print("   1) New / update entry")
        print("   2) List entries")
        print("   3) View entry")
        print("   4) Set entry status")
        print("   5) Cohort summary")
        print("   6) Delete entry")
        print("   0) Back")
        choice = _prompt("  Select: ")
        if choice in ("0", ""):
            return
        actions = {
            "1": _upsert, "2": _list, "3": _view,
            "4": _set_status, "5": _summary, "6": _delete,
        }
        handler = actions.get(choice)
        if handler is None:
            print("  Invalid selection.")
            continue
        handler()


def _collect(existing: data.ExamEntry | None = None) -> dict[str, Any]:
    def ask(label: str, current) -> str:
        suffix = f" [{current}]" if current not in (None, "") else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else (str(current) if current not in (None, "") else "")
    f: dict[str, Any] = {}
    f["pupil_id"]   = ask("Pupil ID",
                            existing.pupil_id if existing else None)
    if not existing:
        print("  Active subjects:")
        for s in subjects_data.list_all(active_only=True)[:20]:
            print(f"    #{s.subject_id:<4} {s.code:<8} {s.name}")
    f["subject_id"] = ask("Subject ID",
                            existing.subject_id if existing else None)
    f["exam_board"] = ask(f"Exam board ({'/'.join(EXAM_BOARDS)})",
                            existing.exam_board if existing else "AQA")
    f["spec_code"]  = ask("Spec code (e.g. 8300)",
                            existing.spec_code if existing else None)
    f["tier"]       = ask(f"Tier ({'/'.join(TIERS)})",
                            existing.tier if existing else "N/A")
    f["candidate_number"] = ask(
        "Candidate number",
        existing.candidate_number if existing else None)
    f["entry_status"]     = ask(
        f"Status ({'/'.join(ENTRY_STATUSES)})",
        existing.entry_status if existing else "Provisional")
    f["entry_date"]       = ask(
        "Entry date (YYYY-MM-DD, blank = today)",
        existing.entry_date if existing else None)
    f["fee"]              = ask(
        "Fee (£, blank ok)",
        existing.fee if existing else None)
    f["notes"]            = ask("Notes",
                                  existing.notes if existing else None)
    return f


@_safe
def _upsert() -> None:
    print("\n  ── New / Update Entry ──")
    pid = _prompt("  Pupil ID: ")
    if not pid:
        return
    sid_raw = _prompt("  Subject ID: ")
    if not sid_raw:
        return
    try:
        sid = int(sid_raw)
    except ValueError:
        print("  Subject ID must be a number.")
        return
    existing = data.get_for(pid, sid)
    if existing:
        print(f"  Existing entry on {existing.exam_board}, "
              f"{existing.entry_status}.")
    fields = _collect(existing)
    fields["pupil_id"] = pid
    fields["subject_id"] = sid
    e = data.upsert(fields)
    print(f"  Saved entry #{e.entry_id}: {e.pupil_id} / "
          f"{e.subject_code} ({e.exam_board} {e.tier}, "
          f"{e.entry_status})")


@_safe
def _list() -> None:
    yg = _prompt(f"  Year ({'/'.join(YEAR_GROUPS)}, blank): ") or None
    sid_raw = _prompt("  Subject ID (blank): ")
    sid = None
    if sid_raw:
        try:
            sid = int(sid_raw)
        except ValueError:
            print("  Subject ID must be a number.")
            return
    board = _prompt(f"  Board ({'/'.join(EXAM_BOARDS)}, blank): ") or None
    status = _prompt(
        f"  Status ({'/'.join(ENTRY_STATUSES)}, blank): ") or None
    tier = _prompt(f"  Tier ({'/'.join(TIERS)}, blank): ") or None
    pid = _prompt("  Pupil ID (blank): ") or None
    rows = data.list_entries(year_group=yg, subject_id=sid,
                               exam_board=board, entry_status=status,
                               tier=tier, pupil_id=pid)
    print(f"\n  {len(rows)} entry(ies):")
    _print_table(rows)
    _prompt("\n  Press Enter to continue...")


def _ask_id(label: str) -> int | None:
    raw = _prompt(f"  {label}: ")
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        print(f"  {label} must be a number.")
        return None


@_safe
def _view() -> None:
    eid = _ask_id("Entry ID")
    if eid is None:
        return
    e = data.get(eid)
    if e is None:
        print("  No entry with that ID.")
        return
    print(f"\n  ── Entry #{e.entry_id} ──")
    print(f"  Pupil:        {e.pupil_id} ({e.pupil_name or '-'}, "
          f"Yr {e.pupil_year or '-'})")
    print(f"  Subject:      {e.subject_code} — {e.subject_name}")
    print(f"  Board:        {e.exam_board}    "
          f"Spec: {e.spec_code or '-'}    Tier: {e.tier}")
    print(f"  Candidate:    {e.candidate_number or '-'}")
    print(f"  Status:       {e.entry_status}    "
          f"Entered on: {e.entry_date}")
    print(f"  Fee:          "
          f"{'£' + format(e.fee, 'g') if e.fee is not None else '-'}")
    print(f"  Notes:        {e.notes or '-'}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _set_status() -> None:
    eid = _ask_id("Entry ID")
    if eid is None:
        return
    e = data.get(eid)
    if e is None:
        print("  No entry with that ID.")
        return
    print(f"  Current: {e.entry_status}")
    print(f"  Allowed: {', '.join(ENTRY_STATUSES)}")
    new = _prompt("  New status: ")
    if not new:
        return
    e = data.set_status(eid, new)
    print(f"  Status now: {e.entry_status}")


@_safe
def _summary() -> None:
    yg = _prompt(f"  Year ({'/'.join(YEAR_GROUPS)}, blank): ") or None
    s = data.cohort_summary(year_group=yg)
    print(f"\n  Total entries: {s['total']}")
    print("  By status: "
          + "   ".join(f"{k}: {v}" for k, v in s["by_status"].items()))
    print("  By board:  "
          + "   ".join(f"{k}: {v}" for k, v in s["by_board"].items()))
    print("  By tier:   "
          + "   ".join(f"{k}: {v}" for k, v in s["by_tier"].items()))
    print(f"  Total fees: £{s['total_fees']}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _delete() -> None:
    eid = _ask_id("Entry ID")
    if eid is None:
        return
    e = data.get(eid)
    if e is None:
        print("  No entry with that ID.")
        return
    confirm = _prompt(
        f"  Delete entry #{eid} ({e.pupil_id} / {e.subject_code})? "
        f"(y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    if data.delete(eid):
        print(f"  Deleted entry #{eid}.")


_DISPATCH = {"GCSE Exam Entries": open_exam_entries}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching exam_entries CLI label: %s", label)
    handler()
    return True
