"""Funding — admin screen.

Negotiated prices, contribution splits and the payment schedule.

Two levels: the ledger across the whole provider, and one
apprenticeship's price and instalment plan. The money actions live on
the second, because claiming an instalment without seeing which
apprenticeship it belongs to is how the wrong one gets clawed back.
"""

from __future__ import annotations

import logging
from datetime import date
from tkinter import ttk
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.application.apprentices import apprentice_service
from education_system.systems.apprenticeships.application.funding import funding_service

logger = logging.getLogger(__name__)

TITLE = "Funding"
SUBTITLE = "Negotiated prices, contribution splits and the payment schedule."

_RECORD_COLUMNS = (
    ("apprentice", "Apprentice", 190),
    ("employer", "Employer", 170),
    ("programme", "Programme", 190),
    ("model", "Model", 120),
    ("band", "Band", 60, "e"),
    ("price", "Price", 110, "e"),
    ("employer_share", "Employer", 110, "e"),
    ("gov_share", "Government", 110, "e"),
    ("paid", "Paid", 110, "e"),
    ("status", "Status", 120),
)

_PAYMENT_COLUMNS = (
    ("due", "Due", 110),
    ("amount", "Amount", 110, "e"),
    ("type", "Type", 110),
    ("status", "Status", 110),
    ("claimed", "Claimed", 110),
    ("paid", "Paid", 110),
    ("notes", "Notes", 240),
)

_PAYMENT_TAGS = {
    "Paid": "Green", "Claimed": "Green",
    "Withheld": "Amber", "Clawed Back": "Red",
}


def render(gui) -> None:
    """Draw the funding ledger into the content pane."""
    frame = gui.clear()
    widgets.heading(frame, TITLE, subtitle=SUBTITLE)

    ok, dashboard = widgets.guard(lambda: funding_service.funding_dashboard(gui.actor))
    if not ok or dashboard is None:
        return
    totals = dashboard["totals"]
    widgets.kpi_row(frame, [
        ("Contracted", widgets.money(dashboard["contracted_value"])),
        ("Scheduled", widgets.money(totals["scheduled"])),
        ("Claimed", widgets.money(totals["claimed"])),
        ("Paid", widgets.money(totals["paid"])),
        ("Withheld", widgets.money(totals["withheld"])),
        ("Overdue", widgets.money(dashboard["overdue_value"])),
    ])
    if dashboard["overdue_count"]:
        ttk.Label(
            frame,
            text=f"{dashboard['overdue_count']} instalment(s) are past their due date "
                 f"and unclaimed.",
            foreground=config.ERROR_FG,
        ).pack(anchor="w", pady=(0, 6))

    filters = widgets.FilterBar(
        frame,
        (("funding_model", "Model", "combo", config.FUNDING_MODELS),),
        lambda: reload(),
    )
    table = widgets.DataTable(
        frame, _RECORD_COLUMNS,
        on_activate=lambda ident: _detail(gui, int(ident)),
    )
    hint = widgets.empty_state(frame, "")

    def reload() -> None:
        _, rows = widgets.guard(
            lambda: funding_service.list_funding(gui.actor, **filters.values())
        )
        rows = rows or []
        table.populate(
            rows,
            lambda r: (r["apprentice_name"], r["employer_name"], r["programme_title"],
                       r["funding_model"], r["band"],
                       widgets.money(r["negotiated_price"]),
                       widgets.money(r["employer_contribution"]),
                       widgets.money(r["government_contribution"]),
                       widgets.money(r["paid_to_date"]), r["apprentice_status"]),
            identity=lambda r: r["apprentice_id"],
            tag=lambda r: r["apprentice_status"],
            noun="record",
        )
        hint.config(text="" if rows else _NOTHING)

    def open_detail() -> None:
        chosen = table.require_selection_int("open an apprenticeship's funding")
        if chosen is not None:
            _detail(gui, chosen)

    buttons: list[tuple[str, Any]] = [("Open", open_detail)]
    if gui.actor.can("funding.manage"):
        buttons += [
            ("Set Funding…", lambda: _set_funding_for_selection(gui, table)),
            ("Claim Everything Due", lambda: _bulk_claim(gui)),
        ]
    widgets.button_bar(frame, buttons)
    reload()


