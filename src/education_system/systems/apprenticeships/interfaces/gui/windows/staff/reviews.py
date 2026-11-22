"""Progress Reviews — staff screen.

Tripartite reviews: schedule, record the outcome, sign and set targets.

Opens on the queue rather than the full list, because the tutor's
question is "what is late and what is unsigned?" — an unsigned review is
not evidence of anything, and a gap in the cycle is a funding-audit
finding. The full list is a tab behind it.
"""

from __future__ import annotations

import logging
from datetime import date
from tkinter import ttk
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.application.apprentices import apprentice_service
from education_system.systems.apprenticeships.application.learning import review_service

logger = logging.getLogger(__name__)

TITLE = "Progress Reviews"
SUBTITLE = "Tripartite reviews: schedule, record the outcome, sign and set targets."

# Which line of the review provider staff sign.
SIGNATORY = "provider"

_COLUMNS = (
    ("apprentice", "Apprentice", 190),
    ("scheduled", "Scheduled", 110),
    ("held", "Held", 110),
    ("status", "Status", 160),
    ("rating", "Progress", 90),
    ("missing", "Still to sign", 210),
)

_TARGET_COLUMNS = (
    ("due", "Due", 110),
    ("description", "Target", 400),
    ("owner", "Owner", 100),
    ("priority", "Priority", 80),
    ("ksbs", "KSBs", 110),
    ("status", "Status", 130),
    ("outcome", "Outcome", 240),
)

_STATUS_TAGS = {
    "Complete": "Green", "Awaiting Signatures": "Amber", "Missed": "Red",
}


def render(gui) -> None:
    """Draw the progress reviews screen into the content pane."""
    frame = gui.clear()
    widgets.heading(frame, TITLE, subtitle=SUBTITLE)

    if not gui.actor.can("review.view"):
        widgets.empty_state(frame, "Your role may not see progress reviews.")
        return

    ok, queue = widgets.guard(lambda: review_service.review_queue(gui.actor))
    if not ok or queue is None:
        return

    widgets.kpi_row(frame, [
        ("Overdue", len(queue["overdue"])),
        ("Awaiting signatures", len(queue["awaiting_signature"])),
        ("Coming up", len(queue["upcoming"])),
    ], per_row=3)

    notebook = ttk.Notebook(frame)
    notebook.pack(fill="both", expand=True)

    for label, rows, blurb in (
        (f"Overdue ({len(queue['overdue'])})", queue["overdue"],
         "The meeting was booked and has not happened. Hold it, or record it as "
         "missed with a reason and book a replacement."),
        (f"Awaiting signatures ({len(queue['awaiting_signature'])})",
         queue["awaiting_signature"],
         "Held and written up, but not yet evidence. All three parties have to sign."),
        (f"Coming up ({len(queue['upcoming'])})", queue["upcoming"],
         "Booked and still ahead of their date."),
    ):
        tab = ttk.Frame(notebook, padding=8)
        notebook.add(tab, text=label)
        _list(gui, tab, rows, blurb)

    everything = ttk.Frame(notebook, padding=8)
    notebook.add(everything, text="All reviews")
    _all(gui, everything)


def _list(gui, parent: Any, rows: list, blurb: str) -> None:
    ttk.Label(
        parent, text=blurb, foreground=config.MUTED_FG, wraplength=900, justify="left",
    ).pack(anchor="w", pady=(0, 8))
    if not rows:
        widgets.empty_state(parent, "Nothing here.")
        _actions(gui, parent, None)
        return

    table = widgets.DataTable(
        parent, _COLUMNS, height=min(12, len(rows)),
        on_activate=lambda ident: _detail(gui, int(ident)),
    )
    table.populate(
        rows,
        lambda r: (r.apprentice_name, r.scheduled_date, r.held_date, r.status,
                   r.progress_rating, ", ".join(r.missing_signatures)),
        identity=lambda r: r.review_id,
        tag=lambda r: "Red" if r.is_overdue else _STATUS_TAGS.get(r.status),
        noun="review",
    )
    _actions(gui, parent, table)


