"""CLI: exam timetable, candidate clashes and resolutions, contingency days."""

from __future__ import annotations

from education_system.systems.sixth_form.domain.assessment.exams_office import timetable
from education_system.systems.sixth_form.domain.assessment.exams_office.boards import SESSIONS
from education_system.systems.sixth_form.interfaces.cli.assessment.exams_office.exams_cli_helpers import (
    UserAbort,
    ask,
    board,
    form,
    pause,
    pick,
    run_menu,
    save_text,
    series,
    show_table,
    yes,
)


def show() -> None:
    season, year = series()
    rows = timetable.list_papers(season=season, year=year)
    show_table([("ID", 4), ("Date", 10), ("Ses", 3), ("Start", 5), ("End", 5),
                ("Board", 18), ("Component", 10), ("Title", 26), ("Cands", 5)],
               [(p.timetable_id, p.exam_date, p.session, p.start_time, p.end_time,
                 p.exam_board, p.component_code, p.title,
                 len(timetable.entries_for_paper(p))) for p in rows])
    missing = timetable.unscheduled_entries(season, year)
    if missing:
        print("\n  Entered but not timetabled: "
              + ", ".join(f"{c} ({b}, {n})" for b, c, n in missing))
    for c in timetable.list_contingency(season=season, year=year):
        print(f"  Contingency: {c.exam_date} {c.session or 'all day'}")
    pause()


def add() -> None:
    print("\n═══ Timetable a paper ═══")
    data = {"exam_board": board()}
    data["season"], data["year"] = series()
    data.update(form([("component_code", "Component code"),
                      ("exam_date", "Date (YYYY-MM-DD)"), ("session", "Session", SESSIONS),
                      ("start_time", "Start (blank = session start)"),
                      ("duration_minutes", "Duration (blank = catalogue)"),
                      ("title", "Title (blank = catalogue)")]))
    p = timetable.save_paper(data)
    print(f"\n  ✓ {p.label}")
    pause()


def delete() -> None:
    tid = int(ask("Timetable ID", required=True))
    if yes("Delete it"):
        timetable.delete_paper(tid)
        print("  ✓ Deleted")


def clashes() -> None:
    season, year = series()
    rows = timetable.candidate_clashes(season, year)
    show_table([("#", 3), ("Date", 10), ("Ses", 3), ("Student", 10), ("Name", 20),
                ("Papers", 22), ("Mins", 5), ("Resolution", 40)],
               [(i, c.exam_date, c.session, c.student_id, c.full_name,
                 ", ".join(p.component_code for p in c.papers), c.total_minutes,
                 c.resolution.method if c.resolution else "UNRESOLVED")
                for i, c in enumerate(rows, 1)])
    if rows and yes("Record a resolution"):
        n = int(ask("Clash #", required=True))
        if not 1 <= n <= len(rows):
            raise UserAbort
        c = rows[n - 1]
        method = pick("Method", list(timetable.RESOLUTION_METHODS))
        moved = pick("Paper moved", [p.component_code for p in c.papers], allow_blank=True)
        data = form([("moved_to_date", "Moved to date"),
                     ("moved_to_session", "Moved to session", SESSIONS),
                     ("moved_to_time", "Moved to time"), ("supervisor", "Supervisor"),
                     ("notes", "Notes")], {"moved_to_date": c.exam_date})
        moved_id = next((p.timetable_id for p in c.papers if p.component_code == moved), None)
        timetable.resolve_clash({**data, "student_id": c.student_id, "season": season,
                                 "year": year, "exam_date": c.exam_date,
                                 "session": c.session, "method": method,
                                 "moved_timetable_id": moved_id})
        print("  ✓ Resolution recorded")
    pause()


def contingency() -> None:
    season, year = series()
    for c in timetable.list_contingency(season=season, year=year):
        print(f"  {c.contingency_id}: {c.exam_date} {c.session or 'all day'} {c.notes or ''}")
    if yes("Add a contingency day"):
        data = form([("exam_date", "Date"), ("session", "Session (blank = all day)",
                                             SESSIONS), ("notes", "Notes")])
        timetable.save_contingency({**data, "season": season, "year": year})
        print("  ✓ Saved")
    pause()


def make_sitting() -> None:
    tid = int(ask("Timetable ID", required=True))
    room = ask("Room", required=True)
    s = timetable.create_sitting(tid, room=room)
    print(f"\n  ✓ Sitting #{s.sitting_id} created and filled: {s.label}")
    pause()


def print_timetable() -> None:
    season, year = series()
    lines = [f"EXAM TIMETABLE — {season} {year}", ""]
    for p in timetable.list_papers(season=season, year=year):
        lines.append(f"{p.exam_date} {p.session} {p.start_time}-{p.end_time}  "
                     f"{p.exam_board:<18} {p.component_code:<10} {p.title or ''}")
    save_text("\n".join(lines) + "\n", f"timetable_{season}{year}.txt")


MENU = [
    ("Show timetable", show), ("Add / update paper", add), ("Delete paper", delete),
    ("Candidate clashes & resolutions", clashes), ("Contingency days", contingency),
    ("Create sitting from timetable", make_sitting), ("Print timetable", print_timetable),
]


def run() -> None:
    run_menu("Exam Timetable", MENU)
