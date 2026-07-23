"""Tests for AcademicStaffManager service (staff-HR academic features).

Covers teaching portfolios, research profiles, student supervisions,
external examiners, and peer observations against a fresh in-file SQLite
DB with the full Staff-HR schema installed (see conftest.hr_db).
"""

from education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.academic_staff_manager import (
    AcademicStaffManager as M,
)


class TestTeachingPortfolio:
    def test_update_creates_then_get_returns_it(self, hr_db):
        assert M.update_teaching_portfolio('U1', teaching_philosophy='Active learning') is True
        pf = M.get_teaching_portfolio('U1')
        assert pf is not None
        assert pf['user_id'] == 'U1'
        assert pf['teaching_philosophy'] == 'Active learning'

    def test_update_existing_portfolio(self, hr_db):
        M.update_teaching_portfolio('U1', teaching_philosophy='First')
        M.update_teaching_portfolio('U1', teaching_philosophy='Second')
        pf = M.get_teaching_portfolio('U1')
        assert pf['teaching_philosophy'] == 'Second'

    def test_get_missing_returns_none(self, hr_db):
        assert M.get_teaching_portfolio('nobody') is None


class TestResearchProfile:
    def test_update_and_get(self, hr_db):
        assert M.update_research_profile('R1', research_interests='NLP') is True
        rp = M.get_research_profile('R1')
        assert rp['research_interests'] == 'NLP'


class TestSupervisions:
    def test_add_and_get(self, hr_db):
        sid = M.add_supervision('SUP1', 'STU1', 'phd', student_name='Bob',
                                thesis_title='Deep Nets')
        assert isinstance(sid, int) and sid > 0
        rows = M.get_supervisions('SUP1')
        assert len(rows) == 1
        assert rows[0]['student_name'] == 'Bob'
        assert rows[0]['supervision_role'] == 'primary'

    def test_status_filter(self, hr_db):
        M.add_supervision('SUP1', 'STU1', 'phd', student_name='A')
        sid2 = M.add_supervision('SUP1', 'STU2', 'phd', student_name='B')
        M.update_supervision(sid2, status='completed')
        assert len(M.get_supervisions('SUP1', status='completed')) == 1
        assert len(M.get_supervisions('SUP1')) == 2

    def test_get_empty(self, hr_db):
        assert M.get_supervisions('SUPX') == []

    def test_update_no_data_returns_false(self, hr_db):
        assert M.update_supervision(1) is False


class TestExternalExaminers:
    def test_add_and_active_only(self, hr_db):
        M.add_external_examiner('Dr Smith', institution='Oxford')
        rows = M.get_external_examiners(active_only=False)
        assert len(rows) == 1
        assert rows[0]['name'] == 'Dr Smith'
        # Default status is not 'active', so active_only filter returns none.
        assert M.get_external_examiners(active_only=True) == []


class TestPeerObservations:
    def test_create_submit_acknowledge_lifecycle(self, hr_db):
        oid = M.create_observation('OB1', 'OB2', '2026-05-01',
                                   observer_name='Ann', observee_name='Ben')
        assert oid > 0
        obs = M.get_peer_observations('OB1', role='observer')
        assert len(obs) == 1
        assert obs[0]['status'] == 'draft'

        assert M.submit_observation(oid) is True
        assert M.get_peer_observations('OB2', role='observee')[0]['status'] == 'submitted'

        assert M.acknowledge_observation(oid) is True
        both = M.get_peer_observations('OB1', role='both')
        assert both[0]['status'] == 'acknowledged'
        assert both[0]['acknowledged_date'] is not None
