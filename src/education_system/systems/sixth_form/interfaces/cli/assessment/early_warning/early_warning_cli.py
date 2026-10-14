"""CLI flows for Sixth Form Early Warning."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable
from education_system.systems.sixth_form.domain.assessment.early_warning import (
    early_warning as data,
)
from education_system.systems.sixth_form.domain.learners.students import (
    students as student_data,
)
from education_system.systems.sixth_form.domain.assessment.early_warning.early_warning import (
    ALERT_TYPES,
    Alert,
    DEFAULT_ALERT_TYPE,
    DEFAULT_SEVERITY,
    DEFAULT_SOURCE,
    DEFAULT_STATUS,
    SEVERITIES,
    SOURCES,
    STATUSES,
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


def _multiline(prompt: str, *, default: str = "") -> str:
    print(f"\n  {prompt} (end with '.'; ENTER for default)")
    if default:
        for line in default.splitlines():
            print(f"    | {line}")
    lines: list[str] = []
    try:
        while True:
            ln = input("  > ")
            if ln.strip() == ".":
                break
            if not lines and not ln:
                return default
            lines.append(ln)
    except (EOFError, KeyboardInterrupt):
        print()
        raise _UserAbort
    return "\n".join(lines)


def _pick_from(label: str, options: list[str],
                default: str | None = None) -> str:
    print(f"\n  {label}:")
    for i, opt in enumerate(options, 1):
        marker = " *" if opt == default else "  "
        print(f"    {marker}{i:>2}) {opt}")
    while True:
        raw = _input(f"  Pick #1..{len(options)}",
                      default=default or "")
        if default and raw == default:
            return default
        if not raw.isdigit():
            print("    Enter a number (or 'cancel' to abort).")
            continue
        n = int(raw)
        if not (1 <= n <= len(options)):
            print("    Out of range.")
            continue
        return options[n - 1]


def _pick_student() -> str:
    rows = student_data.list_students()
    if not rows:
        print("    No students.")
        raise _UserAbort
    print("\n  Students:")
    for i, s in enumerate(rows, 1):
        print(f"    {i:>3}) {s.student_id}  {s.full_name}")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or student id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1].student_id
            continue
        match = next((s for s in rows
                       if s.student_id.lower() == raw.lower()), None)
        if match:
            return match.student_id
        print("    No matching student.")


def _pick_alert() -> Alert:
    rows = data.list_alerts()
    if not rows:
        print("    No alerts.")
        raise _UserAbort
    names = {s.student_id: s.full_name
              for s in student_data.list_students()}
    print("\n  Alerts:")
    for i, a in enumerate(rows, 1):
        flag = "!" if a.severity == "Critical" else " "
        print(f"    {i:>3}){flag}#{a.alert_id}  "
              f"{a.student_id}  "
              f"{names.get(a.student_id, '?')[:14]:<14}  "
              f"{a.alert_type[:14]:<14}  "
              f"{a.severity:<8}  "
              f"[{a.status}]  {a.title[:30]}")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            match = next((a for a in rows if a.alert_id == n), None)
            if match:
                return match
        print("    No matching alert.")


# ── Print helpers ──────────────────────────────────────────────────

def _print_alerts(rows: list[Alert]) -> None:
    if not rows:
        print("\n  (no alerts)")
        return
    names = {s.student_id: s.full_name
              for s in student_data.list_students()}
    print()
    print(f"  {'#':>4}  {'Student':<10}  {'Name':<18}  "
          f"{'Type':<14}  {'Severity':<10}  {'Status':<13}  "
          f"{'Raised':<10}  {'Age':>4}  Title")
    print("  " + "-" * 130)
    for a in rows:
        print(f"  {a.alert_id:>4}  {a.student_id:<10}  "
              f"{names.get(a.student_id, '?')[:18]:<18}  "
              f"{a.alert_type[:14]:<14}  "
              f"{a.severity:<10}  {a.status:<13}  "
              f"{a.raised_on:<10}  {a.age_days:>3}d  "
              f"{a.title[:30]}")
    print(f"\n  {len(rows)} alert(s).")


def _print_alert_full(a: Alert) -> None:
    print()
    print(f"    #{a.alert_id}  {a.title}")
    print(f"    Student         : {a.student_id}")
    print(f"    Type            : {a.alert_type}")
    print(f"    Severity        : {a.severity}")
    print(f"    Status          : {a.status}  (age "
          f"{a.age_days}d)")
    print(f"    Source          : {a.source}")
    print(f"    Raised on/by    : {a.raised_on} / "
          f"{a.raised_by or '—'}")
    if a.acknowledged_on:
        print(f"    Acknowledged    : {a.acknowledged_on} by "
              f"{a.acknowledged_by or '—'}")
    if a.resolved_on:
        print(f"    Resolved        : {a.resolved_on} by "
              f"{a.resolved_by or '—'}")
    if a.trigger_metric:
        print(f"    Trigger metric  : {a.trigger_metric}")
    if a.threshold:
        print(f"    Threshold       : {a.threshold}")
    if a.linked_ilp_id:
        print(f"    Linked ILP      : #{a.linked_ilp_id}")
    if a.linked_intervention_id:
        print(f"    Linked iv'tion  : #{a.linked_intervention_id}")
    if a.description:
        print()
        print("    Description:")
        for line in a.description.splitlines():
            print(f"      {line}")
    if a.action_taken:
        print()
        print("    Action taken:")
        for line in a.action_taken.splitlines():
            print(f"      {line}")
    if a.notes:
        print()
        print("    Notes:")
        for line in a.notes.splitlines():
            print(f"      {line}")


# ── Flows ──────────────────────────────────────────────────────────

def list_open() -> None:
    print("\n═══ Open Alerts ═══")
    _print_alerts(data.list_alerts(open_only=True))
    _pause()


def list_critical() -> None:
    print("\n═══ Critical / High Open Alerts ═══")
    rows = data.list_alerts(open_only=True, min_severity="High")
    _print_alerts(rows)
    _pause()


def list_all() -> None:
    print("\n═══ All Alerts ═══")
    _print_alerts(data.list_alerts())
    _pause()


def filter_flow() -> None:
    print("\n═══ Filter Alerts ═══")
    try:
        sid = _input("Student id") or None
        atype = _input(f"Type ({'/'.join(ALERT_TYPES[:3])}…)") or None
        severity = _input(f"Severity ({'/'.join(SEVERITIES)})") or None
        status = _input(f"Status ({'/'.join(STATUSES)})") or None
        source = _input(f"Source ({'/'.join(SOURCES[:3])}…)") or None
        title = _input("Title contains") or None
        df = _input("From (YYYY-MM-DD)") or None
        dt2 = _input("To (YYYY-MM-DD)") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.list_alerts(
            student_id=sid, alert_type=atype,
            severity=severity, status=status, source=source,
            title_like=title, date_from=df, date_to=dt2,
        )
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_alerts(rows)
    _pause()


def per_student_flow() -> None:
    print("\n═══ Per-Student Alerts ═══")
    try:
        sid = _pick_student()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_alerts(data.alerts_for_student(sid))
    summ = data.student_summary(sid)
    print(f"\n  Summary for {sid}:")
    print(f"    Total          : {summ.total}")
    print(f"    Open           : {summ.open_count}")
    print(f"    Critical open  : {summ.critical_open}")
    print(f"    High open      : {summ.high_open}")
    if summ.by_type:
        print("    By type:")
        for t, n in summ.by_type.items():
            print(f"      {t:<22} : {n}")
    _pause()


def view_flow() -> None:
    print("\n═══ View Alert ═══")
    try:
        a = _pick_alert()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_alert_full(a)
    _pause()


def _collect_form(existing: Alert | None) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    is_edit = existing is not None
    if is_edit:
        payload["student_id"] = existing.student_id
        print(f"\n  Editing for student {existing.student_id}")
    else:
        payload["student_id"] = _pick_student()
    payload["title"] = _input(
        "Title",
        default=(existing.title if is_edit else ""),
        allow_empty=False)
    payload["alert_type"] = _pick_from(
        "Type", list(ALERT_TYPES),
        default=(existing.alert_type if is_edit
                  else DEFAULT_ALERT_TYPE))
    payload["severity"] = _pick_from(
        "Severity", list(SEVERITIES),
        default=(existing.severity if is_edit
                  else DEFAULT_SEVERITY))
    payload["source"] = _pick_from(
        "Source", list(SOURCES),
        default=(existing.source if is_edit else DEFAULT_SOURCE))
    payload["status"] = _pick_from(
        "Status", list(STATUSES),
        default=(existing.status if is_edit else DEFAULT_STATUS))
    payload["raised_on"] = _input(
        "Raised on (YYYY-MM-DD)",
        default=(existing.raised_on if is_edit
                  else _date.today().isoformat()))
    payload["raised_by"] = _input(
        "Raised by",
        default=(existing.raised_by or "") if is_edit else "")
    payload["trigger_metric"] = _input(
        "Trigger metric (e.g. 'Attendance 78%')",
        default=(existing.trigger_metric or "")
        if is_edit else "")
    payload["threshold"] = _input(
        "Threshold (e.g. 'Attendance < 90%')",
        default=(existing.threshold or "") if is_edit else "")
    try:
        payload["description"] = _multiline(
            "Description",
            default=(existing.description or "")
            if is_edit else "")
        payload["action_taken"] = _multiline(
            "Action taken",
            default=(existing.action_taken or "")
            if is_edit else "")
    except _UserAbort:
        raise
    payload["linked_ilp_id"] = _input(
        "Linked ILP id (optional)",
        default=(str(existing.linked_ilp_id)
                  if is_edit and existing.linked_ilp_id else ""))
    payload["linked_intervention_id"] = _input(
        "Linked intervention id (optional)",
        default=(str(existing.linked_intervention_id)
                  if is_edit and existing.linked_intervention_id
                  else ""))
    payload["notes"] = _input(
        "Notes",
        default=(existing.notes or "") if is_edit else "")
    return payload


def new_alert() -> None:
    print("\n═══ New Alert ═══")
    try:
        payload = _collect_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        a = data.create_alert(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Raised alert #{a.alert_id}")
    _pause()


def edit_alert() -> None:
    print("\n═══ Edit Alert ═══")
    try:
        a = _pick_alert()
        payload = _collect_form(a)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_alert(a.alert_id, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated #{a.alert_id}")
    _pause()


def acknowledge_flow() -> None:
    print("\n═══ Acknowledge Alert ═══")
    try:
        a = _pick_alert()
        by = _input("Acknowledged by")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.acknowledge(a.alert_id, acknowledged_by=by or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{a.alert_id} → Acknowledged")
    _pause()


def resolve_flow() -> None:
    print("\n═══ Resolve Alert ═══")
    try:
        a = _pick_alert()
        by = _input("Resolved by")
        action = _multiline("Action taken")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.resolve(a.alert_id,
                        resolved_by=by or None,
                        action_taken=action or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{a.alert_id} → Resolved")
    _pause()


def dismiss_flow() -> None:
    print("\n═══ Dismiss Alert ═══")
    try:
        a = _pick_alert()
        by = _input("Dismissed by")
        reason = _input("Reason")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.dismiss(a.alert_id,
                        resolved_by=by or None,
                        reason=reason or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{a.alert_id} → Dismissed")
    _pause()


def escalate_flow() -> None:
    print("\n═══ Escalate Alert ═══")
    try:
        a = _pick_alert()
        by = _input("Escalated by")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        upd = data.escalate(a.alert_id, raised_by=by or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{a.alert_id} → {upd.severity} / {upd.status}")
    _pause()


def set_status_flow() -> None:
    print("\n═══ Change Status ═══")
    try:
        a = _pick_alert()
        new_status = _pick_from("New status", list(STATUSES),
                                  default=a.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_status(a.alert_id, new_status)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{a.alert_id} → {new_status}")
    _pause()


def delete_flow() -> None:
    print("\n═══ Delete Alert ═══")
    try:
        a = _pick_alert()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete alert #{a.alert_id}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_alert(a.alert_id):
        print(f"\n  ✓ Deleted #{a.alert_id}")
    _pause()


def scan_flow() -> None:
    print("\n═══ Auto-Scan for Alerts ═══")
    print("  Scans attendance, behaviour, and target setting "
          "for tripped thresholds. Existing open alerts of the "
          "same (student × type × source) are skipped.\n")
    try:
        att_window = int(_input("Attendance window (days)",
                                   default="28"))
        att_min = float(_input("Min attendance %",
                                  default="90"))
        beh_window = int(_input("Behaviour window (days)",
                                   default="28"))
        beh_max = int(_input("Max negatives in window",
                                default="5"))
        by = _input("Raised by", default="Auto Scanner")
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    try:
        result = data.scan(
            raised_by=by or None,
            attendance_window_days=att_window,
            attendance_min_pct=att_min,
            behaviour_window_days=beh_window,
            behaviour_max_negatives=beh_max,
        )
    except Exception as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created {result.created} alert(s), "
          f"skipped {result.skipped_duplicates} duplicate(s)")
    if result.sources:
        print("  By source:")
        for src, n in result.sources.items():
            print(f"    {src:<22} : {n}")
    _pause()


def summary_flow() -> None:
    print("\n═══ Early Warning Summary ═══")
    summ = data.summary()
    print(f"\n  Total alerts        : {summ.total}")
    print(f"  Open                : {summ.open_count}")
    print(f"  Critical open       : {summ.critical_open}")
    print(f"  High open           : {summ.high_open}")
    print(f"  Aged ≥ 14d (open)   : {summ.aged_over_14_days}")
    print(f"  Distinct students   : {summ.distinct_students}")
    print("\n  By status:")
    for s in STATUSES:
        n = summ.by_status.get(s, 0)
        if n:
            print(f"    {s:<14} : {n}")
    print("\n  By severity:")
    for s in SEVERITIES:
        n = summ.by_severity.get(s, 0)
        if n:
            print(f"    {s:<10} : {n}")
    print("\n  By type:")
    for t in ALERT_TYPES:
        n = summ.by_type.get(t, 0)
        if n:
            print(f"    {t:<22} : {n}")
    print("\n  By source:")
    for s in SOURCES:
        n = summ.by_source.get(s, 0)
        if n:
            print(f"    {s:<22} : {n}")
    _pause()


# ── Submenu ───────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Open alerts",          list_open),
    ("Critical / High open", list_critical),
    ("All alerts",           list_all),
    ("Filter",               filter_flow),
    ("Per-student",          per_student_flow),
    ("View alert",           view_flow),
    ("─" * 6,                lambda: None),
    ("New alert",            new_alert),
    ("Edit alert",           edit_alert),
    ("Acknowledge",          acknowledge_flow),
    ("Resolve",              resolve_flow),
    ("Dismiss",              dismiss_flow),
    ("Escalate",             escalate_flow),
    ("Change status",        set_status_flow),
    ("Delete alert",         delete_flow),
    ("─" * 6,                lambda: None),
    ("Auto-scan for alerts", scan_flow),
    ("Summary",              summary_flow),
]


def run() -> None:
    while True:
        print("\n── Early Warning ──")
        for i, (label, _) in enumerate(_MENU, 1):
            if label.startswith("─"):
                print(f"      {label * 3}")
            else:
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
        label, handler = _MENU[int(choice) - 1]
        if label.startswith("─"):
            continue
        try:
            handler()
        except _UserAbort:
            print("\n  Cancelled.")
        except Exception as e:
            logger.exception("Early-warning CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Early Warning":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Early-warning CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
