"""Gradebook screen.

The old window is the Gradebook tab: Year / Pupil / Term / Type filters and
Apply, New entry, Edit, Summary, Delete and Refresh, with the old columns; the
old entry dialog keeps its fields (pupil, subject, assessment name, type, term,
date, marks, max marks, grade, teacher, comments). Added: assessments set to a
class with a whole-class mark sheet, grade boundaries, locking, the cohort
summary, a markbook grid, missing marks, pupils of concern and CSV
export / import. Rules live in :mod:`modules.assessment.domain.gradebook`.
"""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import ttk
from typing import Callable

from education_system.platform.delivery.gui.parented_dialogs import (
    filedialog,
    make_toplevel,
    messagebox,
    simpledialog,
)
from education_system.systems.secondary.modules.assessment.domain import gradebook as GB
from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.modules.curriculum.domain import teaching_groups as TG
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.gui.components import widgets as W

logger = logging.getLogger(__name__)
ALL = ""
YEARS = ("7", "8", "9", "10", "11")
STATUS_BG = {"Marked": "#ffffff", "Absent": "#fde2e2", "Excused": "#eeeeee",
             "Locked": "#eeeeee", "Open": "#ffffff", "low": "#fde2e2", "high": "#e7f6ea"}
_ERRORS = (GB.ValidationError, GB.PermissionDenied, GB.NotFound)


class ScrollFrame(ttk.Frame):
    """A frame whose ``body`` scrolls vertically (long class lists)."""

    def __init__(self, parent) -> None:
        super().__init__(parent)
        canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0)
        bar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        self.body = ttk.Frame(canvas)
        canvas.create_window(0, 0, window=self.body, anchor="nw")
        self.body.bind("<Configure>",
                       lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))


_problems = W.problems


def _tree(parent, columns, height: int = 10, *, multi: bool = False) -> ttk.Treeview:
    return W.tree(parent, columns, height=height, select="extended" if multi else "browse",
                  stretch={"name", "pupil", "why"}, tags=STATUS_BG, xscroll=True)


_text_window = W.text_window


def _grid_rows(frm, rows, start: int = 0) -> None:
    for i, (text, w) in enumerate(rows, start):
        ttk.Label(frm, text=text).grid(row=i, column=0, sticky="nw", pady=2, padx=(0, 8))
        w.grid(row=i, column=1, sticky="w", pady=2)


def _buttons(frm, row: int, win, save, label: str = "Save") -> None:
    bar = ttk.Frame(frm)
    bar.grid(row=row, column=0, columnspan=2, sticky="e", pady=(8, 0))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="right")
    ttk.Button(bar, text=label, command=save).pack(side="right", padx=(0, 6))


def _pct(v) -> str:
    return "-" if v is None else f"{v:g}%"


def _subjects() -> dict[str, S.Subject]:
    return {f"{s.code} - {s.name}": s for s in S.list_subjects()}


def _groups(principal: Principal | None = None) -> dict[str, TG.TeachingGroup]:
    rows = TG.info(TG.list_groups(teacher=principal.username if principal else None))
    return {f"{i.group.code} - {i.subject.code} Y{i.group.year_group}"
            + (f" ({i.group.teacher_name})" if i.group.teacher_name else ""): i.group
            for i in rows if i.group.is_active}


_ENTRY_COLS = (("id", "ID", 45), ("date", "Date", 85), ("pupil", "Pupil", 150),
               ("year", "Yr", 35), ("subj", "Subj", 60), ("term", "Term", 65),
               ("type", "Type", 80), ("name", "Assessment", 200), ("marks", "Marks", 75),
               ("pct", "%", 45), ("grade", "Grade", 50), ("group", "Group", 70),
               ("teacher", "Teacher", 110))
_ASSESS_COLS = (("id", "ID", 45), ("date", "Date", 85), ("for", "For", 75),
                ("subj", "Subj", 60), ("term", "Term", 65), ("type", "Type", 80),
                ("name", "Assessment", 200), ("max", "Out of", 55), ("weight", "Weight", 50),
                ("marked", "Marked", 55), ("teacher", "Teacher", 110), ("status", "Status", 60))


def _entry_row(e: GB.Entry) -> tuple:
    return (e.mark_id, e.assessment_date, e.pupil_name, e.pupil_year, e.subject_code, e.term,
            e.assessment_type, e.assessment_name, e.marks_label,
            "" if e.mark_pct is None else f"{e.mark_pct:.0f}", e.grade or "",
            e.group_code or "", e.teacher or "")


