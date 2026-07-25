"""Tkinter views for Sixth Form SEF Builder."""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from education_system.platform import branding
from education_system.systems.sixth_form.domain.assessment.sef_builder import (
    sef_builder as data,
)
from education_system.systems.sixth_form.domain.assessment.sef_builder.sef_builder import (
    AREAS,
    DEFAULT_AREA,
    DEFAULT_STATUS,
    JUDGEMENTS,
    SEFSection,
    STATUSES,
    ValidationError,
    judgement_label,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)

_STATUS_TAGS = {
    "Draft":      ("#fff7e6", "#7a5800"),
    "In Review":  ("#e6f0ff", "#1a3f8c"),
    "Approved":   ("#e6f7e6", "#0d6b2a"),
    "Published":  ("#d6ffd6", "#0d6b2a"),
    "Archived":   ("#eeeeee", "#444444"),
}


def open_sef_builder_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"SEF Builder — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    SectionsTab(nb, scope="open",      label="Open")
    SectionsTab(nb, scope="published", label="Published")
    SectionsTab(nb, scope="all",       label="All")
    CycleTab(nb)
    SummaryTab(nb)


class SectionsTab:
    def __init__(self, nb: ttk.Notebook, *,
                 scope: str, label: str) -> None:
        self.scope = scope
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text=label)
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Cycle:").pack(side="left")
        self.f_cycle = ttk.Entry(bar, width=12)
        self.f_cycle.pack(side="left", padx=(2, 8))

        ttk.Label(bar, text="Area:").pack(side="left")
        self.f_area = ttk.Combobox(bar, values=("",) + AREAS,
                                     state="readonly", width=26)
        self.f_area.current(0)
        self.f_area.pack(side="left", padx=(2, 8))

        if self.scope == "all":
            ttk.Label(bar, text="Status:").pack(side="left")
            self.f_status = ttk.Combobox(bar,
                                           values=("",) + STATUSES,
                                           state="readonly", width=12)
            self.f_status.current(0)
            self.f_status.pack(side="left", padx=(2, 8))
        else:
            self.f_status = None

        ttk.Label(bar, text="Author:").pack(side="left")
        self.f_author = ttk.Entry(bar, width=14)
        self.f_author.pack(side="left", padx=(2, 8))

        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left",
                                                  padx=(8, 4))
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left")
        ttk.Button(bar, text="New",
                    command=self._new).pack(side="left", padx=(16, 0))

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "cycle", "area", "judgement",
                "status", "author", "approved_on", "updated")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                   show="headings",
                                   selectmode="browse")
        widths = {"id": 60, "cycle": 100, "area": 240,
                   "judgement": 100, "status": 110,
                   "author": 130, "approved_on": 110,
                   "updated": 160}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c],
                              anchor=("center" if c in ("id",
                                                          "judgement")
                                       else "w"))
        vsb = ttk.Scrollbar(table_frame, orient="vertical",
                              command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        for status, (bg, fg) in _STATUS_TAGS.items():
            self.tree.tag_configure(status, background=bg,
                                       foreground=fg)
        self.tree.bind("<Double-Button-1>", lambda _e: self._edit())

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 8))
        for label, cmd in (
                ("View / Edit",       self._edit),
                ("Submit for review", self._submit),
                ("Approve",           self._approve),
                ("Publish",           self._publish),
                ("Archive",           self._archive),
                ("Change status",     self._set_status),
                ("Delete",            self._delete),
                ("Refresh",           self.refresh),
        ):
            ttk.Button(actions, text=label,
                        command=cmd).pack(side="left", padx=4)
        self.count = ttk.Label(actions, text="")
        self.count.pack(side="right")

    def _clear(self) -> None:
        self.f_cycle.delete(0, "end")
        self.f_area.current(0)
        self.f_author.delete(0, "end")
        if self.f_status is not None:
            self.f_status.current(0)
        self.refresh()

    def _filters(self) -> dict:
        f: dict = {}
        if self.f_cycle.get().strip():
            f["cycle"] = self.f_cycle.get().strip()
        if self.f_area.get():
            f["area"] = self.f_area.get()
        if self.f_author.get().strip():
            f["author_like"] = self.f_author.get().strip()
        if self.f_status is not None and self.f_status.get():
            f["status"] = self.f_status.get()
        if self.scope == "open":
            f["open_only"] = True
        elif self.scope == "published":
            f["published_only"] = True
        return f

    def refresh(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        try:
            rows = data.list_sections(**self._filters())
        except ValidationError as e:
            messagebox.showerror("SEF", str(e), parent=self.frame)
            return
        for s in rows:
            jval = (f"{s.judgement} "
                     f"{judgement_label(s.judgement)[:3]}"
                     if s.judgement else "—")
            self.tree.insert("", "end", iid=str(s.section_id),
                              values=(s.section_id, s.cycle,
                                       s.area, jval, s.status,
                                       s.author or "—",
                                       s.approved_on or "—",
                                       s.last_updated),
                              tags=(s.status,))
        self.count.config(text=f"{len(rows)} section(s)")

    def _selected(self) -> SEFSection | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("SEF",
                                  "Select a section first.",
                                  parent=self.frame)
            return None
        return data.get_section(int(sel[0]))

    def _new(self) -> None:
        if SEFEditor(self.frame).result is not None:
            self.refresh()

    def _edit(self) -> None:
        s = self._selected()
        if s and SEFEditor(self.frame,
                              section=s).result is not None:
            self.refresh()

    def _submit(self) -> None:
        s = self._selected()
        if not s:
            return
        reviewer = _prompt_text(self.frame, "Reviewer (optional)",
                                  initial=s.reviewer or "")
        if reviewer is None:
            return
        try:
            data.submit_for_review(s.section_id,
                                        reviewer=reviewer or None)
        except ValidationError as e:
            messagebox.showerror("SEF", str(e), parent=self.frame)
            return
        self.refresh()

    def _approve(self) -> None:
        s = self._selected()
        if not s:
            return
        if ApproveDialog(self.frame,
                            section=s).result is not None:
            self.refresh()

    def _publish(self) -> None:
        s = self._selected()
        if not s:
            return
        try:
            data.publish(s.section_id)
        except ValidationError as e:
            messagebox.showerror("SEF", str(e), parent=self.frame)
            return
        self.refresh()

    def _archive(self) -> None:
        s = self._selected()
        if not s:
            return
        try:
            data.archive(s.section_id)
        except ValidationError as e:
            messagebox.showerror("SEF", str(e), parent=self.frame)
            return
        self.refresh()

    def _set_status(self) -> None:
        s = self._selected()
        if not s:
            return
        new = _prompt_choice(self.frame, "New status",
                                list(STATUSES), default=s.status)
        if not new:
            return
        try:
            data.set_status(s.section_id, new)
        except ValidationError as e:
            messagebox.showerror("SEF", str(e), parent=self.frame)
            return
        self.refresh()

    def _delete(self) -> None:
        s = self._selected()
        if not s:
            return
        if not messagebox.askyesno("SEF",
                                       f"Delete section #{s.section_id}?",
                                       parent=self.frame):
            return
        data.delete_section(s.section_id)
        self.refresh()


class CycleTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Per Cycle")
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Cycle:").pack(side="left")
        self.combo = ttk.Combobox(bar, state="readonly", width=20)
        self.combo.pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Show",
                    command=self._show).pack(side="left")
        ttk.Button(bar, text="Refresh cycles",
                    command=self._reload).pack(side="left", padx=8)
        self.text = tk.Text(self.frame, wrap="word",
                              font=("TkFixedFont", 10))
        self.text.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        self.text.config(state="disabled")
        self._reload()

    def _reload(self) -> None:
        cycles = data.list_cycles()
        self.combo["values"] = cycles
        if cycles:
            self.combo.current(0)

    def _show(self) -> None:
        cycle = self.combo.get()
        if not cycle:
            return
        cs = data.cycle_summary(cycle)
        rows = data.list_sections(cycle=cycle)
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("end",
                            f"SEF Cycle {cs.cycle}\n"
                            f"{'=' * 60}\n\n"
                            f"Sections           : {cs.total}\n"
                            f"Published          : {cs.published}\n"
                            f"Average judgement  : "
                            f"{cs.average_judgement if cs.average_judgement is not None else '—'}\n\n"
                            f"Per-area judgements:\n")
        for area in AREAS:
            j = cs.judgement_by_area.get(area)
            if j is not None:
                self.text.insert("end",
                                    f"  {area:<28}: {j}  "
                                    f"({judgement_label(j)})\n")
        self.text.insert("end", f"\n{'-' * 60}\nSections:\n\n")
        for s in rows:
            self.text.insert("end",
                                f"#{s.section_id}  {s.area:<28}  "
                                f"J={s.judgement or '—'}  [{s.status}]\n")
            if s.summary_statement:
                self.text.insert("end",
                                    f"   {s.summary_statement.splitlines()[0]}\n")
            self.text.insert("end", "\n")
        self.text.config(state="disabled")


class SummaryTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Summary")
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="left")
        self.text = tk.Text(self.frame, wrap="word",
                              font=("TkFixedFont", 10))
        self.text.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        self.refresh()

    def refresh(self) -> None:
        s = data.summary()
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("end", "SEF Builder Summary\n")
        self.text.insert("end", "=" * 60 + "\n\n")
        self.text.insert("end",
                            f"Total              : {s.total}\n"
                            f"Open               : {s.open_count}\n"
                            f"Published          : {s.published}\n"
                            f"Distinct cycles    : {s.distinct_cycles}\n"
                            f"Average judgement  : "
                            f"{s.average_judgement if s.average_judgement is not None else '—'}\n\n")
        self.text.insert("end", "By status:\n")
        for k in STATUSES:
            n = s.by_status.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<14}: {n}\n")
        self.text.insert("end", "\nBy area:\n")
        for k in AREAS:
            n = s.by_area.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<28}: {n}\n")
        self.text.insert("end", "\nBy judgement:\n")
        for j in JUDGEMENTS:
            n = s.by_judgement.get(j, 0)
            if n:
                self.text.insert("end",
                                    f"  {j}  {judgement_label(j):<24}: {n}\n")
        self.text.config(state="disabled")


# ── Editor & approve dialog ───────────────────────────────────────

