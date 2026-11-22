# Auto-generated import definitions
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import sys
import os
import threading
import logging
import random
import csv
from education_system.systems.university.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta

# Import authentication
try:
    from education_system.systems.university.infrastructure.auth import UserAuth
except ImportError:
    UserAuth = None

# Import auth instance management from user_authentication
try:
    from education_system.systems.university.infrastructure.auth import get_current_user, set_auth_instance
    HAS_AUTH = True
except ImportError:
    HAS_AUTH = False
    get_current_user = lambda: None
    set_auth_instance = lambda x: None

# Import MFA (Multi-Factor Authentication) services
try:
    from education_system.systems.university.infrastructure.auth.mfa_service import (
        MFAService,
        setup_totp,
        verify_totp,
        generate_sms_otp,
        verify_sms_otp
    )
    MFA_AVAILABLE = True
except ImportError:
    MFAService = None
    MFA_AVAILABLE = False

try:
    from education_system.systems.university.infrastructure.auth.email_otp_service import EmailOTPService
    EMAIL_OTP_AVAILABLE = True
except ImportError:
    EmailOTPService = None
    EMAIL_OTP_AVAILABLE = False

try:
    from education_system.systems.university.infrastructure.auth.sms_provider import SMSProvider
    SMS_PROVIDER_AVAILABLE = True
except ImportError:
    SMSProvider = None
    SMS_PROVIDER_AVAILABLE = False

# Import security modules
try:
    from education_system.systems.university.infrastructure.security.session_management import (
        SessionManager,
        SessionInfo,
        create_session,
        validate_session
    )
    SESSION_MANAGEMENT_AVAILABLE = True
except ImportError:
    SessionManager = None
    SESSION_MANAGEMENT_AVAILABLE = False

try:
    from education_system.systems.university.infrastructure.security.comprehensive_security import (
        APISecurityManager,
        PasswordSecurityManager,
        SecurityAuditManager,
        DataLossPreventionManager,
        IncidentResponseManager,
        VulnerabilityScanner
    )
    COMPREHENSIVE_SECURITY_AVAILABLE = True
except ImportError:
    APISecurityManager = None
    PasswordSecurityManager = None
    SecurityAuditManager = None
    COMPREHENSIVE_SECURITY_AVAILABLE = False

try:
    from education_system.systems.university.infrastructure.security.data_encryption import (
        EncryptionManager,
        encrypt_sensitive_data,
        decrypt_sensitive_data
    )
    DATA_ENCRYPTION_AVAILABLE = True
except ImportError:
    EncryptionManager = None
    DATA_ENCRYPTION_AVAILABLE = False

try:
    from education_system.systems.university.shell.gui.security.security_dashboard_gui import SecurityDashboard
    SECURITY_DASHBOARD_AVAILABLE = True
except ImportError:
    SecurityDashboard = None
    SECURITY_DASHBOARD_AVAILABLE = False

try:
    from education_system.systems.university.shell.gui.security.audit_log_viewer_gui import (
        AuditLogViewerGUI,
        show_audit_log_viewer
    )
    AUDIT_LOG_VIEWER_AVAILABLE = True
except ImportError:
    AuditLogViewerGUI = None
    show_audit_log_viewer = None
    AUDIT_LOG_VIEWER_AVAILABLE = False

# Import activity logger for audit trail
try:
    from education_system.systems.university.infrastructure.activity_logger import log_activity
    ACTIVITY_LOGGER_AVAILABLE = True
except ImportError:
    ACTIVITY_LOGGER_AVAILABLE = False
    log_activity = lambda *args, **kwargs: None

# Import internationalization (i18n) for multi-language support
try:
    from education_system.systems.university.infrastructure.i18n import (
        get_text as _t,
        get_current_language,
        get_current_language_name,
        set_language,
        get_available_language_list,
        init_i18n,
    )
    from education_system.systems.university.infrastructure.utils.gui_language_selector import (
        show_gui_language_selector,
    )
    I18N_AVAILABLE = True
    GUI_LANG_SELECTOR_AVAILABLE = True
    # Initialize i18n if not already done
    init_i18n()
except ImportError:
    I18N_AVAILABLE = False
    GUI_LANG_SELECTOR_AVAILABLE = False
    _t = lambda key, **kwargs: key  # Fallback: return key as-is
    get_current_language = lambda: "en"
    get_current_language_name = lambda: "English"
    set_language = lambda lang, save=True: False
    get_available_language_list = lambda: [("en", "English")]
    show_gui_language_selector = lambda parent=None: "en"

# Export _t for import * (underscore names are not exported by default)
translate_text = _t

# Import custom exceptions for lockout handling
try:
    from education_system.systems.university.infrastructure.exceptions import (
        InvalidCredentialsError,
        AuthenticationError,
        DatabaseError
    )
    EXCEPTIONS_AVAILABLE = True
except ImportError:
    InvalidCredentialsError = Exception
    AuthenticationError = Exception
    DatabaseError = Exception
    EXCEPTIONS_AVAILABLE = False

# Configure logging
logger = logging.getLogger(__name__)

auth = None

# Initialize shared_context auth early to prevent warnings during imports
try:
    from education_system.systems.university.infrastructure.shared_context import set_auth as set_shared_auth, get_auth
    # Try to get existing auth or set a placeholder
    try:
        existing_auth = get_auth()
        if existing_auth is not None:
            auth = existing_auth
    except Exception as e:
        logger.debug(f"No existing auth available: {e}")
