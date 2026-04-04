"""Tests for ClubsService."""
import pytest

from education_system.secondary_school.modules.domain.student_life.clubs.services.clubs_service import ClubsService


@pytest.fixture
def clubs_service(db_path):
    return ClubsService(db_path)


class TestClubs:
    def test_create_club(self, clubs_service):
        club = clubs_service.create_club(
            name="Chess Club", category="academic",
            description="Weekly chess", day_of_week="Wednesday",
            start_time="15:30", end_time="16:30",
            location="Room 12", teacher="Mr Adams", max_members=20,
        )
        assert club["name"] == "Chess Club"
        assert club["category"] == "academic"
        assert club["status"] == "active"

    def test_list_clubs(self, clubs_service):
        clubs_service.create_club(name="Art Club", category="arts")
        clubs_service.create_club(name="Football", category="sport")
        result = clubs_service.list_clubs()
        assert len(result) == 2

    def test_delete_club(self, clubs_service):
        club = clubs_service.create_club(name="Drama Club")
        clubs_service.delete_club(club["id"])
        result = clubs_service.list_clubs()
        assert len(result) == 0


class TestClubMembers:
    def test_add_member(self, clubs_service, sample_student):
        club = clubs_service.create_club(name="Science Club")
        clubs_service.add_member(club["id"], sample_student["id"])
        members = clubs_service.list_members(club["id"])
        assert len(members) == 1
        assert members[0]["first_name"] == "John"

    def test_list_members(self, clubs_service, sample_student, sample_student_ks4):
        club = clubs_service.create_club(name="Music Club")
        clubs_service.add_member(club["id"], sample_student["id"])
        clubs_service.add_member(club["id"], sample_student_ks4["id"])
        members = clubs_service.list_members(club["id"])
        assert len(members) == 2

    def test_remove_member(self, clubs_service, sample_student):
        club = clubs_service.create_club(name="Book Club")
        clubs_service.add_member(club["id"], sample_student["id"])
        members = clubs_service.list_members(club["id"])
        clubs_service.remove_member(members[0]["id"])
        assert clubs_service.list_members(club["id"]) == []

    def test_member_count(self, clubs_service, sample_student, sample_student_ks4):
        club = clubs_service.create_club(name="Debate Club")
        assert clubs_service.member_count(club["id"]) == 0
        clubs_service.add_member(club["id"], sample_student["id"])
        clubs_service.add_member(club["id"], sample_student_ks4["id"])
        assert clubs_service.member_count(club["id"]) == 2
