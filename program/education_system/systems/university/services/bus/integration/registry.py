"""Subscriber registration definitions."""
from education_system.systems.university.services.events.in_process import (
    EVENT_CASE_OPENED, EVENT_COURSE_CHANGED, EVENT_ENROLMENT_CHANGED,
    EVENT_EXAM_CHANGED, EVENT_INCIDENT_LOGGED, EVENT_MODULE_SCHEDULE_CHANGED,
    EVENT_SELECTION_CHANGED, EVENT_STAFF_AVAILABILITY_CHANGED, EVENT_TERM_CHANGED,
)
from .admissions.subscribers import (
    _on_adjustment_approved, _on_admissions_decision, _on_apl_approved,
    _on_clearing_accepted,
)
from .assessment.subscribers import _on_exam_event, _on_module_schedule_changed_for_exams
from .campus.events import _on_event_check_in
from .campus.housing import _on_housing_move_out
from .campus.parking import _on_permit_issued
from .curriculum.subscribers import _on_demand_forecast, _on_term_changed, _on_timetable_locked
from .enrolment.subscribers import _on_enrolment_added, _on_enrolment_withdrew
from .finance.subscribers import _on_grant_decided
from .safeguarding.subscribers import _on_case_opened_for_tutor_group, _on_health_risk_assessment
from .student_support.accommodation import _on_accommodation_decided
from .student_support.complaints import _on_complaint_filed
from .student_support.health import _on_health_appointment_booked
from .student_support.internships import _on_internship_placed
from .workforce.subscribers import _on_appraisal_completed, _on_staff_availability_changed

SUBSCRIBERS = (
    (EVENT_COURSE_CHANGED, _on_clearing_accepted),
    (EVENT_COURSE_CHANGED, _on_adjustment_approved),
    (EVENT_COURSE_CHANGED, _on_apl_approved),
    (EVENT_COURSE_CHANGED, _on_demand_forecast),
    (EVENT_STAFF_AVAILABILITY_CHANGED, _on_staff_availability_changed),
    (EVENT_MODULE_SCHEDULE_CHANGED, _on_timetable_locked),
    (EVENT_MODULE_SCHEDULE_CHANGED, _on_module_schedule_changed_for_exams),
    (EVENT_SELECTION_CHANGED, _on_appraisal_completed),
    (EVENT_EXAM_CHANGED, _on_exam_event),
    (EVENT_TERM_CHANGED, _on_term_changed),
    (EVENT_ENROLMENT_CHANGED, _on_enrolment_withdrew),
    (EVENT_INCIDENT_LOGGED, _on_health_risk_assessment),
    (EVENT_INCIDENT_LOGGED, _on_housing_move_out),
    (EVENT_INCIDENT_LOGGED, _on_permit_issued),
    (EVENT_INCIDENT_LOGGED, _on_complaint_filed),
    (EVENT_INCIDENT_LOGGED, _on_health_appointment_booked),
    (EVENT_SELECTION_CHANGED, _on_accommodation_decided),
    (EVENT_SELECTION_CHANGED, _on_grant_decided),
    (EVENT_SELECTION_CHANGED, _on_event_check_in),
    (EVENT_SELECTION_CHANGED, _on_internship_placed),
    (EVENT_SELECTION_CHANGED, _on_admissions_decision),
    (EVENT_CASE_OPENED, _on_case_opened_for_tutor_group),
    (EVENT_ENROLMENT_CHANGED, _on_enrolment_added),
)