except ImportError:
    set_shared_auth = lambda x: None
    get_auth = lambda: None


# Import database connection
from education_system.systems.university.infrastructure.database.db import get_db_connection, get_connection, transaction

# ── Lazy binding machinery ──────────────────────────────────────────────────
#
# Importing every feature GUI eagerly here cost ~19s and pulled in 6,400+
# modules (matplotlib, scipy, sklearn, pandas, nltk, reportlab, boto3 …) before
# the main window could be drawn after login.
#
# A module-level ``__getattr__`` (PEP 562) is not enough on its own: dozens of
# consumers do ``from gui_imports import SomeGUI`` at *their* module level, and
# that form triggers ``__getattr__`` immediately, resolving the import right
# back at startup. (That is exactly why the pre-existing ``_LAZY_GUI`` table
# below was not actually saving anything — features/student_affairs_gui.py
# imports BettingShopGUI and StaffHRGUI by name, so both were loaded eagerly.)
#
# So the names are bound to a *callable proxy* instead. ``from ... import X``
# keeps working and stays cheap; the real class is imported the first time the
# proxy is called or has an attribute read — i.e. when the feature is opened.
#
# This is safe because these names are only ever instantiated: nothing in the
# tree does ``isinstance(x, SomeGUI)`` or subclasses one of them (both checked).
class _LazyGUIClass:
    """Stand-in for a heavy GUI class, resolved on first use."""

    __slots__ = ("_module_path", "_attr", "_resolved")

    def __init__(self, module_path, attr):
        self._module_path = module_path
        self._attr = attr
        self._resolved = None

    def _resolve(self):
        if self._resolved is None:
            import importlib
            self._resolved = getattr(importlib.import_module(self._module_path), self._attr)
        return self._resolved

    def __call__(self, *args, **kwargs):
        return self._resolve()(*args, **kwargs)

    def __getattr__(self, name):
        # Reaches classmethods/staticmethods/class attributes on the real class.
        return getattr(self._resolve(), name)

    def __repr__(self):
        state = "resolved" if self._resolved is not None else "unresolved"
        return f"<lazy {self._attr} from {self._module_path} ({state})>"


def _lazy_class(module_path, attr=None):
    """Bind a GUI class name without importing its module yet."""
    return _LazyGUIClass(module_path, attr)


def _lazy_func(module_path, attr, bind_as=None):
    """Bind a module-level function without importing its module yet.

    ``bind_as`` is the name this module exposes it under, which is not always
    the name in the source module (e.g. ``init_cinema_database`` is
    ``init_database`` in the cinema package). The cache must use the exposed
    name or the stub is never actually replaced.
    """
    exposed = bind_as or attr

    def stub(*args, **kwargs):
        import importlib
        func = getattr(importlib.import_module(module_path), attr)
        globals()[exposed] = func  # cache: later calls skip the indirection
        return func(*args, **kwargs)
    stub.__name__ = exposed
    stub.__qualname__ = exposed
    return stub


# GUI components — imported lazily on first use to speed up startup.
# Use _lazy_import('ClassName') to get the class when actually needed.
_GUI_IMPORT_MAP = {
    "FinanceManagementGUI": ("education_system.systems.university.domains.finance.interfaces.gui.finance_management_gui", "FinanceManagementGUI"),
    "FinancialAidGUI": ("education_system.systems.university.domains.finance.interfaces.gui.financial_aid", "FinancialAidGUI"),
    "StudentUnionManagementGUI": ("education_system.systems.university.domains.student_life.interfaces.gui.student_union_management_gui", "StudentUnionManagementGUI"),
    "HealthPortalManagementGUI": ("education_system.systems.university.domains.health.interfaces.gui.health.health_portal_management_gui", "HealthPortalManagementGUI"),
    "GradeTrackingManagementGUI": ("education_system.systems.university.domains.assessment.interfaces.gui.grade_tracking_management_gui", "GradeTrackingManagementGUI"),
    "RestaurantManagementGUI": ("education_system.systems.university.plugins.campus_commerce.interfaces.gui.restaurant_management_gui", "RestaurantManagementGUI"),
    "CafeSystemGUI": ("education_system.systems.university.plugins.campus_commerce.interfaces.gui.cafe_system_gui", "CafeSystemGUI"),
    "TakeawayGUI": ("education_system.systems.university.plugins.campus_commerce.interfaces.gui.takeaway_gui", "TakeawayGUI"),
    "GroceryGUI": ("education_system.systems.university.plugins.campus_commerce.interfaces.gui.grocery_gui", "GroceryGUI"),
    "GroceryManagementGUI": ("education_system.systems.university.plugins.campus_commerce.interfaces.gui.grocery_gui", "GroceryManagementGUI"),
    "BarGUI": ("education_system.systems.university.plugins.campus_commerce.interfaces.gui.bar_gui", "BarGUI"),
    "EmailManagerManagementGUI": ("education_system.systems.university.shell.gui.email.email_manager_management_gui", "EmailManagerManagementGUI"),
}

