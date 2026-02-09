"""System settings and configuration"""

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
from university_system.modules.domain.finance.gui.finance.common_imports import (
    # Aid type management
    create_aid_type,
    deactivate_aid_type,
    edit_aid_type,
    manage_aid_types,
    view_aid_types,
    # Aid application processing
    process_loan_payment,
    review_pending_aid_applications,
    track_loan_repayments,
    view_aid_application_detail,
    # Communication setup
    enhanced_notification_system,
    setup_email_config,
    setup_sms_config,
    test_email_service,
    test_sms_service,
    # Reporting
    monthly_revenue_trend_report,
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




class SettingsManager:
    """System settings and configuration"""

    def __init__(self, gui):
        """Initialize manager with reference to main GUI"""
        self.gui = gui
        self.root = gui.root
        self.conn = gui.conn
        self.auth = getattr(gui, 'auth', get_global_auth())
        try:
            self.finance_system = gui.finance_system
        except Exception:
            self.finance_system = None

    def update_status(self, message):
        """Update status bar message - delegates to GUI layout"""
        try:
            if hasattr(self.gui, 'layout') and hasattr(self.gui.layout, 'update_status'):
                self.gui.layout.update_status(message)
            elif hasattr(self.gui, 'update_status'):
                self.gui.update_status(message)
        except Exception:
            pass  # Silently ignore if status update fails

    def create_settings_tab(self):
        """Create settings and configuration tab"""
        settings_frame = tk.Frame(self.gui.layout.content_frame, bg='white')
        self.gui.layout.tab_frames['settings'] = settings_frame
        
        # Settings main frame
        main_frame = tk.Frame(settings_frame, bg='white')
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Title
        tk.Label(main_frame, text=_("finance_gui.settings.system_settings_title"), font=('Arial', 18, 'bold'), bg='white').pack(pady=10)

        # Settings notebook
        settings_notebook = ttk.Notebook(main_frame)
        settings_notebook.pack(fill='both', expand=True, pady=10)

        # General settings
        general_frame = ttk.Frame(settings_notebook)
        settings_notebook.add(general_frame, text=_("finance_gui.settings.general_tab"))
        self.create_general_settings(general_frame)

        # Currency settings
        currency_frame = ttk.Frame(settings_notebook)
        settings_notebook.add(currency_frame, text=_("finance_gui.settings.currency_tab"))
        self.create_currency_settings(currency_frame)

        # Notification settings
        notification_frame = ttk.Frame(settings_notebook)
        settings_notebook.add(notification_frame, text=_("finance_gui.settings.notifications_tab"))
        self.create_notification_settings(notification_frame)

        # System maintenance
        maintenance_frame = ttk.Frame(settings_notebook)
        settings_notebook.add(maintenance_frame, text=_("finance_gui.settings.maintenance_tab"))
        self.create_maintenance_settings(maintenance_frame)
    

    def create_general_settings(self, parent):
        """Create general settings interface"""
        # Academic year setting
        year_frame = tk.LabelFrame(parent, text=_("finance_gui.settings.academic_year_frame"), font=('Arial', 10, 'bold'))
        year_frame.pack(fill='x', padx=10, pady=10)

        tk.Label(year_frame, text=_("finance_gui.settings.current_academic_year")).grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.academic_year_var = tk.StringVar(value="2024-2025")
        tk.Entry(year_frame, textvariable=self.academic_year_var, width=15).grid(row=0, column=1, padx=5, pady=5)

        # Default settings
        defaults_frame = tk.LabelFrame(parent, text=_("finance_gui.settings.default_values_frame"), font=('Arial', 10, 'bold'))
        defaults_frame.pack(fill='x', padx=10, pady=10)

        tk.Label(defaults_frame, text=_("finance_gui.settings.grace_period_label")).grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.grace_period_var = tk.StringVar(value="7")
        tk.Entry(defaults_frame, textvariable=self.grace_period_var, width=10).grid(row=0, column=1, padx=5, pady=5)

        tk.Label(defaults_frame, text=_("finance_gui.settings.late_fee_amount_label")).grid(row=1, column=0, sticky='w', padx=5, pady=5)
        self.late_fee_var = tk.StringVar(value="50.00")
        tk.Entry(defaults_frame, textvariable=self.late_fee_var, width=10).grid(row=1, column=1, padx=5, pady=5)

        # Save button
        tk.Button(defaults_frame, text=_("finance_gui.settings.btn_save_settings"), command=self.save_general_settings,
                 bg=self.gui.layout.colors['success'], fg='white').grid(row=2, column=0, columnspan=2, pady=10)
    

    def save_general_settings(self):
        """Persist general finance settings for reuse."""
        settings = {
            'academic_year': self.academic_year_var.get().strip(),
            'grace_period_days': self.grace_period_var.get().strip(),
            'default_late_fee': self.late_fee_var.get().strip(),
            'updated_at': datetime.now().isoformat(),
        }
    
        settings_path = Path(__file__).resolve().parent / 'finance_general_settings.json'
    
        try:
            with settings_path.open('w', encoding='utf-8') as fp:
                json.dump(settings, fp, indent=2)
    
            if hasattr(self.gui, 'layout') and hasattr(self.gui.layout, 'update_status'):
                self.gui.layout.update_status(_("finance_gui.settings.settings_saved"))
            messagebox.showinfo(_("finance_gui.settings.settings_saved_title"), _("finance_gui.settings.settings_saved_message"))
        except Exception as exc:
            if hasattr(self.gui, 'layout') and hasattr(self.gui.layout, 'update_status'):
                self.gui.layout.update_status(_("finance_gui.settings.failed_save_settings"))
            messagebox.showerror(_("finance_gui.settings.save_error_title"), _("finance_gui.settings.save_error_message", error=str(exc)))
    

    def create_currency_settings(self, parent):
        """Create currency settings interface"""
        # Base currency
        base_frame = tk.LabelFrame(parent, text=_("finance_gui.settings.base_currency_frame"), font=('Arial', 10, 'bold'))
        base_frame.pack(fill='x', padx=10, pady=10)

        tk.Label(base_frame, text=_("finance_gui.settings.base_currency_label")).grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.base_currency_var = tk.StringVar(value="GBP")
        currency_combo = ttk.Combobox(base_frame, textvariable=self.base_currency_var,
                                     values=['GBP', 'USD', 'EUR', 'CAD', 'AUD'])
        currency_combo.grid(row=0, column=1, padx=5, pady=5)

        # Exchange rates
        rates_frame = tk.LabelFrame(parent, text=_("finance_gui.settings.exchange_rates_frame"), font=('Arial', 10, 'bold'))
        rates_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Exchange rates table
        self.exchange_rates_tree = ttk.Treeview(rates_frame,
                                              columns=('from_curr', 'to_curr', 'rate', 'date'),
                                              show='headings')
        for col in self.exchange_rates_tree['columns']:
            self.exchange_rates_tree.heading(col, text=col.replace('_', ' ').title())
        self.exchange_rates_tree.pack(fill='both', expand=True, padx=5, pady=5)

        # Update rates button
        tk.Button(rates_frame, text=_("finance_gui.settings.btn_update_rates"), command=self.gui_update_exchange_rates,
                 bg=self.gui.layout.colors['secondary'], fg='white').pack(pady=5)
    

    def create_notification_settings(self, parent):
        """Create notification settings interface"""
        # Email settings
        email_frame = tk.LabelFrame(parent, text=_("finance_gui.settings.email_settings_frame"), font=('Arial', 10, 'bold'))
        email_frame.pack(fill='x', padx=10, pady=10)

        tk.Label(email_frame, text=_("finance_gui.settings.smtp_server_label")).grid(row=0, column=0, sticky='w', padx=5, pady=2)
        self.smtp_server_var = tk.StringVar()
        tk.Entry(email_frame, textvariable=self.smtp_server_var, width=30).grid(row=0, column=1, padx=5, pady=2)

        tk.Label(email_frame, text=_("finance_gui.settings.smtp_port_label")).grid(row=1, column=0, sticky='w', padx=5, pady=2)
        self.smtp_port_var = tk.StringVar(value="587")
        tk.Entry(email_frame, textvariable=self.smtp_port_var, width=10).grid(row=1, column=1, padx=5, pady=2)

        tk.Button(email_frame, text=_("finance_gui.settings.btn_test_email"), command=self.gui_test_email_service,
                 bg=self.gui.layout.colors['warning'], fg='white').grid(row=2, column=0, columnspan=2, pady=5)

        # Notification templates
        templates_frame = tk.LabelFrame(parent, text=_("finance_gui.settings.notification_templates_frame"), font=('Arial', 10, 'bold'))
        templates_frame.pack(fill='both', expand=True, padx=10, pady=10)

        self.templates_tree = ttk.Treeview(templates_frame,
                                         columns=('template_id', 'name', 'type', 'active'),
                                         show='headings')
        for col in self.templates_tree['columns']:
            self.templates_tree.heading(col, text=col.replace('_', ' ').title())
        self.templates_tree.pack(fill='both', expand=True, padx=5, pady=5)
    

    def create_maintenance_settings(self, parent):
        """Create system maintenance interface"""
        # Database maintenance
        db_frame = tk.LabelFrame(parent, text=_("finance_gui.settings.db_maintenance_frame"), font=('Arial', 10, 'bold'))
        db_frame.pack(fill='x', padx=10, pady=10)

        tk.Button(db_frame, text=_("finance_gui.settings.btn_init_db"), command=self.initialize_database,
                 bg=self.gui.layout.colors['secondary'], fg='white', width=20).pack(pady=5)
        tk.Button(db_frame, text=_("finance_gui.settings.btn_clean_db"), command=self.clean_database,
                 bg=self.gui.layout.colors['warning'], fg='white', width=20).pack(pady=5)
        tk.Button(db_frame, text=_("finance_gui.settings.btn_backup_db"), command=self.backup_database,
                 bg=self.gui.layout.colors['success'], fg='white', width=20).pack(pady=5)
        tk.Button(db_frame, text=_("finance_gui.settings.btn_db_stats"), command=self.show_database_stats,
                 bg=self.gui.layout.colors['dark'], fg='white', width=20).pack(pady=5)

        # System information
        info_frame = tk.LabelFrame(parent, text=_("finance_gui.settings.system_info_frame"), font=('Arial', 10, 'bold'))
        info_frame.pack(fill='both', expand=True, padx=10, pady=10)

        self.system_info_text = ScrolledText(info_frame, height=10, font=('Courier', 9))
        self.system_info_text.pack(fill='both', expand=True, padx=5, pady=5)

        # Load system info
        self.load_system_info()
    

    def create_currency_tab(self):
        """Create multi-currency management tab"""
        tab = tk.Frame(self.gui.layout.content_frame, bg='white')
        self.gui.layout.tab_frames['currency'] = tab
        
        main_frame = ttk.Frame(tab, padding=20)
        main_frame.pack(fill='both', expand=True)
        
        # Currency controls
        control_frame = ttk.LabelFrame(main_frame, text=_("finance_gui.settings.currency_management_frame"), padding=15)
        control_frame.pack(fill='x', pady=(0, 20))

        ttk.Button(control_frame, text=_("finance_gui.settings.btn_update_exchange_rates"),
                  command=self.gui_update_exchange_rates, width=25).grid(row=0, column=0, padx=10, pady=5)
        ttk.Button(control_frame, text=_("finance_gui.settings.btn_currency_converter"),
                  command=self.gui_currency_converter, width=25).grid(row=0, column=1, padx=10, pady=5)

        # Currency converter frame
        converter_frame = ttk.LabelFrame(main_frame, text=_("finance_gui.settings.quick_converter_frame"), padding=15)
        converter_frame.pack(fill='x', pady=(0, 20))

        # Converter inputs
        ttk.Label(converter_frame, text=_("finance_gui.settings.amount_label")).grid(row=0, column=0, padx=5, pady=5, sticky='e')
        self.amount_var = tk.StringVar()
        ttk.Entry(converter_frame, textvariable=self.amount_var, width=15).grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(converter_frame, text=_("finance_gui.settings.from_label")).grid(row=0, column=2, padx=5, pady=5, sticky='e')
        self.from_currency_var = tk.StringVar(value='GBP')
        ttk.Combobox(converter_frame, textvariable=self.from_currency_var,
                    values=SUPPORTED_CURRENCIES, width=10, state='readonly').grid(row=0, column=3, padx=5, pady=5)

        ttk.Label(converter_frame, text=_("finance_gui.settings.to_label")).grid(row=0, column=4, padx=5, pady=5, sticky='e')
        self.to_currency_var = tk.StringVar(value='USD')
        ttk.Combobox(converter_frame, textvariable=self.to_currency_var,
                    values=SUPPORTED_CURRENCIES, width=10, state='readonly').grid(row=0, column=5, padx=5, pady=5)

        ttk.Button(converter_frame, text=_("finance_gui.settings.btn_convert"),
                  command=self.quick_convert).grid(row=0, column=6, padx=10, pady=5)

        self.conversion_result = tk.StringVar(value=_("finance_gui.settings.result_placeholder"))
        ttk.Label(converter_frame, textvariable=self.conversion_result, 
                 font=('Arial', 12, 'bold'), foreground='blue').grid(row=1, column=0, columnspan=7, pady=10)
        
        # Exchange rates display
        rates_frame = ttk.LabelFrame(main_frame, text=_("finance_gui.settings.current_rates_frame"), padding=15)
        rates_frame.pack(fill='both', expand=True)

        columns = (_("finance_gui.settings.column_from"), _("finance_gui.settings.column_to"), _("finance_gui.settings.column_rate"), _("finance_gui.settings.column_last_updated"), _("finance_gui.settings.column_source"))
        self.rates_tree = ttk.Treeview(rates_frame, columns=columns, show='headings', height=10)
        
        for col in columns:
            self.rates_tree.heading(col, text=col)
            self.rates_tree.column(col, width=120, anchor='center')
        
        # Scrollbars
        rates_v_scroll = ttk.Scrollbar(rates_frame, orient='vertical', command=self.rates_tree.yview)
        self.rates_tree.configure(yscrollcommand=rates_v_scroll.set)
        
        self.rates_tree.pack(side='left', fill='both', expand=True)
        rates_v_scroll.pack(side='right', fill='y')
        
        self.refresh_exchange_rates()
    

    def load_exchange_rates(self):
        """Load exchange rates data"""
        def load_thread():
            try:
                conn = get_connection()
                cursor = conn.cursor()
                
                cursor.execute('''
                SELECT from_currency, to_currency, exchange_rate, rate_date
                FROM exchange_rates
                ORDER BY from_currency, to_currency
                ''')
                
                rates = cursor.fetchall()
                conn.close()
                
                self.root.after(0, lambda: self.update_exchange_rates_table(rates))
                
            except Exception as e:
                print(f"Error loading exchange rates: {e}")
        
        threading.Thread(target=load_thread, daemon=True).start()
    

    def update_exchange_rates_table(self, rates):
        """Update exchange rates table"""
        try:
            for item in self.exchange_rates_tree.get_children():
                self.exchange_rates_tree.delete(item)
            
            for rate in rates:
                self.exchange_rates_tree.insert('', 'end', values=rate)
        except AttributeError:
            pass  # Table not created yet
    

    def gui_update_exchange_rates(self):
        """GUI for updating exchange rates"""
        if messagebox.askyesno(_("finance_gui.settings.confirm_title"), _("finance_gui.settings.confirm_update_rates")):
            try:
                self.update_status(_("finance_gui.settings.updating_rates"))
                
                def update_rates():
                    # Simulate API call with sample rates
                    sample_rates = {
                        'USD': 1.27,
                        'EUR': 1.17, 
                        'CAD': 1.71,
                        'AUD': 1.91,
                        'JPY': 188.50,
                        'CHF': 1.14
                    }
                    
                    conn = get_connection()
                    cursor = conn.cursor()
                    
                    current_date = datetime.now().strftime('%Y-%m-%d')
                    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    base_currency = 'GBP'
                    
                    rates_updated = 0
                    
                    for currency, rate in sample_rates.items():
                        if currency != base_currency:
                            cursor.execute('''
                            INSERT OR REPLACE INTO exchange_rates 
                            (from_currency, to_currency, exchange_rate, rate_date, source, created_at)
                            VALUES (?, ?, ?, ?, ?, ?)
                            ''', (base_currency, currency, rate, current_date, 'api', current_time))
                            rates_updated += 1
                    
                    # Update last update time
                    cursor.execute('''
                    UPDATE currency_settings 
                    SET last_rate_update = ?, updated_at = ?
                    ''', (current_time, current_time))
                    
                    conn.commit()
                    conn.close()
                    
                    messagebox.showinfo(_("finance_gui.settings.success_title"), _("finance_gui.settings.rates_updated", count=rates_updated))
                    self.refresh_exchange_rates()
                    self.update_status(_("finance_gui.settings.exchange_rates_updated"))

                thread = threading.Thread(target=update_rates)
                thread.daemon = True
                thread.start()

            except Exception as e:
                messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.failed_update_rates", error=str(e)))
    

    def gui_currency_converter(self):
        """Open detailed currency converter dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.settings.currency_converter_title"))
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()

        # Converter frame
        converter_frame = ttk.LabelFrame(dialog, text=_("finance_gui.settings.conversion_frame"), padding=20)
        converter_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # Amount input
        ttk.Label(converter_frame, text=_("finance_gui.settings.amount_label"), font=('Arial', 14)).grid(row=0, column=0, sticky='e', padx=10, pady=10)
        amount_var = tk.StringVar()
        amount_entry = ttk.Entry(converter_frame, textvariable=amount_var, font=('Arial', 14), width=15)
        amount_entry.grid(row=0, column=1, padx=10, pady=10)
        amount_entry.focus()
        
        # From currency
        ttk.Label(converter_frame, text=_("finance_gui.settings.from_label"), font=('Arial', 14)).grid(row=1, column=0, sticky='e', padx=10, pady=10)
        from_var = tk.StringVar(value='GBP')
        from_combo = ttk.Combobox(converter_frame, textvariable=from_var, values=SUPPORTED_CURRENCIES,
                                 state='readonly', font=('Arial', 14), width=10)
        from_combo.grid(row=1, column=1, padx=10, pady=10)

        # To currency
        ttk.Label(converter_frame, text=_("finance_gui.settings.to_label"), font=('Arial', 14)).grid(row=2, column=0, sticky='e', padx=10, pady=10)
        to_var = tk.StringVar(value='USD')
        to_combo = ttk.Combobox(converter_frame, textvariable=to_var, values=SUPPORTED_CURRENCIES, 
                               state='readonly', font=('Arial', 14), width=10)
        to_combo.grid(row=2, column=1, padx=10, pady=10)
        
        # Result display
        result_frame = ttk.LabelFrame(converter_frame, text=_("finance_gui.settings.conversion_result_frame"), padding=15)
        result_frame.grid(row=4, column=0, columnspan=2, pady=20, sticky='ew')

        result_var = tk.StringVar(value=_("finance_gui.settings.enter_amount_prompt"))
        result_label = ttk.Label(result_frame, textvariable=result_var, font=('Arial', 16, 'bold'), 
                                foreground='blue')
        result_label.pack()
        
        def convert_currency():
            try:
                amount = float(amount_var.get())
                from_currency = from_var.get()
                to_currency = to_var.get()

                if amount <= 0:
                    messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.amount_greater_zero"))
                    return
                
                if from_currency == to_currency:
                    result_var.set(f"{amount:.2f} {from_currency}")
                    return
                
                # Get exchange rate
                conn = get_connection()
                cursor = conn.cursor()
                
                cursor.execute('''
                SELECT exchange_rate FROM exchange_rates
                WHERE from_currency = ? AND to_currency = ?
                ORDER BY rate_date DESC, created_at DESC
                LIMIT 1
                ''', (from_currency, to_currency))
                
                result = cursor.fetchone()
                
                if result:
                    rate = result[0]
                    converted_amount = amount * rate
                    result_var.set(f"{amount:.2f} {from_currency} = {converted_amount:.2f} {to_currency}\nRate: 1 {from_currency} = {rate:.4f} {to_currency}")
                else:
                    # Try reverse conversion
                    cursor.execute('''
                    SELECT exchange_rate FROM exchange_rates
                    WHERE from_currency = ? AND to_currency = ?
                    ORDER BY rate_date DESC, created_at DESC
                    LIMIT 1
                    ''', (to_currency, from_currency))
                    
                    result = cursor.fetchone()
                    
                    if result:
                        rate = 1 / result[0]
                        converted_amount = amount * rate
                        result_var.set(f"{amount:.2f} {from_currency} = {converted_amount:.2f} {to_currency}\nRate: 1 {from_currency} = {rate:.4f} {to_currency}")
                    else:
                        result_var.set(_("finance_gui.settings.rate_not_found", **{"from": from_currency, "to": to_currency}))

                conn.close()

            except ValueError:
                messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.please_enter_valid_amount"))
            except Exception as e:
                messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.conversion_failed", error=str(e)))

        # Convert button
        ttk.Button(converter_frame, text=_("finance_gui.settings.btn_convert"), command=convert_currency).grid(row=3, column=0, columnspan=2, pady=20)
        
        # Bind Enter key to convert
        dialog.bind('<Return>', lambda e: convert_currency())
    

    def quick_convert(self):
        """Quick currency conversion in main interface"""
        try:
            amount = float(self.amount_var.get())
            from_currency = self.from_currency_var.get()
            to_currency = self.to_currency_var.get()
            
            if amount <= 0:
                self.conversion_result.set("Amount must be greater than zero")
                return
            
            if from_currency == to_currency:
                self.conversion_result.set(f"{amount:.2f} {from_currency}")
                return
            
            converted = convert_currency(amount, from_currency, to_currency)
            self.conversion_result.set(f"{amount:.2f} {from_currency} = {converted:.2f} {to_currency}")
            
        except ValueError:
            self.conversion_result.set("Please enter a valid amount")
        except Exception as e:
            self.conversion_result.set(f"Conversion failed: {e}")
    

    def refresh_exchange_rates(self):
        """Refresh exchange rates display"""
        # Check if rates_tree exists before attempting to update
        if not hasattr(self, 'rates_tree') or self.rates_tree is None:
            return

        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT from_currency, to_currency, exchange_rate, rate_date, source
            FROM exchange_rates
            ORDER BY rate_date DESC, from_currency, to_currency
            ''')

            rates = cursor.fetchall()

            # Clear existing items
            for item in self.rates_tree.get_children():
                self.rates_tree.delete(item)

            # Add rate data
            for rate in rates:
                from_curr, to_curr, rate_value, rate_date, source = rate
                self.rates_tree.insert('', 'end', values=(
                    from_curr, to_curr, f"{rate_value:.4f}", rate_date, source
                ))

            conn.close()

        except Exception as e:
            messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.failed_refresh_rates", error=str(e)))
    
    # Analytics and Dashboard Functions

    def convert_currency(amount, from_currency, to_currency):
        """Convert amount from one currency to another (original function)"""
        if from_currency == to_currency:
            return amount
        
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Get latest exchange rate
            cursor.execute('''
            SELECT exchange_rate FROM exchange_rates
            WHERE from_currency = ? AND to_currency = ?
            ORDER BY rate_date DESC, created_at DESC
            LIMIT 1
            ''', (from_currency, to_currency))
            
            result = cursor.fetchone()
            
            if result:
                rate = result[0]
                converted_amount = amount * rate
                conn.close()
                return converted_amount
            else:
                # Try reverse conversion
                cursor.execute('''
                SELECT exchange_rate FROM exchange_rates
                WHERE from_currency = ? AND to_currency = ?
                ORDER BY rate_date DESC, created_at DESC
                LIMIT 1
                ''', (to_currency, from_currency))
                
                result = cursor.fetchone()
                
                if result:
                    rate = 1 / result[0]
                    converted_amount = amount * rate
                    conn.close()
                    return converted_amount
                else:
                    conn.close()
                    print(f"Exchange rate not found for {from_currency}/{to_currency}")
                    return amount
        
        except sqlite3.Error as e:
            print(f"Database error in currency conversion: {e}")
            return amount
    
    # System and utility functions

    def load_notification_templates(self):
        """Load notification templates"""
        def load_thread():
            try:
                conn = get_connection()
                cursor = conn.cursor()
                
                cursor.execute('''
                SELECT template_id, template_name, template_type, is_active
                FROM notification_templates
                ORDER BY template_type, template_name
                ''')
                
                templates = cursor.fetchall()
                conn.close()
                
                self.root.after(0, lambda: self.update_notification_templates(templates))
                
            except Exception as e:
                print(f"Error loading notification templates: {e}")
        
        threading.Thread(target=load_thread, daemon=True).start()
    

    def update_notification_templates(self, templates):
        """Update notification templates table"""
        try:
            for item in self.templates_tree.get_children():
                self.templates_tree.delete(item)
            
            for template in templates:
                template_id, name, template_type, is_active = template
                active_str = "Yes" if is_active else "No"
                display_data = (template_id, name, template_type, active_str)
                self.templates_tree.insert('', 'end', values=display_data)
        except AttributeError:
            pass  # Table not created yet
    

    def load_system_info(self):
        """Load system information"""
        try:
            import sys
            # Use the shared DEFAULT_DB_PATH for database status and metadata.  This ensures
            # that the GUI reflects the correct database location even when the working
            # directory changes.  Import inside the method to avoid circular
            # dependencies on module load.
            from university_system.infrastructure.database.db import DEFAULT_DB_PATH
            db_exists = os.path.exists(DEFAULT_DB_PATH)
            last_modified = (
                datetime.fromtimestamp(os.path.getmtime(DEFAULT_DB_PATH)).strftime('%Y-%m-%d %H:%M:%S')
                if db_exists else 'N/A'
            )
            info_text = f"""System Information
    ===================
    Database: {os.path.basename(DEFAULT_DB_PATH)}
    Status: {'Connected' if db_exists else 'Not Found'}
    Last Modified: {last_modified}
    
    Version: 2.0.0 GUI
    GUI Framework: Tkinter
    Python Version: {sys.version}
    Platform: {sys.platform}
    
    Current User: {self.auth.current_user['username'] if self.auth and self.auth.current_user else 'Not Authenticated'}
    Session Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    """
            
            self.system_info_text.delete('1.0', tk.END)
            self.system_info_text.insert('1.0', info_text)
        except Exception as e:
            print(f"Error loading system info: {e}")
    
    # ==================== DIALOG METHODS ====================
    
    

    def gui_setup_email_config(self):
        """GUI wrapper for setup_email_config"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.settings.email_config_title"))
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()

        form_frame = ttk.LabelFrame(dialog, text=_("finance_gui.settings.email_settings_config_frame"), padding=20)
        form_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # SMTP Server
        ttk.Label(form_frame, text=_("finance_gui.settings.smtp_server_label")).pack(anchor='w', pady=5)
        smtp_var = tk.StringVar(value="smtp.gmail.com")
        ttk.Entry(form_frame, textvariable=smtp_var).pack(anchor='w', fill='x', pady=5)
        
        # Port
        ttk.Label(form_frame, text=_("finance_gui.settings.port_label")).pack(anchor='w', pady=5)
        port_var = tk.StringVar(value="587")
        ttk.Entry(form_frame, textvariable=port_var).pack(anchor='w', fill='x', pady=5)

        # Username
        ttk.Label(form_frame, text=_("finance_gui.settings.username_label")).pack(anchor='w', pady=5)
        username_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=username_var).pack(anchor='w', fill='x', pady=5)

        # Password
        ttk.Label(form_frame, text=_("finance_gui.settings.password_label")).pack(anchor='w', pady=5)
        password_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=password_var, show="*").pack(anchor='w', fill='x', pady=5)
        
        def save_config():
            try:
                smtp_server = smtp_var.get().strip()
                port = int(port_var.get())
                username = username_var.get().strip()
                password = password_var.get().strip()

                if not all([smtp_server, port, username, password]):
                    messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.all_fields_required"))
                    return

                setup_email_config(smtp_server, port, username, password)
                messagebox.showinfo(_("finance_gui.settings.success_title"), _("finance_gui.settings.email_config_saved"))
                dialog.destroy()

            except ValueError:
                messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.invalid_port"))
            except Exception as e:
                messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.failed_save_email_config", error=str(e)))

        ttk.Button(form_frame, text=_("finance_gui.settings.btn_save_config"), command=save_config).pack(pady=20)
    

    def gui_setup_sms_config(self):
        """GUI wrapper for setup_sms_config"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.settings.sms_config_title"))
        dialog.geometry("500x350")
        dialog.transient(self.root)
        dialog.grab_set()

        form_frame = ttk.LabelFrame(dialog, text=_("finance_gui.settings.sms_settings_frame"), padding=20)
        form_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # Service provider
        ttk.Label(form_frame, text=_("finance_gui.settings.sms_provider_label")).pack(anchor='w', pady=5)
        provider_var = tk.StringVar(value="twilio")
        provider_combo = ttk.Combobox(form_frame, textvariable=provider_var,
                                     values=["twilio", "aws_sns"], state='readonly')
        provider_combo.pack(anchor='w', fill='x', pady=5)

        # Account SID / Access Key
        ttk.Label(form_frame, text=_("finance_gui.settings.account_sid_label")).pack(anchor='w', pady=5)
        sid_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=sid_var).pack(anchor='w', fill='x', pady=5)

        # Auth Token / Secret Key
        ttk.Label(form_frame, text=_("finance_gui.settings.auth_token_label")).pack(anchor='w', pady=5)
        token_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=token_var, show="*").pack(anchor='w', fill='x', pady=5)
        
        def save_config():
            try:
                provider = provider_var.get()
                sid = sid_var.get().strip()
                token = token_var.get().strip()

                if not all([provider, sid, token]):
                    messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.all_fields_required"))
                    return

                setup_sms_config(provider, sid, token)
                messagebox.showinfo(_("finance_gui.settings.success_title"), _("finance_gui.settings.sms_config_saved"))
                dialog.destroy()

            except Exception as e:
                messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.failed_save_sms_config", error=str(e)))

        ttk.Button(form_frame, text=_("finance_gui.settings.btn_save_config"), command=save_config).pack(pady=20)
    

    def gui_test_email_service(self):
        """GUI wrapper for test_email_service"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.settings.test_email_title"))
        dialog.geometry("400x300")
        dialog.transient(self.root)
        dialog.grab_set()

        form_frame = ttk.LabelFrame(dialog, text=_("finance_gui.settings.email_test_frame"), padding=20)
        form_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # Test email address
        ttk.Label(form_frame, text=_("finance_gui.settings.test_email_address_label")).pack(anchor='w', pady=5)
        email_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=email_var).pack(anchor='w', fill='x', pady=5)
        
        def run_test():
            try:
                test_email = email_var.get().strip()
                if not test_email:
                    messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.test_email_required"))
                    return

                test_email_service(test_email)
                messagebox.showinfo(_("finance_gui.settings.success_title"), _("finance_gui.settings.test_email_sent", email=test_email))
                dialog.destroy()

            except Exception as e:
                messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.email_test_failed", error=str(e)))

        ttk.Button(form_frame, text=_("finance_gui.settings.btn_send_test_email"), command=run_test).pack(pady=20)
    

    def gui_test_sms_service(self):
        """GUI wrapper for test_sms_service"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.settings.test_sms_title"))
        dialog.geometry("400x300")
        dialog.transient(self.root)
        dialog.grab_set()

        form_frame = ttk.LabelFrame(dialog, text=_("finance_gui.settings.sms_test_frame"), padding=20)
        form_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # Test phone number
        ttk.Label(form_frame, text=_("finance_gui.settings.test_phone_label")).pack(anchor='w', pady=5)
        phone_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=phone_var).pack(anchor='w', fill='x', pady=5)
        
        def run_test():
            try:
                test_phone = phone_var.get().strip()
                if not test_phone:
                    messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.test_phone_required"))
                    return

                test_sms_service(test_phone)
                messagebox.showinfo(_("finance_gui.settings.success_title"), _("finance_gui.settings.test_sms_sent", phone=test_phone))
                dialog.destroy()

            except Exception as e:
                messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.sms_test_failed", error=str(e)))

        ttk.Button(form_frame, text=_("finance_gui.settings.btn_send_test_sms"), command=run_test).pack(pady=20)
    

    def gui_enhanced_notification_system(self):
        """GUI wrapper for enhanced_notification_system"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.settings.enhanced_notifications_title"))
        dialog.geometry("600x500")
        dialog.transient(self.root)
        dialog.grab_set()

        try:
            old_stdout = sys.stdout
            sys.stdout = mystdout = io.StringIO()
            
            enhanced_notification_system()
            
            output = mystdout.getvalue()
            sys.stdout = old_stdout
            
            text_widget = ScrolledText(dialog, height=25, width=70, font=('Courier', 10))
            text_widget.pack(fill='both', expand=True, padx=10, pady=10)
            text_widget.insert('1.0', output)

            ttk.Button(dialog, text=_("finance_gui.settings.btn_close"), command=dialog.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.failed_notification_system", error=str(e)))
    
    # Add menu update methods to include new GUI functions in menus

    def gui_setup_automated_notifications(self):
        """GUI wrapper for notification setup"""
        try:
            # Call the original setup function logic
            conn = get_connection()
            cursor = conn.cursor()
            
            # Default notification schedules
            schedules = [
                (1, '{"fee_status": "unpaid", "days_before_due": 7}', 7, 3, 7, 1),
                (2, '{"fee_status": "unpaid", "days_overdue": 1}', -1, 5, 3, 1),
                (4, '{"payment_plan_created": true}', 0, 1, 0, 1)
            ]
            
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            for template_id, conditions, days_before, max_reminders, interval, is_active in schedules:
                cursor.execute('''
                INSERT OR REPLACE INTO notification_schedules 
                (template_id, trigger_condition, days_before_due, max_reminders, 
                 reminder_interval_days, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (template_id, conditions, days_before, max_reminders, interval, is_active, now, now))
            
            conn.commit()
            conn.close()
            
            messagebox.showinfo(_("finance_gui.settings.success_title"),
                               _("finance_gui.settings.notifications_setup_success"))

            self.update_status(_("finance_gui.settings.settings_saved"))

        except Exception as e:
            messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.failed_setup_notifications", error=str(e)))
    

    def gui_send_automated_notifications(self):
        """GUI wrapper for sending automated notifications"""
        if messagebox.askyesno(_("finance_gui.settings.confirm_title"), _("finance_gui.settings.confirm_send_notifications")):
            try:
                self.update_status(_("finance_gui.settings.sending_notifications"))
                
                def send_notifications():
                    # Simplified notification sending
                    notifications_sent = 0
                    
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()
                        
                        # Find overdue fees for notifications
                        cursor.execute('''
                        SELECT DISTINCT sf.student_id, s.first_name, s.last_name, s.email_address,
                               COUNT(*) as overdue_count, SUM(sf.amount) as total_overdue
                        FROM student_fees sf
                        JOIN students s ON sf.student_id = s.student_id
                        WHERE sf.status IN ('unpaid', 'partial') 
                        AND date(sf.due_date) < date('now')
                        GROUP BY sf.student_id
                        LIMIT 10
                        ''')
                        
                        overdue_students = cursor.fetchall()
                        
                        for student in overdue_students:
                            student_id, first_name, last_name, email, count, total = student
    
                            # Send overdue payment reminder using template system
                            try:
                                from university_system.infrastructure.email.template_utils import render_template

                                subject, message = render_template("finance/overdue_payment_reminder", {
                                    "first_name": first_name,
                                    "last_name": last_name,
                                    "overdue_count": str(count),
                                    "total_amount": f"{total:.2f}",
                                    "student_id": student_id
                                })

                                if not (subject and message):
                                    # Fallback if template not found
                                    subject = "Overdue Payment Reminder"
                                    message = f"Dear {first_name} {last_name}, you have {count} overdue fees totaling £{total:.2f}"
                            except Exception as e:
                                # Error handling - use fallback template
                                subject = "Overdue Payment Reminder"
                                message = f"Dear {first_name} {last_name}, you have {count} overdue fees totaling £{total:.2f}"
    
                            # In a real implementation, you would call actual email/SMS services here
                            print(f"📧 Notification sent to {email}: {subject}")
                            notifications_sent += 1
                        
                        conn.close()
                        
                    except Exception as e:
                        print(f"Error in notification sending: {e}")
                    
                    messagebox.showinfo(_("finance_gui.settings.notifications_sent_title"),
                                       _("finance_gui.settings.notifications_sent_message", count=notifications_sent))

                    self.update_status(_("finance_gui.settings.sent_notifications_status", count=notifications_sent))

                thread = threading.Thread(target=send_notifications)
                thread.daemon = True
                thread.start()

            except Exception as e:
                messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.failed_send_notifications", error=str(e)))
    

    def gui_system_settings(self):
        """GUI for system settings"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.settings.system_settings_dialog_title"))
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()

        # Settings notebook
        settings_notebook = ttk.Notebook(dialog)
        settings_notebook.pack(fill='both', expand=True, padx=20, pady=20)

        # General settings tab
        general_tab = ttk.Frame(settings_notebook)
        settings_notebook.add(general_tab, text=_("finance_gui.settings.general_settings_tab"))

        # Currency settings
        currency_frame = ttk.LabelFrame(general_tab, text=_("finance_gui.settings.currency_settings_frame"), padding=15)
        currency_frame.pack(fill='x', pady=10)

        ttk.Label(currency_frame, text=_("finance_gui.settings.base_currency_label")).pack(anchor='w')
        base_currency_var = tk.StringVar(value='GBP')
        ttk.Combobox(currency_frame, textvariable=base_currency_var, 
                    values=SUPPORTED_CURRENCIES, state='readonly').pack(anchor='w', pady=5)
        
        ttk.Label(currency_frame, text=_("finance_gui.settings.auto_update_rates_label")).pack(anchor='w', pady=(10,0))
        auto_update_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(currency_frame, variable=auto_update_var).pack(anchor='w')

        # Notification settings tab
        notification_tab = ttk.Frame(settings_notebook)
        settings_notebook.add(notification_tab, text=_("finance_gui.settings.notifications_settings_tab"))

        email_frame = ttk.LabelFrame(notification_tab, text=_("finance_gui.settings.email_settings_frame"), padding=15)
        email_frame.pack(fill='x', pady=10)

        ttk.Label(email_frame, text=_("finance_gui.settings.smtp_server_label")).pack(anchor='w')
        smtp_var = tk.StringVar(value='smtp.gmail.com')
        ttk.Entry(email_frame, textvariable=smtp_var, width=30).pack(anchor='w', pady=5)
        
        ttk.Label(email_frame, text=_("finance_gui.settings.from_email_label")).pack(anchor='w')
        from_email_var = tk.StringVar()
        ttk.Entry(email_frame, textvariable=from_email_var, width=30).pack(anchor='w', pady=5)

        def save_settings():
            try:
                # In a real implementation, save settings to database or config file
                messagebox.showinfo(_("finance_gui.settings.success_title"), _("finance_gui.settings.settings_saved_dialog"))
                dialog.destroy()
            except Exception as e:
                messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.failed_save_settings_dialog", error=str(e)))

        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text=_("finance_gui.settings.btn_save_settings"), command=save_settings).pack(side='left', padx=10)
        ttk.Button(button_frame, text=_("finance_gui.settings.btn_cancel"), command=dialog.destroy).pack(side='left', padx=10)
    
    # Report generation functions

    def create_aid_tab(self):
        """Create financial aid tab"""
        aid_frame = tk.Frame(self.gui.layout.content_frame, bg='white')
        self.gui.layout.tab_frames['aid'] = aid_frame

        # Aid toolbar
        toolbar = tk.Frame(aid_frame, bg='white')
        toolbar.pack(fill='x', padx=10, pady=5)

        new_aid_buttons = [
            (_("finance_gui.settings.manage_aid_types_title"), self.gui_manage_aid_types),
            (_("finance_gui.settings.edit_aid_type_title"), self.gui_edit_aid_type),
            (_("finance_gui.settings.deactivate_aid_type_title"), self.gui_deactivate_aid_type),
            (_("finance_gui.settings.review_pending_aid_title"), self.gui_review_pending_aid_applications),
            (_("finance_gui.settings.process_loan_payment_title"), self.gui_process_loan_payment),
            (_("finance_gui.settings.view_aid_application_title"), self.gui_view_aid_application_detail),
        ]

        tk.Button(toolbar, text=_("finance_gui.settings.aid_toolbar_new_application"), command=self.new_aid_application,
                 bg=self.gui.layout.colors['success'], fg='white').pack(side='left', padx=5)
        tk.Button(toolbar, text=_("finance_gui.settings.aid_toolbar_review_applications"), command=self.review_aid_applications,
                 bg=self.gui.layout.colors['warning'], fg='white').pack(side='left', padx=5)
        tk.Button(toolbar, text=_("finance_gui.settings.aid_toolbar_disburse_aid"), command=self.disburse_aid,
                 bg=self.gui.layout.colors['secondary'], fg='white').pack(side='left', padx=5)
        tk.Button(toolbar, text=_("finance_gui.settings.aid_toolbar_track_repayments"), command=self.track_loan_repayments,
                 bg=self.gui.layout.colors['dark'], fg='white').pack(side='left', padx=5)

        # Aid content with tabs
        aid_notebook = ttk.Notebook(aid_frame)
        aid_notebook.pack(fill='both', expand=True, padx=10, pady=10)

        # Applications tab
        apps_frame = ttk.Frame(aid_notebook)
        aid_notebook.add(apps_frame, text=_("finance_gui.settings.applications_tab"))
        
        self.aid_apps_tree = ttk.Treeview(apps_frame, 
                                         columns=('aid_id', 'student', 'type', 'amount', 'status'), 
                                         show='headings')
        for col in self.aid_apps_tree['columns']:
            self.aid_apps_tree.heading(col, text=col.replace('_', ' ').title())
        self.aid_apps_tree.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Aid types tab
        types_frame = ttk.Frame(aid_notebook)
        aid_notebook.add(types_frame, text=_("finance_gui.settings.aid_types_tab"))
        
        self.aid_types_tree = ttk.Treeview(types_frame,
                                          columns=('type_id', 'name', 'category', 'max_amount'),
                                          show='headings')
        for col in self.aid_types_tree['columns']:
            self.aid_types_tree.heading(col, text=col.replace('_', ' ').title())
        self.aid_types_tree.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Load aid data
        self.refresh_financial_aid()
    

    def new_aid_application(self):
        """Create new aid application"""
        student_id = simpledialog.askstring(_("finance_gui.settings.financial_aid_title"), _("finance_gui.settings.enter_student_id_prompt"))
        if student_id:
            aid_type = simpledialog.askstring(_("finance_gui.settings.financial_aid_title"), _("finance_gui.settings.enter_aid_type_prompt"))
            if aid_type:
                amount = simpledialog.askfloat(_("finance_gui.settings.financial_aid_title"), _("finance_gui.settings.enter_aid_amount_prompt"))
                if amount:
                    messagebox.showinfo(_("finance_gui.settings.success_title"), _("finance_gui.settings.aid_application_created", amount=f"£{amount:.2f}", student_id=student_id))
                    self.refresh_financial_aid()
    

    def review_aid_applications(self):
        """Review pending aid applications"""
        try:
            old_stdout = sys.stdout
            sys.stdout = mystdout = io.StringIO()
            
            review_pending_aid_applications()
            
            output = mystdout.getvalue()
            sys.stdout = old_stdout
            
            self.show_text_window(_("finance_gui.settings.aid_applications_review_title"), output)

        except Exception as e:
            sys.stdout = old_stdout
            messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.failed_review_applications", error=str(e)))
    

    def disburse_aid(self):
        """Disburse financial aid"""
        # Create disbursement dialog
        disburse_dialog = tk.Toplevel(self.root)
        disburse_dialog.title(_("finance_gui.settings.disburse_aid_title"))
        disburse_dialog.geometry("700x600")
        disburse_dialog.transient(self.root)

        ttk.Label(disburse_dialog, text=_("finance_gui.settings.disburse_aid_heading"),
                 font=('TkDefaultFont', 14, 'bold')).pack(pady=10)

        # Student selection
        selection_frame = ttk.LabelFrame(disburse_dialog, text=_("finance_gui.settings.student_selection_frame"), padding=15)
        selection_frame.pack(fill='x', padx=10, pady=10)

        ttk.Label(selection_frame, text=_("finance_gui.settings.student_id_label_form")).grid(row=0, column=0, sticky='w', pady=5)
        student_id_var = tk.StringVar()
        student_id_entry = ttk.Entry(selection_frame, textvariable=student_id_var, width=30)
        student_id_entry.grid(row=0, column=1, pady=5, padx=5)
    
        ttk.Label(selection_frame, text=_("finance_gui.settings.student_name_label_form")).grid(row=1, column=0, sticky='w', pady=5)
        student_name_label = ttk.Label(selection_frame, text="", foreground='blue')
        student_name_label.grid(row=1, column=1, sticky='w', pady=5, padx=5)

        def lookup_student():
            student_id = student_id_var.get().strip()
            if student_id:
                # Lookup student (mock implementation)
                student_name_label.config(text=_("finance_gui.settings.student_prefix", student_id=student_id))
                aid_details_frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Button(selection_frame, text=_("finance_gui.settings.lookup_student_btn"), command=lookup_student).grid(row=0, column=2, padx=5)

        # Aid details
        aid_details_frame = ttk.LabelFrame(disburse_dialog, text=_("finance_gui.settings.aid_details_frame"), padding=15)
    
        form_frame = ttk.Frame(aid_details_frame)
        form_frame.pack(fill='x')

        ttk.Label(form_frame, text=_("finance_gui.settings.aid_type_label_form")).grid(row=0, column=0, sticky='w', pady=5)
        aid_type_var = tk.StringVar(value="Grant")
        aid_type_combo = ttk.Combobox(form_frame, textvariable=aid_type_var,
                                      values=['Grant', 'Scholarship', 'Loan', 'Emergency Aid', 'Bursary'],
                                      width=28, state='readonly')
        aid_type_combo.grid(row=0, column=1, pady=5, padx=5)
    
        ttk.Label(form_frame, text=_("finance_gui.settings.amount_label_form")).grid(row=1, column=0, sticky='w', pady=5)
        amount_var = tk.StringVar()
        amount_entry = ttk.Entry(form_frame, textvariable=amount_var, width=30)
        amount_entry.grid(row=1, column=1, pady=5, padx=5)
    
        ttk.Label(form_frame, text=_("finance_gui.settings.payment_method_label_form")).grid(row=2, column=0, sticky='w', pady=5)
        method_var = tk.StringVar(value="Bank Transfer")
        method_combo = ttk.Combobox(form_frame, textvariable=method_var,
                                    values=['Bank Transfer', 'Cheque', 'Fee Reduction', 'Direct Credit'],
                                    width=28, state='readonly')
        method_combo.grid(row=2, column=1, pady=5, padx=5)
    
        ttk.Label(form_frame, text=_("finance_gui.settings.reference_label_form")).grid(row=3, column=0, sticky='w', pady=5)
        reference_var = tk.StringVar()
        reference_entry = ttk.Entry(form_frame, textvariable=reference_var, width=30)
        reference_entry.grid(row=3, column=1, pady=5, padx=5)
    
        ttk.Label(form_frame, text=_("finance_gui.settings.notes_label_form")).grid(row=4, column=0, sticky='nw', pady=5)
        notes_text = tk.Text(form_frame, height=4, width=30)
        notes_text.grid(row=4, column=1, pady=5, padx=5)

        # Disbursement summary
        summary_frame = ttk.LabelFrame(aid_details_frame, text=_("finance_gui.settings.disbursement_summary_frame"))
        summary_frame.pack(fill='x', pady=10)
    
        summary_label = ttk.Label(summary_frame, text="", font=('Courier', 9))
        summary_label.pack(padx=10, pady=10)
    
        def update_summary():
            try:
                amount = float(amount_var.get() or 0)
                summary_text = f"""
    Student ID:       {student_id_var.get()}
    Aid Type:         {aid_type_var.get()}
    Amount:           £{amount:,.2f}
    Payment Method:   {method_var.get()}
    Reference:        {reference_var.get() or 'N/A'}
    """
                summary_label.config(text=summary_text)
            except ValueError:
                summary_label.config(text=_("finance_gui.settings.invalid_amount_msg"))
    
        # Update summary when values change
        amount_var.trace('w', lambda *args: update_summary())
        aid_type_var.trace('w', lambda *args: update_summary())
        method_var.trace('w', lambda *args: update_summary())
    
        def process_disbursement():
            student_id = student_id_var.get().strip()
            if not student_id:
                messagebox.showwarning(_("finance_gui.settings.student_required_warning_title"), _("finance_gui.settings.student_required_warning_msg"), parent=disburse_dialog)
                return

            try:
                amount = float(amount_var.get())
                if amount <= 0:
                    raise ValueError(_("finance_gui.settings.amount_greater_zero"))
            except ValueError as e:
                messagebox.showwarning(_("finance_gui.settings.invalid_amount_warning_title"), str(e), parent=disburse_dialog)
                return

            if not reference_var.get().strip():
                messagebox.showwarning(_("finance_gui.settings.reference_required_warning_title"), _("finance_gui.settings.reference_required_warning_msg"), parent=disburse_dialog)
                return

            if messagebox.askyesno(_("finance_gui.settings.confirm_disbursement_title"),
                                  _("finance_gui.settings.confirm_disbursement_msg", amount=f"£{amount:,.2f}", aid_type=aid_type_var.get(), student_id=student_id),
                                  parent=disburse_dialog):
                # Process disbursement (mock implementation)
                messagebox.showinfo(_("finance_gui.settings.success_title"),
                                  _("finance_gui.settings.disbursement_success_msg", amount=f"£{amount:,.2f}", reference=reference_var.get()),
                                  parent=disburse_dialog)
                disburse_dialog.destroy()
                if hasattr(self, 'refresh_financial_aid'):
                    self.refresh_financial_aid()
    
        # Buttons
        button_frame = ttk.Frame(disburse_dialog)
        button_frame.pack(pady=15)

        ttk.Button(button_frame, text=_("finance_gui.settings.process_disbursement_btn"), command=process_disbursement).pack(side='left', padx=5)
        ttk.Button(button_frame, text=_("finance_gui.settings.btn_cancel"), command=disburse_dialog.destroy).pack(side='left', padx=5)
    

    def track_loan_repayments(self):
        """Track loan repayments"""
        try:
            old_stdout = sys.stdout
            sys.stdout = mystdout = io.StringIO()
            
            track_loan_repayments()
            
            output = mystdout.getvalue()
            sys.stdout = old_stdout
            
            self.show_text_window(_("finance_gui.settings.loan_repayments_title"), output)

        except Exception as e:
            sys.stdout = old_stdout
            messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.failed_track_repayments", error=str(e)))
    
    # ==================== BUDGET METHODS ====================
    

    def refresh_financial_aid(self):
        """Refresh financial aid data"""
        def refresh_thread():
            try:
                conn = get_connection()
                cursor = conn.cursor()
                
                # Get aid applications
                cursor.execute('''
                SELECT sfa.aid_id, s.first_name || ' ' || s.last_name as student_name,
                       fat.aid_name, sfa.awarded_amount, sfa.status
                FROM student_financial_aid sfa
                JOIN students s ON sfa.student_id = s.student_id
                JOIN financial_aid_types fat ON sfa.aid_type_id = fat.aid_type_id
                ORDER BY sfa.application_date DESC
                ''')
                
                aid_applications = cursor.fetchall()
                
                # Get aid types
                cursor.execute('''
                SELECT aid_type_id, aid_name, aid_category, max_amount
                FROM financial_aid_types
                WHERE is_active = 1
                ORDER BY aid_category, aid_name
                ''')
                
                aid_types = cursor.fetchall()
                conn.close()
                
                self.root.after(0, lambda: self.update_financial_aid_data(aid_applications, aid_types))
                
            except Exception as e:
                print(f"Error refreshing financial aid: {e}")
        
        refresh_thread()
    

    def update_financial_aid_data(self, aid_applications, aid_types):
        """Update financial aid data in UI"""
        # Update aid applications
        for item in self.aid_apps_tree.get_children():
            self.aid_apps_tree.delete(item)
        
        for app in aid_applications:
            aid_id, student_name, aid_name, amount, status = app
            display_data = (aid_id, student_name, aid_name, f"£{amount:.2f}", status)
            self.aid_apps_tree.insert('', 'end', values=display_data)
        
        # Update aid types
        for item in self.aid_types_tree.get_children():
            self.aid_types_tree.delete(item)
        
        for aid_type in aid_types:
            type_id, name, category, max_amount = aid_type
            max_amt_str = f"£{max_amount:.2f}" if max_amount else "Unlimited"
            display_data = (type_id, name, category, max_amt_str)
            self.aid_types_tree.insert('', 'end', values=display_data)
    

    def gui_manage_financial_aid(self):
        """Switch to financial aid tab"""
        self.show_tab('aid')
    

    def gui_manage_aid_types(self):
        """GUI wrapper for manage_aid_types"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.settings.manage_aid_types_title"))
        dialog.geometry("800x600")
        dialog.transient(self.root)
        dialog.grab_set()

        try:
            old_stdout = sys.stdout
            sys.stdout = mystdout = io.StringIO()
            
            manage_aid_types()
            
            output = mystdout.getvalue()
            sys.stdout = old_stdout
            
            text_widget = ScrolledText(dialog, height=25, width=90, font=('Courier', 10))
            text_widget.pack(fill='both', expand=True, padx=10, pady=10)
            text_widget.insert('1.0', output)
            
            ttk.Button(dialog, text=_("finance_gui.settings.btn_close"), command=dialog.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.failed_manage_aid_types", error=str(e)))
    

    def gui_edit_aid_type(self):
        """GUI wrapper for edit_aid_type"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.settings.edit_aid_type_title"))
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()

        form_frame = ttk.LabelFrame(dialog, text=_("finance_gui.settings.edit_aid_type_frame"), padding=20)
        form_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # Aid type ID
        ttk.Label(form_frame, text=_("finance_gui.settings.aid_type_id_label")).pack(anchor='w', pady=5)
        aid_id_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=aid_id_var).pack(anchor='w', fill='x', pady=5)
        
        # New name
        ttk.Label(form_frame, text=_("finance_gui.settings.new_name_label")).pack(anchor='w', pady=5)
        name_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=name_var).pack(anchor='w', fill='x', pady=5)

        # New max amount
        ttk.Label(form_frame, text=_("finance_gui.settings.new_max_amount_label")).pack(anchor='w', pady=5)
        amount_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=amount_var).pack(anchor='w', fill='x', pady=5)
        
        def edit_aid():
            try:
                aid_id = int(aid_id_var.get())
                new_name = name_var.get().strip()
                new_max_amount = float(amount_var.get()) if amount_var.get().strip() else None

                if not aid_id:
                    messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.aid_type_id_required"))
                    return

                edit_aid_type(aid_id, new_name, new_max_amount)
                messagebox.showinfo(_("finance_gui.settings.success_title"), _("finance_gui.settings.aid_type_updated"))
                dialog.destroy()

            except ValueError:
                messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.invalid_id_or_amount"))
            except Exception as e:
                messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.failed_edit_aid_type", error=str(e)))

        ttk.Button(form_frame, text=_("finance_gui.settings.update_aid_type_btn"), command=edit_aid).pack(pady=20)
    

    def gui_deactivate_aid_type(self):
        """GUI wrapper for deactivate_aid_type"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.settings.deactivate_aid_type_title"))
        dialog.geometry("400x200")
        dialog.transient(self.root)
        dialog.grab_set()

        form_frame = ttk.LabelFrame(dialog, text=_("finance_gui.settings.deactivate_aid_type_frame"), padding=20)
        form_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # Aid type ID
        ttk.Label(form_frame, text=_("finance_gui.settings.aid_type_id_to_deactivate")).pack(anchor='w', pady=5)
        aid_id_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=aid_id_var).pack(anchor='w', fill='x', pady=5)
        
        def deactivate_aid():
            try:
                aid_id = int(aid_id_var.get())

                if messagebox.askyesno(_("finance_gui.settings.confirm_title"), _("finance_gui.settings.confirm_deactivate_aid", aid_id=aid_id)):
                    deactivate_aid_type(aid_id)
                    messagebox.showinfo(_("finance_gui.settings.success_title"), _("finance_gui.settings.aid_type_deactivated"))
                    dialog.destroy()

            except ValueError:
                messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.invalid_aid_type_id"))
            except Exception as e:
                messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.failed_deactivate_aid_type", error=str(e)))

        ttk.Button(form_frame, text=_("finance_gui.settings.deactivate_btn"), command=deactivate_aid).pack(pady=20)
    

    def gui_review_pending_aid_applications(self):
        """GUI wrapper for review_pending_aid_applications"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.settings.review_pending_aid_title"))
        dialog.geometry("800x600")
        dialog.transient(self.root)
        dialog.grab_set()

        try:
            old_stdout = sys.stdout
            sys.stdout = mystdout = io.StringIO()
            
            review_pending_aid_applications()
            
            output = mystdout.getvalue()
            sys.stdout = old_stdout
            
            text_widget = ScrolledText(dialog, height=25, width=90, font=('Courier', 10))
            text_widget.pack(fill='both', expand=True, padx=10, pady=10)
            text_widget.insert('1.0', output)
            
            ttk.Button(dialog, text=_("finance_gui.settings.btn_close"), command=dialog.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.failed_review_pending_applications", error=str(e)))
    

    def gui_process_loan_payment(self):
        """GUI wrapper for process_loan_payment"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.settings.process_loan_payment_title"))
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()

        form_frame = ttk.LabelFrame(dialog, text=_("finance_gui.settings.loan_payment_details_frame"), padding=20)
        form_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # Loan ID
        ttk.Label(form_frame, text=_("finance_gui.settings.loan_id_label")).pack(anchor='w', pady=5)
        loan_id_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=loan_id_var).pack(anchor='w', fill='x', pady=5)

        # Payment amount
        ttk.Label(form_frame, text=_("finance_gui.settings.payment_amount_label")).pack(anchor='w', pady=5)
        amount_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=amount_var).pack(anchor='w', fill='x', pady=5)

        # Payment method
        ttk.Label(form_frame, text=_("finance_gui.settings.payment_method_label_form")).pack(anchor='w', pady=5)
        method_var = tk.StringVar(value="bank_transfer")
        method_combo = ttk.Combobox(form_frame, textvariable=method_var,
                                   values=["bank_transfer", "direct_debit", "check", "online"])
        method_combo.pack(anchor='w', fill='x', pady=5)
        
        def process_payment():
            try:
                loan_id = int(loan_id_var.get())
                amount = float(amount_var.get())
                method = method_var.get()

                if not all([loan_id, amount > 0, method]):
                    messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.all_fields_required"))
                    return

                process_loan_payment(loan_id, amount, method)
                messagebox.showinfo(_("finance_gui.settings.success_title"), _("finance_gui.settings.loan_payment_processed"))
                dialog.destroy()

            except ValueError:
                messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.invalid_loan_id_or_amount"))
            except Exception as e:
                messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.failed_process_loan_payment", error=str(e)))

        ttk.Button(form_frame, text=_("finance_gui.settings.process_payment_btn"), command=process_payment).pack(pady=20)
    

    def gui_view_aid_application_detail(self):
        """GUI wrapper for view_aid_application_detail"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.settings.view_aid_application_title"))
        dialog.geometry("700x500")
        dialog.transient(self.root)
        dialog.grab_set()

        # Application ID input
        input_frame = ttk.Frame(dialog, padding=10)
        input_frame.pack(fill='x')

        ttk.Label(input_frame, text=_("finance_gui.settings.application_id_label")).pack(side='left', padx=5)
        app_id_var = tk.StringVar()
        ttk.Entry(input_frame, textvariable=app_id_var, width=15).pack(side='left', padx=5)
        
        def show_details():
            app_id = app_id_var.get().strip()
            if not app_id:
                messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.application_id_required"))
                return

            try:
                app_id_int = int(app_id)
                old_stdout = sys.stdout
                sys.stdout = mystdout = io.StringIO()

                view_aid_application_detail(app_id_int)

                output = mystdout.getvalue()
                sys.stdout = old_stdout

                details_text.delete('1.0', tk.END)
                details_text.insert('1.0', output)

            except ValueError:
                messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.invalid_application_id"))
            except Exception as e:
                messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.failed_view_application_details", error=str(e)))

        ttk.Button(input_frame, text=_("finance_gui.settings.view_details_btn"), command=show_details).pack(side='left', padx=10)
        
        # Details display
        details_text = ScrolledText(dialog, height=20, width=80, font=('Courier', 10))
        details_text.pack(fill='both', expand=True, padx=10, pady=10)
    

    def gui_track_loan_repayments(self):
        """GUI wrapper for track_loan_repayments"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.settings.track_loan_repayments_title"))
        dialog.geometry("800x600")
        dialog.transient(self.root)
        dialog.grab_set()

        try:
            old_stdout = sys.stdout
            sys.stdout = mystdout = io.StringIO()
            
            track_loan_repayments()
            
            output = mystdout.getvalue()
            sys.stdout = old_stdout
            
            text_widget = ScrolledText(dialog, height=25, width=90, font=('Courier', 10))
            text_widget.pack(fill='both', expand=True, padx=10, pady=10)
            text_widget.insert('1.0', output)
            
            ttk.Button(dialog, text=_("finance_gui.settings.btn_close"), command=dialog.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.failed_track_repayments", error=str(e)))
    

    def gui_view_aid_types(self):
        """GUI wrapper for view_aid_types"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.settings.view_aid_types_title"))
        dialog.geometry("700x500")
        dialog.transient(self.root)
        dialog.grab_set()

        try:
            old_stdout = sys.stdout
            sys.stdout = mystdout = io.StringIO()
            
            view_aid_types()
            
            output = mystdout.getvalue()
            sys.stdout = old_stdout
            
            text_widget = ScrolledText(dialog, height=25, width=80, font=('Courier', 10))
            text_widget.pack(fill='both', expand=True, padx=10, pady=10)
            text_widget.insert('1.0', output)
            
            ttk.Button(dialog, text=_("finance_gui.settings.btn_close"), command=dialog.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.failed_view_aid_types", error=str(e)))
    

    def gui_create_aid_type(self):
        """GUI wrapper for create_aid_type"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.settings.create_aid_type_title"))
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()

        form_frame = ttk.LabelFrame(dialog, text=_("finance_gui.settings.aid_type_details_frame"), padding=20)
        form_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # Aid name
        ttk.Label(form_frame, text=_("finance_gui.settings.aid_type_name_label")).pack(anchor='w', pady=5)
        name_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=name_var).pack(anchor='w', fill='x', pady=5)

        # Category
        ttk.Label(form_frame, text=_("finance_gui.settings.category_label")).pack(anchor='w', pady=5)
        category_var = tk.StringVar()
        category_combo = ttk.Combobox(form_frame, textvariable=category_var,
                                     values=["scholarship", "grant", "loan", "work_study"])
        category_combo.pack(anchor='w', fill='x', pady=5)
        
        # Max amount
        ttk.Label(form_frame, text=_("finance_gui.settings.max_amount_label")).pack(anchor='w', pady=5)
        amount_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=amount_var).pack(anchor='w', fill='x', pady=5)

        # Description
        ttk.Label(form_frame, text=_("finance_gui.settings.description_label")).pack(anchor='w', pady=5)
        desc_text = tk.Text(form_frame, height=4, width=50)
        desc_text.pack(anchor='w', fill='both', expand=True, pady=5)
        
        def create_aid():
            try:
                name = name_var.get().strip()
                category = category_var.get().strip()
                max_amount = float(amount_var.get()) if amount_var.get().strip() else None
                description = desc_text.get("1.0", tk.END).strip()

                if not all([name, category]):
                    messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.name_and_category_required"))
                    return

                create_aid_type(name, category, max_amount, description)
                messagebox.showinfo(_("finance_gui.settings.success_title"), _("finance_gui.settings.aid_type_created"))
                dialog.destroy()

            except ValueError:
                messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.invalid_max_amount"))
            except Exception as e:
                messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.failed_create_aid_type", error=str(e)))

        ttk.Button(form_frame, text=_("finance_gui.settings.create_aid_type_btn"), command=create_aid).pack(pady=20)
    

    def create_scholarships_tab(self):
        """Create scholarships management tab"""
        tab = tk.Frame(self.gui.layout.content_frame, bg='white')
        self.gui.layout.tab_frames['scholarships'] = tab
        
        main_frame = ttk.Frame(tab, padding=20)
        main_frame.pack(fill='both', expand=True)
        
        # Control buttons
        control_frame = ttk.LabelFrame(main_frame, text=_("finance_gui.settings.scholarship_management_frame"), padding=15)
        control_frame.pack(fill='x', pady=(0, 20))

        buttons = [
            (_("finance_gui.settings.view_scholarships_btn"), self.gui_view_available_scholarships),
            (_("finance_gui.settings.create_scholarship_btn"), self.gui_create_new_scholarship),
            (_("finance_gui.settings.award_scholarship_btn"), self.gui_award_scholarship_to_student),
            (_("finance_gui.settings.scholarship_reports_btn"), self.gui_scholarship_reports)
        ]
        
        for i, (text, command) in enumerate(buttons):
            ttk.Button(control_frame, text=text, command=command, width=25).grid(row=i//2, column=i%2, padx=10, pady=5)
        
        # Scholarships display
        display_frame = ttk.LabelFrame(main_frame, text=_("finance_gui.settings.available_scholarships_frame"), padding=15)
        display_frame.pack(fill='both', expand=True)
        
        columns = ('ID', 'Name', 'Amount', 'Academic Year', 'Criteria', 'Deadline', 'Status')
        self.scholarships_tree = ttk.Treeview(display_frame, columns=columns, show='headings', height=12)
        
        for col in columns:
            self.scholarships_tree.heading(col, text=col)
            width = 150 if col in ['Name', 'Criteria'] else 100
            self.scholarships_tree.column(col, width=width, anchor='center')
        
        # Scrollbars
        scholar_v_scroll = ttk.Scrollbar(display_frame, orient='vertical', command=self.scholarships_tree.yview)
        scholar_h_scroll = ttk.Scrollbar(display_frame, orient='horizontal', command=self.scholarships_tree.xview)
        self.scholarships_tree.configure(yscrollcommand=scholar_v_scroll.set, xscrollcommand=scholar_h_scroll.set)
        
        self.scholarships_tree.pack(side='left', fill='both', expand=True)
        scholar_v_scroll.pack(side='right', fill='y')
        scholar_h_scroll.pack(side='bottom', fill='x')
        
        self.refresh_scholarships()
    

    def refresh_scholarships(self):
        """Refresh scholarships display"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT scholarship_id, scholarship_name, amount, academic_year, 
                   criteria, deadline,
                   CASE WHEN is_active = 1 THEN 'Active' ELSE 'Inactive' END as status
            FROM scholarships
            WHERE is_active = 1
            ORDER BY scholarship_name
            LIMIT 50
            ''')
            
            scholarships = cursor.fetchall()
            
            # Clear existing items if scholarships_tree exists
            if hasattr(self, 'scholarships_tree'):
                for item in self.scholarships_tree.get_children():
                    self.scholarships_tree.delete(item)
                
                # Add scholarship data
                for scholarship in scholarships:
                    scholarship_id, name, amount, year, criteria, deadline, status = scholarship
                    criteria_short = criteria[:30] + "..." if len(criteria) > 30 else criteria
                    
                    self.scholarships_tree.insert('', 'end', values=(
                        scholarship_id, name, f"£{amount:.2f}", year, 
                        criteria_short, deadline, status
                    ))
            
            conn.close()
            
        except Exception as e:
            print(f"Error refreshing scholarships: {e}")
    

    def gui_create_new_scholarship(self):
        """GUI wrapper for creating new scholarship"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.settings.create_scholarship_title"))
        dialog.geometry("600x600")
        dialog.transient(self.root)
        dialog.grab_set()

        # Scholarship details form
        form_frame = ttk.LabelFrame(dialog, text=_("finance_gui.settings.scholarship_details_frame"), padding=20)
        form_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # Scholarship name
        ttk.Label(form_frame, text=_("finance_gui.settings.scholarship_name_label"), font=('Arial', 12)).pack(anchor='w', pady=5)
        name_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=name_var, font=('Arial', 12), width=50).pack(anchor='w', pady=5)
        
        # Description
        ttk.Label(form_frame, text=_("finance_gui.settings.description_form_label"), font=('Arial', 12)).pack(anchor='w', pady=(15, 5))
        desc_text = tk.Text(form_frame, height=4, width=60, font=('Arial', 10))
        desc_text.pack(anchor='w', pady=5)

        # Amount
        ttk.Label(form_frame, text=_("finance_gui.settings.scholarship_amount_label"), font=('Arial', 12)).pack(anchor='w', pady=(15, 5))
        amount_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=amount_var, font=('Arial', 12), width=20).pack(anchor='w', pady=5)

        # Academic year
        ttk.Label(form_frame, text=_("finance_gui.settings.academic_year_form_label"), font=('Arial', 12)).pack(anchor='w', pady=(15, 5))
        year_var = tk.StringVar(value="2024-2025")
        ttk.Entry(form_frame, textvariable=year_var, font=('Arial', 12), width=20).pack(anchor='w', pady=5)

        # Eligibility criteria
        ttk.Label(form_frame, text=_("finance_gui.settings.eligibility_criteria_label"), font=('Arial', 12)).pack(anchor='w', pady=(15, 5))
        criteria_text = tk.Text(form_frame, height=3, width=60, font=('Arial', 10))
        criteria_text.pack(anchor='w', pady=5)

        # Deadline
        ttk.Label(form_frame, text=_("finance_gui.settings.deadline_label"), font=('Arial', 12)).pack(anchor='w', pady=(15, 5))
        deadline_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=deadline_var, font=('Arial', 12), width=20).pack(anchor='w', pady=5)
        
        def create_scholarship():
            try:
                name = name_var.get().strip()
                description = desc_text.get("1.0", tk.END).strip()
                amount = float(amount_var.get())
                academic_year = year_var.get().strip()
                criteria = criteria_text.get("1.0", tk.END).strip()
                deadline = deadline_var.get().strip()

                if not all([name, description, amount > 0, academic_year, criteria, deadline]):
                    messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.all_fields_required_scholarship"))
                    return
                
                # Call the original function indirectly
                conn = get_connection()
                cursor = conn.cursor()
                
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                cursor.execute('''
                INSERT INTO scholarships 
                (scholarship_name, description, amount, academic_year, criteria, deadline, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (name, description, amount, academic_year, criteria, deadline, now, now))
                
                scholarship_id = cursor.lastrowid
                conn.commit()
                conn.close()

                messagebox.showinfo(_("finance_gui.settings.success_title"), _("finance_gui.settings.scholarship_created_msg", scholarship_id=scholarship_id))
                dialog.destroy()
                self.refresh_scholarships()

            except ValueError:
                messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.invalid_amount_entered"))
            except Exception as e:
                messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.failed_create_scholarship", error=str(e)))

        # Buttons
        button_frame = ttk.Frame(form_frame)
        button_frame.pack(pady=20)

        ttk.Button(button_frame, text=_("finance_gui.settings.create_scholarship_form_btn"), command=create_scholarship).pack(side='left', padx=10)
        ttk.Button(button_frame, text=_("finance_gui.settings.btn_cancel"), command=dialog.destroy).pack(side='left', padx=10)
    

    def gui_award_scholarship_to_student(self):
        """GUI wrapper for awarding scholarship to student"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.settings.award_scholarship_title"))
        dialog.geometry("600x500")
        dialog.transient(self.root)
        dialog.grab_set()

        # Student and scholarship selection
        selection_frame = ttk.LabelFrame(dialog, text=_("finance_gui.settings.award_details_frame"), padding=20)
        selection_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # Student ID
        ttk.Label(selection_frame, text=_("finance_gui.settings.student_id_award_label"), font=('Arial', 12)).pack(anchor='w', pady=5)
        student_id_var = tk.StringVar()
        ttk.Entry(selection_frame, textvariable=student_id_var, font=('Arial', 12), width=20).pack(anchor='w', pady=5)

        # Scholarship selection
        ttk.Label(selection_frame, text=_("finance_gui.settings.available_scholarships_combo_label"), font=('Arial', 12)).pack(anchor='w', pady=(15, 5))
        
        # Load available scholarships
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
            SELECT scholarship_id, scholarship_name, amount, academic_year
            FROM scholarships 
            WHERE is_active = 1 AND deadline >= date('now')
            ORDER BY scholarship_name
            ''')
            scholarships = cursor.fetchall()
            conn.close()
        except Exception:
            scholarships = []
        
        scholarship_var = tk.StringVar()
        scholarship_combo = ttk.Combobox(selection_frame, textvariable=scholarship_var, 
                                       state='readonly', width=60, font=('Arial', 12))
        
        scholarship_values = []
        self.scholarship_data = {}
        
        for scholarship in scholarships:
            scholarship_id, name, amount, year = scholarship
            display_text = f"{name} - £{amount:.2f} ({year})"
            scholarship_values.append(display_text)
            self.scholarship_data[display_text] = scholarship
        
        scholarship_combo['values'] = scholarship_values
        scholarship_combo.pack(anchor='w', pady=5)
        
        def award_scholarship():
            try:
                student_id = student_id_var.get().strip()
                selected_scholarship = scholarship_var.get()

                if not student_id or not selected_scholarship:
                    messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.student_id_and_scholarship_required"))
                    return

                if selected_scholarship not in self.scholarship_data:
                    messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.invalid_scholarship_selection"))
                    return

                scholarship_info = self.scholarship_data[selected_scholarship]
                scholarship_id, name, amount, year = scholarship_info

                # Check if student exists
                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('SELECT COUNT(*) FROM students WHERE student_id = ?', (student_id,))
                if cursor.fetchone()[0] == 0:
                    messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.student_not_found", student_id=student_id))
                    conn.close()
                    return

                # Check if already awarded
                cursor.execute('''
                SELECT COUNT(*) FROM student_scholarships
                WHERE student_id = ? AND scholarship_id = ?
                ''', (student_id, scholarship_id))

                if cursor.fetchone()[0] > 0:
                    messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.student_already_awarded"))
                    conn.close()
                    return
                
                # Award the scholarship
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                award_date = datetime.now().strftime('%Y-%m-%d')
                
                cursor.execute('''
                INSERT INTO student_scholarships 
                (student_id, scholarship_id, award_date, amount_awarded, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'awarded', ?, ?)
                ''', (student_id, scholarship_id, award_date, amount, now, now))
                
                conn.commit()
                conn.close()

                messagebox.showinfo(_("finance_gui.settings.success_title"),
                                   _("finance_gui.settings.scholarship_awarded_msg", student_id=student_id, name=name, amount=f"£{amount:.2f}"))

                dialog.destroy()
                self.update_status(_("finance_gui.settings.scholarship_awarded_status", student_id=student_id))

            except Exception as e:
                messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.failed_award_scholarship", error=str(e)))

        ttk.Button(selection_frame, text=_("finance_gui.settings.award_scholarship_form_btn"), command=award_scholarship).pack(pady=20)
        ttk.Button(selection_frame, text=_("finance_gui.settings.btn_cancel"), command=dialog.destroy).pack(pady=5)
    

    def gui_scholarship_reports(self):
        """GUI wrapper for scholarship reports"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.settings.scholarship_reports_title"))
        dialog.geometry("800x600")
        dialog.transient(self.root)
        dialog.grab_set()

        # Report selection
        selection_frame = ttk.LabelFrame(dialog, text=_("finance_gui.settings.report_options_frame"), padding=15)
        selection_frame.pack(fill='x', padx=20, pady=10)

        report_type_var = tk.StringVar(value="distribution")

        ttk.Radiobutton(selection_frame, text=_("finance_gui.settings.distribution_summary_radio"),
                       variable=report_type_var, value="distribution").pack(anchor='w', pady=2)
        ttk.Radiobutton(selection_frame, text=_("finance_gui.settings.student_scholarship_report_radio"),
                       variable=report_type_var, value="student").pack(anchor='w', pady=2)
        ttk.Radiobutton(selection_frame, text=_("finance_gui.settings.utilization_analysis_radio"),
                       variable=report_type_var, value="utilization").pack(anchor='w', pady=2)

        # Report output
        output_frame = ttk.LabelFrame(dialog, text=_("finance_gui.settings.report_output_frame"), padding=15)
        output_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        report_output = ScrolledText(output_frame, height=20, width=80, font=('Courier', 10))
        report_output.pack(fill='both', expand=True)
        
        def generate_scholarship_report():
            try:
                report_type = report_type_var.get()
                
                old_stdout = sys.stdout
                sys.stdout = mystdout = io.StringIO()
                
                if report_type == "distribution":
                    scholarship_distribution_summary()
                elif report_type == "student":
                    student_scholarship_report()
                elif report_type == "utilization":
                    scholarship_utilization_analysis()
                
                output = mystdout.getvalue()
                sys.stdout = old_stdout
                
                report_output.delete('1.0', tk.END)
                report_output.insert('1.0', output)

            except Exception as e:
                messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.failed_generate_report", error=str(e)))

        ttk.Button(selection_frame, text=_("finance_gui.settings.generate_report_btn"), command=generate_scholarship_report).pack(pady=10)
    

    def gui_manage_scholarships(self):
        """Switch to scholarships tab"""
        self.show_tab('scholarships')
    

    def gui_view_available_scholarships(self):
        """View available scholarships"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.settings.available_scholarships_title"))
        dialog.geometry("800x600")
        dialog.transient(self.root)
        dialog.grab_set()

        # Scholarships display
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        # Filter frame
        filter_frame = ttk.LabelFrame(main_frame, text=_("finance_gui.settings.filter_options_frame"), padding=10)
        filter_frame.pack(fill='x', pady=(0, 10))

        ttk.Label(filter_frame, text=_("finance_gui.settings.filter_academic_year_label")).grid(row=0, column=0, padx=5, pady=5, sticky='e')
        year_var = tk.StringVar(value="2024-2025")
        ttk.Entry(filter_frame, textvariable=year_var, width=12).grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(filter_frame, text=_("finance_gui.settings.filter_status_label")).grid(row=0, column=2, padx=5, pady=5, sticky='e')
        status_var = tk.StringVar(value="active")
        status_combo = ttk.Combobox(filter_frame, textvariable=status_var,
                                   values=["active", "inactive", "all"], state='readonly', width=10)
        status_combo.grid(row=0, column=3, padx=5, pady=5)
    
        def load_scholarships():
            try:
                conn = get_connection()
                cursor = conn.cursor()
                
                query = '''
                SELECT scholarship_id, scholarship_name, description, amount, 
                       academic_year, criteria, deadline,
                       CASE WHEN is_active = 1 THEN 'Active' ELSE 'Inactive' END as status
                FROM scholarships
                WHERE 1=1
                '''
                params = []
                
                if year_var.get():
                    query += ' AND academic_year = ?'
                    params.append(year_var.get())
                
                if status_var.get() != 'all':
                    query += ' AND is_active = ?'
                    params.append(1 if status_var.get() == 'active' else 0)
                
                query += ' ORDER BY scholarship_name'
                
                cursor.execute(query, params)
                scholarships = cursor.fetchall()
                
                # Clear existing items
                for item in scholarship_tree.get_children():
                    scholarship_tree.delete(item)
                
                # Add scholarship data
                for scholarship in scholarships:
                    scholarship_id, name, desc, amount, year, criteria, deadline, status = scholarship
                    display_data = (
                        scholarship_id, name, f"£{amount:.2f}", year, 
                        criteria[:30] + "..." if len(criteria) > 30 else criteria,
                        deadline, status
                    )
                    scholarship_tree.insert('', 'end', values=display_data)
                
                conn.close()
                
            except Exception as e:
                messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.failed_load_scholarships", error=str(e)))

        ttk.Button(filter_frame, text=_("finance_gui.settings.load_scholarships_btn"), command=load_scholarships).grid(row=0, column=4, padx=10, pady=5)
        
        # Scholarships table
        columns = ('ID', 'Name', 'Amount', 'Year', 'Criteria', 'Deadline', 'Status')
        scholarship_tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=15)
        
        for col in columns:
            scholarship_tree.heading(col, text=col)
            width = 200 if col in ['Name', 'Criteria'] else 100
            scholarship_tree.column(col, width=width, anchor='center')
        
        # Scrollbars
        v_scroll = ttk.Scrollbar(main_frame, orient='vertical', command=scholarship_tree.yview)
        h_scroll = ttk.Scrollbar(main_frame, orient='horizontal', command=scholarship_tree.xview)
        scholarship_tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)
        
        scholarship_tree.pack(side='left', fill='both', expand=True)
        v_scroll.pack(side='right', fill='y')
        h_scroll.pack(side='bottom', fill='x')
        
        # Load initial data
        load_scholarships()
    

    def create_admin_tab(self):
        """Create admin and system management tab"""
        tab = tk.Frame(self.gui.layout.content_frame, bg='white')
        self.gui.layout.tab_frames['admin'] = tab
        
        main_frame = ttk.Frame(tab, padding=20)
        main_frame.pack(fill='both', expand=True)
        
        # System controls
        system_frame = ttk.LabelFrame(main_frame, text=_("finance_gui.settings.system_management_frame"), padding=15)
        system_frame.pack(fill='x', pady=(0, 20))

        # Add this button in the admin_buttons list in create_admin_tab method
        admin_buttons = [
            (_("finance_gui.settings.initialize_system_btn"), self.gui_initialize_system),
            (_("finance_gui.settings.create_sample_data_btn"), self.gui_create_sample_students),
            (_("finance_gui.settings.setup_notifications_btn"), self.gui_setup_automated_notifications),
            (_("finance_gui.settings.send_notifications_btn"), self.gui_send_automated_notifications),
            (_("finance_gui.settings.view_audit_logs_btn"), self.gui_view_audit_logs),
            (_("finance_gui.settings.system_settings_btn"), self.gui_system_settings),
            (_("finance_gui.settings.advanced_reporting_btn"), self.launch_reporting_gui),
            (_("finance_gui.settings.database_verification_btn"), self.gui_verify_fix),
            (_("finance_gui.settings.check_packages_btn"), self.gui_check_required_packages),
            (_("finance_gui.settings.setup_workflows_btn"), self.gui_setup_collection_workflows),
            (_("finance_gui.settings.email_config_btn"), self.gui_setup_email_config),
            (_("finance_gui.settings.sms_config_btn"), self.gui_setup_sms_config),
            (_("finance_gui.settings.test_email_btn"), self.gui_test_email_service),
            (_("finance_gui.settings.test_sms_btn"), self.gui_test_sms_service),
            (_("finance_gui.settings.analyze_admin_menu_btn"), self.update_admin_menu_with_missing_functions),
            (_("finance_gui.settings.analyze_reports_menu_btn"), self.update_reports_menu_with_missing_functions),
        ]

        for i, (text, command) in enumerate(admin_buttons):
            ttk.Button(system_frame, text=text, command=command, width=25).grid(row=i//2, column=i%2, padx=10, pady=5)
        # System status
        status_frame = ttk.LabelFrame(main_frame, text=_("finance_gui.settings.system_status_frame"), padding=15)
        status_frame.pack(fill='both', expand=True)
        
        self.status_text = ScrolledText(status_frame, height=15, width=80, font=('Courier', 10))
        self.status_text.pack(fill='both', expand=True)
        
        # Update system status
        self.update_system_status()
    

    def gui_initialize_system(self):
        """GUI wrapper for system initialization"""
        if messagebox.askyesno(_("finance_gui.settings.confirm_title"), _("finance_gui.settings.confirm_init_system")):
            try:
                self.update_status(_("finance_gui.settings.initializing_system"))

                def initialize():
                    init_enhanced_finance_db()
                    messagebox.showinfo(_("finance_gui.settings.success_title"), _("finance_gui.settings.system_initialized"))
                    self.update_system_status()
                    self.update_status(_("finance_gui.settings.system_initialization_completed"))

                thread = threading.Thread(target=initialize)
                thread.daemon = True
                thread.start()

            except Exception as e:
                messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.system_initialization_failed", error=str(e)))
    

    def gui_create_sample_students(self):
        """GUI wrapper for creating sample students"""
        if messagebox.askyesno(_("finance_gui.settings.confirm_title"), _("finance_gui.settings.confirm_create_sample_data")):
            try:
                create_sample_students()
                messagebox.showinfo(_("finance_gui.settings.success_title"), _("finance_gui.settings.sample_students_created"))
                self.update_status(_("finance_gui.settings.sample_students_created_status"))
            except Exception as e:
                messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.failed_create_sample_students", error=str(e)))
    

    def update_admin_menu_with_missing_functions(self):
        """Update admin menu to include missing GUI functions"""
        try:
            # Define admin functions that should be available
            expected_functions = {
                'System Management': [
                    ('gui_initialize_system', 'Initialize System'),
                    ('gui_create_sample_students', 'Create Sample Data'),
                    ('gui_setup_automated_notifications', 'Setup Notifications'),
                    ('gui_send_automated_notifications', 'Send Notifications'),
                    ('gui_view_audit_logs', 'View Audit Logs'),
                    ('gui_system_settings', 'System Settings'),
                    ('launch_reporting_gui', 'Advanced Reporting GUI'),
                    ('gui_verify_fix', 'Database Verification'),
                    ('gui_check_required_packages', 'Check Packages'),
                    ('gui_setup_collection_workflows', 'Setup Workflows'),
                    ('gui_setup_email_config', 'Email Config'),
                    ('gui_setup_sms_config', 'SMS Config'),
                    ('gui_test_email_service', 'Test Email'),
                    ('gui_test_sms_service', 'Test SMS'),
                ],
                'Database Operations': [
                    ('initialize_database', 'Initialize Database'),
                    ('clean_database', 'Clean Database'),
                    ('backup_database', 'Backup Database'),
                    ('show_database_stats', 'Database Statistics'),
                ]
            }

            # Check which functions exist
            missing_functions = []
            available_functions = []

            for category, functions in expected_functions.items():
                for func_name, display_name in functions:
                    # Check if function exists in this class or gui object
                    if hasattr(self, func_name):
                        available_functions.append((category, func_name, display_name))
                    elif hasattr(self.gui, func_name):
                        available_functions.append((category, func_name, display_name))
                    elif hasattr(self.gui, 'compliance') and hasattr(self.gui.compliance, func_name):
                        available_functions.append((category, func_name, display_name))
                    elif hasattr(self.gui, 'db_manager') and hasattr(self.gui.db_manager, func_name):
                        available_functions.append((category, func_name, display_name))
                    elif hasattr(self.gui, 'report_manager') and hasattr(self.gui.report_manager, func_name):
                        available_functions.append((category, func_name, display_name))
                    else:
                        missing_functions.append((category, func_name, display_name))

            # Display report
            report = _("finance_gui.settings.admin_menu_analysis_report_title") + "\n"
            report += "=" * 60 + "\n\n"
            report += _("finance_gui.settings.available_functions_label", count=len(available_functions)) + "\n"
            report += _("finance_gui.settings.missing_functions_label", count=len(missing_functions)) + "\n\n"

            if missing_functions:
                report += _("finance_gui.settings.missing_functions_section") + "\n"
                report += "-" * 60 + "\n"
                for category, func_name, display_name in missing_functions:
                    report += f"  [{category}] {func_name} - {display_name}\n"
                report += "\n"

            report += _("finance_gui.settings.available_functions_section") + "\n"
            report += "-" * 60 + "\n"
            current_category = None
            for category, func_name, display_name in sorted(available_functions):
                if category != current_category:
                    report += f"\n{category}:\n"
                    current_category = category
                report += f"  ✓ {display_name}\n"

            # Show report
            result_window = tk.Toplevel(self.gui.root)
            result_window.title(_("finance_gui.settings.admin_menu_analysis_title"))
            result_window.geometry("700x500")

            text_widget = ScrolledText(result_window, font=('Courier', 10), wrap='word')
            text_widget.pack(fill='both', expand=True, padx=10, pady=10)
            text_widget.insert('1.0', report)
            text_widget.config(state='disabled')

            close_btn = ttk.Button(result_window, text=_("finance_gui.settings.btn_close"), command=result_window.destroy)
            close_btn.pack(pady=5)

            self.update_status(_("finance_gui.settings.admin_menu_analysis_completed"))

        except Exception as e:
            messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.failed_analyze_admin_menu", error=str(e)))
            print(f"Admin menu analysis error: {e}")
    

    def update_reports_menu_with_missing_functions(self):
        """Update reports menu to include missing GUI functions"""
        try:
            # Define report functions that should be available
            expected_functions = {
                'Financial Reports': [
                    ('gui_revenue_summary_report', 'Revenue Summary'),
                    ('gui_outstanding_fees_report', 'Outstanding Fees'),
                    ('gui_payment_collection_report', 'Payment Collection'),
                    ('gui_student_account_summary', 'Student Accounts'),
                    ('gui_fee_type_analysis', 'Fee Type Analysis'),
                    ('gui_monthly_revenue_trend_report', 'Monthly Revenue Trend'),
                    ('gui_payment_method_analysis', 'Payment Methods'),
                ],
                'Collection Reports': [
                    ('gui_aging_analysis_report', 'Aging Analysis'),
                    ('gui_collection_case_status_report', 'Collection Cases'),
                    ('gui_recovery_rate_analysis', 'Recovery Rate'),
                    ('gui_agency_performance_report', 'Agency Performance'),
                ],
                'Budget & Performance': [
                    ('gui_variance_analysis_report', 'Variance Analysis'),
                    ('gui_budget_performance_trends', 'Budget Performance'),
                    ('gui_category_performance_report', 'Category Performance'),
                    ('gui_budget_vs_actual_analysis', 'Budget vs Actual'),
                ],
                'Forecasting & Analytics': [
                    ('gui_generate_revenue_forecast', 'Revenue Forecast'),
                    ('gui_generate_predictive_analytics', 'Predictive Analytics'),
                    ('gui_generate_cash_flow_analysis', 'Cash Flow Analysis'),
                    ('gui_generate_enrollment_projections', 'Enrollment Projections'),
                    ('gui_generate_risk_analysis', 'Risk Analysis'),
                    ('gui_detect_payment_fraud', 'Payment Fraud Detection'),
                ],
                'Financial Aid Reports': [
                    ('gui_generate_aid_reports', 'Aid Reports'),
                    ('gui_scholarship_reports', 'Scholarship Reports'),
                ],
                'Audit & Compliance': [
                    ('gui_generate_audit_report', 'Audit Report'),
                    ('gui_view_audit_logs', 'Audit Logs'),
                ]
            }

            # Check which functions exist
            missing_functions = []
            available_functions = []

            for category, functions in expected_functions.items():
                for func_name, display_name in functions:
                    # Check if function exists in various managers
                    found = False
                    if hasattr(self, func_name):
                        found = True
                    elif hasattr(self.gui, func_name):
                        found = True
                    elif hasattr(self.gui, 'report_manager') and hasattr(self.gui.report_manager, func_name):
                        found = True
                    elif hasattr(self.gui, 'budget_manager') and hasattr(self.gui.budget_manager, func_name):
                        found = True
                    elif hasattr(self.gui, 'analytics') and hasattr(self.gui.analytics, func_name):
                        found = True
                    elif hasattr(self.gui, 'compliance') and hasattr(self.gui.compliance, func_name):
                        found = True

                    if found:
                        available_functions.append((category, func_name, display_name))
                    else:
                        missing_functions.append((category, func_name, display_name))

            # Display report
            report = _("finance_gui.settings.reports_menu_analysis_report_title") + "\n"
            report += "=" * 60 + "\n\n"
            report += _("finance_gui.settings.available_functions_label", count=len(available_functions)) + "\n"
            report += _("finance_gui.settings.missing_functions_label", count=len(missing_functions)) + "\n\n"

            if missing_functions:
                report += _("finance_gui.settings.missing_functions_section") + "\n"
                report += "-" * 60 + "\n"
                for category, func_name, display_name in missing_functions:
                    report += f"  [{category}] {func_name} - {display_name}\n"
                report += "\n"

            report += _("finance_gui.settings.available_functions_by_category") + "\n"
            report += "-" * 60 + "\n"
            current_category = None
            for category, func_name, display_name in sorted(available_functions):
                if category != current_category:
                    report += f"\n{category}:\n"
                    current_category = category
                report += f"  ✓ {display_name}\n"

            # Show report
            result_window = tk.Toplevel(self.gui.root)
            result_window.title(_("finance_gui.settings.reports_menu_analysis_title"))
            result_window.geometry("700x600")

            text_widget = ScrolledText(result_window, font=('Courier', 10), wrap='word')
            text_widget.pack(fill='both', expand=True, padx=10, pady=10)
            text_widget.insert('1.0', report)
            text_widget.config(state='disabled')

            # Add buttons frame
            btn_frame = ttk.Frame(result_window)
            btn_frame.pack(fill='x', padx=10, pady=5)

            ttk.Button(btn_frame, text=_("finance_gui.settings.btn_close"), command=result_window.destroy).pack(side='left', padx=5)

            if missing_functions:
                def export_missing():
                    """Export missing functions list"""
                    try:
                        filename = filedialog.asksaveasfilename(
                            defaultextension=".txt",
                            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
                        )
                        if filename:
                            with open(filename, 'w') as f:
                                f.write(_("finance_gui.settings.missing_report_functions_title") + "\n")
                                f.write("=" * 60 + "\n\n")
                                for category, func_name, display_name in missing_functions:
                                    f.write(f"{category}: {func_name} - {display_name}\n")
                            messagebox.showinfo(_("finance_gui.settings.success_title"), _("finance_gui.settings.export_success_msg", filename=filename))
                    except Exception as e:
                        messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.export_failed", error=str(e)))

                ttk.Button(btn_frame, text=_("finance_gui.settings.export_missing_btn"), command=export_missing).pack(side='left', padx=5)

            self.update_status(_("finance_gui.settings.reports_menu_analysis_completed"))

        except Exception as e:
            messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.failed_analyze_reports_menu", error=str(e)))
            print(f"Reports menu analysis error: {e}")
    
    # Additional missing GUI functions from the original finance.py
    

    def gui_monthly_revenue_trend_report(self):
        """GUI wrapper for monthly_revenue_trend_report"""
        try:
            old_stdout = sys.stdout
            sys.stdout = mystdout = io.StringIO()
            
            monthly_revenue_trend_report()
            
            output = mystdout.getvalue()
            sys.stdout = old_stdout
            
            self.show_tab('reports')  # Reports tab
            self.report_text.delete('1.0', tk.END)
            self.report_text.insert('1.0', output)
            self.update_status(_("finance_gui.settings.monthly_revenue_trend_generated"))

        except Exception as e:
            messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.failed_generate_monthly_revenue", error=str(e)))

    def initialize_database(self):
        """Wrapper to call database manager's initialize function"""
        if hasattr(self.gui, 'db'):
            self.gui.db.initialize_database()
        else:
            messagebox.showwarning(_("finance_gui.settings.not_available_title"), _("finance_gui.settings.db_manager_not_initialized"))

    def clean_database(self):
        """Wrapper to call database manager's clean function"""
        if hasattr(self.gui, 'db'):
            self.gui.db.clean_database()
        else:
            messagebox.showwarning(_("finance_gui.settings.not_available_title"), _("finance_gui.settings.db_manager_not_initialized"))

    def backup_database(self):
        """Wrapper to call database manager's backup function"""
        if hasattr(self.gui, 'db'):
            self.gui.db.backup_database()
        else:
            messagebox.showwarning(_("finance_gui.settings.not_available_title"), _("finance_gui.settings.db_manager_not_initialized"))

    def show_database_stats(self):
        """Wrapper to call database manager's stats function"""
        if hasattr(self.gui, 'db'):
            self.gui.db.show_database_stats()
        else:
            messagebox.showwarning(_("finance_gui.settings.not_available_title"), _("finance_gui.settings.db_manager_not_initialized"))

    def update_system_status(self):
        """Update system status display"""
        if hasattr(self, 'status_text'):
            try:
                status = _("finance_gui.settings.system_status_title") + "\n"
                status += "=" * 50 + "\n"
                status += _("finance_gui.settings.database_connected") + "\n"
                status += _("finance_gui.settings.last_updated", timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')) + "\n"

                # Add more status info as needed
                self.status_text.delete('1.0', tk.END)
                self.status_text.insert('1.0', status)
            except Exception as e:
                print(_("finance_gui.settings.failed_update_system_status", error=str(e)))

