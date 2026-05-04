"""Operations Console — unified entry point for the four "Monitoring &
Logs" buttons plus the standalone Log Analyzer.

Single Toplevel + Notebook hosting:
  - Activity Log       (infrastructure/logging/gui/log_management_gui)
  - Audit Viewer       (modules/shared/gui/security/audit_log_viewer_gui)
  - Activity Logger    (modules/shared/gui/simple_activity_logger_gui)
  - Log Analyzer       (formerly shared/extras/log-analyzer)
  - System Monitoring  (formerly inline in admin_tools_gui)

Existing GUIs are reused, not rewritten — adapters here just embed
each one inside a tab.
"""

from education_system.university_system.modules.shared.gui.operations_console.console import (
    OperationsConsole,
    open_operations_console,
)

__all__ = ["OperationsConsole", "open_operations_console"]
