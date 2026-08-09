"""CLI flows for attendance analysis, returns and configuration.

Submenu hung off Attendance: the analytics that say what the figures
mean, the anomaly sweep, the governor report, the statutory returns, and
the two configuration screens — thresholds and the calendar — that
everything else reads from.
"""

from __future__ import annotations

import logging
from datetime import date as _date, timedelta as _timedelta
from typing import Callable

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance_analytics as analytics,
    attendance_anomalies as anomalies,
    attendance_calendar as calendar,
    attendance_census as census,
    attendance_governor_report as governor,
    attendance_integration as integration,
    attendance_thresholds as thresholds,
)
from education_system.systems.sixth_form.domain.academics.attendance.attendance import (
    ValidationError,
)
from education_system.systems.sixth_form.domain.academics.attendance.attendance_cli import (
    _input,
    _pause,
    _pick_from,
    _UserAbort,
)
from education_system.systems.sixth_form.domain.academics.timetable.timetable import (
    day_name,
)

logger = logging.getLogger(__name__)


def _today() -> str:
    return _date.today().isoformat()


def _term_ago() -> str:
    return (_date.today() - _timedelta(days=42)).isoformat()


def _yes(prompt: str, *, default: str = "n") -> bool:
    return _input(prompt, default=default).lower().startswith("y")


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value:.1f}%"


# ═══ Analytics ══════════════════════════════════════════════════════

def insight_correlation() -> None:
    print("\n═══ Attendance and Attainment ═══")
    print("\n  Not 'does attendance matter in general' — does it here,")
    print("  this year. Reported with its sample size, never as proof.")
    try:
        date_from = _input("From (YYYY-MM-DD)", default=_term_ago())
        date_to = _input("To (YYYY-MM-DD)", default=_today())
        overall = analytics.attainment_correlation(date_from=date_from,
                                                   date_to=date_to)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except _UserAbort:
        return
    print(f"\n  {overall.label}")
    if overall.reliable:
        print(f"    Mean attendance {_pct(overall.mean_attendance)}, "
              f"mean grade points {overall.mean_points}")
    by_subject = analytics.correlation_by_subject(date_from=date_from,
                                                  date_to=date_to)
    if by_subject:
        print("\n  By subject:")
        for entry in by_subject[:15]:
            print(f"    {entry.label}")
    _pause()


def insight_subjects() -> None:
    print("\n═══ One Learner, By Subject ═══")
    print("\n  'Is it everything, or one class?' changes the conversation.")
    try:
        student_id = _input("Student ID", allow_empty=False)
        rows = analytics.subject_comparison(student_id)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except _UserAbort:
        return
    if not rows:
        print("\n  No marks in the window.")
        _pause()
        return
    for entry in rows:
        flag = "  ← outlier" if entry.is_outlier else ""
        print(f"    {entry.label}{flag}")
    insight = analytics.learner_insight(student_id)
    if insight["is_single_subject_problem"]:
        print("\n  ⚠ This looks like one subject, not a general pattern.")
    print(f"\n  {insight['forecast'].label}")
    _pause()


def insight_forecast() -> None:
    print("\n═══ Forecast ═══")
    try:
        one = _yes("One learner? (y/N)")
        if one:
            projection = analytics.forecast(
                _input("Student ID", allow_empty=False))
            print(f"\n  {projection.label}")
            print(f"    Sessions so far {projection.sessions_so_far}, "
                  f"remaining {projection.sessions_remaining}")
        else:
            rows = analytics.forecast_cohort()
            if not rows:
                print("\n  ✓ Nobody is projected to finish below target.")
            else:
                print(f"\n  {len(rows)} learner(s) projected below target:\n")
                for projection in rows[:30]:
                    print(f"    {projection.label}")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
    except _UserAbort:
        return
    _pause()


def insight_benchmark() -> None:
    print("\n═══ This Year Against Last ═══")
    try:
        overall = analytics.benchmark()
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  {overall.label}")
    if overall.current_window:
        print(f"    Comparing {overall.current_window[0]}→"
              f"{overall.current_window[1]} with "
              f"{overall.previous_window[0]}→{overall.previous_window[1]}")
    groups = analytics.benchmark_by_group()
    if groups:
        print("\n  By group (biggest fall first):")
        for entry in groups[:15]:
            print(f"    {entry.label}")
    _pause()


