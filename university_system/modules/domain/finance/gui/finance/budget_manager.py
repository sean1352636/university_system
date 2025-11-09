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
from university_system.modules.domain.finance.gui.finance_reporting_gui import launch_financial_gui

# Import authentication - REQUIRED (no fallback for security)
from university_system.infrastructure.auth.user_authentication import UserAuth, get_global_auth
from university_system.infrastructure.shared_context import get_auth

# Import other modules with backward compatibility fallbacks
try:
    from university_system.infrastructure.email.email_service import send_email
    from university_system.infrastructure.database.db import get_connection
    from university_system.infrastructure.logging.log_config import configure_logging, get_log_file
except ImportError:
    # Fallback for backward compatibility (non-security critical)
    def send_email(*args, **kwargs):
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




class BudgetManager:
    """Budget planning and analysis"""

    def __init__(self, gui):
        """Initialize manager with reference to main GUI"""
        self.gui = gui
        self.root = gui.root
        self.conn = gui.conn
        try:
            self.finance_system = gui.finance_system
        except:
            self.finance_system = None

    def create_budget_tab(self):
        """Create budget management tab"""
        budget_frame = tk.Frame(self.gui.layout.content_frame, bg='white')
        self.gui.layout.tab_frames['budget'] = budget_frame
        
        # Budget toolbar - First row
        toolbar = tk.Frame(budget_frame, bg='white')
        toolbar.pack(fill='x', padx=10, pady=5)
        
        tk.Button(toolbar, text="📊 New Budget", command=self.create_budget_plan,
                 bg=self.gui.layout.colors['success'], fg='white').pack(side='left', padx=5)
        tk.Button(toolbar, text="✏️ Edit Budget", command=self.edit_budget_plan,
                 bg=self.gui.layout.colors['warning'], fg='white').pack(side='left', padx=5)
        tk.Button(toolbar, text="📈 Budget Analysis", command=self.budget_analysis,
                 bg=self.gui.layout.colors['secondary'], fg='white').pack(side='left', padx=5)
        tk.Button(toolbar, text="✅ Approve Budget", command=self.approve_budget,
                 bg=self.gui.layout.colors['success'], fg='white').pack(side='left', padx=5)
        
        # Budget toolbar - Second row
        toolbar2 = tk.Frame(budget_frame, bg='white')
        toolbar2.pack(fill='x', padx=10, pady=5)
        
        tk.Button(toolbar2, text="📂 Manage Categories", command=self.gui_manage_budget_categories,
                 bg=self.gui.layout.colors['info'], fg='white').pack(side='left', padx=5)
        tk.Button(toolbar2, text="✏️ Edit Category", command=self.gui_edit_budget_category,
                 bg=self.gui.layout.colors['warning'], fg='white').pack(side='left', padx=5)
        tk.Button(toolbar2, text="🚫 Deactivate Category", command=self.gui_deactivate_budget_category,
                 bg=self.gui.layout.colors['danger'], fg='white').pack(side='left', padx=5)
        tk.Button(toolbar2, text="💰 Update Actuals", command=self.gui_update_actual_amounts,
                 bg=self.gui.layout.colors['primary'], fg='white').pack(side='left', padx=5)
        tk.Button(toolbar2, text="💳 Apply Credits", command=self.gui_apply_credit_to_fees,
                 bg=self.gui.layout.colors['success'], fg='white').pack(side='left', padx=5)
        
        # Budget content with notebook
        budget_notebook = ttk.Notebook(budget_frame)
        budget_notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Budget plans tab
        plans_frame = ttk.Frame(budget_notebook)
        budget_notebook.add(plans_frame, text="Budget Plans")
        
        self.budget_plans_tree = ttk.Treeview(plans_frame,
                                            columns=('budget_id', 'name', 'year', 'revenue', 'expenses', 'status'),
                                            show='headings')
        for col in self.budget_plans_tree['columns']:
            self.budget_plans_tree.heading(col, text=col.replace('_', ' ').title())
        self.budget_plans_tree.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Budget categories tab
        categories_frame = ttk.Frame(budget_notebook)
        budget_notebook.add(categories_frame, text="Categories")
        
        self.budget_categories_tree = ttk.Treeview(categories_frame,
                                                 columns=('category_id', 'name', 'type', 'parent'),
                                                 show='headings')
        for col in self.budget_categories_tree['columns']:
            self.budget_categories_tree.heading(col, text=col.replace('_', ' ').title())
        self.budget_categories_tree.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Load budget data
        self.refresh_budget()
    

    def create_budget_plan(self):
        """Create new budget plan"""
        plan_name = simpledialog.askstring("Budget Plan", "Enter budget plan name:")
        if plan_name:
            year = simpledialog.askstring("Budget Plan", "Enter budget year:", initialvalue=str(datetime.now().year))
            if year:
                amount = simpledialog.askfloat("Budget Plan", "Enter total budget amount:")
                if amount:
                    messagebox.showinfo("Success", f"Budget plan '{plan_name}' for {year} created with £{amount:.2f}")
                    self.refresh_budget()
    

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
    
            try:
                year = int(year_var.get())
                if year < 2000 or year > 2100:
                    raise ValueError("Year must be between 2000 and 2100")
            except ValueError as e:
                messagebox.showwarning("Invalid Year", str(e), parent=edit_dialog)
                return
    
            try:
                revenue = float(revenue_var.get() or 0)
                expenses = float(expenses_var.get() or 0)
                if revenue < 0 or expenses < 0:
                    raise ValueError("Budget amounts cannot be negative")
            except ValueError as e:
                messagebox.showwarning("Invalid Amount", str(e), parent=edit_dialog)
                return
    
            # Update tree item
            self.budget_plans_tree.item(selection[0], values=(
                budget_id,
                new_name,
                year,
                f"£{revenue:,.2f}",
                f"£{expenses:,.2f}",
                status_var.get()
            ))
    
            messagebox.showinfo("Success", f"Budget plan '{new_name}' updated successfully", parent=edit_dialog)
            edit_dialog.destroy()
            if hasattr(self, 'refresh_budget'):
                self.refresh_budget()
    
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
        """GUI wrapper for manage_budget_categories"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Manage Budget Categories")
        dialog.geometry("800x600")
        dialog.transient(self.root)
        dialog.grab_set()
        
        try:
            old_stdout = sys.stdout
            sys.stdout = mystdout = io.StringIO()
            
            manage_budget_categories()
            
            output = mystdout.getvalue()
            sys.stdout = old_stdout
            
            text_widget = ScrolledText(dialog, height=25, width=90, font=('Courier', 10))
            text_widget.pack(fill='both', expand=True, padx=10, pady=10)
            text_widget.insert('1.0', output)
            
            ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=10)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to manage budget categories: {e}")
    

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