class GradebookPage:
    TABS = ("Gradebook", "Assessments", "Markbook", "Missing marks", "Concerns",
            "Grade boundaries")

    def __init__(self, parent: ttk.Frame, *, principal: Principal, state: dict,
                 open_pupil: Callable[[int], None] | None = None) -> None:
        self.parent, self.principal, self.state = parent, principal, state
        self.open_pupil = open_pupil
        self.editor = GB.is_editor(principal)
        activity_log.record("gradebook.view")
        ttk.Label(parent, text="Gradebook", font=("", 16, "bold")).pack(anchor="w")
        self.summary_var = tk.StringVar()
        ttk.Label(parent, textvariable=self.summary_var, foreground="#666").pack(anchor="w",
                                                                                 pady=(0, 6))
        self.book = ttk.Notebook(parent)
        self.book.pack(fill="both", expand=True)
        self.tabs = {n: ttk.Frame(self.book, padding=8) for n in self.TABS}
        for n, f in self.tabs.items():
            self.book.add(f, text=n)
        self._build_entries(self.tabs["Gradebook"])
        self._build_assessments(self.tabs["Assessments"])
        self.book.select(self.TABS.index(state.get("tab", "Gradebook")))
        self.book.bind("<<NotebookTabChanged>>", self._on_tab)
        self._on_tab()

    def _on_tab(self, _e=None) -> None:
        name = self.TABS[self.book.index(self.book.select())]
        self.state["tab"] = name
        if name == "Gradebook":
            self.refresh()
            return
        if name == "Assessments":
            self.refresh_assessments()
            return
        tab = self.tabs[name]
        for w in tab.winfo_children():
            w.destroy()
        try:
            {"Markbook": self._draw_markbook, "Missing marks": self._draw_missing,
             "Concerns": self._draw_concerns,
             "Grade boundaries": self._draw_boundaries}[name](tab)
        except Exception:
            logger.exception("Gradebook tab %s failed", name)
            ttk.Label(tab, text="Couldn't load this tab - see the log.",
                      foreground="#a00").pack(anchor="w")

    # ── Gradebook tab (old window) ───────────────────────────────────

    def _build_entries(self, tab: ttk.Frame) -> None:
        st = self.state
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self.year_var = tk.StringVar(value=st.get("year", ALL))
        self.pupil_var = tk.StringVar(value=st.get("pupil", ""))
        self.term_var = tk.StringVar(value=st.get("term", ALL))
        self.type_var = tk.StringVar(value=st.get("type", ALL))
        ttk.Label(bar, text="Year:").pack(side="left", padx=(0, 4))
        ttk.Combobox(bar, textvariable=self.year_var, values=[ALL, *YEARS], state="readonly",
                     width=4).pack(side="left")
        ttk.Label(bar, text="Pupil:").pack(side="left", padx=(8, 4))
        ttk.Entry(bar, textvariable=self.pupil_var, width=12).pack(side="left")
        ttk.Label(bar, text="Term:").pack(side="left", padx=(8, 4))
        ttk.Combobox(bar, textvariable=self.term_var, values=[ALL, *GB.TERMS],
                     state="readonly", width=9).pack(side="left")
        ttk.Label(bar, text="Type:").pack(side="left", padx=(8, 4))
        ttk.Combobox(bar, textvariable=self.type_var, values=[ALL, *GB.ASSESSMENT_TYPES],
                     state="readonly", width=11).pack(side="left")
        for text, cmd in (("Apply", self.refresh), ("New entry", self.new_entry),
                          ("Edit", self.edit_entry), ("Summary", self.pupil_summary),
                          ("Delete", self.delete_entry), ("Refresh", self.refresh)):
            ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=2)
        bar2 = ttk.Frame(tab)
        bar2.pack(fill="x", pady=(0, 4))
        ttk.Label(bar2, text="Subject:").pack(side="left", padx=(0, 4))
        self.subjects = _subjects()
        self.subj_var = tk.StringVar(value=st.get("subject", ALL))
        ttk.Combobox(bar2, textvariable=self.subj_var, values=[ALL, *self.subjects],
                     state="readonly", width=22).pack(side="left")
        self.this_year_var = tk.BooleanVar(value=st.get("this_year", True))
        ttk.Checkbutton(bar2, text=f"This school year ({TG.current_year()})",
                        variable=self.this_year_var, command=self.refresh).pack(
            side="left", padx=8)
        ttk.Button(bar2, text="Open pupil", command=self.open_entry_pupil).pack(side="left",
                                                                                 padx=8)
        self.entry_tree = _tree(tab, _ENTRY_COLS, height=16)
        self.entry_tree.bind("<Double-1>", lambda _e: self.edit_entry())
        self.entry_rows: dict[str, GB.Entry] = {}

    def refresh(self) -> None:
        st = self.state
        st.update(year=self.year_var.get(), pupil=self.pupil_var.get(),
                  term=self.term_var.get(), type=self.type_var.get(),
                  subject=self.subj_var.get(), this_year=self.this_year_var.get())
        pid = None
        if self.pupil_var.get().strip():
            p = P.find_by_reference(self.pupil_var.get())
            if p is None:
                messagebox.showinfo("Gradebook", "No pupil with that admission number or UPN.",
                                    parent=self.parent)
                return
            pid = p.pupil_id
        subj = self.subjects.get(self.subj_var.get())
        rows = GB.list_entries(pupil_id=pid, year_group=int(self.year_var.get())
                               if self.year_var.get() else None,
                               term=self.term_var.get() or None,
                               assessment_type=self.type_var.get() or None,
                               subject_id=subj.subject_id if subj else None,
                               academic_year=TG.current_year() if self.this_year_var.get()
                               else None)
        self.entry_tree.delete(*self.entry_tree.get_children())
        self.entry_rows = {}
        for e in rows:
            iid = str(e.mark_id)
            self.entry_rows[iid] = e
            self.entry_tree.insert("", "end", iid=iid, values=_entry_row(e), tags=(e.status,))
        self.summary_var.set(f"{len(rows)} mark(s) shown · "
                             f"{len(GB.list_assessments(academic_year=TG.current_year()))} "
                             f"assessment(s) this year")

    def _entry(self) -> GB.Entry | None:
        sel = self.entry_tree.selection()
        if not sel:
            messagebox.showinfo("Gradebook", "Select an entry first.", parent=self.parent)
            return None
        return self.entry_rows.get(sel[0])

    def new_entry(self) -> None:
        entry_dialog(self.parent, self.principal, None, self.refresh)

    def edit_entry(self) -> None:
        e = self._entry()
        if e:
            entry_dialog(self.parent, self.principal, e, self.refresh)

    def delete_entry(self) -> None:
        e = self._entry()
        if not e or not messagebox.askyesno("Delete entry", f"Delete entry for "
                                            f"{e.pupil_name} — {e.assessment_name}?",
                                            parent=self.parent):
            return
        try:
            GB.delete_entry(e.mark_id, actor=self.principal)
        except _ERRORS as ex:
            messagebox.showerror("Delete entry", _problems(ex), parent=self.parent)
            return
        self.refresh()

    def pupil_summary(self) -> None:
        """The old Summary: one pupil in one subject."""
        e = self.entry_rows.get((self.entry_tree.selection() or [""])[0])
        if e:
            pid, sid, label = e.pupil_id, e.subject_id, f"{e.pupil_name} · {e.subject_code}"
        else:
            ref = simpledialog.askstring("Summary", "Pupil (admission no or UPN):",
                                         parent=self.parent)
            p = P.find_by_reference(ref or "") if ref else None
            if p is None:
                return
            subj = simpledialog.askstring("Summary", "Subject code:", parent=self.parent)
            match = next((s for s in self.subjects.values()
                          if subj and s.code.lower() == subj.strip().lower()), None)
            if match is None:
                messagebox.showerror("Gradebook", "No subject with that code.",
                                     parent=self.parent)
                return
            pid, sid, label = p.pupil_id, match.subject_id, f"{p.display_name} · {match.code}"
        s = GB.pupil_subject_summary(pid, sid)
        lines = [label, f"Entries: {s['count']}", f"Avg %: {_pct(s['avg_pct'])} (weighted)",
                 f"Latest grade: {s['latest_grade'] or '-'}", f"Absent: {s['absent']}", "",
                 "By term: " + "    ".join(f"{k}: {v}" for k, v in s["by_term"].items()), ""]
        lines += [f"{x.assessment_date}  {x.assessment_name[:28]:<28} {x.marks_label:<8} "
                  f"{_pct(x.mark_pct):<6} {x.grade or ''}" for x in s["entries"]]
        _text_window(self.parent, "Gradebook — summary", "\n".join(lines))

    def open_entry_pupil(self) -> None:
        e = self._entry()
        if e and self.open_pupil:
            self.open_pupil(e.pupil_id)

    # ── Assessments ──────────────────────────────────────────────────

    def _build_assessments(self, tab: ttk.Frame) -> None:
        st = self.state
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self.mine_var = tk.BooleanVar(value=st.get("mine", not self.editor))
        ttk.Checkbutton(bar, text="Only mine", variable=self.mine_var,
                        command=self.refresh_assessments).pack(side="left")
        ttk.Label(bar, text="Search:").pack(side="left", padx=(8, 4))
        self.a_search = tk.StringVar(value=st.get("a_search", ""))
        e = ttk.Entry(bar, textvariable=self.a_search, width=16)
        e.pack(side="left")
        e.bind("<Return>", lambda _e: self.refresh_assessments())
        for text, cmd in (("New", self.new_assessment), ("Edit", self.edit_assessment),
                          ("Enter marks", self.enter_marks), ("Summary", self.cohort),
                          ("Lock / unlock", self.lock), ("Delete", self.delete_assessment),
                          ("Import marks…", self.import_marks), ("History", self.history),
                          ("Refresh", self.refresh_assessments)):
            ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=2)
        self.a_tree = _tree(tab, _ASSESS_COLS, height=16)
        self.a_tree.bind("<Double-1>", lambda _e: self.enter_marks())
        self.a_rows: dict[str, GB.Assessment] = {}

    def refresh_assessments(self) -> None:
        self.state.update(mine=self.mine_var.get(), a_search=self.a_search.get())
        rows = GB.list_assessments(academic_year=TG.current_year(),
                                   teacher=self.principal.username if self.mine_var.get()
                                   else None, search=self.a_search.get().strip() or None)
        self.a_tree.delete(*self.a_tree.get_children())
        self.a_rows = {}
        for a in rows:
            iid = str(a.assessment_id)
            self.a_rows[iid] = a
            self.a_tree.insert("", "end", iid=iid, tags=(a.status,), values=(
                a.assessment_id, a.assessment_date, a.for_label, a.subject_code, a.term,
                a.assessment_type, a.name, "" if a.max_marks is None else f"{a.max_marks:g}",
                f"{a.weight:g}", a.marked, a.teacher or "", a.status))
        self.summary_var.set(f"{len(rows)} assessment(s) this school year "
                             f"({TG.current_year()})")

    def _assessment(self) -> GB.Assessment | None:
        sel = self.a_tree.selection()
        if not sel:
            messagebox.showinfo("Gradebook", "Select an assessment first.", parent=self.parent)
            return None
        return self.a_rows.get(sel[0])

    def new_assessment(self) -> None:
        assessment_dialog(self.parent, self.principal, None, self.refresh_assessments)

    def edit_assessment(self) -> None:
        a = self._assessment()
        if a:
            assessment_dialog(self.parent, self.principal, a, self.refresh_assessments)

    def enter_marks(self) -> None:
        a = self._assessment()
        if a:
            MarkSheet(self.parent, self.principal, a, on_close=self.refresh_assessments)

    def cohort(self) -> None:
        a = self._assessment()
        if a:
            _text_window(self.parent, f"{a.name} - summary", cohort_text(a.assessment_id))

    def lock(self) -> None:
        a = self._assessment()
        if not a:
            return
        try:
            GB.set_locked(a.assessment_id, not a.locked, actor=self.principal)
        except _ERRORS as e:
            messagebox.showerror("Lock", _problems(e), parent=self.parent)
            return
        self.refresh_assessments()

    def delete_assessment(self) -> None:
        a = self._assessment()
        if not a or not messagebox.askyesno(
                "Delete assessment", f"Delete '{a.name}' ({a.for_label})"
                + (f" and its {a.marked} mark(s)" if a.marked else "") + "?",
                parent=self.parent):
            return
        try:
            GB.delete(a.assessment_id, actor=self.principal)
        except _ERRORS as e:
            messagebox.showerror("Delete assessment", _problems(e), parent=self.parent)
            return
        self.refresh_assessments()

    def import_marks(self) -> None:
        a = self._assessment()
        if not a:
            return
        path = filedialog.askopenfilename(parent=self.parent, filetypes=[("CSV", "*.csv")],
                                          title="CSV with Admission no, Mark / Grade, "
                                                "Comments")
        if not path:
            return
        try:
            n, notes = GB.import_marks(a.assessment_id, path, actor=self.principal)
        except (*_ERRORS, OSError, UnicodeDecodeError) as e:
            messagebox.showerror("Import marks", _problems(e), parent=self.parent)
            return
        messagebox.showinfo("Import marks", f"Saved {n} mark(s)."
                            + ("\n\n" + "\n".join(notes) if notes else ""), parent=self.parent)
        self.refresh_assessments()

    def history(self) -> None:
        a = self._assessment()
        if not a:
            return
        lines = [f"{h['at']}  {h['actor']:<14} {h['action']:<10} "
                 + ", ".join(f"{k}: {v}" for k, v in h["detail"].items())
                 for h in GB.history(a.assessment_id)]
        _text_window(self.parent, f"{a.name} - history", "\n".join(lines) or "No changes.")

    # ── Markbook ─────────────────────────────────────────────────────

    def _draw_markbook(self, tab: ttk.Frame) -> None:
        groups = _groups(None if self.editor else self.principal) or _groups()
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        gvar = tk.StringVar(value=self.state.get("mb_group") if self.state.get("mb_group")
                            in groups else next(iter(groups), ""))
        term = tk.StringVar(value=self.state.get("mb_term", ALL))
        ttk.Label(bar, text="Group:").pack(side="left", padx=(0, 4))
        ttk.Combobox(bar, textvariable=gvar, values=list(groups), state="readonly",
                     width=34).pack(side="left")
        ttk.Label(bar, text="Term:").pack(side="left", padx=(8, 4))
        ttk.Combobox(bar, textvariable=term, values=[ALL, *GB.TERMS], state="readonly",
                     width=9).pack(side="left")
        holder = ttk.Frame(tab)
        holder.pack(fill="both", expand=True)
        ids: dict[str, int] = {}

        def fill(*_a) -> None:
            self.state.update(mb_group=gvar.get(), mb_term=term.get())
            for w in holder.winfo_children():
                w.destroy()
            g = groups.get(gvar.get())
            if g is None:
                ttk.Label(holder, text="No teaching groups to show.").pack(anchor="w")
                return
            mb = GB.markbook(group_id=g.group_id, term=term.get() or None)
            cols = [("pupil", "Pupil", 170)] + [
                (f"a{a.assessment_id}", f"{a.name[:14]}\n{a.assessment_date[5:]}", 90)
                for a in mb["assessments"]] + [("avg", "Average", 65), ("grade", "Latest", 55)]
            tree = _tree(holder, cols, height=18)
            ids.clear()
            for r in mb["rows"]:
                p = r["pupil"]
                cells = [r["cells"].get(a.assessment_id) for a in mb["assessments"]]
                avg = r["avg_pct"]
                iid = tree.insert("", "end", tags=("low" if avg is not None and avg < 40 else
                                                   "high" if avg is not None and avg >= 70
                                                   else "Marked",), values=(
                    f"{p.legal_last_name}, {p.preferred_name or p.legal_first_name}",
                    *[(c.marks_label + (f" {c.grade}" if c.grade else "")) if c else "·"
                      for c in cells], _pct(avg), r["latest_grade"] or ""))
                ids[iid] = p.pupil_id
            tree.bind("<Double-1>", lambda _e: self.open_pupil(ids[tree.selection()[0]])
                      if tree.selection() and self.open_pupil else None)

        def export() -> None:
            g = groups.get(gvar.get())
            if g is None:
                return
            path = filedialog.asksaveasfilename(parent=tab, defaultextension=".csv",
                                                initialfile=f"markbook-{g.code.replace('/', '-')}.csv",
                                                filetypes=[("CSV", "*.csv")])
            if not path:
                return
            try:
                n = GB.export_markbook(path, actor=self.principal, group_id=g.group_id,
                                       term=term.get() or None)
            except (*_ERRORS, OSError) as e:
                messagebox.showerror("Export", _problems(e), parent=tab)
                return
            messagebox.showinfo("Export", f"Saved {n} pupil(s) to {path}.", parent=tab)
        ttk.Button(bar, text="Export…", command=export).pack(side="left", padx=8)
        gvar.trace_add("write", fill)
        term.trace_add("write", fill)
        fill()

    # ── Missing marks ────────────────────────────────────────────────

    def _draw_missing(self, tab: ttk.Frame) -> None:
        everyone = tk.BooleanVar(value=self.state.get("miss_all", self.editor))
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        tree = _tree(tab, (("date", "Date", 85), ("for", "Group", 80), ("subj", "Subj", 60),
                           ("name", "Assessment", 240), ("teacher", "Teacher", 130),
                           ("n", "Still to mark", 90)), height=16)
        rows: dict[str, GB.Assessment] = {}

        def fill() -> None:
            self.state["miss_all"] = everyone.get()
            tree.delete(*tree.get_children())
            rows.clear()
            for a, n in GB.missing_marks(self.principal, everyone=everyone.get()):
                iid = tree.insert("", "end", values=(a.assessment_date, a.for_label,
                                                     a.subject_code, a.name, a.teacher or "",
                                                     n))
                rows[iid] = a
            if not rows:
                tree.insert("", "end", values=("", "", "", "Nothing waiting to be marked"))

        def open_sheet(_e=None) -> None:
            sel = tree.selection()
            if sel and sel[0] in rows:
                MarkSheet(tab, self.principal, rows[sel[0]], on_close=fill)
        ttk.Checkbutton(bar, text="Everyone's", variable=everyone, command=fill).pack(
            side="left")
        ttk.Button(bar, text="Enter marks", command=open_sheet).pack(side="left", padx=8)
        tree.bind("<Double-1>", open_sheet)
        fill()

    # ── Concerns ─────────────────────────────────────────────────────

    def _draw_concerns(self, tab: ttk.Frame) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        below = tk.StringVar(value=str(self.state.get("below", 40)))
        drop = tk.StringVar(value=str(self.state.get("drop", 15)))
        year = tk.StringVar(value=self.state.get("c_year", ALL))
        for label, var, w in (("Average below %:", below, 5), ("or a drop of:", drop, 5)):
            ttk.Label(bar, text=label).pack(side="left", padx=(8, 4))
            ttk.Entry(bar, textvariable=var, width=w).pack(side="left")
        ttk.Label(bar, text="Year:").pack(side="left", padx=(8, 4))
        ttk.Combobox(bar, textvariable=year, values=[ALL, *YEARS], state="readonly",
                     width=4).pack(side="left")
        tree = _tree(tab, (("pupil", "Pupil", 180), ("adm", "Adm no", 85), ("yr", "Yr", 35),
                           ("subj", "Subj", 60), ("avg", "Average", 70),
                           ("why", "Why", 320)), height=16)
        ids: dict[str, int] = {}

        def fill(*_a) -> None:
            try:
                b, d = float(below.get()), float(drop.get())
            except ValueError:
                messagebox.showerror("Concerns", "Enter numbers.", parent=tab)
                return
            self.state.update(below=b, drop=d, c_year=year.get())
            tree.delete(*tree.get_children())
            ids.clear()
            for c in GB.concerns(below=b, drop=d, year_group=int(year.get()) if year.get()
                                 else None):
                iid = tree.insert("", "end", tags=("low",), values=(
                    c["pupil_name"], c["admission_no"], c["year"], c["subject_code"],
                    _pct(c["avg_pct"]), c["why"]))
                ids[iid] = c["pupil_id"]
        tree.bind("<Double-1>", lambda _e: self.open_pupil(ids[tree.selection()[0]])
                  if tree.selection() and self.open_pupil else None)
        ttk.Button(bar, text="Apply", command=fill).pack(side="left", padx=8)
        year.trace_add("write", fill)
        fill()

    # ── Grade boundaries ─────────────────────────────────────────────

    def _draw_boundaries(self, tab: ttk.Frame) -> None:
        ttk.Label(tab, text="A subject's boundaries turn a % into a grade when a teacher "
                            "doesn't type one (an assessment can have its own). Write them "
                            "as grade:minimum %, highest first.", foreground="#666",
                  wraplength=900, justify="left").pack(anchor="w", pady=(0, 6))
        frm = ScrollFrame(tab)
        frm.pack(fill="both", expand=True)
        body = frm.body
        state = "normal" if self.editor else "disabled"
        vars_: dict[int, tk.StringVar] = {}
        for i, s in enumerate(S.list_subjects()):
            ttk.Label(body, text=f"{s.code} - {s.name}").grid(row=i, column=0, sticky="w",
                                                              padx=(0, 8), pady=2)
            v = tk.StringVar(value=GB.subject_boundaries(s.subject_id) or "")
            ttk.Entry(body, textvariable=v, width=70, state=state).grid(row=i, column=1,
                                                                        sticky="w")
            vars_[s.subject_id] = v
            if self.editor:
                ttk.Button(body, text="GCSE 9-1", command=lambda v=v: v.set(
                    GB.GCSE_BOUNDARIES)).grid(row=i, column=2, padx=4)
        if not self.editor:
            ttk.Label(tab, text="Only a head of department can change these.",
                      foreground="#888").pack(anchor="w", pady=6)
            return

        def save() -> None:
            errors = []
            for sid, v in vars_.items():
                if (GB.subject_boundaries(sid) or "") == v.get().strip():
                    continue
                try:
                    GB.set_subject_boundaries(sid, v.get(), actor=self.principal)
                except _ERRORS as e:
                    errors.append(f"{S.get(sid).code}: {_problems(e)}")
            if errors:
                messagebox.showerror("Grade boundaries", "\n".join(errors), parent=tab)
            else:
                messagebox.showinfo("Grade boundaries", "Saved.", parent=tab)
        ttk.Button(tab, text="Save", command=save).pack(anchor="w", pady=8)


