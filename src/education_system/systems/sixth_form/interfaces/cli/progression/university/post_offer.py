"""CLI for UCAS Extra, Clearing and Adjustment."""

from __future__ import annotations

import logging

from education_system.systems.sixth_form.domain.progression.university import (
    post_offer as data,
    ucas as ucas_data,
    workflow as workflow_data,
)
from education_system.systems.sixth_form.interfaces.cli.progression import _record_menus as rm

logger = logging.getLogger(__name__)


def _application() -> int | None:
    sid = rm.pick_student()
    app = ucas_data.get_application_for_student(sid)
    if app is None:
        print("  This student has no UCAS application.")
        rm.pause()
        return None
    return app.application_id


def cohort() -> None:
    cycle = rm.ask_int("Cycle (entry year)", default=workflow_data.default_cycle_year())
    only = rm.ask_yes("Only applications that can open or have open routes?", default=True)
    rm.print_table([r.as_row() for r in data.cohort(cycle, only_actionable=only)],
                   (("application_id", "App", 5), ("student_name", "Student", 24),
                    ("status", "Status", 10), ("confirmation", "Results day", 26),
                    ("eligible", "Can open", 24), ("open_routes", "Open", 20)))
    rm.pause()


def explain() -> None:
    app_id = _application()
    if app_id is None:
        return
    for e in data.eligibility(app_id):
        print(f"\n  {e.route:<11} {'ELIGIBLE' if e.eligible else 'not eligible'}")
        print(f"              {e.reason}")
    rm.pause()


def record_results() -> None:
    app_id = _application()
    if app_id is None:
        return
    outcome = rm.choose("UCAS outcome", data.CONFIRMATION_OUTCOMES)
    exceeded = outcome == "Firm confirmed" and rm.ask_yes("Conditions exceeded?")
    data.record_confirmation(app_id, outcome, exceeded_conditions=exceeded,
                             confirmed_on=rm.ask("Confirmed on (YYYY-MM-DD, blank = today)") or None,
                             notes=rm.ask("Notes"))
    print("  ✓ Recorded.")
    rm.pause()


def open_route() -> None:
    app_id = _application()
    if app_id is None:
        return
    routes = data.eligible_routes(app_id)
    if not routes:
        print("  Not eligible for any route — see 'Why'.")
        rm.pause()
        return
    r = data.open_route(app_id, rm.choose("Route", routes), notes=rm.ask("Notes"))
    print(f"  ✓ Opened {r['route']} (route #{r['route_id']}).")
    rm.pause()


def _pick_route(status: str | None = "Active") -> dict | None:
    rows = data.list_routes(status=status)
    rm.print_table(rows, (("route_id", "#", 5), ("route", "Route", 10),
                          ("student_name", "Student", 24), ("status", "Status", 20),
                          ("n_choices", "Choices", 7)))
    return rm.pick_row(rows, "route_id", "Route #")


def routes() -> None:
    rm.print_table(data.list_routes(),
                   (("route_id", "#", 5), ("route", "Route", 10),
                    ("student_name", "Student", 24), ("status", "Status", 20),
                    ("opened_on", "Opened", 10), ("outcome", "Outcome", 40)))
    rm.pause()


def route_choices() -> None:
    r = _pick_route(status=None)
    if r is None:
        return
    rm.print_table(data.list_choices(r["route_id"]),
                   (("po_choice_id", "#", 5), ("university", "University", 24),
                    ("course_name", "Course", 28), ("status", "Status", 18),
                    ("entry_requirements", "Requirements", 20)))
    if rm.ask_yes("Add a choice?"):
        values = rm.form((("university", "University", "text"),
                          ("course_name", "Course", "text"),
                          ("course_code", "Course code", "text"),
                          ("entry_requirements", "Entry requirements", "text"),
                          ("status", "Status", "choice", data.CHOICE_STATUSES)))
        data.add_choice(r["route_id"], values)
        print("  ✓ Added.")
    elif rm.ask_yes("Update a choice's status?"):
        rows = data.list_choices(r["route_id"])
        c = rm.pick_row(rows, "po_choice_id", "Choice #")
        if c:
            data.update_choice(c["po_choice_id"],
                               {"status": rm.choose("Status", data.CHOICE_STATUSES)})
            print("  ✓ Updated.")
    rm.pause()


def close_route() -> None:
    r = _pick_route()
    if r is None:
        return
    status = rm.choose("Result", ("Placed", "Closed - not placed", "Withdrawn"))
    placed = None
    if status == "Placed":
        rows = data.list_choices(r["route_id"])
        rm.print_table(rows, (("po_choice_id", "#", 5), ("university", "University", 24),
                              ("course_name", "Course", 28)))
        c = rm.pick_row(rows, "po_choice_id", "Placed on choice #")
        placed = c["po_choice_id"] if c else None
    data.close_route(r["route_id"], status=status, outcome=rm.ask("Outcome note"),
                     placed_po_choice_id=placed)
    print("  ✓ Closed.")
    rm.pause()


def log_contact() -> None:
    app_id = _application()
    if app_id is None:
        return
    values = rm.form((("university", "University", "text"),
                      ("contact_date", "Date", "date"),
                      ("method", "Method", "choice", data.CONTACT_METHODS),
                      ("contact_name", "Spoke to", "text"),
                      ("summary", "Summary", "text"), ("outcome", "Outcome", "text"),
                      ("follow_up_date", "Follow up on", "date")))
    open_routes = data.list_routes(application_id=app_id)
    if open_routes and rm.ask_yes("Link to a route?"):
        r = rm.pick_row(open_routes, "route_id", "Route #")
        values["route_id"] = r["route_id"] if r else None
    data.log_contact(app_id, values)
    print("  ✓ Logged.")
    rm.pause()


def contacts() -> None:
    rm.print_table(data.list_contacts(),
                   (("contact_date", "Date", 10), ("student_id", "Student", 10),
                    ("university", "University", 22), ("method", "Method", 8),
                    ("summary", "Summary", 40), ("follow_up_date", "Follow up", 10)))
    rm.pause()


MENU = (
    ("Cohort — who can use Extra / Clearing / Adjustment", cohort),
    ("Why (eligibility for one learner)", explain),
    ("Record results-day confirmation", record_results),
    ("Open a route", open_route),
    ("List routes", routes),
    ("Route choices (view / add / update)", route_choices),
    ("Close a route (placed / not placed)", close_route),
    ("Log contact with a university", log_contact),
    ("Contact log", contacts),
)


def run() -> None:
    rm.run_menu("Extra, Clearing & Adjustment", MENU)


__all__ = ["run", "MENU"]
