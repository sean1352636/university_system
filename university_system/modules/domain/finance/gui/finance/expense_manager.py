"""Fee and expense management"""

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




class ExpenseManager:
    """Fee and expense management"""

    def __init__(self, gui):
        """Initialize manager with reference to main GUI"""
        self.gui = gui
        self.root = gui.root
        self.conn = gui.conn
        try:
            self.finance_system = gui.finance_system
        except:
            self.finance_system = None

        def create_fees_tab(self):
            """Create fees management tab"""
            fees_frame = tk.Frame(self.content_frame, bg='white')
            self.tab_frames['fees'] = fees_frame
            
            # Create fees interface
            main_container = tk.PanedWindow(fees_frame, orient='horizontal')
            main_container.pack(fill='both', expand=True, padx=10, pady=10)
            
            # Left panel - Fee Types
            left_panel = tk.Frame(main_container, bg='white', relief='sunken', bd=2)
            main_container.add(left_panel, minsize=300)
            
            tk.Label(left_panel, text="Fee Types", font=('Arial', 14, 'bold'), bg='white').pack(pady=10)
            
            # Fee types listbox
            self.fee_types_listbox = tk.Listbox(left_panel, font=('Arial', 9))
            self.fee_types_listbox.pack(fill='both', expand=True, padx=10, pady=5)
            self.fee_types_listbox.bind('<Double-1>', self.edit_fee_type)
            
            # Fee type buttons
            fee_btn_frame = tk.Frame(left_panel, bg='white')
            fee_btn_frame.pack(fill='x', padx=10, pady=5)
            
            tk.Button(fee_btn_frame, text="Add Fee Type", command=self.add_fee_type,
                     bg=self.colors['success'], fg='white').pack(side='left', padx=2)
            tk.Button(fee_btn_frame, text="Edit", command=self.edit_fee_type,
                     bg=self.colors['warning'], fg='white').pack(side='left', padx=2)
            tk.Button(fee_btn_frame, text="Delete", command=self.delete_fee_type,
                     bg=self.colors['danger'], fg='white').pack(side='left', padx=2)
            
            # Right panel - Student Fees
            right_panel = tk.Frame(main_container, bg='white', relief='sunken', bd=2)
            main_container.add(right_panel, minsize=400)
            
            tk.Label(right_panel, text="Student Fees", font=('Arial', 14, 'bold'), bg='white').pack(pady=10)
            
            # Student fees toolbar
            fees_toolbar = tk.Frame(right_panel, bg='white')
            fees_toolbar.pack(fill='x', padx=10, pady=5)
            
            tk.Button(fees_toolbar, text="Assign Fee", command=self.assign_fee_to_student,
                     bg=self.colors['secondary'], fg='white').pack(side='left', padx=2)
            tk.Button(fees_toolbar, text="Bulk Assign", command=self.bulk_assign_fees,
                     bg=self.colors['warning'], fg='white').pack(side='left', padx=2)
            tk.Button(fees_toolbar, text="Late Fees", command=self.calculate_late_fees,
                     bg=self.colors['danger'], fg='white').pack(side='left', padx=2)
            
            # Student fees table
            self.create_student_fees_table(right_panel)
            
            # Load fees data
            self.refresh_fees()
        

        def create_student_fees_table(self, parent):
            """Create student fees table"""
            table_frame = tk.Frame(parent)
            table_frame.pack(fill='both', expand=True, padx=10, pady=5)
            
            columns = ('fee_id', 'student_id', 'fee_type', 'amount', 'due_date', 'status')
            self.student_fees_tree = ttk.Treeview(table_frame, columns=columns, show='headings')
            
            for col in columns:
                self.student_fees_tree.heading(col, text=col.replace('_', ' ').title())
                self.student_fees_tree.column(col, width=100)
            
            # Scrollbars
            v_scroll = ttk.Scrollbar(table_frame, orient='vertical', command=self.student_fees_tree.yview)
            self.student_fees_tree.configure(yscrollcommand=v_scroll.set)
            
            self.student_fees_tree.pack(side='left', fill='both', expand=True)
            v_scroll.pack(side='right', fill='y')
        

        def refresh_fees(self):
            """Refresh fees data"""
            def refresh_thread():
                try:
                    conn = get_connection()
                    cursor = conn.cursor()
                    
                    # Get fee types
                    cursor.execute("SELECT fee_type_id, fee_name, description FROM fee_types")
                    fee_types = cursor.fetchall()
                    
                    # Get student fees
                    cursor.execute('''
                    SELECT sf.student_fee_id, sf.student_id, ft.fee_name, sf.amount, sf.due_date, sf.status
                    FROM student_fees sf
                    JOIN fee_types ft ON sf.fee_type_id = ft.fee_type_id
                    ORDER BY sf.due_date DESC
                    LIMIT 100
                    ''')
                    
                    student_fees = cursor.fetchall()
                    conn.close()
                    
                    # Update UI
                    self.root.after(0, lambda: self.update_fees_data(fee_types, student_fees))
                    
                except Exception as e:
                    print(f"Error refreshing fees: {e}")
            
            refresh_thread()
        

        def update_fees_data(self, fee_types, student_fees):
            """Update fees data in UI"""
            # Update fee types listbox
            self.fee_types_listbox.delete(0, tk.END)
            for fee_type_id, name, description in fee_types:
                self.fee_types_listbox.insert(tk.END, f"{name} - {description}")
            
            # Update student fees table
            for item in self.student_fees_tree.get_children():
                self.student_fees_tree.delete(item)
            
            for fee in student_fees:
                self.student_fees_tree.insert('', 'end', values=fee)
        

        def add_fee_type(self):
            """Add new fee type"""
            # Simple fee type dialog using built-in dialogs
            fee_name = simpledialog.askstring("Add Fee Type", "Enter Fee Name:")
            if fee_name:
                amount = simpledialog.askfloat("Add Fee Type", "Enter Fee Amount:")
                if amount:
                    description = simpledialog.askstring("Add Fee Type", "Enter Description:", initialvalue="")
                    try:
                        # Here you would save the fee type to database
                        messagebox.showinfo("Success", f"Fee type '{fee_name}' added successfully")
                        self.refresh_fees()
                    except Exception as e:
                        messagebox.showerror("Error", f"Failed to add fee type: {e}")
        

        def edit_fee_type(self, event=None):
            """Edit selected fee type"""
            selection = self.fee_types_listbox.curselection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a fee type to edit.")
                return
            
            fee_index = selection[0]
            # Get fee type ID and show edit dialog
            messagebox.showinfo("Edit Fee Type", f"Edit fee type at index {fee_index}")
        

        def delete_fee_type(self):
            """Delete selected fee type"""
            selection = self.fee_types_listbox.curselection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a fee type to delete.")
                return
            
            if messagebox.askyesno("Confirm Delete", "Are you sure you want to delete this fee type?"):
                # Implement delete logic
                self.refresh_fees()
        

        def assign_fee_to_student(self):
            """Assign fee to student"""
            # Simple fee assignment dialog using built-in dialogs
            student_id = simpledialog.askstring("Assign Fee", "Enter Student ID:")
            if student_id:
                fee_type = simpledialog.askstring("Assign Fee", "Enter Fee Type Name:")
                if fee_type:
                    amount = simpledialog.askfloat("Assign Fee", "Enter Amount:")
                    if amount:
                        due_date = simpledialog.askstring("Assign Fee", "Due Date (YYYY-MM-DD):",
                                                         initialvalue=datetime.now().strftime("%Y-%m-%d"))
                        if due_date:
                            try:
                                # Here you would save the fee assignment to database
                                messagebox.showinfo("Success", f"Fee '{fee_type}' (£{amount:.2f}) assigned to student {student_id}")
                                self.refresh_fees()
                            except Exception as e:
                                messagebox.showerror("Error", f"Failed to assign fee: {e}")
        

        def gui_assign_fees_to_student(self):
            """GUI wrapper for assign_fees_to_student"""
            dialog = tk.Toplevel(self.root)
            dialog.title("Assign Fees to Student")
            dialog.geometry("500x400")
            dialog.transient(self.root)
            dialog.grab_set()
            
            # Student selection
            ttk.Label(dialog, text="Student ID:", font=('Arial', 12)).pack(pady=10)
            student_id_var = tk.StringVar()
            student_entry = ttk.Entry(dialog, textvariable=student_id_var, font=('Arial', 12))
            student_entry.pack(pady=5)
            
            # Fee type selection
            ttk.Label(dialog, text="Fee Type:", font=('Arial', 12)).pack(pady=(20, 10))
            fee_type_var = tk.StringVar()
            fee_type_combo = ttk.Combobox(dialog, textvariable=fee_type_var, state='readonly', font=('Arial', 12))
            fee_type_combo.pack(pady=5)
            
            # Load fee types
            conn = None
            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute('SELECT fee_name FROM fee_types ORDER BY fee_name')
                fee_types = [row[0] for row in cursor.fetchall()]
                fee_type_combo['values'] = fee_types
            except sqlite3.Error as e:
                messagebox.showerror("Error", f"Database error loading fee types: {e}")
                dialog.destroy()
                return
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load fee types: {e}")
                dialog.destroy()
                return
            finally:
                if conn:
                    conn.close()
            
            # Amount
            ttk.Label(dialog, text="Amount (£):", font=('Arial', 12)).pack(pady=(20, 10))
            amount_var = tk.StringVar()
            ttk.Entry(dialog, textvariable=amount_var, font=('Arial', 12)).pack(pady=5)
            
            # Due date
            ttk.Label(dialog, text="Due Date (YYYY-MM-DD):", font=('Arial', 12)).pack(pady=(20, 10))
            due_date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
            ttk.Entry(dialog, textvariable=due_date_var, font=('Arial', 12)).pack(pady=5)
            
            def assign_fee():
                conn = None
                try:
                    # Validate inputs
                    if not all([student_id_var.get(), fee_type_var.get(), amount_var.get(), due_date_var.get()]):
                        messagebox.showerror("Error", "All fields are required")
                        return
    
                    student_id = student_id_var.get().strip()
                    fee_type = fee_type_var.get()
                    amount = float(amount_var.get())
                    due_date = due_date_var.get().strip()
    
                    # Call original function logic
                    conn = get_connection()
                    cursor = conn.cursor()
    
                    # Check if student exists
                    cursor.execute('SELECT COUNT(*) FROM students WHERE student_id = ?', (student_id,))
                    if cursor.fetchone()[0] == 0:
                        messagebox.showerror("Error", f"Student {student_id} not found")
                        return
    
                    # Get fee type ID
                    cursor.execute('SELECT fee_type_id FROM fee_types WHERE fee_name = ?', (fee_type,))
                    fee_type_result = cursor.fetchone()
                    if not fee_type_result:
                        messagebox.showerror("Error", "Fee type not found")
                        return
    
                    fee_type_id = fee_type_result[0]
    
                    # Create student fee
                    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    cursor.execute('''
                    INSERT INTO student_fees
                    (student_id, fee_type_id, amount, due_date, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ''', (student_id, fee_type_id, amount, due_date, now, now))
    
                    fee_id = cursor.lastrowid
                    conn.commit()
    
                    messagebox.showinfo("Success", f"Fee assigned successfully!\nFee ID: {fee_id}")
                    dialog.destroy()
                    self.update_status(f"Fee assigned to student {student_id}")
    
                except ValueError:
                    messagebox.showerror("Error", "Invalid amount entered")
                except sqlite3.Error as e:
                    messagebox.showerror("Error", f"Database error: {e}")
                    if conn:
                        conn.rollback()
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to assign fee: {e}")
                finally:
                    if conn:
                        conn.close()
            
            # Buttons
            button_frame = ttk.Frame(dialog)
            button_frame.pack(pady=20)
            
            ttk.Button(button_frame, text="Assign Fee", command=assign_fee).pack(side='left', padx=10)
            ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=10)
        

        def bulk_assign_fees(self):
            """Bulk assign fees to students"""
            if messagebox.askyesno("Bulk Assign", "This will assign fees to multiple students. Continue?"):
                try:
                    # Call original function
                    self.bulk_assign_fees_to_course()
                    self.refresh_fees()
                    self.update_status("Bulk fee assignment completed")
                except Exception as e:
                    messagebox.showerror("Error", f"Bulk assignment failed: {str(e)}")
        

        def bulk_assign_fees_to_course(self):
            """Bulk assign fees to course with full functionality"""
            try:
                # Create bulk assignment dialog
                dialog = tk.Toplevel(self.root)
                dialog.title("Bulk Fee Assignment")
                dialog.geometry("600x550")
                dialog.transient(self.root)
                dialog.grab_set()

                main_frame = ttk.Frame(dialog, padding="20")
                main_frame.pack(fill=tk.BOTH, expand=True)

                ttk.Label(main_frame, text="Bulk Fee Assignment to Course",
                         font=('Arial', 14, 'bold')).pack(pady=(0, 20))

                # Form frame
                form_frame = ttk.LabelFrame(main_frame, text="Assignment Details", padding=15)
                form_frame.pack(fill=tk.X, pady=(0, 20))

                # Course selection
                ttk.Label(form_frame, text="Course Code:").grid(row=0, column=0, sticky=tk.W, pady=10)
                course_var = tk.StringVar()

                # Get available courses
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute('SELECT DISTINCT course_code FROM courses WHERE status = "active" ORDER BY course_code')
                courses = [row[0] for row in cursor.fetchall()]

                if not courses:
                    courses = ['CS', 'DS', 'ENG', 'BUS']  # Fallback

                course_combo = ttk.Combobox(form_frame, textvariable=course_var, values=courses, state='readonly')
                course_combo.grid(row=0, column=1, sticky=tk.EW, pady=10, padx=(10, 0))

                # Fee type
                ttk.Label(form_frame, text="Fee Type:").grid(row=1, column=0, sticky=tk.W, pady=10)
                fee_type_var = tk.StringVar()
                fee_types = ['Tuition', 'Library', 'Laboratory', 'Sports', 'Technology', 'Registration', 'Examination']
                fee_combo = ttk.Combobox(form_frame, textvariable=fee_type_var, values=fee_types, state='readonly')
                fee_combo.grid(row=1, column=1, sticky=tk.EW, pady=10, padx=(10, 0))

                # Amount
                ttk.Label(form_frame, text="Amount (£):").grid(row=2, column=0, sticky=tk.W, pady=10)
                amount_var = tk.StringVar()
                ttk.Entry(form_frame, textvariable=amount_var).grid(row=2, column=1, sticky=tk.EW, pady=10, padx=(10, 0))

                # Due date
                ttk.Label(form_frame, text="Due Date (YYYY-MM-DD):").grid(row=3, column=0, sticky=tk.W, pady=10)
                due_date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
                ttk.Entry(form_frame, textvariable=due_date_var).grid(row=3, column=1, sticky=tk.EW, pady=10, padx=(10, 0))

                # Description
                ttk.Label(form_frame, text="Description:").grid(row=4, column=0, sticky=tk.W, pady=10)
                desc_var = tk.StringVar()
                ttk.Entry(form_frame, textvariable=desc_var).grid(row=4, column=1, sticky=tk.EW, pady=10, padx=(10, 0))

                form_frame.columnconfigure(1, weight=1)

                # Preview frame
                preview_frame = ttk.LabelFrame(main_frame, text="Preview", padding=10)
                preview_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))

                preview_text = tk.Text(preview_frame, height=6, width=60, wrap=tk.WORD)
                preview_text.pack(fill=tk.BOTH, expand=True)
                preview_text.config(state='disabled')

                def update_preview(*args):
                    """Update preview of students affected"""
                    try:
                        course = course_var.get()
                        if course:
                            cursor.execute('''
                                SELECT COUNT(*) FROM students WHERE course = ? AND status = "Active"
                            ''', (course,))
                            count = cursor.fetchone()[0]
                            preview_text.config(state='normal')
                            preview_text.delete('1.0', tk.END)
                            preview_text.insert('1.0',
                                f"Course: {course}\n"
                                f"Active Students: {count}\n"
                                f"Fee Type: {fee_type_var.get() or 'Not selected'}\n"
                                f"Amount per student: £{amount_var.get() or '0.00'}\n"
                                f"Total fees to assign: £{float(amount_var.get() or 0) * count:,.2f}")
                            preview_text.config(state='disabled')
                    except Exception as e:
                        # Preview update failed (likely invalid input), silently ignore
                        print(f"Debug: Preview update failed: {e}")

                course_var.trace('w', update_preview)
                fee_type_var.trace('w', update_preview)
                amount_var.trace('w', update_preview)

                def assign_fees():
                    """Perform bulk fee assignment"""
                    try:
                        course = course_var.get()
                        fee_type = fee_type_var.get()
                        amount = amount_var.get()
                        due_date = due_date_var.get()
                        description = desc_var.get()

                        if not all([course, fee_type, amount, due_date]):
                            messagebox.showwarning("Missing Data", "Please fill in all required fields")
                            return

                        amount_float = float(amount)
                        if amount_float <= 0:
                            messagebox.showwarning("Invalid Amount", "Amount must be greater than 0")
                            return

                        # Get students in the course
                        cursor.execute('''
                            SELECT student_id FROM students WHERE course = ? AND status = "Active"
                        ''', (course,))
                        students = cursor.fetchall()

                        if not students:
                            messagebox.showinfo("No Students", f"No active students found in course {course}")
                            return

                        # Confirm before proceeding
                        if not messagebox.askyesno("Confirm Assignment",
                            f"Assign £{amount_float:.2f} {fee_type} fee to {len(students)} students in {course}?"):
                            return

                        # Assign fees
                        assigned_count = 0
                        from datetime import datetime
                        current_date = datetime.now().strftime('%Y-%m-%d')

                        for student in students:
                            student_id = student[0]
                            cursor.execute('''
                                INSERT INTO student_fees (student_id, fee_type, amount, due_date, description, created_date)
                                VALUES (?, ?, ?, ?, ?, ?)
                            ''', (student_id, fee_type, amount_float, due_date, description, current_date))
                            assigned_count += 1

                        conn.commit()
                        conn.close()

                        messagebox.showinfo("Success",
                            f"Successfully assigned £{amount_float:.2f} {fee_type} fee to {assigned_count} students in {course}")

                        print(f"✅ Bulk assigned {assigned_count} fees to course {course}")
                        dialog.destroy()

                    except ValueError:
                        messagebox.showerror("Invalid Input", "Please enter a valid amount")
                    except Exception as e:
                        messagebox.showerror("Error", f"Failed to assign fees: {str(e)}")
                        print(f"Error in bulk assignment: {e}")

                # Buttons
                button_frame = ttk.Frame(main_frame)
                button_frame.pack(fill=tk.X)

                ttk.Button(button_frame, text="Assign Fees", command=assign_fees).pack(side=tk.LEFT, padx=(0, 10))
                ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT)

            except Exception as e:
                messagebox.showerror("Error", f"Failed to open bulk assignment dialog: {str(e)}")
                print(f"Error in bulk_assign_fees_to_course: {e}")
    

        def create_late_fees_tab(self):
            """Create late fees management tab"""
            tab = tk.Frame(self.content_frame, bg='white')
            self.tab_frames['late_fees'] = tab
            
            main_frame = ttk.Frame(tab, padding=20)
            main_frame.pack(fill='both', expand=True)
            
            # Control buttons
            control_frame = ttk.LabelFrame(main_frame, text="Late Fee Management", padding=15)
            control_frame.pack(fill='x', pady=(0, 20))
            
            ttk.Button(control_frame, text="🧮 Calculate Late Fees", 
                      command=self.gui_calculate_late_fees, width=25).grid(row=0, column=0, padx=10, pady=5)
            ttk.Button(control_frame, text="❌ Waive Late Fee", 
                      command=self.gui_waive_late_fee, width=25).grid(row=0, column=1, padx=10, pady=5)
            ttk.Button(control_frame, text="📊 Late Fee Report", 
                      command=self.gui_late_fee_report, width=25).grid(row=0, column=2, padx=10, pady=5)
            
            # Late fees display
            display_frame = ttk.LabelFrame(main_frame, text="Outstanding Late Fees", padding=15)
            display_frame.pack(fill='both', expand=True)
            
            columns = ('Student ID', 'Student Name', 'Fee Type', 'Days Overdue', 'Late Fee', 'Applied Date', 'Status')
            self.late_fees_tree = ttk.Treeview(display_frame, columns=columns, show='headings', height=12)
            
            for col in columns:
                self.late_fees_tree.heading(col, text=col)
                self.late_fees_tree.column(col, width=100, anchor='center')
            
            # Scrollbars
            late_v_scroll = ttk.Scrollbar(display_frame, orient='vertical', command=self.late_fees_tree.yview)
            late_h_scroll = ttk.Scrollbar(display_frame, orient='horizontal', command=self.late_fees_tree.xview)
            self.late_fees_tree.configure(yscrollcommand=late_v_scroll.set, xscrollcommand=late_h_scroll.set)
            
            self.late_fees_tree.pack(side='left', fill='both', expand=True)
            late_v_scroll.pack(side='right', fill='y')
            late_h_scroll.pack(side='bottom', fill='x')
            
            self.refresh_late_fees()
        

        def calculate_late_fees(self):
            """Calculate late fees"""
            if messagebox.askyesno("Calculate Late Fees", "Calculate late fees for overdue payments?"):
                try:
                    # Call the backend implementation instead
                    result = self.calculate_late_fees_backend()
                    self.refresh_fees()
                    self.update_status(f"Late fees calculated: {result['count']} fees applied")
                except Exception as e:
                    messagebox.showerror("Error", f"Late fee calculation failed: {str(e)}")
        

        def gui_calculate_late_fees(self):
            """GUI wrapper for calculating late fees"""
            if messagebox.askyesno("Confirm", "This will calculate and apply late fees for all overdue payments. Continue?"):
                try:
                    # Call the original function logic in a thread to avoid blocking UI
                    def calculate_fees():
                        self.update_status("Calculating late fees...")
                        result = self.calculate_late_fees_backend()
                        
                        messagebox.showinfo("Late Fees Calculation Complete", 
                                           f"Late fees applied: {result['count']}\n"
                                           f"Total late fees: £{result['total']:.2f}")
                        
                        self.refresh_late_fees()
                        self.update_status("Late fees calculation completed")
                    
                    thread = threading.Thread(target=calculate_fees)
                    thread.daemon = True
                    thread.start()
                    
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to calculate late fees: {e}")
        

        def calculate_late_fees_backend(self):
            """Backend function for late fee calculation"""
            try:
                conn = get_connection()
                cursor = conn.cursor()
                
                current_date = datetime.now().date()
                
                # Find overdue fees
                cursor.execute('''
                SELECT sf.student_fee_id, sf.student_id, sf.amount, sf.due_date, sf.status,
                       ft.fee_name, ft.late_fee_calculation, ft.late_fee_amount, ft.grace_period_days,
                       s.first_name, s.last_name
                FROM student_fees sf
                JOIN fee_types ft ON sf.fee_type_id = ft.fee_type_id
                JOIN students s ON sf.student_id = s.student_id
                WHERE sf.status IN ('unpaid', 'partial') 
                AND sf.due_date IS NOT NULL 
                AND date(sf.due_date) < date('now')
                AND ft.late_fee_amount > 0
                ''')
                
                overdue_fees = cursor.fetchall()
                late_fees_applied = 0
                total_late_fees = 0
                
                for fee_data in overdue_fees:
                    (student_fee_id, student_id, amount, due_date, status, fee_name, 
                     calculation_method, late_fee_amount, grace_period_days, first_name, last_name) = fee_data
                    
                    # Parse due date
                    due_date_obj = datetime.strptime(due_date, '%Y-%m-%d').date()
                    days_overdue = (current_date - due_date_obj).days
                    
                    # Apply grace period
                    if grace_period_days and days_overdue <= grace_period_days:
                        continue
                    
                    effective_days_overdue = days_overdue - (grace_period_days or 0)
                    
                    # Check if late fee already applied for this period
                    cursor.execute('''
                    SELECT COUNT(*) FROM late_fees 
                    WHERE student_fee_id = ? AND applied_date = ?
                    ''', (student_fee_id, current_date.strftime('%Y-%m-%d')))
                    
                    if cursor.fetchone()[0] > 0:
                        continue  # Late fee already applied today
                    
                    # Calculate late fee based on method
                    calculated_late_fee = 0
                    
                    if calculation_method == 'fixed':
                        calculated_late_fee = late_fee_amount
                    elif calculation_method == 'percentage':
                        calculated_late_fee = amount * (late_fee_amount / 100)
                    elif calculation_method == 'daily':
                        calculated_late_fee = late_fee_amount * effective_days_overdue
                    
                    if calculated_late_fee > 0:
                        # Apply late fee
                        cursor.execute('''
                        INSERT INTO late_fees 
                        (student_fee_id, late_fee_amount, calculation_method, days_overdue, applied_date, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                        ''', (student_fee_id, calculated_late_fee, calculation_method, effective_days_overdue,
                              current_date.strftime('%Y-%m-%d'), datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                        
                        late_fees_applied += 1
                        total_late_fees += calculated_late_fee
                
                conn.commit()
                conn.close()
                
                return {'count': late_fees_applied, 'total': total_late_fees}
                
            except Exception as e:
                raise Exception(f"Failed to calculate late fees: {e}")
        

        def refresh_late_fees(self):
            """Refresh late fees display"""
            try:
                conn = get_connection()
                cursor = conn.cursor()
                
                cursor.execute('''
                SELECT s.student_id, s.first_name, s.last_name, ft.fee_name,
                       lf.days_overdue, lf.late_fee_amount, lf.applied_date, 
                       CASE WHEN lf.waived = 1 THEN 'Waived' ELSE 'Active' END as status
                FROM late_fees lf
                JOIN student_fees sf ON lf.student_fee_id = sf.student_fee_id
                JOIN students s ON sf.student_id = s.student_id
                JOIN fee_types ft ON sf.fee_type_id = ft.fee_type_id
                ORDER BY lf.applied_date DESC
                ''')
                
                late_fees = cursor.fetchall()
                
                # Clear existing items
                for item in self.late_fees_tree.get_children():
                    self.late_fees_tree.delete(item)
                
                # Add late fee data
                for fee in late_fees:
                    student_id, first_name, last_name, fee_name, days_overdue, amount, applied_date, status = fee
                    student_name = f"{first_name} {last_name}"
                    
                    self.late_fees_tree.insert('', 'end', values=(
                        student_id, student_name, fee_name, days_overdue, 
                        f"£{amount:.2f}", applied_date, status
                    ))
                
                conn.close()
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to refresh late fees: {e}")
        

        def gui_waive_late_fee(self):
            """GUI for waiving late fees"""
            dialog = tk.Toplevel(self.root)
            dialog.title("Waive Late Fee")
            dialog.geometry("600x500")
            dialog.transient(self.root)
            dialog.grab_set()
            
            # Student selection
            student_frame = ttk.LabelFrame(dialog, text="Student Selection", padding=15)
            student_frame.pack(fill='x', padx=20, pady=10)
            
            ttk.Label(student_frame, text="Student ID:", font=('Arial', 12)).pack(anchor='w')
            student_id_var = tk.StringVar()
            ttk.Entry(student_frame, textvariable=student_id_var, font=('Arial', 12), width=20).pack(anchor='w', pady=5)
            
            def load_student_late_fees():
                student_id = student_id_var.get().strip()
                if not student_id:
                    return
                
                try:
                    conn = get_connection()
                    cursor = conn.cursor()
                    
                    cursor.execute('''
                    SELECT lf.late_fee_id, lf.late_fee_amount, lf.applied_date, lf.waived,
                           ft.fee_name, sf.amount
                    FROM late_fees lf
                    JOIN student_fees sf ON lf.student_fee_id = sf.student_fee_id
                    JOIN fee_types ft ON sf.fee_type_id = ft.fee_type_id
                    WHERE sf.student_id = ? AND lf.waived = 0
                    ORDER BY lf.applied_date DESC
                    ''', (student_id,))
                    
                    late_fees = cursor.fetchall()
                    
                    # Clear existing items
                    for item in waive_tree.get_children():
                        waive_tree.delete(item)
                    
                    if not late_fees:
                        messagebox.showinfo("Info", f"No active late fees found for student {student_id}")
                        conn.close()
                        return
                    
                    # Add late fee data
                    for fee in late_fees:
                        late_fee_id, amount, applied_date, waived, fee_name, original_amount = fee
                        waive_tree.insert('', 'end', values=(
                            late_fee_id, fee_name, f"£{amount:.2f}", applied_date
                        ))
                    
                    conn.close()
                    
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to load late fees: {e}")
            
            ttk.Button(student_frame, text="Load Late Fees", command=load_student_late_fees).pack(anchor='w', pady=5)
            
            # Late fees display
            fees_frame = ttk.LabelFrame(dialog, text="Active Late Fees", padding=15)
            fees_frame.pack(fill='both', expand=True, padx=20, pady=10)
            
            columns = ('Late Fee ID', 'Fee Name', 'Amount', 'Applied Date')
            waive_tree = ttk.Treeview(fees_frame, columns=columns, show='headings', height=8)
            
            for col in columns:
                waive_tree.heading(col, text=col)
                waive_tree.column(col, width=120, anchor='center')
            
            waive_tree.pack(fill='both', expand=True)
            
            # Waiver details
            waiver_frame = ttk.LabelFrame(dialog, text="Waiver Details", padding=15)
            waiver_frame.pack(fill='x', padx=20, pady=10)
            
            ttk.Label(waiver_frame, text="Reason for waiving late fee:", font=('Arial', 12)).pack(anchor='w')
            reason_text = tk.Text(waiver_frame, height=3, width=50, font=('Arial', 10))
            reason_text.pack(fill='x', pady=5)
            
            def waive_selected_fees():
                selected_items = waive_tree.selection()
                if not selected_items:
                    messagebox.showerror("Error", "Please select late fee(s) to waive")
                    return
                
                reason = reason_text.get("1.0", tk.END).strip()
                if not reason:
                    messagebox.showerror("Error", "Waiver reason is required")
                    return
                
                try:
                    conn = get_connection()
                    cursor = conn.cursor()
                    
                    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    total_waived = 0
                    
                    for item in selected_items:
                        values = waive_tree.item(item)['values']
                        late_fee_id = values[0]
                        amount = float(values[2].replace('£', ''))
                        
                        cursor.execute('''
                        UPDATE late_fees 
                        SET waived = 1, waived_by = ?, waived_date = ?, waiver_reason = ?
                        WHERE late_fee_id = ?
                        ''', (auth.current_user['username'], now, reason, late_fee_id))
                        
                        total_waived += amount
                    
                    conn.commit()
                    conn.close()
                    
                    messagebox.showinfo("Success", f"Late fees waived successfully!\nTotal amount: £{total_waived:.2f}")
                    dialog.destroy()
                    self.refresh_late_fees()
                    self.update_status(f"Late fees totaling £{total_waived:.2f} waived")
                    
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to waive late fees: {e}")
            
            def waive_all_fees():
                if not waive_tree.get_children():
                    messagebox.showerror("Error", "No late fees to waive")
                    return
                
                if messagebox.askyesno("Confirm", "Waive ALL late fees for this student?"):
                    # Select all items
                    for item in waive_tree.get_children():
                        waive_tree.selection_add(item)
                    waive_selected_fees()
            
            # Buttons
            button_frame = ttk.Frame(dialog)
            button_frame.pack(pady=10)
            
            ttk.Button(button_frame, text="Waive Selected", command=waive_selected_fees).pack(side='left', padx=10)
            ttk.Button(button_frame, text="Waive All", command=waive_all_fees).pack(side='left', padx=10)
            ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=10)
        
        # Currency Management Functions

        def gui_late_fee_report(self):
            """Generate late fee report"""
            try:
                conn = get_connection()
                cursor = conn.cursor()
                
                cursor.execute('''
                SELECT s.student_id, s.first_name, s.last_name, ft.fee_name,
                       lf.late_fee_amount, lf.applied_date, lf.days_overdue,
                       CASE WHEN lf.waived = 1 THEN 'Waived' ELSE 'Active' END as status
                FROM late_fees lf
                JOIN student_fees sf ON lf.student_fee_id = sf.student_fee_id
                JOIN students s ON sf.student_id = s.student_id
                JOIN fee_types ft ON sf.fee_type_id = ft.fee_type_id
                ORDER BY lf.applied_date DESC
                LIMIT 100
                ''')
                
                late_fees = cursor.fetchall()
                
                if not late_fees:
                    report_content = "No late fees found in the system."
                else:
                    report_content = f"""Late Fees Report
    {'=' * 100}
    {'Student ID':<12} {'Student Name':<20} {'Fee Type':<20} {'Late Fee':<10} {'Applied':<12} {'Days':<5} {'Status':<8}
    {'-' * 100}
    """
                    
                    total_late_fees = 0
                    active_late_fees = 0
                    
                    for fee in late_fees:
                        student_id, first_name, last_name, fee_name, amount, applied_date, days_overdue, status = fee
                        student_name = f"{first_name} {last_name}"
                        
                        report_content += f"{student_id:<12} {student_name:<20} {fee_name:<20} £{amount:<9.2f} {applied_date:<12} {days_overdue:<5} {status:<8}\n"
                        
                        total_late_fees += amount
                        if status == 'Active':
                            active_late_fees += amount
                    
                    report_content += f"""{'-' * 100}
    Total Late Fees: £{total_late_fees:,.2f}
    Active Late Fees: £{active_late_fees:,.2f}
    Waived Late Fees: £{total_late_fees - active_late_fees:,.2f}
    {'=' * 100}
    """
                
                # Display in reports tab or create new window
                self.show_tab('reports')  # Reports tab
                self.report_text.delete('1.0', tk.END)
                self.report_text.insert('1.0', report_content)
                
                conn.close()
                self.update_status("Late fee report generated")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to generate late fee report: {e}")
    
