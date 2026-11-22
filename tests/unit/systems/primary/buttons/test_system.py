"""The System category of the Primary School main menu, GUI and CLI.

Every entry (Change Password, Multi-Factor Authentication, User Accounts,
User Management, Settings, Compliance, Governance, Policies, GDPR, Risk
Management, Health & Safety, Assets, Multi-Language, To-Do, About) opens
on the sandbox without a stub or an error, in the window and in the
terminal. The data screens keep what is recorded through them, and a
teacher is refused the admin-only entries.

The four account screens talk to the platform ``auth.db``. Here they only
open and go back: nothing signs in, changes a password or enrols a second
factor. Their reads go to a sandbox ``auth.db`` set up by :func:`auth_db`
(the conftest's ``sqlite3.connect`` guard fails the test if anything
reaches the live one).
"""

from __future__ import annotations

import sqlite3
import tkinter as tk
from pathlib import Path

import pytest

from education_system.systems.primary import cli_main, gui_main
from education_system.systems.primary.domain import access

SYSTEM_LABELS = [
    "Change Password", "Multi-Factor Authentication",
    "User Accounts", "User Management",
    "Settings", "Compliance", "Governance", "Policies",
    "GDPR", "Risk Management", "Health & Safety", "Assets",
    "Multi-Language", "To-Do", "About",
]

HANDLERS = {
    "Change Password": "open_change_password",
    "Multi-Factor Authentication": "open_mfa",
    "User Accounts": "open_user_accounts",
    "User Management": "open_user_management",
    "Settings": "open_settings",
    "Compliance": "open_compliance",
    "Governance": "open_governance",
    "Policies": "open_policies",
    "GDPR": "open_gdpr",
    "Risk Management": "open_risk_management",
    "Health & Safety": "open_health_safety",
    "Assets": "open_assets",
    "Multi-Language": "open_multi_language",
    "To-Do": "open_todo",
    "About": "open_about",
}

#: Screens that read or write the platform auth.db.
AUTH_SCREENS = {"Change Password", "Multi-Factor Authentication",
                "User Accounts", "User Management"}
#: System entries only an admin may open.
ADMIN_ONLY_HERE = {"User Accounts", "User Management", "Settings"}

#: What shows once the GUI entry has opened: a page in the main window's
#: content area (the title passed to ``kit.show_page``; its heading is drawn
#: in the content frame and no Toplevel opens), a new window whose title
#: contains the text (the platform dialogs), a window class, a line of text
#: in the window, or the status bar.
GUI_OPENED = {
    "Change Password": ("toplevel", "Change Password"),
    # Matched on the window class: its title is translated, and the sandbox
    # can leave the i18n locale dir pointing at an empty folder.
    "Multi-Factor Authentication": ("window", "MFASetupWizard"),
    "User Accounts": ("page", "User Accounts"),
    "User Management": ("text", "Have primary access"),
    "Settings": ("page", "Settings"),
    "Compliance": ("page", "Compliance"),
    "Governance": ("page", "Governance"),
    "Policies": ("page", "Policies"),
    "GDPR": ("page", "GDPR"),
    "Risk Management": ("page", "Risk Management"),
    "Health & Safety": ("page", "Health & Safety"),
    "Assets": ("page", "Assets"),
    "Multi-Language": ("toplevel", "Select Language"),
    "To-Do": ("page", "To-Do"),
    "About": ("page", "About"),
}


def _page_heading(title: str) -> str:
    """The heading a page draws: its title, except About, which is headed by
    the system's name."""
    if title == "About":
        from education_system.systems.primary.interfaces import about as about_data
        return about_data.SYSTEM_NAME
    return title


def _assert_page(gui, title: str, page_text, toplevels) -> None:
    """*title* is showing as a page in the content area, not in a window."""
    assert toplevels(gui) == [], [w.title() for w in toplevels(gui)]
    assert gui._current_page and gui._current_page[0] == title, gui._current_page
    assert gui.status_var.get() == f"Opened: {title}"
    assert _page_heading(title) in page_text(gui).splitlines()

#: The heading each CLI entry prints when its menu opens.
CLI_HEADER = {
    "Change Password": "═══ Change Password ═══",
    "Multi-Factor Authentication": "── Multi-Factor Authentication ──",
    "User Accounts": "── User Accounts ──",
    "User Management": "── User Management ──",
    "Settings": "── Settings ──",
    "Compliance": "── Compliance ──",
    "Governance": "── Governance ──",
    "Policies": "── Policies ──",
    "GDPR": "── GDPR ──",
    "Risk Management": "── Risk Management ──",
    "Health & Safety": "── Health & Safety ──",
    "Assets": "── Assets ──",
    "Multi-Language": "Select Language",
    "To-Do": "── To-Do ──",
    "About": "System key    : primary",
}

