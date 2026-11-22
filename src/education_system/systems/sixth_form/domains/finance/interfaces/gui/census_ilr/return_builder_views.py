"""Census / ILR window: generated return, attendance extract, funding.

Tabs added to the existing Census / ILR notebook (the original tabs are
unchanged):

* **Return Builder** — pick a return, generate its learners and aims from
  the records, validate it with the real rules, correct a learner by
  hand (kept as an override), and export CSV / school-census learning
  aims CSV / ILR-style XML, plus the year's ILR file ("ILR Export (CSV)",
  the same file as the Enrolment screens' ILR Export). Route (ILR or school census) and UKPRN are
  settings.
* **Attendance Census** — ATTEND's census / ILR attendance extract with
  its validation report and CSV export.
* **Funding** — learners funded (42-day qualifying), bands, learners at
  risk of not qualifying, condition-of-funding non-compliance.
* **16-18 Measures** — see measures_views.
"""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import filedialog, messagebox

from education_system.systems.sixth_form.domains.finance.domain.census_ilr import (
    census_ilr as core,
    funding_summary as funding,
    return_builder as builder,
    return_export as export,
    return_validation as validation,
)
from education_system.systems.sixth_form.interfaces.gui._ui import grab_when_viewable
from education_system.systems.sixth_form.interfaces.gui.governance.compliance.measures.measures_views import (
    MeasuresTab,
    run_async,
)

logger = logging.getLogger(__name__)

TITLE = "Census / ILR"
_ERRORS = (core.ValidationError, ValueError, PermissionError)

_SEV_TAGS = {"Error": ("#ffd1d1", "#8c0d0d"),
             "Warning": ("#fff7e6", "#7a5800"),
             "Info": ("#e6f0ff", "#1a3f8c")}


def add_return_builder_tabs(nb: ttk.Notebook) -> None:
    """Append the gap-build tabs to the Census / ILR notebook."""
    ReturnBuilderTab(nb)
    AttendanceCensusTab(nb)
    FundingTab(nb)
    MeasuresTab(nb)


def _return_label(r: core.CensusReturn) -> str:
    return f"#{r.return_id}  {r.return_type}  {r.academic_year}  [{r.status}]"


# ══ Return builder ═════════════════════════════════════════════════

class ReturnBuilderTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Return Builder")
        self._returns: list[core.CensusReturn] = []
        self._build()
        self._reload_returns()

    # layout
    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 2))
        ttk.Label(bar, text="Return:").pack(side="left")
        self.ret_var = tk.StringVar()
        self.ret_combo = ttk.Combobox(bar, textvariable=self.ret_var,
                                      state="readonly", width=46)
        self.ret_combo.pack(side="left", padx=(2, 6))
        self.ret_combo.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        ttk.Button(bar, text="Reload returns",
                   command=self._reload_returns).pack(side="left")
        self.route_lbl = ttk.Label(bar, text="", foreground="#1a3f8c")
        self.route_lbl.pack(side="left", padx=12)
        ttk.Button(bar, text="Settings…",
                   command=self._settings).pack(side="left")
        self.status = ttk.Label(bar, text="", foreground="#666")
        self.status.pack(side="right")

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(2, 4))
        for label, cmd in (
                ("Generate from records", self._generate),
                ("Validate", self._validate),
                ("Edit learner", self._edit_learner),
                ("Clear learner overrides", self._clear_overrides),
                ("Export CSV", lambda: self._export("csv")),
                ("Export census aims CSV", lambda: self._export("census_aims")),
                ("Export ILR XML", lambda: self._export("xml")),
                ("ILR Export (CSV)", self._export_ilr_year),
                ("Refresh", self.refresh),
        ):
            ttk.Button(actions, text=label, command=cmd).pack(side="left",
                                                              padx=3)
        ttk.Label(self.frame, text=export.SPEC_NOTICE, foreground="#8c0d0d",
                  wraplength=1250).pack(anchor="w", padx=8)

        pane = ttk.PanedWindow(self.frame, orient="vertical")
        pane.pack(fill="both", expand=True, padx=8, pady=4)

        top = ttk.Frame(pane)
        cols = ("ref", "name", "uln", "dob", "age", "postcode", "lldd",
                "aps", "hours", "band", "cof", "att", "over")
        heads = ("Ref", "Name", "ULN", "DOB", "Age", "Postcode", "LLDD",
                 "Avg GCSE", "Planned hrs", "Band", "CoF", "Att %",
                 "Overrides")
        widths = (90, 180, 100, 90, 45, 85, 50, 70, 85, 75, 50, 60, 200)
        self.learners = ttk.Treeview(top, columns=cols, show="headings",
                                     selectmode="browse")
        for c, h, w in zip(cols, heads, widths):
            self.learners.heading(c, text=h)
            self.learners.column(c, width=w, anchor="w")
        self.learners.tag_configure("override", background="#fff7e6")
        vsb = ttk.Scrollbar(top, orient="vertical",
                            command=self.learners.yview)
        self.learners.configure(yscrollcommand=vsb.set)
        self.learners.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.learners.bind("<Double-Button-1>", lambda _e: self._edit_learner())
        pane.add(top, weight=3)

        bottom = ttk.Frame(pane)
        self.find_lbl = ttk.Label(bottom, text="Validation findings")
        self.find_lbl.pack(anchor="w")
        fcols = ("sev", "rule", "ref", "aim", "message", "fix")
        self.findings = ttk.Treeview(bottom, columns=fcols, show="headings")
        for c, h, w in zip(fcols, ("Severity", "Rule", "Learner", "Aim",
                                   "Message", "Fix"),
                           (70, 170, 90, 50, 480, 330)):
            self.findings.heading(c, text=h)
            self.findings.column(c, width=w, anchor="w")
        for sev, (bg, fg) in _SEV_TAGS.items():
            self.findings.tag_configure(sev, background=bg, foreground=fg)
        fsb = ttk.Scrollbar(bottom, orient="vertical",
                            command=self.findings.yview)
        self.findings.configure(yscrollcommand=fsb.set)
        self.findings.pack(side="left", fill="both", expand=True)
        fsb.pack(side="right", fill="y")
        pane.add(bottom, weight=2)

    # data
    def _reload_returns(self) -> None:
        try:
            self._returns = core.list_returns()
        except core.ValidationError as e:
            messagebox.showerror(TITLE, str(e), parent=self.frame)
            return
        labels = [_return_label(r) for r in self._returns]
        self.ret_combo.configure(values=labels)
        if labels and self.ret_var.get() not in labels:
            self.ret_combo.current(0)
        self.refresh()

    def _current(self) -> core.CensusReturn | None:
        idx = self.ret_combo.current()
        if idx < 0 or idx >= len(self._returns):
            return None
        return self._returns[idx]

    def _need_return(self) -> core.CensusReturn | None:
        r = self._current()
        if r is None:
            messagebox.showinfo(TITLE, "Create a return on the All Returns "
                                       "tab first, then pick it here.",
                                parent=self.frame)
        return r

    def refresh(self) -> None:
        try:
            self.route_lbl.config(text=f"Route: {builder.get_route()}")
        except core.ValidationError:
            pass
        self.learners.delete(*self.learners.get_children())
        self.findings.delete(*self.findings.get_children())
        r = self._current()
        if r is None:
            return
        for ln in builder.list_learners(r.return_id):
            self.learners.insert("", "end", iid=str(ln.learner_id), values=(
                ln.learner_ref, ln.name, ln.uln or "—", ln.date_of_birth or "—",
                "" if ln.age_31_aug is None else ln.age_31_aug,
                ln.postcode or "—", "Y" if ln.lldd else "N",
                "" if ln.prior_attainment is None else f"{ln.prior_attainment:.2f}",
                "" if ln.planned_hours is None else f"{ln.planned_hours:g}",
                ln.funding_band or "—",
                {1: "Yes", 0: "No"}.get(ln.cof_compliant, "—"),
                "" if ln.attendance_pct is None else ln.attendance_pct,
                ", ".join(ln.overrides)),
                tags=("override",) if ln.overrides else ())
        found = validation.list_findings(r.return_id)
        for i, f in enumerate(found):
            self.findings.insert("", "end", iid=str(i), values=(
                f.severity, f.rule, f.learner_ref or "", f.aim_id or "",
                f.message, f.fix or ""), tags=(f.severity,))
        errs = sum(1 for f in found if f.severity == validation.ERROR)
        self.find_lbl.config(text=f"Validation findings — {errs} error(s), "
                                  f"{len(found) - errs} other (last run)")

    # actions
    def _generate(self) -> None:
        r = self._need_return()
        if not r:
            return

        def done(res, err) -> None:
            if err is not None:
                messagebox.showerror(TITLE, str(err), parent=self.frame)
                return
            msg = res.summary
            if res.attendance_summary:
                msg += f"\n\nAttendance: {res.attendance_summary}"
            if res.messages:
                msg += "\n\n" + "\n".join(res.messages[:10])
            messagebox.showinfo(TITLE, msg, parent=self.frame)
            self._reload_returns()

        run_async(self.frame, lambda: builder.generate_return(r.return_id),
                  done, status=self.status,
                  busy_text="Generating (attendance can take a while)…")

    def _validate(self) -> None:
        r = self._need_return()
        if not r:
            return

        def done(res, err) -> None:
            if err is not None:
                messagebox.showerror(TITLE, str(err), parent=self.frame)
                return
            messagebox.showinfo(
                TITLE, f"Return is now {res.status}: {res.error_count} "
                       f"error(s), {res.warning_count} warning(s).",
                parent=self.frame)
            self._reload_returns()

        run_async(self.frame, lambda: core.validate_return(r.return_id), done,
                  status=self.status, busy_text="Validating…")

    def _selected_learner(self) -> builder.ReturnLearner | None:
        sel = self.learners.selection()
        if not sel:
            messagebox.showinfo(TITLE, "Select a learner first.",
                                parent=self.frame)
            return None
        return builder.get_learner(int(sel[0]))

    def _edit_learner(self) -> None:
        ln = self._selected_learner()
        if ln and LearnerEditor(self.frame, ln).saved:
            self.refresh()

    def _clear_overrides(self) -> None:
        ln = self._selected_learner()
        if not ln or not ln.overrides:
            return
        if not messagebox.askyesno(
                TITLE, f"Forget hand edits ({', '.join(ln.overrides)}) for "
                       f"{ln.name}? The next generate refreshes them.",
                parent=self.frame):
            return
        try:
            builder.clear_learner_overrides(ln.learner_id)
        except _ERRORS as e:
            messagebox.showerror(TITLE, str(e), parent=self.frame)
            return
        self.refresh()

    def _export(self, kind: str) -> None:
        r = self._need_return()
        if not r:
            return
        ext = ".xml" if kind == "xml" else ".csv"
        stem = {"csv": "return", "census_aims": "census_learning_aims",
                "xml": "ilr"}[kind]
        path = filedialog.asksaveasfilename(
            parent=self.frame, defaultextension=ext,
            initialfile=f"{stem}_{r.return_id}_{_dt.date.today():%Y%m%d}{ext}",
            filetypes=[("XML" if ext == ".xml" else "CSV", f"*{ext}"),
                       ("All files", "*.*")])
        if not path:
            return
        allow = False
        try:
            export.save(r.return_id, path, kind=kind)
        except core.ValidationError as e:
            if not messagebox.askyesno(
                    TITLE, f"{e}\n\nExport it anyway as a DRAFT (not for "
                           "submission)?", parent=self.frame):
                self.refresh()
                return
            allow = True
        except PermissionError as e:
            messagebox.showerror(TITLE, str(e), parent=self.frame)
            return
        if allow:
            try:
                export.save(r.return_id, path, kind=kind, allow_errors=True)
            except _ERRORS as e:
                messagebox.showerror(TITLE, str(e), parent=self.frame)
                return
        messagebox.showinfo(TITLE, f"Written to {path}\n\n{export.SPEC_NOTICE}",
                            parent=self.frame)
        self.refresh()

    def _export_ilr_year(self) -> None:
        """The ILR file for the picked return's funding year — the same
        file the Enrolment screens' ILR Export saves (one code path)."""
        r = self._current()
        year = (builder.normalise_year(r.academic_year) if r
                else builder.current_year())
        path = filedialog.asksaveasfilename(
            parent=self.frame, defaultextension=".csv",
            initialfile=f"ilr_{year.replace('/', '-')}.csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title=f"Save ILR export {year}")
        if not path:
            return
        try:
            res = export.export_ilr_csv(year, path=path)
        except _ERRORS as e:
            messagebox.showerror(TITLE, str(e), parent=self.frame)
            return
        lines = [f"ILR {res.academic_year} written to {res.path}",
                 f"{res.learners} learner(s), {res.deliveries} learning "
                 f"deliver(ies), {len(res.problems)} problem(s)."]
        lines += [f"{p.severity}: {p.student_id} {p.field}: {p.message}"
                  for p in res.problems[:15]]
        if len(res.problems) > 15:
            lines.append(f"…and {len(res.problems) - 15} more")
        messagebox.showinfo(TITLE, "\n".join(lines) + f"\n\n{export.SPEC_NOTICE}",
                            parent=self.frame)

    def _settings(self) -> None:
        if SettingsDialog(self.frame).saved:
            self.refresh()


class LearnerEditor:
    """Hand-correct one generated learner; edited fields become overrides."""

    FIELDS = (("uln", "ULN"), ("family_name", "Family name"),
              ("given_names", "Given names"), ("date_of_birth", "Date of birth"),
              ("sex", "Sex (M/F)"), ("postcode", "Postcode"),
              ("ethnicity", "Ethnicity code"), ("lldd", "LLDD (1/0)"),
              ("ehcp", "EHCP (1/0)"), ("prior_attainment", "Average GCSE"),
              ("gcse_english", "GCSE English"), ("gcse_maths", "GCSE maths"),
              ("planned_qual_hours", "Planned qualification hours"),
              ("planned_eep_hours", "Planned EEP hours"),
              ("planned_hours", "Planned hours (total)"),
              ("funding_band", "Funding band"),
              ("learner_status", "Learner status"))

    def __init__(self, parent: tk.Misc, learner: builder.ReturnLearner) -> None:
        self.learner = learner
        self.saved = False
        self.win = tk.Toplevel(parent)
        self.win.title(f"Return learner — {learner.name}")
        self.win.transient(parent)
        grab_when_viewable(self.win)
        body = ttk.Frame(self.win, padding=10)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="Edited fields are kept as overrides when the "
                             "return is regenerated.",
                  foreground="#7a5800").grid(row=0, column=0, columnspan=2,
                                             sticky="w", pady=(0, 6))
        self.vars: dict[str, tk.StringVar] = {}
        for i, (key, label) in enumerate(self.FIELDS, 1):
            mark = " *" if key in learner.overrides else ""
            ttk.Label(body, text=label + mark).grid(row=i, column=0,
                                                    sticky="w", pady=1)
            v = getattr(learner, key)
            var = tk.StringVar(value="" if v is None else str(v))
            ttk.Entry(body, textvariable=var, width=32).grid(
                row=i, column=1, sticky="w", pady=1)
            self.vars[key] = var
        n = len(self.FIELDS) + 1
        ttk.Label(body, text="Notes").grid(row=n, column=0, sticky="w")
        self.notes = tk.StringVar(value=learner.notes or "")
        ttk.Entry(body, textvariable=self.notes, width=32).grid(
            row=n, column=1, sticky="w")
        bar = ttk.Frame(self.win, padding=(10, 0, 10, 10))
        bar.pack(fill="x")
        ttk.Button(bar, text="Save", command=self._save).pack(side="right",
                                                              padx=4)
        ttk.Button(bar, text="Cancel",
                   command=self.win.destroy).pack(side="right")
        self.win.wait_window()

    def _save(self) -> None:
        payload = {k: v.get() for k, v in self.vars.items()}
        payload["notes"] = self.notes.get()
        try:
            builder.update_learner(self.learner.learner_id, payload)
        except _ERRORS as e:
            messagebox.showerror(TITLE, str(e), parent=self.win)
            return
        self.saved = True
        self.win.destroy()


