"""Tests for InterventionService."""

import pytest
from education_system.secondary_school.core.exceptions import InterventionError


class TestCreateGroup:
    """Tests for creating intervention groups."""

    def test_create_group_returns_dict(
        self, intervention_service, sample_subject
    ):
        group = intervention_service.create_group(
            name="Maths Catch-up",
            subject_id=sample_subject["id"],
            year_group="9",
            lead_teacher="Mr Smith",
            target="Improve grades from 4 to 5",
            start_date="2025-09-01",
            end_date="2025-12-20",
        )
        assert isinstance(group, dict)
        assert group["name"] == "Maths Catch-up"
        assert group["year_group"] == "9"
        assert group["lead_teacher"] == "Mr Smith"


class TestListGroups:
    """Tests for listing intervention groups."""

    def test_list_groups_returns_active(self, intervention_service, sample_subject):
        intervention_service.create_group(
            name="Group A", subject_id=sample_subject["id"],
        )
        intervention_service.create_group(
            name="Group B", subject_id=sample_subject["id"],
        )
        groups = intervention_service.list_groups(status="active")
        assert len(groups) >= 2
        names = [g["name"] for g in groups]
        assert "Group A" in names
        assert "Group B" in names


class TestCloseGroup:
    """Tests for closing intervention groups."""

    def test_close_group_changes_status(self, intervention_service, sample_subject):
        group = intervention_service.create_group(
            name="Temp Group", subject_id=sample_subject["id"],
        )
        intervention_service.close_group(group["id"])
        active = intervention_service.list_groups(status="active")
        assert all(g["id"] != group["id"] for g in active)
        closed = intervention_service.list_groups(status="closed")
        assert any(g["id"] == group["id"] for g in closed)


class TestDeleteGroup:
    """Tests for deleting intervention groups."""

    def test_delete_group_removes_group_and_members(
        self, intervention_service, sample_subject, sample_student
    ):
        group = intervention_service.create_group(
            name="Delete Me", subject_id=sample_subject["id"],
        )
        intervention_service.add_member(group["id"], sample_student["id"])
        intervention_service.delete_group(group["id"])
        groups = intervention_service.list_groups(status=None)
        assert all(g["id"] != group["id"] for g in groups)
        members = intervention_service.list_members(group["id"])
        assert len(members) == 0


class TestMembers:
    """Tests for intervention group members."""

    def test_add_member(self, intervention_service, sample_subject, sample_student):
        group = intervention_service.create_group(
            name="Test Group", subject_id=sample_subject["id"],
        )
        intervention_service.add_member(
            group["id"], sample_student["id"],
            baseline_grade="3", target_grade="5",
        )
        members = intervention_service.list_members(group["id"])
        assert len(members) == 1
        assert members[0]["first_name"] == "John"
        assert members[0]["baseline_grade"] == "3"
        assert members[0]["target_grade"] == "5"

    def test_list_members_returns_student_info(
        self, intervention_service, sample_subject, student_service
    ):
        group = intervention_service.create_group(
            name="Info Group", subject_id=sample_subject["id"],
        )
        s1 = student_service.create_student(
            first_name="Alice", last_name="Wonder", year_group="9",
        )
        intervention_service.add_member(group["id"], s1["id"])
        members = intervention_service.list_members(group["id"])
        assert members[0]["first_name"] == "Alice"
        assert members[0]["last_name"] == "Wonder"
        assert "year_group" in members[0]

    def test_update_member_progress(
        self, intervention_service, sample_subject, sample_student
    ):
        group = intervention_service.create_group(
            name="Progress Group", subject_id=sample_subject["id"],
        )
        intervention_service.add_member(group["id"], sample_student["id"])
        members = intervention_service.list_members(group["id"])
        member_id = members[0]["id"]
        intervention_service.update_member_progress(
            member_id, current_grade="5", progress_notes="Improving steadily",
        )
        updated_members = intervention_service.list_members(group["id"])
        assert updated_members[0]["current_grade"] == "5"
        assert updated_members[0]["progress_notes"] == "Improving steadily"

    def test_remove_member(
        self, intervention_service, sample_subject, sample_student
    ):
        group = intervention_service.create_group(
            name="Remove Group", subject_id=sample_subject["id"],
        )
        intervention_service.add_member(group["id"], sample_student["id"])
        members = intervention_service.list_members(group["id"])
        intervention_service.remove_member(members[0]["id"])
        remaining = intervention_service.list_members(group["id"])
        assert len(remaining) == 0
