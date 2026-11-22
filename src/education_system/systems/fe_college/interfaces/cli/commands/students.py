"""Learner commands — the CLI counterpart of the learner screens."""

from __future__ import annotations

from datetime import date

from education_system.systems.fe_college.config import (
    EMERGENCY_RELATIONSHIPS,
    GENDERS,
    LEARNER_TYPES,
    MODES_OF_STUDY,
    STUDENT_STATUSES,
)
from education_system.systems.fe_college.domain.students.models import (
    Student,
    ValidationError,
)
from education_system.systems.fe_college.interfaces.cli import shell as sh


def directory(ctl) -> None:
    """List learners, with an optional search term and status filter."""
    sh.header("Learners", "Blank search shows everyone.")
    query = sh.prompt("Search (name / ID / ULN)")
    if query is sh.CANCEL:
        return
    status = sh.choose("Status", ["any", *STUDENT_STATUSES])
    if status is sh.CANCEL:
        return

    learners = ctl.students.search(
        query=query, **({} if status == "any" else {"status": status})
    )
    rates = {s.student_id: summary for s, summary in ctl.attendance.by_student()}
    sh.table(
        [("id", "ID"), ("name", "Name"), ("age", "Age"), ("type", "Learner type"),
         ("group", "Group"), ("status", "Status"), ("attendance", "Attendance")],
        [
            {
                "id": s.student_id,
                "name": s.full_name,
                "age": s.age,
                "type": s.learner_type,
                "group": s.tutor_group,
                "status": s.status,
                "attendance": sh.pct(
                    rates[s.student_id].attendance_pct
                    if s.student_id in rates else None
                ),
            }
            for s in learners
        ],
        empty="No learners match.",
        limit=40,
    )


def view(ctl, student_id: str | None = None) -> None:
    """Show one learner's full record."""
    learner = _pick(ctl, student_id, "Learner")
    if learner is None:
        return
    profile = ctl.students.profile(learner.student_id)
    if profile is None:
        sh.error("That learner no longer exists.")
        return

    s = profile.student
    sh.header(s.display_name, f"{s.learner_type} · {s.mode_of_study} · {s.status}")
    sh.key_values([
        ("Legal name", s.legal_name),
        ("Preferred name", s.preferred_name),
        ("Date of birth", s.date_of_birth),
        ("Age", s.age),
        ("Gender", s.gender),
        ("ULN", s.uln),
        ("Email", s.email),
        ("Phone", s.phone),
        ("Address", s.full_address),
        ("Emergency contact", " · ".join(p for p in (
            s.emergency_contact_name, s.emergency_contact_relationship,
            s.emergency_contact_phone) if p)),
        ("Tutor group", s.tutor_group),
        ("Personal tutor", s.personal_tutor),
        ("Started", s.start_date),
        ("Prior attainment", s.prior_attainment),
        ("EHC Plan", s.has_ehcp),
        ("Learning difficulty / disability", s.has_lldd),
        ("Medical notes", s.medical_notes),
        ("Balance", sh.money(profile.balance)),
    ])

    sh.section("Attendance")
    sh.key_values([
        ("Rate", f"{sh.pct(profile.attendance.attendance_pct)} "
                 f"({profile.attendance.band})"),
        ("Punctuality", sh.pct(profile.attendance.punctuality_pct)),
        ("Sessions", profile.attendance.total),
        ("Unauthorised", profile.attendance.unauthorised),
    ])

    sh.section("Enrolments")
    sh.table(
        [("course", "Course"), ("year", "Year"), ("status", "Status"),
         ("aim", "Aim"), ("grade", "Grade")],
        [
            {
                "course": e.course_id,
                "year": e.academic_year,
                "status": e.status,
                "aim": "main" if e.is_main_aim else "additional",
                "grade": e.final_grade,
            }
            for e in profile.enrolments
        ],
        empty="Not enrolled on anything.",
    )

    sh.section("Targets")
    sh.bullet_list(
        [
            f"[{t.status}] {t.description}"
            + (f" (due {t.due_date})" if t.due_date else "")
            + ("  OVERDUE" if t.is_overdue() else "")
            for t in profile.targets
        ],
        empty="No targets set.",
    )

    if profile.support:
        sh.section("Learning support")
        sh.bullet_list([
            f"{p.support_type} — {p.status}"
            + (f" ({p.hours_per_week:g}h/week)" if p.hours_per_week else "")
            for p in profile.support
        ])

    if profile.warnings:
        sh.section("Study programme warnings")
        sh.bullet_list(list(profile.warnings))


