"""Tkinter views for Sixth Form Wellbeing.

A 5-tab notebook:
* Check-ins
* Sessions
* Flags
* Per-student
* Summary
"""

from __future__ import annotations

import logging
import tkinter as tk
from datetime import date as _date
from tkinter import messagebox, ttk
from typing import Any, Callable
from education_system.post_16.sixthform_system.modules.domain.students.students import students
from education_system.post_16.sixthform_system.modules.domain.students.students import students as student_data
from education_system.post_16.sixthform_system.modules.domain.pastoral.wellbeing import wellbeing as data
from education_system.shared import branding
from education_system.post_16.sixthform_system.modules.domain.pastoral.wellbeing.wellbeing import (
    CheckIn,
    DEFAULT_SESSION_STATUS,
    DEFAULT_SESSION_TYPE,
    FLAG_TYPES,
    Flag,
    SCORE_MAX,
    SCORE_MIN,
    SESSION_STATUSES,
    SESSION_TYPES,
    Session,
    ValidationError,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)


def open_wellbeing_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Wellbeing — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    CheckInTab(nb)
    SessionTab(nb)
    FlagTab(nb)
    PerStudentTab(nb)
    SummaryTab(nb)


# ── Shared helpers ────────────────────────────────────────────────

def _student_options() -> list[tuple[str, str]]:
    """Return [(student_id, "S12345 — Alice Smith")] sorted by id."""
    rows = sorted(student_data.list_students(),
                   key=lambda s: s.student_id)
    return [(s.student_id, f"{s.student_id} — {s.full_name}") for s in rows]


def _pick_student_combo(parent: tk.Misc, *,
                         initial: str | None = None) -> tuple[ttk.Combobox,
                                                              list[str]]:
    opts = _student_options()
    ids = [sid for sid, _ in opts]
    labels = [lbl for _, lbl in opts]
    cb = ttk.Combobox(parent, values=labels, state="readonly", width=40)
    if initial:
        if initial in ids:
            cb.current(ids.index(initial))
    elif labels:
        cb.current(0)
    return cb, ids


def _name_lookup() -> dict[str, str]:
    return {s.student_id: s.full_name for s in student_data.list_students()}


def _today() -> str:
    return _date.today().isoformat()


# ══ Check-in tab ═══════════════════════════════════════════════════

class CheckInTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Check-ins")
        self._build()
        self.refresh()

    def _build(self) -> None:
        # Filter bar
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Student ID:").pack(side="left")
        self.f_student = ttk.Entry(bar, width=12)
        self.f_student.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="From:").pack(side="left")
        self.f_from = ttk.Entry(bar, width=12)
        self.f_from.pack(side="left", padx=(2, 6))
        ttk.Label(bar, text="To:").pack(side="left")
        self.f_to = ttk.Entry(bar, width=12)
        self.f_to.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="Mood ≤").pack(side="left")
        self.f_mood = ttk.Entry(bar, width=4)
        self.f_mood.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="Stress ≥").pack(side="left")
        self.f_stress = ttk.Entry(bar, width=4)
        self.f_stress.pack(side="left", padx=(2, 10))
        ttk.Button(bar, text="Apply", command=self.refresh).pack(side="left")
        ttk.Button(bar, text="Clear",
                    command=self._clear_filters).pack(side="left", padx=4)

        # Table
        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "student", "name", "date", "mood", "stress",
                "sleep", "by", "notes")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings")
        widths = {"id": 60, "student": 90, "name": 200, "date": 100,
                  "mood": 60, "stress": 60, "sleep": 60, "by": 130,
                  "notes": 360}
        for c in cols:
            self.tree.heading(c, text=c.capitalize())
            self.tree.column(c, width=widths[c], anchor="w")
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", lambda _e: self._edit_selected())

        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                   anchor="w").pack(fill="x", padx=8)

        # Actions
        self.actions_holder = ttk.Frame(self.frame)
        self.actions_holder.pack(fill="x", padx=8, pady=(4, 8))
        self._build_actions()

    def _build_actions(self) -> None:
        for w in self.actions_holder.winfo_children():
            w.destroy()
        bar = ttk.Frame(self.actions_holder)
        bar.pack(fill="x")
        ttk.Button(bar, text="New",
                    command=self._new).pack(side="left")
        ttk.Button(bar, text="Edit",
                    command=self._edit_selected).pack(side="left", padx=4)
        ttk.Button(bar, text="Delete",
                    command=self._delete_selected).pack(side="left", padx=4)
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="right")

    def _clear_filters(self) -> None:
        for e in (self.f_student, self.f_from, self.f_to,
                   self.f_mood, self.f_stress):
            e.delete(0, "end")
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        try:
            mood = self.f_mood.get().strip()
            stress = self.f_stress.get().strip()
            rows = data.list_checkins(
                student_id=self.f_student.get().strip() or None,
                date_from=self.f_from.get().strip() or None,
                date_to=self.f_to.get().strip() or None,
                low_mood=int(mood) if mood else None,
                high_stress=int(stress) if stress else None,
            )
        except (ValidationError, ValueError) as e:
            messagebox.showerror("Filter error", str(e))
            return
        names = _name_lookup()
        for c in rows:
            self.tree.insert("", "end", values=(
                c.checkin_id, c.student_id, names.get(c.student_id, "?"),
                c.checkin_date,
                "—" if c.mood_score is None else c.mood_score,
                "—" if c.stress_score is None else c.stress_score,
                "—" if c.sleep_score is None else c.sleep_score,
                c.recorded_by or "—",
                (c.notes or "").replace("\n", " ⏎ "),
            ))
        self.count_var.set(f"{len(rows)} check-in(s).")
        self._build_actions()

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        return int(self.tree.item(sel[0])["values"][0])

    def _new(self) -> None:
        CheckInDialog(self.frame.winfo_toplevel(),
                       existing=None, on_save=self.refresh)

    def _edit_selected(self) -> None:
        cid = self._selected_id()
        if cid is None:
            messagebox.showinfo("Edit", "Select a check-in first.")
            return
        existing = data.get_checkin(cid)
        if existing is None:
            messagebox.showerror("Edit", f"No check-in #{cid}")
            return
        CheckInDialog(self.frame.winfo_toplevel(),
                       existing=existing, on_save=self.refresh)

    def _delete_selected(self) -> None:
        cid = self._selected_id()
        if cid is None:
            messagebox.showinfo("Delete", "Select a check-in first.")
            return
        if not messagebox.askyesno("Delete",
                                     f"Delete check-in #{cid}?"):
            return
        try:
            data.delete_checkin(cid)
        except Exception as e:
            messagebox.showerror("Delete failed", str(e))
            return
        self.refresh()


