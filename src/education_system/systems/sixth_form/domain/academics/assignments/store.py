"""Sixth Form coursework assignments — DB plumbing, row mapping, validation,
assignment CRUD, submission/component reads and stored-file clean-up helpers.

Owns ``DB_PATH`` and ``_DB_READY``; the ``assignments`` facade forwards reads
and writes of those names here.

Split out of ``assignments.py``, which re-exports every name defined here."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import datetime as _dt
from education_system import paths
from education_system.systems.sixth_form.infrastructure import database as db
from education_system.systems.sixth_form.domain.academics.assignments.models import (
    ASSIGNMENT_STATUSES,
    ASSIGNMENT_TYPES,
    Assignment,
    AssignmentDetail,
    AssignmentRow,
    Attachment,
    DEFAULT_ASSIGNMENT_STATUS,
    DEFAULT_ASSIGNMENT_TYPE,
    DEFAULT_RELEASE_POLICY,
    DEFAULT_SUBMISSION_STATUS,
    DONE_SUBMISSION_STATUSES,
    RELEASE_POLICIES,
    SUBMISSION_STATUSES,
    Submission,
    SubmissionVersion,
    ValidationError,
    YEAR_GROUPS,
    _ASSIGNMENT_EXTRA_COLS,
    _DATE_RE,
    _SCHEMA,
    _SUBMISSION_EXTRA_COLS,
    logger,
)

DB_PATH = paths.SIXTH_FORM_ASSIGNMENTS_DB


# ── DB plumbing ────────────────────────────────────────────────────

def _connect() -> db.Connection:
    paths.ensure_sixth_form_directories()
    conn = db.connect(str(DB_PATH))
    conn.row_factory = db.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    _students.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        for table, cols in (
            ("coursework_assignments", _ASSIGNMENT_EXTRA_COLS),
            ("coursework_submissions", _SUBMISSION_EXTRA_COLS),
        ):
            have = {r["name"] for r in conn.execute(
                f"PRAGMA table_info({table})").fetchall()}
            for col, ddl in cols:
                if col not in have:
                    conn.execute(
                        f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")
        conn.commit()
    paths.SIXTH_FORM_COURSEWORK_FILES_DIR.mkdir(parents=True, exist_ok=True)
    logger.debug("Assignments schema ready at %s", DB_PATH)

    _DB_READY = True


def _row_assignment(r: db.Row) -> Assignment:
    return Assignment(
        assignment_id=r["assignment_id"], title=r["title"],
        subject_name=r["subject_name"],
        course_id=r["course_id"],
        class_group_id=r["class_group_id"],
        year_group=r["year_group"],
        assignment_type=r["assignment_type"],
        teacher=r["teacher"], set_date=r["set_date"],
        due_date=r["due_date"], max_marks=r["max_marks"],
        weight_percent=r["weight_percent"],
        brief=r["brief"], rubric=r["rubric"],
        resources=r["resources"],
        submission_method=r["submission_method"],
        status=r["status"], notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
        word_limit=r["word_limit"],
        allow_resubmission=bool(r["allow_resubmission"]),
        similarity_threshold=r["similarity_threshold"],
        late_penalty_percent_per_day=r["late_penalty_percent_per_day"],
        late_penalty_cap_percent=r["late_penalty_cap_percent"],
        late_penalty_grace_days=r["late_penalty_grace_days"] or 0,
        moderation_tolerance=r["moderation_tolerance"],
        honour_access_arrangements=bool(r["honour_access_arrangements"]),
        marking_sla_days=r["marking_sla_days"],
        anonymous_marking=bool(r["anonymous_marking"]),
        release_policy=r["release_policy"] or "Immediate",
        release_on=r["release_on"],
        released_at=r["released_at"],
        appeal_window_days=r["appeal_window_days"],
        is_group_assignment=bool(r["is_group_assignment"]),
        peer_assessment_weight=r["peer_assessment_weight"],
        self_assessment_required=bool(r["self_assessment_required"]),
        parent_assignment_id=r["parent_assignment_id"],
        component_weight=r["component_weight"],
        qualification=r["qualification"],
        exam_board=r["exam_board"], spec_code=r["spec_code"],
        unit_code=r["unit_code"], component_code=r["component_code"],
        assessment_objectives=r["assessment_objectives"],
        is_template=bool(r["is_template"]),
        template_name=r["template_name"],
        shared_with_department=bool(r["shared_with_department"]),
        source_assignment_id=r["source_assignment_id"],
        times_reused=r["times_reused"] or 0,
        estimated_hours=r["estimated_hours"],
        auto_publish=bool(r["auto_publish"]),
        published_on=r["published_on"],
        reminder_days=r["reminder_days"],
        chase_enabled=bool(r["chase_enabled"]),
        parent_visible=bool(r["parent_visible"]),
        calendar_event_id=r["calendar_event_id"],
        cover_marker=r["cover_marker"], cover_from=r["cover_from"],
        cover_until=r["cover_until"],
        cover_reason=r["cover_reason"],
    )


def _row_submission(r: db.Row) -> Submission:
    return Submission(
        submission_id=r["submission_id"],
        assignment_id=r["assignment_id"],
        student_id=r["student_id"], status=r["status"],
        submitted_on=r["submitted_on"], marks=r["marks"],
        grade=r["grade"], feedback=r["feedback"],
        marked_by=r["marked_by"], marked_on=r["marked_on"],
        notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
        attempt_no=r["attempt_no"] or 0,
        is_draft=bool(r["is_draft"]),
        word_count=r["word_count"],
        extended_due_date=r["extended_due_date"],
        extension_reason=r["extension_reason"],
        extension_by=r["extension_by"],
        extension_on=r["extension_on"],
        similarity_score=r["similarity_score"],
        similarity_provider=r["similarity_provider"],
        similarity_report=r["similarity_report"],
        similarity_checked_on=r["similarity_checked_on"],
        receipt_ref=r["receipt_ref"],
        auto_status_on=r["auto_status_on"],
        raw_marks=r["raw_marks"],
        penalty_percent=r["penalty_percent"],
        penalty_days=r["penalty_days"],
        penalty_waived=bool(r["penalty_waived"]),
        penalty_waived_reason=r["penalty_waived_reason"],
        sample_band=r["sample_band"],
        sample_note=r["sample_note"],
        sample_by=r["sample_by"],
        sample_on=r["sample_on"],
        access_arrangements=r["access_arrangements"],
        feedback_released=bool(r["feedback_released"]),
        feedback_released_on=r["feedback_released_on"],
        feedback_released_by=r["feedback_released_by"],
        acknowledged_on=r["acknowledged_on"],
        student_response=r["student_response"],
        group_id=r["group_id"],
        group_adjustment=r["group_adjustment"],
        peer_score=r["peer_score"],
        self_predicted_marks=r["self_predicted_marks"],
        self_assessment_note=r["self_assessment_note"],
        self_assessed_on=r["self_assessed_on"],
        objective_marks=r["objective_marks"],
        objective_marked_on=r["objective_marked_on"],
        variant_id=r["variant_id"],
        reminders_sent=r["reminders_sent"],
        chase_level=r["chase_level"] or 0,
        last_chased_on=r["last_chased_on"],
    )


def _row_version(r: db.Row) -> SubmissionVersion:
    return SubmissionVersion(
        version_id=r["version_id"],
        submission_id=r["submission_id"],
        attempt_no=r["attempt_no"],
        is_draft=bool(r["is_draft"]),
        status=r["status"],
        submitted_on=r["submitted_on"],
        submitted_at=r["submitted_at"],
        submitted_by=r["submitted_by"],
        word_count=r["word_count"],
        similarity_score=r["similarity_score"],
        receipt_ref=r["receipt_ref"],
        receipt_hash=r["receipt_hash"],
        receipt_path=r["receipt_path"],
        note=r["note"],
        created_at=r["created_at"],
    )


def _row_attachment(r: db.Row) -> Attachment:
    return Attachment(
        attachment_id=r["attachment_id"],
        assignment_id=r["assignment_id"],
        submission_id=r["submission_id"],
        version_id=r["version_id"],
        kind=r["kind"], filename=r["filename"],
        stored_path=r["stored_path"],
        byte_size=r["byte_size"] or 0,
        sha256=r["sha256"], content_type=r["content_type"],
        uploaded_by=r["uploaded_by"], uploaded_at=r["uploaded_at"],
        notes=r["notes"],
    )


def _require(value, label: str):
    if value in (None, "") or (isinstance(value, str)
                                  and not value.strip()):
        raise ValidationError(f"{label} is required")
    return value


def _validate_date(value: Any, label: str, *,
                    required: bool = False) -> str | None:
    if value in (None, "") or (isinstance(value, str)
                                  and not value.strip()):
        if required:
            raise ValidationError(f"{label} is required")
        return None
    s = str(value).strip()
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    try:
        _dt.date.fromisoformat(s)
    except ValueError:
        raise ValidationError(f"{label} is not a real date") from None
    return s


def _validate_number(value: Any, label: str, *,
                      min_val: float | None = None,
                      max_val: float | None = None) -> float | None:
    if value in (None, "") or (isinstance(value, str)
                                  and not value.strip()):
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{label} must be a number") from None
    if min_val is not None and f < min_val:
        raise ValidationError(f"{label} must be at least {min_val}")
    if max_val is not None and f > max_val:
        raise ValidationError(f"{label} must be at most {max_val}")
    return f


def _validate_subject(value: Any) -> str:
    name = _require(value, "Subject").strip()
    try:
        from education_system.systems.sixth_form.domain.academics.subjects import (
            subjects as _subjects,
        )
        names = {x.name for x in _subjects.list_subjects()}
        if names and name not in names:
            raise ValidationError(
                f"Subject {name!r} not in catalogue")
    except ValidationError:
        raise
    except Exception:
        pass
    return name


def _validate_assignment_payload(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["title"] = _require(payload.get("title"), "Title").strip()
    out["subject_name"] = _validate_subject(payload.get("subject_name"))

    atype = (payload.get("assignment_type")
              or DEFAULT_ASSIGNMENT_TYPE).strip()
    if atype not in ASSIGNMENT_TYPES:
        raise ValidationError(
            f"Type must be one of: {', '.join(ASSIGNMENT_TYPES)}")
    out["assignment_type"] = atype

    status = (payload.get("status")
                or DEFAULT_ASSIGNMENT_STATUS).strip()
    if status not in ASSIGNMENT_STATUSES:
        raise ValidationError(
            f"Status must be one of: "
            f"{', '.join(ASSIGNMENT_STATUSES)}")
    out["status"] = status

    year = (payload.get("year_group") or "").strip()
    if year and year not in YEAR_GROUPS:
        raise ValidationError(
            f"Year group must be one of: {', '.join(YEAR_GROUPS)}")
    out["year_group"] = year or None

    out["teacher"] = (payload.get("teacher") or "").strip() or None
    out["set_date"] = _validate_date(payload.get("set_date"),
                                          "Set date")
    out["due_date"] = _validate_date(payload.get("due_date"),
                                          "Due date")
    if (out["set_date"] and out["due_date"]
            and out["due_date"] < out["set_date"]):
        raise ValidationError(
            "Due date cannot be before set date")

    out["max_marks"] = _validate_number(payload.get("max_marks"),
                                            "Max marks", min_val=0)
    out["weight_percent"] = _validate_number(
        payload.get("weight_percent"), "Weight %",
        min_val=0, max_val=100)

    limit = _validate_number(payload.get("word_limit"), "Word limit",
                              min_val=1)
    out["word_limit"] = int(limit) if limit is not None else None
    out["similarity_threshold"] = _validate_number(
        payload.get("similarity_threshold"), "Similarity threshold %",
        min_val=0, max_val=100)
    allow = payload.get("allow_resubmission", True)
    out["allow_resubmission"] = 0 if allow in (False, 0, "0", "No",
                                                "no", "false") else 1

    out["late_penalty_percent_per_day"] = _validate_number(
        payload.get("late_penalty_percent_per_day"),
        "Late penalty % per day", min_val=0, max_val=100)
    out["late_penalty_cap_percent"] = _validate_number(
        payload.get("late_penalty_cap_percent"),
        "Late penalty cap %", min_val=0, max_val=100)
    grace = _validate_number(payload.get("late_penalty_grace_days"),
                              "Late penalty grace days", min_val=0)
    out["late_penalty_grace_days"] = int(grace) if grace else 0
    out["moderation_tolerance"] = _validate_number(
        payload.get("moderation_tolerance"),
        "Moderation tolerance", min_val=0)
    honour = payload.get("honour_access_arrangements", True)
    out["honour_access_arrangements"] = 0 if honour in (
        False, 0, "0", "No", "no", "false") else 1

    def _flag(key: str, default: Any = False) -> int:
        value = payload.get(key, default)
        return 0 if value in (False, 0, "0", "No", "no", "false",
                               "", None) else 1

    sla = _validate_number(payload.get("marking_sla_days"),
                            "Marking SLA days", min_val=0)
    out["marking_sla_days"] = int(sla) if sla is not None else None
    out["anonymous_marking"] = _flag("anonymous_marking")

    policy = (payload.get("release_policy")
               or DEFAULT_RELEASE_POLICY).strip()
    if policy not in RELEASE_POLICIES:
        raise ValidationError(
            f"Release policy must be one of: "
            f"{', '.join(RELEASE_POLICIES)}")
    out["release_policy"] = policy
    out["release_on"] = _validate_date(payload.get("release_on"),
                                        "Release date")
    if policy == "On date" and not out["release_on"]:
        raise ValidationError(
            "A release date is required when the policy is 'On date'")
    out["released_at"] = (payload.get("released_at") or "").strip() or None

    window = _validate_number(payload.get("appeal_window_days"),
                               "Appeal window days", min_val=0)
    out["appeal_window_days"] = int(window) if window is not None else None

    out["is_group_assignment"] = _flag("is_group_assignment")
    out["peer_assessment_weight"] = _validate_number(
        payload.get("peer_assessment_weight"),
        "Peer assessment weight %", min_val=0, max_val=100)
    out["self_assessment_required"] = _flag("self_assessment_required")

    out["parent_assignment_id"] = None
    if payload.get("parent_assignment_id") not in (None, ""):
        try:
            out["parent_assignment_id"] = int(
                payload["parent_assignment_id"])
        except (TypeError, ValueError):
            raise ValidationError(
                "parent_assignment_id must be a number") from None
    out["component_weight"] = _validate_number(
        payload.get("component_weight"), "Component weight %",
        min_val=0, max_val=100)

    def _text(key: str) -> str | None:
        return (str(payload.get(key) or "").strip() or None)

    out["qualification"]         = _text("qualification")
    out["exam_board"]            = _text("exam_board")
    out["spec_code"]             = _text("spec_code")
    out["unit_code"]             = _text("unit_code")
    out["component_code"]        = _text("component_code")
    out["assessment_objectives"] = _text("assessment_objectives")
    out["template_name"]         = _text("template_name")
    out["cover_marker"]          = _text("cover_marker")
    out["cover_reason"]          = _text("cover_reason")
    out["published_on"]          = _validate_date(
        payload.get("published_on"), "Published on")
    out["cover_from"]            = _validate_date(
        payload.get("cover_from"), "Cover from")
    out["cover_until"]           = _validate_date(
        payload.get("cover_until"), "Cover until")
    if (out["cover_from"] and out["cover_until"]
            and out["cover_until"] < out["cover_from"]):
        raise ValidationError(
            "Cover cannot end before it starts")

    out["is_template"]            = _flag("is_template")
    out["shared_with_department"] = _flag("shared_with_department")
    out["auto_publish"]           = _flag("auto_publish")
    out["chase_enabled"]          = _flag("chase_enabled", True)
    out["parent_visible"]         = _flag("parent_visible", True)

    hours = _validate_number(payload.get("estimated_hours"),
                              "Estimated hours", min_val=0)
    out["estimated_hours"] = hours
    reused = _validate_number(payload.get("times_reused"),
                               "Times reused", min_val=0)
    out["times_reused"] = int(reused) if reused else 0

    for key in ("source_assignment_id", "calendar_event_id"):
        out[key] = None
        if payload.get(key) not in (None, ""):
            try:
                out[key] = int(payload[key])
            except (TypeError, ValueError):
                raise ValidationError(
                    f"{key} must be a number") from None

    # Reminder offsets are stored as a sorted, de-duplicated CSV of
    # days-before-due, so "7, 3, 3, 1" and "1,3,7" mean the same thing.
    raw_days = payload.get("reminder_days")
    if raw_days in (None, ""):
        out["reminder_days"] = None
    else:
        if isinstance(raw_days, (list, tuple, set)):
            candidates = list(raw_days)
        else:
            candidates = [p for p in str(raw_days).split(",")]
        days: set[int] = set()
        for candidate in candidates:
            text = str(candidate).strip()
            if not text:
                continue
            try:
                value = int(text)
            except ValueError:
                raise ValidationError(
                    f"Reminder days must be whole numbers, "
                    f"got {text!r}") from None
            if value < 0:
                raise ValidationError(
                    "Reminder days count backwards from the due date, "
                    "so they cannot be negative")
            days.add(value)
        out["reminder_days"] = (",".join(str(d) for d in
                                          sorted(days, reverse=True))
                                 or None)

    out["course_id"] = None
    if payload.get("course_id") not in (None, ""):
        try:
            out["course_id"] = int(payload.get("course_id"))
        except (TypeError, ValueError):
            raise ValidationError(
                "course_id must be a number") from None
    out["class_group_id"] = None
    if payload.get("class_group_id") not in (None, ""):
        try:
            out["class_group_id"] = int(payload.get("class_group_id"))
        except (TypeError, ValueError):
            raise ValidationError(
                "class_group_id must be a number") from None

    out["brief"]             = (payload.get("brief")
                                  or "").strip() or None
    out["rubric"]            = (payload.get("rubric")
                                  or "").strip() or None
    out["resources"]         = (payload.get("resources")
                                  or "").strip() or None
    out["submission_method"] = (payload.get("submission_method")
                                  or "").strip() or None
    out["notes"]             = (payload.get("notes")
                                  or "").strip() or None
    return out


def _validate_submission_payload(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    aid = payload.get("assignment_id")
    if aid in (None, ""):
        raise ValidationError("Assignment id is required")
    try:
        out["assignment_id"] = int(aid)
    except (TypeError, ValueError):
        raise ValidationError(
            "Assignment id must be a number") from None
    if get_assignment(out["assignment_id"]) is None:
        raise ValidationError(
            f"No assignment #{out['assignment_id']}")

    sid = _require(payload.get("student_id"), "Student").strip()
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    if _students.get_student(sid) is None:
        raise ValidationError(f"No student with id {sid}")
    out["student_id"] = sid

    status = (payload.get("status") or DEFAULT_SUBMISSION_STATUS).strip()
    if status not in SUBMISSION_STATUSES:
        raise ValidationError(
            f"Submission status must be one of: "
            f"{', '.join(SUBMISSION_STATUSES)}")
    out["status"] = status

    out["submitted_on"] = _validate_date(
        payload.get("submitted_on"), "Submitted on")
    out["marks"] = _validate_number(payload.get("marks"),
                                        "Marks", min_val=0)

    assignment = get_assignment(out["assignment_id"])
    if (assignment and assignment.max_marks is not None
            and out["marks"] is not None
            and out["marks"] > assignment.max_marks):
        raise ValidationError(
            f"Marks ({out['marks']}) exceed max_marks "
            f"({assignment.max_marks})")

    wc = _validate_number(payload.get("word_count"), "Word count",
                            min_val=0)
    out["word_count"] = int(wc) if wc is not None else None
    draft = payload.get("is_draft", False)
    out["is_draft"] = 1 if draft in (True, 1, "1", "Yes", "yes",
                                       "true") else 0

    out["grade"]      = (payload.get("grade") or "").strip() or None
    out["feedback"]   = (payload.get("feedback") or "").strip() or None
    out["marked_by"]  = (payload.get("marked_by") or "").strip() or None
    out["marked_on"]  = _validate_date(payload.get("marked_on"),
                                            "Marked on")
    out["notes"]      = (payload.get("notes") or "").strip() or None

    if (out["status"] in DONE_SUBMISSION_STATUSES
            and not out["submitted_on"]
            and out["status"] in ("Submitted", "Late", "Returned")):
        out["submitted_on"] = _dt.date.today().isoformat()
    if out["marks"] is not None and not out["marked_on"]:
        out["marked_on"] = _dt.date.today().isoformat()
    return out


# ── Assignment CRUD ───────────────────────────────────────────────

def create_assignment(payload: dict[str, Any]) -> Assignment:
    init_db()
    p = _validate_assignment_payload(payload)
    _validate_parent_link(None, p["parent_assignment_id"])
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO coursework_assignments
                   (title, subject_name, course_id, class_group_id,
                    year_group, assignment_type, teacher,
                    set_date, due_date, max_marks, weight_percent,
                    brief, rubric, resources, submission_method,
                    status, notes, word_limit, allow_resubmission,
                    similarity_threshold,
                    late_penalty_percent_per_day,
                    late_penalty_cap_percent, late_penalty_grace_days,
                    moderation_tolerance, honour_access_arrangements,
                    marking_sla_days, anonymous_marking,
                    release_policy, release_on, appeal_window_days,
                    is_group_assignment, peer_assessment_weight,
                    self_assessment_required, parent_assignment_id,
                    component_weight,
                    qualification, exam_board, spec_code, unit_code,
                    component_code, assessment_objectives,
                    is_template, template_name,
                    shared_with_department, source_assignment_id,
                    times_reused, estimated_hours,
                    auto_publish, published_on, reminder_days,
                    chase_enabled, parent_visible, calendar_event_id,
                    cover_marker, cover_from, cover_until,
                    cover_reason,
                    created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       ?, ?, ?, ?, ?, ?, ?, ?,
                       ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["title"], p["subject_name"], p["course_id"],
             p["class_group_id"], p["year_group"],
             p["assignment_type"], p["teacher"],
             p["set_date"], p["due_date"], p["max_marks"],
             p["weight_percent"], p["brief"], p["rubric"],
             p["resources"], p["submission_method"],
             p["status"], p["notes"], p["word_limit"],
             p["allow_resubmission"], p["similarity_threshold"],
             p["late_penalty_percent_per_day"],
             p["late_penalty_cap_percent"],
             p["late_penalty_grace_days"],
             p["moderation_tolerance"],
             p["honour_access_arrangements"],
             p["marking_sla_days"], p["anonymous_marking"],
             p["release_policy"], p["release_on"],
             p["appeal_window_days"], p["is_group_assignment"],
             p["peer_assessment_weight"],
             p["self_assessment_required"],
             p["parent_assignment_id"], p["component_weight"],
             p["qualification"], p["exam_board"], p["spec_code"],
             p["unit_code"], p["component_code"],
             p["assessment_objectives"], p["is_template"],
             p["template_name"], p["shared_with_department"],
             p["source_assignment_id"], p["times_reused"],
             p["estimated_hours"], p["auto_publish"],
             p["published_on"], p["reminder_days"],
             p["chase_enabled"], p["parent_visible"],
             p["calendar_event_id"], p["cover_marker"],
             p["cover_from"], p["cover_until"], p["cover_reason"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_assignment(new_id)
    assert out is not None
    logger.info(
        "Created assignment #%d %r (%s, due %s, status %s)",
        new_id, p["title"], p["subject_name"], p["due_date"],
        p["status"])
    _notify_students_assignment_created(out)
    return out


def _students_on_course(course_id: int) -> list[str]:
    """Return distinct student_ids enrolled in any class group of a course."""
    from education_system.systems.sixth_form.domain.academics.class_groups import (
        class_groups as _cg,
    )
    seen: set[str] = set()
    ordered: list[str] = []
    for g in _cg.list_groups(course_id=course_id):
        for sid in _cg.list_members(g.group_id):
            if sid not in seen:
                seen.add(sid)
                ordered.append(sid)
    return ordered


def _notify_students_assignment_created(a: Assignment) -> None:
    """Email every student on the assignment's course. Best-effort."""
    if a.course_id is None:
        return
    try:
        from education_system.systems.sixth_form import SYSTEM_NAME
        from education_system.systems.sixth_form.domain.academics.courses import (
            courses as _courses,
        )
        from education_system.systems.sixth_form.domains.communications.domain.messages import (
            email_templates,
        )
        from education_system.systems.sixth_form.domain.learners.students import (
            students as _students,
        )
        course = _courses.get_course(a.course_id)
        student_ids = _students_on_course(a.course_id)
        if not student_ids:
            logger.info(
                "Assignment #%d: no students on course #%d to notify",
                a.assignment_id, a.course_id)
            return
        sent = 0
        for sid in student_ids:
            student = _students.get_student(sid)
            if student is None:
                continue
            try:
                email_templates.send_from_template(
                    "assignment_set",
                    {
                        "system_name":       SYSTEM_NAME,
                        "first_name":        student.first_name,
                        "full_name":         student.full_name,
                        "student_id":        student.student_id,
                        "title":             a.title,
                        "subject_name":      a.subject_name,
                        "assignment_type":   a.assignment_type,
                        "teacher":           a.teacher or "your teacher",
                        "set_date":          a.set_date or "—",
                        "due_date":          a.due_date or "—",
                        "max_marks":         (str(a.max_marks)
                                                if a.max_marks is not None
                                                else "—"),
                        "submission_method": (a.submission_method
                                                or "see the portal"),
                        "brief":             (a.brief
                                                or "(See the portal for full details.)"),
                        "course_code":       (course.course_code
                                                if course else "—"),
                        "course_title":      (course.title
                                                if course else "—"),
                    },
                    to_name=student.full_name,
                    to_address=student.email,
                    student_id=student.student_id,
                )
                sent += 1
            except Exception:
                logger.exception(
                    "assignment_set email failed for student %s "
                    "(assignment #%d)",
                    sid, a.assignment_id)
        logger.info(
            "Assignment #%d: notified %d/%d student(s) on course #%d",
            a.assignment_id, sent, len(student_ids), a.course_id)
    except Exception:
        logger.exception(
            "Could not notify students for assignment #%d",
            a.assignment_id)


