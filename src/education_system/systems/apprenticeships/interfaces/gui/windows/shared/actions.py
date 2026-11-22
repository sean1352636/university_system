"""Action plans, for everyone who owns an action.

Every action agreed at a progress review, across all the apprentices the
signed-in user may see: the tutor's whole caseload, the employer's own
apprentices, or the apprentice's own plan. Overdue actions are Red and
those due within the week Amber, because the question this screen
answers is "what is slipping?".

Owners move their own actions along and leave progress notes; provider
staff who conduct reviews can also add, edit and carry actions. The
buttons follow the permissions and the service re-checks every one, so
nobody is offered an action that would only be refused.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date
from tkinter import ttk
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.reviews.action_plans import CARRIED_FORWARD
from education_system.systems.apprenticeships.domain.reviews.progress_reviews import ReviewTarget
from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.application.learning import (
    action_plan_service,
    review_service,
)

logger = logging.getLogger(__name__)

TITLE = "Action Plans"
SUBTITLE = (
    "Actions agreed at progress reviews, and who has to do them. Red is overdue, amber "
    f"is due within {config.ACTION_DUE_SOON_DAYS} days. Anything still open when the next "
    "review starts is carried onto it."
)

UNLINKED = (
    "Your sign-in is not linked to a record in this system yet, so there are no actions "
    "to show. Ask your training provider's administrator to link your account."
)

COLUMNS = (
    ("apprentice", "Apprentice", 170),
    ("action", "Action", 330),
    ("owner", "Owner", 100),
    ("priority", "Priority", 80),
    ("due", "Due", 100),
    ("status", "Status", 120),
    ("review", "Set at review", 110),
    ("carried", "Carried", 70, "e"),
)

NOTE_COLUMNS = (
    ("when", "When", 150),
    ("who", "From", 220),
    ("move", "Status change", 200),
    ("note", "Note", 420),
)

# What an owner may move an action to by hand. Carrying is its own step.
_HAND_STATUSES = tuple(s for s in config.TARGET_STATUSES if s != CARRIED_FORWARD)


def render(gui: Any) -> None:
    """Every action in the actor's scope, filterable."""
    frame = gui.clear()
    widgets.heading(frame, TITLE, subtitle=SUBTITLE)
    actor = gui.actor
    if not actor.can("review.view"):
        widgets.empty_state(frame, "Your role does not see action plans.")
        return
    if (actor.role == config.APPRENTICE and actor.apprentice_id is None) or (
        actor.role == config.EMPLOYER and actor.employer_id is None
    ):
        widgets.empty_state(frame, UNLINKED)
        return

    ok, summary = widgets.guard(lambda: action_plan_service.action_summary(actor))
    if ok and summary is not None:
        widgets.kpi_row(frame, [
            ("Open", summary["open"]),
            ("Overdue", summary["overdue"]),
            (f"Due within {config.ACTION_DUE_SOON_DAYS} days", summary["due_soon"]),
            (f"Owned by {_owner_label(actor)}", summary["mine"]),
            ("Carried forward", summary["carried"]),
        ])

    filters = widgets.FilterBar(
        frame,
        (
            ("status", "Status", "combo", config.TARGET_STATUSES),
            ("owner", "Owner", "combo", config.ACTION_OWNERS),
            ("priority", "Priority", "combo", config.ACTION_PRIORITIES),
            ("overdue_only", "Overdue only", "check"),
            ("due_soon", f"Due within {config.ACTION_DUE_SOON_DAYS} days", "check"),
            ("mine_only", "Mine only", "check"),
        ),
        lambda: reload(),
    )
    by_id: dict[int, ReviewTarget] = {}

    def selected(action: str) -> ReviewTarget | None:
        ident = table.require_selection_int(action)
        return by_id.get(ident) if ident is not None else None

    def update_status() -> None:
        target = selected("update an action")
        if target is not None and _may_update(actor, target):
            _status_form(gui, target, reload)

    def add_note() -> None:
        target = selected("add a progress note")
        if target is not None and _may_update(actor, target):
            _note_form(gui, target, reload)

    def show_history() -> None:
        target = selected("see an action's history")
        if target is not None:
            _history(gui, target)

    def edit() -> None:
        target = selected("edit an action")
        if target is not None:
            _edit_form(gui, target, reload)

    def carry() -> None:
        target = selected("carry an action forward")
        if target is None:
            return
        if not widgets.confirm(
            f"Carry “{target.description[:60]}” onto {target.apprentice_name}'s next "
            "review now? It closes here and opens on that review.",
            title="Carry forward",
        ):
            return
        ok, _ = widgets.guard(
            lambda: action_plan_service.carry_to_next_review(actor, target.target_id)
        )
        if ok:
            reload()

    buttons: list[tuple[str, Callable[[], None]]] = [("History…", show_history)]
    if actor.can("action.update"):
        buttons += [("Update status…", update_status), ("Add progress note…", add_note)]
    if actor.can("review.conduct"):
        buttons += [
            ("Add action…", lambda: _add_form(gui, reload)),
            ("Edit…", edit),
            ("Carry to next review…", carry),
        ]
    # Packed before the table: an expanding table packed first would push
    # the action bar off a short screen.
    widgets.button_bar(frame, buttons)
    table = widgets.DataTable(
        frame, COLUMNS, on_activate=lambda ident: _history_by_id(gui, by_id, ident)
    )

    def reload() -> None:
        values = filters.values()
        kwargs: dict[str, Any] = {
            "status": values.get("status"),
            "owner": values.get("owner"),
            "priority": values.get("priority"),
            "overdue_only": bool(values.get("overdue_only")),
            "mine_only": bool(values.get("mine_only")),
        }
        if values.get("due_soon"):
            kwargs["due_within_days"] = config.ACTION_DUE_SOON_DAYS
        ok, rows = widgets.guard(lambda: action_plan_service.list_actions(actor, **kwargs))
        rows = list(rows or []) if ok else []
        if not kwargs["status"]:
            # A carried-forward action lives on as its copy on the later
            # review; listing both would show every slipped action twice.
            rows = [r for r in rows if r.status != CARRIED_FORWARD]
        by_id.clear()
        by_id.update({r.target_id: r for r in rows})
        today = date.today()
        table.populate(
            rows,
            lambda t: (
                t.apprentice_name, t.description, t.owner, t.priority, t.due_date,
                t.status, t.review_date, t.carry_count or "",
            ),
            identity=lambda t: t.target_id,
            tag=lambda t: t.rag(today),
            noun="action",
        )

    reload()


