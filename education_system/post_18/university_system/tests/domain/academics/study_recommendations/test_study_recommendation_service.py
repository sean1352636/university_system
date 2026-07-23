"""Behavioral tests for ``StudyRecommendationService``.

The service is DB-backed. It creates its own ``study_recommendations`` and
``study_sessions`` tables on init, but reads/writes ``study_profiles`` (owned by
``study_matching_service``) and reads ``grades`` — so the fixture seeds those two
into a **temp** DB with ``DEFAULT_DB_PATH`` monkeypatched, never the live app DB.
"""

import sqlite3

import pytest

from education_system.post_18.university_system.modules.domain.academics.study_recommendations.services.study_recommendation_service import (
    StudyRecommendationService,
)

_DB_PATH_ATTR = (
    "education_system.post_18.university_system.infrastructure.database.db.DEFAULT_DB_PATH"
)

# study_profiles matches study_matching_service's real schema; grades is the
# external table get_weak_areas reads.
_EXTERNAL_SCHEMA = """
CREATE TABLE study_profiles (
    profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL UNIQUE,
    study_style TEXT DEFAULT 'Visual',
    preferred_time TEXT DEFAULT 'Evening',
    group_size_preference TEXT DEFAULT 'Small',
    communication_style TEXT DEFAULT 'Collaborative',
    noise_preference TEXT DEFAULT 'Quiet',
    availability_json TEXT,
    interests_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE grades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT,
    module_code TEXT,
    course TEXT,
    grade TEXT,
    score REAL
);
"""


@pytest.fixture()
def svc(tmp_path, monkeypatch):
    """A service instance wired to a temp DB seeded with the external tables."""
    db_path = str(tmp_path / "study.db")
    monkeypatch.setattr(_DB_PATH_ATTR, db_path)
    conn = sqlite3.connect(db_path)
    conn.executescript(_EXTERNAL_SCHEMA)
    conn.commit()
    conn.close()
    # Instantiation creates study_recommendations + study_sessions.
    return StudyRecommendationService(), db_path


def _query(db_path, sql, params=()):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def _exec(db_path, sql, params=()):
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(sql, params)
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# init / _ensure_tables_exist
# ---------------------------------------------------------------------------

