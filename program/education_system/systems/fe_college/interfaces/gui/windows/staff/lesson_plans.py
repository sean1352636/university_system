"""Lesson plans — what a lecturer intends to teach, session by session.

Deliberately short: objectives, activities, differentiation, and the evaluation
written afterwards. A plan can be attached to a timetabled session so it turns
up against the right slot.
"""

from __future__ import annotations

import logging
from datetime import date
from tkinter import ttk

from education_system.systems.fe_college.domain.students.models import ValidationError
from education_system.systems.fe_college.domain.teaching.lesson_plans import (
    PLAN_STATUSES,
    LessonPlan,
)
from education_system.systems.fe_college.interfaces.gui import widgets as w

logger = logging.getLogger(__name__)

TITLE = "Lesson plans"


def open_window(host) -> None:
    Screen(host)


class Screen:
    def __init__(self, host):
        self.host = host
        self.ctl = host.ctl
        host.clear_content()
        parent = host.content_frame

        w.page_header(
            parent, TITLE,
            "Plans for your taught sessions, with the evaluation written after.",
            actions=[
                ("+ New plan", self.new),
                ("↻ Refresh", self.refresh),
            ],
        )

        if not self.ctl.staff_id:
            w.empty_state(parent, "Your account is not linked to a staff record, "
                                  "so you have no lesson plans.")
            return

        self.filters = w.FilterBar(
            parent, self.refresh, search=False,
            filters=[
                ("course_id", "Course", [c.course_id for c in self.ctl.my_courses()]),
                ("status", "Status", PLAN_STATUSES),
            ],
        )

        split = ttk.Frame(parent)
        split.pack(fill="both", expand=True)
        split.columnconfigure(0, weight=3, uniform="p")
        split.columnconfigure(1, weight=2, uniform="p")
        split.rowconfigure(0, weight=1)

        left = ttk.Frame(split)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.table = w.DataTable(left, [
            ("title", "Plan", 240),
            ("course", "Course", 95),
            ("group", "Group", 105),
            ("unit", "Unit", 65),
            ("date", "Date", 100),
            ("status", "Status", 90),
        ], on_double_click=lambda _p: self.edit())
        self.table.tree.bind("<<TreeviewSelect>>", lambda _e: self._show_detail())

        w.button_bar(left, [
            ("Edit", self.edit),
            ("Mark delivered", self.mark_delivered),
            ("Duplicate", self.duplicate),
            ("Delete", self.delete),
        ])

        self.detail = ttk.Frame(split)
        self.detail.grid(row=0, column=1, sticky="nsew")
        self.refresh()

    # ── Data ───────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        try:
            plans = self.ctl.timetable.lesson_plans(
                teacher_id=self.ctl.staff_id, **self.filters.values()
            )
        except Exception as exc:
            logger.exception("Could not list FE College lesson plans")
            w.error(self.host, TITLE, f"Could not load lesson plans: {exc}")
            return

        self.table.set_rows([
            {
                "title": p.title,
                "course": p.course_id,
                "group": p.group_id or "—",
                "unit": p.unit_id or "—",
                "date": w.when(p.lesson_date),
                "status": p.status,
                "_tone": (
                    "good" if p.status == "delivered"
                    else "muted" if p.status == "archived"
                    else "warn" if p.status == "draft"
                    else "plain"
                ),
                "_obj": p,
            }
            for p in plans
        ])
        self.filters.set_count(len(plans), "plan")
        self.host.set_status(f"{len(plans)} lesson plan(s)")
        w.clear(self.detail)
        w.empty_state(self.detail, "Select a plan to read it.")

    def _show_detail(self) -> None:
        plan = self.table.selection()
        w.clear(self.detail)
        if plan is None:
            return
        inner, _canvas = w.scrollable(self.detail)
        ttk.Label(inner, text=plan.title, font=("", 12, "bold"),
                  wraplength=340, justify="left").pack(anchor="w", pady=(0, 6))
        w.kv_panel(inner, "Session", [
            ("Course", plan.course_id),
            ("Group", plan.group_id or "—"),
            ("Unit", plan.unit_id or "—"),
            ("Date", w.when(plan.lesson_date)),
            ("Status", plan.status),
        ]).pack(fill="x", pady=(0, 8))

        for heading, body in (
            ("Learning objectives", plan.objectives),
            ("Activities", plan.activities),
            ("Differentiation", plan.differentiation),
            ("Assessment", plan.assessment),
            ("Resources", plan.resources),
            ("Homework", plan.homework),
            ("Evaluation", plan.evaluation),
        ):
            if not body:
                continue
            panel = ttk.LabelFrame(inner, text=heading, padding=8)
            panel.pack(fill="x", pady=(0, 6))
            ttk.Label(panel, text=body, wraplength=330,
                      justify="left").pack(anchor="w")

    # ── Actions ────────────────────────────────────────────────────────────

    def _form(self, plan: LessonPlan | None):
        courses = self.ctl.my_courses()
        if not courses:
            w.info(self.host, TITLE, "You are not assigned to any courses.")
            return None
        course_options = [f"{c.course_id} — {c.title}" for c in courses]
        selected = plan.course_id if plan else courses[0].course_id
        units = [""] + [u.unit_id for u in self.ctl.courses.units(selected)]
        groups = [""] + [g.group_id for g in self.ctl.courses.groups(selected)]

        return w.ask(
            self.host, "New lesson plan" if plan is None else f"Edit {plan.title}",
            [
                ("course", "Course", "choice", course_options),
                ("title", "Title", "text"),
                ("group_id", "Class group", "choice", groups),
                ("unit_id", "Unit", "choice", units),
                ("lesson_date", "Lesson date", "date"),
                ("status", "Status", "choice", PLAN_STATUSES),
                ("objectives", "Learning objectives (one per line)", "multiline"),
                ("activities", "Activities", "multiline"),
                ("differentiation", "Differentiation", "multiline"),
                ("assessment", "Assessment", "multiline"),
                ("resources", "Resources", "text"),
                ("homework", "Homework", "text"),
                ("evaluation", "Evaluation (after the lesson)", "multiline"),
            ],
            initial={
                "course": next(
                    (o for o in course_options if o.startswith(selected)),
                    course_options[0],
                ),
                "title": plan.title if plan else "",
                "group_id": plan.group_id if plan else "",
                "unit_id": plan.unit_id if plan else "",
                "lesson_date": w.when(
                    plan.lesson_date if plan else date.today(), ""
                ),
                "status": plan.status if plan else "draft",
                "objectives": plan.objectives if plan else "",
                "activities": plan.activities if plan else "",
                "differentiation": plan.differentiation if plan else "",
                "assessment": plan.assessment if plan else "",
                "resources": plan.resources if plan else "",
                "homework": plan.homework if plan else "",
                "evaluation": plan.evaluation if plan else "",
            },
        )

    def _save(self, result: dict, plan: LessonPlan | None) -> bool:
        saved = LessonPlan(
            plan_id=plan.plan_id if plan else None,
            course_id=result["course"].split(" — ")[0],
            title=result["title"],
            teacher_id=self.ctl.staff_id,
            group_id=result["group_id"],
            unit_id=result["unit_id"],
            session_id=plan.session_id if plan else None,
            lesson_date=result["lesson_date"],
            status=result["status"],
            objectives=result["objectives"],
            activities=result["activities"],
            resources=result["resources"],
            differentiation=result["differentiation"],
            assessment=result["assessment"],
            homework=result["homework"],
            evaluation=result["evaluation"],
        )
        try:
            self.ctl.timetable.save_lesson_plan(saved)
        except ValidationError as exc:
            w.error(self.host, "Lesson plan", str(exc))
            return False
        return True

    def new(self) -> None:
        result = self._form(None)
        if result is not None and self._save(result, None):
            self.refresh()

    def edit(self) -> None:
        plan = self.table.require_selection("a lesson plan")
        if plan is None:
            return
        result = self._form(plan)
        if result is not None and self._save(result, plan):
            self.refresh()

    def duplicate(self) -> None:
        """Copy a plan for the next delivery — the common case for a repeat."""
        plan = self.table.require_selection("a lesson plan")
        if plan is None:
            return
        copy = LessonPlan(
            plan_id=None,
            course_id=plan.course_id,
            title=f"{plan.title} (copy)",
            teacher_id=self.ctl.staff_id,
            group_id=plan.group_id,
            unit_id=plan.unit_id,
            lesson_date=None,
            status="draft",
            objectives=plan.objectives,
            activities=plan.activities,
            resources=plan.resources,
            differentiation=plan.differentiation,
            assessment=plan.assessment,
            homework=plan.homework,
            # The evaluation belongs to the delivery that produced it, not to
            # the copy, so it is deliberately not carried over.
            evaluation="",
        )
        try:
            self.ctl.timetable.save_lesson_plan(copy)
        except ValidationError as exc:
            w.error(self.host, "Duplicate", str(exc))
            return
        self.refresh()

    def mark_delivered(self) -> None:
        plan = self.table.require_selection("a lesson plan")
        if plan is None:
            return
        result = w.ask(self.host, f"Delivered — {plan.title}", [
            ("lesson_date", "Taught on", "date"),
            ("evaluation", "How did it go?", "multiline"),
        ], initial={
            "lesson_date": w.when(plan.lesson_date or date.today(), ""),
            "evaluation": plan.evaluation,
        })
        if result is None:
            return
        plan.status = "delivered"
        plan.lesson_date = result["lesson_date"]
        plan.evaluation = result["evaluation"]
        try:
            self.ctl.timetable.save_lesson_plan(plan)
        except ValidationError as exc:
            w.error(self.host, "Mark delivered", str(exc))
            return
        self.refresh()

    def delete(self) -> None:
        plan = self.table.require_selection("a lesson plan")
        if plan is None:
            return
        if not w.confirm(self.host, "Delete plan", f"Delete '{plan.title}'?"):
            return
        self.ctl.timetable.delete_lesson_plan(plan.plan_id)
        self.refresh()


__all__ = ["TITLE", "Screen", "open_window"]
