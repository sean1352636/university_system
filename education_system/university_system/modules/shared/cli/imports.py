"""
Centralized imports for CLI system.

This module contains all imports used across the CLI system with availability flags
for optional dependencies.
"""

# Standard library imports
import sys
import time
import logging
import contextlib
import io
import random
import hashlib
import secrets
import re
import os
import csv
from education_system.university_system.infrastructure.database.db import sqlite3
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

# Optional third-party dependencies with availability flags
try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    pd = None
    HAS_PANDAS = False

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False
    letter = None
    SimpleDocTemplate = None
    Table = None
    TableStyle = None
    Paragraph = None
    getSampleStyleSheet = None
    colors = None

# Import centralized paths and defaults
from education_system.university_system.modules.shared.constants import paths
from education_system.university_system.modules.shared.constants import defaults

# Database file path - use centralized path configuration
DB_PATH = str(paths.DEFAULT_DB_PATH)
LOG_DIR = str(paths.LOG_DIR)

# Configure logging
from education_system.university_system.utils.logging.log_config import configure_logging
logger = configure_logging(name=__name__)

# Activity logging
from education_system.university_system.modules.shared.utils.simple_activity_logger import (
    log_dynamic_activity as log_activity,
    log_create,
    log_read,
    log_update,
    log_delete,
    log_search,
    log_export,
    log_menu_navigation,
    log_dynamic_activity,
)

# SQL safety utilities
from education_system.university_system.modules.shared.utils.sql_safety import (
    validate_table_name,
    validate_column_definition,
    safe_alter_table_add_column,
    SQLIdentifierError,
)

# Internationalization (i18n)
from education_system.university_system.modules.shared.utils.i18n import (
    init_i18n,
    get_text,
    set_language,
    get_current_language,
    get_current_language_name,
    SUPPORTED_LANGUAGES,
)
# Alias for convenience
_t = get_text

from education_system.university_system.modules.shared.utils.language_selector import (
    display_language_selector,
    display_language_menu_option,
)

# Database utilities
from education_system.university_system.infrastructure.database.database_utils import cleanup_database_connections

# Module definitions
from education_system.university_system.modules.domain.academics.services.modules import (
    compulsory_module_1,
    compulsory_module_2,
    optional_module_1,
    optional_module_2,
    optional_module_3,
    optional_module_4,
    CS_optional_module_1,
    CS_optional_module_2,
    CS_optional_module_3,
    CS_optional_module_4,
    DS_optional_module_1,
    DS_optional_module_2,
    DS_optional_module_3,
    DS_optional_module_4,
)

# Assignment system
from education_system.university_system.modules.domain.academics.services.assignments.assignment_submission import (
    display_assignment_menu,
    init_assignment_system,
    add_assignment_permissions
)

# Academic Misconduct CLI
try:
    from education_system.university_system.modules.services.cli.academic_misconduct_cli import academic_misconduct_menu
    ACADEMIC_MISCONDUCT_AVAILABLE = True
except ImportError as e:
    academic_misconduct_menu = None
    ACADEMIC_MISCONDUCT_AVAILABLE = False
    logger.warning(f"Academic Misconduct CLI not available: {e}")

# Security Desk CLI
try:
    from education_system.university_system.modules.services.cli.security_desk_cli import security_desk_menu
    SECURITY_DESK_AVAILABLE = True
except ImportError as e:
    security_desk_menu = None
    SECURITY_DESK_AVAILABLE = False
    logger.warning(f"Security Desk CLI not available: {e}")

# To-Do List CLI
try:
    from education_system.university_system.modules.services.cli.todo_cli import todo_menu
    TODO_AVAILABLE = True
except ImportError as e:
    todo_menu = None
    TODO_AVAILABLE = False
    logger.warning(f"To-Do List CLI not available: {e}")

# Church Management CLI
try:
    from education_system.university_system.modules.services.cli.church_cli import church_menu
    CHURCH_AVAILABLE = True
except ImportError as e:
    church_menu = None
    CHURCH_AVAILABLE = False
    logger.warning(f"Church Management CLI not available: {e}")

# Police Station CLI
try:
    from education_system.university_system.modules.services.cli.police_station_cli import police_station_menu
    POLICE_STATION_AVAILABLE = True
except ImportError as e:
    police_station_menu = None
    POLICE_STATION_AVAILABLE = False
    logger.warning(f"Police Station CLI not available: {e}")

# Taxi Booking CLI
try:
    from education_system.university_system.modules.services.cli.taxi_booking_cli import taxi_booking_menu
    TAXI_BOOKING_AVAILABLE = True