class CheckInDialog:
    def __init__(self, parent: tk.Misc, *,
                 existing: CheckIn | None,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Edit Check-in" if existing else "New Check-in")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        self._build()

    def _build(self) -> None:
        form = ttk.Frame(self.win)
        form.pack(fill="both", expand=True, padx=12, pady=12)

        r = 0
        ttk.Label(form, text="Student:").grid(row=r, column=0,
                                                sticky="e", pady=4)
        if self.existing:
            self.student_cb = None
            self._student_id = self.existing.student_id
            names = _name_lookup()
            ttk.Label(form,
                       text=f"{self._student_id} — "
                            f"{names.get(self._student_id, '?')}"
                       ).grid(row=r, column=1, sticky="w", padx=6)
        else:
            cb, ids = _pick_student_combo(form)
            self.student_cb = cb
            self._student_ids = ids
            cb.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Date:").grid(row=r, column=0,
                                             sticky="e", pady=4)
        self.date_e = ttk.Entry(form, width=14)
        self.date_e.insert(0, self.existing.checkin_date
                              if self.existing else _today())
        self.date_e.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form,
                   text=f"Mood ({SCORE_MIN}-{SCORE_MAX}):").grid(
            row=r, column=0, sticky="e", pady=4)
        self.mood_e = ttk.Entry(form, width=4)
        if self.existing and self.existing.mood_score is not None:
            self.mood_e.insert(0, str(self.existing.mood_score))
        self.mood_e.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form,
                   text=f"Stress ({SCORE_MIN}-{SCORE_MAX}):").grid(
            row=r, column=0, sticky="e", pady=4)
        self.stress_e = ttk.Entry(form, width=4)
        if self.existing and self.existing.stress_score is not None:
            self.stress_e.insert(0, str(self.existing.stress_score))
        self.stress_e.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form,
                   text=f"Sleep ({SCORE_MIN}-{SCORE_MAX}):").grid(
            row=r, column=0, sticky="e", pady=4)
        self.sleep_e = ttk.Entry(form, width=4)
        if self.existing and self.existing.sleep_score is not None:
            self.sleep_e.insert(0, str(self.existing.sleep_score))
        self.sleep_e.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Recorded by:").grid(row=r, column=0,
                                                    sticky="e", pady=4)
        self.by_e = ttk.Entry(form, width=30)
        if self.existing and self.existing.recorded_by:
            self.by_e.insert(0, self.existing.recorded_by)
        self.by_e.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Notes:").grid(row=r, column=0,
                                              sticky="ne", pady=4)
        self.notes_text = tk.Text(form, width=50, height=6, wrap="word")
        if self.existing and self.existing.notes:
            self.notes_text.insert("1.0", self.existing.notes)
        self.notes_text.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        bar = ttk.Frame(form)
        bar.grid(row=r, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save", command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        if self.student_cb is not None:
            idx = self.student_cb.current()
            if idx < 0:
                messagebox.showerror("Validation", "Pick a student.")
                return
            sid = self._student_ids[idx]
        else:
            sid = self._student_id

        def _parse_int(s: str) -> int | None:
            s = s.strip()
            return int(s) if s else None

        payload = {
            "student_id":   sid,
            "checkin_date": self.date_e.get().strip(),
            "mood_score":   self.mood_e.get().strip() or None,
            "stress_score": self.stress_e.get().strip() or None,
            "sleep_score":  self.sleep_e.get().strip() or None,
            "recorded_by":  self.by_e.get().strip(),
            "notes":        self.notes_text.get("1.0", "end").strip(),
        }
        try:
            if self.existing:
                data.update_checkin(self.existing.checkin_id, payload)
            else:
                data.create_checkin(payload)
        except ValidationError as e:
            messagebox.showerror("Validation", str(e))
            return
        except Exception as e:
            logger.exception("save check-in failed")
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


# ══ Session tab ════════════════════════════════════════════════════

class SessionTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Sessions")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Student ID:").pack(side="left")
        self.f_student = ttk.Entry(bar, width=12)
        self.f_student.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="Type:").pack(side="left")
        self.f_type = ttk.Combobox(bar, values=("",) + SESSION_TYPES,
                                     state="readonly", width=18)
        self.f_type.current(0)
        self.f_type.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="Status:").pack(side="left")
        self.f_status = ttk.Combobox(bar, values=("",) + SESSION_STATUSES,
                                       state="readonly", width=12)
        self.f_status.current(0)
        self.f_status.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="From:").pack(side="left")
        self.f_from = ttk.Entry(bar, width=12)
        self.f_from.pack(side="left", padx=(2, 6))
        ttk.Label(bar, text="To:").pack(side="left")
        self.f_to = ttk.Entry(bar, width=12)
        self.f_to.pack(side="left", padx=(2, 10))
        ttk.Button(bar, text="Apply", command=self.refresh).pack(side="left")
        ttk.Button(bar, text="Clear",
                    command=self._clear_filters).pack(side="left", padx=4)

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "student", "name", "date", "type", "mins", "status",
                "provider", "follow")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings")
        widths = {"id": 60, "student": 90, "name": 180, "date": 100,
                  "type": 150, "mins": 60, "status": 100,
                  "provider": 180, "follow": 100}
        for c in cols:
            self.tree.heading(c, text=c.capitalize())
            self.tree.column(c, width=widths[c], anchor="w")
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", lambda _e: self._view_selected())

        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                   anchor="w").pack(fill="x", padx=8)

        self.actions_holder = ttk.Frame(self.frame)
        self.actions_holder.pack(fill="x", padx=8, pady=(4, 8))
        self._build_actions()

    def _build_actions(self) -> None:
        for w in self.actions_holder.winfo_children():
            w.destroy()
        bar = ttk.Frame(self.actions_holder)
        bar.pack(fill="x")
        ttk.Button(bar, text="View",
                    command=self._view_selected).pack(side="left")
        ttk.Button(bar, text="New",
                    command=self._new).pack(side="left", padx=4)
        ttk.Button(bar, text="Edit",
                    command=self._edit_selected).pack(side="left", padx=4)
        ttk.Button(bar, text="Delete",
                    command=self._delete_selected).pack(side="left", padx=4)
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="right")

    def _clear_filters(self) -> None:
        self.f_student.delete(0, "end")
        self.f_from.delete(0, "end")
        self.f_to.delete(0, "end")
        self.f_type.current(0)
        self.f_status.current(0)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        try:
            rows = data.list_sessions(
                student_id=self.f_student.get().strip() or None,
                session_type=self.f_type.get() or None,
                status=self.f_status.get() or None,
                date_from=self.f_from.get().strip() or None,
                date_to=self.f_to.get().strip() or None,
            )
        except ValidationError as e:
            messagebox.showerror("Filter error", str(e))
            return
        names = _name_lookup()
        for s in rows:
            self.tree.insert("", "end", values=(
                s.session_id, s.student_id, names.get(s.student_id, "?"),
                s.session_date, s.session_type,
                s.duration_minutes or "—", s.status,
                s.provider or "—", s.follow_up_date or "—",
            ))
        self.count_var.set(f"{len(rows)} session(s).")
        self._build_actions()

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        return int(self.tree.item(sel[0])["values"][0])

    def _view_selected(self) -> None:
        sid = self._selected_id()
        if sid is None:
            messagebox.showinfo("View", "Select a session first.")
            return
        s = data.get_session(sid)
        if s is None:
            messagebox.showerror("View", f"No session #{sid}")
            return
        names = _name_lookup()
        lines = [
            f"Session   : #{s.session_id}",
            f"Student   : {s.student_id} — {names.get(s.student_id, '?')}",
            f"Date      : {s.session_date}",
            f"Type      : {s.session_type}",
            f"Status    : {s.status}",
            f"Duration  : "
            f"{(str(s.duration_minutes) + ' min') if s.duration_minutes else '—'}",
            f"Provider  : {s.provider or '—'}",
            f"Topics    : {s.topics or '—'}",
            f"Follow-up : {s.follow_up_date or '—'}",
            "",
            "Action plan:",
            s.action_plan or "  —",
            "",
            "Notes:",
            s.notes or "  —",
        ]
        messagebox.showinfo(f"Session #{s.session_id}", "\n".join(lines))

    def _new(self) -> None:
        SessionDialog(self.frame.winfo_toplevel(),
                       existing=None, on_save=self.refresh)

    def _edit_selected(self) -> None:
        sid = self._selected_id()
        if sid is None:
            messagebox.showinfo("Edit", "Select a session first.")
            return
        existing = data.get_session(sid)
        if existing is None:
            messagebox.showerror("Edit", f"No session #{sid}")
            return
        SessionDialog(self.frame.winfo_toplevel(),
                       existing=existing, on_save=self.refresh)

    def _delete_selected(self) -> None:
        sid = self._selected_id()
        if sid is None:
            messagebox.showinfo("Delete", "Select a session first.")
            return
        if not messagebox.askyesno("Delete", f"Delete session #{sid}?"):
            return
        try:
            data.delete_session(sid)
        except Exception as e:
            messagebox.showerror("Delete failed", str(e))
            return
        self.refresh()


