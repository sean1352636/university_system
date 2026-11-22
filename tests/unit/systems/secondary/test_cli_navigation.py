"""Terminal navigation (app.cli_main, app.bootstrap) on scratch databases.

The main menu lists the categories the role may open, a category opens its
sub-menu, every sidebar entry's terminal menu opens and goes back again
without an error, restricted entries are refused, and Logout / Switch to
GUI / Shut down end the session the way the launcher expects. Input is fed
from a script; a menu that keeps asking after the script runs out fails
the test instead of hanging.
"""

from __future__ import annotations

import builtins

import pytest

from education_system import switch
from education_system.systems.secondary.app import bootstrap, cli_main, routing
from education_system.systems.secondary.core.permissions import access
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.database import connection as database
from education_system.systems.secondary.infrastructure.logging import activity_log

ADMIN = Principal(username="admin2", role="admin")
TEACHER = Principal(username="ann", role="teacher")

#: Entries handed to the platform's own screens (they talk to auth.db);
#: checked to be wired, not run.
PLATFORM = {"change_password", "mfa"}
#: Sidebar entries with no screen yet - "hasn't been built yet". Remove a
#: key here when it is built (the test fails until you do).
NOT_BUILT = {"year6_transition"}


class FakeAuth:
    def __init__(self, principal: Principal) -> None:
        self.current_user = {"username": principal.username, "role": principal.role, "id": 1}
        self.logged_out = 0

    def logout(self) -> None:
        self.logged_out += 1


class OutOfInput(BaseException):
    """The script ran out: the menu didn't go back (BaseException, so the
    menu's own ``except Exception`` can't swallow it)."""


@pytest.fixture(autouse=True)
def scratch(tmp_path):
    from education_system.platform.identity.auth.schema import initialise_auth_db
    database.use_database(tmp_path / "secondary.db")
    accounts.use_auth_db(tmp_path / "auth.db")
    initialise_auth_db(str(tmp_path / "auth.db"))
    activity_log.use_log_file(tmp_path / "activity.log")
    yield tmp_path
    activity_log.end_session("test_end")
    database.use_database(None)
    accounts.use_auth_db(None)
    activity_log.use_log_file(None)


@pytest.fixture
def switches(monkeypatch):
    """What the menu asked the launcher to do next."""
    asked: list[tuple] = []
    monkeypatch.setattr(switch, "request_logout", lambda mode="gui": asked.append(("logout", mode)))
    monkeypatch.setattr(switch, "request_switch", lambda system, mode: asked.append(
        ("switch", system, mode)))
    monkeypatch.setattr(switch, "request_exit", lambda: asked.append(("exit",)))
    return asked


@pytest.fixture
def feed(monkeypatch):
    """``feed(answers)`` scripts input(); returns the list of prompts seen."""
    def start(answers):
        answers = list(answers)
        prompts: list[str] = []

        def fake_input(prompt=""):
            prompts.append(str(prompt))
            if not answers:
                raise OutOfInput(f"still asking after the script: {prompt!r}")
            return answers.pop(0)
        monkeypatch.setattr(builtins, "input", fake_input)
        return prompts
    return start


def _log(tmp_path) -> str:
    return (tmp_path / "activity.log").read_text(encoding="utf-8")


def _categories(principal: Principal):
    return access.visible_categories(principal, routing.CATEGORIES)


# ── Main menu ────────────────────────────────────────────────────────

def test_main_menu_lists_the_categories_and_logs_out(feed, switches, capsys) -> None:
    feed(["L"])
    auth = FakeAuth(ADMIN)
    cli_main._main_menu(auth, ADMIN)
    out = capsys.readouterr().out
    for i, (category, _items) in enumerate(_categories(ADMIN), 1):
        assert f"{i:2d}) {category}" in out
    assert "M) My Day" in out and "L) Logout" in out and "Q) Shut down" in out
    assert "S) Switch System" not in out             # superadmin only
    assert switches == [("logout", "cli")] and auth.logged_out == 1


