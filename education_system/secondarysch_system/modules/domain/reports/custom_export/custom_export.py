"""Custom Export for the Secondary School System.

A small, focused export engine: pick a dataset, optionally filter,
optionally choose columns, and write CSV / TSV / JSON / JSONL /
Markdown. Read-only — nothing here mutates state.

Datasets are registered in ``DATASETS``. Each entry knows:
* ``label``       — human name
* ``description`` — one-liner
* ``columns``     — ordered list of ``(key, header)`` tuples
* ``list_fn``     — callable returning an iterable of objects/dicts
* ``filter_keys`` — keyword arg names the ``list_fn`` accepts
"""

from __future__ import annotations

import csv
import io
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable
from education_system.secondarysch_system.modules.domain.reports.custom_export import custom_export as data

logger = logging.getLogger(__name__)

FORMATS: tuple[str, ...] = (
    "csv", "tsv", "json", "jsonl", "markdown",
)
DEFAULT_FORMAT: str = "csv"


# ── Result types ──────────────────────────────────────────────────

class ValidationError(ValueError):
    pass


@dataclass
class DatasetSpec:
    key: str
    label: str
    description: str
    columns: list[tuple[str, str]]
    list_fn: Callable[..., Iterable[Any]]
    filter_keys: list[str] = field(default_factory=list)


@dataclass
class ExportResult:
    dataset_key: str
    fmt: str
    row_count: int
    column_count: int
    path: str | None        # None if written to a buffer
    bytes_written: int


# ── Cell helpers ──────────────────────────────────────────────────

def _get(row: Any, key: str) -> Any:
    """Pull a value by ``key`` from a dataclass / dict / dotted path
    on an object. Returns None if the path can't be resolved."""
    cur = row
    for part in key.split("."):
        if cur is None:
            return None
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            cur = getattr(cur, part, None)
    return cur


def _stringify(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (list, tuple)):
        return ", ".join(_stringify(x) for x in v)
    return str(v)


def _json_safe(v: Any) -> Any:
    if v is None or isinstance(v, (str, int, float, bool)):
        return v
    if isinstance(v, dict):
        return {k: _json_safe(x) for k, x in v.items()}
    if isinstance(v, (list, tuple, set)):
        return [_json_safe(x) for x in v]
    return _stringify(v)


# ── Registry ──────────────────────────────────────────────────────

