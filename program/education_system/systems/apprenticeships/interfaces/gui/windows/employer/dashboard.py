"""The employer's landing screen: what is waiting on them."""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from typing import Any

from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.services import reporting_service

logger = logging.getLogger(__name__)

UNLINKED_MESSAGE = (
    "This login is not linked to an employer record, so there is nothing to show. "
    "Ask the training provider's administrator to link your account to your "
    "organisation — until they do, every employer screen will be empty."
)


def render(gui) -> None:
    """The employer's apprentices and everything awaiting their signature."""
    frame = gui.clear()
    ok, data = widgets.guard(lambda: reporting_service.employer_dashboard(gui.actor))
    if not ok:
        return

    if data.get("unlinked"):
        widgets.heading(frame, "My Apprentices")
        widgets.empty_state(frame, UNLINKED_MESSAGE)
        return

    widgets.heading(
        frame,
        data.get("title") or "My Apprentices",
        subtitle="Your apprentices, the hours and reviews waiting on you, and where "
                 "the funding for this training stands.",
    )
    body = widgets.scrollable(frame)
    widgets.kpi_row(body, data.get("kpis") or ())

    # Off-the-job entries carry an apprentice id and no name, so the
    # dashboard's own cohort doubles as the lookup rather than costing a
    # second query per row.
    names = {s.apprentice.apprentice_id: s.full_name for s in data.get("apprentices") or []}

    _behind_on_otj(gui, body, data)
    _hours_awaiting_approval(gui, body, data, names)
    _reviews_to_sign(gui, body, data)
    _reviews_upcoming(body, data)
    _workplaces(body, data)
    _funding(body, data)


# ── Sections ────────────────────────────────────────────────────────

def _behind_on_otj(gui, parent, data: dict[str, Any]) -> None:
    box = widgets.section(parent, "Apprentices behind on off-the-job training")
    rows = data.get("behind_on_otj") or []
    _table(
        box,
        [("name", "Apprentice", 220), ("programme", "Programme", 240),
         ("logged", "Hours approved", 110, "e"), ("target", "Target", 90, "e"),
         ("otj", "Off-the-job", 100, "e"), ("elapsed", "Time elapsed", 100, "e")],
        rows,
        lambda s: (
            s.full_name, s.programme_title,
            f"{s.otj_hours_logged:,.0f}", f"{s.otj_hours_target:,.0f}",
            widgets.percent(s.otj_percent), widgets.percent(s.progress_percent),
        ),
        lambda s: s.apprentice.apprentice_id,
        "Nobody is behind on their off-the-job hours. Approving hours promptly is "
        "what keeps it that way.",
        tag=lambda _s: "Red",
        noun="apprentice",
    )
    widgets.button_bar(box, [
        ("Open →", lambda: gui.show("employer.apprentices", "My Apprentices")),
    ])


def _hours_awaiting_approval(gui, parent, data: dict[str, Any], names: dict[int, str]) -> None:
    box = widgets.section(parent, "Off-the-job hours awaiting your approval")
    rows = data.get("otj_queue") or []
    _table(
        box,
        [("apprentice", "Apprentice", 200), ("date", "Date", 110),
         ("hours", "Hours", 80, "e"), ("type", "Activity", 200),
         ("description", "Description", 320)],
        rows,
        lambda e: (
            names.get(e.apprentice_id, f"#{e.apprentice_id}"),
            e.activity_date, e.hours, e.activity_type, e.description,
        ),
        lambda e: e.entry_id,
        "No hours are waiting on you.",
        noun="entry",
    )
    widgets.button_bar(box, [
        ("Open →", lambda: gui.show("employer.training", "Off-the-Job Hours")),
    ])


def _reviews_to_sign(gui, parent, data: dict[str, Any]) -> None:
    box = widgets.section(parent, "Progress reviews waiting for your signature")
    rows = data.get("reviews_to_sign") or []
    _table(
        box,
        [("apprentice", "Apprentice", 200), ("held", "Held", 110),
         ("rating", "Rating", 90), ("missing", "Still to sign", 240)],
        rows,
        lambda r: (
            r.apprentice_name, r.held_date, r.progress_rating,
            ", ".join(r.missing_signatures),
        ),
        lambda r: r.review_id,
        "No reviews are waiting on your signature.",
        tag=lambda r: r.progress_rating,
        noun="review",
    )
    widgets.button_bar(box, [
        ("Open →", lambda: gui.show("employer.reviews", "Progress Reviews")),
    ])


def _reviews_upcoming(parent, data: dict[str, Any]) -> None:
    box = widgets.section(parent, "Reviews in the next fortnight")
    rows = data.get("reviews_upcoming") or []
    _table(
        box,
        [("apprentice", "Apprentice", 200), ("scheduled", "Scheduled", 110),
         ("status", "Status", 140), ("conductor", "Conducted by", 180)],
        rows,
        lambda r: (r.apprentice_name, r.scheduled_date, r.status, r.conductor_name),
        lambda r: r.review_id,
        "Nothing booked in the next fortnight.",
        noun="review",
    )


def _workplaces(parent, data: dict[str, Any]) -> None:
    box = widgets.section(parent, "Workplaces")
    rows = data.get("workplaces") or []
    _table(
        box,
        [("name", "Site", 220), ("postcode", "Postcode", 100),
         ("checked", "H&S checked", 120), ("expiry", "H&S expires", 120),
         ("hosting", "Can host apprentices", 160)],
        rows,
        lambda w: (w.name, w.postcode, w.hs_checked_date, w.hs_expiry_date,
                   w.can_host_apprentices),
        lambda w: w.workplace_id,
        "No workplaces are recorded against your organisation.",
        tag=lambda w: "Green" if w.can_host_apprentices else "Red",
        noun="workplace",
    )


def _funding(parent, data: dict[str, Any]) -> None:
    box = widgets.section(parent, "Levy and funding position")
    money = data.get("funding") or {}
    levy = data.get("levy")
    pairs: list[tuple[str, Any]] = [
        ("Scheduled", widgets.money(money.get("scheduled"))),
        ("Paid", widgets.money(money.get("paid"))),
        ("Claimed", widgets.money(money.get("claimed"))),
        ("Withheld", widgets.money(money.get("withheld"))),
        ("Overdue", widgets.money(money.get("overdue"))),
    ]
    if levy is not None:
        pairs.extend([
            ("Annual pay bill", widgets.money(levy.paybill)),
            ("Levy due this year", widgets.money(levy.levy_due)),
            ("Levy per month", widgets.money(levy.monthly_levy)),
            ("Allowance used", widgets.money(levy.allowance_used)),
            ("Levy payer", "Yes" if levy.is_levy_payer else "No — co-investment"),
        ])
    widgets.field_grid(box, pairs, columns=3)


# ── Shared table wiring ─────────────────────────────────────────────

def _table(
    parent,
    columns: Sequence[tuple],
    rows: Sequence[Any],
    to_values: Callable[[Any], Sequence[Any]],
    identity: Callable[[Any], Any],
    empty: str,
    *,
    tag: Callable[[Any], str | None] | None = None,
    noun: str = "row",
) -> None:
    """A short dashboard table, or a sentence saying why there isn't one."""
    if not rows:
        widgets.empty_state(parent, empty)
        return
    table = widgets.DataTable(parent, columns, height=min(8, len(rows)))
    table.populate(rows, to_values, identity=identity, tag=tag, noun=noun)
