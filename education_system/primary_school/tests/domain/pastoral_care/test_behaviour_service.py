"""Tests for BehaviourService and RewardsService in the Primary School Management System."""

import pytest

from education_system.primary_school.core.exceptions import BehaviourError, RewardsError


class TestRecordBehaviour:
    """Tests for recording behaviour incidents."""

    def test_record_positive_behaviour(self, behaviour_service, sample_pupil):
        """Recording a positive behaviour incident should return a record ID."""
        record_id = behaviour_service.record_behaviour(
            pupil_id=sample_pupil["pupil_id"],
            type="positive",
            category="Kindness",
            description="Helped a younger pupil at lunchtime",
            points=2,
            recorded_by="Mrs Taylor",
        )
        assert record_id is not None
        assert isinstance(record_id, int)

    def test_record_negative_behaviour(self, behaviour_service, sample_pupil):
        """Recording a negative behaviour incident should succeed."""
        record_id = behaviour_service.record_behaviour(
            pupil_id=sample_pupil["pupil_id"],
            type="negative",
            category="Disruption",
            description="Talking during assembly",
            points=1,
            action_taken="Verbal warning",
            recorded_by="Mr Jones",
        )
        assert record_id is not None

    def test_record_behaviour_with_date(self, behaviour_service, sample_pupil):
        """Recording behaviour with an explicit date should persist."""
        record_id = behaviour_service.record_behaviour(
            pupil_id=sample_pupil["pupil_id"],
            type="positive",
            category="Excellent Work",
            incident_date="2026-03-05",
        )
        records = behaviour_service.get_records(pupil_id=sample_pupil["pupil_id"])
        assert len(records) == 1
        assert records[0]["incident_date"] == "2026-03-05"

    def test_record_behaviour_default_date(self, behaviour_service, sample_pupil):
        """Recording behaviour without a date should default to today."""
        record_id = behaviour_service.record_behaviour(
            pupil_id=sample_pupil["pupil_id"],
            type="positive",
            category="Good Manners",
        )
        records = behaviour_service.get_records(pupil_id=sample_pupil["pupil_id"])
        assert len(records) == 1
        assert records[0]["incident_date"] is not None

    def test_record_multiple_incidents(self, behaviour_service, sample_pupil):
        """Multiple incidents for the same pupil should all be recorded."""
        behaviour_service.record_behaviour(
            sample_pupil["pupil_id"], "positive", category="Trying Hard",
        )
        behaviour_service.record_behaviour(
            sample_pupil["pupil_id"], "negative", category="Not Listening",
        )
        behaviour_service.record_behaviour(
            sample_pupil["pupil_id"], "positive", category="Helpfulness",
        )
        records = behaviour_service.get_records(pupil_id=sample_pupil["pupil_id"])
        assert len(records) == 3


class TestGetBehaviourRecords:
    """Tests for retrieving behaviour records."""

    def test_get_by_pupil_id(self, behaviour_service, sample_pupil,
                              sample_pupil_ks1):
        """Filtering by pupil ID should return only that pupil's records."""
        behaviour_service.record_behaviour(
            sample_pupil["pupil_id"], "positive", category="Kindness",
        )
        behaviour_service.record_behaviour(
            sample_pupil_ks1["pupil_id"], "positive", category="Trying Hard",
        )
        records = behaviour_service.get_records(pupil_id=sample_pupil["pupil_id"])
        assert len(records) == 1

    def test_get_by_type(self, behaviour_service, sample_pupil):
        """Filtering by type should return only positive or negative records."""
        behaviour_service.record_behaviour(
            sample_pupil["pupil_id"], "positive", category="Kindness",
        )
        behaviour_service.record_behaviour(
            sample_pupil["pupil_id"], "negative", category="Disruption",
        )
        positive = behaviour_service.get_records(type="positive")
        negative = behaviour_service.get_records(type="negative")
        assert len(positive) == 1
        assert len(negative) == 1

    def test_get_by_date_range(self, behaviour_service, sample_pupil):
        """Filtering by date range should return matching records."""
        behaviour_service.record_behaviour(
            sample_pupil["pupil_id"], "positive",
            incident_date="2026-03-01",
        )
        behaviour_service.record_behaviour(
            sample_pupil["pupil_id"], "positive",
            incident_date="2026-03-15",
        )
        behaviour_service.record_behaviour(
            sample_pupil["pupil_id"], "positive",
            incident_date="2026-03-25",
        )
        records = behaviour_service.get_records(
            date_from="2026-03-10", date_to="2026-03-20",
        )
        assert len(records) == 1
        assert records[0]["incident_date"] == "2026-03-15"

    def test_get_all_records(self, behaviour_service, sample_pupil):
        """Getting records with no filters should return all records."""
        behaviour_service.record_behaviour(
            sample_pupil["pupil_id"], "positive",
        )
        behaviour_service.record_behaviour(
            sample_pupil["pupil_id"], "negative",
        )
        records = behaviour_service.get_records()
        assert len(records) == 2

    def test_get_empty_results(self, behaviour_service):
        """Getting records from empty database should return empty list."""
        records = behaviour_service.get_records()
        assert records == []


