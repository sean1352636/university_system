import logging
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
from typing import Any, Optional, List, Dict
from education_system.university_system.modules.shared.utils.i18n import get_text as _

gui_logger = logging.getLogger(__name__)

# Lazy imports to avoid circular dependencies
def _get_resource_management_dialog():
    from education_system.university_system.modules.domain.academics.gui.academic_calendar.dialogs_resources import ResourceManagementDialog
    return ResourceManagementDialog

def _get_course_management_dialog():
    from education_system.university_system.modules.domain.academics.gui.academic_calendar.dialogs_resources import CourseManagementDialog
    return CourseManagementDialog

def _get_notification_settings_dialog():
    from education_system.university_system.modules.domain.academics.gui.academic_calendar.dialogs_admin import NotificationSettingsDialog
    return NotificationSettingsDialog

def _get_event_categories_dialog():
    from education_system.university_system.modules.domain.academics.gui.academic_calendar.dialogs_categories import EventCategoriesDialog
    return EventCategoriesDialog

def _get_advanced_search_dialog():
    from education_system.university_system.modules.domain.academics.gui.academic_calendar.dialogs_search import AdvancedSearchDialog
    return AdvancedSearchDialog

def _get_recurring_event_dialog():
    from education_system.university_system.modules.domain.academics.gui.academic_calendar.dialogs_recurring import RecurringEventDialog
    return RecurringEventDialog

def _get_recurring_events_dialog():
    from education_system.university_system.modules.domain.academics.gui.academic_calendar.dialogs_recurring import RecurringEventsDialog
    return RecurringEventsDialog

def _get_system_maintenance_dialog():
    from education_system.university_system.modules.domain.academics.gui.academic_calendar.dialogs_admin import SystemMaintenanceDialog
    return SystemMaintenanceDialog

def _get_audit_logs_dialog():
    from education_system.university_system.modules.domain.academics.gui.academic_calendar.dialogs_admin import AuditLogsDialog
    return AuditLogsDialog

def _get_project_milestones_dialog():
    from education_system.university_system.modules.domain.academics.gui.academic_calendar.dialogs_reports import ProjectMilestonesDialog
    return ProjectMilestonesDialog

def _get_data_visualization_dialog():
    from education_system.university_system.modules.domain.academics.gui.academic_calendar.dialogs_reports import DataVisualizationDialog
    return DataVisualizationDialog

def _get_timezone_settings_dialog():
    from education_system.university_system.modules.domain.academics.gui.academic_calendar.dialogs_admin import TimezoneSettingsDialog
    return TimezoneSettingsDialog

def _get_reports_dialog():
    from education_system.university_system.modules.domain.academics.gui.academic_calendar.dialogs_reports import ReportsDialog
    return ReportsDialog

def _get_export_dialog():
    from education_system.university_system.modules.domain.academics.gui.academic_calendar.dialogs_misc import ExportDialog
    return ExportDialog

def _get_settings_dialog():
    from education_system.university_system.modules.domain.academics.gui.academic_calendar.dialogs_admin import SettingsDialog
    return SettingsDialog

def _get_import_calendar_dialog():
    from education_system.university_system.modules.domain.academics.gui.academic_calendar.dialogs_misc import ImportCalendarDialog
    return ImportCalendarDialog

def _get_calendar_sync_dialog():
    from education_system.university_system.modules.domain.academics.gui.academic_calendar.dialogs_misc import CalendarSyncDialog
    return CalendarSyncDialog

def _get_import_holidays_dialog():
    from education_system.university_system.modules.domain.academics.gui.academic_calendar.dialogs_misc import ImportHolidaysDialog
    return ImportHolidaysDialog

def _get_bulk_operations_dialog():
    from education_system.university_system.modules.domain.academics.gui.academic_calendar.dialogs_misc import BulkOperationsDialog
    return BulkOperationsDialog

def _get_help_dialog():
    from education_system.university_system.modules.domain.academics.gui.academic_calendar.dialogs_misc import HelpDialog
    return HelpDialog

def _get_about_dialog():
    from education_system.university_system.modules.domain.academics.gui.academic_calendar.dialogs_misc import AboutDialog
    return AboutDialog


