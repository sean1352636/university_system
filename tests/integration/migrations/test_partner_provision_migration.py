"""The partner-provision and student-mobility migration.

The migration executes the DDL held by the two modules rather than a copy
of it, so the runtime bootstrap and a freshly migrated database cannot
drift. These tests check that the arrangement holds: that the statement
lists are still the ones the migration reaches for, that applying them
produces every table, index and trigger, and that doing it twice is a
no-op.
"""

from __future__ import annotations

import ast
import re
import sqlite3
from pathlib import Path

import pytest

from education_system.systems.university.domains.curriculum.domain.collaborative_provision import (
    _db_init as collaborative,
)
from education_system.systems.university.domains.curriculum.domain.student_mobility import (
    _db_init as mobility,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
VERSIONS = REPO_ROOT / "src" / "education_system" / "migrations" / "versions"
MIGRATION = VERSIONS / "a91c47e2f8d3_partner_provision_and_student_mobility.py"

EXPECTED_TABLES = {
    "partner_institutions", "partnership_agreements",
    "collaborative_programmes", "partner_cohorts", "partner_reviews",
    "mobility_agreements", "mobility_placements",
    "mobility_learning_agreements", "mobility_credit_recognitions",
}

EXPECTED_TRIGGERS = {
    "partner_institutions_touch", "partnership_agreements_touch",
    "partner_review_sets_agreement_due", "mobility_placements_touch",
    "mobility_recognition_rollup_insert", "mobility_recognition_rollup_delete",
}


def _statements() -> list[str]:
    return [
        collaborative._CREATE_PARTNERS,
        collaborative._CREATE_AGREEMENTS,
        collaborative._CREATE_PROGRAMMES,
        collaborative._CREATE_COHORTS,
        collaborative._CREATE_REVIEWS,
        *collaborative._INDEXES,
        collaborative._TRIGGER_TOUCH_PARTNER,
        collaborative._TRIGGER_TOUCH_AGREEMENT,
        collaborative._TRIGGER_REVIEW_SETS_DUE,
        mobility._CREATE_AGREEMENTS,
        mobility._CREATE_PLACEMENTS,
        mobility._CREATE_LEARNING_AGREEMENTS,
        mobility._CREATE_RECOGNITIONS,
        *mobility._INDEXES,
        mobility._TRIGGER_TOUCH_PLACEMENT,
        mobility._TRIGGER_ROLLUP_INSERT,
        mobility._TRIGGER_ROLLUP_DELETE,
    ]


@pytest.fixture()
def applied(tmp_path) -> sqlite3.Connection:
    conn = sqlite3.connect(tmp_path / "migrated.db")
    conn.execute("PRAGMA foreign_keys = ON")
    for statement in _statements():
        conn.execute(statement)
    conn.commit()
    yield conn
    conn.close()


def test_migration_references_the_module_ddl():
    """If the migration ever inlines its own copy of the DDL, the two can
    drift silently — which is the failure mode this whole exercise was
    about. Assert it still reaches into the modules."""
    source = MIGRATION.read_text(encoding="utf-8")
    assert "collaborative._CREATE_PARTNERS" in source
    assert "mobility._CREATE_PLACEMENTS" in source
    assert re.search(r"CREATE\s+TABLE", source, re.IGNORECASE) is None, (
        "the migration should execute the modules' DDL, not restate it"
    )


def test_revision_chain():
    source = MIGRATION.read_text(encoding="utf-8")
    tree = ast.parse(source)
    values = {}
    for node in tree.body:
        if isinstance(node, ast.AnnAssign):
            name = getattr(node.target, "id", None)
            if name in ("revision", "down_revision") and node.value:
                values[name] = ast.literal_eval(node.value)
    assert values["revision"] == "a91c47e2f8d3"
    assert values["down_revision"] == "f7b3d81e4c69"


def test_every_table_is_created(applied):
    tables = {row[0] for row in applied.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert EXPECTED_TABLES <= tables


def test_every_trigger_is_created(applied):
    triggers = {row[0] for row in applied.execute(
        "SELECT name FROM sqlite_master WHERE type='trigger'")}
    assert EXPECTED_TRIGGERS <= triggers


def test_applying_twice_is_a_no_op(applied):
    before = sorted(row[0] for row in applied.execute(
        "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL"))
    for statement in _statements():
        applied.execute(statement)
    after = sorted(row[0] for row in applied.execute(
        "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL"))
    assert before == after


def test_downgrade_lists_children_before_parents():
    """Dropping a parent first would fail with foreign keys on."""
    source = MIGRATION.read_text(encoding="utf-8")
    order = [t for t in re.findall(r'"([a-z_]+)"', source)]
    dropped = [t for t in order if t in EXPECTED_TABLES]
    for parent, child in (
        ("partner_institutions", "partnership_agreements"),
        ("partnership_agreements", "collaborative_programmes"),
        ("collaborative_programmes", "partner_cohorts"),
        ("mobility_agreements", "mobility_placements"),
        ("mobility_placements", "mobility_credit_recognitions"),
    ):
        assert dropped.index(child) < dropped.index(parent), (
            f"{child} must be dropped before {parent}"
        )


def test_credit_rollup_trigger_works(applied):
    """The rollup is what keeps credits_recognised honest whichever
    interface wrote the recognition row."""
    applied.execute(
        "INSERT INTO mobility_placements (student_id, host_institution, "
        "credits_expected) VALUES ('S1', 'Uppsala', 60)")
    placement_id = applied.execute(
        "SELECT placement_id FROM mobility_placements").fetchone()[0]
    applied.execute(
        "INSERT INTO mobility_credit_recognitions "
        "(placement_id, home_credits, outcome) VALUES (?, 30, 'Recognised')",
        (placement_id,))
    assert applied.execute(
        "SELECT credits_recognised FROM mobility_placements "
        "WHERE placement_id = ?", (placement_id,)).fetchone()[0] == 30

    applied.execute("DELETE FROM mobility_credit_recognitions")
    assert applied.execute(
        "SELECT credits_recognised FROM mobility_placements "
        "WHERE placement_id = ?", (placement_id,)).fetchone()[0] == 0
