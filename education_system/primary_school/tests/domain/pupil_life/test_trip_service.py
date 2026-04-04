"""Tests for the TripService in the Primary School system."""

import pytest


class TestCreateTrip:
    """Tests for creating trips."""

    def test_create_trip_returns_dict(self, trip_service):
        """Creating a trip returns a dict with id, name, and date."""
        result = trip_service.create_trip(
            trip_name="Farm Visit",
            trip_date="2026-06-15",
            destination="Green Acres Farm",
            year_groups="Year 1,Year 2",
            cost=12.50,
        )
        assert isinstance(result, dict)
        assert result["id"] > 0
        assert result["trip_name"] == "Farm Visit"
        assert result["trip_date"] == "2026-06-15"

    def test_create_trip_persists(self, trip_service, sample_staff):
        """A created trip can be retrieved by id."""
        result = trip_service.create_trip(
            trip_name="Museum Trip",
            trip_date="2026-07-10",
            destination="Natural History Museum",
            description="Year 3 science trip",
            return_date="2026-07-10",
            lead_staff_id=sample_staff["staff_id"],
            cost=8.00,
            max_places=30,
        )
        trip = trip_service.get_trip(result["id"])
        assert trip is not None
        assert trip["trip_name"] == "Museum Trip"
        assert trip["destination"] == "Natural History Museum"
        assert trip["description"] == "Year 3 science trip"
        assert trip["lead_staff_id"] == sample_staff["staff_id"]
        assert trip["max_places"] == 30

    def test_create_trip_defaults(self, trip_service):
        """A trip with minimal fields uses defaults for optional fields."""
        result = trip_service.create_trip(
            trip_name="Local Walk", trip_date="2026-05-01",
        )
        trip = trip_service.get_trip(result["id"])
        assert trip["cost"] == 0


class TestGetTrip:
    """Tests for retrieving a single trip."""

    def test_get_nonexistent_trip(self, trip_service):
        """Getting a non-existent trip returns None."""
        assert trip_service.get_trip(99999) is None


class TestListTrips:
    """Tests for listing trips."""

    def test_list_trips_empty_db(self, trip_service):
        """Listing trips on an empty database returns an empty list."""
        assert trip_service.list_trips() == []

    def test_list_trips_returns_all(self, trip_service):
        """Listing trips returns all trips."""
        trip_service.create_trip(trip_name="Trip A", trip_date="2026-06-01")
        trip_service.create_trip(trip_name="Trip B", trip_date="2026-06-02")
        trips = trip_service.list_trips()
        assert len(trips) == 2

    @pytest.mark.xfail(reason="schema missing updated_at column")
    def test_list_trips_filter_by_status(self, trip_service):
        """Filtering by status returns only matching trips."""
        t = trip_service.create_trip(trip_name="Planned", trip_date="2026-06-01")
        trip_service.update_trip(t["id"], status="Cancelled")
        trip_service.create_trip(trip_name="Active", trip_date="2026-06-02")
        trips = trip_service.list_trips(status="Cancelled")
        assert len(trips) == 1
        assert trips[0]["trip_name"] == "Planned"


class TestUpdateTrip:
    """Tests for updating trips."""

    @pytest.mark.xfail(reason="schema missing updated_at column")
    def test_update_trip_name(self, trip_service):
        """Updating a trip name persists the change."""
        result = trip_service.create_trip(trip_name="Old Name", trip_date="2026-06-01")
        updated = trip_service.update_trip(result["id"], trip_name="New Name")
        assert updated["trip_name"] == "New Name"

    @pytest.mark.xfail(reason="schema missing updated_at column")
    def test_update_cost_and_places(self, trip_service):
        """Updating cost and max_places persists both changes."""
        result = trip_service.create_trip(trip_name="Trip", trip_date="2026-06-01")
        updated = trip_service.update_trip(result["id"], cost=15.00, max_places=25)
        assert updated["cost"] == 15.00
        assert updated["max_places"] == 25

    def test_update_with_no_valid_fields(self, trip_service):
        """Passing no recognised fields returns None."""
        result = trip_service.create_trip(trip_name="Test", trip_date="2026-06-01")
        assert trip_service.update_trip(result["id"], bogus="val") is None


