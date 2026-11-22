"""Discovery and correction views: learners on roll without an
enrolment, learners with live enrolments in two years at once, and moving
an enrolment entered against the wrong learner."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk

from education_system.platform.delivery.gui.parented_dialogs import (
    messagebox,
    simpledialog,
)
from education_system.systems.sixth_form.domain.admissions.enrolments import enrolments as data
from education_system.systems.sixth_form.domain.admissions.enrolments.enrolments import (
    Enrolment,
)

from .enrolment_common import (
    _clear,
    _heading,
    _student_name_map,
    back_to_directory,
    show_error,
)
from .enrolment_pickers import choose_student, students_for_picker

logger = logging.getLogger(__name__)


# ── Transfer (feature 48) ───────────────────────────────────────────

def transfer_to(gui, enrolment_id: int, target: str, reason: str, *,
                confirm: bool = True):
    """Move the enrolment to ``target`` in one step
    (``transfer_enrolment``); shows the TransferResult."""
    e = data.get_enrolment(enrolment_id)
    if e is None:
        messagebox.showerror("Not found", f"No enrolment #{enrolment_id}",
                             parent=gui.root)
        return None
    names = _student_name_map()
    src = f"{e.student_id} {names.get(e.student_id, '')}".strip()
    dst = f"{target} {names.get(target, '')}".strip()
    if confirm and not messagebox.askyesno(
            "Confirm transfer",
            f"Move enrolment #{enrolment_id} ({e.academic_year}, Year "
            f"{e.year_group}) from\n\n  {src}\n\nto\n\n  {dst}?\n\nThe same "
            "record (id, history, withdrawal details) changes owner, and the "
            "learning aims that started in that year move with it.\n\n"
            f"Reason: {reason}", parent=gui.root):
        return None
    try:
        result = data.transfer_enrolment(enrolment_id, target, reason=reason)
    except Exception as exc:  # ValidationError / AccessDenied / DB
        show_error(gui.root, "Transfer failed", exc)
        return None
    messagebox.showinfo(
        "Transferred",
        f"Enrolment #{enrolment_id} now belongs to {dst}.\n"
        f"{result.aims_moved} learning aim(s) moved with it.", parent=gui.root)
    gui.status_var.set(f"Transferred #{enrolment_id} to {target}")
    back_to_directory(gui)
    return result


def open_transfer_enrolment(gui, enrolment_id: int) -> None:
    """Feature #48 — move an enrolment entered against the wrong learner
    to the right one."""
    e = data.get_enrolment(enrolment_id)
    if e is None:
        messagebox.showerror("Not found",
                             f"No enrolment #{enrolment_id}", parent=gui.root)
        return
    if e.is_archived:
        messagebox.showinfo("Archived", f"Enrolment #{enrolment_id} is "
                            "archived; restore it first.", parent=gui.root)
        return
    target = choose_student(
        gui.root, "Transfer enrolment",
        f"Move enrolment #{enrolment_id} ({e.student_id}, {e.academic_year}, "
        f"Year {e.year_group}) to:", exclude={e.student_id})
    if not target:
        return
    reason = simpledialog.askstring(
        "Transfer enrolment", "Reason (e.g. entered against the wrong "
        "learner):", parent=gui.root)
    if reason is None:
        return
    transfer_to(gui, enrolment_id, target, reason)


# ── Learners without an enrolment (feature 18) ──────────────────────

def students_without_enrolment(include_leavers: bool = False) -> list:
    enrolled = {e.student_id for e in data.list_enrolments()}
    return [s for s in students_for_picker(include_leavers)
            if s.student_id not in enrolled]


def _highlight_students_without_enrolment(gui, include_leavers: bool = False) -> None:
    """Feature #18 — students on the roll who have no enrolment record."""
    from .enrolment_views import open_enrolment_from_student_profile

    frame = _clear(gui)
    _heading(frame, "Students Without an Enrolment")
    leavers = tk.BooleanVar(value=include_leavers)
    top = ttk.Frame(frame)
    top.pack(anchor="w", pady=(0, 6))
    ttk.Checkbutton(top, text="Include leavers", variable=leavers,
                    command=lambda: _highlight_students_without_enrolment(
                        gui, bool(leavers.get()))).pack(side="left")
    try:
        missing = students_without_enrolment(include_leavers)
    except Exception as exc:  # noqa: BLE001 — shown
        ttk.Label(frame, text=f"Error: {exc}", foreground="#a33").pack(anchor="w")
        return
    ttk.Label(top, text=f"{len(missing)} student(s) "
              + ("" if include_leavers else "on roll ") + "have no enrolment.",
              foreground="#555").pack(side="left", padx=(12, 0))

    bar = ttk.Frame(frame)
    bar.pack(side="bottom", anchor="w", pady=(12, 0))
    tree = ttk.Treeview(frame, columns=("sid", "name", "status"),
                        show="headings", height=12)
    for col, text, w in (("sid", "Student ID", 110), ("name", "Name", 240),
                         ("status", "Status", 100)):
        tree.heading(col, text=text)
        tree.column(col, width=w)
    tree.pack(anchor="w", fill="both", expand=True)
    for s in missing:
        tree.insert("", "end", iid=s.student_id,
                    values=(s.student_id, s.full_name, s.status))

    def enrol_selected() -> None:
        sel = tree.selection()
        if sel:
            open_enrolment_from_student_profile(gui, sel[0])

    ttk.Button(bar, text="Enrol Selected", command=enrol_selected,
               state="normal" if data.can_write() else "disabled"
               ).pack(side="left", padx=(0, 6))
    ttk.Button(bar, text="Back to Directory",
               command=lambda: back_to_directory(gui)).pack(side="left")
    gui.status_var.set(f"{len(missing)} student(s) without enrolment")


