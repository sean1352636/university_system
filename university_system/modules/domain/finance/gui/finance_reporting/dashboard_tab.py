import tkinter as tk
from tkinter.scrolledtext import ScrolledText
from tkinter import ttk, messagebox, filedialog, scrolledtext
from tkinter.font import Font
import threading
from datetime import datetime, timedelta
import json
import webbrowser
from pathlib import Path
import matplotlib
from university_system.modules.shared.constants import paths
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import numpy as np

# Import auth instance management from user_authentication
try:
    from university_system.infrastructure.auth import get_current_user, set_auth_instance
    HAS_AUTH = True
except ImportError:
    HAS_AUTH = False
    get_current_user = lambda: None
    set_auth_instance = lambda x: None

auth = None

def set_auth(auth_instance):
    global auth
    auth = auth_instance
    # Also set it in the global auth instance if available
    if HAS_AUTH:
        set_auth_instance(auth_instance)
# Import the shared authentication system
try:
    from university_system.infrastructure.auth import UserAuth
    from university_system.infrastructure.shared_context import get_auth
except ImportError as e:
    print(f"⚠️ Could not import UserAuth: {e}")
    UserAuth = None
    get_auth = lambda: None

from university_system.modules.shared.utils.i18n import get_text as _, init_i18n
init_i18n()


# This module defines mixin functions for FinancialManagementGUI
# Note: Methods are registered by main.py to avoid circular imports

def create_dashboard_tab(self):
    """Create dashboard tab with key metrics"""
    dashboard_frame = ttk.Frame(self.notebook, padding="10")
    self.notebook.add(dashboard_frame, text=_("finance_reporting.tabs.dashboard"))

    # Dashboard title
    ttk.Label(dashboard_frame, text=_("finance_reporting.dashboard.title"),
             style='Heading.TLabel').grid(row=0, column=0, columnspan=3, pady=(0, 20))

    # Key metrics frame
    metrics_frame = ttk.LabelFrame(dashboard_frame, text=_("finance_reporting.dashboard.key_metrics"), padding="10")
    metrics_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))

    # Create metric displays
    self.metric_vars = {}
    metrics = [
        (_("finance_reporting.metrics.total_revenue"), 'total_revenue'),
        (_("finance_reporting.metrics.collection_rate"), 'collection_rate'),
        (_("finance_reporting.metrics.active_students"), 'active_students'),
        (_("finance_reporting.metrics.overdue_amount"), 'overdue_amount'),
        (_("finance_reporting.metrics.today_payments"), 'today_payments'),
        (_("finance_reporting.metrics.alert_count"), 'alert_count')
    ]

    for i, (label, var_name) in enumerate(metrics):
        row = i // 3
        col = i % 3

        metric_frame = ttk.Frame(metrics_frame)
        metric_frame.grid(row=row, column=col, padx=10, pady=5, sticky=(tk.W, tk.E))

        ttk.Label(metric_frame, text=label, font=('Arial', 10, 'bold')).grid(row=0, column=0)

        self.metric_vars[var_name] = tk.StringVar(value=_("finance_reporting.status.loading"))
        ttk.Label(metric_frame, textvariable=self.metric_vars[var_name],
                 font=('Arial', 12), foreground='#2980b9').grid(row=1, column=0)

    # Quick actions frame
    actions_frame = ttk.LabelFrame(dashboard_frame, text=_("finance_reporting.dashboard.quick_actions"), padding="10")
    actions_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))

    # Action buttons
    action_buttons = [
        (_("finance_reporting.actions.generate_forecast"), self.run_advanced_forecasting),
        (_("finance_reporting.actions.risk_analysis"), self.run_risk_analysis),
        (_("finance_reporting.actions.export_report"), self.export_quick_report),
        (_("finance_reporting.actions.view_alerts"), self.show_alerts),
        (_("finance_reporting.actions.compliance_check"), self.run_compliance_check),
        (_("finance_reporting.actions.system_health"), self.show_system_health)
    ]

    for i, (text, command) in enumerate(action_buttons):
        row = i // 3
        col = i % 3
        ttk.Button(actions_frame, text=text, command=command, 
                  style='Accent.TButton').grid(row=row, column=col, padx=5, pady=5, sticky=(tk.W, tk.E))

    # Configure column weights
    actions_frame.grid_columnconfigure(0, weight=1)
    actions_frame.grid_columnconfigure(1, weight=1)
    actions_frame.grid_columnconfigure(2, weight=1)

    # Recent activity frame
    activity_frame = ttk.LabelFrame(dashboard_frame, text=_("finance_reporting.dashboard.recent_activity"), padding="10")
    activity_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))

    # Activity log
    self.activity_text = ScrolledText(activity_frame, height=8, wrap=tk.WORD)
    self.activity_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

    activity_frame.grid_rowconfigure(0, weight=1)
    activity_frame.grid_columnconfigure(0, weight=1)
    dashboard_frame.grid_rowconfigure(3, weight=1)

    # Load initial dashboard data
    self.update_dashboard_metrics()

