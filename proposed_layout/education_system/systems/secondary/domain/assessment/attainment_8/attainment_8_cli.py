"""CLI handlers for Attainment 8."""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable

from education_system.systems.secondary.domain.assessment.attainment_8 import (
    attainment_8 as data,
)
from education_system.systems.secondary.domain.assessment.attainment_8.attainment_8 import (
    SOURCES, SLOT_LABELS,
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


def _print_table(rows: list[data.Attainment8Record]) -> None:
    if not rows:
        print("  (no records)")
        return
    print(f"  {'ID':<4} {'Pupil':<10} {'Yr':<3} {'Year':<8} "
          f"{'Src':<10} {'Eng':<3} {'Mth':<3} {'EB':<8} {'Open':<8} "
          f"{'A8':<5} {'Slots':<5}")
    print(f"  {'-'*4} {'-'*10} {'-'*3} {'-'*8} {'-'*10} {'-'*3} "
          f"{'-'*3} {'-'*8} {'-'*8} {'-'*5} {'-'*5}")
    for r in rows:
        eb = "/".join((r.ebacc1_grade or '-', r.ebacc2_grade or '-',
                        r.ebacc3_grade or '-'))
        op = "/".join((r.open1_grade or '-', r.open2_grade or '-',
                        r.open3_grade or '-'))
        a8 = f"{r.attainment_8:.2f}" if r.attainment_8 is not None else "-"
        print(f"  {r.record_id:<4} {r.pupil_id:<10} "
              f"{(r.pupil_year or '-'):<3} {r.academic_year:<8} "
              f"{r.record_source:<10} "
              f"{(r.english_grade or '-'):<3} "
              f"{(r.maths_grade or '-'):<3} "
              f"{eb[:8]:<8} {op[:8]:<8} {a8:<5} "
              f"{r.slots_filled}/8")


@_safe
def open_attainment_8() -> None:
    logger.debug("CLI: open_attainment_8")
    while True:
        print("\n  ── Attainment 8 ──")
        print("   1) Set / update a pupil's record")
        print("   2) List records")
        print("   3) View pupil record")
        print("   4) Cohort summary")
        print("   5) Delete record")
        print("   0) Back")
        choice = _prompt("  Select: ")
        if choice in ("0", ""):
            return
        actions = {
            "1": _upsert, "2": _list, "3": _view,
            "4": _summary, "5": _delete,
        }
        handler = actions.get(choice)
        if handler is None:
            print("  Invalid selection.")
            continue
        handler()


def _collect(existing: data.Attainment8Record | None = None
              ) -> dict[str, Any]:
    def ask(label: str, current) -> str:
        suffix = f" [{current}]" if current not in (None, "") else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else (str(current) if current not in (None, "") else "")
    f: dict[str, Any] = {}
    f["pupil_id"] = ask("Pupil ID",
                         existing.pupil_id if existing else None)
    f["academic_year"] = ask("Academic year (YYYY/YY)",
                              existing.academic_year if existing else None)
    f["record_source"] = ask(f"Source ({'/'.join(SOURCES)})",
                              existing.record_source if existing
                              else "Estimated")
    print("  Grades (1–9 or U) — blanks leave A8 incomplete.")
    for label in SLOT_LABELS:
        nice = label.replace("_grade", "").replace("_", " ").title()
        f[label] = ask(f"  {nice}",
                        (getattr(existing, label) if existing else None))
    f["recorded_by"] = ask("Recorded by",
                            existing.recorded_by if existing else None)
    f["notes"]       = ask("Notes",
                            existing.notes if existing else None)
    return f


@_safe
def _upsert() -> None:
    print("\n  ── Set / Update Attainment 8 ──")
    fields = _collect()
    r = data.upsert(fields)
    print(f"  Saved record #{r.record_id}: {r.pupil_id} "
          f"{r.academic_year} ({r.record_source})")
    if r.attainment_8 is not None:
        print(f"  Total points: {r.total_points}    "
              f"Attainment 8: {r.attainment_8}")
    else:
        print(f"  ({r.slots_filled}/8 slots filled — A8 not computed)")


@_safe
def _list() -> None:
    yg = _prompt(f"  Year ({'/'.join(YEAR_GROUPS)}, blank): ") or None
    ay = _prompt("  Academic year (blank): ") or None
    src = _prompt(f"  Source ({'/'.join(SOURCES)}, blank): ") or None
    pid = _prompt("  Pupil ID (blank): ") or None
    rows = data.list_records(year_group=yg, academic_year=ay,
                               record_source=src, pupil_id=pid)
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
    src = _prompt(f"  Source ({'/'.join(SOURCES)}, default Estimated): ") \
        or "Estimated"
    r = data.get_for(pid, ay, src)
    if r is None:
        print("  No record for that pupil/year/source.")
        return
    print(f"\n  ── Record #{r.record_id} ──")
    print(f"  Pupil:    {r.pupil_id} ({r.pupil_name or '-'}, "
          f"Yr {r.pupil_year or '-'})")
    print(f"  Year:     {r.academic_year}    Source: {r.record_source}")
    print("  Slots:")
    for label in SLOT_LABELS:
        nice = label.replace("_grade", "").replace("_", " ").title()
        print(f"    {nice:<12} {getattr(r, label) or '-'}")
    print(f"  Total points: "
          f"{r.total_points if r.total_points is not None else '-'}")
    print(f"  Attainment 8: "
          f"{r.attainment_8 if r.attainment_8 is not None else '-'}")
    print(f"  Recorded by:  {r.recorded_by or '-'}")
    print(f"  Notes:        {r.notes or '-'}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _summary() -> None:
    yg = _prompt(f"  Year ({'/'.join(YEAR_GROUPS)}, blank): ") or None
    ay = _prompt("  Academic year (blank): ") or None
    src = _prompt(f"  Source ({'/'.join(SOURCES)}, blank): ") or None
    s = data.cohort_summary(year_group=yg, academic_year=ay,
                              record_source=src)
    print(f"\n  Records: {s['count']}    Complete: {s['complete']}    "
          f"Incomplete: {s['incomplete']}")
    print(f"  Avg A8: {s['avg_a8'] if s['avg_a8'] is not None else '-'}    "
          f"Min: {s['min_a8'] if s['min_a8'] is not None else '-'}    "
          f"Max: {s['max_a8'] if s['max_a8'] is not None else '-'}")
    if s["bands"]:
        print("  Bands:")
        for band in ("8.0+", "7.0–7.9", "6.0–6.9", "5.0–5.9",
                     "4.0–4.9", "3.0–3.9", "<3.0"):
            n = s["bands"].get(band, 0)
            if n:
                print(f"    {band:<8} {n}")
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
        f"  Delete A8 record #{rid} ({r.pupil_id} "
        f"{r.academic_year} {r.record_source})? (y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    data.delete(rid)
    print(f"  Deleted record #{rid}.")


_DISPATCH = {"Attainment 8": open_attainment_8}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching attainment_8 CLI label: %s", label)
    handler()
    return True
