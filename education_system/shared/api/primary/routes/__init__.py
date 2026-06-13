"""Primary school REST route blueprints.

One blueprint per module. Registered by the unified server.
"""

from education_system.shared.api.primary.routes.absence_requests_routes import (
    absence_requests_bp,
)
from education_system.shared.api.primary.routes.academic_year_routes import (
    academic_year_bp,
)
from education_system.shared.api.primary.routes.accessibility_routes import (
    accessibility_bp,
)
from education_system.shared.api.primary.routes.activity_feed_routes import (
    activity_feed_bp,
)
from education_system.shared.api.primary.routes.admissions_routes import (
    admissions_bp,
)
from education_system.shared.api.primary.routes.announcements_routes import (
    announcements_bp,
)
from education_system.shared.api.primary.routes.appraisals_routes import (
    appraisals_bp,
)
from education_system.shared.api.primary.routes.assessment_routes import (
    assessment_bp,
)
from education_system.shared.api.primary.routes.assets_routes import (
    assets_bp,
)
from education_system.shared.api.primary.routes.attachments_routes import (
    attachments_bp,
)
from education_system.shared.api.primary.routes.attendance_concerns_routes import (
    attendance_concerns_bp,
)
from education_system.shared.api.primary.routes.attendance_report_routes import (
    attendance_report_bp,
)
from education_system.shared.api.primary.routes.attendance_routes import (
    attendance_bp,
)
from education_system.shared.api.primary.routes.audit_reports_routes import (
    audit_reports_bp,
)
from education_system.shared.api.primary.routes.behaviour_routes import (
    behaviour_bp,
)
from education_system.shared.api.primary.routes.calendar_routes import (
    calendar_bp,
)
from education_system.shared.api.primary.routes.census_routes import (
    census_bp,
)
from education_system.shared.api.primary.routes.class_teachers_routes import (
    class_teachers_bp,
)
from education_system.shared.api.primary.routes.classes_routes import (
    classes_bp,
)
from education_system.shared.api.primary.routes.clubs_routes import (
    clubs_bp,
)
from education_system.shared.api.primary.routes.complaints_routes import (
    complaints_bp,
)
from education_system.shared.api.primary.routes.compliance_routes import (
    compliance_bp,
)
from education_system.shared.api.primary.routes.cover_routes import (
    cover_bp,
)
from education_system.shared.api.primary.routes.cpd_routes import (
    cpd_bp,
)
from education_system.shared.api.primary.routes.custom_export_routes import (
    custom_export_bp,
)
from education_system.shared.api.primary.routes.data_dashboard_routes import (
    data_dashboard_bp,
)
from education_system.shared.api.primary.routes.data_export_routes import (
    data_export_bp,
)
from education_system.shared.api.primary.routes.dbs_checks_routes import (
    dbs_checks_bp,
)
from education_system.shared.api.primary.routes.departments_routes import (
    departments_bp,
)
from education_system.shared.api.primary.routes.dinner_money_routes import (
    dinner_money_bp,
)
from education_system.shared.api.primary.routes.document_hub_routes import (
    document_hub_bp,
)
from education_system.shared.api.primary.routes.early_warning_routes import (
    early_warning_bp,
)
from education_system.shared.api.primary.routes.emergency_routes import (
    emergency_bp,
)
from education_system.shared.api.primary.routes.enrolment_routes import (
    enrolment_bp,
)
from education_system.shared.api.primary.routes.equality_diversity_routes import (
    equality_diversity_bp,
)
from education_system.shared.api.primary.routes.expense_claims_routes import (
    expense_claims_bp,
)
from education_system.shared.api.primary.routes.eyfs_profile_routes import (
    eyfs_profile_bp,
)
from education_system.shared.api.primary.routes.feedback_routes import (
    feedback_bp,
)
from education_system.shared.api.primary.routes.first_aid_routes import (
    first_aid_bp,
)
from education_system.shared.api.primary.routes.funding_routes import (
    funding_bp,
)
from education_system.shared.api.primary.routes.gdpr_routes import (
    gdpr_bp,
)
from education_system.shared.api.primary.routes.governance_routes import (
    governance_bp,
)
from education_system.shared.api.primary.routes.health_safety_routes import (
    health_safety_bp,
)
from education_system.shared.api.primary.routes.homework_routes import (
    homework_bp,
)
from education_system.shared.api.primary.routes.house_points_routes import (
    house_points_bp,
)
from education_system.shared.api.primary.routes.intervention_tracking_routes import (
    intervention_tracking_bp,
)
from education_system.shared.api.primary.routes.kpi_dashboard_routes import (
    kpi_dashboard_bp,
)
from education_system.shared.api.primary.routes.ks1_sats_routes import (
    ks1_sats_bp,
)
from education_system.shared.api.primary.routes.ks2_sats_routes import (
    ks2_sats_bp,
)
from education_system.shared.api.primary.routes.lesson_plans_routes import (
    lesson_plans_bp,
)
from education_system.shared.api.primary.routes.letter_templates_routes import (
    letter_templates_bp,
)
from education_system.shared.api.primary.routes.library_routes import (
    library_bp,
)
from education_system.shared.api.primary.routes.medical_records_routes import (
    medical_records_bp,
)
from education_system.shared.api.primary.routes.messages_routes import (
    messages_bp,
)
from education_system.shared.api.primary.routes.mobile_dashboard_routes import (
    mobile_dashboard_bp,
)
from education_system.shared.api.primary.routes.mtc_routes import (
    mtc_bp,
)
from education_system.shared.api.primary.routes.newsletters_routes import (
    newsletters_bp,
)
from education_system.shared.api.primary.routes.notifications_routes import (
    notifications_bp,
)
from education_system.shared.api.primary.routes.observations_routes import (
    observations_bp,
)
from education_system.shared.api.primary.routes.parent_contacts_routes import (
    parent_contacts_bp,
)
from education_system.shared.api.primary.routes.parents_evenings_routes import (
    parents_evenings_bp,
)
from education_system.shared.api.primary.routes.phonics_routes import (
    phonics_bp,
)
from education_system.shared.api.primary.routes.phonics_screening_routes import (
    phonics_screening_bp,
)
from education_system.shared.api.primary.routes.policies_routes import (
    policies_bp,
)
from education_system.shared.api.primary.routes.prevent_duty_routes import (
    prevent_duty_bp,
)
from education_system.shared.api.primary.routes.progress_report_routes import (
    progress_report_bp,
)
from education_system.shared.api.primary.routes.progress_routes import (
    progress_bp,
)
from education_system.shared.api.primary.routes.pupil_premium_routes import (
    pupil_premium_bp,
)
from education_system.shared.api.primary.routes.pupil_reports_routes import (
    pupil_reports_bp,
)
from education_system.shared.api.primary.routes.pupil_support_routes import (
    pupil_support_bp,
)
from education_system.shared.api.primary.routes.pupils_routes import (
    pupils_bp,
)
from education_system.shared.api.primary.routes.reading_levels_routes import (
    reading_levels_bp,
)
from education_system.shared.api.primary.routes.receipts_routes import (
    receipts_bp,
)
from education_system.shared.api.primary.routes.recruitment_routes import (
    recruitment_bp,
)
from education_system.shared.api.primary.routes.risk_management_routes import (
    risk_management_bp,
)
from education_system.shared.api.primary.routes.safeguarding_routes import (
    safeguarding_bp,
)
from education_system.shared.api.primary.routes.school_council_routes import (
    school_council_bp,
)
from education_system.shared.api.primary.routes.send_routes import (
    send_bp,
)
from education_system.shared.api.primary.routes.staff_absence_routes import (
    staff_absence_bp,
)
from education_system.shared.api.primary.routes.staff_hr_routes import (
    staff_hr_bp,
)
from education_system.shared.api.primary.routes.staff_routes import (
    staff_bp,
)
from education_system.shared.api.primary.routes.staff_wellbeing_routes import (
    staff_wellbeing_bp,
)
from education_system.shared.api.primary.routes.subjects_routes import (
    subjects_bp,
)
from education_system.shared.api.primary.routes.surveys_routes import (
    surveys_bp,
)
from education_system.shared.api.primary.routes.target_setting_routes import (
    target_setting_bp,
)
from education_system.shared.api.primary.routes.teaching_assistants_routes import (
    teaching_assistants_bp,
)
from education_system.shared.api.primary.routes.timetable_routes import (
    timetable_bp,
)
from education_system.shared.api.primary.routes.todo_routes import (
    todo_bp,
)
from education_system.shared.api.primary.routes.transport_routes import (
    transport_bp,
)
from education_system.shared.api.primary.routes.trips_routes import (
    trips_bp,
)
from education_system.shared.api.primary.routes.user_management_routes import (
    user_management_bp,
)
from education_system.shared.api.primary.routes.visitors_routes import (
    visitors_bp,
)
from education_system.shared.api.primary.routes.wellbeing_routes import (
    wellbeing_bp,
)
from education_system.shared.api.primary.routes.wraparound_routes import (
    wraparound_bp,
)
from education_system.shared.api.primary.routes.year_groups_routes import (
    year_groups_bp,
)

