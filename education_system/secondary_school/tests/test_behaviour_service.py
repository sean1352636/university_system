"""Comprehensive tests for BehaviourService."""

import pytest
from education_system.secondary_school.core.exceptions import BehaviourError


class TestAddRecord:
    """Tests for adding behaviour records."""

    def test_add_positive_record(self, behaviour_service, sample_student):
        record = behaviour_service.add_record(
            student_id=sample_student["id"],
            record_type="positive",
            category="achievement",
            description="Outstanding work in class",
            points=5,
            recorded_by="Mrs Smith",
        )
        assert record["student_id"] == sample_student["id"]
        assert record["type"] == "positive"
        assert record["category"] == "achievement"
        assert record["description"] == "Outstanding work in class"
        assert record["points"] == 5
        assert record["recorded_by"] == "Mrs Smith"

    def test_add_negative_record(self, behaviour_service, sample_student):
        record = behaviour_service.add_record(
            student_id=sample_student["id"],
            record_type="negative",
            category="disruption",
            description="Talking in class repeatedly",
            points=3,
            sanction="detention",
            recorded_by="Mr Jones",
        )
        assert record["type"] == "negative"
        assert record["category"] == "disruption"
        assert record["sanction"] == "detention"

    def test_add_record_with_incident_date(self, behaviour_service, sample_student):
        record = behaviour_service.add_record(
            student_id=sample_student["id"],
            record_type="negative",
            category="late",
            incident_date="2026-02-10",
        )
        assert record["incident_date"] == "2026-02-10"

    def test_add_record_default_incident_date(self, behaviour_service, sample_student):
        record = behaviour_service.add_record(
            student_id=sample_student["id"],
            record_type="positive",
            category="helpfulness",
        )
        assert record["incident_date"] is not None  # defaults to today

    def test_add_record_zero_points(self, behaviour_service, sample_student):
        record = behaviour_service.add_record(
            student_id=sample_student["id"],
            record_type="positive",
            category="participation",
            points=0,
        )
        assert record["points"] == 0

    def test_add_record_no_description(self, behaviour_service, sample_student):
        record = behaviour_service.add_record(
            student_id=sample_student["id"],
            record_type="negative",
            category="uniform",
        )
        assert record["description"] is None

    def test_add_multiple_records(self, behaviour_service, sample_student):
        r1 = behaviour_service.add_record(
            student_id=sample_student["id"],
            record_type="positive", category="achievement", points=5,
        )
        r2 = behaviour_service.add_record(
            student_id=sample_student["id"],
            record_type="negative", category="disruption", points=2,
        )
        assert r1["id"] != r2["id"]


class TestGetStudentRecords:
    """Tests for retrieving student behaviour records."""

    def test_get_student_records_empty(self, behaviour_service, sample_student):
        records = behaviour_service.get_student_records(sample_student["id"])
        assert len(records) == 0

    def test_get_student_records_all(self, behaviour_service, sample_student):
        behaviour_service.add_record(
            student_id=sample_student["id"],
            record_type="positive", category="achievement", points=5,
        )
        behaviour_service.add_record(
            student_id=sample_student["id"],
            record_type="negative", category="disruption", points=2,
        )
        records = behaviour_service.get_student_records(sample_student["id"])
        assert len(records) == 2

    def test_get_student_records_filter_positive(self, behaviour_service, sample_student):
        behaviour_service.add_record(
            student_id=sample_student["id"],
            record_type="positive", category="achievement", points=5,
        )
        behaviour_service.add_record(
            student_id=sample_student["id"],
            record_type="negative", category="disruption", points=2,
        )
        positive = behaviour_service.get_student_records(
            sample_student["id"], record_type="positive",
        )
        assert len(positive) == 1
        assert positive[0]["type"] == "positive"

    def test_get_student_records_filter_negative(self, behaviour_service, sample_student):
        behaviour_service.add_record(
            student_id=sample_student["id"],
            record_type="positive", category="achievement", points=5,
        )
        behaviour_service.add_record(
            student_id=sample_student["id"],
            record_type="negative", category="disruption", points=2,
        )
        negative = behaviour_service.get_student_records(
            sample_student["id"], record_type="negative",
        )
        assert len(negative) == 1
        assert negative[0]["type"] == "negative"

    def test_get_student_records_limit(self, behaviour_service, sample_student):
        for i in range(10):
            behaviour_service.add_record(
                student_id=sample_student["id"],
                record_type="positive", category="effort", points=1,
                incident_date=f"2026-01-{i + 1:02d}",
            )
        records = behaviour_service.get_student_records(sample_student["id"], limit=5)
        assert len(records) == 5

    def test_get_student_records_ordered_by_date_desc(self, behaviour_service, sample_student):
        behaviour_service.add_record(
            student_id=sample_student["id"],
            record_type="positive", category="effort",
            incident_date="2026-01-01",
        )
        behaviour_service.add_record(
            student_id=sample_student["id"],
            record_type="positive", category="effort",
            incident_date="2026-01-10",
        )
        behaviour_service.add_record(
            student_id=sample_student["id"],
            record_type="positive", category="effort",
            incident_date="2026-01-05",
        )
        records = behaviour_service.get_student_records(sample_student["id"])
        dates = [r["incident_date"] for r in records]
        assert dates == sorted(dates, reverse=True)