def _all(gui, parent: Any) -> None:
    filters = widgets.FilterBar(
        parent,
        (
            ("status", "Status", "combo", config.REVIEW_STATUSES),
            ("overdue_only", "Overdue only", "check"),
        ),
        lambda: reload(),
    )
    table = widgets.DataTable(
        parent, _COLUMNS,
        on_activate=lambda ident: _detail(gui, int(ident)),
    )

    def reload() -> None:
        _, rows = widgets.guard(lambda: review_service.list_reviews(
            gui.actor, with_children=True, **filters.values()
        ))
        rows = rows or []
        table.populate(
            rows,
            lambda r: (r.apprentice_name, r.scheduled_date, r.held_date, r.status,
                       r.progress_rating, ", ".join(r.missing_signatures)),
            identity=lambda r: r.review_id,
            tag=lambda r: "Red" if r.is_overdue else _STATUS_TAGS.get(r.status),
            noun="review",
        )

    _actions(gui, parent, table)
    reload()


def _actions(gui, parent: Any, table: widgets.DataTable | None) -> None:
    """The buttons under a review list."""

    def chosen(action: str) -> int | None:
        if table is None:
            widgets.warn("There are no reviews in this list.", title="Nothing to act on")
            return None
        return table.require_selection_int(action)

    buttons: list[tuple[str, Any]] = [
        ("Open", lambda: _open(gui, chosen("open a review"))),
    ]
    if gui.actor.can("review.conduct"):
        buttons += [
            ("Schedule…", lambda: _schedule(gui)),
            ("Start", lambda: _start(gui, chosen("start a review"))),
            ("Record Outcome…", lambda: _record(gui, chosen("record an outcome"))),
            ("Mark Missed…", lambda: _missed(gui, chosen("mark a review missed"))),
        ]
    if gui.actor.can("review.sign"):
        buttons.append(("Sign as Provider", lambda: _sign(gui, chosen("sign a review"))))
    widgets.button_bar(parent, buttons)


def _open(gui, review_id: int | None) -> None:
    if review_id is not None:
        _detail(gui, review_id)


# ═════════════════════════════════════════════════════════════════════
# One review
# ═════════════════════════════════════════════════════════════════════

def _detail(gui, review_id: int) -> None:
    """One review, its signatures and the targets agreed at it."""
    frame = gui.clear()
    ok, review = widgets.guard(lambda: review_service.get_review(gui.actor, review_id))
    back = ("← Back to reviews", lambda: render(gui))
    if not ok or review is None:
        widgets.button_bar(frame, [back])
        return

    widgets.heading(
        frame, f"{review.apprentice_name} — {review.held_date or review.scheduled_date}",
        subtitle=f"{review.status} · conducted by {review.conductor_name or 'unassigned'}",
    )
    widgets.field_grid(frame, [
        ("Scheduled", review.scheduled_date),
        ("Held", review.held_date),
        ("Status", review.status),
        ("Progress rating", review.progress_rating),
        ("Off-the-job on track", review.otj_on_track),
        ("Next review", review.next_review_date),
        ("Signed by", ", ".join(sorted(review.signed_by))),
        ("Still to sign", ", ".join(review.missing_signatures)),
    ], columns=4)

    for label, text in (
        ("Summary", review.summary),
        ("Apprentice's comments", review.apprentice_comments),
        ("Employer's comments", review.employer_comments),
    ):
        box = widgets.section(frame, label)
        ttk.Label(
            box, text=text or widgets.EMPTY, wraplength=900, justify="left",
        ).pack(anchor="w")

    box = widgets.section(frame, "Targets")
    targets = widgets.DataTable(
        box, _TARGET_COLUMNS, height=max(3, min(8, len(review.targets)))
    )
    targets.populate(
        review.targets,
        lambda t: (t.due_date, t.description, t.owner, t.priority, t.ksb_codes, t.status,
                   t.outcome_note),
        identity=lambda t: t.target_id,
        tag=lambda t: t.rag(date.today()),
        noun="target",
    )

    buttons: list[tuple[str, Any]] = []
    if gui.actor.can("review.conduct"):
        buttons += [
            ("Add Target…", lambda: _add_target(gui, review_id)),
            ("Bring Forward Open Actions", lambda: _carry_forward(gui, review_id)),
            ("Close Target…", lambda: _close_target(gui, review_id, targets)),
            ("Delete Target", lambda: _delete_target(gui, review_id, targets)),
            ("Record Outcome…", lambda: _record(gui, review_id)),
        ]
    if gui.actor.can("review.sign") and review.can_sign(SIGNATORY):
        buttons.append(("Sign as Provider", lambda: _sign(gui, review_id)))
    if gui.actor.is_admin and review.signed_by and not review.is_complete:
        buttons.append(("Remove a Signature…", lambda: _unsign(gui, review_id, review)))
    buttons.append(back)
    widgets.button_bar(frame, buttons)


