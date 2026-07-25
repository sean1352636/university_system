"""Tests for EDU_DEV_SEED gating of the weak default accounts.

A fresh *production* database (EDU_DEV_SEED unset) must NOT be auto-provisioned
with the well-known weak demo accounts (admin/admin123 etc.). It may instead be
bootstrapped with a single strong admin via EDU_INITIAL_ADMIN_* env vars.
"""

import os

import pytest

from education_system.shared.auth.db import connect
from education_system.shared.auth.schema import initialise_auth_db, seed_default_users


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    """Path to a freshly-initialised (empty) auth DB with seeding env cleared."""
    for var in (
        "EDU_DEV_SEED",
        "EDU_INITIAL_ADMIN_USER",
        "EDU_INITIAL_ADMIN_PASSWORD",
        "EDU_INITIAL_ADMIN_EMAIL",
    ):
        monkeypatch.delenv(var, raising=False)
    path = str(tmp_path / "auth.db")
    initialise_auth_db(path)
    return path


def _usernames(path):
    conn = connect(path)
    try:
        return {r["username"] for r in conn.execute("SELECT username FROM users")}
    finally:
        conn.close()


def test_fresh_prod_db_has_no_weak_defaults(fresh_db):
    """Flag unset + no bootstrap env → zero accounts (no admin/admin123)."""
    seed_default_users(fresh_db)
    assert _usernames(fresh_db) == set()


def test_dev_seed_creates_demo_accounts(fresh_db, monkeypatch):
    """EDU_DEV_SEED=true → the full weak demo set is seeded, forced-change."""
    monkeypatch.setenv("EDU_DEV_SEED", "true")
    seed_default_users(fresh_db)
    names = _usernames(fresh_db)
    assert {"admin", "superadmin"} <= names

    conn = connect(fresh_db)
    try:
        row = conn.execute(
            "SELECT must_change_password FROM users WHERE username = 'admin'"
        ).fetchone()
    finally:
        conn.close()
    assert row["must_change_password"] == 1


def test_env_bootstrap_creates_single_strong_admin(fresh_db, monkeypatch):
    """EDU_INITIAL_ADMIN_* → one admin, not forced to change its own password."""
    monkeypatch.setenv("EDU_INITIAL_ADMIN_USER", "root_admin")
    monkeypatch.setenv("EDU_INITIAL_ADMIN_PASSWORD", "S3cure-Passw0rd!")
    seed_default_users(fresh_db)

    assert _usernames(fresh_db) == {"root_admin"}
    conn = connect(fresh_db)
    try:
        row = conn.execute(
            "SELECT must_change_password FROM users WHERE username = 'root_admin'"
        ).fetchone()
        systems = {
            r["system_key"]
            for r in conn.execute(
                "SELECT us.system_key FROM user_systems us "
                "JOIN users u ON u.id = us.user_id WHERE u.username = 'root_admin'"
            )
        }
    finally:
        conn.close()
    assert row["must_change_password"] == 0
    assert systems == {"university", "sixth_form", "secondary", "primary", "nursery"}


def test_env_bootstrap_rejects_weak_password(fresh_db, monkeypatch):
    """A too-short bootstrap password is refused; no account is created."""
    monkeypatch.setenv("EDU_INITIAL_ADMIN_USER", "root_admin")
    monkeypatch.setenv("EDU_INITIAL_ADMIN_PASSWORD", "short")
    seed_default_users(fresh_db)
    assert _usernames(fresh_db) == set()
