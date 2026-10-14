"""Functional skills: where English and Maths stand, and where they started.

The top half is the current position gateway checks — Achieved, Exempt,
In progress — which belongs to compliance and only a holder of
``compliance.manage`` may change. The bottom half is the initial and
diagnostic assessments behind it (``skills.assess`` records them). One
screen serves provider staff, the apprentice and their employer; the
service scopes what each sees and the buttons follow the permissions.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.learner_support.skills_assessments import (
    SkillsAssessment,
    SkillsProfile,
)
from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.services import apprentice_service, skills_service

logger = logging.getLogger(__name__)

UNLINKED = (
    "Your sign-in is not linked to an apprentice record yet, so there is nothing to "
    "show. Ask your training provider's administrator to link your account."
)

PICK_COLUMNS = (
    ("name", "Apprentice", 220),
    ("programme", "Programme", 240),
    ("employer", "Employer", 200),
    ("status", "Status", 130),
)

STATUS_COLUMNS = (
    ("subject", "Subject", 110),
    ("status", "Status", 110),
    ("level", "Level", 100),
    ("achieved", "Achieved", 110),
    ("exemption", "Exemption reason", 260),
    ("notes", "Notes", 300),
)

ASSESSMENT_COLUMNS = (
    ("date", "Date", 110),
    ("subject", "Subject", 90),
    ("kind", "Type", 90),
    ("level", "Level found", 110),
    ("score", "Score", 70, "e"),
    ("by", "Assessed by", 140),
    ("notes", "Notes", 340),
)


def render(gui: Any) -> None:
    """The apprentice's own position, or the cohort to choose from."""
    frame = gui.clear()
    widgets.heading(
        frame,
        "Functional Skills",
        subtitle="English and Maths towards gateway, and the initial and diagnostic "
                 "assessments that set the starting point.",
    )
    if gui.actor.role == config.APPRENTICE:
        if gui.actor.apprentice_id is None:
            widgets.empty_state(frame, UNLINKED)
            return
        _profile(gui, frame, gui.actor.apprentice_id, reload=lambda: render(gui))
        return

    ok, people = widgets.guard(
        lambda: apprentice_service.list_apprentices(gui.actor, active_only=True)
    )
    if not ok:
        return
    if not people:
        widgets.empty_state(frame, "There are no active apprentices whose records you can see.")
        return

    table = widgets.DataTable(
        frame, PICK_COLUMNS, on_activate=lambda ident: _open(gui, int(ident))
    )

    def open_selected() -> None:
        apprentice_id = table.require_selection_int("open their functional skills")
        if apprentice_id is not None:
            _open(gui, apprentice_id)

    # Packed before the table fills: an expanding table packed first
    # would push the action bar off a short screen.
    widgets.button_bar(frame, [("Open functional skills →", open_selected)])
    table.populate(
        people,
        lambda s: (s.full_name, s.programme_title, s.employer_name, s.apprentice.status),
        identity=lambda s: s.apprentice.apprentice_id,
        noun="apprentice",
    )


def _open(gui: Any, apprentice_id: int) -> None:
    frame = gui.clear()
    ok, summary = widgets.guard(
        lambda: apprentice_service.get_apprentice(gui.actor, apprentice_id)
    )
    name = summary.full_name if ok and summary else f"Apprentice {apprentice_id}"
    widgets.heading(frame, f"Functional Skills — {name}")
    widgets.button_bar(frame, [("← All apprentices", lambda: render(gui))])
    if ok:
        _profile(gui, frame, apprentice_id, reload=lambda: _open(gui, apprentice_id))


def _profile(gui: Any, frame: Any, apprentice_id: int, *, reload: Callable[[], None]) -> None:
    ok, profile = widgets.guard(lambda: skills_service.get_profile(gui.actor, apprentice_id))
    if not ok:
        return
    body = widgets.scrollable(frame)
    by_subject = {s.subject: s for s in profile.skills}
    kpis: list[tuple[str, Any]] = [
        (subject, by_subject[subject].status if subject in by_subject else "—")
        for subject in config.FUNCTIONAL_SKILLS
    ]
    kpis += [
        ("Gateway", "Met" if profile.gateway_satisfied else "Outstanding"),
        ("Needs study", ", ".join(profile.needs_study) or "None"),
        ("Assessments", len(profile.assessments)),
    ]
    widgets.kpi_row(body, kpis)
    _status(gui, body, profile, reload)
    _assessments(gui, body, profile, reload)


# ═════════════════════════════════════════════════════════════════════
# The current position
# ═════════════════════════════════════════════════════════════════════

def _status(gui: Any, parent: Any, profile: SkillsProfile, reload: Callable[[], None]) -> None:
    box = widgets.section(parent, "Current position")
    by_subject = {s.subject: s for s in profile.skills}
    table: widgets.DataTable | None = None

    def update() -> None:
        if table is None:
            return
        subject = table.require_selection("update a subject")
        if subject in by_subject:
            _status_form(gui, profile.apprentice_id, by_subject[subject], reload)

    if skills_service.can_change_status(gui.actor):
        widgets.button_bar(box, [("Update status or exemption…", update)])
    elif gui.actor.can("skills.assess"):
        widgets.empty_state(
            box, "Status and exemption changes are made by a provider administrator, "
                 "from the evidence recorded here.",
        )

    table = widgets.DataTable(box, STATUS_COLUMNS, height=len(profile.skills) or 2)
    table.populate(
        profile.skills,
        lambda s: (s.subject, s.status, s.level, s.achieved_date, s.exemption_reason, s.notes),
        identity=lambda s: s.subject,
        tag=lambda s: "Green" if s.is_satisfied else None,
        noun="subject",
    )