def insight_heatmap() -> None:
    print("\n═══ Attendance Heatmap ═══")
    print("\n  Bad Friday afternoons are real, and usually a timetabling")
    print("  decision rather than a pastoral one.")
    try:
        grid = analytics.heatmap()
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    if not grid.cells:
        print("\n  No marks in the window.")
        _pause()
        return
    periods = sorted({p for _d, p in grid.cells})
    header = "".join(f"{'P' + str(p):>8}" for p in periods)
    print(f"\n    {'Day':<6}{header}")
    for weekday, cells in grid.rows():
        row = "".join(
            f"{(f'{c.percentage:.0f}%' if c and c.percentage is not None else '—'):>8}"
            for c in cells)
        print(f"    {day_name(weekday):<6}{row}")
    worst, best = grid.worst, grid.best
    if worst:
        print(f"\n  Worst: {day_name(worst.weekday)} P{worst.period} "
              f"({_pct(worst.percentage)})")
    if best:
        print(f"  Best:  {day_name(best.weekday)} P{best.period} "
              f"({_pct(best.percentage)})")
    _pause()


_ANALYTICS_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Attendance vs attainment", insight_correlation),
    ("One learner by subject",   insight_subjects),
    ("Forecast",                 insight_forecast),
    ("This year against last",   insight_benchmark),
    ("Heatmap",                  insight_heatmap),
]


# ═══ Anomalies ══════════════════════════════════════════════════════

def anomaly_sweep() -> None:
    print("\n═══ Marking Anomaly Sweep ═══")
    print("\n  Shapes, not accusations. The usual explanation is a teacher")
    print("  under time pressure, which is a workload problem.")
    try:
        window = int(_input("Window (days)", default="90"))
        report = anomalies.sweep(window_days=window)
    except ValueError:
        print("\n  ✗ Window must be a number.")
        _pause()
        return
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except _UserAbort:
        return
    print(f"\n  {report.summary}")
    if not report.findings:
        _pause()
        return
    print()
    for finding in report.findings[:40]:
        print(f"    {finding.label}")
    grouped = anomalies.by_owner(report)
    if grouped:
        print("\n  By person:")
        for owner, findings in sorted(grouped.items(),
                                      key=lambda kv: -len(kv[1])):
            print(f"    {owner[:26]:<28}{len(findings)} finding(s)")
    _pause()


def anomaly_slot() -> None:
    print("\n═══ One Slot's Marking ═══")
    try:
        slot_id = int(_input("Slot ID", allow_empty=False))
        health = anomalies.slot_health(slot_id)
    except ValueError:
        print("\n  ✗ Slot ID must be a number.")
        _pause()
        return
    except _UserAbort:
        return
    profile = health["profile"]
    print(f"\n  Slot #{slot_id}: {profile.registers} register(s), "
          f"{profile.marks} mark(s)")
    print(f"    Absence rate      {_pct(profile.absence_rate)}")
    print(f"    Lateness rate     {_pct(profile.late_rate)}")
    print(f"    Prefilled marks   {_pct(profile.copy_forward_rate)}")
    print(f"    Repeated register {_pct(profile.repetition_rate)}")
    if health["findings"]:
        print("\n  Findings:")
        for finding in health["findings"]:
            print(f"    {finding.label}")
    elif health["looks_healthy"]:
        print("\n  ✓ Nothing unusual.")
    _pause()


_ANOMALY_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Run the sweep",     anomaly_sweep),
    ("One slot's marking", anomaly_slot),
]


# ═══ Governor report ════════════════════════════════════════════════

def report_build() -> None:
    print("\n═══ Governor / SLT Report ═══")
    try:
        use_term = _yes("Use the current term? (Y/n)", default="y")
        if use_term:
            report = governor.build()
        else:
            report = governor.build(
                date_from=_input("From (YYYY-MM-DD)", allow_empty=False),
                date_to=_input("To (YYYY-MM-DD)", default=_today()),
                period_label=_input("Period label (optional)") or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except _UserAbort:
        return
    print()
    print(governor.render_text(report))
    try:
        if _yes("\n  Save it? (y/N)"):
            fmt = _pick_from("Format", ["text", "markdown", "json"],
                             default="markdown")
            path = _input("Path", default=f"attendance_report.{fmt[:2]}")
            saved = governor.save(report, path, fmt=fmt)
            print(f"\n  ✓ Written to {saved}")
    except (ValidationError, OSError) as e:
        print(f"\n  ✗ {e}")
    except _UserAbort:
        pass
    _pause()


def report_trend() -> None:
    print("\n═══ Attendance Over Recent Terms ═══")
    series = governor.termly_series()
    if not series:
        print("\n  No terms configured — set them up in the calendar.")
    for label, percentage in series:
        bar = "█" * int((percentage or 0) / 4)
        print(f"    {label[:34]:<36}{_pct(percentage):>7}  {bar}")
    _pause()


_REPORT_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Build the report",  report_build),
    ("Termly trend",      report_trend),
]


# ═══ Statutory returns ══════════════════════════════════════════════

