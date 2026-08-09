"""Nursery (early years) REST route blueprints.

One blueprint per nursery domain module. Registered by the unified
server under /api/<version>/nursery/.
"""

from education_system.systems.nursery.interfaces.api.routes.accident_log_routes import (
    accident_log_bp,
)
from education_system.systems.nursery.interfaces.api.routes.accident_report_routes import (
    accident_report_bp,
)
from education_system.systems.nursery.interfaces.api.routes.activity_feed_routes import (
    activity_feed_bp,
)
from education_system.systems.nursery.interfaces.api.routes.admissions_routes import (
    admissions_bp,
)
from education_system.systems.nursery.interfaces.api.routes.allergies_routes import (
    allergies_bp,
)
from education_system.systems.nursery.interfaces.api.routes.appraisals_routes import (
    appraisals_bp,
)
from education_system.systems.nursery.interfaces.api.routes.attendance_report_routes import (
    attendance_report_bp,
)
from education_system.systems.nursery.interfaces.api.routes.audit_reports_routes import (
    audit_reports_bp,
)
from education_system.systems.nursery.interfaces.api.routes.bottle_feeds_routes import (
    bottle_feeds_bp,
)
from education_system.systems.nursery.interfaces.api.routes.childcare_vouchers_routes import (
    childcare_vouchers_bp,
)
from education_system.systems.nursery.interfaces.api.routes.children_routes import (
    children_bp,
)
from education_system.systems.nursery.interfaces.api.routes.cohort_tracking_routes import (
    cohort_tracking_bp,
)
from education_system.systems.nursery.interfaces.api.routes.complaints_routes import (
    complaints_bp,
)
from education_system.systems.nursery.interfaces.api.routes.concerns_routes import (
    concerns_bp,
)
from education_system.systems.nursery.interfaces.api.routes.consents_routes import (
    consents_bp,
)
from education_system.systems.nursery.interfaces.api.routes.curriculum_planning_routes import (
    curriculum_planning_bp,
)
from education_system.systems.nursery.interfaces.api.routes.daily_diary_routes import (
    daily_diary_bp,
)
from education_system.systems.nursery.interfaces.api.routes.daily_register_routes import (
    daily_register_bp,
)
from education_system.systems.nursery.interfaces.api.routes.daily_updates_routes import (
    daily_updates_bp,
)
from education_system.systems.nursery.interfaces.api.routes.data_export_routes import (
    data_export_bp,
)
from education_system.systems.nursery.interfaces.api.routes.dbs_checks_routes import (
    dbs_checks_bp,
)
from education_system.systems.nursery.interfaces.api.routes.development_tracking_routes import (
    development_tracking_bp,
)
from education_system.systems.nursery.interfaces.api.routes.discounts_routes import (
    discounts_bp,
)
from education_system.systems.nursery.interfaces.api.routes.dsl_routes import (
    dsl_bp,
)
from education_system.systems.nursery.interfaces.api.routes.effective_learning_routes import (
    effective_learning_bp,
)
from education_system.systems.nursery.interfaces.api.routes.ehc_plans_routes import (
    ehc_plans_bp,
)
from education_system.systems.nursery.interfaces.api.routes.emergency_contacts_routes import (
    emergency_contacts_bp,
)
from education_system.systems.nursery.interfaces.api.routes.enrolment_routes import (
    enrolment_bp,
)
from education_system.systems.nursery.interfaces.api.routes.evidence_routes import (
    evidence_bp,
)
from education_system.systems.nursery.interfaces.api.routes.existing_injuries_routes import (
    existing_injuries_bp,
)
from education_system.systems.nursery.interfaces.api.routes.expense_claims_routes import (
    expense_claims_bp,
)
from education_system.systems.nursery.interfaces.api.routes.eyfs_compliance_routes import (
    eyfs_compliance_bp,
)
from education_system.systems.nursery.interfaces.api.routes.eyfs_profile_routes import (
    eyfs_profile_bp,
)
from education_system.systems.nursery.interfaces.api.routes.feedback_routes import (
    feedback_bp,
)
from education_system.systems.nursery.interfaces.api.routes.first_aid_routes import (
    first_aid_bp,
)
from education_system.systems.nursery.interfaces.api.routes.funded_hours_routes import (
    funded_hours_bp,
)
from education_system.systems.nursery.interfaces.api.routes.funding_claims_routes import (
    funding_claims_bp,
)
from education_system.systems.nursery.interfaces.api.routes.funding_report_routes import (
    funding_report_bp,
)
from education_system.systems.nursery.interfaces.api.routes.gdpr_routes import (
    gdpr_bp,
)
from education_system.systems.nursery.interfaces.api.routes.invoices_routes import (
    invoices_bp,
)
from education_system.systems.nursery.interfaces.api.routes.key_persons_routes import (
    key_persons_bp,
)
from education_system.systems.nursery.interfaces.api.routes.learning_journeys_routes import (
    learning_journeys_bp,
)
from education_system.systems.nursery.interfaces.api.routes.leavers_routes import (
    leavers_bp,
)
from education_system.systems.nursery.interfaces.api.routes.looked_after_routes import (
    looked_after_bp,
)
from education_system.systems.nursery.interfaces.api.routes.meals_routes import (
    meals_bp,
)
from education_system.systems.nursery.interfaces.api.routes.medication_log_routes import (
    medication_log_bp,
)
from education_system.systems.nursery.interfaces.api.routes.messaging_routes import (
    messaging_bp,
)
from education_system.systems.nursery.interfaces.api.routes.newsletters_routes import (
    newsletters_bp,
)
from education_system.systems.nursery.interfaces.api.routes.next_steps_routes import (
    next_steps_bp,
)
from education_system.systems.nursery.interfaces.api.routes.observations_routes import (
    observations_bp,
)
from education_system.systems.nursery.interfaces.api.routes.occupancy_report_routes import (
    occupancy_report_bp,
)
from education_system.systems.nursery.interfaces.api.routes.occupancy_routes import (
    occupancy_bp,
)
from education_system.systems.nursery.interfaces.api.routes.ofsted_routes import (
    ofsted_bp,
)
from education_system.systems.nursery.interfaces.api.routes.parent_contacts_routes import (
    parent_contacts_bp,
)
from education_system.systems.nursery.interfaces.api.routes.parent_meetings_routes import (
    parent_meetings_bp,
)
from education_system.systems.nursery.interfaces.api.routes.payments_routes import (
    payments_bp,
)
from education_system.systems.nursery.interfaces.api.routes.policies_routes import (
    policies_bp,
)
from education_system.systems.nursery.interfaces.api.routes.prevent_duty_routes import (
    prevent_duty_bp,
)
from education_system.systems.nursery.interfaces.api.routes.progress_check_2yr_routes import (
    progress_check_2yr_bp,
)
from education_system.systems.nursery.interfaces.api.routes.qualifications_routes import (
    qualifications_bp,
)
from education_system.systems.nursery.interfaces.api.routes.ratios_routes import (
    ratios_bp,
)
from education_system.systems.nursery.interfaces.api.routes.recruitment_routes import (
    recruitment_bp,
)
from education_system.systems.nursery.interfaces.api.routes.risk_assessments_routes import (
    risk_assessments_bp,
)
from education_system.systems.nursery.interfaces.api.routes.rooms_routes import (
    rooms_bp,
)
from education_system.systems.nursery.interfaces.api.routes.rota_routes import (
    rota_bp,
)
from education_system.systems.nursery.interfaces.api.routes.safeguarding_routes import (
    safeguarding_bp,
)
from education_system.systems.nursery.interfaces.api.routes.send_routes import (
    send_bp,
)
from education_system.systems.nursery.interfaces.api.routes.settling_in_routes import (
    settling_in_bp,
)
from education_system.systems.nursery.interfaces.api.routes.sign_in_out_routes import (
    sign_in_out_bp,
)
from education_system.systems.nursery.interfaces.api.routes.sleep_log_routes import (
    sleep_log_bp,
)
from education_system.systems.nursery.interfaces.api.routes.staff_absence_routes import (
    staff_absence_bp,
)
from education_system.systems.nursery.interfaces.api.routes.staff_routes import (
    staff_bp,
)
from education_system.systems.nursery.interfaces.api.routes.toileting_log_routes import (
    toileting_log_bp,
)
from education_system.systems.nursery.interfaces.api.routes.transitions_routes import (
    transitions_bp,
)
from education_system.systems.nursery.interfaces.api.routes.user_management_routes import (
    user_management_bp,
)
from education_system.systems.nursery.interfaces.api.routes.visitors_routes import (
    visitors_bp,
)
from education_system.systems.nursery.interfaces.api.routes.welfare_routes import (
    welfare_bp,
)
from education_system.systems.nursery.interfaces.api.routes.wellbeing_routes import (
    wellbeing_bp,
)

