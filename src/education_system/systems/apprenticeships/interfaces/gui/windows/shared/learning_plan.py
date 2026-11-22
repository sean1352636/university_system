"""The individual learning plan (ILP), for everyone with a stake in it.

Objectives are what the apprentice will achieve and by when; the
activities under them are how. Provider staff build the plan and move
its progress; the apprentice and their employer read it and add to the
conversation underneath. One screen serves all of them — the service
decides what each actor may see and do, and the buttons follow the same
permissions, so nobody is offered an action that would only be refused.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date
from tkinter import ttk
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.records import signatures as sig_rules
from education_system.systems.apprenticeships.domain.training import sessions as session_rules
from education_system.systems.apprenticeships.domain.training.learning_plan import (
    LearningObjective,
    LearningPlan,
)
from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.interfaces.gui.windows.shared import (
    signatures as signature_window,
)
from education_system.systems.apprenticeships.application.apprentices import apprentice_service
from education_system.systems.apprenticeships.application.learning import (
    learning_plan_service,
    training_service,
)

logger = logging.getLogger(__name__)

UNLINKED = (
    "Your sign-in is not linked to an apprentice record yet, so there is no plan to "
    "show. Ask your training provider's administrator to link your account."
)

PICK_COLUMNS = (
    ("name", "Apprentice", 220),
    ("programme", "Programme", 240),
    ("employer", "Employer", 200),
    ("status", "Status", 130),
)

OBJECTIVE_COLUMNS = (
    ("title", "Objective", 300),
    ("ksbs", "KSBs", 120),
    ("target", "Target date", 110),
    ("status", "Status", 110),
    ("progress", "Progress", 90, "e"),
    ("activities", "Activities", 90, "e"),
)

ACTIVITY_COLUMNS = (
    ("title", "Activity", 260),
    ("objective", "Delivers", 220),
    ("start", "Planned start", 110),
    ("end", "Planned end", 110),
    ("hours", "Hours", 70, "e"),
    ("status", "Status", 110),
)

COMMENT_COLUMNS = (
    ("when", "When", 150),
    ("who", "From", 210),
    ("about", "About", 200),
    ("progress", "Progress", 80, "e"),
    ("comment", "Comment", 420),
)

REVIEW_COLUMNS = (
    ("date", "Date", 110),
    ("status", "Status", 150),
    ("rating", "Progress rating", 120),
    ("by", "Conducted by", 170),
    ("summary", "Summary", 380),
)

SESSION_COLUMNS = (
    ("when", "When", 200),
    ("title", "Session", 300),
    ("mode", "How", 140),
    ("location", "Where", 200),
    ("trainer", "Trainer", 160),
    ("hours", "Off-the-job hours", 130, "e"),
)

_WHOLE_PLAN = "The plan as a whole"


def render(gui: Any) -> None:
    """The apprentice's own plan, or the cohort to choose a plan from."""
    frame = gui.clear()
    widgets.heading(
        frame,
        "Learning Plan",
        subtitle="What the apprentice will achieve, how, and by when — and the "
                 "conversation about it.",
    )
    if gui.actor.role == config.APPRENTICE:
        if gui.actor.apprentice_id is None:
            widgets.empty_state(frame, UNLINKED)
            return
        _plan(gui, frame, gui.actor.apprentice_id, reload=lambda: render(gui))
        return

    ok, people = widgets.guard(
        lambda: apprentice_service.list_apprentices(gui.actor, active_only=True)
    )
    if not ok:
        return
    if not people:
        widgets.empty_state(frame, "There are no active apprentices whose plans you can see.")
        return

    table = widgets.DataTable(
        frame, PICK_COLUMNS, on_activate=lambda ident: _open(gui, int(ident))
    )

    def open_selected() -> None:
        apprentice_id = table.require_selection_int("open a learning plan")
        if apprentice_id is not None:
            _open(gui, apprentice_id)

    # Packed before the table fills: an expanding table packed first
    # would push the action bar off a short screen.
    widgets.button_bar(frame, [("Open learning plan →", open_selected)])
    table.populate(
        people,
        lambda s: (s.full_name, s.programme_title, s.employer_name, s.apprentice.status),
        identity=lambda s: s.apprentice.apprentice_id,
        noun="apprentice",
    )


