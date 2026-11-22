"""Portfolio — apprentice screen.

Your evidence and how far it takes each KSB.

The coverage roll-up sits above the evidence list rather than beside it,
because "which KSBs am I still missing?" is the question this screen
exists to answer — the list of what has already been uploaded is how you
answer it, not the point in itself.

'Competent' is deliberately absent from the coverage dropdown. It is the
assessor's judgement and the one gateway reads, so offering it here
would produce a refusal after the apprentice had filled the form in.
"""

from __future__ import annotations

import logging
from tkinter import ttk
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.application.assessments import portfolio_service
from education_system.systems.apprenticeships.application.programmes import programme_service

logger = logging.getLogger(__name__)

TITLE = "Portfolio"
SUBTITLE = "Your evidence, and how far it takes each of your KSBs."

UNLINKED = (
    "Your sign-in is not linked to an apprentice record yet, so there is no portfolio "
    "to show. Ask your training provider's administrator to link your account."
)

_EVIDENCE_COLUMNS = (
    ("title", "Title", 260),
    ("type", "Type", 170),
    ("ksbs", "KSBs claimed", 170),
    ("status", "Status", 110),
    ("submitted", "Submitted", 140),
    ("feedback", "Assessor feedback", 320),
)

_COVERAGE_COLUMNS = (
    ("code", "KSB", 80),
    ("type", "Type", 110),
    ("coverage", "Coverage", 120),
    ("evidence", "Evidence", 90, "e"),
    ("description", "What you have to show", 520),
)

_STATUS_TAGS = {
    "Accepted": "Green", "Submitted": "Amber", "Referred": "Amber", "Rejected": "Red",
}


def render(gui) -> None:
    """Draw the portfolio screen into the content pane."""
    frame = gui.clear()
    widgets.heading(frame, TITLE, subtitle=SUBTITLE)

    apprentice_id = gui.actor.apprentice_id
    if apprentice_id is None:
        widgets.empty_state(frame, UNLINKED)
        return

    ok, summary = widgets.guard(
        lambda: portfolio_service.get_portfolio(gui.actor, apprentice_id)
    )
    if not ok or summary is None:
        return

    widgets.kpi_row(frame, [
        ("Competent", summary.competent_ksbs),
        ("Developing", summary.developing_ksbs),
        ("Not started", summary.not_started_ksbs),
        ("Evidence items", len(summary.evidence)),
        ("Accepted", summary.accepted_count),
        ("With your assessor", len(summary.awaiting_assessment)),
    ])
    widgets.progress_row(
        frame, "KSBs judged competent", summary.percent_competent,
        detail=f"{summary.competent_ksbs} of {summary.total_ksbs}",
        rag="Green" if summary.is_complete else "Amber",
    )

    notebook = ttk.Notebook(frame)
    notebook.pack(fill="both", expand=True, pady=(10, 0))

    evidence_tab = ttk.Frame(notebook, padding=8)
    notebook.add(evidence_tab, text="My evidence")
    _evidence(gui, evidence_tab, apprentice_id)

    coverage_tab = ttk.Frame(notebook, padding=8)
    notebook.add(coverage_tab, text="Coverage")
    _coverage(coverage_tab, summary.coverage, "Every KSB on your standard.")

    gaps_tab = ttk.Frame(notebook, padding=8)
    notebook.add(gaps_tab, text=f"Still to show ({len(summary.gaps)})")
    _coverage(
        gaps_tab, summary.gaps,
        "The KSBs no accepted evidence has taken to competent yet. Gateway checks "
        "this list, so it has to be empty before you can be put forward.",
    )


# ═════════════════════════════════════════════════════════════════════
# Evidence
# ═════════════════════════════════════════════════════════════════════