def _build_registry() -> dict[str, DatasetSpec]:
    # Source modules are loaded defensively: the secondary-school system does
    # not ship every domain/function this registry was authored against (it was
    # adapted from the sixth-form system, which has extra domains such as
    # `progression` and `bursaries`). Each module is wrapped in a proxy so that
    # a missing module OR a missing function degrades to an empty dataset
    # instead of crashing the whole registry build.
    import importlib

    class _ModuleProxy:
        def __init__(self, _mod):
            self._mod = _mod

        def __getattr__(self, _name):
            val = getattr(self._mod, _name, None) if self._mod is not None else None
            return val if val is not None else (lambda **_kw: [])

    def _load(_path, _name):
        try:
            mod = importlib.import_module(_path + "." + _name)
        except Exception:
            mod = None
        return _ModuleProxy(mod)

    attendance = _load("education_system.secondarysch_system.modules.domain.academics.attendance", "attendance")
    attendance_concerns = _load("education_system.secondarysch_system.modules.domain.pastoral.attendance_concerns", "attendance_concerns")
    behaviour = _load("education_system.secondarysch_system.modules.domain.pastoral.behaviour", "behaviour")
    bursaries = _load("education_system.secondarysch_system.modules.domain.finance.bursaries", "bursaries")
    class_groups = _load("education_system.secondarysch_system.modules.domain.academics.class_groups", "class_groups")
    courses = _load("education_system.secondarysch_system.modules.domain.academics.courses", "courses")
    enrolments = _load("education_system.secondarysch_system.modules.domain.pupils.enrolment", "enrolment")
    exam_entries = _load("education_system.secondarysch_system.modules.domain.assessment.exam_entries", "exam_entries")
    exam_results = _load("education_system.secondarysch_system.modules.domain.assessment.exam_results", "exam_results")
    fees = _load("education_system.secondarysch_system.modules.domain.finance.fees", "fees")
    gradebook = _load("education_system.secondarysch_system.modules.domain.assessment.gradebook", "gradebook")
    homework = _load("education_system.secondarysch_system.modules.domain.academics.homework", "homework")
    mock_exams = _load("education_system.secondarysch_system.modules.domain.assessment.mock_exams", "mock_exams")
    notices = _load("education_system.secondarysch_system.modules.domain.staff_comms.notices", "notices")
    parent_contacts = _load("education_system.secondarysch_system.modules.domain.staff_comms.parent_contacts", "parent_contacts")
    parents_evenings = _load("education_system.secondarysch_system.modules.domain.staff_comms.parents_evenings", "parents_evenings")
    predicted_grades = _load("education_system.secondarysch_system.modules.domain.assessment.predicted_grades", "predicted_grades")
    progress = _load("education_system.secondarysch_system.modules.domain.reports.progress", "progress")
    receipts = _load("education_system.secondarysch_system.modules.domain.finance.receipts", "receipts")
    safeguarding = _load("education_system.secondarysch_system.modules.domain.pastoral.safeguarding", "safeguarding")
    staff = _load("education_system.secondarysch_system.modules.domain.staff_comms.staff", "staff")
    students = _load("education_system.secondarysch_system.modules.domain.pastoral", "_pupils_bridge")
    subjects = _load("education_system.secondarysch_system.modules.domain.academics.subjects", "subjects")
    timetable = _load("education_system.secondarysch_system.modules.domain.academics.timetable", "timetable")
    trips = _load("education_system.secondarysch_system.modules.domain.finance.trips", "trips")
    tutor_groups = _load("education_system.secondarysch_system.modules.domain.pastoral.tutor_groups", "tutor_groups")
    _att = _load("education_system.secondarysch_system.modules.domain.academics.attendance", "attendance")
    _atc = _load("education_system.secondarysch_system.modules.domain.pastoral.attendance_concerns", "attendance_concerns")
    _beh = _load("education_system.secondarysch_system.modules.domain.pastoral.behaviour", "behaviour")
    _bur = _load("education_system.secondarysch_system.modules.domain.finance.bursaries", "bursaries")
    _cg = _load("education_system.secondarysch_system.modules.domain.academics.class_groups", "class_groups")
    _co = _load("education_system.secondarysch_system.modules.domain.academics.courses", "courses")
    _en = _load("education_system.secondarysch_system.modules.domain.pupils.enrolment", "enrolment")
    _eent = _load("education_system.secondarysch_system.modules.domain.assessment.exam_entries", "exam_entries")
    _er = _load("education_system.secondarysch_system.modules.domain.assessment.exam_results", "exam_results")
    _fees = _load("education_system.secondarysch_system.modules.domain.finance.fees", "fees")
    _gb = _load("education_system.secondarysch_system.modules.domain.assessment.gradebook", "gradebook")
    _hw = _load("education_system.secondarysch_system.modules.domain.academics.homework", "homework")
    _me = _load("education_system.secondarysch_system.modules.domain.assessment.mock_exams", "mock_exams")
    _no = _load("education_system.secondarysch_system.modules.domain.staff_comms.notices", "notices")
    _pc = _load("education_system.secondarysch_system.modules.domain.staff_comms.parent_contacts", "parent_contacts")
    _pe = _load("education_system.secondarysch_system.modules.domain.staff_comms.parents_evenings", "parents_evenings")
    _pg = _load("education_system.secondarysch_system.modules.domain.assessment.predicted_grades", "predicted_grades")
    _pr = _load("education_system.secondarysch_system.modules.domain.reports.progress", "progress")
    _rc = _load("education_system.secondarysch_system.modules.domain.finance.receipts", "receipts")
    _sg = _load("education_system.secondarysch_system.modules.domain.pastoral.safeguarding", "safeguarding")
    _staff = _load("education_system.secondarysch_system.modules.domain.staff_comms.staff", "staff")
    _students = _load("education_system.secondarysch_system.modules.domain.pastoral", "_pupils_bridge")
    _sub = _load("education_system.secondarysch_system.modules.domain.academics.subjects", "subjects")
    _tt = _load("education_system.secondarysch_system.modules.domain.academics.timetable", "timetable")
    _tr = _load("education_system.secondarysch_system.modules.domain.finance.trips", "trips")
    _tg = _load("education_system.secondarysch_system.modules.domain.pastoral.tutor_groups", "tutor_groups")
    _wb = _load("education_system.secondarysch_system.modules.domain.pastoral.wellbeing", "wellbeing")


    _appr = _load("education_system.secondarysch_system.modules.domain.progression.apprenticeships", "apprenticeships")
    _car = _load("education_system.secondarysch_system.modules.domain.progression.careers", "careers")
    _of = _load("education_system.secondarysch_system.modules.domain.progression.offers", "offers")
    _ps = _load("education_system.secondarysch_system.modules.domain.progression.personal_statements", "personal_statements")
    _refs = _load("education_system.secondarysch_system.modules.domain.progression.references", "references")
    _uc = _load("education_system.secondarysch_system.modules.domain.progression.ucas", "ucas")
    R: dict[str, DatasetSpec] = {}

    R["students"] = DatasetSpec(
        key="students", label="Students",
        description="Full student directory.",
        columns=[
            ("student_id", "Student ID"),
            ("first_name", "First name"),
            ("last_name", "Last name"),
            ("dob", "DOB"),
            ("email", "Email"),
            ("phone", "Phone"),
            ("year_group", "Year"),
            ("subjects", "Subjects"),
            ("notes", "Notes"),
            ("created_at", "Created at"),
            ("updated_at", "Updated at"),
        ],
        list_fn=_students.list_students,
    )

    R["staff"] = DatasetSpec(
        key="staff", label="Staff",
        description="Staff directory (optionally active-only).",
        columns=[
            ("staff_id", "Staff ID"), ("title", "Title"),
            ("first_name", "First name"), ("last_name", "Last name"),
            ("role", "Role"), ("department", "Department"),
            ("employment_status", "Employment"),
            ("email", "Email"), ("work_phone", "Work phone"),
            ("room", "Room"),
            ("is_tutor", "Tutor"), ("is_dsl", "DSL"),
            ("is_examiner", "Examiner"),
            ("start_date", "Start"), ("end_date", "End"),
        ],
        list_fn=_staff.list_staff,
        filter_keys=["role", "department", "employment_status",
                       "active_only"],
    )

    R["enrolments"] = DatasetSpec(
        key="enrolments", label="Enrolments",
        description="Enrolment of students onto courses.",
        columns=[
            ("enrolment_id", "#"),
            ("student_id", "Student"), ("course_id", "Course"),
            ("academic_year", "Year"), ("status", "Status"),
            ("start_date", "Start"), ("end_date", "End"),
            ("notes", "Notes"),
        ],
        list_fn=_en.list_enrolments,
        filter_keys=["student_id", "course_id",
                       "academic_year", "status"],
    )

    R["courses"] = DatasetSpec(
        key="courses", label="Courses",
        description="Courses offered.",
        columns=[
            ("course_id", "#"), ("name", "Name"),
            ("year_group", "Year"), ("status", "Status"),
            ("notes", "Notes"),
        ],
        list_fn=_co.list_courses,
    )

    R["subjects"] = DatasetSpec(
        key="subjects", label="Subjects",
        description="A-Level / qualification subjects.",
        columns=[
            ("subject_id", "#"), ("name", "Name"),
            ("level", "Level"), ("code", "Code"),
        ],
        list_fn=_sub.list_subjects,
    )

    R["class_groups"] = DatasetSpec(
        key="class_groups", label="Class groups",
        description="Teaching sets.",
        columns=[
            ("group_id", "#"), ("course_id", "Course"),
            ("group_name", "Name"),
            ("academic_year", "Year"),
        ],
        list_fn=_cg.list_groups,
    )

    R["timetable_slots"] = DatasetSpec(
        key="timetable_slots", label="Timetable slots",
        description="Lesson slots (day, period, group, room).",
        columns=[
            ("slot_id", "#"), ("group_id", "Group"),
            ("day", "Day"), ("period", "Period"),
            ("start_time", "Start"), ("end_time", "End"),
            ("room", "Room"), ("academic_year", "Year"),
        ],
        list_fn=_tt.list_slots,
        filter_keys=["group_id", "day", "academic_year"],
    )

    R["attendance"] = DatasetSpec(
        key="attendance", label="Attendance records",
        description="Raw attendance per slot/student/date.",
        columns=[
            ("record_id", "#"), ("slot_id", "Slot"),
            ("student_id", "Student"), ("date", "Date"),
            ("status", "Status"),
            ("minutes_late", "Mins late"),
            ("notes", "Notes"),
        ],
        list_fn=_att.list_records,
        filter_keys=["slot_id", "student_id", "status",
                       "date_from", "date_to"],
    )

    R["homework"] = DatasetSpec(
        key="homework", label="Homework / coursework",
        description="Assignments (header rows).",
        columns=[
            ("assignment_id", "#"), ("group_id", "Group"),
            ("title", "Title"), ("category", "Category"),
            ("issued_date", "Issued"), ("due_date", "Due"),
            ("status", "Status"),
        ],
        list_fn=_hw.list_assignments,
        filter_keys=["group_id", "status"],
    )

    R["gradebook"] = DatasetSpec(
        key="gradebook", label="Gradebook entries",
        description="Per-assignment grade boundary overrides.",
        columns=[
            ("entry_id", "#"), ("assignment_id", "Assignment"),
            ("max_marks", "Max"),
            ("boundary_A_star", "A*"), ("boundary_A", "A"),
            ("boundary_B", "B"), ("boundary_C", "C"),
            ("boundary_D", "D"), ("boundary_E", "E"),
        ],
        list_fn=_gb.list_entries
            if hasattr(_gb, "list_entries") else lambda **_kw: [],
    )

    R["predicted_grades"] = DatasetSpec(
        key="predicted_grades", label="Predicted grades",
        description="Predicted grade per (student, subject).",
        columns=[
            ("prediction_id", "#"), ("student_id", "Student"),
            ("subject", "Subject"), ("grade", "Grade"),
            ("confidence", "Confidence"), ("notes", "Notes"),
        ],
        list_fn=_pg.list_predictions,
        filter_keys=["student_id", "subject", "grade"],
    )

    R["mock_exams"] = DatasetSpec(
        key="mock_exams", label="Mock exams",
        description="Mock papers (header rows).",
        columns=[
            ("mock_id", "#"), ("name", "Name"),
            ("subject", "Subject"),
            ("level", "Level"), ("paper_code", "Paper"),
            ("max_marks", "Max"), ("sat_date", "Date"),
            ("notes", "Notes"),
        ],
        list_fn=_me.list_mocks,
        filter_keys=["subject", "level"],
    )

    R["exam_entries"] = DatasetSpec(
        key="exam_entries", label="Exam entries",
        description="Student registrations for board papers.",
        columns=[
            ("entry_id", "#"), ("student_id", "Student"),
            ("subject", "Subject"), ("paper_code", "Paper"),
            ("season", "Season"), ("year", "Year"),
            ("exam_board", "Board"), ("status", "Status"),
        ],
        list_fn=_eent.list_entries,
        filter_keys=["student_id", "subject", "year",
                       "season", "exam_board"],
    )

    R["exam_results"] = DatasetSpec(
        key="exam_results", label="Exam results",
        description="Board-awarded grades.",
        columns=[
            ("student_id", "Student"),
            ("student_name", "Name"),
            ("subject", "Subject"),
            ("paper_code", "Paper"),
            ("season", "Season"), ("year", "Year"),
            ("result.marks", "Marks"),
            ("result.ums", "UMS"),
            ("result.grade", "Grade"),
            ("result.released_at", "Released"),
        ],
        list_fn=_er.list_results,
        filter_keys=["student_id", "subject", "year",
                       "season", "exam_board", "paper_code", "grade"],
    )

    R["ucas_applications"] = DatasetSpec(
        key="ucas_applications", label="UCAS applications",
        description="One application per student.",
        columns=[
            ("application_id", "#"), ("student_id", "Student"),
            ("cycle_year", "Cycle"), ("status", "Status"),
            ("personal_id", "Personal ID"),
            ("date_submitted", "Submitted"),
        ],
        list_fn=_uc.list_applications
            if (_uc and hasattr(_uc, "list_applications")) else lambda **_kw: [],
    )

    R["personal_statements"] = DatasetSpec(
        key="personal_statements", label="Personal statements",
        description="Drafts per student.",
        columns=[
            ("statement_id", "#"), ("student_id", "Student"),
            ("title", "Title"), ("status", "Status"),
            ("word_count", "Words"), ("updated_at", "Updated"),
        ],
        list_fn=_ps.list_statements
            if hasattr(_ps, "list_statements") else lambda **_kw: [],
    )

    R["references"] = DatasetSpec(
        key="references", label="UCAS references",
        description="Teacher / tutor references.",
        columns=[
            ("reference_id", "#"), ("student_id", "Student"),
            ("staff_id", "Staff"), ("status", "Status"),
            ("updated_at", "Updated"),
        ],
        list_fn=_refs.list_references
            if hasattr(_refs, "list_references") else lambda **_kw: [],
    )

    R["offers"] = DatasetSpec(
        key="offers", label="University offers",
        description="Per-choice offer tracking.",
        columns=[
            ("offer_id", "#"), ("student_id", "Student"),
            ("university", "University"), ("course", "Course"),
            ("offer_type", "Type"), ("conditions", "Conditions"),
            ("status", "Status"),
        ],
        list_fn=_of.list_offers
            if hasattr(_of, "list_offers") else lambda **_kw: [],
    )

    R["apprenticeships"] = DatasetSpec(
        key="apprenticeships", label="Apprenticeships",
        description="Per-application tracking.",
        columns=[
            ("application_id", "#"), ("student_id", "Student"),
            ("employer", "Employer"), ("role", "Role"),
            ("level", "Level"), ("status", "Status"),
            ("applied_date", "Applied"),
        ],
        list_fn=_appr.list_applications
            if hasattr(_appr, "list_applications") else lambda **_kw: [],
    )

    R["careers_sessions"] = DatasetSpec(
        key="careers_sessions", label="Careers sessions",
        description="Logged careers meetings.",
        columns=[
            ("session_id", "#"), ("student_id", "Student"),
            ("session_date", "Date"), ("session_type", "Type"),
            ("staff_id", "Adviser"), ("notes", "Notes"),
        ],
        list_fn=_car.list_sessions
            if hasattr(_car, "list_sessions") else lambda **_kw: [],
    )

    R["tutor_groups"] = DatasetSpec(
        key="tutor_groups", label="Tutor groups",
        description="Per-student tutor assignment.",
        columns=[
            ("student_id", "Student"), ("tutor_group", "Group"),
            ("tutor_staff_id", "Tutor"), ("notes", "Notes"),
        ],
        list_fn=_tg.list_assignments
            if hasattr(_tg, "list_assignments") else lambda **_kw: [],
    )

    R["behaviour"] = DatasetSpec(
        key="behaviour", label="Behaviour log",
        description="Positive + negative pastoral entries.",
        columns=[
            ("entry_id", "#"), ("student_id", "Student"),
            ("entry_date", "Date"), ("kind", "Kind"),
            ("category", "Category"), ("points", "Points"),
            ("staff_id", "Staff"), ("description", "Description"),
        ],
        list_fn=_beh.list_entries
            if hasattr(_beh, "list_entries") else lambda **_kw: [],
    )

    R["safeguarding"] = DatasetSpec(
        key="safeguarding", label="Safeguarding concerns",
        description="⚠ Confidential — restrict export carefully.",
        columns=[
            ("concern_id", "#"), ("student_id", "Student"),
            ("concern_date", "Date"), ("category", "Category"),
            ("risk_level", "Risk"), ("status", "Status"),
            ("reported_by", "Reported by"),
            ("dsl_notified", "DSL notified"),
        ],
        list_fn=_sg.list_concerns,
        filter_keys=["student_id", "risk_level", "status",
                       "category", "open_only"],
    )

    R["wellbeing_checkins"] = DatasetSpec(
        key="wellbeing_checkins", label="Wellbeing check-ins",
        description="Mood / stress / sleep pulse data.",
        columns=[
            ("checkin_id", "#"), ("student_id", "Student"),
            ("checkin_date", "Date"),
            ("mood_score", "Mood"),
            ("stress_score", "Stress"),
            ("sleep_score", "Sleep"),
            ("recorded_by", "By"), ("notes", "Notes"),
        ],
        list_fn=_wb.list_checkins,
        filter_keys=["student_id", "date_from", "date_to"],
    )

    R["wellbeing_sessions"] = DatasetSpec(
        key="wellbeing_sessions", label="Wellbeing sessions",
        description="Counselling / mentoring / support sessions.",
        columns=[
            ("session_id", "#"), ("student_id", "Student"),
            ("session_date", "Date"),
            ("session_type", "Type"), ("status", "Status"),
            ("duration_minutes", "Mins"),
            ("provider", "Provider"),
            ("follow_up_date", "Follow-up"),
        ],
        list_fn=_wb.list_sessions,
        filter_keys=["student_id", "session_type", "status",
                       "date_from", "date_to"],
    )

    R["attendance_concerns"] = DatasetSpec(
        key="attendance_concerns", label="Attendance concerns",
        description="Tracked interventions for attendance.",
        columns=[
            ("concern_id", "#"), ("student_id", "Student"),
            ("raised_date", "Raised"), ("reason", "Reason"),
            ("level", "Level"), ("status", "Status"),
            ("observed_pct", "Observed %"),
            ("threshold_pct", "Threshold %"),
            ("assigned_to", "Assigned"),
            ("follow_up_date", "Follow-up"),
        ],
        list_fn=_atc.list_concerns,
        filter_keys=["student_id", "level", "status",
                       "reason", "open_only"],
    )

    R["parent_contacts"] = DatasetSpec(
        key="parent_contacts", label="Parent contacts",
        description="Parents / guardians per student.",
        columns=[
            ("contact_id", "#"), ("student_id", "Student"),
            ("relationship", "Relationship"),
            ("first_name", "First name"),
            ("last_name", "Last name"),
            ("email", "Email"),
            ("primary_phone", "Phone"),
            ("preferred_method", "Method"),
            ("is_primary", "Primary"),
            ("is_emergency_contact", "Emergency"),
            ("receives_communications", "Comms"),
        ],
        list_fn=_pc.list_contacts,
        filter_keys=["student_id", "relationship",
                       "primary_only", "emergency_only",
                       "receives_only"],
    )

    R["parents_evenings"] = DatasetSpec(
        key="parents_evenings", label="Parents' evenings",
        description="Events.",
        columns=[
            ("event_id", "#"), ("name", "Name"),
            ("event_date", "Date"),
            ("start_time", "Start"), ("end_time", "End"),
            ("year_group", "Year"), ("slot_minutes", "Slot"),
            ("status", "Status"),
        ],
        list_fn=_pe.list_events,
    )

    R["parents_evening_bookings"] = DatasetSpec(
        key="parents_evening_bookings",
        label="Parents' evening bookings",
        description="One row per booked slot.",
        columns=[
            ("booking_id", "#"), ("event_id", "Event"),
            ("student_id", "Student"), ("staff_id", "Staff"),
            ("slot_time", "Slot"), ("status", "Status"),
            ("parent_name", "Parent"),
        ],
        list_fn=_pe.list_bookings,
        filter_keys=["event_id", "student_id", "staff_id",
                       "status"],
    )

    R["notices"] = DatasetSpec(
        key="notices", label="Notices & bulletins",
        description="Announcements.",
        columns=[
            ("notice_id", "#"), ("title", "Title"),
            ("category", "Category"), ("audience", "Audience"),
            ("priority", "Priority"), ("status", "Status"),
            ("pinned", "Pinned"),
            ("publish_from", "From"), ("publish_until", "Until"),
            ("view_count", "Views"),
        ],
        list_fn=_no.list_notices,
        filter_keys=["category", "audience", "priority",
                       "status", "pinned_only"],
    )

    R["fees"] = DatasetSpec(
        key="fees", label="Fee items",
        description="Chargeable fees per student.",
        columns=[
            ("fee_id", "#"), ("student_id", "Student"),
            ("description", "Description"),
            ("category", "Category"),
            ("amount", "Amount"),
            ("issued_date", "Issued"),
            ("due_date", "Due"),
            ("academic_year", "Year"),
            ("stored_status", "Stored status"),
        ],
        list_fn=_fees.list_items,
        filter_keys=["student_id", "category",
                       "academic_year", "stored_status"],
    )

    R["fee_payments"] = DatasetSpec(
        key="fee_payments", label="Fee payments",
        description="Payments against fees.",
        columns=[
            ("payment_id", "#"), ("fee_id", "Fee"),
            ("amount", "Amount"),
            ("paid_on", "Paid on"),
            ("method", "Method"), ("status", "Status"),
            ("reference", "Reference"),
        ],
        list_fn=_fees.list_payments,
        filter_keys=["fee_id", "student_id", "method",
                       "status", "date_from", "date_to"],
    )

    R["bursaries"] = DatasetSpec(
        key="bursaries", label="Bursary applications",
        description="16-19 bursary fund applications.",
        columns=[
            ("application_id", "#"), ("student_id", "Student"),
            ("bursary_type", "Type"),
            ("academic_year", "Year"),
            ("application_date", "Applied"),
            ("amount_requested", "Requested"),
            ("amount_awarded", "Awarded"),
            ("status", "Status"),
            ("eligibility_basis", "Basis"),
        ],
        list_fn=_bur.list_applications,
        filter_keys=["student_id", "bursary_type",
                       "status", "academic_year",
                       "active_only", "approved_only"],
    )

    R["bursary_disbursements"] = DatasetSpec(
        key="bursary_disbursements",
        label="Bursary disbursements",
        description="Payments out from approved bursaries.",
        columns=[
            ("disbursement_id", "#"),
            ("application_id", "App"),
            ("amount", "Amount"), ("paid_on", "Paid on"),
            ("method", "Method"), ("status", "Status"),
            ("reference", "Reference"),
        ],
        list_fn=_bur.list_disbursements,
        filter_keys=["application_id", "student_id",
                       "status", "date_from", "date_to"],
    )

    R["trips"] = DatasetSpec(
        key="trips", label="Trips",
        description="School trips.",
        columns=[
            ("trip_id", "#"), ("name", "Name"),
            ("destination", "Destination"),
            ("start_date", "Start"), ("end_date", "End"),
            ("year_group", "Year"),
            ("cost_per_place", "Cost"),
            ("deposit", "Deposit"),
            ("capacity", "Capacity"),
            ("status", "Status"),
        ],
        list_fn=_tr.list_trips,
        filter_keys=["year_group", "status", "open_only",
                       "date_from", "date_to"],
    )

    R["trip_bookings"] = DatasetSpec(
        key="trip_bookings", label="Trip bookings",
        description="One row per student booked onto a trip.",
        columns=[
            ("booking_id", "#"), ("trip_id", "Trip"),
            ("student_id", "Student"),
            ("booking_date", "Booked"),
            ("status", "Status"),
            ("consent_received", "Consent"),
            ("medical_note", "Medical"),
            ("dietary_note", "Dietary"),
        ],
        list_fn=_tr.list_bookings,
        filter_keys=["trip_id", "student_id", "status",
                       "consent_received", "active_only"],
    )

    R["trip_payments"] = DatasetSpec(
        key="trip_payments", label="Trip payments",
        description="Payments against trip bookings.",
        columns=[
            ("payment_id", "#"), ("booking_id", "Booking"),
            ("amount", "Amount"), ("paid_on", "Paid on"),
            ("method", "Method"), ("status", "Status"),
            ("reference", "Reference"),
        ],
        list_fn=_tr.list_payments,
        filter_keys=["booking_id", "trip_id", "student_id",
                       "method", "status",
                       "date_from", "date_to"],
    )

    R["receipts"] = DatasetSpec(
        key="receipts", label="Receipts",
        description="Issued / draft / voided receipts.",
        columns=[
            ("receipt_id", "#"),
            ("receipt_number", "Number"),
            ("issued_date", "Issued"),
            ("payer_name", "Payer"),
            ("student_id", "Student"),
            ("method", "Method"),
            ("total_amount", "Total"),
            ("status", "Status"),
            ("voided_at", "Voided at"),
            ("void_reason", "Void reason"),
        ],
        list_fn=_rc.list_receipts,
        filter_keys=["student_id", "status", "method",
                       "date_from", "date_to",
                       "issued_only", "voided_only"],
    )

    R["progress_reviews"] = DatasetSpec(
        key="progress_reviews", label="Progress reviews",
        description="Periodic progress snapshots.",
        columns=[
            ("review_id", "#"), ("student_id", "Student"),
            ("review_date", "Date"), ("period", "Period"),
            ("academic_year", "Year"),
            ("overall", "Overall"), ("attitude", "Attitude"),
            ("homework", "Homework"),
            ("attendance_pct", "Att %"),
            ("risk_level", "Risk"), ("status", "Status"),
            ("reviewer_staff_id", "Reviewer"),
        ],
        list_fn=_pr.list_reviews,
        filter_keys=["student_id", "period",
                       "academic_year", "status",
                       "risk_level", "active_only"],
    )

    R["progress_targets"] = DatasetSpec(
        key="progress_targets", label="Progress targets",
        description="Per-review targets.",
        columns=[
            ("target_id", "#"), ("review_id", "Review"),
            ("area", "Area"), ("description", "Description"),
            ("measure", "Measure"),
            ("due_date", "Due"),
            ("status", "Status"),
            ("closed_on", "Closed"),
        ],
        list_fn=_pr.list_targets,
        filter_keys=["review_id", "student_id", "status",
                       "area", "open_only", "due_before"],
    )

    return R


