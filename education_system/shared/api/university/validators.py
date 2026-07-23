"""Input validation helpers for API request payloads.

Each validator raises ``ValidationError`` on bad input so callers
don't need to duplicate validation logic.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from education_system.post_18.university_system.core.exceptions import ValidationError


def _require_fields(data: dict[str, Any], required: list[str]) -> None:
    missing = [f for f in required if not data.get(f)]
    if missing:
        raise ValidationError(f"Missing required fields: {', '.join(missing)}")


def validate_student_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["first_name", "last_name"])
    if data.get("email_address"):
        _validate_email(data["email_address"])


def validate_student_update(data: dict[str, Any]) -> None:
    if not data:
        raise ValidationError("No fields provided for update")
    if data.get("email_address"):
        _validate_email(data["email_address"])


def validate_module_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["module_code", "module_name"])


def validate_module_update(data: dict[str, Any]) -> None:
    if not data:
        raise ValidationError("No fields provided for update")


def validate_enrollment_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["student_id", "module_code"])


def validate_grade_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["student_id"])
    if not data.get("score") and not data.get("letter_grade"):
        raise ValidationError("At least one of 'score' or 'letter_grade' is required")


def validate_grade_update(data: dict[str, Any]) -> None:
    if not data:
        raise ValidationError("No fields provided for update")


def validate_login(data: dict[str, Any]) -> None:
    _require_fields(data, ["username", "password"])


def validate_payment_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["student_id", "amount", "payment_type"])
    try:
        amount = float(data["amount"])
    except (TypeError, ValueError):
        raise ValidationError("'amount' must be a number")
    if amount <= 0:
        raise ValidationError("'amount' must be positive")


def validate_attendance_session_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["module_code", "session_date", "session_type"])


def validate_attendance_record_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["student_id", "session_id", "status"])
    valid_statuses = {"present", "absent", "late", "excused"}
    if data["status"] not in valid_statuses:
        raise ValidationError(
            f"Invalid status '{data['status']}'. Must be one of: {', '.join(sorted(valid_statuses))}"
        )


def validate_assignment_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["module_code", "title", "due_date"])


def validate_assignment_update(data: dict[str, Any]) -> None:
    if not data:
        raise ValidationError("No fields provided for update")


def validate_submission_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["student_id"])


def validate_course_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["course_code", "course_name"])


def validate_course_update(data: dict[str, Any]) -> None:
    if not data:
        raise ValidationError("No fields provided for update")


def validate_user_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["username", "password", "role"])
    valid_roles = {"admin", "instructor", "student", "staff"}
    if data["role"] not in valid_roles:
        raise ValidationError(
            f"Invalid role '{data['role']}'. Must be one of: {', '.join(sorted(valid_roles))}"
        )
    if data.get("email"):
        _validate_email(data["email"])


def validate_user_update(data: dict[str, Any]) -> None:
    if not data:
        raise ValidationError("No fields provided for update")
    valid_roles = {"admin", "instructor", "student", "staff"}
    if data.get("role") and data["role"] not in valid_roles:
        raise ValidationError(
            f"Invalid role '{data['role']}'. Must be one of: {', '.join(sorted(valid_roles))}"
        )
    if data.get("email"):
        _validate_email(data["email"])


def validate_housing_application_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["student_id", "preferred_room_type", "requested_move_in_date", "requested_duration_months"])
    try:
        dur = int(data["requested_duration_months"])
    except (TypeError, ValueError):
        raise ValidationError("'requested_duration_months' must be an integer")
    if dur <= 0:
        raise ValidationError("'requested_duration_months' must be positive")


def validate_housing_application_update(data: dict[str, Any]) -> None:
    if not data:
        raise ValidationError("No fields provided for update")
    valid_statuses = {"submitted", "under_review", "approved", "denied", "cancelled"}
    if data.get("status") and data["status"] not in valid_statuses:
        raise ValidationError(
            f"Invalid status '{data['status']}'. Must be one of: {', '.join(sorted(valid_statuses))}"
        )


def validate_book_loan_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["book_id", "user_id", "due_date"])


def validate_book_reservation_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["book_id", "user_id"])


def validate_health_appointment_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["student_id", "appointment_type", "appointment_date", "appointment_time"])


def validate_facility_booking_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["facility_name", "booking_date", "start_time", "end_time", "purpose"])


def validate_maintenance_request_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["location_type", "request_type", "priority", "description", "reported_by"])
    valid_priorities = {"low", "medium", "high", "urgent"}
    if data["priority"].lower() not in valid_priorities:
        raise ValidationError(
            f"Invalid priority '{data['priority']}'. Must be one of: {', '.join(sorted(valid_priorities))}"
        )


def validate_job_posting_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["company_name", "job_title", "job_description"])


def validate_job_application_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["job_id", "applicant_id"])


def validate_research_project_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["project_title", "principal_investigator_id", "department", "project_type", "start_date"])


def validate_research_publication_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["title", "authors", "publication_type"])


def validate_admission_application_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["prospect_id", "application_type", "program_applied", "academic_year", "semester"])


def validate_event_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["title", "category", "start_datetime", "end_datetime", "location"])


def validate_event_registration_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["event_id"])


def validate_meal_topup(data: dict[str, Any]) -> None:
    _require_fields(data, ["student_id", "amount"])
    try:
        amount = float(data["amount"])
    except (TypeError, ValueError):
        raise ValidationError("'amount' must be a number")
    if amount <= 0:
        raise ValidationError("'amount' must be positive")


def validate_notification_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["user_id", "channel", "priority", "title", "message"])
    valid_priorities = {"low", "normal", "high", "urgent"}
    if data["priority"].lower() not in valid_priorities:
        raise ValidationError(
            f"Invalid priority '{data['priority']}'. Must be one of: {', '.join(sorted(valid_priorities))}"
        )


def validate_mentorship_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["mentor_id", "mentee_id", "skill_area"])


def validate_mentorship_session_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["relationship_id", "session_date", "duration_minutes"])


def validate_parking_permit_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["user_id", "zone", "permit_type", "start_date", "end_date"])


def validate_vehicle_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["license_plate", "owner_id"])


def validate_club_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["club_name"])


def validate_club_member_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["club_id", "student_id"])


def validate_security_ticket_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["type", "subject", "description"])


def validate_lost_found_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["item_description", "found_date"])


def validate_scholarship_application_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["student_id", "scholarship_id"])


def validate_study_group_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["course_id", "group_name", "creator_id"])


def validate_alumni_update(data: dict[str, Any]) -> None:
    if not data:
        raise ValidationError("No fields provided for update")
    if data.get("email_address"):
        _validate_email(data["email_address"])


def validate_alumni_donation_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["alumni_id", "donation_amount", "donation_type"])
    try:
        amount = float(data["donation_amount"])
    except (TypeError, ValueError):
        raise ValidationError("'donation_amount' must be a number")
    if amount <= 0:
        raise ValidationError("'donation_amount' must be positive")


def validate_exam_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["module_code", "date", "start_time", "end_time"])


def validate_exam_update(data: dict[str, Any]) -> None:
    if not data:
        raise ValidationError("No fields provided for update")


def validate_calendar_event_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["name", "event_type"])
    has_single = bool(data.get("date"))
    has_range = bool(data.get("date_start") and data.get("date_end"))
    if not has_single and not has_range:
        raise ValidationError("Either 'date' or both 'date_start' and 'date_end' are required")


def validate_assessment_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["assessment_name", "assessment_type", "module_code", "max_points", "weight"])
    try:
        w = float(data["weight"])
    except (TypeError, ValueError):
        raise ValidationError("'weight' must be a number")
    if not (0 <= w <= 100):
        raise ValidationError("'weight' must be between 0 and 100")


def validate_assessment_update(data: dict[str, Any]) -> None:
    if not data:
        raise ValidationError("No fields provided for update")


def validate_financial_aid_application_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["student_id", "academic_year"])


def validate_aid_package_update(data: dict[str, Any]) -> None:
    if not data:
        raise ValidationError("No fields provided for update")
    valid_statuses = {"offered", "accepted", "declined", "revised"}
    if data.get("package_status") and data["package_status"] not in valid_statuses:
        raise ValidationError(
            f"Invalid status '{data['package_status']}'. Must be one of: {', '.join(sorted(valid_statuses))}"
        )


def validate_degree_program_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["program_code", "program_name", "degree_type", "total_credits_required"])


def validate_degree_program_update(data: dict[str, Any]) -> None:
    if not data:
        raise ValidationError("No fields provided for update")


def validate_prerequisite_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["course_id", "prerequisite_course_id"])


def validate_announcement_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["title", "content", "target_audience", "start_date"])


def validate_announcement_update(data: dict[str, Any]) -> None:
    if not data:
        raise ValidationError("No fields provided for update")


def validate_advising_appointment_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["student_id", "advisor_id", "appointment_date", "appointment_time", "appointment_type"])


def validate_accommodation_request_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["student_id", "accommodation_type"])


def validate_tutoring_offer_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["tutor_id", "subject"])


def validate_chat_room_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["name", "room_type"])


def validate_chat_message_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["room_id", "content"])


def validate_leave_request_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["user_id", "leave_type_id", "start_date", "end_date", "total_days"])


def validate_shift_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["staff_id", "shift_date", "start_time", "end_time"])


def validate_timesheet_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["user_id", "week_start", "week_end"])


def validate_support_ticket_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["title", "description", "category", "priority"])
    if data.get("priority") and data["priority"] not in ("low", "medium", "high", "critical"):
        raise ValidationError("priority must be low, medium, high, or critical")


def validate_ticket_reply_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["message"])


def validate_kb_article_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["title", "content", "category"])


def validate_faq_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["question", "answer", "category"])


def validate_parent_message_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["parent_id", "message_content"])


def validate_parent_conference_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["parent_id", "teacher_id", "datetime"])


def validate_lms_course_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["module_code", "instructor_id"])


def validate_lms_quiz_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["lms_course_id", "title"])


def validate_lms_forum_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["lms_course_id", "topic"])


def validate_misconduct_case_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["student_id", "student_name", "course", "violation_type", "severity"])
    if data.get("severity") and data["severity"] not in ("Minor", "Moderate", "Major", "Severe"):
        raise ValidationError("severity must be Minor, Moderate, Major, or Severe")


def validate_room_booking_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["room_id", "booking_type", "start_datetime", "end_datetime"])


def validate_campus_tour_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["tour_date", "tour_time"])


def validate_resource_booking_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["resource_id", "start_time", "end_time"])


def validate_feedback_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["category_id", "type", "title", "description"])
    if data.get("type") and data["type"] not in ("feedback", "suggestion"):
        raise ValidationError("type must be feedback or suggestion")


def validate_course_evaluation_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["module_code", "academic_year", "semester", "instructor_id", "template_id", "start_date", "end_date"])


def validate_message_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["recipient_id", "subject"])


def validate_newsletter_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["title", "content"])


def validate_mental_health_appointment_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["student_id", "appointment_type", "appointment_date", "appointment_time"])


def validate_counseling_appointment_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["student_id", "appointment_date", "appointment_time"])


def validate_emergency_alert_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["alert_title", "alert_message", "alert_type"])


def validate_emergency_contact_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["student_id", "contact_name", "relationship", "phone_primary"])


def validate_incident_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["incident_type", "description", "incident_datetime"])


def validate_virtual_classroom_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["session_name", "instructor_id", "platform"])


def validate_virtual_session_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["classroom_id", "start_time"])


def validate_equipment_checkout_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["equipment_id", "borrower_id", "checkout_date", "expected_return"])


def validate_equipment_maintenance_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["item_id", "maintenance_type", "performed_date"])


def validate_poll_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["title", "start_date", "end_date"])


def validate_election_candidate_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["election_id", "student_id"])


def validate_document_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["title", "content"])


def validate_credential_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["student_id", "credential_type", "credential_name", "issue_date", "blockchain_hash"])


def validate_badge_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["badge_name", "criteria", "issuer_name"])


def validate_certification_create(data: dict[str, Any]) -> None:
    _require_fields(data, ["user_id", "name"])


def validate_password_change(data: dict[str, Any]) -> None:
    _require_fields(data, ["current_password", "new_password"])
    if len(data["new_password"]) < 8:
        raise ValidationError("New password must be at least 8 characters")


def validate_profile_update(data: dict[str, Any]) -> None:
    if not data:
        raise ValidationError("No fields provided for update")
    if data.get("email"):
        _validate_email(data["email"])


def validate_preferences_update(data: dict[str, Any]) -> None:
    if not data:
        raise ValidationError("No fields provided for update")
    allowed = {"theme", "language", "timezone", "email_notifications", "sms_notifications"}
    unknown = set(data.keys()) - allowed
    if unknown:
        raise ValidationError(f"Unknown preference fields: {', '.join(sorted(unknown))}")


def _validate_email(email: str) -> None:
    pattern = r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
    if not re.match(pattern, email):
        raise ValidationError(f"Invalid email address: {email}")


# -----------------------------------------------------------------------
# Generic format validators
# -----------------------------------------------------------------------

def validate_email(email: str) -> None:
    """Validate that *email* looks like a valid email address.

    Raises ``ValueError`` if the format is invalid.
    """
    pattern = r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
    if not re.match(pattern, email):
        raise ValueError(f"Invalid email format: {email}")


def validate_date(date_str: str, fmt: str = "%Y-%m-%d") -> datetime:
    """Parse *date_str* according to *fmt* and return the datetime object.

    Raises ``ValueError`` if the string does not match the expected format.
    """
    try:
        return datetime.strptime(date_str, fmt)
    except (ValueError, TypeError) as exc:
        raise ValueError(
            f"Invalid date '{date_str}'. Expected format: {fmt}"
        ) from exc


def validate_date_range(start: str, end: str, fmt: str = "%Y-%m-%d") -> None:
    """Ensure *start* date is on or before *end* date.

    Raises ``ValueError`` if *start* is after *end* or either date is invalid.
    """
    start_dt = validate_date(start, fmt)
    end_dt = validate_date(end, fmt)
    if start_dt > end_dt:
        raise ValueError(
            f"Start date ({start}) must be on or before end date ({end})"
        )


def validate_phone(phone: str) -> None:
    """Basic phone number validation.

    Allows digits, spaces, ``+``, ``-``, and parentheses.
    The cleaned number must be between 7 and 15 characters long.

    Raises ``ValueError`` if the phone number is invalid.
    """
    cleaned = re.sub(r"[\s\-\(\)\+]", "", phone)
    if not cleaned.isdigit():
        raise ValueError(
            f"Invalid phone number: {phone}. "
            "Only digits, spaces, +, -, and parentheses are allowed."
        )
    if not (7 <= len(cleaned) <= 15):
        raise ValueError(
            f"Invalid phone number: {phone}. "
            "Must contain between 7 and 15 digits."
        )


def validate_string_length(
    value: str, field_name: str, min_len: int = 1, max_len: int = 500
) -> None:
    """Validate that *value* length is within [*min_len*, *max_len*].

    Raises ``ValueError`` if the length is out of bounds.
    """
    length = len(value)
    if length < min_len or length > max_len:
        raise ValueError(
            f"'{field_name}' must be between {min_len} and {max_len} "
            f"characters long (got {length})."
        )


def validate_enum(value, field_name: str, allowed) -> None:
    """Check that *value* is in the *allowed* set.

    Raises ``ValueError`` if the value is not allowed.
    """
    if value not in allowed:
        raise ValueError(
            f"Invalid value for '{field_name}': {value!r}. "
            f"Must be one of: {', '.join(str(a) for a in sorted(allowed))}"
        )


def validate_positive_int(value, field_name: str) -> int:
    """Validate that *value* is a positive integer.

    Raises ``ValueError`` if the value is not a positive integer.
    """
    try:
        int_val = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"'{field_name}' must be a positive integer, got: {value!r}"
        ) from exc
    if int_val <= 0:
        raise ValueError(
            f"'{field_name}' must be a positive integer, got: {int_val}"
        )
    return int_val