def get_assignment(assignment_id: int) -> Assignment | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM coursework_assignments WHERE assignment_id = ?",
            (assignment_id,)).fetchone()
        return _row_assignment(r) if r else None


def list_assignments(
    *,
    subject_name: str | None = None,
    teacher_like: str | None = None,
    status: str | None = None,
    assignment_type: str | None = None,
    year_group: str | None = None,
    course_id: int | None = None,
    class_group_id: int | None = None,
    open_only: bool = False,
    overdue_only: bool = False,
    title_like: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[Assignment]:
    init_db()
    clauses, args = [], []
    if subject_name:
        clauses.append("subject_name = ?")
        args.append(subject_name.strip())
    if teacher_like:
        clauses.append("teacher LIKE ?")
        args.append(f"%{teacher_like.strip()}%")
    if status:
        if status not in ASSIGNMENT_STATUSES:
            raise ValidationError(
                f"Status must be one of: "
                f"{', '.join(ASSIGNMENT_STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if assignment_type:
        if assignment_type not in ASSIGNMENT_TYPES:
            raise ValidationError(
                f"Type must be one of: "
                f"{', '.join(ASSIGNMENT_TYPES)}")
        clauses.append("assignment_type = ?")
        args.append(assignment_type)
    if year_group:
        if year_group not in YEAR_GROUPS:
            raise ValidationError(
                f"Year group must be one of: "
                f"{', '.join(YEAR_GROUPS)}")
        clauses.append("year_group = ?")
        args.append(year_group)
    if course_id is not None:
        clauses.append("course_id = ?")
        args.append(int(course_id))
    if class_group_id is not None:
        clauses.append("class_group_id = ?")
        args.append(int(class_group_id))
    if open_only:
        clauses.append("status IN ('Draft', 'Set')")
    if overdue_only:
        today = _dt.date.today().isoformat()
        clauses.append("due_date IS NOT NULL AND due_date < ? "
                       "AND status IN ('Draft', 'Set')")
        args.append(today)
    if title_like:
        clauses.append("title LIKE ?")
        args.append(f"%{title_like.strip()}%")
    if date_from:
        clauses.append("due_date >= ?")
        args.append(_validate_date(date_from, "date_from"))
    if date_to:
        clauses.append("due_date <= ?")
        args.append(_validate_date(date_to, "date_to"))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM coursework_assignments {where} "
           "ORDER BY CASE WHEN due_date IS NULL THEN 1 ELSE 0 END, "
           "due_date ASC, assignment_id ASC")
    with _connect() as conn:
        return [_row_assignment(r)
                for r in conn.execute(sql, args).fetchall()]


def list_assignments_with_detail(**kwargs) -> list[AssignmentRow]:
    rows = list_assignments(**kwargs)
    if not rows:
        return []
    with _connect() as conn:
        out: list[AssignmentRow] = []
        for a in rows:
            stats = conn.execute(
                f"SELECT COUNT(*) total, "
                f"  SUM(CASE WHEN status IN "
                f"    ({','.join('?' * len(DONE_SUBMISSION_STATUSES))}) "
                f"    THEN 1 ELSE 0 END) AS done, "
                f"  SUM(CASE WHEN marks IS NOT NULL "
                f"    THEN 1 ELSE 0 END) AS marked, "
                f"  AVG(marks) AS avg_marks "
                f"FROM coursework_submissions "
                f"WHERE assignment_id = ?",
                (*DONE_SUBMISSION_STATUSES, a.assignment_id)).fetchone()
            out.append(AssignmentRow(
                assignment=a,
                total_submissions=stats["total"] or 0,
                submitted_count=stats["done"] or 0,
                marked_count=stats["marked"] or 0,
                average_mark=(round(stats["avg_marks"], 2)
                                if stats["avg_marks"] is not None
                                else None),
            ))
    return out


def get_assignment_detail(assignment_id: int) -> AssignmentDetail | None:
    init_db()
    a = get_assignment(assignment_id)
    if a is None:
        return None
    subs = list_submissions(assignment_id=assignment_id)
    return AssignmentDetail(assignment=a, submissions=subs)


def update_assignment(assignment_id: int,
                       payload: dict[str, Any]) -> Assignment:
    init_db()
    existing = get_assignment(assignment_id)
    if existing is None:
        raise ValidationError(f"No assignment #{assignment_id}")
    merged = {
        "title":             payload.get("title", existing.title),
        "subject_name":      payload.get("subject_name",
                                          existing.subject_name),
        "course_id":         payload.get("course_id",
                                          existing.course_id),
        "class_group_id":    payload.get("class_group_id",
                                          existing.class_group_id),
        "year_group":        payload.get("year_group",
                                          existing.year_group),
        "assignment_type":   payload.get("assignment_type",
                                          existing.assignment_type),
        "teacher":           payload.get("teacher", existing.teacher),
        "set_date":          payload.get("set_date",
                                          existing.set_date),
        "due_date":          payload.get("due_date",
                                          existing.due_date),
        "max_marks":         payload.get("max_marks",
                                          existing.max_marks),
        "weight_percent":    payload.get("weight_percent",
                                          existing.weight_percent),
        "brief":             payload.get("brief", existing.brief),
        "rubric":            payload.get("rubric", existing.rubric),
        "resources":         payload.get("resources",
                                          existing.resources),
        "submission_method": payload.get("submission_method",
                                          existing.submission_method),
        "status":            payload.get("status", existing.status),
        "notes":             payload.get("notes", existing.notes),
        "word_limit":        payload.get("word_limit",
                                          existing.word_limit),
        "allow_resubmission": payload.get("allow_resubmission",
                                            existing.allow_resubmission),
        "similarity_threshold": payload.get(
            "similarity_threshold", existing.similarity_threshold),
        "late_penalty_percent_per_day": payload.get(
            "late_penalty_percent_per_day",
            existing.late_penalty_percent_per_day),
        "late_penalty_cap_percent": payload.get(
            "late_penalty_cap_percent",
            existing.late_penalty_cap_percent),
        "late_penalty_grace_days": payload.get(
            "late_penalty_grace_days", existing.late_penalty_grace_days),
        "moderation_tolerance": payload.get(
            "moderation_tolerance", existing.moderation_tolerance),
        "honour_access_arrangements": payload.get(
            "honour_access_arrangements",
            existing.honour_access_arrangements),
        "marking_sla_days": payload.get("marking_sla_days",
                                          existing.marking_sla_days),
        "anonymous_marking": payload.get("anonymous_marking",
                                           existing.anonymous_marking),
        "release_policy": payload.get("release_policy",
                                        existing.release_policy),
        "release_on": payload.get("release_on", existing.release_on),
        "appeal_window_days": payload.get("appeal_window_days",
                                            existing.appeal_window_days),
        "is_group_assignment": payload.get(
            "is_group_assignment", existing.is_group_assignment),
        "peer_assessment_weight": payload.get(
            "peer_assessment_weight", existing.peer_assessment_weight),
        "self_assessment_required": payload.get(
            "self_assessment_required",
            existing.self_assessment_required),
        "parent_assignment_id": payload.get(
            "parent_assignment_id", existing.parent_assignment_id),
        "component_weight": payload.get("component_weight",
                                          existing.component_weight),
    }
    for key in ("qualification", "exam_board", "spec_code",
                 "unit_code", "component_code",
                 "assessment_objectives", "is_template",
                 "template_name", "shared_with_department",
                 "source_assignment_id", "times_reused",
                 "estimated_hours", "auto_publish", "published_on",
                 "reminder_days", "chase_enabled", "parent_visible",
                 "calendar_event_id", "cover_marker", "cover_from",
                 "cover_until", "cover_reason"):
        merged[key] = payload.get(key, getattr(existing, key))
    p = _validate_assignment_payload(merged)
    _validate_parent_link(assignment_id, p["parent_assignment_id"])
    with _connect() as conn:
        conn.execute(
            """UPDATE coursework_assignments SET
                   title = ?, subject_name = ?, course_id = ?,
                   class_group_id = ?, year_group = ?,
                   assignment_type = ?, teacher = ?, set_date = ?,
                   due_date = ?, max_marks = ?, weight_percent = ?,
                   brief = ?, rubric = ?, resources = ?,
                   submission_method = ?, status = ?, notes = ?,
                   word_limit = ?, allow_resubmission = ?,
                   similarity_threshold = ?,
                   late_penalty_percent_per_day = ?,
                   late_penalty_cap_percent = ?,
                   late_penalty_grace_days = ?,
                   moderation_tolerance = ?,
                   honour_access_arrangements = ?,
                   marking_sla_days = ?, anonymous_marking = ?,
                   release_policy = ?, release_on = ?,
                   appeal_window_days = ?, is_group_assignment = ?,
                   peer_assessment_weight = ?,
                   self_assessment_required = ?,
                   parent_assignment_id = ?, component_weight = ?,
                   qualification = ?, exam_board = ?, spec_code = ?,
                   unit_code = ?, component_code = ?,
                   assessment_objectives = ?, is_template = ?,
                   template_name = ?, shared_with_department = ?,
                   source_assignment_id = ?, times_reused = ?,
                   estimated_hours = ?, auto_publish = ?,
                   published_on = ?, reminder_days = ?,
                   chase_enabled = ?, parent_visible = ?,
                   calendar_event_id = ?, cover_marker = ?,
                   cover_from = ?, cover_until = ?, cover_reason = ?,
                   updated_at = datetime('now')
               WHERE assignment_id = ?""",
            (p["title"], p["subject_name"], p["course_id"],
             p["class_group_id"], p["year_group"],
             p["assignment_type"], p["teacher"],
             p["set_date"], p["due_date"], p["max_marks"],
             p["weight_percent"], p["brief"], p["rubric"],
             p["resources"], p["submission_method"],
             p["status"], p["notes"], p["word_limit"],
             p["allow_resubmission"], p["similarity_threshold"],
             p["late_penalty_percent_per_day"],
             p["late_penalty_cap_percent"],
             p["late_penalty_grace_days"],
             p["moderation_tolerance"],
             p["honour_access_arrangements"],
             p["marking_sla_days"], p["anonymous_marking"],
             p["release_policy"], p["release_on"],
             p["appeal_window_days"], p["is_group_assignment"],
             p["peer_assessment_weight"],
             p["self_assessment_required"],
             p["parent_assignment_id"], p["component_weight"],
             p["qualification"], p["exam_board"], p["spec_code"],
             p["unit_code"], p["component_code"],
             p["assessment_objectives"], p["is_template"],
             p["template_name"], p["shared_with_department"],
             p["source_assignment_id"], p["times_reused"],
             p["estimated_hours"], p["auto_publish"],
             p["published_on"], p["reminder_days"],
             p["chase_enabled"], p["parent_visible"],
             p["calendar_event_id"], p["cover_marker"],
             p["cover_from"], p["cover_until"], p["cover_reason"],
             assignment_id),
        )
        conn.commit()
    out = get_assignment(assignment_id)
    assert out is not None
    logger.info("Updated assignment #%d (status=%s)",
                assignment_id, out.status)
    return out


def set_assignment_status(assignment_id: int,
                          status: str) -> Assignment:
    if status not in ASSIGNMENT_STATUSES:
        raise ValidationError(
            f"Status must be one of: "
            f"{', '.join(ASSIGNMENT_STATUSES)}")
    return update_assignment(assignment_id, {"status": status})


def delete_assignment(assignment_id: int) -> bool:
    init_db()
    with _connect() as conn:
        # Collect file paths before the cascade removes the rows that
        # point at them — SQLite cannot delete from disk.
        stored = _stored_paths_for_assignment(conn, assignment_id)
        receipts = [r["receipt_path"] for r in conn.execute(
            """SELECT receipt_path FROM coursework_submission_versions
               WHERE receipt_path IS NOT NULL
                 AND submission_id IN (SELECT submission_id
                                         FROM coursework_submissions
                                        WHERE assignment_id = ?)""",
            (assignment_id,)).fetchall()]
        cur = conn.execute(
            "DELETE FROM coursework_assignments WHERE assignment_id = ?",
            (assignment_id,))
        conn.commit()
        deleted = bool(cur.rowcount)
    if deleted:
        _unlink_stored(stored + receipts)
        logger.info(
            "Deleted assignment #%d (cascade: submissions, versions, "
            "%d file(s))", assignment_id, len(stored) + len(receipts))
    return deleted


def get_submission(submission_id: int) -> Submission | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM coursework_submissions "
            "WHERE submission_id = ?",
            (submission_id,)).fetchone()
        return _row_submission(r) if r else None


