"""Tests for StaffHRService."""

import pytest

from education_system.college_system.infrastructure.database.db import connect


def _seed_staff(db_path, staff_id_str, first_name, last_name):
    """Insert a row into the staff table and return its integer id."""
    conn = connect(db_path)
    try:
        conn.execute(
            "INSERT INTO staff (staff_id, first_name, last_name) VALUES (?, ?, ?)",
            (staff_id_str, first_name, last_name),
        )
        conn.commit()
        row = conn.execute(
            "SELECT id FROM staff WHERE staff_id = ?", (staff_id_str,)
        ).fetchone()
        return row["id"]
    finally:
        conn.close()


class TestStaffHRService:
    @pytest.fixture
    def staff_hr_service(self, db_path):
        from education_system.college_system.modules.domain.staff_hr.services.staff_hr_service import StaffHRService
        return StaffHRService(db_path)

    @pytest.fixture
    def staff_ids(self, db_path):
        """Seed two staff members and return their integer ids."""
        id1 = _seed_staff(db_path, "TCH001", "Alice", "Smith")
        id2 = _seed_staff(db_path, "TCH002", "Bob", "Jones")
        return id1, id2

    def test_create_record(self, staff_hr_service, staff_ids):
        sid = staff_ids[0]
        record = staff_hr_service.create_record(
            staff_id=sid, contract_type="full_time",
            dbs_number="DBS001", dbs_status="clear",
        )
        assert record["staff_id"] == sid
        assert record["contract_type"] == "full_time"
        assert record["dbs_number"] == "DBS001"

    def test_list_records(self, staff_hr_service, staff_ids):
        staff_hr_service.create_record(staff_id=staff_ids[0])
        staff_hr_service.create_record(staff_id=staff_ids[1])
        records = staff_hr_service.list_records()
        assert len(records) >= 2

    def test_list_records_filter_contract_type(self, staff_hr_service, staff_ids):
        staff_hr_service.create_record(staff_id=staff_ids[0], contract_type="full_time")
        staff_hr_service.create_record(staff_id=staff_ids[1], contract_type="part_time")
        full_time = staff_hr_service.list_records(contract_type="full_time")
        assert all(r["contract_type"] == "full_time" for r in full_time)

    def test_get_record(self, staff_hr_service, staff_ids):
        created = staff_hr_service.create_record(staff_id=staff_ids[0], dbs_status="clear")
        found = staff_hr_service.get_record(created["id"])
        assert found["dbs_status"] == "clear"

    def test_get_by_staff(self, staff_hr_service, staff_ids):
        staff_hr_service.create_record(staff_id=staff_ids[0], contract_type="part_time")
        found = staff_hr_service.get_by_staff(staff_ids[0])
        assert found is not None
        assert found["contract_type"] == "part_time"

    def test_update_record(self, staff_hr_service, staff_ids):
        record = staff_hr_service.create_record(staff_id=staff_ids[0])
        updated = staff_hr_service.update_record(
            record["id"], dbs_status="clear", notes="Updated",
        )
        assert updated["dbs_status"] == "clear"
        assert updated["notes"] == "Updated"

    def test_count_staff(self, staff_hr_service, staff_ids):
        staff_hr_service.create_record(staff_id=staff_ids[0])
        count = staff_hr_service.count_staff()
        assert count >= 1
