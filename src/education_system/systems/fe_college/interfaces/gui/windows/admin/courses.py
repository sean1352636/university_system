"""Admin course management — the college's curriculum offer.

Split view: the course list on the left, and the selected course's units and
entry requirements on the right, because the two are always edited together.
"""

from __future__ import annotations

import logging
from datetime import date
from tkinter import ttk

from education_system.systems.fe_college.config import (
    ACADEMIC_YEAR,
    CURRICULUM_AREAS,
    MODES_OF_STUDY,
    QUALIFICATION_LEVELS,
    QUALIFICATION_TYPES,
)
from education_system.systems.fe_college.domain.courses.entry_requirements import (
    EntryRequirement,
)
from education_system.systems.fe_college.domain.courses.models import (
    COURSE_STATUSES,
    Course,
)
from education_system.systems.fe_college.domain.courses.modules import (
    ASSESSMENT_METHODS,
    UNIT_TYPES,
    Unit,
)
from education_system.systems.fe_college.domain.students.models import ValidationError
from education_system.systems.fe_college.interfaces.gui import widgets as w

logger = logging.getLogger(__name__)

TITLE = "Courses"


def open_window(host) -> None:
    Screen(host)


class Screen:
    def __init__(self, host):
        self.host = host
        self.ctl = host.ctl
        self.selected: Course | None = None
        host.clear_content()
        parent = host.content_frame

        w.page_header(
            parent, TITLE,
            "The qualifications on offer, the units they are built from, and "
            "how well each is recruiting.",
            actions=[
                ("+ New course", self.new),
                ("↻ Refresh", self.refresh),
            ],
        )

        self.filters = w.FilterBar(
            parent, self.refresh,
            search_label="Code / title",
            filters=[
                ("curriculum_area", "Area", CURRICULUM_AREAS),
                ("level", "Level", QUALIFICATION_LEVELS),
                ("status", "Status", COURSE_STATUSES),
                ("academic_year", "Year", self.ctl.courses.academic_years()),
            ],
        )

        split = ttk.Frame(parent)
        split.pack(fill="both", expand=True)
        split.columnconfigure(0, weight=3, uniform="c")
        split.columnconfigure(1, weight=2, uniform="c")
        split.rowconfigure(0, weight=1)

        left = ttk.Frame(split)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.table = w.DataTable(left, [
            ("code", "Code", 95),
            ("title", "Title", 250),
            ("qual", "Qualification", 130),
            ("level", "Lvl", 40, "e"),
            ("area", "Curriculum area", 190),
            ("enrolled", "On", 45, "e"),
            ("cap", "Cap", 45, "e"),
            ("fill", "Filled", 70, "e"),
            ("status", "Status", 90),
            ("viability", "Viability", 105),
        ], on_double_click=lambda _c: self.edit())
        self.table.tree.bind("<<TreeviewSelect>>", lambda _e: self._on_select())

        w.button_bar(left, [
            ("Edit", self.edit),
            ("Entry requirements", self.entry_requirements),
            ("Archive", self.archive),
            ("Cancel course", self.cancel),
            ("Delete", self.delete),
        ])

        self.detail = ttk.Frame(split)
        self.detail.grid(row=0, column=1, sticky="nsew")
        self.refresh()

    # ── Data ───────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        try:
            courses = self.ctl.courses.search(
                query=self.filters.query, **self.filters.values()
            )
        except Exception as exc:
            logger.exception("Could not list FE College courses")
            w.error(self.host, TITLE, f"Could not load courses: {exc}")
            return

        self.table.set_rows([
            {
                "code": c.course_id,
                "title": c.title,
                "qual": c.qualification_type,
                "level": c.level,
                "area": c.curriculum_area or "—",
                "enrolled": c.enrolled,
                "cap": c.capacity or "—",
                "fill": w.pct(c.fill_pct),
                "status": c.status,
                "viability": c.viability,
                "_tone": w.tone_for(c.viability),
                "_obj": c,
            }
            for c in courses
        ])
        self.filters.set_count(len(courses), "course")
        self.host.set_status(f"{len(courses)} course(s)")
        self._show_detail(None)

    def _on_select(self) -> None:
        self._show_detail(self.table.selection())

    def _show_detail(self, course: Course | None) -> None:
        self.selected = course
        w.clear(self.detail)
        if course is None:
            w.empty_state(self.detail, "Select a course to see its units.")
            return

        w.kv_panel(self.detail, course.display_name, [
            ("Qualification", f"{course.qualification_type} (Level {course.level})"),
            ("Awarding body", course.awarding_body or "—"),
            ("Department", course.department or "—"),
            ("Mode", f"{course.mode_of_study} · {course.campus}"),
            ("Guided learning hours", str(course.guided_learning_hours)),
            ("Runs", f"{w.when(course.start_date)} → {w.when(course.end_date)}"),
            ("Enrolled", f"{course.enrolled} of {course.capacity or '—'}"),
            ("Viability", course.viability, w.tone_for(course.viability)),
            ("Fee", w.money(course.fee)),
        ]).pack(fill="x", pady=(0, 10))

        panel = ttk.LabelFrame(self.detail, text="Units", padding=8)
        panel.pack(fill="both", expand=True)
        units = self.ctl.courses.units(course.course_id)
        self.units_table = w.DataTable(panel, [
            ("code", "Code", 70),
            ("title", "Unit", 200),
            ("type", "Type", 90),
            ("credits", "Cr", 40, "e"),
            ("method", "Assessment", 165),
        ], height=8)
        self.units_table.set_rows([
            {
                "code": u.unit_id,
                "title": u.title,
                "type": u.unit_type,
                "credits": u.credits,
                "method": u.assessment_method,
                "_obj": u,
            }
            for u in units
        ])
        ttk.Label(
            panel,
            text=f"{len(units)} unit(s) · {sum(u.credits for u in units)} credits",
            foreground=w.TONE["muted"],
        ).pack(anchor="w", pady=(6, 0))
        w.button_bar(panel, [("+ Add unit", self.add_unit),
                             ("Remove unit", self.remove_unit)])

    # ── Actions ────────────────────────────────────────────────────────────

    def new(self) -> None:
        result = w.ask(
            self.host, "New course", _fields(self.ctl),
            initial={
                "qualification_type": QUALIFICATION_TYPES[0],
                "level": "3",
                "academic_year": ACADEMIC_YEAR,
                "mode_of_study": MODES_OF_STUDY[0],
                "status": "recruiting",
                "campus": "Main Campus",
                "guided_learning_hours": 1080,
                "duration_weeks": 36,
                "capacity": 20,
                "start_date": date.today().isoformat(),
            },
            submit_label="Create",
        )
        if result is None:
            return
        try:
            self.ctl.courses.create(_to_course(result))
        except ValidationError as exc:
            w.error(self.host, "New course", str(exc))
            return
        self.refresh()

    def edit(self) -> None:
        course = self.table.require_selection("a course")
        if course is None:
            return
        result = w.ask(
            self.host, f"Edit {course.course_id}", _fields(self.ctl),
            initial=_from_course(course), submit_label="Save",
        )
        if result is None:
            return
        try:
            self.ctl.courses.update(_to_course(result))
        except ValidationError as exc:
            w.error(self.host, "Edit course", str(exc))
            return
        self.refresh()

    def entry_requirements(self) -> None:
        course = self.table.require_selection("a course")
        if course is None:
            return
        requirement = (
            self.ctl.courses.detail(course.course_id).entry_requirement
            or EntryRequirement(course_id=course.course_id)
        )
        result = w.ask(self.host, f"Entry requirements — {course.course_id}", [
            ("min_age", "Minimum age", "int"),
            ("max_age", "Maximum age (0 = none)", "int"),
            ("min_prior_level", "Minimum prior level", "choice",
             ["", "Entry", "1", "2", "3", "4", "5"]),
            ("min_gcse_english", "Minimum GCSE English", "choice",
             ["", "1", "2", "3", "4", "5", "6", "7", "8", "9"]),
            ("min_gcse_maths", "Minimum GCSE maths", "choice",
             ["", "1", "2", "3", "4", "5", "6", "7", "8", "9"]),
            ("required_subjects", "Required subjects (comma separated)", "text"),
            ("interview_required", "Interview required", "bool"),
            ("dbs_required", "DBS check required", "bool"),
            ("portfolio_required", "Portfolio required", "bool"),
            ("notes", "Notes", "multiline"),
        ], initial={
            "min_age": requirement.min_age,
            "max_age": requirement.max_age,
            "min_prior_level": requirement.min_prior_level,
            "min_gcse_english": requirement.min_gcse_english,
            "min_gcse_maths": requirement.min_gcse_maths,
            "required_subjects": ", ".join(requirement.required_subjects),
            "interview_required": requirement.interview_required,
            "dbs_required": requirement.dbs_required,
            "portfolio_required": requirement.portfolio_required,
            "notes": requirement.notes,
        })
        if result is None:
            return
        try:
            self.ctl.courses.set_entry_requirement(EntryRequirement(
                course_id=course.course_id,
                min_age=result["min_age"],
                max_age=result["max_age"],
                min_prior_level=result["min_prior_level"],
                min_gcse_english=result["min_gcse_english"],
                min_gcse_maths=result["min_gcse_maths"],
                required_subjects=tuple(
                    s.strip() for s in result["required_subjects"].split(",") if s.strip()
                ),
                interview_required=result["interview_required"],
                dbs_required=result["dbs_required"],
                portfolio_required=result["portfolio_required"],
                notes=result["notes"],
            ))
        except ValidationError as exc:
            w.error(self.host, "Entry requirements", str(exc))
            return
        self.host.set_status(f"Saved entry requirements for {course.course_id}")

    def add_unit(self) -> None:
        if self.selected is None:
            w.info(self.host, "Add unit", "Select a course first.")
            return
        result = w.ask(self.host, f"Add unit to {self.selected.course_id}", [
            ("unit_id", "Unit code", "text"),
            ("title", "Title", "text"),
            ("unit_type", "Type", "choice", UNIT_TYPES),
            ("credits", "Credits", "int"),
            ("guided_learning_hours", "Guided learning hours", "int"),
            ("assessment_method", "Assessment method", "choice", ASSESSMENT_METHODS),
            ("sequence", "Order", "int"),
            ("description", "Description", "multiline"),
        ], initial={"credits": 10, "guided_learning_hours": 60,
                    "unit_type": UNIT_TYPES[0],
                    "assessment_method": ASSESSMENT_METHODS[1]})
        if result is None:
            return
        try:
            self.ctl.courses.add_unit(Unit(
                unit_id=result["unit_id"],
                course_id=self.selected.course_id,
                title=result["title"],
                unit_type=result["unit_type"],
                credits=result["credits"],
                guided_learning_hours=result["guided_learning_hours"],
                assessment_method=result["assessment_method"],
                sequence=result["sequence"],
                description=result["description"],
            ))
        except ValidationError as exc:
            w.error(self.host, "Add unit", str(exc))
            return
        self._show_detail(self.selected)

    def remove_unit(self) -> None:
        if self.selected is None:
            return
        unit = self.units_table.require_selection("a unit")
        if unit is None:
            return
        if not w.confirm(self.host, "Remove unit",
                         f"Remove {unit.display_name} from {self.selected.course_id}?"):
            return
        self.ctl.courses.remove_unit(unit.unit_id, self.selected.course_id)
        self._show_detail(self.selected)

    def archive(self) -> None:
        course = self.table.require_selection("a course")
        if course is None:
            return
        if not w.confirm(self.host, "Archive course",
                         f"Archive {course.display_name}?\n\n"
                         "It stops appearing as enrollable. All history is kept."):
            return
        try:
            self.ctl.courses.archive(course.course_id)
        except ValidationError as exc:
            w.error(self.host, "Archive", str(exc))
            return
        self.refresh()

    def cancel(self) -> None:
        course = self.table.require_selection("a course")
        if course is None:
            return
        if not w.confirm(
            self.host, "Cancel course",
            f"Cancel {course.display_name}?\n\n"
            f"Its {course.enrolled} active enrolment(s) are withdrawn so the "
            "funding return stays correct. The learners stay on roll for any "
            "other courses they take.",
        ):
            return
        try:
            withdrawn = self.ctl.courses.cancel(course.course_id)
        except ValidationError as exc:
            w.error(self.host, "Cancel course", str(exc))
            return
        w.info(self.host, "Course cancelled",
               f"{course.course_id} cancelled and {withdrawn} enrolment(s) withdrawn.")
        self.refresh()

    def delete(self) -> None:
        course = self.table.require_selection("a course")
        if course is None:
            return
        if not w.confirm(
            self.host, "Delete course",
            f"Permanently delete {course.display_name}?\n\n"
            "Units, enrolments, sessions, assignments and attendance go with "
            "it. Archiving keeps the history instead.",
        ):
            return
        try:
            self.ctl.courses.delete(course.course_id)
        except ValidationError as exc:
            w.error(self.host, "Delete course", str(exc))
            return
        self.refresh()


