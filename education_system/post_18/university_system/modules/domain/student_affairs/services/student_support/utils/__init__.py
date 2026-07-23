"""
Utility modules for audit, metrics, and helpers.
"""

from education_system.post_18.university_system.modules.domain.student_affairs.services.student_support.utils.audit import (
    audit_action,
)
from education_system.post_18.university_system.modules.domain.student_affairs.services.student_support.utils.metrics import (
    _record_status_change_metrics,
    _update_metrics,
    submit_satisfaction_rating,
)
from education_system.post_18.university_system.modules.domain.student_affairs.services.student_support.utils.helpers import (
    apply_student_support_fixes,
    create_enhanced_ticket,
    display_enhanced_faqs,
    display_enhanced_resources,
    display_faq_list,
    display_full_faq,
    display_full_resource,
    display_resource_list,
    fix_user_preferences_table,
    format_file_size,
    format_priority_display,
    format_ticket_status_display,
    get_user_preferences,
    get_user_preferences_safe,
    handle_support_error,
    manage_preferences,
    patch_enhanced_student_support,
    setup_enhanced_logging,
    truncate_text,
    update_user_preferences,
    validate_ticket_permissions,
)

__all__ = [
    # Audit
    'audit_action',

    # Metrics
    'submit_satisfaction_rating',
    '_record_status_change_metrics',
    '_update_metrics',

    # Helpers
    'setup_enhanced_logging',
    'get_user_preferences',
    'update_user_preferences',
    'get_user_preferences_safe',
    'manage_preferences',
    'validate_ticket_permissions',
    'format_ticket_status_display',
    'format_priority_display',
    'format_file_size',
    'truncate_text',
    'handle_support_error',
    'display_faq_list',
    'display_full_faq',
    'display_enhanced_faqs',
    'display_resource_list',
    'display_full_resource',
    'display_enhanced_resources',
    'patch_enhanced_student_support',
    'apply_student_support_fixes',
    'fix_user_preferences_table',
    'create_enhanced_ticket',
]
