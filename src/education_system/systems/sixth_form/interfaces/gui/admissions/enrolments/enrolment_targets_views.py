"""Enrolment reports from ``enrolment_reports``: targets vs actuals (set,
list, delete), the withdrawal breakdown, and status counts with return
intentions — each with a CSV export."""

from __future__ import annotations

import logging
from tkinter import ttk

from education_system.platform.delivery.gui.parented_dialogs import messagebox
from education_system.systems.sixth_form.domain.admissions.enrolments import (
    enrolment_reports as reports,
)

from . import enrolment_page_kit as kit
from .enrolment_common import _default_academic_year, _year_choices, show_error

logger = logging.getLogger(__name__)


def _slug(year: str) -> str:
    return (year or "all").replace("/", "-")


# ── Targets ─────────────────────────────────────────────────────────

TARGET_COLS = [("label", "Target", 300), ("target", "Target", 70), ("actual", "Actual", 70),
               ("var", "Variance", 80), ("pct", "% of target", 90)]
SUBJECT_COLS = [("yg", "YG", 40), ("type", "Qualification", 160),
                ("subject", "Subject", 220), ("n", "Learners", 80)]


def open_targets(gui, academic_year: str | None = None) -> None:
    year = academic_year or _default_academic_year()
    frame, bar = kit.page(gui, "Enrolment Targets vs Actuals")
    top = ttk.Frame(frame)
    top.pack(anchor="w", fill="x")
    kit.year_picker(top, year, on_change=lambda y: open_targets(gui, y))
    try:
        rows = reports.targets_vs_actuals(year)
        subjects = reports.subject_actuals(year)
    except Exception as exc:  # noqa: BLE001
        show_error(gui.root, "Targets", exc)
        rows, subjects = [], []
    kit.section(frame, "Targets")
    tree = kit.table(frame, TARGET_COLS, [
        (_target_label(r), r.target, r.actual, f"{r.variance:+d}",
         "—" if r.pct_of_target is None else f"{r.pct_of_target:.0f}%") for r in rows],
        iids=[str(r.target_id) for r in rows], height=8)
    if not rows:
        kit.note(frame, "No targets set for this year.", colour="#777")
    kit.section(frame, "Actual learners by subject")
    kit.table(frame, SUBJECT_COLS, [(s.year_group, s.qualification_type, s.subject,
                                     s.learners) for s in subjects], height=8)
    write = kit.can_write()

    def set_target() -> None:
        if kit.ask_form(gui.root, "Set enrolment target", [
                ("academic_year", "Academic year", "readonly", _year_choices(year)),
                ("year_group", "Year group", "readonly", ["12", "13"]),
                ("target", "Target (learners)", "entry", None),
                ("programme", "Programme (optional)", "entry", None),
                ("subject", "Subject (optional)", "entry", None)],
                {"academic_year": year, "year_group": "12"},
                on_submit=lambda v: reports.set_target(
                    v["academic_year"], int(v["year_group"] or 12), _int(v["target"]),
                    programme=kit.blank_none(v.get("programme")),
                    subject=kit.blank_none(v.get("subject")))):
            open_targets(gui, year)

    def delete_target() -> None:
        iid = kit.selected(tree, "Targets", "a target")
        if iid and messagebox.askyesno("Delete target", "Delete this target?",
                                       parent=gui.root):
            if kit.attempt(gui, "Delete target",
                           lambda: reports.delete_target(int(iid))) is not None:
                open_targets(gui, year)

    kit.button(bar, "Set Target…", set_target, enabled=write)
    kit.button(bar, "Delete Target", delete_target, enabled=write)
    kit.csv_button(bar, gui, lambda: rows, f"targets_{_slug(year)}.csv")
    kit.csv_button(bar, gui, lambda: subjects, f"subject_actuals_{_slug(year)}.csv",
                   "Export Subjects CSV")
    gui.status_var.set(f"Targets {year}: {len(rows)}")


def _target_label(r) -> str:
    parts = [f"Year {r.year_group}"]
    if r.programme:
        parts.append(r.programme)
    if r.subject:
        parts.append(r.subject)
    return " · ".join(parts)


def _int(value) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        raise ValueError("The target must be a whole number") from None


# ── Withdrawal breakdown ────────────────────────────────────────────

BREAKDOWN_COLS = [("dim", "Breakdown", 140), ("value", "Value", 300),
                  ("n", "Withdrawals", 100)]


def open_withdrawal_breakdown(gui, academic_year: str | None = None) -> None:
    year = academic_year or _default_academic_year()
    frame, bar = kit.page(gui, "Withdrawal Analytics")
    top = ttk.Frame(frame)
    top.pack(anchor="w", fill="x")
    kit.year_picker(top, year, on_change=lambda y: open_withdrawal_breakdown(gui, y))
    try:
        wa = reports.withdrawal_analytics(year)
    except Exception as exc:  # noqa: BLE001
        show_error(gui.root, "Withdrawal analytics", exc)
        return
    kit.fields_grid(frame, [
        ("Starts", wa.starts), ("Withdrawals", wa.withdrawals),
        ("Early leavers", wa.early_leavers),
        ("Retention", "—" if wa.retention_pct is None else f"{wa.retention_pct:.1f}%"),
    ])
    kit.note(frame, "Starts leave out early leavers (withdrawn inside the qualifying "
             "period); withdrawals are those after it.")
    rows = wa.breakdown_rows()
    kit.table(frame, BREAKDOWN_COLS, [(r["dimension"], r["value"], r["withdrawals"])
                                      for r in rows])
    kit.csv_button(bar, gui, lambda: rows, f"withdrawals_{_slug(year)}.csv")
    gui.status_var.set(f"Withdrawals {year}: {wa.withdrawals}")


# ── Status counts and return intentions ─────────────────────────────

STATUS_COLS = [("year", "Year", 80), ("yg", "YG", 40), ("status", "Status", 120),
               ("n", "Count", 80)]
INTENT_COLS = [("intention", "Intention", 200), ("n", "Learners", 80)]


def open_status_counts(gui, academic_year: str | None = None) -> None:
    year = academic_year if academic_year is not None else _default_academic_year()
    frame, bar = kit.page(gui, "Status Counts & Return Intentions")
    top = ttk.Frame(frame)
    top.pack(anchor="w", fill="x")
    kit.year_picker(top, year, allow_all=True, label="Academic year (blank = all):",
                    on_change=lambda y: open_status_counts(gui, y))
    try:
        counts = reports.status_counts(year or None)
        intents = reports.return_intentions(year) if year else []
    except Exception as exc:  # noqa: BLE001
        show_error(gui.root, "Status counts", exc)
        counts, intents = [], []
    kit.section(frame, "Enrolments by status")
    kit.table(frame, STATUS_COLS, [(c.academic_year, c.year_group, c.status, c.count)
                                   for c in counts], height=10)
    kit.section(frame, "Year 12 return intentions")
    if year:
        kit.table(frame, INTENT_COLS, [(r["intention"], r["learners"]) for r in intents],
                  height=4, expand=False)
    else:
        kit.note(frame, "Choose a year to see return intentions.", colour="#777")
    kit.csv_button(bar, gui, lambda: counts, f"status_counts_{_slug(year)}.csv")
    kit.csv_button(bar, gui, lambda: intents, f"return_intentions_{_slug(year)}.csv",
                   "Export Intentions CSV")
    gui.status_var.set(f"Status counts {year or 'all years'}")
