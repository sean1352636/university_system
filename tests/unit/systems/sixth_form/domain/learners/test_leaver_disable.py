"""Closing a leaver's logins down — and, more importantly, not closing
down the ones that belong to somebody else.

Two rules, and both are guards rather than actions:

* A learner's own login is disabled only when the sixth form was the
  last thing on it. Shared auth means that row is a *person*, who may
  also be a parent, part-time staff or superadmin, and blanket-disabling
  took all of that with it — which is why the code stopped doing it once
  before.
* A parent login is disabled only when every learner it can see has
  gone. One account routinely covers siblings, and cutting a parent off
  from a child still at the college is a worse failure than leaving a
  login open a little too long.

Both run at two different moments now — when the university confirms a
place, and again at handover — so the sibling rule cannot key on the
leaver's own status. The tests below pin that, because the obvious
implementation passes at handover and silently never fires at
confirmation.
"""

from __future__ import annotations

import sqlite3

import pytest

#: The parent-portal tables as they actually exist in the field: the
#: ``contact_id`` column came later and databases created before it
#: never got it, which is why ``parent_portal.init_db()`` cannot run
#: against them. Created here in that older shape deliberately — the
#: disable rules have to work on the databases that exist, not the ones
#: the schema file describes.
_PARENT_DDL = """
CREATE TABLE IF NOT EXISTS parent_accounts (
    account_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    full_name     TEXT NOT NULL,
    email         TEXT,
    password_hash TEXT NOT NULL,
    password_salt TEXT NOT NULL,
    is_active     INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS parent_student_links (
    account_id   INTEGER NOT NULL,
    student_id   TEXT NOT NULL,
    relationship TEXT NOT NULL DEFAULT 'Parent',
    PRIMARY KEY (account_id, student_id)
);
CREATE TABLE IF NOT EXISTS ucas_applications (
    application_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id     TEXT NOT NULL,
    cycle_year     INTEGER NOT NULL,
    status         TEXT NOT NULL DEFAULT 'Draft'
);
"""


@pytest.fixture
def sf(tmp_path, monkeypatch):
    """Two learners on a throwaway database, with parent tables."""
    from education_system.systems.sixth_form.domain.learners.students import (
        students as sd,
    )
    db = str(tmp_path / "sixthform.db")
    monkeypatch.setattr(sd, "DB_PATH", db, raising=False)
    monkeypatch.setattr(sd, "_DB_READY", False, raising=False)
    sd.init_db()

    conn = sqlite3.connect(db)
    conn.executescript(_PARENT_DDL)
    for sid, first in (("SF001", "Robin"), ("SF002", "Sam")):
        conn.execute(
            """INSERT INTO students (student_id, first_name, last_name,
                                     email, subject_1, subject_2, subject_3,
                                     status)
               VALUES (?, ?, 'Fielding', ?, 'Maths', 'Physics', 'Chemistry',
                       'Active')""",
            (sid, first, f"{sid.lower()}@sixthform.ac.uk"))
    conn.commit()
    conn.close()
    return sd


def _parent(sf, account_id: int, username: str, *student_ids: str) -> None:
    conn = sqlite3.connect(str(sf.DB_PATH))
    conn.execute(
        "INSERT INTO parent_accounts (account_id, username, full_name, "
        "password_hash, password_salt) VALUES (?, ?, ?, 'x', 'y')",
        (account_id, username, username))
    for sid in student_ids:
        conn.execute("INSERT INTO parent_student_links (account_id, "
                     "student_id) VALUES (?, ?)", (account_id, sid))
    conn.commit()
    conn.close()


def _is_active(sf, username: str) -> int:
    conn = sqlite3.connect(str(sf.DB_PATH))
    row = conn.execute("SELECT is_active FROM parent_accounts "
                       "WHERE username = ?", (username,)).fetchone()
    conn.close()
    return row[0]


