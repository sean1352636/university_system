"""CLI handlers for Results Day."""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable

from education_system.systems.secondary.domain.assessment.exam_results import (
    exam_results as data,
)
from education_system.systems.secondary.domain.assessment.exam_results.exam_results import (
    RESULT_STATUSES,
)
from education_system.systems.secondary.domain.assessment.exam_entries import (
    exam_entries as entries_data,
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


def _print_table(rows: list[data.ExamResult]) -> None:
    if not rows:
        print("  (no results)")
        return
    print(f"  {'ID':<5} {'Entry':<6} {'Pupil':<10} {'Yr':<3} {'Subj':<6} "
          f"{'Board':<8} {'Tier':<10} {'Grade':<5} {'Marks':<6} "
          f"{'UMS':<5} {'Status':<10}")
    print(f"  {'-'*5} {'-'*6} {'-'*10} {'-'*3} {'-'*6} {'-'*8} {'-'*10} "
          f"{'-'*5} {'-'*6} {'-'*5} {'-'*10}")
    for r in rows:
        print(f"  {r.result_id:<5} {r.entry_id:<6} {r.pupil_id:<10} "
              f"{(r.pupil_year or '-'):<3} "
              f"{(r.subject_code or '?'):<6} "
              f"{(r.exam_board or '-')[:8]:<8} "
              f"{(r.tier or '-')[:10]:<10} "
              f"{(r.final_grade or '-'):<5} "
              f"{(f'{r.marks_awarded:g}' if r.marks_awarded is not None else '-'):<6} "
              f"{(f'{r.ums:g}' if r.ums is not None else '-'):<5} "
              f"{r.status:<10}")


@_safe
def open_exam_results() -> None:
    logger.debug("CLI: open_exam_results")
    while True:
        print("\n  ── Results Day ──")
        print("   1) Record / update result for entry")
        print("   2) List results")
        print("   3) View result")
        print("   4) Pupil results sheet")
        print("   5) Cohort summary")
        print("   6) Pending entries (no result yet)")
        print("   7) Delete result")
        print("   0) Back")
        choice = _prompt("  Select: ")
        if choice in ("0", ""):
            return
        actions = {
            "1": _upsert, "2": _list, "3": _view,
            "4": _pupil_sheet, "5": _summary,
            "6": _pending, "7": _delete,
        }
        handler = actions.get(choice)
        if handler is None:
            print("  Invalid selection.")
            continue
        handler()


def _collect(existing: data.ExamResult | None = None) -> dict[str, Any]:
    def ask(label: str, current) -> str:
        suffix = f" [{current}]" if current not in (None, "") else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else (str(current) if current not in (None, "") else "")
    f: dict[str, Any] = {}
    f["entry_id"]    = ask("Entry ID",
                             existing.entry_id if existing else None)
    f["final_grade"] = ask("Final grade",
                             existing.final_grade if existing else None)
    f["marks_awarded"] = ask("Marks awarded (blank ok)",
                               existing.marks_awarded if existing
                               else None)
    f["ums"]         = ask("UMS (blank ok)",
                             existing.ums if existing else None)
    f["result_date"] = ask("Result date (YYYY-MM-DD, blank = today)",
                             existing.result_date if existing else None)
    f["status"]      = ask(f"Status ({'/'.join(RESULT_STATUSES)})",
                             existing.status if existing else "Pending")
    f["remark_outcome"] = ask(
        "Remark outcome (blank ok)",
        existing.remark_outcome if existing else None)
    f["notes"]       = ask("Notes",
                             existing.notes if existing else None)
    return f


@_safe
def _upsert() -> None:
    print("\n  ── Record / Update Result ──")
    raw = _prompt("  Entry ID: ")
    if not raw:
        return
    try:
        eid = int(raw)
    except ValueError:
        print("  Entry ID must be a number.")
        return
    entry = entries_data.get(eid)
    if entry is None:
        print("  No exam entry with that ID.")
        return
    existing = data.get_for_entry(eid)
    print(f"  Entry: {entry.pupil_id} / {entry.subject_code} "
          f"({entry.exam_board} {entry.tier})")
    fields = _collect(existing)
    fields["entry_id"] = eid
    r = data.upsert(fields)
    print(f"  Saved result #{r.result_id}: "
          f"grade={r.final_grade or '-'} status={r.status}")


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
    status = _prompt(
        f"  Status ({'/'.join(RESULT_STATUSES)}, blank): ") or None
    rows = data.list_results(year_group=yg, subject_id=sid,
                               status=status)
    print(f"\n  {len(rows)} result(s):")
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
    rid = _ask_id("Result ID")
    if rid is None:
        return
    r = data.get(rid)
    if r is None:
        print("  No result with that ID.")
        return
    print(f"\n  ── Result #{r.result_id} ──")
    print(f"  Entry:    #{r.entry_id} ({r.exam_board or '-'} "
          f"{r.tier or '-'})")
    print(f"  Pupil:    {r.pupil_id} ({r.pupil_name or '-'}, "
          f"Yr {r.pupil_year or '-'})")
    print(f"  Subject:  {r.subject_code} — {r.subject_name}")
    print(f"  Grade:    {r.final_grade or '-'}")
    print(f"  Marks:    "
          f"{r.marks_awarded if r.marks_awarded is not None else '-'}")
    print(f"  UMS:      {r.ums if r.ums is not None else '-'}")
    print(f"  Date:     {r.result_date}")
    print(f"  Status:   {r.status}")
    print(f"  Remark:   {r.remark_outcome or '-'}")
    print(f"  Notes:    {r.notes or '-'}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _pupil_sheet() -> None:
    pid = _prompt("  Pupil ID: ")
    if not pid:
        return
    s = data.pupil_results(pid)
    print(f"\n  ── Results sheet: {s['pupil_id']} ──")
    print(f"  Total results: {len(s['results'])}    "
          f"Graded: {s['graded']}    "
          f"Passes (4+): {s['passes']}    "
          f"Strong passes (5+): {s['strong_passes']}")
    _print_table(s["results"])
    _prompt("\n  Press Enter to continue...")


@_safe
def _summary() -> None:
    yg = _prompt(f"  Year ({'/'.join(YEAR_GROUPS)}, blank): ") or None
    sid_raw = _prompt("  Subject ID (blank): ")
    sid = None
    if sid_raw:
        try:
            sid = int(sid_raw)
        except ValueError:
            print("  Subject ID must be a number.")
            return
    s = data.cohort_summary(year_group=yg, subject_id=sid)
    print(f"\n  Total: {s['total']}    Graded: {s['graded']}")
    print(f"  Pass rate (4+): "
          f"{s['pass_rate_pct'] if s['pass_rate_pct'] is not None else '-'}%    "
          f"Strong pass (5+): "
          f"{s['strong_pass_pct'] if s['strong_pass_pct'] is not None else '-'}%")
    if s["by_status"]:
        print("  By status: "
              + "   ".join(f"{k}: {v}"
                            for k, v in s["by_status"].items()))
    if s["by_grade"]:
        print("  By grade:")
        for g in sorted(s["by_grade"].keys(),
                          key=lambda x: (-int(x) if x.isdigit() else 0,
                                          x)):
            print(f"    {g:<4} {s['by_grade'][g]}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _pending() -> None:
    yg = _prompt(f"  Year ({'/'.join(YEAR_GROUPS)}, blank): ") or None
    pending = data.list_pending_for_entries(year_group=yg)
    print(f"\n  {len(pending)} Final entry(ies) with no result yet:")
    if pending:
        print(f"  {'Entry':<6} {'Pupil':<10} {'Yr':<3} {'Subj':<6} "
              f"{'Board':<8} {'Tier':<10}")
        print(f"  {'-'*6} {'-'*10} {'-'*3} {'-'*6} {'-'*8} {'-'*10}")
        for e in pending:
            print(f"  {e.entry_id:<6} {e.pupil_id:<10} "
                  f"{(e.pupil_year or '-'):<3} "
                  f"{(e.subject_code or '?'):<6} "
                  f"{e.exam_board[:8]:<8} {e.tier:<10}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _delete() -> None:
    rid = _ask_id("Result ID")
    if rid is None:
        return
    r = data.get(rid)
    if r is None:
        print("  No result with that ID.")
        return
    confirm = _prompt(
        f"  Delete result #{rid} ({r.pupil_id} / {r.subject_code})? "
        f"(y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    data.delete(rid)
    print(f"  Deleted result #{rid}.")


_DISPATCH = {"Results Day": open_exam_results}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching exam_results CLI label: %s", label)
    handler()
    return True