def _lazy_import(name):
    """Import a GUI class on first use and cache it in the module globals."""
    g = globals()
    if g.get(name) is not None:
        return g[name]
    if name not in _GUI_IMPORT_MAP:
        raise ImportError(f"Unknown lazy GUI import: {name}")
    mod_path, attr = _GUI_IMPORT_MAP[name]
    try:
        import importlib
        mod = importlib.import_module(mod_path)
        cls = getattr(mod, attr)
        g[name] = cls
        if name == "BarGUI":
            g["BAR_GUI_AVAILABLE"] = True
        return cls
    except ImportError:
        if name == "BarGUI":
            g["BAR_GUI_AVAILABLE"] = False
        return None


# Bind every name in _GUI_IMPORT_MAP to a proxy. Previously these were set to
# None and only _lazy_import() could reach them, which meant a plain
# ``from gui_imports import FinanceManagementGUI`` silently got None.
for _name, (_mod, _attr) in _GUI_IMPORT_MAP.items():
    globals()[_name] = _lazy_class(_mod, _attr)
BAR_GUI_AVAILABLE = True

from education_system.systems.university.domains.curriculum.domain.modules import (compulsory_module_1, compulsory_module_2,
                                                               optional_module_1, optional_module_2,
                                                               optional_module_3, optional_module_4,
                                                               CS_optional_module_1, CS_optional_module_2,
                                                               CS_optional_module_3, CS_optional_module_4,
                                                               DS_optional_module_1, DS_optional_module_2,
                                                               DS_optional_module_3, DS_optional_module_4,
                                                               )

# ============================================================================
# PHASE 4 FEATURE IMPORTS - New Features (October 2025)
# ============================================================================

# Feature 1: Virtual Classroom Integration
# NOTE: this block also rebinds ``SessionManager``, shadowing the security
# SessionManager imported near the top of this module. That shadowing predates
# the lazy conversion and is preserved deliberately.
_VC = "education_system.systems.university.domains.teaching.domain.virtual_classroom"
VirtualClassroomManager = _lazy_class(_VC, "VirtualClassroomManager")
SessionManager = _lazy_class(_VC, "SessionManager")
ParticipantManager = _lazy_class(_VC, "ParticipantManager")
RecordingManager = _lazy_class(_VC, "RecordingManager")
VIRTUAL_CLASSROOM_AVAILABLE = True

# Feature 2: Integrated Financial Aid & Scholarship Management
_FA = "education_system.systems.university.domains.finance.domain.services.financial_aid"
FinancialAidManager = _lazy_class(_FA, "FinancialAidManager")
ScholarshipManager = _lazy_class(_FA, "ScholarshipManager")
FINANCIAL_AID_AVAILABLE = True

# Feature 3: Unified Communication Hub
CommunicationManager = _lazy_class(
    "education_system.systems.university.infrastructure.communication", "CommunicationManager")
COMMUNICATION_HUB_AVAILABLE = True

# Features 4-8: Database schemas are available in remaining_features_schema.py
# These features have database tables but no GUI interfaces yet:
# - Mobile App (PWA) Infrastructure
# - Transportation & Parking Management
# - Blockchain Credentials & Digital Badges
#
# Implemented GUIs:
# - Accessibility & Accommodation Tools (button in Medical Accommodation GUI)
# - Parent Portal Enhancement (merged into Parent Portal)
# - Facilities & Space Management
#
# GUI interfaces for these features can be added in future updates.

# ============================================================================

