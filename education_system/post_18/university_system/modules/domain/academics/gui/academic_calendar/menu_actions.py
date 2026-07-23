import logging
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
from typing import Any, Optional, List, Dict
from education_system.post_18.university_system.core.i18n import get_text as _
from education_system.post_18.university_system.modules.domain.academics.gui.academic_calendar.utils import safe_grab_set

gui_logger = logging.getLogger(__name__)

# Lazy imports to avoid circular dependencies
def _get_resource_management_dialog():
    from education_system.post_18.university_system.modules.domain.academics.gui.academic_calendar.dialogs_resources import ResourceManagementDialog
    return ResourceManagementDialog

def _get_course_management_dialog():
    from education_system.post_18.university_system.modules.domain.academics.gui.academic_calendar.dialogs_resources import CourseManagementDialog
    return CourseManagementDialog

def _get_notification_settings_dialog():
    from education_system.post_18.university_system.modules.domain.academics.gui.academic_calendar.dialogs_admin import NotificationSettingsDialog
    return NotificationSettingsDialog

def _get_event_categories_dialog():
    from education_system.post_18.university_system.modules.domain.academics.gui.academic_calendar.dialogs_categories import EventCategoriesDialog
    return EventCategoriesDialog

def _get_advanced_search_dialog():
    from education_system.post_18.university_system.modules.domain.academics.gui.academic_calendar.dialogs_search import AdvancedSearchDialog
    return AdvancedSearchDialog

def _get_recurring_event_dialog():
    from education_system.post_18.university_system.modules.domain.academics.gui.academic_calendar.dialogs_recurring import RecurringEventDialog
    return RecurringEventDialog

def _get_recurring_events_dialog():
    from education_system.post_18.university_system.modules.domain.academics.gui.academic_calendar.dialogs_recurring import RecurringEventsDialog
    return RecurringEventsDialog

def _get_system_maintenance_dialog():
    from education_system.post_18.university_system.modules.domain.academics.gui.academic_calendar.dialogs_admin import SystemMaintenanceDialog
    return SystemMaintenanceDialog

def _get_audit_logs_dialog():
    from education_system.post_18.university_system.modules.domain.academics.gui.academic_calendar.dialogs_admin import AuditLogsDialog
    return AuditLogsDialog

def _get_project_milestones_dialog():
    from education_system.post_18.university_system.modules.domain.academics.gui.academic_calendar.dialogs_reports import ProjectMilestonesDialog
    return ProjectMilestonesDialog

def _get_data_visualization_dialog():
    from education_system.post_18.university_system.modules.domain.academics.gui.academic_calendar.dialogs_reports import DataVisualizationDialog
    return DataVisualizationDialog

def _get_timezone_settings_dialog():
    from education_system.post_18.university_system.modules.domain.academics.gui.academic_calendar.dialogs_admin import TimezoneSettingsDialog
    return TimezoneSettingsDialog

def _get_reports_dialog():
    from education_system.post_18.university_system.modules.domain.academics.gui.academic_calendar.dialogs_reports import ReportsDialog
    return ReportsDialog

def _get_export_dialog():
    from education_system.post_18.university_system.modules.domain.academics.gui.academic_calendar.dialogs_misc import ExportDialog
    return ExportDialog

def _get_settings_dialog():
    from education_system.post_18.university_system.modules.domain.academics.gui.academic_calendar.dialogs_admin import SettingsDialog
    return SettingsDialog

def _get_import_calendar_dialog():
    from education_system.post_18.university_system.modules.domain.academics.gui.academic_calendar.dialogs_misc import ImportCalendarDialog
    return ImportCalendarDialog

def _get_calendar_sync_dialog():
    from education_system.post_18.university_system.modules.domain.academics.gui.academic_calendar.dialogs_misc import CalendarSyncDialog
    return CalendarSyncDialog

def _get_import_holidays_dialog():
    from education_system.post_18.university_system.modules.domain.academics.gui.academic_calendar.dialogs_misc import ImportHolidaysDialog
    return ImportHolidaysDialog

def _get_bulk_operations_dialog():
    from education_system.post_18.university_system.modules.domain.academics.gui.academic_calendar.dialogs_misc import BulkOperationsDialog
    return BulkOperationsDialog

def _get_help_dialog():
    from education_system.post_18.university_system.modules.domain.academics.gui.academic_calendar.dialogs_misc import HelpDialog
    return HelpDialog

