"""Sign-in: Local Authority Education runs only on the launcher's shared session,
for admin and staff roles; anything else fails closed."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from education_system.systems.local_authority import SYSTEM_KEY, SYSTEM_NAME
from education_system.systems.local_authority.core import access


def _auth(role: str | None = None, systems=None, **extra):
    user = {"id": 7, "username": "u1", "systems": systems or [], **extra}
    if role:
        user["role"] = role
    return SimpleNamespace(current_user=user)


def test_manifest_and_registry():
    from education_system.systems import registry
    assert SYSTEM_KEY == "local_authority"
    assert SYSTEM_NAME == "Local Authority Education System"
    assert "local_authority" in registry.SYSTEM_KEYS


def test_staff_role_from_the_account_systems_list():
    p = access.from_auth(_auth(systems=[{"system_key": "local_authority", "role": "staff"}]))
    assert p.role == "staff" and p.is_staff and not p.is_admin
    assert p.can_open("Applications & Offers") and p.can_edit("applications")
    assert not p.can_delete("learners")


def test_alias_key_and_admin():
    p = access.from_auth(_auth(systems=[{"system_key": "la", "role": "Admin"}]))
    assert p.is_admin and p.can_delete("learners")


def test_launcher_role_wins():
    p = access.from_auth(_auth(systems=[{"system_key": "local_authority",
                                          "role": "staff"}]), role="admin")
    assert p.is_admin


@pytest.mark.parametrize("role", [None, "student", "parent", "apprentice"])
def test_other_roles_fail_closed(role):
    p = access.from_auth(_auth(role=role))
    assert not p.is_staff and not p.can_open("Children Directory")
    assert "council education staff only" in access.refusal(p)


def test_no_session_refused():
    with pytest.raises(RuntimeError, match="localauthority"):
        access.require_shared_session(None, "gui")
    assert access.from_auth(None) == access.ANONYMOUS


def test_seeded_accounts_and_roles():
    from education_system.platform.identity.auth import defaults, schema
    names = {a["username"]: a["systems"] for a in schema._DEFAULT_ACCOUNTS}
    assert names["admin11"] == [("local_authority", "admin")]
    assert names["laofficer1"] == [("local_authority", "staff")]
    assert ("local_authority", "admin") in names["superadmin"]
    assert defaults.SYSTEM_ROLES["local_authority"] == ("admin", "staff")
