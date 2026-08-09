"""Progress reviews the employer is a party to, and the signature they owe."""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.interfaces.gui.windows.employer.dashboard import (
    UNLINKED_MESSAGE,
)
from education_system.systems.apprenticeships.services import review_service

logger = logging.getLogger(__name__)

SUBTITLE = (
    "A progress review is tripartite: provider, apprentice and employer. It is not "
    "evidence of anything until all three have signed, so the amber rows are the ones "
    "waiting on you."
)

_COLUMNS = (
    ("apprentice", "Apprentice", 190),
    ("scheduled", "Scheduled", 110),
    ("held", "Held", 110),
    ("status", "Status", 150),
    ("rating", "Rating", 90),
    ("signatures", "Signed by", 240),
)

_TARGET_COLUMNS = (
    ("description", "Target", 420),
    ("due", "Due", 110),
    ("ksbs", "KSBs", 140),
    ("status", "Status", 130),
)


def render(gui) -> None:
    """The employer's reviews, with a detail pane and a Sign button."""
    frame = gui.clear()
    widgets.heading(frame, "Progress Reviews", subtitle=SUBTITLE)
    if gui.actor.employer_id is None:
        widgets.empty_state(frame, UNLINKED_MESSAGE)
        return

    ok, initial = widgets.guard(
        lambda: review_service.list_reviews(gui.actor, with_children=True)
    )
    if not ok:
        return
    if not initial:
        widgets.empty_state(
            frame,
            "No reviews have been booked for your apprentices yet. The provider "
            "schedules them roughly every "
            f"{config.REVIEW_INTERVAL_WEEKS} weeks.",
        )
        return

    def fill(rows: Sequence[Any]) -> None:
        table.populate(
            rows,
            lambda r: (
                r.apprentice_name, r.scheduled_date, r.held_date, r.status,
                r.progress_rating, ", ".join(sorted(r.signed_by)),
            ),
            identity=lambda r: r.review_id,
            tag=_tag_for,
            noun="review",
        )

    def reload() -> None:
        found, rows = widgets.guard(
            lambda: review_service.list_reviews(
                gui.actor, with_children=True, **filters.values()
            )
        )
        if found:
            fill(rows)

    def show_detail(chosen: str) -> None:
        _detail(gui, detail, int(chosen))

    filters = widgets.FilterBar(
        frame, [("status", "Status", "combo", config.REVIEW_STATUSES)], reload
    )
    table = widgets.DataTable(frame, _COLUMNS, on_activate=show_detail)

    buttons: list[tuple[str, Callable[[], None]]] = [
        ("View Detail", lambda: _open_selected(table, show_detail)),
    ]
    if gui.actor.can("review.sign"):
        buttons.append(("Sign", lambda: _sign(gui, table)))
    widgets.button_bar(frame, buttons)

    detail = widgets.section(frame, "Selected review")
    widgets.empty_state(detail, "Pick a review above to read the write-up and sign it.")
    fill(initial)


def _tag_for(review: Any) -> str | None:
    """Amber for anything waiting on a signature, otherwise the RAG rating."""
    if review.status == "Awaiting Signatures":
        return "Amber"
    return review.progress_rating


def _open_selected(table: widgets.DataTable, show_detail: Callable[[str], None]) -> None:
    review_id = table.require_selection_int("read a review")
    if review_id is not None:
        show_detail(str(review_id))


def _detail(gui, detail, review_id: int) -> None:
    for child in detail.winfo_children():
        child.destroy()
    ok, review = widgets.guard(lambda: review_service.get_review(gui.actor, review_id))
    if not ok:
        return

    widgets.field_grid(detail, [
        ("Apprentice", review.apprentice_name),
        ("Status", review.status),
        ("Scheduled", review.scheduled_date),
        ("Held", review.held_date),
        ("Conducted by", review.conductor_name),
        ("Progress rating", review.progress_rating),
        ("Off-the-job on track", review.otj_on_track),
        ("Next review", review.next_review_date),
        ("Summary", review.summary),
        ("Apprentice's comments", review.apprentice_comments),
        ("Your comments", review.employer_comments),
        ("Still to sign", ", ".join(review.missing_signatures) or "Nobody — complete"),
    ], columns=2)

    signatures = widgets.section(detail, "Signatures")
    if review.signatures:
        widgets.field_grid(
            signatures,
            [(s.signatory.title(), f"{s.signed_by} · {s.signed_at}")
             for s in review.signatures],
            columns=3,
        )
    else:
        widgets.empty_state(signatures, "Nobody has signed this review yet.")

    targets = widgets.section(detail, "Targets agreed")
    if review.targets:
        table = widgets.DataTable(targets, _TARGET_COLUMNS, height=min(6, len(review.targets)))
        table.populate(
            review.targets,
            lambda t: (t.description, t.due_date, t.ksb_codes, t.status),
            identity=lambda t: t.target_id,
            tag=lambda t: "Red" if t.is_overdue else None,
            noun="target",
        )
    else:
        widgets.empty_state(targets, "No targets were set at this review.")


def _sign(gui, table: widgets.DataTable) -> None:
    """Add the employer's signature.

    No signatory is passed: the service derives it from the role and
    refuses any other line, so a form cannot sign on the apprentice's
    behalf.
    """
    review_id = table.require_selection_int("sign a review")
    if review_id is None:
        return
    if not widgets.confirm(
        "Sign this review as the employer? Your signature says you were part of the "
        "meeting and agree with the record of it.",
        title="Sign review",
    ):
        return
    ok, _ = widgets.guard(lambda: review_service.sign_review(gui.actor, review_id))
    if ok:
        widgets.inform("Signed.")
        gui.refresh()
