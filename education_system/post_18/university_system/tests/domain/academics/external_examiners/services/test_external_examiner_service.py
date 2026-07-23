"""Tests for the ExternalExaminerService (isolated DB)."""

import pytest

from education_system.post_18.university_system.modules.domain.academics.external_examiners.services.external_examiner_service import (
    ExternalExaminerService,
)


@pytest.fixture()
def service():
    return ExternalExaminerService()


class TestExaminers:
    def test_add_and_get(self, service):
        eid = service.add_examiner("Dr Smith", email="s@uni.edu",
                                   institution="Other Uni",
                                   specialisation="Physics")
        ex = service.get_examiner(eid)
        assert ex["name"] == "Dr Smith"
        assert ex["status"] == "active"

    def test_add_examiner_from_dict(self, service):
        eid = service.add_examiner({"name": "Dr Jones", "expertise_area": "Chem"})
        ex = service.get_examiner(eid)
        assert ex["name"] == "Dr Jones"
        assert ex["specialisation"] == "Chem"

    def test_list_examiners(self, service):
        service.add_examiner("A")
        service.add_examiner("B")
        assert len(service.list_examiners()) == 2

    def test_update_examiner(self, service):
        eid = service.add_examiner("A")
        assert service.update_examiner(eid, status="inactive") is True
        assert service.get_examiner(eid)["status"] == "inactive"
        assert len(service.list_examiners(status="active")) == 0


class TestVisits:
    def test_schedule_and_get_visit(self, service):
        eid = service.add_examiner("Dr Smith")
        vid = service.schedule_visit(eid, "2026-06-01", department="CS",
                                     purpose="Annual review")
        visit = service.get_visit(vid)
        assert visit["department"] == "CS"
        assert visit["examiner_id"] == eid

    def test_record_findings(self, service):
        eid = service.add_examiner("Dr Smith")
        vid = service.schedule_visit(eid, "2026-06-01", department="CS")
        assert service.record_findings(vid, findings="Good",
                                       recommendations="Keep it up",
                                       overall_rating="Excellent") is True
        visit = service.get_visit(vid)
        assert visit["findings"] == "Good"
        assert visit["overall_rating"] == "Excellent"

    def test_list_visits_by_examiner(self, service):
        e1 = service.add_examiner("A")
        e2 = service.add_examiner("B")
        service.schedule_visit(e1, "2026-06-01")
        service.schedule_visit(e2, "2026-06-02")
        assert len(service.list_visits(examiner_id=e1)) == 1
        assert len(service.list_visits()) == 2

    def test_department_summary(self, service):
        eid = service.add_examiner("A")
        service.schedule_visit(eid, "2026-06-01", department="CS")
        service.schedule_visit(eid, "2026-06-02", department="CS")
        summary = service.get_department_summary("CS")
        assert summary[0]["visit_count"] == 2


class TestActions:
    def test_add_action_and_list(self, service):
        eid = service.add_examiner("A")
        vid = service.schedule_visit(eid, "2026-06-01")
        aid = service.add_action_item(vid, action_description="Fix syllabus",
                                      responsible_person="Dept Head",
                                      deadline="2026-07-01")
        actions = service.get_actions_by_visit(vid)
        assert len(actions) == 1
        assert actions[0]["action_description"] == "Fix syllabus"
        assert actions[0]["status"] == "pending"

    def test_update_action_status(self, service):
        eid = service.add_examiner("A")
        vid = service.schedule_visit(eid, "2026-06-01")
        aid = service.add_action_item(vid, action_description="Task")
        assert service.update_action_status(aid, "completed") is True
        actions = service.get_actions_by_visit(vid)
        assert actions[0]["status"] == "completed"
        assert actions[0]["completed_at"] is not None

    def test_overdue_actions(self, service):
        eid = service.add_examiner("A")
        vid = service.schedule_visit(eid, "2026-06-01")
        service.add_action_item(vid, action_description="Old", deadline="2000-01-01")
        overdue = service.get_overdue_actions()
        assert len(overdue) == 1

    def test_examiner_history(self, service):
        eid = service.add_examiner("Dr Smith")
        service.schedule_visit(eid, "2026-06-01")
        hist = service.get_examiner_history(eid)
        assert hist["total_visits"] == 1
        assert hist["examiner"]["name"] == "Dr Smith"
