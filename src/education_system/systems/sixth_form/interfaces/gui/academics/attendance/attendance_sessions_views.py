"""GUI tab for expected sessions and AM/PM statutory marks.

One panel with three inner tabs, mounted on the Attendance screen:

* **Coverage** — expected lessons against marks that exist, and the list
  of registers nobody filled in.
* **True %** — a learner's attendance measured against their timetable
  rather than against the marks that happen to exist, shown next to the
  old figure so the gap is visible.
* **AM/PM** — the statutory session marks, and the roll-up that derives
  them from lesson marks.
"""

from __future__ import annotations

import logging
import tkinter as tk
from datetime import date as _date, timedelta as _timedelta
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import messagebox, simpledialog

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance_sessions as sessions,
)
from education_system.systems.sixth_form.domain.academics.attendance.attendance import (
    ValidationError,
)
from education_system.systems.sixth_form.domain.academics.class_groups import (
    class_groups as cg_data,
)
from education_system.systems.sixth_form.domain.academics.courses import (
    courses as course_data,
)
from education_system.systems.sixth_form.domain.academics.timetable.timetable import (
    day_name,
)

logger = logging.getLogger(__name__)

_WINDOW_DAYS: int = 14


def _today() -> str:
    return _date.today().isoformat()


def _window_start() -> str:
    return (_date.today() - _timedelta(days=_WINDOW_DAYS)).isoformat()


def _actor(gui) -> str | None:
    auth = getattr(gui, "auth", None)
    return ((getattr(auth, "current_user", None) or {}).get("username")
            if auth else None)


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value:.1f}%"


def _group_choices() -> tuple[list[str], dict[str, int]]:
    groups = cg_data.list_groups()
    courses = {c.course_id: c for c in course_data.list_courses()}
    labels = [
        f"#{g.group_id} {g.group_name} "
        f"({courses[g.course_id].course_code if g.course_id in courses else '?'})"
        for g in groups
    ]
    return labels, {label: g.group_id for label, g in zip(labels, groups)}


def _date_bar(parent) -> tuple[ttk.Frame, tk.StringVar, tk.StringVar]:
    bar = ttk.Frame(parent)
    bar.pack(anchor="w", fill="x", pady=(0, 8))
    from_var = tk.StringVar(value=_window_start())
    to_var = tk.StringVar(value=_today())
    ttk.Label(bar, text="From:").pack(side="left")
    ttk.Entry(bar, textvariable=from_var, width=12).pack(
        side="left", padx=(4, 12))
    ttk.Label(bar, text="To:").pack(side="left")
    ttk.Entry(bar, textvariable=to_var, width=12).pack(
        side="left", padx=(4, 12))
    return bar, from_var, to_var


