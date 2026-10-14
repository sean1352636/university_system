
from education_system.systems.university.infrastructure.i18n import get_text as _t
import logging

from education_system.systems.university.domains.academics.interfaces.gui.course_management_gui.core._imports import (
    _, messagebox, tk, Toplevel, ScrolledText, Path, subprocess, sys,
    ACADEMIC_SYSTEMS_AVAILABLE, launch_degree_audit_gui,
    launch_course_evaluation_gui,
    CourseCreateDialog, BulkUpdateDialog, MaintenanceDialog,
    ImportExportDialog, ManageCourseStatusDialog, CourseHistoryDialog,
    AdvancedCourseSearchDialog, CourseAnalyticsDialog, CourseValidationDialog,
    CreateScheduleDialog, ViewSchedulesDialog, UpdateScheduleDialog,
    AddToWaitlistDialog, ViewWaitlistsDialog, ProcessWaitlistDialog,
    RemovePrerequisiteDialog, RecommendCoursesDialog, AlternativeCourseDialog,
    CourseCatalogGUI, COURSE_CATALOG_AVAILABLE,
    CourseForumsGUI, COURSE_FORUMS_AVAILABLE,
    CourseHealthDashboardGUI, COURSE_HEALTH_AVAILABLE,
    AIDetectorGUI, AI_DETECTOR_AVAILABLE,
    ScheduleConflictReportDialog,
    AuditLogViewerDialog,
    PrerequisiteChainDialog,
    EvaluationTemplatesViewerDialog,
)

logger = logging.getLogger(__name__)


from education_system.systems.university.domains.academics.interfaces.gui.course_management_gui import report_widgets as _report


