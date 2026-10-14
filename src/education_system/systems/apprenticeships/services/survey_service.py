"""Surveys: setting them up, answering them, and reading the results.

Three capabilities, deliberately separate. ``survey.manage`` (admin)
creates, opens and closes surveys. ``survey.respond`` (apprentices and
employers) answers them. ``survey.view`` (admin and staff) reads the
results — and only the results: per-question averages, the response
rate and the comments, never who said what.

That last point is enforced below the screens. The results are built
from a repository query that does not select the respondent, and the
aggregation in ``domain/quality/surveys.py`` withholds everything until
enough people have answered for no single answer to be picked out. Who
responded is stored only to stop anyone answering twice.

The End of programme survey is offered only to apprentices at EPA or
Completed; the other apprentice surveys to those on programme.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import date
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError
from education_system.systems.apprenticeships.domain.quality import surveys as rules
from education_system.systems.apprenticeships.domain.quality.surveys import Survey, SurveyResults
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    survey_repository as repo,
)
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    apprentice_repository,
    compliance_repository,
)
from education_system.systems.apprenticeships.services.access import (
    Actor,
    PermissionDenied,
    require,
    require_any,
)

logger = logging.getLogger(__name__)

_TITLE_MAX_LENGTH = 200

_ALREADY = "You have already responded to this survey — thank you"


# ═════════════════════════════════════════════════════════════════════
# Managing and reading
# ═════════════════════════════════════════════════════════════════════

def list_surveys(
    actor: Actor,
    *,
    status: str | None = None,
    audience: str | None = None,
    kind: str | None = None,
    closes_before: str | None = None,
) -> list[Survey]:
    """Every survey, for those who run them or read the results."""
    require_any(actor, "survey.view", "survey.manage")
    return repo.list_surveys(
        status=status or None, audience=audience or None, kind=kind or None,
        closes_before=closes_before or None,
    )


def get_survey(actor: Actor, survey_id: int) -> Survey:
    """One survey — any to a manager or reader, an offered one to a respondent."""
    require_any(actor, "survey.view", "survey.manage", "survey.respond")
    survey = repo.get(survey_id)
    if survey is None:
        raise ValidationError(f"No survey with id {survey_id}")
    if not (actor.can("survey.view") or actor.can("survey.manage")):
        if survey.status == "Draft" or rules.AUDIENCE_ROLES.get(survey.audience) != actor.role:
            raise PermissionDenied("This survey is not addressed to you")
    return survey


def create_survey(actor: Actor, payload: dict[str, Any]) -> Survey:
    """A new survey, as a Draft. It is offered to nobody until it is opened."""
    require(actor, "survey.manage")
    title = _title(payload.get("title"))
    kind = rules.validate_kind(payload.get("kind"))
    audience = rules.validate_audience(
        kind, payload.get("audience") or config.SURVEY_KIND_AUDIENCES[kind][0]
    )
    opens_on, closes_on = rules.validate_dates(payload.get("opens_on"), payload.get("closes_on"))

    survey_id = repo.create({
        "title": title, "audience": audience, "kind": kind, "status": "Draft",
        "opens_on": opens_on, "closes_on": closes_on, "created_by": actor.username,
    })
    compliance_repository.record(
        action="create", entity="survey", entity_id=survey_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"{title} ({kind}, {audience})",
    )
    return _reload(survey_id)


def update_survey(actor: Actor, survey_id: int, payload: dict[str, Any]) -> Survey:
    """Edit a survey that has not closed.

    Kind and audience are fixed once it opens: changing the questions
    under people who have already answered would make their answers
    mean something else.
    """
    require(actor, "survey.manage")
    survey = _require(survey_id)
    if survey.status == "Closed":
        raise ValidationError("A closed survey cannot be changed")

    changes: dict[str, Any] = {}
    if "title" in payload:
        changes["title"] = _title(payload.get("title"))
    kind = survey.kind
    if "kind" in payload or "audience" in payload:
        if survey.status != "Draft":
            raise ValidationError("The kind and audience are fixed once a survey has opened")
        kind = rules.validate_kind(payload.get("kind") or survey.kind)
        changes["kind"] = kind
        changes["audience"] = rules.validate_audience(
            kind, payload.get("audience") or survey.audience
        )
    if "opens_on" in payload or "closes_on" in payload:
        opens_on, closes_on = rules.validate_dates(
            payload.get("opens_on", survey.opens_on), payload.get("closes_on", survey.closes_on)
        )
        changes.update(opens_on=opens_on, closes_on=closes_on)

    repo.update(survey_id, changes)
    compliance_repository.record(
        action="update", entity="survey", entity_id=survey_id,
        actor=actor.username, actor_role=actor.role,
        detail=", ".join(sorted(changes)) or "no change",
    )
    return _reload(survey_id)


def open_survey(actor: Actor, survey_id: int, *, today: date | None = None) -> Survey:
    """Start taking responses. With no opening date, it opens today."""
    require(actor, "survey.manage")
    survey = _require(survey_id)
    rules.require_transition(survey.status, "Open")
    changes: dict[str, Any] = {"status": "Open"}
    if not survey.opens_on:
        changes["opens_on"] = (today or date.today()).isoformat()
    repo.update(survey_id, changes)
    compliance_repository.record(
        action="update", entity="survey", entity_id=survey_id,
        actor=actor.username, actor_role=actor.role, detail=f"{survey.title}: opened",
    )
    return _reload(survey_id)


def close_survey(actor: Actor, survey_id: int, *, today: date | None = None) -> Survey:
    """Stop taking responses. A later closing date is brought forward to today."""
    require(actor, "survey.manage")
    survey = _require(survey_id)
    rules.require_transition(survey.status, "Closed")
    as_of = (today or date.today()).isoformat()
    changes: dict[str, Any] = {"status": "Closed"}
    if not survey.closes_on or survey.closes_on > as_of:
        changes["closes_on"] = as_of
    repo.update(survey_id, changes)
    compliance_repository.record(
        action="update", entity="survey", entity_id=survey_id,
        actor=actor.username, actor_role=actor.role, detail=f"{survey.title}: closed",
    )
    return _reload(survey_id)


def results(actor: Actor, survey_id: int) -> SurveyResults:
    """A survey's anonymised results.

    Built only from answers and comments; the respondent never leaves
    the database. Withheld below ``config.SURVEY_ANONYMITY_THRESHOLD``
    responses.
    """
    require_any(actor, "survey.view", "survey.manage")
    survey = _require(survey_id)
    rows = repo.list_answers(survey_id)
    if survey.audience == "Employer":
        eligible = repo.count_employers_with_apprentices(config.ACTIVE_STATUSES)
        responded = repo.responded_count(survey_id, by="employer")
    else:
        eligible = repo.count_apprentices(rules.eligible_statuses(survey.kind))
        responded = repo.responded_count(survey_id, by="apprentice")
    return rules.summarise(
        survey,
        [answers for answers, _ in rows],
        [comment for _, comment in rows],
        eligible_count=eligible,
        responded_count=responded,
    )


# ═════════════════════════════════════════════════════════════════════
# Responding
# ═════════════════════════════════════════════════════════════════════

def available_surveys(actor: Actor, *, today: date | None = None) -> list[tuple[Survey, bool]]:
    """Open surveys *actor* may answer, each with whether they already have.

    Only surveys for their audience that they are eligible for — an
    apprentice on programme is not offered the End of programme survey.
    """
    require(actor, "survey.respond")
    as_of = today or date.today()
    audience = _audience_for(actor)
    if audience is None:
        return []
    answered = repo.responded_survey_ids(actor.username) if actor.username else set()
    offered = [
        s for s in repo.list_surveys(audience=audience, open_on=as_of.isoformat())
        if ineligibility(actor, s, today=as_of) is None
    ]
    return [(s, s.survey_id in answered) for s in offered]


def ineligibility(actor: Actor, survey: Survey, *, today: date | None = None) -> str | None:
    """Why *actor* may not answer *survey*, or None if they may."""
    as_of = today or date.today()
    if not actor.can("survey.respond"):
        return "Your role does not answer surveys"
    if not survey.is_accepting(as_of):
        return "This survey is not open for responses"
    if rules.AUDIENCE_ROLES.get(survey.audience) != actor.role:
        return f"This survey is for {survey.audience.lower()}s"
    if actor.role == config.EMPLOYER:
        if actor.employer_id is None:
            return "Your sign-in is not linked to an employer record"
        return None
    if actor.apprentice_id is None:
        return "Your sign-in is not linked to an apprentice record"
    apprentice = apprentice_repository.get(actor.apprentice_id)
    if apprentice is None or apprentice.status not in rules.eligible_statuses(survey.kind):
        if survey.kind == "End of programme":
            return "The End of programme survey is for apprentices at EPA or who have completed"
        return "This survey is for apprentices currently on programme"
    return None


def has_responded(actor: Actor, survey_id: int) -> bool:
    require(actor, "survey.respond")
    return bool(actor.username) and repo.has_responded(survey_id, actor.username)


def respond(
    actor: Actor,
    survey_id: int,
    answers: dict[str, Any],
    *,
    comment: str | None = None,
    today: date | None = None,
) -> int:
    """Submit *actor*'s response — once.

    The audit trail records that they responded, never what they said.
    """
    require(actor, "survey.respond")
    survey = get_survey(actor, survey_id)
    reason = ineligibility(actor, survey, today=today)
    if reason is not None:
        raise ValidationError(reason)
    if not actor.username:
        raise ValidationError("Your sign-in has no username to record the response against")
    if repo.has_responded(survey_id, actor.username):
        raise ValidationError(_ALREADY)

    scores = rules.validate_answers(survey.kind, answers)
    text = rules.validate_comment(comment)
    try:
        response_id = repo.add_response(
            survey_id=survey_id,
            respondent=actor.username,
            respondent_role=actor.role,
            apprentice_id=actor.apprentice_id if actor.role == config.APPRENTICE else None,
            employer_id=actor.employer_id,
            answers=scores,
            comment=text,
        )
    except sqlite3.IntegrityError as exc:
        # Two submissions racing past the check above; the unique
        # constraint is the real guarantee.
        raise ValidationError(_ALREADY) from exc
    compliance_repository.record(
        action="create", entity="survey_response", entity_id=response_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"Responded to survey {survey_id}",
    )
    return response_id


# ═════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════

def _audience_for(actor: Actor) -> str | None:
    return next((a for a, role in rules.AUDIENCE_ROLES.items() if role == actor.role), None)


def _require(survey_id: int) -> Survey:
    survey = repo.get(survey_id)
    if survey is None:
        raise ValidationError(f"No survey with id {survey_id}")
    return survey


def _reload(survey_id: int) -> Survey:
    survey = repo.get(survey_id)
    assert survey is not None
    return survey


def _title(value: Any) -> str:
    title = str(value or "").strip()
    if not title:
        raise ValidationError("A survey needs a title")
    if len(title) > _TITLE_MAX_LENGTH:
        raise ValidationError(f"A survey title must be {_TITLE_MAX_LENGTH} characters or fewer")
    return title
