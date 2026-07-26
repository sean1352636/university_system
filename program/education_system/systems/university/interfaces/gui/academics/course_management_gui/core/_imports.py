# Shared imports for course_management_gui.core subpackage
#
# Each mixin module imports the specific names it needs from this
# module (e.g. ``from ._imports import tk, ttk, messagebox``).
# This keeps dependencies explicit and avoids wildcard imports.

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog, Toplevel
from tkinter.scrolledtext import ScrolledText
from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.infrastructure.i18n import get_text as _, init_i18n
init_i18n()
import os
from pathlib import Path
from education_system.systems.university.infrastructure.auth import UserAuth
from education_system.systems.university.infrastructure.shared_context import get_auth
from education_system.systems.university.infrastructure import paths

# Use centralized path configuration
DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH
_CENTRALDEFAULT_DB_PATH = paths.DEFAULT_DB_PATH

# --------------------------------------------------------------------
# Override sqlite3.connect for this GUI. Many database calls within this
# module reference 'courses.db' or str(DEFAULT_DB_PATH) directly. Without
# overriding, these calls would create separate database files in the
# working directory, leading to inconsistencies and missing tables. By
# redirecting those names to the central student_records.db located in
# university_system/data/db_files, we ensure a single database file is
# used across the entire application. Only connections specifying no
# database or targeting courses.db/student_records.db are redirected;
# all other database paths are left untouched.

_original_sqlite_connect = sqlite3.connect

def _patched_sqlite_connect(database, *args, **kwargs):
    try:
        db_name = os.path.basename(str(database)) if database else ""
        if not database or db_name in (str(DEFAULT_DB_PATH), "courses.db"):
            return _original_sqlite_connect(str(_CENTRALDEFAULT_DB_PATH), *args, **kwargs)
    except (TypeError, ValueError) as e:
        logger.warning("Failed to redirect sqlite3.connect for %s: %s", database, e)
    return _original_sqlite_connect(database, *args, **kwargs)

sqlite3.connect = _patched_sqlite_connect
import re
import csv
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import threading
import shutil
import subprocess
import sys
import logging

logger = logging.getLogger(__name__)

# Import chart generation utility
try:
    import matplotlib
    matplotlib.use('TkAgg')
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    import seaborn as sns
    import numpy as np
    CHARTS_AVAILABLE = True
except ImportError:
    CHARTS_AVAILABLE = False
    plt = None
    Figure = None
    FigureCanvasTkAgg = None
    sns = None
    np = None

# Import email service
try:
    from education_system.systems.university.infrastructure.email.email_service import send_email
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False
    send_email = None

# Import module scheduling constants for timetable integration
try:
    from education_system.systems.university.domain.academics.services.module_scheduling import (
        DAYS_OF_WEEK, TIME_SLOTS, SESSION_TYPES
    )
except ImportError:
    DAYS_OF_WEEK = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    TIME_SLOTS = ['09:00', '10:00', '11:00', '12:00', '13:00', '14:00', '15:00', '16:00', '17:00']
    SESSION_TYPES = ['Lecture', 'Lab', 'Tutorial', 'Seminar', 'Workshop']

# Import the original course management functions
try:
    from education_system.systems.university.domain.academics.services.course_management import (
        add_prerequisite, create_course, create_enhanced_course,
        display_enhanced_course_menu, find_alternative_courses,
        generate_course_analytics, generate_enrollment_report,
        initialize_enhanced_database, remove_prerequisite, search_courses,
        update_course, update_schedule, view_all_courses, view_course_details
    )
    ORIGINAL_MODULE_AVAILABLE = True
except ImportError:
    ORIGINAL_MODULE_AVAILABLE = False
    print(_("course_management.warnings.original_module_not_found"))

# Import academic system launchers
try:
    from education_system.systems.university.domain.academics.services.degree_audit.degree_audit_core import launch_degree_audit_gui
    from education_system.systems.university.domain.academics.services.evaluation.course_evaluation_core import launch_course_evaluation_gui
    ACADEMIC_SYSTEMS_AVAILABLE = True
except ImportError as e:
    ACADEMIC_SYSTEMS_AVAILABLE = False
    print(_("course_management.warnings.academic_systems_unavailable", error=str(e)))

