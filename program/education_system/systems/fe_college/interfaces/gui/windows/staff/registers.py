"""Taking a register.

Built for speed, because a register is taken with thirty people waiting: the
whole class defaults to present, keyboard shortcuts set a mark on the selected
row, and one button saves the lot. Each learner's running attendance rate is
shown alongside, which is what turns a register into a moment of intervention
rather than a data-entry chore.
"""

from __future__ import annotations

import logging
import tkinter as tk
from datetime import date
from tkinter import ttk

from education_system.systems.fe_college.config import ATTENDANCE_MARKS
from education_system.systems.fe_college.domain.students.attendance import MARK_LABELS
from education_system.systems.fe_college.domain.students.models import ValidationError
from education_system.systems.fe_college.interfaces.gui import widgets as w

logger = logging.getLogger(__name__)

TITLE = "Registers"

# Keyboard shortcut -> mark. Chosen so a lecturer can run down the list with
# one hand: p/l/a/u/e.
SHORTCUTS = {
    "p": "present",
    "l": "late",
    "a": "authorised",
    "u": "unauthorised",
    "e": "excused",
}


def open_window(host) -> None:
    Screen(host)


class Screen:
    def __init__(self, host):
        self.host = host
        self.ctl = host.ctl
        self.register = None
        host.clear_content()
        parent = host.content_frame

        w.page_header(
            parent, TITLE,
            "Everyone starts as present — mark the exceptions and save. "
            "Keys: P present · L late · A authorised · U unauthorised · E excused.",
        )

        courses = self.ctl.my_courses()
        if not courses:
            w.empty_state(
                parent,
                "You are not assigned to any courses, so there is no register "
                "to take. Ask an administrator to make you a course leader or "
                "class-group teacher.",
            )
            return

        bar = ttk.Frame(parent)
        bar.pack(fill="x", pady=(0, 8))

        ttk.Label(bar, text="Course:").pack(side="left")
        self.course_var = tk.StringVar()
        self.course_combo = ttk.Combobox(
            bar, textvariable=self.course_var, state="readonly", width=40,
            values=[f"{c.course_id} — {c.title}" for c in courses],
        )
        self.course_combo.current(0)
        self.course_combo.pack(side="left", padx=(4, 12))
        self.course_combo.bind("<<ComboboxSelected>>", lambda _e: self.load())

        ttk.Label(bar, text="Date:").pack(side="left")
        self.date_var = tk.StringVar(value=date.today().isoformat())
        date_entry = ttk.Entry(bar, textvariable=self.date_var, width=12)
        date_entry.pack(side="left", padx=(4, 12))
        date_entry.bind("<Return>", lambda _e: self.load())

        ttk.Label(bar, text="Period:").pack(side="left")
        self.period_var = tk.StringVar()
        period_combo = ttk.Combobox(
            bar, textvariable=self.period_var, state="readonly", width=8,
            values=["", *self.ctl.timetable.period_codes()],
        )
        period_combo.current(0)
        period_combo.pack(side="left", padx=(4, 12))
        period_combo.bind("<<ComboboxSelected>>", lambda _e: self.load())

        ttk.Button(bar, text="Load register", command=self.load).pack(side="left")

        self.state_var = tk.StringVar()
        ttk.Label(bar, textvariable=self.state_var,
                  foreground=w.TONE["muted"]).pack(side="right")

        self.table = w.DataTable(parent, [
            ("id", "ID", 90),
            ("name", "Name", 200),
            ("mark", "Mark", 170),
            ("late", "Mins late", 80, "e"),
            ("rate", "Their attendance", 120, "e"),
            ("note", "Note", 220),
        ], height=18, on_double_click=lambda _r: self.cycle_mark())

        w.button_bar(parent, [
            ("Present", lambda: self.set_mark("present")),
            ("Late", lambda: self.set_mark("late")),
            ("Authorised", lambda: self.set_mark("authorised")),
            ("Unauthorised", lambda: self.set_mark("unauthorised")),
            ("Excused", lambda: self.set_mark("excused")),
            ("Add a note", self.add_note),
        ])
        w.button_bar(parent, [
            ("Save register", self.save),
            ("Mark everyone present", lambda: self.set_all("present")),
        ])

        for key, mark in SHORTCUTS.items():
            self.table.tree.bind(
                f"<KeyPress-{key}>", lambda _e, m=mark: self.set_mark(m)
            )
        self.load()

    # ── Data ───────────────────────────────────────────────────────────────

    @property
    def course_id(self) -> str:
        return self.course_var.get().split(" — ")[0]

    def load(self) -> None:
        try:
            on = date.fromisoformat(self.date_var.get().strip())
        except ValueError:
            w.error(self.host, TITLE, "Enter the date as YYYY-MM-DD.")
            return
        if on > date.today():
            w.error(self.host, TITLE, "A register cannot be taken for a future date.")
            return

        try:
            self.register = self.ctl.attendance.build_register(
                self.course_id, on, self.period_var.get()
            )
        except ValidationError as exc:
            w.error(self.host, TITLE, str(exc))
            return
        except Exception as exc:
            logger.exception("Could not build the FE College register")
            w.error(self.host, TITLE, f"Could not load the register: {exc}")
            return

        self.state_var.set(
            "Already taken — showing what was recorded"
            if self.register.already_taken else "New register"
        )
        self._render()

    def _render(self) -> None:
        if self.register is None:
            return
        self.table.set_rows([
            {
                "id": row.student.student_id,
                "name": row.student.full_name,
                "mark": MARK_LABELS.get(row.mark, row.mark),
                "late": row.minutes_late or "",
                "rate": w.pct(row.attendance_pct),
                "note": row.note,
                "_tone": (
                    "good" if row.mark == "present"
                    else "warn" if row.mark in ("late", "authorised", "excused")
                    else "bad"
                ),
                "_obj": row,
            }
            for row in self.register.rows
        ])
        present = self.register.present_count
        total = len(self.register.rows)
        self.host.set_status(
            f"{self.register.course_title} · {self.register.session_date} "
            f"{self.register.period or ''} — {present}/{total} attending".rstrip()
        )

    # ── Marking ────────────────────────────────────────────────────────────

    def set_mark(self, mark: str) -> None:
        row = self.table.selection()
        if row is None:
            w.info(self.host, TITLE, "Select a learner first.")
            return
        row.mark = mark
        if mark != "late":
            row.minutes_late = 0
        elif not row.minutes_late:
            row.minutes_late = 5
        self._render_keeping_position()

    def cycle_mark(self) -> None:
        """Double-click steps through the marks — quicker than the buttons."""
        row = self.table.selection()
        if row is None:
            return
        order = list(ATTENDANCE_MARKS)
        row.mark = order[(order.index(row.mark) + 1) % len(order)]
        if row.mark != "late":
            row.minutes_late = 0
        self._render_keeping_position()

    def set_all(self, mark: str) -> None:
        if self.register is None:
            return
        for row in self.register.rows:
            row.mark = mark
            row.minutes_late = 0
        self._render()

    def add_note(self) -> None:
        row = self.table.selection()
        if row is None:
            w.info(self.host, TITLE, "Select a learner first.")
            return
        result = w.ask(self.host, f"Note — {row.student.full_name}", [
            ("note", "Note", "text"),
            ("minutes_late", "Minutes late", "int"),
        ], initial={"note": row.note, "minutes_late": row.minutes_late})
        if result is None:
            return
        row.note = result["note"]
        if row.mark == "late":
            row.minutes_late = result["minutes_late"]
        self._render_keeping_position()

    def _render_keeping_position(self) -> None:
        """Re-render but keep the selection where it was.

        Without this, marking a learner jumps the selection back to the top and
        taking a register of thirty becomes thirty scrolls.
        """
        items = self.table.tree.selection()
        index = self.table.tree.index(items[0]) if items else None
        self._render()
        children = self.table.tree.get_children()
        if index is not None and children:
            target = children[min(index, len(children) - 1)]
            self.table.tree.selection_set(target)
            self.table.tree.focus(target)
            self.table.tree.see(target)
        self.table.tree.focus_set()

    def save(self) -> None:
        if self.register is None:
            return
        try:
            written = self.ctl.attendance.save_register(
                self.register, recorded_by=self.ctl.staff_id
            )
        except ValidationError as exc:
            w.error(self.host, "Save register", str(exc))
            return
        except Exception as exc:
            logger.exception("Could not save the FE College register")
            w.error(self.host, "Save register", f"Could not save: {exc}")
            return
        self.state_var.set("Saved")
        self.host.set_status(
            f"Saved {written} mark(s) for {self.register.course_id} "
            f"on {self.register.session_date}"
        )
        self.load()


__all__ = ["SHORTCUTS", "TITLE", "Screen", "open_window"]
