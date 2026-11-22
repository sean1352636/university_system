"""CLI "My area": the signed-in member of staff's own records."""

from __future__ import annotations

import logging
from typing import Callable

from education_system.systems.sixth_form.domain.staff.my_area import (
    my_area as data,
)
from education_system.systems.sixth_form.interfaces.cli.operations._ops_cli import (
    ask,
    choose,
    pause,
    run_menu,
    table,
    yes_no,
)

logger = logging.getLogger(__name__)


def overview_flow() -> None:
    o = data.overview()
    print(f"\n═══ {o['name']} ({o['staff_id']}) ═══")
    print(f"  {o['role']}, {o['department']}")
    for label, key in (("Lessons a week", "lessons_per_week"),
                       ("Absence days this year", "absence_days_this_year"),
                       ("CPD hours this year", "cpd_hours_this_year"),
                       ("Mandatory training", "training"),
                       ("DBS", "dbs"),
                       ("Open helpdesk tickets", "open_tickets"),
                       ("Appraisal", "appraisal")):
        print(f"  {label + ':':<26} {o[key]}")
    pause()


def timetable_flow() -> None:
    table(["Day", "Period", "Time", "Group", "Course", "Room"],
          [(e.day_name, e.period, f"{e.start_time or ''}-{e.end_time or ''}",
            e.group_name, e.course, e.room) for e in data.my_timetable()])
    pause()


def absences_flow() -> None:
    table(["Date", "Type", "Expected back", "Returned", "Days", "Status"],
          [(a.absence_date, a.absence_type, a.expected_return,
            a.actual_return, a.days_lost, a.status)
           for a in data.my_absences()])
    pause()


def _pick_appraisal() -> int:
    rows = data.my_appraisals()
    label = choose("Appraisal", [f"{a.appraisal_id} — {a.cycle} ({a.status})"
                                 for a in rows])
    if label is None:
        raise ValueError("You have no appraisal on record")
    return int(label.split(" — ")[0])


def appraisal_flow() -> None:
    aid = _pick_appraisal()
    a = next(x for x in data.my_appraisals() if x.appraisal_id == aid)
    print(f"\n  {a.cycle} — {a.status}; appraiser "
          f"{a.appraiser_name or a.appraiser_id or '—'}")
    print(f"  Overall: {a.grade_label}; pay progression {a.pay_progression}")
    print(f"  Strengths: {a.strengths or '—'}")
    print(f"  To develop: {a.areas_to_develop or '—'}")
    print(f"  Appraiser comments: {a.appraiser_comments or '—'}")
    print(f"  Your comments: {a.appraisee_comments or '—'}")
    table(["#", "Objective", "Type", "Status"],
          [(o.objective_number, o.title, o.objective_type, o.status)
           for o in data.my_objectives(aid)])
    so = data.signoff_for(aid)
    if so:
        print(f"  Signed off {so.signed_at[:10]} — {so.response}")
    pause()


def comments_flow() -> None:
    aid = _pick_appraisal()
    data.add_my_comments(aid, ask("Your comments", required=True))
    print("\n  ✓ Saved")
    pause()


def self_review_flow() -> None:
    aid = _pick_appraisal()
    data.mark_self_review_done(aid, yes_no("Self-review done?", default=True))
    print("\n  ✓ Saved")
    pause()


def sign_off_flow() -> None:
    aid = _pick_appraisal()
    resp = choose("Your response", data.SIGNOFF_RESPONSES,
                  default=data.AGREE)
    so = data.sign_off(aid, resp, ask("Comments (needed unless you agree)"))
    print(f"\n  ✓ Signed off {so.signed_at[:10]} ({so.response})")
    pause()


def training_flow() -> None:
    table(["Training", "State", "Last done", "Expires", "Recorded in"],
          [(c.type_name, c.state or "n/a", c.completed_on, c.expires_on,
            c.latest.source if c.latest else "")
           for c in data.my_training()])
    print(f"\n  CPD hours this year: {data.my_cpd_hours()}")
    pause()


def cpd_flow() -> None:
    table(["Booked", "Attended", "Status", "Hours", "Certificate"],
          [(r.booked_on, r.attended_on, r.status, r.hours_completed,
            "filed" if r.certificate_filed else "")
           for r in data.my_cpd()])
    pause()


def dbs_flow() -> None:
    c = data.my_dbs()
    print(f"\n  DBS: {data.dbs_state(c)}")
    if c is not None:
        print(f"  Level {c.level}; issued {c.issued_on or '—'}; "
              f"update service "
              f"{'yes' if c.update_service_subscribed else 'no'}")
    pause()


def tickets_flow() -> None:
    table(["Ref", "Summary", "Status", "With", "Raised"],
          [(t.reference, t.title, t.status, t.assignee_name,
            t.raised_at[:10]) for t in data.my_tickets()])
    pause()


def helpdesk_flow() -> None:
    from education_system.systems.sixth_form.domains.operations.interfaces.cli.helpdesk import (
        helpdesk_cli,
    )
    helpdesk_cli.run()


def directed_flow() -> None:
    d = data.my_directed_time()
    print(f"\n  {d.message}")
    for row in d.rows:
        print("  " + "   ".join(f"{k}: {v}" for k, v in row.items()))
    pause()


_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Overview",                   overview_flow),
    ("My timetable",               timetable_flow),
    ("My absences",                absences_flow),
    ("─" * 6,                      lambda: None),
    ("My appraisal",               appraisal_flow),
    ("Add my appraisal comments",  comments_flow),
    ("Self-review done",           self_review_flow),
    ("Sign off my appraisal",      sign_off_flow),
    ("─" * 6,                      lambda: None),
    ("My mandatory training",      training_flow),
    ("My CPD",                     cpd_flow),
    ("My DBS status",              dbs_flow),
    ("─" * 6,                      lambda: None),
    ("My helpdesk tickets",        tickets_flow),
    ("Helpdesk (report / follow)", helpdesk_flow),
    ("My directed time",           directed_flow),
]


def run() -> None:
    try:
        s = data.my_staff_record()
    except (ValueError, PermissionError) as e:
        print(f"\n  ✗ {e}")
        pause()
        return
    run_menu(f"My area — {s.full_name}", _MENU)


def my_area_menu() -> None:
    """Entry point for the main CLI menu."""
    run()


def dispatch(label: str) -> bool:
    if label != "My Area":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("My area CLI crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        pause()
    return True
