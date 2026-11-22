"""Roles and access overview (domain.governance.user_management.user_management).

Reads and writes the platform login database - only ever the sandbox copy,
which each test checks before seeding it.
"""

from __future__ import annotations

import datetime as dt
import sqlite3
from pathlib import Path

import pytest

from education_system.platform.identity.auth.role_manager import ROLE_HIERARCHY, RoleManager
from education_system.systems.primary.domain.governance.user_management import (
    user_management as UM,
)


class _Sessions:
    def __init__(self):
        self.invalidated: list[int] = []

    def invalidate_user_sessions(self, user_id):
        self.invalidated.append(user_id)


class _Auth:
    """Enough of UserAuth for the user-accounts helpers, on the sandbox DB."""

    def __init__(self, db_path: str):
        self._db_path = db_path
        self.role_manager = RoleManager(db_path)
        self.session_manager = _Sessions()
        self.current_user = None


@pytest.fixture
def auth(primary_sandbox):
    db = Path(primary_sandbox.PLATFORM_AUTH_DB).resolve()
    sandbox_root = Path(primary_sandbox.PLATFORM_DATA_DIR).resolve()
    live_var = Path(primary_sandbox.VAR_DIR).resolve()
    assert sandbox_root in db.parents
    assert live_var not in db.parents
    return _Auth(str(db))


def _user(auth, username, *, systems=(), active=True, locked_until=None, last_login=None):
    conn = sqlite3.connect(auth._db_path)
    try:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, display_name, email, is_active, "
            "locked_until, last_login) VALUES (?, 'x', ?, ?, ?, ?, ?)",
            (username, username.title(), f"{username}@school.test", int(active),
             locked_until, last_login))
        uid = cur.lastrowid
        for key, role in systems:
            conn.execute("INSERT INTO user_systems (user_id, system_key, role) VALUES (?, ?, ?)",
                         (uid, key, role))
        conn.commit()
    finally:
        conn.close()
    return uid


def _future() -> str:
    return (dt.datetime.utcnow() + dt.timedelta(hours=2)).isoformat(timespec="seconds")


def _past() -> str:
    return (dt.datetime.utcnow() - dt.timedelta(hours=2)).isoformat(timespec="seconds")


def _role(auth, uid, key):
    return {s["system_key"]: s["role"] for s in auth.role_manager.get_user_systems(uid)}.get(key)


# ── constants ──

def test_system_key_and_known_systems():
    assert UM.SYSTEM_KEY == "primary"
    assert UM.KNOWN_SYSTEMS[0] == "primary"
    assert set(UM.KNOWN_SYSTEMS) == {"primary", "nursery", "secondary", "sixth_form",
                                     "fe_college", "apprenticeships", "university"}
    assert len(UM.KNOWN_SYSTEMS) == 7


# ── access matrix ──

def test_access_matrix_empty(auth):
    m = UM.access_matrix(auth)
    assert m.systems == [] and m.users_without_primary == []


def test_access_matrix_orders_known_systems_then_others(auth):
    _user(auth, "ann", systems=[("primary", "teacher"), ("secondary", "teacher")])
    _user(auth, "bob", systems=[("primary", "admin")])
    _user(auth, "cat", systems=[("university", "student"), ("zeta_lab", "staff"),
                                ("alpha_lab", "staff")])
    m = UM.access_matrix(auth)
    assert [s.system_key for s in m.systems] == ["primary", "secondary", "university",
                                                 "alpha_lab", "zeta_lab"]
    primary = m.systems[0]
    assert primary.users == 2 and primary.by_role == {"teacher": 1, "admin": 1}
    assert [u.username for u in m.users_without_primary] == ["cat"]


# ── role distribution ──

def test_role_distribution_primary(auth):
    _user(auth, "ann", systems=[("primary", "teacher")])
    _user(auth, "bob", systems=[("primary", "teacher")])
    _user(auth, "cat", systems=[("primary", "admin"), ("secondary", "staff")])
    _user(auth, "dan", systems=[("secondary", "staff")])
    dist = UM.role_distribution(auth)
    assert set(ROLE_HIERARCHY) <= set(dist)
    assert dist["teacher"] == 2 and dist["admin"] == 1 and dist["staff"] == 0
    assert sum(dist.values()) == 3
    assert UM.role_distribution(auth, "secondary")["staff"] == 2


def test_role_distribution_empty(auth):
    assert sum(UM.role_distribution(auth).values()) == 0


