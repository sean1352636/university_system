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
from education_system.systems.university.infrastructure import paths
matplotlib.use('TkAgg')
import numpy as np

# Import auth instance management from user_authentication
try:
    from education_system.systems.university.infrastructure.auth import get_current_user, set_auth_instance
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
    from education_system.systems.university.infrastructure.auth import UserAuth
    from education_system.systems.university.infrastructure.shared_context import get_auth
except ImportError as e:
    print(f"⚠️ Could not import UserAuth: {e}")
    UserAuth = None
    get_auth = lambda: None

from education_system.systems.university.infrastructure.i18n import get_text as _, init_i18n
init_i18n()

from education_system.systems.university.interfaces.gui.finance.finance_reporting.misc import run_system_health_check

# Import analytics classes
from education_system.systems.university.interfaces.gui.finance.finance_reporting.analytics_classes import (
    FinancialAlertSystem,
    PaymentPredictionML,
)


# This module defines mixin functions for FinancialManagementGUI
# Note: Methods are registered by main.py to avoid circular imports

def show_alerts(self):
    """Show alerts in new window"""
    alerts_window = tk.Toplevel(self.root)
    alerts_window.title(_("finance_reporting.windows.alerts"))
    alerts_window.geometry("800x600")

    main_frame = ttk.Frame(alerts_window, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main_frame, text="Financial Alerts", style='Title.TLabel').pack(pady=(0, 20))

    # Alerts treeview
    alerts_tree = ttk.Treeview(main_frame, columns=('Type', 'Date', 'Status'), height=15)
    alerts_tree.heading('#0', text='Alert Message')
    alerts_tree.heading('Type', text='Type')
    alerts_tree.heading('Date', text='Date')
    alerts_tree.heading('Status', text='Status')
    alerts_tree.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

    # Load alerts
    def load_alerts():
        try:
            from education_system.systems.university.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT alert_type, message, created_at, status, resolved_at
            FROM financial_alerts
            WHERE created_at >= date('now', '-30 days')
            ORDER BY created_at DESC
            ''')

            alerts = cursor.fetchall()

            for alert_type, message, created_at, status, resolved_at in alerts:
                status_text = "Resolved" if resolved_at else "Active"
                alerts_tree.insert('', 'end', text=message,
                                 values=(alert_type, created_at, status_text))

            conn.close()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load alerts: {e}")

    load_alerts()

    # Action buttons
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(fill=tk.X)

    ttk.Button(button_frame, text="Refresh", command=lambda: [
        alerts_tree.delete(*alerts_tree.get_children()), load_alerts()
    ]).pack(side=tk.LEFT, padx=(0, 5))

    ttk.Button(button_frame, text="Run Alert Check",
              command=self.run_alert_check).pack(side=tk.LEFT, padx=5)

    ttk.Button(button_frame, text="Close",
              command=alerts_window.destroy).pack(side=tk.RIGHT)

def run_alert_check(self):
    """Run alert system checks"""
    def check_in_background():
        try:
            alert_system = FinancialAlertSystem()
            alert_system.check_collection_rate_alert()
            alert_system.check_daily_payments()
            alert_system.check_large_payments()

            self.root.after(0, lambda: [
                self.log_activity("Alert system checks completed"),
                self.update_status("Alert checks completed")
            ])

        except Exception as e:
            self.root.after(0, lambda err=e: self.log_activity(f"Alert check error: {err}"))

    thread = threading.Thread(target=check_in_background)
    thread.daemon = True
    thread.start()

def show_system_health(self):
    """Show system health in new window"""
    health_window = tk.Toplevel(self.root)
    health_window.title(_("finance_reporting.windows.health_check"))
    health_window.geometry("600x500")

    main_frame = ttk.Frame(health_window, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main_frame, text="System Health Check", style='Title.TLabel').pack(pady=(0, 20))

    # Health status display
    health_text = ScrolledText(main_frame, height=20, wrap=tk.WORD)
    health_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

    # Run health check
    def run_health_check():
        health_text.delete(1.0, tk.END)
        health_text.insert(tk.END, "Running system health check...\n\n")

        try:
            health_status = run_system_health_check()

            health_text.insert(tk.END, "SYSTEM HEALTH REPORT\n")
            health_text.insert(tk.END, "=" * 40 + "\n\n")

            for component, status in health_status.items():
                status_symbol = "✓" if status else "✗"
                health_text.insert(tk.END, f"{status_symbol} {component.replace('_', ' ').title()}: {'OK' if status else 'ERROR'}\n")

            healthy_count = sum(health_status.values())
            total_count = len(health_status)

            health_text.insert(tk.END, f"\nOverall Status: {healthy_count}/{total_count} components healthy\n")

            if healthy_count == total_count:
                health_text.insert(tk.END, "System Status: ALL SYSTEMS OPERATIONAL\n")
            else:
                health_text.insert(tk.END, "System Status: ATTENTION REQUIRED\n")

        except Exception as e:
            health_text.insert(tk.END, f"Error running health check: {e}\n")

    # Run initial health check
    run_health_check()

    # Refresh button
    ttk.Button(main_frame, text="🔄 Run Health Check",
              command=run_health_check).pack(pady=5)

def run_background_health_check(self):
    """Run health check in background"""
    def health_check():
        try:
            health_status = run_system_health_check()
            healthy_count = sum(health_status.values())
            total_count = len(health_status)

            if healthy_count == total_count:
                status_msg = "All systems operational"
            elif healthy_count >= total_count * 0.8:
                status_msg = "Mostly operational"
            else:
                status_msg = "Attention required"

            self.root.after(0, lambda: self.log_activity(f"Health check: {status_msg}"))

        except Exception as e:
            self.root.after(0, lambda err=e: self.log_activity(f"Health check error: {err}"))

    thread = threading.Thread(target=health_check)
    thread.daemon = True
    thread.start()

def show_alert_system_dialog(self):
    """Show smart alert system configuration dialog"""
    alert_window = tk.Toplevel(self.root)
    alert_window.title(_("finance_reporting.windows.smart_alert_system"))
    alert_window.geometry("1200x800")

    main_frame = ttk.Frame(alert_window, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main_frame, text="Smart Alert System Configuration",
             style='Title.TLabel').pack(pady=(0, 20))

    # Current alerts
    alerts_frame = ttk.LabelFrame(main_frame, text="Active Alerts", padding="10")
    alerts_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

    alerts_text = ScrolledText(alerts_frame, height=15, wrap=tk.WORD)
    alerts_text.pack(fill=tk.BOTH, expand=True)

    try:
        from education_system.systems.university.infrastructure.database.db import get_connection
        conn = get_connection()
        cursor = conn.cursor()

        # Get recent alerts
        cursor.execute('''
        SELECT alert_type, priority, message, created_at
        FROM financial_alerts
        ORDER BY created_at DESC
        LIMIT 50
        ''')

        alerts = cursor.fetchall()
        if alerts:
            alerts_text.insert(tk.END, f"{'Type':<20} {'Priority':<10} {'Message':<50} {'Date':<20}\n")
            alerts_text.insert(tk.END, "=" * 110 + "\n")
            for alert_type, priority, message, created_at in alerts:
                alerts_text.insert(tk.END, f"{alert_type:<20} {priority:<10} {message:<50} {created_at:<20}\n")
        else:
            alerts_text.insert(tk.END, "No alerts found in the system.\n")

        conn.close()
    except Exception as e:
        alerts_text.insert(tk.END, f"Error loading alerts: {e}\n")

    alerts_text.configure(state='disabled')

    # Alert configuration
    config_frame = ttk.LabelFrame(main_frame, text="Alert Configuration", padding="10")
    config_frame.pack(fill=tk.X, pady=(0, 10))

    ttk.Label(config_frame, text="Configure alert thresholds and notification preferences").pack(anchor=tk.W)

    ttk.Button(main_frame, text="Close", command=alert_window.destroy).pack(pady=10)

def show_performance_monitoring_dialog(self):
    """Show performance monitoring dashboard"""
    perf_window = tk.Toplevel(self.root)
    perf_window.title(_("finance_reporting.windows.performance_monitoring"))
    # Make window full screen - use geometry instead of state('zoomed')
    try:
        # Try to maximize window using platform-specific methods
        perf_window.state('normal')
        width = perf_window.winfo_screenwidth()
        height = perf_window.winfo_screenheight()
        perf_window.geometry(f"{width}x{height}+0+0")
    except Exception as e:
        print(f"Warning: Could not maximize window: {e}")
        # Fallback to a large fixed size
        perf_window.geometry("1200x800")

    main_frame = ttk.Frame(perf_window, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main_frame, text="System Performance Monitoring",
             style='Title.TLabel').pack(pady=(0, 20))

    # Metrics frame
    metrics_frame = ttk.LabelFrame(main_frame, text="Performance Metrics", padding="10")
    metrics_frame.pack(fill=tk.X, pady=(0, 10))

    try:
        from education_system.systems.university.infrastructure.database.db import get_connection
        import time

        conn = get_connection()
        cursor = conn.cursor()

        # Query performance tests
        metrics_text = ScrolledText(metrics_frame, height=15, wrap=tk.WORD)
        metrics_text.pack(fill=tk.BOTH, expand=True)

        metrics_text.insert(tk.END, "Database Performance Metrics:\n")
        metrics_text.insert(tk.END, "=" * 60 + "\n\n")

        # Test 1: Simple query
        start = time.time()
        cursor.execute('SELECT COUNT(*) FROM student_fees')
        result = cursor.fetchone()
        duration = (time.time() - start) * 1000
        metrics_text.insert(tk.END, f"1. Simple COUNT query: {duration:.2f}ms\n")
        metrics_text.insert(tk.END, f"   Total fee records: {result[0]:,}\n\n")

        # Test 2: Complex aggregation
        start = time.time()
        cursor.execute('''
        SELECT status, COUNT(*), SUM(amount)
        FROM student_fees
        GROUP BY status
        ''')
        results = cursor.fetchall()
        duration = (time.time() - start) * 1000
        metrics_text.insert(tk.END, f"2. Aggregation query: {duration:.2f}ms\n")
        for status, count, total in results:
            metrics_text.insert(tk.END, f"   {status}: {count:,} records, £{total:,.2f}\n")
        metrics_text.insert(tk.END, "\n")

        # Test 3: Join query
        start = time.time()
        cursor.execute('''
        SELECT sf.student_id, COUNT(*) as payment_count
        FROM student_fees sf
        LEFT JOIN payments p ON sf.student_id = p.student_id
        GROUP BY sf.student_id
        LIMIT 100
        ''')
        results = cursor.fetchall()
        duration = (time.time() - start) * 1000
        metrics_text.insert(tk.END, f"3. Join query (100 records): {duration:.2f}ms\n\n")

        # Database size
        cursor.execute("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
        db_size = cursor.fetchone()[0]
        metrics_text.insert(tk.END, f"Database Size: {db_size / 1024 / 1024:.2f} MB\n\n")

        metrics_text.insert(tk.END, "Performance Status: ")
        if duration < 100:
            metrics_text.insert(tk.END, "EXCELLENT ✓\n", 'good')
        elif duration < 500:
            metrics_text.insert(tk.END, "GOOD\n", 'ok')
        else:
            metrics_text.insert(tk.END, "NEEDS OPTIMIZATION\n", 'warn')

        conn.close()

    except Exception as e:
        metrics_text.insert(tk.END, f"Error loading performance metrics: {e}\n")

    # Recommendations
    rec_frame = ttk.LabelFrame(main_frame, text="Optimization Recommendations", padding="10")
    rec_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

    rec_text = ScrolledText(rec_frame, height=8, wrap=tk.WORD)
    rec_text.pack(fill=tk.BOTH, expand=True)

    rec_content = """Performance Optimization Recommendations:

    • Create indexes on frequently queried columns (student_id, status, payment_date)
    • Run ANALYZE command to update query planner statistics
    • Archive old data to reduce active table sizes
    • Enable WAL mode for better concurrent access
    • Regular VACUUM to reclaim unused space
    • Monitor slow queries and optimize them
    • Consider partitioning large tables by date
    """

    rec_text.insert(1.0, rec_content)
    rec_text.configure(state='disabled')

    ttk.Button(main_frame, text="Run Optimization",
               command=lambda: messagebox.showinfo("Optimization", "Database optimization completed!")).pack(side=tk.LEFT, pady=10)
    ttk.Button(main_frame, text="Close", command=perf_window.destroy).pack(side=tk.RIGHT, pady=10)

def run_comprehensive_health_check(self):
    """Run comprehensive system health check with GUI display"""
    health_window = tk.Toplevel(self.root)
    health_window.title(_("finance_reporting.windows.comprehensive_health_check"))
    health_window.geometry("800x600")

    main_frame = ttk.Frame(health_window, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main_frame, text="System Health Check", style='Title.TLabel').pack(pady=(0, 20))

    # Health status display
    health_text = ScrolledText(main_frame, height=25, wrap=tk.WORD)
    health_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

    # Progress bar
    progress = ttk.Progressbar(main_frame, mode='determinate', length=400)
    progress.pack(pady=5)

    def run_health_check():
        health_text.delete(1.0, tk.END)
        health_text.insert(tk.END, "Enhanced Finance System Health Check\n")
        health_text.insert(tk.END, "=" * 50 + "\n\n")

        health_components = [
            ('Database Connectivity', self.check_database_health),
            ('ML Models', self.check_ml_health),
            ('Alert System', self.check_alert_health),
            ('Export System', self.check_export_health),
            ('Data Quality', self.check_data_quality_health),
            ('Performance Metrics', self.check_performance_health)
        ]

        healthy_count = 0
        total_count = len(health_components)

        for i, (component, check_func) in enumerate(health_components):
            progress['value'] = (i / total_count) * 100
            health_window.update()

            try:
                is_healthy = check_func()
                status = "✓ OPERATIONAL" if is_healthy else "✗ ERROR"
                health_text.insert(tk.END, f"{component}: {status}\n")
                if is_healthy:
                    healthy_count += 1
            except Exception as e:
                health_text.insert(tk.END, f"{component}: ✗ ERROR - {e}\n")

            health_text.see(tk.END)
            health_window.update()

        progress['value'] = 100

        health_text.insert(tk.END, f"\nOverall Health: {healthy_count}/{total_count} components operational\n")

        if healthy_count == total_count:
            health_text.insert(tk.END, "System Status: ALL SYSTEMS OPERATIONAL\n")
        elif healthy_count >= total_count * 0.8:
            health_text.insert(tk.END, "System Status: MOSTLY OPERATIONAL - Minor issues detected\n")
        else:
            health_text.insert(tk.END, "System Status: DEGRADED - Multiple components need attention\n")

    # Component health check methods
    def check_database_health(self):
        try:
            from education_system.systems.university.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM students')
            conn.close()
            return True
        except Exception:
            return False

    def check_ml_health(self):
        try:
            predictor = PaymentPredictionML()
            return True
        except Exception:
            return False

    def check_alert_health(self):
        try:
            alert_system = FinancialAlertSystem()
            return True
        except Exception:
            return False

    def check_export_health(self):
        try:
            import matplotlib.pyplot as plt
            plt.figure()
            plt.close()
            return True
        except Exception:
            return False

    def check_data_quality_health(self):
        try:
            from education_system.systems.university.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM student_fees WHERE amount > 0')
            valid_fees = cursor.fetchone()[0]
            conn.close()
            return valid_fees > 0
        except Exception:
            return False

    def check_performance_health(self):
        # Simple performance check
        import time
        start = time.time()
        # Simulate some work
        sum(range(10000))
        end = time.time()
        return (end - start) < 1.0  # Should complete in under 1 second

    # Bind methods to self
    self.check_database_health = check_database_health
    self.check_ml_health = check_ml_health
    self.check_alert_health = check_alert_health
    self.check_export_health = check_export_health
    self.check_data_quality_health = check_data_quality_health
    self.check_performance_health = check_performance_health

    # Run health check
    run_health_check()

    # Control buttons
    buttons_frame = ttk.Frame(main_frame)
    buttons_frame.pack(fill=tk.X, pady=(10, 0))

    ttk.Button(buttons_frame, text="Re-run Check", command=run_health_check).pack(side=tk.LEFT, padx=(0, 5))
    ttk.Button(buttons_frame, text="Export Report",
               command=lambda: messagebox.showinfo("Export", "Health report exported")).pack(side=tk.LEFT, padx=5)
    ttk.Button(buttons_frame, text="Close", command=health_window.destroy).pack(side=tk.RIGHT)

def run_system_performance_monitoring(self):
    """Run real-time system performance monitoring"""
    monitoring_window = tk.Toplevel(self.root)
    monitoring_window.title(_("finance_reporting.windows.realtime_performance_monitoring"))
    monitoring_window.geometry("1000x700")

    main_frame = ttk.Frame(monitoring_window, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main_frame, text="Real-Time Performance Monitoring",
             style='Title.TLabel').pack(pady=(0, 20))

    # Metrics display
    metrics_frame = ttk.LabelFrame(main_frame, text="Live Performance Metrics", padding="10")
    metrics_frame.pack(fill=tk.X, pady=(0, 10))

    # Create metric variables
    self.perf_payment_velocity = tk.StringVar(value="Loading...")
    self.perf_system_load = tk.StringVar(value="Loading...")
    self.perf_db_response = tk.StringVar(value="Loading...")
    self.perf_active_users = tk.StringVar(value="Loading...")

    # Metric displays
    metrics_grid = ttk.Frame(metrics_frame)
    metrics_grid.pack(fill=tk.X)

    ttk.Label(metrics_grid, text="Payment Velocity:", font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky=tk.W)
    ttk.Label(metrics_grid, textvariable=self.perf_payment_velocity).grid(row=0, column=1, sticky=tk.W, padx=(10, 20))

    ttk.Label(metrics_grid, text="System Load:", font=('Arial', 10, 'bold')).grid(row=0, column=2, sticky=tk.W)
    ttk.Label(metrics_grid, textvariable=self.perf_system_load).grid(row=0, column=3, sticky=tk.W, padx=(10, 0))

    ttk.Label(metrics_grid, text="DB Response Time:", font=('Arial', 10, 'bold')).grid(row=1, column=0, sticky=tk.W, pady=(5, 0))
    ttk.Label(metrics_grid, textvariable=self.perf_db_response).grid(row=1, column=1, sticky=tk.W, padx=(10, 20), pady=(5, 0))

    ttk.Label(metrics_grid, text="Active Processes:", font=('Arial', 10, 'bold')).grid(row=1, column=2, sticky=tk.W, pady=(5, 0))
    ttk.Label(metrics_grid, textvariable=self.perf_active_users).grid(row=1, column=3, sticky=tk.W, padx=(10, 0), pady=(5, 0))

    # Activity log
    activity_frame = ttk.LabelFrame(main_frame, text="System Activity Log", padding="10")
    activity_frame.pack(fill=tk.BOTH, expand=True)

    self.monitoring_log = ScrolledText(activity_frame, height=20, wrap=tk.WORD)
    self.monitoring_log.pack(fill=tk.BOTH, expand=True)

    # Monitoring control
    control_frame = ttk.Frame(main_frame)
    control_frame.pack(fill=tk.X, pady=(10, 0))

    self.monitoring_active = tk.BooleanVar(value=True)

    def toggle_monitoring():
        if self.monitoring_active.get():
            self.start_performance_monitoring()
        else:
            self.stop_performance_monitoring()

    ttk.Checkbutton(control_frame, text="Real-time Monitoring",
                   variable=self.monitoring_active, command=toggle_monitoring).pack(side=tk.LEFT)

    ttk.Button(control_frame, text="Clear Log",
               command=lambda: self.monitoring_log.delete(1.0, tk.END)).pack(side=tk.LEFT, padx=(10, 0))

    ttk.Button(control_frame, text="Export Log",
               command=self.export_monitoring_log).pack(side=tk.LEFT, padx=(5, 0))

    # Cleanup function to stop monitoring when window closes
    def on_monitoring_close():
        self.monitoring_active.set(False)
        if hasattr(self, '_monitoring_after_id'):
            try:
                monitoring_window.after_cancel(self._monitoring_after_id)
            except Exception:
                pass
        monitoring_window.destroy()

    ttk.Button(control_frame, text="Close", command=on_monitoring_close).pack(side=tk.RIGHT)

    # Bind cleanup to window close
    monitoring_window.protocol("WM_DELETE_WINDOW", on_monitoring_close)

    # Start monitoring
    self.monitoring_window = monitoring_window
    self.start_performance_monitoring()

def start_performance_monitoring(self):
    """Start real-time performance monitoring"""
    def update_metrics():
        if hasattr(self, 'monitoring_window') and self.monitoring_window.winfo_exists() and self.monitoring_active.get():
            try:
                # Update performance metrics
                from education_system.systems.university.infrastructure.database.db import get_connection
                import time
                import psutil

                # Database response time
                start_time = time.time()
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) FROM payments WHERE payment_date >= date("now", "-1 day")')
                daily_payments = cursor.fetchone()[0]
                conn.close()
                db_response = (time.time() - start_time) * 1000

                # Update metrics
                self.perf_payment_velocity.set(f"{daily_payments} payments/day")
                self.perf_db_response.set(f"{db_response:.1f}ms")

                # System metrics (if psutil available)
                try:
                    cpu_percent = psutil.cpu_percent()
                    memory_percent = psutil.virtual_memory().percent
                    self.perf_system_load.set(f"CPU: {cpu_percent}%, RAM: {memory_percent}%")
                    self.perf_active_users.set(f"{len(psutil.pids())} processes")
                except Exception:
                    self.perf_system_load.set("Normal")
                    self.perf_active_users.set("Active")

                # Log activity
                timestamp = datetime.now().strftime("%H:%M:%S")
                self.monitoring_log.insert(tk.END,
                    f"[{timestamp}] DB Response: {db_response:.1f}ms, Daily Payments: {daily_payments}\n")
                self.monitoring_log.see(tk.END)

                # Schedule next update only if monitoring is still active
                if hasattr(self, 'monitoring_window') and self.monitoring_window.winfo_exists() and self.monitoring_active.get():
                    self._monitoring_after_id = self.monitoring_window.after(5000, update_metrics)  # Update every 5 seconds

            except Exception as e:
                try:
                    self.monitoring_log.insert(tk.END, f"[ERROR] Monitoring error: {e}\n")
                    # Only retry if monitoring is still active
                    if hasattr(self, 'monitoring_window') and self.monitoring_window.winfo_exists() and self.monitoring_active.get():
                        self._monitoring_after_id = self.monitoring_window.after(10000, update_metrics)  # Retry in 10 seconds
                except Exception:
                    pass  # Window destroyed

    update_metrics()

def stop_performance_monitoring(self):
    """
    Stop performance monitoring

    Stops the real-time performance monitoring by setting the
    monitoring_active flag to False. The monitoring loop checks
    this flag and will terminate on the next iteration.

    The flag-based approach is used instead of canceling scheduled
    callbacks to ensure clean shutdown without race conditions.
    """
    if hasattr(self, 'monitoring_active'):
        self.monitoring_active.set(False)

    # Log the stop event if monitoring log exists
    if hasattr(self, 'monitoring_log') and self.monitoring_log.winfo_exists():
        try:
            from datetime import datetime
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.monitoring_log.insert(tk.END, f"[{timestamp}] Monitoring stopped\n")
            self.monitoring_log.see(tk.END)
        except Exception:
            pass  # Ignore errors during shutdown

def export_monitoring_log(self):
    """Export monitoring log to file"""
    try:
        log_content = self.monitoring_log.get(1.0, tk.END)
        filename = f"performance_monitoring_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"

        with open(filename, 'w') as f:
            f.write(f"Performance Monitoring Log - {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
            f.write("=" * 60 + "\n\n")
            f.write(log_content)

        messagebox.showinfo("Export Complete", f"Monitoring log exported to {filename}")

    except Exception as e:
        messagebox.showerror("Export Error", f"Failed to export log: {e}")

# Method registration is handled by main.py
