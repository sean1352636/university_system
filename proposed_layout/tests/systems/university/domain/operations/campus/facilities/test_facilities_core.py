"""Tests for the Facilities & Space Management core service.

Covers building/room registration, room bookings (incl. conflict
detection), maintenance requests, work orders, asset inventory, and the
cleaning-schedule / occupancy managers that own their own auxiliary
tables.

Each test gets an isolated SQLite file via the ``facilities_db`` fixture,
which monkeypatches ``DEFAULT_DB_PATH`` and initialises the canonical
facilities schema (the ``CleaningScheduleManager`` /
``OccupancyManager`` tables are created lazily by the service itself).
"""

from __future__ import annotations

import pytest

from education_system.systems.university.infrastructure.database import db as db_module
from education_system.systems.university.infrastructure.database.db import get_connection
from education_system.systems.university.infrastructure.database.schemas.facilities_housing_schemas import (
    init_facilities_management_system_db,
)
from education_system.systems.university.domain.operations.campus.facilities.services.facilities_management_core import (
    AssetManager,
    BuildingManager,
    CleaningScheduleManager,
    MaintenanceRequestManager,
    OccupancyManager,
    RoomBookingManager,
    RoomManager,
    WorkOrderManager,
)


@pytest.fixture
def facilities_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "facilities_test.db")
    monkeypatch.setattr(db_module, "DEFAULT_DB_PATH", db_path)
    init_facilities_management_system_db()
    yield db_path


def _building(**overrides) -> int:
    defaults = dict(
        building_name="Science Block",
        building_code="SCI",
        address="1 Campus Way",
        total_floors=3,
        building_type="academic",
    )
    defaults.update(overrides)
    return BuildingManager.register_building(**defaults)


def _room(building_id: int, **overrides) -> int:
    defaults = dict(
        building_id=building_id,
        room_number="101",
        room_type="Lecture",
        capacity=50,
        floor_number=1,
    )
    defaults.update(overrides)
    return RoomManager.register_room(**defaults)


class TestBuildingManager:
    def test_register_building_returns_id_and_persists(self, facilities_db):
        bid = _building()
        assert isinstance(bid, int) and bid > 0

        with get_connection() as conn:
            row = conn.execute(
                "SELECT building_name, building_code, total_floors, building_type "
                "FROM buildings WHERE building_id = ?", (bid,),
            ).fetchone()
        assert row["building_name"] == "Science Block"
        assert row["building_code"] == "SCI"
        assert row["total_floors"] == 3
        assert row["building_type"] == "academic"

    def test_duplicate_building_code_raises(self, facilities_db):
        _building(building_code="DUP")
        # building_code has a UNIQUE constraint; the service wraps the
        # IntegrityError in a generic Exception.
        with pytest.raises(Exception):
            _building(building_name="Other", building_code="DUP")


class TestRoomManager:
    def test_register_room_backfills_building_name(self, facilities_db):
        bid = _building(building_name="Library", building_code="LIB")
        rid = _room(bid, room_number="A1")
        assert isinstance(rid, int) and rid > 0

        with get_connection() as conn:
            row = conn.execute(
                "SELECT building_id, building, room_number, status, is_active "
                "FROM rooms WHERE room_id = ?", (rid,),
            ).fetchone()
        assert row["building_id"] == bid
        # building_name is looked up from the building when not supplied.
        assert row["building"] == "Library"
        assert row["room_number"] == "A1"
        assert row["status"] == "available"
        assert row["is_active"] == 1

    def test_get_available_rooms_returns_registered_room(self, facilities_db):
        bid = _building()
        rid = _room(bid)
        rooms = RoomManager.get_available_rooms()
        ids = {r["room_id"] for r in rooms}
        assert rid in ids

    def test_get_available_rooms_filters_by_type(self, facilities_db):
        bid = _building()
        _room(bid, room_number="L1", room_type="Lab")
        _room(bid, room_number="C1", room_type="Lecture")

        rooms = RoomManager.get_available_rooms(room_type="Lab")
        assert rooms
        assert all(r["room_type"] == "Lab" for r in rooms)

    def test_get_available_rooms_filters_by_min_capacity(self, facilities_db):
        bid = _building()
        _room(bid, room_number="small", capacity=10)
        big = _room(bid, room_number="big", capacity=200)

        rooms = RoomManager.get_available_rooms(min_capacity=100)
        ids = {r["room_id"] for r in rooms}
        assert big in ids
        assert all(r["capacity"] >= 100 for r in rooms)


