"""Tests for TransportService."""

import pytest


class TestTransportService:
    @pytest.fixture
    def transport_service(self, db_path):
        from education_system.college_system.modules.domain.transport.services.transport_service import TransportService
        return TransportService(db_path)

    def test_create_record(self, transport_service, sample_student):
        record = transport_service.create_record(
            student_id=sample_student["id"],
            transport_type="bus_pass",
            route="Route 42",
            provider="National Express",
            eligible=1,
            cost=350.0,
        )
        assert record["transport_type"] == "bus_pass"
        assert record["route"] == "Route 42"
        assert record["provider"] == "National Express"
        assert record["eligible"] == 1
        assert record["cost"] == 350.0
        assert record["status"] == "active"

    def test_list_records(self, transport_service, sample_student):
        transport_service.create_record(
            student_id=sample_student["id"],
            transport_type="bus_pass", route="Route 1",
        )
        records = transport_service.list_records()
        assert len(records) >= 1

    def test_get_record(self, transport_service, sample_student):
        created = transport_service.create_record(
            student_id=sample_student["id"],
            transport_type="train_pass", route="Northern Line",
        )
        found = transport_service.get_record(created["id"])
        assert found["transport_type"] == "train_pass"

    def test_update_record(self, transport_service, sample_student):
        record = transport_service.create_record(
            student_id=sample_student["id"],
            transport_type="bus_pass", route="Route 1",
        )
        updated = transport_service.update_record(
            record["id"], route="Route 2",
        )
        assert updated["route"] == "Route 2"

    def test_get_student_transport(self, transport_service, sample_student):
        transport_service.create_record(
            student_id=sample_student["id"],
            transport_type="bus_pass", route="Route 5",
        )
        found = transport_service.get_student_transport(sample_student["id"])
        assert found is not None

    def test_delete_record(self, transport_service, sample_student):
        record = transport_service.create_record(
            student_id=sample_student["id"],
            transport_type="driving", route="N/A",
        )
        result = transport_service.delete_record(record["id"])
        assert result is True
