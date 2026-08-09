"""Reports — admin screen.

Cohort, programme, employer and funding-audit reporting.

One screen with a report picker rather than four screens, because these
are read one after another in the same sitting — a programme manager
checks the cohort, then which programme the drift is in, then which
employer. Making that three clicks through a sidebar would put the
comparison a page apart.
"""

from __future__ import annotations

import logging
from tkinter import ttk
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.services import (
    apprentice_service,
    compliance_service,
    reporting_service,
)

logger = logging.getLogger(__name__)

TITLE = "Reports"
SUBTITLE = "Cohort, programme, employer and funding-audit reporting."

_PROGRAMME_COLUMNS = (
    ("reference", "Reference", 100),
    ("title", "Programme", 240),
    ("level", "Level", 70, "e"),
    ("active", "Active", 80, "e"),
    ("total", "Total", 70, "e"),
    ("completed", "Completed", 90, "e"),
    ("withdrawn", "Withdrawn", 90, "e"),
    ("behind", "Behind", 80, "e"),
    ("ksbs", "KSBs", 70, "e"),
    ("achievement", "Achievement", 100, "e"),
)

_EMPLOYER_COLUMNS = (
    ("employer", "Employer", 250),
    ("active", "Active", 80, "e"),
    ("total", "Total", 70, "e"),
    ("completed", "Completed", 90, "e"),
    ("withdrawn", "Withdrawn", 90, "e"),
    ("retention", "Retention", 90, "e"),
    ("approvals", "Approvals waiting", 130, "e"),
    ("satisfaction", "Satisfaction", 100, "e"),
)

_COUNT_COLUMNS = (("label", "", 320), ("count", "Apprentices", 110, "e"))


def render(gui) -> None:
    """Draw the reports screen into the content pane."""
    frame = gui.clear()
    widgets.heading(frame, TITLE, subtitle=SUBTITLE)

    if not gui.actor.can("report.view"):
        widgets.empty_state(frame, "Your role may not read the provider's reports.")
        return

    reports: dict[str, Any] = {
        "Cohort statistics": _cohort,
        "Programme report": _programmes,
        "Employer report": _employers,
    }
    if gui.actor.is_provider and gui.actor.can("compliance.view"):
        reports["Funding evidence pack"] = _evidence_pack

    body = ttk.Frame(frame)
    chooser = ttk.Frame(frame)
    chooser.pack(fill="x", pady=(0, 8))
    ttk.Label(chooser, text="Report:").pack(side="left", padx=(0, 6))
    picker = ttk.Combobox(
        chooser, values=list(reports), state="readonly", width=30
    )
    picker.set(next(iter(reports)))
    picker.pack(side="left")

    def show(_event: Any = None) -> None:
        for child in body.winfo_children():
            child.destroy()
        reports[picker.get()](gui, body)

    picker.bind("<<ComboboxSelected>>", show)
    ttk.Button(chooser, text="Refresh", command=show).pack(side="left", padx=(8, 0))
    _export_control(gui, chooser)

    body.pack(fill="both", expand=True)
    show()


def _export_control(gui, parent: Any) -> None:
    """Write any of the reports out as CSV for somebody outside the system."""
    ttk.Label(parent, text="Export:").pack(side="left", padx=(24, 6))
    kinds = ttk.Combobox(
        parent, values=list(reporting_service.EXPORTS), state="readonly", width=14
    )
    kinds.set(next(iter(reporting_service.EXPORTS)))
    kinds.pack(side="left")

    def export() -> None:
        ok, path = widgets.guard(
            lambda: reporting_service.export_csv(gui.actor, kinds.get()), title="Export"
        )
        if ok and path is not None:
            widgets.inform(f"Written to\n\n{path}", title="Exported")
            gui.status_var.set(f"Exported {kinds.get()} to {path.name}")

    ttk.Button(parent, text="Export CSV", command=export).pack(side="left", padx=(6, 0))


# ═════════════════════════════════════════════════════════════════════
# Cohort
# ═════════════════════════════════════════════════════════════════════