_NOTHING = (
    "No funding has been agreed yet. Open an apprentice from here once they are on "
    "programme — the band comes from the standard, so usually the only figure anyone "
    "types is the negotiated price."
)


# ═════════════════════════════════════════════════════════════════════
# One apprenticeship
# ═════════════════════════════════════════════════════════════════════

def _detail(gui, apprentice_id: int) -> None:
    """One apprenticeship's price, split and instalment plan."""
    frame = gui.clear()
    ok, summary = widgets.guard(
        lambda: funding_service.get_funding(gui.actor, apprentice_id)
    )
    name = _name(gui, apprentice_id)
    widgets.heading(frame, f"Funding — {name}")
    back = ("← Back to funding", lambda: render(gui))
    if not ok or summary is None:
        widgets.button_bar(frame, [back])
        return

    record = summary.record
    if record is None:
        widgets.empty_state(
            frame,
            "No price has been agreed for this apprenticeship yet. Nothing can be "
            "claimed until there is one.",
        )
        buttons = [back]
        if gui.actor.can("funding.manage"):
            buttons.insert(0, ("Set Funding…",
                               lambda: _set_funding(gui, apprentice_id, None)))
        widgets.button_bar(frame, buttons)
        return

    widgets.field_grid(frame, [
        ("Model", record.funding_model),
        ("Band", f"{record.band} (cap {widgets.money(record.band_maximum)})"),
        ("Negotiated price", widgets.money(record.negotiated_price)),
        ("Headroom under the cap", widgets.money(record.headroom)),
        ("Employer contribution", widgets.money(record.employer_contribution)),
        ("Government contribution", widgets.money(record.government_contribution)),
        ("Additional payments", widgets.money(record.additional_payments)),
        ("Total value", widgets.money(record.total_value)),
        ("Scheduled", widgets.money(summary.scheduled_total)),
        ("Claimed", widgets.money(summary.claimed_total)),
        ("Paid", widgets.money(summary.paid_total)),
        ("Withheld", widgets.money(summary.withheld_total)),
        ("Outstanding", widgets.money(summary.outstanding_total)),
        ("Notes", record.notes),
    ], columns=4)

    box = widgets.section(frame, "Payment schedule")
    payments = summary.payments
    if not payments:
        widgets.empty_state(
            box,
            "No instalments are scheduled. That happens when the apprentice has no "
            "start or planned end date yet — the plan is built from those.",
        )
    table = widgets.DataTable(box, _PAYMENT_COLUMNS, height=min(14, max(4, len(payments))))
    table.populate(
        payments,
        lambda p: (f"{p.due_date}{'  !' if p.is_overdue else ''}", widgets.money(p.amount),
                   p.payment_type, p.status, p.claimed_at, p.paid_at, p.notes),
        identity=lambda p: p.payment_id,
        tag=lambda p: "Red" if p.is_overdue else _PAYMENT_TAGS.get(p.status),
        noun="instalment",
    )

    if not gui.actor.can("funding.manage"):
        widgets.button_bar(frame, [back])
        return

    def move(action: Any, prompt: str, *, reason: str | None = None) -> None:
        payment_id = table.require_selection_int(prompt)
        if payment_id is None:
            return
        if reason is None:
            ok, _ = widgets.guard(lambda: action(gui.actor, payment_id))
        else:
            note = widgets.ask_reason(reason, title="Reason")
            if not note:
                return
            ok, _ = widgets.guard(lambda: action(gui.actor, payment_id, reason=note))
        if ok:
            _detail(gui, apprentice_id)

    widgets.button_bar(frame, [
        ("Set Funding…", lambda: _set_funding(gui, apprentice_id, record)),
        ("Rebuild Schedule", lambda: _regenerate(gui, apprentice_id)),
        ("Claim", lambda: move(funding_service.claim_payment, "claim an instalment")),
        ("Mark Paid", lambda: move(funding_service.mark_paid, "reconcile an instalment")),
        ("Withhold…", lambda: move(
            funding_service.withhold_payment, "withhold an instalment",
            reason="Why is this instalment being held back?",
        )),
        ("Claw Back…", lambda: move(
            funding_service.claw_back, "claw a payment back",
            reason="Why is this money being recovered?",
        )),
        back,
    ])


