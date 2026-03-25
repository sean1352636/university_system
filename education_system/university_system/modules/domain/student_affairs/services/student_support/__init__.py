"""
Student Support Module - Refactored into modular structure.

This module provides comprehensive student support ticket management with
features including:
- Ticket creation and tracking
- Knowledge base management
- Advanced search and analytics
- Automated escalations and notifications
- Report generation
- Bulk operations

The module is organized into:
- config: Configuration and constants
- models: Data models
- database: Database schema and initialization
- auth: Authentication helpers
- core: Core ticket operations
- features: Additional features (templates, KB, search, etc.)
- operations: Bulk operations, export, merge
- automation: Background tasks, escalations, sentiment analysis
- utils: Utilities and helpers

For backward compatibility, all public functions are re-exported from this
__init__.py file.
"""

from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Import configuration
from education_system.university_system.modules.domain.student_affairs.services.student_support.config import (
    SUPPORT_DB,
    TICKET_STATUSES,
    TICKET_PRIORITIES,
    SUPPORT_CATEGORIES,
    NotificationType,
    TicketSentiment,
    FileType,
    SupportConfig,
)

# Import models
from education_system.university_system.modules.domain.student_affairs.services.student_support.models import (
    AttachmentData,
    DashboardData,
    KBArticleData,
    NotificationData,
    ReportData,
    ResponseData,
    SearchResult,
    TemplateData,
    TicketData,
)

# Import database functions
from education_system.university_system.modules.domain.student_affairs.services.student_support.database import init_enhanced_db

# Import auth functions
from education_system.university_system.modules.domain.student_affairs.services.student_support.auth import set_auth, get_auth_instance

# Import all submodules
from education_system.university_system.modules.domain.student_affairs.services.student_support import core
from education_system.university_system.modules.domain.student_affairs.services.student_support import features
from education_system.university_system.modules.domain.student_affairs.services.student_support import operations
from education_system.university_system.modules.domain.student_affairs.services.student_support import automation
from education_system.university_system.modules.domain.student_affairs.services.student_support import utils

# Re-export all public functions for backward compatibility
from education_system.university_system.modules.domain.student_affairs.services.student_support.core import (
    add_response_enhanced,
    add_ticket_response,
    create_support_ticket,
    display_ticket_details_enhanced,
    download_attachment,
    download_attachment_menu,
    get_student_tickets,
    get_ticket_attachments,
    get_ticket_details,
    get_ticket_history,
    update_ticket_status,
    update_status_enhanced,
    add_internal_note,
    use_ticket_template,
    view_all_tickets_enhanced,
    view_my_tickets_enhanced,
    view_ticket_history,
)
from education_system.university_system.modules.domain.student_affairs.services.student_support.features import (
    advanced_search,
    browse_knowledge_base,
    create_kb_article,
    create_kb_article_interactive,
    create_response_template,
    create_response_template_interactive,
    create_ticket_template,
    create_ticket_template_interactive,
    display_article_list,
    display_dashboard,
    display_full_article,
    display_support_menu,
    generate_reports,
    generate_reports_menu,
    get_dashboard_data,
    get_kb_articles,
    get_response_templates,
    get_ticket_templates,
    get_user_notifications,
    manage_knowledge_base_menu,
    manage_templates_menu,
    mark_notification_read,
    perform_advanced_search,
    publish_kb_article,
    publish_kb_article_interactive,
    show_kb_statistics,
    show_template_statistics,
    view_all_kb_articles,
    view_notifications,
    view_response_templates,
    view_ticket_templates,
)
from education_system.university_system.modules.domain.student_affairs.services.student_support.operations import (
    bulk_assign_tickets_menu,
    bulk_operations_menu,
    bulk_update_category_menu,
    bulk_update_priority_menu,
    bulk_update_status_menu,
    bulk_update_tickets,
    export_data,
    export_data_menu,
    export_filtered_results,
    export_filtered_tickets_menu,
    export_metrics_menu,
    export_responses_menu,
    export_tickets_menu,
    merge_tickets,
    merge_tickets_menu,
    perform_bulk_assign,
)
from education_system.university_system.modules.domain.student_affairs.services.student_support.automation import (
    _apply_escalation_rule,
    _create_escalation_notification,
    _escalate_ticket,
    _estimate_resolution_time,
    _get_auto_assignment,
    _load_staff_assignments,
    _process_escalations,
    _process_notification_queue,
    _reassign_ticket,
    _start_background_tasks,
    _suggest_category,
    _update_metrics,
    _analyze_sentiment,
)
from education_system.university_system.modules.domain.student_affairs.services.student_support.utils import (
    _record_status_change_metrics,
    apply_student_support_fixes,
    audit_action,
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
    submit_satisfaction_rating,
    truncate_text,
    update_user_preferences,
    validate_ticket_permissions,
)