class SessionDialog:
    def __init__(self, parent: tk.Misc, *,
                 existing: Session | None,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Edit Session" if existing else "New Session")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        self._build()

    def _build(self) -> None:
        form = ttk.Frame(self.win)
        form.pack(fill="both", expand=True, padx=12, pady=12)

        r = 0
        ttk.Label(form, text="Student:").grid(row=r, column=0,
                                                sticky="e", pady=4)
        if self.existing:
            self.student_cb = None
            self._student_id = self.existing.student_id
            names = _name_lookup()
            ttk.Label(form,
                       text=f"{self._student_id} — "
                            f"{names.get(self._student_id, '?')}"
                       ).grid(row=r, column=1, sticky="w", padx=6)
        else:
            cb, ids = _pick_student_combo(form)
            self.student_cb = cb
            self._student_ids = ids
            cb.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Date:").grid(row=r, column=0,
                                              sticky="e", pady=4)
        self.date_e = ttk.Entry(form, width=14)
        self.date_e.insert(0, self.existing.session_date
                              if self.existing else _today())
        self.date_e.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Type:").grid(row=r, column=0,
                                              sticky="e", pady=4)
        self.type_cb = ttk.Combobox(form, values=SESSION_TYPES,
                                       state="readonly", width=22)
        self.type_cb.set(self.existing.session_type
                           if self.existing else DEFAULT_SESSION_TYPE)
        self.type_cb.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Status:").grid(row=r, column=0,
                                                sticky="e", pady=4)
        self.status_cb = ttk.Combobox(form, values=SESSION_STATUSES,
                                         state="readonly", width=14)
        self.status_cb.set(self.existing.status
                             if self.existing else DEFAULT_SESSION_STATUS)
        self.status_cb.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Duration (min):").grid(row=r, column=0,
                                                       sticky="e", pady=4)
        self.dur_e = ttk.Entry(form, width=8)
        if self.existing and self.existing.duration_minutes:
            self.dur_e.insert(0, str(self.existing.duration_minutes))
        self.dur_e.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Provider:").grid(row=r, column=0,
                                                  sticky="e", pady=4)
        self.prov_e = ttk.Entry(form, width=40)
        if self.existing and self.existing.provider:
            self.prov_e.insert(0, self.existing.provider)
        self.prov_e.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Topics:").grid(row=r, column=0,
                                                sticky="e", pady=4)
        self.topics_e = ttk.Entry(form, width=60)
        if self.existing and self.existing.topics:
            self.topics_e.insert(0, self.existing.topics)
        self.topics_e.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Follow-up date:").grid(row=r, column=0,
                                                       sticky="e", pady=4)
        self.follow_e = ttk.Entry(form, width=14)
        if self.existing and self.existing.follow_up_date:
            self.follow_e.insert(0, self.existing.follow_up_date)
        self.follow_e.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Action plan:").grid(row=r, column=0,
                                                    sticky="ne", pady=4)
        self.plan_text = tk.Text(form, width=60, height=6, wrap="word")
        if self.existing and self.existing.action_plan:
            self.plan_text.insert("1.0", self.existing.action_plan)
        self.plan_text.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Notes:").grid(row=r, column=0,
                                              sticky="ne", pady=4)
        self.notes_text = tk.Text(form, width=60, height=6, wrap="word")
        if self.existing and self.existing.notes:
            self.notes_text.insert("1.0", self.existing.notes)
        self.notes_text.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        bar = ttk.Frame(form)
        bar.grid(row=r, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save", command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        if self.student_cb is not None:
            idx = self.student_cb.current()
            if idx < 0:
                messagebox.showerror("Validation", "Pick a student.")
                return
            sid = self._student_ids[idx]
        else:
            sid = self._student_id
        payload = {
            "student_id":       sid,
            "session_date":     self.date_e.get().strip(),
            "session_type":     self.type_cb.get(),
            "status":           self.status_cb.get(),
            "duration_minutes": self.dur_e.get().strip() or None,
            "provider":         self.prov_e.get().strip(),
            "topics":           self.topics_e.get().strip(),
            "action_plan":      self.plan_text.get("1.0", "end").strip(),
            "follow_up_date":   self.follow_e.get().strip(),
            "notes":            self.notes_text.get("1.0", "end").strip(),
        }
        try:
            if self.existing:
                data.update_session(self.existing.session_id, payload)
            else:
                data.create_session(payload)
        except ValidationError as e:
            messagebox.showerror("Validation", str(e))
            return
        except Exception as e:
            logger.exception("save session failed")
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


# ══ Flag tab ═══════════════════════════════════════════════════════

class FlagTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Flags")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Student ID:").pack(side="left")
        self.f_student = ttk.Entry(bar, width=12)
        self.f_student.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="Type:").pack(side="left")
        self.f_type = ttk.Combobox(bar, values=("",) + FLAG_TYPES,
                                     state="readonly", width=24)
        self.f_type.current(0)
        self.f_type.pack(side="left", padx=(2, 10))
        self.f_active_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar, text="Active only",
                          variable=self.f_active_var,
                          command=self.refresh).pack(side="left")
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=(10, 2))
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left")

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "student", "name", "type", "start", "end",
                "status", "notes")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings")
        widths = {"id": 60, "student": 90, "name": 200, "type": 200,
                  "start": 100, "end": 100, "status": 80, "notes": 360}
        for c in cols:
            self.tree.heading(c, text=c.capitalize())
            self.tree.column(c, width=widths[c], anchor="w")
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", lambda _e: self._edit_selected())

        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                   anchor="w").pack(fill="x", padx=8)

        self.actions_holder = ttk.Frame(self.frame)
        self.actions_holder.pack(fill="x", padx=8, pady=(4, 8))
        self._build_actions()

    def _build_actions(self) -> None:
        for w in self.actions_holder.winfo_children():
            w.destroy()
        bar = ttk.Frame(self.actions_holder)
        bar.pack(fill="x")
        ttk.Button(bar, text="New",
                    command=self._new).pack(side="left")
        ttk.Button(bar, text="Edit",
                    command=self._edit_selected).pack(side="left", padx=4)
        ttk.Button(bar, text="Close",
                    command=self._close_selected).pack(side="left", padx=4)
        ttk.Button(bar, text="Re-open",
                    command=self._reopen_selected).pack(side="left", padx=4)
        ttk.Button(bar, text="Delete",
                    command=self._delete_selected).pack(side="left", padx=4)
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="right")

    def _clear(self) -> None:
        self.f_student.delete(0, "end")
        self.f_type.current(0)
        self.f_active_var.set(False)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        try:
            rows = data.list_flags(
                student_id=self.f_student.get().strip() or None,
                flag_type=self.f_type.get() or None,
                active_only=self.f_active_var.get(),
            )
        except ValidationError as e:
            messagebox.showerror("Filter error", str(e))
            return
        names = _name_lookup()
        for f in rows:
            self.tree.insert("", "end", values=(
                f.flag_id, f.student_id, names.get(f.student_id, "?"),
                f.flag_type, f.start_date or "—", f.end_date or "—",
                "Active" if f.active else "Closed",
                (f.notes or "").replace("\n", " ⏎ "),
            ))
        self.count_var.set(f"{len(rows)} flag(s).")
        self._build_actions()

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        return int(self.tree.item(sel[0])["values"][0])

    def _new(self) -> None:
        FlagDialog(self.frame.winfo_toplevel(),
                    existing=None, on_save=self.refresh)

    def _edit_selected(self) -> None:
        fid = self._selected_id()
        if fid is None:
            messagebox.showinfo("Edit", "Select a flag first.")
            return
        existing = data.get_flag(fid)
        if existing is None:
            messagebox.showerror("Edit", f"No flag #{fid}")
            return
        FlagDialog(self.frame.winfo_toplevel(),
                    existing=existing, on_save=self.refresh)

    def _close_selected(self) -> None:
        fid = self._selected_id()
        if fid is None:
            messagebox.showinfo("Close", "Select a flag first.")
            return
        if not messagebox.askyesno("Close",
                                     f"Close flag #{fid} (today)?"):
            return
        try:
            data.close_flag(fid)
        except Exception as e:
            messagebox.showerror("Close failed", str(e))
            return
        self.refresh()

    def _reopen_selected(self) -> None:
        fid = self._selected_id()
        if fid is None:
            messagebox.showinfo("Re-open", "Select a flag first.")
            return
        if not messagebox.askyesno("Re-open", f"Re-open flag #{fid}?"):
            return
        try:
            data.reopen_flag(fid)
        except Exception as e:
            messagebox.showerror("Re-open failed", str(e))
            return
        self.refresh()

    def _delete_selected(self) -> None:
        fid = self._selected_id()
        if fid is None:
            messagebox.showinfo("Delete", "Select a flag first.")
            return
        if not messagebox.askyesno("Delete", f"Delete flag #{fid}?"):
            return
        try:
            data.delete_flag(fid)
        except Exception as e:
            messagebox.showerror("Delete failed", str(e))
            return
        self.refresh()


