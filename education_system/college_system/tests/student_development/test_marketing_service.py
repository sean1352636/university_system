"""Tests for MarketingService."""

import pytest


class TestMarketingService:
    @pytest.fixture
    def service(self, db_path):
        from education_system.college_system.modules.domain.marketing.services.marketing_service import MarketingService
        return MarketingService(db_path)

    @pytest.fixture
    def sample_event(self, service):
        return service.create_event(
            event_name="Autumn Open Day",
            event_date="2026-10-15",
            event_type="open_day",
            capacity=500, location="Main Hall",
        )

    def test_create_event(self, service):
        event = service.create_event(
            event_name="Taster Day", event_date="2026-06-20",
            event_type="taster", capacity=100,
        )
        assert event is not None

    def test_list_events(self, service):
        service.create_event("Event A", "2026-06-01")
        service.create_event("Event B", "2026-07-01")
        events = service.list_events()
        assert len(events) >= 2

    def test_get_event(self, service, sample_event):
        eid = sample_event if isinstance(sample_event, int) else sample_event.get("id", sample_event)
        found = service.get_event(eid)
        assert found is not None

    def test_update_event(self, service, sample_event):
        eid = sample_event if isinstance(sample_event, int) else sample_event.get("id", sample_event)
        updated = service.update_event(eid, capacity=600)
        assert updated is not None

    def test_delete_event(self, service, sample_event):
        eid = sample_event if isinstance(sample_event, int) else sample_event.get("id", sample_event)
        result = service.delete_event(eid)
        assert result is True

    def test_create_registration(self, service, sample_event):
        eid = sample_event if isinstance(sample_event, int) else sample_event.get("id", sample_event)
        reg = service.create_registration(
            event_id=eid, student_name="Alice Jones",
            email="alice@school.co.uk", school="Greenfield Academy",
            interests="Computer Science, Mathematics",
        )
        assert reg is not None

    def test_list_registrations(self, service, sample_event):
        eid = sample_event if isinstance(sample_event, int) else sample_event.get("id", sample_event)
        service.create_registration(eid, "Student A")
        regs = service.list_registrations(event_id=eid)
        assert len(regs) >= 1

    def test_mark_attended(self, service, sample_event):
        eid = sample_event if isinstance(sample_event, int) else sample_event.get("id", sample_event)
        reg = service.create_registration(eid, "Attendee")
        rid = reg if isinstance(reg, int) else reg.get("id", reg)
        result = service.mark_attended(rid)
        assert result is not None

    def test_create_campaign(self, service):
        campaign = service.create_campaign(
            campaign_name="Summer Social Media",
            campaign_type="digital",
            budget=2000, target_audience="Year 11 leavers",
        )
        assert campaign is not None

    def test_list_campaigns(self, service):
        service.create_campaign("Campaign A")
        campaigns = service.list_campaigns()
        assert len(campaigns) >= 1

    def test_get_stats(self, service):
        stats = service.get_stats()
        assert stats is not None
