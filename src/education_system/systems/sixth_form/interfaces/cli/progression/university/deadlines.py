"""CLI for UCAS deadlines — cohort deadlines, overdue/at-risk, cycle dates."""

from __future__ import annotations

import logging

from education_system.systems.sixth_form.domain.progression.university import (
    deadlines as data,
    ucas as ucas_data,
    workflow as workflow_data,
)
from education_system.systems.sixth_form.interfaces.cli.progression import _record_menus as rm

logger = logging.getLogger(__name__)

_COLUMNS = (("student_name", "Student", 22), ("key", "Deadline", 10),
            ("deadline", "UCAS", 10), ("internal_date", "College", 10),
            ("days_to_internal", "Days", 5), ("state", "State", 34),
            ("outstanding", "Outstanding", 40))


def _cycle() -> int:
    return rm.ask_int("Cycle (entry year)", default=workflow_data.default_cycle_year()) \
        or workflow_data.default_cycle_year()


def cohort() -> None:
    cycle = _cycle()
    rm.print_table([r.as_row() for r in data.cohort_deadlines(cycle)], _COLUMNS)
    rm.pause()


def overdue() -> None:
    rm.print_table([r.as_row() for r in data.overdue(_cycle())], _COLUMNS)
    rm.pause()


def at_risk() -> None:
    print(f"\n  Within {data.AT_RISK_DAYS} days of the college deadline with stages outstanding.")
    rm.print_table([r.as_row() for r in data.at_risk(_cycle())], _COLUMNS)
    rm.pause()


def cycle_dates() -> None:
    cycle = _cycle()
    rows = [{"key": d.key, "date": d.date.isoformat(),
             "internal": d.internal_date.isoformat() if d.internal_date else "—",
             "source": d.source, "label": d.label} for d in data.get_deadlines(cycle)]
    rm.print_table(rows, (("key", "Key", 12), ("date", "UCAS", 10),
                          ("internal", "College", 10), ("source", "Source", 10),
                          ("label", "Deadline", 60)))
    print("\n  Computed dates are the usual pattern — check UCAS/JCQ each cycle.")
    rm.pause()


def set_dates() -> None:
    cycle = _cycle()
    key = rm.choose("Deadline", data.DEADLINE_KEYS)
    current = data.get_deadline(cycle, key)
    ext = rm.ask("UCAS date (YYYY-MM-DD)", default=current.date.isoformat())
    internal = rm.ask("College deadline (YYYY-MM-DD, blank = default lead)",
                      default=current.internal_date.isoformat() if current.internal_date else "")
    notes = rm.ask("Notes (e.g. source)", default=current.notes or "")
    d = data.set_deadline(cycle, key, deadline_date=ext, internal_date=internal or None,
                          notes=notes)
    print(f"\n  ✓ {d.key}: {d.date} (college {d.internal_date})")
    rm.pause()


def reset_dates() -> None:
    cycle = _cycle()
    key = rm.choose("Deadline", data.DEADLINE_KEYS)
    print("  ✓ Reset." if data.reset_deadline(cycle, key) else "  (no override was set)")
    rm.pause()


def choice_flags() -> None:
    sid = rm.pick_student()
    app = ucas_data.get_application_for_student(sid)
    if app is None:
        print("  No UCAS application.")
        rm.pause()
        return
    flags = data.choice_flags(app.application_id)
    rows = [{"choice_id": f.choice_id, "order": f.choice_order, "uni": f.university,
             "course": f.course_name, "detected": f.detected or "—",
             "override": f.override or "—", "effective": f.effective or "January"}
            for f in flags]
    rm.print_table(rows, (("choice_id", "Id", 5), ("order", "#", 2), ("uni", "University", 24),
                          ("course", "Course", 26), ("detected", "Detected", 12),
                          ("override", "Override", 12), ("effective", "Effective", 12)))
    if rows and rm.ask_yes("Override a flag?"):
        row = rm.pick_row(rows, "choice_id", "Choice id")
        if row:
            flag = rm.choose("Flag", data.FLAG_VALUES, allow_blank=True)
            data.set_choice_flag(row["choice_id"], flag or None,
                                 notes=rm.ask("Notes"))
            print("  ✓ Saved.")
    info = data.application_deadline(app.application_id)
    print(f"\n  Deadline: {info.key} {info.deadline} (college {info.internal_date}) — {info.state}")
    rm.pause()


MENU = (
    ("All applications with their deadline", cohort),
    ("Overdue", overdue),
    ("At risk", at_risk),
    ("One learner's choices and October flags", choice_flags),
    ("Cycle dates", cycle_dates),
    ("Set a cycle date", set_dates),
    ("Reset a cycle date to computed", reset_dates),
)


def run() -> None:
    rm.run_menu("UCAS deadlines", MENU)


__all__ = ["run", "MENU"]
