"""Functional skills: the English and Maths position and the assessments behind it.

Exposes: menu, skills_menu.

Anyone holding ``skills.view`` reads; ``skills.assess`` records initial
and diagnostic assessments; changing the position itself, or recording
an exemption, is for holders of ``compliance.manage``.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.learner_support.skills_assessments import (
    SkillsAssessment,
    SkillsProfile,
)
from education_system.systems.apprenticeships.interfaces.cli import prompts
from education_system.systems.apprenticeships.interfaces.cli.commands import apprentices
from education_system.systems.apprenticeships.services import skills_service
from education_system.systems.apprenticeships.services.access import Actor

logger = logging.getLogger(__name__)

_STATUS_COLUMNS = (("Subject", 9), ("Status", 12), ("Level", 9), ("Achieved", 11),
                   ("Exemption", 32))
_ASSESSMENT_COLUMNS = (("Date", 11), ("Subject", 8), ("Type", 10), ("Level", 10),
                       ("Score", -6), ("By", 14), ("Notes", 24))


def menu(actor: Actor) -> None:
    """An apprentice sees their own; everyone else picks an apprentice first."""
    if actor.role == config.APPRENTICE:
        if actor.apprentice_id is None:
            prompts.fail("Your login is not linked to an apprentice record yet.")
            prompts.pause()
            return
        prompts.title("My Functional Skills")
        _show(actor, actor.apprentice_id)
        prompts.pause()
        return
    summary = apprentices.pick(actor, heading="Whose functional skills?", active_only=True)
    skills_menu(actor, summary.apprentice.apprentice_id, summary.full_name)


def skills_menu(actor: Actor, apprentice_id: int, name: str) -> None:
    def view() -> None:
        prompts.title(f"Functional skills — {name}")
        _show(actor, apprentice_id)
        prompts.pause()

    entries: list[tuple[str, Callable[[], None]]] = [("View", view)]
    if actor.can("skills.assess"):
        entries += [
            ("Record an assessment", lambda: _record(actor, apprentice_id)),
            ("Edit an assessment", lambda: _edit(actor, apprentice_id)),
            ("Delete an assessment", lambda: _delete(actor, apprentice_id)),
        ]
    if skills_service.can_change_status(actor):
        entries.append(("Update status or exemption", lambda: _set_status(actor, apprentice_id)))
    prompts.run_menu(f"Functional skills — {name}", entries)


def _show(actor: Actor, apprentice_id: int) -> None:
    profile = skills_service.get_profile(actor, apprentice_id)
    prompts.details([
        ("Gateway", "met" if profile.gateway_satisfied
         else "outstanding: " + ", ".join(profile.outstanding)),
        ("Needs study", ", ".join(profile.needs_study) or "none"),
        ("No initial assessment", ", ".join(profile.unassessed) or "—"),
    ])
    prompts.note("\nCurrent position:")
    prompts.table(
        _STATUS_COLUMNS, profile.skills,
        lambda s: (s.subject, s.status, s.level, s.achieved_date, s.exemption_reason),
        noun="subject",
    )
    prompts.note("\nAssessments, newest first:")
    prompts.table(
        _ASSESSMENT_COLUMNS, profile.assessments,
        lambda a: (a.assessed_on, a.subject, a.kind,
                   (a.level or "") + (" !" if a.is_below_target else ""),
                   f"{a.score:.0f}%" if a.score is not None else "", a.assessed_by, a.notes),
        noun="assessment",
        empty="no assessments recorded yet",
    )
    if any(a.is_below_target for a in profile.assessments):
        prompts.note(f"  ! below {config.SKILLS_TARGET_LEVEL}")


def _record(actor: Actor, apprentice_id: int) -> None:
    prompts.title("Record an assessment")
    created = skills_service.record_assessment(actor, apprentice_id, _payload(None))
    prompts.ok(f"Recorded the {created.kind.lower()} {created.subject} assessment.")
    prompts.pause()


def _edit(actor: Actor, apprentice_id: int) -> None:
    assessment = _pick(skills_service.get_profile(actor, apprentice_id))
    skills_service.update_assessment(actor, assessment.assessment_id, _payload(assessment))
    prompts.ok("Assessment updated.")
    prompts.pause()


def _delete(actor: Actor, apprentice_id: int) -> None:
    assessment = _pick(skills_service.get_profile(actor, apprentice_id))
    if not prompts.ask_yes_no("Really delete this assessment?"):
        raise prompts.Abort
    reason = prompts.ask("Reason for deletion", required=True)
    skills_service.delete_assessment(actor, assessment.assessment_id, reason=reason)
    prompts.ok("Assessment deleted.")
    prompts.pause()


def _set_status(actor: Actor, apprentice_id: int) -> None:
    profile = skills_service.get_profile(actor, apprentice_id)
    skill = prompts.choose("Subject", profile.skills, render=lambda s: f"{s.subject} — {s.status}")
    status = prompts.choose_value("Status", config.FUNCTIONAL_SKILL_STATUSES, default=skill.status)
    level = exemption = achieved = None
    if status == "Achieved":
        level = prompts.choose_value("Level achieved", config.FUNCTIONAL_SKILL_LEVELS,
                                     default=skill.level)
        achieved = prompts.ask("Achieved on (YYYY-MM-DD, blank for today)") or None
    elif status == "Exempt":
        exemption = prompts.choose_value("Exemption reason", config.EXEMPTION_REASONS,
                                         default=skill.exemption_reason)
    notes = prompts.ask("Notes", default=skill.notes or "")
    updated = skills_service.set_status(
        actor, apprentice_id, skill.subject, status=status, level=level,
        achieved_date=achieved, exemption_reason=exemption, notes=notes,
    )
    prompts.ok(f"{updated.subject} is now {updated.status}.")
    prompts.pause()


def _pick(profile: SkillsProfile) -> SkillsAssessment:
    if not profile.assessments:
        prompts.fail("There are no assessments on record.")
        raise prompts.Abort
    return prompts.choose(
        "Assessment", profile.assessments,
        render=lambda a: f"{a.assessed_on} {a.kind} {a.subject} — {a.level or a.score}",
    )


def _payload(existing: SkillsAssessment | None) -> dict[str, object]:
    def current(attr: str, default: str = "") -> str:
        value = getattr(existing, attr, None) if existing is not None else None
        return default if value is None else str(value)

    level = prompts.choose(
        "Level found (blank if only a score)", config.SKILLS_ASSESSMENT_LEVELS, allow_blank=True,
    )
    return {
        "subject": prompts.choose_value(
            "Subject", config.SKILLS_ASSESSMENT_SUBJECTS, default=current("subject") or None,
        ),
        "kind": prompts.choose_value(
            "Type", config.SKILLS_ASSESSMENT_KINDS, default=current("kind", "Initial"),
        ),
        "assessed_on": prompts.ask(
            "Taken on (YYYY-MM-DD)", default=current("assessed_on", date.today().isoformat()),
        ),
        "level": level or (current("level") if existing else ""),
        "score": prompts.ask("Score %", default=current("score")),
        "notes": prompts.ask("Notes", default=current("notes")),
    }
