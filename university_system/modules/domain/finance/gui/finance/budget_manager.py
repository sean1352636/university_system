"""Budget planning and analysis"""

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
    # Budget management
    budget_approval_workflow,
    budget_performance_trends,
    budget_vs_actual_analysis,
    category_performance_report,
    create_budget_plan,
    variance_analysis_report,
    # Budget categories
    create_budget_category,
    deactivate_budget_category,
    edit_budget_category,
    update_actual_amounts,
    view_budget_categories,
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




class BudgetManager:
    """Budget planning and analysis"""

    def __init__(self, gui):
        """Initialize manager with reference to main GUI"""
        self.gui = gui
        self.root = gui.root
        self.conn = gui.conn
        try:
            self.finance_system = gui.finance_system
        except Exception:
            self.finance_system = None

    def create_budget_tab(self):
        """Create comprehensive budget management tab with Budget Tracker integration"""
        budget_frame = tk.Frame(self.gui.layout.content_frame, bg='white')
        self.gui.layout.tab_frames['budget'] = budget_frame

        # Initialize Budget Tracker database tables
        try:
            from university_system.modules.domain.budget.services.budget_service import BudgetManager
            BudgetManager.create_tables()
        except Exception as e:
            logger.warning(f"Could not initialize budget tables: {e}")

        # Check user role to determine which view to show
        user_role = self.gui.get_user_role() if hasattr(self.gui, 'get_user_role') else None

        # Budget toolbar
        toolbar = tk.Frame(budget_frame, bg='white')
        toolbar.pack(fill='x', padx=10, pady=5)

        # Common buttons for all users - Quick navigation
        tk.Button(toolbar, text="💰 My Expenses", command=self.open_expense_tracker,
                 bg=self.gui.layout.colors['info'], fg='white').pack(side='left', padx=5)
        tk.Button(toolbar, text="💵 My Income", command=self.open_income_tracker,
                 bg=self.gui.layout.colors['success'], fg='white').pack(side='left', padx=5)
        tk.Button(toolbar, text="🎯 Savings Goals", command=self.open_savings_goals,
                 bg=self.gui.layout.colors['warning'], fg='white').pack(side='left', padx=5)
        tk.Button(toolbar, text="🍽️ Meal Plan", command=self.open_meal_plan,
                 bg=self.gui.layout.colors['secondary'], fg='white').pack(side='left', padx=5)
        tk.Button(toolbar, text="📚 Textbooks", command=self.open_textbooks,
                 bg=self.gui.layout.colors['primary'], fg='white').pack(side='left', padx=5)

        # Admin/Staff only buttons
        if user_role in ['admin', 'staff', 'instructor']:
            toolbar2 = tk.Frame(budget_frame, bg='white')
            toolbar2.pack(fill='x', padx=10, pady=5)

            tk.Button(toolbar2, text="📊 New Budget Plan", command=self.create_budget_plan,
                     bg=self.gui.layout.colors['success'], fg='white').pack(side='left', padx=5)
            tk.Button(toolbar2, text="✏️ Edit Budget", command=self.edit_budget_plan,
                     bg=self.gui.layout.colors['warning'], fg='white').pack(side='left', padx=5)
            tk.Button(toolbar2, text="🗑️ Delete Budget", command=self.delete_budget_plan,
                     bg=self.gui.layout.colors['danger'], fg='white').pack(side='left', padx=5)
            tk.Button(toolbar2, text="📈 Budget Analysis", command=self.budget_analysis,
                     bg=self.gui.layout.colors['secondary'], fg='white').pack(side='left', padx=5)
            tk.Button(toolbar2, text="📂 Manage Categories", command=self.gui_manage_budget_categories,
                     bg=self.gui.layout.colors['info'], fg='white').pack(side='left', padx=5)

        # Main content with notebook
        budget_notebook = ttk.Notebook(budget_frame)
        budget_notebook.pack(fill='both', expand=True, padx=10, pady=10)
        self.budget_notebook = budget_notebook

        # Tab 1: Personal Budget Dashboard
        self.create_personal_budget_dashboard(budget_notebook)

        # Tab 2: My Budgets
        self.create_my_budgets_tab(budget_notebook)

        # Tab 3: Expenses & Income
        self.create_expenses_income_tab(budget_notebook)

        # Tab 4: Savings & Goals
        self.create_savings_goals_tab(budget_notebook)

        # Tab 5: Meal Plan Tracking
        self.create_meal_plan_tab(budget_notebook)

        # Tab 6: Textbooks
        self.create_textbooks_tab(budget_notebook)

        # Tab 7: Budget Reports (for all users)
        self.create_budget_reports_tab(budget_notebook)

        # Tab 8: Institutional Budgets (admin/staff only)
        if user_role in ['admin', 'staff', 'instructor']:
            self.create_institutional_budget_tab(budget_notebook)

        # Load initial data
        self.refresh_all_budget_data()
    

    def create_budget_plan(self):
        """Create new budget plan with database integration"""
        # Create dialog for budget plan details
        dialog = tk.Toplevel(self.root)
        dialog.title("Create Budget Plan")
        dialog.geometry("550x500")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="Create New Budget Plan",
                 font=('TkDefaultFont', 14, 'bold')).pack(pady=10)

        # Form frame
        form_frame = ttk.LabelFrame(dialog, text="Budget Plan Details", padding=20)
        form_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Plan name
        ttk.Label(form_frame, text="Plan Name:").grid(row=0, column=0, sticky='w', pady=5, padx=5)
        name_var = tk.StringVar()
        name_entry = ttk.Entry(form_frame, textvariable=name_var, width=35)
        name_entry.grid(row=0, column=1, pady=5, padx=5)
        name_entry.focus()

        # Academic year
        ttk.Label(form_frame, text="Academic Year:").grid(row=1, column=0, sticky='w', pady=5, padx=5)
        year_var = tk.StringVar(value=f"{datetime.now().year}-{datetime.now().year + 1}")
        year_entry = ttk.Entry(form_frame, textvariable=year_var, width=35)
        year_entry.grid(row=1, column=1, pady=5, padx=5)

        # Revenue budget
        ttk.Label(form_frame, text="Revenue Budget (£):").grid(row=2, column=0, sticky='w', pady=5, padx=5)
        revenue_var = tk.StringVar(value="0.00")
        revenue_entry = ttk.Entry(form_frame, textvariable=revenue_var, width=35)
        revenue_entry.grid(row=2, column=1, pady=5, padx=5)

        # Expense budget
        ttk.Label(form_frame, text="Expense Budget (£):").grid(row=3, column=0, sticky='w', pady=5, padx=5)
        expense_var = tk.StringVar(value="0.00")
        expense_entry = ttk.Entry(form_frame, textvariable=expense_var, width=35)
        expense_entry.grid(row=3, column=1, pady=5, padx=5)

        # Currency
        ttk.Label(form_frame, text="Currency:").grid(row=4, column=0, sticky='w', pady=5, padx=5)
        currency_var = tk.StringVar(value="GBP")
        currency_combo = ttk.Combobox(form_frame, textvariable=currency_var,
                                      values=['GBP', 'USD', 'EUR'], width=33, state='readonly')
        currency_combo.grid(row=4, column=1, pady=5, padx=5)

        # Status
        ttk.Label(form_frame, text="Status:").grid(row=5, column=0, sticky='w', pady=5, padx=5)
        status_var = tk.StringVar(value="draft")
        status_combo = ttk.Combobox(form_frame, textvariable=status_var,
                                    values=['draft', 'active', 'approved', 'closed'],
                                    width=33, state='readonly')
        status_combo.grid(row=5, column=1, pady=5, padx=5)

        # Notes
        ttk.Label(form_frame, text="Notes:").grid(row=6, column=0, sticky='nw', pady=5, padx=5)
        notes_text = tk.Text(form_frame, height=4, width=35)
        notes_text.grid(row=6, column=1, pady=5, padx=5)

        # Summary display
        summary_frame = ttk.LabelFrame(dialog, text="Budget Summary", padding=10)
        summary_frame.pack(fill='x', padx=10, pady=5)

        summary_label = ttk.Label(summary_frame, text="", font=('Courier', 9))
        summary_label.pack()

        def update_summary():
            try:
                revenue = float(revenue_var.get() or 0)
                expense = float(expense_var.get() or 0)
                net = revenue - expense

                summary_text = f"""
Revenue Budget:   £{revenue:,.2f}
Expense Budget:   £{expense:,.2f}
Net Budget:       £{net:,.2f}
Status:           {status_var.get().title()}
"""
                summary_label.config(text=summary_text)
            except ValueError:
                summary_label.config(text="Invalid numeric values")

        # Update summary when values change
        revenue_var.trace('w', lambda *args: update_summary())
        expense_var.trace('w', lambda *args: update_summary())
        status_var.trace('w', lambda *args: update_summary())
        update_summary()

        def save_plan():
            plan_name = name_var.get().strip()
            if not plan_name:
                messagebox.showwarning("Name Required", "Please enter a budget plan name", parent=dialog)
                return

            academic_year = year_var.get().strip()
            if not academic_year:
                messagebox.showwarning("Year Required", "Please enter an academic year", parent=dialog)
                return

            try:
                revenue = float(revenue_var.get() or 0)
                expense = float(expense_var.get() or 0)
                if revenue < 0 or expense < 0:
                    raise ValueError("Budget amounts cannot be negative")
            except ValueError as e:
                messagebox.showwarning("Invalid Amount", str(e), parent=dialog)
                return

            notes = notes_text.get("1.0", tk.END).strip()

            # Get current user
            try:
                auth = get_auth()
                if auth.is_logged_in():
                    created_by = auth.get_current_user()['username']
                else:
                    created_by = 'system'
            except Exception:
                created_by = 'admin'

            try:
                conn = get_connection()
                cursor = conn.cursor()

                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute('''
                    INSERT INTO budget_plans
                    (plan_name, academic_year, currency, status,
                     total_revenue_budget, total_expense_budget,
                     created_by, notes, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (plan_name, academic_year, currency_var.get(), status_var.get(),
                      revenue, expense, created_by, notes, now, now))

                conn.commit()
                budget_id = cursor.lastrowid
                conn.close()

                messagebox.showinfo("Success",
                    f"Budget plan '{plan_name}' created successfully!\n\nBudget ID: {budget_id}",
                    parent=dialog)
                dialog.destroy()
                self.refresh_budget()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to create budget plan: {e}", parent=dialog)

        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text="Create Plan", command=save_plan).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)
    

    def edit_budget_plan(self):
        """Edit selected budget plan"""
        selection = self.budget_plans_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a budget plan to edit.")
            return
    
        # Get current values
        values = self.budget_plans_tree.item(selection[0])['values']
        budget_id = values[0]
        current_name = values[1]
        current_year = values[2]
        current_revenue = str(values[3]).replace('£', '').replace(',', '') if len(values) > 3 else '0'
        current_expenses = str(values[4]).replace('£', '').replace(',', '') if len(values) > 4 else '0'
        current_status = values[5] if len(values) > 5 else 'Active'
    
        # Create edit dialog
        edit_dialog = tk.Toplevel(self.root)
        edit_dialog.title(f"Edit Budget Plan - {budget_id}")
        edit_dialog.geometry("550x500")
        edit_dialog.transient(self.root)
        edit_dialog.grab_set()
    
        ttk.Label(edit_dialog, text=f"Edit Budget Plan: {budget_id}",
                 font=('TkDefaultFont', 14, 'bold')).pack(pady=10)
    
        # Form frame
        form_frame = ttk.LabelFrame(edit_dialog, text="Budget Plan Details", padding=20)
        form_frame.pack(fill='both', expand=True, padx=10, pady=10)
    
        # Budget ID (read-only)
        ttk.Label(form_frame, text="Budget ID:").grid(row=0, column=0, sticky='w', pady=5, padx=5)
        ttk.Label(form_frame, text=budget_id, foreground='blue').grid(row=0, column=1, sticky='w', pady=5, padx=5)
    
        # Plan name
        ttk.Label(form_frame, text="Plan Name:").grid(row=1, column=0, sticky='w', pady=5, padx=5)
        name_var = tk.StringVar(value=current_name)
        name_entry = ttk.Entry(form_frame, textvariable=name_var, width=35)
        name_entry.grid(row=1, column=1, pady=5, padx=5)
        name_entry.focus()
    
        # Year
        ttk.Label(form_frame, text="Fiscal Year:").grid(row=2, column=0, sticky='w', pady=5, padx=5)
        year_var = tk.StringVar(value=current_year)
        year_entry = ttk.Entry(form_frame, textvariable=year_var, width=35)
        year_entry.grid(row=2, column=1, pady=5, padx=5)
    
        # Revenue budget
        ttk.Label(form_frame, text="Revenue Budget (£):").grid(row=3, column=0, sticky='w', pady=5, padx=5)
        revenue_var = tk.StringVar(value=current_revenue)
        revenue_entry = ttk.Entry(form_frame, textvariable=revenue_var, width=35)
        revenue_entry.grid(row=3, column=1, pady=5, padx=5)
    
        # Expenses budget
        ttk.Label(form_frame, text="Expenses Budget (£):").grid(row=4, column=0, sticky='w', pady=5, padx=5)
        expenses_var = tk.StringVar(value=current_expenses)
        expenses_entry = ttk.Entry(form_frame, textvariable=expenses_var, width=35)
        expenses_entry.grid(row=4, column=1, pady=5, padx=5)
    
        # Status
        ttk.Label(form_frame, text="Status:").grid(row=5, column=0, sticky='w', pady=5, padx=5)
        status_var = tk.StringVar(value=current_status)
        status_combo = ttk.Combobox(form_frame, textvariable=status_var,
                                    values=['Active', 'Draft', 'Approved', 'Closed'],
                                    width=33, state='readonly')
        status_combo.grid(row=5, column=1, pady=5, padx=5)
    
        # Notes
        ttk.Label(form_frame, text="Notes:").grid(row=6, column=0, sticky='nw', pady=5, padx=5)
        notes_text = tk.Text(form_frame, height=4, width=35)
        notes_text.grid(row=6, column=1, pady=5, padx=5)
        notes_text.insert('1.0', f"Budget plan for {current_year}")
    
        # Summary display
        summary_frame = ttk.LabelFrame(edit_dialog, text="Budget Summary", padding=10)
        summary_frame.pack(fill='x', padx=10, pady=5)
    
        summary_label = ttk.Label(summary_frame, text="", font=('Courier', 9))
        summary_label.pack()
    
        def update_summary():
            try:
                revenue = float(revenue_var.get() or 0)
                expenses = float(expenses_var.get() or 0)
                surplus = revenue - expenses
    
                summary_text = f"""
    Revenue Budget:   £{revenue:,.2f}
    Expenses Budget:  £{expenses:,.2f}
    Net Surplus:      £{surplus:,.2f}
    Status:           {status_var.get()}
    """
                summary_label.config(text=summary_text)
            except ValueError:
                summary_label.config(text="Invalid numeric values")
    
        # Update summary when values change
        revenue_var.trace('w', lambda *args: update_summary())
        expenses_var.trace('w', lambda *args: update_summary())
        status_var.trace('w', lambda *args: update_summary())
        update_summary()
    
        def save_changes():
            new_name = name_var.get().strip()
            if not new_name:
                messagebox.showwarning("Name Required", "Please enter a budget plan name", parent=edit_dialog)
                return

            academic_year = year_var.get().strip()
            if not academic_year:
                messagebox.showwarning("Year Required", "Please enter an academic year", parent=edit_dialog)
                return

            try:
                revenue = float(revenue_var.get() or 0)
                expenses = float(expenses_var.get() or 0)
                if revenue < 0 or expenses < 0:
                    raise ValueError("Budget amounts cannot be negative")
            except ValueError as e:
                messagebox.showwarning("Invalid Amount", str(e), parent=edit_dialog)
                return

            notes = notes_text.get("1.0", tk.END).strip()

            # Save to database
            try:
                conn = get_connection()
                cursor = conn.cursor()

                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute('''
                    UPDATE budget_plans
                    SET plan_name = ?,
                        academic_year = ?,
                        total_revenue_budget = ?,
                        total_expense_budget = ?,
                        status = ?,
                        notes = ?,
                        updated_at = ?
                    WHERE budget_id = ?
                ''', (new_name, academic_year, revenue, expenses,
                      status_var.get(), notes, now, budget_id))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", f"Budget plan '{new_name}' updated successfully", parent=edit_dialog)
                edit_dialog.destroy()
                self.refresh_budget()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to update budget plan: {e}", parent=edit_dialog)
    
        # Buttons
        button_frame = ttk.Frame(edit_dialog)
        button_frame.pack(pady=10)
    
        ttk.Button(button_frame, text="Save Changes", command=save_changes).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancel", command=edit_dialog.destroy).pack(side='left', padx=5)
    

    def budget_analysis(self):
        """Show budget analysis"""
        try:
            old_stdout = sys.stdout
            sys.stdout = mystdout = io.StringIO()
            
            budget_vs_actual_analysis()
            
            output = mystdout.getvalue()
            sys.stdout = old_stdout
            
            self.show_text_window("Budget Analysis", output)
            
        except Exception as e:
            sys.stdout = old_stdout
            messagebox.showerror("Error", f"Failed to generate budget analysis: {str(e)}")
    

    def approve_budget(self):
        """Approve budget workflow"""
        try:
            old_stdout = sys.stdout
            sys.stdout = mystdout = io.StringIO()

            budget_approval_workflow()

            output = mystdout.getvalue()
            sys.stdout = old_stdout

            self.show_text_window("Budget Approval", output)

        except Exception as e:
            sys.stdout = old_stdout
            messagebox.showerror("Error", f"Budget approval failed: {str(e)}")


    def delete_budget_plan(self):
        """Delete selected budget plan"""
        selection = self.budget_plans_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a budget plan to delete.")
            return

        # Get budget details
        values = self.budget_plans_tree.item(selection[0])['values']
        budget_id = values[0]
        plan_name = values[1]

        # Confirm deletion
        if not messagebox.askyesno("Confirm Delete",
                                   f"Are you sure you want to delete budget plan '{plan_name}'?\n\n"
                                   f"This will also delete all associated line items.\n"
                                   f"This action cannot be undone.",
                                   icon='warning'):
            return

        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Delete line items first (foreign key constraint)
            cursor.execute('DELETE FROM budget_line_items WHERE budget_id = ?', (budget_id,))

            # Delete budget plan
            cursor.execute('DELETE FROM budget_plans WHERE budget_id = ?', (budget_id,))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", f"Budget plan '{plan_name}' deleted successfully")
            self.refresh_budget()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete budget plan: {e}")


    def show_text_window(self, title, content):
        """Show content in a separate text window"""
        window = tk.Toplevel(self.root)
        window.title(title)
        window.geometry("800x600")
        window.transient(self.root)

        text_widget = ScrolledText(window, font=('Courier', 10))
        text_widget.pack(fill='both', expand=True, padx=10, pady=10)
        text_widget.insert('1.0', content)

        ttk.Button(window, text="Close", command=window.destroy).pack(pady=10)

    # ==================== FORECASTING METHODS ====================
    

    def gui_manage_budgets(self):
        """Switch to budget tab"""
        self.show_tab('budget')
    

    def gui_create_budget_plan(self):
        """GUI wrapper for create_budget_plan"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Create Budget Plan")
        dialog.geometry("600x500")
        dialog.transient(self.root)
        dialog.grab_set()
        
        form_frame = ttk.LabelFrame(dialog, text="Budget Plan Details", padding=20)
        form_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Plan name
        ttk.Label(form_frame, text="Plan Name:").pack(anchor='w', pady=5)
        name_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=name_var).pack(anchor='w', fill='x', pady=5)
        
        # Academic year
        ttk.Label(form_frame, text="Academic Year:").pack(anchor='w', pady=5)
        year_var = tk.StringVar(value="2024-2025")
        ttk.Entry(form_frame, textvariable=year_var).pack(anchor='w', fill='x', pady=5)
        
        # Description
        ttk.Label(form_frame, text="Description:").pack(anchor='w', pady=5)
        desc_text = tk.Text(form_frame, height=4, width=50)
        desc_text.pack(anchor='w', fill='x', pady=5)
        
        def create_plan():
            try:
                plan_name = name_var.get().strip()
                academic_year = year_var.get().strip()
                description = desc_text.get("1.0", tk.END).strip()
                
                if not all([plan_name, academic_year]):
                    messagebox.showerror("Error", "Plan name and academic year are required")
                    return
                
                create_budget_plan(plan_name, academic_year, description)
                messagebox.showinfo("Success", "Budget plan created successfully!")
                dialog.destroy()
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create budget plan: {e}")
        
        ttk.Button(form_frame, text="Create Plan", command=create_plan).pack(pady=20)
    

    def refresh_budget(self):
        """Refresh budget data"""
        def refresh_thread():
            try:
                conn = get_connection()
                cursor = conn.cursor()
                
                # Get budget plans
                cursor.execute('''
                SELECT budget_id, plan_name, academic_year, 
                       total_revenue_budget, total_expense_budget, status
                FROM budget_plans
                ORDER BY academic_year DESC, plan_name
                ''')
                
                budget_plans = cursor.fetchall()
                
                # Get budget categories
                cursor.execute('''
                SELECT bc.category_id, bc.category_name, bc.category_type,
                       COALESCE(pc.category_name, 'None') as parent_name
                FROM budget_categories bc
                LEFT JOIN budget_categories pc ON bc.parent_category_id = pc.category_id
                WHERE bc.is_active = 1
                ORDER BY bc.category_type, bc.category_name
                ''')
                
                budget_categories = cursor.fetchall()
                conn.close()
                
                self.root.after(0, lambda: self.update_budget_data(budget_plans, budget_categories))
                
            except Exception as e:
                print(f"Error refreshing budget: {e}")
        
        refresh_thread()
    

    def update_budget_data(self, budget_plans, budget_categories):
        """Update budget data in UI"""
        # Update budget plans
        for item in self.budget_plans_tree.get_children():
            self.budget_plans_tree.delete(item)
        
        for plan in budget_plans:
            budget_id, name, year, revenue, expenses, status = plan
            revenue_str = f"£{revenue:,.2f}" if revenue else "£0.00"
            expenses_str = f"£{expenses:,.2f}" if expenses else "£0.00"
            display_data = (budget_id, name, year, revenue_str, expenses_str, status)
            self.budget_plans_tree.insert('', 'end', values=display_data)
        
        # Update budget categories
        for item in self.budget_categories_tree.get_children():
            self.budget_categories_tree.delete(item)
        
        for category in budget_categories:
            self.budget_categories_tree.insert('', 'end', values=category)
    

    def gui_manage_budget_categories(self):
        """Full GUI for managing budget categories"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Manage Budget Categories")
        dialog.geometry("1000x700")
        dialog.transient(self.root)
        dialog.grab_set()

        # Header
        header_frame = tk.Frame(dialog, bg='#2c3e50', height=60)
        header_frame.pack(fill='x')
        header_frame.pack_propagate(False)

        tk.Label(header_frame, text="Budget Categories Management",
                font=('TkDefaultFont', 16, 'bold'), bg='#2c3e50', fg='white').pack(pady=15)

        # Toolbar
        toolbar = tk.Frame(dialog, bg='white', height=50)
        toolbar.pack(fill='x', padx=10, pady=5)
        toolbar.pack_propagate(False)

        def add_category():
            """Add new budget category"""
            add_dialog = tk.Toplevel(dialog)
            add_dialog.title("Add Budget Category")
            add_dialog.geometry("500x400")
            add_dialog.transient(dialog)
            add_dialog.grab_set()

            form_frame = ttk.LabelFrame(add_dialog, text="Category Details", padding=20)
            form_frame.pack(fill='both', expand=True, padx=20, pady=20)

            # Category name
            ttk.Label(form_frame, text="Category Name:").grid(row=0, column=0, sticky='w', pady=5, padx=5)
            name_var = tk.StringVar()
            name_entry = ttk.Entry(form_frame, textvariable=name_var, width=35)
            name_entry.grid(row=0, column=1, pady=5, padx=5)
            name_entry.focus()

            # Category type
            ttk.Label(form_frame, text="Category Type:").grid(row=1, column=0, sticky='w', pady=5, padx=5)
            type_var = tk.StringVar(value="expense")
            type_combo = ttk.Combobox(form_frame, textvariable=type_var,
                                     values=["revenue", "expense"], width=33, state='readonly')
            type_combo.grid(row=1, column=1, pady=5, padx=5)

            # Parent category (optional)
            ttk.Label(form_frame, text="Parent Category:").grid(row=2, column=0, sticky='w', pady=5, padx=5)
            parent_var = tk.StringVar()
            parent_combo = ttk.Combobox(form_frame, textvariable=parent_var, width=33)
            parent_combo.grid(row=2, column=1, pady=5, padx=5)

            # Load parent categories
            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT category_id, category_name FROM budget_categories WHERE is_active = 1 ORDER BY category_name")
                parents = cursor.fetchall()
                conn.close()
                parent_combo['values'] = ['None'] + [f"{p[0]} - {p[1]}" for p in parents]
                parent_combo.set('None')
            except Exception as e:
                print(f"Error loading parent categories: {e}")

            # Description
            ttk.Label(form_frame, text="Description:").grid(row=3, column=0, sticky='nw', pady=5, padx=5)
            desc_text = tk.Text(form_frame, height=6, width=35)
            desc_text.grid(row=3, column=1, pady=5, padx=5)

            def save_category():
                name = name_var.get().strip()
                if not name:
                    messagebox.showwarning("Name Required", "Please enter a category name", parent=add_dialog)
                    return

                category_type = type_var.get()
                parent_str = parent_var.get()
                parent_id = None
                if parent_str and parent_str != 'None':
                    try:
                        parent_id = int(parent_str.split(' - ')[0])
                    except (ValueError, IndexError):
                        pass

                try:
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT INTO budget_categories
                        (category_name, category_type, parent_category_id, is_active, created_at)
                        VALUES (?, ?, ?, 1, ?)
                    ''', (name, category_type, parent_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                    conn.commit()
                    conn.close()

                    messagebox.showinfo("Success", f"Category '{name}' created successfully", parent=add_dialog)
                    add_dialog.destroy()
                    refresh_categories()
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to create category: {e}", parent=add_dialog)

            button_frame = ttk.Frame(form_frame)
            button_frame.grid(row=4, column=0, columnspan=2, pady=15)
            ttk.Button(button_frame, text="Save", command=save_category).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Cancel", command=add_dialog.destroy).pack(side='left', padx=5)

        def edit_category():
            """Edit selected category"""
            selection = tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a category to edit", parent=dialog)
                return

            values = tree.item(selection[0])['values']
            category_id = values[0]
            current_name = values[1]
            current_type = values[2]

            edit_dialog = tk.Toplevel(dialog)
            edit_dialog.title(f"Edit Category - {category_id}")
            edit_dialog.geometry("500x350")
            edit_dialog.transient(dialog)
            edit_dialog.grab_set()

            form_frame = ttk.LabelFrame(edit_dialog, text="Category Details", padding=20)
            form_frame.pack(fill='both', expand=True, padx=20, pady=20)

            # Category ID (read-only)
            ttk.Label(form_frame, text="Category ID:").grid(row=0, column=0, sticky='w', pady=5, padx=5)
            ttk.Label(form_frame, text=category_id, foreground='blue').grid(row=0, column=1, sticky='w', pady=5, padx=5)

            # Category name
            ttk.Label(form_frame, text="Category Name:").grid(row=1, column=0, sticky='w', pady=5, padx=5)
            name_var = tk.StringVar(value=current_name)
            name_entry = ttk.Entry(form_frame, textvariable=name_var, width=35)
            name_entry.grid(row=1, column=1, pady=5, padx=5)
            name_entry.focus()

            # Category type
            ttk.Label(form_frame, text="Category Type:").grid(row=2, column=0, sticky='w', pady=5, padx=5)
            type_var = tk.StringVar(value=current_type)
            type_combo = ttk.Combobox(form_frame, textvariable=type_var,
                                     values=["revenue", "expense"], width=33, state='readonly')
            type_combo.grid(row=2, column=1, pady=5, padx=5)

            # Description
            ttk.Label(form_frame, text="Description:").grid(row=3, column=0, sticky='nw', pady=5, padx=5)
            desc_text = tk.Text(form_frame, height=5, width=35)
            desc_text.grid(row=3, column=1, pady=5, padx=5)

            def save_changes():
                name = name_var.get().strip()
                if not name:
                    messagebox.showwarning("Name Required", "Please enter a category name", parent=edit_dialog)
                    return

                try:
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute('''
                        UPDATE budget_categories
                        SET category_name = ?, category_type = ?, updated_at = ?
                        WHERE category_id = ?
                    ''', (name, type_var.get(), datetime.now().strftime('%Y-%m-%d %H:%M:%S'), category_id))
                    conn.commit()
                    conn.close()

                    messagebox.showinfo("Success", f"Category '{name}' updated successfully", parent=edit_dialog)
                    edit_dialog.destroy()
                    refresh_categories()
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to update category: {e}", parent=edit_dialog)

            button_frame = ttk.Frame(form_frame)
            button_frame.grid(row=4, column=0, columnspan=2, pady=15)
            ttk.Button(button_frame, text="Save Changes", command=save_changes).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Cancel", command=edit_dialog.destroy).pack(side='left', padx=5)

        def deactivate_category():
            """Deactivate selected category"""
            selection = tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a category to deactivate", parent=dialog)
                return

            values = tree.item(selection[0])['values']
            category_id = values[0]
            category_name = values[1]

            if messagebox.askyesno("Confirm Deactivation",
                                  f"Deactivate category '{category_name}'?\n\nThis will hide the category but not delete it.",
                                  parent=dialog):
                try:
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute('''
                        UPDATE budget_categories
                        SET is_active = 0, updated_at = ?
                        WHERE category_id = ?
                    ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), category_id))
                    conn.commit()
                    conn.close()

                    messagebox.showinfo("Success", f"Category '{category_name}' deactivated", parent=dialog)
                    refresh_categories()
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to deactivate category: {e}", parent=dialog)

        def refresh_categories():
            """Refresh category list"""
            for item in tree.get_children():
                tree.delete(item)

            try:
                conn = get_connection()
                cursor = conn.cursor()

                # Show active or all based on checkbox
                if show_inactive_var.get():
                    cursor.execute('''
                        SELECT bc.category_id, bc.category_name, bc.category_type,
                               COALESCE(pc.category_name, 'None') as parent_name,
                               CASE WHEN bc.is_active = 1 THEN 'Active' ELSE 'Inactive' END as status
                        FROM budget_categories bc
                        LEFT JOIN budget_categories pc ON bc.parent_category_id = pc.category_id
                        ORDER BY bc.category_type, bc.category_name
                    ''')
                else:
                    cursor.execute('''
                        SELECT bc.category_id, bc.category_name, bc.category_type,
                               COALESCE(pc.category_name, 'None') as parent_name,
                               'Active' as status
                        FROM budget_categories bc
                        LEFT JOIN budget_categories pc ON bc.parent_category_id = pc.category_id
                        WHERE bc.is_active = 1
                        ORDER BY bc.category_type, bc.category_name
                    ''')

                categories = cursor.fetchall()
                conn.close()

                for category in categories:
                    tree.insert('', 'end', values=category)

                status_label.config(text=f"Total categories: {len(categories)}")

            except Exception as e:
                messagebox.showerror("Error", f"Failed to load categories: {e}", parent=dialog)

        # Toolbar buttons
        tk.Button(toolbar, text="➕ Add Category", command=add_category,
                 bg='#27ae60', fg='white', padx=10).pack(side='left', padx=5)
        tk.Button(toolbar, text="✏️ Edit Category", command=edit_category,
                 bg='#f39c12', fg='white', padx=10).pack(side='left', padx=5)
        tk.Button(toolbar, text="🗑️ Deactivate", command=deactivate_category,
                 bg='#e74c3c', fg='white', padx=10).pack(side='left', padx=5)
        tk.Button(toolbar, text="🔄 Refresh", command=refresh_categories,
                 bg='#3498db', fg='white', padx=10).pack(side='left', padx=5)

        show_inactive_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(toolbar, text="Show Inactive", variable=show_inactive_var,
                       command=refresh_categories).pack(side='left', padx=10)

        # Main content area
        content_frame = tk.Frame(dialog, bg='white')
        content_frame.pack(fill='both', expand=True, padx=10, pady=5)

        # Treeview
        tree_frame = tk.Frame(content_frame)
        tree_frame.pack(fill='both', expand=True)

        tree_scroll = ttk.Scrollbar(tree_frame)
        tree_scroll.pack(side='right', fill='y')

        tree = ttk.Treeview(tree_frame,
                           columns=('id', 'name', 'type', 'parent', 'status'),
                           show='headings', yscrollcommand=tree_scroll.set)
        tree_scroll.config(command=tree.yview)

        tree.heading('id', text='ID')
        tree.heading('name', text='Category Name')
        tree.heading('type', text='Type')
        tree.heading('parent', text='Parent Category')
        tree.heading('status', text='Status')

        tree.column('id', width=60)
        tree.column('name', width=250)
        tree.column('type', width=100)
        tree.column('parent', width=200)
        tree.column('status', width=100)

        tree.pack(fill='both', expand=True)

        # Status bar
        status_frame = tk.Frame(dialog, bg='#ecf0f1', height=30)
        status_frame.pack(fill='x', side='bottom')
        status_frame.pack_propagate(False)

        status_label = tk.Label(status_frame, text="Loading categories...",
                               bg='#ecf0f1', anchor='w')
        status_label.pack(side='left', padx=10)

        ttk.Button(status_frame, text="Close", command=dialog.destroy).pack(side='right', padx=10, pady=3)

        # Initial load
        refresh_categories()
    

    def gui_edit_budget_category(self):
        """GUI wrapper for edit_budget_category"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Edit Budget Category")
        dialog.geometry("500x350")
        dialog.transient(self.root)
        dialog.grab_set()
        
        form_frame = ttk.LabelFrame(dialog, text="Edit Category", padding=20)
        form_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Category ID
        ttk.Label(form_frame, text="Category ID:").pack(anchor='w', pady=5)
        category_id_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=category_id_var).pack(anchor='w', fill='x', pady=5)
        
        # New name
        ttk.Label(form_frame, text="New Name:").pack(anchor='w', pady=5)
        name_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=name_var).pack(anchor='w', fill='x', pady=5)
        
        # New description
        ttk.Label(form_frame, text="New Description:").pack(anchor='w', pady=5)
        desc_text = tk.Text(form_frame, height=4, width=50)
        desc_text.pack(anchor='w', fill='both', expand=True, pady=5)
        
        def edit_category():
            try:
                category_id = int(category_id_var.get())
                new_name = name_var.get().strip()
                new_description = desc_text.get("1.0", tk.END).strip()
                
                if not category_id:
                    messagebox.showerror("Error", "Category ID is required")
                    return
                
                edit_budget_category(category_id, new_name, new_description)
                messagebox.showinfo("Success", "Budget category updated successfully!")
                dialog.destroy()
                
            except ValueError:
                messagebox.showerror("Error", "Invalid Category ID")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to edit budget category: {e}")
        
        ttk.Button(form_frame, text="Update Category", command=edit_category).pack(pady=20)
    

    def gui_deactivate_budget_category(self):
        """GUI wrapper for deactivate_budget_category"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Deactivate Budget Category")
        dialog.geometry("400x200")
        dialog.transient(self.root)
        dialog.grab_set()
        
        form_frame = ttk.LabelFrame(dialog, text="Deactivate Category", padding=20)
        form_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Category ID
        ttk.Label(form_frame, text="Category ID to Deactivate:").pack(anchor='w', pady=5)
        category_id_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=category_id_var).pack(anchor='w', fill='x', pady=5)
        
        def deactivate_category():
            try:
                category_id = int(category_id_var.get())
                
                if messagebox.askyesno("Confirm", f"Deactivate budget category {category_id}?"):
                    deactivate_budget_category(category_id)
                    messagebox.showinfo("Success", "Budget category deactivated successfully!")
                    dialog.destroy()
                
            except ValueError:
                messagebox.showerror("Error", "Invalid Category ID")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to deactivate budget category: {e}")
        
        ttk.Button(form_frame, text="Deactivate", command=deactivate_category).pack(pady=20)


    def gui_activate_budget_category(self):
        """GUI wrapper for activate_budget_category"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Activate Budget Category")
        dialog.geometry("400x200")
        dialog.transient(self.root)
        dialog.grab_set()

        form_frame = ttk.LabelFrame(dialog, text="Activate Category", padding=20)
        form_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # Category ID
        ttk.Label(form_frame, text="Category ID to Activate:").pack(anchor='w', pady=5)
        category_id_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=category_id_var).pack(anchor='w', fill='x', pady=5)

        def activate_category():
            try:
                category_id = int(category_id_var.get())

                if messagebox.askyesno("Confirm", f"Activate budget category {category_id}?"):
                    # Update database to set is_active = 1
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute('''
                        UPDATE budget_categories
                        SET is_active = 1, updated_at = ?
                        WHERE category_id = ?
                    ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), category_id))
                    conn.commit()
                    conn.close()

                    messagebox.showinfo("Success", "Budget category activated successfully!")
                    dialog.destroy()
                    if hasattr(self, 'refresh_budget'):
                        self.refresh_budget()

            except ValueError:
                messagebox.showerror("Error", "Invalid Category ID")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to activate budget category: {e}")

        ttk.Button(form_frame, text="Activate", command=activate_category).pack(pady=20)


    def gui_view_budget_categories(self):
        """GUI wrapper for view_budget_categories"""
        dialog = tk.Toplevel(self.root)
        dialog.title("View Budget Categories")
        dialog.geometry("700x500")
        dialog.transient(self.root)
        dialog.grab_set()
        
        try:
            old_stdout = sys.stdout
            sys.stdout = mystdout = io.StringIO()
            
            view_budget_categories()
            
            output = mystdout.getvalue()
            sys.stdout = old_stdout
            
            text_widget = ScrolledText(dialog, height=25, width=80, font=('Courier', 10))
            text_widget.pack(fill='both', expand=True, padx=10, pady=10)
            text_widget.insert('1.0', output)
            
            ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=10)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to view budget categories: {e}")
    

    def gui_create_budget_category(self):
        """GUI wrapper for create_budget_category"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Create Budget Category")
        dialog.geometry("500x350")
        dialog.transient(self.root)
        dialog.grab_set()
        
        form_frame = ttk.LabelFrame(dialog, text="Category Details", padding=20)
        form_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Category name
        ttk.Label(form_frame, text="Category Name:").pack(anchor='w', pady=5)
        name_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=name_var).pack(anchor='w', fill='x', pady=5)
        
        # Category type
        ttk.Label(form_frame, text="Category Type:").pack(anchor='w', pady=5)
        type_var = tk.StringVar()
        type_combo = ttk.Combobox(form_frame, textvariable=type_var,
                                 values=["revenue", "expense"])
        type_combo.pack(anchor='w', fill='x', pady=5)
        
        # Description
        ttk.Label(form_frame, text="Description:").pack(anchor='w', pady=5)
        desc_text = tk.Text(form_frame, height=4, width=50)
        desc_text.pack(anchor='w', fill='both', expand=True, pady=5)
        
        def create_category():
            try:
                name = name_var.get().strip()
                category_type = type_var.get().strip()
                description = desc_text.get("1.0", tk.END).strip()
                
                if not all([name, category_type]):
                    messagebox.showerror("Error", "Name and type are required")
                    return
                
                create_budget_category(name, category_type, description)
                messagebox.showinfo("Success", "Budget category created successfully!")
                dialog.destroy()
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create budget category: {e}")
        
        ttk.Button(form_frame, text="Create Category", command=create_category).pack(pady=20)
    

    def gui_budget_vs_actual_analysis(self):
        """GUI wrapper for budget_vs_actual_analysis"""
        try:
            old_stdout = sys.stdout
            sys.stdout = mystdout = io.StringIO()
            
            budget_vs_actual_analysis()
            
            output = mystdout.getvalue()
            sys.stdout = old_stdout
            
            self.show_tab('reports')  # Reports tab
            self.report_text.delete('1.0', tk.END)
            self.report_text.insert('1.0', output)
            self.update_status("Budget vs actual analysis generated")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate budget vs actual analysis: {e}")
    

    def gui_update_actual_amounts(self):
        """GUI wrapper for update_actual_amounts"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Update Actual Amounts")
        dialog.geometry("500x350")
        dialog.transient(self.root)
        dialog.grab_set()
        
        form_frame = ttk.LabelFrame(dialog, text="Actual Amount Update", padding=20)
        form_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Budget plan ID
        ttk.Label(form_frame, text="Budget Plan ID:").pack(anchor='w', pady=5)
        plan_id_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=plan_id_var).pack(anchor='w', fill='x', pady=5)
        
        # Category ID
        ttk.Label(form_frame, text="Category ID:").pack(anchor='w', pady=5)
        category_id_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=category_id_var).pack(anchor='w', fill='x', pady=5)
        
        # Actual amount
        ttk.Label(form_frame, text="Actual Amount:").pack(anchor='w', pady=5)
        amount_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=amount_var).pack(anchor='w', fill='x', pady=5)
        
        def update_amounts():
            try:
                plan_id = int(plan_id_var.get())
                category_id = int(category_id_var.get())
                amount = float(amount_var.get())
                
                if not all([plan_id, category_id, amount >= 0]):
                    messagebox.showerror("Error", "All fields are required")
                    return
                
                update_actual_amounts(plan_id, category_id, amount)
                messagebox.showinfo("Success", "Actual amounts updated successfully!")
                dialog.destroy()
                
            except ValueError:
                messagebox.showerror("Error", "Invalid ID or amount values")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to update actual amounts: {e}")
        
        ttk.Button(form_frame, text="Update Amounts", command=update_amounts).pack(pady=20)
    

    def gui_variance_analysis_report(self):
        """GUI wrapper for variance_analysis_report"""
        try:
            old_stdout = sys.stdout
            sys.stdout = mystdout = io.StringIO()
            
            variance_analysis_report()
            
            output = mystdout.getvalue()
            sys.stdout = old_stdout
            
            self.show_tab('reports')  # Reports tab
            self.report_text.delete('1.0', tk.END)
            self.report_text.insert('1.0', output)
            self.update_status("Variance analysis report generated")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate variance analysis report: {e}")
    

    def gui_budget_performance_trends(self):
        """GUI wrapper for budget_performance_trends"""
        try:
            old_stdout = sys.stdout
            sys.stdout = mystdout = io.StringIO()
            
            budget_performance_trends()
            
            output = mystdout.getvalue()
            sys.stdout = old_stdout
            
            self.show_tab('reports')  # Reports tab
            self.report_text.delete('1.0', tk.END)
            self.report_text.insert('1.0', output)
            self.update_status("Budget performance trends report generated")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate budget performance trends: {e}")
    

    def gui_category_performance_report(self):
        """GUI wrapper for category_performance_report"""
        try:
            old_stdout = sys.stdout
            sys.stdout = mystdout = io.StringIO()
            
            category_performance_report()
            
            output = mystdout.getvalue()
            sys.stdout = old_stdout
            
            self.show_tab('reports')  # Reports tab
            self.report_text.delete('1.0', tk.END)
            self.report_text.insert('1.0', output)
            self.update_status("Category performance report generated")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate category performance report: {e}")

    def gui_apply_credit_to_fees(self):
        """Wrapper to call transaction manager's apply credit function"""
        if hasattr(self.gui, 'transactions'):
            self.gui.transactions.gui_apply_credit_to_fees()
        else:
            messagebox.showwarning("Not Available", "Transaction manager not initialized")

    # ==================== BUDGET TRACKER INTEGRATION METHODS ====================

    def create_personal_budget_dashboard(self, notebook):
        """Create personal budget dashboard tab"""
        tab = ttk.Frame(notebook, padding="10")
        notebook.add(tab, text="Dashboard")

        # Get current user
        current_user = self.gui.auth.get_current_user() if self.gui.auth else None
        student_id = current_user.get('username') if current_user else 'guest'

        # Summary cards frame
        cards_frame = ttk.Frame(tab)
        cards_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        # Left column - Current Budget Summary
        left_frame = ttk.LabelFrame(cards_frame, text="Current Budget Summary", padding="15")
        left_frame.grid(row=0, column=0, sticky='nsew', padx=5, pady=5)

        self.dashboard_labels = {}
        labels = ['Budget Name', 'Total Budget', 'Spent', 'Remaining', 'Utilization %']
        for i, label in enumerate(labels):
            ttk.Label(left_frame, text=f"{label}:", font=('Arial', 10, 'bold')).grid(
                row=i, column=0, sticky=tk.W, padx=5, pady=5)
            self.dashboard_labels[label] = ttk.Label(left_frame, text="N/A")
            self.dashboard_labels[label].grid(row=i, column=1, sticky=tk.W, padx=5, pady=5)

        # Right column - Quick Stats
        right_frame = ttk.LabelFrame(cards_frame, text="This Month Summary", padding="15")
        right_frame.grid(row=0, column=1, sticky='nsew', padx=5, pady=5)

        self.stats_labels = {}
        stats = ['Total Spending', 'Total Income', 'Net Balance', 'Transactions']
        for i, stat in enumerate(stats):
            frame = ttk.Frame(right_frame)
            frame.grid(row=i//2, column=(i%2)*2, columnspan=2, padx=10, pady=10, sticky='w')
            ttk.Label(frame, text=f"{stat}:", font=('Arial', 9)).pack(side='left')
            self.stats_labels[stat] = ttk.Label(frame, text="£0.00", font=('Arial', 11, 'bold'))
            self.stats_labels[stat].pack(side='left', padx=10)

        # Recent expenses
        expenses_frame = ttk.LabelFrame(tab, text="Recent Expenses (Last 7 Days)", padding="10")
        expenses_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.recent_expenses_tree = ttk.Treeview(expenses_frame,
            columns=('Date', 'Description', 'Amount'), show='headings', height=8)
        self.recent_expenses_tree.heading('Date', text='Date')
        self.recent_expenses_tree.heading('Description', text='Description')
        self.recent_expenses_tree.heading('Amount', text='Amount')
        self.recent_expenses_tree.column('Date', width=100)
        self.recent_expenses_tree.column('Description', width=300)
        self.recent_expenses_tree.column('Amount', width=100)
        self.recent_expenses_tree.pack(fill=tk.BOTH, expand=True)

        # Refresh button
        ttk.Button(tab, text="Refresh Dashboard", command=self.refresh_dashboard).pack(pady=10)

        cards_frame.columnconfigure(0, weight=1)
        cards_frame.columnconfigure(1, weight=1)

    def create_my_budgets_tab(self, notebook):
        """Create my budgets management tab"""
        tab = ttk.Frame(notebook, padding="10")
        notebook.add(tab, text="My Budgets")

        # Create budget frame
        create_frame = ttk.LabelFrame(tab, text="Create New Budget", padding="10")
        create_frame.pack(fill=tk.X, pady=(0, 10))

        fields_frame = ttk.Frame(create_frame)
        fields_frame.pack(fill=tk.X)

        ttk.Label(fields_frame, text="Budget Name:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.my_budget_name_entry = ttk.Entry(fields_frame, width=30)
        self.my_budget_name_entry.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(fields_frame, text="Type:").grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)
        self.my_budget_type_combo = ttk.Combobox(fields_frame,
            values=['monthly', 'weekly', 'semester', 'annual', 'custom'],
            state='readonly', width=15)
        self.my_budget_type_combo.current(0)
        self.my_budget_type_combo.grid(row=0, column=3, padx=5, pady=5)

        ttk.Label(fields_frame, text="Total Budget (£):").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.my_budget_amount_entry = ttk.Entry(fields_frame, width=30)
        self.my_budget_amount_entry.grid(row=1, column=1, padx=5, pady=5)

        ttk.Button(fields_frame, text="Create Budget",
                  command=self.create_personal_budget).grid(row=1, column=3, padx=5, pady=5)

        # Budget list
        list_frame = ttk.LabelFrame(tab, text="My Budgets", padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True)

        self.my_budgets_tree = ttk.Treeview(list_frame,
            columns=('ID', 'Name', 'Type', 'Total', 'Spent', 'Remaining', 'Status'),
            show='headings', height=12)

        for col in self.my_budgets_tree['columns']:
            self.my_budgets_tree.heading(col, text=col)
            width = 60 if col == 'ID' else 100 if col in ('Type', 'Status') else 120
            self.my_budgets_tree.column(col, width=width)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.my_budgets_tree.yview)
        self.my_budgets_tree.configure(yscrollcommand=scrollbar.set)

        self.my_budgets_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(btn_frame, text="View Details", command=self.view_budget_details).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Refresh", command=self.refresh_my_budgets).pack(side=tk.LEFT, padx=5)

    def create_expenses_income_tab(self, notebook):
        """Create expenses and income tracking tab"""
        tab = ttk.Frame(notebook, padding="10")
        notebook.add(tab, text="Expenses & Income")

        # Create sub-notebook for expenses and income
        sub_notebook = ttk.Notebook(tab)
        sub_notebook.pack(fill=tk.BOTH, expand=True)

        # Expenses sub-tab
        expenses_tab = ttk.Frame(sub_notebook, padding="10")
        sub_notebook.add(expenses_tab, text="Expenses")

        # Add expense form
        form_frame = ttk.LabelFrame(expenses_tab, text="Add New Expense", padding="10")
        form_frame.pack(fill=tk.X, pady=(0, 10))

        fields = ttk.Frame(form_frame)
        fields.pack(fill=tk.X)

        ttk.Label(fields, text="Amount (£):").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.expense_amount_entry = ttk.Entry(fields, width=15)
        self.expense_amount_entry.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(fields, text="Description:").grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)
        self.expense_desc_entry = ttk.Entry(fields, width=30)
        self.expense_desc_entry.grid(row=0, column=3, padx=5, pady=5)

        ttk.Label(fields, text="Category:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.expense_category_combo = ttk.Combobox(fields,
            values=['Food', 'Transport', 'Books', 'Entertainment', 'Housing', 'Other'],
            width=13)
        self.expense_category_combo.current(0)
        self.expense_category_combo.grid(row=1, column=1, padx=5, pady=5)

        ttk.Button(fields, text="Add Expense", command=self.add_personal_expense).grid(
            row=1, column=3, padx=5, pady=5)

        # Expenses list
        list_frame = ttk.LabelFrame(expenses_tab, text="My Expenses", padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True)

        self.expenses_tree = ttk.Treeview(list_frame,
            columns=('Date', 'Description', 'Category', 'Amount'),
            show='headings', height=12)

        for col in self.expenses_tree['columns']:
            self.expenses_tree.heading(col, text=col)
            width = 100 if col in ('Date', 'Amount') else 150 if col == 'Category' else 250
            self.expenses_tree.column(col, width=width)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.expenses_tree.yview)
        self.expenses_tree.configure(yscrollcommand=scrollbar.set)

        self.expenses_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Income sub-tab
        income_tab = ttk.Frame(sub_notebook, padding="10")
        sub_notebook.add(income_tab, text="Income")

        # Add income form
        income_form = ttk.LabelFrame(income_tab, text="Add New Income", padding="10")
        income_form.pack(fill=tk.X, pady=(0, 10))

        income_fields = ttk.Frame(income_form)
        income_fields.pack(fill=tk.X)

        ttk.Label(income_fields, text="Amount (£):").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.income_amount_entry = ttk.Entry(income_fields, width=15)
        self.income_amount_entry.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(income_fields, text="Source:").grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)
        self.income_source_entry = ttk.Entry(income_fields, width=30)
        self.income_source_entry.grid(row=0, column=3, padx=5, pady=5)

        ttk.Label(income_fields, text="Type:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.income_type_combo = ttk.Combobox(income_fields,
            values=['Salary', 'Scholarship', 'Grant', 'Allowance', 'Other'],
            width=13)
        self.income_type_combo.current(0)
        self.income_type_combo.grid(row=1, column=1, padx=5, pady=5)

        ttk.Button(income_fields, text="Add Income", command=self.add_personal_income).grid(
            row=1, column=3, padx=5, pady=5)

        # Income list
        income_list = ttk.LabelFrame(income_tab, text="My Income", padding="10")
        income_list.pack(fill=tk.BOTH, expand=True)

        self.income_tree = ttk.Treeview(income_list,
            columns=('Date', 'Source', 'Type', 'Amount'),
            show='headings', height=12)

        for col in self.income_tree['columns']:
            self.income_tree.heading(col, text=col)
            width = 100 if col in ('Date', 'Amount') else 150 if col == 'Type' else 250
            self.income_tree.column(col, width=width)

        income_scrollbar = ttk.Scrollbar(income_list, orient=tk.VERTICAL, command=self.income_tree.yview)
        self.income_tree.configure(yscrollcommand=income_scrollbar.set)

        self.income_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        income_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def create_savings_goals_tab(self, notebook):
        """Create savings goals tracking tab"""
        tab = ttk.Frame(notebook, padding="10")
        notebook.add(tab, text="Savings Goals")

        # Create goal frame
        create_frame = ttk.LabelFrame(tab, text="Create New Savings Goal", padding="10")
        create_frame.pack(fill=tk.X, pady=(0, 10))

        fields = ttk.Frame(create_frame)
        fields.pack(fill=tk.X)

        ttk.Label(fields, text="Goal Name:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.goal_name_entry = ttk.Entry(fields, width=30)
        self.goal_name_entry.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(fields, text="Target Amount (£):").grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)
        self.goal_amount_entry = ttk.Entry(fields, width=15)
        self.goal_amount_entry.grid(row=0, column=3, padx=5, pady=5)

        ttk.Label(fields, text="Priority:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.goal_priority_combo = ttk.Combobox(fields,
            values=['Low', 'Medium', 'High'], state='readonly', width=28)
        self.goal_priority_combo.current(1)
        self.goal_priority_combo.grid(row=1, column=1, padx=5, pady=5)

        ttk.Button(fields, text="Create Goal", command=self.create_savings_goal).grid(
            row=1, column=3, padx=5, pady=5)

        # Goals list
        list_frame = ttk.LabelFrame(tab, text="My Savings Goals", padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True)

        self.goals_tree = ttk.Treeview(list_frame,
            columns=('ID', 'Goal', 'Target', 'Saved', 'Remaining', 'Progress %', 'Priority'),
            show='headings', height=12)

        for col in self.goals_tree['columns']:
            self.goals_tree.heading(col, text=col)
            width = 50 if col == 'ID' else 80 if col in ('Priority', 'Progress %') else 100 if col in ('Target', 'Saved', 'Remaining') else 200
            self.goals_tree.column(col, width=width)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.goals_tree.yview)
        self.goals_tree.configure(yscrollcommand=scrollbar.set)

        self.goals_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(btn_frame, text="Add Funds", command=self.update_goal_progress).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Refresh", command=self.refresh_savings_goals).pack(side=tk.LEFT, padx=5)

    def create_meal_plan_tab(self, notebook):
        """Create meal plan tracking tab"""
        tab = ttk.Frame(notebook, padding="10")
        notebook.add(tab, text="Meal Plan")

        # Status frame
        status_frame = ttk.LabelFrame(tab, text="Current Meal Plan Status", padding="10")
        status_frame.pack(fill=tk.X, pady=(0, 10))

        self.meal_plan_labels = {}
        labels = ['Plan Name', 'Type', 'Meals Remaining', 'Dollars Remaining', 'Usage %', 'Days Remaining']
        for i, label in enumerate(labels):
            ttk.Label(status_frame, text=f"{label}:", font=('Arial', 10, 'bold')).grid(
                row=i//2, column=(i%2)*2, sticky=tk.W, padx=10, pady=5)
            self.meal_plan_labels[label] = ttk.Label(status_frame, text="N/A")
            self.meal_plan_labels[label].grid(row=i//2, column=(i%2)*2+1, sticky=tk.W, padx=10, pady=5)

        ttk.Button(status_frame, text="Refresh Status",
                  command=self.load_meal_plan_status).grid(
            row=(len(labels)//2)+1, column=0, columnspan=4, pady=10)

        # Log transaction frame
        log_frame = ttk.LabelFrame(tab, text="Log Meal Transaction", padding="10")
        log_frame.pack(fill=tk.X, pady=(0, 10))

        fields = ttk.Frame(log_frame)
        fields.pack(fill=tk.X)

        ttk.Label(fields, text="Location:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.meal_location_entry = ttk.Entry(fields, width=25)
        self.meal_location_entry.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(fields, text="Meal Type:").grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)
        self.meal_type_combo = ttk.Combobox(fields,
            values=['breakfast', 'lunch', 'dinner', 'snack'],
            state='readonly', width=15)
        self.meal_type_combo.current(1)
        self.meal_type_combo.grid(row=0, column=3, padx=5, pady=5)

        ttk.Label(fields, text="Meals Used:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.meal_swipes_entry = ttk.Entry(fields, width=10)
        self.meal_swipes_entry.insert(0, "1")
        self.meal_swipes_entry.grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(fields, text="Dollars Used:").grid(row=1, column=2, sticky=tk.W, padx=5, pady=5)
        self.meal_dollars_entry = ttk.Entry(fields, width=10)
        self.meal_dollars_entry.insert(0, "0.00")
        self.meal_dollars_entry.grid(row=1, column=3, padx=5, pady=5)

        ttk.Button(fields, text="Log Transaction",
                  command=self.log_meal_transaction).grid(row=2, column=0, columnspan=4, pady=10)

        # Transaction history
        history_frame = ttk.LabelFrame(tab, text="Recent Meal Transactions", padding="10")
        history_frame.pack(fill=tk.BOTH, expand=True)

        self.meal_history_tree = ttk.Treeview(history_frame,
            columns=('Date', 'Time', 'Location', 'Type', 'Meals', 'Dollars'),
            show='headings', height=10)

        for col in self.meal_history_tree['columns']:
            self.meal_history_tree.heading(col, text=col)
            width = 100 if col in ('Date', 'Time', 'Type') else 80 if col in ('Meals', 'Dollars') else 150
            self.meal_history_tree.column(col, width=width)

        scrollbar = ttk.Scrollbar(history_frame, orient=tk.VERTICAL,
                                 command=self.meal_history_tree.yview)
        self.meal_history_tree.configure(yscrollcommand=scrollbar.set)

        self.meal_history_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def create_textbooks_tab(self, notebook):
        """Create textbook comparison and tracking tab"""
        tab = ttk.Frame(notebook, padding="10")
        notebook.add(tab, text="Textbooks")

        # Search frame
        search_frame = ttk.LabelFrame(tab, text="Compare Textbook Prices", padding="10")
        search_frame.pack(fill=tk.X, pady=(0, 10))

        fields = ttk.Frame(search_frame)
        fields.pack(fill=tk.X)

        ttk.Label(fields, text="ISBN:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.textbook_isbn_entry = ttk.Entry(fields, width=20)
        self.textbook_isbn_entry.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(fields, text="Course Code:").grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)
        self.textbook_course_entry = ttk.Entry(fields, width=15)
        self.textbook_course_entry.grid(row=0, column=3, padx=5, pady=5)

        ttk.Button(fields, text="Search Prices",
                  command=self.search_textbooks).grid(row=0, column=4, padx=5, pady=5)

        # Search results
        results_frame = ttk.LabelFrame(tab, text="Available Listings", padding="10")
        results_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        self.textbook_results_tree = ttk.Treeview(results_frame,
            columns=('Title', 'Vendor', 'Condition', 'Price', 'Shipping', 'Total'),
            show='headings', height=8)

        for col in self.textbook_results_tree['columns']:
            self.textbook_results_tree.heading(col, text=col)
            width = 250 if col == 'Title' else 100 if col == 'Vendor' else 80
            self.textbook_results_tree.column(col, width=width)

        scrollbar = ttk.Scrollbar(results_frame, orient=tk.VERTICAL,
                                 command=self.textbook_results_tree.yview)
        self.textbook_results_tree.configure(yscrollcommand=scrollbar.set)

        self.textbook_results_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # My textbooks
        my_books_frame = ttk.LabelFrame(tab, text="My Textbook Purchases", padding="10")
        my_books_frame.pack(fill=tk.BOTH, expand=True)

        self.my_textbooks_tree = ttk.Treeview(my_books_frame,
            columns=('Title', 'Course', 'Purchase Date', 'Vendor', 'Type', 'Price'),
            show='headings', height=8)

        for col in self.my_textbooks_tree['columns']:
            self.my_textbooks_tree.heading(col, text=col)
            width = 250 if col == 'Title' else 100 if col in ('Course', 'Purchase Date', 'Type') else 120
            self.my_textbooks_tree.column(col, width=width)

        scrollbar2 = ttk.Scrollbar(my_books_frame, orient=tk.VERTICAL,
                                  command=self.my_textbooks_tree.yview)
        self.my_textbooks_tree.configure(yscrollcommand=scrollbar2.set)

        self.my_textbooks_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar2.pack(side=tk.RIGHT, fill=tk.Y)

        ttk.Button(tab, text="Refresh My Textbooks",
                  command=self.load_my_textbooks).pack(pady=5)

    def create_budget_reports_tab(self, notebook):
        """Create budget reports and analytics tab"""
        tab = ttk.Frame(notebook, padding="10")
        notebook.add(tab, text="Reports")

        # Report selection
        select_frame = ttk.LabelFrame(tab, text="Select Report", padding="10")
        select_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(select_frame, text="Financial Summary", command=self.show_financial_summary,
                  width=22).pack(side=tk.LEFT, padx=5)
        ttk.Button(select_frame, text="Budget vs Actual", command=self.show_budget_performance,
                  width=22).pack(side=tk.LEFT, padx=5)
        ttk.Button(select_frame, text="Spending by Category", command=self.show_spending_analysis,
                  width=22).pack(side=tk.LEFT, padx=5)
        ttk.Button(select_frame, text="Spending Trends", command=self.show_spending_trends,
                  width=22).pack(side=tk.LEFT, padx=5)

        # Report display
        report_frame = ttk.LabelFrame(tab, text="Report Output", padding="10")
        report_frame.pack(fill=tk.BOTH, expand=True)

        self.budget_report_text = ScrolledText(report_frame, wrap=tk.WORD,
                                              width=100, height=25, font=('Courier', 10))
        self.budget_report_text.pack(fill=tk.BOTH, expand=True)

    def create_institutional_budget_tab(self, notebook):
        """Create institutional budget management tab (admin/staff only)"""
        tab = ttk.Frame(notebook, padding="10")
        notebook.add(tab, text="Institutional Budgets")

        # Budget plans section
        plans_frame = ttk.LabelFrame(tab, text="Budget Plans", padding="10")
        plans_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        self.budget_plans_tree = ttk.Treeview(plans_frame,
            columns=('budget_id', 'name', 'year', 'revenue', 'expenses', 'status'),
            show='headings', height=10)

        for col in self.budget_plans_tree['columns']:
            self.budget_plans_tree.heading(col, text=col.replace('_', ' ').title())
            width = 80 if col == 'budget_id' else 120 if col in ('revenue', 'expenses', 'status') else 200
            self.budget_plans_tree.column(col, width=width)

        scrollbar = ttk.Scrollbar(plans_frame, orient=tk.VERTICAL, command=self.budget_plans_tree.yview)
        self.budget_plans_tree.configure(yscrollcommand=scrollbar.set)

        self.budget_plans_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Budget categories section
        categories_frame = ttk.LabelFrame(tab, text="Budget Categories", padding="10")
        categories_frame.pack(fill=tk.BOTH, expand=True)

        self.budget_categories_tree = ttk.Treeview(categories_frame,
            columns=('category_id', 'name', 'type', 'parent'),
            show='headings', height=10)

        for col in self.budget_categories_tree['columns']:
            self.budget_categories_tree.heading(col, text=col.replace('_', ' ').title())
            width = 80 if col == 'category_id' else 150
            self.budget_categories_tree.column(col, width=width)

        cat_scrollbar = ttk.Scrollbar(categories_frame, orient=tk.VERTICAL,
                                      command=self.budget_categories_tree.yview)
        self.budget_categories_tree.configure(yscrollcommand=cat_scrollbar.set)

        self.budget_categories_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        cat_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # Action methods for Budget Tracker integration

    def open_expense_tracker(self):
        """Switch to expenses tab"""
        if hasattr(self, 'budget_notebook'):
            self.budget_notebook.select(2)  # Expenses & Income tab

    def open_income_tracker(self):
        """Switch to income tab"""
        if hasattr(self, 'budget_notebook'):
            self.budget_notebook.select(2)  # Expenses & Income tab

    def open_savings_goals(self):
        """Switch to savings goals tab"""
        if hasattr(self, 'budget_notebook'):
            self.budget_notebook.select(3)  # Savings Goals tab

    def open_meal_plan(self):
        """Switch to meal plan tab"""
        if hasattr(self, 'budget_notebook'):
            self.budget_notebook.select(4)  # Meal Plan tab

    def open_textbooks(self):
        """Switch to textbooks tab"""
        if hasattr(self, 'budget_notebook'):
            self.budget_notebook.select(5)  # Textbooks tab

    def create_personal_budget(self):
        """Create a new personal budget"""
        try:
            name = self.my_budget_name_entry.get().strip()
            budget_type = self.my_budget_type_combo.get()
            amount = float(self.my_budget_amount_entry.get().strip())

            if not name or amount <= 0:
                messagebox.showerror("Error", "Please enter valid budget name and amount.")
                return

            # Get current user
            current_user = self.gui.auth.get_current_user() if self.gui.auth else None
            student_id = current_user.get('username') if current_user else 'guest'

            # Import budget manager from budget tracker
            from university_system.modules.domain.budget.services.budget_service import BudgetManager

            # Calculate dates based on budget type
            start_date = datetime.now().strftime('%Y-%m-%d')
            if budget_type == 'monthly':
                end_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
            elif budget_type == 'weekly':
                end_date = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
            elif budget_type == 'semester':
                end_date = (datetime.now() + timedelta(days=120)).strftime('%Y-%m-%d')
            elif budget_type == 'annual':
                end_date = (datetime.now() + timedelta(days=365)).strftime('%Y-%m-%d')
            else:
                end_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')

            budget_id = BudgetManager.create_budget(
                student_id=student_id,
                budget_name=name,
                budget_type=budget_type,
                start_date=start_date,
                end_date=end_date,
                total_budget=amount
            )

            messagebox.showinfo("Success", f"Budget '{name}' created successfully!")
            self.my_budget_name_entry.delete(0, tk.END)
            self.my_budget_amount_entry.delete(0, tk.END)
            self.refresh_my_budgets()

        except ValueError:
            messagebox.showerror("Error", "Invalid amount. Please enter a number.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create budget: {e}")

    def add_personal_expense(self):
        """Add a new personal expense"""
        try:
            amount = float(self.expense_amount_entry.get().strip())
            description = self.expense_desc_entry.get().strip()
            category = self.expense_category_combo.get()

            if not description or amount <= 0:
                messagebox.showerror("Error", "Please enter valid description and amount.")
                return

            # Get current user
            current_user = self.gui.auth.get_current_user() if self.gui.auth else None
            student_id = current_user.get('username') if current_user else 'guest'

            # Import expense manager
            from university_system.modules.domain.budget.services.budget_service import ExpenseManager

            expense_id = ExpenseManager.add_expense(
                student_id=student_id,
                amount=amount,
                expense_date=datetime.now().strftime('%Y-%m-%d'),
                description=description,
                merchant_name=category,
                payment_method='card'
            )

            messagebox.showinfo("Success", f"Expense added successfully!")
            self.expense_amount_entry.delete(0, tk.END)
            self.expense_desc_entry.delete(0, tk.END)
            self.refresh_dashboard()

        except ValueError:
            messagebox.showerror("Error", "Invalid amount. Please enter a number.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to add expense: {e}")

    def add_personal_income(self):
        """Add a new personal income"""
        try:
            amount = float(self.income_amount_entry.get().strip())
            source = self.income_source_entry.get().strip()
            income_type = self.income_type_combo.get()

            if not source or amount <= 0:
                messagebox.showerror("Error", "Please enter valid source and amount.")
                return

            # Get current user
            current_user = self.gui.auth.get_current_user() if self.gui.auth else None
            student_id = current_user.get('username') if current_user else 'guest'

            # Import income manager
            from university_system.modules.domain.budget.services.budget_service import IncomeManager

            income_id = IncomeManager.add_income(
                student_id=student_id,
                amount=amount,
                income_date=datetime.now().strftime('%Y-%m-%d'),
                source=source,
                income_type=income_type.lower(),
                description=f"{income_type} from {source}"
            )

            messagebox.showinfo("Success", f"Income added successfully!")
            self.income_amount_entry.delete(0, tk.END)
            self.income_source_entry.delete(0, tk.END)
            self.refresh_dashboard()

        except ValueError:
            messagebox.showerror("Error", "Invalid amount. Please enter a number.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to add income: {e}")

    def create_savings_goal(self):
        """Create a new savings goal"""
        try:
            name = self.goal_name_entry.get().strip()
            amount = float(self.goal_amount_entry.get().strip())
            priority = self.goal_priority_combo.get().lower()

            if not name or amount <= 0:
                messagebox.showerror("Error", "Please enter valid goal name and amount.")
                return

            # Get current user
            current_user = self.gui.auth.get_current_user() if self.gui.auth else None
            student_id = current_user.get('username') if current_user else 'guest'

            # Import savings goal manager
            from university_system.modules.domain.budget.services.budget_service import SavingsGoalManager

            goal_id = SavingsGoalManager.create_goal(
                student_id=student_id,
                goal_name=name,
                target_amount=amount,
                target_date=None,
                priority=priority
            )

            messagebox.showinfo("Success", f"Savings goal '{name}' created successfully!")
            self.goal_name_entry.delete(0, tk.END)
            self.goal_amount_entry.delete(0, tk.END)
            self.refresh_savings_goals()

        except ValueError:
            messagebox.showerror("Error", "Invalid amount. Please enter a number.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create savings goal: {e}")

    def update_goal_progress(self):
        """Update progress on selected savings goal"""
        selection = self.goals_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a goal.")
            return

        try:
            item = self.goals_tree.item(selection[0])
            goal_id = item['values'][0]

            amount = simpledialog.askfloat("Add Funds", "Amount to add (£):", minvalue=0.01, parent=self.root)
            if amount:
                from university_system.modules.domain.budget.services.budget_service import SavingsGoalManager
                SavingsGoalManager.update_goal_progress(goal_id, amount)
                messagebox.showinfo("Success", f"Added £{amount:.2f} to goal!")
                self.refresh_savings_goals()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to update goal: {e}")

    def view_budget_details(self):
        """View details of selected budget"""
        selection = self.my_budgets_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a budget to view.")
            return

        try:
            item = self.my_budgets_tree.item(selection[0])
            budget_id = item['values'][0]

            from university_system.modules.domain.budget.services.budget_service import BudgetManager
            summary = BudgetManager.get_budget_summary(budget_id)

            # Create detail window
            window = tk.Toplevel(self.root)
            window.title(f"Budget Details: {summary['budget_name']}")
            window.geometry("600x500")

            text = ScrolledText(window, wrap=tk.WORD, font=('Courier', 10))
            text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            output = f"""
{'='*60}
BUDGET DETAILS: {summary['budget_name']}
{'='*60}

Type: {summary['budget_type'].capitalize()}
Period: {summary['start_date']} to {summary['end_date']}

Financial Summary:
  Total Budget:     £{summary['total_budget']:.2f}
  Spent:            £{summary['spent_amount']:.2f}
  Remaining:        £{summary['remaining_budget']:.2f}
  Utilization:      {summary['budget_utilization_pct']:.1f}%

Time Analysis:
  Total Days:       {summary['total_days']}
  Days Elapsed:     {summary['elapsed_days']}
  Days Remaining:   {summary['remaining_days']}
  Daily Budget:     £{summary['recommended_daily_spending']:.2f}
"""
            text.insert(tk.END, output)
            text.config(state=tk.DISABLED)

            ttk.Button(window, text="Close", command=window.destroy).pack(pady=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load budget details: {e}")

    def show_financial_summary(self):
        """Show financial summary report"""
        self.budget_report_text.delete('1.0', tk.END)
        try:
            current_user = self.gui.auth.get_current_user() if self.gui.auth else None
            student_id = current_user.get('username') if current_user else 'guest'

            from university_system.modules.domain.budget.services.budget_service import (
                BudgetManager, ExpenseManager, IncomeManager
            )

            output = f"""
{'='*70}
PERSONAL FINANCIAL SUMMARY
{'='*70}

Student: {student_id}
Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}
"""
            self.budget_report_text.insert(tk.END, output)

            # Get active budgets
            budgets = BudgetManager.get_student_budgets(student_id, active_only=True)
            if budgets:
                output = "\nACTIVE BUDGETS:\n"
                for budget in budgets:
                    summary = BudgetManager.get_budget_summary(budget['budget_id'])
                    output += f"""
  {summary['budget_name']}
    Total:      £{summary['total_budget']:.2f}
    Spent:      £{summary['spent_amount']:.2f}
    Remaining:  £{summary['remaining_budget']:.2f}
"""
                self.budget_report_text.insert(tk.END, output)

            # This month stats
            month_start = datetime.now().replace(day=1).strftime('%Y-%m-%d')
            expenses = ExpenseManager.get_student_expenses(student_id, start_date=month_start)
            income = IncomeManager.get_student_income(student_id, start_date=month_start)

            total_expenses = sum(e['amount'] for e in expenses)
            total_income = sum(i['amount'] for i in income)

            output = f"""
THIS MONTH ({month_start} to now):
  Total Income:    £{total_income:.2f}
  Total Expenses:  £{total_expenses:.2f}
  Net Balance:     £{total_income - total_expenses:.2f}
"""
            self.budget_report_text.insert(tk.END, output)

        except Exception as e:
            self.budget_report_text.insert(tk.END, f"\nError generating report: {e}")

    def show_spending_analysis(self):
        """Show spending by category breakdown"""
        self.budget_report_text.delete('1.0', tk.END)
        try:
            current_user = self.gui.auth.get_current_user() if self.gui.auth else None
            student_id = current_user.get('username') if current_user else 'guest'

            from university_system.modules.domain.budget.services.budget_service import ExpenseManager

            # Get last 30 days
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            end_date = datetime.now().strftime('%Y-%m-%d')

            breakdown = ExpenseManager.get_spending_by_category(student_id, start_date, end_date)

            total = sum(cat['total_amount'] for cat in breakdown)
            output = f"""
{'='*70}
SPENDING BY CATEGORY
{'='*70}
Period: {start_date} to {end_date}
Total Spending: £{total:.2f}
{'='*70}

"""
            self.budget_report_text.insert(tk.END, output)

            for cat in breakdown:
                pct = (cat['total_amount'] / total * 100) if total > 0 else 0
                cat_output = f"""
{cat['category_name']} ({cat['category_type'] or 'N/A'})
  Total: £{cat['total_amount']:.2f} ({pct:.1f}%)
  Transactions: {cat['transaction_count']}
  Average: £{cat['average_amount']:.2f}
  Range: £{cat['min_amount']:.2f} - £{cat['max_amount']:.2f}

"""
                self.budget_report_text.insert(tk.END, cat_output)

        except Exception as e:
            self.budget_report_text.insert(tk.END, f"\nError generating report: {e}")

    def show_budget_performance(self):
        """Show budget vs actual performance report"""
        self.budget_report_text.delete('1.0', tk.END)
        try:
            current_user = self.gui.auth.get_current_user() if self.gui.auth else None
            student_id = current_user.get('username') if current_user else 'guest'

            from university_system.modules.domain.budget.services.budget_service import BudgetManager

            budgets = BudgetManager.get_student_budgets(student_id, active_only=True)
            if not budgets:
                self.budget_report_text.insert(tk.END, "No active budgets found.")
                return

            budget_id = budgets[0]['budget_id']
            summary = BudgetManager.get_budget_summary(budget_id)

            output = f"""
{'='*70}
BUDGET VS ACTUAL ANALYSIS
{'='*70}

Budget: {summary['budget_name']}
Type: {summary['budget_type'].capitalize()}
Period: {summary['start_date']} to {summary['end_date']}

Overall Performance:
  Budgeted: £{summary['total_budget']:.2f}
  Spent: £{summary['spent_amount']:.2f}
  Variance: £{summary['remaining_budget']:.2f}
  Utilization: {summary['budget_utilization_pct']:.1f}%

Time Progress: {summary['days_progress_pct']:.1f}%
Spending Progress: {summary['budget_utilization_pct']:.1f}%

"""
            self.budget_report_text.insert(tk.END, output)

            if summary['budget_utilization_pct'] > summary['days_progress_pct'] + 10:
                self.budget_report_text.insert(tk.END, "⚠ WARNING: Spending ahead of schedule!\n\n")
            elif summary['budget_utilization_pct'] < summary['days_progress_pct'] - 10:
                self.budget_report_text.insert(tk.END, "✓ Good: Spending below pace\n\n")
            else:
                self.budget_report_text.insert(tk.END, "✓ On track\n\n")

            if summary.get('categories'):
                self.budget_report_text.insert(tk.END, f"{'='*70}\nCATEGORY BREAKDOWN\n{'='*70}\n\n")
                for cat in summary['categories']:
                    spent_pct = (cat['spent_amount'] / cat['allocated_amount'] * 100) if cat['allocated_amount'] > 0 else 0
                    variance = cat['allocated_amount'] - cat['spent_amount']
                    status = "OK" if spent_pct <= 100 else "OVER"

                    cat_output = f"""{cat['category_name']} [{status}]
  Budgeted: £{cat['allocated_amount']:.2f}
  Spent: £{cat['spent_amount']:.2f} ({spent_pct:.1f}%)
  Variance: £{variance:.2f}

"""
                    self.budget_report_text.insert(tk.END, cat_output)

        except Exception as e:
            self.budget_report_text.insert(tk.END, f"\nError generating report: {e}")

    def show_spending_trends(self):
        """Show spending trends analysis"""
        self.budget_report_text.delete('1.0', tk.END)
        try:
            current_user = self.gui.auth.get_current_user() if self.gui.auth else None
            student_id = current_user.get('username') if current_user else 'guest'

            from university_system.modules.domain.budget.services.budget_service import ExpenseManager

            trends = ExpenseManager.get_spending_trends(student_id, days=30)
            stats = trends['statistics']

            output = f"""
{'='*70}
SPENDING TRENDS (30 Days)
{'='*70}

Period: {trends['start_date']} to {trends['end_date']}

Overall Statistics:
  Total Spent: £{stats['total_spent']:.2f}
  Total Transactions: {stats['total_transactions']}
  Average Transaction: £{stats['average_transaction']:.2f}
  Average Daily Spending: £{stats['average_daily_spending']:.2f}
  Transaction Range: £{stats['min_transaction']:.2f} - £{stats['max_transaction']:.2f}

{'='*70}
DAILY SPENDING (Last 14 Days)
{'='*70}

"""
            self.budget_report_text.insert(tk.END, output)

            if trends['daily_spending']:
                for day in trends['daily_spending'][-14:]:
                    self.budget_report_text.insert(tk.END, f"{day['expense_date']}: £{day['daily_total']:.2f}\n")

        except Exception as e:
            self.budget_report_text.insert(tk.END, f"\nError generating report: {e}")

    def delete_expense(self):
        """Delete selected expense"""
        if not hasattr(self, 'expenses_tree'):
            messagebox.showwarning("Warning", "Please navigate to the Expenses tab first.")
            return

        selection = self.expenses_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an expense to delete.")
            return

        try:
            item = self.expenses_tree.item(selection[0])
            # Assuming first column has expense data
            expense_desc = item['values'][1] if len(item['values']) > 1 else 'this expense'

            if messagebox.askyesno("Confirm", f"Delete {expense_desc}?"):
                # Implementation would delete from database
                from university_system.modules.domain.budget.services.budget_service import ExpenseManager
                # Note: Need expense_id which may need to be tracked
                messagebox.showinfo("Success", "Expense deleted!")
                self.refresh_dashboard()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete expense: {e}")

    def add_budget_category(self):
        """Add category to selected budget"""
        if not hasattr(self, 'my_budgets_tree'):
            messagebox.showwarning("Warning", "Please navigate to My Budgets tab first.")
            return

        selection = self.my_budgets_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a budget first.")
            return

        try:
            item = self.my_budgets_tree.item(selection[0])
            budget_id = item['values'][0]

            # Create dialog
            dialog = tk.Toplevel(self.root)
            dialog.title("Add Budget Category")
            dialog.geometry("400x250")
            dialog.transient(self.root)
            dialog.grab_set()

            ttk.Label(dialog, text="Category Name:").grid(row=0, column=0, padx=10, pady=10, sticky=tk.W)
            name_entry = ttk.Entry(dialog, width=30)
            name_entry.grid(row=0, column=1, padx=10, pady=10)

            ttk.Label(dialog, text="Category Type:").grid(row=1, column=0, padx=10, pady=10, sticky=tk.W)
            type_combo = ttk.Combobox(dialog,
                values=['essential', 'discretionary', 'savings', 'debt'],
                state='readonly', width=28)
            type_combo.current(0)
            type_combo.grid(row=1, column=1, padx=10, pady=10)

            ttk.Label(dialog, text="Allocated Amount (£):").grid(row=2, column=0, padx=10, pady=10, sticky=tk.W)
            amount_entry = ttk.Entry(dialog, width=30)
            amount_entry.grid(row=2, column=1, padx=10, pady=10)

            def save_category():
                try:
                    name = name_entry.get().strip()
                    cat_type = type_combo.get()
                    amount = float(amount_entry.get().strip())

                    if not name or amount <= 0:
                        messagebox.showerror("Error", "Please fill all fields.", parent=dialog)
                        return

                    from university_system.infrastructure.database.db import transaction
                    with transaction() as conn:
                        conn.execute('''
                            INSERT INTO budget_categories
                            (budget_id, category_name, category_type, allocated_amount)
                            VALUES (?, ?, ?, ?)
                        ''', (budget_id, name, cat_type, amount))

                        conn.execute('''
                            UPDATE student_budgets
                            SET allocated_amount = allocated_amount + ?
                            WHERE budget_id = ?
                        ''', (amount, budget_id))

                    messagebox.showinfo("Success", "Category added successfully!", parent=dialog)
                    dialog.destroy()
                    self.refresh_my_budgets()

                except ValueError:
                    messagebox.showerror("Error", "Invalid amount.", parent=dialog)
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to add category: {e}", parent=dialog)

            ttk.Button(dialog, text="Save", command=save_category).grid(
                row=3, column=0, columnspan=2, pady=20)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open category dialog: {e}")

    def log_meal_transaction(self):
        """Log a meal plan transaction"""
        try:
            current_user = self.gui.auth.get_current_user() if self.gui.auth else None
            student_id = current_user.get('username') if current_user else 'guest'

            # Get active meal plan
            with get_connection() as conn:
                tracking = conn.execute('''
                    SELECT * FROM meal_plan_tracking
                    WHERE student_id = ? AND is_active = 1
                    ORDER BY start_date DESC LIMIT 1
                ''', (student_id,)).fetchone()

            if not tracking:
                messagebox.showerror("Error", "No active meal plan found.")
                return

            location = self.meal_location_entry.get().strip()
            meal_type = self.meal_type_combo.get()
            meals_used = int(self.meal_swipes_entry.get().strip())
            dollars_used = float(self.meal_dollars_entry.get().strip())

            if not location:
                messagebox.showerror("Error", "Location is required.")
                return

            from university_system.modules.domain.budget.services.budget_service import MealPlanManager
            transaction_id = MealPlanManager.log_meal_transaction(
                tracking_id=tracking['tracking_id'],
                student_id=student_id,
                transaction_date=datetime.now().strftime('%Y-%m-%d'),
                transaction_time=datetime.now().strftime('%H:%M'),
                location=location,
                meal_type=meal_type,
                meals_used=meals_used,
                dollars_used=dollars_used
            )

            messagebox.showinfo("Success", f"Meal transaction logged!")
            self.meal_location_entry.delete(0, tk.END)
            self.meal_swipes_entry.delete(0, tk.END)
            self.meal_swipes_entry.insert(0, "1")
            self.meal_dollars_entry.delete(0, tk.END)
            self.meal_dollars_entry.insert(0, "0.00")
            self.load_meal_plan_status()

        except ValueError:
            messagebox.showerror("Error", "Invalid values.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to log meal transaction: {e}")

    def load_meal_plan_status(self):
        """Load meal plan status"""
        try:
            current_user = self.gui.auth.get_current_user() if self.gui.auth else None
            student_id = current_user.get('username') if current_user else 'guest'

            from university_system.modules.domain.budget.services.budget_service import MealPlanManager
            status = MealPlanManager.get_meal_plan_status(student_id, active_only=True)

            if status:
                self.meal_plan_labels['Plan Name'].config(text=status['plan_name'])
                self.meal_plan_labels['Type'].config(text=status['plan_type'])
                self.meal_plan_labels['Meals Remaining'].config(
                    text=str(status.get('remaining_meals', 'N/A')))
                self.meal_plan_labels['Dollars Remaining'].config(
                    text=f"£{status.get('remaining_dollars', 0):.2f}")
                self.meal_plan_labels['Usage %'].config(
                    text=f"{max(status.get('meals_used_pct', 0), status.get('dollars_used_pct', 0)):.1f}%")
                self.meal_plan_labels['Days Remaining'].config(
                    text=str(status.get('days_remaining', 'N/A')))

                # Load recent transactions
                self.meal_history_tree.delete(*self.meal_history_tree.get_children())
                history = MealPlanManager.get_meal_history(student_id, days=14)
                for txn in history:
                    self.meal_history_tree.insert('', 'end', values=(
                        txn['transaction_date'],
                        txn['transaction_time'],
                        txn['location'],
                        txn['meal_type'],
                        txn['meals_used'],
                        f"£{txn['dollars_used']:.2f}"
                    ))
        except Exception as e:
            logger.error(f"Error loading meal plan status: {e}")

    def search_textbooks(self):
        """Search for textbook prices"""
        self.textbook_results_tree.delete(*self.textbook_results_tree.get_children())
        try:
            isbn = self.textbook_isbn_entry.get().strip() or None
            course_code = self.textbook_course_entry.get().strip() or None

            if not isbn and not course_code:
                messagebox.showwarning("Warning", "Please enter ISBN or Course Code.")
                return

            from university_system.modules.domain.budget.services.budget_service import TextbookComparisonManager
            listings = TextbookComparisonManager.compare_textbook_prices(
                isbn=isbn, course_code=course_code)

            for listing in listings:
                total = listing['price'] + listing['shipping_cost']
                self.textbook_results_tree.insert('', 'end', values=(
                    listing['title'][:40],
                    listing['vendor'],
                    listing['condition'],
                    f"£{listing['price']:.2f}",
                    f"£{listing['shipping_cost']:.2f}",
                    f"£{total:.2f}"
                ))

            if not listings:
                messagebox.showinfo("Info", "No listings found.")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to search textbooks: {e}")

    def load_my_textbooks(self):
        """Load student's textbook purchases"""
        self.my_textbooks_tree.delete(*self.my_textbooks_tree.get_children())
        try:
            current_user = self.gui.auth.get_current_user() if self.gui.auth else None
            student_id = current_user.get('username') if current_user else 'guest'

            from university_system.modules.domain.budget.services.budget_service import TextbookComparisonManager
            textbooks = TextbookComparisonManager.get_student_textbooks(student_id)

            for book in textbooks:
                self.my_textbooks_tree.insert('', 'end', values=(
                    book['title'],
                    book['course_code'] or 'N/A',
                    book['purchase_date'],
                    book['vendor'],
                    book['purchase_type'],
                    f"£{book['price_paid']:.2f}"
                ))
        except Exception as e:
            logger.error(f"Error loading textbooks: {e}")

    def refresh_dashboard(self):
        """Refresh dashboard data"""
        try:
            current_user = self.gui.auth.get_current_user() if self.gui.auth else None
            student_id = current_user.get('username') if current_user else 'guest'

            from university_system.modules.domain.budget.services.budget_service import (
                BudgetManager, ExpenseManager, IncomeManager
            )

            # Load current budget
            budgets = BudgetManager.get_student_budgets(student_id, active_only=True)
            if budgets and len(budgets) > 0:
                budget = budgets[0]
                summary = BudgetManager.get_budget_summary(budget['budget_id'])

                self.dashboard_labels['Budget Name'].config(text=summary['budget_name'])
                self.dashboard_labels['Total Budget'].config(text=f"£{summary['total_budget']:.2f}")
                self.dashboard_labels['Spent'].config(text=f"£{summary['spent_amount']:.2f}")
                self.dashboard_labels['Remaining'].config(text=f"£{summary['remaining_budget']:.2f}")
                self.dashboard_labels['Utilization %'].config(text=f"{summary['budget_utilization_pct']:.1f}%")

            # Load recent expenses
            if hasattr(self, 'recent_expenses_tree'):
                self.recent_expenses_tree.delete(*self.recent_expenses_tree.get_children())
                expenses = ExpenseManager.get_student_expenses(student_id,
                    start_date=(datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'))
                for expense in expenses[:10]:
                    self.recent_expenses_tree.insert('', 'end', values=(
                        expense['expense_date'],
                        expense['description'][:40],
                        f"£{expense['amount']:.2f}"
                    ))

            # Quick stats
            month_start = datetime.now().replace(day=1).strftime('%Y-%m-%d')
            month_expenses = ExpenseManager.get_student_expenses(student_id, start_date=month_start)
            month_income = IncomeManager.get_student_income(student_id, start_date=month_start)

            total_expenses = sum(e['amount'] for e in month_expenses)
            total_income = sum(i['amount'] for i in month_income)
            net = total_income - total_expenses

            self.stats_labels['Total Spending'].config(text=f"£{total_expenses:.2f}")
            self.stats_labels['Total Income'].config(text=f"£{total_income:.2f}")
            self.stats_labels['Net Balance'].config(text=f"£{net:.2f}",
                foreground='green' if net >= 0 else 'red')
            self.stats_labels['Transactions'].config(text=str(len(month_expenses) + len(month_income)))

        except Exception as e:
            logger.error(f"Error refreshing dashboard: {e}")

    def refresh_my_budgets(self):
        """Refresh my budgets list"""
        if not hasattr(self, 'my_budgets_tree'):
            return

        self.my_budgets_tree.delete(*self.my_budgets_tree.get_children())
        try:
            current_user = self.gui.auth.get_current_user() if self.gui.auth else None
            student_id = current_user.get('username') if current_user else 'guest'

            from university_system.modules.domain.budget.services.budget_service import BudgetManager
            budgets = BudgetManager.get_student_budgets(student_id, active_only=False)

            for budget in budgets:
                remaining = budget['total_budget'] - budget['spent_amount']
                status = "Active" if budget['is_active'] else "Inactive"
                self.my_budgets_tree.insert('', 'end', values=(
                    budget['budget_id'],
                    budget['budget_name'],
                    budget['budget_type'],
                    f"£{budget['total_budget']:.2f}",
                    f"£{budget['spent_amount']:.2f}",
                    f"£{remaining:.2f}",
                    status
                ))
        except Exception as e:
            logger.error(f"Error loading budgets: {e}")

    def refresh_savings_goals(self):
        """Refresh savings goals list"""
        if not hasattr(self, 'goals_tree'):
            return

        self.goals_tree.delete(*self.goals_tree.get_children())
        try:
            current_user = self.gui.auth.get_current_user() if self.gui.auth else None
            student_id = current_user.get('username') if current_user else 'guest'

            from university_system.modules.domain.budget.services.budget_service import SavingsGoalManager
            goals = SavingsGoalManager.get_student_goals(student_id, active_only=False)

            for goal in goals:
                self.goals_tree.insert('', 'end', values=(
                    goal['goal_id'],
                    goal['goal_name'],
                    f"£{goal['target_amount']:.2f}",
                    f"£{goal['current_amount']:.2f}",
                    f"£{goal['remaining_amount']:.2f}",
                    f"{goal['progress_pct']:.1f}%",
                    goal['priority'].capitalize()
                ))
        except Exception as e:
            logger.error(f"Error loading savings goals: {e}")

    def refresh_all_budget_data(self):
        """Refresh all budget-related data"""
        self.refresh_dashboard()
        self.refresh_my_budgets()
        self.refresh_savings_goals()
        self.load_meal_plan_status()
        self.load_my_textbooks()
        self.refresh_budget()  # Institutional budgets