def _open(gui: Any, apprentice_id: int) -> None:
    """One apprentice's plan, for staff and employers."""
    frame = gui.clear()
    ok, summary = widgets.guard(
        lambda: apprentice_service.get_apprentice(gui.actor, apprentice_id)
    )
    name = summary.full_name if ok and summary else f"Apprentice {apprentice_id}"
    widgets.heading(frame, f"Learning Plan — {name}")
    widgets.button_bar(frame, [("← All learning plans", lambda: render(gui))])
    if ok:
        _plan(gui, frame, apprentice_id, reload=lambda: _open(gui, apprentice_id))


def _plan(gui: Any, frame: Any, apprentice_id: int, *, reload: Callable[[], None]) -> None:
    ok, plan = widgets.guard(lambda: learning_plan_service.get_plan(gui.actor, apprentice_id))
    if not ok:
        return
    today = date.today()
    upcoming = plan.next_target(today)

    body = widgets.scrollable(frame)
    widgets.kpi_row(body, [
        ("Overall progress", f"{plan.overall_progress:.0f}%"),
        ("Objectives", len(plan.counted_objectives)),
        ("Achieved", plan.achieved),
        ("Overdue", len(plan.overdue(today))),
        ("Next target", upcoming.target_date if upcoming else "—"),
    ])
    _objectives(gui, body, plan, today, reload)
    _activities(gui, body, plan, reload)
    _signoff(gui, body, plan, reload)
    _comments(gui, body, plan, reload)
    if gui.actor.can("review.view"):
        _reviews(gui, body, apprentice_id)
    if gui.actor.role == config.APPRENTICE:
        _sessions(gui, body)


# ═════════════════════════════════════════════════════════════════════
# Sign-off
# ═════════════════════════════════════════════════════════════════════

def _signoff(gui: Any, parent: Any, plan: LearningPlan, reload: Callable[[], None]) -> None:
    """Who has signed the plan as it stands, and a Sign action for whoever still must.

    Shown straight after the objectives and activities because those are
    what a signature covers: change either and every signature lapses.
    """
    box = widgets.section(parent, "Sign-off")
    ok, state = widgets.guard(
        lambda: learning_plan_service.plan_signatures(gui.actor, plan.apprentice_id)
    )
    if not ok:
        return
    signatory = sig_rules.signatory_for(gui.actor.role)
    has_content = bool(plan.objectives or plan.activities)

    def sign() -> None:
        if signature_window.sign_dialog(
            gui, sig_rules.LEARNING_PLAN, plan.apprentice_id, state.title, signatory=signatory
        ):
            reload()

    if (has_content and gui.actor.can("signature.sign") and signatory in state.required
            and state.state(signatory) != sig_rules.SIGNED):
        widgets.button_bar(box, [(f"Sign plan as {signatory}…", sign)])

    ttk.Label(
        box,
        text=f"{state.summary}. The apprentice, their employer and the provider each sign "
             "the plan. A signature covers the objectives and activities as they stand — "
             "changing either afterwards means it has to be signed again.",
        foreground=config.MUTED_FG, wraplength=900, justify="left",
    ).pack(anchor="w", pady=(0, 6))
    if not has_content:
        widgets.empty_state(
            box, "There is nothing to sign until objectives or activities are on the plan."
        )
        return
    signature_window.signoff_table(box, state)


# ═════════════════════════════════════════════════════════════════════
# Objectives
# ═════════════════════════════════════════════════════════════════════