def _tree(parent, columns: list[tuple[str, str, int]],
          height: int = 12) -> ttk.Treeview:
    holder = ttk.Frame(parent)
    holder.pack(fill="both", expand=True)
    tree = ttk.Treeview(holder, columns=[c[0] for c in columns],
                        show="headings", height=height)
    for key, text, width in columns:
        tree.heading(key, text=text)
        tree.column(key, width=width, anchor="w")
    scroll = ttk.Scrollbar(holder, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    tree.pack(side="left", fill="both", expand=True)
    scroll.pack(side="right", fill="y")
    return tree


# ── Entry point ─────────────────────────────────────────────────────

def build_sessions_tab(gui, parent: ttk.Frame) -> None:
    inner = ttk.Notebook(parent)
    inner.pack(fill="both", expand=True)
    coverage = ttk.Frame(inner, padding=8)
    true_pct = ttk.Frame(inner, padding=8)
    ampm = ttk.Frame(inner, padding=8)
    inner.add(coverage, text="Coverage")
    inner.add(true_pct, text="True %")
    inner.add(ampm, text="AM / PM")
    _build_coverage(gui, coverage)
    _build_true(gui, true_pct)
    _build_ampm(gui, ampm)


# ── Coverage ────────────────────────────────────────────────────────

def _build_coverage(gui, parent: ttk.Frame) -> None:
    bar, from_var, to_var = _date_bar(parent)
    group_labels, group_by_label = _group_choices()
    group_var = tk.StringVar(value="(all)")
    ttk.Label(bar, text="Group:").pack(side="left")
    ttk.Combobox(bar, textvariable=group_var,
                 values=["(all)", *group_labels], state="readonly",
                 width=30).pack(side="left", padx=(4, 8))

    ttk.Label(
        parent,
        text=("Expected lessons come from the timetable, not from the "
              "marks. A register nobody filled in contributes to neither "
              "side of the usual fraction, so a group whose Friday "
              "registers are never taken reads as 100% — these are those "
              "lessons."),
        foreground="#666", wraplength=780, justify="left",
    ).pack(anchor="w", pady=(0, 6))

    tree = _tree(parent, [
        ("date", "Date", 100),
        ("day", "Day", 60),
        ("period", "Period", 70),
        ("slot", "Slot", 60),
        ("session", "Session", 80),
        ("missing", "Unmarked", 90),
        ("names", "Learners", 380),
    ])
    summary = ttk.Label(parent, text="", foreground="#555")
    summary.pack(anchor="w", pady=(6, 0))

    def refresh() -> None:
        tree.delete(*tree.get_children())
        group_id = group_by_label.get(group_var.get())
        try:
            missing = sessions.missing_marks(
                group_id=group_id,
                date_from=from_var.get().strip(),
                date_to=to_var.get().strip())
            cover = sessions.coverage(
                group_id=group_id,
                date_from=from_var.get().strip(),
                date_to=to_var.get().strip())
        except ValidationError as e:
            summary.config(text=str(e), foreground="#a33")
            return

        grouped: dict[tuple[str, int], list] = {}
        for gap in missing:
            grouped.setdefault(
                (gap.lesson.date, gap.lesson.slot_id), []).append(gap)
        for (date_s, slot_id), gaps in sorted(grouped.items()):
            lesson = gaps[0].lesson
            names = ", ".join(g.student_name for g in gaps[:6])
            if len(gaps) > 6:
                names += f" … (+{len(gaps) - 6})"
            tree.insert("", "end", values=(
                date_s, day_name(lesson.day), lesson.period, slot_id,
                lesson.session, len(gaps), names))
        summary.config(
            text=(f"Coverage {cover.recorded}/{cover.expected} "
                  f"({_pct(cover.percentage)}) · {cover.missing} mark(s) "
                  f"missing across {len(grouped)} lesson(s)"),
            foreground="#a33" if cover.missing else "#2a2")

    ttk.Button(bar, text="Show", command=refresh).pack(side="left")
    refresh()


# ── True percentage ─────────────────────────────────────────────────

def _build_true(gui, parent: ttk.Frame) -> None:
    bar, from_var, to_var = _date_bar(parent)
    student_var = tk.StringVar(value="")
    ttk.Label(bar, text="Student ID:").pack(side="left")
    ttk.Entry(bar, textvariable=student_var, width=14).pack(
        side="left", padx=(4, 12))

    ttk.Label(
        parent,
        text=("Two percentages for the same learner. 'Against timetable' "
              "divides by what was scheduled; 'against marks only' "
              "divides by the rows that exist. A wide gap between them is "
              "a register-taking problem, not an attendance problem."),
        foreground="#666", wraplength=780, justify="left",
    ).pack(anchor="w", pady=(0, 8))

    body = ttk.Frame(parent)
    body.pack(anchor="w", fill="x")
    fields: dict[str, ttk.Label] = {}
    rows = [
        ("expected", "Expected lessons"),
        ("recorded", "Marked"),
        ("unrecorded", "Never marked"),
        ("present", "Present"),
        ("approved", "Approved (off site)"),
        ("authorised", "Authorised absence"),
        ("unauthorised", "Unauthorised absence"),
        ("not_counted", "Not counted"),
        ("pct", "Against timetable"),
        ("pct_old", "Against marks only"),
        ("pct_unauth", "Unauthorised rate"),
    ]
    for i, (key, label) in enumerate(rows):
        ttk.Label(body, text=label + ":").grid(
            row=i, column=0, sticky="w", pady=1)
        value = ttk.Label(body, text="—", font=("", 10, "bold"))
        value.grid(row=i, column=1, sticky="w", padx=(16, 0))
        fields[key] = value

    note = ttk.Label(parent, text="", foreground="#a33", wraplength=760,
                     justify="left")
    note.pack(anchor="w", pady=(10, 0))

    def refresh() -> None:
        student_id = student_var.get().strip()
        if not student_id:
            note.config(text="Enter a student ID.")
            return
        try:
            summary = sessions.true_summary(
                student_id,
                date_from=from_var.get().strip(),
                date_to=to_var.get().strip())
        except ValidationError as e:
            note.config(text=str(e))
            return
        fields["expected"].config(text=str(summary.expected))
        fields["recorded"].config(text=str(summary.recorded))
        fields["unrecorded"].config(text=str(summary.unrecorded))
        fields["present"].config(text=str(summary.present))
        fields["approved"].config(text=str(summary.approved))
        fields["authorised"].config(text=str(summary.authorised))
        fields["unauthorised"].config(text=str(summary.unauthorised))
        fields["not_counted"].config(text=str(summary.not_counted))
        fields["pct"].config(text=_pct(summary.percentage))
        fields["pct_old"].config(text=_pct(summary.recorded_percentage))
        fields["pct_unauth"].config(
            text=_pct(summary.unauthorised_percentage))
        note.config(
            text=(f"{summary.unrecorded} lesson(s) were never marked — the "
                  f"gap between the two percentages is that, not a change "
                  f"in behaviour." if summary.unrecorded else ""))

    ttk.Button(bar, text="Show", command=refresh).pack(side="left")


# ── AM / PM sessions ────────────────────────────────────────────────

def _build_ampm(gui, parent: ttk.Frame) -> None:
    bar, from_var, to_var = _date_bar(parent)
    student_var = tk.StringVar(value="")
    ttk.Label(bar, text="Student:").pack(side="left")
    ttk.Entry(bar, textvariable=student_var, width=14).pack(
        side="left", padx=(4, 12))

    ttk.Label(
        parent,
        text=("Statutory attendance is counted in two sessions a day, not "
              "in periods. The roll-up collapses each day's lesson marks "
              "into an AM and a PM mark, taking the most favourable "
              "meaning in each half — in the room for any of it means "
              "present for the session. Marks a human typed are left "
              "alone."),
        foreground="#666", wraplength=780, justify="left",
    ).pack(anchor="w", pady=(0, 6))

    tree = _tree(parent, [
        ("date", "Date", 100),
        ("student", "Student", 130),
        ("session", "Session", 80),
        ("code", "Code", 60),
        ("status", "Status", 110),
        ("source", "Source", 90),
        ("notes", "Notes", 300),
    ])
    summary = ttk.Label(parent, text="", foreground="#555")
    summary.pack(anchor="w", pady=(6, 4))
    actions = ttk.Frame(parent)
    actions.pack(anchor="w")

    def refresh() -> None:
        tree.delete(*tree.get_children())
        try:
            marks = sessions.list_session_marks(
                student_id=student_var.get().strip() or None,
                date_from=from_var.get().strip() or None,
                date_to=to_var.get().strip() or None)
        except ValidationError as e:
            summary.config(text=str(e), foreground="#a33")
            return
        for mark in marks:
            tree.insert("", "end", values=(
                mark.date, mark.student_id, mark.session, mark.code,
                mark.status, "derived" if mark.derived else "manual",
                mark.notes or ""))
        derived = sum(1 for m in marks if m.derived)
        text = f"{len(marks)} session mark(s), {derived} derived"
        alert = False
        student_id = student_var.get().strip()
        if student_id:
            stats = sessions.session_summary(
                student_id,
                date_from=from_var.get().strip() or None,
                date_to=to_var.get().strip() or None)
            text += (f" · attendance {_pct(stats.percentage)} over "
                     f"{stats.possible} possible session(s)")
            if stats.persistently_absent:
                text += " · persistently absent (<90%)"
                alert = True
        summary.config(text=text, foreground="#a33" if alert else "#555")

    def roll_up() -> None:
        if not messagebox.askyesno(
                "Roll up sessions",
                "Derive AM/PM marks from the lesson marks in this "
                "window?\n\nExisting derived marks are rewritten; marks "
                "somebody typed by hand are left alone.",
                parent=gui.root):
            return
        try:
            written = sessions.roll_up_range(
                date_from=from_var.get().strip(),
                date_to=to_var.get().strip(),
                student_id=student_var.get().strip() or None,
                recorded_by=_actor(gui))
        except ValidationError as e:
            messagebox.showerror("Could not roll up", str(e), parent=gui.root)
            return
        messagebox.showinfo("Roll-up complete",
                            f"Wrote {written} session mark(s).",
                            parent=gui.root)
        refresh()

    def add() -> None:
        student_id = (student_var.get().strip() or simpledialog.askstring(
            "Session mark", "Student ID:", parent=gui.root))
        if not student_id:
            return
        date_s = simpledialog.askstring(
            "Session mark", "Date (YYYY-MM-DD):", initialvalue=_today(),
            parent=gui.root)
        session = simpledialog.askstring(
            "Session mark", "Session (AM or PM):", initialvalue="AM",
            parent=gui.root)
        code = simpledialog.askstring(
            "Session mark", "Mark code (e.g. / \\ I M O N):",
            parent=gui.root)
        if not (date_s and session and code):
            return
        try:
            sessions.mark_session(student_id, date_s, session, code,
                                  recorded_by=_actor(gui))
        except ValidationError as e:
            messagebox.showerror("Invalid session mark", str(e),
                                 parent=gui.root)
            return
        refresh()

    ttk.Button(bar, text="Show", command=refresh).pack(side="left")
    ttk.Button(actions, text="Roll up from lessons", command=roll_up).pack(
        side="left", padx=(0, 6))
    ttk.Button(actions, text="Add session mark", command=add).pack(
        side="left", padx=(0, 6))
    ttk.Button(actions, text="Refresh", command=refresh).pack(side="left")
    refresh()
