"""Tests for the CurriculumSpecificationService (isolated DB)."""

import pytest

from education_system.systems.university.domain.academics.curriculum_specification.services.curriculum_specification_service import (
    CurriculumSpecificationService,
)


@pytest.fixture()
def service():
    return CurriculumSpecificationService()


class TestProgrammes:
    def test_create_and_get(self, service):
        pid = service.create_programme(code="CS-BSC", title="BSc Computer Science",
                                       award="BSc", level="6", credits=360)
        prog = service.get_programme(pid)
        assert prog["code"] == "CS-BSC"
        assert prog["status"] == "draft"

    def test_create_requires_code_and_title(self, service):
        with pytest.raises(ValueError):
            service.create_programme(title="No code")

    def test_create_invalid_status(self, service):
        with pytest.raises(ValueError):
            service.create_programme(code="X", title="Y", status="banana")

    def test_approve(self, service):
        pid = service.create_programme(code="X", title="Y")
        assert service.approve_programme(pid, "dean") is True
        assert service.get_programme(pid)["status"] == "approved"

    def test_new_version_clones(self, service):
        pid = service.create_programme(code="X", title="Y", credits=120)
        new_id = service.new_programme_version(pid, "2.0", created_by="admin")
        clone = service.get_programme(new_id)
        assert clone["version"] == "2.0"
        assert clone["status"] == "draft"
        assert clone["credits"] == 120
        assert new_id != pid

    def test_list_filters(self, service):
        service.create_programme(code="A", title="A", department="CS")
        service.create_programme(code="B", title="B", department="Maths")
        assert len(service.list_programmes(department="CS")) == 1


class TestModuleDescriptors:
    def test_create_and_list(self, service):
        pid = service.create_programme(code="X", title="Y")
        did = service.create_module_descriptor(programme_id=pid,
                                               module_code="CS101",
                                               title="Intro", credits=20)
        mods = service.list_module_descriptors(pid)
        assert len(mods) == 1
        assert mods[0]["module_code"] == "CS101"

    def test_create_requires_code_title(self, service):
        with pytest.raises(ValueError):
            service.create_module_descriptor(title="No code")


class TestLearningOutcomes:
    def test_add_and_list(self, service):
        pid = service.create_programme(code="X", title="Y")
        service.add_learning_outcome("programme", pid, "Understand X",
                                     code="LO1", domain="knowledge")
        los = service.list_learning_outcomes("programme", pid)
        assert len(los) == 1
        assert los[0]["code"] == "LO1"

    def test_invalid_parent_type(self, service):
        with pytest.raises(ValueError):
            service.add_learning_outcome("bad", 1, "desc")

    def test_invalid_domain(self, service):
        with pytest.raises(ValueError):
            service.add_learning_outcome("programme", 1, "desc", domain="bogus")

    def test_delete(self, service):
        pid = service.create_programme(code="X", title="Y")
        lo = service.add_learning_outcome("programme", pid, "desc")
        assert service.delete_learning_outcome(lo) is True
        assert service.list_learning_outcomes("programme", pid) == []


class TestAssessmentStrategy:
    def test_add_and_weighting_total(self, service):
        pid = service.create_programme(code="X", title="Y")
        did = service.create_module_descriptor(programme_id=pid,
                                               module_code="CS101", title="Intro")
        service.add_assessment_component(did, "Exam", assessment_type="exam",
                                         weighting_pct=60,
                                         learning_outcomes_assessed="LO1")
        service.add_assessment_component(did, "Coursework",
                                         assessment_type="coursework",
                                         weighting_pct=40,
                                         learning_outcomes_assessed="LO2")
        assert service.assessment_weighting_total(did) == 100.0

    def test_invalid_assessment_type(self, service):
        pid = service.create_programme(code="X", title="Y")
        did = service.create_module_descriptor(programme_id=pid,
                                               module_code="CS101", title="Intro")
        with pytest.raises(ValueError):
            service.add_assessment_component(did, "Thing", assessment_type="bogus")

    def test_validate_strategy_flags_issues(self, service):
        pid = service.create_programme(code="X", title="Y")
        did = service.create_module_descriptor(programme_id=pid,
                                               module_code="CS101", title="Intro")
        # No components
        result = service.validate_assessment_strategy(did)
        assert result["valid"] is False
        assert any("No assessment" in i for i in result["issues"])
        # Weighting != 100 and missing LO map
        service.add_assessment_component(did, "Exam", weighting_pct=50)
        result = service.validate_assessment_strategy(did)
        assert result["valid"] is False
        assert result["total"] == 50

    def test_validate_strategy_valid(self, service):
        pid = service.create_programme(code="X", title="Y")
        did = service.create_module_descriptor(programme_id=pid,
                                               module_code="CS101", title="Intro")
        service.add_assessment_component(did, "Exam", weighting_pct=100,
                                         learning_outcomes_assessed="LO1")
        result = service.validate_assessment_strategy(did)
        assert result["valid"] is True


class TestChangeControl:
    def test_propose_approve_reject(self, service):
        pid = service.create_programme(code="X", title="Y")
        ch = service.propose_change("programme", pid, "Update aims",
                                    change_type="minor")
        assert service.approve_change(ch, "committee") is True
        changes = service.list_changes("programme", pid, status="approved")
        assert len(changes) == 1

    def test_propose_invalid_parent(self, service):
        with pytest.raises(ValueError):
            service.propose_change("bad", 1, "summary")


class TestReportingAndExport:
    def test_generate_handbook(self, service):
        pid = service.create_programme(code="CS-BSC", title="BSc CS",
                                       award="BSc", educational_aims="Learn CS")
        service.add_learning_outcome("programme", pid, "Understand CS", code="LO1")
        service.create_module_descriptor(programme_id=pid, module_code="CS101",
                                         title="Intro", credits=20)
        handbook = service.generate_handbook(pid)
        assert "BSc CS" in handbook
        assert "CS101" in handbook
        assert "Learn CS" in handbook

    def test_generate_handbook_missing(self, service):
        with pytest.raises(ValueError):
            service.generate_handbook(99999)

    def test_programme_summary(self, service):
        pid = service.create_programme(code="X", title="Y")
        service.create_module_descriptor(programme_id=pid, module_code="M1",
                                         title="M1", credits=20, is_core=1)
        service.create_module_descriptor(programme_id=pid, module_code="M2",
                                         title="M2", credits=10, is_core=0)
        summary = service.programme_summary(pid)
        assert summary["module_count"] == 2
        assert summary["core_modules"] == 1
        assert summary["total_credits"] == 30

    def test_hesa_payload(self, service):
        pid = service.create_programme(code="CS-BSC", title="BSc CS", credits=360)
        payload = service.hesa_programme_payload(pid)
        assert payload["programme_code"] == "CS-BSC"
        assert payload["credit_value"] == 360
