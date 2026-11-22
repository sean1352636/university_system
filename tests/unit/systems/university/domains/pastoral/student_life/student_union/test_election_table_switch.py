"""`elections` is the one Student Union election table.

Covers the schema helper (fresh creation, additive columns, legacy fold,
voting-window pairing), the reconcile that rebuilds child tables still keyed
to ``union_elections``, and the voting-methods service reading ``elections``.
All against throw-away SQLite files — never the live database.
"""
import sqlite3

import pytest

from education_system.systems.university.infrastructure.database.schemas import (
    student_union_elections_schema as schema,
)

_ELECTION_COLUMNS = {
    "id", "title", "description", "start_date", "end_date", "status", "department",
    "nomination_start", "nomination_end", "voting_start", "voting_end", "created_at",
}


def _connect(path):
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _columns(conn, table):
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def _fk_targets(conn, table):
    return {(row[2], row[4]) for row in conn.execute(f"PRAGMA foreign_key_list({table})")
            if row[3] == "election_id"}


def _students(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS students (student_id TEXT PRIMARY KEY, "
                 "first_name TEXT, last_name TEXT, course TEXT)")
    conn.execute("INSERT OR IGNORE INTO students VALUES ('S1', 'Ada', 'Lovelace', 'Maths')")
    conn.execute("INSERT OR IGNORE INTO students VALUES ('S2', 'Alan', 'Turing', 'CS')")


class TestFreshSchema:
    def test_fresh_database_has_full_elections_and_no_union_elections(self, tmp_path):
        conn = _connect(tmp_path / "fresh.db")
        schema.ensure_election_tables(conn.cursor())
        assert _columns(conn, "elections") == _ELECTION_COLUMNS
        assert conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'union_elections'"
                            ).fetchone() is None
        for child in ("election_candidates", "election_votes", "ranked_votes"):
            assert _fk_targets(conn, child) == {("elections", "id")}

    def test_old_elections_table_gains_columns_and_keeps_rows(self, tmp_path):
        conn = _connect(tmp_path / "old.db")
        conn.execute("CREATE TABLE elections (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                     "title TEXT NOT NULL, description TEXT, start_date TEXT, "
                     "end_date TEXT, status TEXT DEFAULT 'active')")
        conn.execute("INSERT INTO elections (title, start_date, end_date) "
                     "VALUES ('President', '2026-11-01', '2026-11-05')")
        schema.ensure_elections_table(conn.cursor())
        schema.ensure_elections_table(conn.cursor())  # idempotent
        assert _columns(conn, "elections") == _ELECTION_COLUMNS
        assert conn.execute("SELECT title FROM elections").fetchone()[0] == "President"

    def test_sync_voting_window_pairs_both_sides(self, tmp_path):
        conn = _connect(tmp_path / "sync.db")
        schema.ensure_elections_table(conn.cursor())
        conn.execute("INSERT INTO elections (title, start_date, end_date) "
                     "VALUES ('CLI made', '2026-11-01', '2026-11-05')")
        conn.execute("INSERT INTO elections (title, voting_start, voting_end) "
                     "VALUES ('Screen made', '2026-12-01', '2026-12-03')")
        schema.sync_voting_window(conn.cursor())
        rows = dict((r[0], r[1:]) for r in conn.execute(
            "SELECT title, start_date, end_date, voting_start, voting_end FROM elections"))
        assert rows["CLI made"] == ("2026-11-01", "2026-11-05", "2026-11-01", "2026-11-05")
        assert rows["Screen made"] == ("2026-12-01", "2026-12-03", "2026-12-01", "2026-12-03")


class TestLegacyFold:
    def _legacy(self, conn):
        conn.execute("CREATE TABLE union_elections (election_id INTEGER PRIMARY KEY "
                     "AUTOINCREMENT, position TEXT, department TEXT, nomination_start TEXT, "
                     "nomination_end TEXT, voting_start TEXT, voting_end TEXT, "
                     "status TEXT DEFAULT 'upcoming', created_at TEXT, description TEXT)")
        conn.execute("INSERT INTO union_elections VALUES (7, 'Treasurer', 'Law', '2026-10-01', "
                     "'2026-10-10', '2026-10-15', '2026-10-20', 'voting', '2026-09-30', 'desc')")

    def test_fold_copies_ids_and_all_dates_and_is_idempotent(self, tmp_path):
        conn = _connect(tmp_path / "fold.db")
        self._legacy(conn)
        assert schema.fold_legacy_union_elections(conn.cursor()) == 1
        assert schema.fold_legacy_union_elections(conn.cursor()) == 0
        row = conn.execute(
            "SELECT id, title, department, nomination_start, nomination_end, voting_start, "
            "voting_end, start_date, end_date, status, created_at, description "
            "FROM elections").fetchall()
        assert row == [(7, "Treasurer", "Law", "2026-10-01", "2026-10-10", "2026-10-15",
                        "2026-10-20", "2026-10-15", "2026-10-20", "voting", "2026-09-30",
                        "desc")]
        # The legacy table is left in place.
        assert conn.execute("SELECT COUNT(*) FROM union_elections").fetchone()[0] == 1

    def test_fold_backfills_rows_an_earlier_fold_copied_without_dates(self, tmp_path):
        conn = _connect(tmp_path / "backfill.db")
        self._legacy(conn)
        conn.execute("CREATE TABLE elections (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                     "title TEXT NOT NULL, description TEXT, start_date TEXT, "
                     "end_date TEXT, status TEXT DEFAULT 'active')")
        conn.execute("INSERT INTO elections VALUES (7, 'Treasurer', 'Law', '2026-10-15', "
                     "'2026-10-20', 'voting')")
        schema.fold_legacy_union_elections(conn.cursor())
        assert conn.execute(
            "SELECT nomination_start, nomination_end, voting_start, voting_end, department "
            "FROM elections WHERE id = 7").fetchone() == (
                "2026-10-01", "2026-10-10", "2026-10-15", "2026-10-20", "Law")

    def test_no_legacy_table_is_a_no_op(self, tmp_path):
        conn = _connect(tmp_path / "none.db")
        assert schema.fold_legacy_union_elections(conn.cursor()) == 0