# Optional modules ---------------------------------------------------------
# Every entry below was previously an eager ``try: from … import X`` block.
# Together they were the bulk of the ~19s startup import: each one drags in its
# whole domain package, and between them they pulled matplotlib, scipy, sklearn,
# pandas, nltk, reportlab and boto3 into a login that never uses them.
#
# They are now bound to lazy proxies (see _LazyGUIClass above), so the module
# is imported the first time the feature is actually opened.
#
# The availability flags are optimistically True, matching the convention
# already used by _LAUNCHER_MAP and _LAZY_GUI further down: a genuinely broken
# dependency now surfaces when the user opens that feature, instead of silently
# hiding the menu entry at startup. The *_IMPORT_ERROR globals stay defined
# (as None) because features/student_affairs_gui.py imports them by name.
_OPTIONAL_GUI = {
    # name: (module path, attribute in that module)
    "AdvancedSearchGUI": ("education_system.systems.university.domains.learners.interfaces.gui.students.advanced_search", "AdvancedSearchGUI"),
    "ModuleSchedulingGUI": ("education_system.systems.university.domains.teaching.interfaces.gui.module_scheduling", "ModuleSchedulingGUI"),
    "CourseManagementGUI": ("education_system.systems.university.domains.curriculum.interfaces.gui.course_management_gui", "CourseManagementGUI"),
    "AssignmentGUI": ("education_system.systems.university.domains.assessment.interfaces.gui.assignment_system", "AssignmentGUI"),
    "DocumentManagerGUI": ("education_system.systems.university.shell.gui.document_manager.main_gui", "DocumentManagerGUI"),
    "ReportingSystemGUI": ("education_system.systems.university.shell.gui.analytics.enhanced_reporting", "ReportingSystemGUI"),
    "PDFExportGUI": ("education_system.systems.university.shell.gui.pdf_export_gui", "PDFExportGUI"),
    "HousingAccommodationGUI": ("education_system.systems.university.domains.operations.interfaces.gui.campus.housing.housing_accommodation_gui.main_gui", "HousingGUI"),
    "LibraryGUI": ("education_system.systems.university.domains.library.interfaces.gui.library", "LibraryGUI"),
    "ParentPortalGUI": ("education_system.systems.university.domains.learners.interfaces.gui.parent_portal", "ParentPortalGUI"),
    "GUIStudentAnalytics": ("education_system.systems.university.shell.gui.analytics.student_analytics", "GUIStudentAnalytics"),
    "StudentGradesPortal": ("education_system.systems.university.domains.assessment.interfaces.gui.student_grades", "StudentGradesPortal"),
    "StudentOutcomesGUI": ("education_system.systems.university.domains.curriculum.interfaces.gui.student_outcomes_gui", "StudentOutcomesGUI"),
    "StudentTimetableGUI": ("education_system.systems.university.domains.teaching.interfaces.gui.student_timetable_gui", "StudentTimetableGUI"),
    "StudentRegistrationPortal": ("education_system.systems.university.domains.curriculum.interfaces.gui.student_registration", "StudentRegistrationPortal"),
    "StudentSupportGUI": ("education_system.systems.university.domains.student_support.interfaces.gui.student_support", "StudentSupportGUI"),
    "TripManagementGUI": ("education_system.systems.university.domains.operations.interfaces.gui.campus.mobility.trip_management_gui", "TripManagementGUI"),
    "AlumniGUIApp": ("education_system.systems.university.domains.learners.interfaces.gui.alumni", "AlumniGUIApp"),
    "GradeTrackingApp": ("education_system.systems.university.domains.assessment.interfaces.gui.grade_tracking", "GradeTrackingApp"),
    "BackupGUI": ("education_system.systems.university.shell.gui.database.backup_gui", "BackupGUI"),
    "CalendarGUI": ("education_system.systems.university.domains.teaching.interfaces.gui.academic_calendar", "CalendarGUI"),
    "AccommodationGUI": ("education_system.systems.university.domains.health.interfaces.gui.health.medical_accommodation", "AccommodationGUI"),
    "AIDetectorGUI": ("education_system.systems.university.domains.integrity.interfaces.gui.ai_detector", "AIDetectorGUI"),
    "BatchOperationsGUI": ("education_system.systems.university.shell.gui.batch_operations", "BatchOperationsGUI"),
    "EmailManagerGUI": ("education_system.systems.university.shell.gui.email.email_gui", "EmailManagerGUI"),
    "FinancialManagementGUI": ("education_system.systems.university.domains.finance.interfaces.gui.finance_reporting", "FinancialManagementGUI"),
    "ParkingManagementGUI": ("education_system.systems.university.domains.operations.interfaces.gui.campus.mobility.parking_management_gui", "ParkingManagementGUI"),
    "RestaurantManagementGUI": ("education_system.systems.university.plugins.campus_commerce.interfaces.gui.restaurant_management_gui", "RestaurantManagementGUI"),
    "ShopManagementGUI": ("education_system.systems.university.plugins.campus_commerce.interfaces.gui.shop_management_gui.main_gui", "UniversityShopGUI"),
    "CharityShopApp": ("education_system.systems.university.plugins.campus_commerce.interfaces.gui.charity_shop_gui", "CharityShopApp"),
    "ActivityLoggerGUI": ("education_system.systems.university.shell.gui.activity_logger", "EnhancedActivityLoggerGUI"),
    "UniversityChatbotGUI": ("education_system.systems.university.shell.gui.ai.chatbot_gui", "ChatbotGUI"),
    "LogManagementGUI": ("education_system.systems.university.shell.gui.logging.log_management_gui", "LogManagementGUI"),
    "InternshipManagementGUI": ("education_system.systems.university.domains.student_life.interfaces.gui.internship_management", "InternshipGUI"),
    "AttendanceGUI": ("education_system.systems.university.domains.teaching.interfaces.gui.attendance_tracker", "AttendanceGUI"),
    "HelpdeskGUI": ("education_system.systems.university.domains.student_support.interfaces.gui.helpdesk", "HelpdeskGUI"),
}

for _name, (_mod, _attr) in _OPTIONAL_GUI.items():
    globals()[_name] = _lazy_class(_mod, _attr)

# Module-level functions that came from the same blocks.
launch_module_scheduling_gui = _lazy_func(
    "education_system.systems.university.domains.teaching.interfaces.gui.module_scheduling",
    "launch_module_scheduling_gui")
start_document_manager_gui = _lazy_func(
    "education_system.systems.university.shell.gui.document_manager.console",
    "start_document_manager_gui")
display_document_management_menu = _lazy_func(
    "education_system.systems.university.shell.gui.document_manager.console",
    "display_document_management_menu")
start_enhanced_reporting_gui = _lazy_func(
    "education_system.systems.university.shell.gui.analytics.enhanced_reporting",
    "start_enhanced_reporting_gui")
show_pdf_export_gui = _lazy_func(
    "education_system.systems.university.shell.gui.pdf_export_gui", "show_pdf_export_gui")
display_helpdesk_menu = _lazy_func(
    "education_system.systems.university.domains.student_support.domain.helpdesk",
    "display_helpdesk_menu")

# Alias kept for callers that reference the class through this name.
# Spelled via globals() because AlumniGUIApp itself is bound by the loop above,
# which static analysis cannot see.
ALUMNI_GUI_APP_CLASS = globals()["AlumniGUIApp"]

