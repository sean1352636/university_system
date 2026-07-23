"""
Configuration and constants for the Student Support module.

This module defines all configuration parameters, enums, and constants
used throughout the student support system.
"""

from dataclasses import dataclass
from enum import Enum
from typing import List
from education_system.post_18.university_system.core.paths import DEFAULT_DB_PATH


# Enhanced Constants
SUPPORT_DB = str(DEFAULT_DB_PATH)
TICKET_STATUSES = ['Open', 'In Progress', 'Resolved', 'Closed', 'Escalated', 'On Hold']
TICKET_PRIORITIES = ['Low', 'Medium', 'High', 'Urgent', 'Critical']
SUPPORT_CATEGORIES = [
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
