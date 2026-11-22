"""Who may decide grant expenses / budget transfers and asset requests.

Grant items: the grant's principal investigator or the research office,
never the person who submitted them; transfers are the research office's
alone. Asset requests: the requester's line manager or HR, never the
requester. Only items still awaiting a decision can be decided.
"""

import sqlite3

import pytest

from education_system.systems.university.domains.staff.domain.staff_hr.services.managers.asset_manager import (
    AssetManager,
)
from education_system.systems.university.domains.staff.domain.staff_hr.services.managers.grant_budget_manager import (
    GrantBudgetManager as G,
)

ADMIN = {'username': 'admin', 'role': 'admin'}
PI = {'username': 'pi', 'role': 'staff'}
OFFICE = {'username': 'office', 'role': 'staff'}
RESEARCHER = {'username': 'res', 'role': 'staff'}
MANAGER = {'username': 'mgr', 'role': 'staff'}
OTHER = {'username': 'other', 'role': 'staff'}


@pytest.fixture
def db(hr_db):
    """A grant (#1, PI 'pi') with two allocations; 'office' holds the
    research office role; 'res' reports to 'mgr'."""
    conn = sqlite3.connect(hr_db)
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT, role TEXT,
                                          first_name TEXT, last_name TEXT);
        CREATE TABLE IF NOT EXISTS grant_applications (
            application_id INTEGER PRIMARY KEY, principal_investigator_id TEXT,
            title TEXT, status TEXT);
        CREATE TABLE IF NOT EXISTS research_office_roles (
            username TEXT, role TEXT, scope TEXT DEFAULT '', granted_by TEXT, granted_at TEXT);
    ''')
    for name, role in (('admin', 'admin'), ('pi', 'staff'), ('office', 'staff'),
                       ('res', 'staff'), ('mgr', 'staff'), ('other', 'staff')):
        conn.execute("INSERT INTO users (username, role) VALUES (?, ?)", (name, role))
    conn.execute("INSERT INTO staff_profiles (user_id, manager_id) VALUES ('res', 'mgr')")
    conn.execute("INSERT INTO grant_applications VALUES (1, 'pi', 'Grant', 'active')")
    conn.execute("INSERT INTO research_office_roles (username, role) VALUES "
                 "('office', 'research_office')")
    conn.commit()
    conn.close()
    cat = G.create_category('Approval test kit', 'Kit')
    a1 = G.create_allocation(1, cat, 1000.0)
    a2 = G.create_allocation(1, cat, 500.0)
    return {'path': hr_db, 'cat': cat, 'a1': a1, 'a2': a2}


def _expense(db, by='res'):
    return G.submit_expense(1, db['a1'], db['cat'], 'Microscope', 100.0, '2026-10-01',
                            'Vendor', None, 'INV1', by)


def _transfer(db, by='pi'):
    return G.request_transfer(1, db['a1'], db['a2'], 50.0, 'Rebalance', by)


class TestGrantExpenses:
    def test_pi_approves(self, db):
        eid = _expense(db)
        G.approve_expense(eid, actor=PI)
        e = G.get_expense(eid)
        assert e['status'] == 'approved' and e['approved_by'] == 'pi'
        assert G.get_allocation(db['a1'])['spent_amount'] == 100.0

    def test_research_office_rejects(self, db):
        eid = _expense(db)
        G.reject_expense(eid, actor=OFFICE)
        assert G.get_expense(eid)['status'] == 'rejected'

    def test_submitter_cannot_approve_own_expense(self, db):
        eid = _expense(db, by='pi')
        with pytest.raises(PermissionError):
            G.approve_expense(eid, actor=PI)
        assert G.get_expense(eid)['status'] == 'submitted'

    def test_unrelated_staff_refused(self, db):
        eid = _expense(db)
        with pytest.raises(PermissionError):
            G.approve_expense(eid, actor=OTHER)
        with pytest.raises(PermissionError):
            G.approve_expense(eid)          # nobody named

    def test_decided_expense_cannot_be_decided_again(self, db):
        eid = _expense(db)
        G.approve_expense(eid, actor=PI)
        with pytest.raises(ValueError):
            G.reject_expense(eid, actor=OFFICE)
        assert G.get_allocation(db['a1'])['spent_amount'] == 100.0


class TestGrantTransfers:
    def test_research_office_approves(self, db):
        tid = _transfer(db)
        G.approve_transfer(tid, actor=OFFICE)
        assert G.get_allocation(db['a1'])['allocated_amount'] == 950.0
        assert G.get_allocation(db['a2'])['allocated_amount'] == 550.0

    def test_pi_cannot_approve_transfers(self, db):
        tid = _transfer(db, by='res')
        with pytest.raises(PermissionError):
            G.approve_transfer(tid, actor=PI)

    def test_requester_cannot_decide_own_transfer(self, db):
        tid = _transfer(db, by='office')
        with pytest.raises(PermissionError):
            G.reject_transfer(tid, actor=OFFICE)

    def test_admin_decides_once(self, db):
        tid = _transfer(db)
        G.reject_transfer(tid, actor=ADMIN)
        with pytest.raises(ValueError):
            G.approve_transfer(tid, actor=ADMIN)
        assert G.get_allocation(db['a1'])['allocated_amount'] == 1000.0

    def test_can_decide(self, db):
        assert G.can_decide(PI) and G.can_decide(OFFICE) and G.can_decide(ADMIN)
        assert not G.can_decide(OTHER)
        assert not G.can_decide(None)


class TestAssetRequests:
    def _request(self, db, by='res'):
        conn = sqlite3.connect(db['path'])
        cur = conn.execute("INSERT INTO asset_requests (requested_by, item_name, category_id, "
                           "status) VALUES (?, 'Laptop', 1, 'pending')", (by,))
        conn.commit()
        rid = cur.lastrowid
        conn.close()
        return rid

    def _row(self, db, rid):
        conn = sqlite3.connect(db['path'])
        conn.row_factory = sqlite3.Row
        row = dict(conn.execute("SELECT * FROM asset_requests WHERE request_id = ?",
                                (rid,)).fetchone())
        conn.close()
        return row

    def test_line_manager_approves(self, db):
        rid = self._request(db)
        assert AssetManager.approve_request(rid, approved_amount=900.0, actor=MANAGER) is True
        row = self._row(db, rid)
        assert row['status'] == 'approved' and row['approved_by'] == 'mgr'

    def test_requester_cannot_approve_own(self, db):
        rid = self._request(db)
        with pytest.raises(PermissionError):
            AssetManager.approve_request(rid, actor=RESEARCHER)
        assert self._row(db, rid)['status'] == 'pending'

    def test_unrelated_staff_cannot_reject(self, db):
        rid = self._request(db)
        with pytest.raises(PermissionError):
            AssetManager.reject_request(rid, reason='no', actor=OTHER)

    def test_hr_rejects_and_not_pending_returns_false(self, db):
        rid = self._request(db)
        assert AssetManager.reject_request(rid, reason='Budget', actor=ADMIN) is True
        assert self._row(db, rid)['rejection_reason'] == 'Budget'
        assert AssetManager.approve_request(rid, actor=ADMIN) is False