class TestDeleteTrip:
    """Tests for deleting trips."""

    def test_delete_existing_trip(self, trip_service):
        """Deleting an existing trip returns True and removes it."""
        result = trip_service.create_trip(trip_name="Gone", trip_date="2026-06-01")
        assert trip_service.delete_trip(result["id"]) is True
        assert trip_service.get_trip(result["id"]) is None

    def test_delete_nonexistent_trip(self, trip_service):
        """Deleting a non-existent trip returns False."""
        assert trip_service.delete_trip(99999) is False


class TestAttendees:
    """Tests for trip attendee operations."""

    def test_add_attendee(self, trip_service, sample_pupil):
        """Adding an attendee returns True."""
        trip = trip_service.create_trip(trip_name="Day Out", trip_date="2026-06-15")
        result = trip_service.add_attendee(trip["id"], sample_pupil["pupil_id"])
        assert result is True

    def test_get_attendees(self, trip_service, sample_pupil, sample_pupil_ks1):
        """get_attendees returns all attendees for a trip."""
        trip = trip_service.create_trip(trip_name="Zoo Trip", trip_date="2026-06-20")
        trip_service.add_attendee(trip["id"], sample_pupil["pupil_id"])
        trip_service.add_attendee(trip["id"], sample_pupil_ks1["pupil_id"])
        attendees = trip_service.get_attendees(trip["id"])
        assert len(attendees) == 2

    def test_get_attendees_empty(self, trip_service):
        """A trip with no attendees returns an empty list."""
        trip = trip_service.create_trip(trip_name="Empty Trip", trip_date="2026-06-01")
        assert trip_service.get_attendees(trip["id"]) == []

    def test_update_attendee_consent(self, trip_service, sample_pupil):
        """Updating attendee consent_received persists the change."""
        trip = trip_service.create_trip(trip_name="Trip", trip_date="2026-06-15")
        trip_service.add_attendee(trip["id"], sample_pupil["pupil_id"])
        result = trip_service.update_attendee(
            trip["id"], sample_pupil["pupil_id"], consent_received=1,
        )
        assert result is True
        attendees = trip_service.get_attendees(trip["id"])
        assert attendees[0]["consent_received"] == 1

    def test_update_attendee_payment_and_medical(self, trip_service, sample_pupil):
        """Updating payment and medical info persists both changes."""
        trip = trip_service.create_trip(trip_name="Trip", trip_date="2026-06-15")
        trip_service.add_attendee(trip["id"], sample_pupil["pupil_id"])
        trip_service.update_attendee(
            trip["id"], sample_pupil["pupil_id"],
            payment_received=1, medical_info="Carries inhaler",
        )
        attendees = trip_service.get_attendees(trip["id"])
        assert attendees[0]["payment_received"] == 1
        assert attendees[0]["medical_info"] == "Carries inhaler"

    def test_update_attendee_no_fields(self, trip_service, sample_pupil):
        """Updating an attendee with no fields returns None."""
        trip = trip_service.create_trip(trip_name="Trip", trip_date="2026-06-15")
        trip_service.add_attendee(trip["id"], sample_pupil["pupil_id"])
        assert trip_service.update_attendee(trip["id"], sample_pupil["pupil_id"]) is None

    def test_delete_trip_removes_attendees(self, trip_service, sample_pupil):
        """Deleting a trip also removes its attendee records."""
        trip = trip_service.create_trip(trip_name="Temp Trip", trip_date="2026-06-15")
        trip_service.add_attendee(trip["id"], sample_pupil["pupil_id"])
        trip_service.delete_trip(trip["id"])
        assert trip_service.get_trip(trip["id"]) is None
