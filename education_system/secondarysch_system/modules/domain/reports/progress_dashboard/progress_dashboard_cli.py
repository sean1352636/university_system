"""CLI flows for the Progress Dashboard."""

from __future__ import annotations

import logging
from typing import Callable

from education_system.secondarysch_system.modules.domain.reports.progress import progress
from education_system.secondarysch_system.modules.domain.reports.progress_dashboard import (
    progress_dashboard as data,
)
from education_system.secondarysch_system.modules.domain.reports.progress_dashboard.progress_dashboard import (
    Dashboard,
    StudentRow,
)

logger = logging.getLogger(__name__)


class _UserAbort(Exception):
    pass


def _input(prompt: str, *, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        raw = input(f"  {prompt}{suffix}: ")
    except (EOFError, KeyboardInterrupt):
        print()
        raise _UserAbort
    s = raw.strip()
    if s.lower() == "cancel":
        raise _UserAbort
    return s or default


def _pause() -> None:
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


def _print_rows(rows: list[StudentRow]) -> None:
    if not rows:
        print("\n  (no rows)")
        return
    print()
    print(f"  {'Student':<10}  {'Name':<24}  {'Risk':<8}  "
          f"{'Overall':<24}  {'Att%':<6}  "
          f"{'Open':>4}  {'Over':>4}  {'Met':>4}  {'Period':<22}")
    print("  " + "-" * 118)
    for r in rows:
        att = "—" if r.attendance_pct is None else f"{r.attendance_pct:.1f}"
        print(f"  {r.student_id:<10}  {r.full_name[:24]:<24}  "
              f"{(r.risk or '—'):<8}  "
              f"{(r.overall or '—')[:24]:<24}  {att:<6}  "
              f"{r.open_targets:>4}  {r.overdue_targets:>4}  "
              f"{r.met_targets:>4}  {(r.latest_period or '—')[:22]:<22}")
    print(f"\n  {len(rows)} student(s).")


def _print_header(d: Dashboard) -> None:
    cov = d.review_coverage_pct
    cov_s = "—" if cov is None else f"{cov:.1f}%"
    print(f"\n  Generated         : {d.generated_on}")
    print(f"  Students          : {d.total_students}")
    print(f"  Reviewed          : {d.reviewed_students}  ({cov_s})")
    print(f"  Unreviewed        : {d.unreviewed_students}")
    print(f"  High/Critical     : {d.high_risk_students}")
    print(f"  With overdue tgts : {d.overdue_target_students}")


# ── Flows ─────────────────────────────────────────────────────────

def overview() -> None:
    print("\n═══ Progress Dashboard ═══")
    d = data.build_dashboard()
    _print_header(d)
    _print_rows(d.rows)
    _pause()


def risk_distribution() -> None:
    print("\n═══ Risk Distribution ═══")
    d = data.build_dashboard()
    _print_header(d)
    print("\n  Risk levels:")
    for r in progress.RISK_LEVELS:
        n = d.by_risk.get(r, 0)
        print(f"    {r:<10} : {n}")
    print("\n  Overall ratings:")
    for r in progress.RATINGS:
        n = d.by_overall.get(r, 0)
        if n:
            print(f"    {r:<28} : {n}")
    print("\n  Review status:")
    for s in progress.REVIEW_STATUSES:
        n = d.by_status.get(s, 0)
        if n:
            print(f"    {s:<12} : {n}")
    _pause()


def at_risk() -> None:
    print("\n═══ High / Critical Risk Students ═══")
    rows = data.students_at_risk()
    _print_rows(rows)
    _pause()


def unreviewed() -> None:
    print("\n═══ Students Without a Review ═══")
    rows = data.students_without_review()
    _print_rows(rows)
    _pause()


def overdue() -> None:
    print("\n═══ Students With Overdue Targets ═══")
    rows = data.students_with_overdue_targets()
    _print_rows(rows)
    _pause()


def filter_by_risk() -> None:
    print("\n═══ Filter by Risk Level ═══")
    print("  Levels: " + ", ".join(progress.RISK_LEVELS))
    try:
        choice = _input("Risk level")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if choice not in progress.RISK_LEVELS:
        print(f"  ✗ Must be one of: {', '.join(progress.RISK_LEVELS)}")
        _pause()
        return
    d = data.build_dashboard(risk_filter=choice)
    _print_rows(d.rows)
    _pause()


# ── Menu ──────────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Overview (all students)",     overview),
    ("Risk Distribution",           risk_distribution),
    ("High / Critical Risk",        at_risk),
    ("Students Without a Review",   unreviewed),
    ("Students With Overdue Targets", overdue),
    ("Filter by Risk",              filter_by_risk),
]


def run() -> None:
    while True:
        print("\n── Progress Dashboard ──")
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
            logger.exception("Progress dashboard CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Progress Dashboard":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Progress dashboard CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
