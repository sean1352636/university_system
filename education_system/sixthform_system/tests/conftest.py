"""Shared fixtures for Sixth Form tests."""

from __future__ import annotations

import pytest


@pytest.fixture
def fresh_ay_db(tmp_path, monkeypatch):
    """Point the Academic Year data module at a brand-new SQLite file.

    Returns the data module so tests can call its API directly.
    """
    db_path = tmp_path / "ay.db"
    from education_system.sixthform_system.modules.domain.academics.academic_year import (
        academic_year as data,
    )
    monkeypatch.setattr(data, "DB_PATH", str(db_path))
    monkeypatch.setattr(data, "_DB_READY", False)
    # Reset RBAC defaults so a previous test can't leak.
    monkeypatch.setattr(data, "ENFORCE_RBAC", False)
    monkeypatch.setattr(data, "CURRENT_ACTOR_ROLE", None)
    monkeypatch.setattr(data, "CURRENT_ACTOR", None)
    data.init_db()
    return data