# ── Form plumbing ───────────────────────────────────────────────────────────

def _fields(ctl):
    leaders = [""] + [s.staff_id for s in ctl.staff.teaching_staff()]
    return (
        ("course_id", "Course code", "text"),
        ("title", "Title", "text"),
        ("qualification_type", "Qualification", "choice", QUALIFICATION_TYPES),
        ("level", "Level", "choice", QUALIFICATION_LEVELS),
        ("curriculum_area", "Curriculum area", "choice", ["", *CURRICULUM_AREAS]),
        ("academic_year", "Academic year", "text"),
        ("mode_of_study", "Mode of study", "choice", MODES_OF_STUDY),
        ("status", "Status", "choice", COURSE_STATUSES),
        ("course_leader", "Course leader", "choice", leaders),
        ("awarding_body", "Awarding body", "text"),
        ("guided_learning_hours", "Guided learning hours", "int"),
        ("duration_weeks", "Duration (weeks)", "int"),
        ("capacity", "Capacity", "int"),
        ("start_date", "Start date", "date"),
        ("end_date", "End date", "date"),
        ("campus", "Campus", "text"),
        ("fee", "Fee (£)", "float"),
        ("description", "Description", "multiline"),
    )


def _from_course(c: Course) -> dict:
    return {
        "course_id": c.course_id,
        "title": c.title,
        "qualification_type": c.qualification_type,
        "level": c.level,
        "curriculum_area": c.curriculum_area,
        "academic_year": c.academic_year,
        "mode_of_study": c.mode_of_study,
        "status": c.status,
        "course_leader": c.course_leader,
        "awarding_body": c.awarding_body,
        "guided_learning_hours": c.guided_learning_hours,
        "duration_weeks": c.duration_weeks,
        "capacity": c.capacity,
        "start_date": w.when(c.start_date, ""),
        "end_date": w.when(c.end_date, ""),
        "campus": c.campus,
        "fee": c.fee,
        "description": c.description,
    }


def _to_course(d: dict) -> Course:
    return Course(
        course_id=d["course_id"],
        title=d["title"],
        qualification_type=d["qualification_type"],
        level=d["level"],
        curriculum_area=d["curriculum_area"],
        academic_year=d["academic_year"],
        mode_of_study=d["mode_of_study"],
        status=d["status"],
        course_leader=d["course_leader"],
        awarding_body=d["awarding_body"],
        guided_learning_hours=d["guided_learning_hours"],
        duration_weeks=d["duration_weeks"],
        capacity=d["capacity"],
        start_date=d["start_date"],
        end_date=d["end_date"],
        campus=d["campus"],
        fee=d["fee"],
        description=d["description"],
    )


__all__ = ["TITLE", "Screen", "open_window"]