class FlagDialog:
    def __init__(self, parent: tk.Misc, *,
                 existing: Flag | None,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Edit Flag" if existing else "New Flag")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        self._build()

    def _build(self) -> None:
        form = ttk.Frame(self.win)
        form.pack(fill="both", expand=True, padx=12, pady=12)

        r = 0
        ttk.Label(form, text="Student:").grid(row=r, column=0,
                                                sticky="e", pady=4)
        if self.existing:
            self.student_cb = None
            self._student_id = self.existing.student_id
            names = _name_lookup()
            ttk.Label(form,
                       text=f"{self._student_id} — "
                            f"{names.get(self._student_id, '?')}"
                       ).grid(row=r, column=1, sticky="w", padx=6)
        else:
            cb, ids = _pick_student_combo(form)
            self.student_cb = cb
            self._student_ids = ids
            cb.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Flag type:").grid(row=r, column=0,
                                                   sticky="e", pady=4)
        self.type_cb = ttk.Combobox(form, values=FLAG_TYPES,
                                       state="readonly", width=28)
        self.type_cb.set(self.existing.flag_type
                           if self.existing else FLAG_TYPES[0])
        self.type_cb.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Start date:").grid(row=r, column=0,
                                                    sticky="e", pady=4)
        self.start_e = ttk.Entry(form, width=14)
        self.start_e.insert(0, (self.existing.start_date
                                  if self.existing
                                  else _today()) or "")
        self.start_e.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="End date (blank=active):").grid(
            row=r, column=0, sticky="e", pady=4)
        self.end_e = ttk.Entry(form, width=14)
        if self.existing and self.existing.end_date:
            self.end_e.insert(0, self.existing.end_date)
        self.end_e.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Notes:").grid(row=r, column=0,
                                              sticky="ne", pady=4)
        self.notes_text = tk.Text(form, width=60, height=6, wrap="word")
        if self.existing and self.existing.notes:
            self.notes_text.insert("1.0", self.existing.notes)
        self.notes_text.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        bar = ttk.Frame(form)
        bar.grid(row=r, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save", command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        if self.student_cb is not None:
            idx = self.student_cb.current()
            if idx < 0:
                messagebox.showerror("Validation", "Pick a student.")
                return
            sid = self._student_ids[idx]
        else:
            sid = self._student_id
        payload = {
            "student_id": sid,
            "flag_type":  self.type_cb.get(),
            "start_date": self.start_e.get().strip(),
            "end_date":   self.end_e.get().strip(),
            "notes":      self.notes_text.get("1.0", "end").strip(),
        }
        try:
            if self.existing:
                data.update_flag(self.existing.flag_id, payload)
            else:
                data.create_flag(payload)
        except ValidationError as e:
            messagebox.showerror("Validation", str(e))
            return
        except Exception as e:
            logger.exception("save flag failed")
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


# ══ Per-student tab ════════════════════════════════════════════════

class PerStudentTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Per-student")
        self._build()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=8)
        ttk.Label(bar, text="Student:").pack(side="left")
        self.cb, self._ids = _pick_student_combo(bar)
        self.cb.pack(side="left", padx=6)
        ttk.Button(bar, text="Load", command=self._load).pack(side="left",
                                                                 padx=4)
        ttk.Button(bar, text="Refresh",
                    command=self._refresh_students).pack(side="left", padx=4)

        self.summary_var = tk.StringVar(value="(select a student)")
        ttk.Label(self.frame, textvariable=self.summary_var,
                   justify="left", anchor="w",
                   font=("TkDefaultFont", 10)).pack(
            fill="x", padx=12, pady=(4, 8))

        nb_inner = ttk.Notebook(self.frame)
        nb_inner.pack(fill="both", expand=True, padx=8, pady=4)

        self._ci_frame = ttk.Frame(nb_inner)
        nb_inner.add(self._ci_frame, text="Check-ins")
        self._ses_frame = ttk.Frame(nb_inner)
        nb_inner.add(self._ses_frame, text="Sessions")
        self._flag_frame = ttk.Frame(nb_inner)
        nb_inner.add(self._flag_frame, text="Flags")

        self._ci_tree = self._make_tree(self._ci_frame,
                                          ("id", "date", "mood", "stress",
                                           "sleep", "by", "notes"),
                                          {"id": 60, "date": 100, "mood": 60,
                                           "stress": 60, "sleep": 60,
                                           "by": 130, "notes": 400})
        self._ses_tree = self._make_tree(self._ses_frame,
                                           ("id", "date", "type", "mins",
                                            "status", "provider", "follow"),
                                           {"id": 60, "date": 100,
                                            "type": 160, "mins": 60,
                                            "status": 100, "provider": 180,
                                            "follow": 100})
        self._flag_tree = self._make_tree(self._flag_frame,
                                            ("id", "type", "start", "end",
                                             "status", "notes"),
                                            {"id": 60, "type": 220,
                                             "start": 100, "end": 100,
                                             "status": 80, "notes": 400})

    def _make_tree(self, parent: tk.Misc, cols: tuple[str, ...],
                    widths: dict[str, int]) -> ttk.Treeview:
        wrap = ttk.Frame(parent)
        wrap.pack(fill="both", expand=True)
        tree = ttk.Treeview(wrap, columns=cols, show="headings")
        for c in cols:
            tree.heading(c, text=c.capitalize())
            tree.column(c, width=widths[c], anchor="w")
        vs = ttk.Scrollbar(wrap, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vs.set)
        tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        return tree

    def _refresh_students(self) -> None:
        opts = _student_options()
        self._ids = [sid for sid, _ in opts]
        self.cb["values"] = [lbl for _, lbl in opts]
        if self._ids:
            self.cb.current(0)

    def _load(self) -> None:
        idx = self.cb.current()
        if idx < 0:
            return
        sid = self._ids[idx]
        summ = data.per_student_summary(sid)
        s = student_data.get_student(sid)
        name = s.full_name if s else "?"
        active = ", ".join(summ.active_flags) if summ.active_flags else "—"
        latest = (f"{summ.latest_checkin_date}  (mood="
                  f"{summ.latest_mood if summ.latest_mood is not None else '—'}"
                  f" / stress="
                  f"{summ.latest_stress if summ.latest_stress is not None else '—'}"
                  f" / sleep="
                  f"{summ.latest_sleep if summ.latest_sleep is not None else '—'}"
                  f")") if summ.latest_checkin_date else "—"
        avg = (f"mood={summ.avg_mood if summ.avg_mood is not None else '—'}  "
               f"stress={summ.avg_stress if summ.avg_stress is not None else '—'}"
               f"  sleep="
               f"{summ.avg_sleep if summ.avg_sleep is not None else '—'}")
        self.summary_var.set(
            f"{sid} — {name}\n"
            f"  Check-ins: {summ.checkin_count}   "
            f"Sessions: {summ.session_count}   "
            f"Active flags: {active}\n"
            f"  Latest check-in: {latest}\n"
            f"  Averages: {avg}"
        )

        for tree in (self._ci_tree, self._ses_tree, self._flag_tree):
            for i in tree.get_children():
                tree.delete(i)
        for c in data.list_checkins(student_id=sid):
            self._ci_tree.insert("", "end", values=(
                c.checkin_id, c.checkin_date,
                "—" if c.mood_score is None else c.mood_score,
                "—" if c.stress_score is None else c.stress_score,
                "—" if c.sleep_score is None else c.sleep_score,
                c.recorded_by or "—",
                (c.notes or "").replace("\n", " ⏎ "),
            ))
        for s2 in data.list_sessions(student_id=sid):
            self._ses_tree.insert("", "end", values=(
                s2.session_id, s2.session_date, s2.session_type,
                s2.duration_minutes or "—", s2.status,
                s2.provider or "—", s2.follow_up_date or "—",
            ))
        for f in data.list_flags(student_id=sid):
            self._flag_tree.insert("", "end", values=(
                f.flag_id, f.flag_type, f.start_date or "—",
                f.end_date or "—", "Active" if f.active else "Closed",
                (f.notes or "").replace("\n", " ⏎ "),
            ))