def _objectives(gui: Any, parent: Any, plan: LearningPlan, today: date,
                reload: Callable[[], None]) -> None:
    box = widgets.section(parent, "Objectives")
    by_id = {o.objective_id: o for o in plan.objectives}
    table: widgets.DataTable | None = None

    def selected(action: str) -> LearningObjective | None:
        if table is None:
            widgets.warn("There are no objectives yet.", title="Nothing to choose")
            return None
        ident = table.require_selection_int(action)
        return by_id.get(ident) if ident is not None else None

    def add() -> None:
        _objective_form(gui, plan.apprentice_id, None, reload)

    def edit() -> None:
        objective = selected("edit an objective")
        if objective is not None:
            _objective_form(gui, plan.apprentice_id, objective, reload)

    def progress() -> None:
        objective = selected("record progress")
        if objective is not None:
            _progress_form(gui, objective, reload)

    def delete() -> None:
        objective = selected("delete an objective")
        if objective is None:
            return
        reason = widgets.ask_reason(
            f"Why is “{objective.title}” being deleted? Its activities and comments stay "
            "on the plan. For an objective that no longer applies, set it to Withdrawn "
            "instead."
        )
        if not reason:
            return
        ok, _ = widgets.guard(lambda: learning_plan_service.delete_objective(
            gui.actor, objective.objective_id, reason=reason
        ))
        if ok:
            reload()

    if gui.actor.can("training.manage"):
        widgets.button_bar(box, [
            ("Add objective…", add), ("Edit…", edit),
            ("Record progress…", progress), ("Delete…", delete),
        ])

    if not plan.objectives:
        widgets.empty_state(
            box,
            "No objectives have been set yet. They are agreed with the apprentice and "
            "their employer at the start of the programme.",
        )
        return
    table = widgets.DataTable(box, OBJECTIVE_COLUMNS, height=min(8, len(plan.objectives)))
    table.populate(
        plan.objectives,
        lambda o: (
            o.title, o.ksb_codes, o.target_date, o.status, f"{o.progress}%",
            len(plan.activities_for(o.objective_id)),
        ),
        identity=lambda o: o.objective_id,
        tag=lambda o: o.rag(today),
        noun="objective",
    )


def _objective_form(gui: Any, apprentice_id: int, objective: LearningObjective | None,
                    reload: Callable[[], None]) -> None:
    def current(attr: str, default: Any = "") -> Any:
        value = getattr(objective, attr, None) if objective is not None else None
        return default if value is None else value

    fields = [
        {"key": "title", "label": "Objective", "required": True, "value": current("title")},
        {"key": "description", "label": "Description", "kind": "text",
         "value": current("description")},
        {"key": "ksb_codes", "label": "KSBs", "value": current("ksb_codes"),
         "help": "Comma-separated codes from the standard, e.g. K1, S3, B2."},
        {"key": "target_date", "label": "Target date", "value": current("target_date"),
         "help": "YYYY-MM-DD."},
        {"key": "status", "label": "Status", "kind": "combo",
         "options": config.OBJECTIVE_STATUSES, "value": current("status", "Not started")},
        {"key": "progress", "label": "Progress %", "value": str(current("progress", 0)),
         "help": "0 to 100. Reaching 100 marks the objective Achieved."},
    ]

    def save(values: dict[str, Any]) -> object:
        if objective is None:
            return learning_plan_service.add_objective(gui.actor, apprentice_id, values)
        return learning_plan_service.update_objective(gui.actor, objective.objective_id, values)

    dialog = widgets.FormDialog(
        gui.root, "Edit objective" if objective else "Add objective", fields, save,
    )
    if dialog.saved:
        reload()


def _progress_form(gui: Any, objective: LearningObjective,
                   reload: Callable[[], None]) -> None:
    fields = [
        {"key": "progress", "label": "Progress %", "required": True,
         "value": str(objective.progress)},
        {"key": "status", "label": "Status", "kind": "combo",
         "options": ["", *config.OBJECTIVE_STATUSES], "value": "",
         "help": "Leave blank to work it out from the progress: 100% is Achieved."},
        {"key": "comment", "label": "What has changed", "kind": "text"},
    ]

    def save(values: dict[str, Any]) -> object:
        return learning_plan_service.record_progress(
            gui.actor, objective.objective_id,
            progress=values.get("progress"),
            status=values.get("status") or None,
            comment=values.get("comment"),
        )

    dialog = widgets.FormDialog(
        gui.root, "Record progress", fields, save,
        intro=f"“{objective.title}” is at {objective.progress}%. The update is kept in "
              "the plan's comments, so the plan shows how progress moved.",
    )
    if dialog.saved:
        reload()