class SettingsDialog:
    def __init__(self, parent: tk.Misc) -> None:
        self.saved = False
        self.win = tk.Toplevel(parent)
        self.win.title("Return settings")
        self.win.transient(parent)
        grab_when_viewable(self.win)
        s = builder.get_settings()
        body = ttk.Frame(self.win, padding=10)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="A sixth form in a school files the school "
                             "census;\na sixth-form college files the ILR.",
                  justify="left").grid(row=0, column=0, columnspan=2,
                                       sticky="w", pady=(0, 6))
        ttk.Label(body, text="Route").grid(row=1, column=0, sticky="w")
        self.route = tk.StringVar(value=s["route"] or builder.DEFAULT_ROUTE)
        ttk.Combobox(body, textvariable=self.route, values=builder.ROUTES,
                     state="readonly", width=20).grid(row=1, column=1,
                                                      sticky="w")
        self.vars: dict[str, tk.StringVar] = {}
        for i, (key, label) in enumerate((
                ("ukprn", "UKPRN"), ("provider_name", "Provider name"),
                ("laestab", "LAESTAB (school census)"),
                ("urn", "URN")), 2):
            ttk.Label(body, text=label).grid(row=i, column=0, sticky="w")
            var = tk.StringVar(value=s.get(key) or "")
            ttk.Entry(body, textvariable=var, width=24).grid(row=i, column=1,
                                                             sticky="w")
            self.vars[key] = var
        bar = ttk.Frame(self.win, padding=(10, 0, 10, 10))
        bar.pack(fill="x")
        ttk.Button(bar, text="Save", command=self._save).pack(side="right",
                                                              padx=4)
        ttk.Button(bar, text="Cancel",
                   command=self.win.destroy).pack(side="right")
        self.win.wait_window()

    def _save(self) -> None:
        try:
            builder.set_route(self.route.get())
            for k, v in self.vars.items():
                builder.set_setting(k, v.get())
        except _ERRORS as e:
            messagebox.showerror(TITLE, str(e), parent=self.win)
            return
        self.saved = True
        self.win.destroy()


