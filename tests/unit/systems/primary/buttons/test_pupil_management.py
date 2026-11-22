"""Pupil Management buttons of the Primary School System (GUI and CLI).

Every label in the "Pupil Management" category is opened in the main GUI
(``PrimarySchoolMainGUI.open_*``) and through the CLI ``_submenu`` on an empty
sandbox (see ``conftest.py``), then a few flows are driven end to end:
adding, searching and viewing pupils, admissions → enrolment, year-end
promotion, onboarding, CSV import and promoting a pupil to a leaver.

None of the labels in this category is admin-only, DSL-only or raise-only, so
a teacher opens all of them; a pupil (student) account is refused.
"""

from __future__ import annotations

import pytest

CATEGORY = "Pupil Management"

EXPECTED_LABELS = [
    "Pupil Directory", "Add Pupil", "Search Pupils", "Pupil Profile",
    "Admissions", "Year Group Enrolment", "Onboarding", "Bulk Operations",
    "Leavers", "Year 6 Transition",
]

#: The header each CLI screen prints when it opens (distinct from the menu
#: line, which only shows the bare label).
CLI_HEADERS = {
    "Pupil Directory": "── Pupil Directory ──",
    "Add Pupil": "── Add Pupil ──",
    "Search Pupils": "── Search Pupils ──",
    "Pupil Profile": "── Pupil Profile ──",
    "Admissions": "── Admissions ──",
    "Year Group Enrolment": "── Year Group Enrolment ──",
    "Onboarding": "-- Onboarding --",
    "Bulk Operations": "-- Bulk Operations --",
    "Leavers": "-- Leavers --",
    # Followed by the academic year, e.g. "-- Year 6 Transition (2026-27) --".
    "Year 6 Transition": "-- Year 6 Transition (",
}

#: Answers a CLI screen needs before "0" backs out of it. Add Pupil is a
#: one-shot form (no menu), so it gets a valid pupil; Search and Profile ask
#: one question each.
CLI_SCRIPTS = {
    # Identity: first, middle, last, preferred, DOB, gender (1 = Female), UPN;
    # School: year, class, admission date (Enter = today), roll status
    # (Enter = on roll); Address: 2 lines, town, postcode; Needs: SEN
    # (Enter = N), FSM, EAL, notes; Parent / carer: name, relationship
    # (1 = Mother), phone, e-mail; Medical notes.
    "Add Pupil": ["Ada", "", "Lovelace", "", "2017-04-02", "1", "",
                  "3", "3A", "", "",
                  "", "", "", "",
                  "", "", "", "",
                  "Ann Lovelace", "1", "01234 567890", "",
                  ""],
    "Search Pupils": ["", ""],
    "Pupil Profile": [""],
}

#: Every GUI screen here is a page in the main window's content area: the
#: heading it draws (the title passed to ``kit.show_page``). None opens a
#: Toplevel (Add Pupil's own form is a modal, stubbed by ``no_form_dialog``).
GUI_PAGE_TITLES = {
    "Pupil Directory": "Pupil Directory",
    "Add Pupil": "Add Pupil",
    "Search Pupils": "Search Pupils",
    "Pupil Profile": "Pupil Profile",
    "Admissions": "Admissions",
    "Year Group Enrolment": "Year Group Enrolment",
    "Onboarding": "Onboarding",
    "Bulk Operations": "Bulk Operations",
    "Leavers": "Leavers",
    "Year 6 Transition": "Year 6 Transition",
}

BACK_OUT = ["0", ""] * 20


# ── helpers ──────────────────────────────────────────────────────────

def _nav_items() -> list[tuple[str, str]]:
    from education_system.systems.primary.gui_main import NAV_CATEGORIES
    return dict(NAV_CATEGORIES)[CATEGORY]


def _cli_items() -> list[str]:
    from education_system.systems.primary.cli_main import CATEGORIES
    return dict(CATEGORIES)[CATEGORY]


def _handler_for(label: str) -> str:
    return dict(_nav_items())[label]