# ── Live enrolments in two years (feature 19) ───────────────────────

def live_in_two_years() -> list[tuple[str, list[Enrolment]]]:
    """Learners with live (Enrolled / Pending) enrolments in more than one
    academic year — normally the old year should have been completed or
    withdrawn. (Two in the same year can't happen: the database keeps
    one enrolment per learner per year.)"""
    by_student: dict[str, list[Enrolment]] = {}
    for e in data.list_enrolments():
        if e.is_live:
            by_student.setdefault(e.student_id, []).append(e)
    return sorted(((sid, sorted(rows, key=lambda r: r.academic_year))
                   for sid, rows in by_student.items()
                   if len({r.academic_year for r in rows}) > 1))


def _highlight_duplicate_conflicts(gui) -> None:
    """Feature #19 — learners with live enrolments in two years at once."""
    from .enrolment_views import open_profile

    frame = _clear(gui)
    _heading(frame, "Enrolment Conflicts — live in two years")
    try:
        found = live_in_two_years()
    except Exception as exc:  # noqa: BLE001 — shown
        ttk.Label(frame, text=f"Error: {exc}", foreground="#a33").pack(anchor="w")
        return
    bar = ttk.Frame(frame)
    bar.pack(side="bottom", anchor="w", pady=(12, 0))
    if not found:
        ttk.Label(frame, text="No conflicts — no learner has live (Enrolled or "
                  "Pending) enrolments in more than one academic year.",
                  foreground="#2a7d2a").pack(anchor="w", pady=(8, 0))
    else:
        names = _student_name_map()
        ttk.Label(frame, foreground="#a33", wraplength=900, justify="left", text=(
            f"{len(found)} learner(s) have live enrolments in more than one "
            "year. Complete or withdraw the old year (or reopen the rollover "
            "that missed them).")).pack(anchor="w", pady=(0, 6))
        tree = ttk.Treeview(frame, columns=("id", "sid", "name", "year", "yg",
                                            "status"),
                            show="headings", height=14)
        for col, (text, w) in {
            "id": ("#", 50), "sid": ("Student", 100), "name": ("Name", 200),
            "year": ("Year", 90), "yg": ("YG", 50), "status": ("Status", 100),
        }.items():
            tree.heading(col, text=text)
            tree.column(col, width=w)
        tree.pack(anchor="w", fill="both", expand=True)
        for sid, rows in found:
            for e in rows:
                tree.insert("", "end", iid=str(e.enrolment_id), values=(
                    e.enrolment_id, sid, names.get(sid, "—"), e.academic_year,
                    e.year_group, e.status))
        ttk.Button(bar, text="Open Selected",
                   command=lambda: tree.selection() and open_profile(
                       gui, int(tree.selection()[0]))
                   ).pack(side="left", padx=(0, 6))
    ttk.Button(bar, text="Back to Directory",
               command=lambda: back_to_directory(gui)).pack(side="left")
    gui.status_var.set(f"{len(found)} conflict(s)")