def draw_gradebook(parent: ttk.Frame, *, principal: Principal, state: dict | None = None,
                   open_pupil: Callable[[int], None] | None = None) -> GradebookPage:
    return GradebookPage(parent, principal=principal, state=state if state is not None else {},
                         open_pupil=open_pupil)


def cohort_text(assessment_id: int) -> str:
    s = GB.assessment_summary(assessment_id)
    a = s["assessment"]
    lines = [f"{a.name} · {a.subject_code} {a.for_label} · {a.assessment_date}"
             + (f" · out of {a.max_marks:g}" if a.max_marks else ""), "",
             f"Pupils: {s['count']}   marked {s['marked']} · absent {s['absent']} · excused "
             f"{s['excused']} · still to mark {len(s['missing'])}",
             f"Average: {_pct(s['avg_pct'])}   median {_pct(s['median_pct'])}   highest "
             f"{_pct(s['max_pct'])}   lowest {_pct(s['min_pct'])}",
             "Grades: " + ("  ".join(f"{g}: {n}" for g, n in s["grades"].items()) or "-"), ""]
    lines += [f"{e.pupil_name[:28]:<28} {e.marks_label:<9} {_pct(e.mark_pct):<7} "
              f"{e.grade or '':<4} {e.comments or ''}" for e in s["entries"]]
    if s["missing"]:
        lines += ["", "Still to mark: " + ", ".join(p.display_name for p in s["missing"])]
    return "\n".join(lines)


