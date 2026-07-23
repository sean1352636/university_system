"""Tkinter views for Sixth Form Student Wellbeing."""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import messagebox, ttk

from education_system.shared import branding
from education_system.post_16.sixthform_system.modules.domain.pastoral.student_wellbeing import (
    student_wellbeing as data,
)
from education_system.post_16.sixthform_system.modules.domain.pastoral.student_wellbeing.student_wellbeing import (
    DEFAULT_GOAL_CATEGORY,
    DEFAULT_GOAL_STATUS,
    DEFAULT_RESOURCE_CATEGORY,
    GOAL_CATEGORIES,
    GOAL_STATUSES,
    Goal,
    JournalEntry,
    RESOURCE_CATEGORIES,
    Resource,
    ValidationError,
)
from education_system.post_16.sixthform_system.modules.domain.students.students import (
    students as student_data,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)

_GOAL_STATUS_TAGS = {
    "Active":    ("#e6f0ff", "#1a3f8c"),
    "Paused":    ("#fff7e6", "#7a5800"),
    "Achieved":  ("#e6f7e6", "#0d6b2a"),
    "Abandoned": ("#f3f3f3", "#666666"),
}


def open_student_wellbeing_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Student Wellbeing — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    JournalTab(nb)
    GoalsTab(nb)
    ResourcesTab(nb)
    PerStudentTab(nb)
    SummaryTab(nb)


# ── Shared helpers ─────────────────────────────────────────────────

def _student_options() -> list[tuple[str, str]]:
    rows = sorted(student_data.list_students(),
                  key=lambda s: s.student_id)
    return [(s.student_id, f"{s.student_id} — {s.full_name}")
            for s in rows]


def _today() -> str:
    return _dt.date.today().isoformat()


def _show_error(err: Exception) -> None:
    messagebox.showerror("Validation error", str(err))


# ── Journal tab ─────────────────────────────────────────────────────

class JournalTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Journal")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))

        ttk.Label(bar, text="Student:").pack(side="left")
        self.f_student = ttk.Combobox(bar, state="readonly", width=34)
        self.f_student["values"] = [""] + [d for _id, d in _student_options()]
        self.f_student.current(0)
        self.f_student.pack(side="left", padx=(2, 8))

        ttk.Label(bar, text="From:").pack(side="left")
        self.f_from = ttk.Entry(bar, width=12)
        self.f_from.pack(side="left", padx=(2, 6))
        ttk.Label(bar, text="To:").pack(side="left")
        self.f_to = ttk.Entry(bar, width=12)
        self.f_to.pack(side="left", padx=(2, 6))
        self.low_mood_only = tk.BooleanVar()
        ttk.Checkbutton(bar, text="Low mood (≤2)",
                         variable=self.low_mood_only).pack(side="left",
                                                            padx=(6, 0))

        ttk.Button(bar, text="Apply",
                   command=self.refresh).pack(side="left", padx=(8, 0))
        ttk.Button(bar, text="Clear",
                   command=self._clear_filters).pack(side="left", padx=4)

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(0, 4))
        ttk.Button(actions, text="Add entry",
                   command=self._add).pack(side="left")
        ttk.Button(actions, text="Edit",
                   command=self._edit).pack(side="left", padx=4)
        ttk.Button(actions, text="Delete",
                   command=self._delete).pack(side="left", padx=4)

        cols = ("id", "date", "student", "mood", "energy", "stress",
                 "sleep", "notes")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                  show="headings", height=22)
        for c, w, anchor in [
            ("id", 50, "e"), ("date", 90, "w"),
            ("student", 220, "w"), ("mood", 60, "center"),
            ("energy", 60, "center"), ("stress", 60, "center"),
            ("sleep", 70, "center"), ("notes", 400, "w"),
        ]:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=w, anchor=anchor)
        self.tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.tree.bind("<Double-1>", lambda _e: self._edit())

    def _clear_filters(self) -> None:
        self.f_student.current(0)
        self.f_from.delete(0, tk.END)
        self.f_to.delete(0, tk.END)
        self.low_mood_only.set(False)
        self.refresh()

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        try:
            return int(self.tree.item(sel[0], "values")[0])
        except (ValueError, IndexError):
            return None

    def _filters(self) -> dict:
        kwargs: dict = {}
        student_label = self.f_student.get()
        if student_label:
            sid = student_label.split(" — ", 1)[0]
            kwargs["student_id"] = sid
        df = self.f_from.get().strip()
        if df:
            kwargs["date_from"] = df
        dt_ = self.f_to.get().strip()
        if dt_:
            kwargs["date_to"] = dt_
        if self.low_mood_only.get():
            kwargs["low_mood"] = 2
        return kwargs

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        try:
            rows = data.list_entries_with_detail(**self._filters())
        except ValidationError as e:
            _show_error(e)
            return
        for er in rows:
            e = er.entry
            self.tree.insert("", "end", values=(
                e.entry_id, e.entry_date,
                f"{e.student_id} — {er.student_name}",
                "" if e.mood_score is None else f"{e.mood_score}",
                "" if e.energy_score is None else f"{e.energy_score}",
                "" if e.stress_score is None else f"{e.stress_score}",
                "" if e.sleep_hours is None else f"{e.sleep_hours:g}",
                (e.notes or "")[:200],
            ))

    def _add(self) -> None:
        _EntryDialog(self.frame, on_save=self.refresh)

    def _edit(self) -> None:
        eid = self._selected_id()
        if eid is None:
            messagebox.showinfo("Edit", "Select an entry first.")
            return
        existing = data.get_entry(eid)
        if existing is None:
            messagebox.showerror("Edit", f"Entry #{eid} not found.")
            return
        _EntryDialog(self.frame, existing=existing, on_save=self.refresh)

    def _delete(self) -> None:
        eid = self._selected_id()
        if eid is None:
            messagebox.showinfo("Delete", "Select an entry first.")
            return
        if not messagebox.askyesno("Delete",
                                    f"Delete entry #{eid}?"):
            return
        if data.delete_entry(eid):
            self.refresh()