def test_invalid_choices_are_refused_and_the_menu_stays(feed, switches, capsys) -> None:
    feed(["99", "x", "L"])
    cli_main._main_menu(FakeAuth(ADMIN), ADMIN)
    assert capsys.readouterr().out.count("Invalid selection.") == 2
    assert switches == [("logout", "cli")]


def test_category_submenu_lists_its_entries_and_goes_back(feed, switches, scratch,
                                                          capsys) -> None:
    category, items = _categories(ADMIN)[0]
    feed(["1", "0", "L"])
    cli_main._main_menu(FakeAuth(ADMIN), ADMIN)
    out = capsys.readouterr().out
    assert f"── {category} ──" in out
    for i, (label, _key) in enumerate(items, 1):
        assert f"{i:2d}) {label}" in out
    assert f"menu.category | target={category}" in _log(scratch)


def test_an_entry_opens_from_its_category(feed, switches, scratch) -> None:
    for c, (category, items) in enumerate(_categories(ADMIN), 1):
        keys = [k for _l, k in items]
        if "behaviour" in keys:
            break
    item = keys.index("behaviour") + 1
    feed([str(c), str(item), "0", "", "0", "", "0", "L"])
    cli_main._main_menu(FakeAuth(ADMIN), ADMIN)
    assert "menu.open | target=Behaviour & Rewards | outcome=ok" in _log(scratch)


def test_my_day_opens_from_the_main_menu(feed, switches, scratch) -> None:
    feed(["M", "", "L"])
    cli_main._main_menu(FakeAuth(ADMIN), ADMIN)
    assert "menu.open | target=Staff Portal | outcome=ok" in _log(scratch)


def test_switch_to_gui_hands_back_to_the_launcher(feed, switches, scratch) -> None:
    auth = FakeAuth(ADMIN)
    bootstrap.start_session(auth, None, "cli")
    feed(["G"])
    cli_main._main_menu(auth, ADMIN)
    assert switches == [("switch", "secondary", "gui")] and auth.logged_out == 0
    assert "reason=switch_to_gui" in _log(scratch)


def test_shut_down_asks_first(feed, switches, scratch) -> None:
    auth = FakeAuth(ADMIN)
    bootstrap.start_session(auth, None, "cli")
    feed(["Q", "n", "Q", "y"])
    cli_main._main_menu(auth, ADMIN)
    assert switches == [("exit",)] and auth.logged_out == 1
    assert "reason=shutdown" in _log(scratch)


# ── Every sidebar entry ──────────────────────────────────────────────

_ENTRIES = [(label, key) for label, key in routing.all_entries() if key not in PLATFORM]


@pytest.mark.parametrize(("label", "key"), _ENTRIES, ids=[k for _l, k in _ENTRIES])
def test_every_sidebar_entry_opens_and_goes_back(feed, switches, scratch, capsys,
                                                 label: str, key: str) -> None:
    # "0" backs out of a numbered menu, Enter out of a prompt ("Enter to go back").
    feed(["0", ""] * 20)
    cli_main._open(key, label, FakeAuth(ADMIN), ADMIN)
    out = capsys.readouterr().out
    assert "could not be opened" not in out, out[-2000:]
    assert "outcome=error" not in _log(scratch)
    if key in NOT_BUILT:
        assert "hasn't been built yet" in out
    else:
        assert "hasn't been built yet" not in out, \
            f"{label} is not built - add it to NOT_BUILT or build it"
        assert f"menu.open | target={label} | outcome=ok" in _log(scratch)


@pytest.mark.parametrize("key", sorted(PLATFORM))
def test_platform_entries_are_wired(key: str) -> None:
    assert cli_main._handler_for(key) is cli_main._HANDLERS[key]


def test_every_entry_has_a_handler_unless_not_built() -> None:
    missing = {key for _label, key in routing.all_entries()
               if cli_main._handler_for(key) is None}
    assert missing == NOT_BUILT