#: Extra answers an entry needs before "0" backs out. Change Password reads
#: the current password first; "cancel" there aborts without a change.
CLI_EXTRA = {"Change Password": ["cancel"]}

#: Printed when a CLI entry failed or is not wired.
CLI_FAILURES = ("[stub]", "not yet implemented", "Traceback", "Error opening",
                "Unexpected error", "LiveDataTouched", "no such table")

BACK = ["0", ""] * 20


def _system_items() -> list[str]:
    return dict(cli_main.CATEGORIES)["System"]


def _nav_items() -> list[tuple[str, str]]:
    return dict(gui_main.NAV_CATEGORIES)["System"]


def _choice(label: str) -> str:
    return str(_system_items().index(label) + 1)


def _run_cli(label, auth, scripted_input, capsys, after=()) -> str:
    """Open *label* from the System sub-menu, answer *after*, back out."""
    scripted_input([_choice(label), *after, *BACK])
    cli_main._submenu("System", _system_items(), auth=auth)
    return capsys.readouterr().out


def _assert_cli_ok(out: str) -> None:
    for bad in CLI_FAILURES:
        assert bad not in out, f"{bad!r} in output:\n{out[-3000:]}"


def _tree_rows(widget) -> list[tuple]:
    """Every row of every Treeview under *widget*."""
    rows: list[tuple] = []
    if isinstance(widget, tk.ttk.Treeview):
        rows.extend(tuple(widget.item(i, "values")) for i in widget.get_children(""))
    for child in widget.winfo_children():
        rows.extend(_tree_rows(child))
    return rows


@pytest.fixture
def no_modal_wait(monkeypatch):
    """Modal dialogs (MFA wizard, language picker) wait for the window to
    close and grab the pointer; in a test the dialog is built and left open."""
    monkeypatch.setattr(tk.Misc, "wait_window", lambda self, window=None: None)
    monkeypatch.setattr(tk.Misc, "grab_set", lambda self: None)


@pytest.fixture
def auth_db(primary_sandbox, fake_auth, staff_auth, tmp_path):
    """A sandbox ``auth.db`` with the platform schema and two accounts:
    ``admin3`` (primary admin, secondary teacher) and ``sec_only``
    (secondary only). Both fake sessions get a real ``RoleManager`` on it."""
    from education_system.platform.identity.auth.role_manager import RoleManager
    from education_system.platform.identity.auth.schema import initialise_auth_db

    path = Path(primary_sandbox.PLATFORM_AUTH_DB).resolve()
    assert tmp_path.resolve() in path.parents, f"auth.db not sandboxed: {path}"
    initialise_auth_db(str(path))
    conn = sqlite3.connect(str(path))
    try:
        for username, systems in (("admin3", [("primary", "admin"), ("secondary", "teacher")]),
                                  ("sec_only", [("secondary", "teacher")])):
            cur = conn.execute(
                "INSERT INTO users (username, password_hash, display_name, email) "
                "VALUES (?, 'x', ?, ?)", (username, username.title(), f"{username}@example.test"))
            for system_key, role in systems:
                conn.execute("INSERT INTO user_systems (user_id, system_key, role) VALUES (?, ?, ?)",
                             (cur.lastrowid, system_key, role))
        conn.commit()
    finally:
        conn.close()
    for auth in (fake_auth, staff_auth):
        auth.role_manager = RoleManager(str(path))
    return path


@pytest.fixture
def no_language_change(monkeypatch):
    """Record language changes instead of saving them (the i18n config file
    is a JSON file, not a database, so the sqlite guard would not catch it)."""
    from education_system.platform.features.i18n import selector_cli, selector_gui

    chosen: list[str] = []

    def record(code, save=True):
        chosen.append(code)
        return True

    monkeypatch.setattr(selector_cli, "set_language", record)
    monkeypatch.setattr(selector_gui, "set_language", record)
    return chosen


# ── Catalogue ────────────────────────────────────────────────────────

def test_gui_system_category_lists_every_entry() -> None:
    assert [label for label, _h in _nav_items()] == SYSTEM_LABELS
    assert dict(_nav_items()) == HANDLERS