def list_submissions(
    *,
    assignment_id: int | None = None,
    student_id: str | None = None,
    status: str | None = None,
    done_only: bool = False,
    marked_only: bool = False,
    unmarked_only: bool = False,
) -> list[Submission]:
    init_db()
    clauses, args = [], []
    if assignment_id is not None:
        clauses.append("assignment_id = ?")
        args.append(int(assignment_id))
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if status:
        if status not in SUBMISSION_STATUSES:
            raise ValidationError(
                f"Status must be one of: "
                f"{', '.join(SUBMISSION_STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if done_only:
        ph = ",".join("?" * len(DONE_SUBMISSION_STATUSES))
        clauses.append(f"status IN ({ph})")
        args.extend(DONE_SUBMISSION_STATUSES)
    if marked_only:
        clauses.append("marks IS NOT NULL")
    if unmarked_only:
        clauses.append("marks IS NULL")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM coursework_submissions {where} "
           "ORDER BY assignment_id ASC, student_id ASC")
    with _connect() as conn:
        return [_row_submission(r)
                for r in conn.execute(sql, args).fetchall()]


# ── Multi-part assignments ────────────────────────────────────────

def _validate_parent_link(assignment_id: int | None,
                           parent_id: int | None) -> None:
    """Refuse a parent link that would create a cycle or a deep tree.

    Composition is deliberately one level: an NEA has components, but a
    component cannot itself have components. Two levels would make the
    weighted rollup ambiguous without buying anything a flat list of
    components doesn't already give you.
    """
    if parent_id is None:
        return
    if assignment_id is not None and parent_id == assignment_id:
        raise ValidationError("An assignment cannot be its own parent")
    parent = get_assignment(parent_id)
    if parent is None:
        raise ValidationError(f"No assignment #{parent_id} to be a parent")
    if parent.parent_assignment_id is not None:
        raise ValidationError(
            f"Assignment #{parent_id} is itself a component — "
            f"components cannot be nested")
    if assignment_id is not None and list_components(assignment_id):
        raise ValidationError(
            f"Assignment #{assignment_id} already has components of its "
            f"own, so it cannot become a component")