class TestUpdateBehaviourRecord:
    """Tests for updating behaviour records."""

    def test_update_category(self, behaviour_service, sample_pupil):
        """Updating the category should persist."""
        record_id = behaviour_service.record_behaviour(
            sample_pupil["pupil_id"], "positive", category="Kindness",
        )
        updated = behaviour_service.update_record(
            record_id, category="Helpfulness",
        )
        assert updated is True
        records = behaviour_service.get_records(pupil_id=sample_pupil["pupil_id"])
        assert records[0]["category"] == "Helpfulness"

    def test_update_action_taken(self, behaviour_service, sample_pupil):
        """Updating action taken should persist."""
        record_id = behaviour_service.record_behaviour(
            sample_pupil["pupil_id"], "negative", category="Disruption",
        )
        updated = behaviour_service.update_record(
            record_id, action_taken="Loss of break time",
        )
        assert updated is True

    def test_update_points(self, behaviour_service, sample_pupil):
        """Updating points should persist."""
        record_id = behaviour_service.record_behaviour(
            sample_pupil["pupil_id"], "positive", points=1,
        )
        behaviour_service.update_record(record_id, points=5)
        records = behaviour_service.get_records(pupil_id=sample_pupil["pupil_id"])
        assert records[0]["points"] == 5

    def test_update_no_valid_fields(self, behaviour_service, sample_pupil):
        """Updating with no valid fields should return None."""
        record_id = behaviour_service.record_behaviour(
            sample_pupil["pupil_id"], "positive",
        )
        result = behaviour_service.update_record(record_id, invalid="test")
        assert result is None


class TestDeleteBehaviourRecord:
    """Tests for deleting behaviour records."""

    def test_delete_existing_record(self, behaviour_service, sample_pupil):
        """Deleting an existing record should return True."""
        record_id = behaviour_service.record_behaviour(
            sample_pupil["pupil_id"], "positive",
        )
        deleted = behaviour_service.delete_record(record_id)
        assert deleted is True
        records = behaviour_service.get_records(pupil_id=sample_pupil["pupil_id"])
        assert records == []

    def test_delete_nonexistent_record(self, behaviour_service):
        """Deleting a non-existent record should return False."""
        deleted = behaviour_service.delete_record(99999)
        assert deleted is False


class TestBehaviourSummary:
    """Tests for the pupil behaviour summary."""

    def test_summary_counts(self, behaviour_service, sample_pupil):
        """Summary should count positive and negative incidents correctly."""
        pid = sample_pupil["pupil_id"]
        behaviour_service.record_behaviour(pid, "Positive", points=2)
        behaviour_service.record_behaviour(pid, "Positive", points=3)
        behaviour_service.record_behaviour(pid, "Negative", points=1)

        summary = behaviour_service.get_pupil_summary(pid)
        assert summary["positive_count"] == 2
        assert summary["negative_count"] == 1
        assert summary["total_points"] == 6  # 2+3+1

    def test_summary_empty(self, behaviour_service, sample_pupil):
        """Summary for a pupil with no records should have all zeros."""
        summary = behaviour_service.get_pupil_summary(sample_pupil["pupil_id"])
        assert summary["positive_count"] == 0
        assert summary["negative_count"] == 0
        assert summary["total_points"] == 0


# ── Rewards tests ────────────────────────────────────────────────────────


class TestAwardReward:
    """Tests for awarding rewards."""

    def test_award_house_point(self, rewards_service, sample_pupil):
        """Awarding a house point should return a reward ID."""
        reward_id = rewards_service.award_reward(
            pupil_id=sample_pupil["pupil_id"],
            reward_type="House Point",
            reason="Excellent handwriting",
            awarded_by="Mrs Smith",
            house="Red",
            points=1,
        )
        assert reward_id is not None
        assert isinstance(reward_id, int)

    def test_award_star_of_the_week(self, rewards_service, sample_pupil):
        """Awarding Star of the Week should succeed."""
        reward_id = rewards_service.award_reward(
            pupil_id=sample_pupil["pupil_id"],
            reward_type="Star of the Week",
            reason="Outstanding effort in maths",
            awarded_by="Mr Jones",
        )
        assert reward_id is not None

    def test_award_headteacher_award(self, rewards_service, sample_pupil):
        """Awarding a Headteacher Award should succeed."""
        reward_id = rewards_service.award_reward(
            pupil_id=sample_pupil["pupil_id"],
            reward_type="Headteacher Award",
            reason="Consistent good behaviour all term",
            points=5,
        )
        rewards = rewards_service.get_rewards(pupil_id=sample_pupil["pupil_id"])
        assert len(rewards) == 1
        assert rewards[0]["reward_type"] == "Headteacher Award"
        assert rewards[0]["points"] == 5

    def test_award_with_explicit_date(self, rewards_service, sample_pupil):
        """Awarding with an explicit date should persist that date."""
        rewards_service.award_reward(
            pupil_id=sample_pupil["pupil_id"],
            reward_type="Sticker",
            award_date="2026-03-01",
        )
        rewards = rewards_service.get_rewards(pupil_id=sample_pupil["pupil_id"])
        assert rewards[0]["award_date"] == "2026-03-01"


