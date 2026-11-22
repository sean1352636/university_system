"""Repair of sixth-form table links (infrastructure.schema_repair)."""

from __future__ import annotations

import sqlite3

import pytest

from education_system.systems.primary.infrastructure import schema_repair as SR


@pytest.fixture
def db(primary_sandbox, tmp_path):
    """A hand-made database shaped like the broken sixth-form ports."""
    path = tmp_path / "broken.db"
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE pupils (pupil_id TEXT PRIMARY KEY, name TEXT);
        INSERT INTO pupils VALUES ('P1', 'Ann'), ('P2', 'Ben');

        CREATE TABLE hs_incidents (
            incident_id INTEGER PRIMARY KEY AUTOINCREMENT,
            affected_student_id TEXT,
            note TEXT NOT NULL,
            FOREIGN KEY(affected_student_id)
                REFERENCES students(student_id) ON DELETE SET NULL
        );
        CREATE INDEX ix_inc_student ON hs_incidents(affected_student_id);
        CREATE TABLE audit (msg TEXT);
        CREATE TRIGGER trg_inc AFTER INSERT ON hs_incidents
            BEGIN INSERT INTO audit VALUES ('inc ' || NEW.note); END;
        INSERT INTO hs_incidents (affected_student_id, note) VALUES ('P1', 'fell'), (NULL, 'spill');

        CREATE TABLE messages (
            message_id INTEGER PRIMARY KEY,
            student_id TEXT REFERENCES students(student_id),
            alumni_id INTEGER,
            body TEXT,
            FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id) ON DELETE CASCADE
        );
        INSERT INTO messages VALUES (1, 'P2', 7, 'hello');

        CREATE TABLE clean (id INTEGER PRIMARY KEY, pupil_id TEXT REFERENCES pupils(pupil_id));
    """)
    conn.commit()
    conn.close()
    return path


def _sql(conn, name, kind="table"):
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type=? AND name=?",
                       (kind, name)).fetchone()
    return row[0] if row else None


def test_repair_rebuilds_only_broken_tables(db):
    assert sorted(SR.repair_links(db)) == ["hs_incidents", "messages"]


def test_rows_are_kept(db):
    SR.repair_links(db)
    conn = sqlite3.connect(db)
    try:
        assert conn.execute("SELECT incident_id, affected_student_id, note FROM hs_incidents "
                            "ORDER BY incident_id").fetchall() == [(1, "P1", "fell"),
                                                                   (2, None, "spill")]
        assert conn.execute("SELECT * FROM messages").fetchall() == [(1, "P2", 7, "hello")]
    finally:
        conn.close()


def test_student_fk_repointed_and_alumni_fk_dropped(db):
    SR.repair_links(db)
    conn = sqlite3.connect(db)
    try:
        inc = {(r[2], r[3], r[4], r[6]) for r in conn.execute("PRAGMA foreign_key_list(hs_incidents)")}
        msg = {(r[2], r[3], r[4]) for r in conn.execute("PRAGMA foreign_key_list(messages)")}
        assert inc == {("pupils", "affected_student_id", "pupil_id", "SET NULL")}
        assert msg == {("pupils", "student_id", "pupil_id")}
        for name in ("hs_incidents", "messages"):
            sql = _sql(conn, name)
            assert "students" not in sql and "alumni(" not in sql
            assert "__repaired" not in sql
        assert not conn.execute("SELECT name FROM sqlite_master WHERE name LIKE '%__repaired'"
                                ).fetchall()
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        conn.close()


def test_indexes_and_triggers_recreated(db):
    SR.repair_links(db)
    conn = sqlite3.connect(db)
    try:
        assert "affected_student_id" in _sql(conn, "ix_inc_student", "index")
        assert _sql(conn, "trg_inc", "trigger") is not None
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("INSERT INTO hs_incidents (affected_student_id, note) VALUES ('P2', 'cut')")
        conn.commit()
        assert conn.execute("SELECT msg FROM audit").fetchall()[-1] == ("inc cut",)
    finally:
        conn.close()


def test_repaired_tables_accept_inserts_with_fks_on(db):
    SR.repair_links(db)
    conn = sqlite3.connect(db)
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("INSERT INTO messages (student_id, alumni_id, body) VALUES ('P2', 99, 'x')")
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO hs_incidents (affected_student_id, note) "
                         "VALUES ('NOPE', 'x')")
        conn.execute("DELETE FROM pupils WHERE pupil_id = 'P1'")
        assert conn.execute("SELECT affected_student_id FROM hs_incidents WHERE note='fell'"
                            ).fetchone() == (None,)
    finally:
        conn.close()


def test_second_call_is_noop(db):
    SR.repair_links(db)
    conn = sqlite3.connect(db)
    before = conn.execute("SELECT type, name, sql FROM sqlite_master ORDER BY name").fetchall()
    conn.close()
    assert SR.repair_links(db) == []
    SR._done.clear()                     # even a fresh process finds nothing to do
    assert SR.repair_links(db) == []
    conn = sqlite3.connect(db)
    after = conn.execute("SELECT type, name, sql FROM sqlite_master ORDER BY name").fetchall()
    conn.close()
    assert after == before


def test_clean_database_untouched(primary_sandbox, tmp_path):
    path = tmp_path / "clean.db"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE pupils (pupil_id TEXT PRIMARY KEY)")
    conn.execute("CREATE TABLE t (id INTEGER, p TEXT REFERENCES pupils(pupil_id))")
    conn.commit()
    conn.close()
    assert SR.repair_links(path) == []
