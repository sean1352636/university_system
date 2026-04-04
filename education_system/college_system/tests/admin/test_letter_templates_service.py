"""Tests for LetterTemplateService."""

import pytest


class TestLetterTemplateService:
    @pytest.fixture
    def service(self, db_path):
        from education_system.college_system.modules.domain.letter_templates.services.letter_templates_service import LetterTemplateService
        return LetterTemplateService(db_path)

    @pytest.fixture
    def sample_template(self, service):
        return service.create_template(
            template_name="Offer Letter",
            body_template="Dear {{name}}, we are pleased to offer...",
            category="admissions",
        )

    def test_create_template(self, service):
        t = service.create_template(
            template_name="Welcome Letter",
            body_template="Dear {{name}}, welcome to...",
        )
        assert t is not None

    def test_list_templates(self, service):
        service.create_template(template_name="T1", body_template="Body 1")
        service.create_template(template_name="T2", body_template="Body 2")
        templates = service.list_templates()
        assert len(templates) >= 2

    def test_get_template(self, service, sample_template):
        tid = sample_template["id"]
        found = service.get_template(tid)
        assert found is not None
        assert found["template_name"] == "Offer Letter"

    def test_update_template(self, service, sample_template):
        updated = service.update_template(
            sample_template["id"], template_name="Updated Offer",
        )
        assert updated["template_name"] == "Updated Offer"

    def test_delete_template(self, service, sample_template):
        result = service.delete_template(sample_template["id"])
        assert result is True

    def test_generate_letter(self, service, sample_template):
        letter = service.generate_letter(
            template_id=sample_template["id"],
            recipient_name="John Doe",
            body="Dear John, we are pleased to offer you a place.",
        )
        assert letter is not None

    def test_list_letters(self, service, sample_template):
        service.generate_letter(
            sample_template["id"], "Alice", "Dear Alice...",
        )
        letters = service.list_letters(template_id=sample_template["id"])
        assert len(letters) >= 1

    def test_mark_sent(self, service, sample_template):
        letter = service.generate_letter(
            sample_template["id"], "Bob", "Dear Bob...",
        )
        result = service.mark_sent(letter["id"], sent_via="email")
        assert result["status"] in ("sent", "delivered")

    def test_get_stats(self, service):
        stats = service.get_stats()
        assert stats is not None
