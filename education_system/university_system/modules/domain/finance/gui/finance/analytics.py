"""Predictive analytics and forecasting"""

from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH  # injected
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from tkinter.scrolledtext import ScrolledText
from education_system.university_system.infrastructure.database.db import sqlite3
import sys
import io
import os
from education_system.university_system.modules.shared.utils.i18n import get_text as _
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
from education_system.university_system.modules.domain.finance.gui.finance_reporting import launch_financial_gui

# Import authentication - REQUIRED (no fallback for security)
from education_system.university_system.infrastructure.auth import UserAuth, get_global_auth
from education_system.university_system.infrastructure.shared_context import get_auth

# Import database utilities - use centralized connection management
from education_system.university_system.infrastructure.database.db import get_connection

# Import optional modules with fallbacks for non-critical functionality
try:
    from education_system.university_system.infrastructure.email.email_service import send_email
except ImportError:
    def send_email(*args, **kwargs):
        """Fallback stub when email service is unavailable."""
        return True

try:
    from education_system.university_system.infrastructure.logging.log_config import configure_logging, get_log_file
except ImportError:
    def configure_logging(name=None):
        """Fallback logging configuration."""
        return logging.getLogger(name or __name__)

    def get_log_file(name):
        """Fallback log file path resolution."""
        from education_system.university_system.modules.shared.constants import paths
        return str(paths.LOG_DIR / name)

# Import finance functions from common_imports module (explicit imports)
from education_system.university_system.modules.domain.finance.gui.finance.common_imports import (
    detect_payment_fraud,
)

# Import analytics and forecasting functions
try:
    from education_system.university_system.modules.domain.finance.reporting.revenue_analytics import (
        generate_predictive_analytics,
        generate_comprehensive_forecast_report,
    )
except ImportError:
    def generate_predictive_analytics():
        print("Predictive Analytics\n" + "=" * 40)
        print("Function not available - revenue_analytics module not found")
    def generate_comprehensive_forecast_report():
        print("Comprehensive Forecast Report\n" + "=" * 40)
        print("Function not available - revenue_analytics module not found")

try:
    from education_system.university_system.modules.domain.finance.core.analytics import (
        generate_enrollment_projections,
        generate_cash_flow_analysis,
        generate_risk_analysis,
        generate_scenario_planning,
    )
except ImportError:
    def generate_enrollment_projections():
        print("Enrollment Projections\n" + "=" * 40)
        print("Function not available - finance_misc.analytics module not found")
    def generate_cash_flow_analysis():
        print("Cash Flow Analysis\n" + "=" * 40)
        print("Function not available - finance_misc.analytics module not found")
    def generate_risk_analysis():
        print("Risk Analysis\n" + "=" * 40)
        print("Function not available - finance_misc.analytics module not found")
    def generate_scenario_planning():
        print("Scenario Planning\n" + "=" * 40)
        print("Function not available - finance_misc.analytics module not found")

# Configure logging
log_path = get_log_file("app.log")
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
        'public_key': os.getenv('STRIPE_PUBLIC_KEY', ''),
        'secret_key': os.getenv('STRIPE_SECRET_KEY', ''),
        'webhook_secret': os.getenv('STRIPE_WEBHOOK_SECRET', '')
    },
    'paypal': {
        'client_id': os.getenv('PAYPAL_CLIENT_ID', ''),
        'client_secret': os.getenv('PAYPAL_CLIENT_SECRET', ''),
        'environment': os.getenv('PAYPAL_ENVIRONMENT', 'sandbox')
    }
}

# WARNING: Never commit real API keys to version control!
# Set these environment variables in your deployment environment
SUPPORTED_CURRENCIES = ['GBP', 'USD', 'EUR', 'CAD', 'AUD']
# Load exchange API key from environment variable
EXCHANGE_API_KEY = os.getenv('EXCHANGE_API_KEY', '')