def return_build() -> None:
    print("\n═══ Build a Statutory Return ═══")
    try:
        kind = _pick_from("Return", list(census.RETURN_KINDS),
                          default=census.CENSUS)
        date_from = _input("From (YYYY-MM-DD)", allow_empty=False)
        date_to = _input("To (YYYY-MM-DD)", default=_today())
        builder = (census.ilr_extract if kind == census.ILR
                   else census.census_extract)
        built = builder(date_from=date_from, date_to=date_to)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except _UserAbort:
        return
    print(f"\n  {built.summary}")
    print()
    print(census.validation_report(built))
    if not built.submittable:
        print("\n  Fix the errors above, then build it again.")
        _pause()
        return
    try:
        if _yes("\n  Export to CSV? (y/N)"):
            path = _input("Path", default=f"attendance_{kind}.csv")
            saved = census.save(built, path)
            print(f"\n  ✓ Written to {saved}")
            print("    Nothing has been submitted — that is still a")
            print("    deliberate act by somebody who has read the above.")
    except (ValidationError, OSError) as e:
        print(f"\n  ✗ {e}")
    except _UserAbort:
        pass
    _pause()


def return_codes() -> None:
    print("\n═══ Code Mapping ═══")
    print()
    print(census.mapping_table())
    try:
        date_from = _input("\n  Usage from (YYYY-MM-DD)", default=_term_ago())
        date_to = _input("  Usage to (YYYY-MM-DD)", default=_today())
        usage = census.code_usage(date_from=date_from, date_to=date_to)
    except (ValidationError, _UserAbort):
        _pause()
        return
    if usage:
        print("\n  Code usage in that window:")
        for code, n in list(usage.items())[:25]:
            print(f"    {code:<12}{n:>6}")
        if "O" not in usage:
            print("\n  ⚠ No unauthorised absences coded at all. A college")
            print("    with no truancy is coding everything as authorised.")
    _pause()


_RETURN_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Build & validate a return", return_build),
    ("Code mapping & usage",      return_codes),
]


# ═══ Configuration ══════════════════════════════════════════════════

def config_thresholds() -> None:
    print("\n═══ Thresholds ═══")
    print("\n  Every figure the rest of the system branches on.")
    rows = thresholds.list_thresholds(scope=thresholds.SCOPE_COLLEGE)
    print(f"\n    {'Key':<26}{'Value':>8}  {'Direction':<9}Description")
    for entry in rows:
        print(f"    {entry.key:<26}{entry.value:>7g}{entry.unit or '':<2}"
              f"{entry.direction:<9}{(entry.description or '')[:34]}")
    try:
        if not _yes("\n  Change one? (y/N)"):
            return
        key = _input("Key", allow_empty=False)
        value = float(_input("New value", allow_empty=False))
        scope = _pick_from("Scope", list(thresholds.SCOPES),
                           default=thresholds.SCOPE_COLLEGE)
        scope_value = (None if scope == thresholds.SCOPE_COLLEGE
                       else _input(f"Which {scope}", allow_empty=False))
        updated = thresholds.set_threshold(
            key, value, scope=scope, scope_value=scope_value,
            actor=_input("Changed by") or None)
        print(f"\n  ✓ {updated.label}")
    except ValueError:
        print("\n  ✗ Value must be a number.")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
    except _UserAbort:
        print("\n  Cancelled.")
    _pause()


def config_calendar() -> None:
    print("\n═══ Calendar ═══")
    terms = calendar.list_terms()
    if terms:
        print("\n  Terms:")
        for term in terms:
            print(f"    {term.label}")
    else:
        print("\n  ⚠ No terms configured — everything counts as term time,")
        print("    which makes half term look like a fortnight of absence.")
    try:
        action = _pick_from("Action", ["Add a term", "Mark non-teaching days",
                                       "Check a date", "Nothing"],
                            default="Nothing")
        if action == "Add a term":
            term = calendar.add_term(
                _input("Name", allow_empty=False),
                _input("Starts (YYYY-MM-DD)", allow_empty=False),
                _input("Ends (YYYY-MM-DD)", allow_empty=False),
                academic_year=_input("Academic year (optional)") or None)
            print(f"\n  ✓ {term.label}")
        elif action == "Mark non-teaching days":
            kind = _pick_from("Kind", list(calendar.DAY_KINDS),
                              default=calendar.HALF_TERM)
            year_group = _input("Year group (blank = whole college)") or None
            added = calendar.add_range(
                _input("From (YYYY-MM-DD)", allow_empty=False),
                _input("To (YYYY-MM-DD)", allow_empty=False),
                kind=kind,
                year_group=int(year_group) if year_group else None,
                name=_input("Name (optional)") or None)
            print(f"\n  ✓ {added} day(s) marked {kind}.")
        elif action == "Check a date":
            date_s = _input("Date (YYYY-MM-DD)", default=_today())
            status = calendar.day_status(date_s)
            state = ("open" if status.open else "closed")
            print(f"\n  {date_s} is {state}"
                  + (f" — {status.reason}" if status.reason else "")
                  + (f" (sessions: {', '.join(status.sessions)})"
                     if status.sessions else ""))
    except ValueError:
        print("\n  ✗ Year group must be a number.")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
    except _UserAbort:
        print("\n  Cancelled.")
    _pause()


