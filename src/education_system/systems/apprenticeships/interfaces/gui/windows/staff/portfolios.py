"""Portfolio assessment: the submitted-evidence queue and the judgements on it."""

from __future__ import annotations

import logging
from tkinter import ttk

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.application.apprentices import apprentice_service
from education_system.systems.apprenticeships.application.assessments import portfolio_service

logger = logging.getLogger(__name__)

UNLINKED = (
    "Your login is not linked to a staff record, so no portfolios are routed to you "
    "for assessment. Ask an administrator to link your account to your staff profile "
    "— an unlinked login is not the same as an empty queue."
)

# Where an assessment decision may land. The other two evidence statuses
# belong to the apprentice, not the assessor.
OUTCOMES = ("Accepted", "Referred", "Rejected")

COLUMNS = (
    ("apprentice", "Apprentice", 180),
    ("title", "Evidence", 240),
    ("type", "Type", 160),
    ("ksbs", "KSBs mapped", 160),
    ("status", "Status", 110),
    ("submitted", "Submitted", 150),
)

MAPPING_COLUMNS = (
    ("code", "KSB", 80),
    ("type", "Type", 110),
    ("coverage", "Coverage", 120),
    ("description", "Statement", 380),
    ("note", "Assessor note", 240),
)

GAP_COLUMNS = (
    ("code", "KSB", 80),
    ("type", "Type", 110),
    ("coverage", "Coverage", 120),
    ("evidence", "Evidence mapped", 120, "e"),
    ("description", "Statement", 420),
)


def render(gui) -> None:
    """Evidence waiting on this assessor, with the whole portfolio behind it."""
    frame = gui.clear()
    widgets.heading(
        frame,
        "Portfolios",
        subtitle="Submitted evidence and the KSBs it claims to show.",
    )
    # Only a tutor needs a staff record; an admin works across the cohort.
    if gui.actor.role == config.STAFF and gui.actor.staff_id is None:
        widgets.empty_state(frame, UNLINKED)
        return

    names = _names(gui)
    body = ttk.Frame(frame)
    showing_all = {"value": False}

    def reload() -> None:
        for child in body.winfo_children():
            child.destroy()
        if showing_all["value"]:
            rows = portfolio_service.list_evidence(gui.actor, **bar.values())
            empty = "No evidence matches these filters."
        else:
            rows = portfolio_service.assessment_queue(gui.actor)
            empty = (
                "Nothing is waiting on your judgement. Evidence arrives here when an "
                "apprentice submits it."
            )
        if not rows:
            widgets.empty_state(body, empty)
            widgets.button_bar(body, [_mode_button(reload, showing_all)])
            return

        table = widgets.DataTable(
            body, COLUMNS,
            on_activate=lambda ident: _detail(gui, int(ident)),
        )
        table.populate(
            rows,
            lambda e: (
                names.get(e.apprentice_id, f"Apprentice {e.apprentice_id}"),
                e.title, e.evidence_type, ", ".join(e.ksb_codes),
                e.status, e.submitted_at,
            ),
            identity=lambda e: e.evidence_id,
            noun="item",
        )
        owners = {e.evidence_id: e.apprentice_id for e in rows}
        _actions(gui, body, table, owners, names, reload, showing_all)

    bar = widgets.FilterBar(
        frame,
        (
            ("status", "Status", "combo", config.EVIDENCE_STATUSES),
            ("evidence_type", "Type", "combo", config.EVIDENCE_TYPES),
        ),
        reload,
    )
    body.pack(fill="both", expand=True)
    reload()


def _mode_button(reload, showing_all: dict) -> tuple:
    """Toggle between the assessment queue and the full list.

    The filter bar only applies in full-list mode — the queue is defined
    as "submitted, mine", and a status filter over it would be a
    contradiction rather than a narrowing.
    """
    label = "Show Assessment Queue" if showing_all["value"] else "Show All Evidence"

    def toggle() -> None:
        showing_all["value"] = not showing_all["value"]
        reload()

    return (label, toggle)


def _actions(gui, parent, table, owners, names, reload, showing_all) -> None:
    """The buttons under the evidence list."""

    def open_detail() -> None:
        chosen = table.require_selection_int("open a piece of evidence")
        if chosen is not None:
            _detail(gui, chosen)

    def assess() -> None:
        chosen = table.require_selection_int("record an assessment decision")
        if chosen is not None:
            _assess_form(gui, chosen, on_saved=gui.refresh)

    def gaps() -> None:
        chosen = table.require_selection_int("see an apprentice's coverage gaps")
        if chosen is None:
            return
        apprentice_id = owners[chosen]
        _gaps(gui, apprentice_id, names.get(apprentice_id, f"Apprentice {apprentice_id}"))

    widgets.button_bar(parent, [
        ("Open", open_detail),
        ("Assess…", assess),
        ("Coverage Gaps", gaps),
        _mode_button(reload, showing_all),
    ])


# ═════════════════════════════════════════════════════════════════════
# One piece of evidence
# ═════════════════════════════════════════════════════════════════════

