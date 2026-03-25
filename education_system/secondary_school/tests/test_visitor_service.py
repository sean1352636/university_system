"""Tests for VisitorService."""
import pytest


class TestVisitor:
    def test_sign_in(self, visitor_service):
        visitor = visitor_service.sign_in(
            visitor_name="Jane Smith", purpose="Meeting with Head",
            visiting="Mr Brown", organisation="Ofsted",
        )
        assert visitor["visitor_name"] == "Jane Smith"
        assert visitor["purpose"] == "Meeting with Head"

    def test_sign_out(self, visitor_service):
        visitor = visitor_service.sign_in("John Doe", "Delivery")
        assert visitor["sign_out_time"] is None
        visitor_service.sign_out(visitor["id"])
        visitors = visitor_service.list_visitors()
        signed_out = [v for v in visitors if v["id"] == visitor["id"]][0]
        assert signed_out["sign_out_time"] is not None

    def test_list_visitors(self, visitor_service):
        visitor_service.sign_in("Visitor A", "Meeting")
        visitor_service.sign_in("Visitor B", "Interview")
        visitors = visitor_service.list_visitors()
        assert len(visitors) >= 2

    def test_list_visitors_on_site_only(self, visitor_service):
        v1 = visitor_service.sign_in("On Site", "Meeting")
        v2 = visitor_service.sign_in("Signed Out", "Delivery")
        visitor_service.sign_out(v2["id"])
        on_site = visitor_service.list_visitors(on_site_only=True)
        assert any(v["id"] == v1["id"] for v in on_site)
        assert all(v["id"] != v2["id"] for v in on_site)

    def test_delete_visitor(self, visitor_service):
        visitor = visitor_service.sign_in("Delete Me", "Tour")
        visitor_service.delete_visitor(visitor["id"])
        visitors = visitor_service.list_visitors()
        assert all(v["id"] != visitor["id"] for v in visitors)

    def test_on_site_count(self, visitor_service):
        visitor_service.sign_in("Count A", "Meeting")
        visitor_service.sign_in("Count B", "Interview")
        v3 = visitor_service.sign_in("Count C", "Delivery")
        visitor_service.sign_out(v3["id"])
        count = visitor_service.on_site_count()
        assert count >= 2
