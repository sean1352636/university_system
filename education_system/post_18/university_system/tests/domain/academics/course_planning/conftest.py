"""Shared fixtures for the course-planning service tests.

``PlanningService`` reaches the DB through the shared ``get_connection`` /
``transaction`` helpers, which resolve the target file from the module-level
``DEFAULT_DB_PATH``. Repointing that constant at a per-test temp file gives
full isolation; the service creates all of its own tables on construction
(``_ensure_tables_exist``), guarded by a per-path ``_schema_ready`` set, so a
fresh path always re-initialises.

A couple of read paths (``get_semester_plan``) LEFT JOIN the external
``courses`` / ``modules`` catalog tables, so we create empty stand-ins for
those to keep the SQL valid without pulling in the whole catalog schema.
"""

import pytest

from education_system.post_18.university_system.infrastructure.database.db import sqlite3


@pytest.fixture()
def planning_service(tmp_path, monkeypatch):
    db_path = str(tmp_path / "planning.db")

    # Seed a WAL DB with the minimal external catalog tables the service's
    # JOINs reference (empty is fine — the joins are LEFT JOINs).
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=OFF")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS courses "
        "(code TEXT, name TEXT, course_name TEXT, credits INTEGER, department TEXT)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS modules "
        "(module_code TEXT, module_name TEXT, credits INTEGER, department TEXT)"
    )
    conn.commit()
    conn.close()

    # Point the shared DB layer at our temp file.
    monkeypatch.setattr(
        "education_system.post_18.university_system.infrastructure.database.db.DEFAULT_DB_PATH",
        db_path,
    )
    # Keep the schema-ready guard from short-circuiting init for this path,
    # and don't leak our temp path into other tests' state.
    from education_system.post_18.university_system.modules.domain.academics.course_planning.services.planning_service import (
        PlanningService,
    )

    PlanningService._schema_ready.discard(db_path)
    # log_activity would write to a separate activity store; neutralise it.
    monkeypatch.setattr(
        "education_system.post_18.university_system.modules.domain.academics."
        "course_planning.services.planning_service.log_activity",
        lambda *a, **k: None,
    )

    svc = PlanningService()
    yield svc
    PlanningService._schema_ready.discard(db_path)


@pytest.fixture()
def lesson_db(tmp_path, monkeypatch):
    """Point the shared DB layer at a temp file holding the two planner tables
    that the Lesson Planner GUI normally creates (lesson_service does raw CRUD
    over them but does not create them itself)."""
    db_path = str(tmp_path / "lessons.db")
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=OFF")
    conn.execute(
        "CREATE TABLE lesson_plans ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, course TEXT, title TEXT, "
        "instructor TEXT, type TEXT, day TEXT, start TEXT, end TEXT, room TEXT, "
        "notes TEXT, updated_at TEXT, updated_by TEXT)"
    )
    conn.execute(
        "CREATE TABLE lesson_courses ("
        "code TEXT PRIMARY KEY, name TEXT, dept TEXT, credits TEXT, "
        "semester TEXT, description TEXT, updated_at TEXT, updated_by TEXT)"
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(
        "education_system.post_18.university_system.infrastructure.database.db.DEFAULT_DB_PATH",
        db_path,
    )
    return db_path