def _confirm_ucas(sf, student_id: str) -> None:
    """Give a learner a Confirmed UCAS place, without leaving the roll."""
    conn = sqlite3.connect(str(sf.DB_PATH))
    conn.execute("INSERT INTO ucas_applications (student_id, cycle_year, "
                 "status) VALUES (?, 2027, 'Confirmed')", (student_id,))
    conn.commit()
    conn.close()


def _mark_left(sf, student_id: str) -> None:
    conn = sqlite3.connect(str(sf.DB_PATH))
    conn.execute("UPDATE students SET status = 'Left' WHERE student_id = ?",
                 (student_id,))
    conn.commit()
    conn.close()


# ── The learner's own login ─────────────────────────────────────────

class _Roles:
    """Stand-in for RoleManager, returning whatever a test sets."""
    systems: list = []

    def __init__(self, *_a, **_k):
        pass

    def get_user_systems(self, _user_id):
        return list(type(self).systems)


@pytest.fixture
def auth(tmp_path, monkeypatch):
    """A throwaway auth database with one account and a live session."""
    import contextlib
    from education_system.platform.identity.auth import db as auth_db
    from education_system.platform.identity.auth import role_manager

    path = str(tmp_path / "auth.db")
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT UNIQUE,
                            is_active INTEGER DEFAULT 1, updated_at TEXT);
        CREATE TABLE sessions (id INTEGER PRIMARY KEY, user_id INTEGER,
                               is_active INTEGER DEFAULT 1);
        INSERT INTO users (id, username) VALUES (7, 'SF001');
        INSERT INTO sessions (user_id, is_active) VALUES (7, 1);
    """)
    conn.commit()
    conn.close()

    @contextlib.contextmanager
    def _connect(*_a, **_k):
        c = sqlite3.connect(path)
        c.row_factory = sqlite3.Row
        try:
            yield c
        finally:
            c.close()

    monkeypatch.setattr(auth_db, "connect", _connect)
    monkeypatch.setattr(role_manager, "RoleManager", _Roles)
    _Roles.systems = []

    def _state(username="SF001"):
        c = sqlite3.connect(path)
        c.row_factory = sqlite3.Row
        user = c.execute("SELECT is_active FROM users WHERE username = ?",
                         (username,)).fetchone()
        live = c.execute("SELECT COUNT(*) FROM sessions "
                         "WHERE user_id = 7 AND is_active = 1").fetchone()[0]
        c.close()
        return (user["is_active"] if user else None), live

    return _state


class TestLeaverLogin:
    def test_disabled_when_nothing_is_left_on_the_account(self, sf, auth):
        _Roles.systems = []
        assert sf.disable_leaver_login("SF001") is True
        assert auth() == (0, 0)

    def test_live_sessions_are_revoked_with_it(self, sf, auth):
        """A session issued before the change still carries the old
        membership set, so leaving it live leaves a way in."""
        _Roles.systems = []
        assert auth()[1] == 1
        sf.disable_leaver_login("SF001")
        assert auth()[1] == 0

    @pytest.mark.parametrize("held", [
        [{"system_key": "university"}],
        [{"system_key": "staff"}],
        [{"system_key": "sixth_form"}, {"system_key": "parent"}],
    ])
    def test_kept_when_the_account_still_holds_something(self, sf, auth, held):
        """The account is a person, not a sixth-form login. This is the
        exact regression that made the code stop disabling outright."""
        _Roles.systems = held
        assert sf.disable_leaver_login("SF001") is False
        assert auth() == (1, 1)

    def test_no_account_is_not_an_error(self, sf, auth):
        _Roles.systems = []
        assert sf.disable_leaver_login("SF999") is False

    def test_calling_twice_is_harmless(self, sf, auth):
        """Confirmation disables it; the later handover calls again."""
        _Roles.systems = []
        assert sf.disable_leaver_login("SF001") is True
        assert sf.disable_leaver_login("SF001") is True
        assert auth() == (0, 0)

    def test_a_broken_auth_database_does_not_stop_the_transfer(
            self, sf, monkeypatch):
        from education_system.platform.identity.auth import db as auth_db

        def _boom(*_a, **_k):
            raise sqlite3.OperationalError("no such table: users")

        monkeypatch.setattr(auth_db, "connect", _boom)
        assert sf.disable_leaver_login("SF001") is False


# ── Parent logins ───────────────────────────────────────────────────

class TestParentLogins:
    def test_an_account_only_for_this_learner_is_disabled(self, sf):
        _parent(sf, 901, "p.only", "SF001")
        assert sf.disable_orphaned_parent_logins("SF001") == ["p.only"]
        assert _is_active(sf, "p.only") == 0

    def test_an_account_covering_a_sibling_on_roll_is_kept(self, sf):
        """The failure worth avoiding: cutting a parent off from a child
        still at the college."""
        _parent(sf, 902, "p.both", "SF001", "SF002")
        assert sf.disable_orphaned_parent_logins("SF001") == []
        assert _is_active(sf, "p.both") == 1

    def test_the_leaver_does_not_keep_their_own_parent_account_open(self, sf):
        """Runs at confirmation, where the learner is still Active. Keying
        the sibling count on their own status would never close anything.
        """
        _parent(sf, 903, "p.only", "SF001")
        _confirm_ucas(sf, "SF001")
        assert sf.disable_orphaned_parent_logins("SF001") == ["p.only"]

    def test_two_siblings_confirmed_in_the_same_cycle_close_the_account(
            self, sf):
        """Neither has left, so each is Active in the other's count — the
        account would otherwise stay open forever."""
        _parent(sf, 904, "p.both", "SF001", "SF002")
        _confirm_ucas(sf, "SF001")
        assert sf.disable_orphaned_parent_logins("SF001") == []

        _confirm_ucas(sf, "SF002")
        assert sf.disable_orphaned_parent_logins("SF002") == ["p.both"]
        assert _is_active(sf, "p.both") == 0

    def test_a_sibling_who_has_left_does_not_hold_it_open(self, sf):
        _parent(sf, 905, "p.both", "SF001", "SF002")
        _mark_left(sf, "SF002")
        assert sf.disable_orphaned_parent_logins("SF001") == ["p.both"]

    def test_an_already_disabled_account_is_not_reported_again(self, sf):
        """Called at confirmation and again at handover; the second run
        should say it did nothing rather than claim the work twice."""
        _parent(sf, 906, "p.only", "SF001")
        assert sf.disable_orphaned_parent_logins("SF001") == ["p.only"]
        assert sf.disable_orphaned_parent_logins("SF001") == []

    def test_a_learner_with_no_parent_account_is_a_no_op(self, sf):
        assert sf.disable_orphaned_parent_logins("SF001") == []

    def test_a_database_without_parent_tables_is_a_no_op(self, sf):
        """A college that has never opened the parent portal still
        transfers learners."""
        conn = sqlite3.connect(str(sf.DB_PATH))
        conn.executescript("DROP TABLE parent_student_links;"
                           "DROP TABLE parent_accounts;")
        conn.commit()
        conn.close()
        assert sf.disable_orphaned_parent_logins("SF001") == []

    def test_a_database_without_ucas_tables_still_applies_the_status_rule(
            self, sf):
        """The confirmed-sibling clause is dropped, not fatal."""
        conn = sqlite3.connect(str(sf.DB_PATH))
        conn.executescript("DROP TABLE ucas_applications;")
        conn.commit()
        conn.close()
        _parent(sf, 907, "p.both", "SF001", "SF002")
        assert sf.disable_orphaned_parent_logins("SF001") == []
        _mark_left(sf, "SF002")
        assert sf.disable_orphaned_parent_logins("SF001") == ["p.both"]
