"""Target Grades screen.

The old window is the Targets tab: Year / Pupil / Source filters with Apply,
New / update, Edit, Delete and Refresh, the old columns (ID, Pupil, Yr, Name,
Subj, Target, Min, Asp, Source, Set on) and the old dialog (pupil, subject,
target, minimum, aspirational, source, set by, set date, notes). Added: a
subject filter, history, CSV export / import, a whole-class sheet, missing
targets, progress against target and the distribution. Rules live in
:mod:`modules.assessment.domain.target_grades`.
"""

from __future__ import annotations

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
from education_system.systems.secondary.modules.assessment.domain import target_grades as TGR
from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.modules.curriculum.domain import teaching_groups as TG
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.gui.components import widgets as W

logger = logging.getLogger(__name__)
ALL = ""
YEARS = ("7", "8", "9", "10", "11")
STATUS_BG = {"Above": "#e7f6ea", "On track": "#ffffff", "Below": "#fff6d6",
             "Well below": "#fde2e2", "No data": "#eeeeee", "Different scale": "#eeeeee",
             "low": "#fde2e2"}
_ERRORS = (TGR.ValidationError, TGR.PermissionDenied, TGR.NotFound)


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


def _tree(parent, columns, height: int = 10) -> ttk.Treeview:
    return W.tree(parent, columns, height=height, stretch={"name", "pupils"}, tags=STATUS_BG)


_text_window = W.text_window


def _subjects() -> dict[str, S.Subject]:
    return {f"{s.code} - {s.name}": s for s in S.list_subjects()}


def _groups(principal: Principal | None = None) -> dict[str, TG.TeachingGroup]:
    rows = TG.info(TG.list_groups(academic_year=TG.current_year(),
                                  teacher=principal.username if principal else None))
    return {f"{i.group.code} - {i.subject.code} Y{i.group.year_group}"
            + (f" ({i.group.teacher_name})" if i.group.teacher_name else ""): i.group
            for i in rows if i.group.is_active}


def history_text(pupil_id: int, subject_id: int | None = None) -> str:
    rows = TGR.history(pupil_id, subject_id)
    return "\n".join(
        f"{h['at']}  {h['actor']:<14} {h['subject_code'] or '':<6} {h['action']:<7} "
        f"{h['old'] or '-'} → {h['new'] or '-'}"
        + (f"  ({h['reason']})" if h["reason"] else "") for h in rows) or "No history."


