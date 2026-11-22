"""Compliance — admin screen.

Eligibility, documents, functional skills, audit trail and retention.

Funding is conditional on paperwork, so the screen opens on what is
wrong rather than on a list of everybody: the flagged cohort first, one
apprentice's whole position behind it, and the administrator-only audit
and retention views on their own tabs.
"""

from __future__ import annotations

import logging
from datetime import date
from tkinter import ttk
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.interfaces.gui.windows.admin import audit_log
from education_system.systems.apprenticeships.application.apprentices import apprentice_service
from education_system.systems.apprenticeships.application.compliance import compliance_service
from education_system.systems.apprenticeships.application.records import document_service

logger = logging.getLogger(__name__)

TITLE = "Compliance"
SUBTITLE = "Eligibility, documents, functional skills, audit trail and retention."

_FLAG_COLUMNS = (
    ("apprentice", "Apprentice", 200),
    ("status", "Status", 130),
    ("employer", "Employer", 180),
    ("rag", "RAG", 70),
    ("outstanding", "Outstanding", 460),
)

_AUDIT_COLUMNS = (
    ("ts", "When", 150),
    ("actor", "Who", 130),
    ("role", "Role", 130),
    ("action", "Action", 90),
    ("entity", "Entity", 160),
    ("entity_id", "Id", 90),
    ("detail", "Detail", 420),
)

_RETENTION_COLUMNS = (
    ("apprentice", "Apprentice", 220),
    ("status", "Status", 130),
    ("ended", "Ended", 120),
    ("expiry", "Retention expired", 150),
)


def render(gui) -> None:
    """Draw the compliance screen into the content pane."""
    frame = gui.clear()
    widgets.heading(frame, TITLE, subtitle=SUBTITLE)

    if not gui.actor.can("compliance.view"):
        widgets.empty_state(frame, "Your role may not read the compliance position.")
        return

    notebook = ttk.Notebook(frame)
    notebook.pack(fill="both", expand=True)

    overview = ttk.Frame(notebook, padding=8)
    notebook.add(overview, text="Cohort")
    _overview(gui, overview)

    record = ttk.Frame(notebook, padding=8)
    notebook.add(record, text="One apprentice")
    _record_tab(gui, record)

    if gui.actor.is_admin:
        audit = ttk.Frame(notebook, padding=8)
        notebook.add(audit, text="Audit trail")
        _audit_tab(gui, audit)

        retention = ttk.Frame(notebook, padding=8)
        notebook.add(retention, text="Retention")
        _retention_tab(gui, retention)


# ═════════════════════════════════════════════════════════════════════
# Cohort
# ═════════════════════════════════════════════════════════════════════

def _overview(gui, parent: Any) -> None:
    ok, data = widgets.guard(lambda: compliance_service.compliance_dashboard(gui.actor))
    if not ok or data is None:
        return

    widgets.kpi_row(parent, [
        ("Cohort", data["total"]),
        ("Green", data["green"]),
        ("Amber", data["amber"]),
        ("Red", data["red"]),
    ])
    ttk.Label(
        parent,
        text="An apprentice who was never eligible, or whose training plan was never "
             "signed, is a clawback at audit however good the training was.",
        foreground=config.MUTED_FG, wraplength=900, justify="left",
    ).pack(anchor="w", pady=(0, 8))

    flagged = data["flagged"]
    if not flagged:
        widgets.empty_state(parent, "Nothing is flagged — every record is green.")
        return

    table = widgets.DataTable(parent, _FLAG_COLUMNS, height=min(14, len(flagged)))
    table.populate(
        flagged,
        lambda r: (r.get("apprentice_name"), r.get("status"), r.get("employer_name"),
                   r.get("rag"),
                   "; ".join([*r.get("failed_checks", []), *r.get("missing", [])])),
        identity=lambda r: r["apprentice_id"],
        tag=lambda r: r.get("rag"),
        noun="flag",
    )


# ═════════════════════════════════════════════════════════════════════
# One apprentice
# ═════════════════════════════════════════════════════════════════════

def _record_tab(gui, parent: Any) -> None:
    ok, summaries = widgets.guard(
        lambda: apprentice_service.list_apprentices(gui.actor)
    )
    if not ok or not summaries:
        widgets.empty_state(parent, "There are no apprentices to open.")
        return

    labels = {s.full_name: s.apprentice.apprentice_id for s in summaries}
    row = ttk.Frame(parent)
    row.pack(fill="x", pady=(0, 8))
    ttk.Label(row, text="Apprentice:").pack(side="left", padx=(0, 6))
    picker = ttk.Combobox(row, values=list(labels), state="readonly", width=34)
    picker.set(next(iter(labels)))
    picker.pack(side="left")

    body = ttk.Frame(parent)
    body.pack(fill="both", expand=True)

    def show(_event: Any = None) -> None:
        for child in body.winfo_children():
            child.destroy()
        _record(gui, body, labels[picker.get()], show)

    picker.bind("<<ComboboxSelected>>", show)
    ttk.Button(row, text="Refresh", command=show).pack(side="left", padx=(8, 0))
    show()


