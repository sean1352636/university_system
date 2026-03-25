"""Tests for AssetsService (equipment and device loans)."""

import pytest

from education_system.college_system.modules.domain.assets.services.assets_service import AssetsService
from education_system.college_system.core.exceptions import AssetsError


class TestAssetsService:
    @pytest.fixture
    def assets_service(self, db_path):
        return AssetsService(db_path)

    def test_create_loan(self, assets_service, sample_student):
        loan = assets_service.create_loan(
            description="Dell Latitude 5520",
            asset_tag="LAP-001",
            student_id=sample_student["id"],
            asset_type="laptop",
            condition_out="good",
            recorded_by=1,
            notes="Loaned for coursework",
        )
        assert loan["description"] == "Dell Latitude 5520"
        assert loan["asset_tag"] == "LAP-001"
        assert loan["asset_type"] == "laptop"
        assert loan["status"] == "on_loan"

    def test_create_loan_default_type(self, assets_service, sample_student):
        loan = assets_service.create_loan(
            description="Calculator",
            asset_tag="CALC-001",
            student_id=sample_student["id"],
        )
        assert loan["asset_type"] == "laptop"

    def test_list_loans_all(self, assets_service, sample_student):
        assets_service.create_loan(
            description="Laptop A", asset_tag="LAP-A",
            student_id=sample_student["id"],
        )
        assets_service.create_loan(
            description="Laptop B", asset_tag="LAP-B",
            student_id=sample_student["id"],
        )
        loans = assets_service.list_loans()
        assert len(loans) >= 2

    def test_list_loans_by_status(self, assets_service, sample_student):
        assets_service.create_loan(
            description="Device", asset_tag="DEV-001",
            student_id=sample_student["id"],
        )
        on_loan = assets_service.list_loans(status="on_loan")
        assert all(l["status"] == "on_loan" for l in on_loan)

    def test_list_loans_by_asset_type(self, assets_service, sample_student):
        assets_service.create_loan(
            description="Chromebook", asset_tag="CB-001",
            student_id=sample_student["id"], asset_type="laptop",
        )
        laptops = assets_service.list_loans(asset_type="laptop")
        assert all(l["asset_type"] == "laptop" for l in laptops)

    def test_get_loan(self, assets_service, sample_student):
        created = assets_service.create_loan(
            description="Specific Device", asset_tag="SD-001",
            student_id=sample_student["id"],
        )
        found = assets_service.get_loan(created["id"])
        assert found["description"] == "Specific Device"
        assert found["asset_tag"] == "SD-001"

    def test_get_loan_not_found(self, assets_service):
        with pytest.raises(AssetsError, match="not found"):
            assets_service.get_loan(99999)

    def test_return_asset(self, assets_service, sample_student):
        loan = assets_service.create_loan(
            description="Return Me", asset_tag="RET-001",
            student_id=sample_student["id"],
        )
        returned = assets_service.return_asset(loan["id"], condition_in="good")
        assert returned["status"] == "returned"
        assert returned["condition_in"] == "good"

    def test_return_asset_with_damage(self, assets_service, sample_student):
        loan = assets_service.create_loan(
            description="Damaged Device", asset_tag="DMG-001",
            student_id=sample_student["id"],
        )
        returned = assets_service.return_asset(
            loan["id"], condition_in="damaged", notes="Screen cracked",
        )
        assert returned["status"] == "returned"
        assert returned["condition_in"] == "damaged"

    def test_update_loan(self, assets_service, sample_student):
        loan = assets_service.create_loan(
            description="Update Me", asset_tag="UPD-001",
            student_id=sample_student["id"],
        )
        updated = assets_service.update_loan(
            loan["id"], notes="Extended loan period",
            due_date="2026-07-01",
        )
        assert updated["notes"] == "Extended loan period"

    def test_update_loan_no_valid_fields(self, assets_service, sample_student):
        loan = assets_service.create_loan(
            description="No Update", asset_tag="NUP-001",
            student_id=sample_student["id"],
        )
        with pytest.raises(AssetsError, match="No valid fields"):
            assets_service.update_loan(loan["id"], bad_field="nope")

    def test_get_student_loans(self, assets_service, sample_student):
        assets_service.create_loan(
            description="Student Device 1", asset_tag="SD1-001",
            student_id=sample_student["id"],
        )
        assets_service.create_loan(
            description="Student Device 2", asset_tag="SD2-001",
            student_id=sample_student["id"],
        )
        student_loans = assets_service.get_student_loans(sample_student["id"])
        assert len(student_loans) >= 2

    def test_get_student_loans_empty(self, assets_service, sample_student):
        loans = assets_service.get_student_loans(sample_student["id"])
        assert loans == []

    def test_delete_asset(self, assets_service, sample_student):
        loan = assets_service.create_loan(
            description="Delete Me", asset_tag="DEL-001",
            student_id=sample_student["id"],
        )
        assert assets_service.delete_asset(loan["id"]) is True

    def test_delete_asset_not_found(self, assets_service):
        with pytest.raises(AssetsError, match="not found"):
            assets_service.delete_asset(99999)

    def test_count_active_loans(self, assets_service, sample_student):
        initial_count = assets_service.count_active_loans()
        assets_service.create_loan(
            description="Active Loan", asset_tag="ACT-001",
            student_id=sample_student["id"],
        )
        assert assets_service.count_active_loans() == initial_count + 1

    def test_count_active_loans_excludes_returned(self, assets_service, sample_student):
        loan = assets_service.create_loan(
            description="Return Count Test", asset_tag="RCT-001",
            student_id=sample_student["id"],
        )
        count_before = assets_service.count_active_loans()
        assets_service.return_asset(loan["id"])
        count_after = assets_service.count_active_loans()
        assert count_after == count_before - 1
