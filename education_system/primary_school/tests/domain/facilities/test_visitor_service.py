"""Tests for the VisitorService in the Primary School system."""

import pytest

from education_system.primary_school.core.exceptions import VisitorError


class TestSignIn:
    """Tests for signing in visitors."""

    def test_sign_in_returns_dict_with_id(self, visitor_service):
        """Signing in a visitor returns a dict with a valid ID."""
        result = visitor_service.sign_in(
            visitor_name="Jane Doe",
            purpose="Parent meeting",
            visiting="Mrs Smith",
            organisation="N/A",
            dbs_checked=1,
            badge_number="V001",
        )
        assert isinstance(result, dict)
        assert result["id"] > 0
        assert result["visitor_name"] == "Jane Doe"
        assert result["status"] == "Signed In"

    def test_sign_in_persists(self, visitor_service):
        """A signed-in visitor is retrievable via get_visitor."""
        result = visitor_service.sign_in(
            visitor_name="John Builder",
            purpose="Maintenance",
            organisation="ABC Plumbing",
        )
        fetched = visitor_service.get_visitor(result["id"])
        assert fetched is not None
        assert fetched["visitor_name"] == "John Builder"
        assert fetched["purpose"] == "Maintenance"
        assert fetched["organisation"] == "ABC Plumbing"
        assert fetched["sign_out_time"] is None

    def test_sign_in_multiple_visitors(self, visitor_service):
        """Multiple visitors can be signed in independently."""
        v1 = visitor_service.sign_in(
            visitor_name="Visitor A", purpose="Interview",
        )
        v2 = visitor_service.sign_in(
            visitor_name="Visitor B", purpose="Delivery",
        )
        assert v1["id"] != v2["id"]


class TestSignOut:
    """Tests for signing out visitors."""

    def test_sign_out_returns_true(self, visitor_service):
        """Signing out a currently signed-in visitor returns True."""
        result = visitor_service.sign_in(
            visitor_name="Mary Visitor", purpose="Meeting",
        )
        assert visitor_service.sign_out(result["id"]) is True

    def test_sign_out_sets_sign_out_time(self, visitor_service):
        """After sign-out the sign_out_time field is populated."""
        result = visitor_service.sign_in(
            visitor_name="Tom Visitor", purpose="Tour",
        )
        visitor_service.sign_out(result["id"])
        fetched = visitor_service.get_visitor(result["id"])
        assert fetched["sign_out_time"] is not None

    def test_sign_out_already_signed_out_raises(self, visitor_service):
        """Signing out a visitor who is already signed out raises an error."""
        result = visitor_service.sign_in(
            visitor_name="Double Out", purpose="Test",
        )
        visitor_service.sign_out(result["id"])
        with pytest.raises(VisitorError):
            visitor_service.sign_out(result["id"])


class TestGetVisitor:
    """Tests for retrieving a single visitor."""

    def test_get_nonexistent_visitor_returns_none(self, visitor_service):
        """Requesting a non-existent visitor ID returns None."""
        assert visitor_service.get_visitor(99999) is None


class TestListVisitors:
    """Tests for listing visitors."""

    def test_list_visitors_empty_db(self, visitor_service):
        """Listing visitors on an empty database returns an empty list."""
        assert visitor_service.list_visitors() == []

    def test_list_visitors_filter_not_signed_out(self, visitor_service):
        """Filtering signed_out=False returns only visitors still on site."""
        v1 = visitor_service.sign_in(
            visitor_name="Still Here", purpose="Workshop",
        )
        v2 = visitor_service.sign_in(
            visitor_name="Gone Home", purpose="Delivery",
        )
        visitor_service.sign_out(v2["id"])
        on_site = visitor_service.list_visitors(signed_out=False)
        assert len(on_site) == 1
        assert on_site[0]["visitor_name"] == "Still Here"


class TestGetCurrentVisitors:
    """Tests for retrieving currently signed-in visitors."""

    def test_current_visitors_empty_db(self, visitor_service):
        """No current visitors on an empty database."""
        assert visitor_service.get_current_visitors() == []

    def test_current_visitors_excludes_signed_out(self, visitor_service):
        """get_current_visitors excludes visitors who have signed out."""
        v1 = visitor_service.sign_in(
            visitor_name="Present", purpose="Parent help",
        )
        v2 = visitor_service.sign_in(
            visitor_name="Departed", purpose="Courier",
        )
        visitor_service.sign_out(v2["id"])
        current = visitor_service.get_current_visitors()
        names = [v["visitor_name"] for v in current]
        assert "Present" in names
        assert "Departed" not in names
