"""Button tests for the Primary School System's **Academic Management** menu.

Every label in the category is opened from the real main GUI
(``PrimarySchoolMainGUI.open_*``) and from the real CLI submenu
(``cli_main._submenu``) against the empty sandbox from ``conftest.py``.
A few simple CLI add-flows are driven end to end and checked through the
domain modules, and the access rules for the category are checked for staff
(teacher) and non-staff (pupil / parent) accounts.
"""

from __future__ import annotations

import re

import pytest

CATEGORY = "Academic Management"

#: The labels the category is expected to carry (GUI and CLI share them).
EXPECTED_LABELS = [
    "Academic Year", "Calendar", "Year Groups (R–6)", "Classes", "Subjects",
    "Timetable", "Attendance Register", "Lesson Plans", "Cover",
    "Homework / Reading Log", "Phonics Tracking", "Reading Levels",
    "Library", "Clubs & Activities",
]

#: The heading each CLI screen prints as ``── Heading ──`` / ``-- Heading --``.
CLI_HEADERS = {
    "Academic Year": "Academic Year",
    "Calendar": "Calendar",
    "Year Groups (R–6)": "Year Groups",
    "Classes": "Classes",
    "Subjects": "Subjects",
    "Timetable": "Timetable",
    "Attendance Register": "Attendance",
    "Lesson Plans": "Lesson Plans",
    "Cover": "Cover",
    "Homework / Reading Log": "Homework",
    "Phonics Tracking": "Phonics Tracking",
    "Reading Levels": "Reading Levels",
    "Library": "Library",
    "Clubs & Activities": "Clubs & Activities",
}

#: The page heading each GUI button draws in the main window's content area
#: (the title it passes to ``kit.show_page``).
GUI_PAGE_TITLES = {
    "Academic Year": "Academic Year",
    "Calendar": "Calendar",
    "Year Groups (R–6)": "Year Groups",
    "Classes": "Classes",
    "Subjects": "Subjects",
    "Timetable": "Timetable",
    "Attendance Register": "Attendance",
    "Lesson Plans": "Lesson Plans",
    "Cover": "Cover",
    "Homework / Reading Log": "Homework",
    "Phonics Tracking": "Phonics Tracking",
    "Reading Levels": "Reading Levels",
    "Library": "Library",
    "Clubs & Activities": "Clubs & Activities",
}

#: Enough "Back" / "Enter" answers to leave every nested menu.
BACK_OUT = ["0", ""] * 20


def _gui_items() -> list[tuple[str, str]]:
    from education_system.systems.primary import gui_main
    return list(dict(gui_main.NAV_CATEGORIES)[CATEGORY])


def _cli_items() -> list[str]:
    from education_system.systems.primary import cli_main
    return list(dict(cli_main.CATEGORIES)[CATEGORY])


def _handler_for(label: str) -> str:
    return dict(_gui_items())[label]


def _run_cli(label, auth, scripted_input, capsys, answers=None):
    """Open *label* from the Academic Management submenu, then back out.
    Returns (stdout, prompts seen)."""
    from education_system.systems.primary import cli_main

    items = _cli_items()
    choice = str(items.index(label) + 1)
    prompts = scripted_input([choice, *(answers or []), *BACK_OUT])
    cli_main._submenu(CATEGORY, items, auth=auth)
    return capsys.readouterr().out, prompts


def _assert_clean_cli(out: str, label: str) -> None:
    assert "[stub]" not in out, f"{label} fell through to the stub"
    assert "Traceback" not in out, out
    assert "Error:" not in out, f"{label} printed an error:\n{out}"
    assert "Error opening" not in out, out
    assert "Unexpected error" not in out, out
    assert "Validation error" not in out, out


def _header_re(header: str) -> re.Pattern[str]:
    return re.compile(rf"(──|--) {re.escape(header)} (──|--)")


# ── Catalogue ────────────────────────────────────────────────────────

def test_gui_category_lists_every_label_with_real_handlers():
    from education_system.systems.primary import gui_main

    items = _gui_items()
    assert [label for label, _ in items] == EXPECTED_LABELS
    for label, handler in items:
        assert handler.startswith("open_"), label
        method = getattr(gui_main.PrimarySchoolMainGUI, handler, None)
        assert callable(method), f"{label}: {handler} is not a method"
        # Not one of the generic fallbacks.
        assert handler not in ("_show_stub", "_show_denied"), label


def test_cli_category_lists_every_label():
    assert _cli_items() == EXPECTED_LABELS
    assert set(CLI_HEADERS) == set(EXPECTED_LABELS)
    assert set(GUI_PAGE_TITLES) == set(EXPECTED_LABELS)


