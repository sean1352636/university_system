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
# Only the flag is needed here (menu.py shows the calendar options when it is
# set); importing calendar_core at load pulled in seaborn/scipy/matplotlib and
# made every import of this package take ~12s. Calendar sync itself goes
# through trip_bus.
# (find_spec on the submodule would import the academic_calendar package,
# whose __init__ loads the charts — so look for the file instead.)
import importlib.util as _importlib_util
try:
    _calendar_pkg = _importlib_util.find_spec(
        "education_system.systems.university.domains.teaching.domain.academic_calendar")
    CALENDAR_AVAILABLE = bool(_calendar_pkg and any(
        os.path.exists(os.path.join(p, "calendar_core.py"))
        for p in (_calendar_pkg.submodule_search_locations or ())))
except ImportError as e:
    CALENDAR_AVAILABLE = False
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


def get_auth():
    """The auth instance set by :func:`set_auth` (``None`` when nobody is signed in).

    There is deliberately no test fallback: an unauthenticated caller gets
    ``None`` and is refused. Tests set a fake auth with :func:`set_auth`.
    """
    return auth


def set_auth(auth_instance):
    global auth
    auth = auth_instance
    # Also set it in the global auth instance if available
    if HAS_AUTH:
        set_auth_instance(auth_instance)