class TestRoomBookingManager:
    def test_book_room_returns_id_and_persists(self, facilities_db):
        bid = _building()
        rid = _room(bid)
        booking_id = RoomBookingManager.book_room(
            room_id=rid,
            booked_by="staff01",
            booking_type="lecture",
            start_datetime="2026-09-01T10:00",
            end_datetime="2026-09-01T12:00",
            purpose="Intro lecture",
            expected_attendees=40,
        )
        assert isinstance(booking_id, int) and booking_id > 0

        with get_connection() as conn:
            row = conn.execute(
                "SELECT room_id, booked_by, booking_status, expected_attendees "
                "FROM room_bookings WHERE booking_id = ?", (booking_id,),
            ).fetchone()
        assert row["room_id"] == rid
        assert row["booked_by"] == "staff01"
        # Schema default keeps confirmed bookings in conflict checks.
        assert row["booking_status"] == "confirmed"
        assert row["expected_attendees"] == 40

    def test_overlapping_booking_raises_and_is_not_persisted(self, facilities_db):
        bid = _building()
        rid = _room(bid)
        RoomBookingManager.book_room(
            room_id=rid, booked_by="s1", booking_type="lecture",
            start_datetime="2026-09-01T10:00", end_datetime="2026-09-01T12:00",
        )
        with pytest.raises(Exception, match="already booked"):
            RoomBookingManager.book_room(
                room_id=rid, booked_by="s2", booking_type="seminar",
                start_datetime="2026-09-01T11:00", end_datetime="2026-09-01T13:00",
            )

        with get_connection() as conn:
            n = conn.execute(
                "SELECT COUNT(*) FROM room_bookings WHERE room_id = ?", (rid,),
            ).fetchone()[0]
        assert n == 1

    def test_non_overlapping_booking_succeeds(self, facilities_db):
        bid = _building()
        rid = _room(bid)
        first = RoomBookingManager.book_room(
            room_id=rid, booked_by="s1", booking_type="lecture",
            start_datetime="2026-09-01T10:00", end_datetime="2026-09-01T12:00",
        )
        # Starts exactly when the first ends -> no overlap.
        second = RoomBookingManager.book_room(
            room_id=rid, booked_by="s2", booking_type="seminar",
            start_datetime="2026-09-01T12:00", end_datetime="2026-09-01T14:00",
        )
        assert first != second
        assert isinstance(second, int) and second > 0


class TestMaintenanceAndWorkOrders:
    def test_submit_request_marks_room_location_type(self, facilities_db):
        bid = _building()
        rid = _room(bid)
        request_id = MaintenanceRequestManager.submit_request(
            request_type="plumbing", priority="high",
            description="Leaking tap", reported_by="staff01",
            building_id=bid, room_id=rid,
        )
        assert isinstance(request_id, int) and request_id > 0

        with get_connection() as conn:
            row = conn.execute(
                "SELECT location_type, building_id, room_id, status "
                "FROM maintenance_requests WHERE request_id = ?", (request_id,),
            ).fetchone()
        assert row["location_type"] == "room"
        assert row["room_id"] == rid
        assert row["status"] == "open"

    def test_submit_request_building_only_sets_building_location(self, facilities_db):
        bid = _building()
        request_id = MaintenanceRequestManager.submit_request(
            request_type="electrical", priority="medium",
            description="Flickering lights", reported_by="staff02",
            building_id=bid,
        )
        with get_connection() as conn:
            row = conn.execute(
                "SELECT location_type, room_id FROM maintenance_requests "
                "WHERE request_id = ?", (request_id,),
            ).fetchone()
        assert row["location_type"] == "building"
        assert row["room_id"] is None

    def test_create_work_order_links_to_request(self, facilities_db):
        bid = _building()
        request_id = MaintenanceRequestManager.submit_request(
            request_type="hvac", priority="low",
            description="AC servicing", reported_by="staff03",
            building_id=bid,
        )
        wo_id = WorkOrderManager.create_work_order(
            request_id=request_id, work_order_type="repair",
            description="Replace filter", assigned_technician="tech7",
        )
        assert isinstance(wo_id, int) and wo_id > 0

        with get_connection() as conn:
            row = conn.execute(
                "SELECT request_id, assigned_technician, status "
                "FROM work_orders WHERE work_order_id = ?", (wo_id,),
            ).fetchone()
        assert row["request_id"] == request_id
        assert row["assigned_technician"] == "tech7"
        assert row["status"] == "pending"


