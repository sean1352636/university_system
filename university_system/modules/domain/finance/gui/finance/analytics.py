"""Predictive analytics and forecasting"""

from university_system.infrastructure.database.db import DEFAULT_DB_PATH  # injected
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
from university_system.modules.domain.finance.gui.finance_reporting_gui import launch_financial_gui

# Import your existing modules - keep backward compatibility
try:
    from university_system.infrastructure.email.email_service import send_email
    from university_system.infrastructure.auth.user_authentication import UserAuth, get_global_auth
    from university_system.infrastructure.database.db import get_connection
    from university_system.infrastructure.logging.log_config import configure_logging, get_log_file
except ImportError:
    # Fallback for backward compatibility
    def send_email(*args, **kwargs):
        return True
    
    class UserAuth:
        def __init__(self):
            self.current_user = {"username": "admin"}
        def check_permission(self, p):
            return True
    
    from pathlib import Path
    def get_connection():
        """
        Fallback database connection for standalone mode.
        Use the central student_records.db located in the refactored/db_files
        directory rather than creating an enhanced_student_finance.db in the
        current working directory. This ensures the application operates on
        a single database file when the main refactored modules are not
        available.
        """
        # Determine the project root (refactored directory) one level above finance
        base_dir = Path(__file__).resolve().parents[1]
        db_path = base_dir / "db_files" / str(DEFAULT_DB_PATH)
        return sqlite3.connect(str(DEFAULT_DB_PATH))
    
    def configure_logging(name=None):
        return logging.getLogger(name or __name__)
    
    def get_log_file(name):
        from university_system.modules.shared.constants import paths
        return str(paths.LOG_DIR / name)

# Import all required finance functions from common_imports module
from university_system.modules.domain.finance.gui.finance.common_imports import *

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




