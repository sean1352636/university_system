"""Signing in: the launcher's session becomes a SEND principal; non-staff are refused."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from education_system.systems.special_education.core import access


def _auth(role=None, systems=None):
    return SimpleNamespace(current_user={"id": 9, "username": "senco1", "role": role,
                                         "systems": systems or []})


def test_role_from_the_accounts_send_entry():
    p = access.from_auth(_auth(systems=[{"system_key": "special_education", "role": "staff"}]))
    assert (p.username, p.role, p.user_id) == ("senco1", "staff", 9)
    assert p.is_staff and p.can_edit("needs") and not p.can_delete("needs")


def test_launcher_role_wins_for_superadmin_choice():
    p = access.from_auth(_auth(systems=[{"system_key": "special_education", "role": "admin"}]),
                         role="staff")
    assert p.role == "staff"


@pytest.mark.parametrize("role", [None, "student", "parent", "teacher"])
def test_non_send_staff_fail_closed(role):
    p = access.from_auth(_auth(role=role))
    assert not p.is_staff and not p.can_open("SEND Register")


def test_no_session_is_refused():
    with pytest.raises(RuntimeError, match="no standalone login"):
        access.require_shared_session(None, "gui")
    with pytest.raises(RuntimeError):
        access.require_shared_session(SimpleNamespace(current_user=None), "cli")
    assert access.from_auth(None) == access.ANONYMOUS


def test_registered_with_the_platform():
    from education_system.launcher.systems import AUTH_GUI_SYSTEMS, LAUNCHERS
    from education_system.platform.identity.auth.defaults import SYSTEMS, roles_for_system
    from education_system.platform.kernel.core.system_keys import canonical_system_key
    from education_system.systems import registry
    assert "special_education" in registry.SYSTEM_KEYS
    assert registry.get("special_education").display_name == "Special Education (SEND) System"
    assert "special_education" in SYSTEMS and "special_education" in AUTH_GUI_SYSTEMS
    assert ("special_education", "gui") in LAUNCHERS and ("special_education", "cli") in LAUNCHERS
    assert roles_for_system("special_education") == ("admin", "staff")
    assert canonical_system_key("SEND") == "special_education"
