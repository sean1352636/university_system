"""CLI flows for the Sixth Form Attendance Report."""

from __future__ import annotations

import logging
from typing import Any, Callable
from education_system.systems.sixth_form.domain.operations.reporting.attendance_report import attendance_report
from education_system.systems.sixth_form.domain.academics.class_groups import class_groups
from education_system.systems.sixth_form.domain.operations.reporting.attendance_report import attendance_report as data
from education_system.systems.sixth_form.domain.academics.class_groups import class_groups as cg_data
from education_system.systems.sixth_form.domain.learners.students import students as student_data
from education_system.systems.sixth_form.domain.operations.reporting.attendance_report.attendance_report import (
    DOW_NAMES,
    DowRow,
    StatusBreakdown,
    StudentRow,
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


def _pick_group_optional() -> int | None:
    groups = cg_data.list_groups()
    if not groups:
        print("    No class groups.")
        return None
    print("\n  Class groups (blank = none):")
    for i, g in enumerate(groups, 1):
        print(f"    {i:>3}) #{g.group_id}  {g.name}")
    raw = _input("Pick # or group ID (blank=skip)")
    if not raw:
        return None
    if raw.isdigit():
        n = int(raw)
        if 1 <= n <= len(groups):
            return groups[n - 1].group_id
        for g in groups:
            if g.group_id == n:
                return n
    return None


# ── Print helpers ──────────────────────────────────────────────────

def _pct(v: float | None) -> str:
    return "—" if v is None else f"{v:.1f}%"


def _print_breakdown(b: StatusBreakdown, *, indent: str = "  ") -> None:
    print(f"{indent}Total      : {b.total}")
    print(f"{indent}  Present  : {b.present}")
    print(f"{indent}  Late     : {b.late}")
    print(f"{indent}  Absent   : {b.absent}")
    print(f"{indent}  Authoris.: {b.authorised}")
    print(f"{indent}Percentage : {_pct(b.percentage)}")


def _print_dow(rows: list[DowRow]) -> None:
    print()
    print(f"  {'Day':<4}  {'Total':>6}  {'P':>5}  {'L':>5}  "
          f"{'A':>5}  {'Au':>5}  Attendance")
    print("  " + "-" * 60)
    for r in rows:
        b = r.breakdown
        print(f"  {r.dow:<4}  {b.total:>6}  {b.present:>5}  "
              f"{b.late:>5}  {b.absent:>5}  {b.authorised:>5}  "
              f"{_pct(b.percentage)}")


def _print_students(rows: list[StudentRow], *,
                      threshold: float | None = None) -> None:
    print()
    print(f"  {'Student':<10}  {'Name':<26}  {'Total':>6}  "
          f"{'P':>4}  {'L':>4}  {'A':>4}  {'Au':>4}  Attendance")
    print("  " + "-" * 88)
    for r in rows:
        b = r.breakdown
        marker = ""
        pct = b.percentage
        if threshold is not None and pct is not None and pct < threshold:
            marker = " ⚠"
        print(f"  {r.student_id:<10}  {r.full_name[:26]:<26}  "
              f"{b.total:>6}  {b.present:>4}  {b.late:>4}  "
              f"{b.absent:>4}  {b.authorised:>4}  "
              f"{_pct(pct)}{marker}")


# ── Flows ──────────────────────────────────────────────────────────

def cohort_flow() -> None:
    print("\n═══ Cohort Report ═══")
    try:
        df = _input("From (YYYY-MM-DD, blank=window)") or None
        dt = _input("To (YYYY-MM-DD, blank=window)") or None
        window = int(_input("Window (days, if no dates)",
                              default="28"))
        thr = float(_input("Threshold % for below-flag",
                              default="90"))
        gid = _pick_group_optional()
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    try:
        r = data.cohort_report(
            date_from=df, date_to=dt, window_days=window,
            group_id=gid, threshold_pct=thr)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    print(f"\n  Window: {r.date_from} → {r.date_to}")
    if gid is not None:
        g = cg_data.get_group(gid)
        print(f"  Filtered to group #{gid} ({g.name if g else '?'})")
    print(f"  Distinct students: {r.student_count}")
    print(f"  Sessions covered : {r.sessions}")
    print()
    _print_breakdown(r.breakdown)
    print(f"\n  Students below {r.threshold_pct}%: "
          f"{r.students_below_threshold}")
    _pause()


def per_student_flow() -> None:
    print("\n═══ Per-Student Report ═══")
    try:
        sid = _pick_student()
        df = _input("From (YYYY-MM-DD, blank=window)") or None
        dt = _input("To (YYYY-MM-DD, blank=window)") or None
        window = int(_input("Window (days)", default="84"))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    try:
        r = data.per_student_report(
            sid, date_from=df, date_to=dt, window_days=window)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    print(f"\n  {r.student_id} — {r.full_name}")
    print(f"  Window: {r.date_from} → {r.date_to}")
    print()
    _print_breakdown(r.breakdown)
    print(f"\n  Recent (last 28 days): "
          f"lates={r.recent_lates}  absences={r.recent_absences}")
    print("\n  By day of week:")
    _print_dow([data.DowRow(dow=d, breakdown=b)
                  for d, b in r.by_dow.items()])
    if r.daily_trend:
        print(f"\n  Daily trend ({len(r.daily_trend)} day(s) "
              f"with records):")
        for d, b in r.daily_trend[-20:]:
            pct = _pct(b.percentage)
            print(f"    {d}  total={b.total:>3}  "
                  f"P={b.present:>2}  L={b.late:>2}  "
                  f"A={b.absent:>2}  Au={b.authorised:>2}  "
                  f"{pct}")
        if len(r.daily_trend) > 20:
            print(f"    … ({len(r.daily_trend) - 20} more not shown)")
    _pause()


def per_group_flow() -> None:
    print("\n═══ Per-Group Report ═══")
    try:
        gid = _pick_group_optional()
        if gid is None:
            print("\n  Cancelled.")
            return
        df = _input("From (YYYY-MM-DD, blank=window)") or None
        dt = _input("To (YYYY-MM-DD, blank=window)") or None
        window = int(_input("Window (days)", default="28"))
        thr = float(_input("Highlight threshold %", default="90"))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    try:
        r = data.per_group_report(
            gid, date_from=df, date_to=dt, window_days=window)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    print(f"\n  Group #{r.group_id} — {r.group_name}")
    print(f"  Window: {r.date_from} → {r.date_to}")
    print(f"  Members: {r.total_members}")
    print()
    _print_breakdown(r.breakdown)
    print(f"\n  Per-student (worst attendance first; ⚠ < {thr}%):")
    _print_students(r.rows, threshold=thr)
    _pause()


def daily_flow() -> None:
    print("\n═══ Daily Breakdown ═══")
    try:
        df = _input("From (YYYY-MM-DD, blank=window)") or None
        dt = _input("To (YYYY-MM-DD, blank=window)") or None
        window = int(_input("Window (days)", default="28"))
        gid = _pick_group_optional()
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    try:
        rows = data.daily_breakdown(
            date_from=df, date_to=dt, window_days=window,
            group_id=gid)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    if not rows:
        print("\n  (no records)")
        _pause()
        return
    print()
    print(f"  {'Date':<10}  {'Total':>6}  {'P':>5}  {'L':>5}  "
          f"{'A':>5}  {'Au':>5}  Attendance")
    print("  " + "-" * 60)
    for d in rows:
        b = d.breakdown
        print(f"  {d.date:<10}  {b.total:>6}  {b.present:>5}  "
              f"{b.late:>5}  {b.absent:>5}  {b.authorised:>5}  "
              f"{_pct(b.percentage)}")
    _pause()


def dow_flow() -> None:
    print("\n═══ Day-of-Week Breakdown ═══")
    try:
        df = _input("From (YYYY-MM-DD, blank=window)") or None
        dt = _input("To (YYYY-MM-DD, blank=window)") or None
        window = int(_input("Window (days)", default="84"))
        gid = _pick_group_optional()
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    try:
        rows = data.by_dow_breakdown(
            date_from=df, date_to=dt, window_days=window,
            group_id=gid)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_dow(rows)
    _pause()


def risk_flow() -> None:
    print("\n═══ Risk Report ═══")
    try:
        df = _input("From (YYYY-MM-DD, blank=window)") or None
        dt = _input("To (YYYY-MM-DD, blank=window)") or None
        window = int(_input("Window (days)", default="28"))
        thr = float(_input("Minimum attendance %", default="90"))
        max_l = int(_input("Max lates", default="5"))
        max_a = int(_input("Max absences", default="3"))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    try:
        rows = data.risk_report(
            date_from=df, date_to=dt, window_days=window,
            threshold_pct=thr, max_lates=max_l, max_absences=max_a)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    if not rows:
        print("\n  (no students at risk)")
        _pause()
        return
    print(f"\n  {len(rows)} student(s) flagged "
          f"({df or 'window'} → {dt or 'today'}):")
    print()
    print(f"  {'Student':<10}  {'Name':<24}  {'%':>5}  "
          f"{'P':>3}  {'L':>3}  {'A':>3}  Reasons")
    print("  " + "-" * 96)
    for r in rows:
        b = r.breakdown
        reasons = "; ".join(r.reasons)[:46]
        print(f"  {r.student_id:<10}  {r.full_name[:24]:<24}  "
              f"{_pct(b.percentage):>5}  "
              f"{b.present:>3}  {b.late:>3}  {b.absent:>3}  "
              f"{reasons}")
    _pause()


# ── Submenu ───────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Cohort Report",          cohort_flow),
    ("Per-Student Report",     per_student_flow),
    ("Per-Group Report",       per_group_flow),
    ("Daily Breakdown",        daily_flow),
    ("Day-of-Week Breakdown",  dow_flow),
    ("Risk Report",            risk_flow),
]


def run() -> None:
    while True:
        print("\n── Attendance Report ──")
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
            logger.exception("Attendance-report CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Attendance Report":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Attendance-report CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
