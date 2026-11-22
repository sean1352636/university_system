"""Role rule for the Primary School menus, and idle logout in its CLI.

The safeguarding-lead lookup is replaced for every test, so nothing here opens a
staff database.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from education_system import switch
from education_system.platform.delivery.cli import cli_helpers
from education_system.systems.primary import cli_main, gui_main
from education_system.systems.primary.domain import access

ACCOUNT = {"Change Password", "Multi-Factor Authentication", "Multi-Language"}


def nav_labels():
    return {label for _c, items in gui_main.NAV_CATEGORIES for label, _h in items}


def cli_labels():
    return {label for _c, items in cli_main.CATEGORIES for label in items}


def principal(role, *, username="user", systems=None, dsl=False):
    if systems is None:
        systems = [{"system_key": "primary", "role": role}] if role else []
    auth = SimpleNamespace(current_user={"username": username, "systems": systems})
    with patch.object(access.POLICY, "_dsl_check", lambda _u, _e: dsl):
        return access.from_auth(auth)


SUPERADMIN_SYSTEMS = [
    {"system_key": key, "role": "admin"}
    for key in ("university", "sixth_form", "secondary", "primary")
]


@pytest.fixture(autouse=True)
def _no_staff_db_and_clean_state(monkeypatch):
    monkeypatch.setattr(access.POLICY, "_dsl_check", lambda _u, _e: False)
    access.set_current(access.POLICY.anonymous)
    yield
    access.set_current(access.POLICY.anonymous)
    switch.consume()


def test_every_policy_label_is_a_real_menu_entry():
    menu = nav_labels() | cli_labels()
    assert access.ADMIN_ONLY <= menu
    assert access.POLICY.dsl_only <= menu
    assert access.POLICY.raise_only <= menu
    assert ACCOUNT <= menu


@pytest.mark.parametrize("p", [
    principal("admin"),
    principal("student", systems=SUPERADMIN_SYSTEMS),
], ids=["admin", "superadmin"])
def test_admin_and_superadmin_keep_everything_in_order(p):
    assert p.filter_menu(gui_main.NAV_CATEGORIES) == gui_main.NAV_CATEGORIES
    assert p.filter_menu(cli_main.CATEGORIES) == cli_main.CATEGORIES
    assert all(p.can_open(label) for label in nav_labels() | cli_labels())
    assert p.can_view_safeguarding
    assert p.notice() == ""


@pytest.mark.parametrize("role", ["teacher", "staff"])
def test_staff_lose_only_the_admin_screens(role):
    p = principal(role)
    assert {label for label in nav_labels() if not p.can_open(label)} == (
        (access.ADMIN_ONLY | access.POLICY.dsl_only) & nav_labels())
    assert not p.can_open("Dinner Money")
    assert not p.can_open("User Management")
    assert not p.can_open("Settings")
    assert not p.can_open("Audit Reports")
    assert p.can_open("Behaviour Log")


def test_staff_keep_a_screen_the_matrix_does_not_mention():
    assert principal("teacher").can_open("A Screen Added Later")


def test_non_lead_teacher_can_only_raise_a_concern():
    p = principal("teacher")
    assert p.can_open("Safeguarding")
    assert p.opens_raise_only("Safeguarding")
    assert not p.can_open("Prevent Duty")


def test_lead_teacher_reads_safeguarding():
    p = principal("teacher", dsl=True)
    assert not p.opens_raise_only("Safeguarding")
    assert p.can_view_safeguarding
    assert p.can_open("Prevent Duty")


def test_lead_lookup_failure_fails_closed():
    auth = SimpleNamespace(current_user={
        "username": "t", "systems": [{"system_key": "primary", "role": "teacher"}]})
    with patch.object(access.POLICY, "_dsl_check", side_effect=OSError):
        assert not access.from_auth(auth).can_view_safeguarding


def test_lead_is_matched_by_staff_id_or_email_only():
    leads = [SimpleNamespace(staff_id="T1", email="lead@school.example")]
    with patch("education_system.systems.primary.domain.staff.staff.list_staff",
               return_value=leads):
        assert access._is_dsl("t1", None)
        assert access._is_dsl("someone", "LEAD@school.example")
        assert not access._is_dsl("someone", "other@school.example")


@pytest.mark.parametrize("role", ["student", "parent"])
def test_learners_get_only_their_account(role):
    p = principal(role)
    assert {label for label in nav_labels() if p.can_open(label)} == ACCOUNT
    assert not p.opens_raise_only("Safeguarding")
    assert p.notice()
    assert not p.has_staff_screens


@pytest.mark.parametrize("role", ["", "alumni", "instructor", "ADMINISTRATOR"])
def test_unknown_or_missing_role_opens_nothing(role):
    p = principal(role)
    assert p.filter_menu(gui_main.NAV_CATEGORIES) == []
    assert not p.can_open("Change Password")
    assert not p.can_open("A Screen Added Later")
    assert p.notice()


def test_no_session_opens_nothing():
    for auth in (None, SimpleNamespace(current_user=None),
                 SimpleNamespace(current_user={"role": "admin"})):
        assert access.from_auth(auth, "admin") is access.POLICY.anonymous


def test_a_role_from_another_system_does_not_count():
    auth = SimpleNamespace(current_user={
        "username": "u", "role": "admin",
        "systems": [{"system_key": "university", "role": "admin"}]})
    assert not access.from_auth(auth).can_open("Pupil Directory")


def test_the_accounts_own_role_beats_the_launcher_argument():
    auth = SimpleNamespace(current_user={
        "username": "u", "systems": [{"system_key": "primary", "role": "student"}]})
    assert not access.from_auth(auth, "admin").is_admin


def test_current_for_rederives_for_a_different_user():
    access.set_current(principal("admin", username="first"))
    auth = SimpleNamespace(current_user={
        "username": "second", "systems": [{"system_key": "primary", "role": "student"}]})
    assert access.current_for(auth).role == "student"


# ── GUI: the check where a screen opens ───────────────────────────────

def bare_gui(p):
    gui = object.__new__(gui_main.PrimarySchoolMainGUI)
    gui.principal = p
    gui._show_denied = MagicMock()
    return gui


def test_gui_refuses_a_screen_opened_directly():
    gui = bare_gui(principal("student"))
    gui._guard_screens()
    gui.open_pupil_directory()
    gui._show_denied.assert_called_once_with("Pupil Directory")


def test_gui_guards_an_open_method_with_no_menu_entry():
    gui = bare_gui(principal("student"))
    with patch.object(gui_main.PrimarySchoolMainGUI, "open_not_in_menu", MagicMock(), create=True) as screen:
        gui._guard_screens()
        gui.open_not_in_menu()
    screen.assert_not_called()
    gui._show_denied.assert_called_once()


def test_gui_lets_an_allowed_screen_through():
    p = principal("student")
    gui = bare_gui(p)
    with patch.object(gui_main.PrimarySchoolMainGUI, "open_change_password") as screen:
        gui._guard_screens()
        gui.open_change_password()
    screen.assert_called_once()
    gui._show_denied.assert_not_called()


def test_gui_stub_path_is_checked():
    gui = bare_gui(principal("parent"))
    gui._show_stub("Timetable")
    gui._show_denied.assert_called_once_with("Timetable")


# ── CLI ───────────────────────────────────────────────────────────────

def run_menu(p, answers):
    auth = MagicMock()
    auth.current_user = {"username": p.username, "systems": []}
    access.set_current(p)
    with patch.object(cli_main, "_prompt", side_effect=answers):
        cli_main._main_menu(auth)
    return auth


def test_cli_learner_menu_is_filtered_and_explains_itself(capsys):
    p = principal("student")
    run_menu(p, ["9", "l"])
    out = capsys.readouterr().out
    assert p.notice() in out
    assert "System" in out and "Pupil Management" not in out
    assert "Invalid selection." in out


def test_cli_admin_menu_is_unchanged(capsys):
    run_menu(principal("admin"), ["l"])
    out = capsys.readouterr().out
    for category, _items in cli_main.CATEGORIES:
        assert category in out


def test_cli_refuses_before_dispatching(capsys):
    access.set_current(principal("student"))
    auth = MagicMock()
    auth.current_user = {"username": "user"}
    with patch.object(cli_main, "_prompt", side_effect=["1", "0"]), \
            patch("education_system.platform.cross_system.journey_cli.dispatch") as dispatch:
        cli_main._submenu("Pupils", ["Pupil Directory"], auth=auth)
    dispatch.assert_not_called()
    assert "does not have access to Pupil Directory" in capsys.readouterr().out


def test_cli_non_lead_teacher_only_raises(capsys):
    access.set_current(principal("teacher"))
    auth = MagicMock()
    auth.current_user = {"username": "user"}
    with patch.object(cli_main, "_prompt", side_effect=["1", "0"]), \
            patch("education_system.systems.primary.interfaces.cli.safeguarding."
                  "safeguarding_cli.raise_concern") as raise_concern, \
            patch("education_system.systems.primary.interfaces.cli.safeguarding."
                  "safeguarding_cli.dispatch") as full_screen:
        cli_main._submenu("Pastoral", ["Safeguarding"], auth=auth)
    raise_concern.assert_called_once_with()
    full_screen.assert_not_called()


def test_run_uses_the_launcher_role():
    auth = MagicMock()
    auth.current_user = {"username": "u", "systems": []}
    with patch.object(cli_main, "run_authenticated", return_value=0):
        cli_main.run(role="parent", shared_auth=auth)
    assert access.current_for(auth).role == "parent"


def test_cli_idle_timeout_runs_the_logout_path(monkeypatch):
    monkeypatch.setenv("EDU_IDLE_TIMEOUT_MINUTES", "5")
    auth = MagicMock()
    auth.current_user = {"username": "u", "systems": []}

    def timed_out(_prompt=""):
        raise cli_helpers._IdleTimeoutSignal()

    with patch("builtins.input", timed_out), patch("signal.alarm"):
        assert cli_main.run_authenticated(auth) == 0
    auth.logout.assert_called_once_with()
    assert switch.consume() == ("__login__", "cli")