# ═════════════════════════════════════════════════════════════════════
# Conducting
# ═════════════════════════════════════════════════════════════════════

def _schedule(gui) -> None:
    ok, summaries = widgets.guard(
        lambda: apprentice_service.list_apprentices(gui.actor, active_only=True)
    )
    if not ok or not summaries:
        widgets.warn("There is nobody on programme to book a review for.")
        return

    labels = {s.full_name: s.apprentice.apprentice_id for s in summaries}
    fields = [
        {"key": "apprentice", "label": "Apprentice", "kind": "combo", "required": True,
         "options": list(labels)},
        {"key": "scheduled_date", "label": "Date", "required": True,
         "value": date.today().isoformat(), "help": "YYYY-MM-DD"},
    ]

    def save(values: dict[str, Any]) -> Any:
        return review_service.schedule_review(
            gui.actor, labels[values["apprentice"]],
            scheduled_date=values["scheduled_date"],
        )

    dialog = widgets.FormDialog(
        gui.root, "Schedule a review", fields, save,
        intro=f"Reviews fall every {config.REVIEW_INTERVAL_WEEKS} weeks, counted from "
              "the last meeting that actually happened — so one that slipped moves "
              "the whole cycle with it.",
    )
    if dialog.saved:
        gui.refresh()


def _start(gui, review_id: int | None) -> None:
    if review_id is None:
        return
    ok, _ = widgets.guard(lambda: review_service.start_review(gui.actor, review_id))
    if ok:
        gui.refresh()


def _record(gui, review_id: int | None) -> None:
    """Write the meeting up and send it out for signature."""
    if review_id is None:
        return
    ok, review = widgets.guard(lambda: review_service.get_review(gui.actor, review_id))
    if not ok or review is None:
        return

    fields = [
        {"key": "held_date", "label": "Date held", "required": True,
         "value": review.held_date or date.today().isoformat(), "help": "YYYY-MM-DD"},
        {"key": "progress_rating", "label": "Progress", "kind": "combo",
         "options": config.RAG_RATINGS, "value": review.progress_rating or "Green"},
        {"key": "otj_on_track", "label": "Off-the-job on track", "kind": "combo",
         "options": ("Yes", "No", "Not judged"),
         "value": _tristate_label(review.otj_on_track),
         "help": "'Not judged' is stored as such — it is not the same as 'behind'."},
        {"key": "summary", "label": "Summary", "kind": "text",
         "value": review.summary or ""},
        {"key": "apprentice_comments", "label": "Apprentice's comments", "kind": "text",
         "value": review.apprentice_comments or ""},
        {"key": "employer_comments", "label": "Employer's comments", "kind": "text",
         "value": review.employer_comments or ""},
        {"key": "next_review_date", "label": "Next review",
         "value": review.next_review_date or "",
         "help": "Blank takes the standard interval from the date held."},
    ]

    def save(values: dict[str, Any]) -> Any:
        payload = dict(values)
        payload["otj_on_track"] = {
            "Yes": "yes", "No": "no", "Not judged": "",
        }[values["otj_on_track"]]
        return review_service.record_review(gui.actor, review_id, payload)

    dialog = widgets.FormDialog(
        gui.root, f"Write up — {review.apprentice_name}", fields, save,
        intro="Recording an outcome sends the review out for signature. It is not "
              "evidence until the provider, the apprentice and the employer have all "
              "signed.",
    )
    if dialog.saved:
        _detail(gui, review_id)


def _missed(gui, review_id: int | None) -> None:
    if review_id is None:
        return
    reason = widgets.ask_reason(
        "Why did the meeting not happen?", title="Mark review missed"
    )
    if not reason:
        return
    ok, _ = widgets.guard(
        lambda: review_service.mark_missed(gui.actor, review_id, reason=reason)
    )
    if ok:
        widgets.inform(
            "Recorded as missed. Book a replacement — a gap in the review cycle is a "
            "funding-audit finding."
        )
        gui.refresh()


# ═════════════════════════════════════════════════════════════════════
# Signatures
# ═════════════════════════════════════════════════════════════════════