def _evidence(gui, parent: Any, apprentice_id: int) -> None:
    filters = widgets.FilterBar(
        parent, (("status", "Status", "combo", config.EVIDENCE_STATUSES),),
        lambda: reload(),
    )
    table = widgets.DataTable(parent, _EVIDENCE_COLUMNS, height=12)
    items: dict[int, Any] = {}

    def reload() -> None:
        loaded, rows = widgets.guard(lambda: portfolio_service.list_evidence(
            gui.actor, apprentice_id=apprentice_id, **filters.values()
        ))
        rows = (rows or []) if loaded else []
        items.clear()
        items.update({item.evidence_id: item for item in rows})
        table.populate(
            rows,
            lambda e: (e.title, e.evidence_type, ", ".join(e.ksb_codes), e.status,
                       e.submitted_at, e.feedback),
            identity=lambda e: e.evidence_id,
            tag=lambda e: _STATUS_TAGS.get(e.status),
            noun="item",
        )
        if not rows:
            table.count_var.set(
                "Nothing here yet. Add the work you have done and map it to the KSBs "
                "it shows."
            )

    def chosen(action: str) -> Any | None:
        evidence_id = table.require_selection_int(action)
        return items.get(evidence_id) if evidence_id is not None else None

    def add() -> None:
        dialog = widgets.FormDialog(
            parent, "Add evidence", _fields(None),
            lambda values: portfolio_service.add_evidence(gui.actor, values),
            intro="Saved as a draft. Map it to the KSBs it shows, then submit it — "
                  "nothing counts until your assessor has accepted it.",
            save_label="Save draft",
        )
        if dialog.saved:
            gui.refresh()

    def edit() -> None:
        item = chosen("edit it")
        if item is None:
            return
        if not item.is_editable:
            widgets.warn(
                f"This is {item.status.lower()} and cannot be changed. Submitted work "
                "is with your assessor; accepted work is locked because the KSBs it "
                "covers depend on it.",
                title="Locked",
            )
            return
        dialog = widgets.FormDialog(
            parent, f"Edit “{item.title}”", _fields(item),
            lambda values: portfolio_service.update_evidence(
                gui.actor, item.evidence_id, values
            ),
        )
        if dialog.saved:
            gui.refresh()

    def submit() -> None:
        item = chosen("submit it")
        if item is None:
            return
        if not item.mappings and not widgets.confirm(
            "This item does not claim any KSB, so accepting it would move nothing "
            "forward.\n\nSubmit it anyway?",
            title="No KSBs claimed",
        ):
            return
        ok, _ = widgets.guard(
            lambda: portfolio_service.submit_evidence(gui.actor, item.evidence_id)
        )
        if ok:
            gui.refresh()

    def delete() -> None:
        item = chosen("delete it")
        if item is None:
            return
        if not widgets.confirm(
            f"Delete “{item.title}” and the KSB claims on it?", title="Delete evidence"
        ):
            return
        ok, _ = widgets.guard(
            lambda: portfolio_service.delete_evidence(gui.actor, item.evidence_id)
        )
        if ok:
            gui.refresh()

    def mappings() -> None:
        item = chosen("map it to a KSB")
        if item is not None:
            _mappings(gui, item, apprentice_id)

    if gui.actor.can("portfolio.upload"):
        widgets.button_bar(parent, [
            ("Add Evidence", add),
            ("Edit", edit),
            ("Map to KSBs…", mappings),
            ("Submit", submit),
            ("Delete", delete),
        ])
    reload()


def _mappings(gui, evidence: Any, apprentice_id: int) -> None:
    """The KSB claims on one item, and what can still be added."""
    frame = gui.clear()
    widgets.heading(
        frame, f"KSBs claimed — {evidence.title}",
        subtitle="Which parts of your standard this piece of evidence shows.",
    )

    table = widgets.DataTable(frame, (
        ("code", "KSB", 80),
        ("type", "Type", 110),
        ("coverage", "Coverage", 120),
        ("description", "Statement", 460),
        ("note", "Assessor note", 280),
    ), height=10)
    table.populate(
        evidence.mappings,
        lambda m: (m.ksb_code, m.ksb_type, m.coverage, m.ksb_description, m.assessor_note),
        identity=lambda m: m.map_id,
        tag=lambda m: "Green" if m.coverage == "Competent" else None,
        noun="claim",
    )
    if not evidence.mappings:
        widgets.empty_state(
            frame,
            "No KSB is claimed yet, so accepting this would move nothing forward.",
        )

    def add() -> None:
        _map_form(gui, evidence, apprentice_id)

    def remove() -> None:
        map_id = table.require_selection_int("withdraw a claim")
        if map_id is None:
            return
        if not widgets.confirm("Withdraw this KSB claim?", title="Withdraw claim"):
            return
        ok, _ = widgets.guard(lambda: portfolio_service.unmap_ksb(gui.actor, map_id))
        if ok:
            _reopen(gui, evidence.evidence_id, apprentice_id)

    widgets.button_bar(frame, [
        ("Claim a KSB…", add),
        ("Withdraw Claim", remove),
        ("← Back to portfolio", lambda: render(gui)),
    ])