class _EntryDialog:
    def __init__(self, parent, *, existing: JournalEntry | None = None,
                 on_save=None) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Journal entry"
                        + (f" #{existing.entry_id}" if existing else ""))
        self.win.transient(parent.winfo_toplevel())
        self.win.after_idle(self.win.grab_set)
        self._build()

    def _build(self) -> None:
        frm = ttk.Frame(self.win, padding=12)
        frm.pack(fill="both", expand=True)
        frm.columnconfigure(1, weight=1)

        ttk.Label(frm, text="Student:").grid(row=0, column=0, sticky="w")
        self.student = ttk.Combobox(frm, state="readonly", width=44)
        self.student["values"] = [d for _id, d in _student_options()]
        if self.existing:
            for i, (sid, d) in enumerate(_student_options()):
                if sid == self.existing.student_id:
                    self.student.current(i)
                    break
            self.student.config(state="disabled")
        self.student.grid(row=0, column=1, sticky="ew", pady=2)

        ttk.Label(frm, text="Date (YYYY-MM-DD):").grid(
            row=1, column=0, sticky="w")
        self.entry_date = ttk.Entry(frm)
        self.entry_date.insert(0,
                                self.existing.entry_date
                                if self.existing else _today())
        self.entry_date.grid(row=1, column=1, sticky="ew", pady=2)

        def _score_row(label: str, row: int, init):
            ttk.Label(frm, text=label).grid(row=row, column=0, sticky="w")
            cb = ttk.Combobox(frm, state="readonly",
                               values=("", "1", "2", "3", "4", "5"),
                               width=6)
            cb.set("" if init is None else str(init))
            cb.grid(row=row, column=1, sticky="w", pady=2)
            return cb

        e = self.existing
        self.mood = _score_row("Mood (1-5):", 2,
                                e.mood_score if e else None)
        self.energy = _score_row("Energy (1-5):", 3,
                                  e.energy_score if e else None)
        self.stress = _score_row("Stress (1-5):", 4,
                                  e.stress_score if e else None)

        ttk.Label(frm, text="Sleep hours:").grid(row=5, column=0,
                                                   sticky="w")
        self.sleep = ttk.Entry(frm, width=10)
        self.sleep.insert(0, "" if not e or e.sleep_hours is None
                              else f"{e.sleep_hours:g}")
        self.sleep.grid(row=5, column=1, sticky="w", pady=2)

        ttk.Label(frm, text="Notes:").grid(row=6, column=0,
                                             sticky="nw", pady=(6, 0))
        self.notes = tk.Text(frm, height=4, width=50)
        if e and e.notes:
            self.notes.insert("1.0", e.notes)
        self.notes.grid(row=6, column=1, sticky="ew", pady=(6, 0))

        ttk.Label(frm, text="Grateful for:").grid(row=7, column=0,
                                                    sticky="nw", pady=(6, 0))
        self.gratitude = tk.Text(frm, height=3, width=50)
        if e and e.gratitude:
            self.gratitude.insert("1.0", e.gratitude)
        self.gratitude.grid(row=7, column=1, sticky="ew", pady=(6, 0))

        btns = ttk.Frame(frm)
        btns.grid(row=8, column=0, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(btns, text="Cancel",
                    command=self.win.destroy).pack(side="right", padx=4)
        ttk.Button(btns, text="Save",
                    command=self._save).pack(side="right")

    def _payload(self) -> dict:
        student_label = self.student.get()
        sid = student_label.split(" — ", 1)[0] if student_label else ""
        return {
            "student_id":   sid,
            "entry_date":   self.entry_date.get().strip(),
            "mood_score":   self.mood.get() or None,
            "energy_score": self.energy.get() or None,
            "stress_score": self.stress.get() or None,
            "sleep_hours":  self.sleep.get().strip() or None,
            "notes":        self.notes.get("1.0", "end").strip(),
            "gratitude":    self.gratitude.get("1.0", "end").strip(),
        }

    def _save(self) -> None:
        try:
            if self.existing:
                data.update_entry(self.existing.entry_id, self._payload())
            else:
                data.create_entry(self._payload())
        except ValidationError as e:
            _show_error(e)
            return
        if self.on_save:
            self.on_save()
        self.win.destroy()


# ── Goals tab ──────────────────────────────────────────────────────

class GoalsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Goals")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Student:").pack(side="left")
        self.f_student = ttk.Combobox(bar, state="readonly", width=34)
        self.f_student["values"] = [""] + [d for _id, d in _student_options()]
        self.f_student.current(0)
        self.f_student.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Category:").pack(side="left")
        self.f_category = ttk.Combobox(bar, state="readonly",
                                        values=("",) + GOAL_CATEGORIES,
                                        width=16)
        self.f_category.current(0)
        self.f_category.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Status:").pack(side="left")
        self.f_status = ttk.Combobox(bar, state="readonly",
                                      values=("",) + GOAL_STATUSES,
                                      width=12)
        self.f_status.current(0)
        self.f_status.pack(side="left", padx=(2, 8))
        self.open_only = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar, text="Open only",
                         variable=self.open_only).pack(side="left",
                                                        padx=(6, 0))
        ttk.Button(bar, text="Apply",
                   command=self.refresh).pack(side="left", padx=(8, 0))

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(0, 4))
        ttk.Button(actions, text="Add goal",
                   command=self._add).pack(side="left")
        ttk.Button(actions, text="Edit",
                   command=self._edit).pack(side="left", padx=4)
        ttk.Button(actions, text="Mark Achieved",
                   command=self._achieve).pack(side="left", padx=4)
        ttk.Button(actions, text="Delete",
                   command=self._delete).pack(side="left", padx=4)

        cols = ("id", "status", "student", "title", "category",
                 "target", "progress")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                  show="headings", height=22)
        for c, w, anchor in [
            ("id", 50, "e"), ("status", 90, "w"),
            ("student", 220, "w"), ("title", 320, "w"),
            ("category", 130, "w"), ("target", 100, "w"),
            ("progress", 90, "center"),
        ]:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=w, anchor=anchor)
        for status, (bg, fg) in _GOAL_STATUS_TAGS.items():
            self.tree.tag_configure(status, background=bg, foreground=fg)
        self.tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.tree.bind("<Double-1>", lambda _e: self._edit())

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        try:
            return int(self.tree.item(sel[0], "values")[0])
        except (ValueError, IndexError):
            return None

    def _filters(self) -> dict:
        kwargs: dict = {}
        student_label = self.f_student.get()
        if student_label:
            kwargs["student_id"] = student_label.split(" — ", 1)[0]
        cat = self.f_category.get()
        if cat:
            kwargs["category"] = cat
        status = self.f_status.get()
        if status:
            kwargs["status"] = status
        if self.open_only.get() and not status:
            kwargs["open_only"] = True
        return kwargs

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        try:
            rows = data.list_goals_with_detail(**self._filters())
        except ValidationError as e:
            _show_error(e)
            return
        for gr in rows:
            g = gr.goal
            self.tree.insert("", "end", values=(
                g.goal_id, g.status,
                f"{g.student_id} — {gr.student_name}",
                g.title, g.category, g.target_date or "—",
                f"{g.progress_pct}%",
            ), tags=(g.status,))

    def _add(self) -> None:
        _GoalDialog(self.frame, on_save=self.refresh)

    def _edit(self) -> None:
        gid = self._selected_id()
        if gid is None:
            messagebox.showinfo("Edit", "Select a goal first.")
            return
        existing = data.get_goal(gid)
        if existing is None:
            messagebox.showerror("Edit", f"Goal #{gid} not found.")
            return
        _GoalDialog(self.frame, existing=existing, on_save=self.refresh)

    def _achieve(self) -> None:
        gid = self._selected_id()
        if gid is None:
            messagebox.showinfo("Mark Achieved", "Select a goal first.")
            return
        try:
            data.mark_goal_achieved(gid)
        except ValidationError as e:
            _show_error(e)
            return
        self.refresh()

    def _delete(self) -> None:
        gid = self._selected_id()
        if gid is None:
            messagebox.showinfo("Delete", "Select a goal first.")
            return
        if not messagebox.askyesno("Delete", f"Delete goal #{gid}?"):
            return
        if data.delete_goal(gid):
            self.refresh()


