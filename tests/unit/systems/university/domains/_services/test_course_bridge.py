"""Unit tests for the course/module bridge.

``courses`` holds programmes (CS, 360 credits, capacity 120); ``modules``
holds the taught units students enrol in (CS-Y1-1). Readers used to join the
two on code equality, which matched nothing, so every capacity report showed
zero enrolled. These tests pin the mapping, the occupancy arithmetic and the
duplicate-column repair.
"""

import pytest

from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.services.bus import course_bridge as cb

_SCHEMA = """
CREATE TABLE courses (
    id TEXT PRIMARY KEY, code TEXT, course_code TEXT, name TEXT, course_name TEXT,
    credits INTEGER, credit_hours INTEGER, max_enrollment INTEGER, department TEXT,
    status TEXT DEFAULT 'active'
);
CREATE TABLE modules (
    module_code TEXT PRIMARY KEY, module_name TEXT, capacity INTEGER, course TEXT
);
CREATE TABLE course_curriculum (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_code TEXT, year INTEGER, module_code TEXT, module_name TEXT
);
CREATE TABLE student_modules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT, module_code TEXT, status TEXT
);
CREATE TABLE course_module_map (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_code TEXT NOT NULL, module_code TEXT NOT NULL,
    link_source TEXT NOT NULL DEFAULT 'manual',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(course_code, module_code)
);
CREATE TABLE students (student_id TEXT PRIMARY KEY, course TEXT);

INSERT INTO courses (id, code, course_code, name, course_name, credits, credit_hours,
                     max_enrollment, department)
VALUES ('CS','CS','CS','Computer Science','Computer Science',360,360,120,'Computing'),
       ('BUS','BUS','BUS','Business','Business',360,360,150,'Business');

INSERT INTO modules (module_code, module_name, course) VALUES
    ('CS-Y1-1','Programming','CS'), ('CS-Y1-2','Systems','CS'),
    ('BUS-Y1-1','Accounting','BUS'), ('FREE-1','Free Elective', NULL);

INSERT INTO course_curriculum (course_code, year, module_code, module_name) VALUES
    ('CS', 1, 'CS-Y1-1', 'Programming'), ('CS', 1, 'CS-Y1-2', 'Systems'),
    ('BUS', 1, 'BUS-Y1-1', 'Accounting');

-- Two students on CS, each taking both modules; one on BUS; one on the
-- unmapped elective.
INSERT INTO student_modules (student_id, module_code, status) VALUES
    ('S1','CS-Y1-1','Enrolled'), ('S1','CS-Y1-2','Enrolled'),
    ('S2','CS-Y1-1','Enrolled'), ('S2','CS-Y1-2','Enrolled'),
    ('S3','BUS-Y1-1','Enrolled'), ('S4','FREE-1','Enrolled'),
    ('S5','CS-Y1-1','Dropped');

INSERT INTO students (student_id, course) VALUES
    ('S1','CS'), ('S2','Computer Science'), ('S3','BUS'), ('S4', NULL);
"""


@pytest.fixture()
def db(tmp_path, monkeypatch):
    path = str(tmp_path / "bridge.db")
    monkeypatch.setattr(
        "education_system.systems.university.infrastructure.database.db.DEFAULT_DB_PATH",
        path,
    )
    conn = sqlite3.connect(path)
    conn.executescript(_SCHEMA)
    conn.commit()
    conn.close()
    return path


class TestMapping:

    def test_modules_for_course(self, db):
        assert cb.modules_for_course("CS") == ["CS-Y1-1", "CS-Y1-2"]

    def test_course_for_module(self, db):
        assert cb.course_for_module("CS-Y1-2") == "CS"

    def test_unmapped_module_has_no_course(self, db):
        assert cb.course_for_module("FREE-1") is None

    def test_unknown_inputs(self, db):
        assert cb.modules_for_course("NOPE") == []
        assert cb.course_for_module("") is None

    def test_modules_column_is_a_fallback_source(self, db, tmp_path):
        """A module linked only by ``modules.course`` is still found."""
        conn = sqlite3.connect(str(tmp_path / "bridge.db"))
        conn.execute("INSERT INTO modules (module_code, module_name, course) "
                     "VALUES ('CS-Y2-1','Algorithms','CS')")
        conn.commit()
        conn.close()
        assert "CS-Y2-1" in cb.modules_for_course("CS")

    def test_unmapped_modules_are_reported(self, db):
        assert cb.unmapped_modules() == ["FREE-1"]

    def test_link_table_is_a_mapping_source(self, db, tmp_path):
        """Links made in the Course ⇄ Module Links tab must be visible.

        ``course_module_map`` was invisible to the bridge at first, so links
        made through that tab attributed nothing.
        """
        conn = sqlite3.connect(str(tmp_path / "bridge.db"))
        conn.execute("INSERT INTO course_module_map (course_code, module_code, "
                     "link_source) VALUES ('BUS','FREE-1','manual')")
        conn.commit()
        conn.close()
        assert cb.course_for_module("FREE-1") == "BUS"
        assert cb.unmapped_modules() == []


