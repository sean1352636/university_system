"""Tests for EquipmentManager: categories, equipment CRUD, bookings with
conflict detection, and maintenance lifecycle."""

import sqlite3

import pytest

from education_system.systems.university.domains.staff.domain.staff_hr.services.managers.equipment_manager import (
    EquipmentManager as M,
)


ADMIN = {'username': 'admin', 'role': 'admin'}
MANAGER = {'username': 'mgr', 'role': 'staff'}
OTHER = {'username': 'other', 'role': 'staff'}
BOOKER = {'username': 'U1', 'role': 'staff'}


@pytest.fixture
def people(hr_db):
    """U1 reports to mgr; 'other' is an unrelated member of staff."""
    conn = sqlite3.connect(hr_db)
    conn.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT, "
                 "role TEXT, first_name TEXT, last_name TEXT)")
    for name, role in (('admin', 'admin'), ('mgr', 'staff'), ('other', 'staff'), ('U1', 'staff')):
        conn.execute("INSERT INTO users (username, role) VALUES (?, ?)", (name, role))
    conn.execute("INSERT INTO staff_profiles (user_id, manager_id) VALUES ('U1', 'mgr')")
    conn.commit()
    conn.close()
    return hr_db


class TestCategoriesAndEquipment:
    def test_create_category_and_list(self, hr_db):
        cid = M.create_category('Microscopes', description='Optical')
        assert cid > 0
        # The schema seeds a few standard categories alongside this one.
        cats = M.get_categories()
        assert 'Microscopes' in [c['name'] for c in cats]

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

    def test_requires_approval_pending_then_approve(self, people):
        eid = M.add_equipment('Laser', requires_approval=True)
        bid = M.create_booking(eid, 'U1', '2026-06-02', '09:00', '10:00')
        assert M.get_booking(bid)['status'] == 'pending'
        M.approve_booking(bid, actor=ADMIN)
        booking = M.get_booking(bid)
        assert booking['status'] == 'approved'
        assert booking['approved_by'] == 'admin'


class TestBookingApprovalChecks:
    def _pending(self):
        eid = M.add_equipment('Laser', requires_approval=True)
        return M.create_booking(eid, 'U1', '2026-06-02', '09:00', '10:00')

    def test_line_manager_can_approve(self, people):
        bid = self._pending()
        M.approve_booking(bid, actor=MANAGER)
        assert M.get_booking(bid)['approved_by'] == 'mgr'

    def test_booker_cannot_approve_own_booking(self, people):
        bid = self._pending()
        with pytest.raises(PermissionError):
            M.approve_booking(bid, actor=BOOKER)
        assert M.get_booking(bid)['status'] == 'pending'

    def test_unrelated_staff_cannot_reject(self, people):
        bid = self._pending()
        with pytest.raises(PermissionError):
            M.reject_booking(bid, notes='no', actor=OTHER)
        assert M.get_booking(bid)['status'] == 'pending'

    def test_nobody_named_is_refused(self, people):
        bid = self._pending()
        with pytest.raises(PermissionError):
            M.approve_booking(bid)

    def test_only_pending_bookings_are_decided(self, people):
        bid = self._pending()
        M.reject_booking(bid, notes='clash', actor=MANAGER)
        with pytest.raises(ValueError):
            M.approve_booking(bid, actor=ADMIN)

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
