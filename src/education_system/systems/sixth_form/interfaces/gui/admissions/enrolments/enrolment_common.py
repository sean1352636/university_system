"""Shared helpers for the enrolment screens (directory, cohort tools,
reports, record actions)."""

from __future__ import annotations

import logging
import tkinter as tk
from dataclasses import dataclass
from datetime import date
from tkinter import ttk
from typing import Any, Callable

from education_system.platform.delivery.gui.parented_dialogs import (
    make_toplevel,
    messagebox,
)
from education_system.systems.sixth_form.domain.admissions.enrolments import enrolments as data
from education_system.systems.sixth_form.domain.admissions.enrolments.enrolments import (
    Enrolment,
    STATUSES,
)
from education_system.systems.sixth_form.domain.learners.students import students as student_data

logger = logging.getLogger(__name__)


def back_to_directory(gui) -> None:
    """Return to the enrolment directory (imported late: the directory
    module imports this one)."""
    from .enrolment_views import open_directory
    open_directory(gui)


def _clear(gui) -> ttk.Frame:
    for w in gui.content_frame.winfo_children():
        w.destroy()
    return gui.content_frame


def _heading(parent, text: str) -> None:
    ttk.Label(parent, text=text, font=("", 16, "bold")).pack(
        anchor="w", pady=(0, 8))


def _default_academic_year() -> str:
    """The current academic year: the academic year register's current
    year, else the year today falls in (1 August boundary)."""
    try:
        return data.current_academic_year()
    except Exception:  # noqa: BLE001 — register unreadable: date rule
        logger.exception("Current academic year not read")
        today = date.today()
        start = today.year if today.month >= 8 else today.year - 1
        return f"{start}/{str(start + 1)[-2:]}"


def _next_academic_year(academic_year: str) -> str:
    """'2025/26' -> '2026/27'. Falls back to the year after the current
    one if the input isn't in the expected ``YYYY/YY`` form."""
    try:
        return data.next_academic_year((academic_year or "").strip())
    except ValueError:
        return data.next_academic_year(_default_academic_year())


def _year_choices(*extra: str) -> list[str]:
    """Academic years for pickers: the register's and those in use
    (``known_academic_years``), plus any ``extra``, newest first."""
    try:
        years = set(data.known_academic_years())
    except Exception:  # noqa: BLE001 — still offer the current year
        logger.exception("Known academic years not read")
        years = {_default_academic_year()}
    years |= {y for y in extra if y}
    return sorted(years, reverse=True)


def describe_error(exc: BaseException) -> str:
    """The message to show for a failed action: access refusals and
    validation messages as they are, anything else marked unexpected."""
    if isinstance(exc, PermissionError):     # access.AccessDenied
        return f"You are not allowed to do this.\n\n{exc}"
    if isinstance(exc, ValueError):          # every ValidationError
        return str(exc)
    return f"Unexpected error: {exc}"


def show_error(parent, title: str, exc: BaseException) -> None:
    if not isinstance(exc, (PermissionError, ValueError)):
        logger.error("%s failed", title, exc_info=exc)
    messagebox.showerror(title, describe_error(exc), parent=parent)


def _enrolment_to_payload(e: Enrolment, **overrides: Any) -> dict[str, Any]:
    """Build an ``update_enrolment`` payload from an existing record, with
    optional field overrides. ``student_id`` is immutable so it's omitted."""
    payload: dict[str, Any] = {
        "academic_year": e.academic_year,
        "year_group": e.year_group,
        "tutor_group": e.tutor_group,
        "start_date": e.start_date,
        "status": e.status,
        "notes": e.notes,
    }
    payload.update(overrides)
    return payload


def _report_bulk(gui, title: str, ok: list[str], fail: list[str],
                 notes: list[str] | None = None) -> None:
    """Summarise a bulk operation's outcome (with any per-row ``notes``,
    e.g. aims ended), then return to the directory."""
    lines = [f"{len(ok)} succeeded, {len(fail)} failed."]
    if fail:
        lines.append("")
        lines.extend(fail[:15])
        if len(fail) > 15:
            lines.append(f"…and {len(fail) - 15} more.")
    if notes:
        lines += ["", *notes[:25]]
        if len(notes) > 25:
            lines.append(f"…and {len(notes) - 25} more.")
    show = messagebox.showinfo if not fail else messagebox.showwarning
    show(title, "\n".join(lines), parent=gui.root)
    gui.status_var.set(f"{title}: {len(ok)} ok, {len(fail)} failed")
    back_to_directory(gui)


