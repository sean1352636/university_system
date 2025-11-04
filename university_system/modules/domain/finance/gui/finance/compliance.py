"""Collections and compliance management"""

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




class ComplianceManager:
    """Collections and compliance management"""

    def __init__(self, gui):
        """Initialize manager with reference to main GUI"""
        self.gui = gui
        self.root = gui.root
        self.conn = gui.conn
        try:
            self.finance_system = gui.finance_system
        except:
            self.finance_system = None

        def create_collections_tab(self):
            """Create collections management tab"""
            collections_frame = tk.Frame(self.content_frame, bg='white')
            self.tab_frames['collections'] = collections_frame
            
            # Collections toolbar
            toolbar = tk.Frame(collections_frame, bg='white')
            toolbar.pack(fill='x', padx=10, pady=5)
            
            tk.Button(toolbar, text="👁️ View Overdue", command=self.view_overdue_accounts,
                     bg=self.colors['danger'], fg='white').pack(side='left', padx=5)
            tk.Button(toolbar, text="📋 Create Case", command=self.create_collection_case,
                     bg=self.colors['warning'], fg='white').pack(side='left', padx=5)
            tk.Button(toolbar, text="🏢 Manage Agencies", command=self.manage_agencies,
                     bg=self.colors['secondary'], fg='white').pack(side='left', padx=5)
            tk.Button(toolbar, text="📈 Track Progress", command=self.track_collections,
                     bg=self.colors['success'], fg='white').pack(side='left', padx=5)
            
            # Additional toolbar buttons (second row if needed)
            toolbar2 = tk.Frame(collections_frame, bg='white')
            toolbar2.pack(fill='x', padx=10, pady=5)
            
            tk.Button(toolbar2, text="📊 Track Progress", command=self.gui_track_collection_progress,
                     bg=self.colors['info'], fg='white').pack(side='left', padx=5)
            tk.Button(toolbar2, text="🔄 Update Case Status", command=self.gui_update_collection_case_status,
                     bg=self.colors['warning'], fg='white').pack(side='left', padx=5)
            tk.Button(toolbar2, text="💰 Create Arrangement", command=self.gui_create_payment_arrangement,
                     bg=self.colors['success'], fg='white').pack(side='left', padx=5)
            tk.Button(toolbar2, text="🏢 Assign to Agency", command=self.gui_assign_to_collection_agency,
                     bg=self.colors['secondary'], fg='white').pack(side='left', padx=5)
            tk.Button(toolbar2, text="📨 Send Notice", command=self.gui_send_collection_notice,
                     bg=self.colors['danger'], fg='white').pack(side='left', padx=5)
            
            # Collections content
            content_frame = tk.PanedWindow(collections_frame, orient='horizontal')
            content_frame.pack(fill='both', expand=True, padx=10, pady=10)
            
            # Left panel - Overdue accounts
            left_panel = tk.LabelFrame(content_frame, text="Overdue Accounts", font=('Arial', 12, 'bold'))
            content_frame.add(left_panel, minsize=400)
            
            self.overdue_tree = ttk.Treeview(left_panel, columns=('student_id', 'name', 'amount', 'days'), show='headings')
            self.overdue_tree.heading('student_id', text='Student ID')
            self.overdue_tree.heading('name', text='Name')
            self.overdue_tree.heading('amount', text='Amount')
            self.overdue_tree.heading('days', text='Days Overdue')
            self.overdue_tree.pack(fill='both', expand=True, padx=5, pady=5)
            
            # Right panel - Collection cases
            right_panel = tk.LabelFrame(content_frame, text="Collection Cases", font=('Arial', 12, 'bold'))
            content_frame.add(right_panel, minsize=400)
            
            self.cases_tree = ttk.Treeview(right_panel, columns=('case_id', 'student', 'status', 'agency'), show='headings')
            self.cases_tree.heading('case_id', text='Case ID')
            self.cases_tree.heading('student', text='Student')
            self.cases_tree.heading('status', text='Status')
            self.cases_tree.heading('agency', text='Agency')
            self.cases_tree.pack(fill='both', expand=True, padx=5, pady=5)
            
            # Load collections data
            self.refresh_collections()
        

        def view_overdue_accounts(self):
            """View overdue accounts"""
            try:
                old_stdout = sys.stdout
                sys.stdout = mystdout = io.StringIO()
                
                view_overdue_accounts()
                
                output = mystdout.getvalue()
                sys.stdout = old_stdout
                
                # Show in a new window
                self.show_text_window("Overdue Accounts", output)
                
            except Exception as e:
                sys.stdout = old_stdout
                messagebox.showerror("Error", f"Failed to view overdue accounts: {str(e)}")
        

        def create_collection_case(self):
            """Create new collection case"""
            case_name = simpledialog.askstring("Collection Case", "Enter case name:")
            if case_name:
                student_id = simpledialog.askstring("Collection Case", "Enter student ID:")
                if student_id:
                    messagebox.showinfo("Success", f"Collection case '{case_name}' created for student {student_id}")
                    # Here you would save to database
                    self.refresh_collections()
        

        def manage_agencies(self):
            """Manage collection agencies"""
            # Create agencies management dialog
            agencies_dialog = tk.Toplevel(self.root)
            agencies_dialog.title("Manage Collection Agencies")
            agencies_dialog.geometry("900x600")
            agencies_dialog.transient(self.root)
    
            ttk.Label(agencies_dialog, text="Collection Agencies Management",
                     font=('TkDefaultFont', 14, 'bold')).pack(pady=10)
    
            # Control buttons
            controls_frame = ttk.Frame(agencies_dialog)
            controls_frame.pack(fill='x', padx=10, pady=5)
    
            ttk.Button(controls_frame, text="Add Agency", command=lambda: self.add_agency(agencies_tree)).pack(side='left', padx=5)
            ttk.Button(controls_frame, text="Edit Agency", command=lambda: self.edit_agency(agencies_tree)).pack(side='left', padx=5)
            ttk.Button(controls_frame, text="Remove Agency", command=lambda: self.remove_agency(agencies_tree)).pack(side='left', padx=5)
            ttk.Button(controls_frame, text="Refresh", command=lambda: self.load_agencies(agencies_tree)).pack(side='left', padx=5)
    
            # Agencies list
            list_frame = ttk.Frame(agencies_dialog)
            list_frame.pack(fill='both', expand=True, padx=10, pady=5)
    
            agencies_tree = ttk.Treeview(list_frame,
                                        columns=('ID', 'Name', 'Contact', 'Email', 'Phone', 'Commission', 'Status'),
                                        show='headings', height=20)
    
            agencies_tree.heading('ID', text='Agency ID')
            agencies_tree.heading('Name', text='Agency Name')
            agencies_tree.heading('Contact', text='Contact Person')
            agencies_tree.heading('Email', text='Email')
            agencies_tree.heading('Phone', text='Phone')
            agencies_tree.heading('Commission', text='Commission %')
            agencies_tree.heading('Status', text='Status')
    
            agencies_tree.column('ID', width=80)
            agencies_tree.column('Name', width=150)
            agencies_tree.column('Contact', width=120)
            agencies_tree.column('Email', width=150)
            agencies_tree.column('Phone', width=120)
            agencies_tree.column('Commission', width=100)
            agencies_tree.column('Status', width=80)
    
            # Scrollbar
            scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=agencies_tree.yview)
            agencies_tree.configure(yscrollcommand=scrollbar.set)
    
            agencies_tree.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')
    
            # Load initial data
            self.load_agencies(agencies_tree)
    
            # Close button
            ttk.Button(agencies_dialog, text="Close", command=agencies_dialog.destroy).pack(pady=10)
    

        def add_agency(self, tree):
            """Add new collection agency"""
            add_dialog = tk.Toplevel()
            add_dialog.title("Add Collection Agency")
            add_dialog.geometry("500x400")
            add_dialog.transient(tree.winfo_toplevel())
            add_dialog.grab_set()
    
            ttk.Label(add_dialog, text="Add New Collection Agency", font=('TkDefaultFont', 12, 'bold')).pack(pady=10)
    
            form_frame = ttk.Frame(add_dialog, padding=20)
            form_frame.pack(fill='both', expand=True)
    
            fields = {}
            labels = ['Agency Name', 'Contact Person', 'Email', 'Phone', 'Commission %']
            for i, label in enumerate(labels):
                ttk.Label(form_frame, text=f"{label}:").grid(row=i, column=0, sticky='w', pady=5, padx=5)
                fields[label] = ttk.Entry(form_frame, width=30)
                fields[label].grid(row=i, column=1, pady=5, padx=5)
    
            ttk.Label(form_frame, text="Status:").grid(row=len(labels), column=0, sticky='w', pady=5, padx=5)
            status_var = tk.StringVar(value="Active")
            status_combo = ttk.Combobox(form_frame, textvariable=status_var, values=['Active', 'Inactive'], width=28, state='readonly')
            status_combo.grid(row=len(labels), column=1, pady=5, padx=5)
    
            def save_agency():
                name = fields['Agency Name'].get().strip()
                if not name:
                    messagebox.showwarning("Name Required", "Please enter agency name", parent=add_dialog)
                    return
    
                try:
                    commission = float(fields['Commission %'].get() or '0')
                    if commission < 0 or commission > 100:
                        raise ValueError("Commission must be between 0 and 100")
                except ValueError as e:
                    messagebox.showwarning("Invalid Commission", str(e), parent=add_dialog)
                    return
    
                # Add to tree (in real implementation, save to database)
                agency_id = f"AG{len(tree.get_children()) + 1:03d}"
                tree.insert('', 'end', values=(
                    agency_id,
                    name,
                    fields['Contact Person'].get(),
                    fields['Email'].get(),
                    fields['Phone'].get(),
                    f"{commission}%",
                    status_var.get()
                ))
    
                messagebox.showinfo("Success", f"Agency '{name}' added successfully", parent=add_dialog)
                add_dialog.destroy()
    
            button_frame = ttk.Frame(add_dialog)
            button_frame.pack(pady=10)
            ttk.Button(button_frame, text="Save", command=save_agency).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Cancel", command=add_dialog.destroy).pack(side='left', padx=5)
    

        def edit_agency(self, tree):
            """Edit selected agency"""
            selection = tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select an agency to edit")
                return
    
            values = tree.item(selection[0], 'values')
            messagebox.showinfo("Edit Agency", f"Editing agency: {values[1]}\n\nFull edit functionality would update database records.")
    

        def remove_agency(self, tree):
            """Remove selected agency"""
            selection = tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select an agency to remove")
                return
    
            values = tree.item(selection[0], 'values')
            if messagebox.askyesno("Confirm Removal", f"Remove agency '{values[1]}'?\n\nThis action cannot be undone."):
                tree.delete(selection[0])
                messagebox.showinfo("Success", "Agency removed successfully")
    

        def load_agencies(self, tree):
            """Load agencies from database"""
            # Clear existing items
            for item in tree.get_children():
                tree.delete(item)
    
            # Sample data (in real implementation, load from database)
            sample_agencies = [
                ('AG001', 'Premier Collections Ltd', 'John Smith', 'j.smith@premier.com', '020 7123 4567', '15%', 'Active'),
                ('AG002', 'Swift Recovery Services', 'Jane Doe', 'jane@swiftrecovery.co.uk', '0161 234 5678', '12.5%', 'Active'),
                ('AG003', 'National Debt Solutions', 'Bob Johnson', 'b.johnson@nds.com', '0131 345 6789', '20%', 'Inactive'),
            ]
    
            for agency in sample_agencies:
                tree.insert('', 'end', values=agency)
        

        def track_collections(self):
            """Track collection progress"""
            try:
                old_stdout = sys.stdout
                sys.stdout = mystdout = io.StringIO()
                
                track_collection_progress()
                
                output = mystdout.getvalue()
                sys.stdout = old_stdout
                
                self.show_text_window("Collection Progress", output)
                
            except Exception as e:
                sys.stdout = old_stdout
                messagebox.showerror("Error", f"Failed to track collections: {str(e)}")
        
        # ==================== FINANCIAL AID METHODS ====================
        

        def refresh_collections(self):
            """Refresh collections data"""
            def refresh_thread():
                try:
                    conn = get_connection()
                    cursor = conn.cursor()
                    
                    # Get overdue accounts
                    cursor.execute('''
                    SELECT sf.student_id, s.first_name || ' ' || s.last_name as name,
                           SUM(sf.amount) - COALESCE(SUM(pa.amount), 0) as amount,
                           MAX(julianday('now') - julianday(sf.due_date)) as days_overdue
                    FROM student_fees sf
                    JOIN students s ON sf.student_id = s.student_id
                    LEFT JOIN payment_allocations pa ON sf.student_fee_id = pa.student_fee_id
                    WHERE sf.status IN ('unpaid', 'partial') AND date(sf.due_date) < date('now')
                    GROUP BY sf.student_id
                    HAVING (SUM(sf.amount) - COALESCE(SUM(pa.amount), 0)) > 0
                    ORDER BY days_overdue DESC
                    ''')
                    
                    overdue_accounts = cursor.fetchall()
                    
                    # Get collection cases
                    cursor.execute('''
                    SELECT cc.case_id, s.first_name || ' ' || s.last_name as student_name,
                           cc.case_status, COALESCE(ca.agency_name, 'Unassigned') as agency
                    FROM collection_cases cc
                    JOIN students s ON cc.student_id = s.student_id
                    LEFT JOIN collection_agencies ca ON cc.agency_id = ca.agency_id
                    WHERE cc.case_status NOT IN ('resolved', 'closed')
                    ORDER BY cc.created_at DESC
                    ''')
                    
                    collection_cases = cursor.fetchall()
                    conn.close()
                    
                    self.root.after(0, lambda: self.update_collections_data(overdue_accounts, collection_cases))
                    
                except Exception as e:
                    print(f"Error refreshing collections: {e}")
            
            refresh_thread()
        

        def update_collections_data(self, overdue_accounts, collection_cases):
            """Update collections data in UI"""
            # Update overdue accounts
            for item in self.overdue_tree.get_children():
                self.overdue_tree.delete(item)
            
            for account in overdue_accounts:
                student_id, name, amount, days_overdue = account
                display_data = (student_id, name, f"£{amount:.2f}", f"{int(days_overdue)}")
                self.overdue_tree.insert('', 'end', values=display_data)
            
            # Update collection cases
            for item in self.cases_tree.get_children():
                self.cases_tree.delete(item)
            
            for case in collection_cases:
                self.cases_tree.insert('', 'end', values=case)
        

        def gui_view_overdue_accounts(self):
            """GUI wrapper for view_overdue_accounts"""
            dialog = tk.Toplevel(self.root)
            dialog.title("Overdue Accounts")
            dialog.geometry("800x600")
            dialog.transient(self.root)
            dialog.grab_set()
            
            try:
                old_stdout = sys.stdout
                sys.stdout = mystdout = io.StringIO()
                
                view_overdue_accounts()
                
                output = mystdout.getvalue()
                sys.stdout = old_stdout
                
                text_widget = ScrolledText(dialog, height=25, width=90, font=('Courier', 10))
                text_widget.pack(fill='both', expand=True, padx=10, pady=10)
                text_widget.insert('1.0', output)
                
                ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=10)
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to view overdue accounts: {e}")
    

        def gui_create_collection_case(self):
            """GUI wrapper for create_collection_case"""
            dialog = tk.Toplevel(self.root)
            dialog.title("Create Collection Case")
            dialog.geometry("500x400")
            dialog.transient(self.root)
            dialog.grab_set()
            
            form_frame = ttk.LabelFrame(dialog, text="Collection Case Details", padding=20)
            form_frame.pack(fill='both', expand=True, padx=20, pady=20)
            
            # Student ID
            ttk.Label(form_frame, text="Student ID:").pack(anchor='w', pady=5)
            student_id_var = tk.StringVar()
            ttk.Entry(form_frame, textvariable=student_id_var).pack(anchor='w', fill='x', pady=5)
            
            # Case notes
            ttk.Label(form_frame, text="Case Notes:").pack(anchor='w', pady=5)
            notes_text = tk.Text(form_frame, height=6, width=50)
            notes_text.pack(anchor='w', fill='both', expand=True, pady=5)
            
            def create_case():
                try:
                    student_id = student_id_var.get().strip()
                    notes = notes_text.get("1.0", tk.END).strip()
                    
                    if not student_id:
                        messagebox.showerror("Error", "Student ID is required")
                        return
                    
                    create_collection_case(student_id, notes)
                    messagebox.showinfo("Success", "Collection case created successfully!")
                    dialog.destroy()
                    
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to create collection case: {e}")
            
            ttk.Button(form_frame, text="Create Case", command=create_case).pack(pady=20)
    

        def gui_manage_collection_agencies(self):
            """GUI wrapper for manage_collection_agencies"""
            dialog = tk.Toplevel(self.root)
            dialog.title("Manage Collection Agencies")
            dialog.geometry("800x600")
            dialog.transient(self.root)
            dialog.grab_set()
            
            try:
                old_stdout = sys.stdout
                sys.stdout = mystdout = io.StringIO()
                
                manage_collection_agencies()
                
                output = mystdout.getvalue()
                sys.stdout = old_stdout
                
                text_widget = ScrolledText(dialog, height=25, width=90, font=('Courier', 10))
                text_widget.pack(fill='both', expand=True, padx=10, pady=10)
                text_widget.insert('1.0', output)
                
                ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=10)
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to manage collection agencies: {e}")
    

        def gui_add_collection_agency(self):
            """GUI wrapper for add_collection_agency"""
            dialog = tk.Toplevel(self.root)
            dialog.title("Add Collection Agency")
            dialog.geometry("500x400")
            dialog.transient(self.root)
            dialog.grab_set()
            
            form_frame = ttk.LabelFrame(dialog, text="Agency Details", padding=20)
            form_frame.pack(fill='both', expand=True, padx=20, pady=20)
            
            # Agency name
            ttk.Label(form_frame, text="Agency Name:").pack(anchor='w', pady=5)
            name_var = tk.StringVar()
            ttk.Entry(form_frame, textvariable=name_var).pack(anchor='w', fill='x', pady=5)
            
            # Contact email
            ttk.Label(form_frame, text="Contact Email:").pack(anchor='w', pady=5)
            email_var = tk.StringVar()
            ttk.Entry(form_frame, textvariable=email_var).pack(anchor='w', fill='x', pady=5)
            
            # Phone
            ttk.Label(form_frame, text="Phone:").pack(anchor='w', pady=5)
            phone_var = tk.StringVar()
            ttk.Entry(form_frame, textvariable=phone_var).pack(anchor='w', fill='x', pady=5)
            
            # Commission rate
            ttk.Label(form_frame, text="Commission Rate (%):").pack(anchor='w', pady=5)
            commission_var = tk.StringVar()
            ttk.Entry(form_frame, textvariable=commission_var).pack(anchor='w', fill='x', pady=5)
            
            def add_agency():
                try:
                    name = name_var.get().strip()
                    email = email_var.get().strip()
                    phone = phone_var.get().strip()
                    commission = float(commission_var.get())
                    
                    if not all([name, email, phone, commission >= 0]):
                        messagebox.showerror("Error", "All fields are required")
                        return
                    
                    add_collection_agency(name, email, phone, commission)
                    messagebox.showinfo("Success", "Collection agency added successfully!")
                    dialog.destroy()
                    
                except ValueError:
                    messagebox.showerror("Error", "Invalid commission rate")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to add collection agency: {e}")
            
            ttk.Button(form_frame, text="Add Agency", command=add_agency).pack(pady=20)
    

        def gui_edit_collection_agency(self):
            """GUI wrapper for edit_collection_agency"""
            dialog = tk.Toplevel(self.root)
            dialog.title("Edit Collection Agency")
            dialog.geometry("500x400")
            dialog.transient(self.root)
            dialog.grab_set()
            
            form_frame = ttk.LabelFrame(dialog, text="Edit Agency", padding=20)
            form_frame.pack(fill='both', expand=True, padx=20, pady=20)
            
            # Agency ID
            ttk.Label(form_frame, text="Agency ID:").pack(anchor='w', pady=5)
            agency_id_var = tk.StringVar()
            ttk.Entry(form_frame, textvariable=agency_id_var).pack(anchor='w', fill='x', pady=5)
            
            # New name
            ttk.Label(form_frame, text="New Name:").pack(anchor='w', pady=5)
            name_var = tk.StringVar()
            ttk.Entry(form_frame, textvariable=name_var).pack(anchor='w', fill='x', pady=5)
            
            # New email
            ttk.Label(form_frame, text="New Email:").pack(anchor='w', pady=5)
            email_var = tk.StringVar()
            ttk.Entry(form_frame, textvariable=email_var).pack(anchor='w', fill='x', pady=5)
            
            # New commission rate
            ttk.Label(form_frame, text="New Commission Rate (%):").pack(anchor='w', pady=5)
            commission_var = tk.StringVar()
            ttk.Entry(form_frame, textvariable=commission_var).pack(anchor='w', fill='x', pady=5)
            
            def edit_agency():
                try:
                    agency_id = int(agency_id_var.get())
                    new_name = name_var.get().strip()
                    new_email = email_var.get().strip()
                    new_commission = float(commission_var.get()) if commission_var.get().strip() else None
                    
                    if not agency_id:
                        messagebox.showerror("Error", "Agency ID is required")
                        return
                    
                    edit_collection_agency(agency_id, new_name, new_email, new_commission)
                    messagebox.showinfo("Success", "Collection agency updated successfully!")
                    dialog.destroy()
                    
                except ValueError:
                    messagebox.showerror("Error", "Invalid Agency ID or commission rate")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to edit collection agency: {e}")
            
            ttk.Button(form_frame, text="Update Agency", command=edit_agency).pack(pady=20)
    

        def gui_deactivate_collection_agency(self):
            """GUI wrapper for deactivate_collection_agency"""
            dialog = tk.Toplevel(self.root)
            dialog.title("Deactivate Collection Agency")
            dialog.geometry("400x200")
            dialog.transient(self.root)
            dialog.grab_set()
            
            form_frame = ttk.LabelFrame(dialog, text="Deactivate Agency", padding=20)
            form_frame.pack(fill='both', expand=True, padx=20, pady=20)
            
            # Agency ID
            ttk.Label(form_frame, text="Agency ID to Deactivate:").pack(anchor='w', pady=5)
            agency_id_var = tk.StringVar()
            ttk.Entry(form_frame, textvariable=agency_id_var).pack(anchor='w', fill='x', pady=5)
            
            def deactivate_agency():
                try:
                    agency_id = int(agency_id_var.get())
                    
                    if messagebox.askyesno("Confirm", f"Deactivate collection agency {agency_id}?"):
                        deactivate_collection_agency(agency_id)
                        messagebox.showinfo("Success", "Collection agency deactivated successfully!")
                        dialog.destroy()
                    
                except ValueError:
                    messagebox.showerror("Error", "Invalid Agency ID")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to deactivate collection agency: {e}")
            
            ttk.Button(form_frame, text="Deactivate", command=deactivate_agency).pack(pady=20)
    

        def gui_view_collection_agencies(self):
            """GUI wrapper for view_collection_agencies"""
            dialog = tk.Toplevel(self.root)
            dialog.title("View Collection Agencies")
            dialog.geometry("700x500")
            dialog.transient(self.root)
            dialog.grab_set()
            
            try:
                old_stdout = sys.stdout
                sys.stdout = mystdout = io.StringIO()
                
                view_collection_agencies()
                
                output = mystdout.getvalue()
                sys.stdout = old_stdout
                
                text_widget = ScrolledText(dialog, height=25, width=80, font=('Courier', 10))
                text_widget.pack(fill='both', expand=True, padx=10, pady=10)
                text_widget.insert('1.0', output)
                
                ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=10)
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to view collection agencies: {e}")
    

        def gui_assign_to_collection_agency(self):
            """GUI wrapper for assign_to_collection_agency"""
            dialog = tk.Toplevel(self.root)
            dialog.title("Assign to Collection Agency")
            dialog.geometry("500x300")
            dialog.transient(self.root)
            dialog.grab_set()
            
            form_frame = ttk.LabelFrame(dialog, text="Assignment Details", padding=20)
            form_frame.pack(fill='both', expand=True, padx=20, pady=20)
            
            # Case ID
            ttk.Label(form_frame, text="Collection Case ID:").pack(anchor='w', pady=5)
            case_id_var = tk.StringVar()
            ttk.Entry(form_frame, textvariable=case_id_var).pack(anchor='w', fill='x', pady=5)
            
            # Agency ID
            ttk.Label(form_frame, text="Agency ID:").pack(anchor='w', pady=5)
            agency_id_var = tk.StringVar()
            ttk.Entry(form_frame, textvariable=agency_id_var).pack(anchor='w', fill='x', pady=5)
            
            def assign_case():
                try:
                    case_id = int(case_id_var.get())
                    agency_id = int(agency_id_var.get())
                    
                    assign_to_collection_agency(case_id, agency_id)
                    messagebox.showinfo("Success", "Case assigned to collection agency successfully!")
                    dialog.destroy()
                    
                except ValueError:
                    messagebox.showerror("Error", "Invalid case ID or agency ID")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to assign case: {e}")
            
            ttk.Button(form_frame, text="Assign Case", command=assign_case).pack(pady=20)
    

        def gui_track_collection_progress(self):
            """GUI wrapper for track_collection_progress"""
            try:
                old_stdout = sys.stdout
                sys.stdout = mystdout = io.StringIO()
                
                track_collection_progress()
                
                output = mystdout.getvalue()
                sys.stdout = old_stdout
                
                self.show_text_window("Collection Progress Tracking", output)
                self.update_status("Collection progress tracking completed")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to track collection progress: {e}")
    

        def gui_update_collection_case_status(self):
            """GUI wrapper for update_collection_case_status"""
            dialog = tk.Toplevel(self.root)
            dialog.title("Update Collection Case Status")
            dialog.geometry("500x350")
            dialog.transient(self.root)
            dialog.grab_set()
            
            form_frame = ttk.LabelFrame(dialog, text="Status Update", padding=20)
            form_frame.pack(fill='both', expand=True, padx=20, pady=20)
            
            # Case ID
            ttk.Label(form_frame, text="Case ID:").pack(anchor='w', pady=5)
            case_id_var = tk.StringVar()
            ttk.Entry(form_frame, textvariable=case_id_var).pack(anchor='w', fill='x', pady=5)
            
            # New status
            ttk.Label(form_frame, text="New Status:").pack(anchor='w', pady=5)
            status_var = tk.StringVar()
            status_combo = ttk.Combobox(form_frame, textvariable=status_var,
                                       values=["active", "resolved", "closed", "transferred"])
            status_combo.pack(anchor='w', fill='x', pady=5)
            
            # Notes
            ttk.Label(form_frame, text="Update Notes:").pack(anchor='w', pady=5)
            notes_text = tk.Text(form_frame, height=4, width=50)
            notes_text.pack(anchor='w', fill='both', expand=True, pady=5)
            
            def update_status():
                try:
                    case_id = int(case_id_var.get())
                    new_status = status_var.get()
                    notes = notes_text.get("1.0", tk.END).strip()
                    
                    if not all([case_id, new_status]):
                        messagebox.showerror("Error", "Case ID and status are required")
                        return
                    
                    update_collection_case_status(case_id, new_status, notes)
                    messagebox.showinfo("Success", "Collection case status updated successfully!")
                    dialog.destroy()
                    
                except ValueError:
                    messagebox.showerror("Error", "Invalid case ID")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to update case status: {e}")
            
            ttk.Button(form_frame, text="Update Status", command=update_status).pack(pady=20)
    

        def gui_create_payment_arrangement(self):
            """GUI wrapper for create_payment_arrangement"""
            dialog = tk.Toplevel(self.root)
            dialog.title("Create Payment Arrangement")
            dialog.geometry("600x500")
            dialog.transient(self.root)
            dialog.grab_set()
            
            form_frame = ttk.LabelFrame(dialog, text="Payment Arrangement", padding=20)
    
            form_frame.pack(fill='both', expand=True, padx=20, pady=20)
            
            # Student ID
            ttk.Label(form_frame, text="Student ID:").pack(anchor='w', pady=5)
            student_id_var = tk.StringVar()
            ttk.Entry(form_frame, textvariable=student_id_var).pack(anchor='w', fill='x', pady=5)
            
            # Total amount
            ttk.Label(form_frame, text="Total Amount:").pack(anchor='w', pady=5)
            total_amount_var = tk.StringVar()
            ttk.Entry(form_frame, textvariable=total_amount_var).pack(anchor='w', fill='x', pady=5)
            
            # Monthly payment
            ttk.Label(form_frame, text="Monthly Payment:").pack(anchor='w', pady=5)
            monthly_payment_var = tk.StringVar()
            ttk.Entry(form_frame, textvariable=monthly_payment_var).pack(anchor='w', fill='x', pady=5)
            
            # Start date
            ttk.Label(form_frame, text="Start Date (YYYY-MM-DD):").pack(anchor='w', pady=5)
            start_date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
            ttk.Entry(form_frame, textvariable=start_date_var).pack(anchor='w', fill='x', pady=5)
            
            # Terms
            ttk.Label(form_frame, text="Terms and Conditions:").pack(anchor='w', pady=5)
            terms_text = tk.Text(form_frame, height=4, width=50)
            terms_text.pack(anchor='w', fill='both', expand=True, pady=5)
            
            def create_arrangement():
                try:
                    student_id = student_id_var.get().strip()
                    total_amount = float(total_amount_var.get())
                    monthly_payment = float(monthly_payment_var.get())
                    start_date = start_date_var.get().strip()
                    terms = terms_text.get("1.0", tk.END).strip()
                    
                    if not all([student_id, total_amount > 0, monthly_payment > 0, start_date]):
                        messagebox.showerror("Error", "All required fields must be filled")
                        return
                    
                    create_payment_arrangement(student_id, total_amount, monthly_payment, start_date, terms)
                    messagebox.showinfo("Success", "Payment arrangement created successfully!")
                    dialog.destroy()
                    
                except ValueError:
                    messagebox.showerror("Error", "Invalid amount values")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to create payment arrangement: {e}")
            
            ttk.Button(form_frame, text="Create Arrangement", command=create_arrangement).pack(pady=20)
    

        def gui_send_arrangement_confirmation(self):
            """GUI wrapper for send_arrangement_confirmation"""
            dialog = tk.Toplevel(self.root)
            dialog.title("Send Arrangement Confirmation")
            dialog.geometry("400x200")
            dialog.transient(self.root)
            dialog.grab_set()
            
            form_frame = ttk.LabelFrame(dialog, text="Send Confirmation", padding=20)
            form_frame.pack(fill='both', expand=True, padx=20, pady=20)
            
            # Arrangement ID
            ttk.Label(form_frame, text="Arrangement ID:").pack(anchor='w', pady=5)
            arrangement_id_var = tk.StringVar()
            ttk.Entry(form_frame, textvariable=arrangement_id_var).pack(anchor='w', fill='x', pady=5)
            
            def send_confirmation():
                try:
                    arrangement_id = int(arrangement_id_var.get())
                    
                    send_arrangement_confirmation(arrangement_id)
                    messagebox.showinfo("Success", "Arrangement confirmation sent successfully!")
                    dialog.destroy()
                    
                except ValueError:
                    messagebox.showerror("Error", "Invalid arrangement ID")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to send confirmation: {e}")
            
            ttk.Button(form_frame, text="Send Confirmation", command=send_confirmation).pack(pady=20)
    

        def gui_setup_collection_workflows(self):
            """GUI wrapper for setup_collection_workflows"""
            if messagebox.askyesno("Confirm", "Set up automated collection workflows?"):
                try:
                    setup_collection_workflows()
                    messagebox.showinfo("Success", "Collection workflows set up successfully!")
                    self.update_status("Collection workflows configured")
                    
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to setup collection workflows: {e}")
    

        def gui_send_collection_notice(self):
            """GUI wrapper for send_collection_notice"""
            dialog = tk.Toplevel(self.root)
            dialog.title("Send Collection Notice")
            dialog.geometry("500x400")
            dialog.transient(self.root)
            dialog.grab_set()
            
            form_frame = ttk.LabelFrame(dialog, text="Collection Notice", padding=20)
            form_frame.pack(fill='both', expand=True, padx=20, pady=20)
            
            # Student ID
            ttk.Label(form_frame, text="Student ID:").pack(anchor='w', pady=5)
            student_id_var = tk.StringVar()
            ttk.Entry(form_frame, textvariable=student_id_var).pack(anchor='w', fill='x', pady=5)
            
            # Notice type
            ttk.Label(form_frame, text="Notice Type:").pack(anchor='w', pady=5)
            notice_type_var = tk.StringVar(value="first_notice")
            notice_combo = ttk.Combobox(form_frame, textvariable=notice_type_var,
                                       values=["first_notice", "second_notice", "final_notice"])
            notice_combo.pack(anchor='w', fill='x', pady=5)
            
            # Custom message
            ttk.Label(form_frame, text="Custom Message:").pack(anchor='w', pady=5)
            message_text = tk.Text(form_frame, height=6, width=50)
            message_text.pack(anchor='w', fill='both', expand=True, pady=5)
            
            def send_notice():
                try:
                    student_id = student_id_var.get().strip()
                    notice_type = notice_type_var.get()
                    custom_message = message_text.get("1.0", tk.END).strip()
                    
                    if not student_id:
                        messagebox.showerror("Error", "Student ID is required")
                        return
                    
                    send_collection_notice(student_id, notice_type, custom_message)
                    messagebox.showinfo("Success", "Collection notice sent successfully!")
                    dialog.destroy()
                    
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to send collection notice: {e}")
            
            ttk.Button(form_frame, text="Send Notice", command=send_notice).pack(pady=20)
    

        def gui_recovery_rate_analysis(self):
            """GUI wrapper for recovery_rate_analysis"""
            try:
                old_stdout = sys.stdout
                sys.stdout = mystdout = io.StringIO()
                
                recovery_rate_analysis()
                
                output = mystdout.getvalue()
                sys.stdout = old_stdout
                
                self.show_tab('reports')  # Reports tab
                self.report_text.delete('1.0', tk.END)
                self.report_text.insert('1.0', output)
                self.update_status("Recovery rate analysis generated")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to generate recovery rate analysis: {e}")
    

        def gui_agency_performance_report(self):
            """GUI wrapper for agency_performance_report"""
            try:
                old_stdout = sys.stdout
                sys.stdout = mystdout = io.StringIO()
                
                agency_performance_report()
                
                output = mystdout.getvalue()
                sys.stdout = old_stdout
                
                self.show_tab('reports')  # Reports tab
                self.report_text.delete('1.0', tk.END)
                self.report_text.insert('1.0', output)
                self.update_status("Agency performance report generated")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to generate agency performance report: {e}")
    

        def gui_collection_performance_summary(self):
            """GUI wrapper for collection_performance_summary"""
            try:
                old_stdout = sys.stdout
                sys.stdout = mystdout = io.StringIO()
                
                collection_performance_summary()
                
                output = mystdout.getvalue()
                sys.stdout = old_stdout
                
                self.show_tab('reports')  # Reports tab
                self.report_text.delete('1.0', tk.END)
                self.report_text.insert('1.0', output)
                self.update_status("Collection performance summary generated")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to generate collection performance summary: {e}")
    
        # Add these to handle missing core functions that might not have been implemented

        def gui_aging_analysis_report(self):
            """GUI wrapper for aging_analysis_report"""
            try:
                old_stdout = sys.stdout
                sys.stdout = mystdout = io.StringIO()
                
                aging_analysis_report()
                
                output = mystdout.getvalue()
                sys.stdout = old_stdout
                
                self.show_tab('reports')  # Reports tab
                self.report_text.delete('1.0', tk.END)
                self.report_text.insert('1.0', output)
                self.update_status("Aging analysis report generated")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to generate aging analysis: {e}")
    

        def gui_collection_case_status_report(self):
            """GUI wrapper for collection_case_status_report"""
            try:
                old_stdout = sys.stdout
                sys.stdout = mystdout = io.StringIO()
                
                collection_case_status_report()
                
                output = mystdout.getvalue()
                sys.stdout = old_stdout
                
                self.show_tab('reports')  # Reports tab
                self.report_text.delete('1.0', tk.END)
                self.report_text.insert('1.0', output)
                self.update_status("Collection case status report generated")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to generate collection case status report: {e}")
    

        def gui_view_student_collection_detail(self):
            """GUI wrapper for view_student_collection_detail"""
            dialog = tk.Toplevel(self.root)
            dialog.title("Student Collection Details")
            dialog.geometry("700x500")
            dialog.transient(self.root)
            dialog.grab_set()
            
            # Student ID input
            input_frame = ttk.Frame(dialog, padding=10)
            input_frame.pack(fill='x')
            
            ttk.Label(input_frame, text="Student ID:").pack(side='left', padx=5)
            student_id_var = tk.StringVar()
            ttk.Entry(input_frame, textvariable=student_id_var, width=15).pack(side='left', padx=5)
            
            def show_details():
                student_id = student_id_var.get().strip()
                if not student_id:
                    messagebox.showerror("Error", "Student ID is required")
                    return
                
                try:
                    old_stdout = sys.stdout
                    sys.stdout = mystdout = io.StringIO()
                    
                    view_student_collection_detail(student_id)
                    
                    output = mystdout.getvalue()
                    sys.stdout = old_stdout
                    
                    details_text.delete('1.0', tk.END)
                    details_text.insert('1.0', output)
                    
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to view collection details: {e}")
            
            ttk.Button(input_frame, text="View Details", command=show_details).pack(side='left', padx=10)
            
            # Details display
            details_text = ScrolledText(dialog, height=20, width=80, font=('Courier', 10))
            details_text.pack(fill='both', expand=True, padx=10, pady=10)
    

        def gui_manage_collections(self):
            """Switch to collections tab"""
            # Switch to collections tab
            self.show_tab('collections')
        

        def gui_view_audit_logs(self):
            """GUI for viewing audit logs"""
            dialog = tk.Toplevel(self.root)
            dialog.title("Audit Logs")
            dialog.geometry("1000x600")
            dialog.transient(self.root)
            dialog.grab_set()
            
            # Date range selection
            filter_frame = ttk.LabelFrame(dialog, text="Filter Options", padding=15)
            filter_frame.pack(fill='x', padx=20, pady=10)
            
            ttk.Label(filter_frame, text="Start Date:").grid(row=0, column=0, padx=5, pady=5, sticky='e')
            start_date_var = tk.StringVar(value=(datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
            ttk.Entry(filter_frame, textvariable=start_date_var, width=12).grid(row=0, column=1, padx=5, pady=5)
            
            ttk.Label(filter_frame, text="End Date:").grid(row=0, column=2, padx=5, pady=5, sticky='e')
            end_date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
            ttk.Entry(filter_frame, textvariable=end_date_var, width=12).grid(row=0, column=3, padx=5, pady=5)
            
            def load_audit_logs():
                try:
                    conn = get_connection()
                    cursor = conn.cursor()
                    
                    cursor.execute('''
                    SELECT user_id, action, table_name, record_id, new_values, timestamp
                    FROM audit_log
                    WHERE date(timestamp) BETWEEN ? AND ?
                    ORDER BY timestamp DESC
                    LIMIT 1000
                    ''', (start_date_var.get(), end_date_var.get()))
                    
                    logs = cursor.fetchall()
                    
                    # Clear existing items
                    for item in audit_tree.get_children():
                        audit_tree.delete(item)
                    
                    # Add log data
                    for log in logs:
                        user_id, action, table_name, record_id, details, timestamp = log
                        details_summary = str(details)[:50] + "..." if len(str(details)) > 50 else str(details)
                        
                        audit_tree.insert('', 'end', values=(
                            timestamp, user_id, action, table_name, record_id, details_summary
                        ))
                    
                    status_label.config(text=f"Loaded {len(logs)} audit entries")
                    conn.close()
                    
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to load audit logs: {e}")
            
            ttk.Button(filter_frame, text="Load Logs", command=load_audit_logs).grid(row=0, column=4, padx=10, pady=5)
            
            # Audit logs display
            logs_frame = ttk.LabelFrame(dialog, text="Audit Log Entries", padding=15)
            logs_frame.pack(fill='both', expand=True, padx=20, pady=10)
            
            columns = ('Timestamp', 'User', 'Action', 'Table', 'Record ID', 'Details')
            audit_tree = ttk.Treeview(logs_frame, columns=columns, show='headings', height=15)
            
            for col in columns:
                audit_tree.heading(col, text=col)
                width = 200 if col == 'Details' else 120 if col == 'Timestamp' else 100
                audit_tree.column(col, width=width, anchor='center')
            
            # Scrollbars
            audit_v_scroll = ttk.Scrollbar(logs_frame, orient='vertical', command=audit_tree.yview)
            audit_h_scroll = ttk.Scrollbar(logs_frame, orient='horizontal', command=audit_tree.xview)
            audit_tree.configure(yscrollcommand=audit_v_scroll.set, xscrollcommand=audit_h_scroll.set)
            
            audit_tree.pack(side='left', fill='both', expand=True)
            audit_v_scroll.pack(side='right', fill='y')
            audit_h_scroll.pack(side='bottom', fill='x')
            
            # Status
            status_label = ttk.Label(dialog, text="Click 'Load Logs' to view audit entries")
            status_label.pack(pady=10)
            
            # Load initial data
            load_audit_logs()
        

        def gui_check_required_packages(self):
            """GUI wrapper for check_required_packages"""
            try:
                old_stdout = sys.stdout
                sys.stdout = mystdout = io.StringIO()
                
                check_required_packages()
                
                output = mystdout.getvalue()
                sys.stdout = old_stdout
                
                self.show_text_window("Package Requirements Check", output)
                self.update_status("Package requirements checked")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to check required packages: {e}")
    

        def gui_create_approval_workflow(self):
            """GUI wrapper for create_approval_workflow"""
            dialog = tk.Toplevel(self.root)
            dialog.title("Create Approval Workflow")
            dialog.geometry("500x400")
            dialog.transient(self.root)
            dialog.grab_set()
            
            form_frame = ttk.LabelFrame(dialog, text="Workflow Details", padding=20)
            form_frame.pack(fill='both', expand=True, padx=20, pady=20)
            
            # Workflow type
            ttk.Label(form_frame, text="Workflow Type:").pack(anchor='w', pady=5)
            type_var = tk.StringVar()
            type_combo = ttk.Combobox(form_frame, textvariable=type_var,
                                     values=["payment", "refund", "budget", "aid_application"])
            type_combo.pack(anchor='w', fill='x', pady=5)
            
            # Entity ID
            ttk.Label(form_frame, text="Entity ID:").pack(anchor='w', pady=5)
            entity_id_var = tk.StringVar()
            ttk.Entry(form_frame, textvariable=entity_id_var).pack(anchor='w', fill='x', pady=5)
            
            # Notes
            ttk.Label(form_frame, text="Notes:").pack(anchor='w', pady=5)
            notes_text = tk.Text(form_frame, height=4, width=50)
            notes_text.pack(anchor='w', fill='both', expand=True, pady=5)
            
            def create_workflow():
                try:
                    workflow_type = type_var.get().strip()
                    entity_id = entity_id_var.get().strip()
                    notes = notes_text.get("1.0", tk.END).strip()
                    
                    if not all([workflow_type, entity_id]):
                        messagebox.showerror("Error", "Workflow type and entity ID are required")
                        return
                    
                    create_approval_workflow(workflow_type, entity_id, notes)
                    messagebox.showinfo("Success", "Approval workflow created successfully!")
                    dialog.destroy()
                    
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to create approval workflow: {e}")
            
            ttk.Button(form_frame, text="Create Workflow", command=create_workflow).pack(pady=20)
    