# ═════════════════════════════════════════════════════════════════════
# Forms
# ═════════════════════════════════════════════════════════════════════

def _may_update(actor: Any, target: ReviewTarget) -> bool:
    """Say why not, up front, rather than offering a form that will be refused."""
    if target.status == CARRIED_FORWARD:
        widgets.warn(
            "This action was carried forward to a later review. Update the copy on that "
            "review instead.", title="Carried forward",
        )
        return False
    if not action_plan_service.may_update(actor, target):
        widgets.warn(
            f"This action is the {target.owner.lower()}'s to do. Only its owner or the "
            "training provider may update it."
        )
        return False
    return True


def _status_form(gui: Any, target: ReviewTarget, reload: Callable[[], None]) -> None:
    options = [s for s in _HAND_STATUSES if s != target.status]
    fields = [
        {"key": "status", "label": "New status", "kind": "combo", "required": True,
         "options": options, "value": "Met" if "Met" in options else options[0]},
        {"key": "note", "label": "What has happened", "kind": "text",
         "help": "Kept in the action's history with the status change."},
    ]

    def save(values: dict[str, Any]) -> object:
        return action_plan_service.update_status(
            gui.actor, target.target_id, status=values.get("status", ""),
            note=values.get("note"),
        )

    dialog = widgets.FormDialog(
        gui.root, "Update action", fields, save,
        intro=f"“{target.description}” is {target.status}"
              + (f", due {target.due_date}." if target.due_date else "."),
    )
    if dialog.saved:
        reload()


def _note_form(gui: Any, target: ReviewTarget, reload: Callable[[], None]) -> None:
    fields = [{"key": "body", "label": "Progress note", "kind": "text", "required": True}]

    def save(values: dict[str, Any]) -> object:
        return action_plan_service.add_note(gui.actor, target.target_id, values.get("body", ""))

    dialog = widgets.FormDialog(
        gui.root, "Add a progress note", fields, save,
        intro=f"On “{target.description}”. The status stays {target.status}.",
    )
    if dialog.saved:
        reload()


