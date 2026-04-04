"""Tests for the RewardsService in the Primary School system."""

import pytest


class TestAwardReward:
    """Tests for awarding rewards."""

    def test_award_reward_returns_id(self, rewards_service, sample_pupil):
        """Awarding a reward returns a valid integer ID."""
        reward_id = rewards_service.award_reward(
            pupil_id=sample_pupil["pupil_id"],
            reward_type="star",
            points=1,
            reason="Excellent reading",
            awarded_by="STF0001",
            house="Red",
        )
        assert isinstance(reward_id, int)
        assert reward_id > 0

    def test_award_reward_persists(self, rewards_service, sample_pupil):
        """An awarded reward can be retrieved afterwards."""
        pid = sample_pupil["pupil_id"]
        rewards_service.award_reward(
            pupil_id=pid,
            reward_type="sticker",
            points=2,
            reason="Great handwriting",
            awarded_by="STF0001",
        )
        rewards = rewards_service.get_rewards(pupil_id=pid)
        assert len(rewards) == 1
        assert rewards[0]["reward_type"] == "sticker"
        assert rewards[0]["points"] == 2

    def test_award_multiple_reward_types(self, rewards_service, sample_pupil):
        """Different reward types are stored independently."""
        pid = sample_pupil["pupil_id"]
        rewards_service.award_reward(
            pupil_id=pid, reward_type="star", points=1, reason="R1",
        )
        rewards_service.award_reward(
            pupil_id=pid, reward_type="certificate", points=5, reason="R2",
        )
        rewards_service.award_reward(
            pupil_id=pid, reward_type="house_points", points=10,
            reason="R3", house="Blue",
        )
        rewards = rewards_service.get_rewards(pupil_id=pid)
        assert len(rewards) == 3


class TestGetRewards:
    """Tests for retrieving rewards."""

    def test_get_rewards_empty_db(self, rewards_service):
        """Querying an empty database returns an empty list."""
        assert rewards_service.get_rewards() == []

    def test_get_rewards_by_pupil(self, rewards_service, sample_pupil, sample_pupil_ks1):
        """Filtering by pupil_id returns only that pupil's rewards."""
        pid = sample_pupil["pupil_id"]
        rewards_service.award_reward(
            pupil_id=pid, reward_type="star", points=1, reason="A",
        )
        rewards_service.award_reward(
            pupil_id=sample_pupil_ks1["pupil_id"], reward_type="sticker",
            points=1, reason="B",
        )
        rewards = rewards_service.get_rewards(pupil_id=pid)
        assert len(rewards) == 1
        assert rewards[0]["reason"] == "A"

    def test_get_rewards_by_type(self, rewards_service, sample_pupil):
        """Filtering by reward_type returns only matching records."""
        pid = sample_pupil["pupil_id"]
        rewards_service.award_reward(
            pupil_id=pid, reward_type="star", points=1, reason="R1",
        )
        rewards_service.award_reward(
            pupil_id=pid, reward_type="certificate", points=5, reason="R2",
        )
        rewards = rewards_service.get_rewards(reward_type="certificate")
        assert len(rewards) == 1
        assert rewards[0]["points"] == 5


class TestUpdateReward:
    """Tests for updating rewards."""

    def test_update_reward_reason(self, rewards_service, sample_pupil):
        """Updating the reason field persists the change."""
        pid = sample_pupil["pupil_id"]
        reward_id = rewards_service.award_reward(
            pupil_id=pid, reward_type="star", points=1, reason="Old reason",
        )
        result = rewards_service.update_reward(reward_id, reason="New reason")
        assert result is True
        rewards = rewards_service.get_rewards(pupil_id=pid)
        assert rewards[0]["reason"] == "New reason"

    def test_update_reward_points(self, rewards_service, sample_pupil):
        """Updating points changes the stored value."""
        pid = sample_pupil["pupil_id"]
        reward_id = rewards_service.award_reward(
            pupil_id=pid, reward_type="house_points", points=5,
            reason="Initial", house="Green",
        )
        rewards_service.update_reward(reward_id, points=10)
        rewards = rewards_service.get_rewards(pupil_id=pid)
        assert rewards[0]["points"] == 10

    def test_update_with_no_valid_fields(self, rewards_service, sample_pupil):
        """Passing no recognised fields returns None."""
        reward_id = rewards_service.award_reward(
            pupil_id=sample_pupil["pupil_id"], reward_type="star",
            points=1, reason="R",
        )
        result = rewards_service.update_reward(reward_id, fake_field="value")
        assert result is None


class TestDeleteReward:
    """Tests for deleting rewards."""

    def test_delete_existing_reward(self, rewards_service, sample_pupil):
        """Deleting an existing reward returns True and removes it."""
        pid = sample_pupil["pupil_id"]
        reward_id = rewards_service.award_reward(
            pupil_id=pid, reward_type="sticker", points=1, reason="Gone",
        )
        assert rewards_service.delete_reward(reward_id) is True
        assert rewards_service.get_rewards(pupil_id=pid) == []

    def test_delete_nonexistent_reward(self, rewards_service):
        """Deleting a non-existent reward returns False."""
        assert rewards_service.delete_reward(99999) is False


class TestGetHousePointsSummary:
    """Tests for the house points summary."""

    def test_house_points_summary_empty(self, rewards_service):
        """An empty database returns an empty summary."""
        assert rewards_service.get_house_points_summary() == []

    def test_house_points_summary_totals(self, rewards_service, sample_pupil, sample_pupil_ks2):
        """Points are correctly aggregated per house."""
        pid1 = sample_pupil["pupil_id"]
        pid2 = sample_pupil_ks2["pupil_id"]
        rewards_service.award_reward(
            pupil_id=pid1, reward_type="house_points",
            points=10, reason="R1", house="Red",
        )
        rewards_service.award_reward(
            pupil_id=pid2, reward_type="house_points",
            points=15, reason="R2", house="Blue",
        )
        rewards_service.award_reward(
            pupil_id=pid1, reward_type="house_points",
            points=5, reason="R3", house="Red",
        )
        summary = rewards_service.get_house_points_summary()
        totals = {row["house"]: row["total_points"] for row in summary}
        assert totals["Red"] == 15
        assert totals["Blue"] == 15


class TestGetPupilRewardsSummary:
    """Tests for the pupil rewards summary."""

    def test_pupil_summary_empty(self, rewards_service, sample_pupil):
        """A pupil with no rewards returns an empty summary."""
        assert rewards_service.get_pupil_rewards_summary(sample_pupil["pupil_id"]) == []

    def test_pupil_summary_counts_and_points(self, rewards_service, sample_pupil):
        """Summary returns correct counts and totals per reward type."""
        pid = sample_pupil["pupil_id"]
        rewards_service.award_reward(
            pupil_id=pid, reward_type="star", points=1, reason="R1",
        )
        rewards_service.award_reward(
            pupil_id=pid, reward_type="star", points=1, reason="R2",
        )
        rewards_service.award_reward(
            pupil_id=pid, reward_type="certificate", points=5, reason="R3",
        )
        summary = rewards_service.get_pupil_rewards_summary(pid)
        by_type = {row["reward_type"]: row for row in summary}
        assert by_type["star"]["count"] == 2
        assert by_type["star"]["total_points"] == 2
        assert by_type["certificate"]["count"] == 1
        assert by_type["certificate"]["total_points"] == 5
