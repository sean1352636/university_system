"""Tests for StudentSupportService."""

import pytest

from education_system.college_system.modules.domain.student_support.services.student_support_service import StudentSupportService
from education_system.college_system.core.exceptions import StudentSupportError


class TestInterventions:
    def test_create_intervention(self, db_path, sample_student):
        svc = StudentSupportService(db_path)
        item = svc.create_intervention(sample_student["id"], 1, "academic",
                                       targets="Improve grades", sessions_planned=5)
        assert item["intervention_type"] == "academic"
        assert item["sessions_planned"] == 5
        assert item["status"] == "planned"

    def test_list_interventions(self, db_path, sample_student):
        svc = StudentSupportService(db_path)
        svc.create_intervention(sample_student["id"], 1, "academic")
        svc.create_intervention(sample_student["id"], 1, "attendance")
        items = svc.list_interventions(student_id=sample_student["id"])
        assert len(items) >= 2

    def test_record_session_attended(self, db_path, sample_student):
        svc = StudentSupportService(db_path)
        item = svc.create_intervention(sample_student["id"], 1, "mentoring",
                                       sessions_planned=3)
        updated = svc.record_session_attended(item["id"])
        assert updated["sessions_attended"] == 1

    def test_update_intervention(self, db_path, sample_student):
        svc = StudentSupportService(db_path)
        item = svc.create_intervention(sample_student["id"], 1, "academic")
        updated = svc.update_intervention(item["id"], status="active",
                                          outcome="In progress")
        assert updated["status"] == "active"


class TestRiskRegister:
    def test_create_risk(self, db_path, sample_student):
        svc = StudentSupportService(db_path)
        risk = svc.create_risk(sample_student["id"], "academic", "high", 1,
                               mitigations="Extra tutoring")
        assert risk["risk_type"] == "academic"
        assert risk["risk_level"] == "high"
        assert risk["status"] == "open"

    def test_resolve_risk(self, db_path, sample_student):
        svc = StudentSupportService(db_path)
        risk = svc.create_risk(sample_student["id"], "attendance", "medium", 1)
        resolved = svc.resolve_risk(risk["id"])
        assert resolved["status"] == "resolved"

    def test_escalate_risk(self, db_path, sample_student):
        svc = StudentSupportService(db_path)
        risk = svc.create_risk(sample_student["id"], "wellbeing", "high", 1)
        escalated = svc.escalate_risk(risk["id"])
        assert escalated["status"] == "escalated"

    def test_student_risk_profile(self, db_path, sample_student):
        svc = StudentSupportService(db_path)
        svc.create_risk(sample_student["id"], "academic", "low", 1)
        profile = svc.get_student_risk_profile(sample_student["id"])
        assert profile["total_risks"] >= 1


class TestDocuments:
    def test_upload_document(self, db_path, sample_student):
        svc = StudentSupportService(db_path)
        doc = svc.upload_document(sample_student["id"], "consent_form",
                                  "Photo Consent", 1)
        assert doc["document_type"] == "consent_form"
        assert doc["verified"] == 0

    def test_verify_document(self, db_path, sample_student):
        svc = StudentSupportService(db_path)
        doc = svc.upload_document(sample_student["id"], "id_document",
                                  "Passport Copy", 1)
        verified = svc.verify_document(doc["id"], 1)
        assert verified["verified"] == 1
