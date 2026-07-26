"""Tests for EquipmentManager: categories, equipment CRUD, bookings with
conflict detection, and maintenance lifecycle."""

import pytest

from education_system.systems.university.domain.staff.staff_hr.services.managers.equipment_manager import (
    EquipmentManager as M,
)


class TestCategoriesAndEquipment:
    def test_create_category_and_list(self, hr_db):
        cid = M.create_category('Microscopes', description='Optical')
        assert cid > 0
        cats = M.get_categories()
        assert len(cats) == 1
        assert cats[0]['name'] == 'Microscopes'

    def test_add_and_get_equipment(self, hr_db):
        eid = M.add_equipment('Centrifuge', location='Lab A')
        assert eid > 0
        eq = M.get_equipment(eid)
        assert eq['name'] == 'Centrifuge'
        assert eq['status'] == 'available'

    def test_get_equipment_missing(self, hr_db):
        assert M.get_equipment(999) is None

    def test_filter_equipment(self, hr_db):
        M.add_equipment('A', location='Lab A')
        M.add_equipment('B', location='Lab B')
        assert len(M.get_all_equipment(location='Lab A')) == 1
        assert len(M.get_all_equipment()) == 2


class TestBookings:
    def test_create_booking_auto_approved(self, hr_db):
        eid = M.add_equipment('Scope')  # requires_approval defaults False
        bid = M.create_booking(eid, 'U1', '2026-06-01', '09:00', '11:00',
                               purpose='Experiment')
        assert bid > 0
        assert M.get_booking(bid)['status'] == 'approved'

    def test_conflicting_booking_raises(self, hr_db):
        eid = M.add_equipment('Scope')
        M.create_booking(eid, 'U1', '2026-06-01', '09:00', '11:00')
        with pytest.raises(ValueError):
            M.create_booking(eid, 'U2', '2026-06-01', '10:00', '12:00')

    def test_requires_approval_pending_then_approve(self, hr_db):
        eid = M.add_equipment('Laser', requires_approval=True)
        bid = M.create_booking(eid, 'U1', '2026-06-02', '09:00', '10:00')
        assert M.get_booking(bid)['status'] == 'pending'
        M.approve_booking(bid, 'admin')
        assert M.get_booking(bid)['status'] == 'approved'

    def test_cancel_booking(self, hr_db):
        eid = M.add_equipment('Scope')
        bid = M.create_booking(eid, 'U1', '2026-06-03', '09:00', '10:00')
        M.cancel_booking(bid)
        assert M.get_booking(bid)['status'] == 'cancelled'
        # A cancelled slot frees the time for a new booking.
        bid2 = M.create_booking(eid, 'U2', '2026-06-03', '09:00', '10:00')
        assert bid2 > 0


class TestMaintenance:
    def test_schedule_and_complete(self, hr_db):
        eid = M.add_equipment('Scope')
        mid = M.schedule_maintenance(eid, maintenance_type='routine')
        assert mid > 0
        assert M.get_equipment(eid)['status'] == 'maintenance'
        M.complete_maintenance(mid, 'tech1')
        assert M.get_equipment(eid)['status'] == 'available'
        hist = M.get_maintenance_history(eid)
        assert hist[0]['status'] == 'completed'

    def test_complete_unknown_raises(self, hr_db):
        with pytest.raises(ValueError):
            M.complete_maintenance(999, 'tech1')
