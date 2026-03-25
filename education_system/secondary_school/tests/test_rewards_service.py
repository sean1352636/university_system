"""Tests for RewardsService."""
import pytest
from education_system.secondary_school.core.exceptions import RewardsError


class TestAwardReward:
    def test_award_creates_reward_with_points(self, rewards_service, sample_student):
        r = rewards_service.award(
            student_id=sample_student["id"], reason="Great classwork",
            reward_type="merit", category="academic", points=5,
        )
        assert r["student_id"] == sample_student["id"]
        assert r["reward_type"] == "merit"
        assert r["category"] == "academic"
        assert r["points"] == 5
        assert r["reason"] == "Great classwork"

    def test_award_creates_certificate_reward(self, rewards_service, sample_student):
        r = rewards_service.award(
            student_id=sample_student["id"], reason="100% attendance",
            reward_type="certificate", category="attendance",
            points=10, certificate=True,
        )
        assert r["reward_type"] == "certificate"
        assert r["certificate_issued"] == 1


class TestListRewards:
    def test_list_returns_rewards(self, rewards_service, sample_student):
        rewards_service.award(sample_student["id"], "R1")
        rewards_service.award(sample_student["id"], "R2")
        result = rewards_service.list_rewards()
        assert len(result) >= 2

    def test_list_filter_by_student(self, rewards_service, sample_student, sample_student_ks4):
        rewards_service.award(sample_student["id"], "R1")
        rewards_service.award(sample_student_ks4["id"], "R2")
        result = rewards_service.list_rewards(student_id=sample_student["id"])
        assert len(result) == 1
        assert result[0]["student_id"] == sample_student["id"]


class TestDeleteReward:
    def test_delete_removes_record(self, rewards_service, sample_student):
        r = rewards_service.award(sample_student["id"], "To delete")
        rewards_service.delete_reward(r["id"])
        result = rewards_service.list_rewards()
        assert all(x["id"] != r["id"] for x in result)


class TestStudentTotals:
    def test_student_totals_returns_aggregated(self, rewards_service, sample_student):
        rewards_service.award(sample_student["id"], "R1", points=5)
        rewards_service.award(sample_student["id"], "R2", points=3)
        totals = rewards_service.student_totals()
        assert len(totals) >= 1
        entry = totals[0]
        assert entry["total_points"] == 8
        assert entry["total_awards"] == 2


class TestLeaderboard:
    def test_leaderboard_returns_sorted(self, rewards_service, sample_student, sample_student_ks4):
        rewards_service.award(sample_student["id"], "R1", points=3)
        rewards_service.award(sample_student_ks4["id"], "R2", points=10)
        board = rewards_service.leaderboard()
        assert len(board) == 2
        # Highest points first
        assert board[0]["total_points"] >= board[1]["total_points"]
        assert board[0]["first_name"] == "Jane"