class EnhancedStudentSupport:
    """
    Enhanced Student Support System with comprehensive ticket management.

    This class provides a unified interface to all student support functionality.
    It delegates to specialized modules for different aspects of support operations.

    Attributes
    ----------
    config : SupportConfig
        Configuration settings for the support system
    notification_queue : list
        Queue for pending notifications
    staff_assignments : dict
        Mapping of categories to assigned staff members

    Examples
    --------
    >>> support = EnhancedStudentSupport()
    >>> ticket_id = support.create_support_ticket(
    ...     student_id='S12345',
    ...     title='Cannot access course materials',
    ...     description='Getting 404 error when clicking course link',
    ...     category='Technical',
    ...     priority='High'
    ... )
    """

    def __init__(self, config: Optional[SupportConfig] = None):
        """
        Initialize the enhanced student support system.

        Parameters
        ----------
        config : SupportConfig, optional
            Configuration settings. If not provided, defaults are used.
        """
        self.config = config or SupportConfig()
        self.notification_queue = []
        self.staff_assignments = {}

        try:
            self.init_enhanced_db()
            self._load_staff_assignments()
            self._start_background_tasks()
            logger.info("Enhanced StudentSupport initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Enhanced StudentSupport: {e}")
            raise

    def init_enhanced_db(self):
        """Initialize the enhanced support database with new tables."""
        init_enhanced_db()

    # === Core Ticket Operations ===
    def create_support_ticket(self, student_id, title, description, category, priority='Medium',
                              template_id=None, attachments=None, tags=None):
        """Create a new support ticket with enhanced features."""
        return core.create_support_ticket(
            student_id, title, description, category, priority,
            template_id, attachments, tags
        )

    def get_student_tickets(self, student_id=None, filters=None, page=1, per_page=20):
        """Get support tickets for a student with filtering and pagination."""
        return core.get_student_tickets(student_id, filters, page, per_page)

    def get_ticket_details(self, ticket_id):
        """Get detailed information about a specific ticket."""
        return core.get_ticket_details(ticket_id)

    def get_ticket_attachments(self, ticket_id):
        """Get all attachments for a ticket."""
        return core.get_ticket_attachments(ticket_id)

    def download_attachment(self, attachment_id):
        """Download a specific attachment."""
        return core.download_attachment(attachment_id)

    def get_ticket_history(self, ticket_id):
        """Get complete history of a ticket including all changes and responses."""
        return core.get_ticket_history(ticket_id)

    # === Response Management ===
    def add_ticket_response(self, ticket_id, response_text, template_id=None,
                            is_internal=False, attachments=None):
        """Add a response to a support ticket."""
        return core.add_ticket_response(
            ticket_id, response_text, template_id, is_internal, attachments
        )

    # === Status Management ===
    def update_ticket_status(self, ticket_id, new_status, resolution_notes=None):
        """Update the status of a support ticket."""
        return core.update_ticket_status(ticket_id, new_status, resolution_notes)

    # === Template Management ===
    def get_ticket_templates(self):
        """Get all available ticket templates."""
        return features.get_ticket_templates()

    def get_response_templates(self, category=None):
        """Get response templates, optionally filtered by category."""
        return features.get_response_templates(category)

    def create_ticket_template(self, name, title_template, description_template,
                               category, priority):
        """Create a new ticket template."""
        return features.create_ticket_template(
            name, title_template, description_template, category, priority
        )

    def create_response_template(self, name, subject, content, category=None, variables=None):
        """Create a new response template."""
        return features.create_response_template(name, subject, content, category, variables)

    # === Knowledge Base ===
    def create_kb_article(self, title, content, category, summary=None, tags=None, is_published=False):
        """Create a new knowledge base article."""
        return features.create_kb_article(title, content, category, summary, tags, is_published)

    def get_kb_articles(self, category=None, published_only=True):
        """Get knowledge base articles."""
        return features.get_kb_articles(category, published_only)

    def publish_kb_article(self, article_id):
        """Publish a knowledge base article."""
        return features.publish_kb_article(article_id)

    # === Search ===
    def advanced_search(self, query, search_type='global', filters=None, page=1, per_page=20):
        """Perform advanced search across tickets, FAQs, and resources."""
        return features.advanced_search(query, search_type, filters, page, per_page)

    def _search_faqs(self, query, filters=None):
        """Search FAQs with relevance scoring."""
        return features._search_faqs(query, filters)

    def _search_knowledge_base(self, query, filters=None):
        """Search knowledge base articles."""
        return features._search_knowledge_base(query, filters)

    # === Notifications ===
    def get_user_notifications(self, user_id=None, unread_only=False):
        """Get notifications for a user."""
        return features.get_user_notifications(user_id, unread_only)

    def mark_notification_read(self, notification_id, user_id=None):
        """Mark a notification as read."""
        return features.mark_notification_read(notification_id, user_id)

    # === Dashboard ===
    def get_dashboard_data(self, user_role, user_id):
        """Get dashboard data for a user."""
        return features.get_dashboard_data(user_role, user_id)

    # === Reports ===
    def generate_reports(self, report_type, date_range, filters=None):
        """Generate various reports."""
        return features.generate_reports(report_type, date_range, filters)

    # === Bulk Operations ===
    def bulk_update_tickets(self, ticket_ids, updates):
        """Update multiple tickets at once."""
        return operations.bulk_update_tickets(ticket_ids, updates)

    def merge_tickets(self, primary_ticket_id, secondary_ticket_ids, merge_reason):
        """Merge multiple tickets into one."""
        return operations.merge_tickets(primary_ticket_id, secondary_ticket_ids, merge_reason)

    # === Export ===
    def export_data(self, export_type, filters=None, format='csv'):
        """Export data in various formats."""
        return operations.export_data(export_type, filters, format)

    # === User Preferences ===
    def get_user_preferences(self, user_id=None):
        """Get user preferences."""
        return utils.get_user_preferences(user_id)

    def update_user_preferences(self, preferences, user_id=None):
        """Update user preferences."""
        return utils.update_user_preferences(preferences, user_id)

    def submit_satisfaction_rating(self, ticket_id, rating, feedback=None):
        """Submit satisfaction rating for a resolved ticket."""
        return utils.submit_satisfaction_rating(ticket_id, rating, feedback)

    # === Private/Internal Methods ===
    def _load_staff_assignments(self):
        """Load staff assignment mappings from database."""
        self.staff_assignments = automation._load_staff_assignments()

    def _start_background_tasks(self):
        """Start background tasks for escalation and notifications."""
        automation._start_background_tasks()

    def _log_audit(self, audit_data):
        """Log audit trail information."""
        utils._log_audit(audit_data)


