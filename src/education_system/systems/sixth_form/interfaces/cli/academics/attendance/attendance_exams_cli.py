"""CLI for exam-room registers: the off-timetable exam flows plus seating,
access arrangements and separate rooms. Used by the Exams Office menu."""

from __future__ import annotations

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance_exams as exams,
)
from education_system.systems.sixth_form.interfaces.cli.academics.attendance import (
    attendance_offtimetable_cli as offtt,
)
from education_system.systems.sixth_form.interfaces.cli.assessment.exams_office.exams_cli_helpers import (
    ask,
    pause,
    run_menu,
    save_text,
    show_table,
)


def _sitting_id() -> int:
    return int(ask("Sitting #", required=True))


def candidates() -> None:
    sid = _sitting_id()
    rows = exams.list_candidates(sid, with_names=True)
    show_table([("Seat", 4), ("Cand", 5), ("Student", 10), ("Name", 22), ("State", 9),
                ("Extra", 5), ("Finish", 6), ("Access", 40)],
               [(c.seat, c.candidate_no, c.student_id, c.full_name, c.state,
                 c.extra_time_pct or "", c.finish_time, c.access_arrangements)
                for c in rows])
    pause()


def apply_access() -> None:
    n = exams.apply_access_arrangements(_sitting_id())
    print(f"  ✓ {n} candidate(s) have access arrangements")
    pause()


def print_plan() -> None:
    sid = _sitting_id()
    save_text(exams.seating_plan_text(sid), f"seating_plan_{sid}.txt")


def separate_room() -> None:
    sid = _sitting_id()
    flagged = [c.student_id for c in exams.list_candidates(sid) if c.separate_room]
    raw = ask("Student IDs, comma-separated", default=",".join(flagged))
    room = ask("Room", required=True)
    target = exams.move_candidates_to_room(sid, [s.strip() for s in raw.split(",")
                                                 if s.strip()], room)
    print(f"  ✓ Moved to sitting #{target.sitting_id} ({target.label})")
    pause()


def change_seat() -> None:
    sid = _sitting_id()
    exams.seat_candidate(sid, ask("Student ID", required=True), ask("Seat", required=True))
    print("  ✓ Seat changed")


MENU = [
    ("Create sitting (and fill from entries)", offtt.exam_create),
    ("Seating plan", offtt.exam_seating),
    ("Printable seating plan", print_plan),
    ("Candidates & access arrangements", candidates),
    ("Re-apply access arrangements", apply_access),
    ("Change seat", change_seat),
    ("Move candidates to a separate room", separate_room),
    ("Take the register", offtt.exam_register),
    ("Absentees & reportable", offtt.exam_absentees),
    ("Unsigned registers", offtt.exam_unsigned),
]


def run() -> None:
    run_menu("Exam Registers & Seating", MENU)
