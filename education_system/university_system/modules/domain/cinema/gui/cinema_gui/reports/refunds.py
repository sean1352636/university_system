"""
Cinema Booking System - Refunds Management

Functions for processing refunds, viewing booking details, and exporting
refund data. Supports cash, card, and student account refund methods
with integration to the university finance system.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from education_system.university_system.infrastructure.database.db import sqlite3
import json
import csv
from datetime import datetime, timedelta

try:
    from education_system.university_system.modules.shared.utils.i18n import get_text as _t
except ImportError:
    def _t(key, default=None):
        return default if default else key.split('.')[-1].replace('_', ' ').title()

from ..database import DB_FILE

# Finance integration
try:
    from education_system.university_system.modules.shared.utils.finance_integration import (
        process_student_finance_account_payment,
        get_student_finance_account_balance,
        record_payment_to_finance
    )
    FINANCE_AVAILABLE = True
except ImportError:
    FINANCE_AVAILABLE = False
    def process_student_finance_account_payment(*args, **kwargs):
        return {'success': False, 'message': 'Finance integration not available'}
    def get_student_finance_account_balance(*args, **kwargs):
        return None
    def record_payment_to_finance(*args, **kwargs):
        return None

# Auth integration
try:
    from education_system.university_system.infrastructure.shared_context import get_auth
    AUTH_AVAILABLE = True
except ImportError:
    AUTH_AVAILABLE = False
    def get_auth():
        return None

# Email integration
try:
    from education_system.university_system.infrastructure.email import send_email
    from education_system.university_system.infrastructure.email.template_utils import render_template
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False
    def send_email(*args, **kwargs):
        return False
    render_template = None

def show_refunds_page(self):
    """Display refunds management interface"""
    self.clear_content()

    # Header
    header_frame = ttk.Frame(self.content_frame, style='Content.TFrame')
    header_frame.pack(fill=tk.X, pady=(0, 10))

    ttk.Label(header_frame, text=_t("cinema.refunds.title"),
             style="Title.TLabel").pack(side=tk.LEFT)

    # Search frame
    search_frame = ttk.LabelFrame(self.content_frame, text=_t("cinema.buttons.search"), padding="10")
    search_frame.pack(fill=tk.X, pady=(0, 10))

    ttk.Label(search_frame, text=_t("cinema.buttons.search_label")).grid(row=0, column=0, sticky=tk.W, padx=5)
    self.refund_search_var = tk.StringVar()
    self.refund_search_var.trace('w', lambda *args: self.refresh_cinema_refunds_list())
    search_entry = ttk.Entry(search_frame, textvariable=self.refund_search_var, width=40)
    search_entry.grid(row=0, column=1, sticky=tk.W, padx=5)

    # Table frame
    table_frame = ttk.Frame(self.content_frame)
    table_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

    # Create treeview with 7 columns
    columns = ('booking_id', 'booking_ref', 'date', 'customer', 'amount', 'payment_method', 'status')
    self.refunds_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=15)

    # Configure columns
    self.refunds_tree.heading('booking_id', text='Booking ID')
    self.refunds_tree.heading('booking_ref', text='Reference')
    self.refunds_tree.heading('date', text='Date')
    self.refunds_tree.heading('customer', text='Customer')
    self.refunds_tree.heading('amount', text='Amount')
    self.refunds_tree.heading('payment_method', text='Payment Method')
    self.refunds_tree.heading('status', text='Status')

    self.refunds_tree.column('booking_id', width=80)
    self.refunds_tree.column('booking_ref', width=150)
    self.refunds_tree.column('date', width=150)
    self.refunds_tree.column('customer', width=200)
    self.refunds_tree.column('amount', width=100)
    self.refunds_tree.column('payment_method', width=120)
    self.refunds_tree.column('status', width=100)

    # Scrollbars
    vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.refunds_tree.yview)
    hsb = ttk.Scrollbar(table_frame, orient="horizontal", command=self.refunds_tree.xview)
    self.refunds_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

    self.refunds_tree.grid(row=0, column=0, sticky=(tk.N, tk.S, tk.E, tk.W))
    vsb.grid(row=0, column=1, sticky=(tk.N, tk.S))
    hsb.grid(row=1, column=0, sticky=(tk.E, tk.W))

    table_frame.grid_rowconfigure(0, weight=1)
    table_frame.grid_columnconfigure(0, weight=1)

    # Buttons frame
    buttons_frame = ttk.Frame(self.content_frame)
    buttons_frame.pack(fill=tk.X)

    ttk.Button(buttons_frame, text=_t("cinema.btn.process_refund"),
              command=self.process_cinema_refund).pack(side=tk.LEFT, padx=5)
    ttk.Button(buttons_frame, text=_t("cinema.members.view_details"),
              command=self.view_cinema_booking_details).pack(side=tk.LEFT, padx=5)
    ttk.Button(buttons_frame, text=_t("cinema.buttons.refresh"),
              command=self.refresh_cinema_refunds_list).pack(side=tk.LEFT, padx=5)
    ttk.Button(buttons_frame, text=_t("cinema.reports.export_to_csv"),
              command=self.export_cinema_refunds_to_csv).pack(side=tk.LEFT, padx=5)

    # Load data
    self.refresh_cinema_refunds_list()

def refresh_cinema_refunds_list(self):
    """Refresh the refunds list with search support"""
    # Clear existing items
    for item in self.refunds_tree.get_children():
        self.refunds_tree.delete(item)

    try:
        search_term = self.refund_search_var.get().lower()

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                b.id,
                b.booking_ref,
                b.booking_time,
                b.customer_name,
                b.customer_email,
                b.total_amount,
                b.payment_method,
                b.status,
                b.payment_status
            FROM bookings b
            ORDER BY b.booking_time DESC
        """)

        bookings = cursor.fetchall()
        conn.close()

        for booking in bookings:
            booking_id, booking_ref, date, customer_name, customer_email, amount, payment_method, status, payment_status = booking

            # Apply search filter
            if search_term:
                searchable = f"{booking_id} {booking_ref} {customer_name or ''} {customer_email or ''} {status}".lower()
                if search_term not in searchable:
                    continue

            # Format date
            if date:
                try:
                    date_obj = datetime.strptime(date, '%Y-%m-%d %H:%M:%S')
                    formatted_date = date_obj.strftime('%Y-%m-%d %H:%M')
                except (ValueError, TypeError):
                    formatted_date = date
            else:
                formatted_date = ''

            # Color code by status
            tag = 'refunded' if status == 'refunded' else 'active'

            self.refunds_tree.insert('', tk.END, values=(
                booking_id,
                booking_ref,
                formatted_date,
                customer_name or customer_email,
                f"\u00a3{amount:.2f}",
                payment_method or 'N/A',
                status or 'active'
            ), tags=(tag,))

        # Configure tags
        self.refunds_tree.tag_configure('refunded', background='#ffcccc')
        self.refunds_tree.tag_configure('active', background='#ccffcc')

    except Exception as e:
        print(f"Error refreshing refunds list: {e}")
        messagebox.showerror(_t("cinema.common.error"), f"Failed to load refunds: {str(e)}")

