"""CLI for university admissions tests."""

from __future__ import annotations

import logging

from education_system.systems.sixth_form.domain.progression.university import (
    admissions_tests as data,
    ucas as ucas_data,
    workflow as workflow_data,
)
from education_system.systems.sixth_form.interfaces.cli.progression import _record_menus as rm

logger = logging.getLogger(__name__)

_COLUMNS = (("entry_id", "#", 4), ("student_name", "Student", 22), ("test_code", "Test", 6),
            ("registration_deadline", "Reg. by", 10), ("booked", "Bk", 3),
            ("test_date", "Test date", 10), ("score", "Score", 8), ("status", "Status", 16))

_FIELDS = (
    ("registration_deadline", "Registration deadline", "date"),
    ("registered_on", "Registered on", "date"),
    ("booked", "Booked", "bool"), ("booking_ref", "Booking reference", "text"),
    ("test_date", "Test date", "date"), ("test_centre", "Test centre", "text"),
    ("score", "Score / band", "text"), ("result_date", "Result received", "date"),
    ("adjustments_requested", "Reasonable adjustments requested", "text"),
    ("adjustments_approved", "Adjustments approved", "bool"),
    ("bursary_or_fee_waiver", "Bursary / fee waiver", "bool"),
    ("notes", "Notes", "text"),
)


def list_entries() -> None:
    cycle = rm.ask_int("Cycle (blank = all)")
    rm.print_table(data.list_entries(cycle_year=cycle), _COLUMNS)
    rm.pause()


def new_entry() -> None:
    sid = rm.pick_student()
    cycle = rm.ask_int("Cycle (entry year)", default=workflow_data.default_cycle_year())
    code = rm.choose("Test", data.test_codes())
    values = rm.form(_FIELDS)
    e = data.create_entry({"student_id": sid, "cycle_year": cycle, "test_code": code, **values})
    print(f"  ✓ Saved entry #{e['entry_id']} ({e['status']}).")
    rm.pause()


def edit_entry() -> None:
    rows = data.list_entries()
    rm.print_table(rows, _COLUMNS)
    row = rm.pick_row(rows, "entry_id", "Entry #")
    if row is None:
        return
    values = rm.form(_FIELDS, row)
    if rm.ask_yes("Mark withdrawn?", default=row["status"] == "Withdrawn"):
        values["status"] = "Withdrawn"
    else:
        values["status"] = None
    e = data.update_entry(row["entry_id"], values)
    print(f"  ✓ Updated ({e['status']}).")
    rm.pause()


def delete_entry() -> None:
    rows = data.list_entries()
    rm.print_table(rows, _COLUMNS)
    row = rm.pick_row(rows, "entry_id", "Entry #")
    if row and rm.ask_yes(f"Delete {row['test_code']} for {row['student_name']}?"):
        data.delete_entry(row["entry_id"])
        print("  ✓ Deleted.")
    rm.pause()


def alerts() -> None:
    print("\n  Registration closing (or closed) with nothing booked:")
    rm.print_table(data.registration_alerts(), (("alert", "Alert", 28),) + _COLUMNS[1:])
    print("\n  Booked tests in the next 30 days:")
    rm.print_table(data.upcoming_tests(), _COLUMNS)
    rm.pause()


def suggestions() -> None:
    cycle = rm.ask_int("Cycle (entry year)", default=workflow_data.default_cycle_year())
    rows = []
    for d in ucas_data.list_applications_with_detail(cycle_year=cycle):
        for s in data.suggested_tests(d.application.application_id):
            rows.append({"student": d.student_name, **s})
    rm.print_table(rows, (("student", "Student", 22), ("test_code", "Test", 6),
                          ("because", "Because of", 60)))
    rm.pause()


def test_list() -> None:
    rm.print_table(data.list_test_types(include_inactive=True),
                   (("code", "Code", 6), ("name", "Name", 40), ("active", "Act", 3),
                    ("course_keywords", "Course keywords", 50)))
    if rm.ask_yes("Add or edit a test?"):
        code = rm.ask("Code (existing code edits it)", required=True).upper()
        existing = next((t for t in data.list_test_types(include_inactive=True)
                         if t["code"] == code), {})
        values = rm.form((("name", "Name", "text"),
                          ("course_keywords", "Course keywords (comma-separated)", "text"),
                          ("university_keywords", "University keywords", "text"),
                          ("notes", "Notes", "text"), ("active", "Active", "bool")),
                         existing or {"active": True})
        data.save_test_type({"code": code, **values})
        print("  ✓ Saved.")
    rm.pause()


MENU = (
    ("List test entries", list_entries),
    ("New test entry", new_entry),
    ("Edit test entry (book / score / adjustments)", edit_entry),
    ("Delete test entry", delete_entry),
    ("Alerts — registration deadlines and upcoming tests", alerts),
    ("Suggested tests from UCAS choices", suggestions),
    ("Test list (configure)", test_list),
)


def run() -> None:
    rm.run_menu("Admissions tests", MENU)


__all__ = ["run", "MENU"]
