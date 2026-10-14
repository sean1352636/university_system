"""The platform's learner-login linking rules, independent of any system.

Stand-in adapters answer "which learner does this login belong to?", so
these tests exercise only ``cross_system.login_links``: which roles count,
agreement and disagreement between systems, manual links, legacy system
keys, and ``sync_all``'s system filter. Temp auth.db only; the stand-ins
are installed with ``monkeypatch`` so the real registry is restored.
"""

from __future__ import annotations

import pytest

from education_system.platform.cross_system import identity_service, login_links
from education_system.platform.cross_system.adapters import registry
from education_system.platform.cross_system.adapters.base import PhaseAdapter
from education_system.platform.identity.auth.db import connect
from education_system.platform.identity.auth.schema import initialise_auth_db


class _Pairing(PhaseAdapter):
    """Pairs logins with local ids from a dict, for the given learner roles."""

    def __init__(self, system: str, roles: tuple[str, ...], pairs: dict[str, list[str]]):
        self.system = system
        super().__init__()
        self.learner_login_roles = roles
        self.pairs = pairs

    def learner_ids_for_login(self, account: dict) -> list[str]:
        return list(self.pairs.get(account["username"], []))


class _NoPairing(PhaseAdapter):
    """An adapter that has not implemented login pairing."""

    def __init__(self, system: str):
        self.system = system
        super().__init__()


# ── Plain helpers (the fixtures below are thin wrappers) ─────────────

def fresh_db(tmp_path, mp) -> str:
    path = str(tmp_path / "auth.db")
    mp.setattr(identity_service, "_initialised", set())
    initialise_auth_db(path)
    return path


def installer(mp):
    def install(*adapters: PhaseAdapter) -> None:
        for adapter in adapters:
            mp.setitem(registry._adapters, adapter.system, adapter)
    return install


def account(db: str, username: str, *grants: tuple[str, str]) -> int:
    conn = connect(db)
    try:
        user_id = int(conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, 'x')",
            (username,)).lastrowid)
        for system, role in grants:
            conn.execute("INSERT INTO user_systems (user_id, system_key, role) "
                         "VALUES (?, ?, ?)", (user_id, system, role))
        conn.commit()
    finally:
        conn.close()
    return user_id


def learner(db: str, system: str, local_id: str, first: str,
            dob: str = "2010-01-01") -> str:
    return identity_service.get_or_create_journey(
        first_name=first, last_name="Test", date_of_birth=dob, system=system,
        student_id=local_id, announce=False, db_path=db)


def link_of(db: str, user_id: int) -> str | None:
    return identity_service.journey_for_user(user_id, db_path=db)


def last_actor(db: str, user_id: int) -> str | None:
    conn = connect(db)
    try:
        row = conn.execute(
            "SELECT username FROM security_audit_log WHERE user_id = ? "
            "ORDER BY id DESC LIMIT 1", (user_id,)).fetchone()
    finally:
        conn.close()
    return row["username"] if row else None


@pytest.fixture
def db(tmp_path, monkeypatch):
    return fresh_db(tmp_path, monkeypatch)


@pytest.fixture
def install(monkeypatch):
    return installer(monkeypatch)


# ── Tests ────────────────────────────────────────────────────────────

def test_a_learner_role_links_the_login(db, install):
    install(_Pairing("secondary", ("student",), {"amy": ["S1"]}))
    jid = learner(db, "secondary", "S1", "Amy")
    user_id = account(db, "amy", ("secondary", "student"))
    outcome = login_links.sync_username("amy", db_path=db)
    assert outcome.action == login_links.LINKED
    assert link_of(db, user_id) == jid
    assert last_actor(db, user_id) == "secondary:auto-link"


def test_a_parent_role_is_never_linked(db, install):
    install(_Pairing("secondary", ("student",), {"mum": ["S1"]}))
    learner(db, "secondary", "S1", "Amy")
    user_id = account(db, "mum", ("secondary", "parent"))
    assert login_links.sync_username("mum", db_path=db).action == login_links.SKIPPED
    assert link_of(db, user_id) is None


def test_an_adapter_that_does_not_pair_logins_is_ignored(db, install):
    install(_NoPairing("secondary"))
    learner(db, "secondary", "S1", "Amy")
    user_id = account(db, "amy", ("secondary", "student"))
    assert login_links.sync_username("amy", db_path=db).action == login_links.SKIPPED
    assert link_of(db, user_id) is None


