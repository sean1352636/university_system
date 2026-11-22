"""Assessment Points screen (termly data drops).

There was no old screen for this. Tabs: Points (set up, open, close, publish),
Enter grades (a class sheet for one teaching group), Completion (who has
finished, chase by e-mail), Analysis (grade spread and progress against an
earlier point) and Concerns (poor attitude in several subjects). Rules live in
:mod:`modules.assessment.domain.assessment_points`.
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
from education_system.systems.secondary.modules.assessment.domain import assessment_points as AP
from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.modules.curriculum.domain import teaching_groups as TG
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.gui.components import widgets as W

logger = logging.getLogger(__name__)
ALL = ""
YEARS = ("7", "8", "9", "10", "11")
STATUS_BG = {"Draft": "#eeeeee", "Open": "#e7f6ea", "Closed": "#fff6d6",
             "Published": "#ffffff", "low": "#fde2e2", "done": "#e7f6ea", "part": "#fff6d6"}
_ERRORS = (AP.ValidationError, AP.PermissionDenied, AP.NotFound)
ATT_CHOICES = ("", *(f"{k} {v}" for k, v in AP.ATTITUDE.items()))


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
    return W.tree(parent, columns, height=height, stretch={"name", "pupil", "why"}, tags=STATUS_BG)


_text_window = W.text_window


def _point_label(p: AP.Point) -> str:
    return f"{p.name} ({p.academic_year}, Y{p.years_label}) - {p.status}"


def _att(v: int | None) -> str:
    return "" if not v else f"{v} {AP.ATTITUDE[v]}"


def pupil_report_text(point_id: int, pupil_id: int) -> str:
    pt = AP.get_point(point_id)
    rows = AP.pupil_report(pt.point_id, pupil_id)
    p = P.get_pupil(pupil_id)
    lines = [f"{p.display_name if p else pupil_id} · {pt.name} ({pt.academic_year}) · "
             f"{pt.status}", ""]
    lines += [f"{x.subject_code:<8} {x.group_code or '':<10} working at {x.working_at or '-':<11}"
              + (f" predicted {x.predicted or '-':<11}" if pt.collect_predicted else "")
              + (f" attitude {x.attitude or '-'}" if pt.collect_attitude else "")
              + (f" homework {x.homework or '-'}" if pt.collect_homework else "")
              + (f"\n         {x.comment}" if x.comment else "") for x in rows]
    return "\n".join(lines) if rows else "\n".join(lines + ["No grades at this point."])


class AssessmentPointsPage:
    TABS = ("Points", "Enter grades", "Completion", "Analysis", "Concerns")

    def __init__(self, parent: ttk.Frame, *, principal: Principal, state: dict,
                 open_pupil: Callable[[int], None] | None = None) -> None:
        self.parent, self.principal, self.state = parent, principal, state
        self.open_pupil = open_pupil
        self.editor = AP.is_editor(principal)
        activity_log.record("points.view")
        ttk.Label(parent, text="Assessment Points", font=("", 16, "bold")).pack(anchor="w")
        ttk.Label(parent, text="Termly data drops: working-at and predicted grades, attitude "
                               "and homework for every pupil in every subject.",
                  foreground="#666").pack(anchor="w", pady=(0, 6))
        self.book = ttk.Notebook(parent)
        self.book.pack(fill="both", expand=True)
        self.tabs = {n: ttk.Frame(self.book, padding=8) for n in self.TABS}
        for n, f in self.tabs.items():
            self.book.add(f, text=n)
        self._build_points(self.tabs["Points"])
        self.book.select(self.TABS.index(state.get("tab", "Points")))
        self.book.bind("<<NotebookTabChanged>>", self._on_tab)
        self._on_tab()

    def _on_tab(self, _e=None) -> None:
        name = self.TABS[self.book.index(self.book.select())]
        self.state["tab"] = name
        if name == "Points":
            self.refresh()
            return
        tab = self.tabs[name]
        for w in tab.winfo_children():
            w.destroy()
        try:
            {"Enter grades": self._draw_entry, "Completion": self._draw_completion,
             "Analysis": self._draw_analysis, "Concerns": self._draw_concerns}[name](tab)
        except Exception:
            logger.exception("Assessment points tab %s failed", name)
            ttk.Label(tab, text="Couldn't load this tab - see the log.",
                      foreground="#a00").pack(anchor="w")

    def _point_picker(self, bar, key: str = "point", statuses=None) -> tuple[
            tk.StringVar, dict[str, AP.Point]]:
        points = {_point_label(p): p for p in AP.list_points()
                  if statuses is None or p.status in statuses}
        want = self.state.get(key)
        first = next((k for k, p in points.items() if p.point_id == want), None) or \
            next(iter(points), "")
        var = tk.StringVar(value=first)
        ttk.Label(bar, text="Point:").pack(side="left", padx=(0, 4))
        ttk.Combobox(bar, textvariable=var, values=list(points), state="readonly",
                     width=42).pack(side="left")
        return var, points

    # ── Points ───────────────────────────────────────────────────────

    def _build_points(self, tab: ttk.Frame) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self.year_var = tk.StringVar(value=self.state.get("year", TG.current_year()))
        years = sorted({p.academic_year for p in AP.list_points()} | {TG.current_year()},
                       reverse=True)
        ttk.Label(bar, text="School year:").pack(side="left", padx=(0, 4))
        cb = ttk.Combobox(bar, textvariable=self.year_var, values=[ALL, *years],
                          state="readonly", width=9)
        cb.pack(side="left")
        cb.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        buttons = [("Enter grades", self.go_enter), ("Pupil report", self.pupil_report),
                   ("History", self.history), ("Export CSV", self.export)]
        if self.editor:
            buttons = [("New point", self.new_point), ("Edit", self.edit_point),
                       ("Open", lambda: self.move("Open")),
                       ("Close", lambda: self.move("Closed")),
                       ("Publish", lambda: self.move("Published")),
                       ("Unpublish", lambda: self.move("Closed")),
                       ("Delete", self.delete_point), *buttons]
        for text, cmd in buttons + [("Refresh", self.refresh)]:
            ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=2)
        self.tree = _tree(tab, (("id", "ID", 40), ("year", "School year", 80),
                                ("name", "Name", 200), ("yrs", "Years", 80),
                                ("opens", "Opens", 85), ("deadline", "Deadline", 85),
                                ("collect", "Collecting", 220), ("done", "Complete", 90),
                                ("status", "Status", 80)), height=16)
        self.tree.bind("<Double-1>", lambda _e: self.go_enter())
        self.rows: dict[str, AP.Point] = {}

    def refresh(self) -> None:
        self.state["year"] = self.year_var.get()
        self.tree.delete(*self.tree.get_children())
        self.rows.clear()
        for p in AP.list_points(academic_year=self.year_var.get() or None):
            s = AP.summary(p.point_id) if p.status != "Draft" else {"pct": None}
            collect = ", ".join(["working at"] + [n for k, n in (
                ("collect_predicted", "predicted"), ("collect_attitude", "attitude"),
                ("collect_homework", "homework"), ("collect_comment", "comment"))
                if getattr(p, k)])
            iid = self.tree.insert("", "end", tags=(p.status,), values=(
                p.point_id, p.academic_year, p.name, p.years_label, p.opens_on or "",
                (p.deadline or "") + (" (overdue)" if p.overdue else ""), collect,
                "" if s["pct"] is None else f"{s['pct']}%", p.status))
            self.rows[iid] = p

    def _selected(self) -> AP.Point | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Assessment points", "Select a point first.", parent=self.tree)
            return None
        return self.rows[sel[0]]

    def new_point(self) -> None:
        point_dialog(self.tree, self.principal, None, on_saved=self.refresh)

    def edit_point(self) -> None:
        p = self._selected()
        if p:
            point_dialog(self.tree, self.principal, p, on_saved=self.refresh)

    def move(self, status: str) -> None:
        p = self._selected()
        if not p:
            return
        if status == "Published" and not messagebox.askyesno(
                "Publish", f"Publish '{p.name}'? Its grades will be fixed.", parent=self.tree):
            return
        try:
            AP.set_status(p.point_id, status, actor=self.principal)
        except _ERRORS as e:
            messagebox.showerror("Assessment points", _problems(e), parent=self.tree)
            return
        self.refresh()

    def delete_point(self) -> None:
        p = self._selected()
        if not p:
            return
        n = len(AP.grades(p.point_id))
        if not messagebox.askyesno("Delete", f"Delete '{p.name}'"
                                   + (f" and its {n} grade(s)" if n else "") + "?",
                                   parent=self.tree):
            return
        try:
            AP.delete_point(p.point_id, actor=self.principal)
        except _ERRORS as e:
            messagebox.showerror("Assessment points", _problems(e), parent=self.tree)
            return
        self.refresh()

    def go_enter(self) -> None:
        p = self._selected()
        if p:
            self.state["point"] = p.point_id
            self.book.select(self.TABS.index("Enter grades"))

    def pupil_report(self) -> None:
        p = self._selected()
        if not p:
            return
        ref = simpledialog.askstring("Pupil report", "Admission number or UPN:",
                                     parent=self.tree)
        pupil = P.find_by_reference(ref or "") if ref else None
        if pupil is None:
            if ref:
                messagebox.showinfo("Pupil report", "No pupil with that admission number.",
                                    parent=self.tree)
            return
        _text_window(self.tree, f"{pupil.display_name} - {p.name}",
                     pupil_report_text(p.point_id, pupil.pupil_id))

    def history(self) -> None:
        p = self._selected()
        if p:
            rows = AP.history(p.point_id)
            _text_window(self.tree, f"{p.name} - history", "\n".join(
                f"{h['at']}  {h['actor']:<14} {h['action']:<8} "
                + ", ".join(f"{k}: {v}" for k, v in h["detail"].items()) for h in rows)
                or "No history.")

    def export(self) -> None:
        p = self._selected()
        if not p:
            return
        path = filedialog.asksaveasfilename(parent=self.tree, defaultextension=".csv",
                                            initialfile=f"{p.name}.csv",
                                            filetypes=[("CSV", "*.csv")])
        if not path:
            return
        try:
            n = AP.export_point(p.point_id, path, actor=self.principal)
        except (*_ERRORS, OSError) as e:
            messagebox.showerror("Export", _problems(e), parent=self.tree)
            return
        messagebox.showinfo("Export", f"Exported {n} row(s).", parent=self.tree)

    # ── Enter grades ─────────────────────────────────────────────────

    def _draw_entry(self, tab: ttk.Frame) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        pvar, points = self._point_picker(bar, statuses=("Open", "Closed", "Published"))
        mine = tk.BooleanVar(value=self.state.get("mine", not self.editor))
        gvar = tk.StringVar()
        ttk.Label(bar, text="Group:").pack(side="left", padx=(8, 4))
        gbox = ttk.Combobox(bar, textvariable=gvar, state="readonly", width=30)
        gbox.pack(side="left")
        ttk.Checkbutton(bar, text="My groups", variable=mine).pack(side="left", padx=6)
        info = tk.StringVar()
        ttk.Label(tab, textvariable=info, foreground="#666").pack(anchor="w")
        holder = ttk.Frame(tab)
        holder.pack(fill="both", expand=True)
        groups: dict[str, TG.TeachingGroup] = {}
        sheet: dict[str, GradeSheet] = {}

        def load_groups(*_a) -> None:
            pt = points.get(pvar.get())
            groups.clear()
            if pt:
                self.state.update(point=pt.point_id, mine=mine.get())
                done = {r["group"].group_id: r for r in AP.completion(pt.point_id)}
                for g in AP.groups_for(pt, teacher=self.principal.username if mine.get()
                                       else None):
                    r = done.get(g.group_id)
                    groups[f"{g.code} Y{g.year_group}"
                           + (f" ({r['done']}/{r['pupils']})" if r else "")] = g
            gbox.configure(values=list(groups))
            want = self.state.get("group")
            gvar.set(next((k for k, g in groups.items() if g.group_id == want), None)
                     or next(iter(groups), ""))

        def load_sheet(*_a) -> None:
            for w in holder.winfo_children():
                w.destroy()
            pt, g = points.get(pvar.get()), groups.get(gvar.get())
            if not pt or not g:
                info.set("No open point." if not points else "No groups to enter for this "
                         "point." if not groups else "")
                return
            self.state["group"] = g.group_id
            pt = AP.get_point(pt.point_id)
            can = AP.can_enter(self.principal, pt, g)
            info.set(f"{g.code} · {S.get(g.subject_id).code} · Year {g.year_group} · "
                     f"{g.teacher_name or 'no teacher'} · scale "
                     f"{', '.join(pt.scale_for(g.year_group))} · "
                     + ("you can enter grades" if can else f"view only ({pt.status.lower()})"))
            sheet["s"] = GradeSheet(holder, self.principal, pt, g, editable=can)
        pvar.trace_add("write", lambda *_a: (load_groups(), load_sheet()))
        mine.trace_add("write", lambda *_a: (load_groups(), load_sheet()))
        gvar.trace_add("write", load_sheet)
        load_groups()
        load_sheet()

    # ── Completion ───────────────────────────────────────────────────

    def _draw_completion(self, tab: ttk.Frame) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        pvar, points = self._point_picker(bar, statuses=("Open", "Closed", "Published"))
        total = tk.StringVar()
        tree = _tree(tab, (("group", "Group", 100), ("subj", "Subj", 60), ("yr", "Yr", 35),
                           ("teacher", "Teacher", 160), ("pupils", "Pupils", 60),
                           ("done", "Entered", 60), ("pct", "%", 50)), height=16)
        ttk.Label(tab, textvariable=total, foreground="#666").pack(anchor="w", pady=4)

        def fill(*_a) -> None:
            tree.delete(*tree.get_children())
            pt = points.get(pvar.get())
            if not pt:
                total.set("No points yet.")
                return
            self.state["point"] = pt.point_id
            for r in AP.completion(pt.point_id):
                g = r["group"]
                tree.insert("", "end", tags=("done" if r["done"] >= r["pupils"] else
                                             "part" if r["done"] else "low",), values=(
                    g.code, r["subject_code"], g.year_group, g.teacher_name or "",
                    r["pupils"], r["done"], f"{r['pct']}%"))
            s = AP.summary(pt.point_id)
            total.set(f"{s['complete']} of {s['groups']} groups complete · {s['done']} of "
                      f"{s['pupils']} grades in"
                      + (f" ({s['pct']}%)" if s["pct"] is not None else ""))

        def chase() -> None:
            pt = points.get(pvar.get())
            if not pt or not messagebox.askyesno(
                    "Chase", "E-mail every teacher with unfinished groups?", parent=tab):
                return
            try:
                r = AP.chase(pt.point_id, actor=self.principal)
            except _ERRORS as e:
                messagebox.showerror("Chase", _problems(e), parent=tab)
                return
            from education_system.systems.secondary.modules.communication.gui import email_views
            for mid in r["sent"]:
                email_views.deliver_in_background(tab, mid, self.principal,
                                                  lambda _rep, _err: None)
            messagebox.showinfo("Chase", f"E-mailed {len(r['sent'])} teacher(s)."
                                + (f"\nNo e-mail address: {', '.join(r['no_email'])}"
                                   if r["no_email"] else ""), parent=tab)
        ttk.Button(bar, text="Refresh", command=fill).pack(side="left", padx=6)
        if self.editor:
            ttk.Button(bar, text="Chase teachers", command=chase).pack(side="left")
        pvar.trace_add("write", fill)
        fill()

    # ── Analysis ─────────────────────────────────────────────────────

    def _draw_analysis(self, tab: ttk.Frame) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        pvar, points = self._point_picker(bar)
        year = tk.StringVar(value=self.state.get("a_year", ALL))
        ttk.Label(bar, text="Year:").pack(side="left", padx=(8, 4))
        ttk.Combobox(bar, textvariable=year, values=[ALL, *YEARS], state="readonly",
                     width=4).pack(side="left")
        bar2 = ttk.Frame(tab)
        bar2.pack(fill="x", pady=(0, 4))
        ttk.Label(bar2, text="Compare with:").pack(side="left", padx=(0, 4))
        evar = tk.StringVar(value="")
        ttk.Combobox(bar2, textvariable=evar, values=["", *points], state="readonly",
                     width=42).pack(side="left")
        text = tk.Text(tab, wrap="none", font=("TkFixedFont", 10), height=12)
        text.pack(fill="both", expand=True)
        ttk.Label(tab, text="Grades gone down (double-click to open the pupil):").pack(
            anchor="w", pady=(6, 0))
        tree = _tree(tab, (("pupil", "Pupil", 180), ("yr", "Yr", 35), ("subj", "Subj", 60),
                           ("before", "Before", 90), ("now", "Now", 90)), height=7)
        ids: dict[str, int] = {}

        def fill(*_a) -> None:
            pt = points.get(pvar.get())
            text.configure(state="normal")
            text.delete("1.0", "end")
            tree.delete(*tree.get_children())
            ids.clear()
            if not pt:
                text.insert("1.0", "No points yet.")
                return
            self.state.update(point=pt.point_id, a_year=year.get())
            y = int(year.get()) if year.get() else None
            d = AP.distribution(pt.point_id, year_group=y)
            lines = [f"{pt.name} - working-at grades by subject", ""]
            lines += [f"{s:<8} " + "  ".join(f"{g}: {n}" for g, n in c.items())
                      for s, c in d["subjects"].items()] or ["No grades yet."]
            if d["attitude"]:
                lines += ["", "Attitude: " + "  ".join(f"{k}: {v}"
                                                       for k, v in d["attitude"].items())]
            e = points.get(evar.get())
            if e and e.point_id != pt.point_id:
                pr = AP.progress(pt.point_id, e.point_id, year_group=y)
                lines += ["", f"Against {e.name}: up {pr['up']} · same {pr['same']} · down "
                              f"{pr['down']}" + (f" · different scale {pr['different_scale']}"
                                                 if pr["different_scale"] else "")]
                for r in pr["declines"]:
                    iid = tree.insert("", "end", tags=("low",), values=(
                        r["pupil_name"], r["year"], r["subject_code"], r["before"], r["now"]))
                    ids[iid] = r["pupil_id"]
            text.insert("1.0", "\n".join(lines))
            text.configure(state="disabled")
        tree.bind("<Double-1>", lambda _e: self.open_pupil(ids[tree.selection()[0]])
                  if tree.selection() and self.open_pupil else None)
        for v in (pvar, year, evar):
            v.trace_add("write", fill)
        fill()

    # ── Concerns ─────────────────────────────────────────────────────

    def _draw_concerns(self, tab: ttk.Frame) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        pvar, points = self._point_picker(bar)
        n = tk.StringVar(value=str(self.state.get("min_subjects", 2)))
        worst = tk.StringVar(value=self.state.get("worst", "3 or 4"))
        ttk.Label(bar, text="Attitude:").pack(side="left", padx=(8, 4))
        ttk.Combobox(bar, textvariable=worst, values=("3 or 4", "4 only"), state="readonly",
                     width=7).pack(side="left")
        ttk.Label(bar, text="in at least").pack(side="left", padx=4)
        ttk.Spinbox(bar, from_=1, to=12, textvariable=n, width=3).pack(side="left")
        ttk.Label(bar, text="subjects").pack(side="left", padx=4)
        tree = _tree(tab, (("pupil", "Pupil", 180), ("adm", "Adm no", 85), ("yr", "Yr", 35),
                           ("form", "Form", 55), ("count", "Subjects", 65),
                           ("why", "Where", 320)), height=16)
        ids: dict[str, int] = {}

        def fill(*_a) -> None:
            tree.delete(*tree.get_children())
            ids.clear()
            pt = points.get(pvar.get())
            try:
                k = max(1, int(n.get()))
            except ValueError:
                return
            if not pt:
                return
            self.state.update(point=pt.point_id, min_subjects=k, worst=worst.get())
            for c in AP.attitude_concerns(pt.point_id, min_subjects=k,
                                          worst=4 if worst.get() == "4 only" else 3):
                iid = tree.insert("", "end", tags=("low",), values=(
                    c["pupil_name"], c["admission_no"], c["year"], c["form"] or "",
                    c["count"], c["subjects"]))
                ids[iid] = c["pupil_id"]
        tree.bind("<Double-1>", lambda _e: self.open_pupil(ids[tree.selection()[0]])
                  if tree.selection() and self.open_pupil else None)
        ttk.Button(bar, text="Apply", command=fill).pack(side="left", padx=8)
        for v in (pvar, worst):
            v.trace_add("write", fill)
        fill()


def draw_assessment_points(parent: ttk.Frame, *, principal: Principal,
                           state: dict | None = None,
                           open_pupil: Callable[[int], None] | None = None
                           ) -> AssessmentPointsPage:
    return AssessmentPointsPage(parent, principal=principal,
                                state=state if state is not None else {},
                                open_pupil=open_pupil)


# ── Grade sheet ──────────────────────────────────────────────────────

class GradeSheet:
    """One group's grades at one point, a row per pupil."""

    def __init__(self, parent, principal: Principal, pt: AP.Point, g: TG.TeachingGroup, *,
                 editable: bool) -> None:
        self.principal, self.pt, self.g, self.editable = principal, pt, g, editable
        self.scale = ("", *pt.scale_for(g.year_group))
        bar = ttk.Frame(parent)
        bar.pack(fill="x", pady=4)
        state = "normal" if editable else "disabled"
        for text, cmd in (("Save grades", self.save), ("Fill blanks from gradebook",
                                                       self.from_gradebook),
                          ("Import CSV…", self.import_csv)):
            ttk.Button(bar, text=text, command=cmd, state=state).pack(side="left", padx=2)
        self.scroll = ScrollFrame(parent)
        self.scroll.pack(fill="both", expand=True)
        self.rows: dict[int, dict[str, tk.StringVar]] = {}
        self._fill()

    def _cols(self) -> list[tuple[str, str]]:
        pt = self.pt
        return [("working_at", "Working at")] + [c for on, c in (
            (pt.collect_predicted, ("predicted", "Predicted")),
            (pt.collect_attitude, ("attitude", "Attitude")),
            (pt.collect_homework, ("homework", "Homework")),
            (pt.collect_comment, ("comment", "Comment"))) if on]

    def _fill(self) -> None:
        body = self.scroll.body
        for w in body.winfo_children():
            w.destroy()
        cols = self._cols()
        for c, h in enumerate(["Pupil", *(h for _k, h in cols)]):
            ttk.Label(body, text=h, font=("", 9, "bold")).grid(row=0, column=c, sticky="w",
                                                               padx=4)
        self.rows = {}
        state = "readonly" if self.editable else "disabled"
        rows = AP.sheet(self.pt.point_id, self.g.group_id)
        for i, (p, x) in enumerate(rows, 1):
            ttk.Label(body, text=f"{p.legal_last_name}, {p.preferred_name or p.legal_first_name}"
                      ).grid(row=i, column=0, sticky="w", padx=4)
            v: dict[str, tk.StringVar] = {}
            for c, (k, _h) in enumerate(cols, 1):
                cur = getattr(x, k) if x else None
                if k in ("attitude", "homework"):
                    var = tk.StringVar(value=_att(cur))
                    w = ttk.Combobox(body, textvariable=var, values=ATT_CHOICES, state=state,
                                     width=22)
                elif k == "comment":
                    var = tk.StringVar(value=cur or "")
                    w = ttk.Entry(body, textvariable=var, width=40,
                                  state="normal" if self.editable else "disabled")
                else:
                    var = tk.StringVar(value=cur or "")
                    w = ttk.Combobox(body, textvariable=var, values=self.scale, state=state,
                                     width=11)
                w.grid(row=i, column=c, padx=4, pady=1, sticky="w")
                v[k] = var
            self.rows[p.pupil_id] = v
        if not rows:
            ttk.Label(body, text="No pupils in this group.").grid(row=1, column=0,
                                                                  columnspan=4)

    def _data(self) -> dict[int, dict[str, str]]:
        out = {}
        for pid, v in self.rows.items():
            d = {k: var.get().strip() for k, var in v.items()}
            for k in ("attitude", "homework"):
                if k in d:
                    d[k] = d[k].split(" ", 1)[0]
            out[pid] = d
        return out

    def save(self) -> None:
        have = {p.pupil_id: x for p, x in AP.sheet(self.pt.point_id, self.g.group_id)}
        changes = {}
        for pid, d in self._data().items():
            x = have.get(pid)
            old = {k: "" if x is None or getattr(x, k) is None else str(getattr(x, k))
                   for k in d}
            if d != old:
                changes[pid] = d
        owner = self.scroll
        if not changes:
            messagebox.showinfo("Grades", "Nothing changed.", parent=owner)
            return
        try:
            n = AP.save_sheet(self.pt.point_id, self.g.group_id, changes, actor=self.principal)
        except _ERRORS as e:
            messagebox.showerror("Grades", _problems(e), parent=owner)
            return
        messagebox.showinfo("Grades", f"Saved {n} pupil(s).", parent=owner)
        self._fill()

    def from_gradebook(self) -> None:
        sug = AP.from_gradebook(self.pt.point_id, self.g.group_id)
        n = 0
        for pid, grade in sug.items():
            v = self.rows.get(pid)
            if v and not v["working_at"].get():
                v["working_at"].set(grade)
                n += 1
        messagebox.showinfo("Gradebook", f"Filled {n} blank grade(s) - check them, then Save."
                            if n else "No gradebook grades on this scale to fill in.",
                            parent=self.scroll)

    def import_csv(self) -> None:
        path = filedialog.askopenfilename(parent=self.scroll, filetypes=[("CSV", "*.csv")])
        if not path:
            return
        try:
            n = AP.import_grades(self.pt.point_id, self.g.group_id, path,
                                 actor=self.principal)
        except (*_ERRORS, OSError, UnicodeDecodeError) as e:
            messagebox.showerror("Import", _problems(e), parent=self.scroll)
            return
        messagebox.showinfo("Import", f"Imported {n} pupil(s).", parent=self.scroll)
        self._fill()