for _flag in (
    "ADVANCED_SEARCH_GUI_AVAILABLE", "MODULE_SCHEDULING_GUI_AVAILABLE",
    "COURSE_MANAGEMENT_GUI_AVAILABLE", "ASSIGNMENT_SUBMISSION_GUI_AVAILABLE",
    "DOCUMENT_MANAGER_GUI_AVAILABLE", "ENHANCED_REPORTING_GUI_AVAILABLE",
    "PDF_EXPORT_GUI_AVAILABLE", "HOUSING_ACCOMMODATION_GUI_AVAILABLE",
    "LIBRARY_GUI_AVAILABLE", "PARENT_PORTAL_GUI_AVAILABLE",
    "STUDENT_ANALYTICS_GUI_AVAILABLE", "STUDENT_GRADES_GUI_AVAILABLE",
    "STUDENT_OUTCOMES_GUI_AVAILABLE", "STUDENT_TIMETABLE_GUI_AVAILABLE",
    "STUDENT_REGISTRATION_GUI_AVAILABLE",
    "STUDENT_SUPPORT_GUI_AVAILABLE", "TRIP_MANAGEMENT_GUI_AVAILABLE",
    "ALUMNI_PORTAL_GUI_AVAILABLE", "GRADE_TRACKING_GUI_AVAILABLE",
    "DATA_BACKUP_GUI_AVAILABLE", "ACADEMIC_CALENDAR_GUI_AVAILABLE",
    "ACCOMMODATION_GUI_AVAILABLE", "AI_DETECTOR_GUI_AVAILABLE",
    "BATCH_OPS_GUI_AVAILABLE", "EMAIL_MANAGER_GUI_AVAILABLE",
    "FINANCE_REPORTING_GUI_AVAILABLE", "PARKING_MANAGEMENT_GUI_AVAILABLE",
    "PLAGIARISM_GUI_AVAILABLE", "RESTAURANT_MANAGEMENT_GUI_AVAILABLE",
    "SHOP_GUI_AVAILABLE", "CHARITY_SHOP_GUI_AVAILABLE",
    "ACTIVITY_LOGGER_GUI_AVAILABLE", "CHATBOT_GUI_AVAILABLE",
    "LOG_MANAGEMENT_GUI_AVAILABLE", "INTERNSHIP_MANAGEMENT_GUI_AVAILABLE",
    "ATTENDANCE_GUI_AVAILABLE", "HELPDESK_GUI_AVAILABLE", "HELPDESK_CLI_AVAILABLE",
):
    globals()[_flag] = True

# Import-error strings are no longer produced at startup (nothing is imported
# at startup to fail), but consumers import these names, so keep them defined.
ADVANCED_SEARCH_GUI_IMPORT_ERROR = None
MODULE_SCHEDULING_GUI_IMPORT_ERROR = None
PARENT_PORTAL_GUI_IMPORT_ERROR = None
_STUDENT_SUPPORT_GUI_IMPORT_ERROR = None
_TRIP_MGMT_IMPORT_ERROR = None
ALUMNI_PORTAL_IMPORT_ERROR = None

# Set remaining GUI availability variables to False (no corresponding GUI files found)
ANALYTICS_GUI_AVAILABLE = False  # This uses student_analytics_gui which is imported separately
CALENDAR_GUI_AVAILABLE = False  # This would be a separate calendar system
HELP_DESK_GUI_AVAILABLE = False  # Would use helpdesk_gui.py

# Advanced feature GUI launchers — lazy-loaded on first call to avoid heavy
# imports (pandas, matplotlib, reportlab, etc.) at startup.
_LAUNCHER_MAP = {
    "launch_advanced_attendance_gui": "education_system.systems.university.domains.teaching.domain.attendance.attendance_tracker",
    "launch_career_services_gui": "education_system.systems.university.domains.student_life.domain.career_services.career_services_core",
    "launch_extras_gui": "education_system.platform.features.extras.launcher",
    "launch_admissions_crm_gui": "education_system.systems.university.domains.admissions.domain.services.admissions_crm_core",
    "launch_predictive_analytics_gui": "education_system.systems.university.shell.gui.analytics.predictive_analytics_gui",
    "launch_timetable_optimizer_gui": "education_system.systems.university.domains.teaching.domain.module_scheduling",
    "launch_campus_events_gui": "education_system.systems.university.domains.operations.domain.campus.services.campus_events_gui",
    "launch_alumni_relations_gui": "education_system.systems.university.domains.learners.interfaces.gui.alumni",
    "launch_facilities_management_gui": "education_system.systems.university.domains.operations.domain.campus.facilities.services.facilities_management_core",
    "launch_business_intelligence_gui": "education_system.systems.university.shell.gui.analytics.business_intelligence_gui",
    "launch_ai_features_gui": "education_system.systems.university.shell.gui.ai.ai_features_gui",
    "launch_mobile_app_pwa_gui": "education_system.systems.university.domains.operations.interfaces.gui.campus.mobility.mobile_app_pwa_gui",
    "launch_blockchain_credentials_gui": "education_system.systems.university.domains.progression.interfaces.gui.blockchain_credentials_gui",
    "launch_integration_marketplace_gui": "education_system.systems.university.shell.gui.services.integration_marketplace_gui",
}

# Extras launcher has a different attr name in its module
_LAUNCHER_ATTR_OVERRIDE = {
    "launch_extras_gui": "launch_as_toplevel",
}

EXTRAS_LAUNCHER_AVAILABLE = True  # assume available, will be set False on import failure