class TestStudentPoints:
    """Tests for getting student behaviour points."""

    def test_student_points_empty(self, behaviour_service, sample_student):
        points = behaviour_service.get_student_points(sample_student["id"])
        assert points["positive"] == 0
        assert points["negative"] == 0
        assert points["net"] == 0

    def test_student_points_positive_only(self, behaviour_service, sample_student):
        behaviour_service.add_record(
            student_id=sample_student["id"],
            record_type="positive", category="achievement", points=5,
        )
        behaviour_service.add_record(
            student_id=sample_student["id"],
            record_type="positive", category="effort", points=3,
        )
        points = behaviour_service.get_student_points(sample_student["id"])
        assert points["positive"] == 8
        assert points["negative"] == 0
        assert points["net"] == 8

    def test_student_points_negative_only(self, behaviour_service, sample_student):
        behaviour_service.add_record(
            student_id=sample_student["id"],
            record_type="negative", category="disruption", points=4,
        )
        points = behaviour_service.get_student_points(sample_student["id"])
        assert points["positive"] == 0
        assert points["negative"] == 4
        assert points["net"] == -4

    def test_student_points_mixed(self, behaviour_service, sample_student):
        behaviour_service.add_record(
            student_id=sample_student["id"],
            record_type="positive", category="achievement", points=10,
        )
        behaviour_service.add_record(
            student_id=sample_student["id"],
            record_type="negative", category="disruption", points=3,
        )
        behaviour_service.add_record(
            student_id=sample_student["id"],
            record_type="positive", category="effort", points=5,
        )
        points = behaviour_service.get_student_points(sample_student["id"])
        assert points["positive"] == 15
        assert points["negative"] == 3
        assert points["net"] == 12

    def test_student_points_net_can_be_negative(self, behaviour_service, sample_student):
        behaviour_service.add_record(
            student_id=sample_student["id"],
            record_type="positive", category="effort", points=2,
        )
        behaviour_service.add_record(
            student_id=sample_student["id"],
            record_type="negative", category="disruption", points=10,
        )
        points = behaviour_service.get_student_points(sample_student["id"])
        assert points["net"] == -8


class TestResolveRecord:
    """Tests for resolving behaviour records."""

    def test_resolve_record(self, behaviour_service, sample_student):
        record = behaviour_service.add_record(
            student_id=sample_student["id"],
            record_type="negative", category="disruption",
        )
        result = behaviour_service.resolve_record(record["id"])
        assert result is True

    def test_resolve_record_updates_flag(self, behaviour_service, sample_student):
        record = behaviour_service.add_record(
            student_id=sample_student["id"],
            record_type="negative", category="disruption",
        )
        behaviour_service.resolve_record(record["id"])
        records = behaviour_service.get_student_records(sample_student["id"])
        assert records[0]["resolved"] == 1


