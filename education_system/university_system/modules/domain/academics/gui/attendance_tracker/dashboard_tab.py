import tkinter as tk
from tkinter import ttk, messagebox
import datetime
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# Import internationalization support
from education_system.university_system.modules.shared.utils.i18n import get_text as _, init_i18n
init_i18n()

# Import main database connection
try:
    from education_system.university_system.infrastructure.database.db import get_db_connection
    MAIN_DB_AVAILABLE = True
except ImportError:
    MAIN_DB_AVAILABLE = False

ORIGINAL_FUNCTIONS_AVAILABLE = MAIN_DB_AVAILABLE


def create_sample_charts(self):
        """Create sample charts when no data is available"""
        # Sample trend data
        self.trend_ax.clear()
        dates = pd.date_range(start=datetime.date.today()-datetime.timedelta(days=30),
                             end=datetime.date.today(), freq='D')
        rates = [85 + (i % 10) - 5 for i in range(len(dates))]

        self.trend_ax.plot(dates, rates, marker='o', linewidth=2, markersize=4)
        self.trend_ax.set_title(_("attendance.charts.trend_title_sample"))
        self.trend_ax.set_ylabel(_("attendance.charts.attendance_rate"))
        self.trend_ax.grid(True, alpha=0.3)
        self.trend_fig.tight_layout()
        self.trend_canvas.draw()

        # Sample distribution data
        self.dist_ax.clear()
        statuses = [_("attendance.present"), _("attendance.late"), _("attendance.absent"), _("attendance.excused")]
        counts = [70, 15, 10, 5]
        colors = ['green', 'yellow', 'red', 'blue']

        self.dist_ax.pie(counts, labels=statuses, colors=colors, autopct='%1.1f%%', startangle=90)
        self.dist_ax.set_title(_("attendance.charts.distribution_title_sample"))
        self.dist_fig.tight_layout()
        self.dist_canvas.draw()

def update_dashboard_stats(self):
        """Update dashboard statistics"""
        try:
            if not ORIGINAL_FUNCTIONS_AVAILABLE:
                # Sample data
                self.stat_cards['total_students'].config(text="125")
                self.stat_cards['active_modules'].config(text="8")
                self.stat_cards['todays_sessions'].config(text="12")
                self.stat_cards['overall_attendance'].config(text="87.5%")
                return

            conn = get_db_connection()
            cursor = conn.cursor()

            # Total students
            cursor.execute("SELECT COUNT(*) FROM students")
            total_students = cursor.fetchone()[0]
            self.stat_cards['total_students'].config(text=str(total_students))

            # Active modules
            cursor.execute("SELECT COUNT(DISTINCT module_code) FROM attendance_records")
            active_modules = cursor.fetchone()[0]
            self.stat_cards['active_modules'].config(text=str(active_modules))

            # Today's sessions
            today = datetime.date.today().isoformat()
            cursor.execute("SELECT COUNT(*) FROM attendance_sessions WHERE date = ? AND status = 'active'", (today,))
            todays_sessions = cursor.fetchone()[0]
            self.stat_cards['todays_sessions'].config(text=str(todays_sessions))

            # Overall attendance rate
            cursor.execute('''
            SELECT AVG(CASE WHEN status IN ('Present', 'Late') THEN 1.0 ELSE 0.0 END) * 100
            FROM attendance_records
            WHERE date >= date('now', '-30 days')
            ''')
            overall_rate = cursor.fetchone()[0] or 0
            self.stat_cards['overall_attendance'].config(text=f"{overall_rate:.1f}%")

            conn.close()

        except Exception as e:
            print(f"Error updating dashboard stats: {e}")
            # Set default values
            for key in self.stat_cards:
                self.stat_cards[key].config(text="--")

