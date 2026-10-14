"""CLI flows for Sixth Form Intervention Tracking."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable
from education_system.systems.sixth_form.domain.assessment.intervention_tracking import (
    intervention_tracking as data,
)
from education_system.systems.sixth_form.domain.learners.students import (
    students as student_data,
)
from education_system.systems.sixth_form.domain.assessment.intervention_tracking.intervention_tracking import (
    DEFAULT_DELIVERY_MODE,
    DEFAULT_FREQUENCY,
    DEFAULT_INTERVENTION_TYPE,
    DEFAULT_SESSION_STATUS,
    DEFAULT_STATUS,
    DELIVERY_MODES,
    FREQUENCIES,
    IMPACT_GRADES,
    INTERVENTION_TYPES,
    Intervention,
    SESSION_STATUSES,
    STATUSES,
    Session,
    ValidationError,
    impact_label,
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


def _pick_subject() -> str | None:
    try:
        from education_system.systems.sixth_form.domain.academics.subjects import (
            subjects as _subjects,
        )
        names = [s.name for s in _subjects.list_subjects()]
    except Exception:
        names = []
    if not names:
        return _input("Subject") or None
    return _pick_from("Subject", [""] + names) or None


def _pick_intervention() -> Intervention:
    rows = data.list_interventions()
    if not rows:
        print("    No interventions yet.")
        raise _UserAbort
    names = {s.student_id: s.full_name
              for s in student_data.list_students()}
    print("\n  Interventions:")
    for i, iv in enumerate(rows, 1):
        print(f"    {i:>3}) #{iv.intervention_id}  "
              f"{iv.student_id}  "
              f"{names.get(iv.student_id, '?')[:16]:<16}  "
              f"{iv.intervention_type[:18]:<18}  "
              f"{iv.title[:26]:<26}  [{iv.status}]")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            match = next((iv for iv in rows
                            if iv.intervention_id == n), None)
            if match:
                return match
        print("    No matching intervention.")


def _pick_session(intervention_id: int) -> Session:
    rows = data.list_sessions(intervention_id=intervention_id)
    if not rows:
        print("    No sessions on this intervention.")
        raise _UserAbort
    print("\n  Sessions:")
    for i, s in enumerate(rows, 1):
        print(f"    {i:>3}) #{s.session_id}  {s.session_date}  "
              f"{s.status:<12}  "
              f"{(s.topic or '—')[:20]}")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            match = next((s for s in rows
                            if s.session_id == n), None)
            if match:
                return match
        print("    No matching session.")


# ── Print helpers ──────────────────────────────────────────────────

def _print_interventions(rows: list[Intervention]) -> None:
    if not rows:
        print("\n  (no interventions)")
        return
    names = {s.student_id: s.full_name
              for s in student_data.list_students()}
    print()
    print(f"  {'#':>4}  {'Student':<10}  {'Name':<18}  "
          f"{'Type':<18}  {'Subject':<14}  "
          f"{'Status':<11}  {'Impact':<8}  Title")
    print("  " + "-" * 120)
    for iv in rows:
        impact = (str(iv.impact_grade)
                  if iv.impact_grade is not None else "—")
        print(f"  {iv.intervention_id:>4}  "
              f"{iv.student_id:<10}  "
              f"{names.get(iv.student_id, '?')[:18]:<18}  "
              f"{iv.intervention_type[:18]:<18}  "
              f"{(iv.subject_name or '—')[:14]:<14}  "
              f"{iv.status:<11}  "
              f"{impact:<8}  {iv.title[:30]}")
    print(f"\n  {len(rows)} intervention(s).")


def _print_intervention_full(iv: Intervention) -> None:
    det = data.get_intervention_detail(iv.intervention_id)
    assert det is not None
    print()
    print(f"    #{iv.intervention_id}  {iv.title}")
    print(f"    Student         : {iv.student_id} — "
          f"{det.student_name}")
    print(f"    Type            : {iv.intervention_type}")
    print(f"    Subject         : {iv.subject_name or '—'}")
    print(f"    Lead            : {iv.lead_staff or '—'}")
    print(f"    Mode / Frequency: "
          f"{iv.delivery_mode or '—'} · {iv.frequency or '—'}")
    print(f"    Location        : {iv.location or '—'}")
    print(f"    Range           : "
          f"{iv.start_date or '—'} → {iv.end_date or '—'}")
    print(f"    Sessions planned: {iv.sessions_planned or '—'}")
    print(f"    Sessions logged : {len(det.sessions)}  "
          f"(attended {det.sessions_attended})")
    if det.attendance_pct is not None:
        print(f"    Attendance %    : {det.attendance_pct}")
    print(f"    Total minutes   : {det.total_minutes}")
    print(f"    Status          : {iv.status}")
    print(f"    Impact grade    : "
          f"{iv.impact_grade or '—'}  ({iv.impact_label})")
    print(f"    Funding source  : {iv.funding_source or '—'}")
    print(f"    Referral source : {iv.referral_source or '—'}")
    for label, val in (
            ("Rationale",          iv.rationale),
            ("Success criteria",   iv.success_criteria),
            ("Baseline indicator", iv.baseline_indicator),
            ("Exit indicator",     iv.exit_indicator),
            ("Impact summary",     iv.impact_summary),
            ("Notes",              iv.notes),
    ):
        if val:
            print()
            print(f"    {label}:")
            for line in val.splitlines():
                print(f"      {line}")
    if det.sessions:
        print()
        print("    Sessions:")
        for s in det.sessions:
            mins = (f"{s.duration_minutes}m"
                    if s.duration_minutes is not None else "—")
            print(f"      #{s.session_id}  {s.session_date}  "
                  f"{s.status:<12}  {mins:<6}  "
                  f"{(s.topic or '—')}")


# ── Intervention flows ────────────────────────────────────────────

def list_all() -> None:
    print("\n═══ All Interventions ═══")
    _print_interventions(data.list_interventions())
    _pause()


def list_open() -> None:
    print("\n═══ Open Interventions ═══")
    _print_interventions(data.list_interventions(open_only=True))
    _pause()


def filter_flow() -> None:
    print("\n═══ Filter Interventions ═══")
    try:
        sid = _input("Student id") or None
        itype = _input(
            f"Type ({'/'.join(INTERVENTION_TYPES[:3])}…)") or None
        subj = _input("Subject") or None
        status = _input(f"Status ({'/'.join(STATUSES)})") or None
        lead = _input("Lead contains") or None
        impact_raw = _input("Impact grade (1-4)") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    impact: int | None = None
    if impact_raw:
        try:
            impact = int(impact_raw)
        except ValueError:
            print("  ✗ Impact must be 1-4.")
            _pause()
            return
    try:
        rows = data.list_interventions(
            student_id=sid, intervention_type=itype,
            subject_name=subj, status=status,
            lead_like=lead, impact_grade=impact,
        )
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_interventions(rows)
    _pause()


def per_student_flow() -> None:
    print("\n═══ Per-Student Interventions ═══")
    try:
        sid = _pick_student()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_interventions(data.list_interventions(student_id=sid))
    _pause()


def view_flow() -> None:
    print("\n═══ View Intervention ═══")
    try:
        iv = _pick_intervention()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_intervention_full(iv)
    _pause()


def _collect_iv_form(existing: Intervention | None
                       ) -> dict[str, Any]:
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
    payload["intervention_type"] = _pick_from(
        "Type", list(INTERVENTION_TYPES),
        default=(existing.intervention_type if is_edit
                  else DEFAULT_INTERVENTION_TYPE))
    if is_edit:
        payload["subject_name"] = _input(
            "Subject",
            default=existing.subject_name or "")
    else:
        payload["subject_name"] = _pick_subject()
    payload["lead_staff"] = _input(
        "Lead staff",
        default=(existing.lead_staff or "") if is_edit else "")
    payload["delivery_mode"] = _pick_from(
        "Delivery mode", [""] + list(DELIVERY_MODES),
        default=(existing.delivery_mode if is_edit
                  else DEFAULT_DELIVERY_MODE))
    payload["frequency"] = _pick_from(
        "Frequency", [""] + list(FREQUENCIES),
        default=(existing.frequency if is_edit
                  else DEFAULT_FREQUENCY))
    payload["location"] = _input(
        "Location",
        default=(existing.location or "") if is_edit else "")
    payload["start_date"] = _input(
        "Start date (YYYY-MM-DD)",
        default=(existing.start_date if is_edit
                  else _date.today().isoformat()))
    payload["end_date"] = _input(
        "End date (YYYY-MM-DD)",
        default=(existing.end_date or "") if is_edit else "")
    payload["sessions_planned"] = _input(
        "Sessions planned (optional)",
        default=(str(existing.sessions_planned)
                  if is_edit and existing.sessions_planned is not None
                  else ""))
    payload["status"] = _pick_from(
        "Status", list(STATUSES),
        default=(existing.status if is_edit else DEFAULT_STATUS))
    payload["referral_source"] = _input(
        "Referral source",
        default=(existing.referral_source or "")
        if is_edit else "")
    payload["funding_source"] = _input(
        "Funding source",
        default=(existing.funding_source or "")
        if is_edit else "")
    try:
        payload["rationale"] = _multiline(
            "Rationale",
            default=(existing.rationale or "") if is_edit else "")
        payload["success_criteria"] = _multiline(
            "Success criteria",
            default=(existing.success_criteria or "")
            if is_edit else "")
        payload["baseline_indicator"] = _multiline(
            "Baseline indicator (e.g. mock = D, attendance 78%)",
            default=(existing.baseline_indicator or "")
            if is_edit else "")
    except _UserAbort:
        raise
    payload["exit_indicator"] = _input(
        "Exit indicator (optional)",
        default=(existing.exit_indicator or "")
        if is_edit else "")
    payload["impact_grade"] = _input(
        "Impact grade (1-4, optional)",
        default=(str(existing.impact_grade)
                  if is_edit and existing.impact_grade is not None
                  else ""))
    payload["impact_summary"] = _input(
        "Impact summary",
        default=(existing.impact_summary or "")
        if is_edit else "")
    payload["notes"] = _input(
        "Notes",
        default=(existing.notes or "") if is_edit else "")
    return payload


def new_intervention() -> None:
    print("\n═══ New Intervention ═══")
    try:
        payload = _collect_iv_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        iv = data.create_intervention(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created intervention #{iv.intervention_id}")
    _pause()


def edit_intervention() -> None:
    print("\n═══ Edit Intervention ═══")
    try:
        iv = _pick_intervention()
        payload = _collect_iv_form(iv)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_intervention(iv.intervention_id, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated #{iv.intervention_id}")
    _pause()


def complete_flow() -> None:
    print("\n═══ Complete Intervention ═══")
    try:
        iv = _pick_intervention()
        exit_ind = _input(
            "Exit indicator",
            default=iv.exit_indicator or "")
        impact_raw = _input(
            "Impact grade (1-4)",
            default=(str(iv.impact_grade)
                      if iv.impact_grade is not None else ""))
        summary = _multiline(
            "Impact summary",
            default=iv.impact_summary or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    impact: int | None = None
    if impact_raw:
        try:
            impact = int(impact_raw)
        except ValueError:
            print("  ✗ Impact must be 1-4.")
            _pause()
            return
    try:
        data.complete_intervention(
            iv.intervention_id,
            exit_indicator=exit_ind or None,
            impact_grade=impact,
            impact_summary=summary or None,
        )
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{iv.intervention_id} → Completed")
    _pause()


def set_status_flow() -> None:
    print("\n═══ Change Status ═══")
    try:
        iv = _pick_intervention()
        new_status = _pick_from("New status", list(STATUSES),
                                  default=iv.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_status(iv.intervention_id, new_status)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{iv.intervention_id} → {new_status}")
    _pause()


def delete_intervention_flow() -> None:
    print("\n═══ Delete Intervention ═══")
    try:
        iv = _pick_intervention()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete intervention #{iv.intervention_id}? "
              "Sessions go too. Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_intervention(iv.intervention_id):
        print(f"\n  ✓ Deleted #{iv.intervention_id}")
    _pause()


# ── Session flows ─────────────────────────────────────────────────

def log_session_flow() -> None:
    print("\n═══ Log Session ═══")
    try:
        iv = _pick_intervention()
        date_str = _input("Session date",
                            default=_date.today().isoformat())
        duration = _input("Duration (mins)", default="45")
        status = _pick_from("Status", list(SESSION_STATUSES),
                              default=DEFAULT_SESSION_STATUS)
        delivered = _input("Delivered by",
                              default=iv.lead_staff or "")
        topic = _input("Topic")
        notes = _input("Notes")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        s = data.log_session(
            iv.intervention_id,
            session_date=date_str,
            duration_minutes=int(duration) if duration else None,
            status=status,
            delivered_by=delivered or None,
            topic=topic or None,
            notes=notes or None,
        )
    except (ValueError, ValidationError) as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Logged session #{s.session_id}")
    _pause()


def list_sessions_flow() -> None:
    print("\n═══ Sessions for Intervention ═══")
    try:
        iv = _pick_intervention()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = data.list_sessions(intervention_id=iv.intervention_id)
    if not rows:
        print("\n  (no sessions)")
    else:
        print()
        print(f"  {'#':>4}  {'Date':<10}  {'Status':<12}  "
              f"{'Mins':<6}  {'Delivered by':<18}  Topic")
        for s in rows:
            mins = (str(s.duration_minutes)
                    if s.duration_minutes is not None else "—")
            print(f"  {s.session_id:>4}  {s.session_date:<10}  "
                  f"{s.status:<12}  {mins:<6}  "
                  f"{(s.delivered_by or '—')[:18]:<18}  "
                  f"{s.topic or '—'}")
    _pause()


def edit_session_flow() -> None:
    print("\n═══ Edit Session ═══")
    try:
        iv = _pick_intervention()
        s = _pick_session(iv.intervention_id)
        date_str = _input("Date", default=s.session_date,
                            allow_empty=False)
        duration = _input(
            "Duration (mins)",
            default=(str(s.duration_minutes)
                      if s.duration_minutes is not None else ""))
        status = _pick_from("Status", list(SESSION_STATUSES),
                              default=s.status)
        delivered = _input("Delivered by",
                              default=s.delivered_by or "")
        topic = _input("Topic", default=s.topic or "")
        notes = _input("Notes", default=s.notes or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_session(s.session_id, {
            "session_date": date_str,
            "duration_minutes": int(duration) if duration else None,
            "status": status,
            "delivered_by": delivered or None,
            "topic": topic or None,
            "notes": notes or None,
        })
    except (ValueError, ValidationError) as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated #{s.session_id}")
    _pause()


def set_session_status_flow() -> None:
    print("\n═══ Change Session Status ═══")
    try:
        iv = _pick_intervention()
        s = _pick_session(iv.intervention_id)
        new_status = _pick_from(
            "New status", list(SESSION_STATUSES),
            default=s.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_session_status(s.session_id, new_status)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{s.session_id} → {new_status}")
    _pause()


def delete_session_flow() -> None:
    print("\n═══ Delete Session ═══")
    try:
        iv = _pick_intervention()
        s = _pick_session(iv.intervention_id)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete session #{s.session_id}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_session(s.session_id):
        print(f"\n  ✓ Deleted #{s.session_id}")
    _pause()


def summary_flow() -> None:
    print("\n═══ Intervention Tracking Summary ═══")
    summ = data.summary()
    print(f"\n  Total interventions  : {summ.total}")
    print(f"  Open                 : {summ.open_count}")
    print(f"  Distinct students    : {summ.distinct_students}")
    print(f"  Total sessions       : {summ.total_sessions}")
    print(f"  Attended sessions    : {summ.attended_sessions}")
    print(f"  Total minutes        : {summ.total_minutes}")
    print(f"  Average impact grade : "
          f"{summ.average_impact if summ.average_impact is not None else '—'}")
    print("\n  By status:")
    for s in STATUSES:
        n = summ.by_status.get(s, 0)
        if n:
            print(f"    {s:<14} : {n}")
    print("\n  By type:")
    for t in INTERVENTION_TYPES:
        n = summ.by_type.get(t, 0)
        if n:
            print(f"    {t:<22} : {n}")
    print("\n  By impact grade:")
    for g in IMPACT_GRADES:
        n = summ.by_impact.get(g, 0)
        if n:
            print(f"    {g}  {impact_label(g):<20} : {n}")
    _pause()


# ── Submenu ───────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List all",                list_all),
    ("List open",               list_open),
    ("Filter",                  filter_flow),
    ("Per-student",             per_student_flow),
    ("View intervention",       view_flow),
    ("New intervention",        new_intervention),
    ("Edit intervention",       edit_intervention),
    ("Complete (with impact)",  complete_flow),
    ("Change status",           set_status_flow),
    ("Delete intervention",     delete_intervention_flow),
    ("─" * 6,                   lambda: None),
    ("Log session",             log_session_flow),
    ("List sessions",           list_sessions_flow),
    ("Edit session",            edit_session_flow),
    ("Change session status",   set_session_status_flow),
    ("Delete session",          delete_session_flow),
    ("─" * 6,                   lambda: None),
    ("Summary",                 summary_flow),
]


def run() -> None:
    while True:
        print("\n── Intervention Tracking ──")
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
            logger.exception("Intervention-tracking CLI crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Intervention Tracking":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Intervention-tracking CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
