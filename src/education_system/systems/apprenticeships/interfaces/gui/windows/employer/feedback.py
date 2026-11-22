"""Employer satisfaction feedback: what they have said, and saying more."""

from __future__ import annotations

import logging
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.interfaces.gui.windows.employer.dashboard import (
    UNLINKED_MESSAGE,
)
from education_system.systems.apprenticeships.application.apprentices import apprentice_service
from education_system.systems.apprenticeships.application.learning import review_service

logger = logging.getLogger(__name__)

SUBTITLE = (
    "How the apprenticeship is working for you. Feedback can be about one apprentice "
    "or about the provider generally, and it feeds the satisfaction figure their "
    "funding body sees — so it is worth saying when something is not working."
)

_COLUMNS = (
    ("date", "Submitted", 160),
    ("apprentice", "Apprentice", 200),
    ("satisfaction", "Satisfaction", 160),
    ("comments", "Comments", 460),
)


def render(gui) -> None:
    """Past feedback, the running average, and a form for adding more."""
    frame = gui.clear()
    widgets.heading(frame, "Give Feedback", subtitle=SUBTITLE)
    if gui.actor.employer_id is None:
        widgets.empty_state(frame, UNLINKED_MESSAGE)
        return

    ok, entries = widgets.guard(
        lambda: review_service.list_feedback(gui.actor, employer_id=gui.actor.employer_id)
    )
    if not ok:
        return
    _, average = widgets.guard(lambda: review_service.satisfaction_average(gui.actor))

    names = _names(gui)
    widgets.kpi_row(frame, [
        ("Ratings given", len(entries)),
        ("Average satisfaction", f"{average:.1f} / 5" if average else config.EMPTY_CELL),
        ("Positive", sum(1 for f in entries if f.is_positive)),
    ], per_row=3)

    if entries:
        table = widgets.DataTable(frame, _COLUMNS)
        table.populate(
            entries,
            lambda f: (
                f.submitted_at,
                names.get(f.apprentice_id or -1, "General feedback"),
                f.satisfaction, f.comments,
            ),
            identity=lambda f: f.feedback_id,
            tag=lambda f: "Green" if f.is_positive else ("Red" if f.score <= 2 else None),
            noun="rating",
        )
    else:
        widgets.empty_state(
            frame,
            "You have not left any feedback yet. Nobody chases this, so it only "
            "reaches the provider if you write it.",
        )

    if gui.actor.can("review.feedback"):
        widgets.button_bar(frame, [("Give Feedback", lambda: _give(gui, names))])


def _give(gui, names: dict[int, str]) -> None:
    """Collect one satisfaction rating.

    The employer is never asked which organisation the feedback is for:
    the service stamps their own, so it cannot be filed against somebody
    else's name.
    """
    labels = {f"{name} (#{apprentice_id})": apprentice_id for apprentice_id, name in names.items()}

    def on_save(values: dict[str, Any]) -> Any:
        payload: dict[str, Any] = {
            "satisfaction": values.get("satisfaction"),
            "comments": values.get("comments"),
        }
        chosen = values.get("apprentice")
        if chosen:
            payload["apprentice_id"] = labels[chosen]
        return review_service.submit_feedback(gui.actor, payload)

    dialog = widgets.FormDialog(
        gui.content_frame,
        "Give feedback",
        [
            {"key": "apprentice", "label": "Apprentice", "kind": "combo",
             "options": ["", *sorted(labels)],
             "help": "Leave blank if this is about the provider rather than one person."},
            {"key": "satisfaction", "label": "Satisfaction", "kind": "combo",
             "options": config.SATISFACTION_SCALE, "required": True},
            {"key": "comments", "label": "Comments", "kind": "text",
             "help": "What is working, and what is not."},
        ],
        on_save,
        intro="This is recorded against your organisation and shared with the provider.",
        save_label="Submit",
    )
    if dialog.saved:
        gui.refresh()


def _names(gui) -> dict[int, str]:
    """Apprentice ids to names — feedback rows carry the id only."""
    try:
        return {
            s.apprentice.apprentice_id: s.full_name
            for s in apprentice_service.list_apprentices(gui.actor)
        }
    except Exception:
        logger.debug("Could not build the apprentice name lookup", exc_info=True)
        return {}
