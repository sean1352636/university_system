"""CLI: entry codes & components, deadlines & fees, late-fee calculator, amendments.

These flows are added to the Exam Entries menu.
"""

from __future__ import annotations

from education_system.systems.sixth_form.domain.assessment.exams_office import entry_admin
from education_system.systems.sixth_form.interfaces.cli.assessment.exams_office.exams_cli_helpers import (
    ask,
    board,
    form,
    pause,
    pick_student,
    save_text,
    series,
    show_table,
    yes,
)


def components() -> None:
    print("\n═══ Entry codes & components ═══")
    rows = entry_admin.list_components()
    show_table([("ID", 4), ("Board", 18), ("Entry", 8), ("Component", 10),
                ("Title", 28), ("Mins", 4), ("Fee", 7), ("Active", 6)],
               [(c.component_id, c.exam_board, c.entry_code, c.component_code,
                 c.component_title, c.duration_minutes,
                 f"£{c.entry_fee:.2f}" if c.entry_fee is not None else "",
                 "Yes" if c.is_active else "No") for c in rows])
    pause()


def add_component() -> None:
    print("\n═══ Add / update component ═══")
    from education_system.systems.sixth_form.domain.academics.qualifications import (
        grade_scales,
    )
    data = {"exam_board": board()}
    data.update(form([("entry_code", "Entry (qualification) code"),
                      ("entry_title", "Entry title"),
                      ("qualification_type", "Qualification type",
                       list(grade_scales.QUALIFICATION_TYPES)),
                      ("component_code", "Component code"),
                      ("component_title", "Component title"),
                      ("duration_minutes", "Duration (minutes)"),
                      ("entry_fee", "Entry fee per component (£)")]))
    data["is_active"] = yes("Active", default=True)
    c = entry_admin.save_component(data)
    print(f"\n  ✓ Saved {c.component_code} under {c.entry_code}")
    pause()


def enter_for_option() -> None:
    print("\n═══ Enter a candidate for a whole option ═══")
    sid = pick_student()
    b = board()
    code = ask("Entry code", required=True)
    subject = ask("Subject", required=True)
    season, year = series()
    cand = ask("Candidate # (blank = from student record)")
    made = entry_admin.enter_for_option(student_id=sid, exam_board=b, entry_code=code,
                                        subject=subject, season=season, year=year,
                                        candidate_no=cand or None)
    print(f"\n  ✓ {len(made)} component entr(y/ies) created")
    pause()


def deadlines() -> None:
    print("\n═══ Series deadlines & fees ═══")
    rows = entry_admin.list_deadlines()
    show_table([("Board", 18), ("Series", 12), ("Entry", 10), ("Final late", 10),
                ("Late £", 7), ("V.late £", 8), ("Amend by", 10), ("Amend £", 7),
                ("Withdraw by", 11), ("Wdraw £", 7)],
               [(d.exam_board, f"{d.season} {d.year}", d.entry_deadline,
                 d.final_late_deadline, d.late_fee, d.very_late_fee, d.amendment_deadline,
                 d.amendment_fee, d.withdrawal_deadline, d.withdrawal_fee) for d in rows])
    if yes("Add or update a series"):
        b = board()
        season, year = series()
        existing = entry_admin.get_deadlines(b, season, year)
        data = form([("entry_deadline", "Entry deadline (YYYY-MM-DD)"),
                     ("final_late_deadline", "Final late deadline"),
                     ("late_fee", "Late fee (£)"), ("very_late_fee", "Very late fee (£)"),
                     ("amendment_deadline", "Amendment deadline"),
                     ("amendment_fee", "Amendment fee (£)"),
                     ("withdrawal_deadline", "Withdrawal deadline"),
                     ("withdrawal_fee", "Withdrawal fee (£)"), ("notes", "Notes")],
                    vars(existing) if existing else None)
        entry_admin.save_deadlines({**data, "exam_board": b, "season": season, "year": year})
        print("\n  ✓ Saved")
    pause()


def calendar() -> None:
    lines = ["ENTRY DEADLINE CALENDAR", ""]
    for i in entry_admin.deadline_calendar():
        when = f"in {i.days_left} day(s)" if i.days_left >= 0 else f"{-i.days_left} day(s) ago"
        lines.append(f"{i.date}  {i.exam_board:<18} {i.season} {i.year}  {i.kind:<20} {when}")
    save_text("\n".join(lines) + "\n", "entry_deadlines.txt")


def late_fees() -> None:
    print("\n═══ Late-fee calculator ═══")
    season, year = series()
    rows = entry_admin.late_fee_calculator(season=season, year=year)
    show_table([("Date", 10), ("Student", 10), ("Paper", 10), ("Charge", 18), ("Fee", 8)],
               [(f.on_date, f.student_id, f.paper_code, f.what, f"£{f.fee:.2f}")
                for f in rows])
    print(f"  TOTAL £{sum(f.fee for f in rows):.2f}")
    pause()


def amendments() -> None:
    print("\n═══ Amendment history ═══")
    sid = ask("Student ID (blank = all)")
    rows = entry_admin.list_amendments(student_id=sid or None)
    show_table([("When", 19), ("Student", 10), ("Paper", 10), ("Action", 10), ("Fee", 6),
                ("Changes", 50)],
               [(a.amended_at, a.student_id, a.paper_code, a.action,
                 a.fee if a.fee else "", a.changes) for a in rows[:200]])
    pause()


MENU = [
    ("Entry codes & components", components),
    ("Add / update component", add_component),
    ("Enter candidate for whole option", enter_for_option),
    ("Deadlines & fees", deadlines),
    ("Entry deadline calendar", calendar),
    ("Late-fee calculator", late_fees),
    ("Amendment history", amendments),
]
