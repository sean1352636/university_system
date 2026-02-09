"""Dashboard display and statistics"""

from university_system.infrastructure.database.db import DEFAULT_DB_PATH  # injected
from university_system.modules.shared.utils.i18n import get_text as _
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from tkinter.scrolledtext import ScrolledText
from university_system.infrastructure.database.db import sqlite3
import sys
import io
import os
import csv
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import json
import threading
import warnings
from pathlib import Path
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import joblib
from cryptography.fernet import Fernet
import logging
import qrcode
from io import BytesIO
import base64
from university_system.modules.domain.finance.gui.finance_reporting import launch_financial_gui

# Import authentication - REQUIRED (no fallback for security)
from university_system.infrastructure.auth import UserAuth, get_global_auth
from university_system.infrastructure.shared_context import get_auth

# Import database utilities - use centralized connection management
from university_system.infrastructure.database.db import get_connection

# Import optional modules with fallbacks for non-critical functionality
try:
    from university_system.infrastructure.email.email_service import send_email
except ImportError:
    def send_email(*args, **kwargs):
        """Fallback stub when email service is unavailable."""
        return True

try:
    from university_system.infrastructure.logging.log_config import configure_logging, get_log_file
except ImportError:
    def configure_logging(name=None):
        """Fallback logging configuration."""
        return logging.getLogger(name or __name__)

    def get_log_file(name):
        """Fallback log file path resolution."""
        from university_system.modules.shared.constants import paths
        return str(paths.LOG_DIR / name)

# Import finance functions from common_imports module (explicit imports)
# Note: dashboard.py does not use any functions from common_imports directly
# but other modules may depend on these being available, so we import selectively
from university_system.modules.domain.finance.gui.finance.common_imports import (
    initialize_finance,
)

# Configure logging
log_path = get_log_file("analytics.log")
os.makedirs(os.path.dirname(log_path), exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_path),
        logging.StreamHandler()
    ]
)

logger = configure_logging(name=__name__)
warnings.filterwarnings('ignore')

# Global variables for backward compatibility
auth = get_global_auth()  # Use centralized auth instance
ENCRYPTION_KEY = Fernet.generate_key()
cipher_suite = Fernet(ENCRYPTION_KEY)

# Payment gateway configurations (from original file)
PAYMENT_GATEWAYS = {
    'stripe': {
        'public_key': 'pk_test_...',
        'secret_key': 'sk_test_...',
        'webhook_secret': 'whsec_...'
    },
    'paypal': {
        'client_id': 'your_paypal_client_id',
        'client_secret': 'your_paypal_client_secret',
        'environment': 'sandbox'
    }
}

# WARNING: Never commit real API keys to version control!
# Set these environment variables in your deployment environment
SUPPORTED_CURRENCIES = ['GBP', 'USD', 'EUR', 'CAD', 'AUD']
# Load exchange API key from environment variable
EXCHANGE_API_KEY = os.getenv('EXCHANGE_API_KEY', '')