# ── Mark sheet ───────────────────────────────────────────────────────

class MarkSheet:
    """Enter marks for a whole class at once."""

    def __init__(self, owner, principal: Principal, a: GB.Assessment, *,
                 on_close: Callable[[], None]) -> None:
        self.principal, self.a, self.on_close = principal, a, on_close
        self.win = win = make_toplevel(owner.winfo_toplevel())
        win.title(f"Marks - {a.name} ({a.for_label})")
        win.geometry("860x600")
        win.protocol("WM_DELETE_WINDOW", self.close)
        frm = ttk.Frame(win, padding=10)
        frm.pack(fill="both", expand=True)
        self.pairs = pairs = GB.boundaries_for(a)
        ttk.Label(frm, text=f"{a.subject_code} {a.for_label} · {a.assessment_date} · "
                            + (f"out of {a.max_marks:g}" if a.max_marks else "grades only")
                            + (" · grades from boundaries if left blank" if pairs else "")
                            + (" · LOCKED" if a.locked else ""),
                  foreground="#666").pack(anchor="w")
        bar = ttk.Frame(frm)
        bar.pack(fill="x", pady=6)
        ttk.Button(bar, text="Add pupil…", command=self.add_pupil).pack(side="left")
        ttk.Button(bar, text="Summary", command=lambda: _text_window(
            self.win, f"{a.name} - summary", cohort_text(a.assessment_id))).pack(
            side="left", padx=6)
        self.scroll = ScrollFrame(frm)
        self.scroll.pack(fill="both", expand=True)
        self.rows: dict[int, dict[str, tk.Variable]] = {}
        self._fill()
        foot = ttk.Frame(frm)
        foot.pack(fill="x", pady=(8, 0))
        ttk.Button(foot, text="Close", command=self.close).pack(side="right")
        ttk.Button(foot, text="Save marks", command=self.save,
                   state="disabled" if a.locked else "normal").pack(side="right", padx=6)

    def close(self) -> None:
        self.win.destroy()
        self.on_close()

    def _fill(self, extra: list[P.Pupil] | None = None) -> None:
        body = self.scroll.body
        for w in body.winfo_children():
            w.destroy()
        done = {e.pupil_id: e for e in GB.entries(self.a.assessment_id)}
        pupils = GB.pupils_for(self.a) + [p for p in (extra or [])
                                          if p.pupil_id not in {x.pupil_id for x in
                                                                GB.pupils_for(self.a)}]
        for c, h in enumerate(("Pupil", "Mark", "Grade", "Status", "Comment")):
            ttk.Label(body, text=h, font=("", 9, "bold")).grid(row=0, column=c, sticky="w",
                                                               padx=4)
        keep = {pid: {k: v.get() for k, v in vs.items()} for pid, vs in self.rows.items()}
        self.rows = {}
        for i, p in enumerate(pupils, 1):
            e = done.get(p.pupil_id)
            old = keep.get(p.pupil_id, {})
            v = {"marks_awarded": tk.StringVar(value=old.get("marks_awarded", "" if not e or
                                               e.marks_awarded is None
                                               else f"{e.marks_awarded:g}")),
                 "grade": tk.StringVar(value=old.get("grade", (e.grade or "") if e else "")),
                 "status": tk.StringVar(value=old.get("status", e.status if e else "Marked")),
                 "comments": tk.StringVar(value=old.get("comments", (e.comments or "")
                                                        if e else ""))}
            ttk.Label(body, text=f"{p.legal_last_name}, {p.preferred_name or p.legal_first_name}"
                      ).grid(row=i, column=0, sticky="w", padx=4)
            ttk.Entry(body, textvariable=v["marks_awarded"], width=7).grid(row=i, column=1,
                                                                          padx=4)
            ttk.Entry(body, textvariable=v["grade"], width=5).grid(row=i, column=2, padx=4)
            ttk.Combobox(body, textvariable=v["status"], values=GB.MARK_STATUSES,
                         state="readonly", width=8).grid(row=i, column=3, padx=4)
            ttk.Entry(body, textvariable=v["comments"], width=40).grid(row=i, column=4,
                                                                      padx=4, sticky="w")
            self.rows[p.pupil_id] = v
        if not pupils:
            ttk.Label(body, text="No pupils yet - use Add pupil.").grid(row=1, column=0,
                                                                        columnspan=5)

    def add_pupil(self) -> None:
        ref = simpledialog.askstring("Add pupil", "Admission number or UPN:", parent=self.win)
        p = P.find_by_reference(ref or "") if ref else None
        if p is None:
            if ref:
                messagebox.showinfo("Add pupil", "No pupil with that admission number.",
                                    parent=self.win)
            return
        extra = [P.get_pupil(pid) for pid in self.rows]
        self._fill([x for x in extra if x] + [p])

    def save(self) -> None:
        done = {e.pupil_id: e for e in GB.entries(self.a.assessment_id)}
        changes = {}
        for pid, v in self.rows.items():
            data = {k: var.get().strip() for k, var in v.items()}
            e = done.get(pid)
            if e is None and not (data["marks_awarded"] or data["grade"]) and \
                    data["status"] == "Marked":
                continue  # not marked yet
            if e is not None and data == {
                    "marks_awarded": "" if e.marks_awarded is None else f"{e.marks_awarded:g}",
                    "grade": e.grade or "", "status": e.status, "comments": e.comments or ""}:
                continue
            if e is not None and self.pairs and e.marks_awarded is not None and \
                    data["grade"] == (e.grade or "") and \
                    data["marks_awarded"] != f"{e.marks_awarded:g}":
                data["grade"] = ""  # a new mark: work the grade out again
            changes[pid] = data
        if not changes:
            messagebox.showinfo("Marks", "Nothing changed.", parent=self.win)
            return
        try:
            n = GB.record_marks(self.a.assessment_id, changes, actor=self.principal)
        except _ERRORS as e:
            messagebox.showerror("Marks", _problems(e), parent=self.win)
            return
        messagebox.showinfo("Marks", f"Saved {n} mark(s).", parent=self.win)
        self._fill()


