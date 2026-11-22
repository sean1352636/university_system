"""Sixth Form bulk operations — records: exams, UCAS, year/lifecycle changes,
alumni, GDPR, exports, inventory, photos, contacts, password resets, undo,
recurring schedules and the summary.

Split out of ``bulk_operations.py``, which re-exports every name defined here."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import datetime as _dt
import json
from education_system.systems.sixth_form.infrastructure import database as db
from education_system.systems.sixth_form.domain.learners.bulk_operations.base import (
    BulkResult,
    OPERATIONS,
    Summary,
    ValidationError,
    _connect,
    _log_job,
    _validate_targets,
    get_job,
    init_db,
)
from education_system.systems.sixth_form.domain.learners.bulk_operations.ops_behaviour import (
    bulk_add_accommodation,
)

# ── Operation: bulk archive to alumni ─────────────────────────────

def bulk_archive_to_alumni(
    student_ids: list[str],
    *,
    leaving_year: str | None = None,
    leaving_date: str | None = None,
    leaving_reason: str | None = None,
    destination_type: str = "Unknown",
    delete_students: bool = False,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    targets = _validate_targets(student_ids)
    from education_system.systems.sixth_form.domain.learners.alumni import records as alumni_records
    result = BulkResult(operation="archive_to_alumni",
                          target_count=len(targets))
    if dry_run:
        return result
    for sid in targets:
        try:
            alumni_records.archive_student(
                sid,
                leaving_year=leaving_year,
                leaving_date=leaving_date,
                leaving_reason=leaving_reason,
                destination_type=destination_type,
                delete_student=delete_students,
            )
            result.success_ids.append(sid)
        except Exception as e:
            result.failures.append((sid, str(e)))
    summary = (f"Archived {result.success_count}/{result.target_count} "
               f"students → alumni (year={leaving_year or 'auto'}, "
               f"delete={delete_students})")
    result.job_id = _log_job(
        operation="archive_to_alumni", summary=summary,
        params={"leaving_year": leaving_year,
                "leaving_date": leaving_date,
                "leaving_reason": leaving_reason,
                "destination_type": destination_type,
                "delete_students": delete_students},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk exam entries ──────────────────────────────────

def bulk_exam_entries(
    student_ids: list[str],
    *,
    subject: str,
    exam_board: str,
    paper_code: str,
    season: str,
    year: int,
    tier: str | None = None,
    fee: float | None = None,
    candidate_no_prefix: str | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Create an exam entry per student. ``candidate_no_prefix`` (if
    set) is followed by a 4-digit zero-padded index."""
    targets = _validate_targets(student_ids)
    from education_system.systems.sixth_form.domain.assessment.exam_entries import (
        exam_entries as _ee,
    )
    result = BulkResult(operation="exam_entries",
                         target_count=len(targets))
    if dry_run:
        return result
    for idx, sid in enumerate(targets, start=1):
        try:
            candidate_no = None
            if candidate_no_prefix:
                candidate_no = f"{candidate_no_prefix}{idx:04d}"
            _ee.create_entry({
                "student_id":   sid,
                "subject":      subject,
                "exam_board":   exam_board,
                "paper_code":   paper_code,
                "season":       season,
                "year":         year,
                "tier":         tier,
                "fee":          fee,
                "candidate_no": candidate_no,
                "status":       "Entered",
            })
            result.success_ids.append(
                f"{sid}{f':{candidate_no}' if candidate_no else ''}")
        except Exception as e:
            result.failures.append((sid, str(e)))
    summary_text = (
        f"Entered {result.success_count}/{result.target_count} students "
        f"for {subject} {paper_code} ({exam_board} {season} {year})"
    )
    result.job_id = _log_job(
        operation="exam_entries", summary=summary_text,
        params={"subject": subject, "exam_board": exam_board,
                "paper_code": paper_code, "season": season,
                "year": year, "tier": tier, "fee": fee,
                "candidate_no_prefix": candidate_no_prefix},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk exam access arrangements ──────────────────────

def bulk_exam_access_arrangements(
    student_ids: list[str],
    *,
    arrangement: str,
    description: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    approved_by: str | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Convenience wrapper around add_accommodation with
    category='Exam Access' for arrangements like '25% Extra Time',
    'Scribe', 'Reader', 'Rest Breaks'."""
    return bulk_add_accommodation(
        student_ids,
        name=arrangement, category="Exam Access",
        description=description, status="Active",
        start_date=start_date, end_date=end_date,
        approved_by=approved_by, ran_by=ran_by,
        dry_run=dry_run,
    )


# ── Operation: bulk export exam timetables (text) ─────────────────

def bulk_export_exam_timetables(
    student_ids: list[str],
    *,
    output_dir: str,
    year: int | None = None,
    season: str | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    import os
    targets = _validate_targets(student_ids)
    if not output_dir:
        raise ValidationError("output_dir is required")
    if not dry_run:
        os.makedirs(output_dir, exist_ok=True)
    from education_system.systems.sixth_form.domain.assessment.exam_entries import (
        exam_entries as _ee,
    )
    result = BulkResult(operation="exam_timetables",
                         target_count=len(targets))
    if dry_run:
        return result
    for sid in targets:
        try:
            entries = _ee.entries_for_student(sid)
            if year is not None:
                entries = [e for e in entries if e.year == year]
            if season:
                entries = [e for e in entries if e.season == season]
            lines = [
                f"Exam timetable — {sid}",
                f"Year: {year or 'All'} · Season: {season or 'All'}",
                f"Generated: {_dt.datetime.now().isoformat(sep=' ', timespec='seconds')}",
                "",
            ]
            for e in entries:
                lines.append(
                    f"  {e.year} {e.season:<8} "
                    f"{e.exam_board:<8} "
                    f"{e.paper_code:<12} "
                    f"{e.subject}  [{e.status}]"
                )
            path = os.path.join(output_dir, f"exams_{sid}.txt")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("\n".join(lines) + "\n")
            result.success_ids.append(f"{sid}:{path}")
        except Exception as e:
            result.failures.append((sid, str(e)))
    summary_text = (f"Wrote {result.success_count}/{result.target_count} "
                    f"exam timetables to {output_dir}")
    result.job_id = _log_job(
        operation="exam_timetables", summary=summary_text,
        params={"output_dir": output_dir, "year": year,
                "season": season},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: UCAS export predictions ────────────────────────────

def bulk_ucas_export_predictions(
    student_ids: list[str],
    *,
    output_path: str,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Write one CSV row per (student, subject, predicted-grade) for
    selected students. Output format is the columns UCAS bulk-loaders
    accept: student_id, subject, grade, confidence."""
    import csv as _csv
    import os
    targets = _validate_targets(student_ids)
    if not output_path:
        raise ValidationError("output_path is required")
    from education_system.systems.sixth_form.domain.assessment.predicted_grades import (
        predicted_grades as _pred,
    )
    result = BulkResult(operation="ucas_export_predictions",
                         target_count=len(targets))
    if dry_run:
        return result
    rows_written = 0
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8", newline="") as fh:
        w = _csv.writer(fh)
        w.writerow(["student_id", "subject", "grade", "confidence"])
        for sid in targets:
            try:
                preds = _pred.predictions_for_student(sid)
                for p in preds:
                    w.writerow([sid, p.subject, p.grade, p.confidence])
                    rows_written += 1
                result.success_ids.append(f"{sid}:{len(preds)}")
            except Exception as e:
                result.failures.append((sid, str(e)))
    summary_text = (f"Exported {rows_written} prediction row(s) for "
                    f"{result.success_count}/{result.target_count} "
                    f"students → {output_path}")
    result.job_id = _log_job(
        operation="ucas_export_predictions", summary=summary_text,
        params={"output_path": output_path,
                "rows_written": rows_written},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: UCAS update application status ─────────────────────

def bulk_ucas_update_status(
    student_ids: list[str],
    *,
    status: str,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Update each student's UCAS application to the given app status."""
    targets = _validate_targets(student_ids)
    from education_system.systems.sixth_form.domain.progression.university import ucas as _ucas
    if status not in _ucas.APP_STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(_ucas.APP_STATUSES)}")
    result = BulkResult(operation="ucas_update_status",
                         target_count=len(targets))
    if dry_run:
        return result
    for sid in targets:
        try:
            app = _ucas.get_application_for_student(sid)
            if app is None:
                raise ValidationError("No UCAS application")
            _ucas.update_application(app.application_id, {"status": status})
            result.success_ids.append(f"{sid}:app#{app.application_id}")
        except Exception as e:
            result.failures.append((sid, str(e)))
    summary_text = (f"Set UCAS status={status} on "
                    f"{result.success_count}/{result.target_count} apps")
    result.job_id = _log_job(
        operation="ucas_update_status", summary=summary_text,
        params={"status": status}, result=result, ran_by=ran_by,
    )
    return result


# ── Operation: promote year group ─────────────────────────────────

def bulk_promote_year_group(
    student_ids: list[str],
    *,
    new_academic_year: str,
    bump_year_group: bool = True,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Create a new enrolment row for each student in the next academic
    year. If ``bump_year_group`` is True, year_group goes up by one
    (clamped to a max of 13)."""
    targets = _validate_targets(student_ids)
    from education_system.systems.sixth_form.domain.admissions.enrolments import (
        enrolments as _en,
    )
    result = BulkResult(operation="promote_year_group",
                         target_count=len(targets))
    if dry_run:
        for sid in targets:
            try:
                cur = _en.list_for_student(sid)
                if not cur:
                    result.failures.append((sid, "No prior enrolment"))
                    continue
                latest = cur[0]
                new_yg = (min(latest.year_group + 1, 13)
                          if bump_year_group else latest.year_group)
                result.success_ids.append(
                    f"{sid}: Y{latest.year_group} → Y{new_yg} "
                    f"({new_academic_year})")
            except Exception as e:
                result.failures.append((sid, str(e)))
        return result
    for sid in targets:
        try:
            current = _en.list_for_student(sid)
            if not current:
                raise ValidationError("No prior enrolment")
            latest = current[0]  # list is ordered most-recent first
            new_yg = (min(latest.year_group + 1, 13)
                      if bump_year_group else latest.year_group)
            _en.create_enrolment({
                "student_id":    sid,
                "academic_year": new_academic_year,
                "year_group":    new_yg,
                "tutor_group":   latest.tutor_group,
                "start_date":    _dt.date.today().isoformat(),
                "status":        "Enrolled",
            })
            result.success_ids.append(f"{sid}:Y{latest.year_group}→Y{new_yg}")
        except Exception as e:
            result.failures.append((sid, str(e)))
    summary_text = (f"Promoted {result.success_count}/"
                    f"{result.target_count} students into "
                    f"{new_academic_year}")
    result.job_id = _log_job(
        operation="promote_year_group", summary=summary_text,
        params={"new_academic_year": new_academic_year,
                "bump_year_group": bump_year_group},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: mark leavers (Withdrawn) ───────────────────────────

def bulk_mark_leavers(
    student_ids: list[str],
    *,
    leaving_date: str,
    leaving_reason: str | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Flag students as Withdrawn on their most-recent enrolment row,
    without archiving them to alumni."""
    targets = _validate_targets(student_ids)
    from education_system.systems.sixth_form.domain.admissions.enrolments import (
        enrolments as _en,
    )
    result = BulkResult(operation="mark_leavers",
                         target_count=len(targets))
    if dry_run:
        for sid in targets:
            try:
                rows = _en.list_for_student(sid)
                if not rows:
                    result.failures.append(
                        (sid, "No enrolment to update"))
                    continue
                latest = rows[0]
                result.success_ids.append(
                    f"{sid}: {latest.status} → Withdrawn "
                    f"(left {leaving_date})")
            except Exception as e:
                result.failures.append((sid, str(e)))
        return result
    note_base = (f"Left {leaving_date}"
                 + (f": {leaving_reason}" if leaving_reason else ""))
    for sid in targets:
        try:
            rows = _en.list_for_student(sid)
            if not rows:
                raise ValidationError("No enrolment to update")
            latest = rows[0]
            _en.update_enrolment(latest.enrolment_id, {
                "academic_year": latest.academic_year,
                "year_group":    latest.year_group,
                "tutor_group":   latest.tutor_group,
                "start_date":    latest.start_date,
                "status":        "Withdrawn",
                "notes":         ((latest.notes + " | " + note_base)
                                   if latest.notes else note_base),
            })
            result.success_ids.append(sid)
        except Exception as e:
            result.failures.append((sid, str(e)))
    summary_text = (f"Marked {result.success_count}/{result.target_count} "
                    f"students Withdrawn ({leaving_date})")
    result.job_id = _log_job(
        operation="mark_leavers", summary=summary_text,
        params={"leaving_date": leaving_date,
                "leaving_reason": leaving_reason},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: reinstate alumni → active student ──────────────────

def bulk_reinstate_alumni(
    alumni_ids: list[int],
    *,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Delete alumni rows and (if the student row was also removed)
    recreate a minimal students row from the alumnus's stored fields."""
    if not alumni_ids:
        raise ValidationError("Pick at least one alumnus")
    str_targets = _validate_targets([str(a_) for a_ in alumni_ids])
    from education_system.systems.sixth_form.domain.learners.alumni import (
        compliance as alumni_compliance,
        records as alumni_records,
    )
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    result = BulkResult(operation="reinstate_alumni",
                         target_count=len(str_targets))
    if dry_run:
        return result
    for tag in str_targets:
        try:
            aid = int(tag)
            alum = alumni_records.get_alumnus(aid)
            if alum is None:
                raise ValidationError(f"No alumnus #{aid}")
            sid = alum.original_student_id
            if sid and _students.get_student(sid) is None:
                # Recreate minimum-viable student row.
                _students.create_student(allow_duplicate=True, data={
                    "first_name": alum.first_name,
                    "last_name":  alum.last_name,
                    "subject_1":  "Mathematics",
                    "subject_2":  "Biology",
                    "subject_3":  "Chemistry",
                })
            alumni_records.delete_alumnus(aid) if hasattr(alumni_records, "delete_alumnus") \
                else alumni_compliance.anonymise_alumnus(aid)
            result.success_ids.append(f"alum#{aid}→{sid or 'new'}")
        except Exception as e:
            result.failures.append((tag, str(e)))
    summary_text = (f"Reinstated {result.success_count}/"
                    f"{result.target_count} alumni")
    result.job_id = _log_job(
        operation="reinstate_alumni", summary=summary_text,
        params={"alumni_ids": [int(t) for t in str_targets]},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: GDPR redact PII fields on students ─────────────────

def bulk_gdpr_redact(
    student_ids: list[str],
    *,
    fields: list[str] | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Clear personal data from selected students. Default fields:
    ``phone, personal_email, emergency_contact_*``."""
    targets = _validate_targets(student_ids)
    default_fields = ["phone", "personal_email",
                      "emergency_contact_name",
                      "emergency_contact_phone",
                      "emergency_contact_relation"]
    fields = fields or default_fields
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    result = BulkResult(operation="gdpr_redact",
                         target_count=len(targets))
    if dry_run:
        return result
    for sid in targets:
        try:
            existing = _students.get_student(sid)
            if existing is None:
                raise ValidationError(f"No student with id {sid}")
            payload = {
                "first_name":  existing.first_name,
                "middle_name": existing.middle_name,
                "last_name":   existing.last_name,
                "phone":       existing.phone,
                "personal_email": getattr(existing, "personal_email",
                                            None),
                "emergency_contact_name":     existing.emergency_contact_name,
                "emergency_contact_phone":    existing.emergency_contact_phone,
                "emergency_contact_relation": existing.emergency_contact_relation,
                "subject_1": existing.subject_1,
                "subject_2": existing.subject_2,
                "subject_3": existing.subject_3,
            }
            for f in fields:
                if f in payload:
                    payload[f] = None
            _students.update_student(sid, payload)
            result.success_ids.append(sid)
        except Exception as e:
            result.failures.append((sid, str(e)))
    summary_text = (f"Redacted {', '.join(fields)} on "
                    f"{result.success_count}/{result.target_count} students")
    result.job_id = _log_job(
        operation="gdpr_redact", summary=summary_text,
        params={"fields": fields}, result=result, ran_by=ran_by,
    )
    return result


# ── Operation: export student records CSV ─────────────────────────

def bulk_export_student_records(
    student_ids: list[str],
    *,
    output_path: str,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Write one CSV row per student with their core record fields."""
    import csv as _csv
    import os
    targets = _validate_targets(student_ids)
    if not output_path:
        raise ValidationError("output_path is required")
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    result = BulkResult(operation="export_student_records",
                         target_count=len(targets))
    if dry_run:
        return result
    cols = ["student_id", "first_name", "middle_name", "last_name",
            "email", "phone",
            "emergency_contact_name", "emergency_contact_phone",
            "emergency_contact_relation",
            "subject_1", "subject_2", "subject_3"]
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8", newline="") as fh:
        w = _csv.writer(fh)
        w.writerow(cols)
        for sid in targets:
            try:
                st = _students.get_student(sid)
                if st is None:
                    raise ValidationError("Not found")
                w.writerow([getattr(st, c, "") or "" for c in cols])
                result.success_ids.append(sid)
            except Exception as e:
                result.failures.append((sid, str(e)))
    summary_text = (f"Exported {result.success_count}/{result.target_count} "
                    f"student records → {output_path}")
    result.job_id = _log_job(
        operation="export_student_records", summary=summary_text,
        params={"output_path": output_path},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: anonymise alumni ───────────────────────────────────

def bulk_anonymise_alumni(
    alumni_ids: list[int],
    *,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    if not alumni_ids:
        raise ValidationError("Pick at least one alumnus")
    str_targets = _validate_targets([str(a_) for a_ in alumni_ids])
    from education_system.systems.sixth_form.domain.learners.alumni import (
        compliance as alumni_compliance,
    )
    result = BulkResult(operation="anonymise_alumni",
                         target_count=len(str_targets))
    if dry_run:
        return result
    for tag in str_targets:
        try:
            alumni_compliance.anonymise_alumnus(int(tag))
            result.success_ids.append(f"alum#{tag}")
        except Exception as e:
            result.failures.append((tag, str(e)))
    summary_text = (f"Anonymised {result.success_count}/"
                    f"{result.target_count} alumni")
    result.job_id = _log_job(
        operation="anonymise_alumni", summary=summary_text,
        params={"alumni_ids": [int(t) for t in str_targets]},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: assign inventory (locker / library card / ID) ──────

VALID_INVENTORY_KINDS: tuple[str, ...] = (
    "Locker", "Library Card", "ID Badge", "Bus Pass", "Other",
)


def bulk_assign_inventory(
    student_ids: list[str],
    *,
    kind: str,
    starting_number: int = 1,
    prefix: str = "",
    pad: int = 4,
    assigned_by: str | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Assign sequential inventory numbers (lockers, badges, etc.) to
    selected students. Numbers are zero-padded to ``pad`` digits."""
    targets = _validate_targets(student_ids)
    if kind not in VALID_INVENTORY_KINDS:
        raise ValidationError(
            f"kind must be one of: {', '.join(VALID_INVENTORY_KINDS)}")
    init_db()
    result = BulkResult(operation="assign_inventory",
                         target_count=len(targets))
    if dry_run:
        return result
    with _connect() as conn:
        for i, sid in enumerate(targets):
            try:
                ident = f"{prefix}{starting_number + i:0{pad}d}"
                conn.execute(
                    """INSERT INTO student_inventory
                          (student_id, kind, identifier, assigned_by)
                       VALUES (?, ?, ?, ?)""",
                    (sid, kind, ident, assigned_by),
                )
                result.success_ids.append(f"{sid}:{ident}")
            except Exception as e:
                result.failures.append((sid, str(e)))
        conn.commit()
    summary_text = (f"Assigned {result.success_count}/{result.target_count} "
                    f"{kind} numbers")
    result.job_id = _log_job(
        operation="assign_inventory", summary=summary_text,
        params={"kind": kind, "starting_number": starting_number,
                "prefix": prefix, "pad": pad},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: upload photos (ZIP, matched by student_id) ─────────

def bulk_upload_photos(
    zip_path: str,
    *,
    output_dir: str,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Extract image files named ``<student_id>.<ext>`` from a ZIP and
    copy each to ``output_dir/<student_id>.<ext>``. Only files matching
    an existing student id are accepted."""
    import os
    import zipfile
    if not zip_path or not os.path.isfile(zip_path):
        raise ValidationError(f"ZIP not found: {zip_path}")
    if not output_dir:
        raise ValidationError("output_dir is required")
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    valid_ids = {s.student_id for s in _students.list_students()}
    with zipfile.ZipFile(zip_path) as zf:
        names = [n for n in zf.namelist() if not n.endswith("/")]
        result = BulkResult(operation="upload_photos",
                             target_count=len(names))
        if dry_run:
            return result
        os.makedirs(output_dir, exist_ok=True)
        for name in names:
            try:
                base = os.path.basename(name)
                root, ext = os.path.splitext(base)
                if not ext:
                    raise ValidationError("no file extension")
                if root not in valid_ids:
                    raise ValidationError(f"unknown student id {root}")
                target = os.path.join(output_dir, base)
                with zf.open(name) as src, open(target, "wb") as dst:
                    dst.write(src.read())
                result.success_ids.append(f"{root}:{target}")
            except Exception as e:
                result.failures.append((name, str(e)))
    summary_text = (f"Uploaded {result.success_count}/{result.target_count} "
                    f"photos from {os.path.basename(zip_path)}")
    result.job_id = _log_job(
        operation="upload_photos", summary=summary_text,
        params={"zip_path": zip_path, "output_dir": output_dir},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: import emergency contacts CSV ──────────────────────

def bulk_import_contacts_csv(
    csv_path: str,
    *,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Update student emergency-contact fields from a CSV. Required:
    ``student_id``. Optional: ``phone, emergency_contact_name,
    emergency_contact_phone, emergency_contact_relation``."""
    import csv as _csv
    import os
    if not csv_path or not os.path.isfile(csv_path):
        raise ValidationError(f"CSV not found: {csv_path}")
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    rows: list[dict[str, str]] = []
    with open(csv_path, encoding="utf-8-sig", newline="") as fh:
        reader = _csv.DictReader(fh)
        if "student_id" not in (reader.fieldnames or []):
            raise ValidationError("CSV must have student_id column")
        for r in reader:
            rows.append({k: (v or "").strip() for k, v in r.items()})
    result = BulkResult(operation="import_contacts_csv",
                         target_count=len(rows))
    if dry_run:
        return result
    editable = ("phone", "emergency_contact_name",
                "emergency_contact_phone",
                "emergency_contact_relation")
    for i, r in enumerate(rows, start=2):
        sid = r.get("student_id", "")
        try:
            existing = _students.get_student(sid)
            if existing is None:
                raise ValidationError(f"No student with id {sid}")
            payload = {
                "first_name":  existing.first_name,
                "middle_name": existing.middle_name,
                "last_name":   existing.last_name,
                "phone":       existing.phone,
                "emergency_contact_name":     existing.emergency_contact_name,
                "emergency_contact_phone":    existing.emergency_contact_phone,
                "emergency_contact_relation": existing.emergency_contact_relation,
                "subject_1": existing.subject_1,
                "subject_2": existing.subject_2,
                "subject_3": existing.subject_3,
            }
            for k in editable:
                if k in r and r[k]:
                    payload[k] = r[k]
            _students.update_student(sid, payload)
            result.success_ids.append(f"L{i}:{sid}")
        except Exception as e:
            result.failures.append((f"L{i}:{sid}", str(e)))
    summary_text = (f"Updated contacts for "
                    f"{result.success_count}/{result.target_count} "
                    f"students from {os.path.basename(csv_path)}")
    result.job_id = _log_job(
        operation="import_contacts_csv", summary=summary_text,
        params={"csv_path": csv_path},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: force-password-reset flag ──────────────────────────

def bulk_force_password_reset(
    student_ids: list[str],
    *,
    reason: str | None = None,
    flagged_by: str | None = None,
    clear: bool = False,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Flag selected students so they must change their password on
    next login. If ``clear`` is True the flag is removed."""
    targets = _validate_targets(student_ids)
    init_db()
    result = BulkResult(operation="force_password_reset",
                         target_count=len(targets))
    if dry_run:
        return result
    with _connect() as conn:
        for sid in targets:
            try:
                if clear:
                    conn.execute(
                        "DELETE FROM password_reset_required "
                        "WHERE student_id = ?", (sid,))
                else:
                    conn.execute(
                        """INSERT INTO password_reset_required
                              (student_id, flagged_by, reason)
                           VALUES (?, ?, ?)
                           ON CONFLICT(student_id) DO UPDATE SET
                              flagged_at = datetime('now'),
                              flagged_by = excluded.flagged_by,
                              reason = excluded.reason""",
                        (sid, flagged_by, reason))
                result.success_ids.append(sid)
            except Exception as e:
                result.failures.append((sid, str(e)))
        conn.commit()
    word = "Cleared" if clear else "Flagged"
    summary_text = (f"{word} force-password-reset on "
                    f"{result.success_count}/{result.target_count} students")
    result.job_id = _log_job(
        operation="force_password_reset", summary=summary_text,
        params={"reason": reason, "clear": clear,
                "flagged_by": flagged_by},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: undo job (best-effort compensating action) ─────────

_UNDOABLE: tuple[str, ...] = (
    "log_behaviour", "mark_attendance", "apply_lateness",
    "issue_detentions", "award_merits", "escalate_behaviour",
    "publish_report_cards", "assign_inventory",
    "force_password_reset",
)


def bulk_undo_job(
    target_job_id: int,
    *,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Roll back side-effects of a previous job. Supported only for
    ops in ``_UNDOABLE``; for any other operation a single failure is
    recorded."""
    job = get_job(target_job_id)
    if job is None:
        raise ValidationError(f"No job #{target_job_id}")
    result = BulkResult(operation="undo_job",
                         target_count=job.target_count)
    if job.operation not in _UNDOABLE:
        result.failures.append(
            (str(target_job_id),
             f"Operation {job.operation!r} is not undoable"))
        if not dry_run:
            result.job_id = _log_job(
                operation="undo_job",
                summary=f"Attempted undo of job #{target_job_id} "
                        f"({job.operation}) — not undoable",
                params={"target_job_id": target_job_id,
                        "operation": job.operation},
                result=result, ran_by=ran_by)
        return result
    if dry_run:
        return result

    sids = [sid for sid in job.success_ids
            if isinstance(sid, str) and ":" not in sid
            and not sid.startswith("L")]
    op = job.operation
    # ran_at +/- a small window around when side-effects were created.
    ts = job.ran_at  # "YYYY-MM-DD HH:MM:SS"
    removed = 0
    try:
        if op in ("log_behaviour", "issue_detentions", "award_merits",
                   "escalate_behaviour", "apply_lateness"):
            from education_system.systems.sixth_form.infrastructure import database as _sq
            from education_system.systems.sixth_form.domain.pastoral.behaviour import (
                behaviour as _bh,
            )
            _bh.init_db()
            with _sq.connect(str(_bh.DB_PATH)) as conn:
                for sid in sids:
                    cur = conn.execute(
                        "DELETE FROM behaviour_entries "
                        "WHERE student_id = ? "
                        "AND datetime(created_at) "
                        "    BETWEEN datetime(?) "
                        "        AND datetime(?, '+10 seconds')",
                        (sid, ts, ts))
                    removed += cur.rowcount
                    result.success_ids.append(f"{sid}:−{cur.rowcount}")
                conn.commit()
        elif op == "mark_attendance":
            from education_system.systems.sixth_form.domain.academics.attendance import (
                attendance as _att,
            )
            slot_id = job.parameters.get("slot_id")
            date = job.parameters.get("date")
            for sid in sids:
                rows = _att.list_records(
                    student_id=sid, slot_id=slot_id, date=date)
                for r in rows:
                    if _att.delete_record(r.record_id):
                        removed += 1
                result.success_ids.append(f"{sid}:−{len(rows)}")
        elif op == "publish_report_cards":
            init_db()
            period = job.parameters.get("period")
            with _connect() as conn:
                for sid in sids:
                    cur = conn.execute(
                        "DELETE FROM report_card_publications "
                        "WHERE student_id = ? AND period = ?",
                        (sid, period))
                    removed += cur.rowcount
                    result.success_ids.append(f"{sid}:−{cur.rowcount}")
                conn.commit()
        elif op == "assign_inventory":
            init_db()
            with _connect() as conn:
                for entry in job.success_ids:
                    if ":" not in entry:
                        continue
                    sid, ident = entry.split(":", 1)
                    cur = conn.execute(
                        "DELETE FROM student_inventory "
                        "WHERE student_id = ? AND identifier = ?",
                        (sid, ident))
                    removed += cur.rowcount
                    result.success_ids.append(
                        f"{sid}:{ident} −{cur.rowcount}")
                conn.commit()
        elif op == "force_password_reset":
            init_db()
            with _connect() as conn:
                for sid in sids:
                    cur = conn.execute(
                        "DELETE FROM password_reset_required "
                        "WHERE student_id = ?", (sid,))
                    removed += cur.rowcount
                    result.success_ids.append(f"{sid}:−{cur.rowcount}")
                conn.commit()
    except Exception as e:  # noqa: BLE001
        result.failures.append((str(target_job_id), str(e)))

    summary_text = (f"Undid {removed} side-effect(s) from job "
                    f"#{target_job_id} ({op})")
    result.job_id = _log_job(
        operation="undo_job", summary=summary_text,
        params={"target_job_id": target_job_id,
                "operation": op, "rows_removed": removed},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: schedule recurring bulk job ────────────────────────

@dataclass
class Schedule:
    schedule_id: int
    name: str
    operation: str
    parameters: dict[str, Any]
    cron_expr: str
    enabled: bool
    next_run_at: str | None
    last_run_at: str | None
    last_job_id: int | None
    created_by: str | None
    created_at: str
    last_status: str | None = None
    last_error: str | None = None


def _row_schedule(r: db.Row) -> Schedule:
    try:
        params = json.loads(r["parameters"]) if r["parameters"] else {}
    except (TypeError, ValueError):
        params = {}
    return Schedule(
        schedule_id=r["schedule_id"], name=r["name"],
        operation=r["operation"], parameters=params,
        cron_expr=r["cron_expr"], enabled=bool(r["enabled"]),
        next_run_at=r["next_run_at"], last_run_at=r["last_run_at"],
        last_job_id=r["last_job_id"],
        created_by=r["created_by"], created_at=r["created_at"],
        last_status=r["last_status"] if "last_status" in r.keys() else None,
        last_error=r["last_error"] if "last_error" in r.keys() else None,
    )


def create_schedule(
    *,
    name: str,
    operation: str,
    parameters: dict[str, Any],
    cron_expr: str,
    next_run_at: str | None = None,
    created_by: str | None = None,
) -> Schedule:
    name = (name or "").strip()
    if not name:
        raise ValidationError("Schedule name is required")
    if operation not in OPERATIONS:
        raise ValidationError(
            f"Unknown operation {operation!r}")
    from education_system.systems.sixth_form.domain.learners.bulk_operations import (
        recurring,
    )
    cron_expr = recurring.validate_cron(cron_expr)
    recurring.check_schedulable(operation)
    if next_run_at:
        next_run_at = recurring.validate_when(next_run_at)
    else:
        next_run_at = recurring.next_run(cron_expr)
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO bulk_schedules
                  (name, operation, parameters, cron_expr,
                   enabled, next_run_at, created_by)
               VALUES (?, ?, ?, ?, 1, ?, ?)""",
            (name, operation, json.dumps(parameters, default=str),
             cron_expr, next_run_at, created_by),
        )
        conn.commit()
        sid = cur.lastrowid
    out = get_schedule(sid)
    assert out is not None
    return out


def get_schedule(schedule_id: int) -> Schedule | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM bulk_schedules WHERE schedule_id = ?",
            (schedule_id,)).fetchone()
        return _row_schedule(r) if r else None


def list_schedules(*, enabled: bool | None = None) -> list[Schedule]:
    init_db()
    clauses, args = [], []
    if enabled is not None:
        clauses.append("enabled = ?")
        args.append(1 if enabled else 0)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM bulk_schedules {where} "
            "ORDER BY enabled DESC, schedule_id DESC",
            args).fetchall()
    return [_row_schedule(r) for r in rows]


def set_schedule_enabled(schedule_id: int, enabled: bool) -> Schedule:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE bulk_schedules SET enabled = ? "
            "WHERE schedule_id = ?",
            (1 if enabled else 0, schedule_id))
        conn.commit()
        if not cur.rowcount:
            raise ValidationError(f"No schedule #{schedule_id}")
    out = get_schedule(schedule_id)
    assert out is not None
    return out


def delete_schedule(schedule_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM bulk_schedules WHERE schedule_id = ?",
            (schedule_id,))
        conn.commit()
        return bool(cur.rowcount)


def bulk_schedule_recurring(
    *,
    name: str,
    operation: str,
    cron_expr: str,
    parameters: dict[str, Any] | None = None,
    next_run_at: str | None = None,
    created_by: str | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Persist a recurring bulk-job definition. The sixth form
    scheduler's "Recurring bulk jobs" job runs each enabled schedule
    when ``next_run_at`` arrives (:func:`recurring.run_due_schedules`)
    and then moves ``next_run_at`` to the next cron time. Reported as a
    single-target job."""
    if dry_run:
        return BulkResult(operation="schedule_recurring", target_count=1)
    sched = create_schedule(
        name=name, operation=operation,
        parameters=parameters or {}, cron_expr=cron_expr,
        next_run_at=next_run_at, created_by=created_by,
    )
    result = BulkResult(operation="schedule_recurring", target_count=1)
    result.success_ids.append(f"schedule#{sched.schedule_id}:{sched.name}")
    result.job_id = _log_job(
        operation="schedule_recurring",
        summary=(f"Created schedule #{sched.schedule_id} {name!r} "
                 f"({operation} @ {cron_expr})"),
        params={"name": name, "operation": operation,
                "cron_expr": cron_expr,
                "parameters": parameters or {},
                "next_run_at": next_run_at},
        result=result, ran_by=ran_by,
    )
    return result


# ── Summary ───────────────────────────────────────────────────────

def summary() -> Summary:
    init_db()
    with _connect() as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM bulk_jobs").fetchone()[0]
        by_op: dict[str, int] = {o: 0 for o in OPERATIONS}
        for r in conn.execute(
                "SELECT operation, COUNT(*) n FROM bulk_jobs "
                "GROUP BY operation").fetchall():
            by_op[r["operation"]] = r["n"]
        totals = conn.execute(
            "SELECT COALESCE(SUM(target_count), 0) tt, "
            "       COALESCE(SUM(success_count), 0) ts, "
            "       COALESCE(SUM(failure_count), 0) tf "
            "FROM bulk_jobs").fetchone()
        most_recent = conn.execute(
            "SELECT ran_at FROM bulk_jobs "
            "ORDER BY ran_at DESC LIMIT 1").fetchone()
    return Summary(
        total_jobs=total,
        by_operation=by_op,
        total_targets=totals["tt"] or 0,
        total_successes=totals["ts"] or 0,
        total_failures=totals["tf"] or 0,
        most_recent_ts=most_recent["ran_at"] if most_recent else None,
    )
