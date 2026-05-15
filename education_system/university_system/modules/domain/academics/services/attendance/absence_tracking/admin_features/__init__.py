"""Admin features for the Absence Tracker.

This package replaces the former monolithic ``admin_features.py`` module.
All public names previously importable from that module are re-exported here,
so existing imports across student_features, staff_features, and
absence_tracker continue to work unchanged.

Layout:
    context.py          AdminContext, audit, safe, shared logger
    support_tables.py   ensure_support_tables, install_soft_delete, settings
    ui_dialogs.py       Dialogs + pickers (Prompt, StudentPicker, ModulePicker, …)
    export_email.py     CSV export, _email_admin, report rendering
    services/           One module per service class (#1–#50)
    tab_builder.py      FeatureSpec, build_admin_tab, legacy feat_NN_* aliases
"""
from .context import AdminContext, audit, logger, safe
from .export_email import (
    _email_admin,
    _export_rows_to_csv,
    _report_window,
    _rows_to_pdf,
    _rows_to_txt,
)
from .services import (
    AdminServices,
    AttendanceDataService,
    BulkOperationsService,
    DiagnosticsService,
    IntegrationService,
    NotificationService,
    PolicyService,
    ReportingService,
    RequestWorkflowService,
    SecurityAuditService,
    _parents_of,
)
from .support_tables import (
    _get_setting,
    _set_setting,
    ensure_support_tables,
    install_soft_delete,
)
from .tab_builder import (
    FEATURES,
    FeatureSpec,
    _LEGACY_ALIASES,
    _build_feature_registry,
    _wrap,
    build_admin_tab,
)
from .ui_dialogs import (
    ModulePicker,
    Prompt,
    StudentPicker,
    _combo_dialog,
    _pick_module,
    _pick_student,
    _show_table,
    pick_date,
    pick_date_range,
)

# Expose the legacy feat_NN_* callables at module scope (mirrors the original
# admin_features.py footer: ``globals().update(_LEGACY_ALIASES)``).
globals().update(_LEGACY_ALIASES)

__all__ = [
    # Context
    "AdminContext", "audit", "safe", "logger",
    # Support tables / settings
    "ensure_support_tables", "install_soft_delete",
    "_get_setting", "_set_setting",
    # Dialogs / pickers
    "Prompt", "StudentPicker", "ModulePicker",
    "_combo_dialog", "_show_table", "pick_date", "pick_date_range",
    "_pick_student", "_pick_module",
    # Export / email / report rendering
    "_export_rows_to_csv", "_email_admin",
    "_rows_to_txt", "_rows_to_pdf", "_report_window",
    # Services
    "AttendanceDataService", "RequestWorkflowService", "PolicyService",
    "ReportingService", "NotificationService", "IntegrationService",
    "BulkOperationsService", "SecurityAuditService", "DiagnosticsService",
    "AdminServices", "_parents_of",
    # Tab builder + registry
    "FeatureSpec", "FEATURES", "_build_feature_registry",
    "build_admin_tab", "_wrap",
]