# ══ Summary tab ════════════════════════════════════════════════════

class SummaryTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Summary")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=8)
        ttk.Label(bar, text="Upcoming window (days):").pack(side="left")
        self.window_e = ttk.Entry(bar, width=4)
        self.window_e.insert(0, "14")
        self.window_e.pack(side="left", padx=6)
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="left", padx=8)

        self.text = tk.Text(self.frame, wrap="word",
                              font=("TkFixedFont", 10), state="disabled")
        self.text.pack(fill="both", expand=True, padx=8, pady=(4, 8))

    def refresh(self) -> None:
        try:
            window = int(self.window_e.get().strip() or "14")
        except ValueError:
            messagebox.showerror("Summary", "Window must be a whole number.")
            return
        summ = data.summary(upcoming_window_days=window)
        lines: list[str] = []
        lines.append("Totals")
        lines.append("------")
        lines.append(f"  Check-ins        : {summ.total_checkins}")
        lines.append(f"  Sessions         : {summ.total_sessions}")
        lines.append(f"  Flags active     : {summ.active_flags}")
        lines.append(f"  Flags closed     : {summ.closed_flags}")
        lines.append("")
        lines.append("Alerts")
        lines.append("------")
        lines.append(f"  Low-mood check-ins         : "
                      f"{summ.low_mood_count}")
        lines.append(f"  High-stress check-ins      : "
                      f"{summ.high_stress_count}")
        lines.append(f"  Students with recent low mood: "
                      f"{summ.students_low_recent_mood}")
        lines.append(f"  Sessions scheduled in next {window}d: "
                      f"{summ.sessions_scheduled_upcoming}")
        lines.append(f"  Follow-ups due in next {window}d   : "
                      f"{summ.upcoming_follow_ups}")
        lines.append("")
        lines.append("Cohort reach")
        lines.append("------------")
        lines.append(f"  Students with active flag : "
                      f"{summ.students_with_flag}")
        lines.append(f"  Students with any session : "
                      f"{summ.students_with_session}")
        lines.append("")
        lines.append("Active flags by type")
        lines.append("--------------------")
        for t in FLAG_TYPES:
            n = summ.by_flag_type.get(t, 0)
            if n:
                lines.append(f"  {t:<30} : {n}")
        lines.append("")
        lines.append("Sessions by type")
        lines.append("----------------")
        for t in SESSION_TYPES:
            n = summ.by_session_type.get(t, 0)
            if n:
                lines.append(f"  {t:<30} : {n}")
        body = "\n".join(lines)
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", body)
        self.text.configure(state="disabled")
