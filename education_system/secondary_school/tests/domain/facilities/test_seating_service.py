"""Tests for SeatingService."""
import pytest


class TestSeating:
    def test_create_plan(self, seating_service):
        plan = seating_service.create_plan(
            name="9A Maths", room="Room 101",
            year_group="9", teacher="Mr Smith",
        )
        assert plan["name"] == "9A Maths"
        assert plan["room"] == "Room 101"

    def test_list_plans(self, seating_service):
        seating_service.create_plan("Plan A", "Room 1")
        seating_service.create_plan("Plan B", "Room 2")
        plans = seating_service.list_plans()
        assert len(plans) >= 2

    def test_assign_seat(self, seating_service, sample_student):
        plan = seating_service.create_plan("Assign Test", "Room 1")
        seating_service.assign_seat(plan["id"], sample_student["id"], seat_row=1, seat_col=2)
        assignments = seating_service.list_assignments(plan["id"])
        assert len(assignments) == 1
        assert assignments[0]["seat_row"] == 1
        assert assignments[0]["seat_col"] == 2

    def test_list_assignments(self, seating_service, sample_student, sample_student_ks4):
        plan = seating_service.create_plan("List Test", "Room 1")
        seating_service.assign_seat(plan["id"], sample_student["id"], 1, 1)
        seating_service.assign_seat(plan["id"], sample_student_ks4["id"], 1, 2)
        assignments = seating_service.list_assignments(plan["id"])
        assert len(assignments) == 2

    def test_remove_seat(self, seating_service, sample_student):
        plan = seating_service.create_plan("Remove Test", "Room 1")
        seating_service.assign_seat(plan["id"], sample_student["id"], 1, 1)
        assignments = seating_service.list_assignments(plan["id"])
        seating_service.remove_seat(assignments[0]["id"])
        after = seating_service.list_assignments(plan["id"])
        assert len(after) == 0

    def test_seat_count(self, seating_service, sample_student, sample_student_ks4):
        plan = seating_service.create_plan("Count Test", "Room 1")
        assert seating_service.seat_count(plan["id"]) == 0
        seating_service.assign_seat(plan["id"], sample_student["id"], 1, 1)
        seating_service.assign_seat(plan["id"], sample_student_ks4["id"], 1, 2)
        assert seating_service.seat_count(plan["id"]) == 2

    def test_delete_plan(self, seating_service):
        plan = seating_service.create_plan("Delete Test", "Room 1")
        seating_service.delete_plan(plan["id"])
        plans = seating_service.list_plans()
        assert all(p["id"] != plan["id"] for p in plans)