def test_a_failing_menu_is_reported_and_the_menu_stays(feed, switches, scratch, capsys,
                                                       monkeypatch) -> None:
    def boom(_auth, _principal):
        raise ValueError("broken screen")
    monkeypatch.setitem(cli_main._HANDLERS, "about", boom)
    feed([""])
    cli_main._open("about", "About", FakeAuth(ADMIN), ADMIN)
    assert "About could not be opened: broken screen" in capsys.readouterr().out
    assert "outcome=error | error=ValueError" in _log(scratch)


# ── Access ───────────────────────────────────────────────────────────

def test_teacher_menu_hides_restricted_entries(feed, switches, capsys) -> None:
    restricted = {label for label, _key in routing.all_entries() if not TEACHER.can_open(label)}
    assert restricted, "no restricted entries to check"
    shown = {label for _c, items in _categories(TEACHER) for label, _key in items}
    assert not shown & restricted


def test_teacher_is_refused_a_restricted_entry(feed, switches, scratch, capsys) -> None:
    label, key = next((label, key) for label, key in routing.all_entries()
                      if not TEACHER.can_open(label))
    feed([])
    cli_main._open(key, label, FakeAuth(TEACHER), TEACHER)
    assert "doesn't have access" in capsys.readouterr().out
    assert f"menu.open | target={label} | outcome=denied" in _log(scratch)


# ── run() / bootstrap ────────────────────────────────────────────────

def test_run_refuses_without_the_launchers_session() -> None:
    with pytest.raises(RuntimeError, match="CLI must be launched via python -m education_system"):
        cli_main.run(shared_auth=None)
    with pytest.raises(RuntimeError, match="CLI must be launched"):
        cli_main.run(shared_auth=object())                     # no current_user


def test_run_for_staff_starts_a_session_and_shows_the_menu(feed, switches, scratch,
                                                           monkeypatch, capsys) -> None:
    monkeypatch.setattr(bootstrap, "roll_year_if_due", lambda _p: [])
    feed(["L"])
    assert cli_main.run(shared_auth=FakeAuth(ADMIN), role="admin") == 0
    assert f"=== {cli_main.SYSTEM_NAME} ===" in capsys.readouterr().out
    log = _log(scratch)
    assert "user=admin2 | role=admin | cli | session.start" in log
    assert "reason=logout" in log and switches == [("logout", "cli")]


def test_run_refuses_a_login_with_no_school_role(feed, switches, scratch, capsys) -> None:
    feed([])
    assert cli_main.run(shared_auth=FakeAuth(Principal("visitor", "guest"))) == 0
    assert "only for school staff" in capsys.readouterr().out
    assert "reason=refused_not_staff" in _log(scratch)


def test_pupils_and_parents_get_their_portal(feed, switches, monkeypatch) -> None:
    from education_system.systems.secondary.modules.portals.cli import portal_cli
    seen = []
    monkeypatch.setattr(portal_cli, "menu", lambda auth, principal: seen.append(
        principal.role) or "logout")
    for role in ("student", "parent"):
        auth = FakeAuth(Principal(f"{role}1", role))
        assert cli_main.run(shared_auth=auth, role=role) == 0
    assert seen == ["student", "parent"]
    assert switches == [("logout", "cli"), ("logout", "cli")]


def test_year_end_rollover_runs_at_staff_start_up(feed, switches, monkeypatch, capsys) -> None:
    class Rolled:
        def summary(self):
            return "Moved everyone up a year"
    calls = []
    monkeypatch.setattr(bootstrap, "roll_year_if_due",
                        lambda principal: calls.append(principal.username) or [Rolled()])
    feed(["L"])
    cli_main.run(shared_auth=FakeAuth(ADMIN), role="admin")
    assert calls == ["admin2"] and "Moved everyone up a year" in capsys.readouterr().out