def config_retention() -> None:
    print("\n═══ Retention & Subject Access ═══")
    try:
        report = integration.retention_report()
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  Retention: {report['retention_years']} years "
          f"(cutoff {report['cutoff']})")
    print(f"    Attendance marks beyond it : {report['attendance_marks']}")
    print(f"    Session marks              : {report['session_marks']}")
    print(f"    Kiosk events               : {report['kiosk_events']}")
    print(f"    Notifications              : {report['notifications']}")
    print(f"\n  {report['action']}")
    try:
        if report["total"] and _yes("\n  Purge now? (y/N)"):
            if _yes("  This cannot be undone. Really? (y/N)"):
                result = integration.purge(
                    dry_run=False, actor=_input("Authorised by") or None)
                print(f"\n  ✓ {result.total} row(s) deleted.")
        if _yes("\n  Export one learner's data (subject access)? (y/N)"):
            student_id = _input("Student ID", allow_empty=False)
            path = _input("Path", default=f"{student_id}_attendance.json")
            from pathlib import Path
            Path(path).write_text(
                integration.subject_access_json(student_id),
                encoding="utf-8")
            print(f"\n  ✓ Written to {path}")
    except (ValidationError, OSError) as e:
        print(f"\n  ✗ {e}")
    except _UserAbort:
        print("\n  Cancelled.")
    _pause()


def config_webhooks() -> None:
    print("\n═══ Webhooks ═══")
    subscriptions = integration.list_subscriptions(active_only=False)
    if subscriptions:
        for subscription in subscriptions:
            health = "ok" if subscription.healthy else "⚠ failing"
            events = ", ".join(subscription.events) or "all events"
            print(f"    {subscription.name:<20}{subscription.url[:38]:<40}"
                  f"{health}")
            print(f"      {events}")
    else:
        print("\n  None registered.")
    dead = integration.dead_letters()
    if dead:
        print(f"\n  ⚠ {len(dead)} event(s) gave up after "
              f"{integration.MAX_ATTEMPTS} attempts.")
    try:
        if _yes("\n  Register a subscriber? (y/N)"):
            subscription = integration.subscribe(
                _input("Name", allow_empty=False),
                _input("URL", allow_empty=False),
                secret=_input("Signing secret (optional)") or None)
            print(f"\n  ✓ {subscription.name} registered.")
        if dead and _yes("  Retry the dead letters? (y/N)"):
            n = integration.retry_dead()
            print(f"\n  ✓ {n} event(s) requeued.")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
    except _UserAbort:
        print("\n  Cancelled.")
    _pause()


_CONFIG_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Thresholds",            config_thresholds),
    ("Calendar & term dates", config_calendar),
    ("Retention & subject access", config_retention),
    ("Webhooks",              config_webhooks),
]


# ── Submenu plumbing ────────────────────────────────────────────────

def _run_menu(title: str, menu: list[tuple[str, Callable[[], None]]]) -> None:
    while True:
        print(f"\n── {title} ──")
        for i, (label, _) in enumerate(menu, 1):
            print(f"  {i}) {label}")
        print("  0) Back")
        try:
            choice = input("  Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if choice == "0":
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(menu)):
            print("  Invalid selection.")
            continue
        _, handler = menu[int(choice) - 1]
        try:
            handler()
        except _UserAbort:
            print("\n  Cancelled.")
        except Exception as e:
            logger.exception("Insight CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def analytics_menu() -> None:
    _run_menu("Analytics", _ANALYTICS_MENU)


def anomalies_menu() -> None:
    _run_menu("Marking Anomalies", _ANOMALY_MENU)


def governor_menu() -> None:
    _run_menu("Governor Report", _REPORT_MENU)


def returns_menu() -> None:
    _run_menu("Statutory Returns", _RETURN_MENU)


def config_menu() -> None:
    _run_menu("Configuration", _CONFIG_MENU)


_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Analytics",          analytics_menu),
    ("Marking Anomalies",  anomalies_menu),
    ("Governor Report",    governor_menu),
    ("Statutory Returns",  returns_menu),
    ("Configuration",      config_menu),
]


def run() -> None:
    _run_menu("Analysis, Returns & Configuration", _MENU)
