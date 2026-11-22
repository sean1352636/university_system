"""CLI: invigilator pool, allocations, cover check, printable rota."""

from __future__ import annotations

from education_system.systems.sixth_form.domain.assessment.exams_office import invigilation
from education_system.systems.sixth_form.interfaces.cli.assessment.exams_office.exams_cli_helpers import (
    ask,
    form,
    pause,
    pick,
    run_menu,
    save_text,
    show_table,
    yes,
)


def pool() -> None:
    rows = invigilation.list_invigilators(active_only=False)
    show_table([("ID", 4), ("Name", 24), ("Staff", 8), ("Phone", 14), ("Rdr/Scr", 7),
                ("Active", 6)],
               [(i.invigilator_id, i.name, i.staff_id, i.phone,
                 "Yes" if i.can_read_scribe else "", "Yes" if i.is_active else "No")
                for i in rows])
    pause()


def add() -> None:
    staff_id = ask("Staff ID to add from the directory (blank = type details)")
    if staff_id:
        i = invigilation.add_from_staff(staff_id)
    else:
        data = form([("name", "Name"), ("email", "Email"), ("phone", "Phone"),
                     ("trained_on", "Trained on (YYYY-MM-DD)"),
                     ("can_read_scribe", "Trained reader/scribe", False)])
        i = invigilation.save_invigilator(data)
    print(f"  ✓ {i.name} in the pool")
    pause()


def cover() -> None:
    f = ask("From (YYYY-MM-DD, blank = all)")
    t = ask("To (blank = all)")
    rows = invigilation.cover_report(date_from=f or None, date_to=t or None)
    show_table([("Sit", 4), ("Date", 10), ("Start", 5), ("Room", 10), ("Paper", 10),
                ("Cands", 5), ("Need", 4), ("Have", 4), ("R/S need", 8), ("Status", 6),
                ("Invigilators", 34)],
               [(c.sitting.sitting_id, c.sitting.date, c.sitting.start_time, c.sitting.room,
                 c.sitting.paper_code, c.candidates, c.required, c.allocated,
                 c.facilitators_needed, "OK" if c.ok else "SHORT",
                 ", ".join(a.invigilator_name for a in c.allocations)) for c in rows])
    for k in invigilation.conflicts(date_from=f or None, date_to=t or None):
        print(f"  ✗ {k.invigilator_name} double-booked: {k.first.label} / {k.second.label}")
    pause()


def allocate() -> None:
    sid = int(ask("Sitting #", required=True))
    pool_ = invigilation.list_invigilators()
    who = pick("Invigilator", [f"{i.invigilator_id}: {i.name}" for i in pool_])
    role = pick("Role", list(invigilation.ROLES), default="Invigilator")
    stu = ask("For candidate (reader/scribe, blank = none)")
    invigilation.allocate(sid, int(who.split(":")[0]), role=role, student_id=stu or None)
    print("  ✓ Allocated")
    pause()


def unallocate() -> None:
    sid = int(ask("Sitting #", required=True))
    allocs = invigilation.list_allocations(sitting_id=sid)
    if not allocs:
        print("  Nobody allocated.")
        return
    a = pick("Remove", [f"{a.allocation_id}: {a.invigilator_name} ({a.role})" for a in allocs])
    if yes("Remove them"):
        invigilation.unallocate(int(a.split(":")[0]))
        print("  ✓ Removed")


def rota() -> None:
    f = ask("From (YYYY-MM-DD, blank = all)")
    t = ask("To (blank = all)")
    save_text(invigilation.printable_rota(date_from=f or None, date_to=t or None),
              "invigilation_rota.txt")


MENU = [("Invigilator pool", pool), ("Add invigilator", add),
        ("Cover & conflicts", cover), ("Allocate to sitting", allocate),
        ("Remove from sitting", unallocate), ("Printable rota", rota)]


def run() -> None:
    run_menu("Invigilation", MENU)
