"""
Payment management functions - recording and viewing housing payments.
Handles payment recording, history viewing, and finance integration.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
from education_system.post_18.university_system.infrastructure.database.db import get_connection
from education_system.post_18.university_system.modules.shared.utils.simple_activity_logger import (
    log_activity, log_create, log_read, log_update, log_delete
)
from education_system.post_18.university_system.core.i18n import get_text as _t
from education_system.post_18.university_system.modules.domain.campus.housing.services.housing_accommodation import generate_id

# Import finance integration if available
try:
    from education_system.post_18.university_system.modules.domain.finance.core.account_management import (
        get_student_finance_account_balance,
        process_student_finance_account_payment
    )
    FINANCE_ACCOUNT_AVAILABLE = True
except ImportError:
    FINANCE_ACCOUNT_AVAILABLE = False
def get_student_finance_account_balance(student_id):
        return None
def process_student_finance_account_payment(*args, **kwargs):
        return {'success': False, 'message': 'Finance account service not available'}

# Import email service if available
try:
    from education_system.post_18.university_system.infrastructure.email.template_utils import render_template
    from education_system.post_18.university_system.infrastructure.email.email_service import send_email_as_system
    EMAIL_SERVICE_AVAILABLE = True
except ImportError:
    EMAIL_SERVICE_AVAILABLE = False
def render_template(*args, **kwargs):
        return ("", "")
def send_email_as_system(*args, **kwargs):
        return False

# Import immutable audit logging if available
try:
    from education_system.post_18.university_system.infrastructure.security.immutable_audit_log import (
        AuditAction, log_security_event
    )
    from education_system.post_18.university_system.modules.shared.utils.gui_context import get_gui_context
    IMMUTABLE_AUDIT_AVAILABLE = True

    def safe_log_security_event(*args, **kwargs):
        try:
            log_security_event(*args, **kwargs)
        except Exception as e:
            print(f"Warning: Failed to log security event: {e}")
except ImportError:
    IMMUTABLE_AUDIT_AVAILABLE = False

    def safe_log_security_event(*args, **kwargs):
        pass

# Check if finance GUI is available
try:
    from education_system.post_18.university_system.modules.domain.finance.gui.finance.finance_gui import FinanceGUI
    FINANCE_GUI_AVAILABLE = True
except ImportError:
    FINANCE_GUI_AVAILABLE = False


def show_payments(gui_instance):
    """Show payments interface"""
    gui_instance.clear_content()

    # Header with title and finance button
    header_frame = ttk.Frame(gui_instance.content_frame)
    header_frame.pack(fill='x', pady=(0, 20))

    ttk.Label(header_frame, text="Payment Management",
             font=('Arial', 16, 'bold')).pack(side='left', padx=(0, 20))

    # Button to open Finance Management GUI
    ttk.Button(header_frame, text="📊 Open Finance Management",
              command=lambda: open_finance_gui(gui_instance)).pack(side='left')

    # Create notebook
    notebook = ttk.Notebook(gui_instance.content_frame)
    notebook.pack(fill='both', expand=True)

    # Payment history tab
    history_frame = ttk.Frame(notebook, padding="10")
    notebook.add(history_frame, text="Payment History")
    create_payment_history(gui_instance, history_frame)

    # Record payment tab
    record_frame = ttk.Frame(notebook, padding="10")
    notebook.add(record_frame, text="Record Payment")
    create_payment_form(gui_instance, record_frame)


def create_payment_history(gui_instance, parent):
    """Create payment history view"""
    # Filter frame
    filter_frame = ttk.LabelFrame(parent, text="Filter Payments", padding="10")
    filter_frame.pack(fill='x', pady=(0, 20))

    ttk.Label(filter_frame, text="Student ID:").grid(row=0, column=0, sticky='w')
    gui_instance.payment_student_filter = ttk.Entry(filter_frame, width=20)
    gui_instance.payment_student_filter.grid(row=0, column=1, padx=10)

    ttk.Button(filter_frame, text="Filter",
              command=lambda: refresh_payment_history(gui_instance)).grid(row=0, column=2, padx=10)
    ttk.Button(filter_frame, text="Show All",
              command=lambda: show_all_payments(gui_instance)).grid(row=0, column=3, padx=5)

    # Payments list
    list_frame = ttk.Frame(parent)
    list_frame.pack(fill='both', expand=True)

    columns = ('Payment ID', 'Student', 'Amount', 'Date', 'Method', 'Period', 'Status')
    gui_instance.payments_tree = ttk.Treeview(list_frame, columns=columns, show='headings')

    for col in columns:
        gui_instance.payments_tree.heading(col, text=col)
        if col == 'Amount':
            gui_instance.payments_tree.column(col, width=100, anchor='e')
        else:
            gui_instance.payments_tree.column(col, width=120)

    # Scrollbars
    v_scroll = ttk.Scrollbar(list_frame, orient='vertical', command=gui_instance.payments_tree.yview)
    h_scroll = ttk.Scrollbar(list_frame, orient='horizontal', command=gui_instance.payments_tree.xview)
    gui_instance.payments_tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

    gui_instance.payments_tree.pack(side='left', fill='both', expand=True)
    v_scroll.pack(side='right', fill='y')

    # Load recent payments
    show_all_payments(gui_instance)


def refresh_payment_history(gui_instance):
    """Refresh payment history with filter"""
    student_filter = gui_instance.payment_student_filter.get().strip()

    for item in gui_instance.payments_tree.get_children():
        gui_instance.payments_tree.delete(item)

    try:
        conn = get_connection()
        cursor = conn.cursor()

        if student_filter:
            cursor.execute('''
            SELECT p.source_payment_id, s.first_name, s.last_name, p.amount, p.payment_date,
                   p.payment_method, p.payment_period_start, p.payment_period_end, p.status
            FROM payments p
            JOIN students s ON p.student_id = s.student_id
            WHERE p.source_type = 'housing'
              AND (p.student_id LIKE ? OR s.first_name LIKE ? OR s.last_name LIKE ?)
            ORDER BY p.payment_date DESC
            LIMIT 100
            ''', (f'%{student_filter}%', f'%{student_filter}%', f'%{student_filter}%'))
        else:
            cursor.execute('''
            SELECT p.source_payment_id, s.first_name, s.last_name, p.amount, p.payment_date,
                   p.payment_method, p.payment_period_start, p.payment_period_end, p.status
            FROM payments p
            JOIN students s ON p.student_id = s.student_id
            WHERE p.source_type = 'housing'
            ORDER BY p.payment_date DESC
            LIMIT 50
            ''')

        payments = cursor.fetchall()

        for payment in payments:
            student_name = f"{payment[1]} {payment[2]}"
            period = f"{payment[6]} to {payment[7]}"

            gui_instance.payments_tree.insert('', 'end', values=(
                payment[0], student_name, f"£{payment[3]:.2f}", payment[4],
                payment[5], period, payment[8]
            ))

        conn.close()

    except Exception as e:
        messagebox.showerror("Error", f"Failed to load payments: {str(e)}")


def show_all_payments(gui_instance):
    """Show all recent payments"""
    gui_instance.payment_student_filter.delete(0, tk.END)
    refresh_payment_history(gui_instance)


def create_payment_form(gui_instance, parent):
    """Create payment recording form"""
    # Assignment selection
    assign_frame = ttk.LabelFrame(parent, text="Select Assignment", padding="10")
    assign_frame.pack(fill='x', pady=(0, 20))

    ttk.Label(assign_frame, text="Active Assignment:").grid(row=0, column=0, sticky='w')
    gui_instance.assignment_combo = ttk.Combobox(assign_frame, width=50)
    gui_instance.assignment_combo.grid(row=0, column=1, padx=10)

    ttk.Button(assign_frame, text="Refresh",
              command=lambda: load_active_assignments_for_payment(gui_instance)).grid(row=0, column=2, padx=10)

    load_active_assignments_for_payment(gui_instance)

    # Payment details
    payment_frame = ttk.LabelFrame(parent, text="Payment Details", padding="10")
    payment_frame.pack(fill='x', pady=(0, 20))

    ttk.Label(payment_frame, text="Payment Type:").grid(row=0, column=0, sticky='w')
    payment_types = ["Rent", "Deposit", "Damage Charge", "Late Fee", "Other"]
    gui_instance.payment_type_combo = ttk.Combobox(
        payment_frame, width=20, values=payment_types, state='readonly',
    )
    gui_instance.payment_type_combo.grid(row=0, column=1, padx=10)
    gui_instance.payment_type_combo.set("Rent")

    ttk.Label(payment_frame, text="Amount:").grid(row=1, column=0, sticky='w')
    gui_instance.payment_amount_entry = ttk.Entry(payment_frame, width=20)
    gui_instance.payment_amount_entry.grid(row=1, column=1, padx=10)

    ttk.Label(payment_frame, text="Payment Method:").grid(row=2, column=0, sticky='w')
    payment_methods = ["Credit Card", "Bank Transfer", "Cash", "Check", "Other"]
    if FINANCE_ACCOUNT_AVAILABLE:
        payment_methods.insert(0, "Student Finance Account")
    gui_instance.payment_method_combo = ttk.Combobox(payment_frame, width=20, values=payment_methods)
    gui_instance.payment_method_combo.grid(row=2, column=1, padx=10)

    ttk.Label(payment_frame, text="Transaction Reference:").grid(row=3, column=0, sticky='w')
    gui_instance.transaction_ref_entry = ttk.Entry(payment_frame, width=30)
    gui_instance.transaction_ref_entry.grid(row=3, column=1, padx=10)

    # Payment period — only meaningful for Rent. Deposit / damage / late fee
    # leave the entries disabled and store NULL period dates.
    period_frame = ttk.LabelFrame(parent, text="Payment Period (Rent only)", padding="10")
    period_frame.pack(fill='x', pady=(0, 20))

    ttk.Label(period_frame, text="Period Start:").grid(row=0, column=0, sticky='w')
    gui_instance.period_start_entry = ttk.Entry(period_frame, width=20)
    gui_instance.period_start_entry.grid(row=0, column=1, padx=10)
    gui_instance.period_start_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))

    ttk.Label(period_frame, text="Period End:").grid(row=0, column=2, sticky='w', padx=(20, 0))
    gui_instance.period_end_entry = ttk.Entry(period_frame, width=20)
    gui_instance.period_end_entry.grid(row=0, column=3, padx=10)
    next_month = datetime.now().replace(day=28) + timedelta(days=4)
    end_of_month = next_month - timedelta(days=next_month.day)
    gui_instance.period_end_entry.insert(0, end_of_month.strftime('%Y-%m-%d'))

    def _sync_period_state(*_):
        is_rent = gui_instance.payment_type_combo.get() == 'Rent'
        state = 'normal' if is_rent else 'disabled'
        gui_instance.period_start_entry.config(state=state)
        gui_instance.period_end_entry.config(state=state)
    gui_instance.payment_type_combo.bind('<<ComboboxSelected>>', _sync_period_state)
    _sync_period_state()

    # Buttons frame
    buttons_frame = ttk.Frame(parent)
    buttons_frame.pack(pady=20)

    ttk.Button(buttons_frame, text="Record Payment",
              command=lambda: record_payment(gui_instance)).pack(side='left', padx=5)

    if FINANCE_GUI_AVAILABLE:
        ttk.Button(buttons_frame, text="View in Finance System",
                  command=lambda: open_finance_gui(gui_instance)).pack(side='left', padx=5)


def load_active_assignments_for_payment(gui_instance):
    """Load active assignments for payment selection"""
    # Import from assignment_manager
    from education_system.post_18.university_system.modules.domain.campus.housing.gui.housing_accommodation_gui.assignment_manager import load_active_assignments
    load_active_assignments(gui_instance)


def record_payment(gui_instance):
    """Record a new payment"""
    try:
        assignment_text = gui_instance.assignment_combo.get()
        amount_text = gui_instance.payment_amount_entry.get().strip()
        payment_method = gui_instance.payment_method_combo.get()
        transaction_ref = gui_instance.transaction_ref_entry.get().strip() or None
        payment_type = getattr(gui_instance, 'payment_type_combo', None)
        payment_type = payment_type.get() if payment_type else 'Rent'
        if not payment_type:
            payment_type = 'Rent'
        # Period is only required for Rent. For other types we store NULL so
        # reports don't average non-period money into rent periods.
        if payment_type == 'Rent':
            period_start = gui_instance.period_start_entry.get().strip()
            period_end = gui_instance.period_end_entry.get().strip()
        else:
            period_start = None
            period_end = None

        required = [assignment_text, amount_text, payment_method]
        if payment_type == 'Rent':
            required += [period_start, period_end]
        if not all(required):
            messagebox.showerror("Error", "Please fill in all required fields")
            return

        # Extract assignment ID from combo text
        if not assignment_text or '(' not in assignment_text:
            messagebox.showerror("Error", "Please select an assignment")
            return

        student_id = assignment_text.split('(')[1].split(')')[0]

        # Get assignment_id
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
        SELECT assignment_id FROM housing_assignments
        WHERE student_id = ? AND status = 'Active'
        ''', (student_id,))

        result = cursor.fetchone()
        if not result:
            messagebox.showerror("Error", "Assignment not found")
            conn.close()
            return

        assignment_id = result[0]

        # Validate amount
        try:
            amount = float(amount_text)
            if amount <= 0:
                raise ValueError()
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid payment amount")
            conn.close()
            return

        # Validate dates (Rent only).
        if payment_type == 'Rent':
            try:
                datetime.strptime(period_start, '%Y-%m-%d')
                datetime.strptime(period_end, '%Y-%m-%d')
            except ValueError:
                messagebox.showerror("Error", "Please enter valid dates (YYYY-MM-DD)")
                conn.close()
                return

        # Handle Student Finance Account payment
        finance_account_used = False
        low_balance_email_sent = False

        if payment_method == "Student Finance Account" and FINANCE_ACCOUNT_AVAILABLE:
            # Check balance first
            current_balance = get_student_finance_account_balance(student_id)
            if current_balance is None:
                messagebox.showerror("Error",
                    f"No finance account found for student {student_id}.\n"
                    "Please create a finance account first or use a different payment method.")
                conn.close()
                return

            if current_balance < amount:
                messagebox.showerror("Insufficient Balance",
                    f"Student finance account balance is insufficient.\n\n"
                    f"Current Balance: £{current_balance:.2f}\n"
                    f"Required Amount: £{amount:.2f}\n\n"
                    f"Please top up the account or use a different payment method.")
                conn.close()
                return

            # Process the payment from finance account
            processed_by = gui_instance.auth.current_user.get('username', 'System')
            description = (
                f"Housing {payment_type} payment for period {period_start} to {period_end}"
                if payment_type == 'Rent'
                else f"Housing {payment_type} payment"
            )
            payment_result = process_student_finance_account_payment(
                student_id=student_id,
                amount=amount,
                description=description,
                transaction_source="Housing",
                transaction_ref=f"{payment_type.upper().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                processed_by=processed_by,
                check_balance=True,
                send_low_balance_alert=True
            )

            if not payment_result['success']:
                messagebox.showerror("Payment Failed", payment_result['message'])
                conn.close()
                return

            finance_account_used = True
            low_balance_email_sent = payment_result.get('email_sent', False)
            transaction_ref = payment_result.get('transaction_id', transaction_ref)

        # Create payment record
        payment_id = generate_id('PAY')
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
        INSERT INTO payments (
            source_payment_id, source_type, reference_id, reference_type,
            student_id, amount, payment_date, payment_method,
            payment_reference, payment_type,
            payment_period_start, payment_period_end, status,
            processed_by, created_at, updated_at
        ) VALUES (?, 'housing', ?, 'assignment', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            payment_id, assignment_id, student_id, amount, timestamp, payment_method,
            transaction_ref, payment_type, period_start, period_end, 'Completed',
            gui_instance.auth.current_user['username'], timestamp, timestamp
        ))
        payment_row_id = cursor.lastrowid

        # Deposit-specific side effects mirror the CLI: stamp the 30-day TDP
        # deadline on the assignment and move the deposit lifecycle into Held.
        if payment_type == 'Deposit':
            try:
                from education_system.post_18.university_system.modules.domain.campus.housing.services.housing_accommodation.tdp import (
                    set_deposit_deadline_if_unset,
                )
                set_deposit_deadline_if_unset(cursor, assignment_id, timestamp)
            except Exception as _e:
                import logging
                logging.getLogger(__name__).warning("TDP deadline stamp failed: %s", _e)
            try:
                from education_system.post_18.university_system.modules.domain.campus.housing.services.housing_accommodation import deposit_state
                if deposit_state.current_state(cursor, assignment_id) is None:
                    deposit_state.transition(
                        cursor, assignment_id, deposit_state.HELD,
                        reason='deposit received (GUI)',
                        actor=gui_instance.auth.current_user.get('username', 'housing'),
                    )
            except Exception as _e:
                import logging
                logging.getLogger(__name__).warning("deposit state set failed: %s", _e)

        # Get student details for email
        cursor.execute('''
        SELECT s.first_name, s.last_name, s.email_address, r.room_number, b.building_name
        FROM students s
        JOIN housing_assignments a ON s.student_id = a.student_id
        JOIN housing_rooms r ON a.room_id = r.room_id
        JOIN housing_buildings b ON r.building_id = b.building_id
        WHERE a.assignment_id = ?
        ''', (assignment_id,))

        student_info = cursor.fetchone()

        conn.commit()
        conn.close()

        # Auto-post to GL (never raises)
        try:
            from education_system.post_18.university_system.modules.domain.finance.ledger import notify_ledger
            notify_ledger('payment', payment_row_id,
                          posted_by=gui_instance.auth.current_user.get('username', 'housing'))
        except Exception as _e:
            import logging
            logging.getLogger(__name__).warning("ledger hook failed: %s", _e)

        # Immutable audit log for payment creation
        if IMMUTABLE_AUDIT_AVAILABLE:
            admin_user_id, session_id = get_gui_context(gui_instance.auth)
            safe_log_security_event(
                action=AuditAction.RECORD_CREATE,
                user_id=admin_user_id,
                resource_type='housing_payment',
                resource_id=payment_id,
                session_id=session_id,
                details={
                    'student_id': student_id,
                    'assignment_id': assignment_id,
                    'amount': amount,
                    'payment_type': payment_type,
                    'payment_method': payment_method,
                    'period': (f"{period_start} to {period_end}"
                               if payment_type == 'Rent' else None),
                    'finance_account_used': finance_account_used
                }
            )

        # Send email confirmation if available
        email_sent = False
        email_error = None

        if EMAIL_SERVICE_AVAILABLE and student_info and student_info[2]:  # Check if email exists
            try:
                student_name = f"{student_info[0]} {student_info[1]}"
                student_email = student_info[2]
                room_number = student_info[3]
                building_name = student_info[4]

                email_subject, email_body = render_template('housing_payment_confirmation', {
                    'student_name': student_name,
                    'payment_id': payment_id,
                    'amount': f"{amount:.2f}",
                    'timestamp': timestamp,
                    'payment_method': payment_method,
                    'transaction_ref': transaction_ref or 'N/A',
                    'period_start': period_start,
                    'period_end': period_end,
                    'building_name': building_name,
                    'room_number': room_number
                })

                # Attempt to send email
                send_email_as_system(
                    student_email,
                    email_subject,
                    email_body,
                    system_name="Housing Administration"
                )
                email_sent = True
                print(f"✓ Payment confirmation email sent to {student_email}")

            except Exception as e:
                email_error = str(e)
                print(f"✗ Failed to send email confirmation: {email_error}")

        # Build success message
        base_msg = (
            f"✓ Payment recorded successfully!\n\n"
            f"Payment ID: {payment_id}\n"
            f"Type: {payment_type}\n"
            f"Amount: £{amount:.2f}"
        )

        # Add finance account info if used
        if finance_account_used:
            new_balance = payment_result.get('new_balance', 0)
            base_msg += f"\n\n✓ Deducted from Student Finance Account\nNew Balance: £{new_balance:.2f}"
            if low_balance_email_sent:
                base_msg += "\n\n⚠ Low balance alert email sent to student"

        # Show immediate confirmation dialog with email status
        if email_sent:
            messagebox.showinfo(
                "Payment Recorded - Email Sent",
                f"{base_msg}\n\n✓ Email confirmation sent to:\n{student_email}"
            )
        elif EMAIL_SERVICE_AVAILABLE and student_info and student_info[2]:
            # Email service available but failed
            messagebox.showerror(
                "Payment Recorded - Email Failed",
                f"{base_msg}\n\n✗ Failed to send email confirmation:\n{email_error}\n\n"
                f"Please notify the student manually."
            )
        elif student_info and not student_info[2]:
            # No email address on file
            messagebox.showwarning(
                "Payment Recorded - No Email",
                f"{base_msg}\n\n⚠ No email address on file for this student.\n"
                f"Please notify the student manually."
            )
        else:
            # Email service not available
            messagebox.showinfo(
                "Payment Recorded",
                f"{base_msg}\n\nNote: Email service is not available."
            )

        # Clear form
        gui_instance.assignment_combo.set("")
        gui_instance.payment_amount_entry.delete(0, tk.END)
        gui_instance.payment_method_combo.set("")
        gui_instance.transaction_ref_entry.delete(0, tk.END)
        # Period entries may have been disabled for non-Rent — enable to reset
        # them, then restore the right state based on the (now-default) type.
        for entry in (gui_instance.period_start_entry, gui_instance.period_end_entry):
            entry.config(state='normal')
            entry.delete(0, tk.END)
        gui_instance.period_start_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
        next_month = datetime.now().replace(day=28) + timedelta(days=4)
        end_of_month = next_month - timedelta(days=next_month.day)
        gui_instance.period_end_entry.insert(0, end_of_month.strftime('%Y-%m-%d'))
        if hasattr(gui_instance, 'payment_type_combo'):
            gui_instance.payment_type_combo.set('Rent')
            gui_instance.payment_type_combo.event_generate('<<ComboboxSelected>>')

        # Refresh payment history
        refresh_payment_history(gui_instance)

    except Exception as e:
        messagebox.showerror("Error", f"Failed to record payment: {str(e)}")


def open_finance_gui(gui_instance):
    """Open the Finance Management GUI"""
    if not FINANCE_GUI_AVAILABLE:
        messagebox.showinfo("Finance GUI Unavailable",
                          "The Finance Management GUI is not available.\n"
                          "Please ensure the finance module is properly installed.")
        return

    try:
        # Create new window for finance GUI
        finance_window = tk.Toplevel(gui_instance.root)
        finance_window.title("Finance Management System")
        finance_window.geometry("1400x800")

        # Initialize Finance GUI in the new window
        # FinanceGUI sets up the dashboard automatically during __init__
        FinanceGUI(finance_window, gui_instance.auth)

    except Exception as e:
        messagebox.showerror("Error", f"Failed to open Finance GUI: {str(e)}")
