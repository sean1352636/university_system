"""Cross-domain data adapters for the grade tracking GUI.

Same pattern as ``assignment_system/integrations/``: pure data
helpers so the GUI doesn't keep re-implementing queries against
other subsystems' tables.
"""

from education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.integrations.submissions import (
    fetch_assignment_submissions,
    fetch_graded_submission_count,
)
from education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.integrations.parent_portal import (
    fetch_child_grades,
)
from education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.integrations.external_examiners import (
    record_moderation_event,
    find_active_visit_for_module,
)
from education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.integrations.calendar_sync import (
    sync_assessment_to_calendar,
    remove_assessment_from_calendar,
)
from education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.integrations.attendance import (
    fetch_overall_attendance,
)
from education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.integrations.early_warning import (
    flag_at_risk_student,
)
from education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.integrations.student_support import (
    create_wellbeing_referral,
)
from education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.integrations.helpdesk import (
    file_grade_appeal_ticket,
)
from education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.integrations.kpi import (
    push_grade_kpi,
)
from education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.integrations.financial_aid import (
    notify_aid_of_gpa,
)
from education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.integrations.legal import (
    export_grade_audit_for_legal,
)
from education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.integrations.activity import (
    recent_early_warning_indicators,
    recent_wellbeing_referrals,
    recent_grade_appeal_tickets,
    recent_assessment_calendar_events,
    recent_aid_gpa_reviews,
    recent_grade_legal_cases,
)

__all__ = [
    "fetch_assignment_submissions",
    "fetch_graded_submission_count",
    "fetch_child_grades",
    "record_moderation_event",
    "find_active_visit_for_module",
    "sync_assessment_to_calendar",
    "remove_assessment_from_calendar",
    "fetch_overall_attendance",
    "flag_at_risk_student",
    "create_wellbeing_referral",
    "file_grade_appeal_ticket",
    "push_grade_kpi",
    "notify_aid_of_gpa",
    "export_grade_audit_for_legal",
    "recent_early_warning_indicators",
    "recent_wellbeing_referrals",
    "recent_grade_appeal_tickets",
    "recent_assessment_calendar_events",
    "recent_aid_gpa_reviews",
    "recent_grade_legal_cases",
]
