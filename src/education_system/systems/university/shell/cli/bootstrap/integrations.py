"""Legacy integrations used by the compatibility router."""

from education_system.systems.university.shell.cli.imports import (
    logging, datetime, logger, _t, get_text, get_auth, UserAuth, set_auth,
    display_assignment_menu, display_course_management_menu,
    display_academic_calendar_menu, display_trip_management_menu,
    display_housing_accommodation_menu, display_shop_menu,
    display_log_management_menu, display_user_management_menu,
    display_auth_menu, display_parent_portal_menu,
    display_parent_portal_enhancement_menu,
    display_language_menu_option,
    # CLI availability flags
    ACADEMIC_MISCONDUCT_AVAILABLE, academic_misconduct_menu,
    SECURITY_DESK_AVAILABLE, security_desk_menu,
    TODO_AVAILABLE, todo_menu,
    CHURCH_AVAILABLE, church_menu,
    POLICE_STATION_AVAILABLE, police_station_menu,
    TAXI_BOOKING_AVAILABLE, taxi_booking_menu,
    TRAIN_STATION_AVAILABLE, train_station_menu,
    LEGAL_SERVICES_AVAILABLE, legal_services_menu,
    INFORMATION_RIGHTS_AVAILABLE, information_rights_menu,
    CARRENTAL_AVAILABLE, carrental_menu,
    EQUIPMENT_RENTAL_AVAILABLE, equipment_rental_menu,
    PHONE_SHOP_AVAILABLE, phone_shop_menu,
    MUSIC_SHOP_AVAILABLE, music_shop_menu,
    BAR_AVAILABLE, bar_menu,
    BETTING_SHOP_AVAILABLE, launch_betting_shop_cli,
    BUTCHER_SHOP_AVAILABLE, launch_butcher_cli,
    BARBER_SHOP_AVAILABLE, launch_barber_cli,
    NAILBAR_AVAILABLE, launch_nailbar_cli,
    CINEMA_AVAILABLE, launch_cinema_cli,
    MEDICAL_ACCOMMODATION_AVAILABLE, launch_medical_accommodation_cli,
    DEGREE_AUDIT_CLI_AVAILABLE, launch_degree_audit_cli,
    GRADUATION_CEREMONY_CLI_AVAILABLE, launch_graduation_ceremony_cli,
    MAIL_POST_AVAILABLE, mail_post_menu,
    GYM_AVAILABLE, gym_menu,
    DENTIST_AVAILABLE, dentist_menu,
    CHARITY_SHOP_CLI_AVAILABLE, display_charity_shop_menu,
    CAFE_CLI_AVAILABLE, display_cafe_menu,
    TAKEAWAY_CLI_AVAILABLE, display_takeaway_menu,
    GROCERY_CLI_AVAILABLE, display_grocery_menu,
    STAFF_HR_CLI_AVAILABLE, display_staff_hr_menu,
    SECURITY_DASHBOARD_CLI_AVAILABLE, display_security_dashboard_menu,
)

# Import additional functions from database_manager
from education_system.systems.university.shell.cli.database_manager import cleanup_database_on_startup, init_all_databases, init_auth_for_modules, cleanup_database_connections

# Import menu functions
from education_system.systems.university.shell.cli.student_operations import display_student_records_menu, set_auth as set_student_ops_auth
from education_system.systems.university.shell.cli.integration_manager import display_integrated_academic_menu, set_auth as set_integration_auth
from education_system.systems.university.domains.quality.domain.evaluation.course_evaluation_core import display_course_evaluation_menu
from education_system.systems.university.domains.health.interfaces.cli.health_portal import (
    display_health_portal_menu,
)
from education_system.systems.university.domains.student_life.domain.career_services.career_services_core import display_career_services_menu
from education_system.systems.university.domains.student_support.domain.student_support.features.dashboard import display_support_menu
from education_system.systems.university.domains.student_support.domain.student_support.auth import set_auth as set_support_auth
from education_system.systems.university.domains.library.domain.library.menu import display_library_menu
from education_system.systems.university.domains.operations.domain.campus.facilities.services.facilities_management_core import display_facilities_management_menu
from education_system.systems.university.domains.admissions.domain.services.admissions_crm_core import display_admissions_crm_menu
from education_system.systems.university.domains.admissions.domain.ucas.ucas_cli import run as display_ucas_management_menu
from education_system.systems.university.domains.research.interfaces.cli.research.research_office_cli import display_research_grants_menu, display_research_office_menu
from education_system.systems.university.domains.operations.domain.campus.services.campus_events_core import display_campus_events_menu
try:
    from education_system.systems.university.domains.finance.interfaces.cli.menu import (
        display_finance_menu,
    )
    from education_system.systems.university.domains.finance.domain.core.finance_context import (
        set_auth as set_finance_auth,
    )
except ImportError:
    display_finance_menu = None

    def set_finance_auth(_auth):
        return None

# Import menu functions that may not exist - with fallbacks
try:
    from education_system.systems.university.domains.assessment.interfaces.gui.grade_tracking_management_gui import display_enhanced_grade_menu, predictive_analytics_menu