def process_cinema_refund(self):
    """Process a refund for a cinema booking"""
    # Get selected booking
    selection = self.refunds_tree.selection()
    if not selection:
        messagebox.showwarning(_t("cinema.messages.warnings.select_item"), "Please select a booking to refund.")
        return

    item = self.refunds_tree.item(selection[0])
    values = item['values']
    booking_id = values[0]
    booking_ref = values[1]
    amount_str = values[4]
    status = values[6]

    # Check if already refunded
    if status == 'refunded':
        messagebox.showwarning("Already Refunded", _t("cinema.messages.already_refunded"))
        return

    # Parse amount
    try:
        amount = float(amount_str.replace('\u00a3', '').replace(',', ''))
    except (ValueError, TypeError):
        messagebox.showerror(_t("cinema.common.error"), "Invalid amount format.")
        return

    # Confirm refund
    if not messagebox.askyesno("Confirm Refund",
                               f"Refund \u00a3{amount:.2f} for Booking {booking_ref}?"):
        return

    try:
        # Get customer email
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT customer_email FROM bookings WHERE id = ?", (booking_id,))
        result = cursor.fetchone()
        conn.close()

        if not result:
            messagebox.showerror(_t("cinema.common.error"), "Booking not found.")
            return
        customer_email = result[0]

        # Show refund method dialog
        self.show_cinema_refund_method_dialog(booking_id, booking_ref, amount, customer_email)

    except Exception as e:
        print(f"Error processing cinema refund: {e}")
        messagebox.showerror(_t("cinema.common.error"), f"Failed to process refund: {str(e)}")

