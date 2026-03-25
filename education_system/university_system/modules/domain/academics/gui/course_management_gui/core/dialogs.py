import logging

from education_system.university_system.modules.domain.academics.gui.course_management_gui.core._imports import (
    _, messagebox, tk, Toplevel, ScrolledText, Path, subprocess, sys,
    ACADEMIC_SYSTEMS_AVAILABLE, launch_degree_audit_gui,
    launch_course_evaluation_gui,
    CourseCreateDialog, BulkUpdateDialog, MaintenanceDialog,
    ImportExportDialog, ManageCourseStatusDialog, CourseHistoryDialog,
    AdvancedCourseSearchDialog, CourseAnalyticsDialog, CourseValidationDialog,
    CreateScheduleDialog, ViewSchedulesDialog, UpdateScheduleDialog,
    AddToWaitlistDialog, ViewWaitlistsDialog, ProcessWaitlistDialog,
    RemovePrerequisiteDialog, RecommendCoursesDialog, AlternativeCourseDialog,
)

logger = logging.getLogger(__name__)


class DialogsMixin:
    """Miscellaneous dialogs, launchers, and utility methods."""

    # --- Academic system launchers ---

    def show_lms_gui(self):
        """Switch to the LMS tab in the course management notebook."""
        try:
            for i in range(self.notebook.index("end")):
                if self.notebook.tab(i, "text") == _("lms.title"):
                    self.notebook.select(i)
                    return
            messagebox.showinfo("LMS", "LMS tab is available in the Course Management tabs above.")
        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to open LMS tab: {e}")

    def show_degree_audit_gui(self):
        """Launch the Degree Audit GUI"""
        try:
            if ACADEMIC_SYSTEMS_AVAILABLE:
                launch_degree_audit_gui(self.root, self.auth)
            else:
                messagebox.showerror(_("common.error"), _("course_management.messages.degree_audit_not_available"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("course_management.messages.degree_audit_launch_failed").format(error=e))

    def show_course_evaluation_gui(self):
        """Launch the Course Evaluation GUI"""
        try:
            if ACADEMIC_SYSTEMS_AVAILABLE:
                launch_course_evaluation_gui(self.root, self.auth)
            else:
                messagebox.showerror(_("common.error"), _("course_management.messages.course_evaluation_not_available"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("course_management.messages.course_evaluation_launch_failed").format(error=e))

    # --- Quick menu shortcuts ---

    def show_update_schedule(self):
        """Show update schedule dialog"""
        UpdateScheduleDialog(self.root, self.auth)

    def show_process_waitlist(self):
        """Show process waitlist dialog"""
        ProcessWaitlistDialog(self.root, self.auth)

    def show_remove_prerequisite(self):
        """Show remove prerequisite dialog"""
        dialog = RemovePrerequisiteDialog(self.root, self.auth)
        if dialog.result:
            self.update_status(_("course_management.status.prerequisite_removed"))

    def show_manage_status(self):
        """Show manage course status dialog"""
        dialog = ManageCourseStatusDialog(self.root, self.auth)
        if dialog.result:
            self.refresh_course_list()
            self.update_status(_("course_management.status.course_status_updated"))

    def show_import_csv(self):
        """Show import CSV dialog"""
        dialog = ImportExportDialog(self.root, self.auth, "import")
        if dialog.result:
            self.refresh_course_list()
            self.update_status(_("course_management.status.courses_imported"))

    def show_export_csv(self):
        """Show export CSV dialog"""
        dialog = ImportExportDialog(self.root, self.auth, "export")
        if dialog.result:
            self.update_status(_("course_management.status.courses_exported"))

    def show_recommend_courses(self):
        """Show course recommendations dialog"""
        RecommendCoursesDialog(self.root, self.auth)

    def show_course_history(self):
        """Show course history dialog"""
        CourseHistoryDialog(self.root, self.auth)

    def find_alternative_courses(self):
        """Show find alternative courses dialog"""
        AlternativeCourseDialog(self.root, self.auth)

    def show_system_maintenance(self):
        """Show system maintenance dialog (already exists as MaintenanceDialog)"""
        dialog = MaintenanceDialog(self.root, self.auth)
        if dialog.result:
            self.update_status(_("course_management.status.maintenance_completed"))

    def show_analytics(self):
        """
        Entry point for the 'Course Analytics' menu item - redirects to detailed analytics.
        """
        # Use the existing detailed analytics function
        self.show_course_analytics_detailed()

    def show_create_schedule(self):
        """Open dialog to create a new course schedule entry"""
        CreateScheduleDialog(self.root, self.auth)

    def show_view_schedules(self):
        """Open dialog to view all schedules"""
        ViewSchedulesDialog(self.root, self.auth)

    def show_add_waitlist(self):
        """Open dialog to add a student to a course waitlist"""
        AddToWaitlistDialog(self.root, self.auth)

    def show_view_waitlists(self):
        """Open dialog to view course waitlists"""
        ViewWaitlistsDialog(self.root, self.auth)

    def show_create_course(self):
        """Show create course dialog"""
        dialog = CourseCreateDialog(self.root, self.auth)
        if dialog.result:
            self.refresh_course_list()
            self.update_status(_("course_management.status.course_created").format(course=dialog.result))

    # --- Bulk / maintenance / recommendations ---

    def show_bulk_update(self):
        """Show bulk update dialog"""
        dialog = BulkUpdateDialog(self.root, self.auth)
        if dialog.result:
            self.refresh_course_list()
            self.update_status(_("course_management.status.bulk_update_completed"))

    def show_maintenance(self):
        """Show system maintenance dialog"""
        dialog = MaintenanceDialog(self.root, self.auth)
        if dialog.result:
            self.update_status(_("course_management.status.maintenance_completed"))

    def show_recommendations(self):
        """Show course recommendations"""
        dialog = RecommendationsDialog(self.root)
        if dialog.result:
            # Display recommendations in analytics tab
            self.notebook.select(2)  # Analytics tab
            self.analytics_text.delete(1.0, tk.END)
            self.analytics_text.insert(1.0, dialog.result)

    # --- Dialogs ---

    def show_advanced_search(self):
        """Show advanced search dialog"""
        AdvancedCourseSearchDialog(self.root, self.auth)

    def show_course_analytics_detailed(self):
        """Show detailed analytics dialog"""
        CourseAnalyticsDialog(self.root, self.auth)

    def show_data_validation(self):
        """Show data validation dialog"""
        CourseValidationDialog(self.root, self.auth)

    def sort_treeview(self, col):
        """Sort treeview by column"""
        data = [(self.course_tree.set(child, col), child) for child in self.course_tree.get_children('')]

        # Determine if we're sorting numbers or text
        try:
            # Try to convert to float for numeric sorting
            data.sort(key=lambda x: float(x[0]) if x[0].replace('.', '').replace('/', '').isdigit() else float('inf'))
        except Exception:
            # Fall back to string sorting
            data.sort(key=lambda x: x[0].lower())

        # Rearrange items in sorted positions
        for ix, item in enumerate(data):
            self.course_tree.move(item[1], '', ix)

    def show_about(self):
        """Show about dialog"""
        about_text = """Enhanced Course Management System v2.0

A comprehensive GUI-based course management system with:
\u2022 Course creation and management
\u2022 Advanced search and filtering
\u2022 Analytics and reporting
\u2022 Instructor management
\u2022 Prerequisites handling
\u2022 Import/Export capabilities
\u2022 System maintenance tools

Developed with Python and Tkinter
Backwards compatible with original CLI version"""

        messagebox.showinfo(_("course_management.dialogs.about_system"), about_text, parent=self.root)

    def show_help(self):
        """Show help dialog"""
        help_text = """USER GUIDE

COURSE MANAGEMENT:
\u2022 Use the Course List tab to view and manage courses
\u2022 Double-click a course to view details
\u2022 Use search and filters to find specific courses
\u2022 Create new courses using the Create Course button

ANALYTICS:
\u2022 View system-wide analytics in the Analytics tab
\u2022 Generate various reports from the Analytics menu
\u2022 Export data for external analysis

INSTRUCTORS:
\u2022 Manage instructors in the Instructors tab
\u2022 Assign instructors to courses
\u2022 View instructor workloads

IMPORT/EXPORT:
\u2022 Import courses from CSV files (File menu)
\u2022 Export course data to CSV
\u2022 Create database backups

For more information, consult the documentation."""

        # Create help window
        help_window = tk.Toplevel(self.root)
        help_window.title(_("course_management.dialogs.user_guide"))
        help_window.geometry("600x400")

        help_text_widget = ScrolledText(help_window, wrap=tk.WORD)
        help_text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        help_text_widget.insert(1.0, help_text)
        help_text_widget.config(state=tk.DISABLED)

    def return_to_main_menu(self):
        """Return to the main menu/GUI by closing this child window"""
        if messagebox.askyesno(_("course_management.messages.return_to_main_menu_confirm"), _("course_management.messages.return_to_main_menu_confirm")):
            try:
                self.root.destroy()
            except Exception as e:
                messagebox.showerror(_("common.error"), _("course_management.messages.failed_return_to_main", error=str(e)))