_CREATE_FIELDS = [
    ("_identity", "Identity", "section"),
    ("student_id", "Student ID", "text"),
    ("first_name", "Legal first name", "text"),
    ("middle_name", "Middle name(s)", "text"),
    ("last_name", "Legal last name", "text"),
    ("preferred_name", "Preferred name", "text"),
    ("date_of_birth", "Date of birth", "date"),
    ("gender", "Gender", "choice", GENDERS),
    ("uln", "ULN (10 digits, blank if none)", "text"),
    ("_contact", "Contact", "section"),
    ("email", "Email", "text"),
    ("phone", "Phone", "text"),
    ("_address", "Home address", "section"),
    ("address", "Address line 1", "text"),
    ("address_line2", "Address line 2", "text"),
    ("town", "Town / city", "text"),
    ("postcode", "Postcode", "text"),
    ("_emergency", "Emergency contact", "section"),
    ("emergency_contact_name", "Name", "text"),
    ("emergency_contact_relationship", "Relationship", "choice", EMERGENCY_RELATIONSHIPS),
    ("emergency_contact_phone", "Phone", "text"),
    ("_study", "Study", "section"),
    ("learner_type", "Learner type", "choice", LEARNER_TYPES),
    ("mode_of_study", "Mode of study", "choice", MODES_OF_STUDY),
    ("status", "Status", "choice", STUDENT_STATUSES),
    ("tutor_group", "Tutor group", "text"),
    ("personal_tutor", "Personal tutor (staff ID)", "text"),
    ("start_date", "Start date", "date"),
    ("prior_attainment", "Prior attainment", "text"),
    ("_needs", "Needs and medical", "section"),
    ("has_lldd", "Learning difficulty or disability?", "bool"),
    ("has_ehcp", "Has an EHC Plan?", "bool"),
    ("medical_notes", "Medical notes", "text"),
    ("notes", "Notes", "text"),
]


def create(ctl) -> None:
    """Register a new learner, then offer to create their login."""
    sh.header("New learner")
    suggested = ctl.students.next_reference()
    result = sh.form("Learner details", _CREATE_FIELDS,
                     initial={"student_id": suggested, "start_date": date.today()})
    if result is sh.CANCEL:
        return

    values = {k: v for k, v in result.items() if v is not None}
    values["student_id"] = result["student_id"] or suggested
    values["learner_type"] = result["learner_type"] or LEARNER_TYPES[0]
    values["mode_of_study"] = result["mode_of_study"] or MODES_OF_STUDY[0]
    values["status"] = result["status"] or "applicant"
    try:
        learner = Student(**values)
        try:
            created = ctl.students.create(learner, check_duplicate=True)
        except ctl.students.DuplicateLearner as dup:
            sh.warn(str(dup))
            if not sh.confirm("Twins and common names can match. Save as a new learner anyway?"):
                sh.note("Not saved. Use 'View a learner' to open the existing record.")
                return
            created = ctl.students.create(learner)
    except ValidationError as exc:
        sh.error(str(exc))
        return
    sh.success(f"Created {created.display_name}")
    if sh.confirm("Create their login and e-mail them a temporary password?", default=True):
        _create_login(created)


def create_login(ctl, student_id: str | None = None) -> None:
    """Create a login for an existing learner."""
    learner = _pick(ctl, student_id, "Learner")
    if learner is None:
        return
    if not sh.confirm(f"Create a login for {learner.full_name} (username "
                      f"{learner.student_id}) and e-mail them a temporary password?"):
        return
    _create_login(learner)


def _create_login(learner) -> None:
    """Create the login and print the sign-in details once."""
    from education_system.systems.fe_college.services import learner_accounts

    try:
        new = learner_accounts.create_login(learner.student_id)
    except Exception as exc:  # ValidationError / AccountError
        sh.error(f"The login could not be created: {exc}")
        sh.note("Use 'Create a learner login' from the menu to try again.")
        return
    sh.success(f"Login created for {learner.full_name}.")
    sh.key_values([("Username", new.username), ("Password", new.password)])
    sh.note("Note the password now. It won't be shown again.")
    sh.note(new.welcome_detail)


