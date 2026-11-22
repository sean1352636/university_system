"""Sixth Form bulk operations — academic (enrolment, class groups, predicted
grades, marks, reports, grade boundaries, subjects, teaching sets, timetable).

Split out of ``bulk_operations.py``, which re-exports every name defined here."""

from __future__ import annotations

from typing import Any
import datetime as _dt
from education_system.systems.sixth_form.domain.learners.bulk_operations.base import (
    BulkResult,
    ValidationError,
    _connect,
    _log_job,
    _pct_to_letter,
    _validate_targets,
    init_db,
    logger,
)

# ── Operation: bulk enrol ─────────────────────────────────────────

def bulk_enrol(
    student_ids: list[str],
    *,
    academic_year: str,
    year_group: int,
    tutor_group: str | None = None,
    start_date: str | None = None,
    status: str = "Enrolled",
    notes: str | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    targets = _validate_targets(student_ids)
    from education_system.systems.sixth_form.domain.admissions.enrolments import (
        enrolments as _en,
    )
    result = BulkResult(operation="enrol", target_count=len(targets))
    if dry_run:
        return result
    for sid in targets:
        try:
            _en.create_enrolment({
                "student_id":    sid,
                "academic_year": academic_year,
                "year_group":    year_group,
                "tutor_group":   tutor_group,
                "start_date":    start_date,
                "status":        status,
                "notes":         notes,
            })
            result.success_ids.append(sid)
        except Exception as e:
            result.failures.append((sid, str(e)))
    summary_text = (f"Enrolled {result.success_count}/{result.target_count} "
                    f"students for {academic_year} Y{year_group}")
    result.job_id = _log_job(
        operation="enrol", summary=summary_text,
        params={"academic_year": academic_year, "year_group": year_group,
                "tutor_group": tutor_group, "start_date": start_date,
                "status": status},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk move class group ──────────────────────────────

def bulk_move_class_group(
    student_ids: list[str],
    *,
    from_group_id: int | None = None,
    to_group_id: int | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Remove students from one group and/or add them to another.

    Either ``from_group_id`` or ``to_group_id`` must be set; both is the
    common "transfer" case.
    """
    if from_group_id is None and to_group_id is None:
        raise ValidationError("Set from_group_id, to_group_id, or both")
    targets = _validate_targets(student_ids)
    from education_system.systems.sixth_form.domain.academics.class_groups import (
        class_groups as _cg,
    )
    result = BulkResult(operation="move_class_group",
                         target_count=len(targets))
    if dry_run:
        return result
    for sid in targets:
        try:
            actions: list[str] = []
            if from_group_id is not None:
                if _cg.remove_member(from_group_id, sid):
                    actions.append(f"−{from_group_id}")
            if to_group_id is not None:
                _cg.add_member(to_group_id, sid)
                actions.append(f"+{to_group_id}")
            result.success_ids.append(f"{sid}:{','.join(actions) or 'noop'}")
        except Exception as e:
            result.failures.append((sid, str(e)))
    summary_text = (
        f"Moved {result.success_count}/{result.target_count} students "
        f"(from={from_group_id}, to={to_group_id})"
    )
    result.job_id = _log_job(
        operation="move_class_group", summary=summary_text,
        params={"from_group_id": from_group_id,
                "to_group_id": to_group_id},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk assign predicted grades ───────────────────────

def bulk_assign_predicted_grades(
    student_ids: list[str],
    *,
    subject: str,
    grade: str | None = None,
    from_baseline: bool = False,
    confidence: str = "Medium",
    predicted_by: str | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Save a predicted grade for many students on the same subject.

    If ``from_baseline`` is True, each student's grade is derived from
    their primary baseline percentage for the subject; otherwise the
    fixed ``grade`` is used for everyone.
    """
    targets = _validate_targets(student_ids)
    if not from_baseline and not grade:
        raise ValidationError(
            "Either set from_baseline=True or supply a fixed grade")
    from education_system.systems.sixth_form.domain.assessment.predicted_grades import (
        predicted_grades as _pred,
    )
    if from_baseline:
        from education_system.systems.sixth_form.domain.assessment.baseline_assessment import (
            baseline_assessment as _bl,
        )
    result = BulkResult(operation="assign_predicted_grades",
                         target_count=len(targets))
    if dry_run:
        return result
    for sid in targets:
        try:
            chosen = grade
            if from_baseline:
                rec = _bl.get_primary(sid, subject)
                pct = getattr(rec, "percentage", None) if rec else None
                bl_grade = getattr(rec, "baseline_grade", None) if rec else None
                chosen = bl_grade or _pct_to_letter(pct)
                if chosen is None:
                    raise ValidationError(
                        f"No baseline data for {sid} / {subject}")
            _pred.save_prediction({
                "student_id":   sid,
                "subject":      subject,
                "grade":        chosen,
                "confidence":   confidence,
                "predicted_by": predicted_by,
            })
            result.success_ids.append(f"{sid}:{chosen}")
        except Exception as e:
            result.failures.append((sid, str(e)))
    summary_text = (
        f"Saved predicted grades for "
        f"{result.success_count}/{result.target_count} students "
        f"({subject}; {'from baseline' if from_baseline else f'={grade}'})"
    )
    result.job_id = _log_job(
        operation="assign_predicted_grades", summary=summary_text,
        params={"subject": subject, "grade": grade,
                "from_baseline": from_baseline,
                "confidence": confidence,
                "predicted_by": predicted_by},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk import assessment marks ───────────────────────

def bulk_import_assessment_marks(
    csv_path: str,
    *,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Import baseline-assessment records from a CSV.

    Required: ``student_id, subject_name, assessment_type, assessment_date,
    raw_score, max_score``. Optional: ``percentage, baseline_grade,
    confidence, assessor, notes, is_primary``.
    """
    import csv as _csv
    import os
    if not csv_path or not os.path.isfile(csv_path):
        raise ValidationError(f"CSV not found: {csv_path}")
    from education_system.systems.sixth_form.domain.assessment.baseline_assessment import (
        baseline_assessment as _bl,
    )
    rows: list[dict[str, str]] = []
    with open(csv_path, encoding="utf-8-sig", newline="") as fh:
        reader = _csv.DictReader(fh)
        required = {"student_id", "subject_name", "assessment_type",
                    "assessment_date", "raw_score", "max_score"}
        missing = required - set(h.strip() for h in (reader.fieldnames or []))
        if missing:
            raise ValidationError(
                f"CSV missing columns: {', '.join(sorted(missing))}")
        for r in reader:
            rows.append({k: (v or "").strip() for k, v in r.items()})

    result = BulkResult(operation="import_assessment_marks",
                         target_count=len(rows))
    if dry_run:
        return result
    for i, r in enumerate(rows, start=2):
        sid = r.get("student_id", "")
        try:
            _bl.create_record({
                "student_id":      sid,
                "subject_name":    r.get("subject_name"),
                "assessment_type": r.get("assessment_type"),
                "assessment_date": r.get("assessment_date"),
                "raw_score":       r.get("raw_score"),
                "max_score":       r.get("max_score"),
                "percentage":      r.get("percentage") or None,
                "baseline_grade":  r.get("baseline_grade") or None,
                "confidence":      r.get("confidence") or None,
                "assessor":        r.get("assessor") or None,
                "notes":           r.get("notes") or None,
                "is_primary":      (r.get("is_primary") or "").lower()
                                    in ("1", "true", "yes", "y"),
            })
            result.success_ids.append(f"L{i}:{sid}")
        except Exception as e:
            result.failures.append((f"L{i}:{sid}", str(e)))
    import os as _os
    summary_text = (f"Imported {result.success_count}/{result.target_count} "
                    f"assessment rows from {_os.path.basename(csv_path)}")
    result.job_id = _log_job(
        operation="import_assessment_marks", summary=summary_text,
        params={"csv_path": csv_path},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk recalculate grade reports ─────────────────────

def bulk_recalc_grade_reports(
    student_ids: list[str],
    *,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Compute per-student grade reports; audit only (read-only)."""
    targets = _validate_targets(student_ids)
    from education_system.systems.sixth_form.domain.operations.reporting.grades_report import (
        grades_report as _gr,
    )
    result = BulkResult(operation="recalc_grade_reports",
                         target_count=len(targets))
    if dry_run:
        return result
    samples: list[list[Any]] = []
    for sid in targets:
        try:
            rep = _gr.per_student_grade_report(sid)
            avg_pred = getattr(rep, "predicted_avg_grade", None)
            avg_act = getattr(rep, "actual_avg_grade", None)
            samples.append([sid, avg_pred, avg_act])
            result.success_ids.append(
                f"{sid}:pred={avg_pred or '—'},act={avg_act or '—'}")
        except Exception as e:
            result.failures.append((sid, str(e)))
    summary_text = (f"Recalculated grade reports for "
                    f"{result.success_count}/{result.target_count} students")
    result.job_id = _log_job(
        operation="recalc_grade_reports", summary=summary_text,
        params={"samples": samples},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk export progress reports (text) ────────────────

def bulk_export_progress_reports(
    student_ids: list[str],
    *,
    output_dir: str,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Write a plain-text progress report per student to ``output_dir``."""
    import os
    targets = _validate_targets(student_ids)
    if not output_dir:
        raise ValidationError("output_dir is required")
    if not dry_run:
        os.makedirs(output_dir, exist_ok=True)
    from education_system.systems.sixth_form.domain.operations.reporting.grades_report import (
        grades_report as _gr,
    )
    result = BulkResult(operation="export_progress_reports",
                         target_count=len(targets))
    if dry_run:
        return result
    for sid in targets:
        try:
            rep = _gr.per_student_grade_report(sid)
            lines = [
                f"Progress report — {sid}",
                f"Generated: {_dt.datetime.now().isoformat(sep=' ', timespec='seconds')}",
                "",
            ]
            for row in getattr(rep, "rows", []) or []:
                lines.append(
                    f"  {getattr(row, 'subject', '?'):<28}  "
                    f"pred={getattr(row, 'predicted', '—') or '—'}  "
                    f"mock={getattr(row, 'mock', '—') or '—'}  "
                    f"actual={getattr(row, 'actual', '—') or '—'}"
                )
            path = os.path.join(output_dir, f"progress_{sid}.txt")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("\n".join(lines) + "\n")
            result.success_ids.append(f"{sid}:{path}")
        except Exception as e:
            result.failures.append((sid, str(e)))
    summary_text = (f"Wrote {result.success_count}/{result.target_count} "
                    f"progress reports to {output_dir}")
    result.job_id = _log_job(
        operation="export_progress_reports", summary=summary_text,
        params={"output_dir": output_dir},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk publish / unpublish report cards ──────────────

def bulk_publish_report_cards(
    student_ids: list[str],
    *,
    period: str,
    publish: bool = True,
    published_by: str | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    targets = _validate_targets(student_ids)
    period = (period or "").strip()
    if not period:
        raise ValidationError("period is required (e.g. '2025/26 T1')")
    init_db()
    result = BulkResult(
        operation="publish_report_cards", target_count=len(targets))
    if dry_run:
        return result
    # A period built in report_cards only publishes approved cards; a
    # label report_cards does not know is published as before.
    blocked: dict[str, str] = {}
    if publish:
        try:
            from education_system.systems.sixth_form.domain.assessment.report_cards import (
                report_cards as _rc,
            )
            blocked = _rc.unapproved_for_publication(targets, period)
        except Exception:
            logger.exception("Report-card approval check failed for %s", period)
    op_word = "Published" if publish else "Unpublished"
    with _connect() as conn:
        for sid in targets:
            if sid in blocked:
                result.failures.append((sid, blocked[sid]))
                continue
            try:
                if publish:
                    conn.execute(
                        """INSERT INTO report_card_publications
                              (student_id, period, published_at, published_by)
                           VALUES (?, ?, datetime('now'), ?)
                           ON CONFLICT(student_id, period) DO UPDATE SET
                              published_at = datetime('now'),
                              published_by = excluded.published_by""",
                        (sid, period, published_by),
                    )
                else:
                    conn.execute(
                        """DELETE FROM report_card_publications
                           WHERE student_id = ? AND period = ?""",
                        (sid, period),
                    )
                result.success_ids.append(sid)
            except Exception as e:
                result.failures.append((sid, str(e)))
        conn.commit()
    try:
        from education_system.systems.sixth_form.domain.assessment.report_cards import (
            report_cards as _rc,
        )
        _rc.on_publications_changed(list(result.success_ids), period,
                                    publish=publish, by=published_by)
    except Exception:
        logger.exception("Report-card status sync failed for %s", period)
    summary_text = (f"{op_word} report cards for "
                    f"{result.success_count}/{result.target_count} students "
                    f"({period})")
    result.job_id = _log_job(
        operation="publish_report_cards", summary=summary_text,
        params={"period": period, "publish": publish,
                "published_by": published_by},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk apply grade boundaries ────────────────────────

def bulk_apply_grade_boundaries(
    assignment_ids: list[int],
    *,
    a_star: int | None = None,
    a: int | None = None,
    b: int | None = None,
    c: int | None = None,
    d: int | None = None,
    e: int | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Apply the same A*/A/B/C/D/E thresholds to many assignments."""
    if not assignment_ids:
        raise ValidationError("Pick at least one assignment")
    str_targets = _validate_targets([str(a_) for a_ in assignment_ids])
    if all(v is None for v in (a_star, a, b, c, d, e)):
        raise ValidationError("Set at least one grade boundary")
    from education_system.systems.sixth_form.domain.assessment.gradebook import (
        gradebook as _gb,
    )
    result = BulkResult(operation="apply_grade_boundaries",
                         target_count=len(str_targets))
    if dry_run:
        return result
    for tag in str_targets:
        try:
            aid = int(tag)
            _gb.set_boundaries(aid, {
                "a_star": a_star, "a": a, "b": b,
                "c": c, "d": d, "e": e,
            })
            result.success_ids.append(f"assn#{aid}")
        except Exception as e:
            result.failures.append((tag, str(e)))
    summary_text = (
        f"Applied boundaries to {result.success_count}/"
        f"{result.target_count} assignment(s) "
        f"(A*={a_star} A={a} B={b} C={c} D={d} E={e})"
    )
    result.job_id = _log_job(
        operation="apply_grade_boundaries", summary=summary_text,
        params={"a_star": a_star, "a": a, "b": b,
                "c": c, "d": d, "e": e,
                "assignment_ids": [int(t) for t in str_targets]},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk assign subjects ───────────────────────────────

def bulk_assign_subjects(
    student_ids: list[str],
    *,
    subjects: list[str],
    overwrite: bool = False,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Place ``subjects`` into the students' three subject slots.

    By default, only empty slots are filled (so existing subjects are
    preserved and not silently duplicated). With ``overwrite=True``,
    the supplied list replaces the slots wholesale (any missing
    positions are blanked).
    """
    targets = _validate_targets(student_ids)
    if not subjects:
        raise ValidationError("Pick at least one subject")
    # De-dup while preserving order; cap at 3 to match the schema.
    seen: set[str] = set()
    cleaned: list[str] = []
    for s in subjects:
        ss = (s or "").strip()
        if not ss or ss.lower() in seen:
            continue
        seen.add(ss.lower())
        cleaned.append(ss)
    if not cleaned:
        raise ValidationError("No valid subjects supplied")
    if len(cleaned) > 3:
        raise ValidationError(
            "Students can hold at most 3 subjects (subject_1..subject_3)")

    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    from education_system.systems.sixth_form.domain.academics.subjects import (
        subjects as _sub,
    )
    # Validate against the active subject catalogue (warn-only — if
    # the catalogue is empty we accept whatever was typed).
    try:
        active = {n.lower() for n in _sub.get_active_names()}
    except Exception:  # noqa: BLE001
        active = set()
    unknown = [c for c in cleaned if active and c.lower() not in active]
    if unknown and active:
        raise ValidationError(
            f"Unknown subject(s): {', '.join(unknown)}. "
            f"Active: {', '.join(sorted(active))}")

    result = BulkResult(operation="assign_subjects",
                        target_count=len(targets))

    for sid in targets:
        try:
            student = _students.get_student(sid)
            if student is None:
                result.failures.append((sid, "Unknown student"))
                continue
            current = [student.subject_1, student.subject_2, student.subject_3]
            if overwrite:
                new_slots: list[str | None] = list(cleaned) + [None] * (
                    3 - len(cleaned))
            else:
                new_slots = list(current)
                for incoming in cleaned:
                    if any(
                        (c or "").lower() == incoming.lower()
                        for c in new_slots
                    ):
                        continue  # already present
                    free = next(
                        (i for i, c in enumerate(new_slots) if not c),
                        None)
                    if free is None:
                        # All 3 slots full and not overwriting.
                        result.failures.append(
                            (sid, f"All subject slots full — cannot add "
                                  f"{incoming}"))
                        new_slots = current  # leave unchanged
                        break
                    new_slots[free] = incoming
                else:
                    pass
            if new_slots == current:
                result.success_ids.append(f"{sid}: (no change)")
                continue
            if dry_run:
                result.success_ids.append(
                    f"{sid}: {tuple(current)} → {tuple(new_slots)}")
                continue
            payload = {
                "first_name":                 student.first_name,
                "middle_name":                student.middle_name,
                "last_name":                  student.last_name,
                "phone":                      student.phone,
                "emergency_contact_name":     student.emergency_contact_name,
                "emergency_contact_phone":    student.emergency_contact_phone,
                "emergency_contact_relation": student.emergency_contact_relation,
                "subject_1":                  new_slots[0],
                "subject_2":                  new_slots[1],
                "subject_3":                  new_slots[2],
            }
            _students.update_student(sid, payload)
            result.success_ids.append(f"{sid}: {tuple(new_slots)}")
        except Exception as e:  # noqa: BLE001
            result.failures.append((sid, str(e)))

    if dry_run:
        return result
    summary_text = (
        f"Assigned subjects {cleaned!r} (overwrite={overwrite}) to "
        f"{result.success_count}/{result.target_count} students"
    )
    result.job_id = _log_job(
        operation="assign_subjects", summary=summary_text,
        params={"subjects": cleaned, "overwrite": overwrite},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk withdraw subjects ─────────────────────────────

def bulk_withdraw_subjects(
    student_ids: list[str],
    *,
    subjects: list[str],
    ran_by: str | None = None,
    dry_run: bool = False,
    effective_date: str | None = None,
    reason: str | None = None,
    approved_by: str | None = None,
) -> BulkResult:
    """Withdraw the students from their learning aims in ``subjects``.

    Goes through ``learning_aims.withdraw_aim`` — the same workflow as a
    single withdrawal — so every aim gets an effective date, reason,
    approver and a history row, and the funding qualifying-period check
    is recorded. The legacy subject slots follow automatically (they are
    mirrors of the active A-level aims). It used to blank the slot
    through ``update_student``, which recorded nothing, and whose
    validation (three subjects, a partial payload resetting status)
    meant it failed for most learners anyway.

    ``effective_date`` (last day in learning) defaults to today, the
    approver to ``ran_by``; one of the two must name a person.
    """
    import datetime as _dt
    targets = _validate_targets(student_ids)
    if not subjects:
        raise ValidationError("Pick at least one subject to withdraw")
    drop = {(s or "").strip().lower()
            for s in subjects if (s or "").strip()}
    if not drop:
        raise ValidationError("No valid subjects supplied")
    eff = (effective_date or "").strip() or _dt.date.today().isoformat()
    try:
        _dt.date.fromisoformat(eff)
    except ValueError:
        raise ValidationError("Effective date must be YYYY-MM-DD") from None
    approver = (approved_by or "").strip() or (ran_by or "").strip()
    if not dry_run and not approver:
        raise ValidationError("An approver is required to withdraw learning aims")
    why = (reason or "").strip() or "Bulk withdrawal"

    from education_system.systems.sixth_form.domain.academics.qualifications import (
        learning_aims as _aims,
    )
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    result = BulkResult(operation="withdraw_subjects",
                        target_count=len(targets))
    before_qp = 0
    for sid in targets:
        try:
            if _students.get_student(sid) is None:
                result.failures.append((sid, "Unknown student"))
                continue
            hits = [a for a in _aims.active_aims(sid)
                    if a.subject.lower() in drop]
            if not hits:
                result.success_ids.append(f"{sid}: (none of those held)")
                continue
            if dry_run:
                notes = []
                for a in hits:
                    chk = _aims.qualifying_if_withdrawn(a, eff)
                    notes.append(f"{a.label} (qualifying period "
                                 f"{'met' if chk.met else 'NOT met'})")
                result.success_ids.append(f"{sid}: would withdraw "
                                          + "; ".join(notes))
                continue
            done = []
            for a in hits:
                chk = _aims.withdraw_aim(
                    a.aim_id, effective_date=eff, reason=why,
                    approved_by=approver, recorded_by=ran_by)
                if chk.withdrawn_before_qualifying:
                    before_qp += 1
                done.append(a.label + ("" if chk.met
                                       else " [before qualifying period]"))
            result.success_ids.append(f"{sid}: withdrew {', '.join(done)}")
        except Exception as e:  # noqa: BLE001
            result.failures.append((sid, str(e)))
    if dry_run:
        return result
    summary_text = (
        f"Withdrew subjects {sorted(drop)!r} from "
        f"{result.success_count}/{result.target_count} students "
        f"effective {eff}"
        + (f" ({before_qp} aim(s) before qualifying period)" if before_qp else "")
    )
    result.job_id = _log_job(
        operation="withdraw_subjects", summary=summary_text,
        params={"subjects": sorted(drop), "effective_date": eff,
                "reason": why, "approved_by": approver},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk set teaching set ──────────────────────────────

def bulk_set_teaching_set(
    student_ids: list[str],
    *,
    target_group_id: int,
    course_id: int | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Move students into ``target_group_id``, removing them first from
    any *other* group on the same course (so teaching sets don't
    silently overlap).

    If ``course_id`` is not given, it's inferred from ``target_group_id``.
    """
    targets = _validate_targets(student_ids)
    try:
        target_group_id = int(target_group_id)
    except (TypeError, ValueError):
        raise ValidationError("target_group_id must be numeric") from None

    from education_system.systems.sixth_form.domain.academics.class_groups import (
        class_groups as _cg,
    )
    target = _cg.get_group(target_group_id)
    if target is None:
        raise ValidationError(
            f"No class group with id {target_group_id}")
    course_id = course_id or getattr(target, "course_id", None)
    if course_id is None:
        raise ValidationError(
            "Target group has no course_id and none was supplied")

    result = BulkResult(operation="set_teaching_set",
                        target_count=len(targets))
    moved = 0
    removed_total = 0
    for sid in targets:
        try:
            others = [
                g for g in _cg.groups_for_student(sid)
                if g.group_id != target_group_id
                and getattr(g, "course_id", None) == course_id
            ]
            other_names = [g.group_name for g in others]
            already_in_target = any(
                g.group_id == target_group_id
                for g in _cg.groups_for_student(sid))
            if dry_run:
                if already_in_target and not others:
                    result.success_ids.append(f"{sid}: (already there)")
                else:
                    result.success_ids.append(
                        f"{sid}: leave {other_names!r} → join "
                        f"{target.group_name!r}")
                continue
            for g in others:
                if _cg.remove_member(g.group_id, sid):
                    removed_total += 1
            if not already_in_target:
                _cg.add_member(target_group_id, sid)
                moved += 1
                result.success_ids.append(
                    f"{sid}: → {target.group_name}")
            else:
                result.success_ids.append(f"{sid}: (already in target)")
        except Exception as e:  # noqa: BLE001
            result.failures.append((sid, str(e)))
    if dry_run:
        return result
    summary_text = (
        f"Set teaching set {target.group_name!r} (course #{course_id}) for "
        f"{result.success_count}/{result.target_count} students; "
        f"removed {removed_total} prior membership(s), "
        f"added {moved} new"
    )
    result.job_id = _log_job(
        operation="set_teaching_set", summary=summary_text,
        params={"target_group_id": target_group_id,
                "course_id": course_id,
                "moved": moved, "removed": removed_total},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk import timetable slots from CSV ───────────────

def bulk_import_timetable_csv(
    csv_path: str,
    *,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Load timetable slots from a CSV.

    Required headers: ``group_id, day, period``.
    Optional: ``start_time, end_time, room, notes``.

    ``day`` accepts both an integer (1=Mon..7=Sun) and a day name
    (``Mon``/``Monday``). One slot per row; failures are reported
    per-line so partial imports are kept.
    """
    import csv as _csv
    import os
    if not csv_path or not os.path.isfile(csv_path):
        raise ValidationError(f"CSV not found: {csv_path}")
    from education_system.systems.sixth_form.domain.academics.timetable import (
        timetable as _tt,
    )

    try:
        fh = open(csv_path, encoding="utf-8-sig", newline="")
    except OSError as e:
        raise ValidationError(f"Cannot open CSV: {e}") from e
    with fh:
        reader = _csv.DictReader(fh)
        required = {"group_id", "day", "period"}
        headers = {(h or "").strip() for h in (reader.fieldnames or [])}
        missing = required - headers
        if missing:
            raise ValidationError(
                f"CSV missing columns: {', '.join(sorted(missing))}")
        rows: list[dict[str, str]] = [
            {k: (v or "").strip() for k, v in r.items()}
            for r in reader
        ]

    result = BulkResult(operation="import_timetable_csv",
                        target_count=len(rows))
    if not rows:
        result.job_id = _log_job(
            operation="import_timetable_csv",
            summary=(f"Imported 0 timetable rows from "
                     f"{os.path.basename(csv_path)} (empty file)"),
            params={"csv_path": csv_path}, result=result, ran_by=ran_by,
        )
        return result
    if dry_run:
        for i, r in enumerate(rows, start=2):
            result.success_ids.append(
                f"line {i}: group={r.get('group_id')} "
                f"day={r.get('day')} P{r.get('period')}")
        return result

    created = 0
    student_clashes = 0
    teacher_clashes = 0
    for i, r in enumerate(rows, start=2):  # +2 for header
        try:
            payload = {
                "group_id":   r.get("group_id"),
                "day":        r.get("day"),
                "period":     r.get("period"),
                "start_time": r.get("start_time") or None,
                "end_time":   r.get("end_time") or None,
                "room":       r.get("room") or None,
                "notes":      r.get("notes") or None,
            }
            save = _tt.create_slot(payload)
            created += 1
            sc, tc = len(save.student_clashes), len(save.teacher_clashes)
            student_clashes += sc
            teacher_clashes += tc
            tag = f"line {i}: slot #{save.slot.slot_id}"
            if sc or tc:
                tag += f" (clashes: students={sc}, teachers={tc})"
            result.success_ids.append(tag)
        except Exception as e:  # noqa: BLE001
            result.failures.append((f"line {i}", str(e)))
    summary_text = (
        f"Imported {created}/{len(rows)} timetable slot(s) from "
        f"{os.path.basename(csv_path)} "
        f"(student clashes={student_clashes}, teacher clashes={teacher_clashes})"
    )
    result.job_id = _log_job(
        operation="import_timetable_csv", summary=summary_text,
        params={"csv_path": csv_path,
                "created": created,
                "student_clashes": student_clashes,
                "teacher_clashes": teacher_clashes},
        result=result, ran_by=ran_by,
    )
    return result