class AnalyticsManager:
    """Predictive analytics and forecasting"""

    def __init__(self, gui):
        """Initialize manager with reference to main GUI"""
        self.gui = gui
        self.root = gui.root
        self.conn = gui.conn
        try:
            self.finance_system = gui.finance_system
        except:
            self.finance_system = None

        def create_analytics_tab(self):
            """Create analytics and dashboard tab"""
            tab = tk.Frame(self.content_frame, bg='white')
            self.tab_frames['analytics'] = tab
            
            main_frame = ttk.Frame(tab, padding=10)
            main_frame.pack(fill='both', expand=True)
            
            # Control buttons
            control_frame = ttk.LabelFrame(main_frame, text="Analytics & Reports", padding=10)
            control_frame.pack(fill='x', pady=(0, 10))
            
            buttons = [
                ("📊 Financial Dashboard", self.gui_generate_financial_dashboard),
                ("🔮 Predictive Analytics", self.gui_generate_predictive_analytics),
                ("🛡️ Fraud Detection", self.gui_detect_payment_fraud),
                ("📈 Revenue Forecast", self.gui_generate_revenue_forecast)
            ]
            
            for i, (text, command) in enumerate(buttons):
                ttk.Button(control_frame, text=text, command=command, width=25).grid(row=i//2, column=i%2, padx=10, pady=5)
            
            # Charts frame
            charts_frame = ttk.LabelFrame(main_frame, text="Dashboard", padding=10)
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
            forecast_frame = tk.Frame(self.content_frame, bg='white')
            self.tab_frames['forecasting'] = forecast_frame
            
            # Forecasting toolbar
            toolbar = tk.Frame(forecast_frame, bg='white')
            toolbar.pack(fill='x', padx=10, pady=5)
            
            tk.Button(toolbar, text="📈 Revenue Forecast", command=self.generate_revenue_forecast,
                     bg=self.colors['success'], fg='white').pack(side='left', padx=5)
            tk.Button(toolbar, text="🎓 Enrollment Projections", command=self.enrollment_projections,
                     bg=self.colors['secondary'], fg='white').pack(side='left', padx=5)
            tk.Button(toolbar, text="💰 Cash Flow Analysis", command=self.cash_flow_analysis,
                     bg=self.colors['warning'], fg='white').pack(side='left', padx=5)
            tk.Button(toolbar, text="⚠️ Risk Analysis", command=self.risk_analysis,
                     bg=self.colors['danger'], fg='white').pack(side='left', padx=5)
            tk.Button(toolbar, text="🎯 Scenario Planning", command=self.scenario_planning,
                     bg=self.colors['dark'], fg='white').pack(side='left', padx=5)
            
            # Forecasting content
            forecast_notebook = ttk.Notebook(forecast_frame)
            forecast_notebook.pack(fill='both', expand=True, padx=10, pady=10)
            
            # Revenue forecasting tab
            revenue_frame = ttk.Frame(forecast_notebook)
            forecast_notebook.add(revenue_frame, text="Revenue Forecast")
            
            # Forecast parameters frame
            params_frame = tk.LabelFrame(revenue_frame, text="Forecast Parameters", font=('Arial', 10, 'bold'))
            params_frame.pack(fill='x', padx=10, pady=5)
            
            # Parameters
            tk.Label(params_frame, text="Forecast Period (months):").grid(row=0, column=0, sticky='w', padx=5, pady=2)
            self.forecast_months_var = tk.StringVar(value="12")
            tk.Entry(params_frame, textvariable=self.forecast_months_var, width=10).grid(row=0, column=1, padx=5, pady=2)
            
            tk.Label(params_frame, text="Growth Rate (%):").grid(row=0, column=2, sticky='w', padx=5, pady=2)
            self.growth_rate_var = tk.StringVar(value="5.0")
            tk.Entry(params_frame, textvariable=self.growth_rate_var, width=10).grid(row=0, column=3, padx=5, pady=2)
            
            tk.Button(params_frame, text="Generate Forecast", command=self.run_forecast,
                     bg=self.colors['secondary'], fg='white').grid(row=0, column=4, padx=10, pady=2)
            
            # Forecast results
            self.forecast_output = ScrolledText(revenue_frame, height=20, font=('Courier', 9))
            self.forecast_output.pack(fill='both', expand=True, padx=10, pady=10)
            
            # Scenarios tab
            scenarios_frame = ttk.Frame(forecast_notebook)
            forecast_notebook.add(scenarios_frame, text="Scenarios")
            
            # Scenario comparison
            scenario_label = tk.Label(scenarios_frame, text="Financial Scenarios Comparison", 
                                    font=('Arial', 14, 'bold'))
            scenario_label.pack(pady=10)
            
            self.scenarios_tree = ttk.Treeview(scenarios_frame,
                                             columns=('scenario', 'students', 'revenue', 'expenses', 'net'),
                                             show='headings')
            for col in self.scenarios_tree['columns']:
                self.scenarios_tree.heading(col, text=col.replace('_', ' ').title())
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
                messagebox.showerror("Error", f"Failed to generate revenue forecast: {str(e)}")
        

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
                messagebox.showerror("Error", f"Failed to generate enrollment projections: {str(e)}")
        

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
                messagebox.showerror("Error", f"Failed to generate cash flow analysis: {str(e)}")
        

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
                messagebox.showerror("Error", f"Failed to generate risk analysis: {str(e)}")
    

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
                self.forecast_output.insert(tk.END, 'Revenue Forecast\n')
                self.forecast_output.insert(tk.END, '=================\n')
                total = 0.0
                for ym, amt in projections:
                    self.forecast_output.insert(tk.END, f"{ym}\t£{amt:,.2f}\n")
                    total += amt
                self.forecast_output.insert(tk.END, f"\nProjected total: £{total:,.2f}\n")
                self.update_status('Forecast generated')
            except Exception:
                pass
    

        def gui_generate_predictive_analytics(self):
            """GUI wrapper for predictive analytics"""
            try:
                self.update_status("Generating predictive analytics...")
                
                def generate_analytics():
                    old_stdout = sys.stdout
                    sys.stdout = mystdout = io.StringIO()
                    
                    generate_predictive_analytics()
                    
                    output = mystdout.getvalue()
                    sys.stdout = old_stdout
                    
                    self.root.after(0, lambda: self.display_report_output("Predictive Analytics", output))
                    
                threading.Thread(target=generate_analytics, daemon=True).start()
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to generate predictive analytics: {e}")
        

        def gui_detect_payment_fraud(self):
            """GUI wrapper for fraud detection"""
            try:
                self.update_status("Running fraud detection analysis...")
                
                def detect_fraud():
                    old_stdout = sys.stdout
                    sys.stdout = mystdout = io.StringIO()
                    
                    detect_payment_fraud()
                    
                    output = mystdout.getvalue()
                    sys.stdout = old_stdout
                    
                    self.root.after(0, lambda: self.display_report_output("Fraud Detection Report", output))
                    
                threading.Thread(target=detect_fraud, daemon=True).start()
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to run fraud detection: {e}")
        

        def gui_detect_payment_fraud_original(self):
            """GUI wrapper for detect_payment_fraud from original finance.py"""
            try:
                old_stdout = sys.stdout
                sys.stdout = mystdout = io.StringIO()
                
                detect_payment_fraud()
                
                output = mystdout.getvalue()
                sys.stdout = old_stdout
                
                self.show_tab('reports')  # Reports tab
                self.report_text.delete('1.0', tk.END)
                self.report_text.insert('1.0', output)
                self.update_status("Fraud detection analysis completed")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to run fraud detection: {e}")
    

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
                messagebox.showerror("Error", f"Failed to generate cash flow analysis: {e}")
        

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
                messagebox.showerror("Error", f"Failed to generate enrollment projections: {e}")
        

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
                messagebox.showerror("Error", f"Failed to generate risk analysis: {e}")
        

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
                    pass
                
                self.forecast_output.delete('1.0', tk.END)
                self.forecast_output.insert('1.0', output)
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to generate scenario planning: {e}")
        

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
                
                self.display_report_output("Comprehensive Forecast Report", output)
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to generate comprehensive forecast: {e}")
        