except ImportError as e:
    taxi_booking_menu = None
    TAXI_BOOKING_AVAILABLE = False
    logger.warning(f"Taxi Booking CLI not available: {e}")

# Train Station CLI
try:
    from education_system.university_system.modules.services.cli.train_station_cli import train_station_menu
    TRAIN_STATION_AVAILABLE = True
except ImportError as e:
    train_station_menu = None
    TRAIN_STATION_AVAILABLE = False
    logger.warning(f"Train Station CLI not available: {e}")

# Legal Services CLI
try:
    from education_system.university_system.modules.services.cli.legal_services_cli import legal_services_menu
    LEGAL_SERVICES_AVAILABLE = True
except ImportError as e:
    legal_services_menu = None
    LEGAL_SERVICES_AVAILABLE = False
    logger.warning(f"Legal Services CLI not available: {e}")

# Car Rental CLI
try:
    from education_system.university_system.modules.services.cli.carrental_cli import carrental_menu
    CARRENTAL_AVAILABLE = True
except ImportError as e:
    carrental_menu = None
    CARRENTAL_AVAILABLE = False
    logger.warning(f"Car Rental CLI not available: {e}")

# Equipment Rental CLI
try:
    from education_system.university_system.modules.services.cli.equipment_rental_cli import equipment_rental_menu
    EQUIPMENT_RENTAL_AVAILABLE = True
except ImportError as e:
    equipment_rental_menu = None
    EQUIPMENT_RENTAL_AVAILABLE = False
    logger.warning(f"Equipment Rental CLI not available: {e}")

# Phone Shop CLI
try:
    from education_system.university_system.modules.services.cli.phone_shop_cli import phone_shop_menu
    PHONE_SHOP_AVAILABLE = True
except ImportError as e:
    phone_shop_menu = None
    PHONE_SHOP_AVAILABLE = False
    logger.warning(f"Phone Shop CLI not available: {e}")

# Music Shop CLI
try:
    from education_system.university_system.modules.services.cli.music_shop_cli import music_shop_menu
    MUSIC_SHOP_AVAILABLE = True
except ImportError as e:
    music_shop_menu = None
    MUSIC_SHOP_AVAILABLE = False
    logger.warning(f"Music Shop CLI not available: {e}")

# Bar CLI
try:
    from education_system.university_system.modules.services.cli.bar_cli import bar_menu
    BAR_AVAILABLE = True
except ImportError as e:
    bar_menu = None
    BAR_AVAILABLE = False
    logger.warning(f"Bar CLI not available: {e}")

# Betting Shop CLI
try:
    from education_system.university_system.modules.services.cli.betting_shop_cli import launch_betting_shop_cli
    BETTING_SHOP_AVAILABLE = True
except ImportError as e:
    launch_betting_shop_cli = None
    BETTING_SHOP_AVAILABLE = False
    logger.warning(f"Betting Shop CLI not available: {e}")

# Butcher Shop CLI
try:
    from education_system.university_system.modules.services.cli.butcher_cli import launch_butcher_cli
    BUTCHER_SHOP_AVAILABLE = True
except ImportError as e:
    launch_butcher_cli = None
    BUTCHER_SHOP_AVAILABLE = False
    logger.warning(f"Butcher Shop CLI not available: {e}")

# Barber Shop CLI
try:
    from education_system.university_system.modules.services.cli.barber_cli import launch_barber_cli
    BARBER_SHOP_AVAILABLE = True
except ImportError as e:
    launch_barber_cli = None
    BARBER_SHOP_AVAILABLE = False
    logger.warning(f"Barber Shop CLI not available: {e}")

# Nail Bar CLI
try:
    from education_system.university_system.modules.services.cli.nailbar_cli import launch_nailbar_cli
    NAILBAR_AVAILABLE = True
except ImportError as e:
    launch_nailbar_cli = None
    NAILBAR_AVAILABLE = False
    logger.warning(f"Nail Bar CLI not available: {e}")

# Cinema CLI
try:
    from education_system.university_system.modules.services.cli.cinema_cli import launch_cinema_cli
    CINEMA_AVAILABLE = True
except ImportError as e:
    launch_cinema_cli = None
    CINEMA_AVAILABLE = False
    logger.warning(f"Cinema CLI not available: {e}")

# Medical Accommodation CLI
try:
    from education_system.university_system.modules.services.cli.medical_accommodation_cli import launch_medical_accommodation_cli
    MEDICAL_ACCOMMODATION_AVAILABLE = True
