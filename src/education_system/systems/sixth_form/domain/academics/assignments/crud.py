"""Sixth Form coursework assignments — targeting (students / class groups),
submission create/update/delete, marking, and multi-part component roll-up.

Split out of ``assignments.py``, which re-exports every name defined here."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import Any
from education_system.systems.sixth_form.domain.academics.assignments.models import (
    Assignment,
    DEFAULT_SUBMISSION_STATUS,
    Submission,
    SubmissionRow,
    ValidationError,
    logger,
)
from education_system.systems.sixth_form.domain.academics.assignments.store import (
    _connect,
    _stored_paths_for_submission,
    _unlink_stored,
    _validate_submission_payload,
    get_assignment,
    get_submission,
    init_db,
    list_components,
    list_submissions,
)
from education_system.systems.sixth_form.domain.academics.assignments.submissions import (
    submit_work,
)

# ── Submission CRUD ───────────────────────────────────────────────

def add_student(assignment_id: int, student_id: str, *,
                 status: str = DEFAULT_SUBMISSION_STATUS,
                 apply_access_arrangements: bool = True) -> Submission:
    """Put a student on an assignment.

    Their exam-access arrangements are honoured on the way in, so a
    student with extra time gets their deadline uplift without anyone
    having to remember. Set ``apply_access_arrangements=False`` to skip
    that (bulk imports that will sweep afterwards).
    """
    sub = create_submission({
        "assignment_id": assignment_id,
        "student_id": student_id,
        "status": status,
    })
    if not apply_access_arrangements:
        return sub
    try:
        from education_system.systems.sixth_form.domain.academics.assignments import (
            assignments_marking as _marking,
        )
        _marking.apply_access_arrangements_to(sub.submission_id)
    except Exception:
        # SEND data is optional; never block adding a student over it.
        logger.exception(
            "Could not apply access arrangements to submission #%d",
            sub.submission_id)
    out = get_submission(sub.submission_id)
    return out if out is not None else sub


def add_class_group(assignment_id: int, group_id: int) -> int:
    """Bulk-add every member of a class group as a submission row.
    Returns the number of new rows created."""
    init_db()
    if get_assignment(assignment_id) is None:
        raise ValidationError(f"No assignment #{assignment_id}")
    from education_system.systems.sixth_form.domain.academics.class_groups import (
        class_groups as _cg,
    )
    if _cg.get_group(group_id) is None:
        raise ValidationError(f"No class group #{group_id}")
    members = _cg.list_members(group_id)
    n = 0
    for sid in members:
        try:
            add_student(assignment_id, sid)
            n += 1
        except ValidationError as e:
            if "already exists" in str(e).lower():
                continue
            # Likely UNIQUE constraint at the DB level
            logger.debug("Skipping %s: %s", sid, e)
    return n


def create_submission(payload: dict[str, Any]) -> Submission:
    init_db()
    p = _validate_submission_payload(payload)
    with _connect() as conn:
        if conn.execute(
                "SELECT 1 FROM coursework_submissions "
                "WHERE assignment_id = ? AND student_id = ?",
                (p["assignment_id"], p["student_id"])).fetchone():
            raise ValidationError(
                f"Student {p['student_id']} already has a "
                f"submission row for assignment "
                f"#{p['assignment_id']}")
        cur = conn.execute(
            """INSERT INTO coursework_submissions
                   (assignment_id, student_id, status, submitted_on,
                    marks, grade, feedback, marked_by, marked_on,
                    notes, word_count, is_draft,
                    created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["assignment_id"], p["student_id"], p["status"],
             p["submitted_on"], p["marks"], p["grade"],
             p["feedback"], p["marked_by"], p["marked_on"],
             p["notes"], p["word_count"], p["is_draft"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_submission(new_id)
    assert out is not None
    logger.info("Created submission #%d for student %s on assignment #%d",
                new_id, p["student_id"], p["assignment_id"])
    return out


def list_submissions_with_detail(**kwargs) -> list[SubmissionRow]:
    rows = list_submissions(**kwargs)
    if not rows:
        return []
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    names = {s.student_id: s.full_name for s in _students.list_students()}
    return [SubmissionRow(submission=s,
                          student_name=names.get(s.student_id,
                                                   "(unknown)"))
            for s in rows]


def update_submission(submission_id: int,
                       payload: dict[str, Any]) -> Submission:
    init_db()
    existing = get_submission(submission_id)
    if existing is None:
        raise ValidationError(f"No submission #{submission_id}")
    merged = {
        "assignment_id": existing.assignment_id,
        "student_id":    existing.student_id,
        "status":        payload.get("status", existing.status),
        "submitted_on":  payload.get("submitted_on",
                                      existing.submitted_on),
        "marks":         payload.get("marks", existing.marks),
        "grade":         payload.get("grade", existing.grade),
        "feedback":      payload.get("feedback", existing.feedback),
        "marked_by":     payload.get("marked_by", existing.marked_by),
        "marked_on":     payload.get("marked_on", existing.marked_on),
        "notes":         payload.get("notes", existing.notes),
        "word_count":    payload.get("word_count", existing.word_count),
        "is_draft":      payload.get("is_draft", existing.is_draft),
    }
    p = _validate_submission_payload(merged)
    with _connect() as conn:
        conn.execute(
            """UPDATE coursework_submissions SET
                   status = ?, submitted_on = ?, marks = ?,
                   grade = ?, feedback = ?, marked_by = ?,
                   marked_on = ?, notes = ?, word_count = ?,
                   is_draft = ?,
                   updated_at = datetime('now')
               WHERE submission_id = ?""",
            (p["status"], p["submitted_on"], p["marks"],
             p["grade"], p["feedback"], p["marked_by"],
             p["marked_on"], p["notes"], p["word_count"],
             p["is_draft"], submission_id),
        )
        conn.commit()
    out = get_submission(submission_id)
    assert out is not None
    _audit_mark_edit(submission_id, existing, out)
    return out


def _audit_mark_edit(submission_id: int, before: Submission,
                      after: Submission) -> None:
    """Log a mark or grade edit made through the generic update path.

    ``marking.apply_marks`` writes its own audit rows, so this only
    catches edits that bypass the pipeline — a hand-corrected mark in
    the GUI, for instance. Best-effort: an audit failure must never
    lose the edit the user just made.
    """
    changes = [(f, getattr(before, f), getattr(after, f))
               for f in ("marks", "grade")
               if getattr(before, f) != getattr(after, f)]
    if not changes:
        return
    try:
        from education_system.systems.sixth_form.domain.academics.assignments import (
            assignments_marking as _marking,
        )
        for field_name, old, new in changes:
            _marking.record_mark_change(
                submission_id, field=field_name,
                old_value=None if old is None else str(old),
                new_value=None if new is None else str(new),
                source="manual", reason="Edited directly",
                changed_by=after.marked_by)
    except Exception:
        logger.exception("Could not audit mark edit on submission #%d",
                          submission_id)


def mark_submission(submission_id: int, *,
                     marks: float | None = None,
                     grade: str | None = None,
                     feedback: str | None = None,
                     marked_by: str | None = None) -> Submission:
    """Award a mark, running the full marking pipeline.

    ``marks`` is the raw mark the marker awarded. The pipeline in
    ``assignments_marking`` applies any late penalty, derives the grade
    from the assignment's boundaries when one isn't given, and records
    the change in the audit trail. See :func:`marking.apply_marks`.
    """
    from education_system.systems.sixth_form.domain.academics.assignments import (
        assignments_marking as _marking,
    )
    return _marking.apply_marks(
        submission_id, raw_marks=marks, grade=grade,
        feedback=feedback, marked_by=marked_by, source="manual")


def submit(submission_id: int, *,
            late: bool | None = None,
            submitted_on: str | None = None,
            files: Sequence[str | Path] | None = None,
            word_count: int | None = None,
            is_draft: bool = False,
            submitted_by: str | None = None) -> Submission:
    """Record a hand-in. Thin wrapper over :func:`submit_work`.

    ``late`` now defaults to ``None`` meaning "work it out from the
    deadline" — pass ``True``/``False`` to override that judgement.
    """
    submit_work(submission_id, files=files, word_count=word_count,
                 is_draft=is_draft, submitted_on=submitted_on,
                 submitted_by=submitted_by, late=late)
    out = get_submission(submission_id)
    assert out is not None
    return out


def set_submission_status(submission_id: int,
                          status: str) -> Submission:
    return update_submission(submission_id, {"status": status})


def delete_submission(submission_id: int) -> bool:
    init_db()
    with _connect() as conn:
        stored = _stored_paths_for_submission(conn, submission_id)
        cur = conn.execute(
            "DELETE FROM coursework_submissions "
            "WHERE submission_id = ?",
            (submission_id,))
        conn.commit()
        deleted = bool(cur.rowcount)
    if deleted:
        _unlink_stored(stored)
        logger.info("Deleted submission #%d (%d file(s))",
                    submission_id, len(stored))
    return deleted


@dataclass
class ComponentMark:
    """One component's contribution to a student's overall mark."""

    assignment: Assignment
    submission: Submission | None
    weight: float
    percent: float | None = None

    @property
    def contribution(self) -> float | None:
        """Weighted percentage points this component contributes."""
        if self.percent is None:
            return None
        return round(self.percent * self.weight / 100.0, 2)


@dataclass
class ComponentRollup:
    """A student's overall mark across a multi-part assignment."""

    assignment_id: int
    student_id: str
    components: list[ComponentMark] = field(default_factory=list)
    total_weight: float = 0.0
    weighted_percent: float | None = None
    overall_marks: float | None = None
    grade: str | None = None

    @property
    def complete(self) -> bool:
        return bool(self.components) and all(
            c.percent is not None for c in self.components)

    @property
    def message(self) -> str:
        if not self.components:
            return "No components"
        marked = sum(1 for c in self.components if c.percent is not None)
        head = f"{marked}/{len(self.components)} components marked"
        if abs(self.total_weight - 100.0) > 0.001:
            head += f"; weights total {self.total_weight:g}% (not 100%)"
        if self.weighted_percent is not None:
            head += f"; {self.weighted_percent:g}% overall"
        return head


def component_weights(assignment_id: int) -> dict[int, float]:
    """Each component's share, defaulting to an even split.

    A department that hasn't set weights almost always means "these
    count equally", so that is what an unweighted rubric produces
    rather than a zero.
    """
    components = list_components(assignment_id)
    if not components:
        return {}
    stated = {c.assignment_id: c.component_weight for c in components}
    if all(w is None for w in stated.values()):
        even = round(100.0 / len(components), 4)
        return {cid: even for cid in stated}
    # Partly weighted: unstated components share whatever is left.
    used = sum(w for w in stated.values() if w is not None)
    blanks = [cid for cid, w in stated.items() if w is None]
    share = round(max(0.0, 100.0 - used) / len(blanks), 4) if blanks else 0.0
    return {cid: (w if w is not None else share)
            for cid, w in stated.items()}


def component_rollup(assignment_id: int,
                      student_id: str) -> ComponentRollup:
    """Combine a student's component marks into one overall result.

    Percentages are combined rather than raw marks, so components with
    different maximums weigh correctly against each other.
    """
    init_db()
    parent = get_assignment(assignment_id)
    if parent is None:
        raise ValidationError(f"No assignment #{assignment_id}")
    weights = component_weights(assignment_id)
    out = ComponentRollup(assignment_id=assignment_id,
                           student_id=str(student_id).strip())
    for component in list_components(assignment_id):
        subs = list_submissions(assignment_id=component.assignment_id,
                                 student_id=out.student_id)
        sub = subs[0] if subs else None
        percent = None
        if (sub is not None and sub.marks is not None
                and component.max_marks):
            percent = round(100.0 * sub.marks / component.max_marks, 2)
        out.components.append(ComponentMark(
            assignment=component, submission=sub,
            weight=weights.get(component.assignment_id, 0.0),
            percent=percent))
    out.total_weight = round(sum(c.weight for c in out.components), 4)

    scored = [c for c in out.components if c.percent is not None]
    if scored:
        # Rescale by the weight actually marked so a part-marked NEA
        # reports the student's standing so far rather than a figure
        # dragged down by components that haven't been marked yet.
        weight_marked = sum(c.weight for c in scored)
        if weight_marked > 0:
            out.weighted_percent = round(
                sum((c.contribution or 0) for c in scored)
                / weight_marked * 100.0, 2)
            if parent.max_marks:
                out.overall_marks = round(
                    parent.max_marks * out.weighted_percent / 100.0, 2)
    if out.weighted_percent is not None:
        try:
            from education_system.systems.sixth_form.domain.academics.assignments import (
                assignments_marking as _marking,
            )
            out.grade = _marking.pct_to_letter(out.weighted_percent)
        except Exception:
            logger.debug("Could not resolve a rollup grade",
                          exc_info=True)
    return out


def apply_component_rollup(assignment_id: int, student_id: str, *,
                            marked_by: str | None = None
                            ) -> Submission | None:
    """Write a student's rolled-up component mark onto the parent.

    The student needs a submission row on the parent for the overall
    mark to land on; without one there is nothing to write to and this
    returns ``None``.
    """
    rollup = component_rollup(assignment_id, student_id)
    if rollup.overall_marks is None:
        return None
    subs = list_submissions(assignment_id=assignment_id,
                             student_id=rollup.student_id)
    if not subs:
        return None
    from education_system.systems.sixth_form.domain.academics.assignments import (
        assignments_marking as _marking,
    )
    return _marking.apply_marks(
        subs[0].submission_id, raw_marks=rollup.overall_marks,
        marked_by=marked_by, source="manual",
        reason=(f"Rolled up from {len(rollup.components)} component(s): "
                f"{rollup.weighted_percent:g}% weighted"))


def rollup_all(assignment_id: int, *,
                marked_by: str | None = None) -> dict[str, int]:
    """Roll every student's components up onto the parent assignment."""
    init_db()
    done = skipped = 0
    for sub in list_submissions(assignment_id=assignment_id):
        if apply_component_rollup(assignment_id, sub.student_id,
                                   marked_by=marked_by) is not None:
            done += 1
        else:
            skipped += 1
    logger.info("Component rollup on assignment #%d: %d applied, "
                "%d incomplete", assignment_id, done, skipped)
    return {"applied": done, "skipped": skipped}
