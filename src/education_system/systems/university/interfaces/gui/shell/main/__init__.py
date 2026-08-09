# Auto-generated package init
from education_system.systems.university.interfaces.gui.shell.main.main_gui import (
    init_gui, set_auth, UnifiedManagementGUI, HAS_AUTH,
    auth, get_auth, set_shared_auth, tk, ttk, datetime,
)

# Re-export helper functions, flags, GUI classes, and utilities that tests and other modules expect
from education_system.systems.university.interfaces.gui.shell.main.imports.gui_imports import (
    _safe_entry_insert,
    _safe_set_combobox,
    MFA_AVAILABLE,
    ACTIVITY_LOGGER_AVAILABLE,
    log_activity,
    get_db_connection,
    get_current_user,
    set_auth_instance,
    # GUI classes
    FinanceManagementGUI,
    StudentUnionManagementGUI,
    HealthPortalManagementGUI,
    GradeTrackingManagementGUI,
    RestaurantManagementGUI,
    EmailManagerManagementGUI,
    AdvancedSearchGUI,
    AssignmentGUI,
    LibraryGUI,
    # Feature availability flags
    ADVANCED_SEARCH_GUI_AVAILABLE,
    ASSIGNMENT_SUBMISSION_GUI_AVAILABLE,
    DOCUMENT_MANAGER_GUI_AVAILABLE,
    GRADE_TRACKING_GUI_AVAILABLE,
    LIBRARY_GUI_AVAILABLE,
    PARENT_PORTAL_GUI_AVAILABLE,
    VIRTUAL_CLASSROOM_AVAILABLE,
    FINANCIAL_AID_AVAILABLE,
    COMMUNICATION_HUB_AVAILABLE,
    # Security feature flags
    SESSION_MANAGEMENT_AVAILABLE,
    COMPREHENSIVE_SECURITY_AVAILABLE,
    DATA_ENCRYPTION_AVAILABLE,
    SECURITY_DASHBOARD_AVAILABLE,
)
