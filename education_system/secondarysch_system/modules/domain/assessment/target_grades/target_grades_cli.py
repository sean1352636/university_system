"""CLI handlers for target grades."""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable

from education_system.secondarysch_system.modules.domain.assessment.target_grades import (
    target_grades as data,
)
from education_system.secondarysch_system.modules.domain.assessment.target_grades.target_grades import (
    GRADE_SOURCES,
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


def _print_table(rows: list[data.TargetGrade]) -> None:
    if not rows:
        print("  (no targets)")
        return
    print(f"  {'ID':<5} {'Pupil':<10} {'Yr':<3} {'Name':<22} "
          f"{'Subj':<6} {'Tgt':<4} {'Min':<4} {'Asp':<4} "
          f"{'Source':<9} {'Set on':<10}")
    print(f"  {'-'*5} {'-'*10} {'-'*3} {'-'*22} {'-'*6} {'-'*4} "
          f"{'-'*4} {'-'*4} {'-'*9} {'-'*10}")
    for t in rows:
        print(f"  {t.target_id:<5} {t.pupil_id:<10} "
              f"{(t.pupil_year or '-'):<3} "
              f"{(t.pupil_name or '-')[:22]:<22} "
              f"{(t.subject_code or '?'):<6} "
              f"{t.target_grade:<4} "
              f"{(t.minimum_grade or '-'):<4} "
              f"{(t.aspirational_grade or '-'):<4} "
              f"{t.source[:9]:<9} {t.set_date:<10}")


@_safe
def open_target_grades() -> None:
    logger.debug("CLI: open_target_grades")
    while True:
        all_rows = data.list_targets()
        print("\n  ── Target Grades ──")
        print(f"  Total: {len(all_rows)}")
        print("\n   1) Set / update target")
        print("   2) List targets")
        print("   3) View target for pupil + subject")
        print("   4) Distribution (year + subject filter)")
        print("   5) Delete target")
        print("   0) Back")
        choice = _prompt("  Select: ")
        if choice in ("0", ""):
            return
        actions = {
            "1": _upsert, "2": _list, "3": _view,
            "4": _distribution, "5": _delete,
        }
        handler = actions.get(choice)
        if handler is None:
            print("  Invalid selection.")
            continue
        handler()


def _collect(existing: data.TargetGrade | None = None) -> dict[str, Any]:
    def ask(label: str, current) -> str:
        suffix = f" [{current}]" if current not in (None, "") else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else (str(current) if current not in (None, "") else "")

    f: dict[str, Any] = {}
    f["pupil_id"] = ask("Pupil ID",
                         existing.pupil_id if existing else None)
    if not existing:
        print("  Active subjects:")
        for s in subjects_data.list_all(active_only=True)[:30]:
            print(f"    #{s.subject_id:<4} {s.code:<8} {s.name}")
    f["subject_id"]         = ask("Subject ID",
                                    existing.subject_id if existing
                                    else None)
    f["target_grade"]       = ask("Target grade",
                                    existing.target_grade if existing
                                    else None)
    f["minimum_grade"]      = ask("Minimum grade (blank ok)",
                                    existing.minimum_grade if existing
                                    else None)
    f["aspirational_grade"] = ask("Aspirational grade (blank ok)",
                                    existing.aspirational_grade if existing
                                    else None)
    f["source"]             = ask(f"Source ({'/'.join(GRADE_SOURCES)})",
                                    existing.source if existing
                                    else "Teacher")
    f["set_by"]             = ask("Set by",
                                    existing.set_by if existing else None)
    f["set_date"]           = ask("Set date (YYYY-MM-DD, blank = today)",
                                    existing.set_date if existing else None)
    f["notes"]              = ask("Notes",
                                    existing.notes if existing else None)
    return f


@_safe
def _upsert() -> None:
    print("\n  ── Set / Update Target ──")
    pid_raw = _prompt("  Pupil ID: ")
    if not pid_raw:
        return
    sid_raw = _prompt("  Subject ID: ")
    if not sid_raw:
        return
    try:
        sid = int(sid_raw)
    except ValueError:
        print("  Subject ID must be a number.")
        return
    existing = data.get_for(pid_raw, sid)
    if existing:
        print(f"  Existing target: {existing.target_grade} "
              f"(set {existing.set_date} via {existing.source})")
    fields = _collect(existing)
    # Force pupil_id/subject_id to the ones just asked
    fields["pupil_id"] = pid_raw
    fields["subject_id"] = sid
    rec = data.upsert(fields)
    print(f"  Saved target for {rec.pupil_id} / {rec.subject_code} "
          f"= {rec.target_grade}")


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
    pid = _prompt("  Pupil ID (blank): ") or None
    src = _prompt(
        f"  Source ({'/'.join(GRADE_SOURCES)}, blank): ") or None
    rows = data.list_targets(year_group=yg, subject_id=sid,
                              pupil_id=pid, source=src)
    print(f"\n  {len(rows)} target(s):")
    _print_table(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def _view() -> None:
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
    t = data.get_for(pid, sid)
    if t is None:
        print("  No target set for that pupil + subject.")
        return
    print(f"\n  ── Target #{t.target_id} ──")
    print(f"  Pupil:        {t.pupil_id}  {t.pupil_name or ''}")
    print(f"  Subject:      {t.subject_code} — {t.subject_name}")
    print(f"  Target:       {t.target_grade}")
    print(f"  Minimum:      {t.minimum_grade or '-'}")
    print(f"  Aspirational: {t.aspirational_grade or '-'}")
    print(f"  Source:       {t.source}")
    print(f"  Set by:       {t.set_by or '-'}  on {t.set_date}")
    print(f"  Notes:        {t.notes or '-'}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _distribution() -> None:
    yg = _prompt(f"  Year ({'/'.join(YEAR_GROUPS)}, blank): ") or None
    sid_raw = _prompt("  Subject ID (blank): ")
    sid = None
    if sid_raw:
        try:
            sid = int(sid_raw)
        except ValueError:
            print("  Subject ID must be a number.")
            return
    dist = data.distribution(year_group=yg, subject_id=sid)
    total = sum(dist.values())
    print(f"\n  Distribution ({total} target(s)):")
    for g in sorted(dist.keys()):
        print(f"    {g:<4} {dist[g]}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _delete() -> None:
    raw = _prompt("  Target ID: ")
    if not raw:
        return
    try:
        tid = int(raw)
    except ValueError:
        print("  Target ID must be a number.")
        return
    t = data.get(tid)
    if t is None:
        print("  No target with that ID.")
        return
    confirm = _prompt(
        f"  Delete target #{tid} ({t.pupil_id} / {t.subject_code} "
        f"= {t.target_grade})? (y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    data.delete(tid)
    print(f"  Deleted target #{tid}.")


_DISPATCH = {"Target Grades": open_target_grades}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching target_grades CLI label: %s", label)
    handler()
    return True
