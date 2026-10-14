"""Horizontal object-scope regression tests for university API boundaries."""

from flask import Flask, g, jsonify

from education_system.platform.delivery.api.university.auth import (
    authorize_object,
)


def _app(user):
    app = Flask(__name__)

    @app.get('/student/<student_id>')
    def student(student_id):
        g.current_user = user
        denied = authorize_object(student_id)
        if denied is not None:
            return denied
        return jsonify(ok=True)

    return app


def test_student_cannot_read_another_students_record():
    client = _app({'sub': 'student-a', 'user_id': 1, 'role': 'student'}).test_client()
    assert client.get('/student/student-b').status_code == 403


def test_student_can_read_own_record():
    client = _app({'sub': 'student-a', 'user_id': 1, 'role': 'student'}).test_client()
    assert client.get('/student/student-a').status_code == 200


def test_unknown_role_is_denied_even_with_matching_subject():
    client = _app({'sub': 'student-a', 'user_id': 1, 'role': 'unknown'}).test_client()
    assert client.get('/student/student-a').status_code == 403


# ---------------------------------------------------------------------------
# Object-scope ratchet
#
# Any route whose URL carries a resource identifier must make an authorization
# decision, not merely authenticate. Without one, an authenticated caller can
# substitute another id in the path and reach a record that is not theirs.
#
# KNOWN_UNSCOPED is the allow-list of routes that still need this work. It is a
# ratchet: a newly added unscoped route fails the test, and an entry that has
# since been fixed must be deleted from the list. The list can only shrink.
#
# To clear an entry, add the right check for the route and remove the line:
#   * the path id IS the owner   -> @scoped_to("student_id") under @token_required
#   * staff-internal record      -> @staff_required(permission=...)
#   * path id is a resource id   -> fetch the row, then
#                                   deny_unless_owner_or_staff(row["student_id"])
# ---------------------------------------------------------------------------

import ast
import os
import re

from education_system import paths

_UNIVERSITY = paths.SRC_ROOT / "education_system" / "systems" / "university"

_AUTHZ_PRIMITIVES = frozenset({
    "authorize_object", "scoped_to", "staff_required", "require_staff",
    "deny_unless_owner_or_staff", "check_permission", "has_permission",
    "require_permission", "admin_required", "role_required", "require_role",
})
_ROUTE_DECORATOR = re.compile(r"\.(route|get|post|put|patch|delete)\(")
_PATH_PARAM = re.compile(r"<(?:int:|string:|path:)?([A-Za-z_][A-Za-z0-9_]*)>")


def _authz_names(tree, src):
    """Names that constitute an authorization decision in this module.

    Seeded with the shared primitives plus any local helper that can emit a
    403 — several route modules wrap the decision in their own
    ``_authorize_*`` / ``_is_staff`` helper rather than calling a primitive
    directly, and those count.
    """
    names = set(_AUTHZ_PRIMITIVES)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            body = ast.get_source_segment(src, node) or ""
            if "403" in body or "Forbidden" in body:
                names.add(node.name)
    for _ in range(5):
        grew = False
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name in names:
                continue
            body = ast.get_source_segment(src, node) or ""
            if any(re.search(rf"\b{re.escape(n)}\b", body) for n in names):
                names.add(node.name)
                grew = True
        if not grew:
            break
    return names


def _unscoped_routes():
    """Every id-bearing route that makes no authorization decision."""
    found = set()
    for root, _dirs, files in os.walk(_UNIVERSITY):
        posix = root.replace(os.sep, "/")
        if "interfaces/api" not in posix and "/api/" not in posix:
            continue
        for name in files:
            if not name.endswith(".py"):
                continue
            path = os.path.join(root, name)
            src = open(path, encoding="utf-8", errors="replace").read()
            try:
                tree = ast.parse(src)
            except SyntaxError:
                continue
            authz = _authz_names(tree, src)
            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                decorators = [ast.unparse(d) for d in node.decorator_list]
                routes = [d for d in decorators if _ROUTE_DECORATOR.search(d)]
                if not routes or not _PATH_PARAM.findall(routes[0]):
                    continue
                body = ast.get_source_segment(src, node) or ""
                decided = any(
                    re.search(rf"\b{re.escape(n)}\b", body) for n in authz
                ) or any(
                    any(re.search(rf"\b{re.escape(n)}\b", d) for n in authz)
                    for d in decorators
                )
                if not decided:
                    rel = os.path.relpath(path, _UNIVERSITY).replace(os.sep, "/")
                    found.add((rel, node.name))
    return found


