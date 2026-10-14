"""The CLI menu structure, mirroring the GUI navigation.

Each entry names a command as ``"module.function"`` and is resolved lazily, so
a broken command module surfaces as one unavailable menu item rather than
stopping the whole shell from starting.

The three views match ``gui_main.NAVIGATION`` deliberately: a learner who is
shown "My attendance" in the GUI should find the same thing under the same name
here. Where the CLI offers something extra it is because the terminal suits it
better — bulk exports, for instance.
"""

from __future__ import annotations

import importlib
import logging
from collections.abc import Callable

logger = logging.getLogger(__name__)

_COMMAND_PACKAGE = "education_system.systems.fe_college.interfaces.cli.commands"

# view -> [(section, [(label, "module.function")])]
MENUS: dict[str, list[tuple[str, list[tuple[str, str]]]]] = {
    "admin": [
        ("Overview", [
            ("Dashboard", "admin.dashboard"),
            ("Run a report", "reports.run"),
            ("Export every report", "reports.export_all"),
        ]),
        ("Learners", [
            ("Learner directory", "students.directory"),
            ("View a learner", "students.view"),
            ("Add a learner", "students.create"),
            ("Enrol onto a course", "students.enrol"),
            ("Withdraw from a course", "students.withdraw"),
            ("Learners at risk", "students.at_risk"),
            ("Apprenticeship applications", "apprenticeship_progression.dashboard"),
            ("Progress learner to apprenticeship", "apprenticeship_progression.create"),
            ("University applications", "university_progression.dashboard"),
            ("Create UCAS-linked application", "university_progression.create"),
            ("Learner journey (360)", "learner_journey.show"),
        ]),
        ("Staff", [
            ("Staff directory", "staff.directory"),
            ("View a staff member", "staff.view"),
            ("Add a staff member", "staff.create"),
            ("Workload report", "staff.workload"),
            ("Set availability", "staff.availability"),
            ("Verification sampling", "staff.sampling"),
        ]),
        ("Curriculum", [
            ("Course catalogue", "courses.catalogue"),
            ("View a course", "courses.view"),
            ("Add a course", "courses.create"),
            ("Add a unit", "courses.add_unit"),
            ("Course viability", "courses.viability"),
            ("Archive or cancel a course", "courses.archive"),
        ]),
        ("Timetable", [
            ("College timetable", "timetable.college"),
            ("By course", "timetable.by_course"),
            ("By staff member", "timetable.by_staff"),
            ("Add a session", "timetable.add_session"),
            ("Remove a session", "timetable.remove_session"),
            ("Rooms", "timetable.rooms"),
            ("Find a free room", "timetable.free_rooms"),
        ]),
        ("Attendance", [
            ("By course", "attendance.by_course"),
            ("By learner", "attendance.by_learner"),
            ("Weekly trend", "attendance.trend"),
        ]),
        ("Finance", [
            ("Finance overview", "admin.finance"),
            ("Raise a fee", "admin.raise_fee"),
            ("Record a payment", "admin.record_payment"),
            ("Record a bursary", "admin.bursary"),
        ]),
        ("Email", [
            ("Email centre", "email.log"),
            ("Compose a message", "email.compose"),
            ("Send a standard letter", "email.from_template"),
            ("Drafts", "email.drafts"),
            ("Send a draft", "email.send"),
            ("Discard a draft", "email.discard"),
            ("Inbox", "email.inbox"),
            ("Read a message", "email.view"),
            ("Correspondence for a learner", "email.for_learner"),
        ]),
        ("Account", [
            ("Who am I?", "admin.whoami"),
            ("Link a college record", "admin.link_record"),
        ]),
    ],
    "staff": [
        ("Overview", [
            ("My teaching", "admin.dashboard"),
            ("My timetable", "timetable.mine"),
        ]),
        ("Teaching", [
            ("Take a register", "attendance.take_register"),
            ("Attendance by learner", "attendance.by_learner"),
            ("My lesson plans", "timetable.lesson_plans"),
        ]),
        ("Assessment", [
            ("My assignments", "assessments.assignments"),
            ("Set an assignment", "assessments.create_assignment"),
            ("Issue an assignment", "assessments.issue"),
            ("Marking queue", "assessments.marking_queue"),
            ("Mark a piece of work", "assessments.mark"),
            ("Internally verify marking", "assessments.verify"),
        ]),
        ("Learners", [
            ("My learners", "students.directory"),
            ("View a learner", "students.view"),
            ("Set a target", "students.targets"),
            ("Learners at risk", "students.at_risk"),
            ("Learner journey (360)", "learner_journey.show"),
        ]),
        ("Email", [
            ("Compose a message", "email.compose"),
            ("Send a standard letter", "email.from_template"),
            ("Drafts", "email.drafts"),
            ("Send a draft", "email.send"),
            ("Correspondence for a learner", "email.for_learner"),
        ]),
        ("Account", [
            ("Who am I?", "admin.whoami"),
            ("Link a college record", "admin.link_record"),
        ]),
    ],
    "student": [
        ("Overview", [
            ("My dashboard", "admin.dashboard"),
            ("My timetable", "timetable.mine"),
        ]),
        ("My learning", [
            ("My assignments", "assessments.my_assignments"),
            ("Hand work in", "assessments.hand_in"),
            ("My results", "assessments.my_results"),
        ]),
        ("Me", [
            ("My attendance", "attendance.my_attendance"),
            ("Who am I?", "admin.whoami"),
        ]),
    ],
}


def sections(view: str) -> list[tuple[str, list[tuple[str, str]]]]:
    """The menu for a view, falling back to the learner menu."""
    return MENUS.get(view, MENUS["student"])


def resolve(path: str) -> Callable | None:
    """Resolve ``"module.function"`` to a callable, or None if unavailable."""
    module_name, _, function_name = path.rpartition(".")
    try:
        module = importlib.import_module(f"{_COMMAND_PACKAGE}.{module_name}")
    except Exception:
        logger.exception("FE College CLI command module %s could not be imported",
                         module_name)
        return None
    function = getattr(module, function_name, None)
    if function is None:
        logger.error("FE College CLI command %s does not exist", path)
    return function


def all_commands(view: str) -> list[tuple[str, str]]:
    """Every ``(label, path)`` in a view, for the search feature."""
    return [item for _section, items in sections(view) for item in items]


__all__ = ["MENUS", "all_commands", "resolve", "sections"]
