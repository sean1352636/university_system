"""Sixth Form bulk operations — behaviour, pastoral, accommodation and
student-field updates.

Split out of ``bulk_operations.py``, which re-exports every name defined here."""

from __future__ import annotations

from typing import Any
import datetime as _dt
from education_system.systems.sixth_form.domain.learners.bulk_operations.base import (
    BulkResult,
    SAFE_STUDENT_FIELDS,
    ValidationError,
    _log_job,
    _validate_targets,
)

# ── Operation: bulk log behaviour ──────────────────────────────────

def bulk_log_behaviour(
    student_ids: list[str],
    *,
    entry_date: str,
    entry_type: str,
    category: str,
    description: str,
    severity: str | None = None,
    points: int = 0,
    location: str | None = None,
    recorded_by: str | None = None,
    action_taken: str | None = None,
    follow_up_required: bool = False,
    parent_contacted: bool = False,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    targets = _validate_targets(student_ids)
    from education_system.systems.sixth_form.domain.pastoral.behaviour import (
        behaviour as _bh,
    )
    result = BulkResult(operation="log_behaviour",
                          target_count=len(targets))
    if dry_run:
        return result
    for sid in targets:
        try:
            _bh.create_entry({
                "student_id":         sid,
                "entry_date":         entry_date,
                "entry_type":         entry_type,
                "category":           category,
                "description":        description,
                "severity":           severity,
                "points":             points,
                "location":           location,
                "recorded_by":        recorded_by,
                "action_taken":       action_taken,
                "follow_up_required": follow_up_required,
                "parent_contacted":   parent_contacted,
            })
            result.success_ids.append(sid)
        except Exception as e:
            result.failures.append((sid, str(e)))
    summary = (f"Logged {entry_type}/{category} behaviour against "
               f"{result.success_count}/{result.target_count} students")
    result.job_id = _log_job(
        operation="log_behaviour", summary=summary,
        params={"entry_date": entry_date, "entry_type": entry_type,
                "category": category, "severity": severity,
                "points": points, "location": location,
                "recorded_by": recorded_by,
                "description": description},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk add accommodation ─────────────────────────────

def bulk_add_accommodation(
    student_ids: list[str],
    *,
    name: str,
    category: str = "Exam Access",
    description: str | None = None,
    status: str = "Active",
    start_date: str | None = None,
    end_date: str | None = None,
    approved_by: str | None = None,
    approved_date: str | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    targets = _validate_targets(student_ids)
    from education_system.systems.sixth_form.domain.pastoral.accessibility import (
        accessibility as _ax,
    )
    result = BulkResult(operation="add_accommodation",
                          target_count=len(targets))
    if dry_run:
        return result
    for sid in targets:
        try:
            _ax.create_accommodation({
                "student_id":    sid,
                "name":          name,
                "category":      category,
                "description":   description,
                "status":        status,
                "start_date":    start_date,
                "end_date":      end_date,
                "approved_by":   approved_by,
                "approved_date": approved_date,
            })
            result.success_ids.append(sid)
        except Exception as e:
            result.failures.append((sid, str(e)))
    summary = (f"Added accommodation {name!r} ({category}) to "
               f"{result.success_count}/{result.target_count} students")
    result.job_id = _log_job(
        operation="add_accommodation", summary=summary,
        params={"name": name, "category": category,
                "status": status, "start_date": start_date,
                "end_date": end_date, "approved_by": approved_by},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk update student field ───────────────────────────

def bulk_update_student(
    student_ids: list[str],
    *,
    field: str,
    value: Any,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    if field not in SAFE_STUDENT_FIELDS:
        raise ValidationError(
            f"Field {field!r} cannot be bulk-updated. "
            f"Allowed: {', '.join(SAFE_STUDENT_FIELDS)}")
    targets = _validate_targets(student_ids)
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    result = BulkResult(operation="update_student",
                          target_count=len(targets))
    if dry_run:
        # Diff preview: surface before→after per student in success_ids.
        from education_system.systems.sixth_form.domain.learners.students import (
            students as _students,
        )
        for sid in targets:
            try:
                existing = _students.get_student(sid)
                if existing is None:
                    result.failures.append(
                        (sid, f"No student with id {sid}"))
                    continue
                before = getattr(existing, field, None)
                if before == value:
                    result.success_ids.append(f"{sid}: (no change)")
                else:
                    result.success_ids.append(
                        f"{sid}: {before!r} → {value!r}")
            except Exception as e:
                result.failures.append((sid, str(e)))
        return result
    for sid in targets:
        try:
            existing = _students.get_student(sid)
            if existing is None:
                raise ValidationError(f"No student with id {sid}")
            # students.update_student re-validates the whole record,
            # so we have to merge the changed field onto the full
            # payload rather than passing a sparse dict.
            payload: dict[str, Any] = {
                "first_name":                 existing.first_name,
                "middle_name":                existing.middle_name,
                "last_name":                  existing.last_name,
                "phone":                      existing.phone,
                "emergency_contact_name":     existing.emergency_contact_name,
                "emergency_contact_phone":    existing.emergency_contact_phone,
                "emergency_contact_relation": existing.emergency_contact_relation,
                "subject_1":                  existing.subject_1,
                "subject_2":                  existing.subject_2,
                "subject_3":                  existing.subject_3,
            }
            payload[field] = value
            _students.update_student(sid, payload)
            result.success_ids.append(sid)
        except Exception as e:
            result.failures.append((sid, str(e)))
    summary = (f"Set {field}={value!r} on "
               f"{result.success_count}/{result.target_count} students")
    result.job_id = _log_job(
        operation="update_student", summary=summary,
        params={"field": field, "value": value},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk issue detentions (behaviour entries) ──────────

def bulk_issue_detentions(
    student_ids: list[str],
    *,
    date: str,
    reason: str,
    duration_minutes: int = 30,
    room: str | None = None,
    severity: str = "Low",
    recorded_by: str | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    targets = _validate_targets(student_ids)
    from education_system.systems.sixth_form.domain.pastoral.behaviour import (
        behaviour as _bh,
    )
    result = BulkResult(operation="issue_detentions",
                         target_count=len(targets))
    if dry_run:
        return result
    desc = (f"Detention ({duration_minutes} min"
            f"{f', {room}' if room else ''}): {reason}")
    for sid in targets:
        try:
            _bh.create_entry({
                "student_id":  sid,
                "entry_date":  date,
                "entry_type":  "Negative",
                "category":    "Other",
                "severity":    severity,
                "description": desc,
                "location":    room,
                "recorded_by": recorded_by,
                "action_taken": (f"Detention scheduled "
                                  f"({duration_minutes} min)"),
                "follow_up_required": True,
            })
            result.success_ids.append(sid)
        except Exception as e:
            result.failures.append((sid, str(e)))
    summary_text = (f"Issued detentions to "
                    f"{result.success_count}/{result.target_count} students "
                    f"on {date}")
    result.job_id = _log_job(
        operation="issue_detentions", summary=summary_text,
        params={"date": date, "reason": reason,
                "duration_minutes": duration_minutes,
                "room": room, "severity": severity},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk award merits / house points ───────────────────

def bulk_award_merits(
    student_ids: list[str],
    *,
    date: str,
    category: str = "Achievement",
    description: str,
    points: int = 5,
    recorded_by: str | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    targets = _validate_targets(student_ids)
    from education_system.systems.sixth_form.domain.pastoral.behaviour import (
        behaviour as _bh,
    )
    result = BulkResult(operation="award_merits",
                         target_count=len(targets))
    if dry_run:
        return result
    for sid in targets:
        try:
            _bh.create_entry({
                "student_id":  sid,
                "entry_date":  date,
                "entry_type":  "Positive",
                "category":    category,
                "description": description,
                "points":      int(points),
                "recorded_by": recorded_by,
            })
            result.success_ids.append(sid)
        except Exception as e:
            result.failures.append((sid, str(e)))
    summary_text = (f"Awarded {points} merit(s) to "
                    f"{result.success_count}/{result.target_count} "
                    f"students ({category})")
    result.job_id = _log_job(
        operation="award_merits", summary=summary_text,
        params={"date": date, "category": category,
                "points": points, "description": description},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk escalate behaviour ────────────────────────────

def bulk_escalate_behaviour(
    student_ids: list[str],
    *,
    date: str,
    reason: str,
    escalate_to: str = "Senior Tutor",
    follow_up_date: str | None = None,
    recorded_by: str | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Log an escalation entry (negative, High severity) per student."""
    targets = _validate_targets(student_ids)
    from education_system.systems.sixth_form.domain.pastoral.behaviour import (
        behaviour as _bh,
    )
    result = BulkResult(operation="escalate_behaviour",
                         target_count=len(targets))
    if dry_run:
        return result
    for sid in targets:
        try:
            _bh.create_entry({
                "student_id":  sid,
                "entry_date":  date,
                "entry_type":  "Negative",
                "category":    "Other",
                "severity":    "High",
                "description": f"Escalated to {escalate_to}: {reason}",
                "action_taken": f"Escalated to {escalate_to}",
                "follow_up_required": True,
                "follow_up_date": follow_up_date,
                "parent_contacted": True,
                "recorded_by": recorded_by,
            })
            result.success_ids.append(sid)
        except Exception as e:
            result.failures.append((sid, str(e)))
    summary_text = (f"Escalated {result.success_count}/"
                    f"{result.target_count} students to {escalate_to}")
    result.job_id = _log_job(
        operation="escalate_behaviour", summary=summary_text,
        params={"date": date, "reason": reason,
                "escalate_to": escalate_to,
                "follow_up_date": follow_up_date},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk safeguarding flag ─────────────────────────────

def bulk_safeguarding_flag(
    student_ids: list[str],
    *,
    concern_date: str,
    reported_date: str,
    concern_type: str,
    category: str,
    risk_level: str,
    reported_by: str,
    description: str,
    dsl_notified: bool = False,
    dsl_name: str | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    targets = _validate_targets(student_ids)
    from education_system.systems.sixth_form.domain.safeguarding import (
        safeguarding as _sg,
    )
    result = BulkResult(operation="safeguarding_flag",
                         target_count=len(targets))
    if dry_run:
        return result
    for sid in targets:
        try:
            _sg.create_concern({
                "student_id":   sid,
                "concern_date": concern_date,
                "reported_date": reported_date,
                "concern_type": concern_type,
                "category":     category,
                "risk_level":   risk_level,
                "reported_by":  reported_by,
                "description":  description,
                "dsl_notified": dsl_notified,
                "dsl_name":     dsl_name,
                "dsl_notified_at": (reported_date if dsl_notified else None),
            })
            result.success_ids.append(sid)
        except Exception as e:
            result.failures.append((sid, str(e)))
    summary_text = (
        f"Opened safeguarding concern for "
        f"{result.success_count}/{result.target_count} students "
        f"({category}, risk={risk_level})"
    )
    result.job_id = _log_job(
        operation="safeguarding_flag", summary=summary_text,
        params={"concern_date": concern_date,
                "reported_date": reported_date,
                "concern_type": concern_type, "category": category,
                "risk_level": risk_level, "reported_by": reported_by,
                "dsl_notified": dsl_notified},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk assign mentors ────────────────────────────────

def bulk_assign_mentors(
    mentee_ids: list[str],
    *,
    mentor_id: str,
    programme: str,
    start_date: str,
    frequency: str = "Weekly",
    coordinator: str | None = None,
    planned_end: str | None = None,
    sessions_planned: int | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Pair one mentor with many mentees (one ``peer_mentoring`` row each)."""
    targets = _validate_targets(mentee_ids)
    mentor_id = (mentor_id or "").strip()
    if not mentor_id:
        raise ValidationError("mentor_id is required")
    if mentor_id in targets:
        raise ValidationError("Mentor cannot be in the mentee list")
    from education_system.systems.sixth_form.domain.pastoral.peer_mentoring import (
        peer_mentoring as _pm,
    )
    result = BulkResult(operation="assign_mentors",
                         target_count=len(targets))
    if dry_run:
        return result
    for sid in targets:
        try:
            _pm.create_pairing({
                "mentor_id":   mentor_id,
                "mentee_id":   sid,
                "programme":   programme,
                "frequency":   frequency,
                "start_date":  start_date,
                "planned_end": planned_end,
                "sessions_planned": sessions_planned,
                "coordinator": coordinator,
            })
            result.success_ids.append(sid)
        except Exception as e:
            result.failures.append((sid, str(e)))
    summary_text = (
        f"Paired mentor {mentor_id} with "
        f"{result.success_count}/{result.target_count} mentee(s) "
        f"({programme})"
    )
    result.job_id = _log_job(
        operation="assign_mentors", summary=summary_text,
        params={"mentor_id": mentor_id, "programme": programme,
                "frequency": frequency, "start_date": start_date,
                "planned_end": planned_end,
                "sessions_planned": sessions_planned,
                "coordinator": coordinator},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: reset behaviour points (term roll-over) ────────────

def bulk_reset_behaviour_points(
    student_ids: list[str],
    *,
    date_from: str,
    date_to: str,
    reset_date: str | None = None,
    note: str = "Term reset",
    recorded_by: str | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """For each student, compute net behaviour points over the window
    and log a single counter entry that zeroes them out."""
    targets = _validate_targets(student_ids)
    from education_system.systems.sixth_form.domain.pastoral.behaviour import (
        behaviour as _bh,
    )
    reset_date = reset_date or _dt.date.today().isoformat()
    result = BulkResult(operation="reset_behaviour_points",
                         target_count=len(targets))
    if dry_run:
        return result
    adjustments: list[tuple[str, int]] = []
    for sid in targets:
        try:
            entries = _bh.list_entries(student_id=sid)
            net = 0
            for e in entries:
                d = e.entry_date
                if d and date_from <= d <= date_to:
                    net += (e.points or 0)
            if net == 0:
                result.success_ids.append(f"{sid}:already-zero")
                continue
            offset = -net
            etype = "Positive" if offset > 0 else "Negative"
            cat = ("Other" if etype == "Negative"
                   else "Other")
            severity = ("Low" if etype == "Negative" else None)
            _bh.create_entry({
                "student_id":  sid,
                "entry_date":  reset_date,
                "entry_type":  etype,
                "category":    cat,
                "severity":    severity,
                "description": f"{note} ({date_from}..{date_to}): "
                               f"net={net} → offset={offset}",
                "points":      offset,
                "recorded_by": recorded_by,
            })
            adjustments.append((sid, offset))
            result.success_ids.append(f"{sid}:{offset:+d}")
        except Exception as e:
            result.failures.append((sid, str(e)))
    summary_text = (f"Reset behaviour points for "
                    f"{result.success_count}/{result.target_count} "
                    f"students ({date_from}..{date_to})")
    result.job_id = _log_job(
        operation="reset_behaviour_points", summary=summary_text,
        params={"date_from": date_from, "date_to": date_to,
                "reset_date": reset_date, "note": note,
                "adjustments": adjustments},
        result=result, ran_by=ran_by,
    )
    return result
