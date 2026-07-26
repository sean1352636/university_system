"""Data models: enums and dataclasses used across the chatbot package."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List


class UserRole(Enum):
    STUDENT = "student"
    FACULTY = "faculty"
    STAFF = "staff"
    ADMIN = "admin"
    GUEST = "guest"


class QueryType(Enum):
    ACADEMIC = "academic"
    FINANCIAL = "financial"
    TECHNICAL = "technical"
    ADMINISTRATIVE = "administrative"
    GENERAL = "general"


class NotificationChannel(Enum):
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    IN_APP = "in_app"


@dataclass
class AuthenticatedSession:
    user_id: str
    username: str
    role: str
    permissions: List[str]
    auth_token: str
    login_time: datetime
    last_activity: datetime


@dataclass
class UserSession:
    user_id: str
    session_token: str
    login_time: datetime
    last_activity: datetime
    role: UserRole
    is_active: bool = True


@dataclass
class ConversationContext:
    conversation_id: str
    user_id: str
    messages: List[Dict]
    intent_history: List[str]
    entities: Dict[str, Any]
    session_data: Dict[str, Any]


@dataclass
class StudentProfile:
    student_id: str
    name: str
    email: str
    program: str
    year: int
    gpa: float
    completed_courses: List[str]
    current_courses: List[str]
    interests: List[str]
    financial_aid: bool