class TestReconcile:
    @pytest.fixture
    def core(self, tmp_path, monkeypatch):
        from education_system.systems.university.domains.student_life.domain.student_life.student_union.administration import (
            student_union_core,
        )
        db = tmp_path / "reconcile.db"
        monkeypatch.setattr(student_union_core, "get_connection", lambda *a, **k: _connect(db))
        return student_union_core, db

    def test_rebuilds_children_against_elections_keeping_extra_columns(self, core):
        module, db = core
        conn = _connect(db)
        _students(conn)
        conn.execute("CREATE TABLE union_elections (election_id INTEGER PRIMARY KEY "
                     "AUTOINCREMENT, position TEXT, department TEXT, nomination_start TEXT, "
                     "nomination_end TEXT, voting_start TEXT, voting_end TEXT, status TEXT)")
        conn.execute("CREATE TABLE elections (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                     "title TEXT NOT NULL, description TEXT, start_date TEXT, "
                     "end_date TEXT, status TEXT DEFAULT 'active')")
        conn.execute("CREATE TABLE election_candidates (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                     "election_id INTEGER, student_id TEXT, manifesto TEXT, votes INTEGER "
                     "DEFAULT 0, candidate_name TEXT, FOREIGN KEY (election_id) REFERENCES "
                     "union_elections (election_id))")
        conn.execute("CREATE TABLE election_votes (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                     "election_id INTEGER, voter_id TEXT, candidate_id INTEGER, vote_time "
                     "TEXT, FOREIGN KEY (election_id) REFERENCES union_elections (election_id))")
        conn.execute("CREATE TABLE ranked_votes (vote_id INTEGER PRIMARY KEY AUTOINCREMENT, "
                     "election_id INTEGER, voter_id TEXT, candidate_preferences TEXT, "
                     "vote_time TEXT, FOREIGN KEY (election_id) REFERENCES "
                     "union_elections (election_id))")
        conn.execute("INSERT INTO union_elections VALUES (3, 'President', NULL, '2026-10-01', "
                     "'2026-10-05', '2026-10-10', '2026-10-12', 'voting')")
        conn.execute("INSERT INTO election_candidates (election_id, student_id, manifesto, "
                     "candidate_name) VALUES (3, 'S1', 'm', 'Ada L')")
        conn.commit()
        conn.close()

        module._reconcile_election_schema()
        module._reconcile_election_schema()  # idempotent

        conn = _connect(db)
        for child in ("election_candidates", "election_votes", "ranked_votes"):
            assert _fk_targets(conn, child) == {("elections", "id")}
        assert conn.execute("SELECT candidate_name FROM election_candidates"
                            ).fetchone()[0] == "Ada L"
        assert conn.execute("SELECT title, nomination_start, voting_end FROM elections "
                            "WHERE id = 3").fetchone() == ("President", "2026-10-01",
                                                           "2026-10-12")
        # A vote referencing the folded election now passes the foreign key.
        conn.execute("INSERT INTO election_votes (election_id, voter_id, candidate_id) "
                     "VALUES (3, 'S2', 1)")
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO election_votes (election_id, voter_id) VALUES (99, 'S2')")


class TestVotingMethodsReadElections:
    @pytest.fixture
    def conn(self, tmp_path):
        conn = _connect(tmp_path / "vm.db")
        _students(conn)
        schema.ensure_election_tables(conn.cursor())
        conn.execute("INSERT INTO elections (id, title, department, nomination_start, "
                     "nomination_end, voting_start, voting_end, start_date, end_date, status) "
                     "VALUES (5, 'Welfare Officer', 'All', '2000-01-01', '2000-01-02', "
                     "'2000-01-03', '2999-12-31', '2000-01-03', '2999-12-31', 'voting')")
        conn.execute("INSERT INTO election_candidates (id, election_id, student_id) "
                     "VALUES (1, 5, 'S1')")
        conn.execute("INSERT INTO election_candidates (id, election_id, student_id) "
                     "VALUES (2, 5, 'S2')")
        conn.commit()
        return conn

    def test_elections_lists_with_legacy_keys(self, conn):
        from education_system.systems.university.domains.student_life.domain.student_life.student_union.elections import (
            voting_methods as vm,
        )
        rows = vm.elections(conn)
        assert len(rows) == 1
        assert rows[0]["election_id"] == 5
        assert rows[0]["position"] == "Welfare Officer"
        assert rows[0]["candidates"] == 2

    def test_ranked_ballot_is_stored_against_elections(self, conn):
        from education_system.systems.university.domains.student_life.domain.student_life.student_union.elections import (
            voting_methods as vm,
        )
        vm.save_election_config(conn, election_id=5, method=vm.RANKED)
        vote_id = vm.cast_ranked(conn, election_id=5, voter_id="S1", ranked_candidate_ids=[2, 1])
        assert vote_id
        assert conn.execute("SELECT candidate_preferences FROM ranked_votes"
                            ).fetchone()[0] == "2,1"

    def test_unknown_election_is_refused(self, conn):
        from education_system.systems.university.domains.student_life.domain.student_life.student_union.elections import (
            voting_methods as vm,
        )
        with pytest.raises(ValueError):
            vm.save_election_config(conn, election_id=404, method=vm.SIMPLE)