_DATASETS_CACHE: dict[str, DatasetSpec] | None = None


def DATASETS() -> dict[str, DatasetSpec]:  # noqa: N802
    """Lazy-built registry — avoids importing every module at import
    time (matters when tests stub modules)."""
    global _DATASETS_CACHE
    if _DATASETS_CACHE is None:
        _DATASETS_CACHE = _build_registry()
    return _DATASETS_CACHE


def list_datasets() -> list[DatasetSpec]:
    return sorted(DATASETS().values(), key=lambda d: d.label.lower())


def get_dataset(key: str) -> DatasetSpec:
    reg = DATASETS()
    if key not in reg:
        raise ValidationError(
            f"Unknown dataset {key!r}. Try one of: "
            f"{', '.join(sorted(reg.keys()))}")
    return reg[key]


# ── Fetch + filter rows ───────────────────────────────────────────

def _apply_filters(spec: DatasetSpec,
                     filters: dict[str, Any]) -> list[Any]:
    """Call ``spec.list_fn(**filters_for_known_keys)`` and return
    rows. Unknown keys are ignored — a friendly behaviour for the
    quick-export CLI."""
    if not filters:
        return list(spec.list_fn())
    accepted = {k: v for k, v in filters.items()
                 if k in spec.filter_keys and v not in (None, "")}
    try:
        return list(spec.list_fn(**accepted))
    except TypeError:
        # list_fn signature changed; fall back to no-filter call.
        return list(spec.list_fn())