def _get_about_dialog():
    from education_system.post_18.university_system.modules.domain.academics.gui.academic_calendar.dialogs_misc import AboutDialog
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
            from education_system.post_18.university_system.modules.domain.academics.services.academic_calendar.cli import (
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

    def _open_trip_manager(self):
        """Open the trip management GUI in a child window"""
        try:
            from education_system.post_18.university_system.modules.domain.campus.mobility.gui.trip_management_gui import TripManagementGUI
            trip_window = tk.Toplevel(self.root)
            trip_window.title(_("academic_calendar.trips.manager_title", default="Trip Management"))
            trip_window.geometry("1200x800")
            trip_window.transient(self.root)
            TripManagementGUI(auth_instance=self.auth_manager, root=trip_window)
        except ImportError:
            self._show_error(_("academic_calendar.trips.not_available",
                              default="Trip management module is not available."))
        except Exception as e:
            self._show_error(_("academic_calendar.trips.open_error",
                              default="Error opening trip manager: {error}").format(error=e))

    def _create_trip_calendar_event(self):
        """Create a calendar event for a trip"""
        try:
            from education_system.post_18.university_system.modules.domain.campus.mobility.gui.trip_management_gui.calendar_dialogs import CreateCalendarEventDialog
            CreateCalendarEventDialog(
                self.root, self.auth_manager, self.calendar_manager, self._refresh_current_view)
        except ImportError:
            self._show_error(_("academic_calendar.trips.not_available",
                              default="Trip management module is not available."))
        except Exception as e:
            self._show_error(_("academic_calendar.trips.calendar_event_error",
                              default="Error creating trip calendar event: {error}").format(error=e))

    def _view_trip_calendar_links(self):
        """View existing trip-calendar event links in a dialog"""
        try:
            from education_system.post_18.university_system.modules.domain.campus.mobility.gui.trip_management_gui._imports import safe_db_operation

            def get_links(conn):
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT t.trip_name, t.destination, t.start_date, t.end_date,
                           e.name as event_name, e.event_type, e.date_added as created_at
                    FROM academic_calendar_events e
                    JOIN trips t ON e.trip_id = t.id
                    WHERE e.trip_id IS NOT NULL
                    ORDER BY t.start_date
                ''')
                return cursor.fetchall()

            links = safe_db_operation(get_links)

            dialog = tk.Toplevel(self.root)
            dialog.title(_("academic_calendar.trips.links_title", default="Trip-Calendar Links"))
            dialog.geometry("800x400")
            dialog.transient(self.root)
            safe_grab_set(dialog, self.root)

            tree = ttk.Treeview(dialog,
                                columns=('trip', 'destination', 'dates', 'event', 'type', 'created'),
                                show='headings', height=15)
            tree.heading('trip', text=_("academic_calendar.trips.col_trip", default="Trip"))
            tree.heading('destination', text=_("academic_calendar.trips.col_destination", default="Destination"))
            tree.heading('dates', text=_("academic_calendar.trips.col_dates", default="Dates"))
            tree.heading('event', text=_("academic_calendar.trips.col_event", default="Calendar Event"))
            tree.heading('type', text=_("academic_calendar.trips.col_type", default="Type"))
            tree.heading('created', text=_("academic_calendar.trips.col_created", default="Created"))

            tree.column('trip', width=150)
            tree.column('destination', width=100)
            tree.column('dates', width=150)
            tree.column('event', width=150)
            tree.column('type', width=80)
            tree.column('created', width=100)

            scrollbar = ttk.Scrollbar(dialog, orient="vertical", command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)

            tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0), pady=10)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 10), pady=10)

            if links:
                for link in links:
                    trip_name, dest, start, end, event_name, event_type, created = link
                    tree.insert('', tk.END, values=(
                        trip_name, dest, f"{start} - {end}",
                        event_name, event_type, created[:10] if created else ''))
            else:
                tree.insert('', tk.END, values=(
                    _("academic_calendar.trips.no_links", default="No trip-calendar links found"),
                    '', '', '', '', ''))

            ttk.Button(dialog, text=_("common.close", default="Close"),
                       command=dialog.destroy).pack(pady=(0, 10))

        except ImportError:
            self._show_error(_("academic_calendar.trips.not_available",
                              default="Trip management module is not available."))
        except Exception as e:
            self._show_error(_("academic_calendar.trips.links_error",
                              default="Error viewing trip-calendar links: {error}").format(error=e))

    def _show_help(self):
        """Show help dialog"""
        _get_help_dialog()(self.root)

    def _show_about(self):
        """Show about dialog"""
        _get_about_dialog()(self.root)