class TestSharedModules:
    """A module can be taught on more than one programme (CIS0001 is taught
    to both Computer Science and Data Science)."""

    @pytest.fixture()
    def shared(self, db, tmp_path):
        path = str(tmp_path / "bridge.db")
        conn = sqlite3.connect(path)
        conn.executescript("""
            INSERT INTO modules (module_code, module_name) VALUES
                ('SHARED-1','Shared Foundations');
            INSERT INTO course_module_map (course_code, module_code, link_source)
                VALUES ('CS','SHARED-1','inferred'), ('BUS','SHARED-1','inferred');
            -- S3 is a BUS student who also takes the shared module.
            INSERT INTO student_modules (student_id, module_code, status)
                VALUES ('S3','SHARED-1','Enrolled'), ('S1','SHARED-1','Enrolled');
        """)
        conn.commit()
        conn.close()
        return path

    def test_module_resolves_to_every_course(self, shared):
        assert cb.courses_for_module("SHARED-1") == ["BUS", "CS"]

    def test_single_answer_helper_picks_one(self, shared):
        assert cb.course_for_module("SHARED-1") == "BUS"

    def test_appears_in_both_curricula(self, shared):
        assert "SHARED-1" in cb.modules_for_course("CS")
        assert "SHARED-1" in cb.modules_for_course("BUS")

    def test_headcount_is_programme_attributed(self, shared):
        """A BUS student taking a shared CS module is not a CS headcount.

        Without this, sharing one module between two programmes would count
        every one of its students against both capacities.
        """
        assert cb.course_occupancy("CS")["headcount"] == 2       # S1, S2 only
        assert cb.course_occupancy("BUS")["headcount"] == 1      # S3 only

    def test_enrolments_count_everyone_taught(self, shared):
        """Teaching volume is not programme-filtered: both students are sat
        in the same room."""
        assert cb.course_occupancy("CS")["enrolments"] == 6      # 4 + both shared

    def test_student_programme_matched_by_name(self, shared):
        """``students.course`` holds 'Computer Science' for S2, not 'CS'."""
        assert cb.course_occupancy("CS")["headcount"] == 2

    def test_unknown_programme_still_counts(self, shared, tmp_path):
        conn = sqlite3.connect(str(tmp_path / "bridge.db"))
        conn.execute("INSERT INTO student_modules (student_id, module_code, status) "
                     "VALUES ('S4','SHARED-1','Enrolled')")   # S4 has course NULL
        conn.commit()
        conn.close()
        assert cb.course_occupancy("CS")["headcount"] == 3


