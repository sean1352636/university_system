"""
Automation modules for escalations, sentiment analysis, and background tasks.

(The ImportError fallbacks that used to duplicate every function here —
including writes to the removed ``notifications`` table — are gone: these
modules are part of the package and import cleanly.)
"""

from education_system.systems.university.domains.student_support.domain.student_support.automation.escalations import (
    _process_escalations,
    _apply_escalation_rule,
    _escalate_ticket,
    _create_escalation_notification,
    _reassign_ticket,
    _process_sla_breaches,
)
from education_system.systems.university.domains.student_support.domain.student_support.automation.sentiment_analysis import (
    _analyze_sentiment,
    _suggest_category,
    _get_auto_assignment,
    _estimate_resolution_time,
)
from education_system.systems.university.domains.student_support.domain.student_support.automation.background_tasks import (
    _start_background_tasks,
    _process_notification_queue,
    _update_metrics,
    _load_staff_assignments,
)

__all__ = [
    '_process_escalations',
    '_apply_escalation_rule',
    '_escalate_ticket',
    '_create_escalation_notification',
    '_reassign_ticket',
    '_process_sla_breaches',
    '_analyze_sentiment',
    '_suggest_category',
    '_get_auto_assignment',
    '_estimate_resolution_time',
    '_start_background_tasks',
    '_process_notification_queue',
    '_update_metrics',
    '_load_staff_assignments',
]
