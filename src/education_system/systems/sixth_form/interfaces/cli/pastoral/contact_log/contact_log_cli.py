"""CLI: General contact log."""

from __future__ import annotations

from education_system.systems.sixth_form.domain.pastoral._records import today
from education_system.systems.sixth_form.domain.pastoral.contact_log import (
    contact_log as data,
)
from education_system.systems.sixth_form.interfaces.cli.pastoral import _records_cli as ui

_COLS = (
    ("#", lambda c: c.contact_id, 5),
    ("Date", lambda c: c.contact_date, 10),
    ("Student", lambda c: c.student_id, 9),
    ("With", lambda c: c.contact_with, 14),
    ("Method", lambda c: c.method, 8),
    ("Dir", lambda c: c.direction[:3], 3),
    ("Reason", lambda c: c.reason, 16),
    ("Summary", lambda c: c.summary, 30),
    ("Follow up", lambda c: (c.follow_up_by or "yes") + (
        " !" if c.follow_up_overdue else "") if c.follow_up_open else "", 12),
)


def student_log() -> None:
    sid = ui.pick_student()
    ui.print_rows(data.contacts_for_student(sid), _COLS,
                  empty="(no contacts you can see)")
    ui.pause()


def follow_ups() -> None:
    ui.print_rows(data.list_contacts(
        follow_up_open_only=True,
        mine_only=ui.yes_no("Only contacts I logged?", False)), _COLS,
        empty="(no open follow-ups)")
    ui.pause()


def follow_up_done() -> None:
    rows = data.list_contacts(follow_up_open_only=True)
    ui.print_rows(rows, _COLS)
    c = ui.pick_row(rows, lambda r: r.contact_id, "contact")
    data.complete_follow_up(c.contact_id, on=ui.ask("On", default=today()),
                            notes=ui.ask_multiline("Notes"))
    print("\n  ✓ Follow-up recorded.")
    ui.pause()


def summary() -> None:
    s = data.summary(date_from=ui.ask("From (blank = 30 days ago)") or None,
                     date_to=ui.ask("To (blank = today)") or None)
    print(f"\n═══ Contacts {s.date_from} to {s.date_to} ═══")
    print(f"  Contacts: {s.total}   students: {s.students}   "
          f"out/in: {s.outgoing}/{s.incoming}")
    print(f"  Follow-ups open: {s.follow_ups_open} "
          f"({s.follow_ups_overdue} overdue)")
    for title, d in (("By reason", s.by_reason), ("By method", s.by_method),
                     ("Contact with", s.by_with)):
        print(f"\n  {title}:")
        for k, n in sorted(d.items(), key=lambda kv: -kv[1]):
            print(f"    {k:<30} {n}")
    ui.pause()


def run() -> None:
    ui.run_menu("Contact Log", [
        *ui.crud_items("contact", data.SPEC,
                       load=lambda: data.list_contacts(), columns=_COLS,
                       create=data.log_contact, update=data.update_contact,
                       delete=data.delete_contact),
        ("A student's contact log", student_log),
        ("Open follow-ups", follow_ups),
        ("Mark follow-up done", follow_up_done),
        ("Summary", summary),
    ])


def contact_log_menu() -> None:
    """Entry point for the main CLI menu."""
    run()
