"""Student Analytics GUI package - composed from mixin modules."""
from education_system.post_18.university_system.modules.shared.gui.student_analytics_gui.student_analytics_gui import GUIStudentAnalytics
from education_system.post_18.university_system.modules.shared.gui.student_analytics_gui.dialogs import FilterDialog, CustomReportDialog, ConfigDialog
from education_system.post_18.university_system.modules.shared.gui.student_analytics_gui._imports import CONFIG, configure_matplotlib, StudentAnalytics, pd, json, datetime

__all__ = [
    'GUIStudentAnalytics',
    'FilterDialog',
    'CustomReportDialog',
    'ConfigDialog',
    'launch_gui',
    'main',
    'get_gui_analytics_class',
    'integrate_with_main_system',
    'CONFIG',
]


# Extension to original StudentAnalytics class
def add_gui_methods():
    """Add GUI-compatible methods to the original StudentAnalytics class"""

    def return_to_main_menu(self):
        """Return to the main menu"""
        try:
            # Use the gui_launcher utility to avoid circular imports
            from education_system.post_18.university_system.modules.shared.gui.gui_launcher import return_to_main_menu as _return
            _return(self, self.auth)
        except Exception as e:
            print(f"Error returning to main menu: {e}")
            import traceback
            traceback.print_exc()

    def export_data_choice(self, choice):
        """Handle export data choice for GUI"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        students_df = self.get_all_students(self.custom_filters)
        modules_df = self.get_all_modules(self.custom_filters)

        if choice == '1':
            # Excel export
            filename = f"{self.reports_dir}/student_data_export_{timestamp}.xlsx"

            with pd.ExcelWriter(filename, engine='openpyxl') as writer:
                students_df.to_excel(writer, sheet_name='Students', index=False)

                if not modules_df.empty:
                    modules_df.to_excel(writer, sheet_name='Modules', index=False)

                # Summary statistics
                summary_data = {
                    'Metric': ['Total Students', 'Average GPA', 'Average Engagement', 'Completion Rate'],
                    'Value': [
                        len(students_df),
                        students_df['gpa'].mean(),
                        students_df['engagement_score'].mean(),
                        (students_df['completion_status'] == 'Completed').mean() * 100
                    ]
                }
                pd.DataFrame(summary_data).to_excel(writer, sheet_name='Summary', index=False)

            print(f"Excel export completed: {filename}")

        elif choice == '2':
            # CSV export
            students_filename = f"{self.reports_dir}/students_{timestamp}.csv"
            students_df.to_csv(students_filename, index=False)
            print(f"Students CSV exported: {students_filename}")

            if not modules_df.empty:
                modules_filename = f"{self.reports_dir}/modules_{timestamp}.csv"
                modules_df.to_csv(modules_filename, index=False)
                print(f"Modules CSV exported: {modules_filename}")

        elif choice == '3':
            # JSON export
            filename = f"{self.reports_dir}/student_data_{timestamp}.json"
            export_data = {
                'students': students_df.to_dict('records'),
                'modules': modules_df.to_dict('records') if not modules_df.empty else [],
                'export_metadata': {
                    'timestamp': timestamp,
                    'total_students': len(students_df),
                    'total_modules': len(modules_df)
                }
            }

            with open(filename, 'w') as f:
                json.dump(export_data, f, indent=2, default=str)

            print(f"JSON export completed: {filename}")

        elif choice == '4':
            # Statistical summary
            self.generate_statistical_summary_report(students_df, modules_df, timestamp)

    # Add the method to the class
    StudentAnalytics.export_data_choice = export_data_choice


def launch_gui(auth_manager=None):
    """Launch the GUI version of Student Analytics with optional auth"""
    print("Launching Enhanced Student Analytics GUI...")

    # Create and run GUI with auth context
    app = GUIStudentAnalytics(auth_manager)
    app.run()


# Apply GUI method patches at import time so every entry path
# (`launch_gui`, `integrate_with_main_system`, direct `GUIStudentAnalytics(...)`
# from elsewhere) ends up with `export_data_choice` available on the
# `StudentAnalytics` instance the runners call into. Previously it was only
# applied inside `launch_gui()` and any other path raised
# `AttributeError: 'StudentAnalytics' object has no attribute 'export_data_choice'`.
add_gui_methods()


def main():
    """Main function with backward compatibility"""
    import sys

    # Check if GUI mode is requested
    if len(sys.argv) > 1 and sys.argv[1] in ['--gui', '-g', 'gui']:
        launch_gui()
    else:
        # Run original command-line interface
        analytics = StudentAnalytics()
        analytics.display_main_menu()


def get_gui_analytics_class():
    """Return the GUIStudentAnalytics class for integration"""
    return GUIStudentAnalytics


def integrate_with_main_system(main_gui_instance, auth_manager):
    """Integrate analytics with main GUI system"""
    try:
        # Create analytics instance
        analytics_gui = GUIStudentAnalytics()

        # Set auth context
        if hasattr(analytics_gui, 'auth'):
            analytics_gui.auth = auth_manager

        return analytics_gui
    except Exception as e:
        print(f"Failed to integrate analytics: {e}")
        return None


# Entry point with backward compatibility
if __name__ == "__main__":
    # Check if GUI libraries are available
    try:
        import tkinter
        gui_available = True
    except ImportError:
        gui_available = False
        print("GUI libraries not available. Running in command-line mode.")

    # Ask user for interface preference if GUI is available
    if gui_available:
        print("\nEnhanced Student Analytics Dashboard")
        print("=====================================")
        print("Choose interface:")
        print("1. GUI Mode (Recommended)")
        print("2. Command Line Mode (Classic)")

        choice = input("\nSelect interface (1 or 2, or press Enter for GUI): ").strip()

        if choice == '2':
            # Run command-line version
            analytics = StudentAnalytics()
            analytics.display_main_menu()
        else:
            # Run GUI version (default) - now with None for auth since standalone
            launch_gui(None)
    else:
        # Fall back to command-line mode
        analytics = StudentAnalytics()
        analytics.display_main_menu()