# ══ Attendance census (ATTEND's extract) ═══════════════════════════

class AttendanceCensusTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Attendance Census")
        self.built = None
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        start, _end = builder.year_bounds(builder.current_year())
        ttk.Label(bar, text="From:").pack(side="left")
        self.d_from = tk.StringVar(value=start)
        ttk.Entry(bar, textvariable=self.d_from, width=11).pack(side="left",
                                                                padx=(2, 8))
        ttk.Label(bar, text="To:").pack(side="left")
        self.d_to = tk.StringVar(value=_dt.date.today().isoformat())
        ttk.Entry(bar, textvariable=self.d_to, width=11).pack(side="left",
                                                              padx=(2, 8))
        ttk.Label(bar, text="Kind:").pack(side="left")
        self.kind = tk.StringVar(value=builder.route_attendance_kind(
            builder.get_route()))
        ttk.Combobox(bar, textvariable=self.kind, values=("census", "ilr"),
                     state="readonly", width=8).pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Build", command=self._build_extract).pack(
            side="left")
        ttk.Button(bar, text="Export CSV", command=self._export).pack(
            side="left", padx=6)
        self.status = ttk.Label(bar, text="", foreground="#666")
        self.status.pack(side="right")

        cols = ("id", "name", "possible", "attended", "pct", "auth",
                "unauth", "unmarked", "hours")
        self.tree = ttk.Treeview(self.frame, columns=cols, show="headings",
                                 height=12)
        for c, h, w in zip(cols, ("Student", "Name", "Possible", "Attended",
                                  "%", "Authorised", "Unauthorised",
                                  "Unmarked", "Hours attended"),
                           (100, 220, 80, 80, 60, 90, 100, 90, 110)):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=4)
        self.report = tk.Text(self.frame, height=12, wrap="word",
                              font=("TkFixedFont", 10))
        self.report.pack(fill="both", expand=False, padx=8, pady=(0, 8))

    def _build_extract(self) -> None:
        kind, f, t = self.kind.get(), self.d_from.get().strip(), self.d_to.get().strip()

        def done(ret, err) -> None:
            if err is not None:
                messagebox.showerror(TITLE, str(err), parent=self.frame)
                return
            from education_system.systems.sixth_form.domain.academics.attendance import (
                attendance_census,
            )
            self.built = ret
            self.tree.delete(*self.tree.get_children())
            for r in ret.rows:
                self.tree.insert("", "end", values=(
                    r.student_id, r.student_name or "", r.sessions_possible,
                    r.sessions_attended,
                    "" if r.attendance_pct is None else r.attendance_pct,
                    r.authorised, r.unauthorised, r.unmarked,
                    f"{r.hours_attended:g}"))
            self.report.delete("1.0", "end")
            self.report.insert("end", ret.summary + "\n\n"
                               + attendance_census.validation_report(ret))

        run_async(self.frame,
                  lambda: builder.attendance_extract(kind, f, t, fresh=True),
                  done, status=self.status, busy_text="Building extract…")

    def _export(self) -> None:
        if self.built is None:
            messagebox.showinfo(TITLE, "Build the extract first.",
                                parent=self.frame)
            return
        from education_system.systems.sixth_form.domain.academics.attendance import (
            attendance_census,
        )
        path = filedialog.asksaveasfilename(
            parent=self.frame, defaultextension=".csv",
            initialfile=f"attendance_{self.built.kind}.csv",
            filetypes=[("CSV", "*.csv")])
        if not path:
            return
        try:
            attendance_census.save(self.built, path)
        except _ERRORS as e:
            messagebox.showerror(TITLE, str(e), parent=self.frame)
            return
        messagebox.showinfo(TITLE, f"Written to {path}", parent=self.frame)


