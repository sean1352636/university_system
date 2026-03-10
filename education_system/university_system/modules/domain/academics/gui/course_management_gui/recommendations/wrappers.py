from ._imports import (
    messagebox, _, ORIGINAL_MODULE_AVAILABLE, initialize_enhanced_database,
)


class WrappersMixin:
    # =====================================================================
    # ENHANCED DATABASE INITIALIZATION
    # =====================================================================

    def initialize_enhanced_database_wrapper(self):
        """
        Wrapper for initialize_enhanced_database() from CLI module.
        This creates all advanced tables for course management.
        """
        try:
            if ORIGINAL_MODULE_AVAILABLE:
                success = initialize_enhanced_database()
                if success:
                    self.update_status("Enhanced database initialized successfully")
                    messagebox.showinfo(_("common.success"), "Enhanced database tables created successfully!")
                else:
                    self.update_status("Database initialization failed", error=True)
                    messagebox.showerror(_("common.error"), "Failed to initialize enhanced database")
            else:
                # Use fallback
                self.init_fallback_database()
                self.update_status("Database initialized with fallback")
        except Exception as e:
            self.update_status(f"Initialization error: {e}", error=True)
            messagebox.showerror(_("common.error"), f"Database initialization failed: {e}")

    # =====================================================================
    # CORE COURSE MANAGEMENT WRAPPERS
    # =====================================================================

    def create_enhanced_course_wrapper(self):
        """
        Wrapper that opens the enhanced course creation dialog.
        Calls the existing show_create_course() method.
        """
        self.show_create_course()

    def create_course_wrapper(self):
        """
        Basic course creation wrapper (same as enhanced for GUI).
        Calls the existing show_create_course() method.
        """
        self.show_create_course()

    def view_all_courses_wrapper(self):
        """
        Display all courses in the main list.
        Refreshes the course list and switches to the first tab.
        """
        self.refresh_course_list()
        self.notebook.select(0)  # Switch to course list tab
        self.update_status("Course list refreshed")

    def update_course_wrapper(self):
        """
        Update the selected course.
        Calls the existing edit_selected_course() method.
        """
        self.edit_selected_course()

    def delete_course_wrapper(self):
        """
        Delete the selected course.
        Calls the existing delete_selected_course() method.
        """
        self.delete_selected_course()

    def view_course_details_wrapper(self):
        """
        View detailed information about the selected course.
        Switches to the course details tab.
        """
        selected = self.course_tree.selection()
        if not selected:
            messagebox.showwarning(_("course_management.messages.no_selection"), "Please select a course to view details.")
            return

        # Switch to details tab
        self.notebook.select(1)
        self.show_course_details()
        self.update_status("Viewing course details")

    # =====================================================================
    # INSTRUCTOR MANAGEMENT WRAPPERS
    # =====================================================================

    def create_instructor_wrapper(self):
        """
        Create a new instructor profile.
        Calls the existing show_add_instructor() method.
        """
        self.show_add_instructor()

    def view_instructors_wrapper(self):
        """
        View all instructors in the system.
        Refreshes the instructor list and switches to instructors tab.
        """
        self.refresh_instructor_list()
        # Find and select the instructors tab (usually tab 3)
        for i in range(self.notebook.index('end')):
            if 'Instructor' in self.notebook.tab(i, 'text'):
                self.notebook.select(i)
                break
        self.update_status("Instructor list refreshed")

    def assign_instructor_to_course_wrapper(self):
        """
        Assign an instructor to a course.
        Calls the existing show_assign_instructor() method.
        """
        self.show_assign_instructor()

    # =====================================================================
    # WRAPPER FUNCTIONS FOR EXISTING FEATURES
    # =====================================================================

    def search_courses_wrapper(self):
        """Search courses with filters. Calls existing show_search_dialog()."""
        self.show_search_dialog()

    def import_courses_from_csv_wrapper(self):
        """Import courses from CSV file. Calls existing import_csv()."""
        self.import_csv()

    def export_courses_to_csv_wrapper(self):
        """Export courses to CSV file. Calls existing export_csv()."""
        self.export_csv()

    def generate_course_analytics_wrapper(self):
        """Generate course analytics. Calls existing generate_analytics()."""
        self.generate_analytics()

    def generate_enrollment_report_wrapper(self):
        """Generate enrollment report. Calls existing show_enrollment_report()."""
        self.show_enrollment_report()

    def department_statistics_wrapper(self):
        """Generate department statistics. Calls existing show_department_stats()."""
        self.show_department_stats()

    def recommend_courses_wrapper(self):
        """Recommend courses to student. Calls existing show_recommendations()."""
        self.show_recommendations()

    def find_alternative_courses_wrapper(self):
        """Find alternative courses. Calls existing find_alternative_courses()."""
        self.find_alternative_courses()

    def bulk_update_courses_wrapper(self):
        """Bulk update multiple courses. Calls existing show_bulk_update()."""
        self.show_bulk_update()

    def system_maintenance_wrapper(self):
        """System maintenance operations. Calls existing show_maintenance()."""
        self.show_maintenance()
