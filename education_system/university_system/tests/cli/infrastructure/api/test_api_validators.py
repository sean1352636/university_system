#!/usr/bin/env python3
"""
Comprehensive tests for API input validators.

Tests all validator functions in shared.api.university.validators, covering:
- _require_fields helper
- _validate_email regex helper
- All validate_*_create validators (required fields + value constraints)
- All validate_*_update validators (non-empty + optional value constraints)

Organised into test classes by domain area.
"""

import pytest

from education_system.university_system.core.exceptions import ValidationError
from education_system.shared.api.university.validators import (
    _require_fields,
    _validate_email,
    validate_student_create,
    validate_student_update,
    validate_module_create,
    validate_module_update,
    validate_enrollment_create,
    validate_grade_create,
    validate_grade_update,
    validate_login,
    validate_payment_create,
    validate_attendance_session_create,
    validate_attendance_record_create,
    validate_assignment_create,
    validate_assignment_update,
    validate_submission_create,
    validate_course_create,
    validate_course_update,
    validate_user_create,
    validate_user_update,
    validate_housing_application_create,
    validate_housing_application_update,
    validate_book_loan_create,
    validate_book_reservation_create,
    validate_health_appointment_create,
    validate_facility_booking_create,
    validate_maintenance_request_create,
    validate_job_posting_create,
    validate_job_application_create,
    validate_research_project_create,
    validate_research_publication_create,
    validate_admission_application_create,
    validate_event_create,
    validate_event_registration_create,
    validate_meal_topup,
    validate_notification_create,
    validate_mentorship_create,
    validate_mentorship_session_create,
    validate_parking_permit_create,
    validate_vehicle_create,
    validate_club_create,
    validate_club_member_create,
    validate_security_ticket_create,
    validate_lost_found_create,
    validate_scholarship_application_create,
    validate_study_group_create,
    validate_alumni_update,
    validate_alumni_donation_create,
    validate_exam_create,
    validate_exam_update,
    validate_calendar_event_create,
    validate_assessment_create,
    validate_assessment_update,
    validate_financial_aid_application_create,
    validate_aid_package_update,
    validate_degree_program_create,
    validate_degree_program_update,
    validate_prerequisite_create,
    validate_announcement_create,
    validate_announcement_update,
    validate_advising_appointment_create,
    validate_accommodation_request_create,
    validate_tutoring_offer_create,
    validate_chat_room_create,
    validate_chat_message_create,
    validate_leave_request_create,
    validate_shift_create,
    validate_timesheet_create,
    validate_support_ticket_create,
    validate_ticket_reply_create,
    validate_kb_article_create,
    validate_faq_create,
    validate_parent_message_create,
    validate_parent_conference_create,
    validate_lms_course_create,
    validate_lms_quiz_create,
    validate_lms_forum_create,
    validate_misconduct_case_create,
    validate_room_booking_create,
    validate_campus_tour_create,
    validate_resource_booking_create,
    validate_feedback_create,
    validate_course_evaluation_create,
    validate_message_create,
    validate_newsletter_create,
    validate_mental_health_appointment_create,
    validate_counseling_appointment_create,
    validate_emergency_alert_create,
    validate_emergency_contact_create,
    validate_incident_create,
    validate_virtual_classroom_create,
    validate_virtual_session_create,
    validate_equipment_checkout_create,
    validate_equipment_maintenance_create,
    validate_poll_create,
    validate_election_candidate_create,
    validate_document_create,
    validate_credential_create,
    validate_badge_create,
    validate_certification_create,
)


# ============================================================================
# Helpers
# ============================================================================