def show_cinema_refund_method_dialog(self, booking_id, booking_ref, amount, customer_email):
    """Show dialog to select refund method"""
    dialog = tk.Toplevel(self.root)
    dialog.title("Select Refund Method")
    dialog.geometry("500x400")
    dialog.transient(self.root)
    dialog.grab_set()

    # Center the dialog
    dialog.update_idletasks()
    x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
    y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
    dialog.geometry(f"+{x}+{y}")

    # Header
    ttk.Label(dialog, text="Select Refund Method",
             font=('Arial', 12, 'bold')).pack(pady=10)

    ttk.Label(dialog, text=f"Refund Amount: \u00a3{amount:.2f}").pack(pady=5)

    # Get student_id from booking and show balance if available
    student_id = None
    current_balance = None
    payment_method = None

    if FINANCE_AVAILABLE:
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()

            # Get payment method from booking
            cursor.execute("SELECT payment_method FROM bookings WHERE id = ?", (booking_id,))
            payment_result = cursor.fetchone()
            if payment_result:
                payment_method = payment_result[0]

            # Try to get student_id from email if provided
            if customer_email:
                cursor.execute("SELECT student_id FROM students WHERE email = ? AND email IS NOT NULL AND email != ''",
                             (customer_email,))
                result = cursor.fetchone()
                if result:
                    student_id = result[0]

            conn.close()

            # If we found a student_id, show their balance
            if student_id:
                try:
                    from education_system.university_system.modules.shared.utils.finance_integration import (
                        get_student_finance_account_balance,
                        ensure_student_finance_account_exists
                    )
                    ensure_student_finance_account_exists(student_id)
                    current_balance = get_student_finance_account_balance(student_id)
                    ttk.Label(dialog, text=f"Student ID: {student_id}",
                             foreground='blue').pack(pady=2)
                    ttk.Label(dialog, text=f"Current Account Balance: \u00a3{current_balance:.2f}",
                             foreground='blue').pack(pady=2)
                    new_balance = current_balance + amount
                    ttk.Label(dialog, text=f"New Balance After Refund: \u00a3{new_balance:.2f}",
                             foreground='green').pack(pady=5)
                except Exception as e:
                    print(f"Could not get student balance: {e}")
            elif payment_method == "Student Account":
                # If paid via student account but we can't find student_id, show a note
                ttk.Label(dialog, text=_t("cinema.messages.student_id_not_found"),
                         foreground='orange').pack(pady=5)
                ttk.Label(dialog, text="You will be asked for Student ID if you select Student Account refund",
                         foreground='grey').pack(pady=2)
        except Exception as e:
            print(f"Could not retrieve booking info: {e}")

    # Buttons frame
    buttons_frame = ttk.Frame(dialog)
    buttons_frame.pack(pady=20, fill=tk.BOTH, expand=True)

    def refund_cash():
        dialog.destroy()
        self._complete_cinema_refund(booking_id, booking_ref, amount, 'cash', customer_email, student_id)

    def refund_card():
        dialog.destroy()
        self._complete_cinema_refund(booking_id, booking_ref, amount, 'card', customer_email, student_id)

    def refund_student_account():
        if not FINANCE_AVAILABLE:
            messagebox.showerror(_t("cinema.common.error"), "Finance system not available.")
            return

        # Get student_id - either from auto-detection or manual entry
        final_student_id = student_id
        if not final_student_id:
            final_student_id = simpledialog.askstring("Student ID Required",
                "Enter Student ID for refund to student account:",
                parent=dialog)
            if not final_student_id:
                messagebox.showwarning(_t("cinema.messages.success.cancelled"), "Student ID is required for student account refund.")
                return

            # Verify the student exists
            try:
                from education_system.university_system.modules.shared.utils.finance_integration import (
                    get_student_finance_account_balance,
                    ensure_student_finance_account_exists
                )
                ensure_student_finance_account_exists(final_student_id)
                balance = get_student_finance_account_balance(final_student_id)
                if balance is None:
                    messagebox.showerror(_t("cinema.common.error"), f"Student account not found for ID: {final_student_id}")
                    return
            except Exception as e:
                messagebox.showerror(_t("cinema.common.error"), f"Could not verify student account: {str(e)}")
                return

        dialog.destroy()
        self.add_cinema_refund_to_student_account(booking_id, booking_ref, amount, customer_email, final_student_id)

    # Create buttons
    cash_btn = ttk.Button(buttons_frame, text=_t("cinema.refunds.as_cash"),
                         command=refund_cash, width=30)
    cash_btn.pack(pady=10)

    card_btn = ttk.Button(buttons_frame, text=_t("cinema.refunds.to_card"),
                         command=refund_card, width=30)
    card_btn.pack(pady=10)

    account_btn = ttk.Button(buttons_frame, text=_t("cinema.refunds.to_student_account"),
                            command=refund_student_account, width=30)
    account_btn.pack(pady=10)

    # Only disable if finance system is not available
    # Student ID can be entered manually if not auto-detected
    if not FINANCE_AVAILABLE:
        account_btn.config(state='disabled')

    ttk.Button(buttons_frame, text=_t("cinema.buttons.cancel"),
              command=dialog.destroy, width=30).pack(pady=10)