def _run_cli(label: str, answers, *, auth, scripted_input, capsys) -> str:
    """Pick *label* in the Pupil Management submenu, feed *answers*, back out."""
    from education_system.systems.primary import cli_main
    items = _cli_items()
    choice = str(items.index(label) + 1)
    scripted_input([choice, *answers, *BACK_OUT])
    cli_main._submenu(CATEGORY, items, auth=auth)
    return capsys.readouterr().out


def _assert_clean_cli(out: str) -> None:
    assert "[stub]" not in out
    assert "Traceback" not in out
    assert "Error:" not in out
    assert "Error opening" not in out
    assert "Validation error" not in out


def _new_pupil(first="Grace", last="Hopper", year="3", class_name="3B", **extra):
    from education_system.systems.primary.domain.learners.pupils import pupils
    fields = {"first_name": first, "last_name": last, "year_group": year,
              "class_name": class_name, **extra}
    return pupils.create_pupil(fields)


def _walk(widget):
    yield widget
    for child in widget.winfo_children():
        yield from _walk(child)


@pytest.fixture
def no_form_dialog(monkeypatch):
    """``Add Pupil`` blocks in ``_form_dialog`` (``wait_window``) until the
    user saves; answer it as Cancel unless a test sets ``.result``."""
    from education_system.systems.primary.interfaces.gui.learners.pupils import pupil_views

    class Answer:
        result = None
        calls = 0

    def fake_form(host, title, initial=None, **_kw):
        Answer.calls += 1
        return Answer.result

    monkeypatch.setattr(pupil_views, "_form_dialog", fake_form)
    return Answer


# ── 1. menu shape ────────────────────────────────────────────────────

def test_gui_category_lists_every_pupil_management_label():
    labels = [label for label, _handler in _nav_items()]
    assert labels == EXPECTED_LABELS


def test_gui_handlers_are_real_methods_not_the_stub():
    from education_system.systems.primary.gui_main import PrimarySchoolMainGUI
    for label, handler in _nav_items():
        method = getattr(PrimarySchoolMainGUI, handler, None)
        assert callable(method), f"{label}: {handler} is missing"
        assert handler in vars(PrimarySchoolMainGUI), (
            f"{label}: {handler} is not defined on PrimarySchoolMainGUI")
        assert method is not getattr(PrimarySchoolMainGUI, "_show_stub", None)


def test_cli_category_matches_the_gui():
    assert _cli_items() == EXPECTED_LABELS


def test_cli_labels_are_routed_to_a_module_dispatch():
    from education_system.systems.primary.interfaces.cli.admissions import admissions_cli
    from education_system.systems.primary.interfaces.cli.admissions.enrolment import enrolment_cli
    from education_system.systems.primary.interfaces.cli.learners.pupils import pupil_cli
    from education_system.systems.primary.interfaces.cli.learners.pupils.bulk_operations import (
        bulk_operations_cli,
    )
    from education_system.systems.primary.interfaces.cli.learners.pupils.leavers import leavers_cli
    from education_system.systems.primary.interfaces.cli.learners.pupils.onboarding import (
        onboarding_cli,
    )
    routed = set()
    for module in (pupil_cli, onboarding_cli, bulk_operations_cli, leavers_cli,
                   admissions_cli, enrolment_cli):
        routed |= set(module._DISPATCH)
    assert set(EXPECTED_LABELS) <= routed


# ── 2. GUI: every button opens a screen ──────────────────────────────

@pytest.mark.gui
@pytest.mark.parametrize("label", EXPECTED_LABELS)
def test_gui_button_opens_screen(label, primary_gui, content_text, page_text,
                                 toplevels, no_form_dialog):
    gui = primary_gui
    before = set(toplevels(gui))

    getattr(gui, _handler_for(label))()
    gui.root.update_idletasks()

    text = content_text(gui)
    assert "not yet implemented" not in text
    assert "Could not open" not in text
    assert "does not have access" not in text
    assert not [m for m in gui.messages if m[0] == "showerror"], gui.messages

    new_windows = [w for w in toplevels(gui) if w not in before]
    assert new_windows == [], f"{label} opened a window: {[w.title() for w in new_windows]}"
    assert gui.content_frame.winfo_children()
    title = GUI_PAGE_TITLES[label]
    assert gui._current_page and gui._current_page[0] == title, gui._current_page
    assert title in page_text(gui).splitlines(), f"{label}: no {title!r} heading"