class SEFEditor:
    def __init__(self, parent, *,
                 section: SEFSection | None = None) -> None:
        self.section = section
        self.result: SEFSection | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(f"Edit SEF #{section.section_id}"
                          if section else "New SEF section")
        self.win.geometry("780x780")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        self._build()
        if section:
            self._load()
        self.win.wait_window()

    def _build(self) -> None:
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        body.grid_columnconfigure(3, weight=1)
        self.vars: dict[str, tk.Variable] = {}
        self.texts: dict[str, tk.Text] = {}

        def entry(row, col, label, key, width=22):
            ttk.Label(body, text=label).grid(
                row=row, column=col, sticky="w", padx=4, pady=2)
            v = tk.StringVar()
            self.vars[key] = v
            ttk.Entry(body, textvariable=v, width=width).grid(
                row=row, column=col + 1, sticky="ew", padx=4, pady=2)

        def combo(row, col, label, key, values, width=22):
            ttk.Label(body, text=label).grid(
                row=row, column=col, sticky="w", padx=4, pady=2)
            v = tk.StringVar()
            self.vars[key] = v
            ttk.Combobox(body, textvariable=v, values=values,
                          state="readonly", width=width).grid(
                row=row, column=col + 1, sticky="ew", padx=4, pady=2)

        entry(0, 0, "Cycle*", "cycle")
        combo(0, 2, "Area*", "area", AREAS)
        combo(1, 0, "Judgement", "judgement",
                 ("", "1", "2", "3", "4"))
        combo(1, 2, "Status*", "status", STATUSES)
        entry(2, 0, "Author", "author")
        entry(2, 2, "Reviewer", "reviewer")
        entry(3, 0, "Approved by", "approved_by")
        entry(3, 2, "Approved on (YYYY-MM-DD)", "approved_on")

        row = 4
        for key, label in (
                ("summary_statement",    "Summary"),
                ("strengths",            "Strengths"),
                ("areas_to_develop",     "Areas to develop"),
                ("evidence",             "Evidence"),
                ("improvement_actions",  "Improvement actions"),
        ):
            ttk.Label(body, text=label).grid(
                row=row, column=0, sticky="nw", padx=4, pady=(6, 2))
            t = tk.Text(body, height=4, width=70, wrap="word")
            t.grid(row=row, column=1, columnspan=3,
                     sticky="ew", padx=4, pady=(6, 2))
            self.texts[key] = t
            row += 1

        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")

        # defaults
        today = _dt.date.today()
        self.vars["cycle"].set(f"{today.year}-{today.year + 1}")
        self.vars["area"].set(DEFAULT_AREA)
        self.vars["status"].set(DEFAULT_STATUS)

    def _load(self) -> None:
        s = self.section
        assert s is not None
        for key in ("cycle", "area", "status",
                     "author", "reviewer",
                     "approved_by", "approved_on"):
            self.vars[key].set(getattr(s, key) or "")
        self.vars["judgement"].set(
            str(s.judgement) if s.judgement is not None else "")
        for k in self.texts:
            self.texts[k].delete("1.0", "end")
            self.texts[k].insert("1.0", getattr(s, k) or "")

    def _save(self) -> None:
        payload: dict = {}
        for k, v in self.vars.items():
            payload[k] = v.get().strip()
        for k, t in self.texts.items():
            payload[k] = t.get("1.0", "end").rstrip()
        try:
            if self.section:
                self.result = data.update_section(
                    self.section.section_id, payload)
            else:
                self.result = data.create_section(payload)
        except ValidationError as e:
            messagebox.showerror("SEF", str(e), parent=self.win)
            return
        self.win.destroy()


