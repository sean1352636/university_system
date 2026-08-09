import os
import csv
import json
import uuid
import shutil
import platform
import subprocess
import logging
import calendar as cal
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from education_system.systems.university.infrastructure.logging.log_config import configure_logging
from education_system import paths
from education_system.systems.university.infrastructure.database.db import get_connection

from education_system.systems.university.domains.academics.domain.services.academic_calendar.exceptions import (
    CalendarError, ValidationError, DatabaseError,
    PermissionError, ExportError
)
from education_system.systems.university.domains.academics.domain.services.academic_calendar.config import CalendarConfig, ValidationUtils
from education_system.systems.university.domains.academics.domain.services.academic_calendar.database import DatabaseManager
from education_system.systems.university.domains.academics.domain.services.academic_calendar.auth import AuthenticationManager
from education_system.systems.university.domains.academics.domain.services.academic_calendar.audit import AuditManager
from education_system.systems.university.domains.academics.domain.services.academic_calendar.recurring_events import RecurringEventManager
from education_system.systems.university.domains.academics.domain.services.academic_calendar.categories import EventCategoryManager, CourseManager
from education_system.systems.university.domains.academics.domain.services.academic_calendar.resources import ResourceManager
from education_system.systems.university.domains.academics.domain.services.academic_calendar.notifications import NotificationManager, SMSNotificationManager
from education_system.systems.university.domains.academics.domain.services.academic_calendar.search import AdvancedSearchManager
from education_system.systems.university.domains.academics.domain.services.academic_calendar.holidays import HolidayManager
from education_system.systems.university.domains.academics.domain.services.academic_calendar.visualization import DataVisualizationManager, EnhancedCalendarVisualizationManager
from education_system.systems.university.domains.academics.domain.services.academic_calendar.dependencies import EventDependencyManager
from education_system.systems.university.domains.academics.domain.services.academic_calendar.reporting import AdvancedReportingManager
from education_system.systems.university.domains.academics.domain.services.academic_calendar.deadlines import AcademicDeadlineManager
from education_system.systems.university.domains.academics.domain.services.academic_calendar.batch import BatchOperationsManager
from education_system.systems.university.domains.academics.domain.services.academic_calendar.timezone import EnhancedTimeZoneManager

logger = configure_logging(name=__name__)

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    requests = None

try:
    from ics import Calendar as ICSCalendar, Event as ICSEvent
    ICS_AVAILABLE = True
except Exception:
    ICS_AVAILABLE = False

try:
    import pytz
    PYTZ_AVAILABLE = True
except ImportError:
    PYTZ_AVAILABLE = False

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

try:
    from flask import Flask
    from flask_cors import CORS
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False

try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


# Main Academic Calendar Manager
