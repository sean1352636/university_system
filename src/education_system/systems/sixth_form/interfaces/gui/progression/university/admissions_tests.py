"""GUI for university admissions tests — the "Admissions tests" tab.

Four inner tabs: every learner's test entries; the alerts (registration
closing with nothing booked, tests coming up); suggestions from each
application's choices; and the configurable list of tests itself.
"""

from __future__ import annotations

import logging
from tkinter import ttk

from education_system.systems.sixth_form.domain.progression.university import (
    admissions_tests as data,
    ucas as ucas_data,
    workflow as workflow_data,
)
from education_system.systems.sixth_form.interfaces.gui.progression import _record_tabs as rt

logger = logging.getLogger(__name__)

_ENTRY_FIELDS = (
    ("student", "Student", "choice", rt.student_choices),
    ("cycle_year", "Cycle (entry year)", "number"),
    ("test_code", "Test", "choice", data.test_codes),
    ("registration_deadline", "Registration deadline", "date"),
    ("registered_on", "Registered on", "date"),
    ("booked", "Booked", "bool"), ("booking_ref", "Booking reference", "text"),
    ("test_date", "Test date", "date"), ("test_centre", "Test centre", "text"),
    ("score", "Score / band", "text"), ("result_date", "Result received", "date"),
    ("adjustments_requested", "Reasonable adjustments requested", "multiline"),
    ("adjustments_approved", "Adjustments approved", "bool"),
    ("bursary_or_fee_waiver", "Bursary / fee waiver", "bool"),
    ("status", "Withdrawn?", "choice", ("Withdrawn",)),
    ("notes", "Notes", "multiline"),
)

_COLUMNS = (
    ("student_name", "Student", 170), ("test_code", "Test", 70),
    ("cycle_year", "Cycle", 60), ("registration_deadline", "Reg. deadline", 100),
    ("booked", "Booked", 60), ("test_date", "Test date", 90),
    ("score", "Score", 80), ("status", "Status", 120),
    ("adjustments_requested", "Adjustments", 200),
)


def build_tab(gui, parent: ttk.Frame) -> None:
    nb = ttk.Notebook(parent)
    nb.pack(fill="both", expand=True)
    rt.notebook_tab(nb, "Entries", _entries)
    rt.notebook_tab(nb, "Alerts", _alerts)
    rt.notebook_tab(nb, "Suggestions", _suggestions)
    rt.notebook_tab(nb, "Test list", _types)


def _save_entry(entry_id, values):
    payload = dict(values)
    payload["student_id"] = rt.student_id_of(payload.pop("student", ""))
    if entry_id is None:
        return data.create_entry(payload)
    payload.pop("student_id", None)
    payload.pop("cycle_year", None)
    return data.update_entry(entry_id, payload)


def _entries(parent: ttk.Frame) -> None:
    def load(f):
        cycle = f.get("cycle") or ""
        return data.list_entries(cycle_year=int(cycle) if cycle.isdigit() else None,
                                 test_code=f.get("test") or None,
                                 status=f.get("status") or None)

    def new(table):
        rt.form_dialog(table.parent, "New admissions test entry", _ENTRY_FIELDS,
                       {"cycle_year": workflow_data.default_cycle_year()},
                       lambda v: _save_entry(None, v), table.refresh)

    def edit(table):
        row = table.require()
        initial = dict(row)
        initial["student"] = f"{row['student_id']} — {row.get('student_name') or ''}"
        initial["status"] = "Withdrawn" if row["status"] == "Withdrawn" else ""
        fields = tuple(f if f[0] not in ("student", "cycle_year") else
                       (f[0], f[1], "readonly") for f in _ENTRY_FIELDS)
        rt.form_dialog(table.parent, f"{row['test_code']} — {row['student_name']}",
                       fields, initial, lambda v: _save_entry(row["entry_id"], v),
                       table.refresh)

    def delete(table):
        row = table.require()
        if rt.confirm(table.parent, "Delete", f"Delete this {row['test_code']} entry?"):
            data.delete_entry(row["entry_id"])
            table.refresh()

    rt.RecordTable(
        parent, _COLUMNS, load, key="entry_id",
        filters=[("cycle", "Cycle", "text", (), workflow_data.default_cycle_year()),
                 ("test", "Test", "choice", data.test_codes),
                 ("status", "Status", "choice", data.ENTRY_STATUSES)],
        tags=lambda r: ("good" if r["score"] else
                        ("warn" if not r["booked"] and r["status"] != "Withdrawn" else None)),
        actions=[("New…", new), ("Edit…", edit), ("Delete", delete)],
        on_open=edit)