KNOWN_UNSCOPED: set[tuple[str, str]] = {
    ("domains/academics/interfaces/api/academics_domain_routes.py", "get_program"),
    ("domains/academics/interfaces/api/assignment_routes.py", "get_assignment"),
    ("domains/academics/interfaces/api/calendar_routes.py", "get_event"),
    ("domains/academics/interfaces/api/collaborative_provision_routes.py", "get_agreement"),
    ("domains/academics/interfaces/api/collaborative_provision_routes.py", "get_partner"),
    ("domains/academics/interfaces/api/collaborative_provision_routes.py", "update_agreement"),
    ("domains/academics/interfaces/api/collaborative_provision_routes.py", "update_cohort"),
    ("domains/academics/interfaces/api/collaborative_provision_routes.py", "update_partner"),
    ("domains/academics/interfaces/api/course_planning_routes.py", "check_eligibility"),
    ("domains/academics/interfaces/api/course_planning_routes.py", "detect_schedule_conflicts"),
    ("domains/academics/interfaces/api/course_planning_routes.py", "get_planned_course"),
    ("domains/academics/interfaces/api/course_planning_routes.py", "get_prerequisite"),
    ("domains/academics/interfaces/api/course_planning_routes.py", "get_prerequisite_chain"),
    ("domains/academics/interfaces/api/course_planning_routes.py", "get_prerequisite_tree"),
    ("domains/academics/interfaces/api/course_planning_routes.py", "get_semester_plan"),
    ("domains/academics/interfaces/api/course_routes.py", "course_waitlist"),
    ("domains/academics/interfaces/api/course_routes.py", "get_course"),
    ("domains/academics/interfaces/api/course_routes.py", "update_course"),
    ("domains/academics/interfaces/api/degree_routes.py", "get_program"),
    ("domains/academics/interfaces/api/degree_routes.py", "list_requirements"),
    ("domains/academics/interfaces/api/evaluation_routes.py", "get_template"),
    ("domains/academics/interfaces/api/exam_routes.py", "get_exam"),
    ("domains/academics/interfaces/api/exam_routes.py", "list_accommodations"),
    ("domains/academics/interfaces/api/exam_routes.py", "update_exam"),
    ("domains/academics/interfaces/api/library_routes.py", "get_book"),
    ("domains/academics/interfaces/api/lms_routes.py", "get_course"),
    ("domains/academics/interfaces/api/lms_routes.py", "list_forums"),
    ("domains/academics/interfaces/api/lms_routes.py", "list_quizzes"),
    ("domains/academics/interfaces/api/lms_routes.py", "update_course"),
    ("domains/academics/interfaces/api/module_routes.py", "delete_module"),
    ("domains/academics/interfaces/api/module_routes.py", "get_module"),
    ("domains/academics/interfaces/api/module_routes.py", "update_module"),
    ("domains/academics/interfaces/api/office_hours_routes.py", "book_office_hour"),
    ("domains/academics/interfaces/api/office_hours_routes.py", "cancel_booking"),
    ("domains/academics/interfaces/api/office_hours_routes.py", "delete_office_hours"),
    ("domains/academics/interfaces/api/office_hours_routes.py", "get_office_hour"),
    ("domains/academics/interfaces/api/office_hours_routes.py", "update_office_hours"),
    ("domains/academics/interfaces/api/research_routes.py", "get_project"),
    ("domains/academics/interfaces/api/research_routes.py", "update_project"),
    ("domains/academics/interfaces/api/student_mobility_routes.py", "add_learning_agreement_line"),
    ("domains/academics/interfaces/api/student_mobility_routes.py", "get_placement"),
    ("domains/academics/interfaces/api/student_mobility_routes.py", "learning_agreement"),
    ("domains/academics/interfaces/api/student_mobility_routes.py", "list_recognitions"),
    ("domains/academics/interfaces/api/student_mobility_routes.py", "record_recognition"),
    ("domains/academics/interfaces/api/student_mobility_routes.py", "set_placement_status"),
    ("domains/academics/interfaces/api/student_mobility_routes.py", "sign_learning_agreement"),
    ("domains/academics/interfaces/api/student_mobility_routes.py", "update_agreement"),
    ("domains/academics/interfaces/api/student_mobility_routes.py", "update_placement"),
    ("domains/academics/interfaces/api/study_group_routes.py", "add_member"),
    ("domains/academics/interfaces/api/study_group_routes.py", "get_group"),
    ("domains/academics/interfaces/api/study_group_routes.py", "list_members"),
    ("domains/academics/interfaces/api/study_group_routes.py", "update_group"),
    ("domains/academics/interfaces/api/study_matching_routes.py", "get_group"),
    ("domains/academics/interfaces/api/study_matching_routes.py", "get_profile"),
    ("domains/academics/interfaces/api/study_matching_routes.py", "get_question"),
    ("domains/academics/interfaces/api/study_matching_routes.py", "get_virtual_room"),
    ("domains/academics/interfaces/api/study_recommendation_routes.py", "complete_recommendation"),
    ("domains/academics/interfaces/api/study_recommendation_routes.py", "get_recommendation"),
    ("domains/academics/interfaces/api/study_recommendation_routes.py", "get_session"),
    ("domains/academics/interfaces/api/ta_routes.py", "get_ta"),
    ("domains/academics/interfaces/api/ta_routes.py", "get_tas_for_module"),
    ("domains/academics/interfaces/api/ta_routes.py", "remove_ta"),
    ("domains/academics/interfaces/api/ta_routes.py", "set_ta_permissions"),
    ("domains/academics/interfaces/api/ta_routes.py", "update_ta"),
    ("domains/academics/interfaces/api/timetable_routes.py", "module_schedule"),
    ("domains/academics/interfaces/api/virtual_classroom_routes.py", "get_classroom"),
    ("domains/academics/interfaces/api/virtual_classroom_routes.py", "list_recordings"),
    ("domains/academics/interfaces/api/virtual_classroom_routes.py", "list_sessions"),
    ("domains/admissions/interfaces/api/admission_routes.py", "accept_application_choice"),
    ("domains/admissions/interfaces/api/admission_routes.py", "application_readiness"),
    ("domains/admissions/interfaces/api/admission_routes.py", "get_application_lifecycle"),
    ("domains/admissions/interfaces/api/admissions_crm_routes.py", "get_prospect"),
    ("domains/admissions/interfaces/api/admissions_crm_routes.py", "get_tour"),
    ("domains/admissions/interfaces/api/clearing_adjustment_routes.py", "get_adjustment"),
    ("domains/admissions/interfaces/api/clearing_adjustment_routes.py", "get_application"),
    ("domains/admissions/interfaces/api/clearing_adjustment_routes.py", "get_vacancy"),
    ("domains/admissions/interfaces/api/clearing_adjustment_routes.py", "process_adjustment"),
    ("domains/admissions/interfaces/api/clearing_adjustment_routes.py", "update_application_status"),
    ("domains/admissions/interfaces/api/clearing_adjustment_routes.py", "update_vacancy"),
    ("domains/assessment/interfaces/api/assessment_routes.py", "get_assessment"),
    ("domains/assessment/interfaces/api/assessment_routes.py", "update_assessment"),
    ("domains/assessment/interfaces/api/external_examiner_routes.py", "get_action"),
    ("domains/assessment/interfaces/api/external_examiner_routes.py", "get_examiner"),
    ("domains/assessment/interfaces/api/external_examiner_routes.py", "get_examiner_history"),
    ("domains/assessment/interfaces/api/external_examiner_routes.py", "get_visit"),
    ("domains/assessment/interfaces/api/external_examiner_routes.py", "record_findings"),
    ("domains/assessment/interfaces/api/external_examiner_routes.py", "update_action_status"),
    ("domains/assessment/interfaces/api/external_examiner_routes.py", "update_examiner"),
    ("domains/finance/interfaces/api/blockchain_routes.py", "get_badge"),
    ("domains/finance/interfaces/api/blockchain_routes.py", "get_credential"),
    ("domains/finance/interfaces/api/blockchain_routes.py", "verify_credential_by_id"),
    ("domains/finance/interfaces/api/blockchain_routes.py", "verify_credential_hash"),
    ("domains/finance/interfaces/api/financial_aid_routes.py", "get_package"),
    ("domains/finance/interfaces/api/financial_aid_routes.py", "list_installments"),
    ("domains/finance/interfaces/api/financial_aid_routes.py", "update_package"),
    ("domains/finance/interfaces/api/scholarship_finder_routes.py", "get_application"),
    ("domains/finance/interfaces/api/scholarship_finder_routes.py", "get_opportunitie"),
    ("domains/finance/interfaces/api/scholarship_routes.py", "get_scholarship"),
    ("domains/governance/interfaces/api/hesa_export_routes.py", "generate_xml_export"),
    ("domains/governance/interfaces/api/hesa_export_routes.py", "get_return"),
    ("domains/governance/interfaces/api/hesa_export_routes.py", "get_submission_log"),
    ("domains/governance/interfaces/api/hesa_export_routes.py", "log_submission_action"),
    ("domains/governance/interfaces/api/hesa_export_routes.py", "update_return_status"),
    ("domains/governance/interfaces/api/legal_routes.py", "cancel_consultation"),
    ("domains/governance/interfaces/api/legal_routes.py", "close_dispute"),
    ("domains/governance/interfaces/api/legal_routes.py", "get_case"),
    ("domains/governance/interfaces/api/legal_routes.py", "get_consultation"),
    ("domains/governance/interfaces/api/legal_routes.py", "get_document"),
    ("domains/governance/interfaces/api/legal_routes.py", "update_agreement_status"),
    ("domains/governance/interfaces/api/legal_routes.py", "update_consultation"),
    ("domains/learners/interfaces/api/alumni_routes.py", "get_alumni"),
    ("domains/learners/interfaces/api/alumni_routes.py", "update_alumni"),
    ("domains/learners/interfaces/api/enrollment_routes.py", "drop_enrollment"),
    ("domains/learners/interfaces/api/student_id_routes.py", "get_card"),
    ("domains/learners/interfaces/api/student_id_routes.py", "get_replacement"),
    ("domains/operations/interfaces/api/barber_routes.py", "get_service"),
    ("domains/operations/interfaces/api/barber_routes.py", "get_staff"),
    ("domains/operations/interfaces/api/barber_routes.py", "get_staff_availability"),
    ("domains/operations/interfaces/api/betting_routes.py", "get_market"),
    ("domains/operations/interfaces/api/butcher_routes.py", "get_order"),
    ("domains/operations/interfaces/api/butcher_routes.py", "get_product"),
    ("domains/operations/interfaces/api/campus_navigation_routes.py", "get_building"),
    ("domains/operations/interfaces/api/campus_navigation_routes.py", "get_building_stats"),
    ("domains/operations/interfaces/api/campus_navigation_routes.py", "get_poi"),
    ("domains/operations/interfaces/api/campus_navigation_routes.py", "get_route"),
    ("domains/operations/interfaces/api/campus_navigation_routes.py", "rate_navigation"),
    ("domains/operations/interfaces/api/campus_navigation_routes.py", "remove_favorite"),
    ("domains/operations/interfaces/api/campus_routes.py", "get_building"),
    ("domains/operations/interfaces/api/carrental_routes.py", "get_vehicle"),
    ("domains/operations/interfaces/api/carrental_routes.py", "process_refund"),
    ("domains/operations/interfaces/api/cinema_routes.py", "get_booking"),
    ("domains/operations/interfaces/api/cinema_routes.py", "get_movie"),
    ("domains/operations/interfaces/api/cinema_routes.py", "get_screening"),
    ("domains/operations/interfaces/api/commerce_routes.py", "get_menu"),
    ("domains/operations/interfaces/api/commerce_routes.py", "get_order"),
    ("domains/operations/interfaces/api/equipment_routes.py", "cancel_rental"),
    ("domains/operations/interfaces/api/equipment_routes.py", "checkout_item"),
    ("domains/operations/interfaces/api/equipment_routes.py", "extend_rental"),
    ("domains/operations/interfaces/api/equipment_routes.py", "get_equipment"),
    ("domains/operations/interfaces/api/equipment_routes.py", "return_item"),
    ("domains/operations/interfaces/api/event_routes.py", "create_registration"),
    ("domains/operations/interfaces/api/event_routes.py", "get_event"),
    ("domains/operations/interfaces/api/event_routes.py", "list_registrations"),
    ("domains/operations/interfaces/api/event_routes.py", "update_event"),
    ("domains/operations/interfaces/api/events_discovery_routes.py", "cancel_event"),
    ("domains/operations/interfaces/api/events_discovery_routes.py", "cancel_rsvp"),
    ("domains/operations/interfaces/api/events_discovery_routes.py", "get_event"),
    ("domains/operations/interfaces/api/events_discovery_routes.py", "get_event_reviews"),
    ("domains/operations/interfaces/api/events_discovery_routes.py", "get_event_statistics"),
    ("domains/operations/interfaces/api/events_discovery_routes.py", "get_rsvp"),
    ("domains/operations/interfaces/api/events_discovery_routes.py", "update_event"),
    ("domains/operations/interfaces/api/events_discovery_routes.py", "update_rsvp"),
    ("domains/operations/interfaces/api/facilities_mgmt_routes.py", "get_inspection"),
    ("domains/operations/interfaces/api/facilities_mgmt_routes.py", "get_work_order"),
    ("domains/operations/interfaces/api/facility_routes.py", "update_booking"),
    ("domains/operations/interfaces/api/facility_routes.py", "update_maintenance"),
    ("domains/operations/interfaces/api/feedback_system_routes.py", "get_categorie"),
    ("domains/operations/interfaces/api/feedback_system_routes.py", "get_response"),
    ("domains/operations/interfaces/api/feedback_system_routes.py", "get_submission"),
    ("domains/operations/interfaces/api/feedback_system_routes.py", "update_submission_status"),
    ("domains/operations/interfaces/api/gym_routes.py", "cancel_class_booking"),
    ("domains/operations/interfaces/api/gym_routes.py", "cancel_membership"),
    ("domains/operations/interfaces/api/gym_routes.py", "get_booking"),
    ("domains/operations/interfaces/api/gym_routes.py", "get_classe"),
    ("domains/operations/interfaces/api/gym_routes.py", "get_member_bookings"),
    ("domains/operations/interfaces/api/gym_routes.py", "get_member_pt_sessions"),
    ("domains/operations/interfaces/api/gym_routes.py", "get_membership"),
    ("domains/operations/interfaces/api/gym_routes.py", "renew_membership"),
    ("domains/operations/interfaces/api/gym_routes.py", "report_equipment_issue"),
    ("domains/operations/interfaces/api/housing_routes.py", "get_room"),
    ("domains/operations/interfaces/api/lost_found_routes.py", "add_photo"),
    ("domains/operations/interfaces/api/lost_found_routes.py", "claim_item"),
    ("domains/operations/interfaces/api/lost_found_routes.py", "delete_item"),
    ("domains/operations/interfaces/api/lost_found_routes.py", "get_item"),
    ("domains/operations/interfaces/api/lost_found_routes.py", "get_matches"),
    ("domains/operations/interfaces/api/lost_found_routes.py", "get_photos"),
    ("domains/operations/interfaces/api/lost_found_routes.py", "review_claim"),
    ("domains/operations/interfaces/api/lost_found_routes.py", "update_item_status"),
    ("domains/operations/interfaces/api/mail_routes.py", "get_package"),
    ("domains/operations/interfaces/api/mail_routes.py", "get_po_boxe"),
    ("domains/operations/interfaces/api/marketplace_routes.py", "claim_free_item"),
    ("domains/operations/interfaces/api/marketplace_routes.py", "delete_listing"),
    ("domains/operations/interfaces/api/marketplace_routes.py", "get_free_item"),
    ("domains/operations/interfaces/api/marketplace_routes.py", "get_listing"),
    ("domains/operations/interfaces/api/marketplace_routes.py", "get_saved_listings"),
    ("domains/operations/interfaces/api/marketplace_routes.py", "get_sublet"),
    ("domains/operations/interfaces/api/marketplace_routes.py", "get_user_listings"),
    ("domains/operations/interfaces/api/marketplace_routes.py", "mark_listing_sold"),
    ("domains/operations/interfaces/api/marketplace_routes.py", "remove_saved_listing"),
    ("domains/operations/interfaces/api/marketplace_routes.py", "save_listing"),
    ("domains/operations/interfaces/api/marketplace_routes.py", "update_listing"),
    ("domains/operations/interfaces/api/mobility_routes.py", "get_device"),
    ("domains/operations/interfaces/api/mobility_routes.py", "get_session"),
    ("domains/operations/interfaces/api/musicshop_routes.py", "add_to_wishlist"),
    ("domains/operations/interfaces/api/musicshop_routes.py", "cancel_order"),
    ("domains/operations/interfaces/api/musicshop_routes.py", "get_customer_orders"),
    ("domains/operations/interfaces/api/musicshop_routes.py", "get_order"),
    ("domains/operations/interfaces/api/musicshop_routes.py", "get_product"),
    ("domains/operations/interfaces/api/musicshop_routes.py", "get_wishlist"),
    ("domains/operations/interfaces/api/musicshop_routes.py", "process_refund"),
    ("domains/operations/interfaces/api/musicshop_routes.py", "record_payment"),
    ("domains/operations/interfaces/api/musicshop_routes.py", "remove_from_wishlist"),
    ("domains/operations/interfaces/api/musicshop_routes.py", "update_order_status"),
    ("domains/operations/interfaces/api/musicshop_routes.py", "update_product"),
    ("domains/operations/interfaces/api/nailbar_routes.py", "get_appointment"),
    ("domains/operations/interfaces/api/nailbar_routes.py", "get_customer_appointments"),
    ("domains/operations/interfaces/api/nailbar_routes.py", "get_technician"),
    ("domains/operations/interfaces/api/nailbar_routes.py", "get_technician_availability"),
    ("domains/operations/interfaces/api/nailbar_routes.py", "get_treatment"),
    ("domains/operations/interfaces/api/nailbar_routes.py", "update_appointment_status"),
    ("domains/operations/interfaces/api/nailbar_routes.py", "update_treatment"),
    ("domains/operations/interfaces/api/parking_routes.py", "get_permit"),
    ("domains/operations/interfaces/api/phoneshop_routes.py", "cancel_order"),
    ("domains/operations/interfaces/api/phoneshop_routes.py", "get_customer_orders"),
    ("domains/operations/interfaces/api/phoneshop_routes.py", "get_order"),
    ("domains/operations/interfaces/api/phoneshop_routes.py", "get_product"),
    ("domains/operations/interfaces/api/phoneshop_routes.py", "get_warrantie"),
    ("domains/operations/interfaces/api/phoneshop_routes.py", "process_refund"),
    ("domains/operations/interfaces/api/phoneshop_routes.py", "record_payment"),
    ("domains/operations/interfaces/api/phoneshop_routes.py", "update_order_status"),
    ("domains/operations/interfaces/api/phoneshop_routes.py", "update_product"),
    ("domains/operations/interfaces/api/printing_routes.py", "get_job"),
    ("domains/operations/interfaces/api/printing_routes.py", "get_quota"),
    ("domains/operations/interfaces/api/roommate_finder_routes.py", "get_matche"),
    ("domains/operations/interfaces/api/roommate_finder_routes.py", "get_profile"),
    ("domains/operations/interfaces/api/security_routes.py", "get_ticket"),
    ("domains/operations/interfaces/api/security_routes.py", "update_ticket"),
    ("domains/operations/interfaces/api/study_rooms_routes.py", "get_booking"),
    ("domains/operations/interfaces/api/study_rooms_routes.py", "get_room"),
    ("domains/operations/interfaces/api/textbooks_routes.py", "get_listing"),
    ("domains/operations/interfaces/api/textbooks_routes.py", "get_textbook"),
    ("domains/pastoral/interfaces/api/accommodation_routes.py", "get_accommodation"),
    ("domains/pastoral/interfaces/api/achievement_badge_routes.py", "get_award"),
    ("domains/pastoral/interfaces/api/achievement_badge_routes.py", "get_badge"),
    ("domains/pastoral/interfaces/api/achievement_badge_routes.py", "revoke_badge"),
    ("domains/pastoral/interfaces/api/achievement_badge_routes.py", "toggle_badge_display"),
    ("domains/pastoral/interfaces/api/career_routes.py", "get_job"),
    ("domains/pastoral/interfaces/api/career_routes.py", "list_placements"),
    ("domains/pastoral/interfaces/api/career_routes.py", "register_for_career_event"),
    ("domains/pastoral/interfaces/api/club_routes.py", "add_member"),
    ("domains/pastoral/interfaces/api/club_routes.py", "get_club"),
    ("domains/pastoral/interfaces/api/club_routes.py", "list_members"),
    ("domains/pastoral/interfaces/api/club_routes.py", "update_club"),
    ("domains/pastoral/interfaces/api/dentist_routes.py", "get_appointment"),
    ("domains/pastoral/interfaces/api/dentist_routes.py", "get_available_slots"),
    ("domains/pastoral/interfaces/api/dentist_routes.py", "get_dentist_schedule"),
    ("domains/pastoral/interfaces/api/dentist_routes.py", "get_patient"),
    ("domains/pastoral/interfaces/api/dentist_routes.py", "get_patient_payments"),
    ("domains/pastoral/interfaces/api/dentist_routes.py", "get_treatment"),
    ("domains/pastoral/interfaces/api/dentist_routes.py", "update_appointment_status"),
    ("domains/pastoral/interfaces/api/early_warning_routes.py", "update_intervention"),
    ("domains/pastoral/interfaces/api/election_routes.py", "cast_poll_vote"),
    ("domains/pastoral/interfaces/api/election_routes.py", "get_poll"),
    ("domains/pastoral/interfaces/api/emergency_routes.py", "update_incident"),
    ("domains/pastoral/interfaces/api/helpdesk_routes.py", "create_reply"),
    ("domains/pastoral/interfaces/api/helpdesk_routes.py", "get_ticket"),
    ("domains/pastoral/interfaces/api/helpdesk_routes.py", "list_replies"),
    ("domains/pastoral/interfaces/api/helpdesk_routes.py", "update_ticket"),
    ("domains/pastoral/interfaces/api/mentorship_routes.py", "get_relationship"),
    ("domains/pastoral/interfaces/api/mentorship_routes.py", "list_sessions"),
    ("domains/pastoral/interfaces/api/mentorship_routes.py", "update_relationship"),
    ("domains/pastoral/interfaces/api/social_matching_routes.py", "get_matche"),
    ("domains/pastoral/interfaces/api/social_matching_routes.py", "get_profile"),
    ("domains/pastoral/interfaces/api/student_affairs_routes.py", "get_support_request"),
    ("domains/pastoral/interfaces/api/student_affairs_routes.py", "get_tool"),
    ("domains/pastoral/interfaces/api/student_app_routes.py", "get_notification"),
    ("domains/pastoral/interfaces/api/student_app_routes.py", "mark_notification_read"),
    ("domains/pastoral/interfaces/api/student_app_routes.py", "remove_quick_link"),
    ("domains/pastoral/interfaces/api/student_jobs_routes.py", "get_application"),
    ("domains/pastoral/interfaces/api/student_jobs_routes.py", "get_employment"),
    ("domains/pastoral/interfaces/api/student_jobs_routes.py", "get_posting"),
    ("domains/pastoral/interfaces/api/student_wellbeing_routes.py", "delete_referral"),
    ("domains/pastoral/interfaces/api/student_wellbeing_routes.py", "get_checkin"),
    ("domains/pastoral/interfaces/api/student_wellbeing_routes.py", "get_counselling"),
    ("domains/pastoral/interfaces/api/student_wellbeing_routes.py", "get_referral"),
    ("domains/pastoral/interfaces/api/student_wellbeing_routes.py", "update_referral"),
    ("domains/pastoral/interfaces/api/tutoring_routes.py", "get_offer"),
    ("domains/pastoral/interfaces/api/tutoring_routes.py", "update_offer"),
    ("domains/pastoral/interfaces/api/wellness_routes.py", "get_crisis_resource"),
    ("domains/progression/interfaces/api/credential_routes.py", "get_blockchain_credential"),
    ("domains/progression/interfaces/api/credential_routes.py", "verify_credential"),
    ("domains/progression/interfaces/api/portfolio_routes.py", "get_item"),
    ("domains/progression/interfaces/api/portfolio_routes.py", "get_portfolio"),
    ("domains/progression/interfaces/api/portfolio_routes.py", "get_skill"),
    ("domains/staff/interfaces/api/hr_routes.py", "get_department"),
    ("domains/staff/interfaces/api/hr_routes.py", "get_staff"),
    ("domains/staff/interfaces/api/hr_routes.py", "update_timesheet"),
    ("domains/staff/interfaces/api/staff_hr_routes.py", "get_leave_request"),
    ("domains/staff/interfaces/api/staff_hr_routes.py", "get_staff"),
    ("shell/api/routes/announcement_routes.py", "get_announcement"),
    ("shell/api/routes/chat_routes.py", "create_message"),
    ("shell/api/routes/chat_routes.py", "get_room"),
    ("shell/api/routes/chat_routes.py", "list_messages"),
    ("shell/api/routes/document_routes.py", "get_repository_document"),
    ("shell/api/routes/mfa_routes.py", "revoke_trusted_device"),
    ("shell/api/routes/notification_routes.py", "mark_read"),
    ("shell/api/routes/web_routes.py", "operations_asset"),
    ("shell/api/routes/web_routes.py", "operations_page"),
    ("shell/api/routes/web_routes.py", "student_page"),
}


def test_no_new_unscoped_id_bearing_routes():
    """A route that takes a resource id must authorize, not just authenticate."""
    actual = _unscoped_routes()
    new = actual - KNOWN_UNSCOPED
    assert not new, (
        "New API route(s) take a resource identifier but make no "
        "authorization decision — an authenticated caller could swap the id "
        "and reach another subject's record:\n"
        + "\n".join(f"  {rel}::{fn}" for rel, fn in sorted(new))
        + "\n\nAdd @scoped_to(\"<owner_param>\") beneath @token_required when the "
        "path id is the owner, @staff_required(...) for staff-internal "
        "records, or deny_unless_owner_or_staff(<owner from the row>) when the "
        "path id is a resource id."
    )


def test_fixed_routes_are_removed_from_the_allow_list():
    """The allow-list only shrinks."""
    actual = _unscoped_routes()
    stale = KNOWN_UNSCOPED - actual
    assert not stale, (
        "These routes now authorize correctly — delete them from "
        "KNOWN_UNSCOPED so the ratchet keeps tightening:\n"
        + "\n".join(f"  {rel}::{fn}" for rel, fn in sorted(stale))
    )
