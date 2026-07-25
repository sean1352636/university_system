"""Shared fixtures for staff-HR manager service tests.

Provides a fresh, empty SQLite database with the full Staff-HR schema
initialised, isolated from the seeded template DB used elsewhere (whose
pre-existing ``documents`` table lacks columns the schema installer expects).
"""

import pytest

import education_system.systems.university.infrastructure.database.db as _db
from education_system.systems.university.infrastructure.database.schemas.staff_hr_schemas_all import (
    init_staff_hr_schemas,
)


@pytest.fixture
def hr_db(tmp_path, monkeypatch):
    """Point the DB layer at a fresh temp file and install the Staff-HR schema."""
    db_path = str(tmp_path / "hr_test.db")
    monkeypatch.setattr(_db, "DEFAULT_DB_PATH", db_path)
    monkeypatch.setattr(_db, "DEFAULT_DB_NAME", "hr_test.db")
    init_staff_hr_schemas()
    return db_path