# ── 3. CLI: every item opens its screen and backs out ────────────────

@pytest.mark.parametrize("label", EXPECTED_LABELS)
def test_cli_item_opens_screen(label, fake_auth, admin_principal,
                               scripted_input, capsys):
    out = _run_cli(label, CLI_SCRIPTS.get(label, []), auth=fake_auth,
                   scripted_input=scripted_input, capsys=capsys)
    _assert_clean_cli(out)
    assert CLI_HEADERS[label] in out
    # The submenu was shown again after the screen closed, then left with 0.
    assert out.count(f"── {CATEGORY} ──") >= 2


# ── 4. behaviour ─────────────────────────────────────────────────────

def test_cli_add_pupil_then_directory_lists_it(fake_auth, admin_principal,
                                               scripted_input, capsys):
    from education_system.systems.primary.domain.learners.pupils import pupils

    out = _run_cli("Add Pupil", CLI_SCRIPTS["Add Pupil"], auth=fake_auth,
                   scripted_input=scripted_input, capsys=capsys)
    _assert_clean_cli(out)
    rows = pupils.list_pupils()
    assert [(p.first_name, p.last_name, p.year_group, p.class_name)
            for p in rows] == [("Ada", "Lovelace", "3", "3A")]
    ada = rows[0]
    assert f"Created pupil {ada.pupil_id}" in out
    assert ada.email and ada.email.startswith(ada.pupil_id.lower() + "@")
    assert ada.send_status == "no"
    assert (ada.sen_status, ada.gender, ada.parent_relationship) == ("N", "Female", "Mother")
    assert ada.admission_date

    out = _run_cli("Pupil Directory", [], auth=fake_auth,
                   scripted_input=scripted_input, capsys=capsys)
    _assert_clean_cli(out)
    assert ada.pupil_id in out
    assert "Ada Lovelace" in out
    assert "(no pupils)" not in out


def test_cli_add_pupil_rejects_bad_year_and_saves_nothing(
        fake_auth, admin_principal, scripted_input, capsys):
    from education_system.systems.primary.domain.learners.pupils import pupils

    answers = ["Ada", "", "Lovelace", "", "2017-04-02", "1", "", "9", *[""] * 16]
    out = _run_cli("Add Pupil", answers, auth=fake_auth,
                   scripted_input=scripted_input, capsys=capsys)
    assert "Validation error: Year group must be one of" in out
    assert pupils.list_pupils() == []


def test_cli_search_and_profile_find_an_existing_pupil(
        fake_auth, admin_principal, scripted_input, capsys):
    grace = _new_pupil(parent_name="Mary Hopper")
    _new_pupil(first="Alan", last="Turing", year="5", class_name="5A")

    out = _run_cli("Search Pupils", ["Hopper", ""], auth=fake_auth,
                   scripted_input=scripted_input, capsys=capsys)
    _assert_clean_cli(out)
    assert "1 match(es)" in out
    assert grace.pupil_id in out
    assert "Turing" not in out

    out = _run_cli("Pupil Profile", [grace.pupil_id, ""], auth=fake_auth,
                   scripted_input=scripted_input, capsys=capsys)
    _assert_clean_cli(out)
    assert f"── Pupil {grace.pupil_id} ──" in out
    assert "Grace Hopper" in out
    assert "Mary Hopper" in out