def enrol(ctl) -> None:
    """Enrol a learner onto a course, checking entry requirements."""
    learner = _pick(ctl, None, "Learner")
    if learner is None:
        return
    courses = ctl.courses.enrollable()
    if not courses:
        sh.note("No courses are accepting enrolments.")
        return
    course = sh.choose_object(
        "Course", courses, lambda c: f"{c.course_id} — {c.title} "
                                     f"({c.enrolled}/{c.capacity or '∞'})"
    )
    if course is sh.CANCEL:
        return
    main_aim = sh.ask_bool("Is this their main learning aim?", True)
    if main_aim is sh.CANCEL:
        return

    try:
        outcome = ctl.enrolments.enrol(
            learner.student_id, course.course_id, is_main_aim=main_aim
        )
    except ValidationError as exc:
        sh.error(str(exc))
        return

    if not outcome.enrolled:
        sh.warn(f"{learner.full_name} does not meet the entry requirements:")
        sh.bullet_list(list(outcome.actions))
        if not sh.confirm("Admit anyway?"):
            return
        try:
            outcome = ctl.enrolments.enrol(
                learner.student_id, course.course_id,
                is_main_aim=main_aim, override_eligibility=True,
            )
        except ValidationError as exc:
            sh.error(str(exc))
            return

    sh.success(f"{learner.full_name} enrolled on {course.course_id}")
    if outcome.actions:
        sh.note("Still to do:")
        sh.bullet_list(list(outcome.actions))


def withdraw(ctl) -> None:
    """Withdraw a learner from a course."""
    learner = _pick(ctl, None, "Learner")
    if learner is None:
        return
    enrolments, _warnings = ctl.enrolments.study_programme(learner.student_id)
    active = [e for e in enrolments if e.is_active]
    if not active:
        sh.note(f"{learner.full_name} has no active enrolments.")
        return

    enrolment = sh.choose_object(
        "Enrolment", active,
        lambda e: f"{e.course_id} ({e.academic_year})"
                  f"{' — main aim' if e.is_main_aim else ''}",
    )
    if enrolment is sh.CANCEL:
        return
    reason = sh.choose("Reason", list(ctl.enrolments.withdrawal_reasons()))
    if reason is sh.CANCEL:
        return
    try:
        ctl.enrolments.withdraw(enrolment.enrolment_id, reason)
    except ValidationError as exc:
        sh.error(str(exc))
        return
    sh.success(f"Withdrew {learner.full_name} from {enrolment.course_id}")


def at_risk(ctl) -> None:
    """Learners whose attendance has dropped below the threshold."""
    sh.header("Learners at risk", "Attendance below 75%, worst first.")
    rows = ctl.reports.at_risk_report()
    sh.table(
        [("student_id", "ID"), ("name", "Name"), ("tutor_group", "Group"),
         ("personal_tutor", "Tutor"), ("attendance_pct", "Attendance"),
         ("unauthorised", "Unauth."), ("band", "Band")],
        [{**r, "attendance_pct": sh.pct(r["attendance_pct"])} for r in rows],
        empty="Nobody is below the threshold.",
        limit=40,
    )


def targets(ctl) -> None:
    """Set a target for a learner."""
    learner = _pick(ctl, None, "Learner")
    if learner is None:
        return
    if not ctl.staff_id:
        sh.warn("Your account is not linked to a staff record, so the target "
                "could not be attributed to you.")
        return
    description = sh.prompt("Target")
    if description is sh.CANCEL or not description:
        return
    due = sh.ask_date("Due by")
    if due is sh.CANCEL:
        return
    try:
        ctl.students.set_target(
            learner.student_id, description, set_by=ctl.staff_id, due_date=due
        )
    except ValidationError as exc:
        sh.error(str(exc))
        return
    sh.success(f"Target set for {learner.full_name}")


def _pick(ctl, student_id: str | None, label: str):
    """Resolve a learner by ID, or prompt for one by search."""
    if student_id:
        found = ctl.students.get(student_id)
        if found is None:
            sh.error(f"No learner with ID {student_id}")
        return found

    query = sh.prompt(f"{label} — search by name or ID")
    if query is sh.CANCEL:
        return None
    matches = ctl.students.search(query=query)
    if not matches:
        sh.note("No learners match.")
        return None
    if len(matches) == 1:
        return matches[0]
    chosen = sh.choose_object("Which one?", matches[:30], lambda s: s.display_name)
    return None if chosen is sh.CANCEL else chosen


__all__ = [
    "at_risk", "create", "directory", "enrol", "targets", "view", "withdraw",
]