class TargetGradesPage:
    TABS = ("Targets", "Class targets", "Missing targets", "Progress", "Distribution")

    def __init__(self, parent: ttk.Frame, *, principal: Principal, state: dict,
                 open_pupil: Callable[[int], None] | None = None) -> None:
        self.parent, self.principal, self.state = parent, principal, state
        self.open_pupil = open_pupil
        self.editor = TGR.is_editor(principal)
        activity_log.record("targets.view")
        ttk.Label(parent, text="Target Grades", font=("", 16, "bold")).pack(anchor="w")
        self.summary_var = tk.StringVar()
        ttk.Label(parent, textvariable=self.summary_var, foreground="#666").pack(anchor="w",
                                                                                 pady=(0, 6))
        self.book = ttk.Notebook(parent)
        self.book.pack(fill="both", expand=True)
        self.tabs = {n: ttk.Frame(self.book, padding=8) for n in self.TABS}
        for n, f in self.tabs.items():
            self.book.add(f, text=n)
        self._build_targets(self.tabs["Targets"])
        self.book.select(self.TABS.index(state.get("tab", "Targets")))
        self.book.bind("<<NotebookTabChanged>>", self._on_tab)
        self._on_tab()

    def _on_tab(self, _e=None) -> None:
        name = self.TABS[self.book.index(self.book.select())]
        self.state["tab"] = name
        if name == "Targets":
            self.refresh()
            return
        tab = self.tabs[name]
        for w in tab.winfo_children():
            w.destroy()
        try:
            {"Class targets": self._draw_class, "Missing targets": self._draw_missing,
             "Progress": self._draw_progress, "Distribution": self._draw_distribution}[name](tab)
        except Exception:
            logger.exception("Target grades tab %s failed", name)
            ttk.Label(tab, text="Couldn't load this tab - see the log.",
                      foreground="#a00").pack(anchor="w")

    # ── Targets (old window) ─────────────────────────────────────────

    def _build_targets(self, tab: ttk.Frame) -> None:
        st = self.state
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self.year_var = tk.StringVar(value=st.get("year", ALL))
        self.pupil_var = tk.StringVar(value=st.get("pupil", ""))
        self.src_var = tk.StringVar(value=st.get("source", ALL))
        ttk.Label(bar, text="Year:").pack(side="left", padx=(0, 4))
        ttk.Combobox(bar, textvariable=self.year_var, values=[ALL, *YEARS], state="readonly",
                     width=4).pack(side="left")
        ttk.Label(bar, text="Pupil:").pack(side="left", padx=(8, 4))
        e = ttk.Entry(bar, textvariable=self.pupil_var, width=12)
        e.pack(side="left")
        e.bind("<Return>", lambda _e: self.refresh())
        ttk.Label(bar, text="Source:").pack(side="left", padx=(8, 4))
        ttk.Combobox(bar, textvariable=self.src_var, values=[ALL, *TGR.GRADE_SOURCES],
                     state="readonly", width=9).pack(side="left")
        for text, cmd in (("Apply", self.refresh), ("New / update", self.new_target),
                          ("Edit", self.edit_target), ("Delete", self.delete_target),
                          ("Refresh", self.refresh)):
            ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=2)
        bar2 = ttk.Frame(tab)
        bar2.pack(fill="x", pady=(0, 4))
        self.subjects = _subjects()
        self.subj_var = tk.StringVar(value=st.get("subject", ALL))
        ttk.Label(bar2, text="Subject:").pack(side="left", padx=(0, 4))
        ttk.Combobox(bar2, textvariable=self.subj_var, values=[ALL, *self.subjects],
                     state="readonly", width=22).pack(side="left")
        for text, cmd in (("History", self.history), ("Open pupil", self.open_selected),
                          ("Export CSV", self.export),
                          *((("Import CSV…", self.import_csv),) if self.editor else ())):
            ttk.Button(bar2, text=text, command=cmd).pack(side="left", padx=2)
        self.tree = _tree(tab, (("id", "ID", 45), ("pupil", "Pupil", 85), ("year", "Yr", 35),
                                ("name", "Name", 180), ("subj", "Subj", 60),
                                ("target", "Target", 75), ("min", "Min", 60),
                                ("asp", "Asp", 60), ("source", "Source", 75),
                                ("set", "Set on", 85), ("by", "Set by", 100)), height=16)
        self.tree.bind("<Double-1>", lambda _e: self.edit_target())
        self.rows: dict[str, TGR.TargetGrade] = {}
        for v in (self.year_var, self.src_var, self.subj_var):
            v.trace_add("write", lambda *_a: self.refresh())

    def refresh(self) -> None:
        st = self.state
        st.update(year=self.year_var.get(), pupil=self.pupil_var.get(),
                  source=self.src_var.get(), subject=self.subj_var.get())
        s = self.subjects.get(self.subj_var.get())
        try:
            rows = TGR.list_targets(year_group=self.year_var.get() or None,
                                    pupil=self.pupil_var.get().strip() or None,
                                    source=self.src_var.get() or None,
                                    subject_id=s.subject_id if s else None)
        except _ERRORS as e:
            messagebox.showerror("Target Grades", _problems(e), parent=self.tree)
            return
        self.tree.delete(*self.tree.get_children())
        self.rows.clear()
        for t in rows:
            iid = self.tree.insert("", "end", values=(
                t.target_id, t.admission_no, t.pupil_year, t.pupil_name, t.subject_code,
                t.target_grade, t.minimum_grade or "-", t.aspirational_grade or "-",
                t.source, t.set_date, t.set_by or ""))
            self.rows[iid] = t
        self.summary_var.set(f"{len(rows)} target(s) listed")

    def _selected(self) -> TGR.TargetGrade | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Target Grades", "Select a target first.", parent=self.tree)
            return None
        return self.rows[sel[0]]

    def new_target(self) -> None:
        target_dialog(self.tree, self.principal, None, on_saved=self.refresh)

    def edit_target(self) -> None:
        t = self._selected()
        if t:
            target_dialog(self.tree, self.principal, t, on_saved=self.refresh)

    def delete_target(self) -> None:
        t = self._selected()
        if not t:
            return
        if not messagebox.askyesno("Delete target", f"Delete target for {t.pupil_name} / "
                                   f"{t.subject_code}?", parent=self.tree):
            return
        reason = simpledialog.askstring("Delete target", "Reason (optional):",
                                        parent=self.tree)
        try:
            TGR.delete(t.target_id, actor=self.principal, reason=reason)
        except _ERRORS as e:
            messagebox.showerror("Target Grades", _problems(e), parent=self.tree)
            return
        self.refresh()

    def history(self) -> None:
        t = self._selected()
        if t:
            _text_window(self.tree, f"{t.pupil_name} - {t.subject_code} target history",
                         history_text(t.pupil_id, t.subject_id))

    def open_selected(self) -> None:
        t = self._selected()
        if t and self.open_pupil:
            self.open_pupil(t.pupil_id)

    def export(self) -> None:
        path = filedialog.asksaveasfilename(parent=self.tree, defaultextension=".csv",
                                            initialfile="target-grades.csv",
                                            filetypes=[("CSV", "*.csv")])
        if not path:
            return
        s = self.subjects.get(self.subj_var.get())
        try:
            n = TGR.export_csv(path, actor=self.principal,
                               year_group=self.year_var.get() or None,
                               subject_id=s.subject_id if s else None,
                               source=self.src_var.get() or None,
                               pupil=self.pupil_var.get().strip() or None)
        except (*_ERRORS, OSError) as e:
            messagebox.showerror("Export", _problems(e), parent=self.tree)
            return
        messagebox.showinfo("Export", f"Exported {n} target(s).", parent=self.tree)

    def import_csv(self) -> None:
        messagebox.showinfo("Import", "Columns: Admission no, Subject (code), Target, and "
                            "optionally Minimum, Aspirational, Source, Set date, Notes.\n\n"
                            "Nothing is saved unless every row is valid.", parent=self.tree)
        path = filedialog.askopenfilename(parent=self.tree, filetypes=[("CSV", "*.csv")])
        if not path:
            return
        source = simpledialog.askstring("Import", "Source for rows without one (blank = "
                                        "Teacher):", parent=self.tree)
        try:
            r = TGR.import_csv(path, actor=self.principal, source=source or None)
        except (*_ERRORS, OSError, UnicodeDecodeError) as e:
            messagebox.showerror("Import", _problems(e), parent=self.tree)
            return
        messagebox.showinfo("Import", f"New {r['set']} · changed {r['changed']} · unchanged "
                            f"{r['unchanged']}", parent=self.tree)
        self.refresh()

    # ── Class targets ────────────────────────────────────────────────

    def _draw_class(self, tab: ttk.Frame) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        mine = tk.BooleanVar(value=self.state.get("mine", not self.editor))
        gvar = tk.StringVar()
        ttk.Label(bar, text="Group:").pack(side="left", padx=(0, 4))
        gbox = ttk.Combobox(bar, textvariable=gvar, state="readonly", width=36)
        gbox.pack(side="left")
        ttk.Checkbutton(bar, text="My groups", variable=mine).pack(side="left", padx=6)
        holder = ttk.Frame(tab)
        holder.pack(fill="both", expand=True)
        groups: dict[str, TG.TeachingGroup] = {}

        def load_groups(*_a) -> None:
            self.state["mine"] = mine.get()
            groups.clear()
            groups.update(_groups(self.principal if mine.get() else None))
            gbox.configure(values=list(groups))
            want = self.state.get("group")
            gvar.set(next((k for k, g in groups.items() if g.group_id == want), None)
                     or next(iter(groups), ""))

        def load(*_a) -> None:
            for w in holder.winfo_children():
                w.destroy()
            g = groups.get(gvar.get())
            if g is None:
                ttk.Label(holder, text="No teaching groups this year.").pack(anchor="w")
                return
            self.state["group"] = g.group_id
            ClassSheet(holder, self.principal, g, open_pupil=self.open_pupil)
        mine.trace_add("write", lambda *_a: (load_groups(), load()))
        gvar.trace_add("write", load)
        load_groups()
        load()

    # ── Missing ──────────────────────────────────────────────────────

    def _draw_missing(self, tab: ttk.Frame) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        year = tk.StringVar(value=self.state.get("m_year", ALL))
        mine = tk.BooleanVar(value=self.state.get("m_mine", not self.editor))
        ttk.Label(bar, text="Year:").pack(side="left", padx=(0, 4))
        ttk.Combobox(bar, textvariable=year, values=[ALL, *YEARS], state="readonly",
                     width=4).pack(side="left")
        ttk.Checkbutton(bar, text="My groups", variable=mine).pack(side="left", padx=6)
        total = tk.StringVar()
        ttk.Label(bar, textvariable=total, foreground="#666").pack(side="left", padx=8)
        tree = _tree(tab, (("group", "Group", 100), ("subj", "Subj", 60), ("yr", "Yr", 35),
                           ("teacher", "Teacher", 140), ("n", "Missing", 60),
                           ("pupils", "Pupils", 420)), height=16)
        gids: dict[str, int] = {}

        def fill(*_a) -> None:
            self.state.update(m_year=year.get(), m_mine=mine.get())
            tree.delete(*tree.get_children())
            gids.clear()
            rows = TGR.missing(year_group=int(year.get()) if year.get() else None,
                               teacher=self.principal.username if mine.get() else None)
            for g, pupils in rows:
                iid = tree.insert("", "end", tags=("low",), values=(
                    g.code, S.get(g.subject_id).code, g.year_group, g.teacher_name or "",
                    len(pupils), ", ".join(p.display_name for p in pupils)))
                gids[iid] = g.group_id
            total.set(f"{sum(len(p) for _g, p in rows)} pupil-subject(s) without a target")

        def open_group(_e=None) -> None:
            sel = tree.selection()
            if sel:
                self.state["group"] = gids[sel[0]]
                self.book.select(self.TABS.index("Class targets"))
        tree.bind("<Double-1>", open_group)
        ttk.Button(bar, text="Set targets for group", command=open_group).pack(side="left")
        year.trace_add("write", fill)
        mine.trace_add("write", fill)
        fill()

    # ── Progress ─────────────────────────────────────────────────────

    def _draw_progress(self, tab: ttk.Frame) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        year = tk.StringVar(value=self.state.get("p_year", ALL))
        subj = tk.StringVar(value=self.state.get("p_subject", ALL))
        status = tk.StringVar(value=self.state.get("p_status", ALL))
        ttk.Label(bar, text="Year:").pack(side="left", padx=(0, 4))
        ttk.Combobox(bar, textvariable=year, values=[ALL, *YEARS], state="readonly",
                     width=4).pack(side="left")
        ttk.Label(bar, text="Subject:").pack(side="left", padx=(8, 4))
        ttk.Combobox(bar, textvariable=subj, values=[ALL, *self.subjects], state="readonly",
                     width=22).pack(side="left")
        ttk.Label(bar, text="Status:").pack(side="left", padx=(8, 4))
        ttk.Combobox(bar, textvariable=status, values=[ALL, *TGR.STATUSES], state="readonly",
                     width=13).pack(side="left")
        totals = tk.StringVar()
        ttk.Label(tab, textvariable=totals, foreground="#666").pack(anchor="w")
        tree = _tree(tab, (("name", "Pupil", 180), ("adm", "Adm no", 85), ("yr", "Yr", 35),
                           ("subj", "Subj", 60), ("target", "Target", 75),
                           ("now", "Now", 85), ("from", "From", 130),
                           ("status", "Status", 95)), height=16)
        ids: dict[str, int] = {}

        def fill(*_a) -> None:
            self.state.update(p_year=year.get(), p_subject=subj.get(), p_status=status.get())
            s = self.subjects.get(subj.get())
            f = {"year_group": int(year.get()) if year.get() else None,
                 "subject_id": s.subject_id if s else None}
            tree.delete(*tree.get_children())
            ids.clear()
            for r in TGR.progress(**f, status=status.get() or None):
                t = r["target"]
                iid = tree.insert("", "end", tags=(r["status"],), values=(
                    t.pupil_name, t.admission_no, t.pupil_year, t.subject_code,
                    t.target_grade, r["current"] or "-", r["from"] or "", r["status"]))
                ids[iid] = t.pupil_id
            totals.set("  ".join(f"{k}: {v}" for k, v in TGR.progress_summary(**f).items()))
        tree.bind("<Double-1>", lambda _e: self.open_pupil(ids[tree.selection()[0]])
                  if tree.selection() and self.open_pupil else None)
        for v in (year, subj, status):
            v.trace_add("write", fill)
        fill()

    # ── Distribution (old) ───────────────────────────────────────────

    def _draw_distribution(self, tab: ttk.Frame) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        year = tk.StringVar(value=self.state.get("d_year", ALL))
        subj = tk.StringVar(value=self.state.get("d_subject", ALL))
        ttk.Label(bar, text="Year:").pack(side="left", padx=(0, 4))
        ttk.Combobox(bar, textvariable=year, values=[ALL, *YEARS], state="readonly",
                     width=4).pack(side="left")
        ttk.Label(bar, text="Subject:").pack(side="left", padx=(8, 4))
        ttk.Combobox(bar, textvariable=subj, values=[ALL, *self.subjects], state="readonly",
                     width=22).pack(side="left")
        tree = _tree(tab, (("grade", "Target", 90), ("n", "Pupils", 70),
                           ("bar", "", 400)), height=16)

        def fill(*_a) -> None:
            self.state.update(d_year=year.get(), d_subject=subj.get())
            s = self.subjects.get(subj.get())
            d = TGR.distribution(year_group=year.get() or None,
                                 subject_id=s.subject_id if s else None)
            tree.delete(*tree.get_children())
            top = max(d.values(), default=0)
            for grade, n in d.items():
                tree.insert("", "end", values=(grade, n, "█" * round(n * 40 / top)
                                               if top else ""))
            tree.insert("", "end", values=("Total", sum(d.values()), ""))
        year.trace_add("write", fill)
        subj.trace_add("write", fill)
        fill()


