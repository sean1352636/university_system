from education_system.systems.university.infrastructure.database.db import DEFAULT_DB_PATH  # injected
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from tkinter.scrolledtext import ScrolledText
from education_system.systems.university.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta
import threading
import sys
import os

# Import centralized authentication system
# Import authentication - REQUIRED (no fallback for security)
from education_system.systems.university.infrastructure.auth import UserAuth, get_global_auth
from education_system.systems.university.infrastructure.shared_context import get_auth

# Authentication is imported unconditionally above (required, no fallback)
AUTH_AVAILABLE = True

# Import i18n for multi-language support
from education_system.systems.university.infrastructure.i18n import (
    init_i18n,
    get_text as _t,
    set_language,
    get_current_language,
    get_current_language_name,
    get_available_languages,
)
from education_system.systems.university.infrastructure.utils.gui_language_selector import show_gui_language_selector

# Import finance integration for student finance account payments
try:
    from education_system.systems.university.infrastructure.utils.finance_integration import (
        process_student_finance_account_payment,
        get_student_finance_account_balance,
        get_student_info,
        LOW_BALANCE_THRESHOLD
    )
    FINANCE_ACCOUNT_AVAILABLE = True
except ImportError:
    FINANCE_ACCOUNT_AVAILABLE = False
    print("Warning: Student finance account integration not available")

# Import custom exceptions for proper error handling
from education_system.systems.university.infrastructure.exceptions import (
    DatabaseError,
    DatabaseConnectionError,
    QueryError,
    ValidationError,
    InvalidInputError
)

# Attempt to import the enhanced restaurant DB initializer from the CLI version.
# If available, calling this will create the full set of tables defined in
# services/restaurant_management.py. Alias the import to avoid naming
# conflicts with this module's own init_db function.
try:
    from education_system.systems.university.domain.operations.commerce.services.restaurant_management import init_db as init_enhanced_restaurant_db
except ImportError:
    init_enhanced_restaurant_db = None

# Database configuration
# Always point to the central student_records.db in refactored/db_files.
try:
    from education_system.systems.university.infrastructure.database.db import DEFAULT_DB_PATH as DATABASE_FILE
except ImportError:
    # Fallback to local file if refactored.database.db is unavailable
    DATABASE_FILE = str(DEFAULT_DB_PATH)

# Import get_db_connection from main_gui
from education_system.systems.university.interfaces.gui.operations.commerce.restaurant_management_gui.core.main_gui import get_db_connection


