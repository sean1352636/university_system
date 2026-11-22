"""Sixth Form bulk operations — attendance.

Split out of ``bulk_operations.py``, which re-exports every name defined here."""

from __future__ import annotations

from typing import Any
import datetime as _dt
import logging
from education_system.systems.sixth_form.domain.learners.bulk_operations.base import (
    BulkResult,
    ValidationError,
    _connect,
    _log_job,
    _preview_targets,
    _validate_targets,
    init_db,
    log_event,
    logger,
)

# ── Attendance helpers ────────────────────────────────────────────

def _daterange(date_from: str, date_to: str) -> list[str]:
    """Inclusive list of YYYY-MM-DD strings between two dates (weekdays only)."""
    try:
        d0 = _dt.date.fromisoformat(date_from)
        d1 = _dt.date.fromisoformat(date_to)
    except ValueError as e:
        raise ValidationError(f"Invalid date: {e}") from e
    if d1 < d0:
        raise ValidationError("date_to must be on or after date_from")
    if (d1 - d0).days > 366:
        raise ValidationError("Date range too wide (max 366 days)")
    out: list[str] = []
    cur = d0
    one = _dt.timedelta(days=1)
    while cur <= d1:
        if cur.weekday() < 5:  # Mon–Fri
            out.append(cur.isoformat())
        cur += one
    return out


# ── Operation: bulk mark attendance ───────────────────────────────