# Import dialog classes from submodules
from education_system.systems.university.interfaces.gui.academics.course_management_gui.courses.course_crud import (
    CourseCreateDialog, CourseEditDialog
)
from education_system.systems.university.interfaces.gui.academics.course_management_gui.courses.course_status import (
    ManageCourseStatusDialog, CourseHistoryDialog
)
from education_system.systems.university.interfaces.gui.academics.course_management_gui.schedules.schedules import (
    CreateScheduleDialog, ViewSchedulesDialog, UpdateScheduleDialog
)
from education_system.systems.university.interfaces.gui.academics.course_management_gui.schedules.conflict_report import (
    ScheduleConflictReportDialog
)
from education_system.systems.university.interfaces.gui.academics.course_management_gui.prerequisites.prerequisites import (
    PrerequisitesWindow, RemovePrerequisiteDialog
)
from education_system.systems.university.interfaces.gui.academics.course_management_gui.prerequisites.chain_viewer import (
    PrerequisiteChainDialog
)
from education_system.systems.university.interfaces.gui.academics.course_management_gui.search.search import (
    AdvancedCourseSearchDialog, AdvancedSearchDialog
)
from education_system.systems.university.interfaces.gui.academics.course_management_gui.waitlists import (
    AddToWaitlistDialog, ViewWaitlistsDialog, ProcessWaitlistDialog
)
from education_system.systems.university.interfaces.gui.academics.course_management_gui.recommendations import (
    RecommendCoursesDialog, AlternativeCourseDialog
)
from education_system.systems.university.interfaces.gui.academics.course_management_gui.analytics.analytics import (
    CourseAnalyticsDialog, EnrollmentReportDialog
)
from education_system.systems.university.interfaces.gui.academics.course_management_gui.bulk.bulk_operations import (
    BulkUpdateDialog
)
from education_system.systems.university.interfaces.gui.academics.course_management_gui.maintenance.maintenance import (
    MaintenanceDialog
)
from education_system.systems.university.interfaces.gui.academics.course_management_gui.maintenance.audit_log import (
    AuditLogViewerDialog
)
from education_system.systems.university.interfaces.gui.academics.course_management_gui.import_export.import_export import (
    ImportExportDialog
)
from education_system.systems.university.interfaces.gui.academics.course_management_gui.core.validation import (
    CourseValidationDialog
)
from education_system.systems.university.interfaces.gui.academics.course_management_gui.instructors.instructors import (
    InstructorCreateDialog, AssignInstructorDialog, InstructorDetailsDialog
)

# Sibling academic GUIs (course catalog / forums / health / AI integrity alerts).
# Each is optional — wrap so a missing or broken sibling does not break the
# whole Course Management GUI.
try:
    from education_system.systems.university.interfaces.gui.academics.course_catalog.course_catalog_gui import CourseCatalogGUI
    COURSE_CATALOG_AVAILABLE = True
except ImportError as e:
    CourseCatalogGUI = None
    COURSE_CATALOG_AVAILABLE = False
    logger.debug("Course Catalog GUI unavailable: %s", e)

try:
    from education_system.systems.university.interfaces.gui.academics.course_forums.course_forums_gui import CourseForumsGUI
    COURSE_FORUMS_AVAILABLE = True
except ImportError as e:
    CourseForumsGUI = None
    COURSE_FORUMS_AVAILABLE = False
    logger.debug("Course Forums GUI unavailable: %s", e)

try:
    from education_system.systems.university.interfaces.gui.academics.course_health.course_health_gui import CourseHealthDashboardGUI
    COURSE_HEALTH_AVAILABLE = True
except ImportError as e:
    CourseHealthDashboardGUI = None
    COURSE_HEALTH_AVAILABLE = False
    logger.debug("Course Health GUI unavailable: %s", e)

try:
    from education_system.systems.university.interfaces.gui.academics.ai_detector import AIDetectorGUI
    AI_DETECTOR_AVAILABLE = True
except ImportError as e:
    AIDetectorGUI = None
    AI_DETECTOR_AVAILABLE = False
    logger.debug("AI Detector GUI unavailable: %s", e)

from education_system.systems.university.interfaces.gui.academics.course_management_gui.academic_systems.templates_viewer import (
    EvaluationTemplatesViewerDialog
)
