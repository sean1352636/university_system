"""Apprentice logins are linked to their platform learner record automatically.

The login (a ``users`` row in the shared auth.db) and the learner record
(a ``journey_id``) are paired through the apprentice record whose
``username`` is the login's. These tests cover when that link is made,
when it moves, and — the important half — when it is deliberately left
alone. Every platform write lands in the temp auth.db the package's
autouse ``platform_auth_db`` fixture provides.
"""

from __future__ import annotations

import pytest

from education_system.platform.cross_system import identity_service
from education_system.platform.identity.auth.db import connect
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    apprentice_repository,
)
from education_system.systems.apprenticeships.application.apprentices import apprentice_service
from education_system.systems.apprenticeships.application.security import (
    access,
    account_service,
    login_links,
)


def _account(username: str, role: str | None = "apprentice") -> int:
    """A shared-auth login, optionally holding an apprenticeships role."""
    conn = connect()
    try:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, 'x')", (username,))
        user_id = int(cur.lastrowid)
        if role:
            conn.execute(
                "INSERT INTO user_systems (user_id, system_key, role) "
                "VALUES (?, 'apprenticeships', ?)", (user_id, role))
        conn.commit()
    finally:
        conn.close()
    return user_id


def _journey(apprentice_id: int) -> str:
    row = identity_service.find_by_student("apprenticeships", str(apprentice_id))
    assert row is not None, "the apprentice was not registered on the platform"
    return row["journey_id"]


def _link(user_id: int) -> str | None:
    return identity_service.journey_for_user(user_id)


def _second_apprentice(admin, cohort, *, username: str | None = None) -> int:
    """A different person on the same programme — a separate learner record."""
    payload = {
        "given_name": "Ava", "family_name": "Stone", "uln": "2234567890",
        "date_of_birth": "2002-02-02",
        "programme_id": cohort["programme"].programme_id,
        "employer_id": cohort["employer"].employer_id,
        "tutor_id": cohort["tutor_id"], "weekly_hours": 30,
    }
    if username:
        payload["username"] = username
    return apprentice_service.create_apprentice(admin, payload).apprentice_id


class TestLinking:
    def test_granting_the_apprentice_role_links_the_login(self, cohort, admin):
        user_id = _account("apprentice1", role=None)
        account_service.grant_role(admin, "apprentice1", "apprentice")
        assert _link(user_id) == _journey(cohort["apprentice_id"])

    def test_creating_an_apprentice_links_an_existing_account(self, cohort, admin):
        user_id = _account("astone")
        second = _second_apprentice(admin, cohort, username="astone")
        assert _link(user_id) == _journey(second)
        assert _link(user_id) != _journey(cohort["apprentice_id"])

    def test_sign_in_links_an_account_from_before_linking(self, cohort):
        user_id = _account("apprentice1")
        assert _link(user_id) is None
        actor = access.resolve({
            "username": "apprentice1",
            "systems": [{"system_key": "apprenticeships", "role": "apprentice"}],
        })
        assert actor.apprentice_id == cohort["apprentice_id"]
        assert _link(user_id) == _journey(cohort["apprentice_id"])

    def test_the_link_is_audited_under_the_automatic_actor(self, cohort):
        user_id = _account("apprentice1")
        login_links.sync_username("apprentice1")
        conn = connect()
        try:
            row = conn.execute(
                "SELECT username FROM security_audit_log WHERE user_id = ? "
                "AND event_type = 'identity.user_linked'", (user_id,)).fetchone()
        finally:
            conn.close()
        assert row["username"] == login_links.AUTO_ACTOR

    def test_sync_all_links_then_changes_nothing(self, cohort):
        _account("apprentice1")
        first = login_links.sync_all()
        second = login_links.sync_all()
        assert first[login_links.LINKED] == 1
        assert second[login_links.LINKED] == second[login_links.RELINKED] \
            == second[login_links.UNLINKED] == 0


class TestLeftAlone:
    def test_an_account_without_the_apprentice_role_is_not_linked(self, cohort):
        user_id = _account("apprentice1", role="staff")
        outcome = login_links.sync_username("apprentice1")
        assert outcome.action == login_links.SKIPPED
        assert _link(user_id) is None

    def test_a_link_set_by_hand_is_never_overwritten(self, cohort, admin):
        other = _journey(_second_apprentice(admin, cohort))
        user_id = _account("apprentice1")
        identity_service.link_user_account(user_id, other, actor="admin5")
        outcome = login_links.sync_username("apprentice1")
        assert outcome.action == login_links.SKIPPED
        assert _link(user_id) == other

    def test_records_of_different_learners_sharing_a_login_link_nothing(self, cohort, admin):
        _second_apprentice(admin, cohort, username="apprentice1")
        user_id = _account("apprentice1")
        outcome = login_links.sync_username("apprentice1")
        assert outcome.action == login_links.SKIPPED
        assert _link(user_id) is None

    def test_an_automatic_link_comes_off_when_a_second_learner_takes_the_login(
            self, cohort, admin):
        user_id = _account("apprentice1")
        login_links.sync_username("apprentice1")
        assert _link(user_id) == _journey(cohort["apprentice_id"])
        _second_apprentice(admin, cohort, username="apprentice1")
        assert _link(user_id) is None

    def test_a_manual_link_survives_its_record_losing_the_username(self, cohort):
        user_id = _account("apprentice1")
        journey = _journey(cohort["apprentice_id"])
        identity_service.link_user_account(user_id, journey, actor="admin5")
        apprentice_repository.update(cohort["apprentice_id"], {"username": None})
        login_links.sync_username("apprentice1")
        assert _link(user_id) == journey

    def test_a_failing_sync_never_blocks_creating_an_apprentice(
            self, cohort, admin, monkeypatch):
        def boom(*_a, **_k):
            raise RuntimeError("auth.db unavailable")

        monkeypatch.setattr(login_links, "sync_username", boom)
        assert _second_apprentice(admin, cohort, username="astone")


class TestMoving:
    def test_the_automatic_link_follows_the_login_to_another_record(self, cohort, admin):
        user_id = _account("apprentice1")
        login_links.sync_username("apprentice1")
        second = _second_apprentice(admin, cohort)
        apprentice_repository.update(cohort["apprentice_id"], {"username": None})
        account_service.link_to_record(admin, "apprentice1", "apprentice", second)
        assert _link(user_id) == _journey(second)

    def test_the_automatic_link_is_removed_when_no_record_uses_the_login(self, cohort):
        user_id = _account("apprentice1")
        login_links.sync_username("apprentice1")
        apprentice_repository.update(cohort["apprentice_id"], {"username": None})
        outcome = login_links.sync_username("apprentice1")
        assert outcome.action == login_links.UNLINKED
        assert _link(user_id) is None

    def test_a_username_change_moves_the_link_to_the_new_login(self, cohort):
        old = _account("apprentice1")
        new = _account("jbell")
        login_links.sync_username("apprentice1")
        apprentice_repository.update(cohort["apprentice_id"], {"username": "jbell"})
        outcomes = login_links.sync_apprentice(
            cohort["apprentice_id"], previous_username="apprentice1")
        assert {o.username: o.action for o in outcomes} == {
            "jbell": login_links.LINKED, "apprentice1": login_links.UNLINKED}
        assert _link(new) == _journey(cohort["apprentice_id"])
        assert _link(old) is None


@pytest.mark.parametrize("blank", [None, "", "   "])
def test_a_blank_username_is_ignored(db, blank):
    assert login_links.sync_username(blank) is None