def real_time_financial_dashboard(self):
    """Enhanced real-time financial dashboard with live metrics - displays charts in window"""
    try:
        from university_system.infrastructure.database.db import get_connection

        # Create figure
        fig = Figure(figsize=(16, 10))

        with get_connection() as conn:
            cursor = conn.cursor()

            # Get current metrics
            cursor.execute("""
                SELECT COALESCE(SUM(amount), 0) as total_revenue
                FROM payments
            """)
            total_revenue = cursor.fetchone()[0] or 0

            # Add club payments to total revenue
            try:
                cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM club_payments WHERE status = 'completed'")
                total_revenue += cursor.fetchone()[0] or 0
            except Exception:
                pass

            # Add housing payments to total revenue
            try:
                cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM housing_payments WHERE status = 'completed'")
                total_revenue += cursor.fetchone()[0] or 0
            except Exception:
                pass

            cursor.execute("""
                SELECT COALESCE(SUM(amount), 0) as today_collections
                FROM payments
                WHERE date(payment_date) = date('now')
            """)
            today_collections = cursor.fetchone()[0] or 0

            cursor.execute("""
                SELECT COALESCE(SUM(amount), 0) as outstanding
                FROM student_fees
                WHERE status = 'pending' OR status = 'unpaid'
            """)
            outstanding = cursor.fetchone()[0] or 0

            # Add library fines to outstanding
            try:
                cursor.execute("""
                    SELECT COALESCE(SUM(fine_amount), 0)
                    FROM book_loans
                    WHERE fine_amount > 0 AND (status = 'active' OR status = 'overdue')
                """)
                outstanding += cursor.fetchone()[0] or 0
            except Exception:
                pass

            # Add late fees to outstanding
            try:
                cursor.execute("SELECT COALESCE(SUM(late_fee_amount), 0) FROM late_fees WHERE waived = 0")
                outstanding += cursor.fetchone()[0] or 0
            except Exception:
                pass

            # Get last 30 days daily collections
            cursor.execute("""
                SELECT
                    date(payment_date) as day,
                    SUM(amount) as daily_total
                FROM payments
                WHERE payment_date >= date('now', '-30 days')
                GROUP BY day
                ORDER BY day
            """)
            daily_data = cursor.fetchall()

            # Get payment status distribution
            cursor.execute("""
                SELECT
                    f.status,
                    COUNT(*) as count,
                    SUM(f.amount) as total
                FROM student_fees f
                GROUP BY f.status
            """)
            status_data = cursor.fetchall()

        # Plot 1: Real-time Metrics
        ax1 = fig.add_subplot(2, 2, 1)
        ax1.axis('off')

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        metrics_text = f"""
        REAL-TIME FINANCIAL DASHBOARD
        Last Updated: {current_time}

        Live Metrics:
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        • Current Revenue:     £{total_revenue:,.2f}
        • Today's Collections: £{today_collections:,.2f}
        • Outstanding Fees:    £{outstanding:,.2f}

        Collection Rate:       {(total_revenue/(total_revenue+outstanding)*100):.1f}%
        Status:                ✓ Operational
        """

        ax1.text(0.1, 0.9, metrics_text, transform=ax1.transAxes,
                fontsize=11, verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.3),
                family='monospace', fontweight='bold')

        # Plot 2: Daily Collections (Last 30 Days)
        if daily_data:
            ax2 = fig.add_subplot(2, 2, 2)
            days = [row[0] for row in daily_data]
            amounts = [float(row[1]) for row in daily_data]
            ax2.plot(days, amounts, marker='o', linewidth=2, color='#3498db')
            ax2.fill_between(range(len(days)), amounts, alpha=0.3, color='#3498db')
            ax2.set_title('Daily Collections Trend (30 Days)', fontsize=12, fontweight='bold')
            ax2.set_xlabel('Date')
            ax2.set_ylabel('Amount (£)')
            ax2.tick_params(axis='x', rotation=45)
            ax2.grid(True, alpha=0.3)

        # Plot 3: Payment Status Distribution
        if status_data:
            ax3 = fig.add_subplot(2, 2, 3)
            statuses = [row[0] for row in status_data]
            counts = [row[1] for row in status_data]
            colors_map = {'paid': '#2ecc71', 'pending': '#f39c12', 'unpaid': '#e74c3c', 'overdue': '#c0392b'}
            colors = [colors_map.get(s.lower(), '#95a5a6') for s in statuses]
            ax3.pie(counts, labels=statuses, autopct='%1.1f%%', colors=colors, startangle=90)
            ax3.set_title('Payment Status Distribution', fontsize=12, fontweight='bold')

        # Plot 4: Revenue vs Outstanding
        ax4 = fig.add_subplot(2, 2, 4)
        categories = ['Revenue\nCollected', 'Outstanding\nFees']
        values = [total_revenue, outstanding]
        colors = ['#2ecc71', '#e74c3c']
        ax4.bar(categories, values, color=colors, alpha=0.7, width=0.6)
        ax4.set_title('Revenue vs Outstanding Fees', fontsize=12, fontweight='bold')
        ax4.set_ylabel('Amount (£)')
        ax4.grid(True, alpha=0.3, axis='y')

        # Add value labels on bars
        for i, v in enumerate(values):
            ax4.text(i, v, f'£{v:,.0f}', ha='center', va='bottom', fontweight='bold')

        fig.tight_layout()

        # Show in window
        self.root.after(0, lambda: self.show_chart_window(
            "Real-Time Financial Dashboard",
            fig
        ))

    except Exception as e:
        messagebox.showerror(_("common.error"), _("finance_reporting.messages.dashboard_error").format(error=str(e)))
        print(f"Dashboard error: {e}")
        import traceback
        traceback.print_exc()