def test_gui_and_cli_carry_the_same_labels():
    assert [label for label, _ in _gui_items()] == _cli_items()


# ── GUI: every button opens a screen ─────────────────────────────────

@pytest.mark.gui
@pytest.mark.parametrize("label", EXPECTED_LABELS)
def test_gui_button_opens_screen(label, primary_gui, content_text, page_text,
                                 toplevels):
    gui = primary_gui
    before_children = set(gui.content_frame.winfo_children())
    before_tops = set(toplevels(gui))

    getattr(gui, _handler_for(label))()
    gui.root.update_idletasks()

    text = content_text(gui)
    assert "not yet implemented" not in text, f"{label} opened the stub"
    assert "Could not open" not in text, text
    assert "does not have access" not in text, f"{label} was refused to admin"
    errors = [m for m in gui.messages if m[0] == "showerror"]
    assert not errors, f"{label} showed an error: {errors}"

    after_children = set(gui.content_frame.winfo_children())
    new_tops = [w for w in toplevels(gui) if w not in before_tops]
    assert not new_tops, f"{label} opened a window: {[w.title() for w in new_tops]}"
    assert after_children and after_children != before_children, (
        f"{label} put nothing in the content area")
    title = GUI_PAGE_TITLES[label]
    assert gui._current_page and gui._current_page[0] == title, gui._current_page
    assert title in page_text(gui).splitlines(), f"{label}: no {title!r} heading"


# ── CLI: every button opens its screen ───────────────────────────────

@pytest.mark.parametrize("label", EXPECTED_LABELS)
def test_cli_button_opens_screen(label, fake_auth, admin_principal,
                                 scripted_input, capsys):
    out, _prompts = _run_cli(label, fake_auth, scripted_input, capsys)
    _assert_clean_cli(out, label)
    assert _header_re(CLI_HEADERS[label]).search(out), (
        f"{label}: heading not shown:\n{out}")


# ── CLI behaviour: add a record, then see it in the domain ───────────

def test_cli_subjects_new_subject_is_saved(fake_auth, admin_principal,
                                           scripted_input, capsys):
    from education_system.systems.primary.domain.academics.subjects import (
        subjects,
    )

    answers = ["1",                       # New subject
               "MATHS", "Mathematics",    # code, name
               "", "",                    # key stage / curriculum defaults
               "Maths Dept", "y", "",     # department, core, notes
               "0"]                       # back out of Subjects
    out, _ = _run_cli("Subjects", fake_auth, scripted_input, capsys, answers)
    _assert_clean_cli(out, "Subjects")
    assert "Created subject" in out

    saved = subjects.get_by_code("MATHS")
    assert saved is not None
    assert saved.name == "Mathematics"
    assert saved.is_core
    assert saved.department == "Maths Dept"
    assert [s.code for s in subjects.list_all()] == ["MATHS"]


def test_cli_classes_add_class_is_listed(fake_auth, admin_principal,
                                         scripted_input, capsys):
    from education_system.systems.primary.domain.academics.classes import classes

    answers = ["4",                                  # Add class
               "Oak", "3", "Ms Teacher", "R12", "28", "",
               "",                                   # Press Enter
               "1", "",                              # List all classes
               "0"]
    out, _ = _run_cli("Classes", fake_auth, scripted_input, capsys, answers)
    _assert_clean_cli(out, "Classes")
    assert "Created class" in out
    assert "1 class(es)" in out

    rows = classes.list_all()
    assert [(c.name, c.year_group) for c in rows] == [("Oak", "3")]
    assert rows[0].capacity == 28


def test_cli_library_add_book_updates_catalogue(fake_auth, admin_principal,
                                                scripted_input, capsys):
    from education_system.systems.primary.domain.academics.library import library

    answers = ["1",                              # Add book
               "The Hobbit", "J.R.R. Tolkien", "",  # title, author, isbn
               "",                               # category (default Fiction)
               "1937", "3", "Shelf A", "",       # year, copies, shelf, notes
               "0"]
    out, _ = _run_cli("Library", fake_auth, scripted_input, capsys, answers)
    _assert_clean_cli(out, "Library")
    assert "Added book" in out

    books = library.list_books()
    assert [b.title for b in books] == ["The Hobbit"]
    assert books[0].copies_total == 3
    overview = library.overview()
    assert overview["books_total"] == 1
    assert overview["copies_total"] == 3