def manage_customer_feedback(self):
    """Main customer feedback management interface"""
    feedback_dialog = tk.Toplevel(self.root)
    feedback_dialog.title("Customer Feedback Management")
    feedback_dialog.geometry("1000x700")
    feedback_dialog.transient(self.root)
    feedback_dialog.grab_set()
    main_frame = ttk.Frame(feedback_dialog, padding=20)
    main_frame.pack(fill='both', expand=True)
    ttk.Label(main_frame, text="Customer Feedback Management",
             font=('Arial', 14, 'bold')).pack(pady=10)
    # Create feedback table if it doesn't exist
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            # Customer feedback table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS customer_feedback (
                    feedback_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    customer_id INTEGER,
                    customer_name TEXT,
                    order_id INTEGER,
                    rating INTEGER CHECK(rating >= 1 AND rating <= 5),
                    category TEXT,
                    feedback_text TEXT NOT NULL,
                    response TEXT,
                    responded_by TEXT,
                    response_date DATETIME,
                    status TEXT DEFAULT 'Pending',
                    feedback_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (customer_id) REFERENCES restaurant_customers(customer_id),
                    FOREIGN KEY (order_id) REFERENCES orders(order_id)
                )
            ''')
            conn.commit()
            conn.close()
    except sqlite3.Error as e:
        messagebox.showerror("Database Error", f"Failed to initialize feedback table: {e}")
        feedback_dialog.destroy()
        return
    # Action buttons frame
    btn_frame = ttk.LabelFrame(main_frame, text="Actions", padding=15)
    btn_frame.pack(fill='x', pady=10)
    # Row 1: Viewing and Managing
    row1 = ttk.Frame(btn_frame)
    row1.pack(fill='x', pady=5)
    ttk.Button(row1, text="View Recent Feedback",
              command=lambda: self.view_recent_feedback(feedback_dialog),
              width=25).pack(side='left', padx=5)
    ttk.Button(row1, text="Respond to Feedback",
              command=lambda: self.respond_to_feedback(feedback_dialog),
              width=25).pack(side='left', padx=5)
    ttk.Button(row1, text="Submit New Feedback (Demo)",
              command=lambda: self.submit_demo_feedback(feedback_dialog),
              width=25).pack(side='left', padx=5)
    # Row 2: Reporting
    row2 = ttk.Frame(btn_frame)
    row2.pack(fill='x', pady=5)
    ttk.Button(row2, text="Export Feedback Report (CSV)",
              command=self.export_feedback_report,
              width=25).pack(side='left', padx=5)
    ttk.Button(row2, text="Generate Analytics Report",
              command=lambda: self.export_feedback_report_pdf(feedback_dialog),
              width=25).pack(side='left', padx=5)
    # Statistics frame
    stats_frame = ttk.LabelFrame(main_frame, text="Feedback Statistics", padding=15)
    stats_frame.pack(fill='x', pady=10)
    def update_stats():
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                # Total feedback
                cursor.execute("SELECT COUNT(*) FROM customer_feedback")
                total = cursor.fetchone()[0]
                # Pending responses
                cursor.execute("SELECT COUNT(*) FROM customer_feedback WHERE status = 'Pending'")
                pending = cursor.fetchone()[0]
                # Average rating
                cursor.execute("SELECT AVG(rating) FROM customer_feedback")
                avg_rating = cursor.fetchone()[0] or 0
                # Ratings distribution
                cursor.execute('''
                    SELECT rating, COUNT(*) FROM customer_feedback
                    GROUP BY rating ORDER BY rating DESC
                ''')
                ratings = cursor.fetchall()
                conn.close()
                stats_text = (f"Total Feedback: {total} | Pending Responses: {pending} | "
                            f"Average Rating: {avg_rating:.2f}/5.0\n\n"
                            f"Rating Distribution: ")
                for rating, count in ratings:
                    stats_text += f"{rating}⭐: {count}  "
                stats_label.config(text=stats_text)
        except sqlite3.Error as e:
            stats_label.config(text=f"Error loading statistics: {e}")
    stats_label = ttk.Label(stats_frame, text="Loading statistics...", font=('Arial', 9))
    stats_label.pack()
    update_stats()
    # Refresh and close buttons
    bottom_frame = ttk.Frame(main_frame)
    bottom_frame.pack(fill='x', pady=10)
    ttk.Button(bottom_frame, text="Refresh Statistics",
              command=update_stats).pack(side='left', padx=5)
    ttk.Button(bottom_frame, text="Close",
              command=feedback_dialog.destroy).pack(side='right', padx=5)

def view_recent_feedback(self, parent_dialog):
    """View and browse customer feedback with filters"""
    view_dialog = tk.Toplevel(parent_dialog)
    view_dialog.title("View Customer Feedback")
    view_dialog.geometry("1200x700")
    view_dialog.transient(parent_dialog)
    view_dialog.grab_set()
    main_frame = ttk.Frame(view_dialog, padding=20)
    main_frame.pack(fill='both', expand=True)
    ttk.Label(main_frame, text="Customer Feedback",
             font=('Arial', 14, 'bold')).pack(pady=10)
    # Filter frame
    filter_frame = ttk.LabelFrame(main_frame, text="Filters", padding=10)
    filter_frame.pack(fill='x', pady=10)
    filter_row = ttk.Frame(filter_frame)
    filter_row.pack(fill='x', pady=5)
    ttk.Label(filter_row, text="Status:").pack(side='left', padx=5)
    status_var = tk.StringVar(value='All')
    status_combo = ttk.Combobox(filter_row, textvariable=status_var,
                               values=['All', 'Pending', 'Responded'],
                               width=15, state='readonly')
    status_combo.pack(side='left', padx=5)
    ttk.Label(filter_row, text="Rating:").pack(side='left', padx=20)
    rating_var = tk.StringVar(value='All')
    rating_combo = ttk.Combobox(filter_row, textvariable=rating_var,
                               values=['All', '5', '4', '3', '2', '1'],
                               width=10, state='readonly')
    rating_combo.pack(side='left', padx=5)
    ttk.Label(filter_row, text="Category:").pack(side='left', padx=20)
    category_var = tk.StringVar(value='All')
    category_combo = ttk.Combobox(filter_row, textvariable=category_var,
                                 values=['All', 'Food Quality', 'Service', 'Cleanliness',
                                        'Pricing', 'Ambiance', 'Other'],
                                 width=15, state='readonly')
    category_combo.pack(side='left', padx=5)
    # Treeview frame
    tree_frame = ttk.Frame(main_frame)
    tree_frame.pack(fill='both', expand=True, pady=10)
    # Scrollbars
    v_scroll = ttk.Scrollbar(tree_frame, orient='vertical')
    h_scroll = ttk.Scrollbar(tree_frame, orient='horizontal')
    columns = ('ID', 'Date', 'Customer', 'Rating', 'Category', 'Feedback', 'Status', 'Response')
    feedback_tree = ttk.Treeview(tree_frame, columns=columns, show='headings',
                                 yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set,
                                 height=20)
    v_scroll.config(command=feedback_tree.yview)
    h_scroll.config(command=feedback_tree.xview)
    # Configure columns
    column_widths = {'ID': 50, 'Date': 100, 'Customer': 120, 'Rating': 60,
                    'Category': 100, 'Feedback': 250, 'Status': 80, 'Response': 200}
    for col in columns:
        feedback_tree.heading(col, text=col)
        feedback_tree.column(col, width=column_widths.get(col, 100))
    feedback_tree.pack(side='left', fill='both', expand=True)
    v_scroll.pack(side='right', fill='y')
    h_scroll.pack(side='bottom', fill='x')
    def load_feedback():
        # Clear existing items
        for item in feedback_tree.get_children():
            feedback_tree.delete(item)
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                # Build query with filters
                query = '''
                    SELECT feedback_id, feedback_date, customer_name, rating,
                           category, feedback_text, status, response
                    FROM customer_feedback
                    WHERE 1=1
                '''
                params = []
                if status_var.get() != 'All':
                    query += ' AND status = ?'
                    params.append(status_var.get())
                if rating_var.get() != 'All':
                    query += ' AND rating = ?'
                    params.append(int(rating_var.get()))
                if category_var.get() != 'All':
                    query += ' AND category = ?'
                    params.append(category_var.get())
                query += ' ORDER BY feedback_date DESC'
                cursor.execute(query, params)
                feedbacks = cursor.fetchall()
                for fb in feedbacks:
                    # Truncate long text for display
                    feedback_text = fb[5][:100] + '...' if len(fb[5]) > 100 else fb[5]
                    response_text = (fb[7][:100] + '...' if fb[7] and len(fb[7]) > 100
                                   else fb[7] or 'N/A')
                    feedback_tree.insert('', 'end', values=(
                        fb[0],  # ID
                        fb[1][:16] if fb[1] else 'N/A',  # Date
                        fb[2] or 'Anonymous',  # Customer
                        f"{fb[3]}⭐",  # Rating
                        fb[4] or 'General',  # Category
                        feedback_text,  # Feedback
                        fb[6],  # Status
                        response_text  # Response
                    ))
                conn.close()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to load feedback: {e}")
    def view_full_feedback():
        """View complete feedback details"""
        selection = feedback_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select feedback to view details")
            return
        item = feedback_tree.item(selection[0])
        feedback_id = item['values'][0]
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM customer_feedback WHERE feedback_id = ?
                ''', (feedback_id,))
                fb = cursor.fetchone()
                conn.close()
                if fb:
                    details = f"""
Feedback ID: {fb[0]}
Customer: {fb[2] or 'Anonymous'}
Order ID: {fb[3] or 'N/A'}
Date: {fb[11]}

Rating: {fb[4]} / 5
Category: {fb[5] or 'General'}

Feedback:
{fb[6]}

Status: {fb[10]}

Response:
{fb[7] or 'No response yet'}

{'Responded by: ' + fb[8] if fb[8] else ''}
{'Response date: ' + fb[9] if fb[9] else ''}
                        """.strip()

                    messagebox.showinfo("Feedback Details", details)
        except (sqlite3.Error, tk.TclError) as e:
            messagebox.showerror("Error", f"Failed to load feedback details: {e}")
    load_feedback()
    # Button frame
    btn_frame = ttk.Frame(main_frame)
    btn_frame.pack(fill='x', pady=10)
    ttk.Button(btn_frame, text="Apply Filters", command=load_feedback).pack(side='left', padx=5)
    ttk.Button(btn_frame, text="View Full Details", command=view_full_feedback).pack(side='left', padx=5)
    ttk.Button(btn_frame, text="Refresh", command=load_feedback).pack(side='left', padx=5)
    ttk.Button(btn_frame, text="Close", command=view_dialog.destroy).pack(side='right', padx=5)

