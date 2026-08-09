"""Behavioural tests for equality_diversity.schema."""

from __future__ import annotations

import json

from education_system.systems.university.domain.pastoral.equality_diversity import (
    schema,
)


def _table_names(conn):
    return {
        r[0]
        for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }


def test_migrate_creates_all_core_tables(raw):
    conn = raw()
    try:
        names = _table_names(conn)
    finally:
        conn.close()
    expected = {
        "ed_people", "ed_incidents", "ed_audit_log", "ed_incident_attachments",
        "ed_incident_notes", "ed_deletions", "ed_saved_searches",
        "ed_column_prefs", "ed_view_log", "ed_consent", "ed_anonymous_tokens",
        "ed_report_schedules", "ed_benchmarks",
    }
    assert expected <= names


def test_migrate_adds_extension_columns(raw):
    conn = raw()
    try:
        people_cols = {r[1] for r in conn.execute("PRAGMA table_info(ed_people)")}
        incident_cols = {r[1] for r in conn.execute("PRAGMA table_info(ed_incidents)")}
    finally:
        conn.close()
    # a sample of the columns added by _add_missing_columns
    assert {"student_id", "staff_id", "deleted_at", "course",
            "programme_level", "last_synced_at"} <= people_cols
    assert {"severity", "sla_deadline", "assigned_to", "anonymous",
            "referred_to"} <= incident_cols


def test_migrate_is_idempotent(raw):
    # Second call must not raise and must not duplicate benchmark seed rows.
    schema.migrate()
    schema.migrate()
    conn = raw()
    try:
        count = conn.execute("SELECT COUNT(*) FROM ed_benchmarks").fetchone()[0]
    finally:
        conn.close()
    expected = sum(len(v) for v in schema.DEFAULT_BASELINES.values())
    assert count == expected


def test_seed_benchmarks_only_seeds_once(raw):
    conn = raw()
    try:
        before = conn.execute("SELECT COUNT(*) FROM ed_benchmarks").fetchone()[0]
        # _seed_benchmarks should early-return because rows already exist
        schema._seed_benchmarks(conn)
        after = conn.execute("SELECT COUNT(*) FROM ed_benchmarks").fetchone()[0]
    finally:
        conn.close()
    assert before == after > 0


def test_get_connection_has_foreign_keys_on():
    conn = schema.get_connection()
    try:
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    finally:
        conn.close()


def test_add_missing_columns_skips_existing(raw):
    conn = raw()
    try:
        before = {r[1] for r in conn.execute("PRAGMA table_info(ed_people)")}
        # Re-running with the same column list should be a no-op (all present).
        schema._add_missing_columns(conn, "ed_people", schema._PEOPLE_COLUMNS)
        after = {r[1] for r in conn.execute("PRAGMA table_info(ed_people)")}
    finally:
        conn.close()
    assert before == after


def test_dump_schedule_config_roundtrips():
    payload = schema.dump_schedule_config(
        "Monthly gender", "monthly", "gender", "csv", "/tmp/out"
    )
    parsed = json.loads(payload)
    assert parsed == {
        "name": "Monthly gender", "cadence": "monthly", "field": "gender",
        "format": "csv", "output_dir": "/tmp/out",
    }