@pytest.mark.parametrize("label", SYSTEM_LABELS)
def test_gui_handler_is_a_real_method(label: str) -> None:
    method = getattr(gui_main.PrimarySchoolMainGUI, HANDLERS[label], None)
    assert callable(method), f"{label}: {HANDLERS[label]} is missing"


def test_cli_system_category_matches_the_gui() -> None:
    assert _system_items() == SYSTEM_LABELS


# ── GUI: every entry opens ───────────────────────────────────────────

@pytest.mark.gui
@pytest.mark.parametrize("label", SYSTEM_LABELS)
def test_gui_entry_opens(label, auth_db, no_modal_wait, no_language_change,
                         primary_gui, content_text, page_text, toplevels) -> None:
    gui = primary_gui
    getattr(gui, HANDLERS[label])()
    gui.root.update_idletasks()

    text = content_text(gui)
    assert "not yet implemented" not in text
    assert "does not have access" not in text
    assert not [m for m in gui.messages if m[0] == "showerror"], gui.messages
    kind, expected = GUI_OPENED[label]
    if kind == "page":
        _assert_page(gui, expected, page_text, toplevels)
    elif kind == "toplevel":
        titles = [w.title() for w in toplevels(gui)]
        assert any(expected in t for t in titles), titles
    elif kind == "window":
        assert expected in [type(w).__name__ for w in toplevels(gui)]
    elif kind == "status":
        assert expected in gui.status_var.get()
    else:
        assert expected in text
    assert no_language_change == []


# ── CLI: every entry opens and goes back ─────────────────────────────

@pytest.mark.parametrize("label", SYSTEM_LABELS)
def test_cli_entry_opens_and_goes_back(label, auth_db, fake_auth, admin_principal,
                                       no_language_change, scripted_input, capsys) -> None:
    out = _run_cli(label, fake_auth, scripted_input, capsys, CLI_EXTRA.get(label, ()))
    assert "── System ──" in out
    assert CLI_HEADER[label] in out, out[-3000:]
    _assert_cli_ok(out)
    assert no_language_change == []


def test_cli_unknown_choice_is_refused(fake_auth, admin_principal, scripted_input, capsys) -> None:
    scripted_input(["99", "abc", "0"])
    cli_main._submenu("System", _system_items(), auth=fake_auth)
    assert capsys.readouterr().out.count("Invalid selection.") == 2


# ── Account screens: primary wording, no changes ─────────────────────

def test_account_screens_use_the_primary_system_key() -> None:
    from education_system.systems.primary.domain.governance.user_management import user_management
    from education_system.systems.primary.interfaces import user_accounts

    assert user_accounts.SYSTEM_KEY == "primary"
    assert user_management.SYSTEM_KEY == "primary"
    assert access.SYSTEM_KEY == "primary"


def test_known_systems_lists_all_seven_with_primary_first() -> None:
    from education_system.systems.primary.domain.governance.user_management import user_management

    known = user_management.KNOWN_SYSTEMS
    assert known[0] == "primary"
    assert len(known) == len(set(known)) == 7
    assert set(known) == {"primary", "nursery", "secondary", "sixth_form",
                          "fe_college", "apprenticeships", "university"}


def test_access_matrix_reads_the_sandbox_auth_db(auth_db, fake_auth) -> None:
    from education_system.systems.primary.domain.governance.user_management import user_management

    matrix = user_management.access_matrix(fake_auth)
    systems = [s.system_key for s in matrix.systems]
    assert systems == ["primary", "secondary"]          # known order, primary first
    assert matrix.systems[0].by_role == {"admin": 1}
    assert [u.username for u in matrix.users_without_primary] == ["sec_only"]


@pytest.mark.parametrize("label", ["User Accounts", "User Management"])
def test_cli_account_menus_say_primary_school(label, auth_db, fake_auth, admin_principal,
                                              scripted_input, capsys) -> None:
    out = _run_cli(label, fake_auth, scripted_input, capsys)
    _assert_cli_ok(out)
    assert "Primary-" in out
    for other in ("Secondary-school", "Sixth-form", "sixth form", "Sixth Form"):
        assert other not in out


def test_cli_user_accounts_lists_primary_users_only(auth_db, fake_auth, admin_principal,
                                                    scripted_input, capsys) -> None:
    # 1) Primary-School Users, then Enter / back out.
    out = _run_cli("User Accounts", fake_auth, scripted_input, capsys, ["1"])
    _assert_cli_ok(out)
    assert "admin3" in out
    assert "sec_only" not in out