# ═════════════════════════════════════════════════════════════════════
# Activities
# ═════════════════════════════════════════════════════════════════════

def _activities(gui: Any, parent: Any, plan: LearningPlan,
                reload: Callable[[], None]) -> None:
    box = widgets.section(parent, "Activities")
    titles = {o.objective_id: o.title for o in plan.objectives}
    by_id = {i.item_id: i for i in plan.activities}
    table: widgets.DataTable | None = None

    def selected(action: str) -> Any:
        if table is None:
            widgets.warn("There are no activities yet.", title="Nothing to choose")
            return None
        ident = table.require_selection_int(action)
        return by_id.get(ident) if ident is not None else None

    def add() -> None:
        _activity_form(gui, plan, None, reload)

    def edit() -> None:
        item = selected("edit an activity")
        if item is not None:
            _activity_form(gui, plan, item, reload)

    def remove() -> None:
        item = selected("remove an activity")
        if item is None or not widgets.confirm(f"Remove “{item.title}” from the plan?"):
            return
        ok, _ = widgets.guard(lambda: training_service.delete_plan_item(gui.actor, item.item_id))
        if ok:
            reload()

    if gui.actor.can("training.manage"):
        widgets.button_bar(box, [("Add activity…", add), ("Edit…", edit), ("Remove", remove)])

    if not plan.activities:
        widgets.empty_state(box, "No activities are planned yet.")
        return
    table = widgets.DataTable(box, ACTIVITY_COLUMNS, height=min(8, len(plan.activities)))
    table.populate(
        plan.activities,
        lambda i: (
            i.title, titles.get(i.objective_id, "—"), i.planned_start, i.planned_end,
            i.planned_hours, i.status,
        ),
        identity=lambda i: i.item_id,
        tag=lambda i: "Green" if i.is_done else None,
        noun="activity",
    )


def _activity_form(gui: Any, plan: LearningPlan, item: Any,
                   reload: Callable[[], None]) -> None:
    # An activity can deliver any open objective, or the one it is
    # already under even if that has since closed.
    objectives = {
        f"{o.objective_id} — {o.title}": o.objective_id
        for o in plan.objectives
        if o.is_open or (item is not None and o.objective_id == item.objective_id)
    }
    current_objective = next(
        (label for label, oid in objectives.items()
         if item is not None and oid == item.objective_id), "",
    )
    statuses = list(config.PLAN_ITEM_STATUSES)
    if item is not None and item.status not in statuses:
        statuses.append(item.status)

    def current(attr: str, default: Any = "") -> Any:
        value = getattr(item, attr, None) if item is not None else None
        return default if value is None else value

    fields = [
        {"key": "title", "label": "Activity", "required": True, "value": current("title")},
        {"key": "description", "label": "Description", "kind": "text",
         "value": current("description")},
        {"key": "objective", "label": "Delivers objective", "kind": "combo",
         "options": ["", *objectives], "value": current_objective},
        {"key": "delivery_mode", "label": "How", "kind": "combo",
         "options": session_rules.DELIVERY_MODES,
         "value": current("delivery_mode", "Classroom")},
        {"key": "planned_start", "label": "Planned start", "value": current("planned_start"),
         "help": "YYYY-MM-DD."},
        {"key": "planned_end", "label": "Planned end", "value": current("planned_end"),
         "help": "YYYY-MM-DD."},
        {"key": "planned_hours", "label": "Planned hours",
         "value": str(current("planned_hours", 0))},
        {"key": "ksb_codes", "label": "KSBs", "value": current("ksb_codes")},
        {"key": "status", "label": "Status", "kind": "combo", "options": statuses,
         "value": current("status", "Planned")},
    ]

    def save(values: dict[str, Any]) -> object:
        payload = {k: v for k, v in values.items() if k != "objective"}
        payload["objective_id"] = objectives.get(values.get("objective") or "")
        if not str(payload.get("planned_hours") or "").strip():
            payload["planned_hours"] = 0
        if item is None:
            return training_service.add_plan_item(gui.actor, plan.apprentice_id, payload)
        return training_service.update_plan_item(gui.actor, item.item_id, payload)

    dialog = widgets.FormDialog(
        gui.root, "Edit activity" if item else "Add activity", fields, save,
    )
    if dialog.saved:
        reload()


