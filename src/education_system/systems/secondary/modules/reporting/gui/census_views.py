"""School Census screen (data manager only).

Kept from the old Census window: the returns list tabs (All Returns, Open
Windows, Overdue) with their filters (Type, Year, Status; Apply, New), their
columns (Id, Ov, Type, Year, Census day, Deadline, Submitted, Learners,
Errors, Warnings, Status) and buttons (Edit, Validate, Submit, Accept, Reject,
Resubmit, Archive, Counts, Status, Delete, Refresh), the return editor's
fields, the Aims tab (learner aims: :mod:`census_aims_views`) and the Summary
tab (returns and aims).

New: the return builder. Build (census term, school year, census day - the
DfE default or another date; Build runs in the background; Save return,
Export CSV, Export XML), then the return's Pupils, Attendance, Exclusions
and Validation tabs (errors and queries per pupil, Open pupil). The rules
are in :mod:`modules.reporting.domain.census`.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

from education_system.platform.delivery.gui.parented_dialogs import (
    filedialog,
    messagebox,
    simpledialog,
)
from education_system.systems.secondary.modules.reporting.domain import census as CE
from education_system.systems.secondary.modules.reporting.gui import report_widgets as RW
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.core.academic_calendar.school_year import current_year
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.gui.components import widgets as W

_RUN_COLUMNS = [("id", "Id", 40), ("ov", "Ov", 30), ("type", "Type", 190),
                ("year", "Year", 70), ("day", "Census day", 90), ("deadline", "Deadline", 90),
                ("submitted", "Submitted", 90), ("learners", "Learners", 70),
                ("errors", "Errors", 60), ("warnings", "Warnings", 70),
                ("status", "Status", 100)]
_STATUS_TAGS = {"Accepted": "good", "Rejected": "bad", "Archived": "muted"}


class CensusPage:
    TABS = ("Build", "Pupils", "Attendance", "Exclusions", "Validation", "All Returns",
            "Open Windows", "Overdue", "Aims", "Summary")
    _PARTS = {"Pupils": "pupils", "Attendance": "attendance", "Exclusions": "exclusions",
              "Validation": "problems"}

    def __init__(self, parent: ttk.Frame, *, principal: Principal, state: dict,
                 open_pupil: Callable[[int], None] | None = None) -> None:
        self.parent, self.principal, self.state = parent, principal, state
        self.open_pupil = open_pupil
        self.ret: CE.CensusReturn | None = None
        activity_log.record("census.view")
        ttk.Label(parent, text="School Census", font=("", 16, "bold")).pack(anchor="w")
        self.status = tk.StringVar(value="Build a return, check the validation report, then "
                                         "save and export it.")
        ttk.Label(parent, textvariable=self.status, foreground="#666").pack(anchor="w",
                                                                            pady=(0, 6))
        self.book = ttk.Notebook(parent)
        self.book.pack(fill="both", expand=True)
        self.tabs = {n: ttk.Frame(self.book, padding=8) for n in self.TABS}
        for n in self.TABS:
            self.book.add(self.tabs[n], text=n)
        self._built: set[str] = set()
        self.boxes: dict[str, RW.TableBox] = {}
        self.run_trees: dict[str, ttk.Treeview] = {}
        start = state.get("tab") if state.get("tab") in self.TABS else "Build"
        self.book.select(self.TABS.index(start))
        self.book.bind("<<NotebookTabChanged>>", self._on_tab)
        self._on_tab()

    # ── helpers ──────────────────────────────────────────────────────

    def _top(self):
        return self.parent.winfo_toplevel()

    def _err(self, title: str, e: Exception) -> None:
        messagebox.showerror(title, W.problems(e), parent=self._top())

    def _on_tab(self, _e=None) -> None:
        name = self.TABS[self.book.index(self.book.select())]
        self.state["tab"] = name
        if name not in self._built:
            self._built.add(name)
            {"Build": self._build_build, "Summary": self._build_summary,
             "Aims": self._build_aims}.get(
                name, self._build_part if name in self._PARTS else self._build_runs)(name)
        self._refresh(name)

    def _refresh(self, name: str) -> None:
        if name in self._PARTS:
            self._fill_part(name)
        elif name in ("All Returns", "Open Windows", "Overdue"):
            self.refresh_runs(name)
        elif name == "Summary":
            self.refresh_summary()
        elif name == "Aims" and hasattr(self, "aims"):
            self.aims.refresh()

    def _build_aims(self, name: str) -> None:
        from education_system.systems.secondary.modules.reporting.gui.census_aims_views import (
            AimsTab,
        )
        self.aims = AimsTab(self.tabs[name], principal=self.principal,
                            open_pupil=self.open_pupil)

    def _refresh_all(self) -> None:
        for n in self._built:
            self._refresh(n)

    # ── Build ────────────────────────────────────────────────────────

    def _build_build(self, name: str) -> None:
        tab = self.tabs[name]
        term, year = CE.next_census()
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        self.term = tk.StringVar(value=self.state.get("term", term))
        self.year = tk.StringVar(value=self.state.get("year", year))
        self.day = tk.StringVar(value=self.state.get("day", ""))
        ttk.Label(bar, text="Census:").pack(side="left")
        cb = ttk.Combobox(bar, textvariable=self.term, values=CE.TERMS, state="readonly",
                          width=8)
        cb.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="School year:").pack(side="left")
        yb = ttk.Combobox(bar, textvariable=self.year, width=8,
                          values=[current_year(), year])
        yb.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Census day (blank = DfE day):").pack(side="left")
        ttk.Entry(bar, textvariable=self.day, width=11).pack(side="left", padx=(2, 8))
        for w in (cb, yb):
            w.bind("<<ComboboxSelected>>", lambda _e: self._show_dates())
        self.build_button = ttk.Button(bar, text="Build", command=self.build)
        self.build_button.pack(side="left", padx=2)
        bar2 = ttk.Frame(tab)
        bar2.pack(fill="x", pady=(0, 6))
        for text, cmd in (("Save return", self.save), ("Export CSV…", self.export_csv),
                          ("Export XML…", self.export_xml)):
            ttk.Button(bar2, text=text, command=cmd).pack(side="left", padx=2)
        self.dates = tk.StringVar()
        ttk.Label(tab, textvariable=self.dates, foreground="#555").pack(anchor="w")
        self.text = tk.Text(tab, height=18, wrap="word", font=("TkFixedFont", 10))
        self.text.pack(fill="both", expand=True, pady=(6, 0))
        self._show_dates()
        self._show_summary()

    def _show_dates(self) -> None:
        try:
            pr = CE.periods(self.term.get(), self.year.get())
            day = CE.census_date(self.term.get(), self.year.get())
        except W.ERRORS as e:
            self.dates.set(W.problems(e))
            return
        self.dates.set(f"DfE census day {day}.  Attendance: {pr['attendance_term']} "
                       f"({pr['attendance_from']} to {pr['attendance_to']}).  Exclusions: "
                       f"{pr['exclusions_term']} ({pr['exclusions_from']} to "
                       f"{pr['exclusions_to']}).")

    def _show_summary(self) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", "\n".join(self.ret.summary_lines()) if self.ret else
                         "No return built yet.")
        self.text.configure(state="disabled")

    def build(self) -> None:
        term, year, day = self.term.get(), self.year.get().strip(), self.day.get().strip()
        self.state.update(term=term, year=year, day=day)
        self.build_button.state(["disabled"])
        self.status.set("Building the return…")

        def done(ret: CE.CensusReturn) -> None:
            self.build_button.state(["!disabled"])
            self.ret = ret
            c = ret.counts()
            self.status.set(f"{ret.term} {ret.academic_year}: {c['pupils']} pupils, "
                            f"{c['errors']} error(s), {c['queries']} query(ies).")
            self._show_summary()
            self._refresh_all()

        def failed(e: Exception) -> None:
            self.build_button.state(["!disabled"])
            self.status.set("Not built.")
            self._err("School Census", e)

        RW.run_in_background(self.parent, lambda: CE.build(term, year or None,
                                                           actor=self.principal,
                                                           on=day or None),
                             done, failed, name="secondary-census")

    def _need_return(self) -> bool:
        if self.ret is None:
            messagebox.showinfo("School Census", "Build a return first.", parent=self._top())
            return False
        return True

    def save(self) -> None:
        if not self._need_return():
            return
        try:
            rid = CE.save_run(self.ret, actor=self.principal)
        except W.ERRORS as e:
            self._err("Save return", e)
            return
        messagebox.showinfo("Save return", f"Saved as return #{rid} (Draft). Track it under "
                                           "All Returns.", parent=self._top())
        self._refresh_all()

    def export_csv(self, part: str | None = None) -> None:
        if not self._need_return():
            return
        if part is None:
            win, frm = W.dialog(self.parent, "Export CSV")
            v = tk.StringVar(value="pupils")
            for key, label in CE.PARTS.items():
                ttk.Radiobutton(frm, text=label, value=key, variable=v).pack(anchor="w")

            def go() -> None:
                win.destroy()
                self.export_csv(v.get())
            ttk.Button(frm, text="Export…", command=go).pack(anchor="e", pady=(8, 0))
            return
        RW.save_csv(self.parent, f"census_{self.ret.term.lower()}_{part}.csv",
                    lambda path: CE.export_csv(self.ret, path, part, actor=self.principal),
                    "School Census")

    def export_xml(self) -> None:
        if not self._need_return():
            return
        path = filedialog.asksaveasfilename(parent=self._top(), defaultextension=".xml",
                                            filetypes=[("XML", "*.xml")],
                                            initialfile=f"census_{self.ret.term.lower()}.xml")
        if not path:
            return
        try:
            n = CE.export_xml(self.ret, path, actor=self.principal)
        except (*W.ERRORS, OSError) as e:
            self._err("Export XML", e)
            return
        messagebox.showinfo("Export XML", f"Wrote {n} pupil(s).", parent=self._top())

    # ── Return parts ─────────────────────────────────────────────────

    def _build_part(self, name: str) -> None:
        tab = self.tabs[name]
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        ttk.Button(bar, text="Export CSV…",
                   command=lambda: self.export_csv(self._PARTS[name])).pack(side="left",
                                                                            padx=2)
        ttk.Button(bar, text="Open pupil", command=lambda: self._open(name)).pack(
            side="left", padx=2)
        if name == "Validation":
            self.severity = tk.StringVar(value=self.state.get("severity", ""))
            ttk.Label(bar, text="  Show:").pack(side="left")
            cb = ttk.Combobox(bar, textvariable=self.severity, state="readonly", width=8,
                              values=["", CE.ERROR, CE.QUERY])
            cb.pack(side="left", padx=4)
            cb.bind("<<ComboboxSelected>>", lambda _e: self._fill_part("Validation"))
        self.boxes[name] = RW.TableBox(tab)

    def _fill_part(self, name: str) -> None:
        if self.ret is None or name not in self.boxes:
            return
        head, rows = CE.table(self.ret, self._PARTS[name])
        if name == "Validation":
            want = self.severity.get()
            self.state["severity"] = want
            rows = [r for r in rows if not want or r[0] == want]
        box = self.boxes[name]
        box.show(head, rows, tags=lambda r: ("bad",) if name == "Validation" and
                 r[0] == CE.ERROR else ("warn",) if name == "Validation" else ())
        if box.tree is not None:
            box.tree.bind("<Double-1>", lambda _e: self._open(name))

    def _open(self, name: str) -> None:
        row = self.boxes[name].selected() if name in self.boxes else None
        if not row:
            return
        adm = row[1] if name in ("Validation", "Attendance", "Exclusions") else row[0]
        p = P.find_by_reference(str(adm))
        if p and self.open_pupil:
            self.open_pupil(p.pupil_id)

    # ── Returns (the old lists) ──────────────────────────────────────

    def _build_runs(self, name: str) -> None:
        tab = self.tabs[name]
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        fv = {"type": tk.StringVar(), "year": tk.StringVar(), "status": tk.StringVar()}
        for key, label, values, width in (("type", "Type:", ["", *CE.RETURN_TYPES], 24),
                                          ("status", "Status:", ["", *CE.RETURN_STATUSES],
                                           12)):
            ttk.Label(bar, text=label).pack(side="left")
            ttk.Combobox(bar, textvariable=fv[key], values=values, state="readonly",
                         width=width).pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Year:").pack(side="left")
        ttk.Entry(bar, textvariable=fv["year"], width=8).pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Apply", command=lambda: self.refresh_runs(name)).pack(
            side="left", padx=2)
        ttk.Button(bar, text="New", command=self.new_return).pack(side="left", padx=2)
        tree = W.tree(tab, _RUN_COLUMNS, height=14, stretch={"type"},
                      tags={**W.STANDARD_TAGS, "overdue": {"background": "#fde2e2"}})
        tree.bind("<Double-1>", lambda _e: self.edit_return(name))
        self.run_trees[name] = tree
        tree._filters = fv  # type: ignore[attr-defined]
        bar2 = ttk.Frame(tab)
        bar2.pack(fill="x", pady=(6, 0))
        for text, cmd in (("Edit", lambda: self.edit_return(name)),
                          ("Validate", lambda: self.move(name, "validate")),
                          ("Submit", lambda: self.move(name, "submit")),
                          ("Accept", lambda: self.move(name, "accept")),
                          ("Reject", lambda: self.move(name, "reject")),
                          ("Resubmit", lambda: self.move(name, "resubmit")),
                          ("Archive", lambda: self.move(name, "archive")),
                          ("Counts", lambda: self.counts(name)),
                          ("Status", lambda: self.set_status(name)),
                          ("Delete", lambda: self.delete(name)),
                          ("Refresh", lambda: self.refresh_runs(name))):
            ttk.Button(bar2, text=text, command=cmd).pack(side="left", padx=2)
        tree._count = tk.StringVar()  # type: ignore[attr-defined]
        ttk.Label(bar2, textvariable=tree._count, foreground="#666").pack(  # type: ignore[attr-defined]
            side="right")

    def refresh_runs(self, name: str) -> None:
        tree = self.run_trees.get(name)
        if tree is None:
            return
        fv = tree._filters  # type: ignore[attr-defined]
        try:
            rows = CE.list_runs(self.principal, academic_year=fv["year"].get().strip() or None,
                                return_type=fv["type"].get() or None,
                                status=fv["status"].get() or None,
                                overdue_only=name == "Overdue",
                                open_only=name == "Open Windows")
        except W.ERRORS as e:
            self._err("School Census", e)
            return
        tree.delete(*tree.get_children())
        for r in rows:
            tag = "overdue" if r["is_overdue"] else _STATUS_TAGS.get(r["status"], "")
            tree.insert("", "end", iid=str(r["return_id"]), tags=(tag,) if tag else (),
                        values=(r["return_id"], "!" if r["is_overdue"] else "",
                                r["return_type"], r["academic_year"], r["census_date"] or "",
                                r["deadline"] or "", r["submitted_on"] or "", r["pupils"],
                                r["errors"], r["queries"], r["status"]))
        tree._count.set(f"{len(rows)} return(s)")  # type: ignore[attr-defined]

    def _selected_run(self, name: str) -> int | None:
        sel = self.run_trees[name].selection()
        if not sel:
            messagebox.showinfo("School Census", "Select a return first.", parent=self._top())
            return None
        return int(sel[0])

    def _fields(self, r: dict[str, Any] | None) -> list:
        r = r or {}
        return [
            ("return_type", "Return type *", r.get("return_type", CE.RETURN_TYPES[0]),
             list(CE.RETURN_TYPES)),
            ("academic_year", "Academic year *", r.get("academic_year", current_year()), None),
            ("census_date", "Reference date", r.get("census_date") or "", None),
            ("status", "Status *", r.get("status", "Planned"), list(CE.RETURN_STATUSES)),
            ("window_opens", "Window opens", r.get("window_opens") or "", None),
            ("window_closes", "Window closes", r.get("window_closes") or "", None),
            ("deadline", "Submission deadline", r.get("deadline") or "", None),
            ("submitted_on", "Submitted on", r.get("submitted_on") or "", None),
            ("submitted_by", "Submitted by", r.get("submitted_by") or "", None),
            ("accepted_on", "Accepted on", r.get("accepted_on") or "", None),
            ("pupils", "Learner count", r.get("pupils", 0), None),
            ("errors", "Error count", r.get("errors", 0), None),
            ("queries", "Warning count", r.get("queries", 0), None),
            ("file_ref", "File ref", r.get("file_ref") or "", None),
            ("notes", "Notes", r.get("notes") or "", "text"),
        ]

    def new_return(self) -> None:
        W.form_dialog(self.parent, "New return", self._fields(None),
                      lambda d: (CE.create_return(d, actor=self.principal),
                                 self._refresh_all()))

    def edit_return(self, name: str) -> None:
        rid = self._selected_run(name)
        if rid is None:
            return
        try:
            r = CE.get_run(self.principal, rid)
        except W.ERRORS as e:
            self._err("Edit return", e)
            return
        W.form_dialog(self.parent, f"Edit return #{rid}", self._fields(r),
                      lambda d: (CE.update_return(rid, d, actor=self.principal),
                                 self._refresh_all()))

    def move(self, name: str, action: str) -> None:
        rid = self._selected_run(name)
        if rid is None:
            return
        file_ref = None
        if action in ("submit", "resubmit"):
            file_ref = simpledialog.askstring("Submit", "File reference (optional):",
                                              parent=self._top())
        try:
            CE.move(rid, action, actor=self.principal, file_ref=file_ref or None)
        except W.ERRORS as e:
            self._err("School Census", e)
            return
        self._refresh_all()

    def counts(self, name: str) -> None:
        rid = self._selected_run(name)
        if rid is None:
            return
        r = CE.get_run(self.principal, rid)
        W.form_dialog(self.parent, f"Validation counts - return #{rid}",
                      [("errors", "Error count", r["errors"], None),
                       ("queries", "Warning count", r["queries"], None)],
                      lambda d: (CE.record_counts(rid, actor=self.principal, **d),
                                 self._refresh_all()))

    def set_status(self, name: str) -> None:
        rid = self._selected_run(name)
        if rid is None:
            return
        r = CE.get_run(self.principal, rid)
        W.form_dialog(self.parent, f"Status - return #{rid}",
                      [("status", "Status", r["status"], list(CE.RETURN_STATUSES))],
                      lambda d: (CE.set_status(rid, d["status"], actor=self.principal),
                                 self._refresh_all()))

    def delete(self, name: str) -> None:
        rid = self._selected_run(name)
        if rid is None or not messagebox.askyesno("Delete return", f"Delete return #{rid}?",
                                                  parent=self._top()):
            return
        try:
            CE.delete_return(rid, actor=self.principal)
        except W.ERRORS as e:
            self._err("Delete return", e)
            return
        self._refresh_all()

    # ── Summary ──────────────────────────────────────────────────────

    def _build_summary(self, name: str) -> None:
        tab = self.tabs[name]
        ttk.Button(tab, text="Refresh", command=self.refresh_summary).pack(anchor="w")
        self.summary = tk.Text(tab, height=20, wrap="word", font=("TkFixedFont", 10))
        self.summary.pack(fill="both", expand=True, pady=(6, 0))

    def refresh_summary(self) -> None:
        if not hasattr(self, "summary"):
            return
        try:
            s = CE.runs_summary(self.principal)
        except W.ERRORS as e:
            self._err("School Census", e)
            return
        lines = [f"Total returns: {s['total']}", f"Planned: {s['planned']}",
                 f"In progress: {s['in_progress']}", f"Submitted: {s['submitted']}",
                 f"Accepted: {s['accepted']}", f"Rejected: {s['rejected']}",
                 f"Overdue: {s['overdue']}", f"Open windows: {s['open_windows']}", "",
                 "By type:", *(f"  {k}: {v}" for k, v in sorted(s["by_type"].items())),
                 "", "By status:", *(f"  {k}: {v}" for k, v in sorted(s["by_status"].items()))]
        try:
            from education_system.systems.secondary.modules.reporting.domain import (
                census_aims as CA,
            )
            a = CA.summary(self.principal)
            lines += ["", f"Total aims: {a['total']} ({a['learners']} learner(s))",
                      f"Continuing: {a['continuing']}", f"Completed: {a['completed']}",
                      f"Achieved: {a['achieved']}", f"Withdrawn: {a['withdrawn']}",
                      "", "By aim status:",
                      *(f"  {k}: {v}" for k, v in sorted(a["by_status"].items()))]
        except W.ERRORS as e:
            lines += ["", f"Aims: {W.problems(e)}"]
        if self.ret is not None:
            lines += ["", "Return built in this window:", *self.ret.summary_lines()]
        self.summary.configure(state="normal")
        self.summary.delete("1.0", "end")
        self.summary.insert("1.0", "\n".join(lines))
        self.summary.configure(state="disabled")


def draw_census(parent: ttk.Frame, *, principal: Principal, state: dict,
                open_pupil: Callable[[int], None] | None = None) -> CensusPage:
    return CensusPage(parent, principal=principal, state=state, open_pupil=open_pupil)