__all__ = [
    "accident_log_bp",
    "accident_report_bp",
    "activity_feed_bp",
    "admissions_bp",
    "allergies_bp",
    "appraisals_bp",
    "attendance_report_bp",
    "audit_reports_bp",
    "bottle_feeds_bp",
    "childcare_vouchers_bp",
    "children_bp",
    "cohort_tracking_bp",
    "complaints_bp",
    "concerns_bp",
    "consents_bp",
    "curriculum_planning_bp",
    "daily_diary_bp",
    "daily_register_bp",
    "daily_updates_bp",
    "data_export_bp",
    "dbs_checks_bp",
    "development_tracking_bp",
    "discounts_bp",
    "dsl_bp",
    "effective_learning_bp",
    "ehc_plans_bp",
    "emergency_contacts_bp",
    "enrolment_bp",
    "evidence_bp",
    "existing_injuries_bp",
    "expense_claims_bp",
    "eyfs_compliance_bp",
    "eyfs_profile_bp",
    "feedback_bp",
    "first_aid_bp",
    "funded_hours_bp",
    "funding_claims_bp",
    "funding_report_bp",
    "gdpr_bp",
    "invoices_bp",
    "key_persons_bp",
    "learning_journeys_bp",
    "leavers_bp",
    "looked_after_bp",
    "meals_bp",
    "medication_log_bp",
    "messaging_bp",
    "newsletters_bp",
    "next_steps_bp",
    "observations_bp",
    "occupancy_report_bp",
    "occupancy_bp",
    "ofsted_bp",
    "parent_contacts_bp",
    "parent_meetings_bp",
    "payments_bp",
    "policies_bp",
    "prevent_duty_bp",
    "progress_check_2yr_bp",
    "qualifications_bp",
    "ratios_bp",
    "recruitment_bp",
    "risk_assessments_bp",
    "rooms_bp",
    "rota_bp",
    "safeguarding_bp",
    "send_bp",
    "settling_in_bp",
    "sign_in_out_bp",
    "sleep_log_bp",
    "staff_absence_bp",
    "staff_bp",
    "toileting_log_bp",
    "transitions_bp",
    "user_management_bp",
    "visitors_bp",
    "welfare_bp",
    "wellbeing_bp",
]

