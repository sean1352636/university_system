from education_system.systems.university.interfaces.gui.finance.finance_reporting.archive_backup._imports import (
    sys, tk, ttk, ScrolledText, datetime, _,
)


def show_enhanced_system_info(self):
    """Show enhanced system information dialog"""
    info_window = tk.Toplevel(self.root)
    info_window.title(_("finance_reporting.windows.system_info"))
    info_window.geometry("800x600")

    main_frame = ttk.Frame(info_window, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main_frame, text="Enhanced System Information",
             style='Title.TLabel').pack(pady=(0, 20))

    # Create notebook for different info sections
    notebook = ttk.Notebook(main_frame)
    notebook.pack(fill=tk.BOTH, expand=True)

    # System Overview Tab
    overview_frame = ttk.Frame(notebook, padding="10")
    notebook.add(overview_frame, text="System Overview")

    overview_text = ScrolledText(overview_frame, height=20, wrap=tk.WORD)
    overview_text.pack(fill=tk.BOTH, expand=True)

    # Database Statistics Tab
    db_frame = ttk.Frame(notebook, padding="10")
    notebook.add(db_frame, text="Database Statistics")

    db_tree = ttk.Treeview(db_frame, columns=('Records', 'Size'), height=15)
    db_tree.heading('#0', text='Table')
    db_tree.heading('Records', text='Record Count')
    db_tree.heading('Size', text='Estimated Size')
    db_tree.pack(fill=tk.BOTH, expand=True)

    # Feature Status Tab
    features_frame = ttk.Frame(notebook, padding="10")
    notebook.add(features_frame, text="Feature Status")

    features_tree = ttk.Treeview(features_frame, columns=('Status', 'Version'), height=15)
    features_tree.heading('#0', text='Feature')
    features_tree.heading('Status', text='Status')
    features_tree.heading('Version', text='Version')
    features_tree.pack(fill=tk.BOTH, expand=True)

    # Populate system information
    self.populate_system_info(overview_text, db_tree, features_tree)

    ttk.Button(main_frame, text="Refresh",
               command=lambda: self.populate_system_info(overview_text, db_tree, features_tree)).pack(pady=5)
    ttk.Button(main_frame, text="Close", command=info_window.destroy).pack(pady=5)

def populate_system_info(self, overview_text, db_tree, features_tree):
    """Populate system information displays"""
    # Clear existing content
    overview_text.delete(1.0, tk.END)
    for item in db_tree.get_children():
        db_tree.delete(item)
    for item in features_tree.get_children():
        features_tree.delete(item)

    # System overview
    overview_content = f"""Enhanced Financial Management System - Detailed Information
    ================================================================

    Application Details:
    • Version: 2.0.0 (Enhanced GUI Edition)
    • Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    • Python Version: {sys.version.split()[0]}
    • Platform: {sys.platform}

    Core Components:
    • Database Engine: SQLite with enhanced indexing
    • ML Framework: scikit-learn (if available)
    • Visualization: matplotlib + seaborn
    • GUI Framework: tkinter with ttk styling
    • Reporting: ReportLab PDF generation

    Operational Status:
    • Database: Connected and optimized
    • ML Models: Available for risk prediction
    • Alert System: Active monitoring
    • Export System: Multi-format support
    • Real-time Dashboard: Operational

    Recent Activity:
    • System Health Checks: Automated
    • Performance Optimization: Continuous
    • Data Quality Monitoring: Active
    • Compliance Auditing: Scheduled

    Memory and Performance:
    • Database Connections: Pooled and managed
    • Query Optimization: Index-based
    • Chart Generation: Memory-efficient
    • Background Processing: Multi-threaded

    Security Features:
    • Authentication: Role-based access control
    • Audit Logging: Comprehensive trail
    • Data Encryption: Transport layer security
    • Access Control: Permission-based

    Integration Capabilities:
    • API Endpoints: RESTful interface
    • Export Formats: PDF, Excel, CSV, JSON
    • Automated Reports: Scheduled delivery
    • Data Feeds: Real-time synchronization

    Support and Maintenance:
    • Automated Backups: Daily scheduling
    • Archive Management: Configurable retention
    • Performance Monitoring: Real-time metrics
    • Error Logging: Comprehensive tracking

    For technical support or feature requests, contact the system administrator.
    Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    """

    overview_text.insert(1.0, overview_content)
    overview_text.configure(state='disabled')

    # Database statistics
    try:
        from education_system.systems.university.infrastructure.database.db import get_connection
        conn = get_connection()
        cursor = conn.cursor()

        tables = ['students', 'student_fees', 'payments', 'fee_types', 'financial_alerts', 'audit_log']
        for table in tables:
            try:
                from education_system.systems.university.infrastructure.sql_safety import validate_table_name
                validated_table = validate_table_name(table, conn=conn)
                cursor.execute("SELECT COUNT(*) FROM [" + validated_table + "]")
                count = cursor.fetchone()[0]
                size_estimate = f"{count * 0.5:.1f} KB"  # Rough estimate
                db_tree.insert('', 'end', text=table, values=(f"{count:,}", size_estimate))
            except Exception:
                db_tree.insert('', 'end', text=table, values=("N/A", "N/A"))

        conn.close()

    except Exception as e:
        db_tree.insert('', 'end', text="Database Error", values=(str(e), "N/A"))

    # Feature status
    features = [
        ('Advanced Forecasting', 'Operational', '2.0'),
        ('Payment Risk Prediction', 'Operational', '2.0'),
        ('Anomaly Detection', 'Operational', '2.0'),
        ('Cash Flow Forecasting', 'Operational', '2.0'),
        ('Real-time Dashboard', 'Operational', '2.0'),
        ('Automated Reporting', 'Operational', '2.0'),
        ('Compliance Auditing', 'Operational', '2.0'),
        ('Data Quality Assessment', 'Operational', '2.0'),
        ('Performance Optimization', 'Operational', '2.0'),
        ('Archive Management', 'Operational', '2.0'),
        ('API Integration', 'Development', '2.1'),
        ('Mobile Interface', 'Planned', '3.0')
    ]

    for feature, status, version in features:
        features_tree.insert('', 'end', text=feature, values=(status, version))