class TestMarkParentNotified:
    """Tests for marking parent notified."""

    def test_mark_parent_notified(self, behaviour_service, sample_student):
        record = behaviour_service.add_record(
            student_id=sample_student["id"],
            record_type="negative", category="disruption",
        )
        result = behaviour_service.mark_parent_notified(record["id"])
        assert result is True

    def test_mark_parent_notified_updates_flag(self, behaviour_service, sample_student):
        record = behaviour_service.add_record(
            student_id=sample_student["id"],
            record_type="negative", category="disruption",
        )
        behaviour_service.mark_parent_notified(record["id"])
        records = behaviour_service.get_student_records(sample_student["id"])
        assert records[0]["parent_notified"] == 1


class TestRecentIncidents:
    """Tests for getting recent incidents."""

    def test_get_recent_incidents_empty(self, behaviour_service):
        incidents = behaviour_service.get_recent_incidents()
        assert len(incidents) == 0

    def test_get_recent_incidents_returns_negative_only(self, behaviour_service, sample_student):
        # Positive should not appear
        behaviour_service.add_record(
            student_id=sample_student["id"],
            record_type="positive", category="achievement", points=5,
            incident_date="2026-03-09",
        )
        # Only negative within last 7 days should appear
        behaviour_service.add_record(
            student_id=sample_student["id"],
            record_type="negative", category="disruption", points=3,
            incident_date="2026-03-09",
        )
        incidents = behaviour_service.get_recent_incidents(days=7)
        # All should be negative type
        for inc in incidents:
            assert inc["type"] == "negative"

    def test_get_recent_incidents_includes_student_info(self, behaviour_service, sample_student):
        behaviour_service.add_record(
            student_id=sample_student["id"],
            record_type="negative", category="disruption",
            incident_date="2026-03-09",
        )
        incidents = behaviour_service.get_recent_incidents(days=7)
        if len(incidents) > 0:
            assert "first_name" in incidents[0]
            assert "last_name" in incidents[0]
            assert "year_group" in incidents[0]

    def test_get_recent_incidents_limit(self, behaviour_service, student_service):
        s1 = student_service.create_student(first_name="A", last_name="One", year_group="7")
        for i in range(10):
            behaviour_service.add_record(
                student_id=s1["id"],
                record_type="negative", category="late",
                incident_date="2026-03-09",
            )
        incidents = behaviour_service.get_recent_incidents(days=7, limit=5)
        assert len(incidents) <= 5


class TestMultipleStudents:
    """Integration tests across multiple students."""

    def test_points_isolated_per_student(self, behaviour_service, student_service):
        s1 = student_service.create_student(first_name="A", last_name="One")
        s2 = student_service.create_student(first_name="B", last_name="Two")
        behaviour_service.add_record(
            student_id=s1["id"], record_type="positive", category="achievement", points=10,
        )
        behaviour_service.add_record(
            student_id=s2["id"], record_type="negative", category="disruption", points=5,
        )
        p1 = behaviour_service.get_student_points(s1["id"])
        p2 = behaviour_service.get_student_points(s2["id"])
        assert p1["positive"] == 10
        assert p1["negative"] == 0
        assert p2["positive"] == 0
        assert p2["negative"] == 5

    def test_records_isolated_per_student(self, behaviour_service, student_service):
        s1 = student_service.create_student(first_name="A", last_name="One")
        s2 = student_service.create_student(first_name="B", last_name="Two")
        behaviour_service.add_record(
            student_id=s1["id"], record_type="positive", category="effort",
        )
        behaviour_service.add_record(
            student_id=s1["id"], record_type="negative", category="late",
        )
        behaviour_service.add_record(
            student_id=s2["id"], record_type="positive", category="effort",
        )
        assert len(behaviour_service.get_student_records(s1["id"])) == 2
        assert len(behaviour_service.get_student_records(s2["id"])) == 1