def test_cli_user_management_summary_counts_the_sandbox(auth_db, fake_auth, admin_principal,
                                                        scripted_input, capsys) -> None:
    # 1) Summary.
    out = _run_cli("User Management", fake_auth, scripted_input, capsys, ["1"])
    _assert_cli_ok(out)
    assert "Primary-school users      : 1" in out


@pytest.mark.gui
@pytest.mark.parametrize("label", ["User Accounts", "User Management"])
def test_gui_account_screens_say_primary_school(label, auth_db, primary_gui,
                                                content_text) -> None:
    getattr(primary_gui, HANDLERS[label])()
    primary_gui.root.update_idletasks()
    text = content_text(primary_gui)
    assert "Primary-school" in text
    for other in ("Secondary-school", "Sixth-form", "sixth form"):
        assert other not in text


@pytest.mark.gui
def test_gui_user_accounts_lists_the_sandbox_primary_user(auth_db, primary_gui, toplevels) -> None:
    primary_gui.open_user_accounts()
    primary_gui.root.update_idletasks()
    assert toplevels(primary_gui) == []                 # a page, not a window
    rows = _tree_rows(primary_gui.content_frame)
    usernames = {v for r in rows for v in r}
    assert "admin3" in usernames
    assert "sec_only" not in usernames                  # "Primary-school only" is ticked


def test_cli_change_password_cancel_changes_nothing(auth_db, fake_auth, admin_principal,
                                                    scripted_input, capsys, monkeypatch) -> None:
    from education_system.platform.delivery.cli import change_password_cli

    calls: list = []
    monkeypatch.setattr(change_password_cli, "change_password",
                        lambda *a, **k: calls.append((a, k)))
    out = _run_cli("Change Password", fake_auth, scripted_input, capsys, ["cancel"])
    assert "Signed in as: admin3" in out and "Cancelled." in out
    assert calls == []


def test_cli_mfa_shows_status_from_the_sandbox(auth_db, fake_auth, admin_principal,
                                               scripted_input, capsys) -> None:
    out = _run_cli("Multi-Factor Authentication", fake_auth, scripted_input, capsys)
    _assert_cli_ok(out)
    assert "Signed in: admin3" in out
    assert "Status:    disabled" in out
    assert "(none enrolled)" in out


# ── Settings ─────────────────────────────────────────────────────────

def test_cli_settings_edit_saves_to_the_sandbox(primary_sandbox, tmp_path, fake_auth,
                                                admin_principal, scripted_input,
                                                capsys) -> None:
    from education_system.systems.primary.interfaces import settings

    db = Path(settings.DB_PATH).resolve()
    assert tmp_path.resolve() in db.parents
    assert settings.get("attendance.threshold_pct") == 90.0

    # 5) Edit one → by key → new value → Enter.
    out = _run_cli("Settings", fake_auth, scripted_input, capsys,
                   ["5", "attendance.threshold_pct", "85", ""])
    _assert_cli_ok(out)
    assert "→ 85" in out
    assert settings.get("attendance.threshold_pct") == 85.0
    conn = sqlite3.connect(str(db))
    try:
        stored = conn.execute("SELECT value FROM settings_kv WHERE key = ?",
                              ("attendance.threshold_pct",)).fetchone()
    finally:
        conn.close()
    assert stored is not None and float(stored[0]) == 85.0

    # 2) Show local only reads it back.
    out = _run_cli("Settings", fake_auth, scripted_input, capsys, ["2", ""])
    assert "(default: 90.0)" in out

    assert settings.reset_to_default("attendance.threshold_pct") == 90.0
    assert settings.get("attendance.threshold_pct") == 90.0


def test_settings_global_needs_a_real_session(primary_sandbox) -> None:
    from education_system.systems.primary.interfaces import settings

    with pytest.raises(settings.SettingError):
        settings.set("max_login_attempts", 7)


# ── To-Do ────────────────────────────────────────────────────────────

def test_cli_todo_new_then_listed(fake_auth, admin_principal, scripted_input, capsys) -> None:
    from education_system.systems.primary.domain.operations.todo import todo

    # 8) New To-Do: title, description, owner, assignee, status, priority,
    # category, due date, Enter. Then 2) All To-Dos and Enter.
    out = _run_cli("To-Do", fake_auth, scripted_input, capsys,
                   ["8", "Write Year 3 reports", "", "admin3", "", "", "", "", "", "",
                    "2", ""])
    _assert_cli_ok(out)
    assert "Created todo #" in out
    listing = out.split("═══ All To-Dos ═══")[-1]
    assert "Write Year 3 reports" in listing and "1 todo(s)." in listing
    [row] = todo.list_todos()
    assert (row.title, row.owner, row.is_open) == ("Write Year 3 reports", "admin3", True)