class TestRequireFields:
    """Tests for the _require_fields helper."""

    def test_all_fields_present(self):
        data = {"a": "1", "b": "2", "c": "3"}
        _require_fields(data, ["a", "b", "c"])  # should not raise

    def test_single_missing_field(self):
        with pytest.raises(ValidationError, match="Missing required fields: b"):
            _require_fields({"a": "1"}, ["a", "b"])

    def test_multiple_missing_fields(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            _require_fields({}, ["x", "y"])

    def test_empty_string_treated_as_missing(self):
        """_require_fields uses `not data.get(f)` so empty strings are missing."""
        with pytest.raises(ValidationError, match="Missing required fields: name"):
            _require_fields({"name": ""}, ["name"])

    def test_none_value_treated_as_missing(self):
        with pytest.raises(ValidationError, match="Missing required fields: name"):
            _require_fields({"name": None}, ["name"])

    def test_zero_value_treated_as_missing(self):
        """0 is falsy, so _require_fields treats it as missing."""
        with pytest.raises(ValidationError, match="Missing required fields: count"):
            _require_fields({"count": 0}, ["count"])

    def test_no_required_fields(self):
        _require_fields({}, [])  # should not raise

    def test_extra_fields_ignored(self):
        _require_fields({"a": "1", "b": "2", "extra": "3"}, ["a", "b"])


class TestValidateEmail:
    """Tests for the _validate_email regex helper."""

    @pytest.mark.parametrize("email", [
        "user@example.com",
        "first.last@domain.org",
        "user+tag@sub.domain.co.uk",
        "name123@test.io",
        "a@b.cd",
        "user%name@domain.com",
        "dash-name@my-domain.net",
        "under_score@domain.com",
    ])
    def test_valid_emails(self, email):
        _validate_email(email)  # should not raise

    @pytest.mark.parametrize("email", [
        "plainaddress",
        "@missing-user.com",
        "user@.com",
        "user@com",
        "user@domain.",
        "user@domain.c",
        "user@ domain.com",
        "",
        "user@@domain.com",
    ])
    def test_invalid_emails(self, email):
        with pytest.raises(ValidationError, match="Invalid email address"):
            _validate_email(email)

    def test_double_dot_domain_accepted_by_regex(self):
        """The regex in _validate_email does not reject double dots in the domain."""
        _validate_email("user@domain..com")  # accepted by current regex


# ============================================================================
# Student domain
# ============================================================================


class TestStudentValidators:
    """Tests for student create/update validators."""

    def test_create_valid_minimal(self):
        validate_student_create({
            "student_id": "S001",
            "first_name": "Alice",
            "last_name": "Smith",
        })

    def test_create_valid_with_email(self):
        validate_student_create({
            "student_id": "S001",
            "first_name": "Alice",
            "last_name": "Smith",
            "email_address": "alice@example.com",
        })

    def test_create_missing_student_id(self):
        # student_id is not a required field; first_name + last_name suffice
        validate_student_create({"first_name": "A", "last_name": "B"})

    def test_create_missing_first_name(self):
        with pytest.raises(ValidationError, match="Missing required fields.*first_name"):
            validate_student_create({"student_id": "S001", "last_name": "B"})

    def test_create_missing_last_name(self):
        with pytest.raises(ValidationError, match="Missing required fields.*last_name"):
            validate_student_create({"student_id": "S001", "first_name": "A"})

    def test_create_missing_all_fields(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_student_create({})

    def test_create_invalid_email(self):
        with pytest.raises(ValidationError, match="Invalid email address"):
            validate_student_create({
                "student_id": "S001",
                "first_name": "Alice",
                "last_name": "Smith",
                "email_address": "not-an-email",
            })

    def test_create_email_not_validated_when_absent(self):
        """If email_address is not provided, no email validation happens."""
        validate_student_create({
            "student_id": "S001",
            "first_name": "Alice",
            "last_name": "Smith",
        })

    def test_update_valid(self):
        validate_student_update({"first_name": "Bob"})

    def test_update_empty_dict_raises(self):
        with pytest.raises(ValidationError, match="No fields provided for update"):
            validate_student_update({})

    def test_update_with_valid_email(self):
        validate_student_update({"email_address": "new@example.com"})

    def test_update_with_invalid_email(self):
        with pytest.raises(ValidationError, match="Invalid email address"):
            validate_student_update({"email_address": "bad"})


# ============================================================================
# Authentication
# ============================================================================


class TestAuthValidators:
    """Tests for login and user create/update validators."""

    # -- validate_login --

    def test_login_valid(self):
        validate_login({"username": "admin", "password": "secret"})

    def test_login_missing_username(self):
        with pytest.raises(ValidationError, match="Missing required fields.*username"):
            validate_login({"password": "secret"})

    def test_login_missing_password(self):
        with pytest.raises(ValidationError, match="Missing required fields.*password"):
            validate_login({"username": "admin"})

    def test_login_empty(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_login({})

    # -- validate_user_create --

    def test_user_create_valid(self):
        validate_user_create({
            "username": "jdoe",
            "password": "P@ss1234",
            "role": "student",
        })

    @pytest.mark.parametrize("role", ["admin", "instructor", "student", "staff"])
    def test_user_create_all_valid_roles(self, role):
        validate_user_create({
            "username": "u",
            "password": "p",
            "role": role,
        })

    def test_user_create_invalid_role(self):
        with pytest.raises(ValidationError, match="Invalid role"):
            validate_user_create({
                "username": "u",
                "password": "p",
                "role": "superuser",
            })

    def test_user_create_missing_username(self):
        with pytest.raises(ValidationError, match="Missing required fields.*username"):
            validate_user_create({"password": "p", "role": "admin"})

    def test_user_create_missing_password(self):
        with pytest.raises(ValidationError, match="Missing required fields.*password"):
            validate_user_create({"username": "u", "role": "admin"})

    def test_user_create_missing_role(self):
        with pytest.raises(ValidationError, match="Missing required fields.*role"):
            validate_user_create({"username": "u", "password": "p"})

    def test_user_create_with_valid_email(self):
        validate_user_create({
            "username": "u",
            "password": "p",
            "role": "admin",
            "email": "u@example.com",
        })

    def test_user_create_with_invalid_email(self):
        with pytest.raises(ValidationError, match="Invalid email address"):
            validate_user_create({
                "username": "u",
                "password": "p",
                "role": "admin",
                "email": "not-valid",
            })

    # -- validate_user_update --

    def test_user_update_valid(self):
        validate_user_update({"username": "new_name"})

    def test_user_update_empty(self):
        with pytest.raises(ValidationError, match="No fields provided for update"):
            validate_user_update({})

    def test_user_update_valid_role(self):
        validate_user_update({"role": "instructor"})

    def test_user_update_invalid_role(self):
        with pytest.raises(ValidationError, match="Invalid role"):
            validate_user_update({"role": "owner"})

    def test_user_update_valid_email(self):
        validate_user_update({"email": "valid@example.com"})

    def test_user_update_invalid_email(self):
        with pytest.raises(ValidationError, match="Invalid email address"):
            validate_user_update({"email": "oops"})


# ============================================================================
# Finance & payments
# ============================================================================


class TestFinanceValidators:
    """Tests for payment, meal, donation, and financial aid validators."""

    # -- validate_payment_create --

    def test_payment_create_valid(self):
        validate_payment_create({
            "student_id": "S001",
            "amount": 100.50,
            "payment_type": "tuition",
        })

    def test_payment_create_amount_as_string_number(self):
        validate_payment_create({
            "student_id": "S001",
            "amount": "50.25",
            "payment_type": "fee",
        })

    def test_payment_create_missing_student_id(self):
        with pytest.raises(ValidationError, match="Missing required fields.*student_id"):
            validate_payment_create({"amount": 100, "payment_type": "tuition"})

    def test_payment_create_missing_amount(self):
        with pytest.raises(ValidationError, match="Missing required fields.*amount"):
            validate_payment_create({"student_id": "S001", "payment_type": "tuition"})

    def test_payment_create_missing_payment_type(self):
        with pytest.raises(ValidationError, match="Missing required fields.*payment_type"):
            validate_payment_create({"student_id": "S001", "amount": 100})

    def test_payment_create_non_numeric_amount(self):
        with pytest.raises(ValidationError, match="'amount' must be a number"):
            validate_payment_create({
                "student_id": "S001",
                "amount": "abc",
                "payment_type": "tuition",
            })

    def test_payment_create_zero_amount(self):
        """Zero is falsy so _require_fields catches it as missing before the positivity check."""
        with pytest.raises(ValidationError, match="Missing required fields.*amount"):
            validate_payment_create({
                "student_id": "S001",
                "amount": 0,
                "payment_type": "tuition",
            })

    def test_payment_create_negative_amount(self):
        with pytest.raises(ValidationError, match="'amount' must be positive"):
            validate_payment_create({
                "student_id": "S001",
                "amount": -10,
                "payment_type": "tuition",
            })

    def test_payment_create_amount_none(self):
        """None for amount: _require_fields catches this first."""
        with pytest.raises(ValidationError):
            validate_payment_create({
                "student_id": "S001",
                "amount": None,
                "payment_type": "tuition",
            })

    # -- validate_meal_topup --

    def test_meal_topup_valid(self):
        validate_meal_topup({"student_id": "S001", "amount": 25})

    def test_meal_topup_non_numeric(self):
        with pytest.raises(ValidationError, match="'amount' must be a number"):
            validate_meal_topup({"student_id": "S001", "amount": "xyz"})

    def test_meal_topup_zero(self):
        """Zero is falsy so _require_fields catches it as missing before the positivity check."""
        with pytest.raises(ValidationError, match="Missing required fields.*amount"):
            validate_meal_topup({"student_id": "S001", "amount": 0})

    def test_meal_topup_negative(self):
        with pytest.raises(ValidationError, match="'amount' must be positive"):
            validate_meal_topup({"student_id": "S001", "amount": -5})

    def test_meal_topup_missing_fields(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_meal_topup({})

    # -- validate_alumni_donation_create --

    def test_donation_valid(self):
        validate_alumni_donation_create({
            "alumni_id": "A001",
            "donation_amount": 500,
            "donation_type": "cash",
        })

    def test_donation_non_numeric(self):
        with pytest.raises(ValidationError, match="'donation_amount' must be a number"):
            validate_alumni_donation_create({
                "alumni_id": "A001",
                "donation_amount": "lots",
                "donation_type": "cash",
            })

    def test_donation_zero(self):
        """Zero is falsy so _require_fields catches it as missing before the positivity check."""
        with pytest.raises(ValidationError, match="Missing required fields.*donation_amount"):
            validate_alumni_donation_create({
                "alumni_id": "A001",
                "donation_amount": 0,
                "donation_type": "cash",
            })

    def test_donation_negative(self):
        with pytest.raises(ValidationError, match="'donation_amount' must be positive"):
            validate_alumni_donation_create({
                "alumni_id": "A001",
                "donation_amount": -1,
                "donation_type": "cash",
            })

    # -- validate_financial_aid_application_create --

    def test_financial_aid_valid(self):
        validate_financial_aid_application_create({
            "student_id": "S001",
            "academic_year": "2025-2026",
        })

    def test_financial_aid_missing_student_id(self):
        with pytest.raises(ValidationError, match="Missing required fields.*student_id"):
            validate_financial_aid_application_create({"academic_year": "2025-2026"})

    # -- validate_aid_package_update --

    def test_aid_package_update_valid(self):
        validate_aid_package_update({"package_status": "offered"})

    def test_aid_package_update_empty(self):
        with pytest.raises(ValidationError, match="No fields provided for update"):
            validate_aid_package_update({})

    @pytest.mark.parametrize("status", ["offered", "accepted", "declined", "revised"])
    def test_aid_package_update_valid_statuses(self, status):
        validate_aid_package_update({"package_status": status})

    def test_aid_package_update_invalid_status(self):
        with pytest.raises(ValidationError, match="Invalid status"):
            validate_aid_package_update({"package_status": "pending"})


# ============================================================================
# Attendance
# ============================================================================


class TestAttendanceValidators:
    """Tests for attendance session and record validators."""

    def test_session_create_valid(self):
        validate_attendance_session_create({
            "module_code": "CS101",
            "session_date": "2026-01-15",
            "session_type": "lecture",
        })

    def test_session_create_missing_fields(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_attendance_session_create({})

    # -- validate_attendance_record_create --

    def test_record_create_valid_present(self):
        validate_attendance_record_create({
            "student_id": "S001",
            "session_id": "SES01",
            "status": "present",
        })

    @pytest.mark.parametrize("status", ["present", "absent", "late", "excused"])
    def test_record_create_all_valid_statuses(self, status):
        validate_attendance_record_create({
            "student_id": "S001",
            "session_id": "SES01",
            "status": status,
        })

    def test_record_create_invalid_status(self):
        with pytest.raises(ValidationError, match="Invalid status.*tardy"):
            validate_attendance_record_create({
                "student_id": "S001",
                "session_id": "SES01",
                "status": "tardy",
            })

    def test_record_create_missing_student_id(self):
        with pytest.raises(ValidationError, match="Missing required fields.*student_id"):
            validate_attendance_record_create({
                "session_id": "SES01",
                "status": "present",
            })

    def test_record_create_missing_session_id(self):
        with pytest.raises(ValidationError, match="Missing required fields.*session_id"):
            validate_attendance_record_create({
                "student_id": "S001",
                "status": "present",
            })

    def test_record_create_missing_status(self):
        with pytest.raises(ValidationError, match="Missing required fields.*status"):
            validate_attendance_record_create({
                "student_id": "S001",
                "session_id": "SES01",
            })

    def test_record_create_case_sensitive_status(self):
        """Status comparison is exact (lowercase only)."""
        with pytest.raises(ValidationError, match="Invalid status.*Present"):
            validate_attendance_record_create({
                "student_id": "S001",
                "session_id": "SES01",
                "status": "Present",
            })


# ============================================================================
# Housing
# ============================================================================


class TestHousingValidators:
    """Tests for housing application create/update validators."""

    def test_application_create_valid(self):
        validate_housing_application_create({
            "student_id": "S001",
            "preferred_room_type": "single",
            "requested_move_in_date": "2026-09-01",
            "requested_duration_months": 12,
        })

    def test_application_create_duration_as_string(self):
        validate_housing_application_create({
            "student_id": "S001",
            "preferred_room_type": "double",
            "requested_move_in_date": "2026-09-01",
            "requested_duration_months": "6",
        })

    def test_application_create_missing_fields(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_housing_application_create({})

    def test_application_create_duration_not_integer(self):
        with pytest.raises(ValidationError, match="'requested_duration_months' must be an integer"):
            validate_housing_application_create({
                "student_id": "S001",
                "preferred_room_type": "single",
                "requested_move_in_date": "2026-09-01",
                "requested_duration_months": "abc",
            })

    def test_application_create_duration_zero(self):
        """Zero is falsy so _require_fields catches it as missing before the positivity check."""
        with pytest.raises(ValidationError, match="Missing required fields.*requested_duration_months"):
            validate_housing_application_create({
                "student_id": "S001",
                "preferred_room_type": "single",
                "requested_move_in_date": "2026-09-01",
                "requested_duration_months": 0,
            })

    def test_application_create_duration_negative(self):
        with pytest.raises(ValidationError, match="'requested_duration_months' must be positive"):
            validate_housing_application_create({
                "student_id": "S001",
                "preferred_room_type": "single",
                "requested_move_in_date": "2026-09-01",
                "requested_duration_months": -3,
            })

    # -- validate_housing_application_update --

    def test_application_update_valid(self):
        validate_housing_application_update({"preferred_room_type": "double"})

    def test_application_update_empty(self):
        with pytest.raises(ValidationError, match="No fields provided for update"):
            validate_housing_application_update({})

    @pytest.mark.parametrize("status", [
        "submitted", "under_review", "approved", "denied", "cancelled",
    ])
    def test_application_update_valid_statuses(self, status):
        validate_housing_application_update({"status": status})

    def test_application_update_invalid_status(self):
        with pytest.raises(ValidationError, match="Invalid status"):
            validate_housing_application_update({"status": "pending"})


# ============================================================================
# Academics -- modules, enrollments, grades, courses
# ============================================================================


class TestAcademicCoreValidators:
    """Tests for module, enrollment, grade, and course validators."""

    # -- modules --

    def test_module_create_valid(self):
        validate_module_create({"module_code": "CS101", "module_name": "Intro to CS"})

    def test_module_create_missing_code(self):
        with pytest.raises(ValidationError, match="Missing required fields.*module_code"):
            validate_module_create({"module_name": "Intro to CS"})

    def test_module_update_valid(self):
        validate_module_update({"module_name": "Advanced CS"})

    def test_module_update_empty(self):
        with pytest.raises(ValidationError, match="No fields provided for update"):
            validate_module_update({})

    # -- enrollments --

    def test_enrollment_create_valid(self):
        validate_enrollment_create({"student_id": "S001", "module_code": "CS101"})

    def test_enrollment_create_missing_student_id(self):
        with pytest.raises(ValidationError, match="Missing required fields.*student_id"):
            validate_enrollment_create({"module_code": "CS101"})

    # -- grades --

    def test_grade_create_with_score(self):
        validate_grade_create({"student_id": "S001", "score": 95})

    def test_grade_create_with_letter(self):
        validate_grade_create({"student_id": "S001", "letter_grade": "A"})

    def test_grade_create_with_both(self):
        validate_grade_create({"student_id": "S001", "score": 90, "letter_grade": "A"})

    def test_grade_create_missing_both_score_and_letter(self):
        with pytest.raises(
            ValidationError,
            match="At least one of 'score' or 'letter_grade' is required",
        ):
            validate_grade_create({"student_id": "S001"})

    def test_grade_create_missing_student_id(self):
        with pytest.raises(ValidationError, match="Missing required fields.*student_id"):
            validate_grade_create({"score": 90})

    def test_grade_update_valid(self):
        validate_grade_update({"score": 88})

    def test_grade_update_empty(self):
        with pytest.raises(ValidationError, match="No fields provided for update"):
            validate_grade_update({})

    # -- courses --

    def test_course_create_valid(self):
        validate_course_create({"course_code": "CS", "course_name": "Computer Science"})

    def test_course_create_missing(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_course_create({})

    def test_course_update_valid(self):
        validate_course_update({"course_name": "Updated"})

    def test_course_update_empty(self):
        with pytest.raises(ValidationError, match="No fields provided for update"):
            validate_course_update({})


# ============================================================================
# Assessments and calendar events
# ============================================================================


class TestAssessmentValidators:
    """Tests for assessment create/update validators."""

    def test_create_valid(self):
        validate_assessment_create({
            "assessment_name": "Midterm",
            "assessment_type": "exam",
            "module_code": "CS101",
            "max_points": 100,
            "weight": 30,
        })

    def test_create_weight_zero_boundary(self):
        """Zero is falsy so _require_fields catches it as missing before the range check."""
        with pytest.raises(ValidationError, match="Missing required fields.*weight"):
            validate_assessment_create({
                "assessment_name": "Bonus",
                "assessment_type": "extra",
                "module_code": "CS101",
                "max_points": 10,
                "weight": 0,
            })

    def test_create_weight_hundred_boundary(self):
        validate_assessment_create({
            "assessment_name": "Final",
            "assessment_type": "exam",
            "module_code": "CS101",
            "max_points": 100,
            "weight": 100,
        })

    def test_create_weight_as_string(self):
        validate_assessment_create({
            "assessment_name": "Quiz",
            "assessment_type": "quiz",
            "module_code": "CS101",
            "max_points": 20,
            "weight": "15.5",
        })

    def test_create_weight_not_a_number(self):
        with pytest.raises(ValidationError, match="'weight' must be a number"):
            validate_assessment_create({
                "assessment_name": "Quiz",
                "assessment_type": "quiz",
                "module_code": "CS101",
                "max_points": 20,
                "weight": "heavy",
            })

    def test_create_weight_negative(self):
        with pytest.raises(ValidationError, match="'weight' must be between 0 and 100"):
            validate_assessment_create({
                "assessment_name": "Quiz",
                "assessment_type": "quiz",
                "module_code": "CS101",
                "max_points": 20,
                "weight": -1,
            })

    def test_create_weight_over_hundred(self):
        with pytest.raises(ValidationError, match="'weight' must be between 0 and 100"):
            validate_assessment_create({
                "assessment_name": "Quiz",
                "assessment_type": "quiz",
                "module_code": "CS101",
                "max_points": 20,
                "weight": 101,
            })

    def test_create_missing_fields(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_assessment_create({})

    def test_update_valid(self):
        validate_assessment_update({"weight": 40})

    def test_update_empty(self):
        with pytest.raises(ValidationError, match="No fields provided for update"):
            validate_assessment_update({})


class TestCalendarEventValidators:
    """Tests for calendar event create validator with date logic."""

    def test_create_with_single_date(self):
        validate_calendar_event_create({
            "name": "Holiday",
            "event_type": "holiday",
            "date": "2026-12-25",
        })

    def test_create_with_date_range(self):
        validate_calendar_event_create({
            "name": "Exam Week",
            "event_type": "exam_period",
            "date_start": "2026-05-01",
            "date_end": "2026-05-10",
        })

    def test_create_with_both_single_and_range(self):
        """Having both date and date_start+date_end is acceptable."""
        validate_calendar_event_create({
            "name": "Special",
            "event_type": "other",
            "date": "2026-06-01",
            "date_start": "2026-06-01",
            "date_end": "2026-06-02",
        })

    def test_create_missing_dates_entirely(self):
        with pytest.raises(
            ValidationError,
            match="Either 'date' or both 'date_start' and 'date_end' are required",
        ):
            validate_calendar_event_create({
                "name": "Event",
                "event_type": "workshop",
            })

    def test_create_only_date_start_without_end(self):
        with pytest.raises(
            ValidationError,
            match="Either 'date' or both 'date_start' and 'date_end' are required",
        ):
            validate_calendar_event_create({
                "name": "Partial",
                "event_type": "meeting",
                "date_start": "2026-03-01",
            })

    def test_create_only_date_end_without_start(self):
        with pytest.raises(
            ValidationError,
            match="Either 'date' or both 'date_start' and 'date_end' are required",
        ):
            validate_calendar_event_create({
                "name": "Partial",
                "event_type": "meeting",
                "date_end": "2026-03-10",
            })

    def test_create_missing_name(self):
        with pytest.raises(ValidationError, match="Missing required fields.*name"):
            validate_calendar_event_create({
                "event_type": "holiday",
                "date": "2026-12-25",
            })

    def test_create_missing_event_type(self):
        with pytest.raises(ValidationError, match="Missing required fields.*event_type"):
            validate_calendar_event_create({
                "name": "Holiday",
                "date": "2026-12-25",
            })


# ============================================================================
# Misconduct
# ============================================================================


class TestMisconductValidators:
    """Tests for academic misconduct case creation."""

    def test_create_valid(self):
        validate_misconduct_case_create({
            "student_id": "S001",
            "student_name": "John Doe",
            "course": "CS101",
            "violation_type": "plagiarism",
            "severity": "Major",
        })

    @pytest.mark.parametrize("severity", ["Minor", "Moderate", "Major", "Severe"])
    def test_create_all_valid_severities(self, severity):
        validate_misconduct_case_create({
            "student_id": "S001",
            "student_name": "J D",
            "course": "CS101",
            "violation_type": "cheating",
            "severity": severity,
        })

    def test_create_invalid_severity(self):
        with pytest.raises(ValidationError, match="severity must be Minor, Moderate, Major, or Severe"):
            validate_misconduct_case_create({
                "student_id": "S001",
                "student_name": "J D",
                "course": "CS101",
                "violation_type": "cheating",
                "severity": "Critical",
            })

    def test_create_case_sensitive_severity(self):
        """Severity values are case-sensitive (capitalized)."""
        with pytest.raises(ValidationError, match="severity must be"):
            validate_misconduct_case_create({
                "student_id": "S001",
                "student_name": "J D",
                "course": "CS101",
                "violation_type": "cheating",
                "severity": "minor",
            })

    def test_create_missing_fields(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_misconduct_case_create({})


# ============================================================================
# Support tickets
# ============================================================================


class TestSupportTicketValidators:
    """Tests for support ticket creation."""

    def test_create_valid(self):
        validate_support_ticket_create({
            "title": "Issue",
            "description": "Details",
            "category": "IT",
            "priority": "medium",
        })

    @pytest.mark.parametrize("priority", ["low", "medium", "high", "critical"])
    def test_create_all_valid_priorities(self, priority):
        validate_support_ticket_create({
            "title": "Issue",
            "description": "Details",
            "category": "IT",
            "priority": priority,
        })

    def test_create_invalid_priority(self):
        with pytest.raises(ValidationError, match="priority must be low, medium, high, or critical"):
            validate_support_ticket_create({
                "title": "Issue",
                "description": "Details",
                "category": "IT",
                "priority": "urgent",
            })

    def test_create_missing_fields(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_support_ticket_create({})

    def test_create_missing_title(self):
        with pytest.raises(ValidationError, match="Missing required fields.*title"):
            validate_support_ticket_create({
                "description": "d",
                "category": "c",
                "priority": "low",
            })


# ============================================================================
# Maintenance requests
# ============================================================================


class TestMaintenanceRequestValidators:
    """Tests for maintenance request creation with priority validation."""

    def test_create_valid(self):
        validate_maintenance_request_create({
            "location_type": "building",
            "request_type": "repair",
            "priority": "high",
            "description": "Broken window",
            "reported_by": "U001",
        })

    @pytest.mark.parametrize("priority", ["low", "medium", "high", "urgent"])
    def test_create_all_valid_priorities(self, priority):
        validate_maintenance_request_create({
            "location_type": "room",
            "request_type": "cleaning",
            "priority": priority,
            "description": "desc",
            "reported_by": "U002",
        })

    def test_create_case_insensitive_priority(self):
        """Priority check uses .lower(), so mixed case is accepted."""
        validate_maintenance_request_create({
            "location_type": "room",
            "request_type": "repair",
            "priority": "High",
            "description": "desc",
            "reported_by": "U001",
        })

    def test_create_invalid_priority(self):
        with pytest.raises(ValidationError, match="Invalid priority"):
            validate_maintenance_request_create({
                "location_type": "room",
                "request_type": "repair",
                "priority": "critical",
                "description": "desc",
                "reported_by": "U001",
            })

    def test_create_missing_fields(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_maintenance_request_create({})


# ============================================================================
# Notifications
# ============================================================================


class TestNotificationValidators:
    """Tests for notification creation with priority validation."""

    def test_create_valid(self):
        validate_notification_create({
            "user_id": "U001",
            "channel": "email",
            "priority": "normal",
            "title": "Reminder",
            "message": "Your exam is tomorrow.",
        })

    @pytest.mark.parametrize("priority", ["low", "normal", "high", "urgent"])
    def test_create_all_valid_priorities(self, priority):
        validate_notification_create({
            "user_id": "U001",
            "channel": "sms",
            "priority": priority,
            "title": "Alert",
            "message": "msg",
        })

    def test_create_case_insensitive_priority(self):
        """Priority check uses .lower(), so mixed case is accepted."""
        validate_notification_create({
            "user_id": "U001",
            "channel": "push",
            "priority": "HIGH",
            "title": "Alert",
            "message": "msg",
        })

    def test_create_invalid_priority(self):
        with pytest.raises(ValidationError, match="Invalid priority"):
            validate_notification_create({
                "user_id": "U001",
                "channel": "email",
                "priority": "critical",
                "title": "Alert",
                "message": "msg",
            })

    def test_create_missing_fields(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_notification_create({})


# ============================================================================
# Feedback
# ============================================================================


class TestFeedbackValidators:
    """Tests for feedback creation with type validation."""

    def test_create_valid_feedback(self):
        validate_feedback_create({
            "category_id": "C1",
            "type": "feedback",
            "title": "Great service",
            "description": "Very helpful",
        })

    def test_create_valid_suggestion(self):
        validate_feedback_create({
            "category_id": "C1",
            "type": "suggestion",
            "title": "Add feature",
            "description": "Please add X",
        })

    def test_create_invalid_type(self):
        with pytest.raises(ValidationError, match="type must be feedback or suggestion"):
            validate_feedback_create({
                "category_id": "C1",
                "type": "complaint",
                "title": "Bad",
                "description": "desc",
            })

    def test_create_missing_fields(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_feedback_create({})


# ============================================================================
# Assignments & submissions
# ============================================================================


class TestAssignmentValidators:
    """Tests for assignment and submission validators."""

    def test_assignment_create_valid(self):
        validate_assignment_create({
            "module_code": "CS101",
            "title": "HW1",
            "due_date": "2026-03-01",
        })

    def test_assignment_create_missing(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_assignment_create({})

    def test_assignment_update_valid(self):
        validate_assignment_update({"title": "HW2"})

    def test_assignment_update_empty(self):
        with pytest.raises(ValidationError, match="No fields provided for update"):
            validate_assignment_update({})

    def test_submission_create_valid(self):
        validate_submission_create({"student_id": "S001"})

    def test_submission_create_missing_student_id(self):
        with pytest.raises(ValidationError, match="Missing required fields.*student_id"):
            validate_submission_create({})


# ============================================================================
# Exams
# ============================================================================


class TestExamValidators:
    """Tests for exam create/update validators."""

    def test_create_valid(self):
        validate_exam_create({
            "module_code": "CS101",
            "date": "2026-05-15",
            "start_time": "09:00",
            "end_time": "11:00",
        })

    def test_create_missing_fields(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_exam_create({})

    def test_update_valid(self):
        validate_exam_update({"date": "2026-05-20"})

    def test_update_empty(self):
        with pytest.raises(ValidationError, match="No fields provided for update"):
            validate_exam_update({})


# ============================================================================
# Library
# ============================================================================


class TestLibraryValidators:
    """Tests for book loan and reservation validators."""

    def test_loan_create_valid(self):
        validate_book_loan_create({
            "book_id": "B001",
            "user_id": "U001",
            "due_date": "2026-04-01",
        })

    def test_loan_create_missing(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_book_loan_create({})

    def test_reservation_create_valid(self):
        validate_book_reservation_create({"book_id": "B001", "user_id": "U001"})

    def test_reservation_create_missing(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_book_reservation_create({})


# ============================================================================
# Health & counseling
# ============================================================================


class TestHealthValidators:
    """Tests for health, counseling, and mental health appointment validators."""

    def test_health_appointment_valid(self):
        validate_health_appointment_create({
            "student_id": "S001",
            "appointment_type": "checkup",
            "appointment_date": "2026-03-01",
            "appointment_time": "10:00",
        })

    def test_health_appointment_missing(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_health_appointment_create({})

    def test_mental_health_appointment_valid(self):
        validate_mental_health_appointment_create({
            "student_id": "S001",
            "appointment_type": "therapy",
            "appointment_date": "2026-03-01",
            "appointment_time": "14:00",
        })

    def test_mental_health_appointment_missing(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_mental_health_appointment_create({})

    def test_counseling_appointment_valid(self):
        validate_counseling_appointment_create({
            "student_id": "S001",
            "appointment_date": "2026-03-01",
            "appointment_time": "11:00",
        })

    def test_counseling_appointment_missing(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_counseling_appointment_create({})


# ============================================================================
# Facilities & parking
# ============================================================================


class TestFacilityValidators:
    """Tests for facility booking, parking, and vehicle validators."""

    def test_facility_booking_valid(self):
        validate_facility_booking_create({
            "facility_name": "Gym",
            "booking_date": "2026-03-01",
            "start_time": "08:00",
            "end_time": "10:00",
            "purpose": "Practice",
        })

    def test_facility_booking_missing(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_facility_booking_create({})

    def test_parking_permit_valid(self):
        validate_parking_permit_create({
            "user_id": "U001",
            "zone": "A",
            "permit_type": "annual",
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
        })

    def test_parking_permit_missing(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_parking_permit_create({})

    def test_vehicle_create_valid(self):
        validate_vehicle_create({"license_plate": "ABC123", "owner_id": "U001"})

    def test_vehicle_create_missing(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_vehicle_create({})

    def test_room_booking_valid(self):
        validate_room_booking_create({
            "room_id": "R101",
            "booking_type": "class",
            "start_datetime": "2026-03-01T09:00",
            "end_datetime": "2026-03-01T10:00",
        })

    def test_room_booking_missing(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_room_booking_create({})

    def test_resource_booking_valid(self):
        validate_resource_booking_create({
            "resource_id": "RES01",
            "start_time": "09:00",
            "end_time": "10:00",
        })

    def test_resource_booking_missing(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_resource_booking_create({})


# ============================================================================
# Jobs & career
# ============================================================================


class TestJobValidators:
    """Tests for job posting and application validators."""

    def test_job_posting_valid(self):
        validate_job_posting_create({
            "company_name": "Acme",
            "job_title": "Developer",
            "job_description": "Write code",
        })

    def test_job_posting_missing(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_job_posting_create({})

    def test_job_application_valid(self):
        validate_job_application_create({"job_id": "J001", "applicant_id": "S001"})

    def test_job_application_missing(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_job_application_create({})


# ============================================================================
# Research
# ============================================================================


class TestResearchValidators:
    """Tests for research project and publication validators."""

    def test_project_create_valid(self):
        validate_research_project_create({
            "project_title": "AI Ethics",
            "principal_investigator_id": "PI001",
            "department": "CS",
            "project_type": "funded",
            "start_date": "2026-01-01",
        })

    def test_project_create_missing(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_research_project_create({})

    def test_publication_create_valid(self):
        validate_research_publication_create({
            "title": "Paper",
            "authors": "J. Doe",
            "publication_type": "journal",
        })

    def test_publication_create_missing(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_research_publication_create({})


# ============================================================================
# Admissions & events
# ============================================================================


class TestAdmissionsAndEventsValidators:
    """Tests for admissions, events, and campus tours."""

    def test_admission_application_valid(self):
        validate_admission_application_create({
            "prospect_id": "P001",
            "application_type": "undergraduate",
            "program_applied": "CS",
            "academic_year": "2026-2027",
            "semester": "Fall",
        })

    def test_admission_application_missing(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_admission_application_create({})

    def test_event_create_valid(self):
        validate_event_create({
            "title": "Open Day",
            "category": "admissions",
            "start_datetime": "2026-03-01T09:00",
            "end_datetime": "2026-03-01T17:00",
            "location": "Main Hall",
        })

    def test_event_create_missing(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_event_create({})

    def test_event_registration_valid(self):
        validate_event_registration_create({"event_id": "E001"})

    def test_event_registration_missing(self):
        with pytest.raises(ValidationError, match="Missing required fields.*event_id"):
            validate_event_registration_create({})

    def test_campus_tour_valid(self):
        validate_campus_tour_create({
            "tour_date": "2026-04-01",
            "tour_time": "10:00",
        })

    def test_campus_tour_missing(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_campus_tour_create({})


# ============================================================================
# Mentoring
# ============================================================================


class TestMentoringValidators:
    """Tests for mentorship and mentorship session validators."""

    def test_mentorship_create_valid(self):
        validate_mentorship_create({
            "mentor_id": "M001",
            "mentee_id": "S001",
            "skill_area": "Python",
        })

    def test_mentorship_create_missing(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_mentorship_create({})

    def test_session_create_valid(self):
        validate_mentorship_session_create({
            "relationship_id": "R001",
            "session_date": "2026-03-15",
            "duration_minutes": 60,
        })

    def test_session_create_missing(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_mentorship_session_create({})


# ============================================================================
# Clubs & student organisations
# ============================================================================


class TestClubValidators:
    """Tests for club and club member validators."""

    def test_club_create_valid(self):
        validate_club_create({"club_name": "Chess Club"})

    def test_club_create_missing(self):
        with pytest.raises(ValidationError, match="Missing required fields.*club_name"):
            validate_club_create({})

    def test_club_member_create_valid(self):
        validate_club_member_create({"club_id": "C001", "student_id": "S001"})

    def test_club_member_create_missing(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_club_member_create({})


# ============================================================================
# Security & lost-and-found
# ============================================================================


class TestSecurityValidators:
    """Tests for security ticket, lost/found, incident validators."""

    def test_security_ticket_valid(self):
        validate_security_ticket_create({
            "type": "access",
            "subject": "Card issue",
            "description": "My card doesn't work",
        })

    def test_security_ticket_missing(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_security_ticket_create({})

    def test_lost_found_valid(self):
        validate_lost_found_create({
            "item_description": "Blue backpack",
            "found_date": "2026-02-20",
        })

    def test_lost_found_missing(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_lost_found_create({})

    def test_incident_create_valid(self):
        validate_incident_create({
            "incident_type": "theft",
            "description": "Laptop stolen from library",
            "incident_datetime": "2026-02-20T14:00",
        })

    def test_incident_create_missing(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_incident_create({})


# ============================================================================
# Scholarships
# ============================================================================


class TestScholarshipValidators:
    """Tests for scholarship application validators."""

    def test_create_valid(self):
        validate_scholarship_application_create({
            "student_id": "S001",
            "scholarship_id": "SCH001",
        })

    def test_create_missing(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_scholarship_application_create({})


# ============================================================================
# Study groups
# ============================================================================


class TestStudyGroupValidators:
    """Tests for study group creation."""

    def test_create_valid(self):
        validate_study_group_create({
            "course_id": "C001",
            "group_name": "Team Alpha",
            "creator_id": "S001",
        })

    def test_create_missing(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_study_group_create({})


# ============================================================================
# Alumni
# ============================================================================


class TestAlumniValidators:
    """Tests for alumni update validator."""

    def test_update_valid(self):
        validate_alumni_update({"company": "Acme Corp"})

    def test_update_empty(self):
        with pytest.raises(ValidationError, match="No fields provided for update"):
            validate_alumni_update({})

    def test_update_valid_email(self):
        validate_alumni_update({"email_address": "alumni@example.com"})

    def test_update_invalid_email(self):
        with pytest.raises(ValidationError, match="Invalid email address"):
            validate_alumni_update({"email_address": "bad-email"})


# ============================================================================
# Degree programs & prerequisites
# ============================================================================


class TestDegreeProgramValidators:
    """Tests for degree program and prerequisite validators."""

    def test_degree_program_create_valid(self):
        validate_degree_program_create({
            "program_code": "BSCS",
            "program_name": "Computer Science",
            "degree_type": "Bachelor",
            "total_credits_required": 120,
        })

    def test_degree_program_create_missing(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_degree_program_create({})

    def test_degree_program_update_valid(self):
        validate_degree_program_update({"program_name": "Updated Name"})

    def test_degree_program_update_empty(self):
        with pytest.raises(ValidationError, match="No fields provided for update"):
            validate_degree_program_update({})

    def test_prerequisite_create_valid(self):
        validate_prerequisite_create({
            "course_id": "CS201",
            "prerequisite_course_id": "CS101",
        })

    def test_prerequisite_create_missing(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_prerequisite_create({})


# ============================================================================
# Announcements
# ============================================================================


class TestAnnouncementValidators:
    """Tests for announcement create/update validators."""

    def test_create_valid(self):
        validate_announcement_create({
            "title": "Welcome",
            "content": "Welcome to the semester",
            "target_audience": "all",
            "start_date": "2026-01-15",
        })

    def test_create_missing(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_announcement_create({})

    def test_update_valid(self):
        validate_announcement_update({"title": "Updated"})

    def test_update_empty(self):
        with pytest.raises(ValidationError, match="No fields provided for update"):
            validate_announcement_update({})


# ============================================================================
# Advising & accommodation requests
# ============================================================================


class TestAdvisingValidators:
    """Tests for advising appointment and accommodation request validators."""

    def test_advising_appointment_valid(self):
        validate_advising_appointment_create({
            "student_id": "S001",
            "advisor_id": "A001",
            "appointment_date": "2026-03-10",
            "appointment_time": "14:00",
            "appointment_type": "academic",
        })

    def test_advising_appointment_missing(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_advising_appointment_create({})

    def test_accommodation_request_valid(self):
        validate_accommodation_request_create({
            "student_id": "S001",
            "accommodation_type": "extra_time",
        })

    def test_accommodation_request_missing(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_accommodation_request_create({})


# ============================================================================
# Tutoring & chat
# ============================================================================


class TestTutoringChatValidators:
    """Tests for tutoring offer, chat room, and chat message validators."""

    def test_tutoring_offer_valid(self):
        validate_tutoring_offer_create({"tutor_id": "T001", "subject": "Math"})

    def test_tutoring_offer_missing(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_tutoring_offer_create({})

    def test_chat_room_valid(self):
        validate_chat_room_create({"name": "Study Room", "room_type": "group"})

    def test_chat_room_missing(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_chat_room_create({})

    def test_chat_message_valid(self):
        validate_chat_message_create({"room_id": "R001", "content": "Hello"})

    def test_chat_message_missing(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_chat_message_create({})


# ============================================================================
# HR / staff -- leave, shifts, timesheets
# ============================================================================


class TestStaffHRValidators:
    """Tests for leave request, shift, and timesheet validators."""

    def test_leave_request_valid(self):
        validate_leave_request_create({
            "user_id": "U001",
            "leave_type_id": "LT01",
            "start_date": "2026-04-01",
            "end_date": "2026-04-05",
            "total_days": 5,
        })

    def test_leave_request_missing(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_leave_request_create({})

    def test_shift_create_valid(self):
        validate_shift_create({
            "staff_id": "ST001",
            "shift_date": "2026-03-01",
            "start_time": "08:00",
            "end_time": "16:00",
        })

    def test_shift_create_missing(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_shift_create({})

    def test_timesheet_create_valid(self):
        validate_timesheet_create({
            "user_id": "U001",
            "week_start": "2026-03-02",
            "week_end": "2026-03-08",
        })

    def test_timesheet_create_missing(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_timesheet_create({})


# ============================================================================
# Support -- tickets, KB, FAQ
# ============================================================================


class TestSupportKBFAQValidators:
    """Tests for ticket reply, KB article, and FAQ validators."""

    def test_ticket_reply_valid(self):
        validate_ticket_reply_create({"message": "Thanks for your report."})

    def test_ticket_reply_missing(self):
        with pytest.raises(ValidationError, match="Missing required fields.*message"):
            validate_ticket_reply_create({})

    def test_kb_article_valid(self):
        validate_kb_article_create({
            "title": "How to Reset Password",
            "content": "Go to settings...",
            "category": "IT",
        })

    def test_kb_article_missing(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_kb_article_create({})

    def test_faq_valid(self):
        validate_faq_create({
            "question": "How do I enroll?",
            "answer": "Visit the portal.",
            "category": "Enrollment",
        })

    def test_faq_missing(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_faq_create({})


# ============================================================================
# Parent portal
# ============================================================================


class TestParentPortalValidators:
    """Tests for parent message and conference validators."""

    def test_message_valid(self):
        validate_parent_message_create({
            "parent_id": "P001",
            "message_content": "Question about grades",
        })

    def test_message_missing(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_parent_message_create({})

    def test_conference_valid(self):
        validate_parent_conference_create({
            "parent_id": "P001",
            "teacher_id": "T001",
            "datetime": "2026-03-15T10:00",
        })

    def test_conference_missing(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_parent_conference_create({})


# ============================================================================
# LMS
# ============================================================================


class TestLMSValidators:
    """Tests for LMS course, quiz, and forum validators."""

    def test_lms_course_valid(self):
        validate_lms_course_create({"module_code": "CS101", "instructor_id": "I001"})

    def test_lms_course_missing(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_lms_course_create({})

    def test_lms_quiz_valid(self):
        validate_lms_quiz_create({"lms_course_id": "LC01", "title": "Quiz 1"})

    def test_lms_quiz_missing(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_lms_quiz_create({})

    def test_lms_forum_valid(self):
        validate_lms_forum_create({"lms_course_id": "LC01", "topic": "Intro Discussion"})

    def test_lms_forum_missing(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_lms_forum_create({})


# ============================================================================
# Emergency
# ============================================================================


class TestEmergencyValidators:
    """Tests for emergency alert and contact validators."""

    def test_alert_valid(self):
        validate_emergency_alert_create({
            "alert_title": "Evacuation",
            "alert_message": "Please evacuate building B.",
            "alert_type": "fire",
        })

    def test_alert_missing(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_emergency_alert_create({})

    def test_contact_valid(self):
        validate_emergency_contact_create({
            "student_id": "S001",
            "contact_name": "Jane Doe",
            "relationship": "Mother",
            "phone_primary": "+1234567890",
        })

    def test_contact_missing(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_emergency_contact_create({})


# ============================================================================
# Virtual classrooms
# ============================================================================


class TestVirtualClassroomValidators:
    """Tests for virtual classroom and session validators."""

    def test_classroom_create_valid(self):
        validate_virtual_classroom_create({
            "session_name": "Lecture 1",
            "instructor_id": "I001",
            "platform": "Zoom",
        })

    def test_classroom_create_missing(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_virtual_classroom_create({})

    def test_session_create_valid(self):
        validate_virtual_session_create({
            "classroom_id": "VC01",
            "start_time": "2026-03-01T09:00",
        })

    def test_session_create_missing(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_virtual_session_create({})


# ============================================================================
# Equipment
# ============================================================================


class TestEquipmentValidators:
    """Tests for equipment checkout and maintenance validators."""

    def test_checkout_valid(self):
        validate_equipment_checkout_create({
            "equipment_id": "EQ01",
            "borrower_id": "U001",
            "checkout_date": "2026-03-01",
            "expected_return": "2026-03-15",
        })

    def test_checkout_missing(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_equipment_checkout_create({})

    def test_maintenance_valid(self):
        validate_equipment_maintenance_create({
            "item_id": "EQ01",
            "maintenance_type": "preventive",
            "performed_date": "2026-02-28",
        })

    def test_maintenance_missing(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_equipment_maintenance_create({})


# ============================================================================
# Polls & elections
# ============================================================================


class TestPollElectionValidators:
    """Tests for poll and election candidate validators."""

    def test_poll_valid(self):
        validate_poll_create({
            "title": "Best Cafeteria Food",
            "start_date": "2026-03-01",
            "end_date": "2026-03-15",
        })

    def test_poll_missing(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_poll_create({})

    def test_election_candidate_valid(self):
        validate_election_candidate_create({
            "election_id": "EL01",
            "student_id": "S001",
        })

    def test_election_candidate_missing(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_election_candidate_create({})


# ============================================================================
# Documents, credentials, badges, certifications
# ============================================================================


class TestDocumentCredentialValidators:
    """Tests for document, credential, badge, and certification validators."""

    def test_document_valid(self):
        validate_document_create({"title": "Transcript", "content": "..."})

    def test_document_missing(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_document_create({})

    def test_credential_valid(self):
        validate_credential_create({
            "student_id": "S001",
            "credential_type": "diploma",
            "credential_name": "BS Computer Science",
            "issue_date": "2026-06-15",
            "blockchain_hash": "0xabc123",
        })

    def test_credential_missing(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_credential_create({})

    def test_badge_valid(self):
        validate_badge_create({
            "badge_name": "Dean's List",
            "criteria": "GPA > 3.5",
            "issuer_name": "University",
        })

    def test_badge_missing(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_badge_create({})

    def test_certification_valid(self):
        validate_certification_create({"user_id": "U001", "name": "AWS Certified"})

    def test_certification_missing(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_certification_create({})


# ============================================================================
# Communication -- messages, newsletters, course evaluations
# ============================================================================


class TestCommunicationValidators:
    """Tests for message, newsletter, and course evaluation validators."""

    def test_message_valid(self):
        validate_message_create({"recipient_id": "U002", "subject": "Hello"})

    def test_message_missing(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_message_create({})

    def test_newsletter_valid(self):
        validate_newsletter_create({"title": "Monthly Update", "content": "..."})

    def test_newsletter_missing(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_newsletter_create({})

    def test_course_evaluation_valid(self):
        validate_course_evaluation_create({
            "module_code": "CS101",
            "academic_year": "2025-2026",
            "semester": "Fall",
            "instructor_id": "I001",
            "template_id": "TPL01",
            "start_date": "2026-05-01",
            "end_date": "2026-05-15",
        })

    def test_course_evaluation_missing(self):
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_course_evaluation_create({})