def test_cli_clubs_add_club_is_saved(fake_auth, admin_principal,
                                     scripted_input, capsys):
    from education_system.systems.primary.domain.academics.enrichment.clubs import (
        clubs,
    )

    answers = ["4",                                  # Add club
               "Chess Club", "Strategy games", "Monday",
               "15:30", "16:30", "Library", "Mr Knight", "",
               "12", "",                             # max members, notes
               "",                                   # Press Enter
               "0"]
    out, _ = _run_cli("Clubs & Activities", fake_auth, scripted_input,
                      capsys, answers)
    _assert_clean_cli(out, "Clubs & Activities")
    assert "Created club" in out

    rows = clubs.list_all()
    assert [c.name for c in rows] == ["Chess Club"]
    assert rows[0].day_of_week == "Monday"
    assert rows[0].max_members == 12


def test_cli_year_groups_lists_reception_to_year_6(fake_auth, admin_principal,
                                                   scripted_input, capsys):
    from education_system.systems.primary.domain.learners.pupils.pupils import (
        YEAR_GROUPS,
    )

    out, _ = _run_cli("Year Groups (R–6)", fake_auth, scripted_input, capsys)
    _assert_clean_cli(out, "Year Groups (R–6)")
    table = out.split("── Year Groups ──", 1)[-1]
    for yg in YEAR_GROUPS:
        assert re.search(rf"^\s+{re.escape(yg)}\s", table, re.MULTILINE), yg


# ── Access ───────────────────────────────────────────────────────────

def test_no_academic_label_is_restricted():
    from education_system.systems.primary.domain import access

    restricted = (set(access.ADMIN_ONLY) | {"Prevent Duty", "Safeguarding"})
    assert not restricted & set(EXPECTED_LABELS)


def test_teacher_can_open_every_academic_label(staff_principal):
    assert staff_principal.role == "teacher"
    for label in EXPECTED_LABELS:
        assert staff_principal.can_open(label), label


@pytest.mark.parametrize("label", EXPECTED_LABELS)
def test_cli_teacher_opens_screen(label, staff_auth, staff_principal,
                                  scripted_input, capsys):
    out, _ = _run_cli(label, staff_auth, scripted_input, capsys)
    _assert_clean_cli(out, label)
    assert "does not have access" not in out
    assert _header_re(CLI_HEADERS[label]).search(out), out


@pytest.mark.gui
@pytest.mark.parametrize("label", ["Classes", "Lesson Plans", "Library"])
def test_gui_teacher_opens_screen(label, primary_gui, staff_principal,
                                  content_text, page_text):
    primary_gui.principal = staff_principal
    getattr(primary_gui, _handler_for(label))()
    primary_gui.root.update_idletasks()
    text = content_text(primary_gui)
    assert "does not have access" not in text
    assert "not yet implemented" not in text
    assert GUI_PAGE_TITLES[label] in page_text(primary_gui).splitlines()


@pytest.fixture(params=["student", "parent"])
def non_staff(request, staff_auth, monkeypatch):
    """A pupil or parent account (same FakeAuth class as the conftest's)."""
    from education_system.systems.primary.domain import access

    auth = type(staff_auth)(username=f"{request.param}1", role=request.param)
    principal = access.from_auth(auth)
    monkeypatch.setattr(access.POLICY, "_current", principal)
    return auth, principal


def test_non_staff_cannot_open_academic_labels(non_staff):
    from education_system.systems.primary import cli_main

    _auth, principal = non_staff
    for label in EXPECTED_LABELS:
        assert not principal.can_open(label), label
    visible = [cat for cat, _ in
               principal.visible_menu(cli_main.CATEGORIES, labels_only=True)]
    assert CATEGORY not in visible


@pytest.mark.parametrize("label", ["Classes", "Timetable", "Library"])
def test_cli_non_staff_is_refused(label, non_staff, scripted_input, capsys):
    auth, principal = non_staff
    out, _ = _run_cli(label, auth, scripted_input, capsys)
    assert principal.denied_message(label) in out
    assert not _header_re(CLI_HEADERS[label]).search(out)


@pytest.mark.gui
@pytest.mark.parametrize("label", ["Classes", "Subjects", "Homework / Reading Log"])
def test_gui_non_staff_is_refused(label, primary_gui, non_staff, content_text,
                                  toplevels):
    _auth, principal = non_staff
    primary_gui.principal = principal
    before_tops = set(toplevels(primary_gui))
    getattr(primary_gui, _handler_for(label))()
    primary_gui.root.update_idletasks()
    assert principal.denied_message(label) in content_text(primary_gui)
    assert set(toplevels(primary_gui)) == before_tops