class TestGetRewards:
    """Tests for retrieving rewards."""

    def test_get_by_pupil(self, rewards_service, sample_pupil, sample_pupil_ks1):
        """Filtering by pupil should return only their rewards."""
        rewards_service.award_reward(
            sample_pupil["pupil_id"], "House Point", house="Blue",
        )
        rewards_service.award_reward(
            sample_pupil_ks1["pupil_id"], "Sticker",
        )
        rewards = rewards_service.get_rewards(pupil_id=sample_pupil["pupil_id"])
        assert len(rewards) == 1

    def test_get_by_reward_type(self, rewards_service, sample_pupil):
        """Filtering by reward type should return matching rewards."""
        rewards_service.award_reward(
            sample_pupil["pupil_id"], "House Point",
        )
        rewards_service.award_reward(
            sample_pupil["pupil_id"], "Sticker",
        )
        rewards = rewards_service.get_rewards(reward_type="Sticker")
        assert len(rewards) == 1

    def test_get_by_house(self, rewards_service, sample_pupil):
        """Filtering by house should return matching rewards."""
        rewards_service.award_reward(
            sample_pupil["pupil_id"], "House Point", house="Red",
        )
        rewards_service.award_reward(
            sample_pupil["pupil_id"], "House Point", house="Blue",
        )
        red = rewards_service.get_rewards(house="Red")
        assert len(red) == 1

    def test_get_by_date_range(self, rewards_service, sample_pupil):
        """Filtering by date range should return matching rewards."""
        rewards_service.award_reward(
            sample_pupil["pupil_id"], "House Point",
            award_date="2026-02-01",
        )
        rewards_service.award_reward(
            sample_pupil["pupil_id"], "House Point",
            award_date="2026-03-15",
        )
        march = rewards_service.get_rewards(
            date_from="2026-03-01", date_to="2026-03-31",
        )
        assert len(march) == 1


class TestDeleteReward:
    """Tests for deleting rewards."""

    def test_delete_existing_reward(self, rewards_service, sample_pupil):
        """Deleting an existing reward should return True."""
        reward_id = rewards_service.award_reward(
            sample_pupil["pupil_id"], "Sticker",
        )
        deleted = rewards_service.delete_reward(reward_id)
        assert deleted is True

    def test_delete_nonexistent_reward(self, rewards_service):
        """Deleting a non-existent reward should return False."""
        deleted = rewards_service.delete_reward(99999)
        assert deleted is False


class TestHousePointsSummary:
    """Tests for the house points summary."""

    def test_house_points_totals(self, rewards_service, sample_pupil,
                                  sample_pupil_ks1):
        """House points summary should total points per house."""
        rewards_service.award_reward(
            sample_pupil["pupil_id"], "House Point",
            house="Red", points=3,
        )
        rewards_service.award_reward(
            sample_pupil_ks1["pupil_id"], "House Point",
            house="Red", points=2,
        )
        rewards_service.award_reward(
            sample_pupil["pupil_id"], "House Point",
            house="Blue", points=5,
        )
        summary = rewards_service.get_house_points_summary()
        totals = {s["house"]: s["total_points"] for s in summary}
        assert totals["Red"] == 5
        assert totals["Blue"] == 5

    def test_house_points_empty(self, rewards_service):
        """House points summary with no rewards should be empty."""
        summary = rewards_service.get_house_points_summary()
        assert summary == []


class TestPupilRewardsSummary:
    """Tests for the pupil rewards summary."""

    def test_pupil_rewards_breakdown(self, rewards_service, sample_pupil):
        """Pupil summary should break down counts per reward type."""
        pid = sample_pupil["pupil_id"]
        rewards_service.award_reward(pid, "House Point", points=1)
        rewards_service.award_reward(pid, "House Point", points=2)
        rewards_service.award_reward(pid, "Sticker", points=1)

        summary = rewards_service.get_pupil_rewards_summary(pid)
        by_type = {s["reward_type"]: s for s in summary}
        assert by_type["House Point"]["count"] == 2
        assert by_type["House Point"]["total_points"] == 3
        assert by_type["Sticker"]["count"] == 1

    def test_pupil_rewards_summary_empty(self, rewards_service, sample_pupil):
        """Summary for a pupil with no rewards should be empty."""
        summary = rewards_service.get_pupil_rewards_summary(
            sample_pupil["pupil_id"],
        )
        assert summary == []
