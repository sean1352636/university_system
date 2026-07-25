"""Assembly file: composes GUIStudentAnalytics from mixin classes."""
from education_system.systems.university.interfaces.gui.shell.student_analytics._imports import (
    tk, ttk, plt, queue, sys, _t, StudentAnalytics,
)
from education_system.systems.university.interfaces.gui.shell.student_analytics.data import AnalyticsDataMixin
from education_system.systems.university.interfaces.gui.shell.student_analytics.analyses import AnalysesMixin
from education_system.systems.university.interfaces.gui.shell.student_analytics.tabs import TabsMixin
from education_system.systems.university.interfaces.gui.shell.student_analytics.runners import RunnersMixin
from education_system.systems.university.interfaces.gui.shell.student_analytics.results import ResultsMixin
from education_system.systems.university.interfaces.gui.shell.student_analytics.gui_utils import GUIUtilsMixin


class GUIStudentAnalytics(
    AnalyticsDataMixin,
    AnalysesMixin,
    TabsMixin,
    RunnersMixin,
    ResultsMixin,
    GUIUtilsMixin,
):
    """GUI wrapper for the existing StudentAnalytics class"""

    def __init__(self, root=None, auth_manager=None):
        # Accept root window or create new one
        self.root = root if root else tk.Tk()
        self.root.title(_t("analytics.window_title", default="Enhanced Student Analytics Dashboard"))
        self.root.geometry("1400x900")

        # Initialize database paths
        import os
        from education_system.systems.university.infrastructure import paths
        self.db_path = str(paths.DEFAULT_DB_PATH)
        self.custom_filters = {}
        self.plots_dir = str(paths.ANALYTICS_PLOTS_DIR)
        self.reports_dir = str(paths.REPORTS_DIR)
        self.create_directories()

        # Import the original StudentAnalytics class
        # Pass gui_mode=True to prevent CLI output and enable GUI display
        self.analytics = StudentAnalytics(gui_mode=True)

        # Set auth context if provided
        self.auth = auth_manager

        # Queue for thread communication
        self.output_queue = queue.Queue()

        # Setup GUI components
        self.setup_styles()
        self.create_main_interface()
        self.setup_output_capture()

        # Start output monitoring
        self.monitor_output()

        # Register cleanup on window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def on_closing(self):
        """Clean up matplotlib figures before closing"""
        # Cancel the pending monitor_output tick so it can't fire after destroy.
        after_id = getattr(self, '_monitor_after_id', None)
        if after_id is not None:
            try:
                self.root.after_cancel(after_id)
            except Exception:
                pass
            self._monitor_after_id = None
        # Restore stdout so prints don't keep feeding the dead capture queue.
        original_stdout = getattr(self, '_original_stdout', None)
        if original_stdout is not None:
            sys.stdout = original_stdout
            self._original_stdout = None
        try:
            plt.close('all')  # Close all matplotlib figures
        except Exception:
            pass
        finally:
            self.root.destroy()

    def setup_styles(self):
        """Configure the GUI styling"""
        style = ttk.Style()

        # Configure custom styles
        style.configure('Title.TLabel', font=('Arial', 16, 'bold'))
        style.configure('Heading.TLabel', font=('Arial', 12, 'bold'))
        style.configure('Action.TButton', font=('Arial', 10, 'bold'))

    def create_main_interface(self):
        """Create the main GUI interface"""
        # Create main frames
        self.create_header()
        self.create_main_content()
        self.create_status_bar()

    def create_header(self):
        """Create header with title and quick stats"""
        header_frame = ttk.Frame(self.root)
        header_frame.pack(fill='x', padx=10, pady=5)

        # Title
        title_label = ttk.Label(header_frame, text=_t("analytics.header_title", default="🎓 Enhanced Student Analytics Dashboard 🎓"),
                               style='Title.TLabel')
        title_label.pack(pady=5)

        # Quick stats frame
        stats_frame = ttk.Frame(header_frame)
        stats_frame.pack(fill='x', pady=5)

        # Quick stats (will be updated dynamically)
        self.stats_labels = {}
        stats_info = [
            (_t("analytics.total_students", default="Total Students"), "total_students"),
            (_t("analytics.avg_gpa", default="Avg GPA"), "avg_gpa"),
            (_t("analytics.completion_rate", default="Completion Rate"), "completion_rate"),
            (_t("analytics.at_risk", default="At Risk"), "at_risk")
        ]

        for i, (label, key) in enumerate(stats_info):
            frame = ttk.Frame(stats_frame)
            frame.pack(side='left', expand=True, fill='x', padx=5)

            ttk.Label(frame, text=label, style='Heading.TLabel').pack()
            self.stats_labels[key] = ttk.Label(frame, text=_t("common.loading", default="Loading..."),
                                              font=('Arial', 11, 'bold'))
            self.stats_labels[key].pack()

        # Return to Home button
        ttk.Button(stats_frame, text=_t("common.return_to_main_menu", default="🏠 Return to Main Menu"),
                  command=self.return_to_main_menu).pack(side='right', padx=5)

        # Refresh button
        ttk.Button(stats_frame, text=_t("analytics.refresh_stats", default="Refresh Stats"),
                  command=self.refresh_stats).pack(side='right', padx=5)

    def create_status_bar(self):
        """Create status bar at bottom"""
        self.status_frame = ttk.Frame(self.root)
        self.status_frame.pack(fill='x', side='bottom')

        self.status_label = ttk.Label(self.status_frame, text=_t("common.ready", default="Ready"), relief='sunken')
        self.status_label.pack(side='left', fill='x', expand=True)

        self.progress = ttk.Progressbar(self.status_frame, mode='indeterminate')
        self.progress.pack(side='right', padx=5)

    def run(self):
        """Start the GUI application"""
        # Initialize stats on startup
        self.refresh_stats()

        # Start the main loop
        self.root.mainloop()