def fetch(spec_or_key: DatasetSpec | str,
            *,
            filters: dict[str, Any] | None = None,
            limit: int | None = None) -> list[Any]:
    spec = (spec_or_key if isinstance(spec_or_key, DatasetSpec)
            else get_dataset(spec_or_key))
    rows = _apply_filters(spec, filters or {})
    if limit is not None:
        rows = rows[:limit]
    return rows


def project(rows: list[Any],
             columns: list[tuple[str, str]]) -> list[list[str]]:
    """Return a 2-D table (no header row) of stringified cells."""
    return [[_stringify(_get(r, k)) for k, _ in columns]
            for r in rows]


def project_dicts(rows: list[Any],
                    columns: list[tuple[str, str]]) -> list[dict]:
    return [{label: _json_safe(_get(r, k)) for k, label in columns}
            for r in rows]


# ── Writers ──────────────────────────────────────────────────────

def _write_csv_like(rows: list[list[str]],
                      headers: list[str], *,
                      delimiter: str) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=delimiter,
                      quoting=csv.QUOTE_MINIMAL,
                      lineterminator="\n")
    w.writerow(headers)
    for r in rows:
        w.writerow(r)
    return buf.getvalue()


def _write_json(dicts: list[dict]) -> str:
    return json.dumps(dicts, indent=2, ensure_ascii=False) + "\n"


