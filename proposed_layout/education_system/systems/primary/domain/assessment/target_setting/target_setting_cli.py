"""CLI handlers for pupil target setting."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.systems.primary.domain.assessment.target_setting import (
    target_setting as data,
)
from education_system.systems.primary.domain.assessment.target_setting.target_setting import (
    STATUSES, STATUS_LABELS, TARGET_GRADES, TARGET_GRADE_LABELS,
)
from education_system.systems.primary.domain.learners.pupils.pupils import (
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


def _print_table(rows: list[tuple]) -> None:
    if not rows:
        print("  (no targets)")
        return
    print(f"  {'#':<5} {'Pupil':<10} {'Name':<22} {'Yr':<3} "
          f"{'AcYr':<9} {'Subject':<16} {'Grd':<4} {'Score':<6} "
          f"{'Review':<11} {'Status':<10}")
    print(f"  {'-'*5} {'-'*10} {'-'*22} {'-'*3} {'-'*9} {'-'*16} "
          f"{'-'*4} {'-'*6} {'-'*11} {'-'*10}")
    for rec, p in rows:
        name = p.full_name if p else "(unknown)"
        yr = p.year_group if p else "-"
        score = "-" if rec.target_score is None else f"{rec.target_score:g}"
        print(f"  {rec.target_id:<5} {rec.pupil_id:<10} {name[:22]:<22} "
              f"{yr:<3} {rec.academic_year:<9} {rec.subject[:16]:<16} "
              f"{rec.target_grade:<4} {score:<6} "
              f"{(rec.review_date or '-'):<11} {rec.status:<10}")


@_safe
def open_target_setting() -> None:
    logger.debug("CLI: open_target_setting")
    while True:
        print("\n  -- Target Setting --")
        years = data.known_years()
        if years:
            print(f"  Years recorded: {', '.join(years)}")
        print("\n   1) List all targets")
        print("   2) Filter targets")
        print("   3) View pupil's targets")
        print("   4) Summary")
        print("   5) Create target")
        print("   6) Update target")
        print("   7) Change status")
        print("   8) Delete target")
        print("   9) Show grade / status meanings")
        print("   0) Back")
        choice = _prompt("  Select: ")
        if choice == "0" or choice == "":
            return
        actions = {
            "1": _list_all,
            "2": _list_filtered,
            "3": _view_pupil,
            "4": _summary,
            "5": _create,
            "6": _update,
            "7": _change_status,
            "8": _delete,
            "9": _show_help,
        }
        action = actions.get(choice)
        if action is None:
            print("  Invalid selection.")
            continue
        action()


@_safe
def _list_all() -> None:
    rows = data.list_targets()
    print(f"\n  {len(rows)} target(s):")
    _print_table(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def _list_filtered() -> None:
    ay = _prompt("  Academic year (blank for any): ").strip() or None
    subj = _prompt("  Subject (blank for any): ").strip() or None
    print(f"  Statuses: {', '.join(STATUSES)} (blank for any)")
    st = _prompt("  Status: ").strip().lower() or None
    print(f"  Year groups: {', '.join(YEAR_GROUPS)} (blank for any)")
    yg = _prompt("  Pupil year group: ").strip() or None
    rows = data.list_targets(academic_year=ay, subject=subj,
                             status=st, year_group=yg)
    print(f"\n  {len(rows)} target(s):")
    _print_table(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def _view_pupil() -> None:
    pid = _prompt("  Pupil ID: ")
    if not pid:
        return
    rows = data.list_for_pupil(pid)
    print(f"\n  {len(rows)} target(s) for pupil {pid}:")
    if not rows:
        print("    (none)")
    else:
        for t in rows:
            score = "-" if t.target_score is None else f"{t.target_score:g}"
            print(f"    #{t.target_id} {t.academic_year} {t.subject}: "
                  f"{t.target_grade}  score={score}  "
                  f"set={t.set_on or '-'}  review={t.review_date or '-'}  "
                  f"status={t.status}  {t.notes or ''}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _summary() -> None:
    ay = _prompt("  Academic year (blank for all): ").strip() or None
    subj = _prompt("  Subject (blank for any): ").strip() or None
    s = data.summary(academic_year=ay, subject=subj)
    print("\n  -- Summary --")
    print(f"  Total: {s['total']}")
    print("  By status:")
    for st in STATUSES:
        print(f"    {st:<10} {s['by_status'].get(st, 0)}")
    print("  By target grade:")
    for g in TARGET_GRADES:
        print(f"    {g:<5} {s['by_grade'].get(g, 0)}")
    print(f"  Met or exceeded: {s['met_or_exceeded']} "
          f"({s['met_or_exceeded_pct']:.1f}%)")
    _prompt("\n  Press Enter to continue...")


def _collect(defaults: dict | None = None) -> dict:
    d = defaults or {}
    print(f"  (Grades: {', '.join(TARGET_GRADES)})")
    print(f"  (Statuses: {', '.join(STATUSES)})")
    out: dict = {}
    out["pupil_id"]      = _prompt(f"  Pupil ID [{d.get('pupil_id','')}]: ") or d.get("pupil_id", "")
    out["academic_year"] = _prompt(f"  Academic year (e.g. 2025-26) [{d.get('academic_year','')}]: ") or d.get("academic_year", "")
    out["subject"]       = _prompt(f"  Subject [{d.get('subject','')}]: ") or d.get("subject", "")
    out["target_grade"]  = _prompt(f"  Target grade [{d.get('target_grade','')}]: ") or d.get("target_grade", "")
    score_default = "" if d.get("target_score") in (None, "") else f"{d['target_score']:g}"
    out["target_score"]  = _prompt(f"  Target score (optional) [{score_default}]: ") or score_default
    out["set_on"]        = _prompt(f"  Set on YYYY-MM-DD [{d.get('set_on','')}]: ") or d.get("set_on", "")
    out["review_date"]   = _prompt(f"  Review date YYYY-MM-DD [{d.get('review_date','')}]: ") or d.get("review_date", "")
    out["status"]        = _prompt(f"  Status [{d.get('status','open')}]: ") or d.get("status", "open")
    out["notes"]         = _prompt(f"  Notes [{d.get('notes','')}]: ") or d.get("notes", "")
    return out


@_safe
def _create() -> None:
    print("\n  -- Create Target --")
    payload = _collect()
    rec = data.create(payload)
    print(f"  Created #{rec.target_id}: pupil {rec.pupil_id} "
          f"{rec.academic_year} {rec.subject} -> {rec.target_grade}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _update() -> None:
    raw = _prompt("  Target ID to update: ")
    if not raw or not raw.isdigit():
        return
    existing = data.get(int(raw))
    if existing is None:
        print(f"  No target #{raw}")
        return
    defaults = {
        "pupil_id": existing.pupil_id,
        "academic_year": existing.academic_year,
        "subject": existing.subject,
        "target_grade": existing.target_grade,
        "target_score": existing.target_score,
        "set_on": existing.set_on or "",
        "review_date": existing.review_date or "",
        "status": existing.status,
        "notes": existing.notes or "",
    }
    payload = _collect(defaults)
    rec = data.update(int(raw), payload)
    print(f"  Updated #{rec.target_id}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _change_status() -> None:
    raw = _prompt("  Target ID: ")
    if not raw or not raw.isdigit():
        return
    print(f"  Statuses: {', '.join(STATUSES)}")
    new = _prompt("  New status: ").strip().lower()
    if not new:
        return
    rec = data.set_status(int(raw), new)
    print(f"  Target #{rec.target_id} -> {rec.status}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _delete() -> None:
    raw = _prompt("  Target ID to delete: ")
    if not raw or not raw.isdigit():
        return
    confirm = _prompt(f"  Delete target #{raw}? (y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    ok = data.delete(int(raw))
    print(f"  {'Deleted' if ok else 'No such target'}: #{raw}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _show_help() -> None:
    print("\n  -- Target grades --")
    for g in TARGET_GRADES:
        print(f"   {g}  — {TARGET_GRADE_LABELS[g]}")
    print("\n  -- Statuses --")
    for s in STATUSES:
        print(f"   {s:<10} — {STATUS_LABELS[s]}")
    _prompt("\n  Press Enter to continue...")


_DISPATCH = {"Target Setting": open_target_setting}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching target_setting CLI label: %s", label)
    handler()
    return True