@pytest.mark.gui
def test_gui_todo_board_shows_an_open_todo(no_modal_wait, primary_gui, content_text) -> None:
    from education_system.systems.primary.domain.operations.todo import todo

    todo.create_todo({"title": "Order phonics books", "owner": "admin3"})
    primary_gui.open_todo()
    primary_gui.root.update_idletasks()
    assert "Order phonics books" in content_text(primary_gui)


# ── Risk / Assets / Health & Safety ──────────────────────────────────

def test_cli_risk_management_lists_a_recorded_risk(fake_auth, admin_principal,
                                                   scripted_input, capsys) -> None:
    from education_system.systems.primary.domain.governance.risk_management import risk_management

    risk = risk_management.create_risk({"title": "Playground surface worn",
                                        "owner": "admin3", "likelihood": 4, "impact": 4})
    assert risk.inherent_score == 16
    # 5) All Risks.
    out = _run_cli("Risk Management", fake_auth, scripted_input, capsys, ["5", ""])
    _assert_cli_ok(out)
    assert "Playground surface worn" in out
    assert "1 risk(s)." in out


def test_cli_assets_lists_a_recorded_asset(fake_auth, admin_principal,
                                           scripted_input, capsys) -> None:
    from education_system.systems.primary.domain.operations.assets import assets

    assets.create_asset({"asset_tag": "PS-IPAD-01", "name": "Class iPad",
                         "location": "Year 2 classroom"})
    # 1) List all.
    out = _run_cli("Assets", fake_auth, scripted_input, capsys, ["1", ""])
    _assert_cli_ok(out)
    assert "PS-IPAD-01" in out and "Class iPad" in out
    assert "1 asset(s)." in out


def test_cli_health_safety_lists_a_recorded_incident(fake_auth, admin_principal,
                                                     scripted_input, capsys) -> None:
    from education_system.systems.primary.domain.governance.health_safety import health_safety as hs

    hs.create_incident({"incident_date": "2026-10-01", "location": "Hall",
                        "category": hs.CATEGORIES[0], "severity": hs.SEVERITIES[0],
                        "incident_type": hs.INCIDENT_TYPES[0],
                        "description": "Wet floor by the hall doors"})
    # 1) List all.
    out = _run_cli("Health & Safety", fake_auth, scripted_input, capsys, ["1", ""])
    _assert_cli_ok(out)
    assert "Hall" in out and "1 incident(s)." in out
    assert [i.description for i in hs.list_incidents()] == ["Wet floor by the hall doors"]


# ── Compliance ───────────────────────────────────────────────────────

def test_cli_compliance_lists_a_recorded_item(fake_auth, admin_principal,
                                              scripted_input, capsys) -> None:
    from education_system.systems.primary.domain.governance.compliance import compliance

    compliance.create_item({"title": "Fire drill log", "owner": "admin3",
                            "category": "Health & Safety"})
    # 1) List All.
    out = _run_cli("Compliance", fake_auth, scripted_input, capsys, ["1", ""])
    _assert_cli_ok(out)
    assert "Fire drill log" in out


# ── Multi-Language / About ───────────────────────────────────────────

def test_cli_multi_language_picks_a_language(fake_auth, admin_principal, scripted_input,
                                             capsys, no_language_change) -> None:
    out = _run_cli("Multi-Language", fake_auth, scripted_input, capsys, ["2"])
    _assert_cli_ok(out)
    assert "Language set to: Español (Spanish)" in out
    assert no_language_change == ["es"]


def test_about_counts_real_primary_tables(primary_sandbox, tmp_path, fake_auth) -> None:
    from education_system.systems.primary.domain.academics.subjects import subjects
    from education_system.systems.primary.domain.learners.pupils import pupils
    from education_system.systems.primary.interfaces import about

    pupils.init_db()
    subjects.create({"code": "MATH", "name": "Maths", "key_stage": "KS2"})
    info = about.build(auth=fake_auth)
    assert tmp_path.resolve() in Path(info.db_path).resolve().parents
    assert info.system_key == "primary" and info.current_user == "admin3"
    stats = {s.table: s.rows for s in info.table_stats}
    assert stats["pupils"] == 0
    assert stats["subjects"] == 1