except ImportError as e:
    launch_medical_accommodation_cli = None
    MEDICAL_ACCOMMODATION_AVAILABLE = False
    logger.warning(f"Medical Accommodation CLI not available: {e}")

# Degree Audit CLI
try:
    from education_system.university_system.modules.services.cli.degree_audit_cli import launch_degree_audit_cli
    DEGREE_AUDIT_CLI_AVAILABLE = True
except ImportError as e:
    launch_degree_audit_cli = None
    DEGREE_AUDIT_CLI_AVAILABLE = False
    logger.warning(f"Degree Audit CLI not available: {e}")

# Mail/Post CLI
try:
    from education_system.university_system.modules.services.cli.mail_post_cli import mail_post_menu
    MAIL_POST_AVAILABLE = True
except ImportError as e:
    mail_post_menu = None
    MAIL_POST_AVAILABLE = False
    logger.warning(f"Mail/Post CLI not available: {e}")

# Gym CLI
try:
    from education_system.university_system.modules.services.cli.gym_cli import gym_menu
    GYM_AVAILABLE = True
except ImportError as e:
    gym_menu = None
    GYM_AVAILABLE = False
    logger.warning(f"Gym CLI not available: {e}")

# Dentist CLI
try:
    from education_system.university_system.modules.domain.health.portal.dentist_cli import dentist_menu
    DENTIST_AVAILABLE = True
except ImportError as e:
    dentist_menu = None
    DENTIST_AVAILABLE = False
    logger.warning(f"Dentist CLI not available: {e}")

# Authentication and authorization
from education_system.university_system.infrastructure.auth import (
    display_user_management_menu,
    add_finance_permissions,
    UserAuth,
    display_auth_menu,
    set_auth_instance,
    set_global_auth,
    get_global_auth,
)
from education_system.university_system.infrastructure.shared_context import get_auth, set_auth

# Multi-Factor Authentication (MFA) services
try:
    from education_system.university_system.infrastructure.auth.mfa_service import (
        MFAService,
        setup_totp,
        verify_totp,
        generate_sms_otp,
        verify_sms_otp
    )
    MFA_AVAILABLE = True
except ImportError as e:
    MFAService = None
    MFA_AVAILABLE = False
    logger.warning(f"MFA services not available: {e}")

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

# Security modules
try:
    from education_system.university_system.infrastructure.security.session_management import (
        SessionManager,
        SessionInfo,
        create_session,
        validate_session
    )
    SESSION_MANAGEMENT_AVAILABLE = True
except ImportError as e:
    SessionManager = None
    SESSION_MANAGEMENT_AVAILABLE = False
    logger.warning(f"Session management not available: {e}")

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
except ImportError as e:
    APISecurityManager = None
    PasswordSecurityManager = None
    SecurityAuditManager = None
    COMPREHENSIVE_SECURITY_AVAILABLE = False
    logger.warning(f"Comprehensive security not available: {e}")

try:
    from education_system.university_system.infrastructure.security.data_encryption import (
        EncryptionManager,
        encrypt_sensitive_data,
        decrypt_sensitive_data
    )
    DATA_ENCRYPTION_AVAILABLE = True
except ImportError as e:
    EncryptionManager = None
    DATA_ENCRYPTION_AVAILABLE = False
    logger.warning(f"Data encryption not available: {e}")

try:
    from education_system.university_system.infrastructure.security.security_dashboard_cli import display_security_dashboard_menu
    SECURITY_DASHBOARD_CLI_AVAILABLE = True
except ImportError as e:
    display_security_dashboard_menu = None
    SECURITY_DASHBOARD_CLI_AVAILABLE = False
    logger.warning(f"Security Dashboard CLI not available: {e}")

# Student Union modules
from education_system.university_system.modules.domain.student_affairs.student_union.clubs import club_management as su_club
from education_system.university_system.modules.domain.student_affairs.student_union.events import event_management as su_event
from education_system.university_system.modules.domain.student_affairs.student_union.facilities import facility_management as su_fac
from education_system.university_system.modules.domain.student_affairs.student_union.administration import (
    admin_management as su_admin,
    finance_oversight as su_fin,
    miscellaneous as su_misc,
    student_union_core,
)
from education_system.university_system.modules.domain.student_affairs.student_union.elections import election_management as su_elec

# Trip Management
from education_system.university_system.modules.domain.mobility.services.trip_management import (
    display_trip_management_menu,
    init_trip_db,
    setup_trip_permissions,
    set_auth as set_trip_auth,
    integrate_trip_management_with_main,
)