# ══ Funding ════════════════════════════════════════════════════════

class FundingTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Funding")
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Academic year:").pack(side="left")
        self.year = tk.StringVar(value=builder.current_year())
        ttk.Entry(bar, textvariable=self.year, width=10).pack(side="left",
                                                              padx=(2, 8))
        ttk.Label(bar, text="As of:").pack(side="left")
        self.as_of = tk.StringVar(value=_dt.date.today().isoformat())
        ttk.Entry(bar, textvariable=self.as_of, width=11).pack(side="left",
                                                               padx=(2, 8))
        ttk.Button(bar, text="Calculate", command=self.refresh).pack(side="left")
        self.status = ttk.Label(bar, text="", foreground="#666")
        self.status.pack(side="right")

        pane = ttk.PanedWindow(self.frame, orient="horizontal")
        pane.pack(fill="both", expand=True, padx=8, pady=4)
        self.text = tk.Text(pane, wrap="word", font=("TkFixedFont", 10),
                            width=60)
        pane.add(self.text, weight=1)
        right = ttk.Frame(pane)
        cols = ("id", "name", "age", "hours", "band", "funded", "risk",
                "lost", "cof")
        self.tree = ttk.Treeview(right, columns=cols, show="headings")
        for c, h, w in zip(cols, ("Student", "Name", "Age", "Hours", "Band",
                                  "Funded", "At risk", "Lost aims", "CoF"),
                           (90, 180, 45, 70, 75, 60, 60, 70, 50)):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w, anchor="w")
        self.tree.tag_configure("risk", background="#fff7e6")
        self.tree.tag_configure("unfunded", background="#ffd1d1")
        vsb = ttk.Scrollbar(right, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        pane.add(right, weight=2)

    def refresh(self) -> None:
        year, as_of = self.year.get().strip(), self.as_of.get().strip()

        def done(s, err) -> None:
            if err is not None:
                messagebox.showerror(TITLE, str(err), parent=self.frame)
                return
            self.text.delete("1.0", "end")
            self.text.insert("end", s.text())
            self.tree.delete(*self.tree.get_children())
            for ln in s.learners:
                tag = ("unfunded",) if not ln.funded else (
                    ("risk",) if ln.at_risk else ())
                self.tree.insert("", "end", values=(
                    ln.student_id, ln.student_name,
                    "" if ln.age_31_aug is None else ln.age_31_aug,
                    f"{ln.planned_hours:g}", ln.band,
                    "Yes" if ln.funded else "No", len(ln.at_risk),
                    len(ln.withdrawn_before_qualifying),
                    {True: "Yes", False: "No"}.get(ln.cof_compliant, "—")),
                    tags=tag)

        run_async(self.frame,
                  lambda: funding.funding_summary(year or None,
                                                  as_of=as_of or None),
                  done, status=self.status, busy_text="Calculating…")


__all__ = ["add_return_builder_tabs", "ReturnBuilderTab",
           "AttendanceCensusTab", "FundingTab"]