def draw_target_grades(parent: ttk.Frame, *, principal: Principal, state: dict | None = None,
                       open_pupil: Callable[[int], None] | None = None) -> TargetGradesPage:
    return TargetGradesPage(parent, principal=principal,
                            state=state if state is not None else {}, open_pupil=open_pupil)


# ── Class sheet ──────────────────────────────────────────────────────

class ClassSheet:
    """A teaching group's targets, a row per pupil."""

    def __init__(self, parent, principal: Principal, g: TG.TeachingGroup, *,
                 open_pupil: Callable[[int], None] | None = None) -> None:
        self.principal, self.g, self.open_pupil = principal, g, open_pupil
        subject = S.get(g.subject_id)
        names = TGR.scales_for(g.year_group, subject)
        self.grades = ("", *(x for n in names for x in TGR.SCALES[n]))
        bar = ttk.Frame(parent)
        bar.pack(fill="x", pady=4)
        self.source = tk.StringVar(value=TGR.DEFAULT_SOURCE)
        ttk.Label(bar, text=f"{g.code} · {subject.code} · Year {g.year_group} · "
                            f"{g.teacher_name or 'no teacher'}   Source for new targets:"
                  ).pack(side="left")
        ttk.Combobox(bar, textvariable=self.source, values=TGR.GRADE_SOURCES,
                     state="readonly", width=9).pack(side="left", padx=4)
        ttk.Button(bar, text="Save targets", command=self.save).pack(side="left", padx=6)
        ttk.Label(parent, text="Teachers can set and raise targets; only the data manager "
                               "can lower one. To remove a target use Delete on the Targets "
                               "tab.", foreground="#666").pack(anchor="w")
        self.scroll = ScrollFrame(parent)
        self.scroll.pack(fill="both", expand=True)
        self.rows: dict[int, dict[str, tk.StringVar]] = {}
        self._fill()

    def _fill(self) -> None:
        body = self.scroll.body
        for w in body.winfo_children():
            w.destroy()
        for c, h in enumerate(("Pupil", "Target", "Minimum", "Aspirational", "Source",
                               "Notes")):
            ttk.Label(body, text=h, font=("", 9, "bold")).grid(row=0, column=c, sticky="w",
                                                               padx=4)
        self.rows = {}
        rows = TGR.class_sheet(self.g.group_id)
        for i, (p, t) in enumerate(rows, 1):
            ttk.Label(body, text=f"{p.legal_last_name}, {p.preferred_name or p.legal_first_name}"
                      ).grid(row=i, column=0, sticky="w", padx=4)
            v = {"target_grade": tk.StringVar(value=t.target_grade if t else ""),
                 "minimum_grade": tk.StringVar(value=(t.minimum_grade or "") if t else ""),
                 "aspirational_grade": tk.StringVar(value=(t.aspirational_grade or "")
                                                    if t else ""),
                 "notes": tk.StringVar(value=(t.notes or "") if t else "")}
            for c, k in enumerate(("target_grade", "minimum_grade", "aspirational_grade"), 1):
                ttk.Combobox(body, textvariable=v[k], values=self.grades, state="readonly",
                             width=11).grid(row=i, column=c, padx=4, pady=1)
            ttk.Label(body, text=t.source if t else "-").grid(row=i, column=4, sticky="w",
                                                             padx=4)
            ttk.Entry(body, textvariable=v["notes"], width=36).grid(row=i, column=5, padx=4,
                                                                   sticky="w")
            self.rows[p.pupil_id] = v
        if not rows:
            ttk.Label(body, text="No pupils in this group.").grid(row=1, column=0,
                                                                  columnspan=4)

    def save(self) -> None:
        have = {p.pupil_id: t for p, t in TGR.class_sheet(self.g.group_id)}
        changes = {}
        for pid, v in self.rows.items():
            d = {k: var.get().strip() for k, var in v.items()}
            t = have.get(pid)
            old = {k: (getattr(t, k) or "") if t else "" for k in d}
            if d != old and d["target_grade"]:
                if t is None:
                    d["source"] = self.source.get()
                changes[pid] = d
        owner = self.scroll
        if not changes:
            messagebox.showinfo("Targets", "Nothing changed.", parent=owner)
            return
        reason = None
        if TGR.is_editor(self.principal) and any(
                have.get(pid) and TGR._lowered(have[pid], d["target_grade"])
                for pid, d in changes.items()):
            reason = simpledialog.askstring("Lowering targets", "Reason for lowering:",
                                            parent=owner)
            if not reason:
                return
        try:
            n = TGR.save_class(self.g.group_id, changes, actor=self.principal, reason=reason)
        except _ERRORS as e:
            messagebox.showerror("Targets", _problems(e), parent=owner)
            return
        messagebox.showinfo("Targets", f"Saved {n} target(s).", parent=owner)
        self._fill()