def update_dashboard_metrics(self):
    """Update dashboard metrics"""
    def update_in_background():
        try:
            from university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()

            # Total revenue
            cursor.execute('''
            SELECT SUM(sf.amount) as total_expected,
                   SUM(CASE WHEN sf.status = 'paid' THEN sf.amount ELSE 0 END) as total_collected
            FROM student_fees sf
            ''')
            revenue_data = cursor.fetchone()
            total_revenue = revenue_data[1] or 0
            collection_rate = (revenue_data[1] / revenue_data[0] * 100) if revenue_data[0] else 0

            # Active students
            cursor.execute('SELECT COUNT(DISTINCT student_id) FROM student_fees')
            active_students = cursor.fetchone()[0] or 0

            # Overdue amount
            cursor.execute('''
            SELECT SUM(amount) FROM student_fees
            WHERE status != 'paid' AND due_date < date('now')
            ''')
            overdue_amount = cursor.fetchone()[0] or 0

            # Today's payments
            today = datetime.now().strftime('%Y-%m-%d')
            cursor.execute('SELECT COUNT(*), SUM(amount) FROM payments WHERE payment_date = ?', (today,))
            today_data = cursor.fetchone()
            today_payments = f"{today_data[0]} (£{today_data[1] or 0:,.2f})"

            # Alert count
            cursor.execute('''
            SELECT COUNT(*) FROM financial_alerts
            WHERE created_at >= date('now', '-7 days') AND resolved_at IS NULL
            ''')
            alert_count = cursor.fetchone()[0] or 0

            conn.close()

            # Update GUI in main thread (with safety check)
            try:
                if self.root.winfo_exists():
                    self.root.after(0, lambda: self.set_metric_values({
                        'total_revenue': f"£{total_revenue:,.2f}",
                        'collection_rate': f"{collection_rate:.1f}%",
                        'active_students': f"{active_students:,}",
                        'overdue_amount': f"£{overdue_amount:,.2f}",
                        'today_payments': today_payments,
                        'alert_count': str(alert_count)
                    }))
            except Exception:
                pass  # Window was closed

        except Exception as e:
            try:
                if self.root.winfo_exists():
                    self.root.after(0, lambda err=e: self.log_activity(f"Error updating metrics: {err}"))
            except Exception:
                pass  # Window was closed

    thread = threading.Thread(target=update_in_background)
    thread.daemon = True
    thread.start()

def set_metric_values(self, values):
    """Set metric values in the GUI"""
    for key, value in values.items():
        if key in self.metric_vars:
            self.metric_vars[key].set(value)

def refresh_dashboard(self):
    """Refresh dashboard data"""
    self.update_status(_("finance_reporting.status.refreshing_dashboard"))
    self.update_dashboard_metrics()
    self.log_activity(_("finance_reporting.activity.dashboard_refreshed"))
    self.update_status(_("finance_reporting.status.ready"))