def _status_form(gui: Any, apprentice_id: int, skill: Any, reload: Callable[[], None]) -> None:
    fields = [
        {"key": "status", "label": "Status", "kind": "combo",
         "options": config.FUNCTIONAL_SKILL_STATUSES, "value": skill.status},
        {"key": "level", "label": "Level achieved", "kind": "combo",
         "options": ["", *config.FUNCTIONAL_SKILL_LEVELS], "value": skill.level or "",
         "help": "Required when Achieved."},
        {"key": "achieved_date", "label": "Achieved on", "value": skill.achieved_date or "",
         "help": "YYYY-MM-DD. Defaults to today when Achieved."},
        {"key": "exemption_reason", "label": "Exemption reason", "kind": "combo",
         "options": ["", *config.EXEMPTION_REASONS], "value": skill.exemption_reason or "",
         "help": "Required when Exempt."},
        {"key": "notes", "label": "Notes", "kind": "text", "value": skill.notes or ""},
    ]

    def save(values: dict[str, Any]) -> object:
        return skills_service.set_status(
            gui.actor, apprentice_id, skill.subject,
            status=values.get("status") or "Not started",
            level=values.get("level") or None,
            achieved_date=values.get("achieved_date") or None,
            exemption_reason=values.get("exemption_reason") or None,
            notes=values.get("notes") or None,
        )

    dialog = widgets.FormDialog(
        gui.root, f"{skill.subject} — status", fields, save,
        intro="Achieved and Exempt both satisfy gateway, so each needs its evidence: a "
              "level for an achievement, a recognised reason for an exemption.",
    )
    if dialog.saved:
        reload()


# ═════════════════════════════════════════════════════════════════════
# Assessments
# ═════════════════════════════════════════════════════════════════════

def _assessments(gui: Any, parent: Any, profile: SkillsProfile,
                 reload: Callable[[], None]) -> None:
    box = widgets.section(parent, "Initial and diagnostic assessments")
    by_id = {a.assessment_id: a for a in profile.assessments}
    table: widgets.DataTable | None = None

    def selected(action: str) -> SkillsAssessment | None:
        if table is None:
            widgets.warn("There are no assessments yet.", title="Nothing to choose")
            return None
        ident = table.require_selection_int(action)
        return by_id.get(ident) if ident is not None else None

    def add() -> None:
        _assessment_form(gui, profile.apprentice_id, None, reload)

    def edit() -> None:
        assessment = selected("edit an assessment")
        if assessment is not None:
            _assessment_form(gui, profile.apprentice_id, assessment, reload)

    def delete() -> None:
        assessment = selected("delete an assessment")
        if assessment is None:
            return
        reason = widgets.ask_reason(
            f"Why is the {assessment.kind.lower()} {assessment.subject} assessment of "
            f"{assessment.assessed_on} being deleted?"
        )
        if not reason:
            return
        ok, _ = widgets.guard(lambda: skills_service.delete_assessment(
            gui.actor, assessment.assessment_id, reason=reason
        ))
        if ok:
            reload()

    if gui.actor.can("skills.assess"):
        widgets.button_bar(box, [
            ("Record assessment…", add), ("Edit…", edit), ("Delete…", delete),
        ])

    missing = profile.unassessed
    if missing:
        widgets.empty_state(box, "No initial assessment on record for: " + ", ".join(missing))
    if not profile.assessments:
        return
    table = widgets.DataTable(box, ASSESSMENT_COLUMNS, height=min(8, len(profile.assessments)))
    table.populate(
        profile.assessments,
        lambda a: (a.assessed_on, a.subject, a.kind, a.level,
                   f"{a.score:.0f}%" if a.score is not None else "", a.assessed_by, a.notes),
        identity=lambda a: a.assessment_id,
        tag=lambda a: "Amber" if a.is_below_target else None,
        noun="assessment",
    )


def _assessment_form(gui: Any, apprentice_id: int, assessment: SkillsAssessment | None,
                     reload: Callable[[], None]) -> None:
    def current(attr: str, default: Any = "") -> Any:
        value = getattr(assessment, attr, None) if assessment is not None else None
        return default if value is None else value

    fields = [
        {"key": "subject", "label": "Subject", "kind": "combo",
         "options": config.SKILLS_ASSESSMENT_SUBJECTS,
         "value": current("subject", config.SKILLS_ASSESSMENT_SUBJECTS[0])},
        {"key": "kind", "label": "Type", "kind": "combo",
         "options": config.SKILLS_ASSESSMENT_KINDS, "value": current("kind", "Initial")},
        {"key": "assessed_on", "label": "Taken on", "required": True,
         "value": current("assessed_on", date.today().isoformat()), "help": "YYYY-MM-DD."},
        {"key": "level", "label": "Level found", "kind": "combo",
         "options": ["", *config.SKILLS_ASSESSMENT_LEVELS], "value": current("level")},
        {"key": "score", "label": "Score %", "value": str(current("score"))},
        {"key": "notes", "label": "Notes", "kind": "text", "value": current("notes")},
    ]

    def save(values: dict[str, Any]) -> object:
        if assessment is None:
            return skills_service.record_assessment(gui.actor, apprentice_id, values)
        return skills_service.update_assessment(gui.actor, assessment.assessment_id, values)

    dialog = widgets.FormDialog(
        gui.root, "Edit assessment" if assessment else "Record an assessment", fields, save,
        intro=f"Record the level found, the score, or both. English and Maths below "
              f"{config.SKILLS_TARGET_LEVEL} are flagged for functional-skills study.",
    )
    if dialog.saved:
        reload()
