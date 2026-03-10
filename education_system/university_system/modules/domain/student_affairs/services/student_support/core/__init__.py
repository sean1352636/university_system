"""
Core ticket management modules.
"""

from education_system.university_system.modules.domain.student_affairs.services.student_support.core.ticket_manager import (
    create_support_ticket,
    display_ticket_details_enhanced,
    download_attachment,
    get_student_tickets,
    get_ticket_attachments,
    get_ticket_details,
    get_ticket_history,
    use_ticket_template,
    view_all_tickets_enhanced,
    view_my_tickets_enhanced,
)
from education_system.university_system.modules.domain.student_affairs.services.student_support.core.response_manager import (
    add_response_enhanced,
    add_ticket_response,
)
from education_system.university_system.modules.domain.student_affairs.services.student_support.core.status_manager import (
    add_internal_note,
    update_status_enhanced,
    update_ticket_status,
    view_ticket_history,
)
from education_system.university_system.modules.domain.student_affairs.services.student_support.core.attachment_manager import (
    download_attachment_menu,
)

__all__ = [
    # Ticket Manager
    'create_support_ticket',
    'get_student_tickets',
    'get_ticket_details',
    'get_ticket_attachments',
    'download_attachment',
    'get_ticket_history',
    'view_my_tickets_enhanced',
    'use_ticket_template',
    'view_all_tickets_enhanced',
    'display_ticket_details_enhanced',

    # Response Manager
    'add_ticket_response',
    'add_response_enhanced',

    # Status Manager
    'update_ticket_status',
    'update_status_enhanced',
    'add_internal_note',
    'view_ticket_history',

    # Attachment Manager
    'download_attachment_menu',
]