def _lazy_launcher(name):
    """Import a launch_*_gui function on first use."""
    if name not in _LAUNCHER_MAP:
        raise ImportError(f"Unknown launcher: {name}")
    import importlib
    mod = importlib.import_module(_LAUNCHER_MAP[name])
    attr = _LAUNCHER_ATTR_OVERRIDE.get(name, name)
    func = getattr(mod, attr)
    globals()[name] = func
    return func

# Create module-level callable stubs that auto-import on first call.
# Other modules import these names; calling them triggers the real import.
def _make_lazy_stub(name):
    def stub(*args, **kwargs):
        func = _lazy_launcher(name)
        return func(*args, **kwargs)
    stub.__name__ = name
    stub.__qualname__ = name
    return stub

for _ln in list(_LAUNCHER_MAP):
    globals()[_ln] = _make_lazy_stub(_ln)

# ── Advanced / commerce / operations GUIs — lazily loaded (PEP 562) ──────────
# These GUI classes pull heavy dependencies (matplotlib, scipy, sklearn,
# pandas, reportlab, …) and dozens of domain modules. Importing them eagerly
# here added ~20s to startup (cinema and degree-audit alone were ~10s each).
# They are now resolved on first attribute access via the module __getattr__
# below, so a caller's ``from gui_imports import GymGUI`` only pays the cost
# when that feature is actually opened.
#
# Availability flags are optimistically True (same convention as _LAUNCHER_MAP
# above): a genuinely missing dependency now surfaces when the feature is
# launched rather than hiding the menu entry at startup.
# Each target is spelled out in full rather than assembled from a shared prefix.
# It was a shared prefix until the vertical-slice migration, and that is exactly why
# it broke: the complete dotted path never appeared in the source, so the sweep that
# repointed every other reference could not see these. _LAUNCHER_MAP above uses full
# literals and came through the same eleven moves untouched.
_LAZY_GUI = {
    "LegalServicesGUI": ("education_system.systems.university.domains.governance.interfaces.gui.legal.legal_services_gui", "LegalServicesGUI"),
    "launch_legal_services_gui": ("education_system.systems.university.domains.governance.interfaces.gui.legal.legal_services_gui", "launch_legal_services_gui"),
    "BettingShopGUI": ("education_system.systems.university.plugins.campus_commerce.interfaces.gui.betting.betting_shop_gui", "BettingShopGUI"),
    "launch_betting_shop_gui": ("education_system.systems.university.plugins.campus_commerce.interfaces.gui.betting.betting_shop_gui", "launch_betting_shop_gui"),
    "MailPostGUI": ("education_system.systems.university.domains.operations.interfaces.gui.communications.mail.mail_post_gui", "MailPostGUI"),
    "launch_mail_post_gui": ("education_system.systems.university.domains.operations.interfaces.gui.communications.mail.mail_post_gui", "launch_mail_post_gui"),
    "GymGUI": ("education_system.systems.university.plugins.campus_commerce.interfaces.gui.gym.gym_gui", "GymGUI"),
    "launch_gym_gui": ("education_system.systems.university.plugins.campus_commerce.interfaces.gui.gym.gym_gui", "launch_gym_gui"),
    "DentistGUI": ("education_system.systems.university.domains.health.interfaces.gui.health.health_portal.dentist_gui", "DentistGUI"),
    "launch_dentist_gui": ("education_system.systems.university.domains.health.interfaces.gui.health.health_portal.dentist_gui", "launch_dentist_gui"),
    "ButcherGUI": ("education_system.systems.university.plugins.campus_commerce.interfaces.gui.butcher.butcher_gui", "ButcherGUI"),
    "launch_butcher_gui": ("education_system.systems.university.plugins.campus_commerce.interfaces.gui.butcher.butcher_gui", "launch_butcher_gui"),
    "BarberGUI": ("education_system.systems.university.plugins.campus_commerce.interfaces.gui.barber.barber_gui", "BarberGUI"),
    "launch_barber_gui": ("education_system.systems.university.plugins.campus_commerce.interfaces.gui.barber.barber_gui", "launch_barber_gui"),
    "NailBarGUI": ("education_system.systems.university.plugins.campus_commerce.interfaces.gui.nailbar.nailbar_gui", "NailBarGUI"),
    "launch_nailbar_gui": ("education_system.systems.university.plugins.campus_commerce.interfaces.gui.nailbar.nailbar_gui", "launch_nailbar_gui"),
    "CarRentalGUI": ("education_system.systems.university.plugins.campus_commerce.interfaces.gui.carrental.carrental_gui", "CarRentalGUI"),
    "launch_carrental_gui": ("education_system.systems.university.plugins.campus_commerce.interfaces.gui.carrental.carrental_gui", "launch_carrental_gui"),
    "EquipmentGUI": ("education_system.systems.university.domains.operations.interfaces.gui.campus.equipment.equipment_gui", "EquipmentRentalGUI"),
    "launch_equipment_gui": ("education_system.systems.university.domains.operations.interfaces.gui.campus.equipment.equipment_gui", "launch_equipment_gui"),
    "PhoneShopGUI": ("education_system.systems.university.plugins.campus_commerce.interfaces.gui.phoneshop.phoneshop_gui", "PhoneShopGUI"),
    "launch_phoneshop_gui": ("education_system.systems.university.plugins.campus_commerce.interfaces.gui.phoneshop.phoneshop_gui", "launch_phoneshop_gui"),
    "MusicShopGUI": ("education_system.systems.university.plugins.campus_commerce.interfaces.gui.musicshop.musicshop_gui", "MusicShopGUI"),
    "launch_musicshop_gui": ("education_system.systems.university.plugins.campus_commerce.interfaces.gui.musicshop.musicshop_gui", "launch_musicshop_gui"),
    "StaffHRGUI": ("education_system.systems.university.domains.staff.interfaces.gui.staff_hr.staff_hr_gui", "StaffHRGUI"),
    "launch_staff_hr_gui": ("education_system.systems.university.domains.staff.interfaces.gui.staff_hr.staff_hr_gui", "launch_staff_hr_gui"),
    "OfficeHoursGUI": ("education_system.systems.university.domains.teaching.interfaces.gui.office_hours.office_hours_gui", "OfficeHoursGUI"),
    "DegreeAuditGUI": ("education_system.systems.university.domains.curriculum.interfaces.gui.course_management_gui.degree_audit_gui", "DegreeAuditGUI"),
    "GraduationCeremonyGUI": ("education_system.systems.university.domains.curriculum.interfaces.gui.course_management_gui.graduation_ceremony_gui", "GraduationCeremonyGUI"),
    "TaxiBookingApp": ("education_system.systems.university.domains.operations.interfaces.gui.campus.mobility.taxi_booking_gui", "TaxiBookingApp"),
    "TrainStationApp": ("education_system.systems.university.domains.operations.interfaces.gui.campus.mobility.train_station_gui", "TrainStationApp"),
    "CinemaApp": ("education_system.systems.university.plugins.campus_commerce.interfaces.gui.cinema.cinema_gui.core.main_gui", "CinemaApp"),
    "init_cinema_database": ("education_system.systems.university.plugins.campus_commerce.interfaces.gui.cinema.cinema_gui.database", "init_database"),
}

