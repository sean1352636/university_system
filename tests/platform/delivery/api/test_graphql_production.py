from __future__ import annotations

import sqlite3

import pytest

from education_system.platform.delivery.api.graphql import resolvers
from education_system.platform.delivery.api.graphql.schema import schema


def _student_db(path):
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE students (
            id INTEGER PRIMARY KEY,
            student_id TEXT,
            first_name TEXT,
            last_name TEXT,
            email TEXT,
            status TEXT
        );
        INSERT INTO students VALUES (1, 'U001', 'Ada', 'Lovelace',
                                     'ada@example.test', 'active');
        """
    )
    conn.close()


def test_graphql_queries_require_authentication(tmp_path):
    db = tmp_path / "university.db"
    _student_db(db)
    original = resolvers._DB_PATHS["university"]
    resolvers.configure_database_path("university", db)
    try:
        anonymous = schema.execute_sync(
            '{ students(system: "university") { studentId } }', context_value={}
        )
        assert anonymous.errors
        assert "Authentication is required" in str(anonymous.errors[0])

        authenticated = schema.execute_sync(
            '{ students(system: "university") { studentId firstName } }',
            context_value={"user_info": {"sub": "reader", "role": "student"}},
        )
        assert authenticated.errors is None
        assert authenticated.data == {
            "students": [{"studentId": "U001", "firstName": "Ada"}]
        }
    finally:
        resolvers._DB_PATHS["university"] = original


def test_graphql_mutations_enforce_roles():
    result = schema.execute_sync(
        """
        mutation {
          deleteStudent(system: "university", studentId: "U001")
        }
        """,
        context_value={"user_info": {"sub": "staff-user", "role": "staff"}},
    )
    assert result.errors
    assert "Insufficient permissions" in str(result.errors[0])


def test_all_five_canonical_database_paths_are_registered():
    assert set(resolvers._DB_PATHS) == {
        "nursery",
        "primary",
        "secondary",
        "sixth_form",
        "university",
    }
    assert all("post_18" not in str(path) for path in resolvers._DB_PATHS.values())


@pytest.mark.parametrize(
    ("system", "table", "id_column"),
    [
        ("nursery", "pupils", "pupil_id"),
        ("primary", "pupils", "pupil_id"),
        ("secondary", "pupils", "pupil_id"),
        ("sixth_form", "students", "student_id"),
        ("university", "students", "student_id"),
    ],
)
def test_student_query_adapter_supports_every_system(
    tmp_path, system, table, id_column
):
    db = tmp_path / f"{system}.db"
    conn = sqlite3.connect(db)
    conn.execute(
        f"""CREATE TABLE {table} (
            {id_column} TEXT PRIMARY KEY,
            first_name TEXT,
            last_name TEXT,
            status TEXT
        )"""
    )
    conn.execute(
        f"INSERT INTO {table} VALUES (?, ?, ?, ?)",
        ("P001", "Grace", "Hopper", "active"),
    )
    conn.commit()
    conn.close()
    original = resolvers._DB_PATHS[system]
    resolvers.configure_database_path(system, db)
    try:
        students = resolvers.resolve_students(system)
        assert [(student.student_id, student.first_name) for student in students] == [
            ("P001", "Grace")
        ]
    finally:
        resolvers._DB_PATHS[system] = original