def _add_form(gui: Any, reload: Callable[[], None]) -> None:
    ok, reviews = widgets.guard(lambda: action_plan_service.reviews_taking_actions(gui.actor))
    if not ok:
        return
    if not reviews:
        widgets.warn(
            "There is no open review to add an action to. Schedule one from Progress "
            "Reviews first.", title="No open review",
        )
        return
    labels = {
        f"{r.apprentice_name} — {r.held_date or r.scheduled_date} ({r.status})": r.review_id
        for r in reviews
    }
    fields = [
        {"key": "review", "label": "Review", "kind": "combo", "required": True,
         "options": list(labels)},
        *_action_fields(None),
    ]

    def save(values: dict[str, Any]) -> object:
        review_id = labels.get(values.get("review") or "")
        if review_id is None:
            raise ValueError("Choose the review the action was agreed at")
        payload = {k: v for k, v in values.items() if k != "review"}
        return action_plan_service.add_action(gui.actor, review_id, payload)

    if widgets.FormDialog(gui.root, "Add an action", fields, save).saved:
        reload()


def _edit_form(gui: Any, target: ReviewTarget, reload: Callable[[], None]) -> None:
    def save(values: dict[str, Any]) -> object:
        return review_service.update_target(gui.actor, target.target_id, values)

    if widgets.FormDialog(gui.root, "Edit action", _action_fields(target), save).saved:
        reload()


def _action_fields(target: ReviewTarget | None) -> list[dict[str, Any]]:
    def current(attr: str, default: Any = "") -> Any:
        value = getattr(target, attr, None) if target is not None else None
        return default if value is None else value

    return [
        {"key": "description", "label": "Action", "kind": "text", "required": True,
         "value": current("description"),
         "help": "What will be done, specifically enough to judge at the next review."},
        {"key": "owner", "label": "Owner", "kind": "combo", "options": config.ACTION_OWNERS,
         "value": current("owner", config.ACTION_DEFAULT_OWNER)},
        {"key": "priority", "label": "Priority", "kind": "combo",
         "options": config.ACTION_PRIORITIES,
         "value": current("priority", config.ACTION_DEFAULT_PRIORITY)},
        {"key": "due_date", "label": "Due", "value": current("due_date"), "help": "YYYY-MM-DD."},
        {"key": "ksb_codes", "label": "KSBs", "value": current("ksb_codes"),
         "help": "Comma-separated, e.g. K3, S1."},
    ]


# ═════════════════════════════════════════════════════════════════════
# History
# ═════════════════════════════════════════════════════════════════════

def _history_by_id(gui: Any, by_id: dict[int, ReviewTarget], ident: str) -> None:
    target = by_id.get(int(ident))
    if target is not None:
        _history(gui, target)


def _history(gui: Any, target: ReviewTarget) -> None:
    """The action's notes and status moves, across every review it was carried through."""
    ok, notes = widgets.guard(lambda: action_plan_service.history(gui.actor, target.target_id))
    if not ok:
        return
    win = widgets.open_window(gui, f"Action history — {target.apprentice_name}",
                              geometry="1000x460")
    body = ttk.Frame(win, padding=10)
    body.pack(fill="both", expand=True)
    widgets.heading(
        body, target.description,
        subtitle=f"{target.owner} · {target.priority} priority · {target.status}"
                 + (f" · due {target.due_date}" if target.due_date else "")
                 + (f" · carried forward {target.carry_count} time(s)"
                    if target.carry_count else ""),
    )
    widgets.button_bar(body, [("Close", win.destroy)])
    if not notes:
        widgets.empty_state(body, "Nobody has added a note or moved this action yet.")
        return
    table = widgets.DataTable(body, NOTE_COLUMNS, height=min(12, len(notes)))
    table.populate(
        notes,
        lambda n: (
            n.created_at, n.author_label,
            f"{n.from_status} → {n.to_status}" if n.is_status_change else "",
            n.body,
        ),
        identity=lambda n: n.note_id,
        noun="entry",
    )


def _owner_label(actor: Any) -> str:
    owner = action_plan_service.owner_for(actor)
    return {"Apprentice": "you", "Employer": "you", "Tutor": "the provider"}.get(owner or "", "you")