def test_cli_admissions_application_accepted_then_enrolled(
        fake_auth, admin_principal, scripted_input, capsys):
    from education_system.systems.primary.domain.admissions import admissions
    from education_system.systems.primary.domain.learners.pupils import pupils

    new_app = ["1", "Katherine", "Johnson", "2019-08-26", "R",
               "Joy Johnson", "", "joy@example.test", ""]
    out = _run_cli("Admissions", new_app, auth=fake_auth,
                   scripted_input=scripted_input, capsys=capsys)
    _assert_clean_cli(out)
    [app] = admissions.list_applications()
    assert app.applicant_name == "Katherine Johnson"
    assert app.status == "pending"
    assert f"Created application {app.application_id}" in out

    # An application that is not accepted cannot be enrolled.
    out = _run_cli("Admissions", ["6", app.application_id], auth=fake_auth,
                   scripted_input=scripted_input, capsys=capsys)
    assert "Only 'accepted' applications can be enrolled" in out
    assert pupils.list_pupils() == []

    out = _run_cli("Admissions",
                   ["5", app.application_id, "accepted",
                    "6", app.application_id],
                   auth=fake_auth, scripted_input=scripted_input, capsys=capsys)
    _assert_clean_cli(out)
    app = admissions.get_application(app.application_id)
    assert app.status == "enrolled"
    [pupil] = pupils.list_pupils()
    assert app.pupil_id == pupil.pupil_id
    assert (pupil.full_name, pupil.year_group) == ("Katherine Johnson", "R")
    assert f"as pupil {pupil.pupil_id}" in out


def test_cli_enrolment_promotes_a_year_and_bumps_the_class(
        fake_auth, admin_principal, scripted_input, capsys):
    from education_system.systems.primary.domain.learners.pupils import pupils

    moving = _new_pupil(year="3", class_name="3B")
    staying = _new_pupil(first="Alan", last="Turing", year="5", class_name="5A")

    out = _run_cli("Year Group Enrolment", ["3", "3", "y"], auth=fake_auth,
                   scripted_input=scripted_input, capsys=capsys)
    _assert_clean_cli(out)
    assert "Promoted 1 pupil(s) from year 3 to year 4." in out
    moved = pupils.get_pupil(moving.pupil_id)
    assert (moved.year_group, moved.class_name) == ("4", "4B")
    kept = pupils.get_pupil(staying.pupil_id)
    assert (kept.year_group, kept.class_name) == ("5", "5A")


def test_cli_enrolment_promotion_cancel_changes_nothing(
        fake_auth, admin_principal, scripted_input, capsys):
    from education_system.systems.primary.domain.learners.pupils import pupils

    pupil = _new_pupil(year="2", class_name="2A")
    out = _run_cli("Year Group Enrolment", ["3", "2", "n"], auth=fake_auth,
                   scripted_input=scripted_input, capsys=capsys)
    assert "Cancelled." in out
    assert pupils.get_pupil(pupil.pupil_id).year_group == "2"


def test_cli_onboarding_mark_all_done(fake_auth, admin_principal,
                                      scripted_input, capsys):
    from education_system.systems.primary.domain.learners.pupils.onboarding import onboarding

    pupil = _new_pupil()
    assert not onboarding.get_record(pupil.pupil_id).complete

    out = _run_cli("Onboarding", ["5", pupil.pupil_id], auth=fake_auth,
                   scripted_input=scripted_input, capsys=capsys)
    _assert_clean_cli(out)
    record = onboarding.get_record(pupil.pupil_id)
    assert record.complete
    assert record.done_count == record.total
    assert f"Marked all {record.total} step(s) done for pupil {pupil.pupil_id}." in out
    assert onboarding.progress_summary()["complete"] == 1


def test_cli_bulk_import_csv_creates_pupils(fake_auth, admin_principal,
                                            scripted_input, capsys, tmp_path):
    from education_system.systems.primary.domain.learners.pupils import pupils

    csv_path = tmp_path / "import.csv"
    csv_path.write_text(
        "first_name,last_name,year_group,class_name\n"
        "Mae,Jemison,4,4A\n"
        "Bad,Year,9,\n"
        "Rosalind,Franklin,R,\n",
        encoding="utf-8")

    out = _run_cli("Bulk Operations", ["1", str(csv_path), ""], auth=fake_auth,
                   scripted_input=scripted_input, capsys=capsys)
    assert "[stub]" not in out and "Traceback" not in out
    assert "Processed: 3" in out
    assert "Succeeded: 2" in out
    assert "Failed:    1" in out
    names = sorted(p.full_name for p in pupils.list_pupils())
    assert names == ["Mae Jemison", "Rosalind Franklin"]


