"""Pickers shared by the enrolment screens: real tutor groups for a year
group, and on-roll learners (with an "include leavers" option)."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk

from education_system.platform.delivery.gui.parented_dialogs import make_toplevel
from education_system.systems.sixth_form.domain.learners.students import students as student_data

logger = logging.getLogger(__name__)


# ── Tutor groups ────────────────────────────────────────────────────

def _tutor_groups_module():
    from education_system.systems.sixth_form.domain.pastoral.tutor_groups import (
        tutor_groups,
    )
    return tutor_groups


def tutor_group_names(year_group: int | None) -> tuple[bool, list[str]]:
    """(any tutor groups set up at all, names of those for ``year_group``).

    Once any group exists the domain only accepts real groups of the right
    year, so the picker is a fixed list; before that it is free text."""
    try:
        tg = _tutor_groups_module()
        any_groups = bool(tg.list_groups())
        if not any_groups:
            return False, []
        groups = tg.list_groups(year_group=year_group) if year_group else tg.list_groups()
        return True, sorted(g.name for g in groups)
    except Exception:  # noqa: BLE001 — fall back to free text
        logger.exception("Tutor groups not read")
        return False, []


class TutorGroupPicker(ttk.Combobox):
    """Combobox over the real tutor groups of a year group (blank = none);
    free text only while no tutor groups exist."""

    def __init__(self, master, textvariable: tk.StringVar,
                 year_group: int | None = None, **kw) -> None:
        super().__init__(master, textvariable=textvariable, width=kw.pop("width", 16), **kw)
        self.free_text = True
        self.set_year_group(year_group)

    def set_year_group(self, year_group: int | None) -> None:
        exist, names = tutor_group_names(year_group)
        self.free_text = not exist
        if exist:
            self.configure(values=["", *names], state="readonly")
            if self.get() and self.get() not in names:
                # Keep a stored value visible so it can be corrected.
                self.configure(values=["", self.get(), *names])
        else:
            self.configure(values=[], state="normal")


# ── Learners ────────────────────────────────────────────────────────

def students_for_picker(include_leavers: bool = False) -> list:
    """Students on roll (``students.ON_ROLL_STATUSES``), or everyone."""
    try:
        rows = student_data.list_students()
    except Exception:  # noqa: BLE001 — empty picker, logged
        logger.exception("Student list not read")
        return []
    if include_leavers:
        return rows
    return [s for s in rows if s.status in student_data.ON_ROLL_STATUSES]


def student_label(s) -> str:
    tag = "" if s.status in student_data.ON_ROLL_STATUSES else f" [{s.status}]"
    return f"{s.student_id} — {s.full_name}{tag}"


class StudentPicker(ttk.Frame):
    """Combobox of learners with an optional "Include leavers" toggle."""

    def __init__(self, master, *, exclude: set[str] | None = None,
                 leavers_toggle: bool = True, preselect: str | None = None,
                 width: int = 46) -> None:
        super().__init__(master)
        self.exclude = exclude or set()
        self.var = tk.StringVar()
        self.leavers = tk.BooleanVar(value=False)
        self.lookup: dict[str, str] = {}
        self.combo = ttk.Combobox(self, textvariable=self.var, state="readonly",
                                  width=width)
        self.combo.pack(side="left")
        if leavers_toggle:
            ttk.Checkbutton(self, text="Include leavers", variable=self.leavers,
                            command=self.reload).pack(side="left", padx=(8, 0))
        self.reload()
        if preselect:
            self.select(preselect)

    def reload(self) -> None:
        rows = [s for s in students_for_picker(bool(self.leavers.get()))
                if s.student_id not in self.exclude]
        self.lookup = {student_label(s): s.student_id for s in rows}
        self.combo.configure(values=list(self.lookup))
        if self.var.get() not in self.lookup:
            self.var.set("")

    def select(self, student_id: str) -> bool:
        for label, sid in self.lookup.items():
            if sid == student_id:
                self.var.set(label)
                return True
        return False

    def get(self) -> str | None:
        return self.lookup.get(self.var.get())

    @property
    def count(self) -> int:
        return len(self.lookup)


def choose_student(root, title: str, prompt: str, *,
                   exclude: set[str] | None = None) -> str | None:
    """Modal learner picker (on roll, "Include leavers" to widen)."""
    dlg = make_toplevel(root)
    dlg.title(title)
    dlg.grab_set()
    ttk.Label(dlg, text=prompt, wraplength=520, justify="left").pack(
        anchor="w", padx=12, pady=(12, 6))
    picker = StudentPicker(dlg, exclude=exclude)
    picker.pack(anchor="w", padx=12)
    result: dict[str, str | None] = {"sid": None}

    def ok() -> None:
        result["sid"] = picker.get()
        if result["sid"]:
            dlg.destroy()

    bar = ttk.Frame(dlg)
    bar.pack(anchor="e", padx=12, pady=12)
    ttk.Button(bar, text="OK", command=ok).pack(side="left", padx=(0, 6))
    ttk.Button(bar, text="Cancel", command=dlg.destroy).pack(side="left")
    dlg.bind("<Escape>", lambda _e: dlg.destroy())
    dlg.wait_window()
    return result["sid"]