def respond_to_feedback(self, parent_dialog):
    """Respond to customer feedback"""
    # First select feedback to respond to
    select_dialog = tk.Toplevel(parent_dialog)
    select_dialog.title("Select Feedback to Respond")
    select_dialog.geometry("1000x600")
    select_dialog.transient(parent_dialog)
    select_dialog.grab_set()
    main_frame = ttk.Frame(select_dialog, padding=20)
    main_frame.pack(fill='both', expand=True)
    ttk.Label(main_frame, text="Select Feedback to Respond To",
             font=('Arial', 12, 'bold')).pack(pady=10)
    ttk.Label(main_frame, text="Only showing pending feedback that needs a response",
             foreground='blue').pack(pady=5)
    # Feedback list
    tree_frame = ttk.Frame(main_frame)
    tree_frame.pack(fill='both', expand=True, pady=10)
    columns = ('ID', 'Date', 'Customer', 'Rating', 'Category', 'Feedback')
    fb_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)
    for col in columns:
        fb_tree.heading(col, text=col)
        fb_tree.column(col, width=150)
    fb_tree.pack(fill='both', expand=True)
    def load_pending_feedback():
        for item in fb_tree.get_children():
            fb_tree.delete(item)
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT feedback_id, feedback_date, customer_name, rating,
                           category, feedback_text
                    FROM customer_feedback
                    WHERE status = 'Pending'
                    ORDER BY feedback_date DESC
                ''')
                feedbacks = cursor.fetchall()
                for fb in feedbacks:
                    feedback_text = fb[5][:150] + '...' if len(fb[5]) > 150 else fb[5]
                    fb_tree.insert('', 'end', values=(
                        fb[0],
                        fb[1][:16] if fb[1] else 'N/A',
                        fb[2] or 'Anonymous',
                        f"{fb[3]}⭐",
                        fb[4] or 'General',
                        feedback_text
                    ))
                conn.close()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to load feedback: {e}")
    load_pending_feedback()
    def proceed_to_respond():
        selection = fb_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select feedback to respond to")
            return
        item = fb_tree.item(selection[0])
        feedback_id = item['values'][0]
        select_dialog.destroy()
        show_response_dialog(feedback_id)
    def show_response_dialog(feedback_id):
        """Show response composition dialog"""
        response_dialog = tk.Toplevel(parent_dialog)
        response_dialog.title("Respond to Customer Feedback")
        response_dialog.geometry("700x600")
        response_dialog.transient(parent_dialog)
        response_dialog.grab_set()
        main_frame = ttk.Frame(response_dialog, padding=20)
        main_frame.pack(fill='both', expand=True)
        ttk.Label(main_frame, text="Respond to Customer Feedback",
                 font=('Arial', 14, 'bold')).pack(pady=10)
        # Load feedback details
        try:
            conn = get_db_connection()
            if not conn:
                return
            cursor = conn.cursor()
            cursor.execute('''
                SELECT feedback_id, customer_name, rating, category,
                       feedback_text, feedback_date
                FROM customer_feedback WHERE feedback_id = ?
            ''', (feedback_id,))
            fb = cursor.fetchone()
            conn.close()
            if not fb:
                messagebox.showerror("Error", "Feedback not found")
                response_dialog.destroy()
                return
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to load feedback: {e}")
            response_dialog.destroy()
            return
        # Display original feedback
        feedback_frame = ttk.LabelFrame(main_frame, text="Original Feedback", padding=15)
        feedback_frame.pack(fill='x', pady=10)
        feedback_info = f"""
Customer: {fb[1] or 'Anonymous'}
Date: {fb[5]}
Rating: {fb[2]} / 5
Category: {fb[3] or 'General'}

Feedback:
{fb[4]}
            """.strip()
        ttk.Label(feedback_frame, text=feedback_info, justify='left',
                 font=('Arial', 9)).pack(pady=5)
        # Response composition
        response_frame = ttk.LabelFrame(main_frame, text="Your Response", padding=15)
        response_frame.pack(fill='both', expand=True, pady=10)
        ttk.Label(response_frame, text="Compose your response to the customer:",
                 foreground='blue').pack(pady=5)
        response_text = ScrolledText(response_frame, height=10, width=60, font=('Arial', 10))
        response_text.pack(fill='both', expand=True, pady=5)
        # Quick response templates
        templates_frame = ttk.Frame(response_frame)
        templates_frame.pack(fill='x', pady=5)
        ttk.Label(templates_frame, text="Quick Templates:").pack(side='left', padx=5)
        def insert_template(template):
            response_text.delete('1.0', tk.END)
            response_text.insert('1.0', template)
        templates = {
            "Thank You": "Thank you for your valuable feedback! We truly appreciate you taking the time to share your experience with us.",
            "Apology": "We sincerely apologize for the experience you had. This does not reflect our usual standards, and we are taking immediate steps to address this issue.",
            "Improvement": "Thank you for bringing this to our attention. We are constantly working to improve our service and your feedback helps us do that."
        }
        for name, text in templates.items():
            ttk.Button(templates_frame, text=name,
                      command=lambda t=text: insert_template(t)).pack(side='left', padx=2)
        def save_response():
            response = response_text.get('1.0', tk.END).strip()
            if not response:
                messagebox.showwarning("Empty Response", "Please enter a response")
                return
            # Get current user
            current_user = "System"
            if AUTH_AVAILABLE:
                try:
                    from education_system.systems.university.infrastructure.shared_context import get_auth
                    auth = get_auth()
                    if auth.current_user:
                        current_user = auth.current_user.get('username', 'Unknown')
                except (sqlite3.Error, tk.TclError):
                    pass
            try:
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        UPDATE customer_feedback
                        SET response = ?,
                            responded_by = ?,
                            response_date = CURRENT_TIMESTAMP,
                            status = 'Responded'
                        WHERE feedback_id = ?
                    ''', (response, current_user, feedback_id))
                    conn.commit()
                    conn.close()
                    messagebox.showinfo("Success",
                                      f"Response submitted successfully!\n\n"
                                      f"Feedback ID: {feedback_id}\n"
                                      f"Responded by: {current_user}")
                    response_dialog.destroy()
            except sqlite3.Error as e:
                messagebox.showerror("Error", f"Failed to save response: {e}")
        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x', pady=10)
        ttk.Button(btn_frame, text="Submit Response",
                  command=save_response).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Cancel",
                  command=response_dialog.destroy).pack(side='right', padx=5)
    # Buttons
    btn_frame = ttk.Frame(main_frame)
    btn_frame.pack(fill='x', pady=10)
    ttk.Button(btn_frame, text="Respond to Selected",
              command=proceed_to_respond).pack(side='left', padx=5)
    ttk.Button(btn_frame, text="Refresh", command=load_pending_feedback).pack(side='left', padx=5)
    ttk.Button(btn_frame, text="Cancel", command=select_dialog.destroy).pack(side='right', padx=5)

