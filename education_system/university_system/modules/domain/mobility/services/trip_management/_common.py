from education_system.university_system.infrastructure.database.db import sqlite3, DatabaseManager
from education_system.university_system.modules.shared.constants.paths import DEFAULT_DB_PATH, REPORTS_DIR
from education_system.university_system.modules.shared.utils.i18n import get_text
import logging
import time
import os
from datetime import datetime, timedelta
# Import logging helpers from the refactored utils module
from education_system.university_system.modules.shared.utils.simple_activity_logger import (
    log_create,
    log_read,
    log_update,
    log_delete,
    log_menu_navigation,
)
import re
import traceback
try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    logging.warning(get_text("mobility.trip_management.warnings.reportlab_unavailable", "ReportLab not available. PDF generation will be disabled."))

# Academic calendar is optional - may not be available if dependencies missing
try:
    from education_system.university_system.modules.domain.academics.services.academic_calendar.calendar_core import AcademicCalendarManager
    from education_system.university_system.modules.domain.academics.services.academic_calendar.config import CalendarConfig
    CALENDAR_AVAILABLE = True
except ImportError as e:
    CALENDAR_AVAILABLE = False
    # Use debug level since this is expected when optional dependencies (numpy) are missing
    logging.debug(f"Academic calendar module not available (optional): {e}")

# Import auth instance management from user_authentication
try:
    from education_system.university_system.infrastructure.auth import get_current_user, set_auth_instance
    HAS_AUTH = True
except ImportError:
    HAS_AUTH = False
    get_current_user = lambda: None
    set_auth_instance = lambda x: None

auth = None

def set_auth(auth_instance):
    global auth
    auth = auth_instance
    # Also set it in the global auth instance if available
    if HAS_AUTH:
        set_auth_instance(auth_instance)