def show_realtime_dashboard(self):
    """Show real-time dashboard in new window"""
    dashboard_window = tk.Toplevel(self.root)
    dashboard_window.title(_("finance_reporting.windows.realtime_dashboard"))
    dashboard_window.geometry("1000x700")

    # Create dashboard content
    main_frame = ttk.Frame(dashboard_window, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)

    # Title
    ttk.Label(main_frame, text="Real-Time Financial Dashboard", 
             style='Title.TLabel').pack(pady=(0, 20))

    # Metrics frame
    metrics_frame = ttk.LabelFrame(main_frame, text="Live Metrics", padding="10")
    metrics_frame.pack(fill=tk.X, pady=(0, 10))

    # Real-time metrics display
    realtime_metrics = ttk.Frame(metrics_frame)
    realtime_metrics.pack(fill=tk.X)

    # Current hour payments
    hour_frame = ttk.Frame(realtime_metrics)
    hour_frame.pack(side=tk.LEFT, padx=10)
    ttk.Label(hour_frame, text="Current Hour", font=('Arial', 10, 'bold')).pack()
    hour_value = tk.StringVar(value="Loading...")
    ttk.Label(hour_frame, textvariable=hour_value, font=('Arial', 12), 
             foreground='#27ae60').pack()

    # Payment velocity
    velocity_frame = ttk.Frame(realtime_metrics)
    velocity_frame.pack(side=tk.LEFT, padx=10)
    ttk.Label(velocity_frame, text="Payment Velocity", font=('Arial', 10, 'bold')).pack()
    velocity_value = tk.StringVar(value="Loading...")
    ttk.Label(velocity_frame, textvariable=velocity_value, font=('Arial', 12), 
             foreground='#3498db').pack()

    # System status
    status_frame = ttk.Frame(realtime_metrics)
    status_frame.pack(side=tk.LEFT, padx=10)
    ttk.Label(status_frame, text="System Status", font=('Arial', 10, 'bold')).pack()
    system_status = tk.StringVar(value="Online")
    ttk.Label(status_frame, textvariable=system_status, font=('Arial', 12), 
             foreground='#27ae60').pack()

    # Activity log
    activity_frame = ttk.LabelFrame(main_frame, text="Live Activity", padding="10")
    activity_frame.pack(fill=tk.BOTH, expand=True)

    activity_log = ScrolledText(activity_frame, height=15, wrap=tk.WORD)
    activity_log.pack(fill=tk.BOTH, expand=True)

    # Store the after ID for cleanup
    after_id = None

    # Update real-time data
    def update_realtime():
        nonlocal after_id
        try:
            # Check if window still exists
            if not dashboard_window.winfo_exists():
                return

            from university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()

            # Current hour data
            current_hour = datetime.now().strftime('%Y-%m-%d %H:00:00')
            cursor.execute('''
            SELECT COUNT(*), SUM(amount) FROM payments
            WHERE payment_date >= ?
            ''', (current_hour,))
            hour_data = cursor.fetchone()
            hour_value.set(f"{hour_data[0]} payments\n£{hour_data[1] or 0:,.2f}")

            # Payment velocity
            cursor.execute('''
            SELECT COUNT(*) / COUNT(DISTINCT payment_date) as velocity
            FROM payments
            WHERE payment_date >= date('now', '-7 days')
            ''')
            velocity_data = cursor.fetchone()[0] or 0
            velocity_value.set(f"{velocity_data:.1f}\npayments/day")

            conn.close()

            # Add activity entry
            timestamp = datetime.now().strftime("%H:%M:%S")
            activity_log.insert(tk.END, f"[{timestamp}] Dashboard updated - {hour_data[0]} payments this hour\n")
            activity_log.see(tk.END)

        except Exception as e:
            try:
                activity_log.insert(tk.END, f"[ERROR] {e}\n")
            except:
                pass  # Window might be destroyed

        # Schedule next update only if window still exists
        try:
            if dashboard_window.winfo_exists():
                after_id = dashboard_window.after(30000, update_realtime)  # Update every 30 seconds
        except:
            pass  # Window destroyed

    # Cleanup function to cancel scheduled updates
    def on_closing():
        nonlocal after_id
        if after_id is not None:
            try:
                dashboard_window.after_cancel(after_id)
            except:
                pass
        dashboard_window.destroy()

    # Bind cleanup to window close
    dashboard_window.protocol("WM_DELETE_WINDOW", on_closing)

    # Start real-time updates
    update_realtime()

    # Auto-refresh button
    ttk.Button(main_frame, text="🔄 Manual Refresh",
              command=update_realtime).pack(pady=10)

# Method registration is handled by main.py
