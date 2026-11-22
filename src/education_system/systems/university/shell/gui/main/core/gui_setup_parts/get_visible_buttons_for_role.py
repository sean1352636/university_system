"""Extracted function implementation."""

from .. import gui_setup_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def get_visible_buttons_for_role(self, role=None):
    """
    Return a set of button names that should be visible for the given role.
    If role is None (not logged in), only login button is visible.
    """
    if role is None:
        return {'login'}

    # Get user object for detailed permission checking
    user = self.auth.current_user if self.auth else None
    permissions = user.get('permissions', []) if user else []

    # Helper flags
    is_admin = role == 'admin'
    is_staff = role in ('admin', 'staff')
    is_instructor = role in ('admin', 'staff', 'instructor')
    is_student = role == 'student'

    # Base buttons for all logged-in users
    visible = {
            # Nav keys that existed in create_navigation_panel but were in no role set, so the buttons never rendered (2026-10-14).
            'my_finance',
        'change_password', 'mfa_setup', 'security_questions',
        # Student services available to all
        'assignments', 'academic_calendar', 'student_union_portal',
        'campus_events', 'university_shop', 'cafe_system', 'takeaway_system', 'grocery_shop', 'bar', 'student_support', 'internship_portal',
        'career_services', 'helpdesk', 'financial_aid', 'integrated_dashboard',
        'student_handbook',
        'ai_features', 'mobile_app_pwa', 'parent_portal', 'extras_launcher',
        'legal_services', 'betting_shop', 'cinema', 'mail_post', 'gym', 'dentist',
        'butcher', 'barber', 'nailbar', 'carrental', 'equipment', 'phoneshop', 'musicshop',
        # Transportation services
        'taxi_booking', 'train_station',
        # New apps - available to all logged-in users
        'todo_app', 'security_desk', 'church_management',
        # Additional services
        'exam_portal', 'medical_accommodations',
        # Student Success & Engagement (v5.5.0) - available to all
        'academic_progress', 'study_hub',
        'student_jobs', 'roommate_finder',
        'campus_navigation', 'lost_found', 'marketplace', 'wellness_hub',
        'accessibility', 'wellbeing_casework', 'social_matching', 'portfolio', 'events_discovery',
        'feedback_system',
        # Student features (v5.40+)
        'advising_portal', 'student_id_card', 'study_room_booking',
        'printing_services',
        # budget_tracker lives in the Finance GUI; scholarship_finder is in the
        # Finance window's Aid tab (sidebar button removed 2026-10-18).
        # Note: notifications_hub moved to Email GUI
        # Shared modules available to all (including parents)
        'cross_system_calendar', 'digital_transcript', 'certificates',
        # LMS
        'lms',
        # New features (modules 21-30) - student-accessible
        'student_app', 'achievement_badges',
        # New Features sidebar category (13 standalone Tk apps under
        # modules/domain/, launched as subprocesses by main_gui.py).
        'new_feature_complaints_portal',
        # Academic appeals: students see their own; staff run the procedure.
        'new_feature_academic_appeals',
        'new_feature_course_evaluation_system',
        'new_feature_lecturer_evaluation',
        'new_feature_module_evaluation_portal',
        'new_feature_disciplinary_portal',
        'new_feature_fitness_to_practise',
        'new_feature_risk_management',
        'new_feature_first_aid_portal',
        'new_feature_health_safety_portal',
        'new_feature_safeguarding_system',
        'new_feature_background_checker',
        'new_feature_university_research',
        # Cross-system ports added 2026-04
        'new_feature_employer_portal',
        'new_feature_kpi_dashboard',
        'new_feature_institutional_analytics',
        'new_feature_mentoring_matching',
        'new_feature_room_booking',
        'new_feature_building_management',
        # Standalone Tk apps moved from /add 2026-04
        'new_feature_apprenticeship_system',
        'new_feature_placement_tracker',
        'new_feature_bakery_shop',
    }

    # Student-specific additions
    if is_student:
        visible.update({
            'student_records', 'grade_tracking_gui', 'library',
            'scheduling', 'trip_management', 'communication_hub',
            'office_hours', 'graduation_ceremony',
            # Alumni system: students see only their mentoring matches there
            'alumni_management',
            # Student-facing features
            'student_analytics', 'learning_outcomes',
            'my_timetable', 'student_registration',
            # Shared cross-system modules for students
            'student_self_service', 'digital_transcript', 'cross_system_calendar',
        })

    # Health Portal: the health team, students (their own record) and
    # teaching/professional staff (break-glass access only). Never parents or
    # alumni — health records are special-category data.
    from education_system.systems.university.domains.health.application.health import (
        access as health_access,
    )
    if (role in health_access.CLINICAL_ROLES or is_student or is_instructor
            or role in health_access.ADMIN_ROLES):
        visible.add('health_portal')

    # Instructor additions (includes students' features)
    if is_instructor:
        visible.update({
            # Previously orphaned launchers, now on the sidebar (2026-10-14).
            'ai_detector',
            'student_records', 'course_management', 'module_management',
            'grade_tracking_gui', 'library', 'virtual_classroom',
            # 'timetable_manager' retired — the two timetable buttons merged
            # into the single 'my_timetable' entry granted below.
            'scheduling', 'attendance', 'analytics',
            # Early Warning & Interventions (early warning, support cases,
            # outcomes) — staff-facing, as Early Warning always was.
            'export', 'new_feature_intervention_hub', 'communication_hub',
            'office_hours', 'graduation_ceremony',
            'my_timetable', 'student_registration',
            # Scheduling & outcomes tools for teaching staff.
            # 'exam_scheduler' retired — the scheduler is a tab inside Exam
            # Management, and 'exam_portal' is already in the base set that
            # every logged-in role can see.
            'student_analytics', 'student_outcomes',
        })

    # Staff additions (includes instructors' features)
    if is_staff:
        visible.update({
            # Nav keys that were in no role set, plus previously orphaned launchers (2026-10-14).
            'prior_learning', 'mitigating_circumstances', 'apprenticeship_progression', 'information_rights',
            'create_student', 'search_students', 'advanced_search_gui',
            'batch_operations', 'housing_accommodations',
            'restaurant_management', 'cafe_system', 'takeaway_system', 'grocery_shop', 'parking_management', 'facilities_management',
            'alumni_management', 'communication_hub',
            'admissions_crm', 'ucas_management', 'blockchain_credentials',
            'document_manager', 'pdf_export', 'charity_shop',
            # Staff-only security tools
            'police_station',
            # Staff HR management
            'staff_hr',
            # Staff CRUD management
            'view_staff', 'create_staff', 'search_staff',
            # Office hours
            'office_hours',
            # New features - staff level
            # Cross-system modules
            'student_journey', 'reporting_warehouse',
            'analytics_dashboard', 'outcome_tracking', 'predictive_alerts',
            'bulk_transfer', 'transfer_documents', 'reverse_lookup',
            'parent_continuity', 'cross_system_calendar',
            'shared_documents',
            'student_self_service', 'digital_transcript',
            # Analytics tooling for professional-services staff
            'business_intelligence', 'predictive_analytics',
            # International student / Tier-4 sponsor compliance. No sidebar
            # button any more; gates the Student Records right-click item.
            'visa_compliance',
            # OfS / TEF / REF external quality assurance
            'qa_dashboard',
            # Outgoing/incoming exchange: coordinators are professional
            # services staff, not just admins.
            'student_mobility',
            # Shared case register and institution-wide timetabling (staff)
            'new_feature_timetabling', 'new_feature_case_management',
            # Programme governance, PGR administration and assessment boards
            # (staff-only service windows, 2026-10)
            'new_feature_programme_governance', 'new_feature_pgr_admin',
            'new_feature_assessment_boards',
        })

    # Admin-only additions (full access)
    if is_admin:
        visible.update({
            # Nav keys that were in no role set (2026-10-14).
            'university_progression', 'toggle_verification',
            'delete_student', 'finance_management',
            'user_management', 'system_admin_gui', 'security_dashboard',
            'integration_marketplace', 'backup_gui',
            # Admin-only staff management
            'delete_staff',
            # Admin tools
            'usage_adoption_reports',
            'custom_report_builder',
            # Admin-only shared modules
            'central_admin_portal', 'gdpr_compliance', 'equality_diversity',
            # New features - admin level
            'hesa_export', 'clearing_adjustment', 'curriculum_specification',
            # Partner agreements carry contractual and regulatory risk, so
            # the register is admin-only; mobility sits with staff above.
            'collaborative_provision',
            # Dual-control identity changes and SSO provider config (admin)
            'new_feature_identity_management', 'new_feature_sso_providers',
            # Connector config, event queue and record retention (admin)
            'new_feature_connectors',
        })

    # Additional permission-based checks for edge cases
    if 'view_any_student' in permissions or 'view_own_record' in permissions:
        visible.add('student_records')
    if 'manage_courses' in permissions or 'view_courses' in permissions:
        visible.add('course_management')
    if any(p in permissions for p in ['view_books', 'manage_books', 'manage_loans', 'checkout_books']):
        visible.add('library')
    if 'view_trips' in permissions or 'register_for_trips' in permissions or 'manage_trips' in permissions:
        visible.add('trip_management')

    return visible