except ImportError:
    display_enhanced_grade_menu = None
    predictive_analytics_menu = None

try:
    from education_system.systems.university.domains.student_life.interfaces.gui.student_union_management_gui import display_student_union_menu
except ImportError:
    display_student_union_menu = None

# Import fully-implemented menu functions for previously-stubbed features
from education_system.systems.university.domains.teaching.domain.attendance import display_advanced_attendance_menu
from education_system.systems.university.domains.teaching.domain.timetable import display_timetable_optimizer_menu
from education_system.systems.university.domains.learners.interfaces.cli.alumni import display_alumni_relations_menu

# Import utility functions
from education_system.systems.university.shell.cli.utils import safe_auth_check

# Import exceptions
from education_system.systems.university.infrastructure.exceptions import (
    ValidationError, AuthenticationError, PermissionDeniedError
)

# Import auth-related functions
from education_system.systems.university.infrastructure.auth import set_auth_instance

# Import permission setup functions
from education_system.systems.university.domains.learners.domain.alumni import setup_alumni_permissions
from education_system.systems.university.domains.student_life.domain.internship_management import setup_internship_permissions
from education_system.systems.university.domains.student_life.domain.student_life.student_union.administration.student_union_core import setup_student_union_permissions
from education_system.systems.university.infrastructure.auth import add_finance_permissions
from education_system.systems.university.plugins.campus_commerce.domain.services.shop_management import setup_shop_permissions
from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import setup_trip_permissions
from education_system.systems.university.plugins.campus_commerce.interfaces.cli.services.charity_shop_cli import setup_charity_shop_permissions
from education_system.systems.university.plugins.campus_commerce.interfaces.cli.services.cafe_system_cli import setup_cafe_permissions
from education_system.systems.university.plugins.campus_commerce.domain.services.takeaway.takeaway_service import setup_takeaway_permissions
from education_system.systems.university.plugins.campus_commerce.domain.services.grocery.grocery_service import setup_grocery_permissions
from education_system.systems.university.domains.staff.interfaces.cli.staff_hr.staff_hr_cli import setup_staff_hr_permissions
from education_system.systems.university.domains.teaching.domain.office_hours.office_hours_permissions import setup_office_hours_permissions
from education_system.systems.university.domains.assessment.domain.assignments.admin_tools.ta_permissions_setup import setup_ta_permissions

# Import Office Hours and TA Management CLI menus
try:
    from education_system.systems.university.domains.teaching.interfaces.cli.office_hours_cli import display_office_hours_menu
    OFFICE_HOURS_CLI_AVAILABLE = True
except ImportError:
    display_office_hours_menu = None
    OFFICE_HOURS_CLI_AVAILABLE = False

try:
    from education_system.systems.university.domains.assessment.domain.assignments.admin_tools.ta_management_cli import display_ta_management_menu
    TA_MANAGEMENT_CLI_AVAILABLE = True
except ImportError:
    display_ta_management_menu = None
    TA_MANAGEMENT_CLI_AVAILABLE = False

# Import plagiarism checker integration
from education_system.systems.university.domains.integrity.interfaces.gui.plagiarism_main_gui import integrate_plagiarism_checker_with_main

# Import auth linking
from education_system.systems.university.shell.cli.auth_manager import _link_auth_to_student_union

# Import admin tools menus
from education_system.systems.university.shell.cli.admin_tools import display_analytics_menu, display_batch_menu, display_admin_tools_menu

# Import export menu
from education_system.systems.university.shell.cli.export_manager import display_export_menu, display_pdf_export_menu

# Import system monitoring
from education_system.systems.university.shell.cli.system_monitoring import display_system_monitoring_menu

# Import service menus
from education_system.systems.university.shared.analytics.analytics_dashboard_core import display_predictive_analytics_menu
from education_system.systems.university.shared.analytics.business_intelligence.bi_reports_core import display_business_intelligence_menu
from education_system.systems.university.shell.cli.student_search_cli import display_enhanced_menu
from education_system.systems.university.shell.cli.ai.features_menu import display_ai_features_menu
from education_system.systems.university.services.integrations.integration_marketplace_core import display_integration_marketplace_menu

# Import domain-specific menus
from education_system.systems.university.domains.finance.domain.blockchain.services.blockchain_credentials_core import display_blockchain_credentials_menu
from education_system.systems.university.domains.operations.domain.campus.mobility.services.mobile_app_pwa_core import display_mobile_app_pwa_menu
from education_system.systems.university.domains.teaching.domain.virtual_classroom.classroom_manager import VirtualClassroomManager
from education_system.systems.university.domains.teaching.domain.virtual_classroom.session_manager import SessionManager
from education_system.systems.university.domains.teaching.domain.virtual_classroom.participant_manager import ParticipantManager
from education_system.systems.university.domains.teaching.domain.virtual_classroom.recording_manager import RecordingManager
from education_system.systems.university.domains.finance.domain.services.financial_aid.aid_manager import FinancialAidManager
