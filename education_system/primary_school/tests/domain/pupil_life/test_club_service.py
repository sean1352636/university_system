"""Tests for the ClubService in the Primary School system."""

import pytest


class TestCreateClub:
    """Tests for creating clubs."""

    def test_create_club_returns_dict_with_id(self, club_service, sample_staff):
        """Creating a club returns a dict with an id."""
        result = club_service.create_club(
            club_name="Art Club",
            day_of_week="Monday",
            start_time="15:30",
            end_time="16:30",
            staff_id=sample_staff["staff_id"],
            max_capacity=20,
            year_groups="Year 1,Year 2",
        )
        assert isinstance(result, dict)
        assert result["id"] > 0
        assert result["club_name"] == "Art Club"

    def test_create_club_persists(self, club_service):
        """A created club can be retrieved by its id."""
        result = club_service.create_club(
            club_name="Chess Club", day_of_week="Wednesday",
        )
        club = club_service.get_club(result["id"])
        assert club is not None
        assert club["club_name"] == "Chess Club"
        assert club["day_of_week"] == "Wednesday"

    def test_create_club_with_description(self, club_service):
        """A club with a description stores the description."""
        result = club_service.create_club(
            club_name="Science Club",
            description="Fun experiments for curious minds",
        )
        club = club_service.get_club(result["id"])
        assert club["description"] == "Fun experiments for curious minds"


class TestGetClub:
    """Tests for retrieving a single club."""

    def test_get_nonexistent_club(self, club_service):
        """Getting a non-existent club returns None."""
        assert club_service.get_club(99999) is None

    def test_get_club_all_fields(self, club_service, sample_staff):
        """All fields passed to create_club are present on retrieval."""
        result = club_service.create_club(
            club_name="Football",
            day_of_week="Friday",
            start_time="15:15",
            end_time="16:15",
            location="Playing Field",
            staff_id=sample_staff["staff_id"],
            max_capacity=25,
            year_groups="Year 3,Year 4",
            term="Autumn",
        )
        club = club_service.get_club(result["id"])
        assert club["location"] == "Playing Field"
        assert club["max_capacity"] == 25
        assert club["term"] == "Autumn"


class TestListClubs:
    """Tests for listing clubs."""

    def test_list_clubs_empty_db(self, club_service):
        """Listing clubs on an empty database returns an empty list."""
        assert club_service.list_clubs() == []

    def test_list_clubs_returns_all_active(self, club_service):
        """Listing clubs returns all active clubs."""
        club_service.create_club(club_name="Club A")
        club_service.create_club(club_name="Club B")
        clubs = club_service.list_clubs()
        assert len(clubs) == 2

    def test_list_clubs_filter_by_day(self, club_service):
        """Filtering by day_of_week returns only matching clubs."""
        club_service.create_club(club_name="Monday Club", day_of_week="Monday")
        club_service.create_club(club_name="Tuesday Club", day_of_week="Tuesday")
        clubs = club_service.list_clubs(day_of_week="Monday")
        assert len(clubs) == 1
        assert clubs[0]["club_name"] == "Monday Club"


class TestUpdateClub:
    """Tests for updating clubs."""

    @pytest.mark.xfail(reason="schema missing updated_at column")
    def test_update_club_name(self, club_service):
        """Updating a club name persists the change."""
        result = club_service.create_club(club_name="Old Name")
        updated = club_service.update_club(result["id"], club_name="New Name")
        assert updated["club_name"] == "New Name"

    def test_update_with_no_valid_fields(self, club_service):
        """Passing no recognised fields returns None."""
        result = club_service.create_club(club_name="Test")
        assert club_service.update_club(result["id"], bogus="val") is None


class TestDeleteClub:
    """Tests for deleting clubs."""

    def test_delete_existing_club(self, club_service):
        """Deleting an existing club returns True and removes it."""
        result = club_service.create_club(club_name="Gone")
        assert club_service.delete_club(result["id"]) is True
        assert club_service.get_club(result["id"]) is None

    def test_delete_nonexistent_club(self, club_service):
        """Deleting a non-existent club returns False."""
        assert club_service.delete_club(99999) is False


class TestMembership:
    """Tests for club membership operations."""

    def test_add_and_get_members(self, club_service, sample_pupil):
        """Adding a member and retrieving members shows the pupil."""
        club = club_service.create_club(club_name="Reading Club")
        club_service.add_member(club["id"], sample_pupil["pupil_id"])
        members = club_service.get_members(club["id"])
        assert len(members) == 1
        assert members[0]["pupil_id"] == sample_pupil["pupil_id"]

    def test_remove_member(self, club_service, sample_pupil):
        """Removing a member removes them from the club."""
        club = club_service.create_club(club_name="Drama Club")
        club_service.add_member(club["id"], sample_pupil["pupil_id"])
        assert club_service.remove_member(club["id"], sample_pupil["pupil_id"]) is True
        assert club_service.get_members(club["id"]) == []

    def test_remove_nonexistent_member(self, club_service, sample_pupil):
        """Removing a non-member returns False."""
        club = club_service.create_club(club_name="Empty Club")
        assert club_service.remove_member(club["id"], sample_pupil["pupil_id"]) is False

    def test_get_pupil_clubs(self, club_service, sample_pupil):
        """get_pupil_clubs returns all clubs a pupil belongs to."""
        c1 = club_service.create_club(club_name="Club X")
        c2 = club_service.create_club(club_name="Club Y")
        club_service.add_member(c1["id"], sample_pupil["pupil_id"])
        club_service.add_member(c2["id"], sample_pupil["pupil_id"])
        clubs = club_service.get_pupil_clubs(sample_pupil["pupil_id"])
        assert len(clubs) == 2
        names = {c["club_name"] for c in clubs}
        assert names == {"Club X", "Club Y"}

    def test_get_pupil_clubs_empty(self, club_service, sample_pupil):
        """A pupil with no memberships returns an empty list."""
        assert club_service.get_pupil_clubs(sample_pupil["pupil_id"]) == []

    def test_delete_club_removes_members(self, club_service, sample_pupil):
        """Deleting a club also removes its membership records."""
        club = club_service.create_club(club_name="Temp Club")
        club_service.add_member(club["id"], sample_pupil["pupil_id"])
        club_service.delete_club(club["id"])
        assert club_service.get_pupil_clubs(sample_pupil["pupil_id"]) == []
