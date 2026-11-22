"""Course changes: the change dialog for one enrolment (aim, new subject
/ type, the change window, override after the cut-off), the change log,
and the enrolment settings page (with history)."""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import ttk
from typing import Callable

from education_system.platform.delivery.gui.parented_dialogs import make_toplevel
from education_system.systems.sixth_form.domain.admissions.enrolments import (
    course_changes as cc,
)
from education_system.systems.sixth_form.domain.admissions.enrolments import enrolments as data

from . import enrolment_page_kit as kit
from .enrolment_common import _default_academic_year, describe_error, show_error

logger = logging.getLogger(__name__)

SAME_TYPE = "(same type)"

SETTING_LABELS = {
    cc.CHANGE_CUTOFF_DAYS: "Course-change cut-off (days after start)",
    cc.TUTOR_GROUP_LIMIT: "Tutor group size limit",
    cc.VISA_WARNING_DAYS: "Visa warning (days before expiry)",
}


def _subjects() -> list[str]:
    try:
        from education_system.systems.sixth_form.domain.learners.students.students import (
            A_LEVEL_SUBJECTS,
        )
        return list(A_LEVEL_SUBJECTS)
    except Exception:  # noqa: BLE001 — free text still works
        logger.exception("Subject list not read")
        return []


def _qual_types() -> list[str]:
    try:
        from education_system.systems.sixth_form.domain.academics.qualifications import (
            grade_scales,
        )
        return list(grade_scales.QUALIFICATION_TYPES)
    except Exception:  # noqa: BLE001
        logger.exception("Qualification types not read")
        return []


def result_lines(res) -> tuple[list[str], list[str]]:
    lines = list(res.lines)
    if res.override_used:
        lines.append("Made after the cut-off (override recorded).")
    if res.qualifying_met is not None:
        lines.append("Qualifying period for the old aim: "
                     + ("met" if res.qualifying_met else "not met"))
    return lines, list(res.problems)


def submit_change(gui, enrolment_id: int, values: dict, *, parent=None):
    """Run ``change_course`` with form values; show the result. Returns
    the result, or None when refused (the message is shown)."""
    try:
        aim_id = int(kit.code_of(values.get("aim")).lstrip("#"))
    except ValueError:
        show_error(parent or gui.root, "Change course", ValueError("Choose the aim to change"))
        return None
    qtype = values.get("type")
    res = kit.attempt(gui, "Change course", lambda: cc.change_course(
        enrolment_id, aim_id, (values.get("subject") or "").strip(),
        None if qtype in (None, "", SAME_TYPE) else qtype,
        effective_date=kit.blank_none(values.get("effective_date")),
        reason=(values.get("reason") or "").strip(),
        approved_by=(values.get("approved_by") or "").strip(),
        override_reason=kit.blank_none(values.get("override_reason"))), parent=parent)
    if res is not None:
        lines, problems = result_lines(res)
        kit.show_lines(gui, "Course changed", lines, problems, parent=parent)
        gui.status_var.set(f"Course changed: {res.from_label} → {res.to_label}")
    return res


def open_change_course(gui, enrolment_id: int,
                       after: Callable[[], None] | None = None) -> tk.Toplevel | None:
    e = data.get_enrolment(enrolment_id)
    if e is None:
        show_error(gui.root, "Change course", ValueError(f"No enrolment #{enrolment_id}"))
        return None
    try:
        window = cc.change_window(enrolment_id)
        aims = data.aims_for_enrolment(e)
    except Exception as exc:  # noqa: BLE001
        show_error(gui.root, "Change course", exc)
        return None
    if not aims:
        show_error(gui.root, "Change course", ValueError(
            f"Enrolment #{enrolment_id} has no active learning aims to change."))
        return None
    win = make_toplevel(gui.root)
    win.title(f"Change course — {e.student_id}, {e.academic_year}")
    body = ttk.Frame(win, padding=12)
    body.pack(fill="both", expand=True)
    ttk.Label(body, text=f"Change window: {window}",
              foreground="#2e7d32" if window.is_open else "#a33",
              font=("", 10, "bold")).grid(row=0, column=0, columnspan=2, sticky="w",
                                          pady=(0, 8))
    vars_: dict[str, tk.StringVar] = {}

    def row(r: int, key: str, label: str, widget_fn) -> None:
        ttk.Label(body, text=label + ":").grid(row=r, column=0, sticky="e", padx=4, pady=3)
        vars_[key] = tk.StringVar()
        widget_fn(vars_[key]).grid(row=r, column=1, sticky="w", padx=4, pady=3)

    aim_labels = [f"#{a.aim_id} — {a.label}" for a in aims]
    row(1, "aim", "Aim to change", lambda v: ttk.Combobox(
        body, textvariable=v, values=aim_labels, state="readonly", width=48))
    vars_["aim"].set(aim_labels[0])
    row(2, "subject", "New subject", lambda v: ttk.Combobox(
        body, textvariable=v, values=_subjects(), width=46))
    row(3, "type", "New qualification type", lambda v: ttk.Combobox(
        body, textvariable=v, values=[SAME_TYPE, *_qual_types()], state="readonly", width=46))
    vars_["type"].set(SAME_TYPE)
    row(4, "effective_date", "Effective date", lambda v: ttk.Entry(body, textvariable=v,
                                                                   width=14))
    vars_["effective_date"].set(_dt.date.today().isoformat())
    row(5, "reason", "Reason", lambda v: ttk.Entry(body, textvariable=v, width=50))
    row(6, "approved_by", "Approved by", lambda v: ttk.Entry(body, textvariable=v, width=30))
    vars_["approved_by"].set(kit.username() or "")
    row(7, "override_reason", "Override reason", lambda v: ttk.Entry(
        body, textvariable=v, width=50))
    ttk.Label(body, foreground="#555", wraplength=460, text=(
        "Only needed after the cut-off: the reason for changing anyway."
        if not window.is_open else
        "Not needed while the window is open (leave blank).")).grid(
        row=8, column=1, sticky="w", padx=4)

    def go() -> None:
        values = {k: v.get() for k, v in vars_.items()}
        if not window.is_open and not values["override_reason"].strip():
            show_error(win, "Change course", ValueError(
                f"The window closed on {window.cutoff}. Give an override reason."))
            return
        if submit_change(gui, enrolment_id, values, parent=win) is not None:
            win.destroy()
            (after or (lambda: None))()

    bar = ttk.Frame(body)
    bar.grid(row=9, column=0, columnspan=2, sticky="w", pady=(10, 0))
    ttk.Button(bar, text="Change Course", command=go,
               state=kit.state(kit.can_write())).pack(side="left", padx=(0, 6))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="left")
    win.go = go  # type: ignore[attr-defined]  # for scripted checks
    win.vars_ = vars_  # type: ignore[attr-defined]
    return win


