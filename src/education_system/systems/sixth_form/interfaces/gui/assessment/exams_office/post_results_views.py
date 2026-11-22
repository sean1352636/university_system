"""Exams Office tab: post-results services (reviews, scripts, consent, fees)."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import messagebox, simpledialog

from education_system.systems.sixth_form.domain.assessment.exam_entries.exam_entries import (
    EXAM_BOARDS,
    SEASONS,
)
from education_system.systems.sixth_form.domain.assessment.exams_office import (
    post_results as pr,
)
from education_system.systems.sixth_form.interfaces.gui.assessment.exams_office.exams_widgets import (
    guarded,
    ERROR_FG,
    FormField,
    SeriesBar,
    clear,
    form_dialog,
    money,
    run_action,
    selected_id,
    table,
    text_window,
    yn,
)

logger = logging.getLogger(__name__)


def _result_choices(season: str, year: int) -> dict[str, tuple[str, int]]:
    """Label -> ("result"|"qual", id) for every result in the series."""
    from education_system.systems.sixth_form.domain.assessment.exam_results import (
        exam_results as _results,
    )
    from education_system.systems.sixth_form.domain.assessment.exams_office import (
        results_day,
    )
    out: dict[str, tuple[str, int]] = {}
    for r in _results.list_results(season=season, year=year, released_only=False):
        out[f"{r.student_id} {r.student_name} — {r.paper_code} ({r.result.grade})"] = (
            "result", r.result.result_id)
    for q in results_day.list_qualification_results(season=season, year=year,
                                                    released_only=False):
        out[f"{q.student_id} {q.full_name or ''} — {q.entry_code} overall ({q.grade})"] = (
            "qual", q.qual_result_id)
    return out


def build_tab(gui, parent: ttk.Frame) -> None:
    top = ttk.Frame(parent)
    top.pack(fill="x", pady=(0, 6))
    actions = ttk.Frame(parent)
    actions.pack(fill="x", pady=(0, 6))
    holder = ttk.Frame(parent)
    holder.pack(fill="both", expand=True)
    state: dict = {}

    @guarded(gui.root)
    def refresh() -> None:
        clear(holder)
        try:
            season, year = series.get()
            rows = pr.list_requests(season=season, year=year)
        except ValueError as e:
            ttk.Label(holder, text=str(e), foreground=ERROR_FG).pack(anchor="w")
            return
        state["rows"] = {r.request_id: r for r in rows}
        state["tree"] = table(holder, [("#", 40), ("Student", 80), ("Name", 140),
                                       ("Code", 90), ("Service", 190), ("Deadline", 85),
                                       ("Consent", 55), ("Status", 110), ("Fee", 60),
                                       ("Was", 45), ("Outcome", 170), ("Now", 45),
                                       ("Refund", 50)],
                              [(r.request_id, r.student_id, r.full_name, r.code, r.service,
                                r.deadline + (" OVERDUE" if r.overdue else "")
                                if r.deadline else "", yn(r.consent_obtained), r.status,
                                money(r.fee), r.original_grade, r.outcome, r.new_grade,
                                yn(r.fee_refunded)) for r in rows],
                              iids=[r.request_id for r in rows])
        gui.status_var.set(f"{len(rows)} post-results request(s)")

    series = SeriesBar(top, on_change=refresh)

    @guarded(gui.root)
    def new() -> None:
        season, year = series.get()
        choices = _result_choices(season, year)
        if not choices:
            messagebox.showinfo("No results", "No results recorded for this series yet.",
                                parent=gui.root)
            return

        def submit(v: dict) -> None:
            kind, rid = choices[v.pop("target")]
            v["result_id" if kind == "result" else "qual_result_id"] = rid
            pr.create_request(v)

        form_dialog(gui.root, "New post-results request",
                    [FormField("target", "Result", "readonly", list(choices), 60),
                     FormField("service", "Service", "readonly", pr.SERVICES, 40),
                     FormField("consent_obtained", "Candidate consent received", "check"),
                     FormField("consent_ref", "Consent form reference"),
                     FormField("fee", "Fee (blank = fee list)"),
                     FormField("fee_paid_by", "Fee paid by (college / candidate)"),
                     FormField("notes", "Notes")],
                    submit, on_done=refresh)

    @guarded(gui.root)
    def consent() -> None:
        rid = selected_id(state["tree"], gui.root, "a request")
        if rid is None:
            return
        ref = simpledialog.askstring("Consent", "Consent form reference (optional):",
                                     parent=gui.root)
        run_action(gui.root, lambda: pr.record_consent(rid, consent_ref=ref or None),
                   then=refresh)

    @guarded(gui.root)
    def submit_req() -> None:
        rid = selected_id(state["tree"], gui.root, "a request")
        if rid is None:
            return
        ref = simpledialog.askstring("Submit", "Board reference (optional):",
                                     parent=gui.root)
        run_action(gui.root, lambda: pr.submit_request(rid, board_reference=ref or None),
                   then=refresh)

    @guarded(gui.root)
    def outcome() -> None:
        rid = selected_id(state["tree"], gui.root, "a request")
        if rid is None:
            return
        form_dialog(gui.root, f"Outcome for request #{rid}",
                    [FormField("outcome", "Outcome", "readonly", pr.OUTCOMES, 40),
                     FormField("new_grade", "New grade (if changed)"),
                     FormField("new_marks", "New marks"),
                     FormField("outcome_date", "Outcome date"),
                     FormField("notes", "Notes")],
                    lambda v: pr.record_outcome(rid, outcome=v["outcome"],
                                                new_grade=v["new_grade"] or None,
                                                new_marks=v["new_marks"] or None,
                                                outcome_date=v["outcome_date"] or None,
                                                notes=v["notes"] or None),
                    on_done=refresh,
                    note="A changed grade updates the result and is kept in its history.")

    @guarded(gui.root)
    def withdraw() -> None:
        rid = selected_id(state["tree"], gui.root, "a request")
        if rid is not None and messagebox.askyesno("Withdraw", "Withdraw this request?",
                                                   parent=gui.root):
            run_action(gui.root, lambda: pr.withdraw_request(rid), then=refresh)

    @guarded(gui.root)
    def fees() -> None:
        season, year = series.get()
        form_dialog(gui.root, "Post-results fee",
                    [FormField("exam_board", "Board", "readonly", EXAM_BOARDS),
                     FormField("season", "Season", "readonly", SEASONS),
                     FormField("year", "Year"),
                     FormField("service", "Service", "readonly", pr.SERVICES, 40),
                     FormField("fee", "Fee (£)")],
                    lambda v: pr.set_fee(v["exam_board"], v["season"], v["year"],
                                         v["service"], v["fee"]),
                    initial={"exam_board": EXAM_BOARDS[0], "season": season,
                             "year": year})

    @guarded(gui.root)
    def deadlines() -> None:
        season, year = series.get()
        lines = [f"POST-RESULTS DEADLINES — {season} {year}",
                 "(days after results day; JCQ common deadlines — check each year)", ""]
        for board, service, days, when in pr.deadlines_table(season, year):
            lines.append(f"{board:<18} {service:<36} +{days:<3} {when or '(no results day set)'}")
        lines += ["", "FEE LIST"]
        for f in pr.list_fees(year=year):
            lines.append(f"{f['exam_board']:<18} {f['season']} {f['year']}  "
                         f"{f['service']:<36} £{f['fee']:.2f}")
        text_window(gui.root, "Post-results deadlines", "\n".join(lines) + "\n",
                    filename=f"post_results_{season}{year}.txt")

    for label, cmd in (("New request", new), ("Consent received…", consent),
                       ("Submit to board…", submit_req), ("Record outcome…", outcome),
                       ("Withdraw", withdraw), ("Set fee…", fees),
                       ("Deadlines & fees…", deadlines)):
        ttk.Button(actions, text=label, command=cmd).pack(side="left", padx=(0, 6))
    refresh()
