"""Subjects screen: the catalogue (old Key stage / Qualification / Active only
filters and New / Edit / Toggle Active / Delete / Refresh kept) and the
curriculum plan. Rules live in :mod:`modules.curriculum.domain.subjects`."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Callable

from education_system.platform.delivery.gui.parented_dialogs import make_toplevel, messagebox
from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import SUBJECT_EDITORS, Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.gui.components import widgets as W

logger = logging.getLogger(__name__)
ALL = "All"


_problems = W.problems


def _tree(parent, columns, height: int = 10) -> ttk.Treeview:
    return W.tree(parent, columns, height=height, stretch={"name", "dept"})


def _lessons_text(s: S.Subject, by_year: dict[int, int]) -> str:
    return " · ".join(str(by_year.get(y, 0)) if y in s.years else "–" for y in P.YEAR_GROUPS)


def describe(h: dict) -> str:
    a, d = h["action"], h["detail"]
    if a == "update":
        return "changed " + ", ".join(S.FIELD_LABELS.get(k, k).lower() for k in d
                                      if k in S.FIELD_LABELS)
    if a == "curriculum":
        return "lessons " + ", ".join(f"Y{y} {v['from']}→{v['to']}" for y, v in d.items())
    return {"create": "added", "activate": "made active", "deactivate": "made inactive",
            "delete": "deleted"}.get(a, a)


class SubjectsPage:
    TABS = ("Subjects", "Curriculum plan")

    def __init__(self, parent: ttk.Frame, *, principal: Principal, state: dict) -> None:
        self.parent, self.principal, self.state = parent, principal, state
        self.editor = principal.role in SUBJECT_EDITORS
        activity_log.record("subject.list")
        ttk.Label(parent, text="Subjects (KS3 / GCSE)", font=("", 16, "bold")).pack(anchor="w")
        c = S.counts()
        self.summary = ttk.Label(parent, foreground="#666")
        self.summary.pack(anchor="w", pady=(0, 6))
        self._set_summary(c)
        self.book = ttk.Notebook(parent)
        self.book.pack(fill="both", expand=True)
        self.tabs = {name: ttk.Frame(self.book, padding=8) for name in self.TABS}
        for name, frame in self.tabs.items():
            self.book.add(frame, text=name)
        self._build_list(self.tabs["Subjects"])
        self._build_plan(self.tabs["Curriculum plan"])
        self.book.select(self.TABS.index(state.get("tab", "Subjects")))
        self.book.bind("<<NotebookTabChanged>>", self._on_tab)

    def _set_summary(self, c: dict[str, int]) -> None:
        self.summary.configure(text=f"Total {c['total']} · active {c['active']} · inactive "
                                    f"{c['inactive']} · core {c['core']}")

    def _on_tab(self, _e=None) -> None:
        name = self.TABS[self.book.index(self.book.select())]
        self.state["tab"] = name
        if name == "Curriculum plan":
            self.fill_plan()

    def refresh_all(self) -> None:
        self._set_summary(S.counts())
        self.fill_list()
        self.fill_plan()

    # ── Subjects tab ─────────────────────────────────────────────────

    def _build_list(self, tab: ttk.Frame) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self.ks_var = tk.StringVar(value=self.state.get("ks", ALL))
        self.qual_var = tk.StringVar(value=self.state.get("qual", ALL))
        self.active_var = tk.BooleanVar(value=self.state.get("active", True))
        self.search_var = tk.StringVar()
        ttk.Label(bar, text="Key stage:").pack(side="left", padx=(0, 4))
        ttk.Combobox(bar, textvariable=self.ks_var, values=[ALL, *S.KEY_STAGES],
                     state="readonly", width=6).pack(side="left", padx=(0, 8))
        ttk.Label(bar, text="Qualification:").pack(side="left", padx=(0, 4))
        ttk.Combobox(bar, textvariable=self.qual_var, values=[ALL, *S.QUALIFICATIONS],
                     state="readonly", width=7).pack(side="left", padx=(0, 8))
        ttk.Checkbutton(bar, text="Active only", variable=self.active_var).pack(side="left",
                                                                               padx=(0, 8))
        ttk.Label(bar, text="Search:").pack(side="left")
        ttk.Entry(bar, textvariable=self.search_var, width=16).pack(side="left", padx=(2, 8))
        btns = ttk.Frame(tab)
        btns.pack(fill="x", pady=(0, 6))
        kw = {} if self.editor else {"state": "disabled"}
        ttk.Button(btns, text="New", command=self.new, **kw).pack(side="left", padx=2)
        ttk.Button(btns, text="Edit", command=self.edit, **kw).pack(side="left", padx=2)
        ttk.Button(btns, text="Toggle Active", command=self.toggle, **kw).pack(side="left",
                                                                               padx=2)
        ttk.Button(btns, text="Delete", command=self.delete, **kw).pack(side="left", padx=2)
        ttk.Button(btns, text="Refresh", command=self.refresh_all).pack(side="left", padx=2)
        ttk.Button(btns, text="Add standard subjects…", command=self.standard, **kw).pack(
            side="left", padx=(12, 2))
        self.tree = _tree(tab, (
            ("code", "Code", 75), ("name", "Name", 200), ("ks", "Key stage", 70),
            ("qual", "Qualification", 85), ("board", "Exam board", 110),
            ("dept", "Department", 120), ("ebacc", "EBacc", 85), ("core", "Core", 45),
            ("active", "Active", 50), ("lessons", "Lessons Y7–11", 120)), height=14)
        self.tree.tag_configure("inactive", foreground="#888")
        self.detail = ttk.LabelFrame(tab, text="Selected subject", padding=8)
        self.detail.pack(fill="x", pady=(6, 0))
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self.show_detail())
        self.tree.bind("<Double-1>", lambda _e: self.edit())
        for v in (self.ks_var, self.qual_var, self.active_var, self.search_var):
            v.trace_add("write", lambda *_a: self.fill_list())
        self.fill_list()

    def fill_list(self) -> None:
        self.state.update(ks=self.ks_var.get(), qual=self.qual_var.get(),
                          active=self.active_var.get())
        sel = self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        try:
            rows = S.list_subjects(
                key_stage=None if self.ks_var.get() == ALL else self.ks_var.get(),
                qualification=None if self.qual_var.get() == ALL else self.qual_var.get(),
                active_only=self.active_var.get(), search=self.search_var.get().strip() or None)
            plan = S.plan(active_only=False)
        except Exception:
            logger.exception("Subjects list failed")
            ttk.Label(self.detail, text="Couldn't read subjects - see the log.",
                      foreground="#a00").pack(anchor="w")
            return
        for s in rows:
            self.tree.insert("", "end", iid=str(s.subject_id),
                             tags=() if s.is_active else ("inactive",), values=(
                s.code, s.name, s.key_stage, s.qualification, s.exam_board or "",
                s.department or "", s.ebacc_category or "", "Yes" if s.is_core else "",
                "Yes" if s.is_active else "No", _lessons_text(s, plan.get(s.subject_id, {}))))
        if sel and self.tree.exists(sel[0]):
            self.tree.selection_set(sel[0])
        self.show_detail()

    def selected(self, quiet: bool = False) -> S.Subject | None:
        sel = self.tree.selection()
        if not sel:
            if not quiet:
                messagebox.showinfo("Subjects", "Select a subject first.", parent=self.parent)
            return None
        try:
            return S.get(int(sel[0]))
        except S.NotFound:
            return None

    def show_detail(self) -> None:
        for w in self.detail.winfo_children():
            w.destroy()
        s = self.selected(quiet=True)
        if s is None:
            ttk.Label(self.detail, text="Select a subject to see its details.",
                      foreground="#888").pack(anchor="w")
            return
        lines = [
            f"{s.label} · {s.key_stage} · {s.qualification}"
            + (f" · {s.exam_board}" if s.exam_board else "")
            + (f" ({s.spec_code})" if s.spec_code else ""),
            f"Head of subject: {s.head_of_subject or '—'}"
            + (f" ({s.head_of_subject_email})" if s.head_of_subject_email else "")
            + f" · Department: {s.department or '—'}",
            "Lessons per week: " + (", ".join(
                f"Y{y} {n}" for y, n in sorted(S.lessons(s.subject_id).items()))
                or "none planned"),
        ]
        used = S.usage(s.subject_id)
        if used:
            lines.append("Used by: " + ", ".join(f"{n} {what}" for what, n in used))
        if s.notes:
            lines.append(f"Notes: {s.notes}")
        hist = S.history(s.subject_id)[:3]
        if hist:
            lines.append("Recent changes: " + "; ".join(
                f"{h['at'][:16]} {h['actor']} {describe(h)}" for h in hist))
        for line in lines:
            ttk.Label(self.detail, text=line, wraplength=1000, justify="left").pack(anchor="w")

    def new(self) -> None:
        subject_dialog(self.parent, self.principal, None, self.refresh_all)

    def edit(self) -> None:
        s = self.selected()
        if s:
            subject_dialog(self.parent, self.principal, s, self.refresh_all)

    def toggle(self) -> None:
        s = self.selected()
        if not s:
            return
        if s.is_active and not messagebox.askyesno(
                "Make inactive", f"Make {s.label} inactive? It stays on existing records but "
                "can't be chosen for new ones, and drops out of the curriculum plan.",
                parent=self.parent):
            return
        try:
            S.toggle_active(s.subject_id, actor=self.principal)
        except S.PermissionDenied as e:
            messagebox.showerror("Subjects", str(e), parent=self.parent)
            return
        self.refresh_all()

    def delete(self) -> None:
        s = self.selected()
        if not s or not messagebox.askyesno(
                "Delete", f"Delete {s.label}?\n\nUse this for a subject added by mistake. "
                "To stop teaching a subject, make it inactive instead.", parent=self.parent):
            return
        try:
            S.delete(s.subject_id, actor=self.principal)
        except (S.ValidationError, S.PermissionDenied) as e:
            messagebox.showerror("Delete", _problems(e), parent=self.parent)
            return
        self.refresh_all()

    def standard(self) -> None:
        standard_dialog(self.parent, self.principal, self.refresh_all)

    # ── Curriculum plan tab ──────────────────────────────────────────

    def _build_plan(self, tab: ttk.Frame) -> None:
        top = ttk.Frame(tab)
        top.pack(fill="x", pady=(0, 6))
        ttk.Label(top, text="Lessons per week for each active subject. A dash means the year "
                            "isn't in the subject's key stage.", foreground="#666").pack(
            side="left")
        self.week_var = tk.StringVar()
        if self.editor:
            ttk.Button(top, text="Set", command=self.save_week).pack(side="right")
        ttk.Entry(top, textvariable=self.week_var, width=4,
                  state="normal" if self.editor else "readonly").pack(side="right", padx=4)
        ttk.Label(top, text="Lessons in the timetable week:").pack(side="right")
        outer = ttk.Frame(tab)
        outer.pack(fill="both", expand=True)
        canvas = tk.Canvas(outer, highlightthickness=0)
        sb = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        self.grid_frame = ttk.Frame(canvas)
        self.grid_frame.bind("<Configure>", lambda _e: canvas.configure(
            scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.grid_frame, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        foot = ttk.Frame(tab)
        foot.pack(fill="x", pady=(6, 0))
        self.warn = ttk.Label(foot, foreground="#a60", wraplength=900, justify="left")
        self.warn.pack(side="left", anchor="w")
        if self.editor:
            ttk.Button(foot, text="Save plan", command=self.save_plan).pack(side="right")
        self.cells: dict[tuple[int, int], tk.StringVar] = {}

    def fill_plan(self) -> None:
        for w in self.grid_frame.winfo_children():
            w.destroy()
        self.cells.clear()
        self.week_var.set(str(S.periods_per_week()))
        subjects = S.list_subjects()
        plan = S.plan()
        g = self.grid_frame
        ttk.Label(g, text="Subject", font=("", 10, "bold")).grid(row=0, column=0, sticky="w",
                                                                 padx=(0, 12))
        for c, y in enumerate(P.YEAR_GROUPS, 1):
            ttk.Label(g, text=f"Year {y}", font=("", 10, "bold")).grid(row=0, column=c, padx=4)
        for r, s in enumerate(subjects, 1):
            ttk.Label(g, text=s.label + (" *" if s.is_core else "")).grid(
                row=r, column=0, sticky="w", padx=(0, 12))
            for c, y in enumerate(P.YEAR_GROUPS, 1):
                if y not in s.years:
                    ttk.Label(g, text="–", foreground="#aaa").grid(row=r, column=c)
                    continue
                var = tk.StringVar(value=str(plan.get(s.subject_id, {}).get(y, "")))
                ttk.Entry(g, textvariable=var, width=4, justify="center",
                          state="normal" if self.editor else "readonly").grid(
                    row=r, column=c, padx=4, pady=1)
                self.cells[(s.subject_id, y)] = var
        totals = S.year_totals()
        week = S.periods_per_week()
        last = len(subjects) + 1
        ttk.Label(g, text="Total", font=("", 10, "bold")).grid(row=last, column=0, sticky="w",
                                                               pady=(6, 0))
        for c, y in enumerate(P.YEAR_GROUPS, 1):
            ttk.Label(g, text=f"{totals[y]} / {week}", font=("", 10, "bold"),
                      foreground="#a00" if totals[y] > week else "").grid(
                row=last, column=c, pady=(6, 0))
        if not subjects:
            ttk.Label(g, text="No active subjects yet.", foreground="#888").grid(
                row=1, column=0, sticky="w")
        warnings = S.plan_warnings()
        self.warn.configure(text="\n".join(f"⚠ {w}" for w in warnings) if warnings else
                            "* core subject")

    def save_plan(self) -> None:
        by_subject: dict[int, dict[int, str]] = {}
        for (sid, y), var in self.cells.items():
            by_subject.setdefault(sid, {})[y] = var.get()
        current = S.plan()
        errors = []
        for sid, years in by_subject.items():
            now = current.get(sid, {})
            if all((str(now.get(y, "")) == v.strip()) or (not v.strip() and not now.get(y))
                   for y, v in years.items()):
                continue
            try:
                S.set_lessons(sid, years, actor=self.principal)
            except (S.ValidationError, S.PermissionDenied) as e:
                errors.append(f"{S.get(sid).code}: {_problems(e)}")
        if errors:
            messagebox.showerror("Curriculum plan", "Some rows weren't saved:\n\n"
                                 + "\n".join(errors), parent=self.parent)
        self.refresh_all()

    def save_week(self) -> None:
        try:
            S.set_periods_per_week(self.week_var.get(), actor=self.principal)
        except (S.ValidationError, S.PermissionDenied) as e:
            messagebox.showerror("Curriculum plan", _problems(e), parent=self.parent)
            return
        self.fill_plan()


def draw_subjects(parent: ttk.Frame, *, principal: Principal,
                  state: dict | None = None) -> SubjectsPage:
    return SubjectsPage(parent, principal=principal, state=state if state is not None else {})


# ── Dialogs ──────────────────────────────────────────────────────────

def subject_dialog(owner, principal: Principal, s: S.Subject | None,
                   after: Callable[[], None]) -> None:
    if principal.role not in SUBJECT_EDITORS:
        messagebox.showinfo("Subjects", "Your account can view subjects but not change them.",
                            parent=owner)
        return
    win = make_toplevel(owner.winfo_toplevel())
    win.title(f"Edit {s.label}" if s else "New subject")
    win.resizable(False, False)
    frm = ttk.Frame(win, padding=14)
    frm.pack(fill="both", expand=True)
    w: dict[str, object] = {}

    def row(r: int, key: str, widget, hint: str = "") -> None:
        ttk.Label(frm, text=S.FIELD_LABELS[key] + (" *" if key in {"code", "name"} else "")
                  + ":").grid(row=r, column=0, sticky="w", pady=2, padx=(0, 8))
        widget.grid(row=r, column=1, sticky="w", pady=2)
        if hint:
            ttk.Label(frm, text=hint, foreground="#888").grid(row=r, column=2, sticky="w",
                                                              padx=6)
        w[key] = widget

    def entry(key: str, width: int) -> ttk.Entry:
        e = ttk.Entry(frm, width=width)
        v = getattr(s, key) if s else None
        e.insert(0, "" if v is None else str(v))
        return e

    def combo(key: str, values, *, editable: bool = False, default: str = "") -> ttk.Combobox:
        cb = ttk.Combobox(frm, values=list(values), width=22,
                          state="normal" if editable else "readonly")
        v = getattr(s, key) if s else None
        cb.set(v if v else default)
        return cb

    row(0, "code", entry("code", 10), "2-8 capitals or digits, e.g. MATH")
    row(1, "name", entry("name", 34))
    row(2, "key_stage", combo("key_stage", S.KEY_STAGES, default="Both"))
    row(3, "qualification", combo("qualification", S.QUALIFICATIONS, default="GCSE"),
        "KS3 = no qualification")
    row(4, "exam_board", combo("exam_board", ["", *S.EXAM_BOARDS]))
    row(5, "spec_code", entry("spec_code", 12), "e.g. 8300")
    row(6, "department", combo("department", S.departments(), editable=True))
    row(7, "head_of_subject", entry("head_of_subject", 34))
    row(8, "head_of_subject_email", entry("head_of_subject_email", 34))
    row(9, "ebacc_category", combo("ebacc_category", ["", *S.EBACC_CATEGORIES]),
        "for EBacc / Attainment 8")
    core = tk.BooleanVar(value=bool(s.is_core) if s else False)
    ttk.Checkbutton(frm, text="Core - every pupil in these years takes it",
                    variable=core).grid(row=10, column=1, columnspan=2, sticky="w", pady=2)

    ttk.Label(frm, text="Lessons per week:").grid(row=11, column=0, sticky="w", pady=(6, 2))
    lessons_row = ttk.Frame(frm)
    lessons_row.grid(row=11, column=1, columnspan=2, sticky="w", pady=(6, 2))
    now = S.lessons(s.subject_id) if s else {}
    lesson_vars: dict[int, tk.StringVar] = {}
    lesson_entries: dict[int, ttk.Entry] = {}
    for y in P.YEAR_GROUPS:
        ttk.Label(lessons_row, text=f"Y{y}").pack(side="left", padx=(0, 2))
        var = tk.StringVar(value=str(now.get(y, "")))
        e = ttk.Entry(lessons_row, textvariable=var, width=3, justify="center")
        e.pack(side="left", padx=(0, 8))
        lesson_vars[y], lesson_entries[y] = var, e

    def sync_years(_e=None) -> None:
        years = S.KS_YEARS.get(w["key_stage"].get(), S.KS_YEARS["Both"])  # type: ignore[union-attr]
        for y, e in lesson_entries.items():
            e.configure(state="normal" if y in years else "disabled")
        if w["key_stage"].get() == "KS3":  # type: ignore[union-attr]
            w["qualification"].set("KS3")  # type: ignore[union-attr]
        elif w["qualification"].get() == "KS3":  # type: ignore[union-attr]
            w["qualification"].set("GCSE")  # type: ignore[union-attr]

    w["key_stage"].bind("<<ComboboxSelected>>", sync_years)  # type: ignore[union-attr]
    sync_years()
    if s and s.qualification:
        w["qualification"].set(s.qualification)  # type: ignore[union-attr]

    ttk.Label(frm, text="Notes:").grid(row=12, column=0, sticky="nw", pady=2)
    notes = tk.Text(frm, width=46, height=3, wrap="word")
    notes.insert("1.0", (s.notes if s else None) or "")
    notes.grid(row=12, column=1, columnspan=2, sticky="w", pady=2)
    held: dict[str, S.Subject | None] = {"s": s}
    error = tk.StringVar()
    ttk.Label(frm, textvariable=error, foreground="#a00", wraplength=460, justify="left").grid(
        row=13, column=0, columnspan=3, sticky="w")

    def save() -> None:
        data = {k: wid.get() for k, wid in w.items()}  # type: ignore[attr-defined]
        data["is_core"] = core.get()
        data["notes"] = notes.get("1.0", "end").strip()
        years = S.KS_YEARS.get(data["key_stage"], ())
        plan = {y: (v.get() if y in years else "") for y, v in lesson_vars.items()}
        try:
            # Once created, a retry after a lessons problem updates rather than re-creates.
            if held["s"] is not None:
                saved = S.update(held["s"].subject_id, data, actor=principal)[0]
            else:
                saved = S.create(data, actor=principal)
            held["s"] = saved
            _now, warnings = S.set_lessons(saved.subject_id, plan, actor=principal)
        except S.ValidationError as e:
            error.set(_problems(e))
            return
        except S.PermissionDenied as e:
            messagebox.showerror("Subjects", str(e), parent=win)
            return
        win.destroy()
        if warnings:
            messagebox.showwarning("Curriculum plan", "\n".join(warnings), parent=owner)
        after()

    bar = ttk.Frame(frm)
    bar.grid(row=14, column=0, columnspan=3, sticky="e", pady=(10, 0))

    def cancel() -> None:
        win.destroy()
        if held["s"] is not s:  # added before a lessons problem: show it in the list
            after()

    ttk.Button(bar, text="Cancel", command=cancel).pack(side="right")
    ttk.Button(bar, text="Save", command=save).pack(side="right", padx=(0, 6))


def standard_dialog(owner, principal: Principal, after: Callable[[], None]) -> None:
    missing = S.missing_standard()
    if not missing:
        messagebox.showinfo("Standard subjects", "Every standard subject is already in the "
                            "list.", parent=owner)
        return
    win = make_toplevel(owner.winfo_toplevel())
    win.title("Add standard subjects")
    frm = ttk.Frame(win, padding=14)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm, text="Tick the subjects to add. You can change any of them afterwards; "
                        "subjects already in the list aren't shown.", wraplength=480,
              justify="left").pack(anchor="w", pady=(0, 6))
    ticks: dict[str, tk.BooleanVar] = {}
    grid = ttk.Frame(frm)
    grid.pack(fill="x")
    for i, d in enumerate(missing):
        var = tk.BooleanVar(value=True)
        ttk.Checkbutton(grid, text=f"{d['name']} ({d['code']})", variable=var).grid(
            row=i // 2, column=i % 2, sticky="w", padx=(0, 16))
        ticks[d["code"]] = var

    def go() -> None:
        codes = [c for c, v in ticks.items() if v.get()]
        if not codes:
            return
        try:
            made = S.add_standard(codes, actor=principal)
        except (S.ValidationError, S.PermissionDenied) as e:
            messagebox.showerror("Standard subjects", _problems(e), parent=win)
            return
        win.destroy()
        messagebox.showinfo("Standard subjects", f"{len(made)} subject(s) added. Set their "
                            "lessons per week on the Curriculum plan tab.", parent=owner)
        after()

    bar = ttk.Frame(frm)
    bar.pack(fill="x", pady=(10, 0))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="right")
    ttk.Button(bar, text="Add", command=go).pack(side="right", padx=(0, 6))
