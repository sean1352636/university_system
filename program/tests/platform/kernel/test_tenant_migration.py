from __future__ import annotations

import sqlite3

import pytest

from education_system.platform.kernel.core import tenant_db
from education_system.platform.kernel.core.tenant_db import TenantDatabaseManager


def test_legacy_database_migrates_into_isolated_tenant(tmp_path, monkeypatch):
    source = tmp_path / "legacy.db"
    with sqlite3.connect(source) as connection:
        connection.execute("CREATE TABLE students (student_id TEXT)")
        connection.execute("INSERT INTO students VALUES ('S1')")
    monkeypatch.setattr(tenant_db, "_TENANTS_BASE", (tmp_path / "tenants").resolve())

    destination = TenantDatabaseManager.migrate_database_to_tenant(
        source, "north", "university"
    )
    with sqlite3.connect(destination) as connection:
        assert connection.execute("SELECT student_id FROM students").fetchone()[0] == "S1"
    with pytest.raises(FileExistsError):
        TenantDatabaseManager.migrate_database_to_tenant(source, "north", "university")
