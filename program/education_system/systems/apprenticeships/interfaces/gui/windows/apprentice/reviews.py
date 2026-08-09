"""Progress Reviews — apprentice screen.

Your reviews, the targets set at them, and your signature.

A review is worth nothing as funding evidence until the provider, the
apprentice and the employer have all signed — so what the apprentice
needs from this screen is not a history but a short answer to "is
anything waiting on me?". That sits at the top; the record of each
meeting is behind it.
"""

from __future__ import annotations

import logging
from tkinter import ttk
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.services import review_service

logger = logging.getLogger(__name__)

TITLE = "Progress Reviews"
SUBTITLE = "Your reviews, the targets set at them, and your signature."

UNLINKED = (
    "Your sign-in is not linked to an apprentice record yet, so there are no reviews "
    "to show. Ask your training provider's administrator to link your account."
)

# Which line of the review this role signs.
SIGNATORY = "apprentice"

_REVIEW_COLUMNS = (
    ("scheduled", "Scheduled", 120),
    ("held", "Held", 120),
    ("status", "Status", 170),
    ("rating", "Progress", 100),
    ("conductor", "Conducted by", 180),
    ("missing", "Still to sign", 220),
)

_TARGET_COLUMNS = (
    ("due", "Due", 120),
    ("description", "Target", 480),
    ("ksbs", "KSBs", 140),
    ("status", "Status", 140),
    ("outcome", "Outcome", 260),
)

_STATUS_TAGS = {
    "Complete": "Green", "Awaiting Signatures": "Amber", "Missed": "Red",
}


def render(gui) -> None:
    """Draw the progress reviews screen into the content pane."""
    frame = gui.clear()
    widgets.heading(frame, TITLE, subtitle=SUBTITLE)

    if gui.actor.apprentice_id is None:
        widgets.empty_state(frame, UNLINKED)
        return

    ok, reviews = widgets.guard(
        lambda: review_service.list_reviews(gui.actor, with_children=True)
    )
    if not ok:
        return
    reviews = reviews or []

    waiting = [r for r in reviews if r.can_sign(SIGNATORY)]
    ok, targets = widgets.guard(
        lambda: review_service.list_targets(gui.actor, open_only=True)
    )
    targets = (targets or []) if ok else []
    overdue = [t for t in targets if t.is_overdue]

    widgets.kpi_row(frame, [
        ("Reviews", len(reviews)),
        ("Complete", sum(1 for r in reviews if r.is_complete)),
        ("Waiting on your signature", len(waiting)),
        ("Open targets", len(targets)),
        ("Targets overdue", len(overdue)),
    ])

    if waiting:
        ttk.Label(
            frame,
            text=f"{len(waiting)} review(s) are waiting on your signature. A review "
                 "does not count as evidence until all three of you have signed.",
            foreground=config.ERROR_FG, wraplength=900, justify="left",
        ).pack(anchor="w", pady=(0, 8))

    table = widgets.DataTable(
        frame, _REVIEW_COLUMNS, height=10,
        on_activate=lambda ident: _detail(gui, int(ident)),
    )
    table.populate(
        reviews,
        lambda r: (r.scheduled_date, r.held_date, r.status, r.progress_rating,
                   r.conductor_name, ", ".join(r.missing_signatures)),
        identity=lambda r: r.review_id,
        tag=lambda r: "Red" if r.is_overdue else _STATUS_TAGS.get(r.status),
        noun="review",
    )
    if not reviews:
        widgets.empty_state(
            frame,
            "You have no reviews yet. Your tutor books the first one once you are on "
            f"programme; after that they fall every {config.REVIEW_INTERVAL_WEEKS} weeks.",
        )

    def open_detail() -> None:
        review_id = table.require_selection_int("open a review")
        if review_id is not None:
            _detail(gui, review_id)

    def sign() -> None:
        review_id = table.require_selection_int("sign a review")
        if review_id is not None:
            _sign(gui, review_id, on_done=gui.refresh)

    buttons: list[tuple[str, Any]] = [("Open", open_detail)]
    if gui.actor.can("review.sign"):
        buttons.append(("Sign", sign))
    widgets.button_bar(frame, buttons)

    box = widgets.section(frame, "My open targets")
    if not targets:
        widgets.empty_state(box, "No targets are open.")
        return
    target_table = widgets.DataTable(box, _TARGET_COLUMNS, height=min(8, len(targets)))
    target_table.populate(
        targets,
        lambda t: (t.due_date, t.description, t.ksb_codes, t.status, t.outcome_note),
        identity=lambda t: t.target_id,
        tag=lambda t: "Red" if t.is_overdue else None,
        noun="target",
    )


