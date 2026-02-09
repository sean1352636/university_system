"""Dialog wrappers for the enhanced reporting GUI.

This package contains functional wrappers around the various dialog
methods defined on the GUI class as well as standalone dialog
functions.  Each wrapper accepts a GUI instance and delegates to the
corresponding method, allowing dialogs to be invoked without
explicitly referencing the underlying class.
"""

from .settings_dialogs import (
    show_backup_restore_dialog,
    show_user_management_dialog,
    show_directory_settings,
    show_theme_settings,
    show_settings,
    show_advanced_settings,
    show_email_settings_dialog,
    show_system_config_editor,
    validate_email_settings,
)
from .advanced_dialogs import (
    show_advanced_template_creation_dialog,
    show_enhanced_scheduling_dialog,
    show_template_comparison_dialog,
    show_template_versioning_dialog,
    show_bulk_operations_dialog,
    show_data_quality_dialog,
    show_predictive_analytics_dialog,
    show_anomaly_detection_dialog,
    show_correlation_analysis_dialog,
)
from .visualization_dialogs import (
    show_data_visualization_studio,
    show_report_analytics_dashboard,
    show_api_endpoints_documentation,
    show_system_logs_viewer,
    show_data_import_export_dialog,
    show_cache_management_dialog,
    start_api_server,
    start_api_server_gui,
    show_performance_monitor,
    show_data_quality_dashboard,
)
from .template_wizard import (
    show_template_wizard,
    show_wizard_step,
    show_wizard_step_1,
    wizard_next_step,
    wizard_prev_step,
    wizard_finish,
)

__all__ = [
    # settings dialogs
    "show_backup_restore_dialog",
    "show_user_management_dialog",
    "show_directory_settings",
    "show_theme_settings",
    "show_settings",
    "show_advanced_settings",
    "show_email_settings_dialog",
    "show_system_config_editor",
    "validate_email_settings",
    # advanced dialogs
    "show_advanced_template_creation_dialog",
    "show_enhanced_scheduling_dialog",
    "show_template_comparison_dialog",
    "show_template_versioning_dialog",
    "show_bulk_operations_dialog",
    "show_data_quality_dialog",
    "show_predictive_analytics_dialog",
    "show_anomaly_detection_dialog",
    "show_correlation_analysis_dialog",
    # visualization dialogs
    "show_data_visualization_studio",
    "show_report_analytics_dashboard",
    "show_api_endpoints_documentation",
    "show_system_logs_viewer",
    "show_data_import_export_dialog",
    "show_cache_management_dialog",
    "start_api_server",
    "start_api_server_gui",
    "show_performance_monitor",
    "show_data_quality_dashboard",
    # template wizard
    "show_template_wizard",
    "show_wizard_step",
    "show_wizard_step_1",
    "wizard_next_step",
    "wizard_prev_step",
    "wizard_finish",
]