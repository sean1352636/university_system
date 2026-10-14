"""Surveys: answering them, running them, and reading the results.

Apprentices and employers see the surveys open to them and answer each
once. Provider staff read the results; administrators also create, open
and close surveys. Results are anonymous: the screen is given averages,
a response rate and comments, and nothing that says who answered — the
service does not hand it over.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.quality import surveys as rules
from education_system.systems.apprenticeships.domain.quality.surveys import Survey
from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.services import survey_service

logger = logging.getLogger(__name__)

COLUMNS = (
    ("title", "Survey", 260),
    ("kind", "Kind", 170),
    ("audience", "Audience", 100),
    ("status", "Status", 90),
    ("opens", "Opens", 100),
    ("closes", "Closes", 100),
)

OFFERED_COLUMNS = (
    ("title", "Survey", 320),
    ("kind", "Kind", 180),
    ("closes", "Closes", 110),
    ("done", "Answered", 90),
)

QUESTION_COLUMNS = (
    ("question", "Question", 520),
    ("average", "Average (1–5)", 110, "e"),
    ("label", "Typical answer", 150),
    ("answered", "Answers", 80, "e"),
    ("spread", "Spread (1 → 5)", 150),
)


def render(gui: Any) -> None:
    if gui.actor.can("survey.view") or gui.actor.can("survey.manage"):
        _manage(gui)
    else:
        _offered(gui)


# ═════════════════════════════════════════════════════════════════════
# Answering
# ═════════════════════════════════════════════════════════════════════

def _offered(gui: Any) -> None:
    frame = gui.clear()
    widgets.heading(
        frame, "Surveys",
        subtitle="Your answers are anonymous: results are only ever shown as averages "
                 "across everyone who responded.",
    )
    ok, offered = widgets.guard(lambda: survey_service.available_surveys(gui.actor))
    if not ok:
        return
    if not offered:
        widgets.empty_state(frame, "There are no surveys for you to answer at the moment.")
        return
    by_id = {s.survey_id: (s, done) for s, done in offered}
    table = widgets.DataTable(frame, OFFERED_COLUMNS,
                              on_activate=lambda ident: answer(int(ident)))

    def answer(survey_id: int | None) -> None:
        if survey_id is None:
            return
        survey, done = by_id[survey_id]
        if done:
            widgets.inform("You have already answered this survey — thank you.",
                           title="Already answered")
            return
        _answer_form(gui, survey, lambda: render(gui))

    widgets.button_bar(frame, [
        ("Answer…", lambda: answer(table.require_selection_int("answer a survey"))),
    ])
    table.populate(
        [s for s, _ in offered],
        lambda s: (s.title, s.kind, s.closes_on, by_id[s.survey_id][1]),
        identity=lambda s: s.survey_id,
        tag=lambda s: "muted" if by_id[s.survey_id][1] else None,
        noun="survey",
    )


def _answer_form(gui: Any, survey: Survey, reload: Callable[[], None]) -> None:
    keys = {f"q{i}": question for i, question in enumerate(survey.questions)}
    fields: list[dict[str, Any]] = [
        {"key": key, "label": question, "kind": "combo", "options": rules.SCALE,
         "required": True}
        for key, question in keys.items()
    ]
    fields.append({"key": "comment", "label": "Anything else you would like to tell us?",
                   "kind": "text"})

    def save(values: dict[str, Any]) -> object:
        answers = {question: values.get(key) for key, question in keys.items()}
        return survey_service.respond(
            gui.actor, survey.survey_id, answers, comment=values.get("comment"),
        )

    dialog = widgets.FormDialog(
        gui.root, survey.title, fields, save,
        intro="Every question needs an answer. You can respond once.",
        save_label="Submit",
    )
    if dialog.saved:
        widgets.inform("Thank you — your response has been recorded.", title="Submitted")
        reload()


# ═════════════════════════════════════════════════════════════════════
# Running and reading
# ═════════════════════════════════════════════════════════════════════

def _manage(gui: Any) -> None:
    frame = gui.clear()
    manager = gui.actor.can("survey.manage")
    widgets.heading(
        frame, "Surveys",
        subtitle="Results are anonymous and are withheld until at least "
                 f"{config.SURVEY_ANONYMITY_THRESHOLD} people have responded.",
    )
    filters = widgets.FilterBar(
        frame,
        (
            ("status", "Status", "combo", config.SURVEY_STATUSES),
            ("kind", "Kind", "combo", config.SURVEY_KINDS),
            ("audience", "Audience", "combo", config.SURVEY_AUDIENCES),
        ),
        lambda: reload(),
    )
    table = widgets.DataTable(frame, COLUMNS,
                              on_activate=lambda ident: _results(gui, int(ident)))
    surveys: dict[int, Survey] = {}

    def reload() -> None:
        ok, rows = widgets.guard(
            lambda: survey_service.list_surveys(gui.actor, **filters.values())
        )
        surveys.clear()
        surveys.update({s.survey_id: s for s in rows or []})
        table.populate(
            rows or [],
            lambda s: (s.title, s.kind, s.audience, s.status, s.opens_on, s.closes_on),
            identity=lambda s: s.survey_id,
            tag=lambda s: "muted" if s.status == "Closed" else None,
            noun="survey",
        )

    def selected(action: str) -> Survey | None:
        survey_id = table.require_selection_int(action)
        return surveys.get(survey_id) if survey_id is not None else None

    def results() -> None:
        survey = selected("see its results")
        if survey is not None:
            _results(gui, survey.survey_id)

    def change(action: Callable[[Any, int], object], verb: str) -> None:
        survey = selected(f"{verb} a survey")
        if survey is None:
            return
        ok, _ = widgets.guard(lambda: action(gui.actor, survey.survey_id))
        if ok:
            reload()

    def edit() -> None:
        survey = selected("edit a survey")
        if survey is not None:
            _survey_form(gui, survey, reload)

    buttons: list[tuple[str, Callable[[], None]]] = [("Results →", results)]
    if manager:
        buttons += [
            ("New survey…", lambda: _survey_form(gui, None, reload)),
            ("Edit…", edit),
            ("Open", lambda: change(survey_service.open_survey, "open")),
            ("Close", lambda: change(survey_service.close_survey, "close")),
        ]
    widgets.button_bar(frame, buttons)
    reload()


def _survey_form(gui: Any, survey: Survey | None, reload: Callable[[], None]) -> None:
    fixed = survey is not None and survey.status != "Draft"
    fields: list[dict[str, Any]] = [
        {"key": "title", "label": "Title", "required": True,
         "value": survey.title if survey else ""},
    ]
    if not fixed:
        fields += [
            {"key": "kind", "label": "Kind", "kind": "combo", "options": config.SURVEY_KINDS,
             "value": survey.kind if survey else config.SURVEY_KINDS[0], "required": True,
             "help": "Decides the questions. " + " ".join(
                 f"{k}: {', '.join(a)}." for k, a in config.SURVEY_KIND_AUDIENCES.items())},
            {"key": "audience", "label": "Audience", "kind": "combo",
             "options": config.SURVEY_AUDIENCES,
             "value": survey.audience if survey else config.SURVEY_AUDIENCES[0]},
        ]
    fields += [
        {"key": "opens_on", "label": "Opens on", "value": (survey.opens_on if survey else "")
         or "", "help": "YYYY-MM-DD. Blank opens it on the day you press Open."},
        {"key": "closes_on", "label": "Closes on",
         "value": (survey.closes_on if survey else "") or "", "help": "YYYY-MM-DD."},
    ]

    def save(values: dict[str, Any]) -> object:
        if survey is None:
            return survey_service.create_survey(gui.actor, values)
        return survey_service.update_survey(gui.actor, survey.survey_id, values)

    dialog = widgets.FormDialog(
        gui.root, "Edit survey" if survey else "New survey", fields, save,
        intro=None if survey else "A new survey starts as a Draft and is offered to "
                                  "nobody until you open it.",
    )
    if dialog.saved:
        reload()


def _results(gui: Any, survey_id: int) -> None:
    frame = gui.clear()
    ok, result = widgets.guard(lambda: survey_service.results(gui.actor, survey_id))
    if not ok:
        widgets.heading(frame, "Survey results")
        widgets.button_bar(frame, [("← All surveys", lambda: render(gui))])
        return
    survey = result.survey
    widgets.heading(frame, f"Results — {survey.title}",
                    subtitle=f"{survey.kind} survey of {survey.audience.lower()}s, "
                             f"{survey.status.lower()}.")
    widgets.button_bar(frame, [("← All surveys", lambda: render(gui))])
    widgets.kpi_row(frame, [
        ("Responses", result.response_count),
        ("Eligible", result.eligible_count),
        ("Response rate", widgets.percent(result.response_rate)),
    ])
    if result.withheld:
        widgets.empty_state(
            frame,
            f"Results are shown once at least {config.SURVEY_ANONYMITY_THRESHOLD} people "
            "have responded, so that no answer can be traced to one person.",
        )
        return

    body = widgets.scrollable(frame)
    box = widgets.section(body, "Questions")
    table = widgets.DataTable(box, QUESTION_COLUMNS, height=max(1, len(result.questions)))
    table.populate(
        result.questions,
        lambda q: (q.question, q.average, q.average_label, q.answered,
                   " · ".join(str(n) for n in q.distribution)),
        identity=lambda q: survey.questions.index(q.question),
        noun="question",
    )
    comments = widgets.section(body, "Comments")
    if not result.comments:
        widgets.empty_state(comments, "Nobody left a comment.")
        return
    for text in result.comments:
        widgets.field_grid(comments, [("", text)], columns=1)