def _cohort(gui, parent: Any) -> None:
    ok, stats = widgets.guard(lambda: apprentice_service.cohort_statistics(gui.actor))
    if not ok or stats is None:
        return

    widgets.kpi_row(parent, [
        ("Total", stats["total"]),
        ("Active", stats["active"]),
        ("At gateway", stats["at_gateway"]),
        ("Completed", stats["completed"]),
        ("Withdrawn", stats["withdrawn"]),
        ("Behind on off-the-job", stats["behind_on_otj"]),
    ])

    scroll = widgets.scrollable(parent)
    _counts(scroll, "By status", list(stats["by_status"].items()))
    _counts(scroll, "By programme", stats["by_programme"])
    _counts(scroll, "By employer", stats["by_employer"])

    box = widgets.section(scroll, "Behind on off-the-job hours")
    behind = stats["behind_list"]
    if not behind:
        widgets.empty_state(box, "Everybody is holding the pace.")
        return
    table = widgets.DataTable(box, (
        ("name", "Apprentice", 200),
        ("programme", "Programme", 220),
        ("employer", "Employer", 180),
        ("status", "Status", 120),
        ("otj", "Off-the-job", 100, "e"),
        ("elapsed", "Elapsed", 90, "e"),
    ), height=min(12, len(behind)))
    table.populate(
        behind,
        lambda s: (s.full_name, s.programme_title, s.employer_name, s.apprentice.status,
                   widgets.percent(s.otj_percent), widgets.percent(s.progress_percent)),
        identity=lambda s: s.apprentice.apprentice_id,
        tag=lambda _s: "Amber",
        noun="apprentice",
    )


def _counts(parent: Any, heading: str, pairs: list) -> None:
    box = widgets.section(parent, heading)
    rows = list(pairs)
    if not rows:
        widgets.empty_state(box, "Nothing to count yet.")
        return
    table = widgets.DataTable(box, _COUNT_COLUMNS, height=min(10, len(rows)))
    table.populate(
        rows,
        lambda pair: (pair[0], pair[1]),
        identity=lambda pair: pair[0],
        noun="row",
    )


# ═════════════════════════════════════════════════════════════════════
# Programmes and employers
# ═════════════════════════════════════════════════════════════════════

def _programmes(gui, parent: Any) -> None:
    ok, rows = widgets.guard(lambda: reporting_service.programme_report(gui.actor))
    if not ok:
        return
    rows = rows or []
    table = widgets.DataTable(parent, _PROGRAMME_COLUMNS)
    table.populate(
        rows,
        lambda r: (r["programme"].reference, r["programme"].title, r["programme"].level,
                   r["active"], r["total"], r["completed"], r["withdrawn"], r["behind"],
                   r["ksb_count"], widgets.percent(r["achievement_rate"])),
        identity=lambda r: r["programme"].programme_id,
        tag=lambda r: "Amber" if r["behind"] else None,
        noun="programme",
    )
    if not rows:
        widgets.empty_state(parent, "No programmes are defined yet.")


def _employers(gui, parent: Any) -> None:
    ok, rows = widgets.guard(lambda: reporting_service.employer_report(gui.actor))
    if not ok:
        return
    rows = rows or []
    table = widgets.DataTable(parent, _EMPLOYER_COLUMNS)
    table.populate(
        rows,
        lambda r: (r["employer"].name, r["active"], r["total"], r["completed"],
                   r["withdrawn"], widgets.percent(r["retention"]),
                   r["pending_approvals"], _score(r["satisfaction"])),
        identity=lambda r: r["employer"].employer_id,
        tag=lambda r: "Amber" if r["pending_approvals"] else None,
        noun="employer",
    )
    if not rows:
        widgets.empty_state(parent, "No employers are on the books yet.")


def _score(value: float | None) -> str:
    return widgets.EMPTY if value is None else f"{value:.2f} / 5"


# ═════════════════════════════════════════════════════════════════════
# Funding evidence pack
# ═════════════════════════════════════════════════════════════════════

def _evidence_pack(gui, parent: Any) -> None:
    """Everything a funding audit asks for about one apprentice."""
    ok, summaries = widgets.guard(
        lambda: apprentice_service.list_apprentices(gui.actor)
    )
    if not ok or not summaries:
        widgets.empty_state(parent, "There are no apprentices to assemble a pack for.")
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

    def build(_event: Any = None) -> None:
        for child in body.winfo_children():
            child.destroy()
        ok, pack = widgets.guard(
            lambda: compliance_service.evidence_pack(gui.actor, labels[picker.get()]),
            title="Evidence pack",
        )
        if ok and pack is not None:
            _render_pack(body, pack)

    picker.bind("<<ComboboxSelected>>", build)
    ttk.Button(row, text="Assemble", command=build).pack(side="left", padx=(8, 0))
    build()