def _alerts(parent: ttk.Frame) -> None:
    def load(f):
        rows = [dict(r, alert=r["alert"]) for r in data.registration_alerts(within_days=21)]
        for r in data.upcoming_tests(within_days=30):
            rows.append(dict(r, alert="Test in the next 30 days"))
        return rows

    rt.RecordTable(
        parent, (("alert", "Alert", 220),) + _COLUMNS, load, key="entry_id",
        note=("Registration deadlines within three weeks with nothing booked, and "
              "booked tests in the next 30 days."),
        tags=lambda r: "bad" if "passed" in r["alert"] else "warn")


def _suggestions(parent: ttk.Frame) -> None:
    def load(f):
        cycle = f.get("cycle") or ""
        cycle_year = int(cycle) if cycle.isdigit() else workflow_data.default_cycle_year()
        rows = []
        for detail in ucas_data.list_applications_with_detail(cycle_year=cycle_year):
            for s in data.suggested_tests(detail.application.application_id):
                rows.append({"id": f"{detail.application.application_id}:{s['test_code']}",
                             "student_id": detail.application.student_id,
                             "student_name": detail.student_name,
                             "cycle_year": cycle_year, **s})
        return rows

    def add(table):
        row = table.require()
        rt.form_dialog(table.parent, f"Add {row['test_code']} for {row['student_name']}",
                       _ENTRY_FIELDS,
                       {"student": f"{row['student_id']} — {row['student_name']}",
                        "cycle_year": row["cycle_year"], "test_code": row["test_code"]},
                       lambda v: _save_entry(None, v), table.refresh)

    rt.RecordTable(
        parent,
        (("student_name", "Student", 180), ("test_code", "Test", 70),
         ("name", "Test name", 280), ("because", "Because of", 420)),
        load, key="id",
        filters=[("cycle", "Cycle", "text", (), workflow_data.default_cycle_year())],
        note=("Tests the choices point at that have no entry yet, from the keywords "
              "on the test list. A prompt to check — requirements change each cycle."),
        actions=[("Add entry…", add)], on_open=add)


def _types(parent: ttk.Frame) -> None:
    fields = (("code", "Code", "text"), ("name", "Name", "text"),
              ("course_keywords", "Course keywords (comma-separated)", "multiline"),
              ("university_keywords", "University keywords", "multiline"),
              ("notes", "Notes", "multiline"), ("active", "Active", "bool"))

    def new(table):
        rt.form_dialog(table.parent, "New test", fields, {"active": True},
                       data.save_test_type, table.refresh)

    def edit(table):
        row = table.require()
        rt.form_dialog(table.parent, f"Test {row['code']}",
                       (("code", "Code", "readonly"),) + fields[1:], row,
                       lambda v: data.save_test_type({**v, "code": row["code"]}),
                       table.refresh)

    rt.RecordTable(
        parent,
        (("code", "Code", 70), ("name", "Name", 280), ("active", "Active", 60),
         ("course_keywords", "Course keywords", 300), ("notes", "Notes", 320)),
        lambda f: data.list_test_types(include_inactive=True), key="code",
        note="The configurable list. Retire a test by unticking Active; history is kept.",
        tags=lambda r: None if r["active"] else "muted",
        actions=[("New…", new), ("Edit…", edit)], on_open=edit)


__all__ = ["build_tab"]