class TestAssetManager:
    def test_register_asset_persists(self, facilities_db):
        bid = _building()
        rid = _room(bid)
        asset_id = AssetManager.register_asset(
            asset_name="Projector", asset_type="AV", asset_tag="AV-001",
            building_id=bid, room_id=rid, purchase_cost=1200.0,
        )
        assert isinstance(asset_id, int) and asset_id > 0

        with get_connection() as conn:
            row = conn.execute(
                "SELECT asset_name, asset_tag, purchase_cost, status "
                "FROM facility_assets WHERE asset_id = ?", (asset_id,),
            ).fetchone()
        assert row["asset_name"] == "Projector"
        assert row["asset_tag"] == "AV-001"
        assert row["purchase_cost"] == pytest.approx(1200.0)
        assert row["status"] == "active"


class TestCleaningScheduleManager:
    def test_schedule_and_list_due(self, facilities_db):
        bid = _building()
        # Past due date so it shows up against today's default cutoff.
        CleaningScheduleManager.schedule(
            building_id=bid, frequency="daily",
            next_due="2020-01-01", assigned_to="cleaner1",
        )
        # Future due date should be excluded by the default (today) cutoff.
        CleaningScheduleManager.schedule(
            building_id=bid, frequency="weekly", next_due="2999-01-01",
        )
        due = CleaningScheduleManager.list_due()
        assert len(due) == 1
        assert due[0]["assigned_to"] == "cleaner1"
        assert due[0]["next_due"] == "2020-01-01"

    def test_completed_schedule_excluded_from_due(self, facilities_db):
        bid = _building()
        CleaningScheduleManager.schedule(
            building_id=bid, frequency="daily",
            next_due="2020-01-01", status="complete",
        )
        assert CleaningScheduleManager.list_due() == []


class TestOccupancyManager:
    def test_record_derives_utilization_pct(self, facilities_db):
        bid = _building()
        rec_id = OccupancyManager.record(
            building_id=bid, occupant_count=25, capacity=50,
            timestamp="2026-05-01T09:00",
        )
        assert isinstance(rec_id, int) and rec_id > 0

        with get_connection() as conn:
            row = conn.execute(
                "SELECT occupant_count, capacity, utilization_pct "
                "FROM bm_occupancy_records WHERE id = ?", (rec_id,),
            ).fetchone()
        assert row["occupant_count"] == 25
        assert row["utilization_pct"] == pytest.approx(50.0)

    def test_record_negative_counts_raises(self, facilities_db):
        bid = _building()
        with pytest.raises(ValueError, match="non-negative"):
            OccupancyManager.record(building_id=bid, occupant_count=-1, capacity=10)

    def test_utilisation_summary_aggregates_per_building(self, facilities_db):
        bid = _building(building_code="OCC", building_name="Occ Hall")
        OccupancyManager.record(building_id=bid, occupant_count=10, capacity=100)  # 10%
        OccupancyManager.record(building_id=bid, occupant_count=90, capacity=100)  # 90%

        summary = OccupancyManager.utilisation_summary()
        rows = [r for r in summary if r["building_code"] == "OCC"]
        assert len(rows) == 1
        row = rows[0]
        assert row["sample_count"] == 2
        assert row["avg_pct"] == pytest.approx(50.0)
        assert row["peak_pct"] == pytest.approx(90.0)