class TestEnsureTables:
    def test_creates_own_tables(self, svc):
        _, db = svc
        names = {
            r["name"]
            for r in _query(
                db, "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert {"study_recommendations", "study_sessions"} <= names

    def test_init_is_idempotent(self, svc):
        # Re-instantiating over the same DB must not error (CREATE IF NOT EXISTS).
        StudyRecommendationService()


# ---------------------------------------------------------------------------
# create_profile / get_profile / update_profile
# ---------------------------------------------------------------------------

class TestProfiles:
    def test_create_new_profile_persists_extras(self, svc):
        service, db = svc
        pid = service.create_profile(
            "S1", learning_style="visual", study_hours_per_week=10,
            preferred_times="Morning", strengths="algebra", weaknesses="essays",
        )
        assert isinstance(pid, int)
        row = _query(db, "SELECT * FROM study_profiles WHERE student_id='S1'")[0]
        assert row["study_style"] == "visual"
        assert row["preferred_time"] == "Morning"
        # extras packed into interests_json
        import json
        extras = json.loads(row["interests_json"])
        assert extras == {
            "hours_per_week": 10, "strengths": "algebra", "weaknesses": "essays",
        }

    def test_create_profile_twice_updates_and_returns_same_id(self, svc):
        service, db = svc
        pid1 = service.create_profile("S2", learning_style="reading")
        pid2 = service.create_profile("S2", learning_style="auditory",
                                      study_hours_per_week=5)
        assert pid1 == pid2
        rows = _query(db, "SELECT * FROM study_profiles WHERE student_id='S2'")
        assert len(rows) == 1
        assert rows[0]["study_style"] == "auditory"

    def test_get_profile_missing_returns_none(self, svc):
        service, _ = svc
        assert service.get_profile("nobody") is None

    def test_get_profile_maps_columns_and_extras(self, svc):
        service, _ = svc
        service.create_profile("S3", learning_style="kinesthetic",
                               study_hours_per_week=8, strengths="labs")
        prof = service.get_profile("S3")
        assert prof["learning_style"] == "kinesthetic"
        assert prof["study_hours_per_week"] == 8
        assert prof["strengths"] == "labs"
        assert prof["weaknesses"] == ""

    def test_get_profile_handles_malformed_interests_json(self, svc):
        service, db = svc
        _exec(
            db,
            "INSERT INTO study_profiles (student_id, study_style, interests_json) "
            "VALUES ('S4', 'reading', ?)",
            ("{not valid json",),
        )
        prof = service.get_profile("S4")
        assert prof["study_hours_per_week"] == 0
        assert prof["strengths"] == ""
        assert prof["weaknesses"] == ""

    def test_get_profile_handles_non_dict_interests_json(self, svc):
        service, db = svc
        _exec(
            db,
            "INSERT INTO study_profiles (student_id, study_style, interests_json) "
            "VALUES ('S5', 'reading', ?)",
            ("[1, 2, 3]",),
        )
        prof = service.get_profile("S5")
        assert prof["study_hours_per_week"] == 0
        assert prof["strengths"] == ""

    def test_update_profile_empty_kwargs_returns_false(self, svc):
        service, _ = svc
        service.create_profile("S6")
        assert service.update_profile("S6") is False

    def test_update_profile_sets_column(self, svc):
        service, db = svc
        service.create_profile("S7", learning_style="reading")
        assert service.update_profile("S7", study_style="visual") is True
        row = _query(db, "SELECT * FROM study_profiles WHERE student_id='S7'")[0]
        assert row["study_style"] == "visual"
        assert row["updated_at"] is not None


# ---------------------------------------------------------------------------
# get_weak_areas
# ---------------------------------------------------------------------------

class TestWeakAreas:
    def test_returns_low_scores_and_failing_grades(self, svc):
        service, db = svc
        _exec(db, "INSERT INTO grades (student_id, module_code, grade, score) "
                  "VALUES ('W1', 'CS101', 'F', 30)")
        _exec(db, "INSERT INTO grades (student_id, module_code, grade, score) "
                  "VALUES ('W1', 'CS102', 'C', 65)")  # not weak
        _exec(db, "INSERT INTO grades (student_id, module_code, grade, score) "
                  "VALUES ('W1', 'CS103', 'D', 55)")  # weak via grade letter
        weak = service.get_weak_areas("W1")
        modules = {w["module_code"] for w in weak}
        assert modules == {"CS101", "CS103"}

    def test_empty_when_no_weak_areas(self, svc):
        service, db = svc
        _exec(db, "INSERT INTO grades (student_id, module_code, grade, score) "
                  "VALUES ('W2', 'CS200', 'A', 90)")
        assert service.get_weak_areas("W2") == []

    def test_missing_grades_table_is_swallowed(self, svc):
        service, db = svc
        _exec(db, "DROP TABLE grades")
        assert service.get_weak_areas("W3") == []


# ---------------------------------------------------------------------------
# generate_recommendations
# ---------------------------------------------------------------------------

class TestGenerateRecommendations:
    def test_no_weak_areas_no_profile_returns_empty(self, svc):
        service, db = svc
        recs = service.generate_recommendations("G0")
        assert recs == []
        assert _query(
            db, "SELECT * FROM study_recommendations WHERE student_id='G0'"
        ) == []

    def test_weak_areas_generate_focus_recs_with_priority(self, svc):
        service, db = svc
        _exec(db, "INSERT INTO grades (student_id, module_code, grade, score) "
                  "VALUES ('G1', 'CS101', 'F', 30)")   # <40 -> high
        _exec(db, "INSERT INTO grades (student_id, module_code, grade, score) "
                  "VALUES ('G1', 'CS102', 'D', 45)")   # >=40 -> medium
        recs = service.generate_recommendations("G1")
        by_module = {r["module_code"]: r for r in recs}
        assert by_module["CS101"]["priority"] == "high"
        assert by_module["CS102"]["priority"] == "medium"
        assert by_module["CS101"]["recommendation_type"] == "focus_area"
        assert "Review CS101" == by_module["CS101"]["title"]
        # persisted
        saved = _query(
            db, "SELECT * FROM study_recommendations WHERE student_id='G1'"
        )
        assert len(saved) == 2

    def test_profile_adds_technique_recommendation(self, svc):
        service, _ = svc
        service.create_profile("G2", learning_style="visual")
        recs = service.generate_recommendations("G2")
        technique = [r for r in recs if r["recommendation_type"] == "technique"]
        assert len(technique) == 1
        assert "visual learners" in technique[0]["title"]
        assert "mind maps" in technique[0]["description"]
        assert technique[0]["priority"] == "low"

    def test_unknown_learning_style_uses_default_tip(self, svc):
        service, _ = svc
        service.create_profile("G3", learning_style="telepathic")
        recs = service.generate_recommendations("G3")
        technique = [r for r in recs if r["recommendation_type"] == "technique"][0]
        assert technique["description"] == "Use varied study methods."


# ---------------------------------------------------------------------------
# get_recommendations / mark_recommendation_completed
# ---------------------------------------------------------------------------

class TestRecommendationRetrieval:
    def _seed_two(self, service):
        service.create_profile("R1", learning_style="visual")
        return service.generate_recommendations("R1")

    def test_active_only_excludes_completed(self, svc):
        service, db = svc
        self._seed_two(service)
        rec_id = _query(
            db, "SELECT id FROM study_recommendations WHERE student_id='R1' LIMIT 1"
        )[0]["id"]
        assert service.mark_recommendation_completed(rec_id) is True

        active = service.get_recommendations("R1", active_only=True)
        assert all(r["is_completed"] == 0 for r in active)
        assert rec_id not in {r["id"] for r in active}

    def test_active_false_returns_all_including_completed(self, svc):
        service, db = svc
        all_recs = self._seed_two(service)
        rec_id = _query(
            db, "SELECT id FROM study_recommendations WHERE student_id='R1' LIMIT 1"
        )[0]["id"]
        service.mark_recommendation_completed(rec_id)
        # active_only=False still returns the completed one
        service_recs = service.get_recommendations("R1", active_only=False)
        assert len(service_recs) == len(all_recs)
        assert any(r["is_completed"] == 1 for r in service_recs)

    def test_get_recommendations_empty(self, svc):
        service, _ = svc
        assert service.get_recommendations("nobody") == []


# ---------------------------------------------------------------------------
# study sessions: log / history / stats / streak
# ---------------------------------------------------------------------------

class TestStudySessions:
    def test_log_and_history(self, svc):
        service, _ = svc
        sid = service.log_study_session(
            "P1", module_code="CS101", topic="loops",
            duration_minutes=30, effectiveness_rating=4, notes="ok",
        )
        assert isinstance(sid, int)
        hist = service.get_study_history("P1")
        assert len(hist) == 1
        assert hist[0]["topic"] == "loops"
        assert hist[0]["duration_minutes"] == 30

    def test_history_limit(self, svc):
        service, _ = svc
        for i in range(5):
            service.log_study_session("P2", topic=f"t{i}", duration_minutes=10)
        assert len(service.get_study_history("P2", limit=3)) == 3

    def test_stats_empty(self, svc):
        service, _ = svc
        stats = service.get_study_stats("none")
        assert stats == {
            "total_minutes": 0, "total_hours": 0.0,
            "total_sessions": 0, "avg_effectiveness": 0,
        }

    def test_stats_aggregates(self, svc):
        service, _ = svc
        service.log_study_session("P3", duration_minutes=60, effectiveness_rating=4)
        service.log_study_session("P3", duration_minutes=30, effectiveness_rating=5)
        service.log_study_session("P3", duration_minutes=30)  # no rating
        stats = service.get_study_stats("P3")
        assert stats["total_minutes"] == 120
        assert stats["total_hours"] == 2.0
        assert stats["total_sessions"] == 3
        assert stats["avg_effectiveness"] == 4.5  # NULL rating excluded

    def test_streak_zero_without_sessions(self, svc):
        service, _ = svc
        assert service.get_study_streak("none") == 0

    def test_streak_counts_distinct_days(self, svc):
        service, db = svc
        for day in ("2026-07-20", "2026-07-21", "2026-07-22"):
            _exec(
                db,
                "INSERT INTO study_sessions (student_id, duration_minutes, studied_at) "
                "VALUES ('P4', 20, ?)",
                (f"{day} 09:00:00",),
            )
        assert service.get_study_streak("P4") == 3

    def test_streak_same_day_counts_once(self, svc):
        service, db = svc
        for hour in ("08:00:00", "12:00:00", "18:00:00"):
            _exec(
                db,
                "INSERT INTO study_sessions (student_id, duration_minutes, studied_at) "
                "VALUES ('P5', 20, ?)",
                (f"2026-07-20 {hour}",),
            )
        assert service.get_study_streak("P5") == 1
