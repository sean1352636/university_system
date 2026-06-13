from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH  # injected
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
from tkinter.simpledialog import Dialog
from education_system.university_system.infrastructure.database.db import sqlite3
import logging
import time
import os
from datetime import datetime, timedelta
import re
import traceback
from threading import Thread
import queue
from typing import Optional

# Import i18n for language support
from education_system.university_system.core.i18n import (
    init_i18n,
    get_text as _t,
    get_current_language,
)
from education_system.university_system.modules.shared.utils.gui_language_selector import (
    show_gui_language_selector,
    create_language_menu_button,
)

# Import all original functions and classes
try:
    from education_system.university_system.infrastructure.database.db import sqlite3, DatabaseManager
    from education_system.university_system.modules.shared.utils.simple_activity_logger import (
        log_create, log_read, log_update, log_delete, log_menu_navigation,
    )
    from education_system.university_system.infrastructure.auth import UserAuth
except ImportError as e:
    logging.error(f"Required module import failed: {e}")
    raise

# Academic calendar is optional - may not be available if dependencies missing
try:
    from education_system.university_system.modules.domain.academics.services.academic_calendar.calendar_core import AcademicCalendarManager
    from education_system.university_system.modules.domain.academics.services.academic_calendar.config import CalendarConfig
    CALENDAR_AVAILABLE = True
except ImportError as e:
    CALENDAR_AVAILABLE = False
    # Use debug level since this is expected when optional dependencies are missing
    logging.debug(f"Academic calendar module not available (optional): {e}")

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
    logging.warning("ReportLab not available. PDF generation will be disabled.")

try:
    from education_system.university_system.modules.domain.campus.mobility.services.trip_management import (
        TripReportGenerator,
        safe_db_operation as domain_safe_db_operation,
    )
    TRIP_REPORTS_AVAILABLE = True
except Exception as exc:  # pragma: no cover - optional dependency
    TripReportGenerator = None  # type: ignore
    domain_safe_db_operation = None  # type: ignore
    TRIP_REPORTS_AVAILABLE = False
    logging.warning("Trip report generator module not available: %s", exc)

try:
    from education_system.university_system.infrastructure.email.email_service import send_email
    EMAIL_SERVICE_AVAILABLE = True
except Exception as exc:
    send_email = None  # type: ignore
    EMAIL_SERVICE_AVAILABLE = False
    logging.warning("Email service not available: %s", exc)

# Import email template utilities
try:
    from education_system.university_system.infrastructure.email.template_utils import render_template
    TEMPLATE_AVAILABLE = True
except ImportError:
    TEMPLATE_AVAILABLE = False

# Configure logger for this module
logger = logging.getLogger(__name__)

# Provide a module-level safe_db_operation helper so dialogs can reuse CLI logic.
def safe_db_operation(operation_func, *args, **kwargs):
    """
    Execute a database operation safely.

    Prefer the domain implementation when available; otherwise fall back to a
    lightweight local implementation.
    """
    if domain_safe_db_operation:
        return domain_safe_db_operation(operation_func, *args, **kwargs)

    conn: Optional[sqlite3.Connection] = None
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        conn.row_factory = sqlite3.Row
        result = operation_func(conn, *args, **kwargs)
        conn.commit()
        return result
    except Exception as exc:  # pragma: no cover - best effort fallback
        logging.error("Database operation failed: %s", exc)
        if conn:
            try:
                conn.rollback()
            except Exception as e:
                logger.debug(f"Failed to rollback transaction: {e}")
        return False
    finally:
        if conn:
            try:
                conn.close()
            except Exception as e:
                logger.debug(f"Failed to close database connection: {e}")
