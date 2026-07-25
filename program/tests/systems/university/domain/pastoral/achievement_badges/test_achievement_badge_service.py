"""Tests for AchievementBadgeService.

The service creates its own tables via transaction()/get_connection() against
the isolated DEFAULT_DB_PATH (patched by the autouse _isolate_db fixture in
the university tests conftest), so no extra table setup is required.
"""

import pytest

from education_system.systems.university.domain.pastoral.achievement_badges.services.achievement_badge_service import (
    AchievementBadgeService,
)


@pytest.fixture
def svc(temp_db):
    return AchievementBadgeService()


def test_create_and_get_badge(svc):
    badge_id = svc.create_badge("Dean's List", description="Top marks",
                                category="academic", points=50)
    assert isinstance(badge_id, int) and badge_id > 0

    badge = svc.get_badge(badge_id)
    assert badge is not None
    assert badge["name"] == "Dean's List"
    assert badge["points"] == 50
    assert badge["category"] == "academic"


def test_get_badge_missing_returns_none(svc):
    assert svc.get_badge(99999) is None


def test_list_badges_active_only(svc):
    svc.create_badge("Alpha", category="academic")
    svc.create_badge("Beta", category="sports")
    badges = svc.list_badges()
    names = {b["name"] for b in badges}
    assert {"Alpha", "Beta"} <= names


def test_award_badge_and_student_badges(svc):
    badge_id = svc.create_badge("Volunteer", points=10)
    awarded_id = svc.award_badge("STU001", badge_id, awarded_by="admin", reason="100 hours")
    assert isinstance(awarded_id, int)

    student_badges = svc.get_student_badges("STU001")
    assert len(student_badges) == 1
    assert student_badges[0]["name"] == "Volunteer"


def test_award_badge_duplicate_raises(svc):
    badge_id = svc.create_badge("Unique")
    svc.award_badge("STU002", badge_id)
    with pytest.raises(ValueError):
        svc.award_badge("STU002", badge_id)


def test_badge_count_and_points(svc):
    b1 = svc.create_badge("B1", points=10)
    b2 = svc.create_badge("B2", points=25)
    svc.award_badge("STU003", b1)
    svc.award_badge("STU003", b2)

    summary = svc.get_student_badge_count("STU003")
    assert summary["count"] == 2
    assert summary["total_points"] == 35


def test_revoke_badge(svc):
    badge_id = svc.create_badge("Temp")
    svc.award_badge("STU004", badge_id)
    assert svc.revoke_badge("STU004", badge_id) is True
    assert svc.get_student_badges("STU004") == []


def test_progress_tracking(svc):
    badge_id = svc.create_badge("Marathon", criteria="Run 100 miles")
    assert svc.update_progress("STU005", badge_id, 40) is True
    assert svc.update_progress("STU005", badge_id, 80) is True  # update path

    progress = svc.get_progress("STU005", badge_id)
    assert len(progress) == 1
    assert progress[0]["current_progress"] == 80


def test_leaderboard_and_statistics(svc):
    b1 = svc.create_badge("Gold", points=100, category="academic")
    b2 = svc.create_badge("Silver", points=50, category="sports")
    svc.award_badge("STU_A", b1)
    svc.award_badge("STU_A", b2)
    svc.award_badge("STU_B", b2)

    leaderboard = svc.get_leaderboard()
    assert leaderboard[0]["student_id"] == "STU_A"
    assert leaderboard[0]["total_points"] == 150

    stats = svc.get_badge_statistics()
    assert stats["total_badges"] == 2
    assert stats["total_awarded"] == 3
    assert stats["unique_students"] == 2


def test_toggle_badge_display(svc):
    badge_id = svc.create_badge("Toggle")
    svc.award_badge("STU006", badge_id)
    assert svc.toggle_badge_display("STU006", badge_id) is True
    # Non-existent award
    assert svc.toggle_badge_display("NOBODY", badge_id) is False