def _choose_from(gui, title: str, prompt: str,
                 options: list[str], default: str | None = None) -> str | None:
    """Modal combobox picker. Returns the chosen value, or None if cancelled."""
    dlg = make_toplevel(gui.root)
    dlg.title(title)
    dlg.transient(gui.root)
    dlg.grab_set()
    ttk.Label(dlg, text=prompt).pack(anchor="w", padx=12, pady=(12, 6))
    var = tk.StringVar(value=default or (options[0] if options else ""))
    ttk.Combobox(dlg, textvariable=var, values=options,
                 state="readonly", width=24).pack(padx=12)
    result: dict[str, str | None] = {"val": None}

    def ok() -> None:
        result["val"] = var.get()
        dlg.destroy()

    bar = ttk.Frame(dlg)
    bar.pack(anchor="e", padx=12, pady=12)
    ttk.Button(bar, text="OK", command=ok).pack(side="left", padx=(0, 6))
    ttk.Button(bar, text="Cancel", command=dlg.destroy).pack(side="left")
    dlg.wait_window()
    return result["val"]


def _student_name_map() -> dict[str, str]:
    try:
        return {s.student_id: s.full_name for s in student_data.list_students()}
    except Exception:
        logger.exception("Could not build student name map")
        return {}


def _status_counts(rows: list[Enrolment]) -> dict[str, int]:
    counts = {s: 0 for s in STATUSES}
    for e in rows:
        counts[e.status] = counts.get(e.status, 0) + 1
    return counts


_STATUS_COLOURS = {
    "Enrolled":  "#2a7d2a",
    "Pending":   "#b8860b",
    "Withdrawn": "#888888",
    "Completed": "#2a7aa1",
}


def _count_badge_per_status(frame, rows: list[Enrolment]) -> None:
    """Feature #16 — coloured chips showing the count for each status."""
    counts = _status_counts(rows)
    ttk.Label(frame, text=f"Total {len(rows)}",
              font=("", 10, "bold")).pack(side="left", padx=(0, 10))
    for status in STATUSES:
        chip = tk.Label(frame, text=f"{status}: {counts.get(status, 0)}",
                        fg="white", bg=_STATUS_COLOURS.get(status, "#666"),
                        padx=8, pady=1)
        chip.pack(side="left", padx=(0, 6))


def _render_status_bar_chart(frame, counts: dict[str, int]) -> None:
    """Feature #25 — a simple horizontal bar chart drawn on a Canvas."""
    peak = max(counts.values()) if counts and max(counts.values()) else 1
    canvas = tk.Canvas(frame, width=420, height=len(counts) * 30 + 10,
                       highlightthickness=0)
    canvas.pack(anchor="w")
    for i, status in enumerate(STATUSES):
        n = counts.get(status, 0)
        y = 10 + i * 30
        width = int(300 * n / peak)
        canvas.create_rectangle(90, y, 90 + width, y + 20,
                                fill=_STATUS_COLOURS.get(status, "#666"), width=0)
        canvas.create_text(85, y + 10, text=status, anchor="e", font=("", 9))
        canvas.create_text(90 + width + 6, y + 10, text=str(n), anchor="w",
                           font=("", 9, "bold"))


@dataclass
class UndoEntry:
    """One undoable action. ``restore`` returns an optional message to
    show; when ``needs_reason`` it is called with the reason the user
    gives (a reinstatement needs one)."""
    label: str
    restore: Callable[..., str | None]
    needs_reason: bool = False


_UNDO_STACK: list[UndoEntry] = []


def _record_undo(label: str, restore: Callable[..., str | None], *,
                 needs_reason: bool = False) -> None:
    _UNDO_STACK.append(UndoEntry(label, restore, needs_reason))
    if len(_UNDO_STACK) > 20:
        _UNDO_STACK.pop(0)