def create_dashboard_tab(self):
        """Create dashboard tab"""
        dashboard_frame = ttk.Frame(self.notebook)
        self.notebook.add(dashboard_frame, text=_("attendance.tabs.dashboard"))

        # Quick stats frame
        stats_frame = ttk.LabelFrame(dashboard_frame, text=_("attendance.dashboard.quick_statistics"), padding=10)
        stats_frame.pack(fill=tk.X, pady=(0, 10))

        # Stats grid
        stats_grid = ttk.Frame(stats_frame)
        stats_grid.pack(fill=tk.X)

        # Create stat cards
        self.stat_cards = {}
        stat_names = [
            (_("attendance.dashboard.total_students"), "total_students"),
            (_("attendance.dashboard.active_modules"), "active_modules"),
            (_("attendance.dashboard.todays_sessions"), "todays_sessions"),
            (_("attendance.dashboard.overall_attendance"), "overall_attendance")
        ]

        for i, (name, key) in enumerate(stat_names):
            card_frame = ttk.Frame(stats_grid, relief=tk.RAISED, borderwidth=1)
            card_frame.grid(row=0, column=i, padx=5, pady=5, sticky="ew")
            stats_grid.grid_columnconfigure(i, weight=1)

            ttk.Label(card_frame, text=name, font=('Arial', 10, 'bold')).pack(pady=(5, 0))
            value_label = ttk.Label(card_frame, text="--", font=('Arial', 16, 'bold'))
            value_label.pack(pady=(0, 5))

            self.stat_cards[key] = value_label

        # Charts frame
        charts_frame = ttk.Frame(dashboard_frame)
        charts_frame.pack(fill=tk.BOTH, expand=True)

        # Left chart frame
        left_chart_frame = ttk.LabelFrame(charts_frame, text=_("attendance.dashboard.attendance_trends"), padding=5)
        left_chart_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        # Right chart frame
        right_chart_frame = ttk.LabelFrame(charts_frame, text=_("attendance.dashboard.status_distribution"), padding=5)
        right_chart_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))

        # Create matplotlib figures
        self.create_dashboard_charts(left_chart_frame, right_chart_frame)

        # Recent activity frame
        activity_frame = ttk.LabelFrame(dashboard_frame, text=_("attendance.dashboard.recent_activity"), padding=10)
        activity_frame.pack(fill=tk.X, pady=(10, 0))

        # Activity treeview
        activity_columns = (_("attendance.columns.time"), _("attendance.columns.student"), _("attendance.columns.module"), _("attendance.columns.status"), _("attendance.columns.method"))
        self.activity_tree = ttk.Treeview(activity_frame, columns=activity_columns, show="headings", height=6)

        for col in activity_columns:
            self.activity_tree.heading(col, text=col)
            self.activity_tree.column(col, width=120)

        activity_scrollbar = ttk.Scrollbar(activity_frame, orient=tk.VERTICAL, command=self.activity_tree.yview)
        self.activity_tree.configure(yscrollcommand=activity_scrollbar.set)

        self.activity_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        activity_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

