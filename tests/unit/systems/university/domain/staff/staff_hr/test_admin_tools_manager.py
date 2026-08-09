"""Tests for AdminToolsManager: document approvals, interdepartmental
requests, access cards, key assignments, and visitor management."""

from datetime import datetime

from education_system.systems.university.domain.staff.staff_hr.services.managers.admin_tools_manager import (
    AdminToolsManager as M,
)


class TestDocumentApprovals:
    def test_submit_and_pending(self, hr_db):
        aid = M.submit_document('bob', 'policy', 'New Policy',
                                current_approver='alice', total_steps=1)
        assert aid > 0
        pending = M.get_pending_approvals('alice')
        assert len(pending) == 1
        assert pending[0]['document_title'] == 'New Policy'

    def test_approve_final_step(self, hr_db):
        aid = M.submit_document('bob', 'policy', 'P', current_approver='alice',
                                total_steps=1)
        assert M.approve_document(aid, 'alice', comments='ok') is True
        # Approved docs no longer appear in the approver's pending queue.
        assert M.get_pending_approvals('alice') == []
        hist = M.get_approval_history(aid)
        assert len(hist) == 1
        assert hist[0]['action'] == 'approved'

    def test_approve_unknown_returns_false(self, hr_db):
        assert M.approve_document(999, 'alice') is False

    def test_reject_document(self, hr_db):
        aid = M.submit_document('bob', 'policy', 'P', current_approver='alice',
                                total_steps=1)
        assert M.reject_document(aid, 'alice', 'incomplete') is True
        hist = M.get_approval_history(aid)
        assert hist[0]['action'] == 'rejected'


class TestInterdeptRequests:
    def test_create_assign_complete(self, hr_db):
        rid = M.create_request('bob', 'supplies', 'Need chairs', 'Facilities',
                               from_department='IT', priority='high')
        assert rid > 0
        assert M.assign_request(rid, 'carol', 'Carol') is True
        rows = M.get_interdept_requests(status='in_progress')
        assert len(rows) == 1
        assert rows[0]['assigned_to'] == 'carol'

        assert M.complete_request(rid, 'Done') is True
        assert M.get_interdept_requests(status='completed')[0]['response'] == 'Done'

    def test_department_filter(self, hr_db):
        M.create_request('b', 't', 'title', 'Facilities', from_department='IT')
        assert len(M.get_interdept_requests(department='IT')) == 1
        assert len(M.get_interdept_requests(department='HR')) == 0


class TestAccessCards:
    def test_issue_and_deactivate(self, hr_db):
        cid = M.issue_access_card('CARD001', 'bob', 'admin', access_level='2')
        assert cid > 0
        cards = M.get_access_cards(user_id='bob')
        assert len(cards) == 1
        assert M.deactivate_access_card(cid, 'lost') is True
        assert len(M.get_access_cards(status='inactive')) == 1


class TestKeysAndVisitors:
    def test_assign_and_return_key(self, hr_db):
        kid = M.assign_key('K1', 'bob', 'admin', key_type='office')
        assert kid > 0
        assert M.get_key_assignments(user_id='bob')[0]['status'] == 'assigned'
        assert M.return_key(kid) is True
        assert M.get_key_assignments(status='returned')[0]['assignment_id'] == kid

    def test_visitor_checkin_checkout(self, hr_db):
        today = datetime.now().strftime('%Y-%m-%d')
        vid = M.register_visitor('bob', 'Jane Guest', today,
                                 scheduled_time='10:00')
        assert vid > 0
        assert M.check_in_visitor(vid, badge_number='B9') is True
        assert M.get_visitor_registrations(status='checked_in')[0]['badge_number'] == 'B9'
        assert M.check_out_visitor(vid) is True
        assert M.get_todays_visitors('bob')[0]['status'] == 'checked_out'