def _complete_cinema_refund(self, booking_id, booking_ref, amount, refund_method, customer_email, student_id):
    """Complete the refund process (for cash/card)"""
    try:
        # Generate refund reference
        refund_ref = f"CINEMA-REFUND-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        # Update booking status
        cursor.execute("""
            UPDATE bookings
            SET status = 'refunded'
            WHERE id = ?
        """, (booking_id,))

        # Create refund record in cinema_refunds table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cinema_refunds (
                refund_id INTEGER PRIMARY KEY AUTOINCREMENT,
                booking_id INTEGER,
                booking_ref TEXT,
                customer_email TEXT,
                amount DECIMAL(10,2),
                refund_method TEXT,
                refund_reference TEXT,
                refunded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processed_by TEXT,
                FOREIGN KEY (booking_id) REFERENCES bookings(id)
            )
        """)

        # Get processed_by
        processed_by = None
        if AUTH_AVAILABLE:
            try:
                auth = get_auth()
                if auth and hasattr(auth, 'current_user') and auth.current_user:
                    user = auth.current_user
                    processed_by = user.get('username') or user.get('id', '')
            except Exception:
                pass

        cursor.execute("""
            INSERT INTO cinema_refunds
            (booking_id, booking_ref, customer_email, amount, refund_method, refund_reference, processed_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (booking_id, booking_ref, customer_email, amount, refund_method, refund_ref, processed_by))

        conn.commit()
        conn.close()

        # Send receipt
        self.send_cinema_refund_receipt(customer_email, amount, refund_method, refund_ref, booking_ref)

        # Notify finance GUI
        self.notify_cinema_finance_gui(booking_id, amount, refund_method, refund_ref)

        # Refresh list
        self.refresh_cinema_refunds_list()

        messagebox.showinfo(_t("cinema.common.success"),
                          f"Refund processed successfully!\nReference: {refund_ref}")

    except Exception as e:
        print(f"Error completing cinema refund: {e}")
        messagebox.showerror(_t("cinema.common.error"), f"Failed to complete refund: {str(e)}")