for _flag in (
    "LEGAL_SERVICES_GUI_AVAILABLE", "BETTING_SHOP_GUI_AVAILABLE", "MAIL_POST_GUI_AVAILABLE",
    "GYM_GUI_AVAILABLE", "DENTIST_GUI_AVAILABLE", "BUTCHER_GUI_AVAILABLE", "BARBER_GUI_AVAILABLE",
    "NAILBAR_GUI_AVAILABLE", "CARRENTAL_GUI_AVAILABLE", "EQUIPMENT_GUI_AVAILABLE",
    "PHONESHOP_GUI_AVAILABLE", "MUSICSHOP_GUI_AVAILABLE", "STAFF_HR_GUI_AVAILABLE",
    "OFFICE_HOURS_GUI_AVAILABLE", "DEGREE_AUDIT_GUI_AVAILABLE", "GRADUATION_CEREMONY_GUI_AVAILABLE",
    "TAXI_BOOKING_GUI_AVAILABLE", "TRAIN_STATION_GUI_AVAILABLE", "CINEMA_GUI_AVAILABLE",
):
    globals()[_flag] = True


# Bind these as proxies rather than leaving them to __getattr__ alone.
# ``from gui_imports import DegreeAuditGUI`` fires __getattr__ at the importing
# module's import time, which resolved the real class right back at startup —
# features/academic_launchers_gui.py imports OfficeHoursGUI, DegreeAuditGUI and
# GraduationCeremonyGUI by name, and course_management_gui.core._imports pulls
# seaborn, sklearn and pypdf, so the whole scientific stack loaded before the
# window appeared. A proxy makes the `from … import` form cheap.
for _name, (_mod, _attr) in _LAZY_GUI.items():
    if _name.startswith(("launch_", "init_")):
        globals()[_name] = _lazy_func(_mod, _attr, bind_as=_name)
    else:
        globals()[_name] = _lazy_class(_mod, _attr)


def __getattr__(name):  # PEP 562 — fallback for anything not bound above
    spec = _LAZY_GUI.get(name)
    if spec is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib
    module_path, attr = spec
    value = getattr(importlib.import_module(module_path), attr)
    globals()[name] = value  # cache so subsequent access skips __getattr__
    return value

# Global variables for missing components
chatbot_instance = None
CLI_AVAILABLE = True  # Assume CLI is available unless proven otherwise

# Function definitions for missing functions

def _safe_entry_insert(entry_widget, value, index=0) -> None:
    """
    Insert *value* into a Tk/ttk Entry-like widget without ever passing None to Tcl.

    Tk treats None as a missing argument which triggers a ``wrong # args`` error.
    This helper coerces None to an empty string and ensures the target widget is
    cleared before writing the new content.
    """
    text = '' if value is None else str(value)
    try:
        entry_widget.delete(0, tk.END)
    except tk.TclError as e:
        # Widget might not support delete (e.g. not yet mapped); ignore silently.
        logger.debug(f"Widget delete operation failed: {e}")
    entry_widget.insert(index, text)