def _write_jsonl(dicts: list[dict]) -> str:
    return "\n".join(json.dumps(d, ensure_ascii=False)
                     for d in dicts) + "\n"


def _write_markdown(rows: list[list[str]],
                       headers: list[str]) -> str:
    def _esc(s: str) -> str:
        return s.replace("|", "\\|").replace("\n", " ⏎ ")
    lines: list[str] = []
    lines.append("| " + " | ".join(_esc(h) for h in headers) + " |")
    lines.append("|" + "|".join("---" for _ in headers) + "|")
    for r in rows:
        lines.append("| " + " | ".join(_esc(c) for c in r) + " |")
    return "\n".join(lines) + "\n"


def render(
    spec_or_key: DatasetSpec | str,
    *,
    fmt: str = DEFAULT_FORMAT,
    columns: list[str] | None = None,
    filters: dict[str, Any] | None = None,
    limit: int | None = None,
) -> str:
    """Return the rendered export as a string. Use ``export()`` to
    also write it to disk."""
    spec = (spec_or_key if isinstance(spec_or_key, DatasetSpec)
            else get_dataset(spec_or_key))
    fmt = (fmt or DEFAULT_FORMAT).lower().strip()
    if fmt not in FORMATS:
        raise ValidationError(
            f"Format must be one of: {', '.join(FORMATS)}")
    cols = _resolve_columns(spec, columns)
    if not cols:
        raise ValidationError("No columns selected")
    rows_raw = fetch(spec, filters=filters, limit=limit)

    if fmt == "csv":
        rows = project(rows_raw, cols)
        return _write_csv_like(rows, [h for _, h in cols],
                                  delimiter=",")
    if fmt == "tsv":
        rows = project(rows_raw, cols)
        return _write_csv_like(rows, [h for _, h in cols],
                                  delimiter="\t")
    if fmt == "json":
        return _write_json(project_dicts(rows_raw, cols))
    if fmt == "jsonl":
        return _write_jsonl(project_dicts(rows_raw, cols))
    if fmt == "markdown":
        rows = project(rows_raw, cols)
        return _write_markdown(rows, [h for _, h in cols])
    raise ValidationError(f"Unsupported format: {fmt}")