def test_about_stats_name_tables_the_primary_schema_creates() -> None:
    """Every table About counts is created by a primary domain module, so the
    row is a count, not a permanent dash."""
    import re

    from education_system.systems.primary.interfaces import about

    root = Path(about.__file__).resolve().parents[1] / "domain"
    source = "\n".join(p.read_text(encoding="utf-8") for p in root.rglob("*.py"))
    created = set(re.findall(r'CREATE TABLE IF NOT EXISTS\s+"?(\w+)"?', source))
    missing = [t for t, _label in about._STATS_TABLES if t not in created]
    assert missing == []


def test_cli_about_shows_the_sandbox_database(primary_sandbox, tmp_path, fake_auth,
                                              admin_principal, scripted_input, capsys) -> None:
    out = _run_cli("About", fake_auth, scripted_input, capsys)
    _assert_cli_ok(out)
    assert "Signed in as  : admin3" in out
    assert str(tmp_path.resolve()) in out


# ── Access ───────────────────────────────────────────────────────────

def test_admin_only_system_entries() -> None:
    assert ADMIN_ONLY_HERE <= access.ADMIN_ONLY
    assert not (set(SYSTEM_LABELS) - ADMIN_ONLY_HERE) & access.ADMIN_ONLY


@pytest.mark.parametrize("label", SYSTEM_LABELS)
def test_teacher_may_open_only_the_non_admin_entries(label, staff_principal,
                                                     admin_principal) -> None:
    assert admin_principal.can_open(label)
    assert staff_principal.can_open(label) is (label not in ADMIN_ONLY_HERE)


def test_teacher_menus_hide_the_admin_only_entries(staff_principal) -> None:
    cli = dict(staff_principal.visible_menu(cli_main.CATEGORIES, labels_only=True))["System"]
    gui = [label for label, _h in dict(staff_principal.visible_menu(gui_main.NAV_CATEGORIES))["System"]]
    expected = [label for label in SYSTEM_LABELS if label not in ADMIN_ONLY_HERE]
    assert cli == expected
    assert gui == expected


@pytest.mark.parametrize("label", sorted(ADMIN_ONLY_HERE))
def test_cli_teacher_is_refused_admin_only(label, staff_auth, staff_principal,
                                           scripted_input, capsys) -> None:
    out = _run_cli(label, staff_auth, scripted_input, capsys)
    assert f"Your account does not have access to {label}." in out
    assert CLI_HEADER[label] not in out


@pytest.mark.parametrize("label", ["Change Password", "Multi-Factor Authentication",
                                   "To-Do", "About"])
def test_cli_teacher_may_open_the_rest(label, auth_db, staff_auth, staff_principal,
                                       scripted_input, capsys) -> None:
    out = _run_cli(label, staff_auth, scripted_input, capsys, CLI_EXTRA.get(label, ()))
    assert "does not have access" not in out
    assert CLI_HEADER[label] in out
    _assert_cli_ok(out)


@pytest.mark.gui
@pytest.mark.parametrize("label", sorted(ADMIN_ONLY_HERE))
def test_gui_teacher_is_refused_admin_only(label, primary_gui, staff_principal,
                                           content_text, toplevels) -> None:
    primary_gui.principal = staff_principal
    getattr(primary_gui, HANDLERS[label])()
    primary_gui.root.update_idletasks()
    assert f"Your account does not have access to {label}." in content_text(primary_gui)
    assert toplevels(primary_gui) == []
    assert primary_gui.status_var.get() == "Not available for this account"


@pytest.mark.gui
@pytest.mark.parametrize("label", ["Change Password", "Multi-Factor Authentication",
                                   "To-Do", "Risk Management"])
def test_gui_teacher_may_open_the_rest(label, auth_db, no_modal_wait, primary_gui,
                                       staff_principal, content_text, page_text,
                                       toplevels) -> None:
    primary_gui.principal = staff_principal
    getattr(primary_gui, HANDLERS[label])()
    primary_gui.root.update_idletasks()
    assert "does not have access" not in content_text(primary_gui)
    kind, expected = GUI_OPENED[label]
    windows = toplevels(primary_gui)
    if kind == "page":
        _assert_page(primary_gui, expected, page_text, toplevels)
    elif kind == "window":
        assert expected in [type(w).__name__ for w in windows]
    else:
        assert any(expected in w.title() for w in windows)
