"""Restaurant user access: roles, grant/remove, audit, and staying out of the login session."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from education_system.systems.university.plugins.campus_commerce.domain.services.restaurant.operations import (
    user_access,
)


class FakeAuth:
    """A signed-in person whose login role gives exactly *permissions*."""

    def __init__(self, username, *permissions):
        self.current_user = {"username": username, "role": "staff", "permissions": list(permissions)}

    def check_permission(self, permission):
        return permission in self.current_user["permissions"]


ADMIN = FakeAuth("admin", "system_config", "manage_finances", "manage_menu", "manage_inventory",
                 "manage_reservations", "manage_takeaway_restaurants",
                 "update_takeaway_order_status")


def build_env(monkeypatch, tmp_path: Path):
    """Point the module at scratch databases; nothing reaches the live ones."""
    records = tmp_path / "records.db"
    conn = sqlite3.connect(records)
    conn.execute("""CREATE TABLE restaurant_staff (
        staff_id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, role TEXT NOT NULL,
        status TEXT DEFAULT 'Active', is_active BOOLEAN DEFAULT 1)""")
    conn.executemany("INSERT INTO restaurant_staff (name, role) VALUES (?, ?)",
                     [("Ana Cook", "Chef"), ("Ben Host", "Server"), ("Cy Boss", "Manager")])
    conn.commit()
    conn.close()

    logins = tmp_path / "auth.db"
    conn = sqlite3.connect(logins)
    conn.execute("""CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, display_name TEXT,
                                         email TEXT, is_active INTEGER)""")
    conn.execute("CREATE TABLE user_systems (id INTEGER PRIMARY KEY, user_id INTEGER, system_key TEXT, role TEXT)")
    for user_id, (name, role, active) in enumerate(
            [("ana", "staff", 1), ("ben", "staff", 1), ("cy", "staff", 1), ("gone", "staff", 0),
             ("stu", "student", 1)], 1):
        conn.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?)",
                     (user_id, name, name.title(), f"{name}@x.test", active))
        conn.execute("INSERT INTO user_systems (user_id, system_key, role) VALUES (?, 'university', ?)",
                     (user_id, role))
    conn.commit()
    conn.close()

    monkeypatch.setattr(user_access, "DEFAULT_DB_PATH", records)
    monkeypatch.setattr(user_access, "_auth_connect", lambda: sqlite3.connect(logins))
    return records


@pytest.fixture
def records(monkeypatch, tmp_path):
    return build_env(monkeypatch, tmp_path)


def _query(records, sql, *params):
    conn = sqlite3.connect(records)
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def test_role_decides_what_a_person_can_do(records):
    user_access.grant_access(ADMIN, "ana", 1, "Kitchen")
    ana = FakeAuth("ana")
    assert user_access.can(ana, "update_takeaway_order_status")
    assert user_access.can(ana, "manage_inventory")
    assert not user_access.can(ana, "manage_finances")
    assert user_access.allowed_sections(ana) == {"place_order", "orders", "inventory"}


def test_role_is_not_added_to_the_login_session(records):
    user_access.grant_access(ADMIN, "ben", 2, "Finance")
    ben = FakeAuth("ben")
    assert user_access.can(ben, "manage_finances")
    # University finance screens ask the login directly, which must still say no.
    assert not ben.check_permission("manage_finances")


def test_removal_also_takes_away_what_the_login_role_allowed(records):
    ben = FakeAuth("ben", "manage_reservations")
    user_access.grant_access(ADMIN, "ben", 2, "Server")
    assert user_access.can(ben, "manage_reservations")
    user_access.remove_access(ADMIN, "ben", "Moved team")
    assert not user_access.can(ben, "manage_reservations")
    assert user_access.allowed_sections(ben) == set()


def test_login_role_still_applies_with_no_access_row(records):
    assert user_access.can(FakeAuth("ben", "manage_reservations"), "manage_reservations")
    assert not user_access.can(FakeAuth("ben"), "manage_menu")


def test_admin_can_open_every_section(records):
    assert user_access.allowed_sections(ADMIN) >= set(user_access.SECTION_PERMISSIONS) | {"users"}


def test_terminated_staff_lose_access_and_keep_their_record(records):
    user_access.grant_access(ADMIN, "ana", 1, "Kitchen")
    user_access.remove_for_leaver(1, "admin")
    assert not user_access.can(FakeAuth("ana"), "manage_inventory")
    assert _query(records, "SELECT name FROM restaurant_staff WHERE staff_id = 1") == [("Ana Cook",)]
    row = user_access.list_access(ADMIN)[0]
    assert (row["active"], row["state"], row["removed_reason"]) == (False, "Removed", "Staff member left")


@pytest.mark.parametrize("status", ["Terminated", "Inactive", "On Leave"])
def test_access_stops_while_staff_record_is_not_active(records, status):
    user_access.grant_access(ADMIN, "ana", 1, "Kitchen")
    conn = sqlite3.connect(records)
    conn.execute("UPDATE restaurant_staff SET status = ? WHERE staff_id = 1", (status,))
    conn.commit()
    conn.close()
    assert not user_access.can(FakeAuth("ana"), "manage_inventory")
    assert user_access.list_access(ADMIN)[0]["state"].startswith("Blocked")


def test_every_change_is_audited_with_who_and_what(records):
    user_access.grant_access(ADMIN, "ana", 1, "Kitchen")
    user_access.change_role(ADMIN, "ana", "Server")
    user_access.remove_access(ADMIN, "ana", "Left kitchen")
    history = user_access.access_history(ADMIN, "ana")
    assert [row["action"] for row in history] == ["REMOVE_ACCESS", "CHANGE_ACCESS_ROLE", "GRANT_ACCESS"]
    assert {row["user_id"] for row in history} == {"admin"}
    assert '"Server"' in history[1]["new_values"] and '"Kitchen"' in history[1]["old_values"]


def test_regrant_restores_access(records):
    user_access.grant_access(ADMIN, "ana", 1, "Kitchen")
    user_access.remove_access(ADMIN, "ana")
    user_access.grant_access(ADMIN, "ana", 1, "Server")
    assert user_access.can(FakeAuth("ana"), "manage_reservations")
    assert len(_query(records, "SELECT 1 FROM restaurant_user_access")) == 1


@pytest.mark.parametrize("username, staff_id, role, message", [
    ("stu", 1, "Kitchen", "isn't an active university staff login"),
    ("gone", 1, "Kitchen", "isn't an active university staff login"),
    ("ana", 99, "Kitchen", "no longer exists"),
    ("ana", 1, "Owner", "Choose a restaurant role"),
])
def test_grant_refuses_bad_input(records, username, staff_id, role, message):
    with pytest.raises(user_access.AccessError, match=message):
        user_access.grant_access(ADMIN, username, staff_id, role)


def test_one_staff_member_links_to_one_login(records):
    user_access.grant_access(ADMIN, "ana", 1, "Kitchen")
    with pytest.raises(user_access.AccessError, match="already linked"):
        user_access.grant_access(ADMIN, "ben", 1, "Server")


def test_only_admin_or_manager_can_manage(records):
    user_access.grant_access(ADMIN, "ana", 1, "Supervisor")
    for action in (lambda a: user_access.grant_access(a, "ben", 2, "Server"),
                   user_access.list_access, user_access.access_history):
        with pytest.raises(user_access.AccessError):
            action(FakeAuth("ana"))


def test_manager_limits(records):
    user_access.grant_access(ADMIN, "cy", 3, user_access.MANAGER)
    cy = FakeAuth("cy")
    assert "users" in user_access.allowed_sections(cy)

    user_access.grant_access(cy, "ana", 1, "Kitchen")
    with pytest.raises(user_access.AccessError, match="Only an administrator"):
        user_access.grant_access(cy, "ben", 2, user_access.MANAGER)
    with pytest.raises(user_access.AccessError, match="Only an administrator"):
        user_access.change_role(cy, "ana", user_access.MANAGER)
    with pytest.raises(user_access.AccessError, match="your own access"):
        user_access.remove_access(cy, "CY")


def test_manager_cannot_change_another_manager(records):
    user_access.grant_access(ADMIN, "cy", 3, user_access.MANAGER)
    user_access.grant_access(ADMIN, "ana", 1, user_access.MANAGER)
    with pytest.raises(user_access.AccessError, match="Only an administrator"):
        user_access.remove_access(FakeAuth("cy"), "ana")


def test_find_logins_hides_current_access_and_non_staff(records):
    user_access.grant_access(ADMIN, "ana", 1, "Kitchen")
    assert [login["username"] for login in user_access.find_logins(ADMIN)] == ["ben", "cy"]
    assert [login["username"] for login in user_access.find_logins(ADMIN, "be")] == ["ben"]
    assert [s["staff_id"] for s in user_access.staff_available(ADMIN)] == [2, 3]


def test_database_failure_refuses_non_admins(monkeypatch, records):
    user_access.grant_access(ADMIN, "ben", 2, "Server")

    def broken():
        raise sqlite3.OperationalError("disk I/O error")

    monkeypatch.setattr(user_access, "_connect", broken)
    assert not user_access.can(FakeAuth("ben", "manage_reservations"), "manage_reservations")
    assert user_access.can(ADMIN, "manage_menu")


def test_missing_table_means_no_rows_yet(records):
    assert user_access.can(FakeAuth("ben", "manage_reservations"), "manage_reservations")
    assert not user_access.can_manage(FakeAuth("ben"))