class ApproveDialog:
    def __init__(self, parent, *, section: SEFSection) -> None:
        self.section = section
        self.result: SEFSection | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(f"Approve SEF #{section.section_id}")
        self.win.geometry("420x180")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        ttk.Label(body, text="Approved by*").grid(
            row=0, column=0, sticky="w", padx=4, pady=6)
        self.by = tk.StringVar(value=section.approved_by or "")
        ttk.Entry(body, textvariable=self.by).grid(
            row=0, column=1, sticky="ew", padx=4, pady=6)
        ttk.Label(body, text="Approved on").grid(
            row=1, column=0, sticky="w", padx=4, pady=6)
        self.when = tk.StringVar(
            value=section.approved_on
            or _dt.date.today().isoformat())
        ttk.Entry(body, textvariable=self.when, width=14).grid(
            row=1, column=1, sticky="w", padx=4, pady=6)
        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Approve",
                    command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")
        self.win.wait_window()

    def _save(self) -> None:
        try:
            self.result = data.approve(
                self.section.section_id,
                approved_by=self.by.get().strip(),
                approved_on=self.when.get().strip()
                or _dt.date.today().isoformat())
        except ValidationError as e:
            messagebox.showerror("SEF", str(e), parent=self.win)
            return
        self.win.destroy()


# ── Helpers ────────────────────────────────────────────────────────

def _prompt_text(parent, title: str, *,
                  initial: str = "") -> str | None:
    win = tk.Toplevel(parent)
    win.title(title); win.geometry("360x140")
    win.transient(parent); win.after_idle(win.grab_set)
    ttk.Label(win, text=title).pack(anchor="w", padx=8, pady=8)
    var = tk.StringVar(value=initial)
    ttk.Entry(win, textvariable=var).pack(fill="x", padx=8)
    result: dict = {"value": None}

    def ok() -> None:
        result["value"] = var.get().strip()
        win.destroy()

    bar = ttk.Frame(win)
    bar.pack(fill="x", padx=8, pady=12)
    ttk.Button(bar, text="OK", command=ok).pack(side="right", padx=4)
    ttk.Button(bar, text="Cancel",
                command=win.destroy).pack(side="right")
    win.wait_window()
    return result["value"]


def _prompt_choice(parent, title: str, options: list[str], *,
                    default: str | None = None) -> str | None:
    win = tk.Toplevel(parent)
    win.title(title); win.geometry("320x140")
    win.transient(parent); win.after_idle(win.grab_set)
    ttk.Label(win, text=title).pack(anchor="w", padx=8, pady=8)
    var = tk.StringVar(value=default or (options[0] if options else ""))
    ttk.Combobox(win, textvariable=var, values=options,
                  state="readonly").pack(fill="x", padx=8)
    result: dict = {"value": None}

    def ok() -> None:
        result["value"] = var.get()
        win.destroy()

    bar = ttk.Frame(win)
    bar.pack(fill="x", padx=8, pady=12)
    ttk.Button(bar, text="OK", command=ok).pack(side="right", padx=4)
    ttk.Button(bar, text="Cancel",
                command=win.destroy).pack(side="right")
    win.wait_window()
    return result["value"]


__all__ = ["open_sef_builder_window"]