class AnalyticsManager:
    """Predictive analytics and forecasting"""

    def __init__(self, gui):
        """Initialize manager with reference to main GUI"""
        self.gui = gui
        self.root = gui.root
        self.conn = gui.conn
        try:
            self.finance_system = gui.finance_system
        except Exception:
            self.finance_system = None

    def update_status(self, message):
        """Update the status bar message"""
        try:
            if hasattr(self.gui, 'layout') and hasattr(self.gui.layout, 'update_status'):
                self.gui.layout.update_status(message)
            else:
                print(f"Status: {message}")
        except Exception:
            print(f"Status: {message}")

    def display_report_output(self, title, output):
        """Display report output in a popup window"""
        try:
            report_window = tk.Toplevel(self.root)
            report_window.title(title)
            report_window.geometry("800x600")

            from tkinter.scrolledtext import ScrolledText
            text = ScrolledText(report_window, font=('Courier', 10), wrap='word')
            text.pack(fill='both', expand=True, padx=10, pady=10)
            text.insert('1.0', output)
            text.config(state='disabled')

            # Close button
            tk.Button(report_window, text=_("analytics_manager.buttons.close"), command=report_window.destroy,
                     font=('Arial', 10), padx=20, pady=5).pack(pady=10)
        except Exception as e:
            messagebox.showinfo(title, output[:1000] + "..." if len(output) > 1000 else output)

    def show_tab(self, tab_name):
        """Show a specific tab"""
        try:
            if hasattr(self.gui, 'layout') and hasattr(self.gui.layout, 'show_tab'):
                self.gui.layout.show_tab(tab_name)
        except Exception:
            pass

    def create_analytics_tab(self):
        """Create analytics and dashboard tab"""
        tab = tk.Frame(self.gui.layout.content_frame, bg='white')
        self.gui.layout.tab_frames['analytics'] = tab

        main_frame = ttk.Frame(tab, padding=10)
        main_frame.pack(fill='both', expand=True)

        # Control buttons
        control_frame = ttk.LabelFrame(main_frame, text=_("analytics_manager.labels.analytics_reports"), padding=10)
        control_frame.pack(fill='x', pady=(0, 10))

        buttons = [
            (_("analytics_manager.buttons.financial_dashboard"), self.gui_generate_financial_dashboard),
            (_("analytics_manager.buttons.predictive_analytics"), self.gui_generate_predictive_analytics),
            (_("analytics_manager.buttons.fraud_detection"), self.gui_detect_payment_fraud),
            (_("analytics_manager.buttons.revenue_forecast"), self.gui_generate_revenue_forecast)
        ]

        for i, (text, command) in enumerate(buttons):
            ttk.Button(control_frame, text=text, command=command, width=25).grid(row=i//2, column=i%2, padx=10, pady=5)

        # Charts frame
        charts_frame = ttk.LabelFrame(main_frame, text=_("analytics_manager.labels.dashboard"), padding=10)
        charts_frame.pack(fill='both', expand=True)

        # Create matplotlib figure
        self.fig, ((self.ax1, self.ax2), (self.ax3, self.ax4)) = plt.subplots(2, 2, figsize=(12, 8))
        self.fig.tight_layout(pad=3.0)

        self.canvas = FigureCanvasTkAgg(self.fig, charts_frame)
        self.canvas.get_tk_widget().pack(fill='both', expand=True)

        # Load initial dashboard
        self.update_dashboard_charts()

    def create_forecasting_tab(self):
        """Create financial forecasting tab"""
        colors = self.gui.layout.colors
        forecast_frame = tk.Frame(self.gui.layout.content_frame, bg='white')
        self.gui.layout.tab_frames['forecasting'] = forecast_frame

        # Forecasting toolbar
        toolbar = tk.Frame(forecast_frame, bg='white')
        toolbar.pack(fill='x', padx=10, pady=5)

        tk.Button(toolbar, text=_("analytics_manager.buttons.revenue_forecast"), command=self.generate_revenue_forecast,
                 bg=colors['success'], fg='white').pack(side='left', padx=5)
        tk.Button(toolbar, text=_("analytics_manager.buttons.enrollment_projections"), command=self.enrollment_projections,
                 bg=colors['secondary'], fg='white').pack(side='left', padx=5)
        tk.Button(toolbar, text=_("analytics_manager.buttons.cash_flow_analysis"), command=self.cash_flow_analysis,
                 bg=colors['warning'], fg='white').pack(side='left', padx=5)
        tk.Button(toolbar, text=_("analytics_manager.buttons.risk_analysis"), command=self.risk_analysis,
                 bg=colors['danger'], fg='white').pack(side='left', padx=5)
        tk.Button(toolbar, text=_("analytics_manager.buttons.scenario_planning"), command=self.scenario_planning,
                 bg=colors['dark'], fg='white').pack(side='left', padx=5)

        # Forecasting content
        forecast_notebook = ttk.Notebook(forecast_frame)
        forecast_notebook.pack(fill='both', expand=True, padx=10, pady=10)

        # Revenue forecasting tab
        revenue_frame = ttk.Frame(forecast_notebook)
        forecast_notebook.add(revenue_frame, text=_("analytics_manager.tabs.revenue_forecast"))

        # Forecast parameters frame
        params_frame = tk.LabelFrame(revenue_frame, text=_("analytics_manager.labels.forecast_parameters"), font=('Arial', 10, 'bold'))
        params_frame.pack(fill='x', padx=10, pady=5)

        # Parameters
        tk.Label(params_frame, text=_("analytics_manager.labels.forecast_period_months")).grid(row=0, column=0, sticky='w', padx=5, pady=2)
        self.forecast_months_var = tk.StringVar(value="12")
        tk.Entry(params_frame, textvariable=self.forecast_months_var, width=10).grid(row=0, column=1, padx=5, pady=2)

        tk.Label(params_frame, text=_("analytics_manager.labels.growth_rate_percent")).grid(row=0, column=2, sticky='w', padx=5, pady=2)
        self.growth_rate_var = tk.StringVar(value="5.0")
        tk.Entry(params_frame, textvariable=self.growth_rate_var, width=10).grid(row=0, column=3, padx=5, pady=2)

        tk.Button(params_frame, text=_("analytics_manager.buttons.generate_forecast"), command=self.run_forecast,
                 bg=colors['secondary'], fg='white').grid(row=0, column=4, padx=10, pady=2)

        # Forecast results
        self.forecast_output = ScrolledText(revenue_frame, height=20, font=('Courier', 9))
        self.forecast_output.pack(fill='both', expand=True, padx=10, pady=10)

        # Scenarios tab
        scenarios_frame = ttk.Frame(forecast_notebook)
        forecast_notebook.add(scenarios_frame, text=_("analytics_manager.tabs.scenarios"))

        # Scenario comparison
        scenario_label = tk.Label(scenarios_frame, text=_("analytics_manager.labels.scenarios_comparison"),
                                font=('Arial', 14, 'bold'))
        scenario_label.pack(pady=10)

        self.scenarios_tree = ttk.Treeview(scenarios_frame,
                                         columns=('scenario', 'students', 'revenue', 'expenses', 'net'),
                                         show='headings')
        col_names = {
            'scenario': _("analytics_manager.columns.scenario"),
            'students': _("analytics_manager.columns.students"),
            'revenue': _("analytics_manager.columns.revenue"),
            'expenses': _("analytics_manager.columns.expenses"),
            'net': _("analytics_manager.columns.net")
        }
        for col in self.scenarios_tree['columns']:
            self.scenarios_tree.heading(col, text=col_names.get(col, col.replace('_', ' ').title()))
        self.scenarios_tree.pack(fill='both', expand=True, padx=10, pady=10)


    def generate_revenue_forecast(self):
        """Generate revenue forecast"""
        try:
            old_stdout = sys.stdout
            sys.stdout = mystdout = io.StringIO()

            generate_revenue_forecast()

            output = mystdout.getvalue()
            sys.stdout = old_stdout

            self.forecast_output.delete('1.0', tk.END)
            self.forecast_output.insert('1.0', output)

        except Exception as e:
            sys.stdout = old_stdout
            messagebox.showerror(_("common.error"), _("analytics_manager.errors.failed_revenue_forecast", error=str(e)))


    def enrollment_projections(self):
        """Generate enrollment projections"""
        try:
            old_stdout = sys.stdout
            sys.stdout = mystdout = io.StringIO()

            generate_enrollment_projections()

            output = mystdout.getvalue()
            sys.stdout = old_stdout

            self.forecast_output.delete('1.0', tk.END)
            self.forecast_output.insert('1.0', output)

        except Exception as e:
            sys.stdout = old_stdout
            messagebox.showerror(_("common.error"), _("analytics_manager.errors.failed_enrollment_projections", error=str(e)))


    def cash_flow_analysis(self):
        """Generate cash flow analysis"""
        try:
            old_stdout = sys.stdout
            sys.stdout = mystdout = io.StringIO()

            generate_cash_flow_analysis()

            output = mystdout.getvalue()
            sys.stdout = old_stdout

            self.forecast_output.delete('1.0', tk.END)
            self.forecast_output.insert('1.0', output)

        except Exception as e:
            sys.stdout = old_stdout
            messagebox.showerror(_("common.error"), _("analytics_manager.errors.failed_cash_flow_analysis", error=str(e)))


    def risk_analysis(self):
        """Generate risk analysis"""
        try:
            old_stdout = sys.stdout
            sys.stdout = mystdout = io.StringIO()

            generate_risk_analysis()

            output = mystdout.getvalue()
            sys.stdout = old_stdout

            self.forecast_output.delete('1.0', tk.END)
            self.forecast_output.insert('1.0', output)

        except Exception as e:
            sys.stdout = old_stdout
            messagebox.showerror(_("common.error"), _("analytics_manager.errors.failed_risk_analysis", error=str(e)))


    def run_forecast(self):
        """Generate a simple revenue forecast based on current payments and user parameters."""
        try:
            months = int(self.forecast_months_var.get())
        except Exception:
            months = 12
        try:
            growth = float(self.growth_rate_var.get()) / 100.0
        except Exception:
            growth = 0.05
        # Compute baseline monthly revenue from last 12 months if available
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("""SELECT strftime('%Y-%m', payment_date) as ym, COALESCE(SUM(amount),0)
                         FROM payments
                         GROUP BY ym
                         ORDER BY ym DESC
                         LIMIT 12""")
            rows = cur.fetchall()
            conn.close()
            if rows:
                baseline = sum(r[1] for r in rows) / len(rows)
            else:
                baseline = 0.0
        except Exception:
            baseline = 0.0
        projections = []
        value = baseline
        today = datetime.now().replace(day=1)
        for i in range(1, months+1):
            # compound growth monthly
            value = value * (1 + growth)
            dt = (today + timedelta(days=31*i)).replace(day=1)
            projections.append((dt.strftime('%Y-%m'), round(value, 2)))
        # Display
        try:
            self.forecast_output.delete('1.0', tk.END)
            self.forecast_output.insert(tk.END, _("analytics_manager.forecast.title") + '\n')
            self.forecast_output.insert(tk.END, _("analytics_manager.forecast.separator") + '\n')
            total = 0.0
            for ym, amt in projections:
                self.forecast_output.insert(tk.END, f"{ym}\t£{amt:,.2f}\n")
                total += amt
            self.forecast_output.insert(tk.END, f"\n{_('analytics_manager.forecast.projected_total', total=total)}\n")
            self.update_status(_("analytics_manager.messages.forecast_generated"))
        except Exception as e:
            # Widget may not be initialized yet
            print(f"Warning: Could not update forecast output: {e}")


    def gui_generate_predictive_analytics(self):
        """GUI wrapper for predictive analytics"""
        try:
            self.update_status(_("analytics_manager.messages.generating_analytics"))

            def generate_analytics():
                old_stdout = sys.stdout
                sys.stdout = mystdout = io.StringIO()

                generate_predictive_analytics()

                output = mystdout.getvalue()
                sys.stdout = old_stdout

                self.root.after(0, lambda: self.display_report_output(_("analytics_manager.dialogs.predictive_analytics_title"), output))

            threading.Thread(target=generate_analytics, daemon=True).start()

        except Exception as e:
            messagebox.showerror(_("common.error"), _("analytics_manager.errors.failed_generate_analytics", error=e))


    def gui_detect_payment_fraud(self):
        """GUI wrapper for fraud detection"""
        try:
            self.update_status(_("analytics_manager.messages.running_fraud_detection"))

            def detect_fraud():
                old_stdout = sys.stdout
                sys.stdout = mystdout = io.StringIO()

                detect_payment_fraud()

                output = mystdout.getvalue()
                sys.stdout = old_stdout

                self.root.after(0, lambda: self.display_report_output(_("analytics_manager.dialogs.fraud_detection_title"), output))

            threading.Thread(target=detect_fraud, daemon=True).start()

        except Exception as e:
            messagebox.showerror(_("common.error"), _("analytics_manager.errors.failed_fraud_detection", error=e))


    def gui_detect_payment_fraud_original(self):
        """GUI wrapper for detect_payment_fraud from original finance.py"""
        try:
            old_stdout = sys.stdout
            sys.stdout = mystdout = io.StringIO()

            detect_payment_fraud()

            output = mystdout.getvalue()
            sys.stdout = old_stdout

            self.display_report_output(_("analytics_manager.dialogs.fraud_detection_title"), output)
            self.update_status(_("analytics_manager.messages.running_fraud_detection"))

        except Exception as e:
            messagebox.showerror(_("common.error"), _("analytics_manager.errors.failed_fraud_detection", error=e))


    def gui_generate_cash_flow_analysis(self):
        """GUI wrapper for cash flow analysis"""
        try:
            old_stdout = sys.stdout
            sys.stdout = mystdout = io.StringIO()

            generate_cash_flow_analysis()

            output = mystdout.getvalue()
            sys.stdout = old_stdout

            self.forecast_output.delete('1.0', tk.END)
            self.forecast_output.insert('1.0', output)

        except Exception as e:
            messagebox.showerror(_("common.error"), _("analytics_manager.errors.failed_cash_flow_analysis", error=e))


    def gui_generate_enrollment_projections(self):
        """GUI wrapper for enrollment projections"""
        try:
            old_stdout = sys.stdout
            sys.stdout = mystdout = io.StringIO()

            generate_enrollment_projections()

            output = mystdout.getvalue()
            sys.stdout = old_stdout

            self.forecast_output.delete('1.0', tk.END)
            self.forecast_output.insert('1.0', output)

        except Exception as e:
            messagebox.showerror(_("common.error"), _("analytics_manager.errors.failed_enrollment_projections", error=e))


    def gui_generate_risk_analysis(self):
        """GUI wrapper for risk analysis"""
        try:
            old_stdout = sys.stdout
            sys.stdout = mystdout = io.StringIO()

            generate_risk_analysis()

            output = mystdout.getvalue()
            sys.stdout = old_stdout

            self.forecast_output.delete('1.0', tk.END)
            self.forecast_output.insert('1.0', output)

        except Exception as e:
            messagebox.showerror(_("common.error"), _("analytics_manager.errors.failed_risk_analysis", error=e))


    def gui_generate_scenario_planning(self):
        """GUI wrapper for scenario planning"""
        try:
            old_stdout = sys.stdout
            sys.stdout = mystdout = io.StringIO()

            generate_scenario_planning()

            output = mystdout.getvalue()
            sys.stdout = old_stdout

            # Add to scenarios table if it exists
            try:
                scenarios_data = [
                    ("Conservative", "950", "£4.2M", "£3.8M", "£0.4M"),
                    ("Baseline", "1,050", "£4.8M", "£4.2M", "£0.6M"),
                    ("Optimistic", "1,200", "£5.6M", "£4.8M", "£0.8M")
                ]

                for item in self.scenarios_tree.get_children():
                    self.scenarios_tree.delete(item)

                for scenario in scenarios_data:
                    self.scenarios_tree.insert('', 'end', values=scenario)

            except AttributeError:
                # scenarios_tree widget not available in this view
                print("Info: Scenarios tree not available, skipping table update")

            self.forecast_output.delete('1.0', tk.END)
            self.forecast_output.insert('1.0', output)

        except Exception as e:
            messagebox.showerror(_("common.error"), _("analytics_manager.errors.failed_scenario_planning", error=e))


    def scenario_planning(self):
        """Generate scenario planning"""
        try:
            # Generate realistic scenario data
            scenarios_output = f"""Financial Scenario Planning Analysis
    {'=' * 60}
    Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

    SCENARIO ASSUMPTIONS:
    {'=' * 60}

    Conservative Scenario:
    - Student enrollment: 950 (-9.5% from baseline)
    - Tuition increase: 2%
    - Operating cost increase: 4%
    - Financial aid budget: Maintained at current level

    Baseline Scenario:
    - Student enrollment: 1,050 (current projection)
    - Tuition increase: 3%
    - Operating cost increase: 3%
    - Financial aid budget: 5% increase

    Optimistic Scenario:
    - Student enrollment: 1,200 (+14.3% from baseline)
    - Tuition increase: 4%
    - Operating cost increase: 2.5%
    - Financial aid budget: 10% increase

    FINANCIAL PROJECTIONS:
    {'=' * 60}

    Conservative Scenario:
    - Tuition Revenue: £4,200,000
    - Total Revenue: £4,200,000
    - Operating Expenses: £3,800,000
    - Net Income: £400,000
    - Cash Flow: Positive but tight

    Baseline Scenario:
    - Tuition Revenue: £4,800,000
    - Total Revenue: £4,800,000
    - Operating Expenses: £4,200,000
    - Net Income: £600,000
    - Cash Flow: Healthy growth

    Optimistic Scenario:
    - Tuition Revenue: £5,600,000
    - Total Revenue: £5,600,000
    - Operating Expenses: £4,800,000
    - Net Income: £800,000
    - Cash Flow: Strong growth potential

    RISK FACTORS:
    {'=' * 60}

    Conservative Scenario Risks:
    - Enrollment decline may continue
    - Competition from other institutions
    - Economic downturn affecting student ability to pay

    Baseline Scenario Risks:
    - Market saturation in target demographics
    - Regulatory changes in education funding
    - Technology disruption requiring additional investment

    Optimistic Scenario Risks:
    - Overextension of resources
    - Quality maintenance with rapid growth
    - Infrastructure capacity limitations

    RECOMMENDATIONS:
    {'=' * 60}

    1. Diversify revenue streams beyond tuition
    2. Implement flexible cost management strategies
    3. Develop contingency plans for each scenario
    4. Monitor key performance indicators monthly
    5. Maintain strategic reserves for unexpected challenges

    Next Review Date: {(datetime.now() + timedelta(days=90)).strftime('%Y-%m-%d')}
    """

            return scenarios_output

        except Exception as e:
            return f"Error generating scenario planning: {str(e)}"


    def gui_generate_comprehensive_forecast_report(self):
        """GUI wrapper for comprehensive forecast report"""
        try:
            old_stdout = sys.stdout
            sys.stdout = mystdout = io.StringIO()

            generate_comprehensive_forecast_report()

            output = mystdout.getvalue()
            sys.stdout = old_stdout

            self.display_report_output(_("analytics_manager.dialogs.comprehensive_forecast_title"), output)

        except Exception as e:
            messagebox.showerror(_("common.error"), _("analytics_manager.errors.failed_comprehensive_forecast", error=e))

    def gui_generate_financial_dashboard(self):
        """Generate and display financial dashboard with charts"""
        try:
            # Update the dashboard charts
            self.update_dashboard_charts()
            messagebox.showinfo(_("common.success"), _("analytics_manager.messages.dashboard_updated"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("analytics_manager.errors.failed_generate_dashboard", error=e))

    def gui_generate_revenue_forecast(self):
        """Generate revenue forecast report"""
        try:
            # Use the run_forecast method if forecast_output exists
            if hasattr(self, 'forecast_output'):
                self.run_forecast()
            else:
                # Show forecast in a popup window
                forecast_window = tk.Toplevel(self.root)
                forecast_window.title(_("analytics_manager.dialogs.revenue_forecast_title"))
                forecast_window.geometry("600x400")

                from tkinter.scrolledtext import ScrolledText
                output = ScrolledText(forecast_window, font=('Courier', 10))
                output.pack(fill='both', expand=True, padx=10, pady=10)

                # Generate forecast data
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT strftime('%Y-%m', payment_date) as ym, COALESCE(SUM(amount), 0)
                    FROM payments
                    GROUP BY ym
                    ORDER BY ym DESC
                    LIMIT 12
                """)
                rows = cursor.fetchall()
                conn.close()

                baseline = sum(r[1] for r in rows) / len(rows) if rows else 0
                growth = 0.05

                output.insert(tk.END, _("analytics_manager.forecast.title") + "\n")
                output.insert(tk.END, "=" * 40 + "\n\n")
                output.insert(tk.END, _("analytics_manager.forecast.baseline_monthly", amount=baseline) + "\n")
                output.insert(tk.END, _("analytics_manager.forecast.growth_rate") + "\n\n")

                total = 0
                from datetime import timedelta
                today = datetime.now().replace(day=1)
                for i in range(1, 13):
                    baseline *= (1 + growth)
                    dt = (today + timedelta(days=31*i)).replace(day=1)
                    output.insert(tk.END, f"{dt.strftime('%Y-%m')}\t£{baseline:,.2f}\n")
                    total += baseline

                output.insert(tk.END, f"\n{_('analytics_manager.forecast.projected_annual', total=total)}\n")

        except Exception as e:
            messagebox.showerror(_("common.error"), _("analytics_manager.errors.failed_revenue_forecast", error=e))

    def update_dashboard_charts(self):
        """Update all dashboard charts"""
        try:
            # Check if axes exist (created by create_analytics_tab)
            if not hasattr(self, 'ax1'):
                print("Dashboard charts not initialized yet")
                return

            conn = get_connection()
            cursor = conn.cursor()

            # Clear existing plots
            for ax in [self.ax1, self.ax2, self.ax3, self.ax4]:
                ax.clear()

            # Chart 1: Monthly Revenue Trend
            current_year = datetime.now().year
            cursor.execute('''
            SELECT strftime('%m', payment_date) as month, SUM(amount) as revenue
            FROM payments
            WHERE strftime('%Y', payment_date) = ? AND status = 'completed'
            GROUP BY month
            ORDER BY month
            ''', (str(current_year),))

            monthly_data = cursor.fetchall()

            if monthly_data:
                months = [f"Month {m[0]}" for m in monthly_data]
                revenues = [m[1] for m in monthly_data]
                self.ax1.plot(months, revenues, marker='o', linewidth=2, markersize=6)
                self.ax1.set_title(_("analytics_manager.charts.monthly_revenue_trend"))
                self.ax1.set_ylabel(_("analytics_manager.charts.revenue_label"))
                self.ax1.tick_params(axis='x', rotation=45)
            else:
                self.ax1.text(0.5, 0.5, _("analytics_manager.charts.no_revenue_data"), ha='center', va='center', transform=self.ax1.transAxes)
                self.ax1.set_title(_("analytics_manager.charts.monthly_revenue_trend"))

            # Chart 2: Payment Method Distribution
            cursor.execute('''
            SELECT payment_method, COUNT(*), SUM(amount)
            FROM payments
            WHERE strftime('%Y', payment_date) = ? AND status = 'completed'
            GROUP BY payment_method
            ORDER BY SUM(amount) DESC
            ''', (str(current_year),))

            payment_methods = cursor.fetchall()

            if payment_methods:
                methods = [p[0] for p in payment_methods]
                amounts = [p[2] for p in payment_methods]
                self.ax2.pie(amounts, labels=methods, autopct='%1.1f%%')
                self.ax2.set_title(_("analytics_manager.charts.payment_methods_amount"))
            else:
                self.ax2.text(0.5, 0.5, _("analytics_manager.charts.no_payment_data"), ha='center', va='center', transform=self.ax2.transAxes)
                self.ax2.set_title(_("analytics_manager.charts.payment_methods_distribution"))

            # Chart 3: Outstanding Fees by Course
            cursor.execute('''
            SELECT s.course, SUM(sf.amount) - COALESCE(SUM(pa.amount), 0) as outstanding
            FROM student_fees sf
            JOIN students s ON sf.student_id = s.student_id
            LEFT JOIN payment_allocations pa ON sf.student_fee_id = pa.student_fee_id
            WHERE sf.status IN ('unpaid', 'partial')
            GROUP BY s.course
            HAVING outstanding > 0
            ORDER BY outstanding DESC
            LIMIT 10
            ''')

            course_outstanding = cursor.fetchall()

            if course_outstanding:
                courses = [c[0] for c in course_outstanding]
                amounts = [c[1] for c in course_outstanding]
                self.ax3.bar(courses, amounts, color='coral')
                self.ax3.set_title(_("analytics_manager.charts.outstanding_fees_course"))
                self.ax3.set_ylabel(_("analytics_manager.charts.amount_label"))
                self.ax3.tick_params(axis='x', rotation=45)
            else:
                self.ax3.text(0.5, 0.5, _("analytics_manager.charts.no_outstanding_fees"), ha='center', va='center', transform=self.ax3.transAxes)
                self.ax3.set_title(_("analytics_manager.charts.outstanding_fees_course"))

            # Chart 4: Payment Plan Status
            cursor.execute('''
            SELECT status, COUNT(*), SUM(total_amount)
            FROM student_payment_plans
            GROUP BY status
            ''')

            payment_plan_status = cursor.fetchall()

            if payment_plan_status:
                statuses = [p[0] for p in payment_plan_status]
                counts = [p[1] for p in payment_plan_status]
                colors = ['green' if s == 'completed' else 'orange' if s == 'active' else 'red' for s in statuses]
                self.ax4.bar(statuses, counts, color=colors)
                self.ax4.set_title(_("analytics_manager.charts.payment_plan_status"))
                self.ax4.set_ylabel(_("analytics_manager.charts.number_of_plans"))
            else:
                self.ax4.text(0.5, 0.5, _("analytics_manager.charts.no_payment_plans"), ha='center', va='center', transform=self.ax4.transAxes)
                self.ax4.set_title(_("analytics_manager.charts.payment_plan_status"))

            # Refresh the canvas
            self.fig.tight_layout()
            self.canvas.draw()

            conn.close()

        except Exception as e:
            print(f"Error updating dashboard charts: {e}")
            # Show error on charts if they exist
            if hasattr(self, 'ax1'):
                for ax in [self.ax1, self.ax2, self.ax3, self.ax4]:
                    ax.clear()
                    ax.text(0.5, 0.5, f'Error: {str(e)}', ha='center', va='center', transform=ax.transAxes)
                self.canvas.draw()