def submit_demo_feedback(self, parent_dialog):
    """Submit demo feedback for testing purposes"""
    demo_dialog = tk.Toplevel(parent_dialog)
    demo_dialog.title("Submit Feedback (Demo)")
    demo_dialog.geometry("600x500")
    demo_dialog.transient(parent_dialog)
    demo_dialog.grab_set()
    main_frame = ttk.Frame(demo_dialog, padding=20)
    main_frame.pack(fill='both', expand=True)
    ttk.Label(main_frame, text="Submit Customer Feedback",
             font=('Arial', 12, 'bold')).pack(pady=10)
    form_frame = ttk.Frame(main_frame)
    form_frame.pack(fill='both', expand=True, pady=10)
    fields = {}
    row = 0
    ttk.Label(form_frame, text="Customer Name:").grid(row=row, column=0, sticky='w', pady=5)
    fields['name'] = ttk.Entry(form_frame, width=40)
    fields['name'].grid(row=row, column=1, pady=5, padx=10)
    row += 1
    ttk.Label(form_frame, text="Rating:*").grid(row=row, column=0, sticky='w', pady=5)
    fields['rating'] = ttk.Combobox(form_frame, values=['5 - Excellent', '4 - Good', '3 - Average',
                                                        '2 - Poor', '1 - Very Poor'],
                                   width=38, state='readonly')
    fields['rating'].grid(row=row, column=1, pady=5, padx=10)
    fields['rating'].current(0)
    row += 1
    ttk.Label(form_frame, text="Category:*").grid(row=row, column=0, sticky='w', pady=5)
    fields['category'] = ttk.Combobox(form_frame,
                                     values=['Food Quality', 'Service', 'Cleanliness',
                                            'Pricing', 'Ambiance', 'Other'],
                                     width=38, state='readonly')
    fields['category'].grid(row=row, column=1, pady=5, padx=10)
    fields['category'].current(0)
    row += 1
    ttk.Label(form_frame, text="Feedback:*").grid(row=row, column=0, sticky='nw', pady=5)
    fields['feedback'] = ScrolledText(form_frame, height=10, width=40, font=('Arial', 10))
    fields['feedback'].grid(row=row, column=1, pady=5, padx=10)
    def submit_feedback():
        try:
            feedback_text = fields['feedback'].get('1.0', tk.END).strip()
            if not feedback_text:
                messagebox.showwarning("Missing Info", "Please enter feedback")
                return
            rating_text = fields['rating'].get()
            rating = int(rating_text.split(' - ')[0])
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO customer_feedback
                    (customer_name, rating, category, feedback_text, status)
                    VALUES (?, ?, ?, ?, 'Pending')
                ''', (fields['name'].get().strip() or 'Anonymous',
                      rating,
                      fields['category'].get(),
                      feedback_text))
                conn.commit()
                conn.close()
                messagebox.showinfo("Success", "Feedback submitted successfully!")
                demo_dialog.destroy()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to submit feedback: {e}")
    # Buttons
    btn_frame = ttk.Frame(main_frame)
    btn_frame.pack(fill='x', pady=10)
    ttk.Button(btn_frame, text="Submit Feedback", command=submit_feedback).pack(side='left', padx=5)
    ttk.Button(btn_frame, text="Cancel", command=demo_dialog.destroy).pack(side='right', padx=5)

def export_feedback_report(self):
    """Export feedback data to CSV with statistics"""
    try:
        conn = get_db_connection()
        if not conn:
            return
        cursor = conn.cursor()
        # Get all feedback
        cursor.execute('''
            SELECT feedback_id, feedback_date, customer_name, order_id,
                   rating, category, feedback_text, response, responded_by,
                   response_date, status
            FROM customer_feedback
            ORDER BY feedback_date DESC
        ''')
        feedbacks = cursor.fetchall()
        # Get statistics
        cursor.execute("SELECT COUNT(*) FROM customer_feedback")
        total = cursor.fetchone()[0]
        cursor.execute("SELECT AVG(rating) FROM customer_feedback")
        avg_rating = cursor.fetchone()[0] or 0
        cursor.execute('''
            SELECT rating, COUNT(*) FROM customer_feedback
            GROUP BY rating ORDER BY rating DESC
        ''')
        rating_dist = cursor.fetchall()
        cursor.execute('''
            SELECT category, COUNT(*) FROM customer_feedback
            GROUP BY category ORDER BY COUNT(*) DESC
        ''')
        category_dist = cursor.fetchall()
        conn.close()
        # Create CSV content
        import csv
        from io import StringIO
        output = StringIO()
        writer = csv.writer(output)
        # Summary section
        writer.writerow(['CUSTOMER FEEDBACK REPORT'])
        writer.writerow(['Generated:', datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
        writer.writerow([])
        writer.writerow(['SUMMARY STATISTICS'])
        writer.writerow(['Total Feedback:', total])
        writer.writerow(['Average Rating:', f"{avg_rating:.2f}/5.0"])
        writer.writerow([])
        writer.writerow(['RATING DISTRIBUTION'])
        writer.writerow(['Rating', 'Count'])
        for rating, count in rating_dist:
            writer.writerow([f"{rating} Stars", count])
        writer.writerow([])
        writer.writerow(['CATEGORY DISTRIBUTION'])
        writer.writerow(['Category', 'Count'])
        for category, count in category_dist:
            writer.writerow([category or 'N/A', count])
        writer.writerow([])
        # Detailed feedback data
        writer.writerow(['DETAILED FEEDBACK'])
        writer.writerow(['ID', 'Date', 'Customer', 'Order ID', 'Rating', 'Category',
                       'Feedback', 'Response', 'Responded By', 'Response Date', 'Status'])
        for fb in feedbacks:
            writer.writerow(fb)
        csv_content = output.getvalue()
        # Save to file
        filename = f"customer_feedback_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        filepath = os.path.join(os.getcwd(), filename)
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            f.write(csv_content)
        messagebox.showinfo("Export Success",
                          f"Feedback report exported successfully!\n\n"
                          f"File: {filename}\n"
                          f"Location: {filepath}\n"
                          f"Total Feedback: {total}\n"
                          f"Average Rating: {avg_rating:.2f}/5.0")
    except (OSError, IOError) as e:
        messagebox.showerror("Error", f"Failed to export feedback report: {e}")

def export_feedback_report_pdf(self, parent_dialog):
    """Generate comprehensive feedback analytics report"""
    report_dialog = tk.Toplevel(parent_dialog)
    report_dialog.title("Feedback Analytics Report")
    report_dialog.geometry("900x700")
    report_dialog.transient(parent_dialog)
    report_dialog.grab_set()
    main_frame = ttk.Frame(report_dialog, padding=20)
    main_frame.pack(fill='both', expand=True)
    ttk.Label(main_frame, text="Customer Feedback Analytics",
             font=('Arial', 14, 'bold')).pack(pady=10)
    # Report output
    output_frame = ttk.LabelFrame(main_frame, text="Analytics Report", padding=10)
    output_frame.pack(fill='both', expand=True, pady=10)
    output_text = ScrolledText(output_frame, height=30, width=100, font=('Courier', 9))
    output_text.pack(fill='both', expand=True)
    def generate_report():
        try:
            conn = get_db_connection()
            if not conn:
                return
            cursor = conn.cursor()
            # Get statistics
            cursor.execute("SELECT COUNT(*) FROM customer_feedback")
            total = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM customer_feedback WHERE status = 'Pending'")
            pending = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM customer_feedback WHERE status = 'Responded'")
            responded = cursor.fetchone()[0]
            cursor.execute("SELECT AVG(rating) FROM customer_feedback")
            avg_rating = cursor.fetchone()[0] or 0
            cursor.execute('''
                SELECT rating, COUNT(*) FROM customer_feedback
                GROUP BY rating ORDER BY rating DESC
            ''')
            rating_dist = cursor.fetchall()
            cursor.execute('''
                SELECT category, COUNT(*), AVG(rating)
                FROM customer_feedback
                GROUP BY category
                ORDER BY COUNT(*) DESC
            ''')
            category_stats = cursor.fetchall()
            # Get recent feedback samples
            cursor.execute('''
                SELECT customer_name, rating, category, feedback_text, feedback_date
                FROM customer_feedback
                ORDER BY feedback_date DESC
                LIMIT 5
            ''')
            recent = cursor.fetchall()
            # Response rate
            response_rate = (responded / total * 100) if total > 0 else 0
            conn.close()
            # Generate report
            report = f"""
{'='*90}
                    CUSTOMER FEEDBACK ANALYTICS REPORT
                    Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'='*90}

EXECUTIVE SUMMARY:
-----------------
Total Feedback Received:        {total}
Pending Responses:              {pending}
Completed Responses:            {responded}
Response Rate:                  {response_rate:.1f}%

Overall Customer Satisfaction:  {avg_rating:.2f} / 5.0

RATING DISTRIBUTION:
-------------------
"""
            for rating, count in rating_dist:
                percentage = (count / total * 100) if total > 0 else 0
                bar = '#' * int(percentage / 2)
                report += f"{rating} Stars:  {count:>4} ({percentage:>5.1f}%)  {bar}\n"

            report += f"""

FEEDBACK BY CATEGORY:
--------------------
{'Category':<20} {'Count':>8} {'Avg Rating':>12} {'Percentage':>12}
{'-'*60}
"""
            for category, count, avg_rat in category_stats:
                percentage = (count / total * 100) if total > 0 else 0
                report += f"{(category or 'N/A'):<20} {count:>8} {avg_rat:>12.2f} {percentage:>11.1f}%\n"

            report += """

INSIGHTS & RECOMMENDATIONS:
--------------------------
"""
            # Generate insights based on data
            if avg_rating >= 4.5:
                report += "* Excellent overall satisfaction! Customers are very happy.\n"
            elif avg_rating >= 4.0:
                report += "* Good overall satisfaction with room for improvement.\n"
            elif avg_rating >= 3.0:
                report += "! Average satisfaction. Focus on addressing customer concerns.\n"
            else:
                report += "! Low satisfaction. Immediate action required.\n"

            if pending > 0:
                report += f"! {pending} feedback items need responses. Timely responses improve satisfaction.\n"

            if response_rate < 50:
                report += f"! Low response rate ({response_rate:.1f}%). Aim for >80% response rate.\n"

            # Category-specific insights
            if category_stats:
                lowest_cat = min(category_stats, key=lambda x: x[2])
                report += f"! '{lowest_cat[0]}' has lowest rating ({lowest_cat[2]:.2f}). Priority area for improvement.\n"

            report += """

RECENT FEEDBACK SAMPLES:
-----------------------
"""
            for idx, (cust, rating, cat, fb, date) in enumerate(recent, 1):
                fb_short = fb[:200] + '...' if len(fb) > 200 else fb
                report += f"""
{idx}. {cust or 'Anonymous'} | {rating} stars | {cat} | {date}
   {fb_short}
"""

            report += "\n" + "="*90 + "\n"
            report += "\nACTION ITEMS:\n"
            report += "1. Respond to all pending feedback within 24-48 hours\n"
            report += "2. Address lowest-rated categories with targeted improvements\n"
            report += "3. Follow up with customers who gave 1-2 star ratings\n"
            report += "4. Continue practices that led to 5-star ratings\n"
            report += "5. Monitor trends monthly to track improvement\n"
            output_text.delete('1.0', tk.END)
            output_text.insert('1.0', report)
        except (sqlite3.Error, tk.TclError) as e:
            messagebox.showerror("Error", f"Failed to generate report: {e}")
    generate_report()
    # Export button
    def export_report():
        report_content = output_text.get('1.0', tk.END)
        filename = f"feedback_analytics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        filepath = os.path.join(os.getcwd(), filename)
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(report_content)
            messagebox.showinfo("Export Success",
                              f"Analytics report exported!\n\n"
                              f"File: {filename}\n"
                              f"Location: {filepath}")
        except (OSError, IOError) as e:
            messagebox.showerror("Error", f"Failed to export: {e}")
    btn_frame = ttk.Frame(main_frame)
    btn_frame.pack(fill='x', pady=10)
    ttk.Button(btn_frame, text="Export to File", command=export_report).pack(side='left', padx=5)
    ttk.Button(btn_frame, text="Refresh", command=generate_report).pack(side='left', padx=5)
    ttk.Button(btn_frame, text="Close", command=report_dialog.destroy).pack(side='right', padx=5)