def _map_form(gui, evidence: Any, apprentice_id: int) -> None:
    """Claim that this evidence shows a KSB."""
    ok, apprentice = widgets.guard(lambda: _apprentice(gui, apprentice_id))
    if not ok or apprentice is None or apprentice.apprentice.programme_id is None:
        widgets.warn(
            "There is no programme on your record yet, so there are no KSBs to map to.",
            title="No programme",
        )
        return

    ok, ksbs = widgets.guard(lambda: programme_service.list_ksbs(
        gui.actor, apprentice.apprentice.programme_id
    ))
    if not ok:
        return
    claimed = {m.ksb_id for m in evidence.mappings}
    available = {
        f"{k.code} ({k.ksb_type}) — {k.description[:60]}": k.ksb_id
        for k in (ksbs or []) if k.ksb_id not in claimed
    }
    if not available:
        widgets.inform(
            "Every KSB on your standard is already claimed by this item.",
            title="Nothing left to claim",
        )
        return

    # Competent is the assessor's call and the one gateway reads, so it is
    # not on offer here — see the module docstring.
    levels = [level for level in config.KSB_COVERAGE_LEVELS if level != "Competent"]
    fields = [
        {"key": "ksb", "label": "KSB", "kind": "combo", "required": True,
         "options": list(available)},
        {"key": "coverage", "label": "How far it takes it", "kind": "combo",
         "required": True, "options": levels, "value": "Developing",
         "help": "Your assessor decides whether a claim reaches Competent."},
        {"key": "note", "label": "Note", "kind": "text"},
    ]

    def save(values: dict[str, Any]) -> Any:
        return portfolio_service.map_to_ksb(
            gui.actor, evidence.evidence_id, available[values["ksb"]],
            coverage=values["coverage"], note=values["note"],
        )

    if widgets.FormDialog(gui.root, "Claim a KSB", fields, save).saved:
        _reopen(gui, evidence.evidence_id, apprentice_id)


def _reopen(gui, evidence_id: int, apprentice_id: int) -> None:
    """Re-read the item and redraw its mapping pane.

    Back to the same pane rather than ``gui.refresh()``, which would drop
    the apprentice out to the portfolio mid-way through mapping one item.
    """
    ok, evidence = widgets.guard(
        lambda: portfolio_service.get_evidence(gui.actor, evidence_id)
    )
    if ok and evidence is not None:
        _mappings(gui, evidence, apprentice_id)
    else:
        render(gui)


# ═════════════════════════════════════════════════════════════════════
# Coverage
# ═════════════════════════════════════════════════════════════════════

def _coverage(parent: Any, rows: list, blurb: str) -> None:
    ttk.Label(
        parent, text=blurb, foreground=config.MUTED_FG, wraplength=900, justify="left",
    ).pack(anchor="w", pady=(0, 8))
    if not rows:
        widgets.empty_state(
            parent,
            "Every KSB on your standard is competent — the portfolio requirement for "
            "gateway is met.",
        )
        return
    table = widgets.DataTable(parent, _COVERAGE_COLUMNS, height=14)
    table.populate(
        rows,
        lambda c: (c.ksb.code, c.ksb.ksb_type, c.coverage, c.evidence_count,
                   c.ksb.description),
        identity=lambda c: c.ksb.ksb_id,
        tag=lambda c: {"Competent": "Green", "Developing": "Amber"}.get(c.coverage, "Red"),
        noun="KSB",
    )


def _apprentice(gui, apprentice_id: int) -> Any:
    from education_system.systems.apprenticeships.application.apprentices import apprentice_service

    return apprentice_service.get_apprentice(gui.actor, apprentice_id)


def _fields(evidence: Any | None) -> list[dict[str, Any]]:
    return [
        {"key": "title", "label": "Title", "required": True,
         "value": evidence.title if evidence else "",
         "help": "What the work was, in a few words."},
        {"key": "evidence_type", "label": "Type", "kind": "combo", "required": True,
         "options": config.EVIDENCE_TYPES,
         "value": evidence.evidence_type if evidence else ""},
        {"key": "description", "label": "Description", "kind": "text",
         "value": (evidence.description if evidence else "") or "",
         "help": "Your assessor reads this — say what you did and what it shows."},
        {"key": "file_name", "label": "Attached file",
         "value": (evidence.file_name if evidence else "") or "",
         "help": "The name of the document, photo or recording you are handing over."},
    ]
