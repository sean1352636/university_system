"""Results Analysis screen.

Filters: what to analyse (an assessment point, mock series or exam
series), Year, Form, Subject, and an optional second source to compare
with (e.g. the mock against the real results). Run works it out in the
background. Tabs: Headline, Subjects (averages, % 4+ / 5+ / 7+, against
target, residuals - with a chart), Grade distribution, Against target,
Groups, Pupils, Compare and Attainment 8 / P8 (from the headline measures,
for a chosen year group, school year and A8 source). Every tab exports to
CSV; pupil tabs open the pupil or their grades. Rules:
:mod:`modules.reporting.domain.results_analysis`.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

from education_system.systems.secondary.modules.assessment.domain import headline_measures as HM
from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.modules.reporting.domain import results_analysis as RA
from education_system.systems.secondary.modules.reporting.gui import report_widgets as RW
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.core.academic_calendar.school_year import current_year
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.gui.components import widgets as W

_COMPARE = "compare"


class _Bar:
    """The results filters (same interface as RW.FilterBar)."""

    def __init__(self, page: "ResultsAnalysisPage", parent: ttk.Frame) -> None:
        st = page.state
        self.state = st
        try:
            page.sources = RA.sources(page.principal)
        except W.ERRORS:
            page.sources = []
        labels = [""] + [f"{s.label} - {s.detail}" for s in page.sources]
        self.by_label = {f"{s.label} - {s.detail}": s.key for s in page.sources}
        try:
            subs = S.list_subjects()
        except Exception:  # noqa: BLE001 - no subjects yet
            subs = []
        self.subjects = {f"{s.code} {s.name}": s.subject_id for s in subs}
        row1, row2 = ttk.Frame(parent), ttk.Frame(parent)
        row1.pack(fill="x", pady=(0, 4))
        row2.pack(fill="x", pady=(0, 6))
        self.bar = row1
        self.vars: dict[str, tk.StringVar] = {}

        def combo(frame, key, label, values, width, readonly=True, default=""):
            ttk.Label(frame, text=label).pack(side="left")
            v = tk.StringVar(value=st.get(key, default))
            ttk.Combobox(frame, textvariable=v, values=values, width=width,
                         state="readonly" if readonly else "normal").pack(side="left",
                                                                         padx=(2, 8))
            self.vars[key] = v
        first = labels[1] if len(labels) > 1 else ""
        combo(row1, "source", "Analyse:", labels, 46, default=first)
        combo(row1, "year", "Year:", RW.YEARS, 4)
        combo(row1, "form", "Form:", [""], 7, readonly=False)
        combo(row1, "subject", "Subject:", ["", *self.subjects], 22)
        self.run_button = ttk.Button(row1, text="Run", command=page.run)
        self.run_button.pack(side="left", padx=2)
        combo(row2, "compare", "Compare with:", labels, 46)
        combo(row2, "a8_year", "A8/P8 year:", [str(y) for y in (11, 10, 9, 8, 7)], 4,
              default="11")
        combo(row2, "a8_school_year", "School year:", [current_year()], 9, readonly=False,
              default=current_year())
        combo(row2, "a8_source", "A8 source:", list(HM.SOURCES), 10, default="Actual")

    def get(self) -> dict[str, str]:
        out = {k: v.get().strip() for k, v in self.vars.items()}
        self.state.update(out)
        out["source_key"] = self.by_label.get(out["source"], "")
        out["compare_key"] = self.by_label.get(out["compare"], "")
        out["subject_id"] = str(self.subjects.get(out["subject"], ""))
        return out

    def busy(self, on: bool) -> None:
        self.run_button.state(["disabled"] if on else ["!disabled"])


class ResultsAnalysisPage(RW.ReportPage):
    TITLE = "Results Analysis"
    LOG = "results_analysis"
    TABS = {"Headline": "headline", "Subjects": "subjects",
            "Grade distribution": "distribution", "Against target": "targets",
            "Groups": "groups", "Pupils": "pupils", "Compare": _COMPARE,
            "Attainment 8 / P8": "a8p8"}
    PUPIL_TABS = frozenset({"Against target", "Pupils", "Compare"})

    def __init__(self, parent, **kw) -> None:
        activity_log.record("results_analysis.view")
        self.sources: list[RA.Source] = []
        self.compare_detail = tk.BooleanVar(value=True)
        super().__init__(parent, **kw)

    def build_filters(self, parent: ttk.Frame) -> None:
        self.filters = _Bar(self, parent)

    def compute(self, f: dict[str, str]) -> dict[str, Any]:
        out: dict[str, Any] = {"analysis": None, "compare": None, "a8": None}
        if f["source_key"]:
            out["analysis"] = RA.analyse(self.principal, f["source_key"],
                                         year_group=f["year"] or None,
                                         subject_id=f["subject_id"] or None,
                                         form=f["form"] or None)
            if f["compare_key"] and f["compare_key"] != f["source_key"]:
                out["compare"] = RA.compare(self.principal, f["source_key"], f["compare_key"],
                                            year_group=f["year"] or None,
                                            subject_id=f["subject_id"] or None)
        out["a8"] = RA.a8p8(self.principal, year_group=int(f["a8_year"] or 11),
                            academic_year=f["a8_school_year"] or None,
                            record_source=f["a8_source"] or "Actual")
        return out

    def describe(self) -> str:
        a = self.report["analysis"]
        if a is None:
            return "Choose an assessment point, mock series or exam series and press Run."
        h = a.headline()
        return (f"{a.source.label}: {h['pupils']} pupils, {h['results']} results, average "
                f"{RW.RC.show(h['average'])}, 4+ {RW.RC.show(h['pct_4'])}%, "
                f"5+ {RW.RC.show(h['pct_5'])}%, 7+ {RW.RC.show(h['pct_7'])}%.")

    def table(self, section: str):
        if section == _COMPARE:
            c = self.report["compare"]
            if c is None:
                return ["Compare"], [["Choose 'Compare with' and press Run"]]
            return RA.compare_table(c, self.compare_detail.get())
        a = self.report["analysis"]
        if a is None and section != "a8p8":
            return ["Results"], [["Choose what to analyse and press Run"]]
        return RA.table(a, section, a8=self.report["a8"])

    def export(self, path: str, section: str) -> int:
        if section == _COMPARE:
            if self.report["compare"] is None:
                raise RA.ValidationError(["Choose 'Compare with' and press Run"])
            return RA.export_compare_csv(path, self.report["compare"], actor=self.principal,
                                         detail=self.compare_detail.get())
        return RA.export_csv(path, self.report["analysis"], section, actor=self.principal,
                             a8=self.report["a8"])

    def row_tags(self, name: str, row: list[Any]) -> tuple[str, ...]:
        if name == "Against target":
            return {"Well below": ("bad",), "Below": ("warn",), "Above": ("good",)}.get(
                row[-1], ())
        if name == "Subjects" and isinstance(row[-1], (int, float)):
            return ("good",) if row[-1] >= 0.5 else ("bad",) if row[-1] <= -0.5 else ()
        return ()

    def extra_buttons(self, name: str, bar: ttk.Frame) -> None:
        if name == "Subjects":
            ttk.Button(bar, text="Chart", command=self.chart_subjects).pack(side="left",
                                                                            padx=2)
        if name == "Compare":
            ttk.Checkbutton(bar, text="Pupil by pupil", variable=self.compare_detail,
                            command=lambda: self._fill("Compare")).pack(side="left", padx=6)
        if name == "Attainment 8 / P8":
            ttk.Button(bar, text="Summary", command=self.a8_summary).pack(side="left", padx=2)

    def pupil_text(self, pupil_id: int) -> str | None:
        a = self.report["analysis"] if self.report else None
        return RA.pupil_text(a, pupil_id) if a else None

    def chart_subjects(self) -> None:
        a = self.report["analysis"] if self.report else None
        if a is None:
            return
        subs = a.subjects()
        RW.bar_chart(self.parent, "Results by subject", [s["code"] for s in subs],
                     {"% 4+": [s["pct_4"] for s in subs], "% 5+": [s["pct_5"] for s in subs],
                      "% 7+": [s["pct_7"] for s in subs]}, ylabel="%")

    def a8_summary(self) -> None:
        a8 = self.report["a8"] if self.report else None
        if a8 is None:
            return
        h, s, p = a8["headline"], a8["a8"], a8["p8"]
        gap = h["disadvantaged_gap"]
        text = "\n".join([
            f"Year {h['year_group']}, {h['academic_year']}, A8 source: {h['source']}", "",
            f"A8 records: {s['records']}   average A8: {RW.RC.show(s['average_a8'])}   "
            f"average grade: {RW.RC.show(s['average_grade'])}",
            f"Highest {RW.RC.show(s['highest'])}, lowest {RW.RC.show(s['lowest'])}",
            "Bands: " + ", ".join(f"{b} {n}" for b, n in s["bands"].items()), "",
            f"P8 records: {p['records']}   average P8: {RW.RC.show(p['average_p8'])}   "
            f"above 0: {p['above_zero']}   below -0.5: {p['below_minus_half']}", "",
            "Disadvantaged gap (FSM minus not FSM): "
            + ", ".join(f"{k} {RW.RC.show(v)}" for k, v in gap.items()), "",
            f"Pupils with no A8 record: {len(h['missing_a8'])}",
            f"Pupils with no KS2 prior attainment: {len(h['missing_ks2'])}"])
        W.text_window(self.parent, "Attainment 8 / Progress 8", text)


def draw_results_analysis(parent: ttk.Frame, *, principal: Principal, state: dict,
                          open_pupil: Callable[[int], None] | None = None
                          ) -> ResultsAnalysisPage:
    return ResultsAnalysisPage(parent, principal=principal, state=state, open_pupil=open_pupil)
