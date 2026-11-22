"""Signing in: the launcher's session becomes an Alternative Provision principal; non-staff are refused."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from education_system.systems.alternative_provision.core import access


def _auth(role=None, systems=None):
    return SimpleNamespace(current_user={"id": 9, "username": "keyworker1", "role": role,
                                         "systems": systems or []})


def test_role_from_the_accounts_ap_entry():
    p = access.from_auth(_auth(systems=[{"system_key": "alternative_provision", "role": "staff"}]))
    assert (p.username, p.role, p.user_id) == ("keyworker1", "staff", 9)
    assert p.is_staff and p.can_edit("learners") and not p.can_delete("learners")


def test_launcher_role_wins_for_superadmin_choice():
    p = access.from_auth(_auth(systems=[{"system_key": "alternative_provision", "role": "admin"}]),
                         role="staff")
    assert p.role == "staff"


@pytest.mark.parametrize("role", [None, "student", "parent", "teacher"])
def test_non_staff_fail_closed(role):
    p = access.from_auth(_auth(role=role))
    assert not p.is_staff and not p.can_open("Pupil Directory")


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
    assert "alternative_provision" in registry.SYSTEM_KEYS
    assert registry.get("alternative_provision").display_name == "Alternative Provision System"
    assert "alternative_provision" in SYSTEMS and "alternative_provision" in AUTH_GUI_SYSTEMS
    assert ("alternative_provision", "gui") in LAUNCHERS and ("alternative_provision", "cli") in LAUNCHERS
    assert roles_for_system("alternative_provision") == ("admin", "staff")
    assert canonical_system_key("PRU") == "alternative_provision"
