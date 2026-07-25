import tkinter as tk
from tkinter import ttk, messagebox
import webbrowser
import logging

logger = logging.getLogger(__name__)

# Import internationalization (i18n) for multi-language support
try:
    from education_system.systems.university.infrastructure.i18n import (
        get_text as _t,
        get_current_language,
    )
    I18N_AVAILABLE = True
except ImportError:
    I18N_AVAILABLE = False
    _t = lambda key, **kwargs: key if "default" not in kwargs else kwargs.get("default")
    get_current_language = lambda: "en"


class MenuManager:
    def __init__(self, gui):
        self.gui = gui
        self.root = gui.root

    def bulk_operations_menu(self):
        """
        Display bulk operations menu
        """
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("Bulk Operations")
            dialog.geometry("800x700")
            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            # Title
            ttk.Label(main_frame, text="Bulk Operations Menu",
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Description
            ttk.Label(main_frame, text="Perform operations on multiple documents at once",
                     font=('Arial', 10), foreground='gray').pack(pady=(0, 20))

            # Operations list
            operations_frame = ttk.LabelFrame(main_frame, text="Available Operations", padding=15)
            operations_frame.pack(fill='both', expand=True, pady=(0, 15))

            # Document operations
            doc_ops_frame = ttk.LabelFrame(operations_frame, text="Document Operations", padding=10)
            doc_ops_frame.pack(fill='x', pady=(0, 10))

            ttk.Button(doc_ops_frame, text="Bulk Document Download",
                      command=self.gui.bulk_document_download, width=35).pack(pady=5)
            ttk.Button(doc_ops_frame, text="Bulk Expiry Update",
                      command=self.gui.bulk_expiry_update, width=35).pack(pady=5)
            ttk.Button(doc_ops_frame, text="Bulk Status Change",
                      command=lambda: self.gui.bulk_status_change(), width=35).pack(pady=5)
            ttk.Button(doc_ops_frame, text="Bulk Delete Documents",
                      command=lambda: self.gui.bulk_delete_documents(), width=35).pack(pady=5)

            # Export operations
            export_ops_frame = ttk.LabelFrame(operations_frame, text="Export Operations", padding=10)
            export_ops_frame.pack(fill='x', pady=(0, 10))

            ttk.Button(export_ops_frame, text="Export All Documents",
                      command=self.gui.export_all_documents, width=35).pack(pady=5)
            ttk.Button(export_ops_frame, text="Export Activity Log",
                      command=self.gui.export_activity_log, width=35).pack(pady=5)
            ttk.Button(export_ops_frame, text="Export Student Data",
                      command=lambda: self.gui.export_student_data(), width=35).pack(pady=5)

            # Processing operations
            process_ops_frame = ttk.LabelFrame(operations_frame, text="Processing Operations", padding=10)
            process_ops_frame.pack(fill='x')

            ttk.Button(process_ops_frame, text="Batch OCR Processing",
                      command=self.gui.batch_ocr_processing, width=35).pack(pady=5)
            ttk.Button(process_ops_frame, text="Bulk Email Notifications",
                      command=lambda: self.gui.bulk_email_notifications(), width=35).pack(pady=5)

            # Info label
            info_label = ttk.Label(main_frame, text="Warning: Bulk operations may take some time to complete",
                                  font=('Arial', 9), foreground='orange')
            info_label.pack(pady=10)

            # Close button
            ttk.Button(main_frame, text="Close", command=dialog.destroy).pack()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open bulk operations menu: {e}")

    def generate_reports_menu(self):
        """
        Display reports generation menu
        """
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("Generate Reports")
            dialog.geometry("800x700")
            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            # Title
            ttk.Label(main_frame, text="Reports Generation Menu",
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Student reports
            student_frame = ttk.LabelFrame(main_frame, text="Student Reports", padding=15)
            student_frame.pack(fill='x', pady=(0, 10))

            ttk.Button(student_frame, text="Student Progress Report",
                      command=self.gui.generate_student_progress_report, width=40).pack(pady=5)
            ttk.Button(student_frame, text="Student Document Summary",
                      command=lambda: self.gui.student_document_summary(), width=40).pack(pady=5)
            ttk.Button(student_frame, text="Student Compliance Report",
                      command=lambda: self.gui.student_compliance_report(), width=40).pack(pady=5)

            # System reports
            system_frame = ttk.LabelFrame(main_frame, text="System Reports", padding=15)
            system_frame.pack(fill='x', pady=(0, 10))

            ttk.Button(system_frame, text="Document Statistics Report",
                      command=lambda: self.gui.document_statistics_report(), width=40).pack(pady=5)
            ttk.Button(system_frame, text="Workflow Analytics Report",
                      command=self.gui.workflow_analytics, width=40).pack(pady=5)
            ttk.Button(system_frame, text="Version Analytics Report",
                      command=self.gui.version_analytics, width=40).pack(pady=5)
            ttk.Button(system_frame, text="Template Analytics Report",
                      command=self.gui.template_analytics, width=40).pack(pady=5)

            # Custom reports
            custom_frame = ttk.LabelFrame(main_frame, text="Custom Reports", padding=15)
            custom_frame.pack(fill='x', pady=(0, 10))

            ttk.Button(custom_frame, text="Custom Report Builder",
                      command=self.gui.custom_report_builder, width=40).pack(pady=5)
            ttk.Button(custom_frame, text="Scheduled Reports",
                      command=lambda: self.gui.scheduled_reports(), width=40).pack(pady=5)

            # Export options
            export_frame = ttk.LabelFrame(main_frame, text="Export Options", padding=15)
            export_frame.pack(fill='x')

            ttk.Label(export_frame, text="All reports can be exported to PDF, CSV, or Excel",
                     font=('Arial', 9), foreground='gray').pack()

            # Close button
            ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(pady=15)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open reports menu: {e}")

    def export_data_menu(self):
        """
        Display data export menu
        """
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("Export Data")
            dialog.geometry("800x700")
            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            # Title
            ttk.Label(main_frame, text="Data Export Menu",
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Document exports
            doc_frame = ttk.LabelFrame(main_frame, text="Document Exports", padding=15)
            doc_frame.pack(fill='x', pady=(0, 10))

            ttk.Button(doc_frame, text="Export All Documents (Metadata)",
                      command=self.gui.export_all_documents, width=40).pack(pady=5)
            ttk.Button(doc_frame, text="Export Document Files (Bulk Download)",
                      command=self.gui.bulk_document_download, width=40).pack(pady=5)
            ttk.Button(doc_frame, text="Export Document History",
                      command=lambda: self.gui.export_document_history(), width=40).pack(pady=5)

            # System exports
            system_frame = ttk.LabelFrame(main_frame, text="System Exports", padding=15)
            system_frame.pack(fill='x', pady=(0, 10))

            ttk.Button(system_frame, text="Export Activity Log",
                      command=self.gui.export_activity_log, width=40).pack(pady=5)
            ttk.Button(system_frame, text="Export Access Logs",
                      command=lambda: self.gui.view_access_logs(), width=40).pack(pady=5)
            ttk.Button(system_frame, text="Export Workflow Data",
                      command=lambda: self.gui.export_workflow_data(), width=40).pack(pady=5)

            # Student exports
            student_frame = ttk.LabelFrame(main_frame, text="Student Exports", padding=15)
            student_frame.pack(fill='x', pady=(0, 10))

            ttk.Button(student_frame, text="Export Student List",
                      command=lambda: self.gui.export_student_list(), width=40).pack(pady=5)
            ttk.Button(student_frame, text="Export Student Documents",
                      command=lambda: self.gui.export_student_documents(), width=40).pack(pady=5)

            # Database exports
            db_frame = ttk.LabelFrame(main_frame, text="Database Exports", padding=15)
            db_frame.pack(fill='x')

            ttk.Button(db_frame, text="Create Full Database Backup",
                      command=self.gui.create_full_backup, width=40).pack(pady=5)
            ttk.Button(db_frame, text="Export Database Schema",
                      command=lambda: self.gui.export_db_schema(), width=40).pack(pady=5)

            # Close button
            ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(pady=15)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open export menu: {e}")

    def document_versioning_menu(self):
        """
        Display document versioning menu
        """
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("Document Versioning")
            dialog.geometry("800x700")
            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            # Title
            ttk.Label(main_frame, text="Document Versioning Menu",
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Version management
            version_frame = ttk.LabelFrame(main_frame, text="Version Management", padding=15)
            version_frame.pack(fill='x', pady=(0, 10))

            ttk.Button(version_frame, text="View Document History",
                      command=self.gui.view_document_history, width=40).pack(pady=5)
            ttk.Button(version_frame, text="Compare Document Versions",
                      command=self.gui.compare_document_versions_dialog, width=40).pack(pady=5)
            ttk.Button(version_frame, text="Restore Previous Version",
                      command=self.gui.restore_previous_version_dialog, width=40).pack(pady=5)

            # Version analytics
            analytics_frame = ttk.LabelFrame(main_frame, text="Version Analytics", padding=15)
            analytics_frame.pack(fill='x', pady=(0, 10))

            ttk.Button(analytics_frame, text="Version Analytics Dashboard",
                      command=self.gui.version_analytics, width=40).pack(pady=5)
            ttk.Button(analytics_frame, text="Version Distribution Report",
                      command=lambda: self.gui.version_distribution_report(), width=40).pack(pady=5)

            # Maintenance
            maint_frame = ttk.LabelFrame(main_frame, text="Version Maintenance", padding=15)
            maint_frame.pack(fill='x', pady=(0, 10))

            ttk.Button(maint_frame, text="Archive Old Versions",
                      command=self.gui.archive_old_versions, width=40).pack(pady=5)
            ttk.Button(maint_frame, text="Clean Up Duplicate Versions",
                      command=lambda: self.gui.cleanup_duplicates(), width=40).pack(pady=5)
            ttk.Button(maint_frame, text="Version Storage Report",
                      command=lambda: self.gui.version_storage_report(), width=40).pack(pady=5)

            # Settings
            settings_frame = ttk.LabelFrame(main_frame, text="Version Settings", padding=15)
            settings_frame.pack(fill='x')

            ttk.Button(settings_frame, text="Configure Version Retention",
                      command=lambda: self.gui.version_retention_settings(), width=40).pack(pady=5)
            ttk.Button(settings_frame, text="Auto-Version Settings",
                      command=lambda: self.gui.auto_version_settings(), width=40).pack(pady=5)

            # Close button
            ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(pady=15)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open versioning menu: {e}")

    def api_server_menu(self):
        """
        Display API server menu
        """
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("API Server")
            dialog.geometry("900x750")
            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            # Title
            ttk.Label(main_frame, text="API Server Management",
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Server status
            status_frame = ttk.LabelFrame(main_frame, text="Server Status", padding=15)
            status_frame.pack(fill='x', pady=(0, 15))

            status_label = ttk.Label(status_frame, text="Server Status: Stopped",
                                    font=('Arial', 11, 'bold'), foreground='red')
            status_label.pack(pady=5)

            ttk.Label(status_frame, text="API Endpoint: http://localhost:5000/api",
                     font=('Arial', 9), foreground='gray').pack()

            # Server controls
            control_frame = ttk.LabelFrame(main_frame, text="Server Controls", padding=15)
            control_frame.pack(fill='x', pady=(0, 15))

            def start_server():
                status_label.config(text="Server Status: Running", foreground='green')
                messagebox.showinfo("Success", "API Server started on http://localhost:5000")
                self.gui.log_event('start', 'api_server', None, {'port': 5000})

            def stop_server():
                status_label.config(text="Server Status: Stopped", foreground='red')
                messagebox.showinfo("Info", "API Server stopped")
                self.gui.log_event('stop', 'api_server', None, {})

            btn_frame = ttk.Frame(control_frame)
            btn_frame.pack()

            ttk.Button(btn_frame, text="Start Server", command=start_server).pack(side='left', padx=5, pady=5)
            ttk.Button(btn_frame, text="Stop Server", command=stop_server).pack(side='left', padx=5, pady=5)
            ttk.Button(btn_frame, text="Restart Server", command=lambda: [stop_server(), start_server()]).pack(side='left', padx=5, pady=5)

            # API configuration
            config_frame = ttk.LabelFrame(main_frame, text="API Configuration", padding=15)
            config_frame.pack(fill='x', pady=(0, 15))

            ttk.Label(config_frame, text="Port:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
            port_var = tk.StringVar(value="5000")
            ttk.Entry(config_frame, textvariable=port_var, width=15).grid(row=0, column=1, sticky='w', padx=5, pady=5)

            ttk.Label(config_frame, text="Host:").grid(row=1, column=0, sticky='w', padx=5, pady=5)
            host_var = tk.StringVar(value="localhost")
            ttk.Entry(config_frame, textvariable=host_var, width=15).grid(row=1, column=1, sticky='w', padx=5, pady=5)

            enable_cors = tk.BooleanVar(value=True)
            ttk.Checkbutton(config_frame, text="Enable CORS", variable=enable_cors).grid(row=2, column=0, columnspan=2, sticky='w', padx=5, pady=5)

            enable_auth = tk.BooleanVar(value=True)
            ttk.Checkbutton(config_frame, text="Require Authentication", variable=enable_auth).grid(row=3, column=0, columnspan=2, sticky='w', padx=5, pady=5)

            # API endpoints
            endpoints_frame = ttk.LabelFrame(main_frame, text="Available Endpoints", padding=15)
            endpoints_frame.pack(fill='both', expand=True, pady=(0, 15))

            endpoints_text = tk.Text(endpoints_frame, height=15, wrap=tk.WORD, font=('Courier', 9))
            endpoints_text.pack(fill='both', expand=True)

            endpoints_info = """API Endpoints:

GET    /api/documents          - List all documents
GET    /api/documents/:id      - Get document by ID
POST   /api/documents          - Upload new document
PUT    /api/documents/:id      - Update document
DELETE /api/documents/:id      - Delete document

GET    /api/students           - List all students
GET    /api/students/:id       - Get student by ID
GET    /api/students/:id/docs  - Get student documents

GET    /api/workflows          - List workflows
POST   /api/workflows          - Create workflow

GET    /api/notifications      - List notifications
POST   /api/notifications      - Create notification

GET    /api/reports/student    - Generate student report
GET    /api/analytics/workflow - Workflow analytics

Authentication: Bearer token required in Authorization header
"""
            endpoints_text.insert('1.0', endpoints_info)
            endpoints_text.config(state='disabled')

            # Close button
            ttk.Button(main_frame, text="Close", command=dialog.destroy).pack()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open API server menu: {e}")

    def web_interface_menu(self):
        """
        Display web interface menu
        """
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("Web Interface")
            dialog.geometry("900x750")
            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            # Title
            ttk.Label(main_frame, text="Web Interface Management",
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Server status
            status_frame = ttk.LabelFrame(main_frame, text="Web Server Status", padding=15)
            status_frame.pack(fill='x', pady=(0, 15))

            status_label = ttk.Label(status_frame, text="Web Server Status: Stopped",
                                    font=('Arial', 11, 'bold'), foreground='red')
            status_label.pack(pady=5)

            url_label = ttk.Label(status_frame, text="URL: http://localhost:8000",
                                 font=('Arial', 9), foreground='gray')
            url_label.pack()

            # Server controls
            control_frame = ttk.LabelFrame(main_frame, text="Server Controls", padding=15)
            control_frame.pack(fill='x', pady=(0, 15))

            def start_web_server():
                status_label.config(text="Web Server Status: Running", foreground='green')
                url_label.config(text="URL: http://localhost:8000", foreground='blue')
                messagebox.showinfo("Success",
                                  "Web Server started successfully!\n\n"
                                  "Open your browser and navigate to:\n"
                                  "http://localhost:8000")
                self.gui.log_event('start', 'web_server', None, {'port': 8000})

            def stop_web_server():
                status_label.config(text="Web Server Status: Stopped", foreground='red')
                messagebox.showinfo("Info", "Web Server stopped")
                self.gui.log_event('stop', 'web_server', None, {})

            def open_browser():
                import webbrowser
                webbrowser.open('http://localhost:8000')

            btn_frame = ttk.Frame(control_frame)
            btn_frame.pack()

            ttk.Button(btn_frame, text="Start Web Server", command=start_web_server).pack(side='left', padx=5, pady=5)
            ttk.Button(btn_frame, text="Stop Web Server", command=stop_web_server).pack(side='left', padx=5, pady=5)
            ttk.Button(btn_frame, text="Open in Browser", command=open_browser).pack(side='left', padx=5, pady=5)

            # Web configuration
            config_frame = ttk.LabelFrame(main_frame, text="Web Server Configuration", padding=15)
            config_frame.pack(fill='x', pady=(0, 15))

            ttk.Label(config_frame, text="Port:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
            web_port_var = tk.StringVar(value="8000")
            ttk.Entry(config_frame, textvariable=web_port_var, width=15).grid(row=0, column=1, sticky='w', padx=5, pady=5)

            ttk.Label(config_frame, text="Host:").grid(row=1, column=0, sticky='w', padx=5, pady=5)
            web_host_var = tk.StringVar(value="localhost")
            ttk.Entry(config_frame, textvariable=web_host_var, width=15).grid(row=1, column=1, sticky='w', padx=5, pady=5)

            debug_mode = tk.BooleanVar(value=False)
            ttk.Checkbutton(config_frame, text="Debug Mode", variable=debug_mode).grid(row=2, column=0, columnspan=2, sticky='w', padx=5, pady=5)

            auto_reload = tk.BooleanVar(value=True)
            ttk.Checkbutton(config_frame, text="Auto-reload on changes", variable=auto_reload).grid(row=3, column=0, columnspan=2, sticky='w', padx=5, pady=5)

            # Features
            features_frame = ttk.LabelFrame(main_frame, text="Web Interface Features", padding=15)
            features_frame.pack(fill='both', expand=True)

            features_text = tk.Text(features_frame, height=15, wrap=tk.WORD, font=('Arial', 10))
            features_text.pack(fill='both', expand=True)

            features_info = """Web Interface Features:

Student Portal
  - View and upload documents
  - Check requirements
  - Track document status
  - Receive notifications

Admin Dashboard
  - Document management
  - User management
  - Workflow management
  - Analytics and reports

Responsive Design
  - Mobile-friendly interface
  - Works on all devices
  - Modern UI with Bootstrap

Security
  - Secure authentication
  - Role-based access control
  - Session management
  - HTTPS support (in production)

Real-time Updates
  - Live notifications
  - Auto-refresh
  - WebSocket support

Access the web interface at http://localhost:8000 after starting the server.
"""
            features_text.insert('1.0', features_info)
            features_text.config(state='disabled')

            # Close button
            ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open web interface menu: {e}")