def bulk_mark_attendance(
    student_ids: list[str],
    *,
    slot_id: int,
    date: str,
    status: str = "Present",
    minutes_late: int | None = None,
    notes: str | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Stamp the same status against many students on one slot+date."""
    targets = _validate_targets(student_ids)
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance as _att,
    )
    result = BulkResult(operation="mark_attendance",
                         target_count=len(targets))
    if dry_run:
        return result
    entries = {
        sid: {"status": status, "minutes_late": minutes_late, "notes": notes}
        for sid in targets
    }
    try:
        _att.save_register(slot_id, date, entries)
        result.success_ids.extend(targets)
    except Exception as e:
        for sid in targets:
            result.failures.append((sid, str(e)))
    summary_text = (f"Marked {status} for "
                    f"{result.success_count}/{result.target_count} students "
                    f"on slot #{slot_id} ({date})")
    result.job_id = _log_job(
        operation="mark_attendance", summary=summary_text,
        params={"slot_id": slot_id, "date": date, "status": status,
                "minutes_late": minutes_late, "notes": notes},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk authorise absences ────────────────────────────

def bulk_authorise_absences(
    student_ids: list[str],
    *,
    date_from: str,
    date_to: str,
    target_status: str = "Authorised",
    reason: str | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Flip Absent rows → Authorised (or reverse) across a date window.

    Only rows currently in the opposite state are touched. ``reason``,
    if given, is appended to each row's notes column.
    """
    targets = _validate_targets(student_ids)
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance as _att,
    )
    if target_status not in ("Authorised", "Absent"):
        raise ValidationError("target_status must be Authorised or Absent")
    source_status = "Absent" if target_status == "Authorised" else "Authorised"
    result = BulkResult(operation="authorise_absences",
                         target_count=len(targets))
    if dry_run:
        return result
    touched = 0
    for sid in targets:
        try:
            rows = _att.list_records(
                student_id=sid,
                date_from=date_from, date_to=date_to,
                status=source_status,
            )
            for rec in rows:
                merged_notes = rec.notes or ""
                if reason:
                    merged_notes = (
                        f"{merged_notes} | {reason}".strip(" |")
                        if merged_notes else reason
                    )
                _att.update_record(rec.record_id, {
                    "status": target_status,
                    "minutes_late": rec.minutes_late,
                    "notes": merged_notes or None,
                })
                touched += 1
            result.success_ids.append(sid)
        except Exception as e:
            result.failures.append((sid, str(e)))
    summary_text = (
        f"Re-flagged {source_status}→{target_status} on {touched} row(s) "
        f"across {result.success_count}/{result.target_count} students "
        f"({date_from}..{date_to})"
    )
    result.job_id = _log_job(
        operation="authorise_absences", summary=summary_text,
        params={"date_from": date_from, "date_to": date_to,
                "target_status": target_status, "reason": reason,
                "rows_touched": touched},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk apply lateness ────────────────────────────────

def bulk_apply_lateness(
    student_ids: list[str],
    *,
    slot_id: int,
    date: str,
    minutes_late: int,
    auto_log_behaviour_over: int | None = None,
    behaviour_recorded_by: str | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Mark all listed students Late with the same minutes_late.

    If ``auto_log_behaviour_over`` is set and ``minutes_late`` is at or
    above it, a negative behaviour entry is also logged for each student
    (acts as the "auto-detention threshold" trigger).
    """
    targets = _validate_targets(student_ids)
    try:
        minutes_late = int(minutes_late)
    except (TypeError, ValueError):
        raise ValidationError("minutes_late must be a number") from None
    if minutes_late < 0 or minutes_late > 1000:
        raise ValidationError("minutes_late must be 0..1000")
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance as _att,
    )
    result = BulkResult(operation="apply_lateness",
                         target_count=len(targets))
    if dry_run:
        return result
    entries = {
        sid: {"status": "Late", "minutes_late": minutes_late, "notes": None}
        for sid in targets
    }
    try:
        _att.save_register(slot_id, date, entries)
        result.success_ids.extend(targets)
    except Exception as e:
        for sid in targets:
            result.failures.append((sid, str(e)))

    behaviour_logged = 0
    if (result.success_ids and auto_log_behaviour_over is not None
            and minutes_late >= auto_log_behaviour_over):
        from education_system.systems.sixth_form.domain.pastoral.behaviour import (
            behaviour as _bh,
        )
        for sid in list(result.success_ids):
            try:
                _bh.create_entry({
                    "student_id":   sid,
                    "entry_date":   date,
                    "entry_type":   "Negative",
                    "category":     "Lateness",
                    "description":  (f"Auto-flag: {minutes_late} min late "
                                     f"(threshold {auto_log_behaviour_over})"),
                    "severity":     "Low",
                    "points":       1,
                    "recorded_by":  behaviour_recorded_by,
                    "action_taken": "Detention threshold reached",
                })
                behaviour_logged += 1
            except Exception:  # noqa: BLE001 — best-effort secondary log
                logger.exception("auto-log behaviour failed for %s", sid)

    summary_text = (
        f"Marked Late ({minutes_late} min) on slot #{slot_id} ({date}) for "
        f"{result.success_count}/{result.target_count}"
        + (f"; behaviour logged ×{behaviour_logged}"
           if behaviour_logged else "")
    )
    result.job_id = _log_job(
        operation="apply_lateness", summary=summary_text,
        params={"slot_id": slot_id, "date": date,
                "minutes_late": minutes_late,
                "auto_log_behaviour_over": auto_log_behaviour_over,
                "behaviour_logged": behaviour_logged},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk import attendance CSV ─────────────────────────

def bulk_import_attendance_csv(
    csv_path: str,
    *,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Import attendance rows from a CSV.

    Required headers: ``student_id, slot_id, date, status``.
    Optional: ``minutes_late, notes``. One row per record; failures are
    reported per-line so partial imports are kept.
    """
    import csv as _csv
    import os
    if not csv_path or not os.path.isfile(csv_path):
        raise ValidationError(f"CSV not found: {csv_path}")
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance as _att,
    )
    rows: list[dict[str, str]] = []
    with open(csv_path, encoding="utf-8-sig", newline="") as fh:
        reader = _csv.DictReader(fh)
        required = {"student_id", "slot_id", "date", "status"}
        missing = required - set(h.strip() for h in (reader.fieldnames or []))
        if missing:
            raise ValidationError(
                f"CSV missing columns: {', '.join(sorted(missing))}")
        for r in reader:
            rows.append({k: (v or "").strip() for k, v in r.items()})

    result = BulkResult(operation="import_attendance_csv",
                         target_count=len(rows))
    if dry_run:
        return result
    # Group by (slot_id, date) so save_register can upsert in one tx.
    grouped: dict[tuple[int, str], dict[str, dict[str, Any]]] = {}
    line_tags: dict[tuple[int, str, str], int] = {}
    for i, r in enumerate(rows, start=2):  # +2 to account for header line
        sid = r.get("student_id", "")
        try:
            slot_id = int(r.get("slot_id", ""))
        except ValueError:
            result.failures.append(
                (f"line {i}", f"slot_id not numeric: {r.get('slot_id')!r}"))
            continue
        date = r.get("date", "")
        status = r.get("status", "")
        minutes = r.get("minutes_late") or None
        if minutes:
            try:
                minutes = int(minutes)
            except ValueError:
                result.failures.append(
                    (f"line {i}", f"minutes_late not numeric: {minutes!r}"))
                continue
        notes = r.get("notes") or None
        key = (slot_id, date)
        grouped.setdefault(key, {})[sid] = {
            "status": status, "minutes_late": minutes, "notes": notes,
        }
        line_tags[(slot_id, date, sid)] = i

    for (slot_id, date), entries in grouped.items():
        try:
            _att.save_register(slot_id, date, entries)
            for sid in entries:
                result.success_ids.append(
                    f"L{line_tags[(slot_id, date, sid)]}:{sid}")
        except Exception as e:
            for sid in entries:
                result.failures.append(
                    (f"line {line_tags[(slot_id, date, sid)]}:{sid}",
                     str(e)))
    summary_text = (f"Imported {result.success_count}/{result.target_count} "
                    f"attendance rows from {os.path.basename(csv_path)}")
    result.job_id = _log_job(
        operation="import_attendance_csv", summary=summary_text,
        params={"csv_path": csv_path, "groups": len(grouped)},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk recalculate attendance % ──────────────────────

def bulk_recalc_attendance(
    student_ids: list[str],
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Compute attendance summary % for each student in the window.

    Successes carry an ``sid:pct`` token so the job log is auditable; this
    is a read-only operation that exists primarily to bookkeep "we
    recalculated cohort X on date Y".
    """
    targets = _validate_targets(student_ids)
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance as _att,
    )
    result = BulkResult(operation="recalc_attendance",
                         target_count=len(targets))
    if dry_run:
        return result
    samples: list[tuple[str, float | None, int]] = []
    for sid in targets:
        try:
            s = _att.summary_for_student(
                sid, date_from=date_from, date_to=date_to)
            samples.append((sid, s.percentage, s.total))
            tag = f"{sid}:{'—' if s.percentage is None else f'{s.percentage}%'}"
            result.success_ids.append(tag)
        except Exception as e:
            result.failures.append((sid, str(e)))
    summary_text = (
        f"Recalculated attendance for "
        f"{result.success_count}/{result.target_count} students "
        f"({date_from or 'all'}..{date_to or 'all'})"
    )
    result.job_id = _log_job(
        operation="recalc_attendance", summary=summary_text,
        params={"date_from": date_from, "date_to": date_to,
                "samples": [[sid, pct, total]
                            for sid, pct, total in samples]},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk flag students below attendance threshold ──────

def bulk_flag_low_attendance(
    student_ids: list[str],
    *,
    threshold_pct: float = 90.0,
    window_days: int = 28,
    level: str = "Medium",
    reason: str = "Low overall attendance",
    raised_by: str | None = None,
    skip_if_open_concern: bool = True,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """For each student, compute % over the window and open an
    attendance_concern row if below ``threshold_pct``."""
    targets = _validate_targets(student_ids)
    try:
        threshold_pct = float(threshold_pct)
    except (TypeError, ValueError):
        raise ValidationError("threshold_pct must be numeric") from None
    if not (0.0 <= threshold_pct <= 100.0):
        raise ValidationError("threshold_pct must be 0..100")
    try:
        window_days = int(window_days)
    except (TypeError, ValueError):
        raise ValidationError("window_days must be numeric") from None
    if window_days <= 0 or window_days > 365:
        raise ValidationError("window_days must be 1..365")

    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance as _att,
    )
    from education_system.systems.sixth_form.domain.pastoral.attendance_concerns import (
        attendance_concerns as _ac,
    )
    end = _dt.date.today()
    start = end - _dt.timedelta(days=window_days)
    df, dt = start.isoformat(), end.isoformat()

    result = BulkResult(operation="flag_low_attendance",
                         target_count=len(targets))
    if dry_run:
        return result
    flagged = 0
    for sid in targets:
        try:
            summ = _att.summary_for_student(
                sid, date_from=df, date_to=dt)
            pct = summ.percentage
            if summ.total == 0 or pct is None or pct >= threshold_pct:
                result.success_ids.append(f"{sid}:skip")
                continue
            if skip_if_open_concern:
                existing = _ac.list_concerns(
                    student_id=sid, open_only=True)
                if existing:
                    result.success_ids.append(f"{sid}:has-open")
                    continue
            _ac.create_concern({
                "student_id":    sid,
                "raised_date":   dt,
                "reason":        reason,
                "level":         level,
                "status":        "Open",
                "threshold_pct": threshold_pct,
                "observed_pct":  pct,
                "window_days":   window_days,
                "description":   (f"Auto-flagged: {pct}% over last "
                                  f"{window_days} days "
                                  f"(threshold {threshold_pct}%)"),
                "raised_by":     raised_by,
            })
            flagged += 1
            result.success_ids.append(f"{sid}:flagged@{pct}%")
        except Exception as e:
            result.failures.append((sid, str(e)))
    summary_text = (f"Reviewed {result.success_count}/{result.target_count}; "
                    f"opened {flagged} concern(s) under {threshold_pct}% "
                    f"({window_days}-day window)")
    result.job_id = _log_job(
        operation="flag_low_attendance", summary=summary_text,
        params={"threshold_pct": threshold_pct, "window_days": window_days,
                "level": level, "reason": reason,
                "flagged": flagged},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk close-of-day register sign-off ────────────────

def bulk_signoff_register(
    slot_ids: list[int],
    *,
    date: str,
    default_status: str = "Present",
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """For each slot, fill any student who has no record on ``date``
    with ``default_status``. Existing records are left untouched."""
    if not slot_ids:
        raise ValidationError("Pick at least one slot")
    # Reuse target validation on stringified slot ids so the BulkResult
    # contract holds (success_ids are strings).
    str_targets = _validate_targets([str(s) for s in slot_ids])
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance as _att,
    )
    result = BulkResult(operation="signoff_register",
                         target_count=len(str_targets))
    if dry_run:
        return result
    filled_total = 0
    for tag in str_targets:
        try:
            slot_id = int(tag)
            roster = _att.register_view(slot_id, date)
            missing = {
                entry.student_id: {"status": default_status,
                                    "minutes_late": None,
                                    "notes": "Signed off (default)"}
                for entry in roster if entry.record is None
            }
            if missing:
                _att.save_register(slot_id, date, missing)
            filled_total += len(missing)
            result.success_ids.append(f"slot#{slot_id}:+{len(missing)}")
        except Exception as e:
            result.failures.append((tag, str(e)))
    summary_text = (f"Signed off {result.success_count}/"
                    f"{result.target_count} slots on {date}; "
                    f"filled {filled_total} blank entry(ies) as "
                    f"{default_status}")
    result.job_id = _log_job(
        operation="signoff_register", summary=summary_text,
        params={"date": date, "default_status": default_status,
                "slot_ids": [int(t) for t in str_targets],
                "filled": filled_total},
        result=result, ran_by=ran_by,
    )
    return result


# ──────────────────────────────────────────────────────────────────
# Items 1–10 from the "50 more bulk operations" wishlist
# ──────────────────────────────────────────────────────────────────

# ── Operation: bulk mark holiday ──────────────────────────────────

def bulk_mark_holiday(
    student_ids: list[str],
    *,
    date_from: str,
    date_to: str,
    reason: str = "Authorised holiday",
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Mark a date range as Authorised absence for selected students.

    For every weekday in ``[date_from, date_to]`` we look up the
    timetable slots that run on that weekday and stamp an Authorised
    record (with ``reason`` in notes) for each selected student. Any
    existing Absent / Late record in the window for those students is
    flipped to Authorised as well.
    """
    targets = _validate_targets(student_ids)
    dates = _daterange(date_from, date_to)
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance as _att,
    )
    from education_system.systems.sixth_form.domain.academics.timetable import (
        timetable as _tt,
    )
    result = BulkResult(operation="mark_holiday", target_count=len(targets))
    if dry_run:
        return _preview_targets(
            result, targets,
            verb=f"authorise {len(dates)} day(s) ({date_from}..{date_to})")

    # Group slots by day-of-week (1=Mon..7=Sun) once.
    slots_by_day: dict[int, list[Any]] = {}
    try:
        for s in _tt.list_slots():
            slots_by_day.setdefault(s.day, []).append(s)
    except Exception as e:
        for sid in targets:
            result.failures.append((sid, f"Could not load timetable: {e}"))
        summary_text = (f"Mark holiday failed: timetable unreadable "
                        f"({date_from}..{date_to})")
        result.job_id = _log_job(
            operation="mark_holiday", summary=summary_text,
            params={"date_from": date_from, "date_to": date_to,
                    "reason": reason}, result=result, ran_by=ran_by,
        )
        return result

    written = 0
    converted = 0
    for sid in targets:
        try:
            for date in dates:
                weekday = _dt.date.fromisoformat(date).weekday() + 1
                day_slots = slots_by_day.get(weekday, [])
                for s in day_slots:
                    try:
                        _att.save_register(
                            s.slot_id, date,
                            {sid: {"status": "Authorised",
                                   "minutes_late": None,
                                   "notes": reason}},
                        )
                        written += 1
                    except Exception as e:  # noqa: BLE001
                        # Per-slot failure — keep going for the rest.
                        log_event(
                            logging.WARNING,
                            f"mark_holiday: slot #{s.slot_id} {date} "
                            f"failed for {sid}: {e}",
                            operation="mark_holiday")
                # Convert any *other* records on this date (e.g. Absent
                # marks already entered before the holiday was approved).
                existing = _att.list_records(
                    student_id=sid, date_from=date, date_to=date)
                for rec in existing:
                    if rec.status in ("Absent", "Late"):
                        merged = (
                            f"{rec.notes} | {reason}".strip(" |")
                            if rec.notes else reason)
                        _att.update_record(rec.record_id, {
                            "status": "Authorised",
                            "minutes_late": None,
                            "notes": merged,
                        })
                        converted += 1
            result.success_ids.append(sid)
        except Exception as e:  # noqa: BLE001
            result.failures.append((sid, str(e)))

    summary_text = (
        f"Marked holiday for {result.success_count}/{result.target_count} "
        f"students ({date_from}..{date_to}); "
        f"wrote {written} authorised row(s), converted {converted} existing"
    )
    result.job_id = _log_job(
        operation="mark_holiday", summary=summary_text,
        params={"date_from": date_from, "date_to": date_to,
                "reason": reason, "written": written,
                "converted": converted},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk clear attendance ──────────────────────────────

def bulk_clear_attendance(
    student_ids: list[str],
    *,
    date_from: str,
    date_to: str,
    only_status: str | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Delete attendance rows in a date range for register correction.

    If ``only_status`` is given (Present/Late/Absent/Authorised) the
    deletion is restricted to that status — useful when reverting a
    mis-keyed register without nuking the surrounding marks.
    """
    targets = _validate_targets(student_ids)
    _daterange(date_from, date_to)  # validates the range
    if only_status is not None and only_status not in (
            "Present", "Late", "Absent", "Authorised"):
        raise ValidationError(
            "only_status must be Present/Late/Absent/Authorised")
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance as _att,
    )
    result = BulkResult(operation="clear_attendance",
                        target_count=len(targets))
    if dry_run:
        # Count what we'd delete without doing it.
        for sid in targets:
            try:
                rows = _att.list_records(
                    student_id=sid,
                    date_from=date_from, date_to=date_to,
                    status=only_status,
                )
                result.success_ids.append(f"{sid}: would delete {len(rows)}")
            except Exception as e:  # noqa: BLE001
                result.failures.append((sid, str(e)))
        return result
    total_deleted = 0
    for sid in targets:
        try:
            rows = _att.list_records(
                student_id=sid,
                date_from=date_from, date_to=date_to,
                status=only_status,
            )
            n = 0
            for rec in rows:
                if _att.delete_record(rec.record_id):
                    n += 1
            total_deleted += n
            result.success_ids.append(f"{sid}:-{n}")
        except Exception as e:  # noqa: BLE001
            result.failures.append((sid, str(e)))
    summary_text = (
        f"Cleared {total_deleted} attendance row(s) for "
        f"{result.success_count}/{result.target_count} students "
        f"({date_from}..{date_to}"
        + (f", status={only_status}" if only_status else "") + ")"
    )
    result.job_id = _log_job(
        operation="clear_attendance", summary=summary_text,
        params={"date_from": date_from, "date_to": date_to,
                "only_status": only_status, "deleted": total_deleted},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk convert Late→Unauthorised over threshold ──────

def bulk_late_to_unauth(
    student_ids: list[str],
    *,
    date_from: str,
    date_to: str,
    over_minutes: int = 15,
    reason: str | None = "Late > threshold — unauthorised",
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Flip Late records with ``minutes_late > over_minutes`` to Absent."""
    targets = _validate_targets(student_ids)
    _daterange(date_from, date_to)
    try:
        over_minutes = int(over_minutes)
    except (TypeError, ValueError):
        raise ValidationError("over_minutes must be a number") from None
    if over_minutes < 0 or over_minutes > 1000:
        raise ValidationError("over_minutes must be 0..1000")
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance as _att,
    )
    result = BulkResult(operation="late_to_unauth",
                        target_count=len(targets))
    converted = 0
    for sid in targets:
        try:
            rows = _att.list_records(
                student_id=sid, status="Late",
                date_from=date_from, date_to=date_to,
            )
            qualifying = [r for r in rows
                          if (r.minutes_late or 0) > over_minutes]
            if dry_run:
                result.success_ids.append(
                    f"{sid}: would convert {len(qualifying)}")
                continue
            for rec in qualifying:
                merged = (f"{rec.notes} | {reason}".strip(" |")
                          if rec.notes and reason else (reason or rec.notes))
                _att.update_record(rec.record_id, {
                    "status": "Absent",
                    "minutes_late": None,
                    "notes": merged,
                })
                converted += 1
            result.success_ids.append(f"{sid}:-{len(qualifying)}")
        except Exception as e:  # noqa: BLE001
            result.failures.append((sid, str(e)))
    if dry_run:
        return result
    summary_text = (
        f"Converted {converted} Late→Absent row(s) (>{over_minutes} min) "
        f"for {result.success_count}/{result.target_count} students "
        f"({date_from}..{date_to})"
    )
    result.job_id = _log_job(
        operation="late_to_unauth", summary=summary_text,
        params={"date_from": date_from, "date_to": date_to,
                "over_minutes": over_minutes, "reason": reason,
                "converted": converted},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk attendance letters ────────────────────────────

# Default thresholds — anything ≥ stage1 gets no letter; below stage1 →
# stage 1, below stage2 → stage 2, etc.
DEFAULT_ATTENDANCE_STAGES: tuple[tuple[float, str], ...] = (
    (95.0, "Stage 1"),
    (90.0, "Stage 2"),
    (85.0, "Stage 3"),
)


def bulk_attendance_letters(
    student_ids: list[str],
    *,
    window_days: int = 28,
    stages: tuple[tuple[float, str], ...] | None = None,
    send: bool = True,
    sender_staff_id: str | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Generate stage-tiered attendance warning letters.

    For each student we compute attendance % over the last
    ``window_days`` days. Students above every stage threshold get no
    letter; everyone else gets a message tagged with the stage label.
    """
    targets = _validate_targets(student_ids)
    try:
        window_days = int(window_days)
    except (TypeError, ValueError):
        raise ValidationError("window_days must be numeric") from None
    if window_days <= 0 or window_days > 365:
        raise ValidationError("window_days must be 1..365")
    tiers = list(stages or DEFAULT_ATTENDANCE_STAGES)
    if not tiers:
        raise ValidationError("At least one stage tier is required")
    # Tiers must be sorted high → low so we pick the *first* match below.
    tiers.sort(key=lambda t: -float(t[0]))

    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance as _att,
    )
    from education_system.systems.sixth_form.domains.communications.domain.messages import (
        messages as _msg,
    )

    end = _dt.date.today()
    start = end - _dt.timedelta(days=window_days)
    df, dt = start.isoformat(), end.isoformat()

    result = BulkResult(operation="attendance_letters",
                        target_count=len(targets))

    # Bucket students by stage.
    by_stage: dict[str, list[tuple[str, float]]] = {}
    for sid in targets:
        try:
            s = _att.summary_for_student(sid, date_from=df, date_to=dt)
            pct = s.percentage
            if pct is None or s.total == 0:
                result.success_ids.append(f"{sid}:no-data")
                continue
            stage_label: str | None = None
            for threshold, label in tiers:
                if pct < threshold:
                    stage_label = label
                else:
                    break
            if stage_label is None:
                result.success_ids.append(f"{sid}:above-thresholds@{pct}%")
                continue
            by_stage.setdefault(stage_label, []).append((sid, pct))
        except Exception as e:  # noqa: BLE001
            result.failures.append((sid, str(e)))

    if dry_run:
        for stage, rows in by_stage.items():
            for sid, pct in rows:
                result.success_ids.append(f"{sid}:{stage}@{pct}%")
        return result

    sent_total = 0
    if send:
        for stage, rows in by_stage.items():
            sids = [r[0] for r in rows]
            subject = f"Attendance — {stage}"
            body = (
                f"This is an automated {stage} attendance letter.\n\n"
                f"Your attendance over the last {window_days} day(s) has "
                f"fallen below the threshold set by the sixth form. Please "
                f"speak to your tutor about steps to improve.\n\n"
                f"This is generated by Bulk Operations."
            )
            try:
                br = _msg.bulk_send(
                    subject=subject, body=body,
                    student_ids=sids,
                    category="Attendance", priority="High",
                    status="Sent",
                    sender_staff_id=sender_staff_id,
                    tags=f"attendance,{stage.lower().replace(' ', '_')}",
                )
                for m in br.created:
                    sid = getattr(m, "student_id", None)
                    if sid:
                        result.success_ids.append(f"{sid}:{stage}-sent")
                        sent_total += 1
                for label, reason in br.failed:
                    result.failures.append((label, reason))
            except Exception as e:  # noqa: BLE001
                for sid in sids:
                    result.failures.append((sid, str(e)))
    else:
        for stage, rows in by_stage.items():
            for sid, pct in rows:
                result.success_ids.append(f"{sid}:{stage}@{pct}%-queued")

    summary_text = (
        f"Attendance letters: {sent_total if send else 0} sent across "
        + ", ".join(f"{s}×{len(v)}" for s, v in by_stage.items())
        + f" ({window_days}-day window)"
    )
    result.job_id = _log_job(
        operation="attendance_letters", summary=summary_text,
        params={"window_days": window_days,
                "stages": [(t, l) for t, l in tiers],
                "send": send, "sent_total": sent_total,
                "buckets": {k: len(v) for k, v in by_stage.items()}},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk punctuality report (to tutors) ────────────────

def bulk_punctuality_report(
    student_ids: list[str],
    *,
    date_from: str,
    date_to: str,
    sender_staff_id: str | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Email each tutor a punctuality breakdown for their tutees.

    For each student we count Late records and the average
    minutes_late in the window. Students are grouped by their current
    tutor group; one message per tutor goes out via the messages
    module to that tutor's staff id (if the tutor group's ``tutor``
    field looks like a staff id). Students without a tutor group are
    surfaced as failures so they don't get silently dropped.
    """
    targets = _validate_targets(student_ids)
    _daterange(date_from, date_to)
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance as _att,
    )
    from education_system.systems.sixth_form.domains.communications.domain.messages import (
        messages as _msg,
    )
    from education_system.systems.sixth_form.domain.pastoral.tutor_groups import (
        tutor_groups as _tg,
    )
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )

    result = BulkResult(operation="punctuality_report",
                        target_count=len(targets))

    # Aggregate per student: total Late + average minutes_late.
    per_student: dict[str, tuple[int, float, str | None]] = {}
    for sid in targets:
        try:
            student = _students.get_student(sid)
            if student is None:
                result.failures.append((sid, "Unknown student"))
                continue
            rows = _att.list_records(
                student_id=sid, status="Late",
                date_from=date_from, date_to=date_to,
            )
            n = len(rows)
            avg = (sum(r.minutes_late or 0 for r in rows) / n) if n else 0.0
            per_student[sid] = (n, round(avg, 1), student.full_name)
        except Exception as e:  # noqa: BLE001
            result.failures.append((sid, str(e)))

    # Group by tutor.
    buckets: dict[str, list[tuple[str, int, float, str]]] = {}
    no_tutor: list[str] = []
    for sid, (lates, avg, name) in per_student.items():
        try:
            grp = _tg.group_for_student(sid)
        except Exception:  # noqa: BLE001
            grp = None
        tutor_id = (grp.tutor if grp else None) or None
        if not tutor_id:
            no_tutor.append(sid)
            continue
        buckets.setdefault(tutor_id, []).append(
            (sid, lates, avg, name or sid))

    if dry_run:
        for tutor, rows in buckets.items():
            result.success_ids.append(
                f"tutor {tutor}: would email {len(rows)} student(s)")
        for sid in no_tutor:
            result.success_ids.append(f"{sid}:no-tutor")
        return result

    sent = 0
    for tutor, rows in buckets.items():
        rows.sort(key=lambda r: (-r[1], r[3]))  # late-count desc, name
        body_lines = [
            f"Punctuality report ({date_from}..{date_to})",
            "",
            f"{'Student':<24} {'Lates':>6} {'Avg min':>9}",
            "-" * 42,
        ]
        for sid, lates, avg, name in rows:
            body_lines.append(f"{(name[:23]):<24} {lates:>6} {avg:>9}")
        body = "\n".join(body_lines)
        try:
            br = _msg.bulk_send(
                subject=f"Punctuality report — {date_from}..{date_to}",
                body=body,
                staff_ids=[tutor],
                category="Attendance", priority="Normal",
                status="Sent",
                sender_staff_id=sender_staff_id,
                tags="punctuality_report",
            )
            for m in br.created:
                sent += 1
                result.success_ids.append(
                    f"tutor {tutor}: {len(rows)} student(s)")
            for label, reason in br.failed:
                result.failures.append((label, reason))
        except Exception as e:  # noqa: BLE001
            result.failures.append((f"tutor {tutor}", str(e)))

    for sid in no_tutor:
        result.failures.append((sid, "Student has no tutor group"))

    summary_text = (
        f"Punctuality report: emailed {sent} tutor(s) covering "
        f"{sum(len(v) for v in buckets.values())} student(s) "
        f"({date_from}..{date_to}); "
        f"{len(no_tutor)} student(s) skipped (no tutor)"
    )
    result.job_id = _log_job(
        operation="punctuality_report", summary=summary_text,
        params={"date_from": date_from, "date_to": date_to,
                "tutors": list(buckets.keys()),
                "no_tutor": no_tutor},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk register closure (lock past registers) ─────────

def bulk_register_closure(
    slot_ids: list[int],
    *,
    date_from: str,
    date_to: str,
    default_status: str = "Present",
    notes: str | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """For each (slot, date) in the window, ensure blanks are filled
    with ``default_status`` and then record a closure row so the
    register is "locked" — :func:`is_register_closed` can be queried
    by other modules before letting a user edit it.
    """
    if not slot_ids:
        raise ValidationError("Pick at least one slot")
    str_targets = _validate_targets([str(s) for s in slot_ids])
    dates = _daterange(date_from, date_to)
    today = _dt.date.today()
    if any(_dt.date.fromisoformat(d) > today for d in dates):
        raise ValidationError(
            "Cannot close registers in the future — pick a date range "
            "that ends on or before today")
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance as _att,
    )
    result = BulkResult(operation="register_closure",
                        target_count=len(str_targets) * len(dates))
    if dry_run:
        for tag in str_targets:
            for date in dates:
                result.success_ids.append(
                    f"slot#{tag} {date}: would close")
        return result
    init_db()
    filled = 0
    closed = 0
    skipped_existing = 0
    for tag in str_targets:
        try:
            slot_id = int(tag)
        except ValueError:
            result.failures.append((tag, "slot_id not numeric"))
            continue
        for date in dates:
            try:
                roster = _att.register_view(slot_id, date)
                missing = {
                    e.student_id: {"status": default_status,
                                   "minutes_late": None,
                                   "notes": "Auto-filled at closure"}
                    for e in roster if e.record is None
                }
                if missing:
                    _att.save_register(slot_id, date, missing)
                    filled += len(missing)
                with _connect() as conn:
                    cur = conn.execute(
                        "INSERT OR IGNORE INTO register_closures "
                        "(slot_id, date, closed_by, notes) "
                        "VALUES (?, ?, ?, ?)",
                        (slot_id, date, ran_by, notes),
                    )
                    conn.commit()
                    if cur.rowcount:
                        closed += 1
                        result.success_ids.append(
                            f"slot#{slot_id} {date}: closed (+{len(missing)})")
                    else:
                        skipped_existing += 1
                        result.success_ids.append(
                            f"slot#{slot_id} {date}: already closed")
            except Exception as e:  # noqa: BLE001
                result.failures.append((f"slot#{tag} {date}", str(e)))
    summary_text = (
        f"Closed {closed} (slot, date) register(s); "
        f"filled {filled} blank entry(ies); "
        f"{skipped_existing} already closed "
        f"({date_from}..{date_to})"
    )
    result.job_id = _log_job(
        operation="register_closure", summary=summary_text,
        params={"date_from": date_from, "date_to": date_to,
                "default_status": default_status,
                "slot_ids": [int(t) for t in str_targets],
                "closed": closed, "filled": filled,
                "skipped_existing": skipped_existing,
                "notes": notes},
        result=result, ran_by=ran_by,
    )
    return result


def is_register_closed(slot_id: int, date: str) -> bool:
    """Lookup helper — has this (slot, date) register been closed?"""
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM register_closures "
            "WHERE slot_id = ? AND date = ?",
            (slot_id, date),
        ).fetchone()
        return row is not None
