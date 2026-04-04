"""Tests for shared.security.data_classification — field sensitivity lookups."""

import pytest

from education_system.shared.security.data_classification import (
    is_sensitive_field,
    get_sensitive_fields,
    get_fields_by_category,
    get_categories,
)


class TestIsSensitiveField:
    """Test is_sensitive_field for known sensitive and non-sensitive fields."""

    @pytest.mark.parametrize("field", [
        "email_address", "phone_number", "date_of_birth", "medical_notes",
        "ni_number", "bank_details", "safeguarding_notes", "ethnicity",
        "sen_details", "passport_number",
    ])
    def test_known_sensitive_fields(self, field):
        assert is_sensitive_field(field) is True

    @pytest.mark.parametrize("field", [
        "first_name", "last_name", "student_id", "grade", "subject",
        "enrollment_date", "module_code", "room_number",
    ])
    def test_non_sensitive_fields(self, field):
        assert is_sensitive_field(field) is False


class TestGetSensitiveFields:
    """Test get_sensitive_fields returns a frozenset."""

    def test_returns_frozenset(self):
        fields = get_sensitive_fields()
        assert isinstance(fields, frozenset)

    def test_contains_expected_fields(self):
        fields = get_sensitive_fields()
        assert "password" not in fields  # password is not in the set
        assert "home_address" in fields
        assert "allergies" in fields


class TestGetFieldsByCategory:
    """Test get_fields_by_category."""

    def test_medical_category(self):
        fields = get_fields_by_category("medical")
        assert "medical_notes" in fields
        assert "allergies" in fields

    def test_identity_category(self):
        fields = get_fields_by_category("identity")
        assert "passport_number" in fields
        assert "ni_number" in fields

    def test_unknown_category_returns_empty(self):
        assert get_fields_by_category("nonexistent") == set()

    def test_contact_category(self):
        fields = get_fields_by_category("contact")
        assert "email_address" in fields
        assert "phone_number" in fields


class TestGetCategories:
    """Test get_categories returns all category names."""

    def test_returns_list(self):
        cats = get_categories()
        assert isinstance(cats, list)

    def test_expected_categories_present(self):
        cats = get_categories()
        for expected in ("medical", "safeguarding", "contact", "identity", "sen"):
            assert expected in cats

    def test_protected_characteristics_present(self):
        assert "protected_characteristics" in get_categories()
