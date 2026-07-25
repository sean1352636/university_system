"""CLI flows for Sixth Form Bulk Operations."""

from __future__ import annotations

import json
import logging
from datetime import date as _date
from typing import Any, Callable
from education_system.systems.sixth_form.domain.learners.bulk_operations import (
    bulk_operations as data,
)
from education_system.systems.sixth_form.domain.learners.students import (
    students as student_data,
)
from education_system.systems.sixth_form.domain.learners.bulk_operations.bulk_operations import (
    BulkResult,
    Job,
    OPERATIONS,
    SAFE_STUDENT_FIELDS,
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


def _yes_no(prompt: str, *, default: bool = False) -> bool:
    raw = _input(f"{prompt} (y/n)",
                  default="y" if default else "n").strip().lower()
    return raw in ("y", "yes")


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


def _pick_students() -> list[str]:
    """Multi-select student picker. Accepts comma-separated numeric
    picks or student-id tokens, or 'all' to take everyone."""
    rows = student_data.list_students()
    if not rows:
        print("    No students.")
        raise _UserAbort
    print("\n  Students:")
    for i, s in enumerate(rows, 1):
        print(f"    {i:>3}) {s.student_id}  {s.full_name}")
    print("        (enter comma-separated numbers / IDs, "
          "or 'all')")
    while True:
        raw = _input("  Pick", allow_empty=False)
        if raw.lower() == "all":
            return [s.student_id for s in rows]
        tokens = [t.strip() for t in raw.replace(" ", ",").split(",")
                   if t.strip()]
        out: list[str] = []
        ok = True
        for t in tokens:
            if t.isdigit():
                n = int(t)
                if 1 <= n <= len(rows):
                    out.append(rows[n - 1].student_id)
                else:
                    print(f"    Out of range: {t}")
                    ok = False
                    break
            else:
                match = next((s for s in rows
                                if s.student_id.lower() == t.lower()), None)
                if match:
                    out.append(match.student_id)
                else:
                    print(f"    Unknown student: {t!r}")
                    ok = False
                    break
        if not ok:
            continue
        # De-dup, preserve order
        seen: set[str] = set()
        deduped = []
        for sid in out:
            if sid not in seen:
                deduped.append(sid)
                seen.add(sid)
        if not deduped:
            print("    No valid picks.")
            continue
        return deduped


# ── Result/Job printers ────────────────────────────────────────────

def _print_result(r: BulkResult, *, dry_run: bool = False) -> None:
    label = "Preview" if dry_run else "Result"
    print(f"\n  ── {label}: {r.operation} ──")
    print(f"    Targets   : {r.target_count}")
    print(f"    Successes : {r.success_count}")
    print(f"    Failures  : {r.failure_count}")
    if r.job_id:
        print(f"    Job id    : #{r.job_id}")
    # Show per-target diff/preview content if the op surfaced any.
    if r.success_ids:
        print("    Detail (first 20):")
        for tag in r.success_ids[:20]:
            print(f"      · {tag}")
        if len(r.success_ids) > 20:
            print(f"      ... +{len(r.success_ids) - 20} more.")
    elif dry_run and r.target_count and not r.failures:
        print(f"    Would touch {r.target_count} target(s).")
    if r.failures:
        print("    Failures:")
        for sid, reason in r.failures[:20]:
            print(f"      - {sid}: {reason}")
        if len(r.failures) > 20:
            print(f"      ... and {len(r.failures) - 20} more.")
    _pause()


def _print_jobs(rows: list[Job]) -> None:
    if not rows:
        print("\n  (no bulk jobs yet)")
        return
    print()
    print(f"  {'#':>5}  {'When':<19}  {'Operation':<18}  "
          f"{'Targets':>8}  {'OK':>5}  {'Fail':>5}  Summary")
    print("  " + "-" * 110)
    for j in rows:
        print(f"  {j.job_id:>5}  {j.ran_at[:19]:<19}  "
              f"{j.operation:<18}  {j.target_count:>8}  "
              f"{j.success_count:>5}  {j.failure_count:>5}  "
              f"{j.summary[:60]}")
    print(f"\n  {len(rows)} job(s).")


# ── Operation flows ────────────────────────────────────────────────

def bulk_behaviour() -> None:
    print("\n═══ Bulk Log Behaviour ═══")
    try:
        sids = _pick_students()
        entry_type = _pick_from("Entry type", ["Positive", "Negative"],
                                  default="Positive")
        category = _input("Category", allow_empty=False)
        description = _input("Description", allow_empty=False)
        date_str = _input("Date (YYYY-MM-DD)",
                            default=_date.today().isoformat())
        severity = _input("Severity (Low/Medium/High; optional)") or None
        points_raw = _input("Points", default="0")
        location = _input("Location") or None
        recorded_by = _input("Recorded by") or None
        action = _input("Action taken") or None
        follow_up = _yes_no("Follow-up required?", default=False)
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        points = int(points_raw or 0)
    except ValueError:
        print("  ✗ Points must be a number.")
        _pause()
        return
    try:
        r = data.bulk_log_behaviour(
            sids, entry_date=date_str, entry_type=entry_type,
            category=category, description=description,
            severity=severity, points=points, location=location,
            recorded_by=recorded_by, action_taken=action,
            follow_up_required=follow_up, dry_run=dry,
        )
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_accommodation() -> None:
    print("\n═══ Bulk Add Accommodation ═══")
    try:
        sids = _pick_students()
        name = _input("Accommodation name", allow_empty=False)
        category = _input("Category", default="Exam Access")
        description = _input("Description") or None
        status = _input("Status", default="Active")
        start_date = _input("Start date (YYYY-MM-DD)",
                              default=_date.today().isoformat())
        end_date = _input("End date") or None
        approved_by = _input("Approved by") or None
        approved_date = _input("Approved date") or None
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = data.bulk_add_accommodation(
            sids, name=name, category=category, description=description,
            status=status, start_date=start_date, end_date=end_date,
            approved_by=approved_by, approved_date=approved_date,
            dry_run=dry,
        )
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_update_field() -> None:
    print("\n═══ Bulk Update Student Field ═══")
    try:
        sids = _pick_students()
        field = _pick_from("Field", list(SAFE_STUDENT_FIELDS))
        value = _input(f"New value for {field}")
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = data.bulk_update_student(
            sids, field=field, value=value or None, dry_run=dry,
        )
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_message_flow() -> None:
    print("\n═══ Bulk Message Students ═══")
    try:
        sids = _pick_students()
        subject = _input("Subject", allow_empty=False)
        body = _input("Body", allow_empty=False)
        channel = _pick_from("Channel", ["Email", "SMS", "Letter",
                                            "Phone Call", "In Person",
                                            "System"],
                                default="Email")
        category = _input("Category", default="General")
        priority = _pick_from("Priority", ["Low", "Normal", "High",
                                              "Urgent"],
                                default="Normal")
        status = _pick_from("Status", ["Draft", "Queued", "Sent"],
                              default="Sent")
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = data.bulk_message(
            sids, subject=subject, body=body, channel=channel,
            category=category, priority=priority, status=status,
            dry_run=dry,
        )
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_archive_flow() -> None:
    print("\n═══ Bulk Archive Students → Alumni ═══")
    try:
        sids = _pick_students()
        year = _input("Leaving year (YYYY)",
                       default=str(_date.today().year))
        date_str = _input("Leaving date (YYYY-MM-DD)",
                            default=_date.today().isoformat())
        from education_system.systems.sixth_form.domain.learners.alumni.alumni import (
            DESTINATION_TYPES, LEAVING_REASONS, DEFAULT_DESTINATION,
            DEFAULT_LEAVING_REASON,
        )
        reason = _pick_from("Leaving reason", list(LEAVING_REASONS),
                              default=DEFAULT_LEAVING_REASON)
        dest = _pick_from("Destination", list(DESTINATION_TYPES),
                            default=DEFAULT_DESTINATION)
        delete = _yes_no(
            "Also delete the student rows? "
            "(history/links cascade-remove)", default=False)
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if not dry and delete and not _yes_no(
            f"This will DELETE {len(sids)} student row(s). Continue?",
            default=False):
        print("\n  Cancelled.")
        return
    try:
        r = data.bulk_archive_to_alumni(
            sids, leaving_year=year, leaving_date=date_str,
            leaving_reason=reason, destination_type=dest,
            delete_students=delete, dry_run=dry,
        )
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


# ── Attendance bulk flows ──────────────────────────────────────────

def _pick_slot() -> int:
    from education_system.systems.sixth_form.domain.academics.timetable import (
        timetable as _tt,
    )
    slots = _tt.list_slots()
    if not slots:
        print("    No timetable slots.")
        raise _UserAbort
    print("\n  Slots:")
    for i, s in enumerate(slots, 1):
        day = _tt.day_name(s.day)
        print(f"    {i:>3}) #{s.slot_id}  {day} P{s.period}  "
              f"group={s.group_id}  room={s.room or '—'}")
    while True:
        raw = _input("  Pick slot #", allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(slots):
                return slots[n - 1].slot_id
        print("    Out of range.")


def _pick_slots() -> list[int]:
    from education_system.systems.sixth_form.domain.academics.timetable import (
        timetable as _tt,
    )
    slots = _tt.list_slots()
    if not slots:
        print("    No timetable slots.")
        raise _UserAbort
    print("\n  Slots:")
    for i, s in enumerate(slots, 1):
        day = _tt.day_name(s.day)
        print(f"    {i:>3}) #{s.slot_id}  {day} P{s.period}  "
              f"group={s.group_id}  room={s.room or '—'}")
    print("        (comma-separated numbers, or 'all')")
    while True:
        raw = _input("  Pick", allow_empty=False)
        if raw.lower() == "all":
            return [s.slot_id for s in slots]
        toks = [t.strip() for t in raw.replace(" ", ",").split(",") if t.strip()]
        out: list[int] = []
        ok = True
        for t in toks:
            if not t.isdigit():
                ok = False
                print(f"    Not a number: {t}")
                break
            n = int(t)
            if not (1 <= n <= len(slots)):
                ok = False
                print(f"    Out of range: {t}")
                break
            out.append(slots[n - 1].slot_id)
        if ok and out:
            return list(dict.fromkeys(out))


def bulk_mark_attendance_flow() -> None:
    print("\n═══ Bulk Mark Attendance ═══")
    try:
        slot_id = _pick_slot()
        sids = _pick_students()
        date_str = _input("Date (YYYY-MM-DD)",
                           default=_date.today().isoformat())
        status = _pick_from("Status",
                             ["Present", "Late", "Absent", "Authorised"],
                             default="Present")
        minutes_raw = _input("Minutes late (blank for none)") or ""
        notes = _input("Notes") or None
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    minutes = None
    if minutes_raw:
        try:
            minutes = int(minutes_raw)
        except ValueError:
            print("  ✗ Minutes must be a number.")
            _pause()
            return
    try:
        r = data.bulk_mark_attendance(
            sids, slot_id=slot_id, date=date_str, status=status,
            minutes_late=minutes, notes=notes, dry_run=dry,
        )
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_authorise_flow() -> None:
    print("\n═══ Bulk Authorise / Unauthorise Absences ═══")
    try:
        sids = _pick_students()
        date_from = _input("From date (YYYY-MM-DD)", allow_empty=False)
        date_to = _input("To date (YYYY-MM-DD)",
                          default=_date.today().isoformat())
        target = _pick_from("Target status",
                              ["Authorised", "Absent"],
                              default="Authorised")
        reason = _input("Reason / code (optional)") or None
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = data.bulk_authorise_absences(
            sids, date_from=date_from, date_to=date_to,
            target_status=target, reason=reason, dry_run=dry,
        )
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_lateness_flow() -> None:
    print("\n═══ Bulk Apply Lateness ═══")
    try:
        slot_id = _pick_slot()
        sids = _pick_students()
        date_str = _input("Date (YYYY-MM-DD)",
                           default=_date.today().isoformat())
        minutes = int(_input("Minutes late", default="5"))
        threshold_raw = _input(
            "Auto-log behaviour when minutes ≥ (blank = off)") or ""
        recorded_by = _input("Behaviour recorded-by (optional)") or None
        dry = _yes_no("Preview (dry run)?", default=False)
    except (_UserAbort, ValueError):
        print("\n  Cancelled / bad input.")
        return
    threshold = None
    if threshold_raw:
        try:
            threshold = int(threshold_raw)
        except ValueError:
            print("  ✗ Threshold must be a number.")
            _pause()
            return
    try:
        r = data.bulk_apply_lateness(
            sids, slot_id=slot_id, date=date_str, minutes_late=minutes,
            auto_log_behaviour_over=threshold,
            behaviour_recorded_by=recorded_by, dry_run=dry,
        )
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_import_csv_flow() -> None:
    print("\n═══ Bulk Import Attendance CSV ═══")
    print("  Required columns: student_id, slot_id, date, status")
    print("  Optional columns: minutes_late, notes")
    try:
        path = _input("CSV path", allow_empty=False)
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = data.bulk_import_attendance_csv(path, dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_recalc_flow() -> None:
    print("\n═══ Bulk Recalculate Attendance % ═══")
    try:
        sids = _pick_students()
        date_from = _input("From date (blank = all)") or None
        date_to = _input("To date (blank = all)") or None
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = data.bulk_recalc_attendance(
            sids, date_from=date_from, date_to=date_to, dry_run=dry,
        )
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    if not dry and r.success_ids:
        print("\n  Per-student attendance:")
        for tag in r.success_ids[:40]:
            print(f"    {tag}")
        if len(r.success_ids) > 40:
            print(f"    ... +{len(r.success_ids) - 40} more")
    _print_result(r, dry_run=dry)


def bulk_flag_low_attendance_flow() -> None:
    print("\n═══ Bulk Flag Students Under Attendance Threshold ═══")
    try:
        sids = _pick_students()
        threshold = float(_input("Threshold %", default="90"))
        window = int(_input("Window (days)", default="28"))
        level = _pick_from("Level",
                             ["Low", "Medium", "High", "Critical"],
                             default="Medium")
        reason = _input("Reason", default="Low overall attendance")
        raised_by = _input("Raised by (optional)") or None
        skip_open = _yes_no(
            "Skip students who already have an open concern?",
            default=True)
        dry = _yes_no("Preview (dry run)?", default=False)
    except (_UserAbort, ValueError):
        print("\n  Cancelled / bad input.")
        return
    try:
        r = data.bulk_flag_low_attendance(
            sids, threshold_pct=threshold, window_days=window,
            level=level, reason=reason, raised_by=raised_by,
            skip_if_open_concern=skip_open, dry_run=dry,
        )
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_signoff_flow() -> None:
    print("\n═══ Bulk Close-of-Day Register Sign-Off ═══")
    try:
        slot_ids = _pick_slots()
        date_str = _input("Date (YYYY-MM-DD)",
                           default=_date.today().isoformat())
        default_status = _pick_from("Fill blanks as",
                                       ["Present", "Absent", "Authorised"],
                                       default="Present")
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = data.bulk_signoff_register(
            slot_ids, date=date_str, default_status=default_status,
            dry_run=dry,
        )
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


# ── Academic / pastoral bulk flows ─────────────────────────────────

def _pick_group() -> int | None:
    from education_system.systems.sixth_form.domain.academics.class_groups import (
        class_groups as _cg,
    )
    groups = _cg.list_groups()
    if not groups:
        print("    No class groups.")
        return None
    print("\n  Class groups:")
    for i, g in enumerate(groups, 1):
        print(f"    {i:>3}) #{g.group_id}  {g.group_name}  "
              f"({getattr(g, 'subject_name', '—') or '—'})")
    raw = _input("  Pick # (blank to skip)") or ""
    if not raw:
        return None
    if not raw.isdigit():
        print("    Not a number.")
        return None
    n = int(raw)
    if not (1 <= n <= len(groups)):
        print("    Out of range.")
        return None
    return groups[n - 1].group_id


def _pick_subject() -> str:
    from education_system.systems.sixth_form.domain.academics.subjects import (
        subjects as _sub,
    )
    names = _sub.get_active_names()
    if not names:
        return _input("Subject", allow_empty=False)
    return _pick_from("Subject", names, default=names[0])


def bulk_enrol_flow() -> None:
    print("\n═══ Bulk Enrol Students ═══")
    try:
        sids = _pick_students()
        year = _input("Academic year (e.g. 2025/26)", allow_empty=False)
        yg = _pick_from("Year group", ["12", "13"], default="12")
        tutor = _input("Tutor group") or None
        start = _input("Start date",
                         default=_date.today().isoformat())
        status = _pick_from("Status",
                              ["Enrolled", "Pending",
                                "Withdrawn", "Completed"],
                              default="Enrolled")
        notes = _input("Notes") or None
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = data.bulk_enrol(sids, academic_year=year, year_group=int(yg),
                             tutor_group=tutor, start_date=start,
                             status=status, notes=notes, dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_move_group_flow() -> None:
    print("\n═══ Bulk Move Class Group ═══")
    try:
        sids = _pick_students()
        print("  From-group (blank to skip removal):")
        from_id = _pick_group()
        print("  To-group (blank to skip add):")
        to_id = _pick_group()
        if from_id is None and to_id is None:
            print("  ✗ Pick at least one group.")
            _pause()
            return
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = data.bulk_move_class_group(
            sids, from_group_id=from_id, to_group_id=to_id, dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_predicted_grades_flow() -> None:
    print("\n═══ Bulk Assign Predicted Grades ═══")
    try:
        sids = _pick_students()
        subject = _pick_subject()
        from_baseline = _yes_no("Derive from baseline?", default=False)
        grade = None
        if not from_baseline:
            grade = _pick_from("Grade",
                                 ["A*", "A", "B", "C", "D", "E", "U"],
                                 default="C")
        confidence = _pick_from("Confidence",
                                   ["High", "Medium", "Low"],
                                   default="Medium")
        by = _input("Predicted by") or None
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = data.bulk_assign_predicted_grades(
            sids, subject=subject, grade=grade,
            from_baseline=from_baseline, confidence=confidence,
            predicted_by=by, dry_run=dry,
        )
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_import_marks_flow() -> None:
    print("\n═══ Bulk Import Assessment Marks ═══")
    print("  Required: student_id, subject_name, assessment_type,")
    print("            assessment_date, raw_score, max_score")
    print("  Optional: percentage, baseline_grade, confidence,")
    print("            assessor, notes, is_primary")
    try:
        path = _input("CSV path", allow_empty=False)
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = data.bulk_import_assessment_marks(path, dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_recalc_grades_flow() -> None:
    print("\n═══ Bulk Recalculate Grade Reports ═══")
    try:
        sids = _pick_students()
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = data.bulk_recalc_grade_reports(sids, dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_export_progress_flow() -> None:
    print("\n═══ Bulk Export Progress Reports ═══")
    try:
        sids = _pick_students()
        out_dir = _input("Output directory", allow_empty=False)
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = data.bulk_export_progress_reports(
            sids, output_dir=out_dir, dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_publish_reports_flow() -> None:
    print("\n═══ Bulk Publish / Unpublish Report Cards ═══")
    try:
        sids = _pick_students()
        period = _input("Period (e.g. 2025/26 T1)", allow_empty=False)
        publish = _yes_no("Publish? (No = unpublish)", default=True)
        by = _input("Published by") or None
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = data.bulk_publish_report_cards(
            sids, period=period, publish=publish,
            published_by=by, dry_run=dry,
        )
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_grade_boundaries_flow() -> None:
    print("\n═══ Bulk Apply Grade Boundaries ═══")
    try:
        raw = _input("Assignment ids (comma-separated)",
                       allow_empty=False)
        ids = [int(t) for t in raw.replace(" ", ",").split(",") if t]
        a_star = _input("A* threshold") or ""
        a = _input("A threshold") or ""
        b = _input("B threshold") or ""
        c = _input("C threshold") or ""
        d = _input("D threshold") or ""
        e_ = _input("E threshold") or ""
        dry = _yes_no("Preview (dry run)?", default=False)
    except (_UserAbort, ValueError):
        print("\n  Cancelled / bad input.")
        return
    def _n(s: str) -> int | None:
        return int(s) if s else None
    try:
        r = data.bulk_apply_grade_boundaries(
            ids, a_star=_n(a_star), a=_n(a), b=_n(b),
            c=_n(c), d=_n(d), e=_n(e_), dry_run=dry,
        )
    except ValidationError as ve:
        print(f"\n  ✗ {ve}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_detention_flow() -> None:
    print("\n═══ Bulk Issue Detentions ═══")
    try:
        sids = _pick_students()
        date_str = _input("Date", default=_date.today().isoformat())
        reason = _input("Reason", allow_empty=False)
        duration = int(_input("Duration (minutes)", default="30"))
        room = _input("Room") or None
        severity = _pick_from("Severity",
                                ["Low", "Medium", "High"],
                                default="Low")
        by = _input("Recorded by") or None
        dry = _yes_no("Preview (dry run)?", default=False)
    except (_UserAbort, ValueError):
        print("\n  Cancelled / bad input.")
        return
    try:
        r = data.bulk_issue_detentions(
            sids, date=date_str, reason=reason,
            duration_minutes=duration, room=room,
            severity=severity, recorded_by=by, dry_run=dry,
        )
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_merits_flow() -> None:
    print("\n═══ Bulk Award Merits / House Points ═══")
    try:
        sids = _pick_students()
        date_str = _input("Date", default=_date.today().isoformat())
        category = _pick_from(
            "Category",
            ["Excellent Work", "Participation", "Helpfulness",
             "Leadership", "Improvement", "Achievement",
             "Attendance", "Effort", "Community Contribution",
             "Other"], default="Achievement")
        description = _input("Description", allow_empty=False)
        points = int(_input("Points", default="5"))
        by = _input("Recorded by") or None
        dry = _yes_no("Preview (dry run)?", default=False)
    except (_UserAbort, ValueError):
        print("\n  Cancelled / bad input.")
        return
    try:
        r = data.bulk_award_merits(
            sids, date=date_str, category=category,
            description=description, points=points,
            recorded_by=by, dry_run=dry,
        )
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_escalate_flow() -> None:
    print("\n═══ Bulk Escalate Behaviour ═══")
    try:
        sids = _pick_students()
        date_str = _input("Date", default=_date.today().isoformat())
        reason = _input("Reason", allow_empty=False)
        to = _input("Escalate to", default="Senior Tutor")
        follow_up = _input("Follow-up date") or None
        by = _input("Recorded by") or None
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = data.bulk_escalate_behaviour(
            sids, date=date_str, reason=reason,
            escalate_to=to, follow_up_date=follow_up,
            recorded_by=by, dry_run=dry,
        )
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_safeguarding_flow() -> None:
    print("\n═══ Bulk Safeguarding Flag ═══")
    try:
        from education_system.systems.sixth_form.domain.safeguarding.safeguarding import (
            CONCERN_TYPES, CATEGORIES, RISK_LEVELS,
        )
        sids = _pick_students()
        cdate = _input("Concern date",
                         default=_date.today().isoformat())
        rdate = _input("Reported date",
                         default=_date.today().isoformat())
        ctype = _pick_from("Concern type", list(CONCERN_TYPES),
                              default=CONCERN_TYPES[0])
        cat = _pick_from("Category", list(CATEGORIES),
                            default=CATEGORIES[0])
        risk = _pick_from("Risk level", list(RISK_LEVELS),
                              default="Medium")
        by = _input("Reported by", allow_empty=False)
        desc = _input("Description", allow_empty=False)
        dsl = _yes_no("DSL notified?", default=False)
        dsl_name = _input("DSL name") or None if dsl else None
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = data.bulk_safeguarding_flag(
            sids, concern_date=cdate, reported_date=rdate,
            concern_type=ctype, category=cat, risk_level=risk,
            reported_by=by, description=desc,
            dsl_notified=dsl, dsl_name=dsl_name, dry_run=dry,
        )
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_mentors_flow() -> None:
    print("\n═══ Bulk Assign Mentors ═══")
    try:
        from education_system.systems.sixth_form.domain.pastoral.peer_mentoring.peer_mentoring import (
            PROGRAMMES, FREQUENCIES, DEFAULT_FREQUENCY,
        )
        mentor_id = _input("Mentor student id", allow_empty=False)
        print("  Pick mentees:")
        mentees = _pick_students()
        programme = _pick_from("Programme", list(PROGRAMMES),
                                  default=PROGRAMMES[0])
        start = _input("Start date",
                         default=_date.today().isoformat())
        frequency = _pick_from("Frequency", list(FREQUENCIES),
                                  default=DEFAULT_FREQUENCY)
        coord = _input("Coordinator") or None
        planned_end = _input("Planned end") or None
        sessions_raw = _input("Sessions planned") or ""
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    sessions = None
    if sessions_raw:
        try:
            sessions = int(sessions_raw)
        except ValueError:
            print("  ✗ Sessions planned must be a number.")
            _pause()
            return
    try:
        r = data.bulk_assign_mentors(
            mentees, mentor_id=mentor_id, programme=programme,
            start_date=start, frequency=frequency,
            coordinator=coord, planned_end=planned_end,
            sessions_planned=sessions, dry_run=dry,
        )
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


# ── Communications / finance / exams flows ─────────────────────────

def bulk_reset_points_flow() -> None:
    print("\n═══ Bulk Reset Behaviour Points ═══")
    try:
        sids = _pick_students()
        df = _input("Window from (YYYY-MM-DD)", allow_empty=False)
        dt = _input("Window to (YYYY-MM-DD)",
                       default=_date.today().isoformat())
        reset_date = _input("Reset date",
                               default=_date.today().isoformat())
        note = _input("Note", default="Term reset")
        by = _input("Recorded by") or None
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = data.bulk_reset_behaviour_points(
            sids, date_from=df, date_to=dt, reset_date=reset_date,
            note=note, recorded_by=by, dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_sms_flow() -> None:
    print("\n═══ Bulk SMS ═══")
    try:
        sids = _pick_students()
        body = _input("Body", allow_empty=False)
        subject = _input("Subject (audit)", default="SMS")
        sender = _input("Sender staff id") or None
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = data.bulk_send_sms(sids, body=body, subject=subject,
                                 sender_staff_id=sender, dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_letters_flow() -> None:
    print("\n═══ Bulk Send Templated Letters ═══")
    from education_system.systems.sixth_form.domain.operations.communications.letter_templates import (
        letter_templates as _lt,
    )
    templates = _lt.list_templates()
    if not templates:
        print("  No letter templates available.")
        _pause()
        return
    print("\n  Templates:")
    for i, t in enumerate(templates, 1):
        print(f"    {i:>3}) #{t.template_id}  {t.name}")
    try:
        raw = _input("Pick #", allow_empty=False)
        if not raw.isdigit() or not (1 <= int(raw) <= len(templates)):
            print("  Bad pick.")
            _pause()
            return
        tmpl = templates[int(raw) - 1]
        sids = _pick_students()
        ctx_raw = _input(
            "Extra context (k=v, comma-separated; optional)") or ""
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    ctx: dict[str, str] = {}
    for pair in ctx_raw.split(","):
        if "=" in pair:
            k, v = pair.split("=", 1)
            ctx[k.strip()] = v.strip()
    try:
        r = data.bulk_send_letters(
            sids, template_id=tmpl.template_id,
            extra_context=ctx, dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_meeting_invites_flow() -> None:
    print("\n═══ Bulk Parents-Evening Invites ═══")
    from education_system.systems.sixth_form.domain.operations.communications.parents_evenings import (
        parents_evenings as _pe,
    )
    events = _pe.list_events()
    if not events:
        print("  No parents-evening events.")
        _pause()
        return
    print("\n  Events:")
    for i, e in enumerate(events, 1):
        print(f"    {i:>3}) #{e.event_id}  {e.event_date}  {e.title}")
    try:
        raw = _input("Pick #", allow_empty=False)
        if not raw.isdigit() or not (1 <= int(raw) <= len(events)):
            print("  Bad pick.")
            _pause()
            return
        ev = events[int(raw) - 1]
        sids = _pick_students()
        link = _input("Booking link (optional)") or None
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = data.bulk_meeting_invites(
            sids, event_id=ev.event_id,
            booking_link=link, dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_ucas_reminders_flow() -> None:
    print("\n═══ Bulk UCAS Reference Reminders ═══")
    try:
        sids = _pick_students()
        referee = _input("Override referee email (optional)") or None
        deadline = _input("Deadline (optional)") or None
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = data.bulk_ucas_reference_reminders(
            sids, referee_email=referee, deadline=deadline,
            dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_password_reset_flow() -> None:
    print("\n═══ Bulk Password / MFA Emails ═══")
    try:
        sids = _pick_students()
        mfa = _yes_no("MFA enrolment (instead of password reset)?",
                       default=False)
        url = _input("Reset URL (optional)") or None
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = data.bulk_password_reset_emails(
            sids, reset_url=url, mfa_enrolment=mfa, dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_schedule_msg_flow() -> None:
    print("\n═══ Bulk Schedule Message ═══")
    try:
        sids = _pick_students()
        subject = _input("Subject", allow_empty=False)
        body = _input("Body", allow_empty=False)
        send_at = _input("Send at (YYYY-MM-DD HH:MM)", allow_empty=False)
        channel = _pick_from("Channel",
                                ["Email", "SMS", "Letter", "Portal"],
                                default="Email")
        category = _input("Category", default="General")
        priority = _pick_from("Priority",
                                ["Low", "Normal", "High", "Urgent"],
                                default="Normal")
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = data.bulk_schedule_message(
            sids, subject=subject, body=body, send_at=send_at,
            channel=channel, category=category, priority=priority,
            dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_bursary_flow() -> None:
    print("\n═══ Bulk Bursary Award ═══")
    from education_system.systems.sixth_form.domain.finance.bursaries.bursaries import (
        BURSARY_TYPES, ELIGIBILITY_BASES, DEFAULT_TYPE,
    )
    try:
        sids = _pick_students()
        btype = _pick_from("Bursary type", list(BURSARY_TYPES),
                              default=DEFAULT_TYPE)
        amount = float(_input("Amount awarded (£)", allow_empty=False))
        year = _input("Academic year (e.g. 2025/26)") or None
        basis = _pick_from(
            "Eligibility basis", [""] + list(ELIGIBILITY_BASES),
            default="")
        note = _input("Decision note") or None
        by = _input("Assessed by") or None
        dry = _yes_no("Preview (dry run)?", default=False)
    except (_UserAbort, ValueError):
        print("\n  Cancelled / bad input.")
        return
    try:
        r = data.bulk_bursary_award(
            sids, bursary_type=btype, amount_awarded=amount,
            academic_year=year, eligibility_basis=basis or None,
            decision_note=note, assessed_by=by, dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_invoices_flow() -> None:
    print("\n═══ Bulk Raise Invoices ═══")
    from education_system.systems.sixth_form.domain.finance.fees.fees import (
        CATEGORIES, DEFAULT_CATEGORY,
    )
    try:
        sids = _pick_students()
        desc = _input("Description", allow_empty=False)
        cat = _pick_from("Category", list(CATEGORIES),
                            default=DEFAULT_CATEGORY)
        amount = float(_input("Amount (£)", allow_empty=False))
        issued = _input("Issued date",
                           default=_date.today().isoformat())
        due = _input("Due date (optional)") or None
        year = _input("Academic year (optional)") or None
        dry = _yes_no("Preview (dry run)?", default=False)
    except (_UserAbort, ValueError):
        print("\n  Cancelled / bad input.")
        return
    try:
        r = data.bulk_raise_invoices(
            sids, description=desc, category=cat, amount=amount,
            issued_date=issued, due_date=due, academic_year=year,
            dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_discount_flow() -> None:
    print("\n═══ Bulk Fee Discount / Waiver ═══")
    from education_system.systems.sixth_form.domain.finance.fees.fees import (
        CATEGORIES, DEFAULT_CATEGORY,
    )
    try:
        sids = _pick_students()
        desc = _input("Description", allow_empty=False)
        amount = float(_input("Discount amount (£, positive)",
                                 allow_empty=False))
        cat = _pick_from("Category", list(CATEGORIES),
                            default=DEFAULT_CATEGORY)
        issued = _input("Issued date",
                           default=_date.today().isoformat())
        year = _input("Academic year (optional)") or None
        dry = _yes_no("Preview (dry run)?", default=False)
    except (_UserAbort, ValueError):
        print("\n  Cancelled / bad input.")
        return
    try:
        r = data.bulk_fee_discount(
            sids, description=desc, amount=amount, category=cat,
            issued_date=issued, academic_year=year, dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_payments_csv_flow() -> None:
    print("\n═══ Bulk Import Payments CSV ═══")
    print("  Required: fee_id, amount, paid_on, method")
    print("  Optional: reference, notes")
    try:
        path = _input("CSV path", allow_empty=False)
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = data.bulk_import_payments(path, dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_statements_flow() -> None:
    print("\n═══ Bulk Financial Statements ═══")
    try:
        sids = _pick_students()
        out_dir = _input("Output directory", allow_empty=False)
        year = _input("Academic year filter (optional)") or None
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = data.bulk_financial_statements(
            sids, output_dir=out_dir, academic_year=year, dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_exam_entries_flow() -> None:
    print("\n═══ Bulk Exam Entries ═══")
    from education_system.systems.sixth_form.domain.assessment.exam_entries.exam_entries import (
        SEASONS, DEFAULT_SEASON, TIERS,
    )
    try:
        sids = _pick_students()
        subject = _pick_subject()
        board = _input("Exam board (e.g. AQA, OCR, Edexcel)",
                          allow_empty=False)
        code = _input("Paper code", allow_empty=False)
        season = _pick_from("Season", list(SEASONS),
                              default=DEFAULT_SEASON)
        year = int(_input("Year", default=str(_date.today().year)))
        tier_pick = _pick_from("Tier", [""] + list(TIERS), default="")
        fee_raw = _input("Fee (£, optional)") or ""
        prefix = _input("Candidate-no prefix (optional)") or None
        dry = _yes_no("Preview (dry run)?", default=False)
    except (_UserAbort, ValueError):
        print("\n  Cancelled / bad input.")
        return
    fee = float(fee_raw) if fee_raw else None
    try:
        r = data.bulk_exam_entries(
            sids, subject=subject, exam_board=board,
            paper_code=code, season=season, year=year,
            tier=tier_pick or None, fee=fee,
            candidate_no_prefix=prefix, dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_exam_access_flow() -> None:
    print("\n═══ Bulk Exam Access Arrangements ═══")
    try:
        sids = _pick_students()
        arrangement = _pick_from(
            "Arrangement",
            ["25% Extra Time", "50% Extra Time", "Scribe", "Reader",
             "Rest Breaks", "Word Processor", "Separate Room",
             "Prompter", "Other"], default="25% Extra Time")
        desc = _input("Description") or None
        start = _input("Start date",
                          default=_date.today().isoformat())
        end = _input("End date (optional)") or None
        by = _input("Approved by") or None
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = data.bulk_exam_access_arrangements(
            sids, arrangement=arrangement, description=desc,
            start_date=start, end_date=end, approved_by=by,
            dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_exam_timetables_flow() -> None:
    print("\n═══ Bulk Export Exam Timetables ═══")
    try:
        sids = _pick_students()
        out_dir = _input("Output directory", allow_empty=False)
        year_raw = _input("Year filter (optional)") or ""
        season = _input("Season filter (optional)") or None
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    year = int(year_raw) if year_raw else None
    try:
        r = data.bulk_export_exam_timetables(
            sids, output_dir=out_dir, year=year, season=season,
            dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


# ── Lifecycle / admin / meta flows ─────────────────────────────────

def bulk_ucas_export_flow() -> None:
    print("\n═══ Bulk UCAS Export Predictions ═══")
    try:
        sids = _pick_students()
        path = _input("Output CSV path", allow_empty=False)
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = data.bulk_ucas_export_predictions(
            sids, output_path=path, dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_ucas_status_flow() -> None:
    print("\n═══ Bulk Update UCAS Status ═══")
    from education_system.systems.sixth_form.domain.progression.ucas.ucas import (
        APP_STATUSES,
    )
    try:
        sids = _pick_students()
        status = _pick_from("Status", list(APP_STATUSES),
                              default=APP_STATUSES[0])
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = data.bulk_ucas_update_status(
            sids, status=status, dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_promote_flow() -> None:
    print("\n═══ Bulk Promote Year Group ═══")
    try:
        sids = _pick_students()
        year = _input("New academic year (e.g. 2026/27)",
                         allow_empty=False)
        bump = _yes_no("Bump year_group by +1?", default=True)
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = data.bulk_promote_year_group(
            sids, new_academic_year=year, bump_year_group=bump,
            dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_leavers_flow() -> None:
    print("\n═══ Bulk Mark Leavers ═══")
    try:
        sids = _pick_students()
        date_str = _input("Leaving date",
                            default=_date.today().isoformat())
        reason = _input("Leaving reason (optional)") or None
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = data.bulk_mark_leavers(
            sids, leaving_date=date_str, leaving_reason=reason,
            dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_reinstate_flow() -> None:
    print("\n═══ Bulk Reinstate Alumni ═══")
    try:
        raw = _input("Alumni ids (comma-separated)",
                       allow_empty=False)
        ids = [int(t) for t in raw.replace(" ", ",").split(",") if t]
        dry = _yes_no("Preview (dry run)?", default=False)
    except (_UserAbort, ValueError):
        print("\n  Cancelled / bad input.")
        return
    try:
        r = data.bulk_reinstate_alumni(ids, dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_gdpr_flow() -> None:
    print("\n═══ Bulk GDPR Redact ═══")
    try:
        sids = _pick_students()
        raw = _input("Fields to clear (comma; blank = defaults)") or ""
        fields = [f.strip() for f in raw.split(",") if f.strip()] or None
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = data.bulk_gdpr_redact(sids, fields=fields, dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_export_records_flow() -> None:
    print("\n═══ Bulk Export Student Records ═══")
    try:
        sids = _pick_students()
        path = _input("Output CSV path", allow_empty=False)
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = data.bulk_export_student_records(
            sids, output_path=path, dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_anonymise_flow() -> None:
    print("\n═══ Bulk Anonymise Alumni ═══")
    try:
        raw = _input("Alumni ids (comma-separated)",
                       allow_empty=False)
        ids = [int(t) for t in raw.replace(" ", ",").split(",") if t]
        dry = _yes_no("Preview (dry run)?", default=False)
    except (_UserAbort, ValueError):
        print("\n  Cancelled / bad input.")
        return
    try:
        r = data.bulk_anonymise_alumni(ids, dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_inventory_flow() -> None:
    print("\n═══ Bulk Assign Inventory ═══")
    try:
        sids = _pick_students()
        kind = _pick_from("Kind",
                            list(data.VALID_INVENTORY_KINDS),
                            default="Locker")
        start = int(_input("Starting number", default="1"))
        prefix = _input("Prefix (optional)") or ""
        pad = int(_input("Zero-pad digits", default="4"))
        by = _input("Assigned by") or None
        dry = _yes_no("Preview (dry run)?", default=False)
    except (_UserAbort, ValueError):
        print("\n  Cancelled / bad input.")
        return
    try:
        r = data.bulk_assign_inventory(
            sids, kind=kind, starting_number=start, prefix=prefix,
            pad=pad, assigned_by=by, dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_photos_flow() -> None:
    print("\n═══ Bulk Upload Photos ═══")
    try:
        zip_path = _input("ZIP path", allow_empty=False)
        out_dir = _input("Output directory", allow_empty=False)
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = data.bulk_upload_photos(
            zip_path, output_dir=out_dir, dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_contacts_csv_flow() -> None:
    print("\n═══ Bulk Import Emergency Contacts CSV ═══")
    print("  Required: student_id")
    print("  Optional: phone, emergency_contact_name,")
    print("            emergency_contact_phone, emergency_contact_relation")
    try:
        path = _input("CSV path", allow_empty=False)
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = data.bulk_import_contacts_csv(path, dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_pwreset_flag_flow() -> None:
    print("\n═══ Bulk Force Password Reset ═══")
    try:
        sids = _pick_students()
        clear = _yes_no("Clear the flag (instead of setting it)?",
                          default=False)
        reason = _input("Reason (optional)") or None
        by = _input("Flagged by") or None
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = data.bulk_force_password_reset(
            sids, reason=reason, flagged_by=by, clear=clear,
            dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_undo_job_flow() -> None:
    print("\n═══ Undo Job (best-effort rollback) ═══")
    print(f"  Undoable: {', '.join(data._UNDOABLE)}")
    try:
        jid = int(_input("Job id to undo", allow_empty=False))
        dry = _yes_no("Preview (dry run)?", default=False)
    except (_UserAbort, ValueError):
        print("\n  Cancelled / bad input.")
        return
    try:
        r = data.bulk_undo_job(jid, dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_schedule_create_flow() -> None:
    print("\n═══ Create Recurring Bulk Schedule ═══")
    try:
        name = _input("Schedule name", allow_empty=False)
        op = _input(f"Operation ({'/'.join(data.OPERATIONS)})",
                       allow_empty=False)
        cron_expr = _input(
            "Cron expression (e.g. '0 9 * * 1')", allow_empty=False)
        next_run = _input(
            "First run (YYYY-MM-DD HH:MM, optional)") or None
        params_raw = _input("Parameters (k=v,...; optional)") or ""
        by = _input("Created by") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    params: dict = {}
    for pair in params_raw.split(","):
        if "=" in pair:
            k, v = pair.split("=", 1)
            params[k.strip()] = v.strip()
    try:
        r = data.bulk_schedule_recurring(
            name=name, operation=op, cron_expr=cron_expr,
            parameters=params, next_run_at=next_run,
            created_by=by, dry_run=False,
        )
    except (ValidationError, KeyError) as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=False)


def bulk_schedule_list_flow() -> None:
    print("\n═══ Recurring Schedules ═══")
    rows = data.list_schedules()
    if not rows:
        print("  (none)")
        _pause()
        return
    print(f"\n  {'#':>4}  {'On':<3}  {'Name':<24}  {'Op':<20}  "
          f"{'Cron':<20}  Next run")
    print("  " + "-" * 100)
    for s in rows:
        on = "yes" if s.enabled else "no"
        print(f"  {s.schedule_id:>4}  {on:<3}  {s.name[:24]:<24}  "
              f"{s.operation[:20]:<20}  {s.cron_expr[:20]:<20}  "
              f"{s.next_run_at or '—'}")
    print(f"\n  {len(rows)} schedule(s).")
    _pause()


def bulk_schedule_toggle_flow() -> None:
    print("\n═══ Enable / Disable Schedule ═══")
    try:
        sid_raw = _input("Schedule id", allow_empty=False)
        sid = int(sid_raw)
        enable = _yes_no("Enable?", default=True)
    except (_UserAbort, ValueError):
        print("\n  Cancelled / bad input.")
        return
    try:
        s = data.set_schedule_enabled(sid, enable)
        print(f"  ✓ #{s.schedule_id} {s.name}: "
              f"enabled={s.enabled}")
    except ValidationError as e:
        print(f"  ✗ {e}")
    _pause()


def bulk_logs_flow() -> None:
    print("\n═══ Bulk Operation Logs ═══")
    try:
        level = _input("Level filter (DEBUG/INFO/WARNING/ERROR; blank=all)") or None
        op = _input("Operation filter (blank=all)") or None
        n = int(_input("Limit", default="50"))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    try:
        rows = data.list_logs(level=level, operation=op, limit=n)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    if not rows:
        print("\n  (no logs)")
        _pause()
        return
    print()
    print(f"  {'#':>5}  {'When':<19}  {'Level':<8}  "
          f"{'Op':<22}  {'Job':>5}  Message")
    print("  " + "-" * 110)
    for r in rows:
        print(f"  {r.log_id:>5}  {r.ts[:19]:<19}  {r.level:<8}  "
              f"{(r.operation or '—')[:22]:<22}  "
              f"{str(r.job_id or '—'):>5}  {r.message[:60]}")
    print(f"\n  {len(rows)} log row(s).")
    _pause()


def bulk_logs_clear_flow() -> None:
    print("\n═══ Clear Logs ═══")
    try:
        raw = _input(
            "Delete logs older than N days (blank = ALL logs)") or ""
        days = int(raw) if raw else None
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    label = (f"older than {days} days" if days is not None
             else "ALL logs")
    if _input(f"Delete {label}? Type 'yes'",
                default="no").lower() != "yes":
        print("  Cancelled.")
        return
    try:
        n = data.clear_logs(older_than_days=days)
        print(f"  ✓ Deleted {n} row(s).")
    except ValidationError as e:
        print(f"  ✗ {e}")
    _pause()


def bulk_schedule_delete_flow() -> None:
    print("\n═══ Delete Schedule ═══")
    try:
        sid = int(_input("Schedule id", allow_empty=False))
    except (_UserAbort, ValueError):
        print("\n  Cancelled / bad input.")
        return
    if _input(f"Delete schedule #{sid}? Type 'yes'",
                default="no").lower() != "yes":
        print("  Cancelled.")
        return
    if data.delete_schedule(sid):
        print(f"  ✓ Deleted #{sid}")
    else:
        print(f"  ✗ No schedule #{sid}")
    _pause()


# ── Job log ───────────────────────────────────────────────────────

def list_jobs_flow() -> None:
    print("\n═══ Bulk Job Log ═══")
    try:
        op = _input(f"Operation filter ({'/'.join(OPERATIONS)})") or None
        n = int(_input("Limit", default="100"))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    try:
        rows = data.list_jobs(operation=op, limit=n)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_jobs(rows)
    _pause()


def view_job() -> None:
    print("\n═══ View Job ═══")
    try:
        jid = int(_input("Job id", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    j = data.get_job(jid)
    if j is None:
        print(f"  ✗ No job #{jid}")
        _pause()
        return
    print()
    print(f"    Job id      : #{j.job_id}")
    print(f"    When        : {j.ran_at}")
    print(f"    Operation   : {j.operation}")
    print(f"    Summary     : {j.summary}")
    print(f"    Targets     : {j.target_count}")
    print(f"    Successes   : {j.success_count}")
    print(f"    Failures    : {j.failure_count}")
    print(f"    Ran by      : {j.ran_by or '—'}")
    if j.parameters:
        print("\n    Parameters:")
        for line in json.dumps(j.parameters, indent=2).splitlines():
            print(f"      {line}")
    if j.success_ids:
        print(f"\n    Success ids ({len(j.success_ids)}):")
        for sid in j.success_ids[:20]:
            print(f"      {sid}")
        if len(j.success_ids) > 20:
            print(f"      ... +{len(j.success_ids) - 20} more")
    if j.failures:
        print(f"\n    Failures ({len(j.failures)}):")
        for sid, reason in j.failures[:20]:
            print(f"      {sid}: {reason}")
        if len(j.failures) > 20:
            print(f"      ... +{len(j.failures) - 20} more")
    _pause()


def delete_job_flow() -> None:
    print("\n═══ Delete Job ═══")
    try:
        jid = int(_input("Job id", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    if data.get_job(jid) is None:
        print(f"  ✗ No job #{jid}")
        _pause()
        return
    if _input(f"Delete job #{jid}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_job(jid):
        print(f"\n  ✓ Deleted #{jid}")
    _pause()


def summary_flow() -> None:
    print("\n═══ Bulk Operations Summary ═══")
    summ = data.summary()
    print(f"\n  Total jobs         : {summ.total_jobs}")
    print(f"  Total targets      : {summ.total_targets}")
    print(f"  Total successes    : {summ.total_successes}")
    print(f"  Total failures     : {summ.total_failures}")
    print(f"  Most recent        : {summ.most_recent_ts or '—'}")
    print("\n  By operation:")
    for op in OPERATIONS:
        n = summ.by_operation.get(op, 0)
        if n:
            print(f"    {op:<22} : {n}")
    _pause()


# ── New attendance/academic flows (items 1–10) ─────────────────────

def bulk_mark_holiday_flow() -> None:
    print("\n═══ Bulk Mark Holiday (Authorised) ═══")
    try:
        sids = _pick_students()
        date_from = _input("From date (YYYY-MM-DD)", allow_empty=False)
        date_to = _input("To date (YYYY-MM-DD)", allow_empty=False)
        reason = _input("Reason", default="Authorised holiday")
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = data.bulk_mark_holiday(
            sids, date_from=date_from, date_to=date_to,
            reason=reason, dry_run=dry,
        )
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_clear_attendance_flow() -> None:
    print("\n═══ Bulk Clear Attendance ═══")
    try:
        sids = _pick_students()
        date_from = _input("From date (YYYY-MM-DD)", allow_empty=False)
        date_to = _input("To date (YYYY-MM-DD)", allow_empty=False)
        only_status = _input(
            "Restrict to status (Present/Late/Absent/Authorised, blank=all)"
        ) or None
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if not dry and not _yes_no(
            f"This will DELETE attendance rows for {len(sids)} student(s). "
            "Continue?", default=False):
        print("\n  Cancelled.")
        return
    try:
        r = data.bulk_clear_attendance(
            sids, date_from=date_from, date_to=date_to,
            only_status=only_status, dry_run=dry,
        )
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_late_to_unauth_flow() -> None:
    print("\n═══ Bulk Convert Late→Unauthorised ═══")
    try:
        sids = _pick_students()
        date_from = _input("From date (YYYY-MM-DD)", allow_empty=False)
        date_to = _input("To date (YYYY-MM-DD)", allow_empty=False)
        over_raw = _input("Convert when minutes_late >", default="15")
        reason = _input("Reason",
                         default="Late > threshold — unauthorised")
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        over = int(over_raw)
    except ValueError:
        print("  ✗ Threshold must be a number.")
        _pause()
        return
    try:
        r = data.bulk_late_to_unauth(
            sids, date_from=date_from, date_to=date_to,
            over_minutes=over, reason=reason or None, dry_run=dry,
        )
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_attendance_letters_flow() -> None:
    print("\n═══ Bulk Attendance Letters (Stage 1/2/3) ═══")
    try:
        sids = _pick_students()
        window_raw = _input("Window (days)", default="28")
        s1 = _input("Stage 1 threshold % (lower = stage 1)", default="95")
        s2 = _input("Stage 2 threshold %", default="90")
        s3 = _input("Stage 3 threshold %", default="85")
        send = _yes_no("Actually send messages?", default=True)
        sender = _input("Sender staff id") or None
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        window = int(window_raw)
        tiers = tuple(
            (float(t), label) for t, label in
            ((s1, "Stage 1"), (s2, "Stage 2"), (s3, "Stage 3"))
        )
    except ValueError:
        print("  ✗ Window and thresholds must be numeric.")
        _pause()
        return
    try:
        r = data.bulk_attendance_letters(
            sids, window_days=window, stages=tiers, send=send,
            sender_staff_id=sender, dry_run=dry,
        )
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_punctuality_report_flow() -> None:
    print("\n═══ Bulk Punctuality Report (email tutors) ═══")
    try:
        sids = _pick_students()
        date_from = _input("From date (YYYY-MM-DD)", allow_empty=False)
        date_to = _input("To date (YYYY-MM-DD)",
                          default=_date.today().isoformat())
        sender = _input("Sender staff id") or None
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = data.bulk_punctuality_report(
            sids, date_from=date_from, date_to=date_to,
            sender_staff_id=sender, dry_run=dry,
        )
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_register_closure_flow() -> None:
    print("\n═══ Bulk Register Closure (lock past registers) ═══")
    try:
        slot_ids = _pick_slots()
        date_from = _input("From date (YYYY-MM-DD)", allow_empty=False)
        date_to = _input("To date (YYYY-MM-DD)", allow_empty=False)
        default_status = _pick_from("Fill blanks as",
                                       ["Present", "Absent", "Authorised"],
                                       default="Present")
        notes = _input("Notes") or None
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if not dry and not _yes_no(
            "Once closed, registers should be considered locked. "
            "Continue?", default=False):
        print("\n  Cancelled.")
        return
    try:
        r = data.bulk_register_closure(
            slot_ids, date_from=date_from, date_to=date_to,
            default_status=default_status, notes=notes, dry_run=dry,
        )
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_assign_subjects_flow() -> None:
    print("\n═══ Bulk Assign Subjects ═══")
    try:
        sids = _pick_students()
        print("  Pick up to 3 subjects (one at a time, blank to finish).")
        picks: list[str] = []
        for _ in range(3):
            try:
                pick = _pick_subject()
            except _UserAbort:
                break
            if not pick or pick in picks:
                break
            picks.append(pick)
            if not _yes_no("Add another subject?", default=False):
                break
        if not picks:
            print("  ✗ At least one subject required.")
            _pause()
            return
        overwrite = _yes_no(
            "Overwrite existing slots? (no = fill blanks only)",
            default=False)
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = data.bulk_assign_subjects(
            sids, subjects=picks, overwrite=overwrite, dry_run=dry,
        )
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_withdraw_subjects_flow() -> None:
    print("\n═══ Bulk Withdraw Subjects ═══")
    try:
        sids = _pick_students()
        print("  Pick subjects to remove (blank to finish).")
        picks: list[str] = []
        for _ in range(3):
            try:
                pick = _pick_subject()
            except _UserAbort:
                break
            if not pick or pick in picks:
                break
            picks.append(pick)
            if not _yes_no("Withdraw another?", default=False):
                break
        if not picks:
            print("  ✗ At least one subject required.")
            _pause()
            return
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = data.bulk_withdraw_subjects(
            sids, subjects=picks, dry_run=dry,
        )
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_set_teaching_set_flow() -> None:
    print("\n═══ Bulk Set Teaching Set ═══")
    try:
        sids = _pick_students()
        print("  Target group (the set to move students INTO):")
        target = _pick_group()
        if target is None:
            print("  ✗ Pick a target group.")
            _pause()
            return
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = data.bulk_set_teaching_set(
            sids, target_group_id=target, dry_run=dry,
        )
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_import_timetable_csv_flow() -> None:
    print("\n═══ Bulk Import Timetable CSV ═══")
    print("  Required columns: group_id, day, period")
    print("  Optional:         start_time, end_time, room, notes")
    try:
        path = _input("CSV path", allow_empty=False)
        dry = _yes_no("Preview (dry run)?", default=True)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = data.bulk_import_timetable_csv(
            path, dry_run=dry,
        )
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


# ── Submenu ───────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Bulk log behaviour",           bulk_behaviour),
    ("Bulk add accommodation",       bulk_accommodation),
    ("Bulk update student field",    bulk_update_field),
    ("Bulk message students",        bulk_message_flow),
    ("Bulk archive to alumni",       bulk_archive_flow),
    ("─" * 6,                        lambda: None),
    ("Bulk mark attendance",         bulk_mark_attendance_flow),
    ("Bulk authorise absences",      bulk_authorise_flow),
    ("Bulk apply lateness",          bulk_lateness_flow),
    ("Bulk import attendance CSV",   bulk_import_csv_flow),
    ("Bulk recalculate attendance",  bulk_recalc_flow),
    ("Bulk flag low attendance",     bulk_flag_low_attendance_flow),
    ("Bulk register sign-off",       bulk_signoff_flow),
    ("Bulk mark holiday",            bulk_mark_holiday_flow),
    ("Bulk clear attendance",        bulk_clear_attendance_flow),
    ("Bulk late → unauthorised",     bulk_late_to_unauth_flow),
    ("Bulk attendance letters",      bulk_attendance_letters_flow),
    ("Bulk punctuality report",      bulk_punctuality_report_flow),
    ("Bulk register closure",        bulk_register_closure_flow),
    ("─" * 6,                        lambda: None),
    ("Bulk enrol students",          bulk_enrol_flow),
    ("Bulk assign subjects",         bulk_assign_subjects_flow),
    ("Bulk withdraw subjects",       bulk_withdraw_subjects_flow),
    ("Bulk set teaching set",        bulk_set_teaching_set_flow),
    ("Bulk import timetable CSV",    bulk_import_timetable_csv_flow),
    ("─" * 6,                        lambda: None),
    ("Bulk move class group",        bulk_move_group_flow),
    ("Bulk assign predicted grades", bulk_predicted_grades_flow),
    ("Bulk import assessment marks", bulk_import_marks_flow),
    ("Bulk recalc grade reports",    bulk_recalc_grades_flow),
    ("Bulk export progress reports", bulk_export_progress_flow),
    ("Bulk publish report cards",    bulk_publish_reports_flow),
    ("Bulk apply grade boundaries",  bulk_grade_boundaries_flow),
    ("─" * 6,                        lambda: None),
    ("Bulk issue detentions",        bulk_detention_flow),
    ("Bulk award merits",            bulk_merits_flow),
    ("Bulk escalate behaviour",      bulk_escalate_flow),
    ("Bulk safeguarding flag",       bulk_safeguarding_flow),
    ("Bulk assign mentors",          bulk_mentors_flow),
    ("Bulk reset behaviour points",  bulk_reset_points_flow),
    ("─" * 6,                        lambda: None),
    ("Bulk SMS",                     bulk_sms_flow),
    ("Bulk send letters",            bulk_letters_flow),
    ("Bulk parents-evening invites", bulk_meeting_invites_flow),
    ("Bulk UCAS reference reminders", bulk_ucas_reminders_flow),
    ("Bulk password reset emails",   bulk_password_reset_flow),
    ("Bulk schedule message",        bulk_schedule_msg_flow),
    ("─" * 6,                        lambda: None),
    ("Bulk bursary award",           bulk_bursary_flow),
    ("Bulk raise invoices",          bulk_invoices_flow),
    ("Bulk fee discount",            bulk_discount_flow),
    ("Bulk import payments CSV",     bulk_payments_csv_flow),
    ("Bulk financial statements",    bulk_statements_flow),
    ("─" * 6,                        lambda: None),
    ("Bulk exam entries",            bulk_exam_entries_flow),
    ("Bulk exam access arrangements", bulk_exam_access_flow),
    ("Bulk export exam timetables",  bulk_exam_timetables_flow),
    ("Bulk UCAS export predictions", bulk_ucas_export_flow),
    ("Bulk update UCAS status",      bulk_ucas_status_flow),
    ("─" * 6,                        lambda: None),
    ("Bulk promote year group",      bulk_promote_flow),
    ("Bulk mark leavers",            bulk_leavers_flow),
    ("Bulk reinstate alumni",        bulk_reinstate_flow),
    ("Bulk GDPR redact",             bulk_gdpr_flow),
    ("Bulk export student records",  bulk_export_records_flow),
    ("Bulk anonymise alumni",        bulk_anonymise_flow),
    ("─" * 6,                        lambda: None),
    ("Bulk assign inventory",        bulk_inventory_flow),
    ("Bulk upload photos",           bulk_photos_flow),
    ("Bulk import contacts CSV",     bulk_contacts_csv_flow),
    ("Bulk force password reset",    bulk_pwreset_flag_flow),
    ("─" * 6,                        lambda: None),
    ("Undo job",                     bulk_undo_job_flow),
    ("Create recurring schedule",    bulk_schedule_create_flow),
    ("List schedules",               bulk_schedule_list_flow),
    ("Toggle schedule",              bulk_schedule_toggle_flow),
    ("Delete schedule",              bulk_schedule_delete_flow),
    ("─" * 6,                        lambda: None),
    ("View logs",                    bulk_logs_flow),
    ("Clear logs",                   bulk_logs_clear_flow),
    ("─" * 6,                        lambda: None),
    ("Job log",                      list_jobs_flow),
    ("View job",                     view_job),
    ("Delete job",                   delete_job_flow),
    ("Summary",                      summary_flow),
]


def run() -> None:
    # Make sure the SQLite log handler is up before we field any input.
    try:
        data.init_db()
    except Exception as e:  # noqa: BLE001 — non-fatal at the menu level
        print(f"\n  ⚠ Bulk-operations DB not ready: {e}")
    while True:
        print("\n── Bulk Operations ──")
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
        except ValidationError as e:
            data.log_event(logging.WARNING,
                            f"CLI validation error in {label!r}: {e}",
                            operation=label)
            print(f"\n  ✗ {e}")
            _pause()
        except Exception as e:  # noqa: BLE001
            data.log_event(logging.ERROR,
                            f"CLI handler {label!r} crashed: {e}",
                            operation=label, exc_info=True)
            logger.exception("Bulk-operations CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Bulk Operations":
        return False
    try:
        run()
    except Exception as e:  # noqa: BLE001
        try:
            data.log_event(logging.CRITICAL,
                            f"Bulk-operations submenu crashed: {e}",
                            exc_info=True)
        except Exception:  # noqa: BLE001 — last-resort
            pass
        logger.exception("Bulk-operations CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
