"""CLI flows for the Sixth Form Grades Report."""

from __future__ import annotations

import logging
from typing import Any, Callable
from education_system.sixthform_system.modules.domain.grades_report import grades_report
from education_system.sixthform_system.modules.domain.students import students
from education_system.sixthform_system.modules.domain.subjects import subjects as data
from education_system.sixthform_system.modules.domain.students import students as student_data
from education_system.sixthform_system.modules.domain.subjects import subjects as subject_data
from education_system.sixthform_system.modules.domain.grades_report.grades_report import (
    GradeDistribution,
    GRADE_POINTS,
    LETTER_GRADES,
    PASS_GRADES,
    TOP_GRADES,
    ValidationError,
)

logger = logging.getLogger(__name__)


class _UserAbort(Exception):
    pass


# ── Prompt helpers ─────────────────────────────────────────────────

def _input(prompt: str, *, default: str = "",
            allow_empty: bool = True) -> str:
    suffix = f" [{default}]" if default else ""
    try:
        raw = input(f"  {prompt}{suffix}: ")
    except (EOFError, KeyboardInterrupt):
        print()
        raise _UserAbort
    s = raw.strip()
    if s.lower() == "cancel":
        raise _UserAbort
    if not s:
        if default:
            return default
        if not allow_empty:
            print("    Value is required.")
            return _input(prompt, default=default, allow_empty=False)
        return ""
    return s


def _pause() -> None:
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


