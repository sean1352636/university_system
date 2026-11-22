"""CLI flows for Sixth Form Risk Analytics.

Submenu: run a scan / view at-risk register / per-student breakdown /
band summary.
"""

from __future__ import annotations

import logging
from typing import Callable

from education_system.systems.sixth_form.domain.assessment.risk_analytics import (
    risk_analytics as data,
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


_BAND_MARK = {"Low": " ", "Medium": "•", "High": "!", "Critical": "‼"}


def _run_scan() -> None:
    print("\n  Scanning all active students...")
    errors: list[str] = []
    results = data.scan_all(errors=errors)
    print(f"  ✓ Assessed {len(results)} students.")
    for err in errors:
        print(f"  ✗ Not assessed — {err}")
    counts = data.summary()
    for band in data.BANDS:
        print(f"    {band:9} {counts.get(band, 0)}")
    _pause()


def _register() -> None:
    band = _input("Filter band (Low/Medium/High/Critical, blank=all)")
    band = band.title() if band else None
    if band and band not in data.BANDS:
        print("  Invalid band.")
        return _pause()
    snaps = data.latest_snapshots(band=band)
    if not snaps:
        print("\n  No snapshots yet — run a scan first.")
        return _pause()
    print(f"\n  {'Student':<26}{'Score':>6}  {'Band':<9}{'Attend':>7}"
          f"{'Alerts':>8}{'Interv.':>8}")
    print("  " + "-" * 68)
    for s in snaps:
        att = f"{s['attendance_pct']}%" if s["attendance_pct"] is not None else "—"
        mark = _BAND_MARK.get(s["band"], " ")
        print(f"  {mark} {s['full_name'][:23]:<24}{s['score']:>6}  {s['band']:<9}{att:>7}"
              f"{s.get('open_alerts', 0):>8}{s.get('open_interventions', 0):>8}")
    _pause()


def _per_student() -> None:
    sid = _input("Student ID")
    if not sid:
        return
    try:
        a = data.assess_student(sid)
    except ValueError as e:
        print(f"  ✗ {e}")
        return _pause()
    print(f"\n  {a.full_name} ({a.student_id})")
    print(f"  Risk score: {a.score}/100  →  {a.band}")
    print(f"  Attendance: {a.attendance_pct}%   Net negative behaviour: {a.behaviour_points}")
    if a.factors:
        print("\n  Contributing factors:")
        for f in a.factors:
            print(f"    +{f.points:<5} {f.detail}")
    else:
        print("\n  No risk factors detected.")
    if a.predictions:
        print("\n  Forecast by subject:")
        print(f"    {'Subject':<22}{'Base':>5}{'Mock':>5}{'Pred':>5}{'Fcast':>6}{'Target':>7}  On-target")
        for p in a.predictions:
            ot = "—" if p.on_target is None else ("yes" if p.on_target else "NO")
            print(f"    {p.subject[:20]:<22}{(p.baseline_grade or '—'):>5}"
                  f"{(p.latest_mock_grade or '—'):>5}{(p.predicted_grade or '—'):>5}"
                  f"{(p.forecast_grade or '—'):>6}{(p.target_grade or '—'):>7}  {ot}")
    _print_actions(sid)
    _pause()


def _print_actions(sid: str) -> None:
    """Open early-warning alerts and interventions beside the score."""
    try:
        pic = data.student_risk_picture(sid)
    except Exception as e:
        print(f"\n  ✗ Could not load alerts/interventions: {e}")
        return
    live = {iv.intervention_id for iv in pic.open_interventions}
    print(f"\n  Open early-warning alerts ({len(pic.open_alerts)}):")
    for a in pic.open_alerts:
        link = (f"intervention #{a.linked_intervention_id}"
                + ("" if a.linked_intervention_id in live else " (closed)")
                if a.linked_intervention_id else "no intervention yet")
        print(f"    #{a.alert_id:<5} {a.severity:<8} {a.alert_type:<14} "
              f"{a.title[:40]:<40}  {link}")
    print(f"\n  Open interventions ({len(pic.open_interventions)}):")
    for iv in pic.open_interventions:
        print(f"    #{iv.intervention_id:<5} {iv.status:<8} "
              f"{iv.intervention_type:<20} {iv.title[:40]}")


def _open_intervention() -> None:
    from education_system.systems.sixth_form.domain.assessment.early_warning import (
        early_warning as ew,
    )
    raw = _input("Early-warning alert ID")
    if not raw.isdigit():
        print("  ✗ Enter an alert number.")
        return _pause()
    try:
        iv, created = ew.open_intervention(int(raw))
    except ew.ValidationError as e:
        print(f"  ✗ {e}")
        return _pause()
    print(f"  ✓ {'Opened' if created else 'Already linked to'} "
          f"intervention #{iv.intervention_id}: {iv.title}")
    _pause()


_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Run risk scan (all students)", _run_scan),
    ("At-risk register", _register),
    ("Per-student breakdown", _per_student),
    ("Open intervention from an alert", _open_intervention),
]


def run() -> None:
    while True:
        print("\n── Risk Analytics ──")
        for i, (label, _) in enumerate(_MENU, 1):
            print(f"  {i}) {label}")
        print("  0) Back")
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
            logger.exception("Risk-analytics CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Risk Analytics":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Risk-analytics CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