def _sign(gui, review_id: int | None) -> None:
    if review_id is None:
        return
    ok, review = widgets.guard(lambda: review_service.get_review(gui.actor, review_id))
    if not ok or review is None:
        return
    if not review.can_sign(SIGNATORY):
        if SIGNATORY in review.signed_by:
            widgets.warn(
                "The provider has already signed this review.", title="Already signed"
            )
        else:
            widgets.warn(
                "This review has not been held yet, so there is nothing to sign.",
                title="Not held",
            )
        return
    if not widgets.confirm(
        f"Sign {review.apprentice_name}'s review of {review.held_date} as the provider?",
        title="Sign review",
    ):
        return

    ok, signed = widgets.guard(lambda: review_service.sign_review(gui.actor, review_id))
    if not ok or signed is None:
        return
    if signed.is_complete:
        widgets.inform("Signed — all three parties have signed and the review is complete.")
    else:
        widgets.inform(f"Signed. Still waiting on: {', '.join(signed.missing_signatures)}.")
    gui.refresh()


def _unsign(gui, review_id: int, review: Any) -> None:
    """Remove a signature added in error. Administrators only."""
    fields = [
        {"key": "signatory", "label": "Signature", "kind": "combo", "required": True,
         "options": sorted(review.signed_by),
         "help": "For one added in error. A complete review stands as evidence and "
                 "cannot be unpicked — hold another one instead."},
    ]

    def save(values: dict[str, Any]) -> Any:
        return review_service.unsign_review(gui.actor, review_id, values["signatory"])

    if widgets.FormDialog(gui.root, "Remove a signature", fields, save).saved:
        _detail(gui, review_id)


# ═════════════════════════════════════════════════════════════════════
# Targets
# ═════════════════════════════════════════════════════════════════════

def _add_target(gui, review_id: int) -> None:
    fields = [
        {"key": "description", "label": "Target", "kind": "text", "required": True,
         "help": "What they will do before the next review, specifically enough to "
                 "judge it then."},
        {"key": "due_date", "label": "Due", "help": "YYYY-MM-DD"},
        {"key": "ksb_codes", "label": "KSBs it works towards",
         "help": "Comma-separated, e.g. K3, S1."},
        {"key": "owner", "label": "Owner", "kind": "combo", "options": config.ACTION_OWNERS,
         "value": config.ACTION_DEFAULT_OWNER,
         "help": "Who has to do it. The apprentice and employer can update their own."},
        {"key": "priority", "label": "Priority", "kind": "combo",
         "options": config.ACTION_PRIORITIES, "value": config.ACTION_DEFAULT_PRIORITY},
    ]

    def save(values: dict[str, Any]) -> Any:
        return review_service.add_target(gui.actor, review_id, values)

    if widgets.FormDialog(gui.root, "Agree a target", fields, save).saved:
        _detail(gui, review_id)


def _carry_forward(gui, review_id: int) -> None:
    """Pull every action still open on earlier reviews onto this one.

    Starting a review does this on its own; the button is for bringing
    them across before the meeting opens.
    """
    ok, carried = widgets.guard(lambda: review_service.carry_forward(gui.actor, review_id))
    if not ok:
        return
    if carried:
        widgets.inform(f"{len(carried)} open action(s) brought forward onto this review.")
    else:
        widgets.inform("Nothing to bring forward: no earlier action is still open.",
                       title="Nothing to carry")
    _detail(gui, review_id)


def _close_target(gui, review_id: int, table: widgets.DataTable) -> None:
    target_id = table.require_selection_int("close a target")
    if target_id is None:
        return
    outcomes = [s for s in config.TARGET_STATUSES if s != "Open"]
    fields = [
        {"key": "status", "label": "Outcome", "kind": "combo", "required": True,
         "options": outcomes, "value": "Met"},
        {"key": "note", "label": "Note", "kind": "text",
         "help": "Carried Forward moves the action onto the apprentice's next review."},
    ]

    def save(values: dict[str, Any]) -> Any:
        return review_service.close_target(
            gui.actor, target_id, status=values["status"], note=values["note"]
        )

    if widgets.FormDialog(gui.root, "Close a target", fields, save).saved:
        _detail(gui, review_id)


def _delete_target(gui, review_id: int, table: widgets.DataTable) -> None:
    target_id = table.require_selection_int("delete a target")
    if target_id is None:
        return
    if not widgets.confirm(
        "Delete this target?\n\nFor one added in error — to record how a target "
        "turned out, close it with an outcome instead.",
        title="Delete target",
    ):
        return
    ok, _ = widgets.guard(lambda: review_service.delete_target(gui.actor, target_id))
    if ok:
        _detail(gui, review_id)


def _tristate_label(value: bool | None) -> str:
    if value is None:
        return "Not judged"
    return "Yes" if value else "No"