__all__ = [
    "absence_requests_bp",
    "academic_year_bp",
    "accessibility_bp",
    "activity_feed_bp",
    "admissions_bp",
    "announcements_bp",
    "appraisals_bp",
    "assessment_bp",
    "assets_bp",
    "attachments_bp",
    "attendance_concerns_bp",
    "attendance_report_bp",
    "attendance_bp",
    "audit_reports_bp",
    "behaviour_bp",
    "calendar_bp",
    "census_bp",
    "class_teachers_bp",
    "classes_bp",
    "clubs_bp",
    "complaints_bp",
    "compliance_bp",
    "cover_bp",
    "cpd_bp",
    "custom_export_bp",
    "data_dashboard_bp",
    "data_export_bp",
    "dbs_checks_bp",
    "departments_bp",
    "dinner_money_bp",
    "document_hub_bp",
    "early_warning_bp",
    "emergency_bp",
    "enrolment_bp",
    "equality_diversity_bp",
    "expense_claims_bp",
    "eyfs_profile_bp",
    "feedback_bp",
    "first_aid_bp",
    "funding_bp",
    "gdpr_bp",
    "governance_bp",
    "health_safety_bp",
    "homework_bp",
    "house_points_bp",
    "intervention_tracking_bp",
    "kpi_dashboard_bp",
    "ks1_sats_bp",
    "ks2_sats_bp",
    "lesson_plans_bp",
    "letter_templates_bp",
    "library_bp",
    "medical_records_bp",
    "messages_bp",
    "mobile_dashboard_bp",
    "mtc_bp",
    "newsletters_bp",
    "notifications_bp",
    "observations_bp",
    "parent_contacts_bp",
    "parents_evenings_bp",
    "phonics_bp",
    "phonics_screening_bp",
    "policies_bp",
    "prevent_duty_bp",
    "progress_report_bp",
    "progress_bp",
    "pupil_premium_bp",
    "pupil_reports_bp",
    "pupil_support_bp",
    "pupils_bp",
    "reading_levels_bp",
    "receipts_bp",
    "recruitment_bp",
    "risk_management_bp",
    "safeguarding_bp",
    "school_council_bp",
    "send_bp",
    "staff_absence_bp",
    "staff_hr_bp",
    "staff_bp",
    "staff_wellbeing_bp",
    "subjects_bp",
    "surveys_bp",
    "target_setting_bp",
    "teaching_assistants_bp",
    "timetable_bp",
    "todo_bp",
    "transport_bp",
    "trips_bp",
    "user_management_bp",
    "visitors_bp",
    "wellbeing_bp",
    "wraparound_bp",
    "year_groups_bp",
]