class TestOccupancy:

    def test_headcount_counts_students_not_rows(self, db):
        occ = cb.course_occupancy("CS")
        assert occ["headcount"] == 2      # S1 and S2
        assert occ["enrolments"] == 4     # two modules each
        assert occ["capacity"] == 120
        assert occ["module_count"] == 2

    def test_fill_rate(self, db):
        assert cb.course_occupancy("BUS")["fill_rate"] == pytest.approx(1 / 150 * 100)

    def test_dropped_rows_do_not_count(self, db):
        # S5 dropped CS-Y1-1 and must not appear in the headcount.
        assert cb.course_occupancy("CS")["headcount"] == 2

    def test_occupancy_map_covers_every_course(self, db):
        occupancy = cb.course_occupancy_map()
        assert set(occupancy) == {"CS", "BUS"}
        assert occupancy["BUS"]["headcount"] == 1

    def test_unknown_course_is_empty_not_an_error(self, db):
        assert cb.course_occupancy("NOPE")["headcount"] == 0

    def test_module_occupancy_resolves_its_course(self, db):
        module = cb.module_occupancy("CS-Y1-1")
        assert module["enrolled"] == 2
        assert module["course_code"] == "CS"
        assert module["capacity"] is None      # uncapped
        assert module["full"] is False

    def test_module_capacity_is_respected(self, db, tmp_path):
        conn = sqlite3.connect(str(tmp_path / "bridge.db"))
        conn.execute("UPDATE modules SET capacity = 2 WHERE module_code = 'CS-Y1-1'")
        conn.commit()
        conn.close()
        module = cb.module_occupancy("CS-Y1-1")
        assert (module["capacity"], module["full"]) == (2, True)

    def test_old_join_would_have_found_nothing(self, db, tmp_path):
        """The defect this bridge exists to fix, pinned."""
        conn = sqlite3.connect(str(tmp_path / "bridge.db"))
        matched = conn.execute(
            "SELECT COUNT(*) FROM student_modules sm WHERE sm.status='Enrolled' "
            "AND sm.module_code IN (SELECT COALESCE(course_code, code) FROM courses)"
        ).fetchone()[0]
        conn.close()
        assert matched == 0
        assert cb.course_occupancy("CS")["headcount"] > 0


class TestViews:

    def test_install_is_idempotent(self, db):
        assert cb.install_views()
        assert cb.install_views()

    def test_views_exist_after_install(self, db, tmp_path):
        cb.install_views()
        conn = sqlite3.connect(str(tmp_path / "bridge.db"))
        views = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='view'")}
        conn.close()
        assert {"v_course_module_map", "v_student_course", "v_course_occupancy",
                "v_module_occupancy"} <= views


class TestColumnDrift:

    @pytest.fixture()
    def drifted(self, db, tmp_path):
        conn = sqlite3.connect(str(tmp_path / "bridge.db"))
        conn.execute("UPDATE courses SET credit_hours = 400 WHERE id = 'CS'")
        conn.commit()
        conn.close()
        return db

    def test_drift_is_found(self, drifted):
        drift = cb.find_column_drift()
        assert len(drift) == 1
        assert drift[0]["id"] == "CS"
        assert drift[0]["pairs"]["credit_hours"] == {"canonical": 400, "legacy": 360}

    def test_report_only_by_default(self, drifted):
        result = cb.reconcile_course_columns()
        assert result["drifted"] == 1
        assert result["applied"] is False
        assert cb.find_column_drift()          # untouched

    def test_repair_promotes_the_canonical_value(self, drifted):
        cb.reconcile_course_columns(apply=True)
        assert cb.find_column_drift() == []

    def test_clean_data_reports_nothing(self, db):
        assert cb.reconcile_course_columns()["drifted"] == 0


class TestColumnSyncTriggers:

    @pytest.fixture()
    def synced(self, db, tmp_path):
        assert cb.install_course_column_sync()
        return str(tmp_path / "bridge.db")

    def _row(self, path, column):
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM courses WHERE id = 'CS'").fetchone()
        conn.close()
        return row[column]

    def test_canonical_write_mirrors_to_legacy(self, synced):
        conn = sqlite3.connect(synced)
        conn.execute("UPDATE courses SET course_name = 'Computing Science' WHERE id='CS'")
        conn.commit()
        conn.close()
        assert self._row(synced, "name") == "Computing Science"

    def test_legacy_write_mirrors_to_canonical(self, synced):
        conn = sqlite3.connect(synced)
        conn.execute("UPDATE courses SET credits = 480 WHERE id='CS'")
        conn.commit()
        conn.close()
        assert self._row(synced, "credit_hours") == 480

    def test_insert_fills_the_missing_side(self, synced):
        conn = sqlite3.connect(synced)
        conn.execute("INSERT INTO courses (id, code, course_code, name, course_name, "
                     "credits, credit_hours) VALUES ('ENG','ENG','ENG','English', NULL, 360, NULL)")
        conn.commit()
        row = conn.execute("SELECT course_name, credit_hours FROM courses "
                           "WHERE id='ENG'").fetchone()
        conn.close()
        assert row == ("English", 360)

    def test_install_is_idempotent(self, db):
        assert cb.install_course_column_sync()
        assert cb.install_course_column_sync()
