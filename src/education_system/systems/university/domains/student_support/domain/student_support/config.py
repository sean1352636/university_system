"""
Configuration and constants for the Student Support module.

This module defines all configuration parameters, enums, and constants
used throughout the student support system.
"""

from dataclasses import dataclass
from enum import Enum
from typing import List
from education_system.paths import UNIVERSITY_DEFAULT_DB_PATH


# Enhanced Constants
SUPPORT_DB = str(UNIVERSITY_DEFAULT_DB_PATH)
# Display labels of the one status vocabulary (stored values are the keys of
# schema.STATUS_LABELS: 'open', 'in_progress', ...). Any of these labels, or
# the older 'On Hold' / 'Pending', is accepted wherever a status is set.
TICKET_STATUSES = ['Open', 'In Progress', 'Waiting on Student', 'Escalated', 'Resolved', 'Closed']
TICKET_STATUS_VALUES = ['open', 'in_progress', 'waiting_on_student', 'escalated', 'resolved', 'closed']
TICKET_PRIORITIES = ['Low', 'Medium', 'High', 'Urgent', 'Critical']
# The categories offered for new tickets (UK student services; each routes
# to a team — see routing.CATEGORY_TEAM). Tickets raised before keep their
# old value (LEGACY_SUPPORT_CATEGORIES); routing.uk_category /
# routing.category_label map an old value to its UK category.
SUPPORT_CATEGORIES = [
    'International/Visa', 'Wellbeing', 'Disability & Reasonable Adjustments',
    'Accommodation', 'Fees & Funding', 'Academic Registry', 'IT', 'Careers', 'General'
]
LEGACY_SUPPORT_CATEGORIES = [
    'Academic', 'Technical', 'Financial Aid',
    'Library Services', 'Accommodation', 'Accessibility',
    'Mental Health', 'Registration', 'Housing', 'Dining',
    'Parking', 'Career Services', 'Student Activities', 'Other'
]


# New enums for enhanced features
class NotificationType(Enum):
    """Types of notifications supported by the system."""
    EMAIL = "email"
    IN_APP = "in_app"
    PUSH = "push"


class TicketSentiment(Enum):
    """Sentiment classification for ticket analysis."""
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    FRUSTRATED = "frustrated"


class FileType(Enum):
    """File type classification for attachments."""
    IMAGE = "image"
    DOCUMENT = "document"
    VIDEO = "video"
    OTHER = "other"


# Configuration class
@dataclass
class SupportConfig:
    """
    Configuration settings for the student support system.

    Attributes
    ----------
    max_file_size : int
        Maximum file size for attachments in bytes (default: 10MB)
    allowed_file_types : List[str]
        List of allowed file extensions for attachments
    auto_assign_enabled : bool
        Whether to automatically assign tickets to staff
    escalation_time_hours : int
        Hours before tickets are automatically escalated
    satisfaction_survey_enabled : bool
        Whether to send satisfaction surveys after ticket resolution
    ai_suggestions_enabled : bool
        Whether to enable AI-powered suggestions
    """
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    allowed_file_types: List[str] = None
    auto_assign_enabled: bool = True
    escalation_time_hours: int = 24
    satisfaction_survey_enabled: bool = True
    ai_suggestions_enabled: bool = True

    def __post_init__(self):
        """Initialize default allowed file types if not provided."""
        if self.allowed_file_types is None:
            self.allowed_file_types = [
                '.pdf', '.doc', '.docx', '.txt', '.png', '.jpg', '.jpeg',
                '.gif', '.bmp', '.zip', '.rar', '.csv', '.xlsx'
            ]
