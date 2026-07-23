"""Tests for EmployeeManager: staff profiles, documents, workload,
schedules, and directory helpers."""

from education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.employee_manager import (
    EmployeeManager as M,
)


class TestProfiles:
    def test_create_and_get(self, hr_db):
        pid = M.create_profile('U1', department='CS', job_title='Lecturer',
                               employee_id='E100')
        assert pid > 0
        prof = M.get_profile('U1')
        assert prof['department'] == 'CS'
        assert prof['employment_type'] == 'full-time'

    def test_get_missing_returns_none(self, hr_db):
        assert M.get_profile('none') is None

    def test_update_profile(self, hr_db):
        M.create_profile('U1', department='CS')
        assert M.update_profile('U1', department='Maths') is True
        assert M.get_profile('U1')['department'] == 'Maths'

    def test_update_no_data_false(self, hr_db):
        assert M.update_profile('U1') is False

    def test_emergency_contact(self, hr_db):
        M.create_profile('U1')
        assert M.update_emergency_contact('U1', 'Kin', '555', 'parent') is True
        prof = M.get_profile('U1')
        assert prof['emergency_contact_name'] == 'Kin'
        assert prof['emergency_contact_relationship'] == 'parent'


class TestDocuments:
    def test_add_get_delete(self, hr_db):
        did = M.add_document('U1', 'contract', 'Contract.pdf', status='active')
        assert did > 0
        docs = M.get_documents('U1')
        assert len(docs) == 1
        assert docs[0]['document_name'] == 'Contract.pdf'
        # Type filter
        assert len(M.get_documents('U1', doc_type='contract')) == 1
        assert len(M.get_documents('U1', doc_type='visa')) == 0
        assert M.delete_document(did) is True
        assert M.get_documents('U1') == []


class TestWorkloadAndSchedule:
    def test_set_workload_insert_then_update(self, hr_db):
        wid = M.set_workload('U1', '2025/26', 'S1', teaching_hours=10)
        assert wid > 0
        # Same year/semester updates in place, returning the same id.
        wid2 = M.set_workload('U1', '2025/26', 'S1', teaching_hours=20)
        assert wid2 == wid
        rows = M.get_workload('U1', academic_year='2025/26', semester='S1')
        assert len(rows) == 1
        assert rows[0]['teaching_hours'] == 20

    def test_schedule_add_and_delete(self, hr_db):
        sid = M.add_schedule('U1', 1, '09:00', '10:00', location='Rm1')
        assert sid > 0
        assert len(M.get_schedules('U1')) == 1
        assert M.delete_schedule(sid) is True
        assert M.get_schedules('U1') == []


class TestDirectory:
    def test_departments_and_count(self, hr_db):
        M.create_profile('U1', department='CS')
        M.create_profile('U2', department='Maths')
        assert M.get_departments() == ['CS', 'Maths']
        assert M.get_directory_count() == 2
        assert M.get_directory_count(department='CS') == 1