def add_cinema_refund_to_student_account(self, booking_id, booking_ref, amount, customer_email, student_id):
    """Add refund amount to student finance account"""
    if not FINANCE_AVAILABLE:
        messagebox.showerror(_t("cinema.common.error"), "Finance system not available.")
        return

    try:
        from education_system.university_system.modules.shared.utils.finance_integration import ensure_student_finance_account_exists
        from education_system.university_system.infrastructure.database.db import get_db_connection, transaction

        # Ensure student account exists
        ensure_student_finance_account_exists(student_id)

        # Generate refund reference
        refund_ref = f"CINEMA-REFUND-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # Update cinema booking
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("UPDATE bookings SET status = 'refunded' WHERE id = ?", (booking_id,))

        # Create refund record
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cinema_refunds (
                refund_id INTEGER PRIMARY KEY AUTOINCREMENT,
                booking_id INTEGER,
                booking_ref TEXT,
                customer_email TEXT,
                amount DECIMAL(10,2),
                refund_method TEXT,
                refund_reference TEXT,
                refunded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processed_by TEXT,
                FOREIGN KEY (booking_id) REFERENCES bookings(id)
            )
        """)

        # Get processed_by
        processed_by = None
        if AUTH_AVAILABLE:
            try:
                auth = get_auth()
                if auth and hasattr(auth, 'current_user') and auth.current_user:
                    user = auth.current_user
                    processed_by = user.get('username') or user.get('id', '')
            except Exception:
                pass

        cursor.execute("""
            INSERT INTO cinema_refunds
            (booking_id, booking_ref, customer_email, amount, refund_method, refund_reference, processed_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (booking_id, booking_ref, customer_email, amount, 'student_account', refund_ref, processed_by))

        conn.commit()
        conn.close()

        # Add to student finance account
        with transaction() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE student_finance_accounts
                SET balance = balance + ?
                WHERE student_id = ?
            """, (amount, student_id))

            # Get new balance and account_id after update
            cursor.execute("SELECT account_id, balance FROM student_finance_accounts WHERE student_id = ?", (student_id,))
            result = cursor.fetchone()
            if result:
                account_id, new_balance = result
            else:
                account_id, new_balance = None, amount

            # Log transaction in student_finance_transactions
            cursor.execute("""
                INSERT INTO student_finance_transactions
                (account_id, student_id, transaction_type, amount, balance_after, description,
                 reference_id, processed_by, created_at)
                VALUES (?, ?, 'credit', ?, ?, ?, ?, ?, ?)
            """, (account_id, student_id, amount, new_balance, f'Cinema refund - {refund_ref}',
                  refund_ref, 'System', datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

        # Send receipt
        self.send_cinema_refund_receipt(customer_email, amount, 'student_account', refund_ref, booking_ref, new_balance)

        # Notify finance GUI
        self.notify_cinema_finance_gui(booking_id, amount, 'student_account', refund_ref)

        # Refresh list
        self.refresh_cinema_refunds_list()

        messagebox.showinfo(_t("cinema.common.success"),
                          f"Refund added to student account!\n"
                          f"Reference: {refund_ref}\n"
                          f"New Balance: \u00a3{new_balance:.2f}")

    except Exception as e:
        print(f"Error adding cinema refund to student account: {e}")
        messagebox.showerror(_t("cinema.common.error"), f"Failed to add refund to account: {str(e)}")

def send_cinema_refund_receipt(self, customer_email, amount, refund_method, refund_ref, booking_ref, new_balance=None):
    """Send refund receipt email to customer"""
    if not EMAIL_AVAILABLE or not customer_email:
        print("Email service not available or no email address, skipping receipt")
        return

    try:
        # Get customer name
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT customer_name FROM bookings WHERE booking_ref = ?", (booking_ref,))
        result = cursor.fetchone()
        conn.close()

        customer_name = result[0] if result else customer_email

        # Format refund method for display
        method_display = {
            'cash': 'Cash',
            'card': 'Card',
            'student_account': 'Student Finance Account'
        }.get(refund_method, refund_method)

        # Balance text for template
        balance_text = ""
        if new_balance is not None:
            balance_text = f"Your new student account balance is: \u00a3{new_balance:.2f}"

        # Render email from template
        subject, body = render_template('commerce/cinema/refund_receipt', {
            'customer_name': customer_name,
            'booking_ref': booking_ref,
            'refund_amount': f"\u00a3{amount:.2f}",
            'refund_method': method_display,
            'refund_ref': refund_ref,
            'refund_date': datetime.now().strftime('%Y-%m-%d %H:%M'),
            'balance_text': balance_text
        })

        # Fallback if template not found
        if not subject or not body:
            subject = f"Cinema Refund Receipt - {refund_ref}"
            body = f"""
