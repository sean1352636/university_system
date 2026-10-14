"""Appeals: the apprentice lodges one, and whoever made the decision hears it.

An apprentice sees their own appeals, lodges new ones and may withdraw
one still open. The provider admin sees and decides every type except
EPA results; the end-point assessor sees and decides EPA results only.
That routing lives in the service — this screen only decides which
buttons to offer, using the same rule so nobody is shown an action that
would be refused.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.quality import appeals as rules
from education_system.systems.apprenticeships.domain.quality.appeals import Appeal
from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.services import appeal_service

logger = logging.getLogger(__name__)

UNLINKED = (
    "Your sign-in is not linked to an apprentice record yet, so there are no appeals to "
    "show. Ask your training provider's administrator to link your account."
)

COLUMNS = (
    ("ref", "Ref", 90),
    ("apprentice", "Apprentice", 180),
    ("type", "Type", 150),
    ("against", "Against", 280),
    ("lodged", "Lodged", 100),
    ("deadline", "Decide by", 100),
    ("status", "Status", 120),
)

OWN_COLUMNS = (
    ("ref", "Ref", 90),
    ("type", "Type", 160),
    ("against", "Against", 320),
    ("lodged", "Lodged", 100),
    ("status", "Status", 120),
    ("decider", "Decided by", 170),
)


def render(gui: Any) -> None:
    frame = gui.clear()
    actor = gui.actor
    apprentice = actor.role == config.APPRENTICE
    if apprentice:
        subtitle = (
            f"You can appeal a decision made about you within {config.APPEAL_WINDOW_DAYS} "
            "days of it. Appeals against an EPA result go to the End-Point Assessment "
            "Organisation; everything else to your training provider."
        )
    elif actor.role == config.END_POINT_ASSESSOR:
        subtitle = ("Appeals against EPA results. Other appeals are heard by the training "
                    "provider and are not shown here.")
    else:
        subtitle = ("Appeals against the provider's own decisions. Appeals against EPA "
                    "results are heard by the End-Point Assessment Organisation, "
                    "independently of the provider, and are not shown here.")
    widgets.heading(frame, "Appeals", subtitle=subtitle)

    if apprentice and actor.apprentice_id is None:
        widgets.empty_state(frame, UNLINKED)
        return

    filters = None
    if not apprentice:
        specs: list[tuple] = [("status", "Status", "combo", config.APPEAL_STATUSES)]
        if actor.role == config.ADMIN:
            specs.append(("appeal_type", "Type", "combo",
                          [t for t in config.APPEAL_TYPES if t != config.EPA_RESULT_APPEAL]))
        specs += [("open_only", "Open only", "check"), ("overdue_only", "Overdue only", "check")]
        filters = widgets.FilterBar(frame, specs, lambda: reload())

    table = widgets.DataTable(
        frame, OWN_COLUMNS if apprentice else COLUMNS,
        on_activate=lambda ident: _open(gui, int(ident)),
    )
    today = date.today()

    def reload() -> None:
        values = filters.values() if filters is not None else {}
        ok, rows = widgets.guard(lambda: appeal_service.list_appeals(actor, **values))
        rows = rows or []
        if apprentice:
            table.populate(
                rows,
                lambda a: (a.reference, a.appeal_type, a.decision_ref, a.lodged_at,
                           a.status, a.decider_label),
                identity=lambda a: a.appeal_id,
                noun="appeal",
            )
        else:
            table.populate(
                rows,
                lambda a: (a.reference, a.apprentice_name, a.appeal_type, a.decision_ref,
                           a.lodged_at, a.deadline, a.status),
                identity=lambda a: a.appeal_id,
                tag=lambda a: a.rag(today),
                noun="appeal",
            )

    def open_selected() -> None:
        appeal_id = table.require_selection_int("open an appeal")
        if appeal_id is not None:
            _open(gui, appeal_id)

    buttons: list[tuple[str, Callable[[], None]]] = [("Open →", open_selected)]
    # The admin holds appeal.raise too, but is nobody's apprentice: only an
    # apprentice has a decision of their own to appeal.
    if apprentice and actor.can("appeal.raise"):
        buttons.append(("Lodge an appeal…", lambda: _lodge(gui, lambda: render(gui))))
    widgets.button_bar(frame, buttons)
    reload()


# ═════════════════════════════════════════════════════════════════════
# One appeal
# ═════════════════════════════════════════════════════════════════════

def _open(gui: Any, appeal_id: int) -> None:
    frame = gui.clear()
    ok, appeal = widgets.guard(lambda: appeal_service.get_appeal(gui.actor, appeal_id))
    if not ok:
        widgets.heading(frame, "Appeal")
        widgets.button_bar(frame, [("← All appeals", lambda: render(gui))])
        return
    reload = lambda: _open(gui, appeal_id)  # noqa: E731
    today = date.today()
    widgets.heading(
        frame, f"{appeal.reference} — {appeal.appeal_type}",
        subtitle="Decision overdue" if appeal.is_overdue(today) else appeal.status,
    )

    buttons: list[tuple[str, Callable[[], None]]] = [("← All appeals", lambda: render(gui))]
    if appeal.is_open and appeal_service.may_decide(gui.actor, appeal):
        if appeal.status == "Lodged":
            buttons.append(("Start review", lambda: _start_review(gui, appeal, reload)))
        buttons.append(("Decide…", lambda: _decide(gui, appeal, reload)))
    if (appeal.is_open and gui.actor.role == config.APPRENTICE
            and appeal.apprentice_id == gui.actor.apprentice_id):
        buttons.append(("Withdraw…", lambda: _withdraw(gui, appeal, reload)))
    widgets.button_bar(frame, buttons)

    body = widgets.scrollable(frame)
    widgets.field_grid(body, [
        ("Status", appeal.status),
        ("Apprentice", appeal.apprentice_name),
        ("Type", appeal.appeal_type),
        ("Heard by", appeal.decider_label),
        ("Against", appeal.decision_ref),
        ("Decision made", appeal.decision_date),
        ("Lodged", appeal.lodged_at),
        ("Decide by", appeal.deadline),
        ("Decided by", appeal.decided_by),
        ("Decided", appeal.decided_at),
    ], columns=3)
    widgets.field_grid(widgets.section(body, "Grounds"), [("", appeal.grounds)], columns=1)
    if appeal.decision:
        title = "Reason for withdrawal" if appeal.status == "Withdrawn" else "Decision"
        widgets.field_grid(widgets.section(body, title), [("", appeal.decision)], columns=1)


# ═════════════════════════════════════════════════════════════════════
# Forms
# ═════════════════════════════════════════════════════════════════════

def _lodge(gui: Any, reload: Callable[[], None]) -> None:
    """Choose the type first: an EPA result is picked, anything else described."""
    chosen: dict[str, Any] = {}
    picker = widgets.FormDialog(
        gui.root, "Lodge an appeal",
        [{"key": "appeal_type", "label": "What are you appealing?", "kind": "combo",
          "options": config.APPEAL_TYPES, "value": config.APPEAL_TYPES[0], "required": True}],
        lambda values: chosen.update(values),
        intro=f"Appeals must be lodged within {config.APPEAL_WINDOW_DAYS} days of the "
              "decision.",
        save_label="Next",
    )
    if not picker.saved:
        return
    appeal_type = chosen.get("appeal_type") or ""

    results: dict[str, int] = {}
    if rules.is_epa_result(appeal_type):
        ok, found = widgets.guard(lambda: appeal_service.appealable_epa_results(gui.actor))
        if not ok:
            return
        results = {
            f"{r.method}: {r.grade} — assessed {r.assessed_date} (attempt {r.attempt})":
                r.result_id
            for r in found
        }
        if not results:
            widgets.inform(
                f"You have no EPA results from the last {config.APPEAL_WINDOW_DAYS} days to "
                "appeal.", title="Nothing to appeal",
            )
            return
        fields: list[dict[str, Any]] = [
            {"key": "result", "label": "EPA result", "kind": "combo", "options": list(results),
             "value": next(iter(results)), "required": True},
        ]
        intro = "This appeal goes to the End-Point Assessment Organisation."
    else:
        fields = [
            {"key": "decision_ref", "label": "The decision", "required": True,
             "help": "What was decided, e.g. “Unit 3 assessment referred”."},
            {"key": "decision_date", "label": "Date of the decision", "required": True,
             "help": "YYYY-MM-DD."},
        ]
        intro = "This appeal goes to your training provider."
    fields.append({"key": "grounds", "label": "Why you are appealing", "kind": "text",
                   "required": True})

    def save(values: dict[str, Any]) -> object:
        payload = {k: v for k, v in values.items() if k != "result"}
        payload["appeal_type"] = appeal_type
        if results:
            payload["result_id"] = results.get(values.get("result") or "")
        return appeal_service.lodge(gui.actor, payload)

    dialog = widgets.FormDialog(gui.root, f"Appeal — {appeal_type}", fields, save,
                                intro=intro, save_label="Lodge appeal")
    if dialog.saved:
        widgets.inform(
            f"{dialog.result.reference} has been lodged. A decision is due by "
            f"{dialog.result.deadline}.", title="Appeal lodged",
        )
        reload()


def _start_review(gui: Any, appeal: Appeal, reload: Callable[[], None]) -> None:
    ok, _ = widgets.guard(lambda: appeal_service.start_review(gui.actor, appeal.appeal_id))
    if ok:
        reload()


def _decide(gui: Any, appeal: Appeal, reload: Callable[[], None]) -> None:
    fields = [
        {"key": "outcome", "label": "Outcome", "kind": "combo",
         "options": rules.DECISION_STATUSES, "value": rules.DECISION_STATUSES[0],
         "required": True},
        {"key": "decision", "label": "Reasons", "kind": "text", "required": True,
         "help": "The apprentice reads this: say what was considered and why."},
    ]
    dialog = widgets.FormDialog(
        gui.root, f"Decide {appeal.reference}", fields,
        lambda values: appeal_service.decide(
            gui.actor, appeal.appeal_id,
            outcome=values.get("outcome", ""), decision=values.get("decision", ""),
        ),
        intro=f"Against: {appeal.decision_ref}",
    )
    if dialog.saved:
        reload()


def _withdraw(gui: Any, appeal: Appeal, reload: Callable[[], None]) -> None:
    if not widgets.confirm(f"Withdraw {appeal.reference}? This cannot be undone."):
        return
    reason = widgets.ask_reason("Why are you withdrawing it? (optional)")
    ok, _ = widgets.guard(
        lambda: appeal_service.withdraw(gui.actor, appeal.appeal_id, reason=reason)
    )
    if ok:
        reload()
