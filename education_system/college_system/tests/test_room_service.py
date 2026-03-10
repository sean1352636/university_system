"""Tests for RoomService."""

import pytest

from education_system.college_system.modules.domain.timetable.services.room_service import RoomService
from education_system.college_system.core.exceptions import RoomError


class TestRoomService:
    def test_create_room(self, db_path):
        svc = RoomService(db_path)
        room = svc.create_room("A101", building="Main", room_type="classroom", capacity=30)
        assert room["room_code"] == "A101"
        assert room["capacity"] == 30
        assert room["status"] == "active"

    def test_list_rooms(self, db_path):
        svc = RoomService(db_path)
        svc.create_room("B201", room_type="lab")
        svc.create_room("B202", room_type="classroom")
        rooms = svc.list_rooms()
        assert len(rooms) >= 2

    def test_update_room(self, db_path):
        svc = RoomService(db_path)
        room = svc.create_room("C101")
        updated = svc.update_room(room["id"], capacity=40, has_projector=1)
        assert updated["capacity"] == 40

    def test_set_room_status(self, db_path):
        svc = RoomService(db_path)
        room = svc.create_room("D101")
        updated = svc.set_room_status(room["id"], "maintenance")
        assert updated["status"] == "maintenance"

    def test_add_and_list_resources(self, db_path):
        svc = RoomService(db_path)
        room = svc.create_room("E101")
        res = svc.add_resource(room["id"], "Projector", "equipment")
        assert res["resource_name"] == "Projector"

        resources = svc.list_resources(room["id"])
        assert len(resources) == 1

    def test_remove_resource(self, db_path):
        svc = RoomService(db_path)
        room = svc.create_room("F101")
        res = svc.add_resource(room["id"], "Whiteboard")
        svc.remove_resource(res["id"])

        resources = svc.list_resources(room["id"])
        assert len(resources) == 0

    def test_find_available_rooms(self, db_path):
        svc = RoomService(db_path)
        svc.create_room("G101", capacity=30)
        rooms = svc.find_available_rooms("Mon", "09:00", "10:00")
        assert len(rooms) >= 1

    def test_room_utilization(self, db_path):
        svc = RoomService(db_path)
        svc.create_room("H101")
        util = svc.get_room_utilization()
        assert len(util) >= 1
        assert "utilization_pct" in util[0]