def _detail(gui, evidence_id: int) -> None:
    """One piece of evidence, its KSB claims, and the decisions open on it."""
    frame = gui.clear()
    ok, evidence = widgets.guard(lambda: portfolio_service.get_evidence(gui.actor, evidence_id))
    if not ok or evidence is None:
        widgets.button_bar(frame, [("← Back to portfolios", lambda: render(gui))])
        return

    names = _names(gui)
    owner = names.get(evidence.apprentice_id, f"Apprentice {evidence.apprentice_id}")
    widgets.heading(frame, evidence.title, subtitle=f"{owner} · {evidence.evidence_type}")
    widgets.field_grid(frame, [
        ("Status", evidence.status),
        ("Submitted", evidence.submitted_at),
        ("Assessed", evidence.assessed_at),
        ("File", evidence.file_name),
        ("Description", evidence.description),
        ("Assessor feedback", evidence.feedback),
    ], columns=2)

    mappings = evidence.mappings
    box = widgets.section(frame, "KSBs claimed")
    table: widgets.DataTable | None = None
    if mappings:
        table = widgets.DataTable(box, MAPPING_COLUMNS, height=8)
        table.populate(
            mappings,
            lambda m: (
                m.ksb_code, m.ksb_type, m.coverage, m.ksb_description, m.assessor_note,
            ),
            identity=lambda m: m.map_id,
            tag=lambda m: "Green" if m.coverage == "Competent" else None,
            noun="mapping",
        )
    else:
        widgets.empty_state(
            box,
            "This evidence is not mapped to any KSB, so accepting it would move "
            "nothing forward.",
        )

    def set_coverage() -> None:
        if table is None:
            widgets.warn("There are no KSB claims to judge on this evidence.")
            return
        chosen = table.require_selection_int("re-judge a KSB claim")
        if chosen is not None:
            _coverage_form(gui, evidence_id, chosen)

    buttons = []
    if gui.actor.can("portfolio.assess"):
        buttons.append(("Assess…", lambda: _assess_form(
            gui, evidence_id, on_saved=lambda: _detail(gui, evidence_id)
        )))
        buttons.append(("Set Coverage…", set_coverage))
    if gui.actor.can("portfolio.verify"):
        buttons.append(("Verify…", lambda: _verify_form(gui, evidence_id)))
    buttons.append(("← Back to portfolios", lambda: render(gui)))
    widgets.button_bar(frame, buttons)


def _assess_form(gui, evidence_id: int, *, on_saved) -> None:
    """Record an assessor's judgement."""
    fields = [
        {"key": "outcome", "label": "Outcome", "kind": "combo", "required": True,
         "options": OUTCOMES, "value": "Accepted"},
        {"key": "feedback", "label": "Feedback", "kind": "text",
         "help": "Required when referring or rejecting: the work goes back to the "
                 "apprentice, who cannot fix what they were not told about."},
    ]

    def save(values: dict) -> object:
        return portfolio_service.assess_evidence(
            gui.actor, evidence_id,
            outcome=values["outcome"], feedback=values["feedback"],
        )

    dialog = widgets.FormDialog(gui.root, "Assess evidence", fields, save)
    if dialog.saved:
        on_saved()


def _coverage_form(gui, evidence_id: int, map_id: int) -> None:
    """Re-judge how far one KSB claim goes."""
    fields = [
        {"key": "coverage", "label": "Coverage", "kind": "combo", "required": True,
         "options": config.KSB_COVERAGE_LEVELS, "value": "Competent"},
        {"key": "note", "label": "Assessor note", "kind": "text"},
    ]

    def save(values: dict) -> object:
        return portfolio_service.update_mapping(
            gui.actor, map_id, coverage=values["coverage"], note=values["note"]
        )

    dialog = widgets.FormDialog(gui.root, "Set KSB coverage", fields, save)
    if dialog.saved:
        # Back to the same detail pane: gui.refresh() would drop the
        # assessor out to the queue mid-way through judging one item.
        _detail(gui, evidence_id)


def _verify_form(gui, evidence_id: int) -> None:
    """Record an IQA sampling decision on an assessed item."""
    fields = [
        {"key": "outcome", "label": "Sampling outcome", "required": True,
         "help": "The IQA's decision on the assessor's judgement, e.g. 'Agreed'."},
        {"key": "comments", "label": "Comments", "kind": "text"},
    ]

    def save(values: dict) -> object:
        return portfolio_service.verify_evidence(
            gui.actor, evidence_id,
            outcome=values["outcome"], comments=values["comments"],
        )

    dialog = widgets.FormDialog(gui.root, "Verify assessment", fields, save)
    if dialog.saved:
        _detail(gui, evidence_id)


# ═════════════════════════════════════════════════════════════════════
# Coverage gaps
# ═════════════════════════════════════════════════════════════════════

def _gaps(gui, apprentice_id: int, name: str) -> None:
    """Everything this apprentice still has to evidence, worst first."""
    frame = gui.clear()
    widgets.heading(
        frame, f"Coverage gaps — {name}",
        subtitle="KSBs no accepted evidence has yet taken to competent.",
    )
    ok, gaps = widgets.guard(lambda: portfolio_service.coverage_gaps(gui.actor, apprentice_id))
    if ok and gaps:
        table = widgets.DataTable(frame, GAP_COLUMNS)
        table.populate(
            gaps,
            lambda c: (
                c.ksb.code, c.ksb.ksb_type, c.coverage, c.evidence_count, c.ksb.description,
            ),
            identity=lambda c: c.ksb.ksb_id,
            tag=lambda c: "Red" if c.coverage == "Not started" else "Amber",
            noun="KSB",
        )
    elif ok:
        widgets.empty_state(
            frame,
            "Every KSB on this standard is competent — the portfolio gateway "
            "requirement is met.",
        )
    widgets.button_bar(frame, [("← Back to portfolios", lambda: render(gui))])


def _names(gui) -> dict[int, str]:
    """Apprentice ids to names: evidence carries only the id."""
    return {
        s.apprentice.apprentice_id: s.full_name
        for s in apprentice_service.list_apprentices(gui.actor)
    }
