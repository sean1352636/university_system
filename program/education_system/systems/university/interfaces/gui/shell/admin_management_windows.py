"""Compatibility façade for the split implementation."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from . import admin_management_windows_shared as _shared
from .admin_management_windows_shared import *  # noqa: F401,F403

from .admin_management_windows_parts import apimanagementwindow as _part_1
ApiManagementWindow = _part_1.ApiManagementWindow
_shared.ApiManagementWindow = ApiManagementWindow
_shared.__all__.append("ApiManagementWindow") if "ApiManagementWindow" not in _shared.__all__ else None

from .admin_management_windows_parts import auditlogswindow as _part_2
AuditLogsWindow = _part_2.AuditLogsWindow
_shared.AuditLogsWindow = AuditLogsWindow
_shared.__all__.append("AuditLogsWindow") if "AuditLogsWindow" not in _shared.__all__ else None

from .admin_management_windows_parts import diagnosticswindow_init as _part_3_1
from .admin_management_windows_parts import diagnosticswindow_create_storage_tab as _part_3_2
class DiagnosticsWindow(_part_3_1.DiagnosticsWindow, _part_3_2.DiagnosticsWindow):
    """Comprehensive System Diagnostics"""
_shared.DiagnosticsWindow = DiagnosticsWindow
_shared.__all__.append("DiagnosticsWindow") if "DiagnosticsWindow" not in _shared.__all__ else None

from .admin_management_windows_parts import databasemaintenancewindow_init as _part_4_1
from .admin_management_windows_parts import databasemaintenancewindow_create_monitoring_tab as _part_4_2
class DatabaseMaintenanceWindow(_part_4_1.DatabaseMaintenanceWindow, _part_4_2.DatabaseMaintenanceWindow):
    """Comprehensive Database Maintenance Tools"""
_shared.DatabaseMaintenanceWindow = DatabaseMaintenanceWindow
_shared.__all__.append("DatabaseMaintenanceWindow") if "DatabaseMaintenanceWindow" not in _shared.__all__ else None

_exports = {name: globals()[name] for name in ['ApiManagementWindow', 'AuditLogsWindow', 'DatabaseMaintenanceWindow', 'DiagnosticsWindow']}
for _module in [_part_1, _part_2, _part_3_1, _part_3_2, _part_4_1, _part_4_2]:
    _module.__dict__.update(_exports)


# Keep extracted callables synchronized with compatibility-module globals.
for _module in [_part_1, _part_2, _part_3_1, _part_3_2, _part_4_1, _part_4_2]:
    _module.__dict__.update({name: value for name, value in globals().items() if not name.startswith("__")})

__all__ = ['ApiManagementWindow', 'AuditLogsWindow', 'DatabaseMaintenanceWindow', 'DiagnosticsWindow']

if __name__ == "__main__":
    root = tk.Tk()
    root.title(_t('gui.shell.admin_management_windows.windows.admin_management_demo', default="Admin Management Demo"))
    root.geometry("400x300")

    def open_api_management():
        ApiManagementWindow(root)

    def open_audit_logs():
        AuditLogsWindow(root)

    def open_diagnostics():
        DiagnosticsWindow(root)

    def open_database_maintenance():
        DatabaseMaintenanceWindow(root)

    ttk.Label(root, text=_t('gui.shell.admin_management_windows.labels.admin_management_windows_demo', default="Admin Management Windows Demo"),
             font=('Arial', 16, 'bold')).pack(pady=20)

    ttk.Button(root, text=_t('gui.shell.admin_management_windows.buttons.api_management', default="🔌 API Management"), command=open_api_management, width=30).pack(pady=10)
    ttk.Button(root, text=_t('gui.shell.admin_management_windows.buttons.audit_logs', default="📋 Audit Logs"), command=open_audit_logs, width=30).pack(pady=10)
    ttk.Button(root, text=_t('gui.shell.admin_management_windows.buttons.system_diagnostics', default="🔧 System Diagnostics"), command=open_diagnostics, width=30).pack(pady=10)
    ttk.Button(root, text=_t('gui.shell.admin_management_windows.buttons.database_maintenance', default="🗄️ Database Maintenance"), command=open_database_maintenance, width=30).pack(pady=10)

    root.mainloop()
