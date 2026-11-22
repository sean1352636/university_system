"""CLI for per-student emergency contacts (priority order), the call
list used in an emergency, and the contact-attempt log."""

from __future__ import annotations

from education_system.systems.sixth_form.domain.pastoral.emergency import (
    emergency as data,
)
from education_system.systems.sixth_form.interfaces.cli.pastoral import _records_cli as ui

_state: dict[str, str | None] = {"student_id": None}


def _student() -> str:
    if not _state["student_id"]:
        _state["student_id"] = ui.pick_student()
    return _state["student_id"]


def change_student() -> None:
    _state["student_id"] = ui.pick_student()
    print(f"\n  Working on {_state['student_id']}.")


def _incident() -> int | None:
    raw = ui.ask("Incident # (blank = today's calls)")
    return int(raw) if raw.isdigit() else None


_SHEET_COLS = (
    ("Ord", lambda l: l.entry.order, 3),
    ("Source", lambda l: l.entry.source, 15),
    ("Name", lambda l: l.entry.name, 20),
    ("Relationship", lambda l: l.entry.relationship, 12),
    ("Phone", lambda l: l.entry.phone, 14),
    ("Alt phone", lambda l: l.entry.alt_phone, 14),
    ("Collect", lambda l: l.entry.can_collect, 7),
    ("Tries", lambda l: len(l.attempts), 5),
    ("Last outcome", lambda l: l.attempts[0].outcome if l.attempts else None,
     18),
    ("Reached", lambda l: l.reached, 7),
)


def call_list() -> None:
    sid = _student()
    lines = data.call_sheet(sid, incident_id=_incident())
    ui.print_rows(lines, _SHEET_COLS,
                  empty="No contacts on file for this student.")
    if lines and lines[0].entry.source != "Emergency list":
        print("  (No emergency list yet — showing parent contacts / the "
              "medical profile contact.)")
    ui.pause()


def log_call() -> None:
    sid = _student()
    inc = _incident()
    lines = data.call_sheet(sid, incident_id=inc)
    ui.print_rows(lines, _SHEET_COLS)
    line = ui.pick_row(lines, lambda l: l.entry.order, "call list line")
    e = line.entry
    vals = ui.prompt_fields(data.ATTEMPT_SPEC.cols, initial={
        "student_id": sid, "incident_id": inc, "contact_id": e.contact_id,
        "contact_name": e.name, "phone_dialled": e.phone or e.alt_phone})
    a = data.log_attempt({"student_id": sid, **vals})
    print(f"\n  ✓ Logged attempt #{a.attempt_id} ({a.outcome}).")
    ui.pause()


def _pick_contact():
    rows = data.list_contacts(_student())
    ui.print_rows(rows, ui.spec_columns(data.CONTACT_SPEC))
    return ui.pick_row(rows, lambda c: c.contact_id, "contact")


def move(direction: int):
    def run_move() -> None:
        c = _pick_contact()
        c = data.move_contact(c.contact_id, direction)
        print(f"\n  ✓ {c.name} is now priority {c.priority}.")
        ui.pause()
    return run_move


def import_parents() -> None:
    added = data.import_parent_contacts(_student())
    print(f"\n  ✓ Imported {len(added)} parent contact(s).")
    ui.pause()


def run() -> None:
    contacts = ui.crud_items(
        "emergency contact", data.CONTACT_SPEC,
        load=lambda: data.list_contacts(_student()),
        create=data.add_contact, update=data.update_contact,
        delete=data.delete_contact,
        new_initial=lambda: {"student_id": _student()})
    attempts = ui.crud_items(
        "contact attempt", data.ATTEMPT_SPEC,
        load=lambda: data.list_attempts(student_id=_student()),
        create=data.log_attempt, update=data.update_attempt,
        delete=data.delete_attempt,
        new_initial=lambda: {"student_id": _student()})
    data.init_db()
    ui.run_menu("Emergency Contacts & Call Log", [
        ("Choose student", change_student),
        ("Call list", None),
        ("Show call list (priority order + calls made)", call_list),
        ("Log a call against the list", log_call),
        ("Emergency contacts", None),
        *contacts,
        ("Move contact up", move(-1)),
        ("Move contact down", move(+1)),
        ("Import parent contacts", import_parents),
        ("Contact attempts", None),
        *attempts,
    ])