def test_cli_leavers_promote_pupil_moves_record(fake_auth, admin_principal,
                                                scripted_input, capsys):
    from education_system.systems.primary.domain.learners.pupils import pupils
    from education_system.systems.primary.domain.learners.pupils.leavers import leavers

    pupil = _new_pupil(year="6", class_name="6A")
    answers = ["6", pupil.pupil_id, "Hill Secondary", "", "Year 6 transfer",
               "", "2026-07-20", "y", ""]
    out = _run_cli("Leavers", answers, auth=fake_auth,
                   scripted_input=scripted_input, capsys=capsys)
    _assert_clean_cli(out)
    assert pupils.get_pupil(pupil.pupil_id) is None
    [leaver] = leavers.list_leavers()
    assert leaver.pupil_id == pupil.pupil_id
    assert leaver.full_name == "Grace Hopper"
    assert leaver.year_left == "6"
    assert leaver.destination_school == "Hill Secondary"
    assert leaver.leaving_date == "2026-07-20"
    assert f"pupil {pupil.pupil_id} removed." in out


@pytest.mark.gui
def test_gui_add_pupil_saves_and_shows_directory(primary_gui, page_text,
                                                 no_form_dialog):
    from tkinter import ttk

    from education_system.systems.primary.domain.learners.pupils import pupils

    gui = primary_gui
    no_form_dialog.result = {
        "first_name": "Mary", "last_name": "Jackson", "year_group": "2",
        "class_name": "2C", "date_of_birth": "2019-05-14", "gender": "Female",
        "parent_name": "", "parent_phone": "", "medical_notes": "",
        "sen_status": "N",
    }
    gui.open_add_pupil()
    gui.root.update_idletasks()

    [pupil] = pupils.list_pupils()
    assert pupil.full_name == "Mary Jackson"
    assert ("showinfo", "Pupil added") in [(k, t) for k, t, _m in gui.messages]
    # Saving returns to the directory, which lists the new pupil.
    assert gui._current_page and gui._current_page[0] == "Pupil Directory"
    assert "Pupil Directory" in page_text(gui).splitlines()
    trees = [w for w in _walk(gui.content_frame) if isinstance(w, ttk.Treeview)]
    assert trees and pupil.pupil_id in trees[0].get_children()


@pytest.mark.gui
def test_gui_add_pupil_cancel_saves_nothing(primary_gui, no_form_dialog):
    from education_system.systems.primary.domain.learners.pupils import pupils

    primary_gui.open_add_pupil()
    assert no_form_dialog.calls == 1
    assert pupils.list_pupils() == []
    assert primary_gui.status_var.get() == "Add pupil cancelled"
    # Cancelling leaves the Add Pupil page showing.
    assert primary_gui._current_page and primary_gui._current_page[0] == "Add Pupil"


@pytest.mark.gui
def test_gui_profile_loads_a_pupil(primary_gui, page_text):
    from tkinter import ttk

    from education_system.systems.primary.interfaces.gui import kit

    gui = primary_gui
    pupil = _new_pupil(parent_name="Mary Hopper")
    gui.open_pupil_profile()

    widgets = list(_walk(gui.content_frame))
    # The pupil is chosen from a PupilPicker (bound to the pupil id), not typed.
    [picker] = [w for w in widgets if isinstance(w, kit.PupilPicker)]
    [load] = [w for w in widgets
              if isinstance(w, ttk.Button) and w.cget("text") == "Load"]
    picker.set(pupil.pupil_id)
    load.invoke()

    text = page_text(gui).splitlines()
    assert "Grace Hopper" in text
    assert "Mary Hopper" in text
    assert "No pupil with that ID." not in text

    picker.set("P0000000")
    load.invoke()
    assert "No pupil with that ID." in page_text(gui).splitlines()


@pytest.mark.gui
def test_gui_search_filters_pupils(primary_gui):
    from tkinter import ttk

    gui = primary_gui
    grace = _new_pupil()
    alan = _new_pupil(first="Alan", last="Turing", year="5", class_name="5A")
    gui.open_search_pupils()

    widgets = list(_walk(gui.content_frame))
    [tree] = [w for w in widgets if isinstance(w, ttk.Treeview)]
    assert set(tree.get_children()) == {grace.pupil_id, alan.pupil_id}

    # The query box; the year filter beside it is a picker (a Combobox, which
    # is also a ttk.Entry), so leave that out.
    [entry] = [w for w in widgets
               if isinstance(w, ttk.Entry) and not isinstance(w, ttk.Combobox)]
    [search] = [w for w in widgets
                if isinstance(w, ttk.Button) and w.cget("text") == "Search"]
    entry.insert(0, "Turing")
    search.invoke()
    assert tree.get_children() == (alan.pupil_id,)