def _safe_set_combobox(combobox: ttk.Combobox, value) -> None:
    """
    Set a ttk.Combobox value while gracefully handling None and incompatible inputs.

    Tkinter forwards Python's None as a missing argument to the underlying Tcl command,
    which raises `TclError: wrong # args: should be "pathName set value"`. This helper
    normalises None to an empty string and falls back to clearing the widget if Tcl
    still rejects the value (for example when the combobox is readonly and the value
    is outside its list).
    """
    safe_value = '' if value is None else str(value)

    # Empty string is equivalent to "no selection" – clear the widget safely
    if safe_value == '':
        previous_state = combobox.cget('state')
        try:
            combobox.configure(state='normal')
            _safe_entry_insert(combobox, '')
        finally:
            combobox.configure(state=previous_state)
        return

    try:
        combobox.set(safe_value)
    except tk.TclError as err:
        logging.debug("Combobox %s rejected value %r (%s); defaulting to empty string",
                      combobox, value, err)
        previous_state = combobox.cget('state')
        try:
            combobox.configure(state='normal')
            _safe_entry_insert(combobox, '')
        finally:
            combobox.configure(state=previous_state)

def init_calendar_database():
    """Initialize calendar database - placeholder implementation"""
    try:
        # Basic database initialization logic
        from education_system.systems.university.infrastructure.database.db import get_db_connection
        conn = get_db_connection()
        if conn:
            conn.close()
            return True
        return False
    except Exception as e:
        print(f"Error initializing calendar database: {e}")
        return False

def init_enhanced_database():
    """Initialize enhanced database - placeholder implementation"""
    try:
        # Basic database initialization logic
        from education_system.systems.university.infrastructure.database.db import get_db_connection
        conn = get_db_connection()
        if conn:
            conn.close()
            return True
        return False
    except Exception as e:
        print(f"Error initializing enhanced database: {e}")
        return False

def initialize_chatbot_integration():
    """Initialize chatbot integration - placeholder implementation"""
    global chatbot_instance
    try:
        # Placeholder chatbot initialization
        voice_interface_stub = type('VoiceInterfaceStub', (), {
            'enabled': False,
            'cleanup': lambda self: None
        })()

        def process_message_stub(msg):
            """Basic chatbot response logic"""
            msg_lower = msg.lower()

            if any(word in msg_lower for word in ['hello', 'hi', 'hey', 'greetings']):
                return "Hello! I'm the University Chatbot. How can I help you today?"
            elif any(word in msg_lower for word in ['course', 'class', 'subject']):
                return "I can help you with course information. Please specify what courses or subjects you're interested in."
            elif any(word in msg_lower for word in ['registration', 'enroll', 'register']):
                return "For course registration, please visit the Student Portal or contact the Registrar's Office."
            elif any(word in msg_lower for word in ['schedule', 'timetable', 'time']):
                return "You can view your class schedule in the Student Portal under 'Academic Schedule'."
            elif any(word in msg_lower for word in ['help', 'support', 'assistance']):
                return "I'm here to help! You can ask me about courses, registration, schedules, campus services, or general university information."
            elif any(word in msg_lower for word in ['campus', 'location', 'building']):
                return "For campus maps and building locations, please check the university website or visit Student Services."
            elif any(word in msg_lower for word in ['library', 'book', 'research']):
                return "The university library offers research assistance and book reservations. Visit the library website for more details."
            elif any(word in msg_lower for word in ['fee', 'tuition', 'payment', 'cost']):
                return "For tuition and fee information, please check the Finance Office or your Student Account."
            elif any(word in msg_lower for word in ['thank', 'thanks']):
                return "You're welcome! Is there anything else I can help you with?"
            elif any(word in msg_lower for word in ['bye', 'goodbye', 'exit']):
                return "Goodbye! Feel free to return if you have more questions."
            else:
                return f"I understand you're asking about: '{msg}'. While I'm operating in basic mode, I'd recommend contacting Student Services for detailed assistance with your specific query."

        chatbot_instance = type('ChatbotStub', (), {
            'set_auth_system': lambda self, auth: None,
            'process_message': lambda self, msg, user_id=None, session_id=None: process_message_stub(msg),
            'voice_interface': voice_interface_stub,
            'test_voice_interface': lambda self: {'status': 'not_available', 'message': 'Voice interface not available'},
            'get_system_status': lambda self: {'status': 'not_available', 'components': {}},
            'generate_usage_analytics': lambda self: {'total_conversations': 0, 'active_users': 0},
            'connect_to_db': lambda self: False,
            'authenticated_sessions': {},
            'conversation_history': {},
            'auth_system': None,
            'authenticate_user_for_chatbot': lambda self, username, password, mfa=None: {'success': False, 'message': 'Authentication not available'},
            'logout_user': lambda self, session_id: None,
            'text_to_speech': lambda self, text: None,
            'process_voice_input': lambda self, duration=5: "Voice input not available",
            'run_authenticated_console_interface': lambda self: None,
            'run_console_interface': lambda self: None,
            'setup_api_routes': lambda self: None,
            'run_web_server': lambda self: None
        })()
        return True
    except Exception as e:
        print(f"Error initializing chatbot: {e}")
        return False

def safe_auth_check(auth_obj):
    """Safely check if auth object has required attributes"""
    if not auth_obj:
        return False

    # Ensure required attributes exist
    if not hasattr(auth_obj, 'current_user'):
        auth_obj.current_user = None

    if not hasattr(auth_obj, 'last_activity'):
        auth_obj.last_activity = None

    if not hasattr(auth_obj, 'session_timeout'):
        auth_obj.session_timeout = 30

    if not hasattr(auth_obj, 'login_attempts'):
        auth_obj.login_attempts = {}

    if not hasattr(auth_obj, 'max_attempts'):
        auth_obj.max_attempts = 5

    if not hasattr(auth_obj, 'lockout_time'):
        auth_obj.lockout_time = 15

    return True