class DialogsMixin:
    """Miscellaneous dialogs, launchers, and utility methods."""

    # --- Academic system launchers ---

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

    def show_course_catalog(self):
        """Launch the Course Catalog browser (Toplevel)."""
        if not COURSE_CATALOG_AVAILABLE:
            messagebox.showerror(_("common.error"),
                                 _("course_management.messages.catalog_not_available",
                                   default="Course Catalog is not available."))
            return
        try:
            CourseCatalogGUI(self.root, self.auth)
        except Exception as e:
            logger.exception("Failed to launch Course Catalog")
            messagebox.showerror(_("common.error"), f"Failed to launch Course Catalog: {e}")

    def show_course_forums(self):
        """Launch the Course / Module Discussion Forums (Toplevel)."""
        if not COURSE_FORUMS_AVAILABLE:
            messagebox.showerror(_("common.error"),
                                 _("course_management.messages.forums_not_available",
                                   default="Discussion Forums are not available."))
            return
        try:
            CourseForumsGUI(self.root, self.auth)
        except Exception as e:
            logger.exception("Failed to launch Course Forums")
            messagebox.showerror(_("common.error"), f"Failed to launch Discussion Forums: {e}")

    def show_course_health(self):
        """Launch the Course Health Dashboard (Toplevel)."""
        if not COURSE_HEALTH_AVAILABLE:
            messagebox.showerror(_("common.error"),
                                 _("course_management.messages.course_health_not_available",
                                   default="Course Health dashboard is not available."))
            return
        try:
            CourseHealthDashboardGUI(self.root, self.auth)
        except Exception as e:
            logger.exception("Failed to launch Course Health Dashboard")
            messagebox.showerror(_("common.error"), f"Failed to launch Course Health: {e}")

    def show_evaluation_templates(self):
        """Browse the bundled course-evaluation rubric templates."""
        try:
            EvaluationTemplatesViewerDialog(self.root, self.auth)
        except Exception as e:
            logger.exception("Failed to open Evaluation Templates Viewer")
            messagebox.showerror(_("common.error"),
                                 f"Failed to open Evaluation Templates: {e}")

    def show_prerequisite_chain(self):
        """Open the transitive prerequisite chain viewer."""
        try:
            PrerequisiteChainDialog(self.root, self.auth)
        except Exception as e:
            logger.exception("Failed to open Prerequisite Chain Viewer")
            messagebox.showerror(_("common.error"),
                                 f"Failed to open Prerequisite Chain Viewer: {e}")

    def show_audit_log_viewer(self):
        """Open the audit / activity log viewer."""
        try:
            AuditLogViewerDialog(self.root, self.auth)
        except Exception as e:
            logger.exception("Failed to open Audit Log Viewer")
            messagebox.showerror(_("common.error"),
                                 f"Failed to open Audit Log Viewer: {e}")

    def show_schedule_conflict_report(self):
        """Open the cross-course schedule conflict report."""
        try:
            ScheduleConflictReportDialog(self.root, self.auth)
        except Exception as e:
            logger.exception("Failed to open Schedule Conflict Report")
            messagebox.showerror(_("common.error"),
                                 f"Failed to open Schedule Conflict Report: {e}")

    def show_ai_integrity_alerts(self):
        """Launch the AI Detector / Academic Integrity Alerts dashboard."""
        if not AI_DETECTOR_AVAILABLE:
            messagebox.showerror(_("common.error"),
                                 _("course_management.messages.ai_detector_not_available",
                                   default="AI Integrity Alerts are not available."))
            return
        try:
            ai_window = Toplevel(self.root)
            AIDetectorGUI(ai_window, self.auth)
        except Exception as e:
            logger.exception("Failed to launch AI Integrity Alerts")
            messagebox.showerror(_("common.error"), f"Failed to launch AI Integrity Alerts: {e}")

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

    def show_export_pdf(self):
        """Export the course list to a printable PDF (file picker dialog)."""
        from education_system.systems.university.domains.academics.interfaces.gui.course_management_gui.import_export.import_export import export_pdf
        try:
            export_pdf(self)
        except Exception as e:
            logger.exception("PDF export failed")
            messagebox.showerror(_("common.error"), f"PDF export failed: {e}")

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
        from education_system.systems.university.domains.academics.interfaces.gui.course_management_gui.recommendations.recommendations_dialog import RecommendationsDialog
        dialog = RecommendationsDialog(self.root)
        if dialog.result:
            # Display recommendations in analytics tab (text surface)
            self.notebook.select(2)  # Analytics tab
            if hasattr(self, "show_analytics_text"):
                self.show_analytics_text()
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
        """About window — what this GUI actually contains today.

        The old text claimed "Enhanced Course Management System v2.0 …
        backwards compatible with original CLI version" and listed seven
        features, most of a much smaller program. It named none of the tabs
        that exist and was several major versions out of date.
        """
        # The package exposes no __version__ attribute; the installed
        # distribution metadata is the authoritative source.
        try:
            from importlib.metadata import version as _dist_version
            version = _dist_version("education-system")
        except Exception:
            version = "unknown"

        window, surface = _report.report_window(
            self.root, _("course_management.dialogs.about_system"), "720x620")

        _report.banner(surface, "Course Management",
                       f"Part of the University System · version {version}")

        _report.stat_strip(surface, [
            (len(self.notebook.tabs()) if hasattr(self, "notebook") else "—", "Tabs"),
            (self._about_course_count(), "Courses"),
            (self._about_module_count(), "Modules"),
        ])

        body = _report.card(surface, "What this window does", accent="#3498db")
        tk.Label(body,
                 text="Creates and maintains the course catalogue and the "
                      "curriculum built on it — sections, prerequisites, "
                      "materials, learning outcomes, approvals, timetabling "
                      "and rollover — and reports on enrolment across it.",
                 bg=_report.CARD, fg=_report.VALUE, font=(_report.FONT, 9),
                 wraplength=620, justify="left").pack(anchor="w")

        body = _report.card(surface, "Tabs", accent="#9b59b6")
        _report.kv_grid(body, [
            ("Course List", "Search, filter, create, edit and delete courses"),
            ("Course Details", "One course in full, with its modules"),
            ("Analytics", "Enrolment, department and capacity reporting"),
            ("Instructors", "Instructor records and course assignment"),
            ("Academic Systems", "Degree Audit and Course Evaluation"),
            ("Curriculum", "Sections, requisites, materials, outcomes, "
                           "approvals, timetable, rollover, cross-listing, "
                           "grading, waitlist rules, course-module links"),
            ("Course Planning", "Multi-year planning tools"),
        ], cols=1)

        body = _report.card(surface, "Related screens", accent="#16a34a")
        _report.kv_grid(body, [
            ("Assignments", "Assignment System (quizzes live here too)"),
            ("Marks", "Grade Tracking"),
            ("Discussion", "Module Discussion Forums"),
            ("Reading lists", "Library — textbooks added here appear there"),
        ], cols=1)

        tk.Label(surface, text="Python · Tkinter · SQLite",
                 bg=_report.BG, fg=_report.MUTED,
                 font=(_report.FONT, 8)).pack(anchor="w", padx=12, pady=(4, 10))
        window.lift()

    def _about_course_count(self):
        try:
            with self._ext_db() as conn:
                return conn.execute("SELECT COUNT(*) FROM courses").fetchone()[0]
        except Exception:
            return "—"

    def _about_module_count(self):
        try:
            with self._ext_db() as conn:
                return conn.execute("SELECT COUNT(*) FROM modules").fetchone()[0]
        except Exception:
            return "—"

    #: The user guide, as (section, accent, [(action, what it does), ...]).
    #: Held as data so it renders as cards rather than one block of text.
    _USER_GUIDE = [
        ("Courses", "#3498db", [
            ("Find a course", "Course List — type in Search, or narrow by "
                              "department and status."),
            ("See one course", "Double-click its row. Double-click the Name "
                               "column instead for enrolled students and modules."),
            ("Create or change", "Create Course, or select a row and use Edit / Delete."),
            ("Enrolment figures", "Counted live from student records, so they "
                                  "match the students popup."),
        ]),
        ("Curriculum", "#9b59b6", [
            ("Sections & requisites", "Set up teaching sections and prerequisite chains."),
            ("Materials", "Add reading and equipment. A Textbook, Reading or "
                          "Article is added to the Library and this course's "
                          "reading list automatically when you save it."),
            ("Learning outcomes", "Pick a CLO code and a Bloom's level, then "
                                  "map outcomes to programme standards."),
            ("Approvals & rollover", "Move a course through approval, then roll "
                                     "it into the next academic year."),
        ]),
        ("Analytics", "#16a34a", [
            ("Overview", "Headline counts and the status distribution."),
            ("Department analysis", "Pick a department for its totals, its "
                                    "most popular courses and anything under "
                                    "30% full."),
            ("Trends", "Most popular courses and where seats remain."),
            ("Reports", "Enrolment and department reports, savable as PDF, "
                        "CSV or TXT, or emailed to an administrator."),
        ]),
        ("Instructors", "#d97706", [
            ("Records", "Add and edit instructors on the Instructors tab."),
            ("Assign to a course", "Choose the instructor from the list. "
                                   "Assigning the same person to the same "
                                   "course and term twice is refused; taking "
                                   "over someone else's slot asks first."),
        ]),
        ("Academic systems", "#8e44ad", [
            ("Degree Audit", "Progress, prerequisites, what-if scenarios, "
                             "advising appointments and graduation audits."),
            ("Course Evaluation", "Build evaluations and read the results — "
                                  "double-click a question for its full "
                                  "answer distribution."),
        ]),
        ("Data", "#7f8c8d", [
            ("Import / Export", "CSV import and export from the File menu."),
            ("Backups", "Database backups and integrity checks under Maintenance."),
            ("Recalculate enrolment", "Maintenance — rewrites stored enrolment "
                                      "counters from the student records."),
        ]),
    ]

    def show_help(self):
        """User guide, as titled cards rather than one block of text."""
        window, surface = _report.report_window(
            self.root, _("course_management.dialogs.user_guide"), "780x660")

        _report.banner(surface, "User guide",
                       "How to do the common jobs in this window")

        for title, accent, entries in self._USER_GUIDE:
            body = _report.card(surface, title, accent=accent)
            _report.kv_grid(body, entries, cols=1)

        tk.Label(surface,
                 text="Tip: most tables open more detail on double-click.",
                 bg=_report.BG, fg=_report.MUTED, font=(_report.FONT, 8),
                 ).pack(anchor="w", padx=12, pady=(4, 10))
        window.lift()

    def return_to_main_menu(self):
        """Return to the main menu/GUI by closing this child window"""
        if messagebox.askyesno(_("course_management.messages.return_to_main_menu_confirm"), _("course_management.messages.return_to_main_menu_confirm")):
            try:
                self.root.destroy()
            except Exception as e:
                messagebox.showerror(_("common.error"), _("course_management.messages.failed_return_to_main", error=str(e)))