Dear {customer_name},

This is to confirm that your cinema booking refund has been processed successfully.

Refund Details:
- Booking Reference: {booking_ref}
- Refund Amount: \u00a3{amount:.2f}
- Refund Method: {method_display}
- Refund Reference: {refund_ref}
- Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}
"""
            if new_balance is not None:
                body += f"\nYour new student account balance is: \u00a3{new_balance:.2f}\n"
            body += """
If you have any questions about this refund, please contact the cinema.

Best regards,
University Cinema
"""

        # Send email
        send_email(
            to_email=customer_email,
            subject=subject,
            body=body
        )

        print(f"Refund receipt sent to {customer_email}")

    except Exception as e:
        print(f"Error sending cinema refund receipt: {e}")

def notify_cinema_finance_gui(self, booking_id, amount, refund_method, refund_ref):
    """Notify finance system about the refund"""
    try:
        from education_system.university_system.infrastructure.database.db import get_db_connection, transaction

        with transaction() as conn:
            cursor = conn.cursor()

            # Create finance_refunds table if not exists
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS finance_refunds (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    refund_reference TEXT UNIQUE,
                    department TEXT,
                    transaction_id TEXT,
                    amount DECIMAL(10,2),
                    refund_method TEXT,
                    refund_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    processed_by TEXT,
                    notes TEXT
                )
            """)

            # Get processed_by
            processed_by = None
            if AUTH_AVAILABLE:
                try:
                    auth = get_auth()
                    if auth and hasattr(auth, 'current_user') and auth.current_user:
                        user = auth.current_user
                        processed_by = user.get('username') or user.get('id', '')
                except Exception:
                    pass

            # Insert refund record
            cursor.execute("""
                INSERT INTO finance_refunds
                (refund_reference, department, transaction_id, amount, refund_method, processed_by, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (refund_ref, 'Cinema', str(booking_id), amount, refund_method, processed_by,
                 'Cinema booking refund'))

        print(f"Finance GUI notified of refund {refund_ref}")

    except Exception as e:
        print(f"Error notifying finance GUI: {e}")

def view_cinema_booking_details(self):
    """View detailed information about a booking"""
    # Get selected booking
    selection = self.refunds_tree.selection()
    if not selection:
        messagebox.showwarning(_t("cinema.messages.warnings.select_item"), "Please select a booking to view.")
        return

    item = self.refunds_tree.item(selection[0])
    values = item['values']
    booking_id = values[0]

    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        # Get booking details
        cursor.execute("""
            SELECT
                b.id,
                b.booking_ref,
                b.customer_name,
                b.customer_email,
                b.customer_phone,
                b.screening_id,
                b.subtotal,
                b.discount_amount,
                b.snacks_total,
                b.snacks_items,
                b.total_amount,
                b.payment_method,
                b.payment_status,
                b.status,
                b.booking_time,
                b.promo_code
            FROM bookings b
            WHERE b.id = ?
        """, (booking_id,))

        booking = cursor.fetchone()

        if not booking:
            messagebox.showerror(_t("cinema.common.error"), "Booking not found.")
            conn.close()
            return

        (bid, booking_ref, customer_name, customer_email, customer_phone,
         screening_id, subtotal, discount_amount, snacks_total, snacks_items,
         total_amount, payment_method, payment_status, status, booking_time, promo_code) = booking

        # Get screening details
        cursor.execute("""
            SELECT m.title, s.show_time
            FROM screenings s
            JOIN movies m ON s.movie_id = m.id
            WHERE s.id = ?
        """, (screening_id,))
        screening = cursor.fetchone()
        movie_title = screening[0] if screening else 'N/A'
        # Parse show_time which contains both date and time (e.g., "2024-01-15 19:30")
        show_datetime = screening[1] if screening else 'N/A'
        if show_datetime and show_datetime != 'N/A':
            try:
                date_part, time_part = show_datetime.split(' ', 1)
                show_date = date_part
                show_time = time_part
            except (ValueError, TypeError):
                show_date = show_datetime
                show_time = ''
        else:
            show_date = 'N/A'
            show_time = 'N/A'

        # Get booked seats
        cursor.execute("""
            SELECT seat_id, ticket_type
            FROM booked_seats
            WHERE booking_id = ?
        """, (booking_id,))
        seats = cursor.fetchall()
        seats_text = "\n".join([f"  Seat {seat[0]} - {seat[1]}" for seat in seats])

        conn.close()

        # Parse snacks items
        snacks_text = ""
        if snacks_items:
            try:
                snacks_list = json.loads(snacks_items)
                snacks_text = _t("cinema.labels.snacks_drinks")
                for snack, qty in snacks_list.items():
                    snacks_text += f"  {snack} x {qty}\n"
            except (ValueError, json.JSONDecodeError):
                snacks_text = f"\nSnacks: {snacks_items}\n"

        # Create details window
        details_window = tk.Toplevel(self.root)
        details_window.title("Booking Details")
        details_window.geometry("600x700")
        details_window.transient(self.root)

        # Create scrollable text widget
        text_frame = ttk.Frame(details_window)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        text_widget = tk.Text(text_frame, wrap=tk.WORD, width=70, height=40)
        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)

        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Build details text
        details = f"""
CINEMA BOOKING DETAILS
{'=' * 50}

Booking Information:
  Booking ID: {bid}
  Booking Reference: {booking_ref}
  Status: {status}
  Booking Time: {booking_time or 'N/A'}

Customer Information:
  Name: {customer_name}
  Email: {customer_email or 'N/A'}
  Phone: {customer_phone or 'N/A'}

Movie & Screening:
  Movie: {movie_title}
  Date: {show_date}
  Time: {show_time}

Seats:
{seats_text}
{snacks_text}

Financial Details:
  Subtotal: \u00a3{subtotal:.2f}
  Discount: \u00a3{discount_amount:.2f}
  Snacks Total: \u00a3{snacks_total:.2f}
  {'─' * 30}
  Total Amount: \u00a3{total_amount:.2f}

  Payment Method: {payment_method or 'N/A'}
  Payment Status: {payment_status}
  Promo Code: {promo_code or 'None'}

{'=' * 50}
"""

        text_widget.insert('1.0', details)
        text_widget.config(state='disabled')

        # Close button
        ttk.Button(details_window, text=_t("cinema.buttons.close"),
                  command=details_window.destroy).pack(pady=10)

    except Exception as e:
        print(f"Error viewing booking details: {e}")
        messagebox.showerror(_t("cinema.common.error"), f"Failed to load details: {str(e)}")

def export_cinema_refunds_to_csv(self):
    """Export refunds data to CSV file"""
    try:
        # Ask for file location
        file_path = filedialog.asksaveasfilename(
            defaultextension='.csv',
            filetypes=[('CSV files', '*.csv'), ('All files', '*.*')],
            initialfile=f'cinema_refunds_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        )

        if not file_path:
            return

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                b.id,
                b.booking_ref,
                b.booking_time,
                b.customer_name,
                b.customer_email,
                b.total_amount,
                b.payment_method,
                b.status
            FROM bookings b
            ORDER BY b.booking_time DESC
        """)

        bookings = cursor.fetchall()
        conn.close()

        # Write to CSV
        with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)

            # Write header
            writer.writerow(['Booking ID', 'Reference', 'Date', 'Customer Name',
                           'Customer Email', 'Amount', 'Payment Method', 'Status'])

            # Write data
            for booking in bookings:
                booking_id, booking_ref, date, customer_name, customer_email, amount, payment_method, status = booking
                writer.writerow([
                    booking_id,
                    booking_ref,
                    date or '',
                    customer_name or '',
                    customer_email or '',
                    f'{amount:.2f}' if amount else '0.00',
                    payment_method or '',
                    status or 'active'
                ])

        messagebox.showinfo(_t("cinema.common.success"),
                          f"Refunds exported successfully to:\n{file_path}")

    except Exception as e:
        print(f"Error exporting refunds to CSV: {e}")
        messagebox.showerror(_t("cinema.common.error"), f"Failed to export refunds: {str(e)}")