# Housing/Accommodation
from education_system.university_system.modules.domain.housing.services.housing_accommodation import (
    display_housing_accommodation_menu,
    init_housing_db,
    set_auth as set_accommodation_auth,
)

# AI Detector
from education_system.university_system.utils.ai.ai_detector.detector import AIDetector

# Academic Calendar
from education_system.university_system.modules.domain.academics.services.academic_calendar.cli import (
    display_academic_calendar_menu,
    set_auth as set_calendar_auth,
    ensure_calendar_permissions,
)

# Course Management
from education_system.university_system.modules.domain.academics.services.course_management import display_course_management_menu

# Log Management
from education_system.university_system.utils.logging.log_management import display_log_management_menu

# Parent Portal
from education_system.university_system.modules.domain.academics.services.parent_portal import (
    ParentPortal,
    integrate_parent_portal_with_main,
    display_parent_portal_menu,
    display_parent_portal_enhancement_menu
)

# Shop Management
from education_system.university_system.modules.domain.commerce.services.shop_management import (
    init_shop_db,
    setup_shop_permissions,
    display_shop_menu,
    set_auth as set_shop_auth,
    log_activity as shop_log_activity,
    log_create as shop_log_create,
    log_read as shop_log_read,
    log_update as shop_log_update,
    log_delete as shop_log_delete,
)

# Charity Shop CLI
try:
    from education_system.university_system.modules.services.cli.charity_shop_cli import (
        init_charity_shop_db,
        setup_charity_shop_permissions,
        display_charity_shop_menu,
        set_auth as set_charity_shop_auth,
    )
    CHARITY_SHOP_CLI_AVAILABLE = True
except ImportError as e:
    CHARITY_SHOP_CLI_AVAILABLE = False
    display_charity_shop_menu = None
    init_charity_shop_db = lambda: False
    setup_charity_shop_permissions = lambda x=None: None
    set_charity_shop_auth = lambda x: None
    logger.warning(f"Charity Shop CLI not available: {e}")

# Cafe System CLI
try:
    from education_system.university_system.modules.services.cli.cafe_system_cli import (
        init_cafe_db,
        setup_cafe_permissions,
        display_cafe_menu,
        set_auth as set_cafe_auth,
    )
    CAFE_CLI_AVAILABLE = True
except ImportError as e:
    CAFE_CLI_AVAILABLE = False
    display_cafe_menu = None
    init_cafe_db = lambda: False
    setup_cafe_permissions = lambda x=None: None
    set_cafe_auth = lambda x: None
    logger.warning(f"Cafe System CLI not available: {e}")

# Takeaway System
try:
    from education_system.university_system.modules.domain.commerce.services.takeaway import (
        init_takeaway_db,
        setup_takeaway_permissions,
        display_takeaway_menu,
        set_auth as set_takeaway_auth,
    )
    TAKEAWAY_CLI_AVAILABLE = True
except ImportError as e:
    TAKEAWAY_CLI_AVAILABLE = False
    display_takeaway_menu = None
    init_takeaway_db = lambda: False
    setup_takeaway_permissions = lambda x=None: None
    set_takeaway_auth = lambda x: None
    logger.warning(f"Takeaway System CLI not available: {e}")

# Grocery Shop
try:
    from education_system.university_system.modules.domain.commerce.services.grocery import (
        init_grocery_db,
        setup_grocery_permissions,
        display_grocery_menu,
        set_auth as set_grocery_auth,
    )
    GROCERY_CLI_AVAILABLE = True
except ImportError as e:
    GROCERY_CLI_AVAILABLE = False
    display_grocery_menu = None
    init_grocery_db = lambda: False
    setup_grocery_permissions = lambda x=None: None
    set_grocery_auth = lambda x: None
    logger.warning(f"Grocery Shop CLI not available: {e}")

# Staff HR CLI
try:
    from education_system.university_system.modules.domain.staff_hr.cli.staff_hr_cli import (
        init_staff_hr_db,
        setup_staff_hr_permissions,
        display_staff_hr_menu,
        set_auth as set_staff_hr_auth,
    )
    STAFF_HR_CLI_AVAILABLE = True
except ImportError as e:
    STAFF_HR_CLI_AVAILABLE = False
    display_staff_hr_menu = None
    init_staff_hr_db = lambda: False
    setup_staff_hr_permissions = lambda x=None: None
    set_staff_hr_auth = lambda x: None
    logger.warning(f"Staff HR CLI not available: {e}")