# ── Dialog (old fields) ──────────────────────────────────────────────

def target_dialog(owner, principal: Principal, t: TGR.TargetGrade | None, *,
                  on_saved: Callable[[], None]) -> None:
    win = make_toplevel(owner.winfo_toplevel())
    win.title(f"Edit target #{t.target_id}" if t else "Set target grade")
    frm = ttk.Frame(win, padding=12)
    frm.pack(fill="both", expand=True)
    subjects = _subjects()
    pupil = tk.StringVar(value=t.admission_no if t else "")
    subj = tk.StringVar(value=next((k for k, s in subjects.items()
                                    if t and s.subject_id == t.subject_id), ""))
    target = tk.StringVar(value=t.target_grade if t else "")
    lo = tk.StringVar(value=(t.minimum_grade or "") if t else "")
    hi = tk.StringVar(value=(t.aspirational_grade or "") if t else "")
    src = tk.StringVar(value=t.source if t else TGR.DEFAULT_SOURCE)
    by = tk.StringVar(value=(t.set_by or "") if t else principal.username)
    when = tk.StringVar(value=t.set_date if t else "")
    reason = tk.StringVar()
    scale_hint = tk.StringVar()
    grade_boxes: list[ttk.Combobox] = []

    def scales(*_a) -> None:
        s = subjects.get(subj.get())
        p = P.find_by_reference(pupil.get().strip()) if pupil.get().strip() else None
        if not s or not p:
            scale_hint.set("Choose the pupil (admission number) and subject.")
            return
        names = TGR.scales_for(p.year_group, s)
        grades = ["", *(x for n in names for x in TGR.SCALES[n])]
        for b in grade_boxes:
            b.configure(values=grades)
        cur = TGR.get_for(p.pupil_id, s.subject_id)
        scale_hint.set(f"{p.display_name}, Year {p.year_group} · {' or '.join(names)}"
                       + (f" · current target {cur.target_grade}" if cur and not t else ""))
    notes = tk.Text(frm, width=40, height=4, wrap="word")
    notes.insert("1.0", (t.notes or "") if t else "")
    pupil_entry = ttk.Entry(frm, textvariable=pupil, width=14,
                            state="readonly" if t else "normal")
    for var in (target, lo, hi):
        grade_boxes.append(ttk.Combobox(frm, textvariable=var, width=11))
    rows = [("Pupil (admission no):", pupil_entry),
            ("Subject:", ttk.Combobox(frm, textvariable=subj, values=list(subjects),
                                      state="disabled" if t else "readonly", width=30)),
            ("", ttk.Label(frm, textvariable=scale_hint, foreground="#666")),
            ("Target grade:", grade_boxes[0]), ("Minimum grade:", grade_boxes[1]),
            ("Aspirational grade:", grade_boxes[2]),
            ("Source:", ttk.Combobox(frm, textvariable=src, values=TGR.GRADE_SOURCES,
                                     state="readonly", width=12)),
            ("Set by:", ttk.Entry(frm, textvariable=by, width=24)),
            ("Set date:", ttk.Entry(frm, textvariable=when, width=12)),
            ("Notes:", notes),
            ("Reason (if lowering):", ttk.Entry(frm, textvariable=reason, width=40))]
    for i, (text, w) in enumerate(rows):
        ttk.Label(frm, text=text).grid(row=i, column=0, sticky="nw", pady=2, padx=(0, 8))
        w.grid(row=i, column=1, sticky="w", pady=2)
    pupil.trace_add("write", scales)
    subj.trace_add("write", scales)
    scales()

    def save() -> None:
        s = subjects.get(subj.get())
        data = {"pupil": pupil.get().strip(), "subject_id": s.subject_id if s else None,
                "target_grade": target.get(), "minimum_grade": lo.get(),
                "aspirational_grade": hi.get(), "source": src.get(), "set_by": by.get(),
                "set_date": when.get(), "notes": notes.get("1.0", "end").strip()}
        try:
            rec = TGR.upsert(data, actor=principal, reason=reason.get() or None)
        except _ERRORS as e:
            messagebox.showerror("Target Grades", _problems(e), parent=win)
            return
        win.destroy()
        messagebox.showinfo("Target Grades", f"Saved {rec.pupil_name} / {rec.subject_code} = "
                            f"{rec.target_grade}", parent=owner)
        on_saved()
    bar = ttk.Frame(frm)
    bar.grid(row=len(rows), column=0, columnspan=2, sticky="e", pady=(8, 0))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="right")
    ttk.Button(bar, text="Save", command=save).pack(side="right", padx=(0, 6))
