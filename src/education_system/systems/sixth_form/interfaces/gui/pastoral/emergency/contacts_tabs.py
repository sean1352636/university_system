"""Emergency window tabs: per-student emergency contacts (priority
order), the call list used in an emergency, and the contact-attempt log.
"""

from __future__ import annotations

from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import messagebox
from typing import Any

from education_system.systems.sixth_form.domain.pastoral._records import Col
from education_system.systems.sixth_form.domain.pastoral.emergency import emergency as data
from education_system.systems.sixth_form.interfaces.gui.pastoral._records_ui import (
    RecordTab, ask_form,
)

_TAGS = {"reached": ("#e3f5e1", "#205c20"), "fallback": ("#eeeeee", "#555555")}


def _move(direction: int):
    def handler(tab: RecordTab, c: Any) -> None:
        data.move_contact(c.contact_id, direction)
    return handler


def _import(tab: RecordTab, _row: Any) -> None:
    sid = tab.filter_values().get("student_id")
    if not sid:
        messagebox.showinfo("Emergency contacts",
                            "Pick a student in the filter first.",
                            parent=tab.frame)
        return
    data.import_parent_contacts(sid)


def _log_for(tab: RecordTab, line: Any) -> None:
    sid = tab.filter_values().get("student_id")
    e = line.entry
    ask_form(tab.frame, f"Log call — {e.name}", data.ATTEMPT_SPEC.cols,
             initial={"student_id": sid, "contact_id": e.contact_id,
                      "contact_name": e.name,
                      "phone_dialled": e.phone or e.alt_phone,
                      "incident_id": tab.filter_values().get("incident_id")},
             on_save=data.log_attempt)


def _call_sheet(f: dict[str, Any]) -> list[Any]:
    if not f.get("student_id"):
        return []
    inc = f.get("incident_id")
    return data.call_sheet(f["student_id"],
                           incident_id=int(inc) if inc else None)


def add_contact_tabs(nb: ttk.Notebook) -> None:
    data.init_db()
    RecordTab(
        nb, "Call List", None,
        load=_call_sheet,
        columns=(("Order", lambda l: l.entry.order, 50),
                 ("Source", lambda l: l.entry.source, 120),
                 ("Name", lambda l: l.entry.name, 180),
                 ("Relationship", lambda l: l.entry.relationship, 110),
                 ("Phone", lambda l: l.entry.phone, 130),
                 ("Alt phone", lambda l: l.entry.alt_phone, 130),
                 ("May collect", lambda l: l.entry.can_collect, 80),
                 ("Attempts", lambda l: len(l.attempts), 70),
                 ("Last outcome", lambda l: (l.attempts[0].outcome
                                             if l.attempts else None), 200),
                 ("Reached", lambda l: l.reached, 70)),
        filters=(Col("student_id", "Student", "student"),
                 Col("incident_id", "Incident #", "int")),
        actions=(("Log Call", _log_for, True),),
        row_id=lambda l: l.entry.order,
        row_tag=lambda l: "reached" if l.reached else (
            "fallback" if l.entry.source != "Emergency list" else None),
        tag_colours=_TAGS,
        intro=("Ring in this order. With no incident #, today's attempts "
               "are shown. Grey rows come from parent contacts / the "
               "medical profile because the student has no list yet."))
    RecordTab(
        nb, "Emergency Contacts", data.CONTACT_SPEC,
        load=lambda f: data.list_contacts(f.get("student_id") or None),
        create=data.add_contact, update=data.update_contact,
        delete=data.delete_contact,
        filters=(Col("student_id", "Student", "student"),),
        actions=(("Move Up", _move(-1), True),
                 ("Move Down", _move(+1), True),
                 ("Import Parent Contacts", _import, False)),
        new_defaults=lambda t: {"student_id":
                                t.filter_values().get("student_id")},
        intro=("A row linked to a parent contact # shows that contact's "
               "live name and numbers on the call list."))
    RecordTab(
        nb, "Contact Attempts", data.ATTEMPT_SPEC,
        load=lambda f: data.list_attempts(
            student_id=f.get("student_id") or None,
            incident_id=int(f["incident_id"]) if f.get("incident_id")
            else None),
        create=data.log_attempt, update=data.update_attempt,
        delete=data.delete_attempt,
        filters=(Col("student_id", "Student", "student"),
                 Col("incident_id", "Incident #", "int")),
        row_tag=lambda a: "reached" if a.reached else None,
        tag_colours=_TAGS)
