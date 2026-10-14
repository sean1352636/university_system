"""The canonical ``students`` migration, and the revision contract around it.

``e4a17c9d3b52`` is the first migration to own ``students``. Before it, the
table was whatever the first of 48 disagreeing ``CREATE TABLE`` statements
happened to produce, then widened by scattered ``ALTER TABLE`` calls in
unrelated modules.
"""

from __future__ import annotations

import ast
import re
import sqlite3
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
VERSIONS = REPO_ROOT / "src" / "education_system" / "migrations" / "versions"
MIGRATION = VERSIONS / "e4a17c9d3b52_canonical_students_table.py"


def _load_migration_constants() -> dict:
    tree = ast.parse(MIGRATION.read_text(encoding="utf-8"))
    out: dict = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                name = getattr(target, "id", None)
                if name in ("STUDENT_COLUMNS", "INDEXES"):
                    out[name] = ast.literal_eval(node.value)
        elif isinstance(node, ast.AnnAssign):
            # The migration annotates its constants, so STUDENT_COLUMNS and
            # INDEXES arrive here rather than in the Assign branch above.
            name = getattr(node.target, "id", None)
            if node.value is not None and name in (
                    "STUDENT_COLUMNS", "INDEXES", "revision", "down_revision"):
                out[name] = ast.literal_eval(node.value)
    return out


def _revision_graph() -> dict[str, str | None]:
    graph: dict[str, str | None] = {}
    for path in VERSIONS.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        rev = re.search(r'^revision: str = ["\']([^"\']+)', text, re.M)
        down = re.search(r'^down_revision[^=]*= ["\']?([^"\'\n]+)', text, re.M)
        if not rev or not down:
            continue
        target = down.group(1).strip()
        graph[rev.group(1)] = None if target == "None" else target
    return graph


def _heads() -> list[str]:
    graph = _revision_graph()
    parents = {v for v in graph.values() if v}
    return sorted(r for r in graph if r not in parents)


def test_single_head():
    """One linear chain. Two heads make ``alembic upgrade head`` ambiguous.

    Deliberately does not name the head: it moves with every migration, and
    hard-coding it made this test assert a revision three migrations stale
    while the real head drifted. ``test_required_revision_is_head`` is what
    ties the head to the constant the application enforces.
    """
    heads = _heads()
    assert len(heads) == 1, f"expected one head, found {heads}"


def test_required_revision_is_head():
    """``require_supported_schema`` demands an exact match, so a stale
    constant stops the API server against a correctly migrated database.

    This is not hypothetical: the constant sat at ``c3e58a7b91f4`` while the
    chain had moved on to ``b4e19d7a3c62``, and ``create_app()`` refused to
    start against a database that was migrated perfectly correctly.
    """
    from education_system.systems.university.infrastructure.database.schema_version import (
        REQUIRED_REVISION,
    )
    heads = _heads()
    assert len(heads) == 1, f"expected one head, found {heads}"
    assert REQUIRED_REVISION == heads[0], (
        f"REQUIRED_REVISION is {REQUIRED_REVISION} but the Alembic head is "
        f"{heads[0]}. Bump the constant in the same commit as the migration."
    )


def test_upgrade_creates_the_table_on_an_empty_database(tmp_path):
    constants = _load_migration_constants()
    columns = constants["STUDENT_COLUMNS"]
    conn = sqlite3.connect(tmp_path / "fresh.db")
    try:
        body = ",\n    ".join(f'"{n}" {d}' for n, d in columns)
        conn.execute(f"CREATE TABLE IF NOT EXISTS students (\n    {body}\n)")
        for statement in constants["INDEXES"]:
            conn.execute(statement)
        present = {row[1] for row in conn.execute("PRAGMA table_info(students)")}
        assert present == {n for n, _ in columns}
    finally:
        conn.close()


def test_upgrade_widens_an_existing_narrow_table(tmp_path):
    """The upgrade must be additive: an established database keeps its rows."""
    constants = _load_migration_constants()
    columns = constants["STUDENT_COLUMNS"]
    conn = sqlite3.connect(tmp_path / "old.db")
    try:
        conn.execute("CREATE TABLE students (student_id TEXT PRIMARY KEY, "
                     "first_name TEXT, last_name TEXT)")
        conn.execute("INSERT INTO students VALUES ('S1', 'Ada', 'Lovelace')")

        existing = {row[1] for row in conn.execute("PRAGMA table_info(students)")}
        for name, decl in columns:
            if name in existing or "PRIMARY KEY" in decl.upper():
                continue
            conn.execute(f'ALTER TABLE students ADD COLUMN "{name}" {decl}')

        present = {row[1] for row in conn.execute("PRAGMA table_info(students)")}
        assert present == {n for n, _ in columns}
        assert conn.execute(
            "SELECT first_name FROM students WHERE student_id='S1'"
        ).fetchone() == ("Ada",)
    finally:
        conn.close()


@pytest.mark.parametrize("column", [
    "academic_year", "mode_of_study", "campus_code",
    "expected_return_date", "record_closed_at",
])
def test_lifecycle_columns_are_declared(column):
    """``student_lifecycle.ensure_schema`` requires these via
    ``require_tables``. They previously existed only because an unrelated
    bootstrap had already run, so a fresh database failed there."""
    columns = {n for n, _ in _load_migration_constants()["STUDENT_COLUMNS"]}
    assert column in columns
