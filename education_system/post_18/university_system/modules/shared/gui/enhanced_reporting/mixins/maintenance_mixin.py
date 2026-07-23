"""Maintenance methods mixin for the enhanced reporting GUI."""

from education_system.post_18.university_system.modules.shared.gui.enhanced_reporting.standalone.constants import (
    tk, ttk, filedialog, messagebox,
    ScrolledText,
    threading, webbrowser, os, json, logging,
    datetime, timedelta,
    paths, get_db_connection,
    CONFIG, ENHANCED_AVAILABLE,
    DEFAULT_DB_PATH,
    _t,
    CacheManager, SystemConfig,
    run_system_maintenance as _standalone_run_system_maintenance,
    cleanup_old_reports as _standalone_cleanup_old_reports,
    load_templates, load_scheduled_reports,
    get_log_file,
)
from education_system.post_18.university_system.core.sql_safety import validate_table_name


class MaintenanceMixin:
    """Mixin providing maintenance, performance monitoring, and API server methods."""

    def clean_old_reports(self):
        """Clean old report files"""
        self.update_status("Cleaning old reports...")
        self.start_progress()

        def clean_task():
            try:
                if ENHANCED_AVAILABLE:
                    _standalone_cleanup_old_reports()

                self.root.after(0, lambda: [
                    self.stop_progress(),
                    self.update_status("Old reports cleaned"),
                    self.refresh_reports(),
                    messagebox.showinfo("Success", "Old reports cleaned successfully!")
                ])

            except Exception as e:
                self.root.after(0, lambda _e=e: [
                    self.update_status(f"Cleanup failed: {_e}", "error"),
                    messagebox.showerror("Error", f"Failed to clean old reports: {str(_e)}")
                ])

        threading.Thread(target=clean_task, daemon=True).start()

    def clear_cache(self):
        """Clear system cache"""
        self.update_status("Clearing cache...")
        self.start_progress()

        def cache_task():
            try:
                if ENHANCED_AVAILABLE:
                    CacheManager.cleanup_cache()

                self.root.after(0, lambda: [
                    self.stop_progress(),
                    self.update_status("Cache cleared"),
                    messagebox.showinfo("Success", "Cache cleared successfully!")
                ])

            except Exception as e:
                self.root.after(0, lambda _e=e: [
                    self.stop_progress(),
                    self.update_status(f"Cache clear failed: {str(_e)}", "error"),
                    messagebox.showerror("Error", f"Failed to clear cache: {str(_e)}")
                ])

        threading.Thread(target=cache_task, daemon=True).start()

    def run_maintenance_quality_check(self):
        """Run maintenance quality check"""
        self.run_quality_check()

    def optimize_database(self):
        """Optimize database"""
        self.update_status("Optimizing database...")
        self.start_progress()

        def optimize_task():
            try:
                if ENHANCED_AVAILABLE:
                    conn = get_db_connection()
                    try:
                        conn.execute("VACUUM")
                        conn.execute("ANALYZE")
                    finally:
                        conn.close()

                self.root.after(0, lambda: [
                    self.stop_progress(),
                    self.update_status("Database optimized"),
                    messagebox.showinfo("Success", "Database optimized successfully!")
                ])

            except Exception as e:
                self.root.after(0, lambda _e=e: [
                    self.stop_progress(),
                    self.update_status(f"Optimization failed: {str(_e)}", "error"),
                    messagebox.showerror("Error", f"Failed to optimize database: {str(_e)}")
                ])

        threading.Thread(target=optimize_task, daemon=True).start()

    def run_all_maintenance(self):
        """Run all maintenance tasks"""
        self.update_status("Running all maintenance tasks...")
        self.start_progress()

        def maintenance_task():
            try:
                if ENHANCED_AVAILABLE:
                    quality_report = _standalone_run_system_maintenance()

                self.root.after(0, lambda: [
                    self.stop_progress(),
                    self.update_status("All maintenance completed"),
                    self.refresh_data(),
                    messagebox.showinfo("Success", "All maintenance tasks completed successfully!")
                ])

            except Exception as e:
                self.root.after(0, lambda _e=e: [
                    self.stop_progress(),
                    self.update_status(f"Maintenance failed: {str(_e)}", "error"),
                    messagebox.showerror("Error", f"Failed to run maintenance: {str(_e)}")
                ])

        threading.Thread(target=maintenance_task, daemon=True).start()

    def _show_performance_monitor_basic(self):
        """Show performance monitoring window"""
        perf_window = tk.Toplevel(self.root)
        perf_window.title("Performance Monitor")
        perf_window.geometry("600x500")

        perf_text = ScrolledText(perf_window, wrap=tk.WORD)
        perf_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Get performance data
        self.update_status("Gathering performance data...")

        def perf_task():
            try:
                output = "Performance Monitor\n"
                output += "=" * 35 + "\n\n"

                if ENHANCED_AVAILABLE:
                    # Database size
                    db_size = os.path.getsize(CONFIG['database']) / (1024 * 1024)  # MB
                    output += f"Database size: {db_size:.2f} MB\n"

                    # Reports directory size
                    reports_size = 0
                    if os.path.exists(CONFIG['reports_dir']):
                        for root, dirs, files in os.walk(CONFIG['reports_dir']):
                            for file in files:
                                reports_size += os.path.getsize(os.path.join(root, file))
                    reports_size = reports_size / (1024 * 1024)  # MB
                    output += f"Reports size: {reports_size:.2f} MB\n"

                    # Cache directory size
                    cache_size = 0
                    if os.path.exists(CONFIG['cache_dir']):
                        for root, dirs, files in os.walk(CONFIG['cache_dir']):
                            for file in files:
                                cache_size += os.path.getsize(os.path.join(root, file))
                    cache_size = cache_size / (1024 * 1024)  # MB
                    output += f"Cache size: {cache_size:.2f} MB\n\n"

                    # Record counts
                    conn = get_db_connection()
                    try:
                        cursor = conn.cursor()

                        cursor.execute("SELECT COUNT(*) FROM students")
                        student_count = cursor.fetchone()[0]
                        output += f"Total students: {student_count}\n"

                        # Check if other tables exist
                        tables = ['student_modules', 'student_grades', 'student_attendance']
                        for table in tables:
                            try:
                                safe_table = validate_table_name(table)
                                cursor.execute("SELECT COUNT(*) FROM [" + safe_table + "]")
                                count = cursor.fetchone()[0]
                                table_name = table.replace('_', ' ').title()
                                output += f"{table_name}: {count}\n"
                            except Exception:

                                pass  # Table might not exist

                    finally:
                        conn.close()

                    # Template and schedule counts
                    templates = load_templates()
                    output += f"Templates: {len(templates)}\n"

                    scheduled_reports = load_scheduled_reports()
                    output += f"Scheduled reports: {len(scheduled_reports)}\n"

                else:
                    output += "Enhanced features not available\n"
                    output += "Limited performance data shown\n"

                self.root.after(0, lambda: [
                    perf_text.insert(1.0, output),
                    perf_text.config(state=tk.DISABLED),
                    self.update_status("Performance data loaded")
                ])

            except Exception as e:
                error_output = f"Error gathering performance data: {str(e)}"
                self.root.after(0, lambda: [
                    perf_text.insert(1.0, error_output),
                    perf_text.config(state=tk.DISABLED),
                    self.update_status("Performance data failed", "error")
                ])

        threading.Thread(target=perf_task, daemon=True).start()

    def export_system_logs(self):
        """Export system logs"""
        if not ENHANCED_AVAILABLE:
            messagebox.showwarning("Feature Unavailable",
                                 "Log export requires the enhanced system.")
            return

        try:
            log_file = get_log_file('app.log')

            if not os.path.exists(log_file):
                messagebox.showwarning("No Logs", "No log file found")
                return

            file_path = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                initialfile=f"system_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            )

            if file_path:
                # Copy log file
                import shutil
                shutil.copy2(log_file, file_path)
                messagebox.showinfo("Success", f"System logs exported to {file_path}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to export logs: {str(e)}")

    def start_api_server(self):
        """Start the REST API server"""
        if not ENHANCED_AVAILABLE:
            messagebox.showwarning("Feature Unavailable",
                                 "API server requires the enhanced system.")
            return

        # API server dialog
        api_dialog = tk.Toplevel(self.root)
        api_dialog.title("Start API Server")
        api_dialog.geometry("400x300")
        api_dialog.transient(self.root)

        ttk.Label(api_dialog, text="API Server Configuration", style='Subtitle.TLabel').pack(pady=10)

        # Host and port settings
        config_frame = ttk.Frame(api_dialog)
        config_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Label(config_frame, text="Host:").pack(anchor=tk.W)
        host_var = tk.StringVar(value="localhost")
        ttk.Entry(config_frame, textvariable=host_var).pack(fill=tk.X, pady=(0, 10))

        ttk.Label(config_frame, text="Port:").pack(anchor=tk.W)
        port_var = tk.StringVar(value="5000")
        ttk.Entry(config_frame, textvariable=port_var).pack(fill=tk.X, pady=(0, 10))

        # API endpoints info
        info_text = ScrolledText(api_dialog, height=8, wrap=tk.WORD)
        info_text.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        api_info = """API Endpoints:

* POST /api/login - User authentication
* GET  /api/templates - List templates
* POST /api/templates - Create template
* POST /api/reports/generate - Generate report
* GET  /api/analytics/quality - Data quality
* GET  /api/analytics/predictions - Predictions
* GET  /api/analytics/anomalies - Anomaly detection"""

        info_text.insert(1.0, api_info)
        info_text.config(state=tk.DISABLED)

        # Buttons
        button_frame = ttk.Frame(api_dialog)
        button_frame.pack(fill=tk.X, padx=20, pady=(0, 20))

        def start_server():
            host = host_var.get()
            port = int(port_var.get())

            messagebox.showinfo("API Server",
                              f"API server would start on http://{host}:{port}\n\n(This would run in background thread)")
            api_dialog.destroy()

        ttk.Button(button_frame, text="Start Server", command=start_server,
                  style='Success.TButton').pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(button_frame, text="Cancel", command=api_dialog.destroy).pack(side=tk.RIGHT)

    def show_performance_monitor(self):
        """Show system performance monitoring dashboard"""
        try:
            perf_window = tk.Toplevel(self.root)
            perf_window.title("Performance Monitor")
            perf_window.geometry("600x500")
            perf_window.transient(self.root)

            # Header
            header_frame = ttk.Frame(perf_window)
            header_frame.pack(fill=tk.X, padx=20, pady=10)
            ttk.Label(header_frame, text="Performance Monitor",
                     font=('Arial', 14, 'bold')).pack(anchor=tk.W)

            # Performance metrics
            metrics_frame = ttk.LabelFrame(perf_window, text="System Metrics", padding="10")
            metrics_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

            metrics_text = ScrolledText(metrics_frame, wrap=tk.WORD, height=20)
            metrics_text.pack(fill=tk.BOTH, expand=True)

            def load_metrics():
                try:
                    # Database size
                    db_path = CONFIG.get('database', str(DEFAULT_DB_PATH))
                    if os.path.exists(db_path):
                        db_size = os.path.getsize(db_path) / (1024 * 1024)
                        metrics_text.insert(tk.END, f"Database Size: {db_size:.2f} MB\n\n")

                    # Reports directory size
                    reports_dir = CONFIG.get('reports_dir', 'reports')
                    if os.path.exists(reports_dir):
                        reports_size = 0
                        for root, dirs, files in os.walk(reports_dir):
                            for file in files:
                                reports_size += os.path.getsize(os.path.join(root, file))
                        reports_size = reports_size / (1024 * 1024)
                        metrics_text.insert(tk.END, f"Reports Size: {reports_size:.2f} MB\n\n")

                    # Cache directory size
                    cache_dir = CONFIG.get('cache_dir', 'cache')
                    if os.path.exists(cache_dir):
                        cache_size = 0
                        for root, dirs, files in os.walk(cache_dir):
                            for file in files:
                                cache_size += os.path.getsize(os.path.join(root, file))
                        cache_size = cache_size / (1024 * 1024)
                        metrics_text.insert(tk.END, f"Cache Size: {cache_size:.2f} MB\n\n")

                    # Record counts
                    try:
                        conn = get_db_connection()
                        if conn:
                            cursor = conn.cursor()

                            cursor.execute("SELECT COUNT(*) FROM students")
                            student_count = cursor.fetchone()[0]
                            metrics_text.insert(tk.END, f"Total Students: {student_count}\n")

                            cursor.execute("SELECT COUNT(*) FROM courses")
                            course_count = cursor.fetchone()[0]
                            metrics_text.insert(tk.END, f"Total Courses: {course_count}\n")

                            cursor.execute("SELECT COUNT(*) FROM lms_student_enrollment")
                            enrollment_count = cursor.fetchone()[0]
                            metrics_text.insert(tk.END, f"Total Enrollments: {enrollment_count}\n\n")

                            conn.close()
                    except Exception as e:
                        metrics_text.insert(tk.END, f"Could not fetch database records: {str(e)}\n\n")

                    # System info
                    metrics_text.insert(tk.END, f"Python Version: {os.sys.version.split()[0]}\n")
                    metrics_text.insert(tk.END, f"Enhanced Features: {'Available' if ENHANCED_AVAILABLE else 'Not Available'}\n")

                    metrics_text.config(state=tk.DISABLED)

                except Exception as e:
                    metrics_text.insert(tk.END, f"Error loading metrics: {str(e)}")
                    metrics_text.config(state=tk.DISABLED)

            load_metrics()

            # Refresh button
            button_frame = ttk.Frame(perf_window)
            button_frame.pack(fill=tk.X, padx=20, pady=(0, 20))

            def refresh_metrics():
                metrics_text.config(state=tk.NORMAL)
                metrics_text.delete(1.0, tk.END)
                load_metrics()

            ttk.Button(button_frame, text="Refresh", command=refresh_metrics).pack(side=tk.LEFT)
            ttk.Button(button_frame, text="Close", command=perf_window.destroy).pack(side=tk.RIGHT)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to show performance monitor: {str(e)}")

    def export_logs_menu(self):
        """Export logs to file"""
        try:
            log_file = self.get_log_file()

            if not log_file or not os.path.exists(log_file):
                messagebox.showinfo("No Logs", "No log file found")
                return

            save_path = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                title="Export Logs"
            )

            if save_path:
                import shutil
                shutil.copy2(log_file, save_path)
                messagebox.showinfo("Success", f"Logs exported to:\n{save_path}")
                self.update_status("Logs exported successfully", "success")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to export logs: {str(e)}")

    def run_maintenance_menu(self):
        """Show system maintenance menu"""
        try:
            maint_window = tk.Toplevel(self.root)
            maint_window.title("System Maintenance")
            maint_window.geometry("600x500")
            maint_window.transient(self.root)

            ttk.Label(maint_window, text="System Maintenance",
                     font=('Arial', 14, 'bold')).pack(pady=10)

            # Maintenance options
            options_frame = ttk.LabelFrame(maint_window, text="Maintenance Tasks", padding="10")
            options_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

            tasks = [
                ("Clean Cache", self.show_cache_management_dialog, "Manage and clean cache files"),
                ("Export Logs", self.export_logs_menu, "Export system logs"),
                ("View Performance", self.show_performance_monitor, "Show system performance metrics"),
                ("Database Integrity", self.run_quality_checks, "Check database integrity"),
            ]

            for i, (task_name, task_func, description) in enumerate(tasks):
                task_frame = ttk.Frame(options_frame)
                task_frame.pack(fill=tk.X, pady=5)

                ttk.Label(task_frame, text=f"* {task_name}:", font=('Arial', 10, 'bold')).pack(anchor=tk.W)
                ttk.Label(task_frame, text=f"  {description}", foreground='gray').pack(anchor=tk.W)
                ttk.Button(task_frame, text="Run", command=task_func).pack(anchor=tk.E)
                ttk.Separator(options_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)

            ttk.Button(maint_window, text="Close", command=maint_window.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to show maintenance menu: {str(e)}")

    def display_enhanced_reporting_menu(self):
        """Display main enhanced reporting menu (compatibility wrapper)"""
        try:
            # Show GUI help/welcome dialog
            help_window = tk.Toplevel(self.root)
            help_window.title("Enhanced Reporting System - Help")
            help_window.geometry("700x600")
            help_window.transient(self.root)

            # Header
            header_frame = ttk.Frame(help_window)
            header_frame.pack(fill=tk.X, padx=20, pady=10)

            ttk.Label(header_frame, text="Enhanced Reporting System",
                     font=('Arial', 16, 'bold')).pack(anchor=tk.W)
            ttk.Label(header_frame, text="Welcome to the GUI Interface",
                     font=('Arial', 10)).pack(anchor=tk.W)

            # Create tabbed interface for help sections
            help_notebook = ttk.Notebook(help_window)
            help_notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

            # Getting Started Tab
            start_frame = ttk.Frame(help_notebook)
            help_notebook.add(start_frame, text="Getting Started")

            start_text = ScrolledText(start_frame, wrap=tk.WORD, height=20)
            start_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            getting_started = """Getting Started with Enhanced Reporting

Welcome to the Enhanced Reporting System GUI! This interface provides comprehensive
reporting and analytics capabilities for your university management system.

Main Features:

Templates Tab
   * Create custom report templates
   * Edit existing templates
   * Manage template library
   * Import/export templates

Reports Tab
   * Generate reports from templates
   * View report history
   * Export reports (PDF, Excel, HTML)
   * Share reports via email

Analytics Tab
   * Data quality monitoring
   * Predictive analytics
   * Anomaly detection
   * Correlation analysis
   * Interactive visualizations

Schedule Tab
   * Schedule automatic reports
   * Manage scheduled jobs
   * Configure email recipients
   * Set frequency (daily/weekly/monthly)

System Tab
   * Performance monitoring
   * Cache management
   * Configuration settings
   * System maintenance

Quick Start:

1. Create a Template
   * Go to Templates tab
   * Click "Create Template"
   * Select report sections
   * Save template

2. Generate Report
   * Go to Reports tab
   * Select template
   * Choose date range
   * Click "Generate"

3. View Analytics
   * Go to Analytics tab
   * Select analysis type
   * View results
   * Export if needed

Need Help?

* Hover over buttons for tooltips
* Check the System tab for requirements
* Use the status bar for operation feedback
* Check logs for detailed information
"""

            start_text.insert(1.0, getting_started)
            start_text.config(state=tk.DISABLED)

            # Features Tab
            features_frame = ttk.Frame(help_notebook)
            help_notebook.add(features_frame, text="Features")

            features_text = ScrolledText(features_frame, wrap=tk.WORD, height=20)
            features_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            features_info = """Available Features

REPORT GENERATION

* PDF Reports: Professional formatted reports with charts and tables
* Excel Reports: Multi-sheet workbooks with data and analytics
* Interactive Reports: HTML dashboards with interactive visualizations
* Custom Templates: Create templates with specific sections
* Batch Generation: Generate multiple reports at once

DATA ANALYTICS

* Data Quality Monitoring: Check for missing, duplicate, or invalid data
* Predictive Analytics: Dropout risk prediction and trend analysis
* Anomaly Detection: Identify unusual patterns in student data
* Correlation Analysis: Discover relationships between variables
* Statistical Summaries: Comprehensive statistics on all data

VISUALIZATIONS

* Bar Charts: Compare categorical data
* Line Charts: Show trends over time
* Pie Charts: Display proportions
* Heatmaps: Show correlations between variables
* Interactive Dashboards: Plotly-based interactive visualizations

SCHEDULING & AUTOMATION

* Scheduled Reports: Automatically generate reports
* Email Delivery: Send reports to recipients
* Multiple Frequencies: Daily, weekly, monthly schedules
* Configurable Times: Set specific times for generation

SYSTEM MANAGEMENT

* Cache Management: Optimize performance with caching
* Performance Monitoring: Track system resources
* Configuration: Customize system settings
* Backup & Restore: Protect your data
* Logs Export: Download system logs for analysis
"""

            features_text.insert(1.0, features_info)
            features_text.config(state=tk.DISABLED)

            # Keyboard Shortcuts Tab
            shortcuts_frame = ttk.Frame(help_notebook)
            help_notebook.add(shortcuts_frame, text="Shortcuts")

            shortcuts_text = ScrolledText(shortcuts_frame, wrap=tk.WORD, height=20)
            shortcuts_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            shortcuts_info = """Keyboard Shortcuts & Tips

GENERAL SHORTCUTS

* F5: Refresh current view
* Ctrl+N: Create new template
* Ctrl+R: Generate report
* Ctrl+S: Save current item
* Ctrl+Q: Quit application
* Esc: Close dialog windows

NAVIGATION

* Tab: Move between fields
* Shift+Tab: Move backward
* Enter: Confirm/OK
* Esc: Cancel

TIPS & TRICKS

Performance:
* Use cache for faster report generation
* Clean cache regularly to save space
* Schedule reports during off-peak hours

Templates:
* Create reusable templates for common reports
* Use descriptive names for easy identification
* Include all necessary sections initially

Reports:
* Use appropriate date ranges for better performance
* Export to Excel for further analysis
* Share reports via email for collaboration

Analytics:
* Run quality checks regularly
* Monitor anomalies for data issues
* Use correlation analysis for insights

Troubleshooting:
* Check system requirements if features are unavailable
* View logs for detailed error messages
* Ensure database connection is active
* Clear cache if experiencing issues
"""

            shortcuts_text.insert(1.0, shortcuts_info)
            shortcuts_text.config(state=tk.DISABLED)

            # Close button
            button_frame = ttk.Frame(help_window)
            button_frame.pack(pady=10)

            ttk.Button(button_frame, text="Close", command=help_window.destroy,
                      style='TButton').pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="View Documentation Online",
                      command=lambda: webbrowser.open("https://github.com")).pack(side=tk.LEFT, padx=5)

        except Exception as e:
            logging.error(f"Error showing enhanced reporting menu: {str(e)}")
            messagebox.showerror("Error", f"Failed to show help: {str(e)}")