def test_two_systems_agreeing_give_one_link(db, install):
    jid = learner(db, "secondary", "S1", "Amy")
    identity_service.link_system(jid, "sixth_form", student_id="F1", db_path=db)
    install(_Pairing("secondary", ("student",), {"amy": ["S1"]}),
            _Pairing("sixth_form", ("student",), {"amy": ["F1"]}))
    user_id = account(db, "amy", ("secondary", "student"), ("sixth_form", "student"))
    outcome = login_links.sync_username("amy", db_path=db)
    assert outcome.action == login_links.LINKED
    assert outcome.systems == ("secondary", "sixth_form")
    assert link_of(db, user_id) == jid


def test_two_systems_disagreeing_link_nothing(db, install):
    learner(db, "secondary", "S1", "Amy")
    learner(db, "sixth_form", "F1", "Bea", dob="2009-09-09")
    install(_Pairing("secondary", ("student",), {"amy": ["S1"]}),
            _Pairing("sixth_form", ("student",), {"amy": ["F1"]}))
    user_id = account(db, "amy", ("secondary", "student"), ("sixth_form", "student"))
    assert login_links.sync_username("amy", db_path=db).action == login_links.SKIPPED
    assert link_of(db, user_id) is None


def test_a_manual_link_is_left_alone(db, install):
    install(_Pairing("secondary", ("student",), {"amy": ["S1"]}))
    learner(db, "secondary", "S1", "Amy")
    other = learner(db, "secondary", "S2", "Bea", dob="2009-09-09")
    user_id = account(db, "amy", ("secondary", "student"))
    identity_service.link_user_account(user_id, other, actor="admin", db_path=db)
    assert login_links.sync_username("amy", db_path=db).action == login_links.SKIPPED
    assert link_of(db, user_id) == other


def test_only_an_automatic_link_is_removed_when_the_record_goes(db, install):
    adapter = _Pairing("secondary", ("student",), {"amy": ["S1"], "bea": ["S2"]})
    install(adapter)
    learner(db, "secondary", "S1", "Amy")
    jid_b = learner(db, "secondary", "S2", "Bea", dob="2009-09-09")
    amy = account(db, "amy", ("secondary", "student"))
    bea = account(db, "bea", ("secondary", "student"))
    login_links.sync_username("amy", db_path=db)
    identity_service.link_user_account(bea, jid_b, actor="admin", db_path=db)
    adapter.pairs.clear()
    assert login_links.sync_username("amy", db_path=db).action == login_links.UNLINKED
    assert login_links.sync_username("bea", db_path=db).action == login_links.UNCHANGED
    assert link_of(db, amy) is None
    assert link_of(db, bea) == jid_b


def test_legacy_system_keys_are_recognised(db, install):
    install(_Pairing("secondary", ("student",), {"amy": ["S1"]}))
    jid = learner(db, "secondary", "S1", "Amy")
    user_id = account(db, "amy", ("school", "student"))
    assert login_links.sync_username("amy", db_path=db).action == login_links.LINKED
    assert link_of(db, user_id) == jid


def test_sync_all_is_filtered_by_system_and_idempotent(db, install):
    install(_Pairing("secondary", ("student",), {"amy": ["S1"]}),
            _Pairing("sixth_form", ("student",), {"fred": ["F1"]}))
    learner(db, "secondary", "S1", "Amy")
    learner(db, "sixth_form", "F1", "Fred", dob="2008-08-08")
    amy = account(db, "amy", ("secondary", "student"))
    fred = account(db, "fred", ("sixth_form", "student"))

    first = login_links.sync_all(systems=["secondary"], db_path=db)
    assert first[login_links.LINKED] == 1
    assert link_of(db, amy) is not None and link_of(db, fred) is None

    everything = login_links.sync_all(db_path=db)
    assert everything[login_links.LINKED] == 1
    again = login_links.sync_all(db_path=db)
    assert again[login_links.LINKED] == again[login_links.RELINKED] \
        == again[login_links.UNLINKED] == 0


def test_blank_and_unknown_usernames(db):
    assert login_links.sync_username("  ", db_path=db) is None
    assert login_links.sync_username("nobody", db_path=db).action == login_links.SKIPPED