class MenuActionsMixin:
    def _show_resource_management(self):
        """Show resource management dialog"""
        _get_resource_management_dialog()(self.root, self.calendar_manager, self._refresh_current_view)

    def _show_course_management(self):
        """Show course management dialog"""
        _get_course_management_dialog()(self.root, self.calendar_manager, self._refresh_current_view)

    def _show_notification_settings(self):
        """Show notification settings dialog"""
        _get_notification_settings_dialog()(self.root, self.calendar_manager, self.auth_manager, self._refresh_current_view)

    def _show_event_categories(self):
        """Show event categories dialog"""
        _get_event_categories_dialog()(self.root, self.calendar_manager, self._refresh_current_view)

    def _show_advanced_search(self):
        """Show advanced search dialog"""
        _get_advanced_search_dialog()(self.root, self.calendar_manager)

    def _show_create_recurring_event(self):
        """Show create recurring event dialog"""
        _get_recurring_event_dialog()(self.root, self.calendar_manager, self._refresh_current_view)

    def _show_system_backup(self):
        """Show system backup and maintenance options"""
        _get_system_maintenance_dialog()(self.root, self.calendar_manager, self.auth_manager)

    def _show_audit_logs(self):
        """Show audit logs dialog"""
        _get_audit_logs_dialog()(self.root, self.calendar_manager)

    def _show_project_milestones(self):
        """Show project milestones dialog"""
        _get_project_milestones_dialog()(self.root, self.calendar_manager, self._refresh_current_view)

    def _show_data_visualization(self):
        """Show data visualization dialog"""
        _get_data_visualization_dialog()(self.root, self.calendar_manager)

    def _show_timezone_settings(self):
        """Show timezone settings dialog"""
        _get_timezone_settings_dialog()(self.root, self.calendar_manager, self.auth_manager)

    def _show_recurring_events(self):
        """Show recurring events management"""
        _get_recurring_events_dialog()(self.root, self.calendar_manager, self._refresh_current_view)

    def _show_reports(self):
        """Show reports view"""
        _get_reports_dialog()(self.root, self.calendar_manager)

    def _show_export(self):
        """Show export dialog"""
        _get_export_dialog()(self.root, self.calendar_manager)

    def _show_settings(self):
        """Show settings dialog"""
        _get_settings_dialog()(self.root, self.calendar_manager, self.auth_manager)

    def _import_calendar(self):
        """Import calendar from file"""
        _get_import_calendar_dialog()(self.root, self.calendar_manager, self._refresh_current_view)

    def _backup_database(self):
        """Backup database"""
        try:
            result = self.calendar_manager.create_backup()
            if result['success']:
                self._show_success(result['message'])
            else:
                self._show_error(result['message'])
        except Exception as e:
            self._show_error(_("academic_calendar.messages.backup_failed").format(error=e))

    def _restore_database(self):
        """Restore database from backup"""
        backup_file = filedialog.askopenfilename(
            title=_("academic_calendar.messages.select_backup_file"),
            filetypes=[("Database files", "*.db"), ("All files", "*.*")]
        )

        if backup_file:
            if messagebox.askyesno(_("academic_calendar.messages.confirm_restore"),
                                 _("academic_calendar.messages.restore_warning")):
                try:
                    result = self.calendar_manager.restore_backup(backup_file)
                    if result['success']:
                        self._show_success(result['message'])
                        self._refresh_current_view()
                    else:
                        self._show_error(result['message'])
                except Exception as e:
                    self._show_error(_("academic_calendar.messages.restore_failed").format(error=e))

    def _calendar_sync(self):
        """Calendar sync dialog"""
        _get_calendar_sync_dialog()(self.root, self.calendar_manager, self._refresh_current_view)

    def _import_holidays(self):
        """Import holidays dialog"""
        _get_import_holidays_dialog()(self.root, self.calendar_manager, self._refresh_current_view)

    def _bulk_operations(self):
        """Bulk operations dialog"""
        _get_bulk_operations_dialog()(self.root, self.calendar_manager, self._refresh_current_view)

    def _launch_cli_mode(self):
        """Launch CLI mode for backward compatibility"""
        try:
            # Import needed modules
            from education_system.university_system.modules.domain.academics.services.academic_calendar.cli import (
                display_academic_calendar_menu, set_auth
            )

            # Hide GUI temporarily
            self.root.withdraw()

            # Set global auth for CLI mode
            set_auth(self.auth_manager)

            # Launch CLI in a new thread
            def run_cli():
                try:
                    display_academic_calendar_menu()
                except Exception as e:
                    gui_logger.error(f"CLI mode error: {e}")
                finally:
                    # Show GUI again
                    self.root.after(0, self.root.deiconify)

            cli_thread = threading.Thread(target=run_cli, daemon=True)
            cli_thread.start()

        except Exception as e:
            self._show_error(_("academic_calendar.messages.failed_to_launch_cli").format(error=e))
            self.root.deiconify()  # Make sure GUI is visible

    def _show_help(self):
        """Show help dialog"""
        _get_help_dialog()(self.root)

    def _show_about(self):
        """Show about dialog"""
        _get_about_dialog()(self.root)