ALL_BLUEPRINTS = (
    absence_requests_bp,
    academic_year_bp,
    accessibility_bp,
    activity_feed_bp,
    admissions_bp,
    announcements_bp,
    appraisals_bp,
    assessment_bp,
    assets_bp,
    attachments_bp,
    attendance_concerns_bp,
    attendance_report_bp,
    attendance_bp,
    audit_reports_bp,
    behaviour_bp,
    calendar_bp,
    census_bp,
    class_teachers_bp,
    classes_bp,
    clubs_bp,
    complaints_bp,
    compliance_bp,
    cover_bp,
    cpd_bp,
    custom_export_bp,
    data_dashboard_bp,
    data_export_bp,
    dbs_checks_bp,
    departments_bp,
    dinner_money_bp,
    document_hub_bp,
    early_warning_bp,
    emergency_bp,
    enrolment_bp,
    equality_diversity_bp,
    expense_claims_bp,
    eyfs_profile_bp,
    feedback_bp,
    first_aid_bp,
    funding_bp,
    gdpr_bp,
    governance_bp,
    health_safety_bp,
    homework_bp,
    house_points_bp,
    intervention_tracking_bp,
    kpi_dashboard_bp,
    ks1_sats_bp,
    ks2_sats_bp,
    lesson_plans_bp,
    letter_templates_bp,
    library_bp,
    medical_records_bp,
    messages_bp,
    mobile_dashboard_bp,
    mtc_bp,
    newsletters_bp,
    notifications_bp,
    observations_bp,
    parent_contacts_bp,
    parents_evenings_bp,
    phonics_bp,
    phonics_screening_bp,
    policies_bp,
    prevent_duty_bp,
    progress_report_bp,
    progress_bp,
    pupil_premium_bp,
    pupil_reports_bp,
    pupil_support_bp,
    pupils_bp,
    reading_levels_bp,
    receipts_bp,
    recruitment_bp,
    risk_management_bp,
    safeguarding_bp,
    school_council_bp,
    send_bp,
    staff_absence_bp,
    staff_hr_bp,
    staff_bp,
    staff_wellbeing_bp,
    subjects_bp,
    surveys_bp,
    target_setting_bp,
    teaching_assistants_bp,
    timetable_bp,
    todo_bp,
    transport_bp,
    trips_bp,
    user_management_bp,
    visitors_bp,
    wellbeing_bp,
    wraparound_bp,
    year_groups_bp,
)