ALL_BLUEPRINTS = (
    accident_log_bp,
    accident_report_bp,
    activity_feed_bp,
    admissions_bp,
    allergies_bp,
    appraisals_bp,
    attendance_report_bp,
    audit_reports_bp,
    bottle_feeds_bp,
    childcare_vouchers_bp,
    children_bp,
    cohort_tracking_bp,
    complaints_bp,
    concerns_bp,
    consents_bp,
    curriculum_planning_bp,
    daily_diary_bp,
    daily_register_bp,
    daily_updates_bp,
    data_export_bp,
    dbs_checks_bp,
    development_tracking_bp,
    discounts_bp,
    dsl_bp,
    effective_learning_bp,
    ehc_plans_bp,
    emergency_contacts_bp,
    enrolment_bp,
    evidence_bp,
    existing_injuries_bp,
    expense_claims_bp,
    eyfs_compliance_bp,
    eyfs_profile_bp,
    feedback_bp,
    first_aid_bp,
    funded_hours_bp,
    funding_claims_bp,
    funding_report_bp,
    gdpr_bp,
    invoices_bp,
    key_persons_bp,
    learning_journeys_bp,
    leavers_bp,
    looked_after_bp,
    meals_bp,
    medication_log_bp,
    messaging_bp,
    newsletters_bp,
    next_steps_bp,
    observations_bp,
    occupancy_report_bp,
    occupancy_bp,
    ofsted_bp,
    parent_contacts_bp,
    parent_meetings_bp,
    payments_bp,
    policies_bp,
    prevent_duty_bp,
    progress_check_2yr_bp,
    qualifications_bp,
    ratios_bp,
    recruitment_bp,
    risk_assessments_bp,
    rooms_bp,
    rota_bp,
    safeguarding_bp,
    send_bp,
    settling_in_bp,
    sign_in_out_bp,
    sleep_log_bp,
    staff_absence_bp,
    staff_bp,
    toileting_log_bp,
    transitions_bp,
    user_management_bp,
    visitors_bp,
    welfare_bp,
    wellbeing_bp,
)