# ═════════════════════════════════════════════════════════════════════
# The conversation, and the reviews behind it
# ═════════════════════════════════════════════════════════════════════

def _comments(gui: Any, parent: Any, plan: LearningPlan,
              reload: Callable[[], None]) -> None:
    box = widgets.section(parent, "Comments")
    titles = {o.objective_id: o.title for o in plan.objectives}

    def add() -> None:
        about = {f"{o.objective_id} — {o.title}": o.objective_id for o in plan.objectives}
        fields = [
            {"key": "about", "label": "About", "kind": "combo",
             "options": [_WHOLE_PLAN, *about], "value": _WHOLE_PLAN},
            {"key": "comment", "label": "Comment", "kind": "text", "required": True},
        ]

        def save(values: dict[str, Any]) -> object:
            return learning_plan_service.add_comment(
                gui.actor, plan.apprentice_id, values.get("comment", ""),
                objective_id=about.get(values.get("about") or ""),
            )

        dialog = widgets.FormDialog(gui.root, "Add a comment", fields, save)
        if dialog.saved:
            reload()

    if gui.actor.can("plan.comment"):
        widgets.button_bar(box, [("Add comment…", add)])

    if not plan.comments:
        widgets.empty_state(
            box,
            "No comments yet. The apprentice, their employer and the provider can all "
            "add to the plan here.",
        )
        return
    table = widgets.DataTable(box, COMMENT_COLUMNS, height=min(8, len(plan.comments)))
    table.populate(
        plan.comments,
        lambda c: (
            c.created_at, c.author_label, titles.get(c.objective_id, _WHOLE_PLAN),
            f"{c.progress}%" if c.progress is not None else "", c.body,
        ),
        identity=lambda c: c.comment_id,
        noun="comment",
    )


def _reviews(gui: Any, parent: Any, apprentice_id: int) -> None:
    box = widgets.section(parent, "Review history")
    ok, reviews = widgets.guard(
        lambda: learning_plan_service.review_history(gui.actor, apprentice_id)
    )
    if not ok:
        return
    if not reviews:
        widgets.empty_state(box, "No progress reviews yet.")
        return
    table = widgets.DataTable(box, REVIEW_COLUMNS, height=min(6, len(reviews)))
    table.populate(
        reviews,
        lambda r: (
            r.held_date or r.scheduled_date, r.status, r.progress_rating,
            r.conductor_name, r.summary,
        ),
        identity=lambda r: r.review_id,
        tag=lambda r: r.progress_rating if r.progress_rating in config.RAG_RATINGS else None,
        noun="review",
    )


def _sessions(gui: Any, parent: Any) -> None:
    """The apprentice's own timetable: how the plan actually arrives."""
    box = widgets.section(parent, "Sessions coming up")
    ok, summary = widgets.guard(lambda: apprentice_service.get_own_record(gui.actor))
    if not ok:
        return
    programme_id = summary.apprentice.programme_id if summary else None
    if programme_id is None:
        # The timetable is not scoped per apprentice — an unfiltered call
        # would list every session the provider runs.
        widgets.empty_state(
            box, "You are not on a programme yet, so there is no timetable to show."
        )
        return
    ok, sessions = widgets.guard(lambda: training_service.list_sessions(
        gui.actor, programme_id=programme_id, upcoming_only=True
    ))
    if not ok:
        return
    if not sessions:
        widgets.empty_state(box, "Nothing is scheduled for your programme at the moment.")
        return
    table = widgets.DataTable(box, SESSION_COLUMNS, height=min(8, len(sessions)))
    table.populate(
        sessions,
        lambda s: (s.when, s.title, s.delivery_mode, s.location, s.trainer_name, s.otj_hours),
        identity=lambda s: s.session_id,
        noun="session",
    )
