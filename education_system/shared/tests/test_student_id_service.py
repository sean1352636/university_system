"""Tests for StudentIDService."""

import json
import pytest


@pytest.fixture
def id_db(tmp_path):
    return str(tmp_path / "student_id.db")


@pytest.fixture
def svc(id_db):
    from education_system.shared.student_id.student_id_service import StudentIDService
    return StudentIDService(id_db)


class TestGenerateIDCard:
    def test_returns_card_details(self, svc):
        card = svc.generate_id_card("STU001", "Alice Smith", validity_years=2)
        assert "card_number" in card
        assert card["card_number"].startswith("ID-")
        assert "issue_date" in card
        assert "expiry_date" in card

    def test_card_retrievable(self, svc):
        svc.generate_id_card("STU001", "Alice Smith")
        fetched = svc.get_id_card("STU001")
        assert fetched is not None
        assert fetched["full_name"] == "Alice Smith"
        assert fetched["status"] == "active"

    def test_replaces_existing_active_card(self, svc):
        c1 = svc.generate_id_card("STU001", "Alice Smith")
        c2 = svc.generate_id_card("STU001", "Alice Smith")
        assert c1["card_number"] != c2["card_number"]
        # Only one active card
        active = svc.list_active_cards()
        stu001 = [c for c in active if c["student_id"] == "STU001"]
        assert len(stu001) == 1


class TestCardNumberAndQR:
    def test_card_number_format(self, svc):
        num = svc.generate_card_number()
        assert num.startswith("ID-")
        parts = num.split("-")
        assert len(parts) == 3

    def test_unique_card_numbers(self, svc):
        numbers = {svc.generate_card_number() for _ in range(20)}
        assert len(numbers) == 20

    def test_qr_data_is_valid_json(self, svc):
        qr = svc.generate_qr_data("ID-AAAA-0", "STU001", "Test Student")
        data = json.loads(qr)
        assert data["card"] == "ID-AAAA-0"
        assert data["id"] == "STU001"
        assert data["name"] == "Test Student"


class TestDeactivateCard:
    def test_deactivate_removes_from_active(self, svc):
        svc.generate_id_card("STU001", "Alice Smith")
        card = svc.get_id_card("STU001")
        svc.deactivate_card(card["id"])
        active = svc.list_active_cards()
        assert all(c["student_id"] != "STU001" for c in active)

    def test_get_card_returns_none_after_deactivate(self, svc):
        svc.generate_id_card("STU001", "Alice Smith")
        card = svc.get_id_card("STU001")
        svc.deactivate_card(card["id"])
        assert svc.get_id_card("STU001") is None


class TestReissueCard:
    def test_reissue_creates_new_card(self, svc):
        original = svc.generate_id_card("STU001", "Alice Smith")
        reissued = svc.reissue_card("STU001", reason="Lost")
        assert reissued["card_number"] != original["card_number"]

    def test_reissue_deactivates_old(self, svc):
        svc.generate_id_card("STU001", "Alice Smith")
        svc.reissue_card("STU001", reason="Damaged")
        active = svc.list_active_cards()
        stu001 = [c for c in active if c["student_id"] == "STU001"]
        assert len(stu001) == 1

    def test_reissue_no_existing_raises(self, svc):
        with pytest.raises(ValueError, match="No existing card"):
            svc.reissue_card("STU999", reason="Lost")


class TestListActiveCards:
    def test_list_multiple_students(self, svc):
        svc.generate_id_card("STU001", "Alice Smith")
        svc.generate_id_card("STU002", "Bob Jones")
        active = svc.list_active_cards()
        assert len(active) == 2
        names = {c["full_name"] for c in active}
        assert names == {"Alice Smith", "Bob Jones"}

    def test_list_empty(self, svc):
        assert svc.list_active_cards() == []