# ── 5. access ────────────────────────────────────────────────────────

def test_no_pupil_management_label_is_restricted():
    from education_system.systems.primary.domain import access
    policy = access.POLICY
    for label in EXPECTED_LABELS:
        assert label not in access.ADMIN_ONLY
        assert label not in policy.dsl_only
        assert label not in policy.raise_only


def test_teacher_can_open_and_sees_every_label(staff_principal):
    from education_system.systems.primary.cli_main import CATEGORIES
    from education_system.systems.primary.gui_main import NAV_CATEGORIES

    for label in EXPECTED_LABELS:
        assert staff_principal.can_open(label), label
    gui_menu = dict(staff_principal.visible_menu(NAV_CATEGORIES))
    assert [label for label, _h in gui_menu[CATEGORY]] == EXPECTED_LABELS
    cli_menu = dict(staff_principal.visible_menu(CATEGORIES, labels_only=True))
    assert cli_menu[CATEGORY] == EXPECTED_LABELS


@pytest.mark.parametrize("label", EXPECTED_LABELS)
def test_cli_teacher_opens_item(label, staff_auth, staff_principal,
                                scripted_input, capsys):
    out = _run_cli(label, CLI_SCRIPTS.get(label, []), auth=staff_auth,
                   scripted_input=scripted_input, capsys=capsys)
    _assert_clean_cli(out)
    assert "does not have access" not in out
    assert CLI_HEADERS[label] in out


@pytest.mark.gui
def test_gui_teacher_opens_every_button(primary_gui, staff_principal,
                                        content_text, no_form_dialog):
    gui = primary_gui
    gui.principal = staff_principal
    for label in EXPECTED_LABELS:
        getattr(gui, _handler_for(label))()
        text = content_text(gui)
        assert "does not have access" not in text, label
        assert gui.status_var.get() != "Not available for this account", label
    assert not [m for m in gui.messages if m[0] == "showerror"], gui.messages


@pytest.fixture
def pupil_principal(fake_auth, monkeypatch):
    """A signed-in pupil (student account): no staff screens at all."""
    from education_system.systems.primary.domain import access

    auth = type(fake_auth)(username="pupil1", role="student")
    principal = access.from_auth(auth)
    monkeypatch.setattr(access.POLICY, "_current", principal)
    return auth, principal


def test_cli_pupil_account_is_refused_every_item(pupil_principal,
                                                 scripted_input, capsys):
    from education_system.systems.primary import cli_main

    auth, principal = pupil_principal
    items = _cli_items()
    visible = dict(principal.visible_menu(cli_main.CATEGORIES, labels_only=True))
    assert CATEGORY not in visible

    choices = [str(i) for i in range(1, len(items) + 1)]
    scripted_input([*choices, "0"])
    cli_main._submenu(CATEGORY, items, auth=auth)
    out = capsys.readouterr().out
    for label in EXPECTED_LABELS:
        assert f"Your account does not have access to {label}." in out
        assert CLI_HEADERS[label] not in out


@pytest.mark.gui
def test_gui_pupil_account_is_refused_every_button(primary_gui, pupil_principal,
                                                   content_text, toplevels,
                                                   no_form_dialog):
    from education_system.systems.primary.domain.learners.pupils import pupils

    gui = primary_gui
    _auth, principal = pupil_principal
    gui.principal = principal
    before = set(toplevels(gui))
    for label in EXPECTED_LABELS:
        getattr(gui, _handler_for(label))()
        assert content_text(gui).count(
            f"Your account does not have access to {label}.") == 1, label
        assert gui.status_var.get() == "Not available for this account"
    assert set(toplevels(gui)) == before
    assert no_form_dialog.calls == 0
    assert pupils.list_pupils() == []