class _GoalDialog:
    def __init__(self, parent, *, existing: Goal | None = None,
                 on_save=None) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Goal" + (f" #{existing.goal_id}" if existing else ""))
        self.win.transient(parent.winfo_toplevel())
        self.win.after_idle(self.win.grab_set)
        self._build()

    def _build(self) -> None:
        frm = ttk.Frame(self.win, padding=12)
        frm.pack(fill="both", expand=True)
        frm.columnconfigure(1, weight=1)

        g = self.existing

        ttk.Label(frm, text="Student:").grid(row=0, column=0, sticky="w")
        self.student = ttk.Combobox(frm, state="readonly", width=44)
        self.student["values"] = [d for _id, d in _student_options()]
        if g:
            for i, (sid, d) in enumerate(_student_options()):
                if sid == g.student_id:
                    self.student.current(i)
                    break
            self.student.config(state="disabled")
        self.student.grid(row=0, column=1, sticky="ew", pady=2)

        ttk.Label(frm, text="Title:").grid(row=1, column=0, sticky="w")
        self.title = ttk.Entry(frm)
        if g:
            self.title.insert(0, g.title)
        self.title.grid(row=1, column=1, sticky="ew", pady=2)

        ttk.Label(frm, text="Category:").grid(row=2, column=0, sticky="w")
        self.category = ttk.Combobox(frm, state="readonly",
                                      values=GOAL_CATEGORIES, width=20)
        self.category.set(g.category if g else DEFAULT_GOAL_CATEGORY)
        self.category.grid(row=2, column=1, sticky="w", pady=2)

        ttk.Label(frm, text="Target date:").grid(row=3, column=0, sticky="w")
        self.target_date = ttk.Entry(frm, width=14)
        if g and g.target_date:
            self.target_date.insert(0, g.target_date)
        self.target_date.grid(row=3, column=1, sticky="w", pady=2)

        ttk.Label(frm, text="Progress %:").grid(row=4, column=0, sticky="w")
        self.progress = ttk.Spinbox(frm, from_=0, to=100, increment=5,
                                      width=8)
        self.progress.set(str(g.progress_pct) if g else "0")
        self.progress.grid(row=4, column=1, sticky="w", pady=2)

        ttk.Label(frm, text="Status:").grid(row=5, column=0, sticky="w")
        self.status = ttk.Combobox(frm, state="readonly",
                                    values=GOAL_STATUSES, width=14)
        self.status.set(g.status if g else DEFAULT_GOAL_STATUS)
        self.status.grid(row=5, column=1, sticky="w", pady=2)

        ttk.Label(frm, text="Notes:").grid(row=6, column=0,
                                             sticky="nw", pady=(6, 0))
        self.notes = tk.Text(frm, height=5, width=50)
        if g and g.notes:
            self.notes.insert("1.0", g.notes)
        self.notes.grid(row=6, column=1, sticky="ew", pady=(6, 0))

        btns = ttk.Frame(frm)
        btns.grid(row=7, column=0, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(btns, text="Cancel",
                    command=self.win.destroy).pack(side="right", padx=4)
        ttk.Button(btns, text="Save",
                    command=self._save).pack(side="right")

    def _payload(self) -> dict:
        student_label = self.student.get()
        sid = student_label.split(" — ", 1)[0] if student_label else ""
        return {
            "student_id":   sid,
            "title":        self.title.get().strip(),
            "category":     self.category.get(),
            "target_date":  self.target_date.get().strip() or None,
            "progress_pct": self.progress.get(),
            "status":       self.status.get(),
            "notes":        self.notes.get("1.0", "end").strip(),
        }

    def _save(self) -> None:
        try:
            if self.existing:
                data.update_goal(self.existing.goal_id, self._payload())
            else:
                data.create_goal(self._payload())
        except ValidationError as e:
            _show_error(e)
            return
        if self.on_save:
            self.on_save()
        self.win.destroy()


# ── Resources tab ──────────────────────────────────────────────────

class ResourcesTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Resources")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Student:").pack(side="left")
        self.f_student = ttk.Combobox(bar, state="readonly", width=34)
        self.f_student["values"] = [""] + [d for _id, d in _student_options()]
        self.f_student.current(0)
        self.f_student.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Category:").pack(side="left")
        self.f_category = ttk.Combobox(
            bar, state="readonly",
            values=("",) + RESOURCE_CATEGORIES, width=18)
        self.f_category.current(0)
        self.f_category.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Title contains:").pack(side="left")
        self.f_title = ttk.Entry(bar, width=18)
        self.f_title.pack(side="left", padx=(2, 6))
        ttk.Button(bar, text="Apply",
                   command=self.refresh).pack(side="left", padx=(8, 0))

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(0, 4))
        ttk.Button(actions, text="Add resource",
                   command=self._add).pack(side="left")
        ttk.Button(actions, text="Edit",
                   command=self._edit).pack(side="left", padx=4)
        ttk.Button(actions, text="Delete",
                   command=self._delete).pack(side="left", padx=4)

        cols = ("id", "category", "student", "title", "url", "contact")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                  show="headings", height=22)
        for c, w, anchor in [
            ("id", 50, "e"), ("category", 130, "w"),
            ("student", 220, "w"), ("title", 280, "w"),
            ("url", 320, "w"), ("contact", 180, "w"),
        ]:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=w, anchor=anchor)
        self.tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.tree.bind("<Double-1>", lambda _e: self._edit())

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        try:
            return int(self.tree.item(sel[0], "values")[0])
        except (ValueError, IndexError):
            return None

    def _filters(self) -> dict:
        kwargs: dict = {}
        sl = self.f_student.get()
        if sl:
            kwargs["student_id"] = sl.split(" — ", 1)[0]
        cat = self.f_category.get()
        if cat:
            kwargs["category"] = cat
        title = self.f_title.get().strip()
        if title:
            kwargs["title_like"] = title
        return kwargs

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        try:
            rows = data.list_resources_with_detail(**self._filters())
        except ValidationError as e:
            _show_error(e)
            return
        for rr in rows:
            r = rr.resource
            self.tree.insert("", "end", values=(
                r.resource_id, r.category,
                f"{r.student_id} — {rr.student_name}",
                r.title, r.url or "", r.contact or "",
            ))

    def _add(self) -> None:
        _ResourceDialog(self.frame, on_save=self.refresh)

    def _edit(self) -> None:
        rid = self._selected_id()
        if rid is None:
            messagebox.showinfo("Edit", "Select a resource first.")
            return
        existing = data.get_resource(rid)
        if existing is None:
            messagebox.showerror("Edit", f"Resource #{rid} not found.")
            return
        _ResourceDialog(self.frame, existing=existing, on_save=self.refresh)

    def _delete(self) -> None:
        rid = self._selected_id()
        if rid is None:
            messagebox.showinfo("Delete", "Select a resource first.")
            return
        if not messagebox.askyesno("Delete", f"Delete resource #{rid}?"):
            return
        if data.delete_resource(rid):
            self.refresh()


