"""Admin tools GUI package — split from the former admin_tools_gui.py module.

Public API is preserved: every ``show_*`` function that used to be importable
from ``...admin.admin_tools_gui`` is re-exported here so existing call sites
(e.g. ``main_gui.py``) continue to work unchanged.
"""

from .monitoring import (
    show_system_monitoring_dashboard,
    show_query_analyser,
    show_capacity_planning,
)
from .configuration import show_configuration_editor
from .reports import (
    show_usage_adoption_reports,
    show_custom_report_builder,
)
from .api_integrations import (
    show_api_documentation,
    show_integration_status_dashboard,
)
from .notifications import show_notification_template_manager
from .retention import (
    show_data_retention_manager,
    show_system_changelog,
)
from .governance import (
    show_department_isolation,
    show_license_management,
    show_disaster_recovery_plan,
)

__all__ = [
    "show_system_monitoring_dashboard",
    "show_configuration_editor",
    "show_query_analyser",
    "show_capacity_planning",
    "show_usage_adoption_reports",
    "show_custom_report_builder",
    "show_api_documentation",
    "show_notification_template_manager",
    "show_data_retention_manager",
    "show_system_changelog",
    "show_department_isolation",
    "show_integration_status_dashboard",
    "show_license_management",
    "show_disaster_recovery_plan",
]