# ── Change log ──────────────────────────────────────────────────────

LOG_COLS = [("id", "#", 50), ("sid", "Student", 90), ("from", "From", 200),
            ("to", "To", 200), ("eff", "Effective", 90), ("reason", "Reason", 260),
            ("approved", "Approved by", 110), ("by", "Recorded by", 100),
            ("at", "Recorded at", 140), ("qual", "Qualifying met", 100)]


def open_course_change_log(gui, academic_year: str | None = None) -> None:
    year = academic_year if academic_year is not None else _default_academic_year()
    frame, bar = kit.page(gui, "Course Change Log")
    top = ttk.Frame(frame)
    top.pack(anchor="w", fill="x")
    kit.year_picker(top, year, allow_all=True, label="Academic year (blank = all):",
                    on_change=lambda y: open_course_change_log(gui, y))
    try:
        rows = cc.change_log(year or None)
    except Exception as exc:  # noqa: BLE001
        show_error(gui.root, "Course change log", exc)
        rows = []
    kit.table(frame, LOG_COLS, [
        (r["change_id"], r["student_id"], r["from"], r["to"], r["effective_date"],
         r["reason"], r["approved_by"], r["recorded_by"], r["recorded_at"],
         {True: "Yes", False: "No"}.get(r["qualifying_met"], "—")) for r in rows])
    if not rows:
        kit.note(frame, "No course changes recorded.", colour="#777")
    kit.csv_button(bar, gui, lambda: rows,
                   f"course_changes_{(year or 'all').replace('/', '-')}.csv")
    gui.status_var.set(f"{len(rows)} course change(s)")


# ── Settings ────────────────────────────────────────────────────────

HIST_COLS = [("at", "Changed at", 150), ("key", "Setting", 260), ("old", "Old", 70),
             ("new", "New", 70), ("by", "By", 120)]


def open_enrolment_settings(gui) -> None:
    frame, bar = kit.page(gui, "Enrolment Settings")
    try:
        current = cc.settings()
        history = cc.settings_history()
    except Exception as exc:  # noqa: BLE001
        kit.note(frame, f"Settings not read: {describe_error(exc)}", colour="#a33")
        return
    kit.fields_grid(frame, [(SETTING_LABELS.get(k, k),
                             f"{v}" + (" (default)" if v == cc.DEFAULTS.get(k) else ""))
                            for k, v in current.items()], columns=1)
    write = kit.can_write()

    def edit() -> None:
        if kit.ask_form(gui.root, "Enrolment settings", [
                (k, SETTING_LABELS.get(k, k) + f" ({lo}–{hi})", "entry", None)
                for k, (lo, hi) in cc._LIMITS.items()], dict(current),
                on_submit=_save_settings(current)):
            open_enrolment_settings(gui)

    kit.button(bar, "Edit Settings…", edit, enabled=write)
    if not write:
        kit.note(frame, "Changing these needs the admissions or students.manage permission.")
    kit.section(frame, "History")
    kit.table(frame, HIST_COLS, [
        (h.get("changed_at") or h.get("at"), SETTING_LABELS.get(h.get("key"), h.get("key")),
         h.get("old_value"), h.get("new_value"), h.get("changed_by") or h.get("by"))
        for h in history])
    gui.status_var.set("Enrolment settings")


def _save_settings(current: dict) -> Callable[[dict], None]:
    def save(values: dict) -> None:
        for key, value in values.items():
            if str(value).strip() != str(current.get(key)):
                cc.set_setting(key, value)
    return save
