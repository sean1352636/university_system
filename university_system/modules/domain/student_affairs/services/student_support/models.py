"""
Data models and type definitions for the Student Support module.

This module defines the data structures used throughout the student support system,
including dataclasses for requests and responses.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime


@dataclass
class TicketData:
    """Data structure for a support ticket."""
    ticket_id: int
    student_id: str
    title: str
    description: str
    category: str
    priority: str
    status: str
    created_datetime: str
    updated_datetime: Optional[str] = None
    assigned_to: Optional[str] = None
    resolved_datetime: Optional[str] = None
    satisfaction_rating: Optional[int] = None
    satisfaction_feedback: Optional[str] = None
    sentiment: Optional[str] = None
    estimated_resolution_time: Optional[int] = None


@dataclass
class ResponseData:
    """Data structure for a ticket response."""
    response_id: int
    ticket_id: int
    responder_id: str
    response_text: str
    created_datetime: str
    is_internal: bool = False
    template_id: Optional[int] = None


@dataclass
class AttachmentData:
    """Data structure for a file attachment."""
    attachment_id: int
    ticket_id: int
    filename: str
    file_path: str
    file_size: int
    file_type: str
    uploaded_by: str
    uploaded_datetime: str


@dataclass
class NotificationData:
    """Data structure for a user notification."""
    notification_id: int
    user_id: str
    notification_type: str
    title: str
    message: str
    created_datetime: str
    is_read: bool = False
    read_datetime: Optional[str] = None
    related_ticket_id: Optional[int] = None
    expires_at: Optional[str] = None


@dataclass
class KBArticleData:
    """Data structure for a knowledge base article."""
    article_id: int
    title: str
    content: str
    category: str
    summary: Optional[str] = None
    tags: Optional[List[str]] = field(default_factory=list)
    is_published: bool = False
    created_by: Optional[str] = None
    created_datetime: Optional[str] = None
    updated_datetime: Optional[str] = None
    view_count: int = 0
    helpful_votes: int = 0


@dataclass
class TemplateData:
    """Data structure for a ticket or response template."""
    template_id: int
    template_type: str  # 'ticket' or 'response'
    name: str
    category: Optional[str] = None
    priority: Optional[str] = None
    title_template: Optional[str] = None
    description_template: Optional[str] = None
    subject: Optional[str] = None
    content: Optional[str] = None
    variables: Optional[List[str]] = field(default_factory=list)
    usage_count: int = 0
    created_by: Optional[str] = None
    created_datetime: Optional[str] = None


@dataclass
class SearchResult:
    """Data structure for search results."""
    result_type: str  # 'ticket', 'faq', 'resource', 'kb_article'
    result_id: int
    title: str
    snippet: str
    relevance_score: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DashboardData:
    """Data structure for dashboard statistics."""
    total_tickets: int = 0
    open_tickets: int = 0
    in_progress_tickets: int = 0
    resolved_tickets: int = 0
    closed_tickets: int = 0
    avg_resolution_time: Optional[float] = None
    satisfaction_rating: Optional[float] = None
    pending_responses: int = 0
    escalated_tickets: int = 0
    high_priority_tickets: int = 0
    recent_activity: List[Dict[str, Any]] = field(default_factory=list)
    category_breakdown: Dict[str, int] = field(default_factory=dict)


@dataclass
class ReportData:
    """Data structure for generated reports."""
    report_type: str
    generated_datetime: str
    date_range: Dict[str, str]
    filters: Dict[str, Any]
    data: Dict[str, Any]
    summary: str
