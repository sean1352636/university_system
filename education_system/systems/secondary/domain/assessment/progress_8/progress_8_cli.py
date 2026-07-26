"""CLI handlers for Progress 8."""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable

from education_system.systems.secondary.domain.assessment.progress_8 import (
    progress_8 as data,
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


def _print_table(rows: list[data.Progress8Record]) -> None:
    if not rows:
        print("  (no records)")
        return
    print(f"  {'ID':<4} {'Pupil':<10} {'Yr':<3} {'AcYear':<8} "
          f"{'KS2':<5} {'Exp A8':<6} {'A8':<5} {'P8':<6} {'A8 src':<10}")
    print(f"  {'-'*4} {'-'*10} {'-'*3} {'-'*8} {'-'*5} {'-'*6} "
          f"{'-'*5} {'-'*6} {'-'*10}")
    for r in rows:
        a8 = f"{r.attainment_8:.2f}" if r.attainment_8 is not None else "-"
        p8 = (f"{r.progress_8:+.2f}" if r.progress_8 is not None
              else "-")
        print(f"  {r.record_id:<4} {r.pupil_id:<10} "
              f"{(r.pupil_year or '-'):<3} {r.academic_year:<8} "
              f"{r.ks2_prior:<5.2f} {r.expected_a8:<6.2f} "
              f"{a8:<5} {p8:<6} {(r.a8_source or '-')[:10]:<10}")


@_safe
def open_progress_8() -> None:
    logger.debug("CLI: open_progress_8")
    while True:
        print("\n  ── Progress 8 ──")
        print("   1) Set / update a pupil's record")
        print("   2) List records")
        print("   3) View pupil record")
        print("   4) Refresh attainment_8 (re-pull from A8 table)")
        print("   5) Cohort summary")
        print("   6) Delete record")
        print("   0) Back")
        choice = _prompt("  Select: ")
        if choice in ("0", ""):
            return
        actions = {
            "1": _upsert, "2": _list, "3": _view,
            "4": _refresh, "5": _summary, "6": _delete,
        }
        handler = actions.get(choice)
        if handler is None:
            print("  Invalid selection.")
            continue
        handler()


def _collect(existing: data.Progress8Record | None = None
              ) -> dict[str, Any]:
    def ask(label: str, current) -> str:
        suffix = f" [{current}]" if current not in (None, "") else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else (str(current) if current not in (None, "") else "")
    f: dict[str, Any] = {}
    f["pupil_id"]      = ask("Pupil ID",
                              existing.pupil_id if existing else None)
    f["academic_year"] = ask("Academic year (YYYY/YY)",
                              existing.academic_year if existing
                              else None)
    f["ks2_prior"]     = ask("KS2 prior attainment (0–6)",
                              existing.ks2_prior if existing else None)
    f["expected_a8"]   = ask(
        "Expected A8 (blank = estimate from KS2)",
        existing.expected_a8 if existing else None)
    f["attainment_8"]  = ask(
        "Attainment 8 (blank = look up from A8 table)",
        existing.attainment_8 if existing else None)
    f["recorded_by"]   = ask("Recorded by",
                              existing.recorded_by if existing else None)
    f["notes"]         = ask("Notes",
                              existing.notes if existing else None)
    return f


@_safe
def _upsert() -> None:
    print("\n  ── Set / Update Progress 8 ──")
    fields = _collect()
    r = data.upsert(fields)
    print(f"  Saved record #{r.record_id}: {r.pupil_id} "
          f"{r.academic_year}")
    print(f"  KS2: {r.ks2_prior:.2f}    Expected A8: {r.expected_a8:.2f}")
    if r.attainment_8 is not None:
        print(f"  Attainment 8: {r.attainment_8:.2f} "
              f"({r.a8_source})    Progress 8: {r.progress_8:+.2f}")
    else:
        print(f"  Attainment 8 not yet available ({r.a8_source})")


@_safe
def _list() -> None:
    yg = _prompt(f"  Year ({'/'.join(YEAR_GROUPS)}, blank): ") or None
    ay = _prompt("  Academic year (blank): ") or None
    pid = _prompt("  Pupil ID (blank): ") or None
    rows = data.list_records(year_group=yg, academic_year=ay,
                               pupil_id=pid)
    print(f"\n  {len(rows)} record(s):")
    _print_table(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def _view() -> None:
    pid = _prompt("  Pupil ID: ")
    if not pid:
        return
    ay = _prompt("  Academic year (YYYY/YY): ")
    if not ay:
        return
    r = data.get_for(pid, ay)
    if r is None:
        print("  No record for that pupil/year.")
        return
    print(f"\n  ── Progress 8 record #{r.record_id} ──")
    print(f"  Pupil:        {r.pupil_id} ({r.pupil_name or '-'}, "
          f"Yr {r.pupil_year or '-'})")
    print(f"  Academic yr:  {r.academic_year}")
    print(f"  KS2 prior:    {r.ks2_prior:.2f}")
    print(f"  Expected A8:  {r.expected_a8:.2f}")
    print(f"  Attainment 8: "
          f"{r.attainment_8 if r.attainment_8 is not None else '-'}    "
          f"(source: {r.a8_source or '-'})")
    print(f"  Progress 8:   "
          f"{r.progress_8 if r.progress_8 is not None else '-'}")
    print(f"  Recorded by:  {r.recorded_by or '-'}")
    print(f"  Notes:        {r.notes or '-'}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _refresh() -> None:
    raw = _prompt("  Record ID: ")
    if not raw:
        return
    try:
        rid = int(raw)
    except ValueError:
        print("  Record ID must be a number.")
        return
    r = data.refresh_progress_8(rid)
    print(f"  Refreshed #{r.record_id}: A8={r.attainment_8}, "
          f"P8={r.progress_8}")


@_safe
def _summary() -> None:
    yg = _prompt(f"  Year ({'/'.join(YEAR_GROUPS)}, blank): ") or None
    ay = _prompt("  Academic year (blank): ") or None
    s = data.cohort_summary(year_group=yg, academic_year=ay)
    print(f"\n  Records: {s['count']}    With P8: {s['with_p8']}    "
          f"Without P8: {s['without_p8']}")
    print(f"  Avg P8: {s['avg_p8'] if s['avg_p8'] is not None else '-'}    "
          f"Min: {s['min_p8'] if s['min_p8'] is not None else '-'}    "
          f"Max: {s['max_p8'] if s['max_p8'] is not None else '-'}")
    if s["bands"]:
        print("  Bands:")
        for band in ("+1.0 or more", "+0.5 to +0.99", "0 to +0.49",
                     "-0.5 to -0.01", "-1.0 to -0.51",
                     "worse than -1.0"):
            n = s["bands"].get(band, 0)
            if n:
                print(f"    {band:<18} {n}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _delete() -> None:
    raw = _prompt("  Record ID: ")
    if not raw:
        return
    try:
        rid = int(raw)
    except ValueError:
        print("  Record ID must be a number.")
        return
    r = data.get(rid)
    if r is None:
        print("  No record with that ID.")
        return
    confirm = _prompt(
        f"  Delete record #{rid} ({r.pupil_id} {r.academic_year})? "
        f"(y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    data.delete(rid)
    print(f"  Deleted record #{rid}.")


_DISPATCH = {"Progress 8": open_progress_8}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching progress_8 CLI label: %s", label)
    handler()
    return True
