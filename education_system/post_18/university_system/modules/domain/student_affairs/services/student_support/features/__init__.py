"""
Feature modules for student support.
"""

from education_system.post_18.university_system.modules.domain.student_affairs.services.student_support.features.templates import (
    create_response_template,
    create_response_template_interactive,
    create_ticket_template,
    create_ticket_template_interactive,
    get_response_templates,
    get_ticket_templates,
    manage_templates_menu,
    show_template_statistics,
    view_response_templates,
    view_ticket_templates,
)
from education_system.post_18.university_system.modules.domain.student_affairs.services.student_support.features.knowledge_base import (
    browse_knowledge_base,
    create_kb_article,
    create_kb_article_interactive,
    display_article_list,
    display_full_article,
    get_kb_articles,
    manage_knowledge_base_menu,
    publish_kb_article,
    publish_kb_article_interactive,
    show_kb_statistics,
    view_all_kb_articles,
)
from education_system.post_18.university_system.modules.domain.student_affairs.services.student_support.features.search import (
    advanced_search,
    perform_advanced_search,
    _search_faqs,
    _search_resources,
)
from education_system.post_18.university_system.modules.domain.student_affairs.services.student_support.features.knowledge_base import (
    _search_knowledge_base,
)
from education_system.post_18.university_system.modules.domain.student_affairs.services.student_support.features.notifications import (
    get_user_notifications,
    mark_notification_read,
    view_notifications,
)
from education_system.post_18.university_system.modules.domain.student_affairs.services.student_support.features.dashboard import (
    display_dashboard,
    display_support_menu,
    get_dashboard_data,
)
from education_system.post_18.university_system.modules.domain.student_affairs.services.student_support.features.reports import (
    generate_reports,
    generate_reports_menu,
)

__all__ = [
    # Templates
    'get_ticket_templates',
    'get_response_templates',
    'create_ticket_template',
    'create_response_template',
    'manage_templates_menu',
    'view_ticket_templates',
    'create_ticket_template_interactive',
    'view_response_templates',
    'create_response_template_interactive',
    'show_template_statistics',

    # Knowledge Base
    'create_kb_article',
    'get_kb_articles',
    'publish_kb_article',
    'manage_knowledge_base_menu',
    'view_all_kb_articles',
    'create_kb_article_interactive',
    'publish_kb_article_interactive',
    'show_kb_statistics',
    'browse_knowledge_base',
    'display_article_list',
    'display_full_article',

    # Search
    'advanced_search',
    'perform_advanced_search',

    # Notifications
    'get_user_notifications',
    'mark_notification_read',
    'view_notifications',

    # Dashboard
    'get_dashboard_data',
    'display_dashboard',
    'display_support_menu',

    # Reports
    'generate_reports',
    'generate_reports_menu',
]
