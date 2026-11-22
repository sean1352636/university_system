"""Surveys: answer the ones offered to you, or run them and read the results.

Exposes: menu.

Apprentices and employers answer; staff read results; admins also
create, open and close. Results never name anyone — the service does
not return who answered.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from functools import partial

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.quality import surveys as rules
from education_system.systems.apprenticeships.domain.quality.surveys import Survey
from education_system.systems.apprenticeships.interfaces.cli import prompts
from education_system.systems.apprenticeships.application.quality import survey_service
from education_system.systems.apprenticeships.application.security.access import Actor

logger = logging.getLogger(__name__)

_COLUMNS = (("Survey", 28), ("Kind", 22), ("Audience", 10), ("Status", 7), ("Opens", 10),
            ("Closes", 10))


def menu(actor: Actor) -> None:
    entries: list[tuple[str, Callable[[], None]]] = []
    # The admin holds survey.respond too, but no survey is addressed to
    # the provider; only apprentices and employers are asked.
    if actor.can("survey.respond") and actor.role in (config.APPRENTICE, config.EMPLOYER):
        entries.append(("Surveys for me", partial(_answer, actor)))
    if actor.can("survey.view") or actor.can("survey.manage"):
        entries += [
            ("All surveys", partial(_list, actor)),
            ("Results", partial(_results, actor)),
        ]
    if actor.can("survey.manage"):
        entries += [
            ("New survey", partial(_create, actor)),
            ("Open a survey", partial(_change, actor, "Draft", survey_service.open_survey)),
            ("Close a survey", partial(_change, actor, "Open", survey_service.close_survey)),
        ]
    prompts.run_menu("Surveys", entries)


def _list(actor: Actor) -> None:
    prompts.title("Surveys")
    prompts.table(
        _COLUMNS, survey_service.list_surveys(actor),
        lambda s: (s.title, s.kind, s.audience, s.status, s.opens_on, s.closes_on),
        noun="survey",
    )
    prompts.pause()


def _pick(actor: Actor, *, status: str | None = None) -> Survey:
    rows = survey_service.list_surveys(actor, status=status)
    if not rows:
        prompts.fail("There are no surveys here.")
        raise prompts.Abort
    return prompts.choose("Survey", rows,
                          render=lambda s: f"{s.title} — {s.kind}, {s.status}")


# ═════════════════════════════════════════════════════════════════════
# Answering
# ═════════════════════════════════════════════════════════════════════

def _answer(actor: Actor) -> None:
    offered = survey_service.available_surveys(actor)
    waiting = [s for s, done in offered if not done]
    prompts.title("Surveys for me")
    if not waiting:
        prompts.note("There is nothing for you to answer at the moment"
                      + (" — thank you for your responses." if offered else "."))
        prompts.pause()
        return
    survey = prompts.choose("Survey", waiting,
                            render=lambda s: f"{s.title} (closes {s.closes_on or 'open-ended'})")
    prompts.note("Your answers are anonymous. For each question choose from:")
    for score, label in enumerate(rules.SCALE, 1):
        prompts.note(f"  {score}) {label}")
    answers: dict[str, object] = {}
    for question in survey.questions:
        prompts.note(f"\n{question}")
        answers[question] = prompts.choose_value("Your answer", rules.SCALE)
    comment = prompts.ask("\n  Anything else you would like to tell us? (optional)")
    survey_service.respond(actor, survey.survey_id, answers, comment=comment or None)
    prompts.ok("Thank you — your response has been recorded.")
    prompts.pause()


# ═════════════════════════════════════════════════════════════════════
# Running and reading
# ═════════════════════════════════════════════════════════════════════

def _results(actor: Actor) -> None:
    survey = _pick(actor)
    result = survey_service.results(actor, survey.survey_id)
    prompts.title(f"Results — {survey.title}")
    prompts.details([
        ("Kind", survey.kind),
        ("Audience", survey.audience),
        ("Status", survey.status),
        ("Responses", result.response_count),
        ("Eligible", result.eligible_count),
        ("Response rate", "—" if result.response_rate is None else f"{result.response_rate}%"),
    ])
    if result.withheld:
        prompts.note(f"\nResults are shown once at least {config.SURVEY_ANONYMITY_THRESHOLD} "
                     "people have responded, so no answer can be traced to one person.")
        prompts.pause()
        return
    prompts.table(
        (("Question", 48), ("Avg", -5), ("Typical answer", 18), ("n", -4), ("1→5", 14)),
        result.questions,
        lambda q: (q.question, q.average, q.average_label, q.answered,
                   " ".join(str(n) for n in q.distribution)),
        noun="question",
    )
    prompts.note("\nComments:")
    if not result.comments:
        prompts.note("  (none)")
    for text in result.comments:
        prompts.note(f"  • {text}")
    prompts.pause()


def _create(actor: Actor) -> None:
    prompts.title("New survey")
    kind = prompts.choose_value("Kind (decides the questions)", config.SURVEY_KINDS)
    audiences = config.SURVEY_KIND_AUDIENCES[kind]
    audience = audiences[0] if len(audiences) == 1 else prompts.choose_value(
        "Audience", audiences)
    created = survey_service.create_survey(actor, {
        "title": prompts.ask("Title", required=True),
        "kind": kind,
        "audience": audience,
        "opens_on": prompts.ask("Opens on (YYYY-MM-DD, blank for when you open it)"),
        "closes_on": prompts.ask("Closes on (YYYY-MM-DD, optional)"),
    })
    prompts.ok(f"“{created.title}” saved as a Draft. Open it to start taking responses.")
    prompts.pause()


def _change(actor: Actor, status: str, action: Callable[[Actor, int], Survey]) -> None:
    survey = _pick(actor, status=status)
    changed = action(actor, survey.survey_id)
    prompts.ok(f"“{changed.title}” is now {changed.status}.")
    prompts.pause()