def _render_pack(parent: Any, pack: dict[str, Any]) -> None:
    scroll = widgets.scrollable(parent)
    person = pack["apprentice"]
    compliance = pack["compliance"]
    hours = pack["off_the_job"]

    ttk.Label(
        scroll,
        text=f"Assembled {pack['generated_at']} by {pack['generated_by']}",
        foreground=config.MUTED_FG,
    ).pack(anchor="w", pady=(0, 6))

    box = widgets.section(scroll, "Apprentice")
    widgets.field_grid(box, [
        ("ULN", person["uln"]),
        ("Date of birth", person["date_of_birth"]),
        ("Status", person["status"]),
        ("Programme", f"{person['programme_reference'] or ''} "
                      f"{person['programme'] or ''}".strip()),
        ("Level", person["level"]),
        ("Employer", person["employer"]),
        ("Tutor", person["tutor"]),
        ("Funding model", person["funding_model"]),
        ("Weekly hours", person["weekly_hours"]),
        ("Started", person["start_date"]),
        ("Planned end", person["planned_end_date"]),
        ("Actual end", person["actual_end_date"]),
        ("Retention expiry", pack["retention_expiry"]),
    ], columns=4)

    box = widgets.section(scroll, "Compliance")
    widgets.field_grid(box, [
        ("RAG", compliance["rag"]),
        ("Eligible", compliance["is_eligible"]),
        ("Audit ready", compliance["is_audit_ready"]),
        ("Eligibility", f"{compliance['eligibility_passed']}"
                        f"/{compliance['eligibility_total']}"),
        ("Documents signed", f"{compliance['documents_signed']}"
                             f"/{compliance['documents_total']}"),
        ("Failed checks", "; ".join(compliance["failed_checks"])),
        ("Missing documents", "; ".join(compliance["missing_documents"])),
        ("Missing pre-start", "; ".join(compliance["missing_pre_start"])),
        ("Expired documents", "; ".join(compliance["expired_documents"])),
    ], columns=3)

    box = widgets.section(scroll, "Off-the-job hours")
    widgets.field_grid(box, [
        ("Target", hours["target_hours"]),
        ("Approved", hours["approved_hours"]),
        ("Pending", hours["pending_hours"]),
        ("Shortfall", hours["shortfall_hours"]),
        ("Target met", hours["target_met"]),
        ("Entries", hours["entry_count"]),
        ("Reviews signed", pack["reviews"]["signed"]),
        ("Reviews outstanding", pack["reviews"]["outstanding"]),
    ], columns=4)

    box = widgets.section(scroll, "Gateway")
    widgets.field_grid(box, [
        ("Status", pack["gateway"]["status"]),
        ("Requested", pack["gateway"]["requested_at"]),
        ("Requested by", pack["gateway"]["requested_by"]),
        ("Decided", pack["gateway"]["decided_at"]),
        ("Decided by", pack["gateway"]["decided_by"]),
        ("Notes", pack["gateway"]["decision_notes"]),
    ], columns=3)

    box = widgets.section(scroll, "English and Maths")
    skills = pack["functional_skills"]
    if skills:
        table = widgets.DataTable(box, (
            ("subject", "Subject", 120),
            ("status", "Status", 130),
            ("level", "Level", 120),
            ("achieved", "Achieved", 120),
            ("satisfied", "Satisfies gateway", 140),
        ), height=len(skills))
        table.populate(
            skills,
            lambda s: (s["subject"], s["status"], s["level"], s["achieved_date"],
                       s["is_satisfied"]),
            identity=lambda s: s["subject"],
            tag=lambda s: "Green" if s["is_satisfied"] else "Red",
            noun="subject",
        )
    else:
        widgets.empty_state(box, "Nothing recorded.")

    box = widgets.section(scroll, "End-point assessment")
    results = pack["epa"]["results"]
    if results:
        table = widgets.DataTable(box, (
            ("method", "Method", 230),
            ("grade", "Grade", 110),
            ("assessed", "Assessed", 120),
            ("attempt", "Attempt", 90, "e"),
            ("pass", "Pass", 80),
        ), height=min(8, len(results)))
        table.populate(
            results,
            lambda r: (r["method"], r["grade"], r["assessed_date"], r["attempt"],
                       r["is_pass"]),
            identity=lambda r: f"{r['method']}-{r['attempt']}",
            tag=lambda r: "Green" if r["is_pass"] else "Red",
            noun="result",
        )
    else:
        widgets.empty_state(box, "No results recorded.")
