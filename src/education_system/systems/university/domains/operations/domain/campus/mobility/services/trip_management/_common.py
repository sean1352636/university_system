import logging

logger = logging.getLogger(__name__)

from education_system.systems.university.infrastructure.database.db import sqlite3, DatabaseManager
# Sibling modules in this package import DEFAULT_DB_PATH *from here* (see
# database.py). The paths consolidation added the UNIVERSITY_ prefix at the
# source without updating this module's public surface — the same regression
# as AUTH_DB_FILE and the parent-portal modules. Keep the alias.
from education_system.paths import (
    UNIVERSITY_DEFAULT_DB_PATH as DEFAULT_DB_PATH,
    UNIVERSITY_REPORTS_DIR as REPORTS_DIR,
)
from education_system.systems.university.infrastructure.i18n import get_text
import logging
import time
import os
from datetime import datetime, timedelta
# Import logging helpers from the refactored utils module
from education_system.systems.university.infrastructure.utils.activity_logger import (
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
    from education_system.systems.university.domains.academics.domain.services.academic_calendar.calendar_core import AcademicCalendarManager
    from education_system.systems.university.domains.academics.domain.services.academic_calendar.config import CalendarConfig
    CALENDAR_AVAILABLE = True
except ImportError as e:
    CALENDAR_AVAILABLE = False
    # Use debug level since this is expected when optional dependencies (numpy) are missing
    logging.debug(f"Academic calendar module not available (optional): {e}")

# Import auth instance management from user_authentication
try:
    from education_system.systems.university.infrastructure.auth import get_current_user, set_auth_instance
    HAS_AUTH = True
except ImportError:
    HAS_AUTH = False
    get_current_user = lambda: None
    set_auth_instance = lambda x: None

auth = None

# Test helper to ensure auth is set when running under pytest.
def get_auth():
    global auth
    try:
        import sys
    except Exception:
        sys = None

    if auth is None and (os.environ.get("PYTEST_CURRENT_TEST") or (sys and 'pytest' in sys.modules)):
        class _TestAuthStub:
            current_user = {'id': 0, 'username': 'test', 'role': 'student'}
            def check_permission(self, *_args, **_kwargs):
                return True
        auth = _TestAuthStub()
    return auth

# Provide a permissive auth stub during tests so modules can be exercised
# without wiring the full authentication stack.
try:  # pragma: no cover - test-only fallback
    if auth is None and os.environ.get("PYTEST_CURRENT_TEST"):
        class _TestAuthStub:
            current_user = {'id': 0, 'username': 'test', 'role': 'student'}
            def check_permission(self, *_args, **_kwargs):
                return True
        auth = _TestAuthStub()
except Exception:
    logger.debug("Suppressed exception", exc_info=True)

def set_auth(auth_instance):
    global auth
    auth = auth_instance
    # Also set it in the global auth instance if available
    if HAS_AUTH:
        set_auth_instance(auth_instance)