# ── Dialogs ──────────────────────────────────────────────────────────

def assessment_dialog(owner, principal: Principal, a: GB.Assessment | None,
                      after: Callable[[], None]) -> None:
    win = make_toplevel(owner.winfo_toplevel())
    win.title("Edit assessment" if a else "New assessment")
    win.resizable(False, False)
    frm = ttk.Frame(win, padding=12)
    frm.pack(fill="both", expand=True)
    groups = _groups(None if GB.is_editor(principal) else principal)
    subjects = _subjects()
    gvar = tk.StringVar(value=next((k for k, g in groups.items() if a and g.group_id ==
                                    a.group_id), ""))
    svar = tk.StringVar(value=next((k for k, s in subjects.items() if a and s.subject_id ==
                                    a.subject_id), ""))
    year = tk.StringVar(value=str(a.year_group) if a else "")
    v = {k: tk.StringVar(value="" if not a or getattr(a, k) is None else
                         (f"{getattr(a, k):g}" if isinstance(getattr(a, k), float)
                          else str(getattr(a, k))))
         for k in ("name", "assessment_date", "max_marks", "weight", "boundaries", "teacher")}
    if not a:
        v["assessment_date"].set(_dt.date.today().isoformat())
        v["weight"].set("1")
    atype = tk.StringVar(value=a.assessment_type if a else "Test")
    term = tk.StringVar(value=a.term if a else "")
    notes = tk.Text(frm, width=50, height=3, wrap="word")
    notes.insert("1.0", (a.notes or "") if a else "")
    rows = [("Teaching group:", ttk.Combobox(frm, textvariable=gvar, values=["", *groups],
                                             state="readonly", width=40)),
            ("or Subject:", ttk.Combobox(frm, textvariable=svar, values=["", *subjects],
                                         state="readonly", width=30)),
            ("and Year:", ttk.Combobox(frm, textvariable=year, values=["", *YEARS],
                                       state="readonly", width=4)),
            ("Assessment name:", ttk.Entry(frm, textvariable=v["name"], width=40)),
            ("Type:", ttk.Combobox(frm, textvariable=atype, values=GB.ASSESSMENT_TYPES,
                                   state="readonly", width=14)),
            ("Term (blank = from date):", ttk.Combobox(frm, textvariable=term,
                                                       values=["", *GB.TERMS],
                                                       state="readonly", width=10)),
            ("Date:", ttk.Entry(frm, textvariable=v["assessment_date"], width=12)),
            ("Out of (max marks):", ttk.Entry(frm, textvariable=v["max_marks"], width=8)),
            ("Weight:", ttk.Entry(frm, textvariable=v["weight"], width=6)),
            ("Grade boundaries:", ttk.Entry(frm, textvariable=v["boundaries"], width=50)),
            ("Teacher:", ttk.Entry(frm, textvariable=v["teacher"], width=30)),
            ("Notes:", notes)]
    _grid_rows(frm, rows)
    ttk.Label(frm, text="Boundaries blank = the subject's. e.g. " + GB.GCSE_BOUNDARIES,
              foreground="#888").grid(row=len(rows), column=0, columnspan=2, sticky="w")

    def save() -> None:
        g = groups.get(gvar.get())
        s = subjects.get(svar.get())
        data = {k: var.get() for k, var in v.items()}
        data.update(group_id=g.group_id if g else "", subject_id=(s.subject_id if s else
                                                                  g.subject_id if g else ""),
                    year_group=year.get(), assessment_type=atype.get(), term=term.get(),
                    notes=notes.get("1.0", "end"))
        try:
            if a:
                GB.update(a.assessment_id, data, actor=principal)
            else:
                GB.create(data, actor=principal)
        except _ERRORS as e:
            messagebox.showerror("Assessment", _problems(e), parent=win)
            return
        win.destroy()
        after()
    _buttons(frm, len(rows) + 1, win, save)


