"""
Sentiment analysis and AI suggestions.
"""

import sqlite3
import datetime
import json
import logging
import time
import re
import os
import hashlib
import mimetypes
import base64
import secrets
import traceback
from typing import Optional, List, Dict, Any
from functools import wraps

from university_system.infrastructure.database.db import get_connection, sqlite3, DatabaseManager
from university_system.infrastructure.email.email_manager import send_email
from university_system.modules.shared.constants.paths import DEFAULT_DB_PATH, TICKET_TEMPLATES_DIR, UPLOAD_DIR
from university_system.utils.logging.log_config import get_log_file

from ..config import (
    SUPPORT_DB, TICKET_STATUSES, TICKET_PRIORITIES, SUPPORT_CATEGORIES,
    NotificationType, TicketSentiment, FileType, SupportConfig
)
from .. import auth as _auth_mod
from ..auth import get_current_user_safe, require_auth, has_staff_permissions



logger = logging.getLogger(__name__)


def _analyze_sentiment(text):
    """Simple sentiment analysis based on keywords"""
    frustrated_keywords = [
        'frustrated', 'angry', 'terrible', 'awful', 'horrible', 'hate',
        'worst', 'furious', 'disgusted', 'outraged', 'urgent', 'immediately',
        'ridiculous', 'unacceptable', 'disappointed'
    ]
    
    positive_keywords = [
        'thank', 'appreciate', 'great', 'excellent', 'wonderful', 'amazing',
        'perfect', 'love', 'fantastic', 'awesome', 'pleased'
    ]
    
    text_lower = text.lower()
    
    frustrated_count = sum(1 for keyword in frustrated_keywords if keyword in text_lower)
    positive_count = sum(1 for keyword in positive_keywords if keyword in text_lower)
    
    if frustrated_count > 2:
        return TicketSentiment.FRUSTRATED.value
    elif frustrated_count > 0:
        return TicketSentiment.NEGATIVE.value
    elif positive_count > 0:
        return TicketSentiment.POSITIVE.value
    else:
        return TicketSentiment.NEUTRAL.value


def _suggest_category(text):
    """AI-powered category suggestion based on text content"""
    category_keywords = {
        'Technical': ['password', 'login', 'computer', 'wifi', 'internet', 'email', 'software', 'system', 'app', 'website'],
        'Academic': ['grade', 'course', 'assignment', 'professor', 'class', 'exam', 'transcript', 'graduation', 'credit'],
        'Financial Aid': ['scholarship', 'loan', 'tuition', 'payment', 'financial', 'aid', 'grant', 'billing'],
        'Housing': ['dorm', 'room', 'roommate', 'housing', 'residence', 'maintenance', 'key', 'AC', 'heating'],
        'Library Services': ['library', 'book', 'research', 'database', 'citation', 'librarian'],
        'Mental Health': ['counseling', 'stress', 'anxiety', 'depression', 'wellness', 'therapy'],
        'Registration': ['register', 'enrollment', 'schedule', 'waitlist', 'drop', 'add', 'prerequisite'],
        'Dining': ['meal', 'food', 'dining', 'cafeteria', 'allergy', 'dietary'],
        'Parking': ['parking', 'permit', 'ticket', 'car', 'vehicle', 'tow'],
        'Career Services': ['job', 'career', 'internship', 'resume', 'interview', 'employment']
    }
    
    text_lower = text.lower()
    category_scores = {}
    
    for category, keywords in category_keywords.items():
        score = sum(1 for keyword in keywords if keyword in text_lower)
        if score > 0:
            category_scores[category] = score
    
    if category_scores:
        return max(category_scores, key=category_scores.get)
    
    return None


def _get_auto_assignment(category, priority, staff_assignments=None):
    """Get staff member for auto-assignment"""
    # Load staff assignments if not provided
    if staff_assignments is None:
        from .background_tasks import _load_staff_assignments
        staff_assignments = _load_staff_assignments()

    if category not in staff_assignments:
        return None

    # Simple round-robin assignment (in a real system, you'd consider workload)
    staff_list = staff_assignments[category]
    if not staff_list:
        return None

    # Prefer primary staff for high priority tickets
    if priority in ['High', 'Critical', 'Urgent']:
        primary_staff = [s for s in staff_list if s['is_primary']]
        if primary_staff:
            return primary_staff[0]['staff_id']

    return staff_list[0]['staff_id']


def _estimate_resolution_time(category, priority):
    """Estimate resolution time based on category and priority"""
    base_times = {
        'Technical': 4,  # hours
        'Academic': 24,
        'Financial Aid': 48,
        'Housing': 12,
        'Library Services': 2,
        'Mental Health': 1,
        'Registration': 8,
        'Other': 24
    }
    
    priority_multipliers = {
        'Critical': 0.25,
        'Urgent': 0.5,
        'High': 0.75,
        'Medium': 1.0,
        'Low': 2.0
    }
    
    base_hours = base_times.get(category, 24)
    multiplier = priority_multipliers.get(priority, 1.0)
    estimated_hours = base_hours * multiplier
    
    resolution_time = datetime.datetime.now() + datetime.timedelta(hours=estimated_hours)
    return resolution_time.strftime('%Y-%m-%d %H:%M:%S')
