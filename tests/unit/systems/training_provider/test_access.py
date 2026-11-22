"""Sign-in: the Training Provider runs only on the launcher's shared session,
for admin and staff roles; anything else fails closed."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from education_system.systems.training_provider import SYSTEM_KEY, SYSTEM_NAME
from education_system.systems.training_provider.core import access


def _auth(role: str | None = None, systems=None, **extra):
    user = {"id": 7, "username": "u1", "systems": systems or [], **extra}
    if role:
        user["role"] = role
    return SimpleNamespace(current_user=user)


def test_manifest_and_registry():
    from education_system.systems import registry
    assert SYSTEM_KEY == "training_provider"
    assert SYSTEM_NAME == "Training Provider System"
    assert "training_provider" in registry.SYSTEM_KEYS


def test_staff_role_from_the_account_systems_list():
    p = access.from_auth(_auth(systems=[{"system_key": "training_provider", "role": "staff"}]))
    assert p.role == "staff" and p.is_staff and not p.is_admin
    assert p.can_open("Invoices") and p.can_edit("bookings")
    assert not p.can_delete("learners")


def test_alias_key_and_admin():
    p = access.from_auth(_auth(systems=[{"system_key": "tp", "role": "Admin"}]))
    assert p.is_admin and p.can_delete("learners")


def test_launcher_role_wins():
    p = access.from_auth(_auth(systems=[{"system_key": "training_provider",
                                          "role": "staff"}]), role="admin")
    assert p.is_admin


@pytest.mark.parametrize("role", [None, "student", "parent", "apprentice"])
def test_other_roles_fail_closed(role):
    p = access.from_auth(_auth(role=role))
    assert not p.is_staff and not p.can_open("Learner Directory")
    assert "Training Provider staff only" in access.refusal(p)


def test_no_session_refused():
    with pytest.raises(RuntimeError, match="trainingprovider"):
        access.require_shared_session(None, "gui")
    assert access.from_auth(None) == access.ANONYMOUS


def test_seeded_accounts_and_roles():
    from education_system.platform.identity.auth import defaults, schema
    names = {a["username"]: a["systems"] for a in schema._DEFAULT_ACCOUNTS}
    assert names["admin10"] == [("training_provider", "admin")]
    assert names["tptrainer1"] == [("training_provider", "staff")]
    assert ("training_provider", "admin") in names["superadmin"]
    assert defaults.SYSTEM_ROLES["training_provider"] == ("admin", "staff")
