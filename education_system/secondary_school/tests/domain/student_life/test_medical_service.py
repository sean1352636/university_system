"""Tests for MedicalService."""
import pytest

from education_system.secondary_school.modules.domain.student_life.medical.services.medical_service import MedicalService


@pytest.fixture
def medical_service(db_path):
    return MedicalService(db_path)


class TestMedicalConditions:
    def test_add_condition(self, medical_service, sample_student):
        cond = medical_service.add_condition(
            student_id=sample_student["id"],
            condition_name="Asthma",
            severity="medium",
            medications="Inhaler",
            doctor_name="Dr Smith",
        )
        assert cond["condition_name"] == "Asthma"
        assert cond["severity"] == "medium"

    def test_list_conditions(self, medical_service, sample_student):
        medical_service.add_condition(sample_student["id"], "Asthma")
        medical_service.add_condition(sample_student["id"], "Nut Allergy", severity="high")
        result = medical_service.list_conditions()
        assert len(result) == 2

    def test_list_conditions_filter_by_student(self, medical_service, sample_student, sample_student_ks4):
        medical_service.add_condition(sample_student["id"], "Asthma")
        medical_service.add_condition(sample_student_ks4["id"], "Epilepsy")
        result = medical_service.list_conditions(student_id=sample_student["id"])
        assert len(result) == 1
        assert result[0]["condition_name"] == "Asthma"

    def test_delete_condition(self, medical_service, sample_student):
        cond = medical_service.add_condition(sample_student["id"], "Eczema")
        medical_service.delete_condition(cond["id"])
        result = medical_service.list_conditions(student_id=sample_student["id"])
        assert len(result) == 0


class TestFirstAidLog:
    def test_log_incident(self, medical_service, sample_student):
        inc = medical_service.log_incident(
            student_id=sample_student["id"],
            description="Fell in playground",
            incident_date="2026-03-20",
            location="Playground",
            treatment="Ice pack applied",
            treated_by="Mrs Green",
        )
        assert inc["description"] == "Fell in playground"
        assert inc["location"] == "Playground"

    def test_list_incidents(self, medical_service, sample_student):
        medical_service.log_incident(sample_student["id"], "Headache")
        medical_service.log_incident(sample_student["id"], "Cut finger")
        result = medical_service.list_incidents()
        assert len(result) == 2

    def test_list_incidents_filter_by_student(self, medical_service, sample_student, sample_student_ks4):
        medical_service.log_incident(sample_student["id"], "Headache")
        medical_service.log_incident(sample_student_ks4["id"], "Sprain")
        result = medical_service.list_incidents(student_id=sample_student["id"])
        assert len(result) == 1
        assert result[0]["description"] == "Headache"

    def test_delete_incident(self, medical_service, sample_student):
        inc = medical_service.log_incident(sample_student["id"], "Nosebleed")
        medical_service.delete_incident(inc["id"])
        result = medical_service.list_incidents(student_id=sample_student["id"])
        assert len(result) == 0