# ── Point dialog ─────────────────────────────────────────────────────

def point_dialog(owner, principal: Principal, p: AP.Point | None, *,
                 on_saved: Callable[[], None]) -> None:
    win = make_toplevel(owner.winfo_toplevel())
    win.title("Edit point" if p else "New assessment point")
    frm = ttk.Frame(win, padding=12)
    frm.pack(fill="both", expand=True)
    name = tk.StringVar(value=p.name if p else "")
    yvars = {y: tk.BooleanVar(value=(y in p.years) if p else False) for y in P.YEAR_GROUPS}
    ks3 = tk.StringVar(value=p.ks3_scale if p else "KS3 steps")
    ks4 = tk.StringVar(value=p.ks4_scale if p else "GCSE 9-1")
    flags = {k: tk.BooleanVar(value=getattr(p, k) if p else k in (
        "collect_predicted", "collect_attitude")) for k in AP._FLAGS}
    opens = tk.StringVar(value=(p.opens_on or "") if p else "")
    deadline = tk.StringVar(value=(p.deadline or "") if p else "")
    years = ttk.Frame(frm)
    for y, var in yvars.items():
        ttk.Checkbutton(years, text=str(y), variable=var).pack(side="left")
    collect = ttk.Frame(frm)
    for k, label in (("collect_predicted", "Predicted"), ("collect_attitude", "Attitude"),
                     ("collect_homework", "Homework"), ("collect_comment", "Comment")):
        ttk.Checkbutton(collect, text=label, variable=flags[k]).pack(side="left")
    notes = tk.Text(frm, width=50, height=4, wrap="word")
    notes.insert("1.0", (p.notes or "") if p else "")
    rows = [("Name:", ttk.Entry(frm, textvariable=name, width=40)),
            ("Year groups:", years),
            ("KS3 scale (Y7-9):", ttk.Combobox(frm, textvariable=ks3, values=list(AP.SCALES),
                                               state="readonly", width=14)),
            ("KS4 scale (Y10-11):", ttk.Combobox(frm, textvariable=ks4,
                                                 values=list(AP.SCALES), state="readonly",
                                                 width=14)),
            ("Also collect:", collect),
            ("Opens (YYYY-MM-DD):", ttk.Entry(frm, textvariable=opens, width=12)),
            ("Deadline (YYYY-MM-DD):", ttk.Entry(frm, textvariable=deadline, width=12)),
            ("Notes:", notes)]
    for i, (text, w) in enumerate(rows):
        ttk.Label(frm, text=text).grid(row=i, column=0, sticky="nw", pady=2, padx=(0, 8))
        w.grid(row=i, column=1, sticky="w", pady=2)
    if not p:
        ttk.Label(frm, text=f"For {TG.current_year()}. It starts as a draft; open it when "
                            "teachers should enter grades.", foreground="#666").grid(
            row=len(rows), column=0, columnspan=2, sticky="w", pady=(4, 0))

    def save() -> None:
        data = {"name": name.get(), "year_groups": [y for y, v in yvars.items() if v.get()],
                "ks3_scale": ks3.get(), "ks4_scale": ks4.get(), "opens_on": opens.get(),
                "deadline": deadline.get(), "notes": notes.get("1.0", "end").strip(),
                **{k: v.get() for k, v in flags.items()}}
        try:
            if p:
                AP.update_point(p.point_id, data, actor=principal)
            else:
                AP.create_point(data, actor=principal)
        except _ERRORS as e:
            messagebox.showerror("Assessment point", _problems(e), parent=win)
            return
        win.destroy()
        on_saved()
    bar = ttk.Frame(frm)
    bar.grid(row=len(rows) + 1, column=0, columnspan=2, sticky="e", pady=(8, 0))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="right")
    ttk.Button(bar, text="Save", command=save).pack(side="right", padx=(0, 6))