def _record(gui, parent: Any, apprentice_id: int, reload: Any) -> None:
    ok, status = widgets.guard(lambda: compliance_service.get_status(gui.actor, apprentice_id))
    if not ok or status is None:
        return

    widgets.kpi_row(parent, [
        ("RAG", status.rag_rating),
        ("Eligible", "Yes" if status.is_eligible else "No"),
        ("Audit ready", "Yes" if status.is_audit_ready else "No"),
        ("Eligibility", f"{status.eligibility_passed}/{len(status.eligibility)}"),
        ("Documents", f"{status.documents_signed}/{len(status.documents)}"),
        ("English & Maths", "Met" if status.functional_skills_satisfied else "Outstanding"),
    ])

    scroll = widgets.scrollable(parent)
    manage = gui.actor.can("compliance.manage")

    box = widgets.section(scroll, "Eligibility")
    checks = widgets.DataTable(box, (
        ("check", "Check", 320),
        ("passed", "Passed", 80),
        ("by", "Checked by", 140),
        ("when", "When", 110),
        ("evidence", "Evidence", 320),
    ), height=max(3, len(status.eligibility)))
    checks.populate(
        status.eligibility,
        lambda c: (c.label, c.passed, c.checked_by, c.checked_at, c.evidence),
        identity=lambda c: c.check_key,
        tag=lambda c: "Green" if c.passed else "Red",
        noun="check",
    )

    # The checklist is unchanged; alongside each item, any uploaded file
    # tagged as its evidence (Documents screen), so a "Signed" row can be
    # told apart from one with the paperwork actually on file.
    uploads: dict[str, list] = {}
    if gui.actor.can("document.view"):
        found_ok, found = widgets.guard(
            lambda: document_service.checklist_files(gui.actor, apprentice_id)
        )
        uploads = found if found_ok and found else {}

    def uploaded(doc_key: str, fallback: str | None) -> str | None:
        files = uploads.get(doc_key) or []
        if not files:
            return fallback
        latest = files[0]
        more = f" +{len(files) - 1} more" if len(files) > 1 else ""
        return f"{latest.title} (v{latest.version}, {latest.approval_status}){more}"

    box = widgets.section(scroll, "Documents")
    documents = widgets.DataTable(box, (
        ("document", "Document", 260),
        ("status", "Status", 140),
        ("issued", "Issued", 110),
        ("signed", "Signed", 110),
        ("expires", "Expires", 110),
        ("file", "Uploaded file", 220),
        ("notes", "Notes", 200),
    ), height=max(3, len(status.documents)))
    documents.populate(
        status.documents,
        lambda d: (d.label, f"{d.status}{' (expired)' if d.is_expired else ''}",
                   d.issued_date, d.signed_date, d.expiry_date,
                   uploaded(d.doc_key, d.file_name), d.notes),
        identity=lambda d: d.doc_key,
        tag=lambda d: "Green" if d.is_satisfactory else (
            "Red" if d.status == "Missing" or d.is_expired else "Amber"
        ),
        noun="document",
    )

    box = widgets.section(scroll, "English and Maths")
    skills = widgets.DataTable(box, (
        ("subject", "Subject", 120),
        ("status", "Status", 130),
        ("level", "Level", 120),
        ("achieved", "Achieved", 120),
        ("exemption", "Exemption", 300),
        ("satisfied", "Satisfies gateway", 140),
    ), height=max(2, len(status.functional_skills)))
    skills.populate(
        status.functional_skills,
        lambda s: (s.subject, s.status, s.level, s.achieved_date, s.exemption_reason,
                   s.is_satisfied),
        identity=lambda s: s.subject,
        tag=lambda s: "Green" if s.is_satisfied else "Amber",
        noun="subject",
    )

    if not manage:
        return
    widgets.button_bar(parent, [
        ("Set Eligibility Check…",
         lambda: _set_eligibility(gui, apprentice_id, checks, reload)),
        ("Set Document…", lambda: _set_document(gui, apprentice_id, documents, reload)),
        ("Set English / Maths…", lambda: _set_skill(gui, apprentice_id, skills, reload)),
    ])


def _set_eligibility(gui, apprentice_id: int, table: widgets.DataTable, reload: Any) -> None:
    labels = dict(config.ELIGIBILITY_CHECKS)
    selected = table.selected()
    fields = [
        {"key": "check_key", "label": "Check", "kind": "combo", "required": True,
         "options": [labels[key] for key, _ in config.ELIGIBILITY_CHECKS],
         "value": labels.get(selected or "", "")},
        {"key": "passed", "label": "Passes", "kind": "check", "value": True},
        {"key": "evidence", "label": "Evidence seen", "kind": "text",
         "help": "Who checked it and when are stamped from your login — at audit the "
                 "question is who attested to this."},
    ]
    by_label = {label: key for key, label in config.ELIGIBILITY_CHECKS}

    def save(values: dict[str, Any]) -> Any:
        return compliance_service.set_eligibility_check(
            gui.actor, apprentice_id, by_label[values["check_key"]],
            passed=bool(values["passed"]), evidence=values["evidence"],
        )

    if widgets.FormDialog(gui.root, "Record an eligibility check", fields, save).saved:
        reload()