# ═════════════════════════════════════════════════════════════════════
# Actions
# ═════════════════════════════════════════════════════════════════════

def _set_funding_for_selection(gui, table: widgets.DataTable) -> None:
    apprentice_id = table.require_selection_int("set an apprenticeship's funding")
    if apprentice_id is None:
        return
    ok, summary = widgets.guard(
        lambda: funding_service.get_funding(gui.actor, apprentice_id)
    )
    _set_funding(gui, apprentice_id, summary.record if ok and summary else None)


def _set_funding(gui, apprentice_id: int, record: Any) -> None:
    """Agree — or re-negotiate — the price of one apprenticeship."""
    fields = [
        {"key": "negotiated_price", "label": "Negotiated price", "required": True,
         "value": record.negotiated_price if record else "",
         "help": "Checked against the band cap: the excess above it is unfundable."},
        {"key": "band", "label": "Band override",
         "value": record.band if record else "",
         "help": "Blank takes the band from the standard."},
        {"key": "funding_model", "label": "Route override", "kind": "combo",
         "options": ("", *config.FUNDING_MODELS),
         "value": record.funding_model if record else "",
         "help": "Blank derives it from the employer's levy and headcount position."},
        {"key": "additional_payments", "label": "Additional payments",
         "value": record.additional_payments if record else 0.0},
        {"key": "notes", "label": "Notes", "kind": "text",
         "value": (record.notes if record else "") or ""},
    ]

    def save(values: dict[str, Any]) -> Any:
        payload = dict(values)
        # An empty override means "derive it", not "set it to nothing".
        for key in ("band", "funding_model"):
            if not str(payload.get(key) or "").strip():
                payload.pop(key, None)
        return funding_service.set_funding(gui.actor, apprentice_id, payload)

    dialog = widgets.FormDialog(
        gui.root, "Agree a price", fields, save,
        intro="Saving rebuilds the instalment plan. Instalments already claimed or "
              "paid survive — they are real financial events, not a projection.",
    )
    if dialog.saved:
        _detail(gui, apprentice_id)


def _regenerate(gui, apprentice_id: int) -> None:
    if not widgets.confirm(
        "Rebuild the instalment plan from the current dates and price?\n\n"
        "Instalments already claimed or paid are left alone.",
        title="Rebuild schedule",
    ):
        return
    ok, count = widgets.guard(
        lambda: funding_service.regenerate_schedule(gui.actor, apprentice_id)
    )
    if ok:
        widgets.inform(f"{count} instalment(s) scheduled.")
        _detail(gui, apprentice_id)


def _bulk_claim(gui) -> None:
    """Claim every scheduled instalment that has fallen due."""
    ok, payments = widgets.guard(
        lambda: funding_service.list_payments(gui.actor, status="Scheduled")
    )
    if not ok:
        return
    today = date.today().isoformat()
    due = [p for p in (payments or []) if p.due_date <= today]
    if not due:
        widgets.inform("No scheduled instalment has fallen due yet.", title="Nothing to claim")
        return

    total = sum(p.amount for p in due)
    if not widgets.confirm(
        f"Claim {len(due)} instalment(s) totalling {widgets.money(total)}?",
        title="Claim everything due",
    ):
        return
    ok, claimed = widgets.guard(
        lambda: funding_service.bulk_claim(gui.actor, [p.payment_id for p in due])
    )
    if not ok:
        return
    message = f"{claimed} of {len(due)} instalment(s) claimed."
    if claimed < len(due):
        message += "\n\nThe rest had already been claimed by somebody else."
    widgets.inform(message, title="Claimed")
    gui.refresh()


def _name(gui, apprentice_id: int) -> str:
    """The apprentice's name for the heading, or a bare id.

    Deliberately not ``widgets.guard``: a caption that will not resolve
    is not worth a message box on top of the screen the user asked for.
    """
    try:
        return apprentice_service.get_apprentice(gui.actor, apprentice_id).full_name
    except Exception:
        logger.debug("Could not name apprentice %s", apprentice_id, exc_info=True)
        return f"Apprentice {apprentice_id}"
