"""Tests for TutorialService."""

import pytest


class TestTutorialService:
    @pytest.fixture
    def service(self, db_path):
        from education_system.college_system.modules.domain.tutorial.services.tutorial_service import TutorialService
        return TutorialService(db_path)

    def test_create_assignment(self, service):
        assignment = service.create_assignment(
            student_id=1, tutor_id=1,
            tutor_group="12A",
        )
        assert assignment is not None

    def test_list_assignments(self, service):
        service.create_assignment(student_id=1, tutor_id=1)
        assignments = service.list_assignments(tutor_id=1)
        assert len(assignments) >= 1

    def test_get_assignment(self, service):
        assignment = service.create_assignment(student_id=1, tutor_id=1)
        aid = assignment if isinstance(assignment, int) else assignment.get("id", assignment)
        found = service.get_assignment(aid)
        assert found is not None

    def test_update_assignment(self, service):
        assignment = service.create_assignment(student_id=1, tutor_id=1)
        aid = assignment if isinstance(assignment, int) else assignment.get("id", assignment)
        updated = service.update_assignment(aid, tutor_group="13B")
        assert updated is not None

    def test_delete_assignment(self, service):
        assignment = service.create_assignment(student_id=1, tutor_id=1)
        aid = assignment if isinstance(assignment, int) else assignment.get("id", assignment)
        result = service.delete_assignment(aid)
        assert result is True or result is None

    def test_create_session(self, service):
        session = service.create_session(
            tutor_id=1, session_date="2026-04-15",
            tutor_group="12A", topic="UCAS preparation",
        )
        assert session is not None

    def test_list_sessions(self, service):
        service.create_session(tutor_id=1, session_date="2026-04-15")
        sessions = service.list_sessions(tutor_id=1)
        assert len(sessions) >= 1

    def test_complete_session(self, service):
        session = service.create_session(tutor_id=1, session_date="2026-04-15")
        sid = session if isinstance(session, int) else session.get("id", session)
        result = service.complete_session(sid, notes="Covered UCAS deadlines")
        assert result is not None

    def test_create_record(self, service):
        record = service.create_record(
            student_id=1, tutor_id=1,
            meeting_date="2026-04-16",
            meeting_type="1to1",
        )
        assert record is not None

    def test_list_records(self, service):
        service.create_record(1, 1, "2026-04-16")
        records = service.list_records(student_id=1)
        assert len(records) >= 1

    def test_get_follow_ups(self, service):
        result = service.get_follow_ups()
        assert isinstance(result, list)

    def test_get_stats(self, service):
        stats = service.get_stats()
        assert stats is not None
