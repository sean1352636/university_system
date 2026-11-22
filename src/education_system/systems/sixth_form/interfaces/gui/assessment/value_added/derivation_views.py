"""Value Added window: benchmark table and derived VA tabs.

* **Benchmarks** — the average-GCSE → expected grade / MEG table, editable.
  A red banner shows while any seeded PLACEHOLDER band is still in use.
* **Derived VA** — expected grade, actual grade and VA per learner and
  subject, subject means and the cohort mean; "Write to VA records"
  fills value-added records for an exam session through value_added's
  own create/update.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import messagebox

from education_system.systems.sixth_form.domain.academics.qualifications import (
    grade_scales,
)
from education_system.systems.sixth_form.domain.assessment.value_added import (
    derivation as data,
)
from education_system.systems.sixth_form.interfaces.gui._ui import grab_when_viewable
from education_system.systems.sixth_form.interfaces.gui.governance.compliance.measures.measures_views import (
    run_async,
)

logger = logging.getLogger(__name__)

TITLE = "Value Added"
PLACEHOLDER_BANNER = ("PLACEHOLDER benchmarks in use: the seeded bands are a "
                      "straight line (one grade per GCSE point), NOT ALPS or "
                      "DfE data. Replace them with your ALPS / L3VA "
                      "benchmarks before relying on expected grades, VA or "
                      "MEGs.")


def add_derivation_tabs(nb: ttk.Notebook) -> None:
    """Append Benchmarks, Derived VA and MEG tabs to the VA notebook."""
    from education_system.systems.sixth_form.interfaces.gui.assessment.target_setting.meg_views import (
        MEGTab,
    )
    BenchmarksTab(nb)
    DerivedVATab(nb)
    MEGTab(nb)


class BenchmarksTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Benchmarks")
        self.banner = ttk.Label(self.frame, text="", foreground="#8c0d0d",
                                wraplength=1250, justify="left")
        self.banner.pack(anchor="w", padx=8, pady=(8, 0))
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=4)
        ttk.Label(bar, text="Type:").pack(side="left")
        self.f_type = ttk.Combobox(
            bar, values=("",) + tuple(grade_scales.QUALIFICATION_TYPES),
            state="readonly", width=24)
        self.f_type.current(0)
        self.f_type.pack(side="left", padx=(2, 8))
        self.f_type.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        for label, cmd in (("New band", self._new), ("Edit", self._edit),
                           ("Delete", self._delete),
                           ("Restore placeholder", self._restore),
                           ("Refresh", self.refresh)):
            ttk.Button(bar, text=label, command=cmd).pack(side="left", padx=3)
        cols = ("type", "subject", "range", "expected", "meg", "source",
                "notes")
        self.tree = ttk.Treeview(self.frame, columns=cols, show="headings",
                                 selectmode="browse")
        for c, h, w in zip(cols, ("Qualification", "Subject", "Average GCSE",
                                  "Expected", "MEG", "Source", "Notes"),
                           (150, 140, 110, 75, 60, 420, 300)):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w, anchor="w")
        self.tree.tag_configure("placeholder", background="#ffe9e9")
        self.tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.tree.bind("<Double-Button-1>", lambda _e: self._edit())
        self.refresh()

    def refresh(self) -> None:
        self.banner.config(text=PLACEHOLDER_BANNER
                           if data.placeholder_in_use() else "")
        self.tree.delete(*self.tree.get_children())
        for b in data.list_bands(qualification_type=self.f_type.get() or None):
            self.tree.insert("", "end", iid=str(b.band_id), values=(
                b.qualification_type, b.subject or "(all subjects)",
                b.range_label, b.expected_grade, b.minimum_grade, b.source,
                b.notes or ""), tags=("placeholder",) if b.is_placeholder else ())

    def _selected(self) -> data.Band | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo(TITLE, "Select a band first.",
                                parent=self.frame)
            return None
        return data.get_band(int(sel[0]))

    def _new(self) -> None:
        if BandEditor(self.frame).saved:
            self.refresh()

    def _edit(self) -> None:
        b = self._selected()
        if b and BandEditor(self.frame, band=b).saved:
            self.refresh()

    def _delete(self) -> None:
        b = self._selected()
        if b and messagebox.askyesno(TITLE, f"Delete the {b.range_label} "
                                            f"band for {b.qualification_type}?",
                                     parent=self.frame):
            data.delete_band(b.band_id)
            self.refresh()

    def _restore(self) -> None:
        if messagebox.askyesno(
                TITLE, "Delete any remaining placeholder bands and seed the "
                       "linear placeholder again? Your own bands are kept.",
                parent=self.frame):
            data.restore_placeholder()
            self.refresh()


class BandEditor:
    def __init__(self, parent: tk.Misc, *, band: data.Band | None = None) -> None:
        self.band = band
        self.saved = False
        self.win = tk.Toplevel(parent)
        self.win.title("Benchmark band")
        self.win.transient(parent)
        grab_when_viewable(self.win)
        body = ttk.Frame(self.win, padding=10)
        body.pack(fill="both", expand=True)
        self.vars: dict[str, tk.StringVar] = {}
        rows = (("qualification_type", "Qualification type"),
                ("subject", "Subject (blank = all)"),
                ("min_aps", "Average GCSE from"),
                ("max_aps", "Average GCSE below (blank = no limit)"),
                ("expected_grade", "Expected grade"),
                ("meg_grade", "MEG (blank = expected)"),
                ("source", "Source (e.g. ALPS 2025)"), ("notes", "Notes"))
        for i, (key, label) in enumerate(rows):
            ttk.Label(body, text=label).grid(row=i, column=0, sticky="w",
                                             pady=2)
            v = getattr(band, key, None) if band else None
            if band and band.is_placeholder and key == "source":
                v = ""
            var = tk.StringVar(value="" if v is None else str(v))
            if key == "qualification_type":
                w = ttk.Combobox(body, textvariable=var, state="readonly",
                                 values=tuple(grade_scales.QUALIFICATION_TYPES),
                                 width=28)
                if not band:
                    var.set(grade_scales.DEFAULT_QUALIFICATION_TYPE)
            else:
                w = ttk.Entry(body, textvariable=var, width=30)
            w.grid(row=i, column=1, sticky="w", pady=2)
            self.vars[key] = var
        if band and band.is_placeholder:
            ttk.Label(body, text="Saving turns this placeholder band into a "
                                 "real one - enter its source.",
                      foreground="#8c0d0d").grid(row=len(rows), column=0,
                                                 columnspan=2, sticky="w")
        bar = ttk.Frame(self.win, padding=(10, 0, 10, 10))
        bar.pack(fill="x")
        ttk.Button(bar, text="Save", command=self._save).pack(side="right",
                                                              padx=4)
        ttk.Button(bar, text="Cancel",
                   command=self.win.destroy).pack(side="right")
        self.win.wait_window()

    def _save(self) -> None:
        payload = {k: v.get() for k, v in self.vars.items()}
        try:
            if self.band:
                data.update_band(self.band.band_id, payload)
            else:
                data.add_band(payload)
        except (data.ValidationError, ValueError) as e:
            messagebox.showerror(TITLE, str(e), parent=self.win)
            return
        self.saved = True
        self.win.destroy()


class DerivedVATab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Derived VA")
        self.cohort: data.CohortVA | None = None
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Academic year (blank = all):").pack(side="left")
        self.year = tk.StringVar()
        ttk.Entry(bar, textvariable=self.year, width=9).pack(side="left",
                                                             padx=(2, 8))
        ttk.Label(bar, text="Result year:").pack(side="left")
        self.ryear = tk.StringVar()
        ttk.Entry(bar, textvariable=self.ryear, width=6).pack(side="left",
                                                              padx=(2, 8))
        ttk.Label(bar, text="Subject:").pack(side="left")
        self.subject = tk.StringVar()
        ttk.Entry(bar, textvariable=self.subject, width=16).pack(side="left",
                                                                 padx=(2, 8))
        ttk.Button(bar, text="Calculate", command=self.refresh).pack(side="left")
        ttk.Button(bar, text="Write to VA records…",
                   command=self._apply).pack(side="left", padx=6)
        self.status = ttk.Label(bar, text="", foreground="#666")
        self.status.pack(side="right")
        self.headline = ttk.Label(self.frame, text="", font=("", 11, "bold"))
        self.headline.pack(anchor="w", padx=8)
        self.banner = ttk.Label(self.frame, text="", foreground="#8c0d0d",
                                wraplength=1250)
        self.banner.pack(anchor="w", padx=8)

        pane = ttk.PanedWindow(self.frame, orient="horizontal")
        pane.pack(fill="both", expand=True, padx=8, pady=4)
        left = ttk.Frame(pane)
        self.subjects = ttk.Treeview(left, columns=("s", "n", "r", "va"),
                                     show="headings")
        for c, h, w in zip(("s", "n", "r", "va"),
                           ("Subject", "Learners", "Results", "Mean VA"),
                           (160, 70, 70, 80)):
            self.subjects.heading(c, text=h)
            self.subjects.column(c, width=w, anchor="w")
        self.subjects.pack(fill="both", expand=True)
        pane.add(left, weight=1)
        right = ttk.Frame(pane)
        cols = ("id", "name", "subject", "type", "aps", "exp", "meg",
                "act", "va", "note")
        self.rows = ttk.Treeview(right, columns=cols, show="headings")
        for c, h, w in zip(cols, ("Student", "Name", "Subject", "Type",
                                  "Avg GCSE", "Expected", "MEG", "Actual",
                                  "VA", "Note"),
                           (90, 160, 130, 100, 70, 70, 50, 60, 50, 200)):
            self.rows.heading(c, text=h)
            self.rows.column(c, width=w, anchor="w")
        vsb = ttk.Scrollbar(right, orient="vertical", command=self.rows.yview)
        self.rows.configure(yscrollcommand=vsb.set)
        self.rows.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        pane.add(right, weight=3)

    def refresh(self) -> None:
        year = self.year.get().strip() or None
        subj = self.subject.get().strip() or None
        ry_raw = self.ryear.get().strip()
        try:
            ry = int(ry_raw) if ry_raw else None
        except ValueError:
            messagebox.showerror(TITLE, "Result year must be a year, e.g. 2026",
                                 parent=self.frame)
            return

        def done(c, err) -> None:
            if err is not None:
                messagebox.showerror(TITLE, str(err), parent=self.frame)
                return
            self.cohort = c
            self.headline.config(
                text=f"Cohort VA: {'—' if c.mean_va is None else f'{c.mean_va:+.2f}'}"
                     f" grades over {c.with_results} result(s); "
                     f"{len(c.rows)} learner-subject row(s)")
            self.banner.config(text=PLACEHOLDER_BANNER
                               if c.placeholder_in_use else "")
            self.subjects.delete(*self.subjects.get_children())
            for s in c.by_subject:
                self.subjects.insert("", "end", values=(
                    s.subject, s.learners, s.with_results,
                    "—" if s.mean_va is None else f"{s.mean_va:+.2f}"))
            self.rows.delete(*self.rows.get_children())
            for r in c.rows:
                self.rows.insert("", "end", values=(
                    r.student_id, r.student_name, r.subject,
                    r.qualification_type,
                    "" if r.aps is None else f"{r.aps:.2f}",
                    r.expected_grade or "—", r.meg_grade or "—",
                    r.actual_grade or "—",
                    "" if r.va is None else f"{r.va:+.0f}", r.note))

        run_async(self.frame, lambda: data.derive_cohort(
            academic_year=year, subject=subj, results_year=ry), done,
            status=self.status, busy_text="Calculating…")

    def _apply(self) -> None:
        if self.cohort is None:
            messagebox.showinfo(TITLE, "Calculate first.", parent=self.frame)
            return
        session = _ask(self.frame, "Exam session for the VA records "
                                   "(e.g. 'Summer 2026')")
        if not session:
            return
        overwrite = messagebox.askyesno(
            TITLE, "Replace expected grades already typed into existing VA "
                   "records?\n(No = only fill blanks)", parent=self.frame)
        try:
            res = data.apply_to_records(session, rows=self.cohort.rows,
                                        overwrite_expected=overwrite)
        except (data.ValidationError, ValueError) as e:
            messagebox.showerror(TITLE, str(e), parent=self.frame)
            return
        msg = res.summary
        if res.skipped:
            msg += "\n\n" + "\n".join(f"{s} {sub}: {why}"
                                      for s, sub, why in res.skipped[:15])
        messagebox.showinfo(TITLE, msg, parent=self.frame)


def _ask(parent: tk.Misc, prompt: str, initial: str = "") -> str | None:
    win = tk.Toplevel(parent)
    win.title(TITLE)
    win.transient(parent)
    grab_when_viewable(win)
    ttk.Label(win, text=prompt).pack(anchor="w", padx=8, pady=8)
    var = tk.StringVar(value=initial)
    ttk.Entry(win, textvariable=var, width=40).pack(fill="x", padx=8)
    out: dict = {"v": None}

    def ok() -> None:
        out["v"] = var.get().strip()
        win.destroy()

    bar = ttk.Frame(win)
    bar.pack(fill="x", padx=8, pady=10)
    ttk.Button(bar, text="OK", command=ok).pack(side="right", padx=4)
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="right")
    win.wait_window()
    return out["v"]


__all__ = ["add_derivation_tabs", "BenchmarksTab", "DerivedVATab",
           "PLACEHOLDER_BANNER"]
