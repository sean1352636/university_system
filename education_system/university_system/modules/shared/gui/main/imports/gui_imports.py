# Auto-generated import definitions
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import sys
import os
import threading
import logging
import random
import csv
from education_system.university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta

# Import authentication
try:
    from education_system.university_system.infrastructure.auth import UserAuth
except ImportError:
    UserAuth = None

# Import auth instance management from user_authentication
try:
    from education_system.university_system.infrastructure.auth import get_current_user, set_auth_instance
    HAS_AUTH = True
except ImportError:
    HAS_AUTH = False
    get_current_user = lambda: None
    set_auth_instance = lambda x: None

# Import MFA (Multi-Factor Authentication) services
try:
    from education_system.university_system.infrastructure.auth.mfa_service import (
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
    from education_system.university_system.infrastructure.auth.mfa_integration import integrate_mfa_with_auth
    MFA_INTEGRATION_AVAILABLE = True
except ImportError:
    MFA_INTEGRATION_AVAILABLE = False

try:
    from education_system.university_system.infrastructure.auth.email_otp_service import EmailOTPService
    EMAIL_OTP_AVAILABLE = True
except ImportError:
    EmailOTPService = None
    EMAIL_OTP_AVAILABLE = False

try:
    from education_system.university_system.infrastructure.auth.sms_provider import SMSProvider
    SMS_PROVIDER_AVAILABLE = True
except ImportError:
    SMSProvider = None
    SMS_PROVIDER_AVAILABLE = False

# Import security modules
try:
    from education_system.university_system.infrastructure.security.session_management import (
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
    from education_system.university_system.infrastructure.security.comprehensive_security import (
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
    from education_system.university_system.infrastructure.security.data_encryption import (
        EncryptionManager,
        encrypt_sensitive_data,
        decrypt_sensitive_data
    )
    DATA_ENCRYPTION_AVAILABLE = True
except ImportError:
    EncryptionManager = None
    DATA_ENCRYPTION_AVAILABLE = False

try:
    from education_system.university_system.modules.shared.gui.security.security_dashboard_gui import SecurityDashboard
    SECURITY_DASHBOARD_AVAILABLE = True
except ImportError:
    SecurityDashboard = None
    SECURITY_DASHBOARD_AVAILABLE = False

try:
    from education_system.university_system.modules.shared.gui.security.audit_log_viewer_gui import (
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
    from education_system.university_system.modules.shared.utils.activity_logger import log_activity
    ACTIVITY_LOGGER_AVAILABLE = True
except ImportError:
    ACTIVITY_LOGGER_AVAILABLE = False
    log_activity = lambda *args, **kwargs: None

# Import internationalization (i18n) for multi-language support
try:
    from education_system.university_system.modules.shared.utils.i18n import (
        get_text as _t,
        get_current_language,
        get_current_language_name,
        set_language,
        get_available_language_list,
        init_i18n,
    )
    from education_system.university_system.modules.shared.utils.gui_language_selector import (
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
    from education_system.university_system.infrastructure.exceptions import (
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
    from education_system.university_system.infrastructure.shared_context import set_auth as set_shared_auth, get_auth
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

# Import database connection
from education_system.university_system.infrastructure.database.db import get_db_connection, get_connection, transaction

# Import modular GUI components
from education_system.university_system.modules.domain.finance.gui.finance_management_gui import FinanceManagementGUI
from education_system.university_system.modules.domain.finance.gui.financial_aid import FinancialAidGUI
from education_system.university_system.modules.domain.student_affairs.gui.student_union_management_gui import StudentUnionManagementGUI
from education_system.university_system.modules.domain.health.gui.health_portal_management_gui import HealthPortalManagementGUI
from education_system.university_system.modules.domain.academics.gui.grade_tracking_management_gui import GradeTrackingManagementGUI
from education_system.university_system.modules.domain.commerce.gui.restaurant_management_gui import RestaurantManagementGUI
from education_system.university_system.modules.domain.commerce.gui.cafe_system_gui import CafeSystemGUI
from education_system.university_system.modules.domain.commerce.gui.takeaway_gui import TakeawayGUI
from education_system.university_system.modules.domain.commerce.gui.grocery_gui import GroceryGUI, GroceryManagementGUI
try:
    from education_system.university_system.modules.domain.commerce.gui.bar_gui import BarGUI
    BAR_GUI_AVAILABLE = True
except ImportError:
    BarGUI = None
    BAR_GUI_AVAILABLE = False
from education_system.university_system.modules.shared.gui.email.email_manager_management_gui import EmailManagerManagementGUI
from education_system.university_system.modules.domain.academics.services.modules import (compulsory_module_1, compulsory_module_2,
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
try:
    from education_system.university_system.modules.domain.academics.services.virtual_classroom import (
        VirtualClassroomManager,
        SessionManager,
        ParticipantManager,
        RecordingManager,
        BreakoutRoomManager,
        PollManager,
        ChatManager
    )
    VIRTUAL_CLASSROOM_AVAILABLE = True
except Exception as e:
    VirtualClassroomManager = None
    SessionManager = None
    ParticipantManager = None
    RecordingManager = None
    BreakoutRoomManager = None
    PollManager = None
    ChatManager = None
    VIRTUAL_CLASSROOM_AVAILABLE = False

# Feature 2: Integrated Financial Aid & Scholarship Management
try:
    from education_system.university_system.modules.domain.finance.services.financial_aid import (
        FinancialAidManager,
        ScholarshipManager
    )
    FINANCIAL_AID_AVAILABLE = True
except Exception as e:
    FinancialAidManager = None
    ScholarshipManager = None
    FINANCIAL_AID_AVAILABLE = False

# Feature 3: Unified Communication Hub
try:
    from education_system.university_system.modules.shared.services.communication import CommunicationManager
    COMMUNICATION_HUB_AVAILABLE = True
except Exception as e:
    CommunicationManager = None
    COMMUNICATION_HUB_AVAILABLE = False

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
try:
    from education_system.university_system.modules.shared.gui.advanced_search import AdvancedSearchGUI
    ADVANCED_SEARCH_GUI_AVAILABLE = True
    ADVANCED_SEARCH_GUI_IMPORT_ERROR = None
except Exception as adv_import_error:
    AdvancedSearchGUI = None
    ADVANCED_SEARCH_GUI_AVAILABLE = False
    ADVANCED_SEARCH_GUI_IMPORT_ERROR = str(adv_import_error)

try:
    from education_system.university_system.modules.domain.academics.gui.module_scheduling import ModuleSchedulingGUI, launch_module_scheduling_gui
    MODULE_SCHEDULING_GUI_AVAILABLE = True
    MODULE_SCHEDULING_GUI_IMPORT_ERROR = None
except Exception as mod_import_error:
    ModuleSchedulingGUI = None
    launch_module_scheduling_gui = None
    MODULE_SCHEDULING_GUI_AVAILABLE = False
    MODULE_SCHEDULING_GUI_IMPORT_ERROR = str(mod_import_error)

try:
    from education_system.university_system.modules.domain.academics.gui.course_management_gui import CourseManagementGUI
    COURSE_MANAGEMENT_GUI_AVAILABLE = True
except Exception:
    CourseManagementGUI = None
    COURSE_MANAGEMENT_GUI_AVAILABLE = False

try:
    from education_system.university_system.modules.domain.academics.gui.assignment_system import AssignmentGUI
    ASSIGNMENT_SUBMISSION_GUI_AVAILABLE = True
except Exception as e:
    AssignmentGUI = None
    ASSIGNMENT_SUBMISSION_GUI_AVAILABLE = False

try:
    from education_system.university_system.modules.shared.gui.document_manager_gui.main_gui import (
        DocumentManagerGUI,
    )
    from education_system.university_system.modules.shared.gui.document_manager_gui.console import (
        start_document_manager_gui,
        display_document_management_menu,
    )
    DOCUMENT_MANAGER_GUI_AVAILABLE = True
except Exception:
    DocumentManagerGUI = None
    start_document_manager_gui = None
    display_document_management_menu = None
    DOCUMENT_MANAGER_GUI_AVAILABLE = False

try:
    from education_system.university_system.modules.shared.gui.enhanced_reporting import (
        ReportingSystemGUI,
        start_enhanced_reporting_gui,
    )
    ENHANCED_REPORTING_GUI_AVAILABLE = True
except Exception:
    ReportingSystemGUI = None
    start_enhanced_reporting_gui = None
    ENHANCED_REPORTING_GUI_AVAILABLE = False

try:
    from education_system.university_system.modules.shared.gui.pdf_export_gui import PDFExportGUI, show_pdf_export_gui
    PDF_EXPORT_GUI_AVAILABLE = True
except Exception:
    PDFExportGUI = None
    show_pdf_export_gui = None
    PDF_EXPORT_GUI_AVAILABLE = False

try:
    from education_system.university_system.modules.domain.housing.gui.housing_accommodation_gui.main_gui import HousingGUI as HousingAccommodationGUI
    HOUSING_ACCOMMODATION_GUI_AVAILABLE = True
except Exception:
    HousingAccommodationGUI = None
    HOUSING_ACCOMMODATION_GUI_AVAILABLE = False

try:
    from education_system.university_system.modules.domain.academics.gui.library import LibraryGUI
    LIBRARY_GUI_AVAILABLE = True
except Exception:
    LibraryGUI = None
    LIBRARY_GUI_AVAILABLE = False

try:
    from education_system.university_system.modules.domain.academics.gui.parent_portal import ParentPortalGUI
    PARENT_PORTAL_GUI_AVAILABLE = True
    PARENT_PORTAL_GUI_IMPORT_ERROR = None
except Exception as e:
    ParentPortalGUI = None
    PARENT_PORTAL_GUI_AVAILABLE = False
    PARENT_PORTAL_GUI_IMPORT_ERROR = str(e)

try:
    from education_system.university_system.modules.shared.gui.student_analytics_gui import GUIStudentAnalytics
    STUDENT_ANALYTICS_GUI_AVAILABLE = True
except Exception:
    GUIStudentAnalytics = None
    STUDENT_ANALYTICS_GUI_AVAILABLE = False

try:
    from education_system.university_system.modules.domain.academics.gui.student_grades import StudentGradesPortal
    STUDENT_GRADES_GUI_AVAILABLE = True
except Exception:
    StudentGradesPortal = None
    STUDENT_GRADES_GUI_AVAILABLE = False

try:
    from education_system.university_system.modules.domain.academics.gui.student_outcomes_gui import StudentOutcomesGUI
    STUDENT_OUTCOMES_GUI_AVAILABLE = True
except Exception:
    StudentOutcomesGUI = None
    STUDENT_OUTCOMES_GUI_AVAILABLE = False

try:
    from education_system.university_system.modules.domain.academics.gui.student_timetable_gui import StudentTimetableGUI
    STUDENT_TIMETABLE_GUI_AVAILABLE = True
except Exception:
    StudentTimetableGUI = None
    STUDENT_TIMETABLE_GUI_AVAILABLE = False

try:
    from education_system.university_system.modules.domain.academics.gui.student_registration import StudentRegistrationPortal
    STUDENT_REGISTRATION_GUI_AVAILABLE = True
except Exception:
    StudentRegistrationPortal = None
    STUDENT_REGISTRATION_GUI_AVAILABLE = False

try:
    from education_system.university_system.modules.domain.academics.gui.student_dashboard import StudentDashboardPortal
    STUDENT_DASHBOARD_GUI_AVAILABLE = True
except Exception:
    StudentDashboardPortal = None
    STUDENT_DASHBOARD_GUI_AVAILABLE = False

try:
    from education_system.university_system.modules.domain.student_affairs.gui.student_support import StudentSupportGUI
    STUDENT_SUPPORT_GUI_AVAILABLE = True
    _STUDENT_SUPPORT_GUI_IMPORT_ERROR = None
except Exception as e:
    StudentSupportGUI = None
    STUDENT_SUPPORT_GUI_AVAILABLE = False
    _STUDENT_SUPPORT_GUI_IMPORT_ERROR = str(e)

try:
    from education_system.university_system.modules.domain.mobility.gui.trip_management_gui import TripManagementGUI
    TRIP_MANAGEMENT_GUI_AVAILABLE = True
    _TRIP_MGMT_IMPORT_ERROR = None
except Exception as e:
    TripManagementGUI = None
    TRIP_MANAGEMENT_GUI_AVAILABLE = False
    _TRIP_MGMT_IMPORT_ERROR = str(e)

try:
    from education_system.university_system.modules.domain.student_affairs.gui.alumni import AlumniGUIApp
    ALUMNI_PORTAL_GUI_AVAILABLE = True
    ALUMNI_GUI_APP_CLASS = AlumniGUIApp
    ALUMNI_PORTAL_IMPORT_ERROR = None
except Exception as alumni_error:
    AlumniGUIApp = None
    ALUMNI_PORTAL_GUI_AVAILABLE = False
    ALUMNI_GUI_APP_CLASS = None
    ALUMNI_PORTAL_IMPORT_ERROR = str(alumni_error)

try:
    from education_system.university_system.modules.domain.academics.gui.grade_tracking import GradeTrackingApp
    GRADE_TRACKING_GUI_AVAILABLE = True
except Exception as e:
    GradeTrackingApp = None
    GRADE_TRACKING_GUI_AVAILABLE = False

try:
    from education_system.university_system.modules.shared.gui.database.backup_gui import BackupGUI
    DATA_BACKUP_GUI_AVAILABLE = True
except Exception as e:
    BackupGUI = None
    DATA_BACKUP_GUI_AVAILABLE = False

try:
    from education_system.university_system.modules.domain.academics.gui.academic_calendar import CalendarGUI
    ACADEMIC_CALENDAR_GUI_AVAILABLE = True
except Exception as e:
    CalendarGUI = None
    ACADEMIC_CALENDAR_GUI_AVAILABLE = False

try:
    from education_system.university_system.modules.domain.health.gui.medical_accommodation_gui import AccommodationGUI
    ACCOMMODATION_GUI_AVAILABLE = True
except Exception as e:
    AccommodationGUI = None
    ACCOMMODATION_GUI_AVAILABLE = False

try:
    from education_system.university_system.modules.domain.academics.gui.ai_detector import AIDetectorGUI
    AI_DETECTOR_GUI_AVAILABLE = True
except Exception as e:
    AIDetectorGUI = None
    AI_DETECTOR_GUI_AVAILABLE = False

try:
    from education_system.university_system.modules.shared.gui.batch_operations import BatchOperationsGUI
    BATCH_OPS_GUI_AVAILABLE = True
except Exception as e:
    BatchOperationsGUI = None
    BATCH_OPS_GUI_AVAILABLE = False

try:
    from education_system.university_system.modules.shared.gui.email.email_gui import EmailManagerGUI
    EMAIL_MANAGER_GUI_AVAILABLE = True
except Exception as e:
    EmailManagerGUI = None
    EMAIL_MANAGER_GUI_AVAILABLE = False

try:
    from education_system.university_system.modules.domain.finance.gui.finance_reporting import FinancialManagementGUI
    FINANCE_REPORTING_GUI_AVAILABLE = True
except Exception as e:
    FinancialManagementGUI = None
    FINANCE_REPORTING_GUI_AVAILABLE = False

try:
    from education_system.university_system.modules.domain.mobility.gui.parking_management_gui import ParkingManagementGUI
    PARKING_MANAGEMENT_GUI_AVAILABLE = True
except Exception as e:
    ParkingManagementGUI = None
    PARKING_MANAGEMENT_GUI_AVAILABLE = False

try:
    from education_system.university_system.modules.domain.academics.gui.plagiarism_main_gui import PlagiarismCheckerGUI
    PLAGIARISM_GUI_AVAILABLE = True
except Exception as e:
    PlagiarismCheckerGUI = None
    PLAGIARISM_GUI_AVAILABLE = False

try:
    from education_system.university_system.modules.domain.commerce.gui.restaurant_management_gui import RestaurantManagementGUI
    RESTAURANT_MANAGEMENT_GUI_AVAILABLE = True
except Exception as e:
    RestaurantManagementGUI = None
    RESTAURANT_MANAGEMENT_GUI_AVAILABLE = False

try:
    from education_system.university_system.modules.domain.commerce.gui.shop_management_gui.main_gui import UniversityShopGUI as ShopManagementGUI
    SHOP_GUI_AVAILABLE = True
except Exception as e:
    ShopManagementGUI = None
    SHOP_GUI_AVAILABLE = False

try:
    from education_system.university_system.modules.services.gui.charity_shop_gui import CharityShopApp
    CHARITY_SHOP_GUI_AVAILABLE = True
except Exception as e:
    CharityShopApp = None
    CHARITY_SHOP_GUI_AVAILABLE = False

try:
    from education_system.university_system.modules.shared.gui.simple_activity_logger_gui import EnhancedActivityLoggerGUI as ActivityLoggerGUI
    ACTIVITY_LOGGER_GUI_AVAILABLE = True
except Exception as e:
    ActivityLoggerGUI = None
    ACTIVITY_LOGGER_GUI_AVAILABLE = False

try:
    from education_system.university_system.utils.ai.gui.university_chatbot_gui import ChatbotGUI as UniversityChatbotGUI
    CHATBOT_GUI_AVAILABLE = True
except Exception as e:
    UniversityChatbotGUI = None
    CHATBOT_GUI_AVAILABLE = False

try:
    from education_system.university_system.utils.logging.gui.log_management_gui import LogManagementGUI
    LOG_MANAGEMENT_GUI_AVAILABLE = True
except Exception as e:
    LogManagementGUI = None
    LOG_MANAGEMENT_GUI_AVAILABLE = False

try:
    from education_system.university_system.modules.domain.student_affairs.gui.internship_management_gui import InternshipGUI as InternshipManagementGUI
    INTERNSHIP_MANAGEMENT_GUI_AVAILABLE = True
except Exception as e:
    InternshipManagementGUI = None
    INTERNSHIP_MANAGEMENT_GUI_AVAILABLE = False

# Set remaining GUI availability variables to False (no corresponding GUI files found)
ANALYTICS_GUI_AVAILABLE = False  # This uses student_analytics_gui which is imported separately
CALENDAR_GUI_AVAILABLE = False  # This would be a separate calendar system
HELP_DESK_GUI_AVAILABLE = False  # Would use helpdesk_gui.py

# Import AttendanceGUI
try:
    from education_system.university_system.modules.domain.academics.gui.attendance_tracker import AttendanceGUI
    ATTENDANCE_GUI_AVAILABLE = True
except Exception as e:
    AttendanceGUI = None
    ATTENDANCE_GUI_AVAILABLE = False

# Import helpdesk GUI and CLI fallback function
try:
    from education_system.university_system.modules.domain.student_affairs.gui.helpdesk import HelpdeskGUI
    HELPDESK_GUI_AVAILABLE = True
except Exception as e:
    HelpdeskGUI = None
    HELPDESK_GUI_AVAILABLE = False

try:
    from education_system.university_system.modules.domain.student_affairs.services.helpdesk import display_helpdesk_menu
    HELPDESK_CLI_AVAILABLE = True
except Exception as e:
    display_helpdesk_menu = None
    HELPDESK_CLI_AVAILABLE = False
    print(f"❌ Failed to import Helpdesk CLI: {e}")

# Import advanced feature GUI launchers from core files
from education_system.university_system.modules.domain.academics.services.attendance.attendance_tracker import launch_advanced_attendance_gui
from education_system.university_system.modules.domain.student_affairs.services.mental_health.mental_health_core import launch_mental_health_gui
from education_system.university_system.modules.domain.student_affairs.services.early_warning.early_warning_core import launch_early_warning_gui
from education_system.university_system.modules.domain.career.services.career_services_core import launch_career_services_gui

# Import Extras Launcher (games, utilities, mini-projects)
try:
    from education_system.shared.extras.launcher import launch_as_toplevel as launch_extras_gui
    EXTRAS_LAUNCHER_AVAILABLE = True
except Exception as e:
    launch_extras_gui = None
    EXTRAS_LAUNCHER_AVAILABLE = False
    print(f"❌ Failed to import Extras Launcher: {e}")
from education_system.university_system.modules.domain.admissions.services.admissions_crm_core import launch_admissions_crm_gui
from education_system.university_system.modules.shared.services.analytics.predictive_analytics_gui import launch_predictive_analytics_gui
from education_system.university_system.modules.domain.academics.services.module_scheduling import launch_timetable_optimizer_gui
from education_system.university_system.modules.domain.campus.services.campus_events_gui import launch_campus_events_gui
from education_system.university_system.modules.domain.student_affairs.services.alumni_management import launch_alumni_relations_gui
from education_system.university_system.modules.domain.facilities.services.facilities_management_core import launch_facilities_management_gui
from education_system.university_system.modules.shared.services.business_intelligence.business_intelligence_gui import launch_business_intelligence_gui
from education_system.university_system.modules.shared.services.ai_features.ai_features_core import launch_ai_features_gui

# Phase 4: New GUI imports (October 2025)
from education_system.university_system.modules.domain.mobility.gui.mobile_app_pwa_gui import launch_mobile_app_pwa_gui
from education_system.university_system.modules.domain.academics.gui.blockchain_credentials_gui import launch_blockchain_credentials_gui
from education_system.university_system.modules.services.gui.integration_marketplace_gui import launch_integration_marketplace_gui

# Legal Services and Betting Shop GUIs
try:
    from education_system.university_system.modules.domain.legal.gui.legal_services_gui import LegalServicesGUI, launch_legal_services_gui
    LEGAL_SERVICES_GUI_AVAILABLE = True
except ImportError as e:
    LegalServicesGUI = None
    launch_legal_services_gui = None
    LEGAL_SERVICES_GUI_AVAILABLE = False

try:
    from education_system.university_system.modules.domain.betting.gui.betting_shop_gui import BettingShopGUI, launch_betting_shop_gui
    BETTING_SHOP_GUI_AVAILABLE = True
except ImportError as e:
    BettingShopGUI = None
    launch_betting_shop_gui = None
    BETTING_SHOP_GUI_AVAILABLE = False

# Mail/Post System GUI
try:
    from education_system.university_system.modules.domain.mail.gui.mail_post_gui import MailPostGUI, launch_mail_post_gui
    MAIL_POST_GUI_AVAILABLE = True
except ImportError as e:
    MailPostGUI = None
    launch_mail_post_gui = None
    MAIL_POST_GUI_AVAILABLE = False

# Gym/Fitness Center GUI
try:
    from education_system.university_system.modules.domain.gym.gui.gym_gui import GymGUI, launch_gym_gui
    GYM_GUI_AVAILABLE = True
except ImportError as e:
    GymGUI = None
    launch_gym_gui = None
    GYM_GUI_AVAILABLE = False

# Dentist/Dental Clinic GUI
try:
    from education_system.university_system.modules.domain.dentist.gui.dentist_gui import DentistGUI, launch_dentist_gui
    DENTIST_GUI_AVAILABLE = True
except ImportError as e:
    DentistGUI = None
    launch_dentist_gui = None
    DENTIST_GUI_AVAILABLE = False

# Butcher Shop GUI
try:
    from education_system.university_system.modules.domain.butcher.gui.butcher_gui import ButcherGUI, launch_butcher_gui
    BUTCHER_GUI_AVAILABLE = True
except ImportError as e:
    ButcherGUI = None
    launch_butcher_gui = None
    BUTCHER_GUI_AVAILABLE = False

# Barber Shop GUI
try:
    from education_system.university_system.modules.domain.barber.gui.barber_gui import BarberGUI, launch_barber_gui
    BARBER_GUI_AVAILABLE = True
except ImportError as e:
    BarberGUI = None
    launch_barber_gui = None
    BARBER_GUI_AVAILABLE = False

# Nail Bar/Salon GUI
try:
    from education_system.university_system.modules.domain.nailbar.gui.nailbar_gui import NailBarGUI, launch_nailbar_gui
    NAILBAR_GUI_AVAILABLE = True
except ImportError as e:
    NailBarGUI = None
    launch_nailbar_gui = None
    NAILBAR_GUI_AVAILABLE = False

# Car Rental GUI
try:
    from education_system.university_system.modules.domain.carrental.gui.carrental_gui import CarRentalGUI, launch_carrental_gui
    CARRENTAL_GUI_AVAILABLE = True
except ImportError as e:
    CarRentalGUI = None
    launch_carrental_gui = None
    CARRENTAL_GUI_AVAILABLE = False

# Equipment Rental GUI
try:
    from education_system.university_system.modules.domain.equipment.gui.equipment_gui import EquipmentRentalGUI as EquipmentGUI, launch_equipment_gui
    EQUIPMENT_GUI_AVAILABLE = True
except ImportError as e:
    EquipmentGUI = None
    launch_equipment_gui = None
    EQUIPMENT_GUI_AVAILABLE = False

# Phone Shop GUI
try:
    from education_system.university_system.modules.domain.phoneshop.gui.phoneshop_gui import PhoneShopGUI, launch_phoneshop_gui
    PHONESHOP_GUI_AVAILABLE = True
except ImportError as e:
    PhoneShopGUI = None
    launch_phoneshop_gui = None
    PHONESHOP_GUI_AVAILABLE = False

# Music Shop GUI
try:
    from education_system.university_system.modules.domain.musicshop.gui.musicshop_gui import MusicShopGUI, launch_musicshop_gui
    MUSICSHOP_GUI_AVAILABLE = True
except ImportError as e:
    MusicShopGUI = None
    launch_musicshop_gui = None
    MUSICSHOP_GUI_AVAILABLE = False

# Staff HR Management GUI
try:
    from education_system.university_system.modules.domain.staff_hr.gui.staff_hr_gui import StaffHRGUI, launch_staff_hr_gui
    STAFF_HR_GUI_AVAILABLE = True
except ImportError as e:
    StaffHRGUI = None
    launch_staff_hr_gui = None
    STAFF_HR_GUI_AVAILABLE = False

# Office Hours Management GUI
try:
    from education_system.university_system.modules.domain.academics.gui.office_hours.office_hours_gui import OfficeHoursGUI
    OFFICE_HOURS_GUI_AVAILABLE = True
except ImportError as e:
    OfficeHoursGUI = None
    OFFICE_HOURS_GUI_AVAILABLE = False

# TA Management GUI
try:
    from education_system.university_system.modules.domain.academics.gui.ta_management.ta_gui import TAManagementGUI
    TA_MANAGEMENT_GUI_AVAILABLE = True
except ImportError as e:
    TAManagementGUI = None
    TA_MANAGEMENT_GUI_AVAILABLE = False

# Taxi Booking GUI
try:
    from education_system.university_system.modules.domain.mobility.gui.taxi_booking_gui import TaxiBookingApp
    TAXI_BOOKING_GUI_AVAILABLE = True
except ImportError as e:
    TaxiBookingApp = None
    TAXI_BOOKING_GUI_AVAILABLE = False

# Train Station GUI
try:
    from education_system.university_system.modules.domain.mobility.gui.train_station_gui import TrainStationApp
    TRAIN_STATION_GUI_AVAILABLE = True
except ImportError as e:
    TrainStationApp = None
    TRAIN_STATION_GUI_AVAILABLE = False

# Cinema Booking GUI
try:
    from education_system.university_system.modules.domain.cinema.gui.cinema_gui.core.main_gui import CinemaApp
    from education_system.university_system.modules.domain.cinema.gui.cinema_gui.database import init_database as init_cinema_database
    CINEMA_GUI_AVAILABLE = True
except ImportError as e:
    CinemaApp = None
    init_cinema_database = None
    CINEMA_GUI_AVAILABLE = False

# Global variables for missing components
chatbot_instance = None
CLI_AVAILABLE = True  # Assume CLI is available unless proven otherwise

# Function definitions for missing functions
def init_calendar_database():
    """Initialize calendar database - placeholder implementation"""
    try:
        # Basic database initialization logic
        from education_system.university_system.infrastructure.database.db import get_db_connection
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
        from education_system.university_system.infrastructure.database.db import get_db_connection
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
        from education_system.university_system.infrastructure.database.db import get_db_connection
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
        from education_system.university_system.infrastructure.database.db import get_db_connection
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