def export(
    spec_or_key: DatasetSpec | str,
    output_path: str | Path,
    *,
    fmt: str | None = None,
    columns: list[str] | None = None,
    filters: dict[str, Any] | None = None,
    limit: int | None = None,
) -> ExportResult:
    """Write to a file. Format is auto-detected from extension when
    ``fmt`` is None."""
    spec = (spec_or_key if isinstance(spec_or_key, DatasetSpec)
            else get_dataset(spec_or_key))
    path = Path(output_path).expanduser()
    if fmt is None:
        suffix = path.suffix.lower().lstrip(".")
        fmt = suffix if suffix in FORMATS else DEFAULT_FORMAT
        if suffix == "md":
            fmt = "markdown"
    body = render(spec, fmt=fmt, columns=columns,
                     filters=filters, limit=limit)
    path.parent.mkdir(parents=True, exist_ok=True)
    written = path.write_text(body, encoding="utf-8")
    cols = _resolve_columns(spec, columns)
    rows_n = (body.count("\n") - 1) if fmt in ("csv", "tsv")\
        else (len(body.splitlines()) if fmt == "jsonl"
              else fetch(spec, filters=filters, limit=limit).__len__())
    if fmt in ("csv", "tsv", "markdown"):
        # rows_n above for csv/tsv subtracts the header; markdown has
        # 2 header rows, count via list:
        if fmt == "markdown":
            rows_n = max(0, len(body.splitlines()) - 2)
    logger.info(
        "Exported %s → %s (%s, %d row(s), %d byte(s))",
        spec.key, path, fmt, rows_n, written)
    return ExportResult(
        dataset_key=spec.key, fmt=fmt,
        row_count=rows_n, column_count=len(cols),
        path=str(path), bytes_written=written,
    )


def _resolve_columns(spec: DatasetSpec,
                       columns: list[str] | None
                       ) -> list[tuple[str, str]]:
    if not columns:
        return list(spec.columns)
    col_map = {k: h for k, h in spec.columns}
    out: list[tuple[str, str]] = []
    for c in columns:
        c = c.strip()
        if not c:
            continue
        if c in col_map:
            out.append((c, col_map[c]))
        else:
            # Allow free-form keys for advanced users.
            out.append((c, c))
    return out


def preview(
    spec_or_key: DatasetSpec | str,
    *,
    columns: list[str] | None = None,
    filters: dict[str, Any] | None = None,
    limit: int = 10,
) -> tuple[list[str], list[list[str]]]:
    """Return (headers, rows) for a small preview."""
    spec = (spec_or_key if isinstance(spec_or_key, DatasetSpec)
            else get_dataset(spec_or_key))
    cols = _resolve_columns(spec, columns)
    rows_raw = fetch(spec, filters=filters, limit=limit)
    return [h for _, h in cols], project(rows_raw, cols)