class _ResourceDialog:
    def __init__(self, parent, *, existing: Resource | None = None,
                 on_save=None) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Resource"
                        + (f" #{existing.resource_id}" if existing else ""))
        self.win.transient(parent.winfo_toplevel())
        self.win.after_idle(self.win.grab_set)
        self._build()

    def _build(self) -> None:
        frm = ttk.Frame(self.win, padding=12)
        frm.pack(fill="both", expand=True)
        frm.columnconfigure(1, weight=1)

        r = self.existing

        ttk.Label(frm, text="Student:").grid(row=0, column=0, sticky="w")
        self.student = ttk.Combobox(frm, state="readonly", width=44)
        self.student["values"] = [d for _id, d in _student_options()]
        if r:
            for i, (sid, d) in enumerate(_student_options()):
                if sid == r.student_id:
                    self.student.current(i)
                    break
            self.student.config(state="disabled")
        self.student.grid(row=0, column=1, sticky="ew", pady=2)

        ttk.Label(frm, text="Title:").grid(row=1, column=0, sticky="w")
        self.title = ttk.Entry(frm)
        if r:
            self.title.insert(0, r.title)
        self.title.grid(row=1, column=1, sticky="ew", pady=2)

        ttk.Label(frm, text="Category:").grid(row=2, column=0, sticky="w")
        self.category = ttk.Combobox(frm, state="readonly",
                                      values=RESOURCE_CATEGORIES, width=22)
        self.category.set(r.category if r else DEFAULT_RESOURCE_CATEGORY)
        self.category.grid(row=2, column=1, sticky="w", pady=2)

        ttk.Label(frm, text="URL:").grid(row=3, column=0, sticky="w")
        self.url = ttk.Entry(frm)
        if r and r.url:
            self.url.insert(0, r.url)
        self.url.grid(row=3, column=1, sticky="ew", pady=2)

        ttk.Label(frm, text="Contact:").grid(row=4, column=0, sticky="w")
        self.contact = ttk.Entry(frm)
        if r and r.contact:
            self.contact.insert(0, r.contact)
        self.contact.grid(row=4, column=1, sticky="ew", pady=2)

        ttk.Label(frm, text="Notes:").grid(row=5, column=0,
                                             sticky="nw", pady=(6, 0))
        self.notes = tk.Text(frm, height=5, width=50)
        if r and r.notes:
            self.notes.insert("1.0", r.notes)
        self.notes.grid(row=5, column=1, sticky="ew", pady=(6, 0))

        btns = ttk.Frame(frm)
        btns.grid(row=6, column=0, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(btns, text="Cancel",
                    command=self.win.destroy).pack(side="right", padx=4)
        ttk.Button(btns, text="Save",
                    command=self._save).pack(side="right")

    def _payload(self) -> dict:
        student_label = self.student.get()
        sid = student_label.split(" — ", 1)[0] if student_label else ""
        return {
            "student_id": sid,
            "title":      self.title.get().strip(),
            "category":   self.category.get(),
            "url":        self.url.get().strip() or None,
            "contact":    self.contact.get().strip() or None,
            "notes":      self.notes.get("1.0", "end").strip(),
        }

    def _save(self) -> None:
        try:
            if self.existing:
                data.update_resource(self.existing.resource_id,
                                      self._payload())
            else:
                data.create_resource(self._payload())
        except ValidationError as e:
            _show_error(e)
            return
        if self.on_save:
            self.on_save()
        self.win.destroy()


# ── Per-student tab ─────────────────────────────────────────────────

class PerStudentTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Per Student")
        self._build()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Student:").pack(side="left")
        self.student = ttk.Combobox(bar, state="readonly", width=44)
        self.student["values"] = [d for _id, d in _student_options()]
        self.student.pack(side="left", padx=(2, 6))
        ttk.Button(bar, text="Show",
                   command=self.refresh).pack(side="left", padx=4)

        self.summary_lbl = ttk.Label(
            self.frame, text="(select a student)",
            foreground="#555", justify="left", padding=10)
        self.summary_lbl.pack(fill="x", padx=8, pady=(4, 0))

        body = ttk.Frame(self.frame)
        body.pack(fill="both", expand=True, padx=8, pady=8)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(1, weight=1)

        ttk.Label(body, text="Recent journal entries",
                  font=("", 10, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(body, text="Open goals",
                  font=("", 10, "bold")).grid(row=0, column=1,
                                                 sticky="w", padx=(8, 0))

        self.entries_tree = ttk.Treeview(
            body, columns=("date", "mood", "stress", "sleep", "notes"),
            show="headings", height=14)
        for c, w in [("date", 90), ("mood", 60), ("stress", 60),
                       ("sleep", 70), ("notes", 280)]:
            self.entries_tree.heading(c, text=c.title())
            self.entries_tree.column(c, width=w, anchor="w")
        self.entries_tree.grid(row=1, column=0, sticky="nsew",
                                pady=(4, 0))

        self.goals_tree = ttk.Treeview(
            body, columns=("title", "category", "target", "progress",
                            "status"),
            show="headings", height=14)
        for c, w in [("title", 220), ("category", 110), ("target", 90),
                       ("progress", 70), ("status", 90)]:
            self.goals_tree.heading(c, text=c.title())
            self.goals_tree.column(c, width=w, anchor="w")
        self.goals_tree.grid(row=1, column=1, sticky="nsew",
                              padx=(8, 0), pady=(4, 0))

    def refresh(self) -> None:
        sl = self.student.get()
        if not sl:
            messagebox.showinfo("Per Student", "Select a student first.")
            return
        sid = sl.split(" — ", 1)[0]
        try:
            s = data.per_student_summary(sid)
        except ValidationError as e:
            _show_error(e)
            return
        bits = [
            f"Entries: {s.entry_count}",
            f"Goals: {s.goal_count_open} open / "
            f"{s.goal_count_achieved} achieved",
            f"Resources: {s.resource_count}",
        ]
        if s.latest_entry_date:
            latest = (f"Latest {s.latest_entry_date}: "
                       f"mood {s.latest_mood or '—'} · "
                       f"energy {s.latest_energy or '—'} · "
                       f"stress {s.latest_stress or '—'} · "
                       f"sleep "
                       f"{s.latest_sleep_hours if s.latest_sleep_hours is not None else '—'}h")
            bits.append(latest)
        if s.avg_mood is not None or s.avg_sleep_hours is not None:
            bits.append(
                f"Avg: mood {s.avg_mood or '—'} · "
                f"energy {s.avg_energy or '—'} · "
                f"stress {s.avg_stress or '—'} · "
                f"sleep {s.avg_sleep_hours or '—'}h")
        self.summary_lbl.config(text="    ".join(bits))

        for i in self.entries_tree.get_children():
            self.entries_tree.delete(i)
        for e in data.list_entries(student_id=sid)[:30]:
            self.entries_tree.insert("", "end", values=(
                e.entry_date,
                "" if e.mood_score is None else f"{e.mood_score}",
                "" if e.stress_score is None else f"{e.stress_score}",
                "" if e.sleep_hours is None else f"{e.sleep_hours:g}",
                (e.notes or "")[:120],
            ))

        for i in self.goals_tree.get_children():
            self.goals_tree.delete(i)
        for g in data.list_goals(student_id=sid, open_only=True):
            self.goals_tree.insert("", "end", values=(
                g.title, g.category, g.target_date or "—",
                f"{g.progress_pct}%", g.status,
            ))


# ── Summary tab ────────────────────────────────────────────────────

class SummaryTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Overview")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(bar, text="Refresh",
                   command=self.refresh).pack(side="left")

        self.totals_lbl = ttk.Label(
            self.frame, text="", justify="left", padding=10,
            font=("", 10))
        self.totals_lbl.pack(fill="x", padx=8)

        cols_frame = ttk.Frame(self.frame)
        cols_frame.pack(fill="both", expand=True, padx=8, pady=8)
        cols_frame.columnconfigure(0, weight=1)
        cols_frame.columnconfigure(1, weight=1)
        cols_frame.rowconfigure(1, weight=1)

        ttk.Label(cols_frame, text="Goals by category",
                  font=("", 10, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(cols_frame, text="Resources by category",
                  font=("", 10, "bold")).grid(row=0, column=1,
                                                 sticky="w", padx=(8, 0))

        self.goals_tree = ttk.Treeview(
            cols_frame, columns=("category", "count"),
            show="headings", height=12)
        for c, w, a in [("category", 220, "w"), ("count", 80, "e")]:
            self.goals_tree.heading(c, text=c.title())
            self.goals_tree.column(c, width=w, anchor=a)
        self.goals_tree.grid(row=1, column=0, sticky="nsew", pady=(4, 0))

        self.resources_tree = ttk.Treeview(
            cols_frame, columns=("category", "count"),
            show="headings", height=12)
        for c, w, a in [("category", 220, "w"), ("count", 80, "e")]:
            self.resources_tree.heading(c, text=c.title())
            self.resources_tree.column(c, width=w, anchor=a)
        self.resources_tree.grid(row=1, column=1, sticky="nsew",
                                  padx=(8, 0), pady=(4, 0))

    def refresh(self) -> None:
        s = data.summary()
        self.totals_lbl.config(text=(
            f"Entries: {s.total_entries}    "
            f"(low-mood {s.low_mood_count}, "
            f"high-stress {s.high_stress_count})\n"
            f"Goals: {s.total_goals}    "
            f"(active {s.goals_active}, paused {s.goals_paused}, "
            f"achieved {s.goals_achieved}, "
            f"abandoned {s.goals_abandoned})\n"
            f"Resources: {s.total_resources}    "
            f"Students engaged: {s.students_engaged}"
        ))
        for i in self.goals_tree.get_children():
            self.goals_tree.delete(i)
        for cat, n in s.by_goal_category.items():
            if n:
                self.goals_tree.insert("", "end", values=(cat, n))
        for i in self.resources_tree.get_children():
            self.resources_tree.delete(i)
        for cat, n in s.by_resource_category.items():
            if n:
                self.resources_tree.insert("", "end", values=(cat, n))