def list_components(assignment_id: int) -> list[Assignment]:
    """Child assignments that make up this one, in due-date order."""
    init_db()
    with _connect() as conn:
        return [_row_assignment(r) for r in conn.execute(
            "SELECT * FROM coursework_assignments "
            "WHERE parent_assignment_id = ? "
            "ORDER BY CASE WHEN due_date IS NULL THEN 1 ELSE 0 END, "
            "due_date ASC, assignment_id ASC",
            (int(assignment_id),)).fetchall()]


def _unlink_stored(rel_paths: list[str]) -> None:
    """Best-effort removal of stored files and any dirs left empty."""
    root = paths.SIXTH_FORM_COURSEWORK_FILES_DIR
    parents: set[Path] = set()
    for rel in rel_paths:
        if not rel:
            continue
        target = root / rel
        try:
            target.unlink(missing_ok=True)
            parents.add(target.parent)
        except OSError:
            logger.warning("Could not remove coursework file %s", target)
    # Walk upwards removing directories that are now empty, stopping at
    # the store root.
    for parent in sorted(parents, key=lambda p: len(p.parts), reverse=True):
        node = parent
        while node != root and root in node.parents:
            try:
                node.rmdir()
            except OSError:
                break
            node = node.parent


def _stored_paths_for_assignment(conn: db.Connection,
                                  assignment_id: int) -> list[str]:
    rows = conn.execute(
        """SELECT stored_path FROM coursework_attachments
           WHERE assignment_id = ?
              OR submission_id IN (SELECT submission_id
                                     FROM coursework_submissions
                                    WHERE assignment_id = ?)""",
        (assignment_id, assignment_id)).fetchall()
    return [r["stored_path"] for r in rows]


def _stored_paths_for_submission(conn: db.Connection,
                                  submission_id: int) -> list[str]:
    rows = conn.execute(
        "SELECT stored_path FROM coursework_attachments "
        "WHERE submission_id = ?", (submission_id,)).fetchall()
    paths_out = [r["stored_path"] for r in rows]
    receipts = conn.execute(
        "SELECT receipt_path FROM coursework_submission_versions "
        "WHERE submission_id = ? AND receipt_path IS NOT NULL",
        (submission_id,)).fetchall()
    paths_out.extend(r["receipt_path"] for r in receipts)
    return paths_out
