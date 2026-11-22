"""Attainment 8 & Progress 8 screen.

The old two windows are the first two tabs, with their toolbars and columns:

* **Attainment 8** - Year / Academic yr / Source with Apply, New / update,
  Edit, Summary, Delete, Refresh; columns ID, Pupil, Yr, Academic yr,
  Source, Eng, Mth, EBacc, Open, Total, A8. Added: Calculate…, Slots
  (which subjects filled each slot), Export CSV and a Method column.
* **Progress 8** - Year / Academic yr with Apply, New / update, Edit,
  Refresh A8, Summary, Delete, Refresh; columns ID, Pupil, Yr, Academic yr,
  KS2, Exp A8, A8, P8, A8 source. Added: Calculate…, the element columns.

New tabs: Headline measures, KS2 prior attainment and P8 estimates. The
rules are in :mod:`modules.assessment.domain.headline_measures`.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

from education_system.platform.delivery.gui.parented_dialogs import (
    filedialog,
    messagebox,
)
from education_system.systems.secondary.modules.assessment.domain import headline_measures as HM
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.gui.components import widgets as W

logger = logging.getLogger(__name__)
YEARS = ("7", "8", "9", "10", "11")
_ERRORS = (HM.ValidationError, HM.PermissionDenied, HM.NotFound)


_problems = W.problems


def _num(v: Any, places: int = 1) -> str:
    if v is None:
        return "-"
    return f"{v:+.2f}" if places == 2 else (f"{v:g}" if float(v).is_integer() else
                                             f"{v:.{places}f}")


def _tree(parent, columns, height: int = 16) -> ttk.Treeview:
    return W.tree(parent, columns, height=height, stretch={"pupil", "based"}, tags=W.STANDARD_TAGS)


_text_window = W.text_window
_form = W.form_dialog


class HeadlineMeasuresPage:
    TABS = ("Attainment 8", "Progress 8", "Headline measures", "KS2 prior attainment",
            "P8 estimates")

    def __init__(self, parent: ttk.Frame, *, principal: Principal, state: dict,
                 open_pupil: Callable[[int], None] | None = None) -> None:
        self.parent, self.principal, self.state = parent, principal, state
        self.open_pupil = open_pupil
        self.editor = HM.is_editor(principal)
        activity_log.record("headline.view")
        ttk.Label(parent, text="Attainment 8 & Progress 8",
                  font=("", 16, "bold")).pack(anchor="w")
        self.summary_var = tk.StringVar()
        ttk.Label(parent, textvariable=self.summary_var, foreground="#666").pack(
            anchor="w", pady=(0, 6))
        self.book = ttk.Notebook(parent)
        self.book.pack(fill="both", expand=True)
        self.tabs = {n: ttk.Frame(self.book, padding=8) for n in self.TABS}
        for n, f in self.tabs.items():
            self.book.add(f, text=n)
        self._built: set[str] = set()
        self.book.select(self.TABS.index(state.get("tab", "Attainment 8")))
        self.book.bind("<<NotebookTabChanged>>", self._on_tab)
        self._on_tab()

    def _top(self):
        return self.parent.winfo_toplevel()

    def _err(self, title: str, e: Exception) -> None:
        messagebox.showerror(title, _problems(e), parent=self._top())

    def _on_tab(self, _e=None) -> None:
        name = self.TABS[self.book.index(self.book.select())]
        self.state["tab"] = name
        if name not in self._built:
            self._built.add(name)
            {"Attainment 8": self._build_a8, "Progress 8": self._build_p8,
             "Headline measures": self._build_headline, "KS2 prior attainment": self._build_ks2,
             "P8 estimates": self._build_estimates}[name](self.tabs[name])
        {"Attainment 8": self.refresh_a8, "Progress 8": self.refresh_p8,
         "Headline measures": self.refresh_headline, "KS2 prior attainment": self.refresh_ks2,
         "P8 estimates": self.refresh_estimates}[name]()

    # ── Shared filters ───────────────────────────────────────────────

    def _filters(self, bar, *, source: bool) -> None:
        ttk.Label(bar, text="Year:").pack(side="left", padx=(0, 4))
        ttk.Combobox(bar, textvariable=self.year_var(), values=["", *YEARS],
                     state="readonly", width=5).pack(side="left", padx=(0, 6))
        ttk.Label(bar, text="Academic yr:").pack(side="left", padx=(0, 4))
        ttk.Entry(bar, textvariable=self.ay_var(), width=10).pack(side="left", padx=(0, 6))
        if source:
            ttk.Label(bar, text="Source:").pack(side="left", padx=(0, 4))
            ttk.Combobox(bar, textvariable=self.src_var(), values=["", *HM.SOURCES],
                         state="readonly", width=10).pack(side="left", padx=(0, 8))

    def year_var(self) -> tk.StringVar:
        if not hasattr(self, "_year"):
            self._year = tk.StringVar(value=self.state.get("year", "11"))
        return self._year

    def ay_var(self) -> tk.StringVar:
        if not hasattr(self, "_ay"):
            self._ay = tk.StringVar(value=self.state.get("ay", HM.current_year()))
        return self._ay

    def src_var(self) -> tk.StringVar:
        if not hasattr(self, "_src"):
            self._src = tk.StringVar(value=self.state.get("src", ""))
        return self._src

    def _vals(self) -> tuple[str | None, str | None, str | None]:
        y, ay, src = self.year_var().get(), self.ay_var().get().strip(), self.src_var().get()
        self.state.update(year=y, ay=ay, src=src)
        return y or None, ay or None, src or None

    def _button(self, bar, text: str, command, editor_only: bool = False) -> None:
        b = ttk.Button(bar, text=text, command=command)
        if editor_only and not self.editor:
            b.state(["disabled"])
        b.pack(side="left", padx=2)

    # ── Attainment 8 (old window) ────────────────────────────────────

    def _build_a8(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self._filters(bar, source=True)
        self._button(bar, "Apply", self.refresh_a8)
        self._button(bar, "New / update", self.new_a8, True)
        self._button(bar, "Edit", self.edit_a8, True)
        self._button(bar, "Summary", self.a8_summary)
        self._button(bar, "Delete", self.delete_a8, True)
        self._button(bar, "Refresh", self.refresh_a8)
        bar2 = ttk.Frame(tab)
        bar2.pack(fill="x", pady=(0, 6))
        self._button(bar2, "Calculate…", self.calculate_a8, True)
        self._button(bar2, "Slots", self.slots)
        self._button(bar2, "Export CSV…", self.export)
        if self.open_pupil:
            self._button(bar2, "Open pupil", lambda: self._open(self.a8_tree, self.a8_rows))
        self.a8_tree = _tree(tab, [
            ("id", "ID", 50), ("pupil", "Pupil", 180), ("year", "Yr", 40),
            ("ay", "Academic yr", 90), ("src", "Source", 80), ("eng", "Eng", 50),
            ("mth", "Mth", 50), ("eb", "EBacc", 110), ("open", "Open", 110),
            ("total", "Total (A8)", 80), ("a8", "A8 avg grade", 90),
            ("method", "Method", 90)])
        self.a8_tree.bind("<Double-1>", lambda _e: self.slots())
        self.a8_rows: dict[str, Any] = {}

    def refresh_a8(self) -> None:
        y, ay, src = self._vals()
        self.a8_tree.delete(*self.a8_tree.get_children())
        try:
            rows = HM.list_records(year_group=y, academic_year=ay, record_source=src)
        except _ERRORS as e:
            self._err("Attainment 8", e)
            return
        self.a8_rows = {}
        for r in rows:
            self.a8_rows[str(r.record_id)] = r
            eb = "/".join(r.grade(f"ebacc{i}_grade") or "-" for i in (1, 2, 3))
            op = "/".join(r.grade(f"open{i}_grade") or "-" for i in (1, 2, 3))
            self.a8_tree.insert("", "end", iid=str(r.record_id), values=(
                r.record_id, f"{r.admission_no} {r.pupil_name}", r.year_group,
                r.academic_year, r.record_source,
                (r.english_grade or "-") + ("" if r.english_double else " (x1)"),
                r.maths_grade or "-", eb, op, _num(r.total_points), _num(r.average_grade, 2
                                                                        ).lstrip("+"),
                r.method))
        s = HM.cohort_summary(year_group=y, academic_year=ay, record_source=src)
        self.summary_var.set(f"{s['records']} record(s)" + (
            f" · average A8 {s['average_a8']} (average grade {s['average_grade']})"
            if s["records"] else ""))
        activity_log.record("headline.a8_list", results=len(rows))

    def _selected(self, tree, rows, title: str):
        sel = tree.selection()
        if not sel:
            messagebox.showinfo(title, "Select a record first.", parent=self._top())
            return None
        return rows.get(sel[0])

    def _open(self, tree, rows) -> None:
        r = self._selected(tree, rows, "Open pupil")
        if r and self.open_pupil:
            self.open_pupil(r.pupil_id)

    def _a8_dialog(self, rec=None) -> None:
        pupils = {f"{p.admission_no} - {p.display_name} (Y{p.year_group})": p
                  for p in P.list_pupils(year_group=int(self.year_var().get() or 0) or None)}
        fields = []
        if rec is None:
            fields += [("pupil", "Pupil", "", list(pupils)),
                       ("academic_year", "Academic year", self.ay_var().get() or
                        HM.current_year(), None),
                       ("record_source", "Source", self.src_var().get() or HM.DEFAULT_SOURCE,
                        HM.SOURCES)]
        fields += [(s, HM.SLOT_LABELS[s], rec.grade(s) if rec else "", None) for s in HM.SLOTS]
        fields += [("english_double", "English counted twice (took both)",
                    rec.english_double if rec else True, "check"),
                   ("notes", "Notes", rec.notes if rec else "", None)]

        def save(v: dict[str, Any]) -> None:
            if rec is None:
                p = pupils.get(v.pop("pupil"))
                if p is None:
                    raise HM.ValidationError(["Choose a pupil"])
                HM.upsert({**v, "pupil_id": p.pupil_id}, actor=self.principal)
            else:
                HM.update(rec.record_id, v, actor=self.principal)
            self.refresh_a8()

        _form(self.parent, "Attainment 8", fields, save,
              note="Slots (1–9 or U; combined science like 6-5; BTEC D*, D, M, P). A record "
                   "entered here is kept when the year is recalculated.")

    def new_a8(self) -> None:
        self._a8_dialog()

    def edit_a8(self) -> None:
        r = self._selected(self.a8_tree, self.a8_rows, "Edit")
        if r:
            self._a8_dialog(r)

    def delete_a8(self) -> None:
        r = self._selected(self.a8_tree, self.a8_rows, "Delete")
        if r and messagebox.askyesno("Delete", f"Delete the {r.record_source} Attainment 8 "
                                     f"record for {r.pupil_name} ({r.academic_year})?",
                                     parent=self._top()):
            try:
                HM.delete(r.record_id, actor=self.principal)
            except _ERRORS as e:
                self._err("Delete", e)
            self.refresh_a8()

    def a8_summary(self) -> None:
        y, ay, src = self._vals()
        s = HM.cohort_summary(year_group=y, academic_year=ay, record_source=src)
        if not s["records"]:
            messagebox.showinfo("Summary", "No records match.", parent=self._top())
            return
        lines = [f"Records: {s['records']}", f"Average A8: {s['average_a8']} "
                 f"(average grade {s['average_grade']})",
                 f"Highest: {s['highest']:g}   Lowest: {s['lowest']:g}", "",
                 "By source: " + ", ".join(f"{k} {v}" for k, v in s["by_source"].items()),
                 "", "A8 spread:"] + [f"  {b:<9} {n}" for b, n in s["bands"].items()]
        _text_window(self.parent, "Attainment 8 summary", "\n".join(lines))

    def slots(self) -> None:
        r = self._selected(self.a8_tree, self.a8_rows, "Slots")
        if not r:
            return
        lines = [f"{r.pupil_name} ({r.admission_no}) - {r.record_source} {r.academic_year}",
                 f"{r.method}" + (f" from {r.based_on}" if r.based_on else "")
                 + f" · A8 {_num(r.total_points)} · average grade {r.average_grade}", ""]
        for d in r.slot_detail:
            pts = f"{d['points']:g}" + (" (x2)" if d.get("weight") == 2 else "")
            lines.append(f"  {d['slot']:<12} {(d.get('subject') or '-'):<26} "
                         f"{(d.get('grade') or '-'):<5} {pts}"
                         + (f"  {d['note']}" if d.get("note") else ""))
        lines += ["", f"English {r.english_points:g} · Maths {r.maths_points:g} · EBacc "
                  f"{r.ebacc_points:g} · Open {r.open_points:g}",
                  "EBacc entered: " + ("-" if r.ebacc_entered is None else
                                       "yes" if r.ebacc_entered else "no")]
        if r.notes:
            lines += ["", f"Notes: {r.notes}"]
        _text_window(self.parent, "Attainment 8 slots", "\n".join(lines))

    def calculate_a8(self) -> None:
        from education_system.systems.secondary.modules.assessment.domain import (
            assessment_points as AP,
        )
        points = {f"{p.name} ({p.academic_year})": p.point_id
                  for p in AP.list_points(status="Published")}

        def save(v: dict[str, Any]) -> None:
            out = HM.calculate(int(v["year"] or 0), v["source"], actor=self.principal,
                               academic_year=v["ay"] or None,
                               point_id=points.get(v["point"]) if v["point"] else None,
                               overwrite_entered=bool(v["overwrite"]))
            msg = (f"Saved {len(out['saved'])} record(s) from {out['based_on']}.")
            if out["kept"]:
                msg += f"\nKept {len(out['kept'])} entered by hand."
            if out["no_data"]:
                msg += f"\nNo grades for {len(out['no_data'])}: " + ", ".join(
                    out["no_data"][:15]) + ("…" if len(out["no_data"]) > 15 else "")
            messagebox.showinfo("Calculate Attainment 8", msg, parent=self._top())
            self.src_var().set(v["source"])
            self.refresh_a8()

        _form(self.parent, "Calculate Attainment 8", [
            ("year", "Year group", self.year_var().get() or "11", YEARS),
            ("ay", "Academic year", self.ay_var().get() or HM.current_year(), None),
            ("source", "Source", self.src_var().get() or "Actual", HM.SOURCES),
            ("point", "Assessment point (Predicted)", "", ["", *points]),
            ("overwrite", "Also replace records entered by hand", False, "check")],
            save, note="Actual: released exam results (nothing under embargo). Predicted: an "
                       "assessment point (the newest published one if none is chosen). "
                       "Estimated: the latest completed mock exams. Target: target grades.")

    def export(self) -> None:
        path = filedialog.asksaveasfilename(parent=self._top(), defaultextension=".csv",
                                            filetypes=[("CSV", "*.csv")],
                                            initialfile="attainment8.csv")
        if not path:
            return
        y, ay, src = self._vals()
        n = HM.export_csv(path, actor=self.principal, year_group=y, academic_year=ay,
                          record_source=src)
        messagebox.showinfo("Export", f"Exported {n} record(s).", parent=self._top())

    # ── Progress 8 (old window) ──────────────────────────────────────

    def _build_p8(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self._filters(bar, source=False)
        self._button(bar, "Apply", self.refresh_p8)
        self._button(bar, "New / update", self.new_p8, True)
        self._button(bar, "Edit", self.edit_p8, True)
        self._button(bar, "Refresh A8", self.refresh_p8_a8, True)
        self._button(bar, "Summary", self.p8_summary)
        self._button(bar, "Delete", self.delete_p8, True)
        self._button(bar, "Refresh", self.refresh_p8)
        bar2 = ttk.Frame(tab)
        bar2.pack(fill="x", pady=(0, 6))
        self._button(bar2, "Calculate…", self.calculate_p8, True)
        if self.open_pupil:
            self._button(bar2, "Open pupil", lambda: self._open(self.p8_tree, self.p8_rows))
        self.p8_tree = _tree(tab, [
            ("id", "ID", 50), ("pupil", "Pupil", 180), ("year", "Yr", 40),
            ("ay", "Academic yr", 90), ("ks2", "KS2", 60), ("exp", "Exp A8", 70),
            ("a8", "A8", 60), ("p8", "P8", 70), ("src", "A8 source", 90),
            ("eng", "Eng P8", 65), ("mth", "Mth P8", 65), ("eb", "EBacc P8", 70),
            ("open", "Open P8", 70)])
        self.p8_rows: dict[str, Any] = {}

    def refresh_p8(self) -> None:
        y, ay, _src = self._vals()
        self.p8_tree.delete(*self.p8_tree.get_children())
        rows = HM.list_p8(year_group=y, academic_year=ay)
        self.p8_rows = {}
        for r in rows:
            self.p8_rows[str(r.record_id)] = r
            tag = () if r.progress_8 is None else ("good",) if r.progress_8 >= 0.5 else \
                ("bad",) if r.progress_8 <= -0.5 else ()
            self.p8_tree.insert("", "end", iid=str(r.record_id), tags=tag, values=(
                r.record_id, f"{r.admission_no} {r.pupil_name}", r.year_group,
                r.academic_year, _num(r.ks2_prior), _num(r.expected_a8),
                _num(r.attainment_8), _num(r.progress_8, 2), r.a8_source or "-",
                _num(r.p8_english, 2), _num(r.p8_maths, 2), _num(r.p8_ebacc, 2),
                _num(r.p8_open, 2)))
        s = HM.p8_summary(year_group=y, academic_year=ay)
        self.summary_var.set(f"{len(rows)} record(s)" + (
            f" · average P8 {s['average_p8']:+.2f}" if s["records"] else ""))
        activity_log.record("headline.p8_list", results=len(rows))

    def _p8_dialog(self, rec=None) -> None:
        pupils = {f"{p.admission_no} - {p.display_name} (Y{p.year_group})": p
                  for p in P.list_pupils(year_group=int(self.year_var().get() or 0) or None)}
        fields = []
        if rec is None:
            fields += [("pupil", "Pupil", "", list(pupils)),
                       ("academic_year", "Academic year", self.ay_var().get() or
                        HM.current_year(), None)]
        fields += [
            ("ks2_prior", "KS2 prior attainment (80–120)", rec.ks2_prior if rec else "", None),
            ("expected_a8", "Expected A8 (blank = estimates)",
             rec.expected_a8 if rec and rec.expected_from == "Entered" else "", None),
            ("attainment_8", "A8 (blank = from A8 records)",
             rec.attainment_8 if rec and rec.a8_source == "Entered" else "", None),
            ("notes", "Notes", rec.notes if rec else "", None)]

        def save(v: dict[str, Any]) -> None:
            if rec is None:
                p = pupils.get(v.pop("pupil"))
                if p is None:
                    raise HM.ValidationError(["Choose a pupil"])
                HM.upsert_p8({**v, "pupil_id": p.pupil_id}, actor=self.principal)
            else:
                HM.update_p8(rec.record_id, v, actor=self.principal)
            self.refresh_p8()

        _form(self.parent, "Progress 8", fields, save,
              note="Blank KS2 uses the pupil's KS2 record; blank expected A8 uses the DfE "
                   "estimates for the year; blank A8 uses their Attainment 8 record "
                   "(Actual first).")

    def new_p8(self) -> None:
        self._p8_dialog()

    def edit_p8(self) -> None:
        r = self._selected(self.p8_tree, self.p8_rows, "Edit")
        if r:
            self._p8_dialog(r)

    def refresh_p8_a8(self) -> None:
        r = self._selected(self.p8_tree, self.p8_rows, "Refresh A8")
        if r:
            try:
                HM.refresh_a8(r.record_id, actor=self.principal)
            except _ERRORS as e:
                self._err("Refresh A8", e)
            self.refresh_p8()

    def delete_p8(self) -> None:
        r = self._selected(self.p8_tree, self.p8_rows, "Delete")
        if r and messagebox.askyesno("Delete", f"Delete the Progress 8 record for "
                                     f"{r.pupil_name} ({r.academic_year})?",
                                     parent=self._top()):
            try:
                HM.delete_p8(r.record_id, actor=self.principal)
            except _ERRORS as e:
                self._err("Delete", e)
            self.refresh_p8()

    def p8_summary(self) -> None:
        y, ay, _src = self._vals()
        s = HM.p8_summary(year_group=y, academic_year=ay)
        if not s["records"]:
            messagebox.showinfo("Summary", "No Progress 8 scores match.", parent=self._top())
            return
        _text_window(self.parent, "Progress 8 summary", "\n".join([
            f"Pupils with a P8 score: {s['records']}",
            f"Average P8: {s['average_p8']:+.2f}",
            f"Above zero: {s['above_zero']}   Below -0.5: {s['below_minus_half']}",
            f"Highest: {s['highest']:+.2f}   Lowest: {s['lowest']:+.2f}"]))

    def calculate_p8(self) -> None:
        def save(v: dict[str, Any]) -> None:
            out = HM.calculate_p8(int(v["year"] or 0), actor=self.principal,
                                  academic_year=v["ay"] or None, prefer=v["prefer"] or None,
                                  overwrite_entered=bool(v["overwrite"]))
            msg = f"Saved {len(out['saved'])} Progress 8 score(s)."
            for key, label in (("no_ks2", "no KS2 data"), ("no_a8", "no Attainment 8 record"),
                               ("kept", "entered by hand, kept")):
                if out[key]:
                    msg += f"\n{len(out[key])} {label}: " + ", ".join(out[key][:12]) + (
                        "…" if len(out[key]) > 12 else "")
            messagebox.showinfo("Calculate Progress 8", msg, parent=self._top())
            self.refresh_p8()

        _form(self.parent, "Calculate Progress 8", [
            ("year", "Year group", self.year_var().get() or "11", YEARS),
            ("ay", "Academic year", self.ay_var().get() or HM.current_year(), None),
            ("prefer", "A8 source (blank = Actual first)", "", ["", *HM.SOURCES]),
            ("overwrite", "Also replace records entered by hand", False, "check")], save,
            note="Uses each pupil's KS2 prior attainment and the P8 estimates for the year.")

    # ── Headline measures ────────────────────────────────────────────

    def _build_headline(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        ttk.Label(bar, text="Year:").pack(side="left", padx=(0, 4))
        self.h_year = tk.StringVar(value=self.state.get("h_year", "11"))
        ttk.Combobox(bar, textvariable=self.h_year, values=YEARS, state="readonly",
                     width=5).pack(side="left", padx=(0, 6))
        ttk.Label(bar, text="Academic yr:").pack(side="left", padx=(0, 4))
        ttk.Entry(bar, textvariable=self.ay_var(), width=10).pack(side="left", padx=(0, 6))
        ttk.Label(bar, text="Source:").pack(side="left", padx=(0, 4))
        self.h_src = tk.StringVar(value=self.state.get("h_src", "Actual"))
        ttk.Combobox(bar, textvariable=self.h_src, values=HM.SOURCES, state="readonly",
                     width=10).pack(side="left", padx=(0, 8))
        self._button(bar, "Show", self.refresh_headline)
        self.h_tree = _tree(tab, [
            ("group", "Group", 170), ("pupils", "Pupils", 60), ("a8n", "With A8", 65),
            ("a8", "Avg A8", 70), ("p8", "Avg P8", 70), ("p8n", "With P8", 65),
            ("em4", "Eng & maths 4+", 105), ("em5", "Eng & maths 5+", 105),
            ("eb", "EBacc entry", 90)], height=11)
        self.h_info = tk.StringVar()
        ttk.Label(tab, textvariable=self.h_info, foreground="#555", wraplength=900,
                  justify="left").pack(anchor="w", pady=(6, 0))

    def refresh_headline(self) -> None:
        self.state.update(h_year=self.h_year.get(), h_src=self.h_src.get())
        h = HM.headline(year_group=int(self.h_year.get() or 11),
                        academic_year=self.ay_var().get().strip() or None,
                        record_source=self.h_src.get() or "Actual")
        self.h_tree.delete(*self.h_tree.get_children())
        pct = lambda v: "-" if v is None else f"{v:g}%"  # noqa: E731
        for g in h["groups"]:
            self.h_tree.insert("", "end", tags=("muted",) if not g["pupils"] else (), values=(
                g["group"], g["pupils"], g["with_a8"], _num(g["average_a8"]),
                _num(g["average_p8"], 2), g["with_p8"], pct(g["eng_maths_4"]),
                pct(g["eng_maths_5"]), pct(g["ebacc_entry"])))
        gap = h["disadvantaged_gap"]
        self.h_info.set(
            "Disadvantaged gap (FSM minus others): "
            f"A8 {_num(gap['average_a8'])}, P8 {_num(gap['average_p8'], 2)}, "
            f"Eng & maths 4+ {_num(gap['eng_maths_4'])} pts, 5+ {_num(gap['eng_maths_5'])} pts."
            f"\n{len(h['missing_a8'])} pupil(s) have no {h['source']} A8 record; "
            f"{len(h['missing_ks2'])} have no KS2 data (no P8).")
        self.summary_var.set(f"Year {h['year_group']} · {h['academic_year']} · {h['source']}")
        activity_log.record("headline.measures", source=h["source"])

    # ── KS2 prior attainment ─────────────────────────────────────────

    def _build_ks2(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        ttk.Label(bar, text="Year:").pack(side="left", padx=(0, 4))
        self.k_year = tk.StringVar(value=self.state.get("k_year", "11"))
        ttk.Combobox(bar, textvariable=self.k_year, values=["", *YEARS], state="readonly",
                     width=5).pack(side="left", padx=(0, 6))
        self.k_missing = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Missing only", variable=self.k_missing,
                        command=self.refresh_ks2).pack(side="left", padx=(0, 6))
        self._button(bar, "Apply", self.refresh_ks2)
        self._button(bar, "Set KS2…", self.set_ks2, True)
        self._button(bar, "Clear", self.clear_ks2, True)
        self._button(bar, "Import CSV…", self.import_ks2, True)
        self.k_tree = _tree(tab, [
            ("adm", "Adm no", 90), ("pupil", "Pupil", 200), ("year", "Yr", 40),
            ("read", "Reading", 70), ("maths", "Maths", 70), ("prior", "Prior attainment", 110),
            ("src", "Source", 100), ("by", "Updated by", 100)])
        self.k_rows: dict[str, Any] = {}

    def refresh_ks2(self) -> None:
        self.state["k_year"] = self.k_year.get()
        self.k_tree.delete(*self.k_tree.get_children())
        rows = HM.ks2_list(year_group=int(self.k_year.get()) if self.k_year.get() else None,
                           missing_only=self.k_missing.get())
        self.k_rows = {}
        for p, k in rows:
            self.k_rows[str(p.pupil_id)] = (p, k)
            self.k_tree.insert("", "end", iid=str(p.pupil_id),
                               tags=() if k and k.prior else ("muted",), values=(
                p.admission_no, p.display_name, p.year_group,
                k.reading_scaled if k and k.reading_scaled else "-",
                k.maths_scaled if k and k.maths_scaled else "-",
                _num(k.prior) if k else "-", k.source if k else "", k.updated_by if k else ""))
        have = sum(1 for _p, k in rows if k and k.prior)
        self.summary_var.set(f"{len(rows)} pupil(s) · {have} with KS2 data")

    def _k_selected(self):
        sel = self.k_tree.selection()
        if not sel:
            messagebox.showinfo("KS2", "Select a pupil first.", parent=self._top())
            return None
        return self.k_rows.get(sel[0])

    def set_ks2(self) -> None:
        got = self._k_selected()
        if not got:
            return
        p, k = got

        def save(v: dict[str, Any]) -> None:
            HM.set_ks2(p.pupil_id, v, actor=self.principal)
            self.refresh_ks2()

        _form(self.parent, f"KS2 - {p.display_name}", [
            ("reading_scaled", "Reading scaled score", k.reading_scaled if k else "", None),
            ("maths_scaled", "Maths scaled score", k.maths_scaled if k else "", None),
            ("source", "Source", k.source if k else "Entered", HM.KS2_SOURCES),
            ("notes", "Notes", k.notes if k else "", None)], save,
            note=f"Scaled scores {HM.KS2_MIN}–{HM.KS2_MAX}. Prior attainment is their "
                 "average (or the one given).")

    def clear_ks2(self) -> None:
        got = self._k_selected()
        if got and got[1] and messagebox.askyesno(
                "KS2", f"Clear {got[0].display_name}'s KS2 data?", parent=self._top()):
            HM.clear_ks2(got[0].pupil_id, actor=self.principal)
            self.refresh_ks2()

    def import_ks2(self) -> None:
        path = filedialog.askopenfilename(parent=self._top(), filetypes=[("CSV", "*.csv")],
                                          title="KS2 CSV: admission_no, reading, maths")
        if not path:
            return
        try:
            out = HM.import_ks2(path, actor=self.principal)
        except _ERRORS as e:
            self._err("Import KS2", e)
            return
        messagebox.showinfo("Import KS2", f"Imported {out['imported']} pupil(s).",
                            parent=self._top())
        self.refresh_ks2()

    # ── P8 estimates ─────────────────────────────────────────────────

    def _build_estimates(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        ttk.Label(bar, text="Academic yr:").pack(side="left", padx=(0, 4))
        ttk.Entry(bar, textvariable=self.ay_var(), width=10).pack(side="left", padx=(0, 6))
        self._button(bar, "Apply", self.refresh_estimates)
        self._button(bar, "Add / edit row…", self.edit_estimate, True)
        self._button(bar, "Delete row", self.delete_estimate, True)
        self._button(bar, "Import CSV…", self.import_estimates, True)
        self._button(bar, "Copy from year…", self.copy_estimates, True)
        ttk.Label(tab, text="The DfE's Progress 8 estimates: the average A8 of pupils "
                            "nationally with each KS2 prior attainment. Each row applies from "
                            "its KS2 value up to the next row.", foreground="#555",
                  wraplength=900, justify="left").pack(anchor="w", pady=(0, 4))
        self.e_tree = _tree(tab, [
            ("ks2", "KS2 from", 80), ("a8", "Expected A8", 90), ("eng", "English", 70),
            ("mth", "Maths", 70), ("eb", "EBacc", 70), ("open", "Open", 70)])
        self.e_rows: dict[str, Any] = {}

    def refresh_estimates(self) -> None:
        ay = self.ay_var().get().strip() or HM.current_year()
        self.e_tree.delete(*self.e_tree.get_children())
        rows = HM.estimates(ay)
        self.e_rows = {}
        for e in rows:
            iid = f"{e.ks2_from:g}"
            self.e_rows[iid] = e
            self.e_tree.insert("", "end", iid=iid, values=(
                f"{e.ks2_from:g}", _num(e.expected_a8, 2).lstrip("+"),
                *(_num(getattr(e, f"expected_{el}")) for el in HM.ELEMENTS)))
        other = [y for y in HM.estimate_years() if y != ay]
        self.summary_var.set(f"{len(rows)} estimate row(s) for {ay}" + (
            f" · also: {', '.join(other[:4])}" if other else ""))

    def edit_estimate(self) -> None:
        sel = self.e_tree.selection()
        e = self.e_rows.get(sel[0]) if sel else None
        ay = self.ay_var().get().strip() or HM.current_year()

        def save(v: dict[str, Any]) -> None:
            HM.set_estimate(ay, v, actor=self.principal)
            self.refresh_estimates()

        _form(self.parent, f"P8 estimate - {ay}", [
            ("ks2_from", "KS2 from", f"{e.ks2_from:g}" if e else "", None),
            ("expected_a8", "Expected A8 (0–90)", e.expected_a8 if e else "", None),
            *((f"expected_{el}", f"Expected {el} (optional)",
               getattr(e, f"expected_{el}") if e else "", None) for el in HM.ELEMENTS)], save)

    def delete_estimate(self) -> None:
        sel = self.e_tree.selection()
        if not sel:
            messagebox.showinfo("Delete row", "Select a row first.", parent=self._top())
            return
        e = self.e_rows[sel[0]]
        if messagebox.askyesno("Delete row", f"Delete the KS2 {e.ks2_from:g} row?",
                               parent=self._top()):
            HM.delete_estimate(e.academic_year, e.ks2_from, actor=self.principal)
            self.refresh_estimates()

    def import_estimates(self) -> None:
        ay = self.ay_var().get().strip() or HM.current_year()
        path = filedialog.askopenfilename(
            parent=self._top(), filetypes=[("CSV", "*.csv")],
            title=f"Estimates for {ay}: ks2_from, expected_a8 (+ optional elements)")
        if not path or not messagebox.askyesno(
                "Import estimates", f"Replace the {ay} estimates with this file?",
                parent=self._top()):
            return
        try:
            out = HM.import_estimates(ay, path, actor=self.principal)
        except _ERRORS as e:
            self._err("Import estimates", e)
            return
        messagebox.showinfo("Import estimates", f"Imported {out['imported']} row(s).",
                            parent=self._top())
        self.refresh_estimates()

    def copy_estimates(self) -> None:
        ay = self.ay_var().get().strip() or HM.current_year()
        years = [y for y in HM.estimate_years() if y != ay]

        def save(v: dict[str, Any]) -> None:
            n = HM.copy_estimates(v["from"], ay, actor=self.principal)
            messagebox.showinfo("Copy estimates", f"Copied {n} row(s) into {ay}.",
                                parent=self._top())
            self.refresh_estimates()

        _form(self.parent, f"Copy estimates into {ay}",
              [("from", "Copy from", years[0] if years else "", years)], save,
              note="Rows already in the year are kept.")


def draw_headline_measures(parent: ttk.Frame, *, principal: Principal, state: dict,
                           open_pupil: Callable[[int], None] | None = None
                           ) -> HeadlineMeasuresPage:
    return HeadlineMeasuresPage(parent, principal=principal, state=state,
                                open_pupil=open_pupil)