# For backward compatibility - export the class and all functions
__all__ = [
    # Main class
    'EnhancedStudentSupport',

    # Config
    'SUPPORT_DB',
    'TICKET_STATUSES',
    'TICKET_PRIORITIES',
    'SUPPORT_CATEGORIES',
    'NotificationType',
    'TicketSentiment',
    'FileType',
    'SupportConfig',

    # Auth
    'set_auth',
    'get_auth_instance',

    # All core functions
    'create_support_ticket',
    'get_student_tickets',
    'get_ticket_details',
    'get_ticket_attachments',
    'download_attachment',
    'get_ticket_history',
    'add_ticket_response',
    'update_ticket_status',
    'view_my_tickets_enhanced',
    'use_ticket_template',
    'view_all_tickets_enhanced',
    'display_ticket_details_enhanced',
    'add_response_enhanced',
    'update_status_enhanced',
    'add_internal_note',
    'view_ticket_history',
    'download_attachment_menu',

    # Feature functions
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
    'advanced_search',
    'perform_advanced_search',
    'get_user_notifications',
    'mark_notification_read',
    'view_notifications',
    'get_dashboard_data',
    'display_dashboard',
    'display_support_menu',
    'generate_reports',
    'generate_reports_menu',

    # Operations
    'bulk_update_tickets',
    'perform_bulk_assign',
    'bulk_operations_menu',
    'bulk_assign_tickets_menu',
    'bulk_update_status_menu',
    'bulk_update_priority_menu',
    'bulk_update_category_menu',
    'export_filtered_results',
    'export_data',
    'export_data_menu',
    'export_tickets_menu',
    'export_responses_menu',
    'export_metrics_menu',
    'export_filtered_tickets_menu',
    'merge_tickets',
    'merge_tickets_menu',

    # Utilities
    'audit_action',
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
    'submit_satisfaction_rating',
]