# Additional integrations - lazy imports to avoid circular dependencies
def get_enhanced_reporting():
    """Lazy import for enhanced reporting"""
    try:
        from education_system.university_system.modules.shared.services.analytics.enhanced_reporting import display_enhanced_reporting_menu
        return display_enhanced_reporting_menu
    except ImportError:
        return None

def get_predictive_analytics():
    """Lazy import for predictive analytics GUI class"""
    try:
        from education_system.university_system.modules.shared.services.analytics.predictive_analytics_gui import PredictiveAnalyticsGUI
        return PredictiveAnalyticsGUI
    except ImportError:
        return None

def get_business_intelligence():
    """Lazy import for business intelligence"""
    try:
        from education_system.university_system.modules.shared.services.business_intelligence import display_business_intelligence_menu
        return display_business_intelligence_menu
    except ImportError:
        return None

def get_enhanced_menu():
    """Lazy import for enhanced search menu"""
    try:
        from education_system.university_system.modules.shared.gui.advanced_search import display_enhanced_menu
        return display_enhanced_menu
    except ImportError:
        return None

def get_document_management():
    """Lazy import for document management"""
    try:
        from education_system.university_system.modules.shared.utils.document_manager import display_document_management_menu
        return display_document_management_menu
    except ImportError:
        return None

def get_backup_menu():
    """Lazy import for backup menu"""
    try:
        from education_system.university_system.infrastructure.database.data_backup import display_backup_menu
        return display_backup_menu
    except ImportError:
        return None

# Export all availability flags and commonly used imports
__all__ = [
    # Standard library
    'sys', 'time', 'logging', 'contextlib', 'io', 'random', 'hashlib', 'secrets',
    're', 'os', 'csv', 'datetime',
    # Third-party
    'pd', 'HAS_PANDAS', 'HAS_REPORTLAB',
    # Configuration
    'DB_PATH', 'LOG_DIR', 'logger', 'paths', 'defaults',
    # Utilities
    'log_activity', 'log_create', 'log_read', 'log_update', 'log_delete',
    'log_search', 'log_export', 'log_menu_navigation', 'log_dynamic_activity',
    'validate_table_name', 'validate_column_definition', 'safe_alter_table_add_column',
    'SQLIdentifierError',
    # i18n
    'init_i18n', 'get_text', '_t', 'set_language', 'get_current_language',
    'get_current_language_name', 'SUPPORTED_LANGUAGES',
    'display_language_selector', 'display_language_menu_option',
    # Auth
    'UserAuth', 'get_auth', 'set_auth', 'get_global_auth', 'set_global_auth',
    'display_user_management_menu', 'display_auth_menu',
    # Availability flags
    'ACADEMIC_MISCONDUCT_AVAILABLE', 'SECURITY_DESK_AVAILABLE', 'TODO_AVAILABLE',
    'CHURCH_AVAILABLE', 'POLICE_STATION_AVAILABLE', 'TAXI_BOOKING_AVAILABLE',
    'TRAIN_STATION_AVAILABLE', 'LEGAL_SERVICES_AVAILABLE', 'CARRENTAL_AVAILABLE',
    'EQUIPMENT_RENTAL_AVAILABLE', 'PHONE_SHOP_AVAILABLE', 'MUSIC_SHOP_AVAILABLE',
    'BAR_AVAILABLE', 'BETTING_SHOP_AVAILABLE', 'BUTCHER_SHOP_AVAILABLE',
    'BARBER_SHOP_AVAILABLE', 'NAILBAR_AVAILABLE', 'CINEMA_AVAILABLE',
    'MEDICAL_ACCOMMODATION_AVAILABLE', 'DEGREE_AUDIT_CLI_AVAILABLE',
    'MAIL_POST_AVAILABLE', 'GYM_AVAILABLE', 'DENTIST_AVAILABLE',
    'MFA_AVAILABLE', 'MFA_INTEGRATION_AVAILABLE', 'EMAIL_OTP_AVAILABLE',
    'SMS_PROVIDER_AVAILABLE', 'SESSION_MANAGEMENT_AVAILABLE',
    'COMPREHENSIVE_SECURITY_AVAILABLE', 'DATA_ENCRYPTION_AVAILABLE',
    'SECURITY_DASHBOARD_CLI_AVAILABLE', 'CHARITY_SHOP_CLI_AVAILABLE',
    'CAFE_CLI_AVAILABLE', 'TAKEAWAY_CLI_AVAILABLE', 'GROCERY_CLI_AVAILABLE',
    'STAFF_HR_CLI_AVAILABLE',
]