def entry_dialog(owner, principal: Principal, entry: GB.Entry | None,
                 after: Callable[[], None]) -> None:
    """The old New entry / Edit dialog."""
    win = make_toplevel(owner.winfo_toplevel())
    win.title(f"Edit entry #{entry.mark_id}" if entry else "New entry")
    win.resizable(False, False)
    frm = ttk.Frame(win, padding=12)
    frm.pack(fill="both", expand=True)
    subjects = _subjects()
    e = entry
    pupil = tk.StringVar(value=e.admission_no if e else "")
    subj = tk.StringVar(value=next((k for k, s in subjects.items() if e and
                                    s.subject_id == e.subject_id), ""))
    name = tk.StringVar(value=e.assessment_name if e else "")
    atype = tk.StringVar(value=e.assessment_type if e else "Test")
    term = tk.StringVar(value=e.term if e else "")
    day = tk.StringVar(value=e.assessment_date if e else _dt.date.today().isoformat())
    marks = tk.StringVar(value="" if not e or e.marks_awarded is None else
                         f"{e.marks_awarded:g}")
    mx = tk.StringVar(value="" if not e or e.max_marks is None else f"{e.max_marks:g}")
    grade = tk.StringVar(value=(e.grade or "") if e else "")
    status = tk.StringVar(value=e.status if e else "Marked")
    teacher = tk.StringVar(value=(e.teacher or "") if e else "")
    comments = tk.Text(frm, width=40, height=3, wrap="word")
    comments.insert("1.0", (e.comments or "") if e else "")
    locked = e is not None  # the assessment is chosen; edit its mark here
    st = "disabled" if locked else "normal"
    rows = [("Pupil (admission no):", ttk.Entry(frm, textvariable=pupil, width=14, state=st)),
            ("Subject:", ttk.Combobox(frm, textvariable=subj, values=list(subjects),
                                      state="disabled" if locked else "readonly", width=42)),
            ("Assessment name:", ttk.Entry(frm, textvariable=name, width=40, state=st)),
            ("Type:", ttk.Combobox(frm, textvariable=atype, values=GB.ASSESSMENT_TYPES,
                                   state="disabled" if locked else "readonly", width=14)),
            ("Term:", ttk.Combobox(frm, textvariable=term, values=["", *GB.TERMS],
                                   state="disabled" if locked else "readonly", width=10)),
            ("Date:", ttk.Entry(frm, textvariable=day, width=14, state=st)),
            ("Marks awarded:", ttk.Entry(frm, textvariable=marks, width=8)),
            ("Max marks:", ttk.Entry(frm, textvariable=mx, width=8, state=st)),
            ("Grade:", ttk.Entry(frm, textvariable=grade, width=6)),
            ("Status:", ttk.Combobox(frm, textvariable=status, values=GB.MARK_STATUSES,
                                     state="readonly", width=10)),
            ("Teacher:", ttk.Entry(frm, textvariable=teacher, width=24, state=st)),
            ("Comments:", comments)]
    _grid_rows(frm, rows)

    def save() -> None:
        try:
            if e:
                data = {"marks_awarded": marks.get(), "grade": grade.get(),
                        "status": status.get(), "comments": comments.get("1.0", "end")}
                if GB.boundaries_for(GB.get(e.assessment_id)) and e.marks_awarded is not None \
                        and grade.get().strip() == (e.grade or "") \
                        and marks.get().strip() != f"{e.marks_awarded:g}":
                    data["grade"] = ""
                GB.record_marks(e.assessment_id, {e.pupil_id: data}, actor=principal)
            else:
                s = subjects.get(subj.get())
                GB.record_entry({"pupil": pupil.get(), "subject_id": s.subject_id if s else "",
                                 "assessment_name": name.get(), "assessment_type": atype.get(),
                                 "term": term.get(), "assessment_date": day.get(),
                                 "marks_awarded": marks.get(), "max_marks": mx.get(),
                                 "grade": grade.get(), "status": status.get(),
                                 "teacher": teacher.get(),
                                 "comments": comments.get("1.0", "end")}, actor=principal)
        except _ERRORS as ex:
            messagebox.showerror("Gradebook", _problems(ex), parent=win)
            return
        win.destroy()
        after()
    _buttons(frm, len(rows), win, save)
