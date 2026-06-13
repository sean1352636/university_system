"""Tests for the Social Matching service.

Covers the interests / personality / privacy / teams / statistics sub-APIs
that the SocialMatchingService composes. The fixture isolates each test to
its own SQLite file; SocialMatchingService.__init__ creates the schema.
"""

from __future__ import annotations

import pytest

from education_system.university_system.infrastructure.database import db as db_module
from education_system.university_system.modules.domain.student_affairs.social_matching.services.social_matching_service import (
    INTEREST_CATEGORIES,
    PERSONALITY_TYPES,
    SocialMatchingService,
)


@pytest.fixture
def matching(tmp_path, monkeypatch):
    db_path = str(tmp_path / "social_matching_test.db")
    monkeypatch.setattr(db_module, "DEFAULT_DB_PATH", db_path)
    svc = SocialMatchingService()
    # The social_matching schema declares FKs to users(username); seed a
    # minimal users table + the test user so inserts don't fail FK checks.
    import sqlite3 as _sqlite3
    conn = _sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS users "
        "(id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL)"
    )
    conn.execute("INSERT OR IGNORE INTO users (username) VALUES (?)", (USER,))
    conn.execute("INSERT OR IGNORE INTO users (username) VALUES (?)", ("never_set_user",))
    conn.commit()
    conn.close()
    return svc


USER = "test_student_001"


class TestConstants:
    def test_interest_categories_non_empty(self):
        assert isinstance(INTEREST_CATEGORIES, list) and INTEREST_CATEGORIES
        assert all(isinstance(c, str) for c in INTEREST_CATEGORIES)

    def test_personality_types_non_empty(self):
        assert isinstance(PERSONALITY_TYPES, list) and PERSONALITY_TYPES
        assert all(isinstance(p, str) for p in PERSONALITY_TYPES)


class TestInterests:
    def test_add_and_get_interests(self, matching):
        matching.add_user_interest(USER, "Sports", "Basketball", 8, True)
        matching.add_user_interest(USER, "Music", "Rock", 7, True)
        interests = matching.get_user_interests(USER)
        assert len(interests) == 2
        names = {i["name"] for i in interests}
        assert names == {"Basketball", "Rock"}

    def test_remove_interest(self, matching):
        matching.add_user_interest(USER, "Sports", "Basketball", 8, True)
        interest_id = matching.get_user_interests(USER)[0]["interest_id"]
        matching.remove_user_interest(USER, interest_id)
        assert matching.get_user_interests(USER) == []


class TestPersonality:
    def test_set_and_get_profile(self, matching):
        matching.set_personality_profile(
            USER, personality_type="Extrovert",
            extroversion_score=8, openness_score=7,
            social_preference="Love meeting new people",
            group_size_pref="Medium Group (6-10)",
            activity_level="High",
        )
        profile = matching.get_personality_profile(USER)
        assert profile is not None
        assert profile["personality_type"] == "Extrovert"
        assert profile["extroversion_score"] == 8

    def test_missing_profile_returns_none(self, matching):
        assert matching.get_personality_profile("never_set_user") is None


class TestPrivacy:
    def test_set_and_get_privacy(self, matching):
        matching.set_privacy_settings(
            USER, allow_matching=True, show_profile=True,
            allow_messages=False, show_interests=True, show_in_search=False,
        )
        settings = matching.get_privacy_settings(USER)
        assert bool(settings["allow_matching"]) is True
        assert bool(settings["allow_messages"]) is False
        assert bool(settings["show_in_search"]) is False


class TestStatistics:
    def test_statistics_includes_expected_keys(self, matching):
        matching.add_user_interest(USER, "Sports", "Basketball", 8, True)
        stats = matching.get_user_statistics(USER)
        for key in ("total_interests", "total_matches", "requests_sent",
                    "teams_joined", "activities_joined"):
            assert key in stats
        assert stats["total_interests"] >= 1


class TestTeams:
    def test_create_and_query_team(self, matching):
        team_id = matching.create_team(
            creator_id=USER, team_name="Test Basketball Team",
            sport_type="Basketball", team_size=5,
            skill_level="Intermediate",
            description="Test team for module verification",
        )
        assert isinstance(team_id, int) and team_id > 0
        teams = matching.get_available_teams(sport_type="Basketball")
        names = {t["team_name"] for t in teams}
        assert "Test Basketball Team" in names

    def test_filter_by_sport_type(self, matching):
        matching.create_team(USER, "Hoops A", "Basketball", 5, "Intermediate", "")
        matching.create_team(USER, "Pitch B", "Football", 11, "Beginner", "")
        names = {t["team_name"] for t in matching.get_available_teams(sport_type="Football")}
        assert names == {"Pitch B"}