def _set_document(gui, apprentice_id: int, table: widgets.DataTable, reload: Any) -> None:
    labels = dict(config.COMPLIANCE_DOCUMENTS)
    selected = table.selected()
    fields = [
        {"key": "doc_key", "label": "Document", "kind": "combo", "required": True,
         "options": [labels[key] for key, _ in config.COMPLIANCE_DOCUMENTS],
         "value": labels.get(selected or "", "")},
        {"key": "status", "label": "Status", "kind": "combo", "required": True,
         "options": config.DOCUMENT_STATUSES, "value": "Signed"},
        {"key": "issued_date", "label": "Issued", "help": "YYYY-MM-DD"},
        {"key": "signed_date", "label": "Signed",
         "help": "YYYY-MM-DD. Left blank on a Signed document, today is assumed."},
        {"key": "expiry_date", "label": "Expires", "help": "YYYY-MM-DD, where it lapses."},
        {"key": "notes", "label": "Notes", "kind": "text"},
    ]
    by_label = {label: key for key, label in config.COMPLIANCE_DOCUMENTS}

    def save(values: dict[str, Any]) -> Any:
        return compliance_service.set_document(
            gui.actor, apprentice_id, by_label[values["doc_key"]],
            status=values["status"], issued_date=values["issued_date"],
            signed_date=values["signed_date"], expiry_date=values["expiry_date"],
            notes=values["notes"],
        )

    if widgets.FormDialog(gui.root, "Record a document", fields, save).saved:
        reload()


def _set_skill(gui, apprentice_id: int, table: widgets.DataTable, reload: Any) -> None:
    fields = [
        {"key": "subject", "label": "Subject", "kind": "combo", "required": True,
         "options": config.FUNCTIONAL_SKILLS, "value": table.selected() or "English"},
        {"key": "status", "label": "Status", "kind": "combo", "required": True,
         "options": config.FUNCTIONAL_SKILL_STATUSES, "value": "Achieved"},
        {"key": "level", "label": "Level", "kind": "combo",
         "options": ("", *config.FUNCTIONAL_SKILL_LEVELS),
         "help": "Required for an achievement — Achieved satisfies gateway, so it "
                 "has to carry its evidence."},
        {"key": "achieved_date", "label": "Achieved", "value": date.today().isoformat(),
         "help": "YYYY-MM-DD"},
        {"key": "exemption_reason", "label": "Exemption reason", "kind": "combo",
         "options": ("", *config.EXEMPTION_REASONS),
         "help": "Required for an exemption, for the same reason."},
        {"key": "notes", "label": "Notes", "kind": "text"},
    ]

    def save(values: dict[str, Any]) -> Any:
        return compliance_service.set_functional_skill(
            gui.actor, apprentice_id, values["subject"],
            status=values["status"], level=values["level"],
            achieved_date=values["achieved_date"],
            exemption_reason=values["exemption_reason"], notes=values["notes"],
        )

    if widgets.FormDialog(gui.root, "Record English or Maths", fields, save).saved:
        reload()


# ═════════════════════════════════════════════════════════════════════
# Audit and retention
# ═════════════════════════════════════════════════════════════════════

def _audit_tab(gui, parent: Any) -> None:
    """The Audit Log screen's own panel, so the two can never disagree.

    Adds what this tab lacked: the before → after values of each edit,
    a date range, and a drill-down into one entry.
    """
    ttk.Label(
        parent,
        text="Administrators only: the log records what every user did, so a scoped "
             "view would still show a tutor who else touched those records.",
        foreground=config.MUTED_FG, wraplength=900, justify="left",
    ).pack(anchor="w", pady=(0, 8))
    audit_log.audit_panel(gui, parent)


def _retention_tab(gui, parent: Any) -> None:
    ttk.Label(
        parent,
        text=f"A completed apprentice's record is kept {config.RETENTION_YEARS} years "
             "for audit. These are past that and can be disposed of under your "
             "retention policy.",
        foreground=config.MUTED_FG, wraplength=900, justify="left",
    ).pack(anchor="w", pady=(0, 8))

    ok, rows = widgets.guard(lambda: compliance_service.retention_report(gui.actor))
    if not ok:
        return
    rows = rows or []
    if not rows:
        widgets.empty_state(parent, "Nothing is past its retention period.")
        return

    table = widgets.DataTable(parent, _RETENTION_COLUMNS)
    table.populate(
        rows,
        lambda r: (r.get("apprentice_name"), r.get("status"), r.get("actual_end_date"),
                   r.get("retention_expiry")),
        identity=lambda r: r["apprentice_id"],
        tag=lambda _r: "Amber",
        noun="record",
    )