class DashboardManager:
    """Dashboard display and statistics"""

    def __init__(self, gui):
        """Initialize manager with reference to main GUI"""
        self.gui = gui
        self.root = gui.root
        self.conn = gui.conn
        try:
            self.finance_system = gui.finance_system
        except Exception:
            self.finance_system = None

    def refresh_dashboard(self):
        """Refresh dashboard data with current statistics"""
        try:
            # Update connection if available
            if hasattr(self.gui, 'conn') and self.gui.conn:
                self.conn = self.gui.conn
            elif not self.conn:
                self.conn = get_connection()

            # Calculate total revenue (sum of all payments)
            try:
                cursor = self.conn.cursor()
                cursor.execute('SELECT COALESCE(SUM(amount), 0) FROM payments')
                total_revenue = cursor.fetchone()[0]
            except Exception:
                total_revenue = 0

            # Count active students
            try:
                cursor.execute("SELECT COUNT(*) FROM students WHERE status = 'Active'")
                active_students = cursor.fetchone()[0]
            except Exception:
                active_students = 0

            # Calculate overdue amount (unpaid fees past due date)
            try:
                cursor.execute('''
                    SELECT COALESCE(SUM(sf.amount - COALESCE(pa.paid, 0)), 0)
                    FROM student_fees sf
                    LEFT JOIN (
                        SELECT student_fee_id, SUM(amount) as paid
                        FROM payment_allocations
                        GROUP BY student_fee_id
                    ) pa ON sf.student_fee_id = pa.student_fee_id
                    WHERE sf.due_date < date('now') AND (sf.amount - COALESCE(pa.paid, 0)) > 0
                ''')
                overdue_amount = cursor.fetchone()[0]
            except Exception:
                overdue_amount = 0

            # Calculate collection rate (percentage of fees collected)
            try:
                cursor.execute('SELECT COALESCE(SUM(amount), 0) FROM student_fees')
                total_fees = cursor.fetchone()[0]
                if total_fees > 0:
                    collection_rate = (total_revenue / total_fees) * 100
                else:
                    collection_rate = 0
            except Exception:
                collection_rate = 0

            # Update stat cards if they exist in the layout
            if hasattr(self.gui, 'layout') and hasattr(self.gui.layout, 'tab_frames'):
                dashboard_frame = self.gui.layout.tab_frames.get('dashboard')
                if dashboard_frame:
                    # Find and update stat card labels
                    for widget in dashboard_frame.winfo_children():
                        self._update_stat_cards_recursive(widget, {
                            _("finance_gui.dashboard.stat_total_revenue"): f'£{total_revenue:,.2f}',
                            _("finance_gui.dashboard.stat_active_students"): f'{active_students}',
                            _("finance_gui.dashboard.stat_overdue_amount"): f'£{overdue_amount:,.2f}',
                            _("finance_gui.dashboard.stat_collection_rate"): f'{collection_rate:.1f}%'
                        })

            # Load recent activity
            if hasattr(self, 'activity_listbox'):
                self.activity_listbox.delete(0, tk.END)
                try:
                    cursor.execute('''
                        SELECT payment_date, student_id, amount, payment_method
                        FROM payments
                        ORDER BY payment_date DESC
                        LIMIT 10
                    ''')
                    for row in cursor.fetchall():
                        activity = f"{row[0]} - Student {row[1]}: £{row[2]:.2f} via {row[3]}"
                        self.activity_listbox.insert(tk.END, activity)
                except Exception:
                    self.activity_listbox.insert(tk.END, _("finance_gui.dashboard.no_recent_activity"))

            print(_("finance_gui.dashboard.dashboard_refreshed"))
        except Exception as e:
            print(f"Dashboard refresh error: {e}")

    def _update_stat_cards_recursive(self, widget, stats):
        """Recursively update stat card labels"""
        try:
            if isinstance(widget, tk.Label):
                text = widget.cget('text')
                if text in stats:
                    # This is a title label, find the next label (value)
                    parent = widget.master
                    labels = [w for w in parent.winfo_children() if isinstance(w, tk.Label)]
                    if len(labels) >= 2:
                        # Update the value label
                        labels[1].config(text=stats[text])

            # Recurse into children
            for child in widget.winfo_children():
                self._update_stat_cards_recursive(child, stats)
        except Exception as e:
            # Silently skip widgets that can't be updated
            print(f"Debug: Could not update widget: {e}")

    def create_dashboard_tab(self):
        """Create dashboard tab"""
        dashboard_frame = tk.Frame(self.gui.layout.content_frame, bg='white')
        self.gui.layout.tab_frames['dashboard'] = dashboard_frame

        # Create dashboard content
        main_frame = tk.Frame(dashboard_frame, bg='white')
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Dashboard title
        title = tk.Label(main_frame, text=_("finance_gui.dashboard.title"),
                        font=('Arial', 18, 'bold'), bg='white')
        title.pack(pady=10)

        # Quick stats frame
        stats_frame = tk.Frame(main_frame, bg='white')
        stats_frame.pack(fill='x', pady=10)

        # Create stat cards
        self.create_stat_card(stats_frame, _("finance_gui.dashboard.stat_total_revenue"), _("finance_gui.dashboard.loading"), self.gui.layout.colors['success'], 0, 0)
        self.create_stat_card(stats_frame, _("finance_gui.dashboard.stat_active_students"), _("finance_gui.dashboard.loading"), self.gui.layout.colors['secondary'], 0, 1)
        self.create_stat_card(stats_frame, _("finance_gui.dashboard.stat_overdue_amount"), _("finance_gui.dashboard.loading"), self.gui.layout.colors['danger'], 0, 2)
        self.create_stat_card(stats_frame, _("finance_gui.dashboard.stat_collection_rate"), _("finance_gui.dashboard.loading"), self.gui.layout.colors['warning'], 0, 3)

        # Quick actions frame
        actions_frame = tk.LabelFrame(main_frame, text=_("finance_gui.dashboard.quick_actions_frame"),
                                     font=('Arial', 12, 'bold'), bg='white')
        actions_frame.pack(fill='x', pady=20)

        # Action buttons
        btn_frame = tk.Frame(actions_frame, bg='white')
        btn_frame.pack(padx=10, pady=10)

        actions = [
            (_("finance_gui.dashboard.action_record_payment"), self.show_payment_dialog),
            (_("finance_gui.dashboard.action_generate_report"), self.show_reports_tab),
            (_("finance_gui.dashboard.action_sync_data"), self.refresh_dashboard),
            (_("finance_gui.dashboard.action_advanced_reporting"), self.launch_reporting_gui)
        ]

        for i, (text, command) in enumerate(actions):
            btn = tk.Button(btn_frame, text=text, command=command,
                           font=('Arial', 10), bg=self.gui.layout.colors['secondary'],
                           fg='white', padx=20, pady=5)
            btn.grid(row=0, column=i, padx=5)

        # Recent activity frame
        activity_frame = tk.LabelFrame(main_frame, text=_("finance_gui.dashboard.recent_activity_frame"),
                                      font=('Arial', 12, 'bold'), bg='white')
        activity_frame.pack(fill='both', expand=True, pady=10)
        
        # Activity listbox with scrollbar
        activity_container = tk.Frame(activity_frame, bg='white')
        activity_container.pack(fill='both', expand=True, padx=10, pady=10)
        
        self.activity_listbox = tk.Listbox(activity_container, font=('Arial', 9))
        scrollbar = ttk.Scrollbar(activity_container, orient='vertical', command=self.activity_listbox.yview)
        self.activity_listbox.configure(yscrollcommand=scrollbar.set)
        
        self.activity_listbox.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Load dashboard data
        self.refresh_dashboard()
    

    def create_stat_card(self, parent, title, value, color, row, col):
        """Create a statistics card"""
        card_frame = tk.Frame(parent, bg=color, relief='raised', bd=2)
        card_frame.grid(row=row, column=col, padx=10, pady=5, sticky='ew')
        parent.grid_columnconfigure(col, weight=1)
        
        title_label = tk.Label(card_frame, text=title, font=('Arial', 10, 'bold'),
                              bg=color, fg='white')
        title_label.pack(pady=5)
        
        value_label = tk.Label(card_frame, text=value, font=('Arial', 14, 'bold'),
                              bg=color, fg='white')
        value_label.pack(pady=5)
        
        # Store reference for updating
        setattr(self, f"stat_{col}", value_label)
    

    def refresh_dashboard(self):
        """Refresh dashboard data"""
        def refresh_thread():
            conn = None
            try:
                conn = get_connection()
                cursor = conn.cursor()
    
                # Get total revenue
                cursor.execute("SELECT SUM(amount) FROM payments WHERE status = 'completed'")
                total_revenue = cursor.fetchone()[0] or 0
    
                # Get active students
                cursor.execute("SELECT COUNT(*) FROM students WHERE status = 'active'")
                active_students = cursor.fetchone()[0] or 0
    
                # Get overdue amount
                cursor.execute('''
                SELECT SUM(sf.amount) - COALESCE(SUM(pa.amount), 0)
                FROM student_fees sf
                LEFT JOIN payment_allocations pa ON sf.student_fee_id = pa.student_fee_id
                WHERE sf.status IN ('unpaid', 'partial') AND date(sf.due_date) < date('now')
                ''')
                overdue_amount = cursor.fetchone()[0] or 0
    
                # Calculate collection rate
                total_fees = cursor.execute('''
                SELECT SUM(sf.amount) FROM student_fees sf
                WHERE sf.status IN ('paid', 'partial', 'unpaid')
                ''').fetchone()[0] or 1
    
                paid_amount = total_revenue
                collection_rate = (paid_amount / total_fees * 100) if total_fees > 0 else 0
    
                # Update UI in main thread
                self.root.after(0, lambda: self.update_dashboard_stats(
                    total_revenue, active_students, overdue_amount, collection_rate))
    
                # Load recent activity
                self.root.after(100, self.load_recent_activity)
    
            except sqlite3.Error as e:
                if conn:
                    conn.rollback()
                print(f"Database error refreshing dashboard: {e}")
    
            except Exception as e:
                if conn:
                    conn.rollback()
                print(f"Error refreshing dashboard: {e}")
    
            finally:
                if conn:
                    conn.close()
    
        refresh_thread()
    

    def update_dashboard_stats(self, revenue, students, overdue, collection_rate):
        """Update dashboard statistics"""
        try:
            self.stat_0.config(text=f"£{revenue:,.2f}")
            self.stat_1.config(text=f"{students}")
            self.stat_2.config(text=f"£{overdue:,.2f}")
            self.stat_3.config(text=f"{collection_rate:.1f}%")
        except AttributeError:
            pass  # Stats not yet created
    

    def load_recent_activity(self):
        """Load recent activity for dashboard"""
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()
    
            # Get recent payments
            cursor.execute('''
            SELECT p.payment_date, s.first_name, s.last_name, p.amount, p.payment_method
            FROM payments p
            JOIN students s ON p.student_id = s.student_id
            WHERE p.status = 'completed'
            ORDER BY p.payment_date DESC
            LIMIT 10
            ''')
    
            recent_payments = cursor.fetchall()
    
            # Clear and populate activity listbox
            self.activity_listbox.delete(0, tk.END)
            for payment_date, first_name, last_name, amount, method in recent_payments:
                activity_text = f"{payment_date} - {first_name} {last_name} paid £{amount:.2f} via {method}"
                self.activity_listbox.insert(tk.END, activity_text)
    
        except sqlite3.Error as e:
            if conn:
                conn.rollback()
            print(f"Database error loading recent activity: {e}")
    
        except Exception as e:
            if conn:
                conn.rollback()
            print(f"Error loading recent activity: {e}")
    
        finally:
            if conn:
                conn.close()
    

    def load_initial_data(self):
        """Load initial data for all tabs"""
        try:
            self.refresh_dashboard()
            self.refresh_payments()
            self.refresh_fees()
            self.refresh_students()
            self.refresh_collections()
            self.refresh_financial_aid()
            self.refresh_budget()
            self.load_exchange_rates()
            self.load_notification_templates()
        except Exception as e:
            print(f"Error loading initial data: {e}")
    

    def gui_generate_financial_dashboard(self):
        """Generate and display financial dashboard"""
        try:
            if hasattr(self.gui, 'layout') and hasattr(self.gui.layout, 'update_status'):
                self.gui.layout.update_status("Generating financial dashboard...")
            else:
                print("Generating financial dashboard...")

            # Switch to analytics tab first
            if hasattr(self.gui, 'layout') and hasattr(self.gui.layout, 'show_tab'):
                self.gui.layout.show_tab('analytics')

            def generate_dashboard():
                try:
                    # Update charts through analytics manager if available
                    if hasattr(self.gui, 'analytics') and hasattr(self.gui.analytics, 'update_dashboard_charts'):
                        self.gui.analytics.update_dashboard_charts()
                        messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.dashboard.dashboard_updated"))
                    else:
                        messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.dashboard.dashboard_refreshed"))

                    if hasattr(self.gui, 'layout') and hasattr(self.gui.layout, 'update_status'):
                        self.gui.layout.update_status(_("finance_gui.dashboard.dashboard_refreshed"))
                    else:
                        print(_("finance_gui.dashboard.dashboard_refreshed"))
                except Exception as e:
                    messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.dashboard.error_generate_dashboard", error=str(e)))

            thread = threading.Thread(target=generate_dashboard)
            thread.daemon = True
            thread.start()

        except Exception as e:
            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.dashboard.error_generate_dashboard", error=str(e)))
    

    

    def update_quick_stats(self, parent_frame):
        """Update quick statistics display"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Total revenue this year
            current_year = datetime.now().year
            cursor.execute('''
            SELECT SUM(amount) FROM payments 
            WHERE strftime('%Y', payment_date) = ? AND status = 'completed'
            ''', (str(current_year),))
            
            total_revenue = cursor.fetchone()[0] or 0
            
            # Outstanding fees
            cursor.execute('''
            SELECT SUM(sf.amount) - COALESCE(SUM(pa.amount), 0) as outstanding
            FROM student_fees sf
            LEFT JOIN payment_allocations pa ON sf.student_fee_id = pa.student_fee_id
            WHERE sf.status IN ('unpaid', 'partial')
            ''')
            
            outstanding_fees = cursor.fetchone()[0] or 0
            
            # Active payment plans
            cursor.execute('''SELECT COUNT(*) FROM student_payment_plans WHERE status = 'active' ''')
            active_plans = cursor.fetchone()[0] or 0
            
            # Total students
            cursor.execute('''SELECT COUNT(*) FROM students WHERE status = 'active' ''')
            total_students = cursor.fetchone()[0] or 0
            
            # Create or update stats labels
            stats_data = [
                (_("finance_gui.dashboard.stats_total_revenue_ytd"), f"£{total_revenue:,.2f}", "#27ae60"),
                (_("finance_gui.dashboard.stats_outstanding_fees"), f"£{outstanding_fees:,.2f}", "#e74c3c"),
                (_("finance_gui.dashboard.stats_active_payment_plans"), str(active_plans), "#3498db"),
                (_("finance_gui.dashboard.stats_total_active_students"), str(total_students), "#9b59b6")
            ]
            
            # Clear existing widgets
            for widget in parent_frame.winfo_children():
                widget.destroy()
            
            # Create stats display
            for i, (label, value, color) in enumerate(stats_data):
                stat_frame = tk.Frame(parent_frame, bg=color, relief='raised', bd=2)
                stat_frame.grid(row=i//2, column=i%2, padx=10, pady=10, sticky='ew')
                
                tk.Label(stat_frame, text=label, font=('Arial', 12, 'bold'), 
                        fg='white', bg=color).pack(pady=5)
                tk.Label(stat_frame, text=value, font=('Arial', 16, 'bold'), 
                        fg='white', bg=color).pack(pady=5)
            
            parent_frame.columnconfigure(0, weight=1)
            parent_frame.columnconfigure(1, weight=1)
            
            conn.close()
            
        except Exception as e:
            # Create error display
            error_label = tk.Label(parent_frame, text=_("finance_gui.dashboard.error_loading_stats", error=str(e)),
                                 fg='red', font=('Arial', 12))
            error_label.pack(pady=20)

    def show_payment_dialog(self):
        """Wrapper to call transaction manager's payment dialog"""
        if hasattr(self.gui, 'transactions'):
            self.gui.transactions.show_payment_dialog()
        else:
            messagebox.showwarning(_("finance_gui.dashboard.not_available_title"), _("finance_gui.dashboard.transaction_manager_not_init"))

    def show_reports_tab(self):
        """Show the reports tab"""
        try:
            if hasattr(self.gui, 'layout') and hasattr(self.gui.layout, 'show_tab'):
                self.gui.layout.show_tab('reports')
            else:
                messagebox.showinfo(_("finance_gui.dashboard.reports_info_title"), _("finance_gui.dashboard.reports_info_message"))
        except Exception as e:
            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.dashboard.error_show_reports", error=str(e)))

    def launch_reporting_gui(self):
        """Launch the advanced reporting GUI"""
        try:
            from university_system.modules.domain.finance.gui.finance_reporting import launch_financial_gui
            launch_financial_gui(self.root)
        except Exception as e:
            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.dashboard.error_launch_reporting", error=str(e)))

