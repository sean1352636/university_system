"""The signed-in session, shared by the GUI and the CLI.

Neither interface imports a repository or touches the database directly.
Both hold a :class:`CollegeSession`, which owns the signed-in identity and
exposes the services through it. That gives one place to answer the two
questions every screen asks — *who is this* and *what may they see* — instead
of each screen re-deriving the answer from a session dict, and it keeps the
GUI and the CLI from drifting apart on the answer.

Identity resolution matters here: shared auth knows the *account*, while this
college knows the staff or learner *record*. The controller joins the two (by
email, then by username) once at construction, so a lecturer's marking queue
and a learner's timetable resolve without every window repeating the lookup.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from education_system.systems.fe_college.config import (
    ACADEMIC_YEAR,
    COLLEGE_NAME,
)
from education_system.systems.fe_college.domain.staff.models import Staff
from education_system.systems.fe_college.domain.students.models import Student
from education_system.systems.fe_college.services import (
    assessment_service,
    attendance_service,
    course_service,
    enrolment_service,
    reporting_service,
    staff_service,
    student_service,
    timetable_service,
)

logger = logging.getLogger(__name__)

# Launcher roles mapped onto the three views this system offers. The launcher
# also issues "teacher", "parent" and "alumni"; a teacher is a staff view, and
# the other two get the read-only learner view rather than being refused.
ROLE_VIEWS = {
    "admin": "admin",
    "staff": "staff",
    "teacher": "staff",
    "student": "student",
    "parent": "student",
    "alumni": "student",
}


@dataclass
class Identity:
    """Who the signed-in user is, in this college's own terms."""

    username: str
    display_name: str
    role: str
    view: str
    email: str = ""
    staff: Staff | None = None
    student: Student | None = None

    @property
    def staff_id(self) -> str:
        return self.staff.staff_id if self.staff else ""

    @property
    def student_id(self) -> str:
        return self.student.student_id if self.student else ""

    @property
    def is_admin(self) -> bool:
        return self.view == "admin"

    @property
    def is_staff(self) -> bool:
        return self.view == "staff"

    @property
    def is_student(self) -> bool:
        return self.view == "student"

    @property
    def label(self) -> str:
        """How the user is described in the status bar."""
        if self.staff:
            return f"{self.staff.full_name} · {self.staff.role}"
        if self.student:
            return f"{self.student.full_name} · {self.student.student_id}"
        return f"{self.display_name} · {self.role}"


