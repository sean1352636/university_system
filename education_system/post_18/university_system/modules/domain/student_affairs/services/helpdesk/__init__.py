# helpdesk package - split from monolithic helpdesk.py
# All public functions are re-exported here for backward compatibility.

from education_system.post_18.university_system.modules.domain.student_affairs.services.helpdesk.database import (
    init_helpdesk_db,
    init_default_data,
)

from education_system.post_18.university_system.modules.domain.student_affairs.services.helpdesk.notifications import (
    escalate_ticket_manual,
    send_satisfaction_survey,
    save_report_to_file,
)

from education_system.post_18.university_system.modules.domain.student_affairs.services.helpdesk.workflows import (
    run_ticket_workflows,
    check_workflow_conditions,
    execute_workflow_actions,
    escalate_ticket,
    log_ticket_action,
)

from education_system.post_18.university_system.modules.domain.student_affairs.services.helpdesk.permissions import (
    setup_enhanced_helpdesk_permissions,
)

from education_system.post_18.university_system.modules.domain.student_affairs.services.helpdesk.bulk import (
    view_all_tickets_enhanced,
    bulk_assign_tickets,
    bulk_status_change,
    export_ticket_list,
)

from education_system.post_18.university_system.modules.domain.student_affairs.services.helpdesk.menus import (
    display_helpdesk_menu,
    system_management_menu,
    check_overdue_tickets,
    view_user_tickets_enhanced,
)

from education_system.post_18.university_system.modules.domain.student_affairs.services.helpdesk.knowledge_base import (
    manage_knowledge_base,
    view_kb_articles,
    view_kb_article_detail,
    create_kb_article,
    edit_kb_article,
    search_kb_articles,
    kb_statistics,
)

from education_system.post_18.university_system.modules.domain.student_affairs.services.helpdesk.maintenance import (
    system_maintenance,
    database_cleanup,
    rebuild_search_indexes,
    check_data_integrity,
    backup_database,
)

from education_system.post_18.university_system.modules.domain.student_affairs.services.helpdesk.data_io import (
    data_import_export,
    export_tickets_csv,
    export_users_csv,
    import_tickets_csv,
    export_analytics_data,
)

# Tickets subpackage
from education_system.post_18.university_system.modules.domain.student_affairs.services.helpdesk.tickets.creation import (
    create_ticket_enhanced,
    create_ticket_from_template,
    get_form_field_value,
    create_custom_ticket,
    get_priority_selection,
    get_impact_selection,
    get_urgency_selection,
    create_ticket_with_details,
)

from education_system.post_18.university_system.modules.domain.student_affairs.services.helpdesk.tickets.display import (
    display_kb_suggestions,
    display_ticket_replies,
    display_time_tracking,
    display_escalation_history,
    display_audit_trail,
    display_ticket_actions,
    execute_ticket_action,
    display_ticket_attachments,
    display_linked_tickets,
    view_ticket_detail_enhanced,
)

from education_system.post_18.university_system.modules.domain.student_affairs.services.helpdesk.tickets.operations import (
    reply_to_ticket_enhanced,
    change_ticket_status_enhanced,
    assign_ticket_enhanced,
    add_time_entry,
    link_tickets,
)

from education_system.post_18.university_system.modules.domain.student_affairs.services.helpdesk.tickets.attachments import (
    handle_file_attachments,
    add_attachment,
    suggest_knowledge_base_articles,
    extract_keywords,
)

from education_system.post_18.university_system.modules.domain.student_affairs.services.helpdesk.tickets.search import (
    advanced_search_tickets,
    save_search_criteria,
    load_saved_searches,
    execute_search,
    display_search_results,
)

# Analytics subpackage
from education_system.post_18.university_system.modules.domain.student_affairs.services.helpdesk.analytics.dashboard import (
    generate_analytics_dashboard,
    export_analytics_report,
)

from education_system.post_18.university_system.modules.domain.student_affairs.services.helpdesk.analytics.reports import (
    generate_enhanced_ticket_report,
    generate_executive_summary,
    generate_staff_performance_report,
    generate_sla_compliance_report,
    generate_satisfaction_report,
    generate_trend_analysis_report,
    generate_department_report,
    generate_custom_date_report,
)

# Admin subpackage
from education_system.post_18.university_system.modules.domain.student_affairs.services.helpdesk.admin.sla import (
    manage_sla_policies,
    view_sla_policies,
    create_sla_policy,
    edit_sla_policy,
    toggle_sla_policy,
)

from education_system.post_18.university_system.modules.domain.student_affairs.services.helpdesk.admin.templates import (
    manage_ticket_templates,
    view_ticket_templates,
    create_ticket_template,
    edit_ticket_template,
    toggle_ticket_template,
)

from education_system.post_18.university_system.modules.domain.student_affairs.services.helpdesk.admin.admin_workflows import (
    manage_workflows,
    view_workflows,
    create_workflow,
    edit_workflow,
    toggle_workflow,
)

from education_system.post_18.university_system.modules.domain.student_affairs.services.helpdesk.admin.departments import (
    manage_departments,
    view_departments,
    create_department,
    edit_department,
    toggle_department,
)

from education_system.post_18.university_system.modules.domain.student_affairs.services.helpdesk.admin.organizations import (
    manage_organizations,
    view_organizations,
    create_organization,
    edit_organization,
)