def refresh_recent_activity(self):
        """Refresh recent activity list"""
        try:
            # Clear existing items
            for item in self.activity_tree.get_children():
                self.activity_tree.delete(item)

            if not ORIGINAL_FUNCTIONS_AVAILABLE:
                # Sample data
                sample_activities = [
                    ("09:15", "S001 John Doe", "CS101", "Present", "QR Code"),
                    ("09:20", "S002 Jane Smith", "CS101", "Late", "Manual"),
                    ("10:30", "S003 Bob Wilson", "CS102", "Present", "Face Recognition"),
                ]

                for activity in sample_activities:
                    self.activity_tree.insert('', 'end', values=activity)
                return

            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT ar.recorded_at, s.first_name || ' ' || s.last_name || ' (' || ar.student_id || ')' as student,
                   ar.module_code, ar.status, COALESCE(ar.check_in_method, 'manual') as method
            FROM attendance_records ar
            JOIN students s ON ar.student_id = s.student_id
            WHERE ar.recorded_at >= datetime('now', '-24 hours')
            ORDER BY ar.recorded_at DESC
            LIMIT 20
            ''')

            activities = cursor.fetchall()

            for activity in activities:
                recorded_at, student, module_code, status, method = activity
                time_str = recorded_at.split('T')[1][:5] if 'T' in recorded_at else recorded_at[-8:-3]

                self.activity_tree.insert('', 'end', values=(time_str, student, module_code, status, method))

            conn.close()

        except Exception as e:
            print(f"Error refreshing recent activity: {e}")

def update_dashboard_charts(self):
        """Update dashboard charts with current data"""
        try:
            if not ORIGINAL_FUNCTIONS_AVAILABLE:
                # Create sample data for demonstration
                self.create_sample_charts()
                return

            # Get attendance trends data
            conn = get_db_connection()

            # Trend data - last 30 days
            trend_query = '''
            SELECT date,
                   AVG(CASE WHEN status IN ('Present', 'Late') THEN 1.0 ELSE 0.0 END) * 100 as rate
            FROM attendance_records
            WHERE date >= date('now', '-30 days')
            GROUP BY date
            ORDER BY date
            '''

            trend_df = pd.read_sql_query(trend_query, conn)

            # Clear and update trend chart
            self.trend_ax.clear()
            if not trend_df.empty:
                self.trend_ax.plot(pd.to_datetime(trend_df['date']), trend_df['rate'],
                                 marker='o', linewidth=2, markersize=4)
                self.trend_ax.set_title(_("attendance.charts.trend_title"))
                self.trend_ax.set_ylabel(_("attendance.charts.attendance_rate"))
                self.trend_ax.grid(True, alpha=0.3)

                # Add threshold lines
                threshold_warning = 80
                threshold_critical = 70
                self.trend_ax.axhline(y=threshold_warning, color='orange', linestyle='--', alpha=0.7)
                self.trend_ax.axhline(y=threshold_critical, color='red', linestyle='--', alpha=0.7)
            else:
                self.trend_ax.text(0.5, 0.5, _("attendance.charts.no_data"),
                                 transform=self.trend_ax.transAxes, ha='center', va='center')

            self.trend_fig.tight_layout()
            self.trend_canvas.draw()

            # Status distribution data
            status_query = '''
            SELECT status, COUNT(*) as count
            FROM attendance_records
            WHERE date >= date('now', '-7 days')
            GROUP BY status
            '''

            status_df = pd.read_sql_query(status_query, conn)

            # Clear and update distribution chart
            self.dist_ax.clear()
            if not status_df.empty:
                colors = {'Present': 'green', 'Late': 'yellow', 'Excused': 'blue', 'Absent': 'red'}
                pie_colors = [colors.get(status, 'gray') for status in status_df['status']]

                self.dist_ax.pie(status_df['count'], labels=status_df['status'],
                               colors=pie_colors, autopct='%1.1f%%', startangle=90)
                self.dist_ax.set_title(_("attendance.charts.distribution_title"))
            else:
                self.dist_ax.text(0.5, 0.5, _("attendance.charts.no_data"),
                                transform=self.dist_ax.transAxes, ha='center', va='center')

            self.dist_fig.tight_layout()
            self.dist_canvas.draw()

            conn.close()

        except Exception as e:
            self.create_sample_charts()
            print(f"Error updating charts: {e}")

def create_dashboard_charts(self, left_frame, right_frame):
        """Create dashboard charts"""
        # Left chart - Attendance trends
        self.trend_fig, self.trend_ax = plt.subplots(figsize=(6, 4))
        self.trend_canvas = FigureCanvasTkAgg(self.trend_fig, left_frame)
        self.trend_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # Right chart - Status distribution
        self.dist_fig, self.dist_ax = plt.subplots(figsize=(6, 4))
        self.dist_canvas = FigureCanvasTkAgg(self.dist_fig, right_frame)
        self.dist_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # Initialize charts with sample data
        self.update_dashboard_charts()