class CollegeSession:
    """Mediates between an interface and the service layer."""

    # Services exposed as attributes so a screen reads
    # ``self.ctl.students.search(...)`` rather than importing eight modules.
    students = student_service
    staff = staff_service
    courses = course_service
    enrolments = enrolment_service
    attendance = attendance_service
    assessment = assessment_service
    timetable = timetable_service
    reports = reporting_service

    def __init__(self, session_user: dict | None = None, role: str = "student"):
        self.session_user = session_user or {}
        self.college_name = COLLEGE_NAME
        self.academic_year = ACADEMIC_YEAR
        self.identity = self._resolve(self.session_user, role)

    # ── Identity ───────────────────────────────────────────────────────────

    def _resolve(self, user: dict, role: str) -> Identity:
        username = user.get("username", "")
        email = user.get("email", "") or ""
        resolved_role = (role or user.get("role") or "student").lower()
        view = ROLE_VIEWS.get(resolved_role, "student")

        identity = Identity(
            username=username,
            display_name=user.get("display_name") or username or "User",
            role=resolved_role,
            view=view,
            email=email,
        )

        # Staff and learner records are looked up defensively: a valid account
        # with no college record is normal (a new starter, a superadmin), and
        # must not stop the window opening.
        try:
            if view in ("admin", "staff"):
                identity.staff = self._find_staff(email, username)
            if view == "student":
                identity.student = self._find_student(email, username)
                if identity.student is not None and resolved_role in ("student", "alumni"):
                    # Sign-in is where a login from before automatic linking
                    # meets it. The platform re-checks the pairing exactly
                    # (never the fuzzy search above), so this can only link
                    # a login to a learner it unmistakably belongs to.
                    from education_system.platform.cross_system import login_links
                    login_links.try_sync_username(username)
        except Exception:
            logger.exception("Could not resolve FE College record for %s", username)
        return identity

    def _find_staff(self, email: str, username: str) -> Staff | None:
        if email:
            found = staff_service.find_by_email(email)
            if found is not None:
                return found
        if username:
            # Fall back to the ID itself, so a demo account named after a staff
            # reference (STF-0002) still resolves without an email match.
            found = staff_service.get(username.upper())
            if found is not None:
                return found
            matches = staff_service.search(username)
            if len(matches) == 1:
                return matches[0]
        return None

    def _find_student(self, email: str, username: str) -> Student | None:
        if username:
            found = student_service.get(username.upper())
            if found is not None:
                return found
        for term in (email, username):
            if not term:
                continue
            matches = student_service.search(term)
            if len(matches) == 1:
                return matches[0]
        return None

    def rebind_staff(self, staff_id: str) -> Staff | None:
        """Attach a staff record to the session by hand.

        Used by the admin Users window when an account has no matching staff
        record — the alternative is a lecturer whose marking queue is
        permanently empty with no way to fix it from inside the app.
        """
        found = staff_service.get(staff_id)
        if found is not None:
            self.identity.staff = found
        return found

    def rebind_student(self, student_id: str) -> Student | None:
        found = student_service.get(student_id)
        if found is not None:
            self.identity.student = found
        return found

    # ── Convenience ────────────────────────────────────────────────────────

    @property
    def view(self) -> str:
        return self.identity.view

    @property
    def staff_id(self) -> str:
        return self.identity.staff_id

    @property
    def student_id(self) -> str:
        return self.identity.student_id

    def can(self, capability: str) -> bool:
        """Whether the signed-in user may do something.

        Deliberately coarse — this system has three views, not a permission
        matrix. Anything finer belongs in shared auth, not here.
        """
        view = self.identity.view
        if view == "admin":
            return True
        if view == "staff":
            return capability in {
                "view_learners", "take_register", "mark_work", "set_assignments",
                "plan_lessons", "view_timetable", "log_pastoral", "view_reports",
            }
        return capability in {"view_own", "submit_work", "view_timetable"}

    def dashboard_stats(self):
        """The dashboard figures for whichever view is signed in."""
        if self.identity.is_admin:
            return reporting_service.college_stats()
        if self.identity.is_staff and self.staff_id:
            return reporting_service.staff_stats(self.staff_id)
        if self.identity.is_student and self.student_id:
            return reporting_service.student_stats(self.student_id)
        return None

    def my_courses(self) -> list:
        """The courses relevant to the signed-in user."""
        if self.identity.is_admin:
            return course_service.list_all()
        if self.identity.is_staff and self.staff_id:
            led = course_service.search(course_leader=self.staff_id)
            group_courses = {
                g.course_id for g in course_service.groups(teacher_id=self.staff_id)
            }
            seen = {c.course_id for c in led}
            return led + [
                c for c in course_service.list_all()
                if c.course_id in group_courses and c.course_id not in seen
            ]
        if self.identity.is_student and self.student_id:
            enrolments = student_service.profile(self.student_id)
            if enrolments is None:
                return []
            ids = {e.course_id for e in enrolments.enrolments if e.is_active}
            return [c for c in course_service.list_all() if c.course_id in ids]
        return []

    def my_learners(self) -> list[Student]:
        """The learners the signed-in user is responsible for."""
        if self.identity.is_admin:
            return student_service.list_active()
        if self.identity.is_staff and self.staff_id:
            seen: dict[str, Student] = {}
            for course in self.my_courses():
                for learner in student_service.search(course_id=course.course_id):
                    seen[learner.student_id] = learner
            for learner in student_service.search(personal_tutor=self.staff_id):
                seen[learner.student_id] = learner
            return sorted(seen.values(), key=lambda s: (s.last_name, s.first_name))
        return []

    def subtitle(self) -> str:
        """The line under every screen title."""
        return f"{self.college_name} · {self.academic_year} · {self.identity.label}"


__all__ = ["ROLE_VIEWS", "CollegeSession", "Identity"]