def _pick_student() -> str:
    students = student_data.list_students()
    if not students:
        print("    No students.")
        raise _UserAbort
    print("\n  Students:")
    for i, s in enumerate(students, 1):
        print(f"    {i:>3}) {s.student_id}  {s.full_name}")
    while True:
        raw = _input(f"  Pick #1..{len(students)} (or student ID)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(students):
                return students[n - 1].student_id
            continue
        m = next((s for s in students
                   if s.student_id.lower() == raw.lower()), None)
        if m:
            return m.student_id
        print("    No matching student.")


def _pick_subject() -> str:
    try:
        subs = subject_data.list_subjects()
    except Exception:
        subs = []
    if not subs:
        return _input("Subject", allow_empty=False)
    print("\n  Subjects:")
    for i, s in enumerate(subs, 1):
        name = getattr(s, "name", None) or getattr(s, "subject", None)
        print(f"    {i:>3}) {name}")
    while True:
        raw = _input(f"Pick # or type name", allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(subs):
                return getattr(subs[n - 1], "name", None) \
                    or getattr(subs[n - 1], "subject", None)
        return raw


# ── Print helpers ──────────────────────────────────────────────────

def _delta(d: int | None) -> str:
    if d is None:
        return "—"
    if d > 0:
        return f"+{d}"
    return str(d)


def _print_distribution(label: str, dist: GradeDistribution) -> None:
    print(f"\n  {label}:")
    if dist.total == 0:
        print("    (no data)")
        return
    print(f"    {'Grade':<6}  {'#':>5}  Bar")
    print("    " + "-" * 40)
    max_n = max(dist.by_grade.values()) or 1
    for g in LETTER_GRADES:
        n = dist.by_grade.get(g, 0)
        bar = "█" * int(20 * n / max_n) if n else ""
        print(f"    {g:<6}  {n:>5}  {bar}")
    print(f"    {'Total':<6}  {dist.total:>5}")
    print(f"    Average points : {dist.average_points}")
    print(f"    Pass (A*–E)    : {dist.pass_count}  "
          f"({dist.pass_pct}%)")
    print(f"    Top  (A*–C)    : {dist.top_count}  "
          f"({dist.top_pct}%)")


# ── Flows ──────────────────────────────────────────────────────────

def cohort_flow() -> None:
    print("\n═══ Cohort Grade Report ═══")
    try:
        sub = _input("Subject (blank=all)") or None
        yr = _input("Year (blank=all)") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        y_int = int(yr) if yr else None
    except ValueError:
        print("  ✗ Year must be a number.")
        _pause()
        return
    try:
        r = data.cohort_grade_report(year=y_int, subject=sub)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    print(f"\n  Subject filter: {sub or '(all)'}")
    print(f"  Year filter   : {y_int if y_int else '(all)'}")
    print(f"  Predicted rows: {r.predicted_subjects}")
    print(f"  Mock papers   : {r.mock_papers}")
    print(f"  Actual results: {r.actual_papers}")
    _print_distribution("Predicted", r.predicted)
    _print_distribution("Mock",      r.mock)
    _print_distribution("Actual",    r.actual)
    _pause()


def per_student_flow() -> None:
    print("\n═══ Per-Student Grade Report ═══")
    try:
        sid = _pick_student()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = data.per_student_grade_report(sid)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    print(f"\n  {r.student_id} — {r.full_name}")
    if not r.subjects:
        print("\n  (no grade data on file)")
        _pause()
        return
    print()
    print(f"  {'Subject':<28}  {'Pred':<6}  {'Mock':<6}  "
          f"{'Actual':<7}  {'ΔMock':<6}  {'ΔActual':<8}")
    print("  " + "-" * 76)
    for row in r.subjects:
        print(f"  {row.subject[:28]:<28}  "
              f"{(row.predicted_grade or '—'):<6}  "
              f"{(row.latest_mock_grade or '—'):<6}  "
              f"{(row.best_actual_grade or '—'):<7}  "
              f"{_delta(row.delta_mock_vs_pred):<6}  "
              f"{_delta(row.delta_actual_vs_pred):<8}")
    print()
    print(f"  Avg predicted points : {r.avg_predicted}")
    print(f"  Avg mock points      : {r.avg_mock}")
    print(f"  Avg actual points    : {r.avg_actual}")
    if r.notes:
        print("\n  Notes:")
        for note in r.notes:
            print(f"    • {note}")
    _pause()


def per_subject_flow() -> None:
    print("\n═══ Per-Subject Grade Report ═══")
    try:
        sub = _pick_subject()
        yr = _input("Year (blank=all)") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        y_int = int(yr) if yr else None
    except ValueError:
        print("  ✗ Year must be a number.")
        _pause()
        return
    try:
        r = data.per_subject_report(sub, year=y_int)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    print(f"\n  Subject: {r.subject}")
    _print_distribution("Predicted", r.predicted)
    _print_distribution("Mock",      r.mock)
    _print_distribution("Actual",    r.actual)
    if r.top_predicted:
        print("\n  Top predicted:")
        for sid, name, g in r.top_predicted:
            print(f"    {sid}  {name[:26]:<26}  {g}")
    if r.bottom_predicted:
        print("\n  Lowest predicted:")
        for sid, name, g in r.bottom_predicted:
            print(f"    {sid}  {name[:26]:<26}  {g}")
    _pause()


def pred_vs_actual_flow() -> None:
    print("\n═══ Predicted vs Actual ═══")
    try:
        sub = _input("Subject (blank=all)") or None
        yr = _input("Year (blank=all)") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        y_int = int(yr) if yr else None
    except ValueError:
        print("  ✗ Year must be a number.")
        _pause()
        return
    try:
        rows = data.compare_predicted_vs_actual(year=y_int, subject=sub)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    if not rows:
        print("\n  (no comparable rows — need both prediction "
              "and actual for the same student+subject)")
        _pause()
        return
    print(f"\n  {len(rows)} comparison(s) (worst first):")
    print(f"  {'Student':<10}  {'Name':<24}  {'Subject':<22}  "
          f"{'Pred':<6}  {'Actual':<7}  Δ")
    print("  " + "-" * 86)
    for r in rows:
        print(f"  {r.student_id:<10}  {r.full_name[:24]:<24}  "
              f"{r.subject[:22]:<22}  {r.predicted_grade:<6}  "
              f"{r.actual_grade:<7}  {_delta(r.delta)}")
    above = sum(1 for r in rows if r.delta > 0)
    on    = sum(1 for r in rows if r.delta == 0)
    below = sum(1 for r in rows if r.delta < 0)
    print(f"\n  Beat prediction: {above}   On prediction: {on}   "
          f"Below: {below}")
    _pause()


def alerts_flow() -> None:
    print("\n═══ Grade Alerts ═══")
    try:
        gap = int(_input("Flag if mock is N grades below prediction",
                            default="2"))
        target = _input(
            "Min target points (A*=6 A=5 B=4 C=3 D=2 E=1 U=0, "
            "blank=skip)")
        target_int: int | None
        target_int = int(target) if target else None
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    try:
        rows = data.alerts(mock_below_pred_by=gap,
                              min_target_pred_points=target_int)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    if not rows:
        print("\n  (no alerts)")
        _pause()
        return
    print(f"\n  {len(rows)} alert(s):")
    print(f"  {'Student':<10}  {'Name':<22}  {'Subject':<22}  "
          f"{'Pred':<6}  {'Mock':<6}  Reasons")
    print("  " + "-" * 110)
    for r in rows:
        reasons = "; ".join(r.reasons)[:40]
        print(f"  {r.student_id:<10}  {r.full_name[:22]:<22}  "
              f"{r.subject[:22]:<22}  "
              f"{(r.predicted or '—'):<6}  "
              f"{(r.latest_mock or '—'):<6}  {reasons}")
    _pause()


# ── Submenu ───────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Cohort Grade Report",     cohort_flow),
    ("Per-Student",             per_student_flow),
    ("Per-Subject",             per_subject_flow),
    ("Predicted vs Actual",     pred_vs_actual_flow),
    ("Alerts",                  alerts_flow),
]


def run() -> None:
    while True:
        print("\n── Grades Report ──")
        for i, (label, _) in enumerate(_MENU, 1):
            print(f"  {i:>2}) {label}")
        print("   0) Back")
        try:
            choice = input("  Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if choice == "0":
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(_MENU)):
            print("  Invalid selection.")
            continue
        _, handler = _MENU[int(choice) - 1]
        try:
            handler()
        except _UserAbort:
            print("\n  Cancelled.")
        except Exception as e:
            logger.exception("Grades-report CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Grades Report":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Grades-report CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