# ═════════════════════════════════════════════════════════════════════
# One review
# ═════════════════════════════════════════════════════════════════════

def _detail(gui, review_id: int) -> None:
    """One meeting in full: what was said, who signed, what was agreed."""
    frame = gui.clear()
    ok, review = widgets.guard(lambda: review_service.get_review(gui.actor, review_id))
    back = ("← Back to reviews", lambda: render(gui))
    if not ok or review is None:
        widgets.button_bar(frame, [back])
        return

    widgets.heading(
        frame, f"Review of {review.held_date or review.scheduled_date}",
        subtitle=f"{review.status} · conducted by "
                 f"{review.conductor_name or 'your tutor'}",
    )
    widgets.field_grid(frame, [
        ("Scheduled", review.scheduled_date),
        ("Held", review.held_date),
        ("Status", review.status),
        ("Progress rating", review.progress_rating),
        ("Off-the-job on track", review.otj_on_track),
        ("Next review", review.next_review_date),
    ], columns=3)

    for label, text in (
        ("Summary", review.summary),
        ("Your comments", review.apprentice_comments),
        ("Your employer's comments", review.employer_comments),
    ):
        box = widgets.section(frame, label)
        ttk.Label(
            box, text=text or widgets.EMPTY, wraplength=900, justify="left",
            foreground=config.MUTED_FG if not text else "",
        ).pack(anchor="w")

    box = widgets.section(frame, "Signatures")
    signatures = widgets.DataTable(box, (
        ("party", "Party", 140),
        ("by", "Signed by", 220),
        ("when", "When", 180),
    ), height=3)
    signatures.populate(
        review.signatures,
        lambda s: (s.signatory, s.signed_by, s.signed_at),
        identity=lambda s: s.signature_id,
        tag=lambda _s: "Green",
        noun="signature",
    )
    if review.missing_signatures:
        ttk.Label(
            box, text=f"Still to sign: {', '.join(review.missing_signatures)}",
            foreground=config.MUTED_FG,
        ).pack(anchor="w", pady=(4, 0))

    box = widgets.section(frame, "Targets agreed")
    if review.targets:
        targets = widgets.DataTable(box, _TARGET_COLUMNS, height=min(6, len(review.targets)))
        targets.populate(
            review.targets,
            lambda t: (t.due_date, t.description, t.ksb_codes, t.status, t.outcome_note),
            identity=lambda t: t.target_id,
            tag=lambda t: "Red" if t.is_overdue else ("Green" if t.status == "Met" else None),
            noun="target",
        )
    else:
        widgets.empty_state(box, "No targets were set at this review.")

    buttons: list[tuple[str, Any]] = []
    if gui.actor.can("review.sign") and review.can_sign(SIGNATORY):
        buttons.append(("Sign", lambda: _sign(gui, review_id, on_done=lambda: _detail(
            gui, review_id
        ))))
    buttons.append(back)
    widgets.button_bar(frame, buttons)


def _sign(gui, review_id: int, *, on_done: Any) -> None:
    """Add the apprentice's signature, once they have read the write-up."""
    ok, review = widgets.guard(lambda: review_service.get_review(gui.actor, review_id))
    if not ok or review is None:
        return
    if not review.can_sign(SIGNATORY):
        if SIGNATORY in review.signed_by:
            widgets.warn("You have already signed this review.", title="Already signed")
        else:
            widgets.warn(
                "This review has not been held yet, so there is nothing to sign.",
                title="Not held",
            )
        return
    if not widgets.confirm(
        f"Sign the review of {review.held_date}?\n\n"
        "Signing says you were there and the write-up is a fair record of it. It is "
        "one of the three signatures the review needs to count.",
        title="Sign review",
    ):
        return

    ok, signed = widgets.guard(lambda: review_service.sign_review(gui.actor, review_id))
    if not ok or signed is None:
        return
    if signed.is_complete:
        widgets.inform("Signed — all three parties have now signed and it is complete.")
    else:
        widgets.inform(f"Signed. Still waiting on: {', '.join(signed.missing_signatures)}.")
    on_done()
