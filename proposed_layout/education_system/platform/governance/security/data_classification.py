"""Data classification for identifying sensitive fields that need encryption."""

SENSITIVE_FIELDS = frozenset({
    # Medical
    "medical_notes", "medical_conditions", "allergies", "medications",
    "medical_history", "health_notes", "disability_details",
    # Safeguarding
    "safeguarding_notes", "concern_details", "counselling_notes",
    "referral_details", "risk_details", "incident_details",
    # Contact / PII
    "home_address", "address", "postcode", "phone_number", "mobile_number",
    "emergency_contact_phone", "parent_email", "parent_phone",
    "email_address", "personal_email",
    # Identity
    "national_insurance", "ni_number", "bank_details", "bank_account",
    "sort_code", "passport_number", "date_of_birth", "dob",
    # Protected characteristics
    "ethnicity", "religion", "sexual_orientation", "gender_identity",
    # SEN / EHCP
    "sen_details", "ehcp_details", "learning_difficulties",
    "support_needs", "additional_needs",
})

_CATEGORIES = {
    "medical": {"medical_notes", "medical_conditions", "allergies", "medications",
                "medical_history", "health_notes", "disability_details"},
    "safeguarding": {"safeguarding_notes", "concern_details", "counselling_notes",
                     "referral_details", "risk_details", "incident_details"},
    "contact": {"home_address", "address", "postcode", "phone_number", "mobile_number",
                "emergency_contact_phone", "parent_email", "parent_phone",
                "email_address", "personal_email"},
    "identity": {"national_insurance", "ni_number", "bank_details", "bank_account",
                 "sort_code", "passport_number", "date_of_birth", "dob"},
    "protected_characteristics": {"ethnicity", "religion", "sexual_orientation",
                                  "gender_identity"},
    "sen": {"sen_details", "ehcp_details", "learning_difficulties",
            "support_needs", "additional_needs"},
}


def is_sensitive_field(field_name: str) -> bool:
    return field_name in SENSITIVE_FIELDS


def get_sensitive_fields() -> frozenset:
    return SENSITIVE_FIELDS


def get_fields_by_category(category: str) -> set:
    return _CATEGORIES.get(category, set())


def get_categories() -> list:
    return list(_CATEGORIES.keys())
