import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
import csv
import json
import logging
import sqlite3

logger = logging.getLogger(__name__)

try:
    from university_system.infrastructure.database.db import get_connection
except ImportError:
    from university_system.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH
    def get_connection():
        return sqlite3.connect(str(DEFAULT_DB_PATH))

try:
    from university_system.modules.shared.utils.i18n import get_text as _t
except ImportError:
    _t = lambda key, **kwargs: key if "default" not in kwargs else kwargs.get("default")


class DashboardManager:
    """Manager for dashboard-related functionality in the Document Manager GUI."""

    def __init__(self, gui):
        self.gui = gui
        self.root = gui.root

    def show_dashboard(self):
        """Show the main dashboard"""
        self.gui.clear_content_area()

        # Create dashboard frame
        dashboard_frame = ttk.Frame(self.gui.content_area)
        dashboard_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Title
        title_label = ttk.Label(dashboard_frame, text=_t("docmanager.system_dashboard", default="System Dashboard"), font=('Arial', 18, 'bold'))
        title_label.pack(pady=(0, 20))

        # Create stats cards row
        stats_frame = ttk.Frame(dashboard_frame)
        stats_frame.pack(fill='x', pady=(0, 20))

        # Get dashboard statistics
        stats = self.get_dashboard_stats()

        # Create stat cards
        self.create_stat_card(stats_frame, _t("docmanager.total_documents", default="Total Documents"), stats['total_docs'], "#4CAF50", 0)
        self.create_stat_card(stats_frame, _t("docmanager.pending_review", default="Pending Review"), stats['pending_docs'], "#FF9800", 1)
        self.create_stat_card(stats_frame, _t("docmanager.students", default="Students"), stats['total_students'], "#2196F3", 2)
        self.create_stat_card(stats_frame, _t("docmanager.today_uploads", default="Today's Uploads"), stats['today_uploads'], "#9C27B0", 3)

        # Create charts and tables row
        charts_frame = ttk.Frame(dashboard_frame)
        charts_frame.pack(fill='both', expand=True)

        # Document status chart (left side)
        self.create_status_chart(charts_frame)

        # Recent activity table (right side)
        self.create_recent_activity_table(charts_frame)

        # Refresh button
        refresh_btn = ttk.Button(dashboard_frame, text=_t("docmanager.refresh_dashboard", default="🔄 Refresh Dashboard"), command=self.refresh_dashboard)
        refresh_btn.pack(pady=10)

    def create_stat_card(self, parent, title, value, color, column):
        """Create a statistic card"""
        card_frame = ttk.LabelFrame(parent, text=title, padding=15)
        card_frame.grid(row=0, column=column, padx=10, sticky='ew')
        parent.grid_columnconfigure(column, weight=1)

        value_label = ttk.Label(card_frame, text=str(value), font=('Arial', 24, 'bold'))
        value_label.pack()

    def generate_report_dialog(self):
        """Show report generation dialog"""
        self.gui.show_reports()  # Navigate to reports section

    def create_status_chart(self, parent):
        """Create document status distribution chart"""
        chart_frame = ttk.LabelFrame(parent, text="Document Status Distribution", padding=10)
        chart_frame.pack(side='left', fill='both', expand=True, padx=(0, 10))

        # Get status data
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT verification_status, COUNT(*) as count
            FROM student_documents
            WHERE is_current_version = 1
            GROUP BY verification_status
            ORDER BY count DESC
            ''')

            status_data = cursor.fetchall()
            conn.close()

            if status_data:
                # Create simple text-based chart
                total = sum(count for _, count in status_data)

                for status, count in status_data:
                    percentage = (count / total) * 100 if total > 0 else 0

                    row_frame = ttk.Frame(chart_frame)
                    row_frame.pack(fill='x', pady=2)

                    ttk.Label(row_frame, text=f"{status}:", width=15).pack(side='left')
                    ttk.Label(row_frame, text=f"{count} ({percentage:.1f}%)").pack(side='left')

                    # Simple progress bar
                    progress = ttk.Progressbar(row_frame, length=200, mode='determinate')
                    progress['value'] = percentage
                    progress.pack(side='right', padx=10)
            else:
                ttk.Label(chart_frame, text="No data available").pack()

        except sqlite3.Error as e:
            ttk.Label(chart_frame, text=f"Error loading data: {e}").pack()

    def create_recent_activity_table(self, parent):
        """Create recent activity table"""
        activity_frame = ttk.LabelFrame(parent, text="Recent Activity", padding=10)
        activity_frame.pack(side='right', fill='both', expand=True)

        # Create treeview for recent activity
        columns = ('Student', 'Document', 'Action', 'Date')
        self.gui.activity_tree = ttk.Treeview(activity_frame, columns=columns, show='headings', height=10)

        # Define headings
        for col in columns:
            self.gui.activity_tree.heading(col, text=col)
            self.gui.activity_tree.column(col, width=120)

        # Add scrollbar
        scrollbar = ttk.Scrollbar(activity_frame, orient='vertical', command=self.gui.activity_tree.yview)
        self.gui.activity_tree.configure(yscrollcommand=scrollbar.set)

        # Pack widgets
        self.gui.activity_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Load recent activity data
        self.load_recent_activity()

    def load_recent_activity(self):
        """Load recent activity data"""
        # Check if activity_tree exists before using it
        if not hasattr(self.gui, 'activity_tree') or self.gui.activity_tree is None:
            return

        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT s.first_name || ' ' || s.last_name as student_name,
                   dt.type_name, 'Uploaded' as action,
                   DATE(sd.upload_date) as activity_date
            FROM student_documents sd
            JOIN students s ON sd.student_id = s.student_id
            JOIN document_types dt ON sd.type_id = dt.type_id
            WHERE sd.upload_date >= date('now', '-7 days')
            ORDER BY sd.upload_date DESC
            LIMIT 15
            ''')

            activities = cursor.fetchall()
            conn.close()

            # Clear existing items
            for item in self.gui.activity_tree.get_children():
                self.gui.activity_tree.delete(item)

            # Insert new items
            for activity in activities:
                self.gui.activity_tree.insert('', 'end', values=activity)

        except sqlite3.Error as e:
            print(f"Database error loading activity: {e}")
        except Exception as e:
            print(f"Error loading activity: {e}")

    def get_dashboard_stats(self):
        """Get dashboard statistics"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Total documents
            cursor.execute('SELECT COUNT(*) FROM student_documents WHERE is_current_version = 1')
            total_docs = cursor.fetchone()[0]

            # Pending documents
            cursor.execute('SELECT COUNT(*) FROM student_documents WHERE verification_status = "Pending" AND is_current_version = 1')
            pending_docs = cursor.fetchone()[0]

            # Total students
            cursor.execute('SELECT COUNT(*) FROM students')
            total_students = cursor.fetchone()[0]

            # Today's uploads
            today = datetime.now().strftime('%Y-%m-%d')
            cursor.execute('SELECT COUNT(*) FROM student_documents WHERE DATE(upload_date) = ?', (today,))
            today_uploads = cursor.fetchone()[0]

            conn.close()

            return {
                'total_docs': total_docs,
                'pending_docs': pending_docs,
                'total_students': total_students,
                'today_uploads': today_uploads
            }

        except Exception as e:
            print(f"Error getting dashboard stats: {e}")
            return {'total_docs': 0, 'pending_docs': 0, 'total_students': 0, 'today_uploads': 0}

    def refresh_dashboard(self):
        """Refresh dashboard data"""
        try:
            # Only refresh if the activity tree exists
            if hasattr(self.gui, 'activity_tree') and self.gui.activity_tree is not None:
                self.load_recent_activity()
            self.gui.status_var.set("Dashboard refreshed")
        except Exception as e:
            print(f"Error refreshing dashboard: {e}")
            if hasattr(self.gui, 'status_var'):
                self.gui.status_var.set("Error refreshing dashboard")

    def display_dashboard(self):
        """Display main dashboard with statistics and overview"""
        if not self.gui.ensure_login():
            return

        # Create dashboard window
        dashboard_window = tk.Toplevel(self.root)
        dashboard_window.title("Document Manager Dashboard")
        dashboard_window.geometry("1200x800")
        dashboard_window.transient(self.root)
        dashboard_window.grab_set()

        # Title
        title_label = ttk.Label(dashboard_window, text="Document Manager Dashboard",
                               font=("Arial", 18, "bold"))
        title_label.pack(pady=10)

        # Create notebook for different dashboard sections
        notebook = ttk.Notebook(dashboard_window)
        notebook.pack(fill='both', expand=True, padx=10, pady=5)

        # Tab 1: Overview
        overview_frame = ttk.Frame(notebook, padding=10)
        notebook.add(overview_frame, text="Overview")

        # Quick stats at top
        stats_frame = ttk.Frame(overview_frame)
        stats_frame.pack(fill='x', pady=(0, 10))
        self.display_quick_stats(stats_frame)

        # Status overview
        status_frame = ttk.LabelFrame(overview_frame, text="Status Overview", padding=10)
        status_frame.pack(fill='both', expand=True, pady=5)
        self.display_status_overview(status_frame)

        # Tab 2: Recent Activity
        activity_frame = ttk.Frame(notebook, padding=10)
        notebook.add(activity_frame, text="Recent Activity")
        self.display_recent_activity(activity_frame)

        # Tab 3: Expiry Alerts
        alerts_frame = ttk.Frame(notebook, padding=10)
        notebook.add(alerts_frame, text="Expiry Alerts")
        self.gui.display_expiry_alerts(alerts_frame)

        # Tab 4: Performance Metrics
        performance_frame = ttk.Frame(notebook, padding=10)
        notebook.add(performance_frame, text="Performance")
        self.display_performance_metrics(performance_frame)

        # Close button
        ttk.Button(dashboard_window, text="Close",
                  command=dashboard_window.destroy).pack(pady=10)

        # Log activity
        self.gui.log_event('view', 'dashboard', details='Opened main dashboard')

    def display_quick_stats(self, parent_frame):
        """Display quick statistics cards"""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()

                # Total documents
                cursor.execute("SELECT COUNT(*) FROM documents")
                total_docs = cursor.fetchone()[0]

                # Pending documents
                cursor.execute("SELECT COUNT(*) FROM documents WHERE status = 'Pending'")
                pending_docs = cursor.fetchone()[0]

                # Approved documents
                cursor.execute("SELECT COUNT(*) FROM documents WHERE status = 'Approved'")
                approved_docs = cursor.fetchone()[0]

                # Documents expiring soon (30 days)
                cursor.execute("""
                    SELECT COUNT(*) FROM documents
                    WHERE expiry_date IS NOT NULL
                    AND DATE(expiry_date) BETWEEN DATE('now') AND DATE('now', '+30 days')
                """)
                expiring_soon = cursor.fetchone()[0]

            # Create stat cards
            cards = [
                ("Total Documents", total_docs, "#3498db"),
                ("Pending Review", pending_docs, "#f39c12"),
                ("Approved", approved_docs, "#27ae60"),
                ("Expiring Soon", expiring_soon, "#e74c3c")
            ]

            for idx, (title, value, color) in enumerate(cards):
                card_frame = tk.Frame(parent_frame, bg=color, relief='raised', bd=2)
                card_frame.pack(side='left', fill='both', expand=True, padx=5)

                value_label = tk.Label(card_frame, text=str(value), font=("Arial", 24, "bold"),
                                      bg=color, fg='white')
                value_label.pack(pady=(10, 0))

                title_label = tk.Label(card_frame, text=title, font=("Arial", 10),
                                      bg=color, fg='white')
                title_label.pack(pady=(0, 10))

        except Exception as e:
            ttk.Label(parent_frame, text=f"Error loading stats: {e}").pack()

    def display_status_overview(self, parent_frame):
        """Display status breakdown with pie chart representation"""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT status, COUNT(*) as count
                    FROM documents
                    GROUP BY status
                    ORDER BY count DESC
                """)
                status_data = cursor.fetchall()

            if not status_data:
                ttk.Label(parent_frame, text="No document data available").pack()
                return

            # Create treeview for status breakdown
            tree = ttk.Treeview(parent_frame, columns=('Status', 'Count', 'Percentage'),
                               show='headings', height=8)
            tree.heading('Status', text='Status')
            tree.heading('Count', text='Document Count')
            tree.heading('Percentage', text='Percentage')

            tree.column('Status', width=150)
            tree.column('Count', width=150)
            tree.column('Percentage', width=150)

            total = sum(count for _, count in status_data)

            for status, count in status_data:
                percentage = (count / total * 100) if total > 0 else 0
                tree.insert('', 'end', values=(status, count, f"{percentage:.1f}%"))

            tree.pack(fill='both', expand=True, pady=5)

            # Total label
            ttk.Label(parent_frame, text=f"Total Documents: {total}",
                     font=("Arial", 11, "bold")).pack(pady=5)

        except Exception as e:
            ttk.Label(parent_frame, text=f"Error loading status data: {e}").pack()

    def display_recent_activity(self, parent_frame):
        """Display recent activity feed"""
        try:
            # Title
            ttk.Label(parent_frame, text="Recent Activity (Last 50 actions)",
                     font=("Arial", 12, "bold")).pack(pady=5)

            # Create treeview for activity log
            tree = ttk.Treeview(parent_frame,
                               columns=('Time', 'User', 'Action', 'Entity', 'Details'),
                               show='headings', height=20)
            tree.heading('Time', text='Timestamp')
            tree.heading('User', text='User')
            tree.heading('Action', text='Action')
            tree.heading('Entity', text='Entity Type')
            tree.heading('Details', text='Details')

            tree.column('Time', width=150)
            tree.column('User', width=120)
            tree.column('Action', width=100)
            tree.column('Entity', width=120)
            tree.column('Details', width=250)

            scrollbar = ttk.Scrollbar(parent_frame, orient='vertical', command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)

            # Fetch recent activity
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT timestamp, username, action, entity_type, details
                    FROM activity_log
                    ORDER BY timestamp DESC
                    LIMIT 50
                """)
                activities = cursor.fetchall()

            for activity in activities:
                timestamp, user, action, entity, details = activity
                # Truncate details if too long
                if details and len(details) > 50:
                    details = details[:47] + "..."
                tree.insert('', 'end', values=(timestamp, user, action, entity, details or ''))

            tree.pack(side='left', fill='both', expand=True, pady=5)
            scrollbar.pack(side='right', fill='y', pady=5)

            # Export button
            ttk.Button(parent_frame, text="Export Activity Log",
                      command=lambda: self.gui.export_activity_log()).pack(pady=5)

        except Exception as e:
            ttk.Label(parent_frame, text=f"Error loading activity: {e}").pack()

    def display_performance_metrics(self, parent_frame):
        """Display performance metrics"""
        try:
            # Title
            ttk.Label(parent_frame, text="System Performance Metrics",
                     font=("Arial", 12, "bold")).pack(pady=5)

            with get_connection() as conn:
                cursor = conn.cursor()

                # Documents per day (last 30 days)
                cursor.execute("""
                    SELECT DATE(upload_date) as day, COUNT(*) as count
                    FROM documents
                    WHERE upload_date >= DATE('now', '-30 days')
                    GROUP BY DATE(upload_date)
                    ORDER BY day DESC
                """)
                daily_uploads = cursor.fetchall()

                # Average processing time (simulated)
                cursor.execute("""
                    SELECT AVG(
                        JULIANDAY(COALESCE(
                            (SELECT MAX(timestamp) FROM activity_log
                             WHERE entity_type = 'document'
                             AND entity_id = documents.id
                             AND action = 'approve'),
                            DATE('now')
                        )) - JULIANDAY(upload_date)
                    ) as avg_days
                    FROM documents
                    WHERE status = 'Approved'
                """)
                avg_processing = cursor.fetchone()[0] or 0

                # Documents by type
                cursor.execute("""
                    SELECT document_type, COUNT(*) as count
                    FROM documents
                    GROUP BY document_type
                    ORDER BY count DESC
                """)
                type_distribution = cursor.fetchall()

            # Create metrics display
            metrics_frame = ttk.Frame(parent_frame)
            metrics_frame.pack(fill='both', expand=True, pady=5)

            # Left column - Stats
            left_frame = ttk.LabelFrame(metrics_frame, text="Key Metrics", padding=10)
            left_frame.pack(side='left', fill='both', expand=True, padx=(0, 5))

            ttk.Label(left_frame, text=f"Average Processing Time: {avg_processing:.1f} days",
                     font=("Arial", 10)).pack(anchor='w', pady=5)
            ttk.Label(left_frame, text=f"Total Upload Days: {len(daily_uploads)}",
                     font=("Arial", 10)).pack(anchor='w', pady=5)

            if daily_uploads:
                avg_daily = sum(count for _, count in daily_uploads) / len(daily_uploads)
                ttk.Label(left_frame, text=f"Avg Documents/Day: {avg_daily:.1f}",
                         font=("Arial", 10)).pack(anchor='w', pady=5)

            # Daily uploads table
            daily_frame = ttk.LabelFrame(left_frame, text="Daily Uploads (Last 30 Days)", padding=5)
            daily_frame.pack(fill='both', expand=True, pady=10)

            daily_tree = ttk.Treeview(daily_frame, columns=('Date', 'Count'),
                                     show='headings', height=8)
            daily_tree.heading('Date', text='Date')
            daily_tree.heading('Count', text='Documents Uploaded')
            daily_tree.column('Date', width=150)
            daily_tree.column('Count', width=150)

            for date, count in daily_uploads:
                daily_tree.insert('', 'end', values=(date, count))

            daily_tree.pack(fill='both', expand=True)

            # Right column - Type distribution
            right_frame = ttk.LabelFrame(metrics_frame, text="Document Type Distribution", padding=10)
            right_frame.pack(side='right', fill='both', expand=True, padx=(5, 0))

            type_tree = ttk.Treeview(right_frame, columns=('Type', 'Count', 'Percentage'),
                                    show='headings', height=15)
            type_tree.heading('Type', text='Document Type')
            type_tree.heading('Count', text='Count')
            type_tree.heading('Percentage', text='Percentage')

            type_tree.column('Type', width=150)
            type_tree.column('Count', width=100)
            type_tree.column('Percentage', width=100)

            total_types = sum(count for _, count in type_distribution)
            for doc_type, count in type_distribution:
                percentage = (count / total_types * 100) if total_types > 0 else 0
                type_tree.insert('', 'end', values=(doc_type, count, f"{percentage:.1f}%"))

            type_tree.pack(fill='both', expand=True)

            # Export button
            ttk.Button(parent_frame, text="Export Performance Report",
                      command=lambda: self.export_performance_report()).pack(pady=5)

        except Exception as e:
            ttk.Label(parent_frame, text=f"Error loading performance metrics: {e}").pack()

    def export_performance_report(self):
        """Export performance metrics report"""
        messagebox.showinfo("Export Performance Report",
                          "Performance report will be generated and exported to CSV/PDF")
        self.gui.log_event('export', 'performance_report',
                      details='Exported system performance report')