# ── bulk grant / revoke / activate ──

def test_bulk_grant(auth):
    a = _user(auth, "ann")
    b = _user(auth, "bob", systems=[("primary", "parent")])
    res = UM.bulk_grant(auth, [a, b, 9999], "primary", "teacher")
    assert res.succeeded == [a, b]
    assert [uid for uid, _ in res.failed] == [9999] and "No user #9999" in res.failed[0][1]
    assert res.total == 3
    assert _role(auth, a, "primary") == "teacher" and _role(auth, b, "primary") == "teacher"


def test_bulk_grant_rejects_unknown_role_and_empty_list(auth):
    a = _user(auth, "ann")
    with pytest.raises(UM.UserAccountError, match="Role must be one of"):
        UM.bulk_grant(auth, [a], "primary", "headmaster")
    empty = UM.bulk_grant(auth, [], "primary", "teacher")
    assert empty.succeeded == [] and empty.failed == [] and empty.total == 0


def test_bulk_revoke(auth):
    a = _user(auth, "ann", systems=[("primary", "teacher"), ("secondary", "teacher")])
    b = _user(auth, "bob")
    res = UM.bulk_revoke(auth, [a, b, 4242], "primary")
    assert res.succeeded == [a, b] and [uid for uid, _ in res.failed] == [4242]
    assert _role(auth, a, "primary") is None and _role(auth, a, "secondary") == "teacher"
    assert UM.bulk_revoke(auth, [], "primary").total == 0


def test_bulk_set_active(auth):
    a = _user(auth, "ann")
    b = _user(auth, "bob")
    res = UM.bulk_set_active(auth, [a, b, 777], False)
    assert res.succeeded == [a, b] and [uid for uid, _ in res.failed] == [777]
    assert sorted(auth.session_manager.invalidated) == [a, b]
    assert {u.username for u in UM.list_inactive(auth)} == {"ann", "bob"}
    UM.bulk_set_active(auth, [a], True)
    assert [u.username for u in UM.list_inactive(auth)] == ["bob"]
    assert UM.bulk_set_active(auth, [], True).total == 0


# ── listings ──

def test_list_admins(auth):
    _user(auth, "ann", systems=[("primary", "admin")])
    _user(auth, "bob", systems=[("primary", "teacher"), ("secondary", "admin")])
    assert [u.username for u in UM.list_admins(auth)] == ["ann"]
    assert [u.username for u in UM.list_admins(auth, system_key="secondary")] == ["bob"]


def test_list_without_access(auth):
    _user(auth, "ann", systems=[("primary", "teacher")])
    _user(auth, "bob", systems=[("secondary", "teacher")])
    _user(auth, "cat")
    assert [u.username for u in UM.list_without_access(auth)] == ["bob", "cat"]
    assert [u.username for u in UM.list_without_access(auth, system_key="secondary")] == \
        ["ann", "cat"]


def test_list_locked_only_counts_future_locks(auth):
    _user(auth, "ann", locked_until=_future())
    _user(auth, "bob", locked_until=_past())
    _user(auth, "cat")
    assert [u.username for u in UM.list_locked(auth)] == ["ann"]


def test_list_inactive(auth):
    _user(auth, "ann", active=False)
    _user(auth, "bob")
    assert [u.username for u in UM.list_inactive(auth)] == ["ann"]


# ── snapshot ──

def test_snapshot_empty(auth):
    s = UM.snapshot(auth)
    assert (s.locked, s.inactive, s.admins) == (0, 0, 0)
    assert s.summary.total == 0 and s.matrix.systems == []


def test_snapshot_aggregates(auth):
    _user(auth, "ann", systems=[("primary", "admin")])
    _user(auth, "bob", systems=[("primary", "teacher")], active=False)
    _user(auth, "cat", systems=[("secondary", "staff")], locked_until=_future())
    _user(auth, "dan", systems=[("primary", "admin")], locked_until=_future())
    s = UM.snapshot(auth)
    assert (s.locked, s.inactive, s.admins) == (2, 1, 2)
    assert (s.summary.total, s.summary.active, s.summary.primary_users) == (4, 3, 3)
    assert s.role_distribution_primary["admin"] == 2
    assert s.role_distribution_primary["teacher"] == 1
    assert [x.system_key for x in s.matrix.systems] == ["primary", "secondary"]
    assert [u.username for u in s.matrix.users_without_primary] == ["cat"]
