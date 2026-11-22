"""CLI flows for attendance bulk operations.

Split out of ``bulk_operations_cli.py``, which re-exports every name here.
"""

from __future__ import annotations

from datetime import date as _date

from education_system.systems.sixth_form.domain.learners.bulk_operations import ops_attendance as bulk_ops_attendance
from education_system.systems.sixth_form.domain.learners.bulk_operations.base import ValidationError

from education_system.systems.sixth_form.interfaces.cli.learners.bulk_operations.cli_flows.prompts import (
    _input,
    _pause,
    _pick_from,
    _pick_slot,
    _pick_slots,
    _pick_students,
    _print_result,
    _UserAbort,
    _yes_no,
)


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
        r = bulk_ops_attendance.bulk_mark_attendance(
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
        r = bulk_ops_attendance.bulk_authorise_absences(
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
        r = bulk_ops_attendance.bulk_apply_lateness(
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
        r = bulk_ops_attendance.bulk_import_attendance_csv(path, dry_run=dry)
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
        r = bulk_ops_attendance.bulk_recalc_attendance(
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
        r = bulk_ops_attendance.bulk_flag_low_attendance(
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
        r = bulk_ops_attendance.bulk_signoff_register(
            slot_ids, date=date_str, default_status=default_status,
            dry_run=dry,
        )
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


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
        r = bulk_ops_attendance.bulk_mark_holiday(
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
        r = bulk_ops_attendance.bulk_clear_attendance(
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
        r = bulk_ops_attendance.bulk_late_to_unauth(
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
        r = bulk_ops_attendance.bulk_attendance_letters(
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
        r = bulk_ops_attendance.bulk_punctuality_report(
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
        r = bulk_ops_attendance.bulk_register_closure(
            slot_ids, date_from=date_from, date_to=date_to,
            default_status=default_status, notes=notes, dry_run=dry,
        )
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)
