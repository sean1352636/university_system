"""GUI for UCAS deadlines — the Deadlines tab of University & UCAS.

Four inner tabs: every application with the deadline that applies to it
and where it stands; the overdue and at-risk lists on their own; and the
cycle's dates, where a date UCAS has moved is corrected.
"""

from __future__ import annotations

import logging
from tkinter import ttk

from education_system.systems.sixth_form.domain.progression.university import (
    deadlines as data,
    workflow as workflow_data,
)
from education_system.systems.sixth_form.interfaces.gui.progression import _record_tabs as rt

logger = logging.getLogger(__name__)

_STATE_TAG = {
    data.STATE_OVERDUE: "bad", data.STATE_MISSED: "bad", data.STATE_CLOSED: "bad",
    data.STATE_AT_RISK: "warn", data.STATE_SUBMITTED: "good",
    data.STATE_SUBMITTED_LATE: "warn", data.STATE_ON_TRACK: None,
}
_STATES = (data.STATE_ON_TRACK, data.STATE_AT_RISK, data.STATE_OVERDUE,
           data.STATE_MISSED, data.STATE_CLOSED, data.STATE_SUBMITTED,
           data.STATE_SUBMITTED_LATE)

_APP_COLUMNS = (
    ("student_name", "Student", 170), ("student_id", "ID", 80),
    ("key", "Deadline", 90), ("deadline", "UCAS date", 90),
    ("internal_date", "College date", 95), ("days_to_internal", "Days", 50),
    ("state", "State", 220), ("outstanding", "Outstanding", 260),
    ("reason", "Why this deadline", 240),
)


def _cycle(filters: dict[str, str]) -> int:
    raw = filters.get("cycle") or ""
    if not raw:
        return workflow_data.default_cycle_year()
    if not raw.isdigit():
        raise ValueError("Cycle must be a year, e.g. 2027")
    return int(raw)


def _cycle_filter():
    return ("cycle", "Cycle (entry year)", "text", (), workflow_data.default_cycle_year())


def build_tab(gui, parent: ttk.Frame) -> None:
    nb = ttk.Notebook(parent)
    nb.pack(fill="both", expand=True)
    rt.notebook_tab(nb, "Applications", lambda t: _applications(t, None))
    rt.notebook_tab(nb, "Overdue", lambda t: _applications(t, "overdue"))
    rt.notebook_tab(nb, "At risk", lambda t: _applications(t, "at_risk"))
    rt.notebook_tab(nb, "Cycle dates", _cycle_dates)


def _applications(parent: ttk.Frame, which: str | None) -> None:
    def load(f):
        cycle = _cycle(f)
        if which == "overdue":
            rows = data.overdue(cycle)
        elif which == "at_risk":
            rows = data.at_risk(cycle)
        else:
            rows = data.cohort_deadlines(cycle, state=f.get("state") or None)
        return [r.as_row() for r in rows]

    filters = [_cycle_filter()]
    if which is None:
        filters.append(("state", "State", "choice", _STATES))
    note = {
        None: ("Each application's deadline comes from its choices: any Oxford, "
               "Cambridge, medicine, dentistry or veterinary choice puts it on "
               "15 October, otherwise January. The college deadline is earlier. "
               "Due dates on the workflow stages are set from it automatically."),
        "overdue": "Not submitted and past the college deadline, or past UCAS's.",
        "at_risk": (f"Within {data.AT_RISK_DAYS} days of the college deadline with "
                    "workflow stages still outstanding."),
    }[which]
    rt.RecordTable(parent, _APP_COLUMNS, load, key="application_id",
                   filters=filters, note=note,
                   tags=lambda r: _STATE_TAG.get(r["state"]),
                   actions=[("Choices and October flags…", _flags_dialog)],
                   on_open=_flags_dialog)


def _flags_dialog(table: rt.RecordTable) -> None:
    row = table.require()
    flags = data.choice_flags(row["application_id"])
    if not flags:
        raise ValueError("This application has no choices yet.")
    lines = [f"{row['student_name']} — cycle {row['cycle_year']}", ""]
    for f in flags:
        lines.append(f"Choice {f.choice_order}: {f.university} — {f.course_name}")
        lines.append(f"   detected: {f.detected or 'January deadline'}"
                     f"   override: {f.override or '—'}"
                     f"   → {f.effective or 'January deadline'}")
    labels = [f"{f.choice_order}: {f.university} — {f.course_name}" for f in flags]
    by_label = dict(zip(labels, flags))
    rt.form_dialog(
        table.parent, "Override a choice's deadline flag",
        [("choice", "Choice", "choice", labels),
         ("flag", "Flag (blank = automatic)", "choice", data.FLAG_VALUES),
         ("notes", "Notes", "text")],
        {"choice": labels[0]},
        lambda v: data.set_choice_flag(
            by_label[v["choice"]].choice_id, v["flag"] or None, notes=v["notes"]),
        table.refresh,
        intro=("\n".join(lines) + "\n\nOverride when the keywords get a course "
               "wrong — e.g. mark a biomedical-science choice 'Not early'."))


def _cycle_dates(parent: ttk.Frame) -> None:
    def load(f):
        cycle = _cycle(f)
        return [{"id": f"{cycle}:{d.key}", "cycle": cycle, "key": d.key,
                 "label": d.label, "date": d.date.isoformat(),
                 "internal": d.internal_date.isoformat() if d.internal_date else "—",
                 "source": d.source, "notes": d.notes or ""}
                for d in data.get_deadlines(cycle)]

    def edit(table: rt.RecordTable) -> None:
        row = table.require()
        rt.form_dialog(
            table.parent, f"{row['key']} — cycle {row['cycle']}",
            [("deadline_date", "UCAS date", "date"),
             ("internal_date", "College deadline", "date"),
             ("notes", "Notes (e.g. source)", "text")],
            {"deadline_date": row["date"],
             "internal_date": "" if row["internal"] == "—" else row["internal"],
             "notes": row["notes"]},
            lambda v: data.set_deadline(row["cycle"], row["key"],
                                        deadline_date=v["deadline_date"] or None,
                                        internal_date=v["internal_date"] or None,
                                        notes=v["notes"]),
            table.refresh)

    def reset(table: rt.RecordTable) -> None:
        row = table.require()
        if rt.confirm(table.parent, "Reset", f"Go back to the computed {row['key']} date?"):
            data.reset_deadline(row["cycle"], row["key"])
            table.refresh()

    rt.RecordTable(
        parent,
        (("key", "Key", 110), ("label", "Deadline", 360), ("date", "UCAS date", 100),
         ("internal", "College date", 100), ("source", "Source", 90),
         ("notes", "Notes", 240)),
        load, key="id", filters=[_cycle_filter()],
        note=("Computed dates are the usual pattern. UCAS and JCQ publish the real "
              "dates each cycle — check them and set any that differ here (the "
              "January deadline in particular has moved)."),
        actions=[("Set dates…", edit), ("Reset to computed", reset)],
        on_open=edit)


__all__ = ["build_tab"]
