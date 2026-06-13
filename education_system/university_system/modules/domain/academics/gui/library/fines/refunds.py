"""
Library Fines Management - Refund workflow (search, details, processing, email).
"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from education_system.university_system.core.i18n import get_text as _

from education_system.university_system.modules.domain.academics.gui.library.fines.constants import (
    ORIGINAL_LIBRARY_AVAILABLE,
    FINANCE_ACCOUNT_AVAILABLE,
    EMAIL_SERVICE_AVAILABLE,
    send_email_as_system,
)

try:
    from education_system.university_system.modules.domain.academics.services.library.database import (
        get_db_connection, log_audit_event,
    )
    from education_system.university_system.modules.domain.academics.services.library.settings import get_current_user_id
except ImportError:
    pass

try:
    from education_system.university_system.modules.shared.utils.finance_integration import (
        get_student_finance_account_balance,
        ensure_student_finance_account_exists,
        top_up_student_finance_account,
    )
except ImportError:
    pass


def refund_fine_dialog(self):
    """Show dialog to process a fine refund - with user selection"""
    print("\n" + "="*60)
    print("REFUND FINE DIALOG - Starting...")
    print("="*60)

    # Create refund dialog with user search
    refund_main_dialog = tk.Toplevel()
    refund_main_dialog.title("Refund Library Fines")
    refund_main_dialog.geometry("1000x750")
    refund_main_dialog.transient(self.master)
    refund_main_dialog.grab_set()

    print("Dialog window created")

    # Header
    header_frame = ttk.Frame(refund_main_dialog)
    header_frame.pack(fill=tk.X, padx=10, pady=10)
    ttk.Label(header_frame, text="Library Fine Refund System",
     font=('Arial', 16, 'bold')).pack()
    ttk.Label(header_frame, text="Search for users with paid fines and process refunds",
     font=('Arial', 10)).pack()

    # User search section
    search_frame = ttk.LabelFrame(refund_main_dialog, text="Search for User", padding=10)
    search_frame.pack(fill=tk.X, padx=10, pady=10)

    search_row = ttk.Frame(search_frame)
    search_row.pack(fill=tk.X)

    ttk.Label(search_row, text="Student ID or Name:", font=('Arial', 10)).pack(side=tk.LEFT, padx=5)
    search_var = tk.StringVar()
    search_entry = ttk.Entry(search_row, textvariable=search_var, width=30)
    search_entry.pack(side=tk.LEFT, padx=5)

    # Users list with paid fines
    users_frame = ttk.LabelFrame(refund_main_dialog, text="Users with Paid Fines", padding=10)
    users_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    columns = ('User ID', 'Name', 'Email', 'Total Paid', 'Total Refunded', 'Available', 'Payments')
    users_tree = ttk.Treeview(users_frame, columns=columns, show='headings', height=12)

    for col in columns:
        users_tree.heading(col, text=col)
    users_tree.column('User ID', width=100, anchor='center')
    users_tree.column('Name', width=180)
    users_tree.column('Email', width=200)
    users_tree.column('Total Paid', width=100, anchor='e')
    users_tree.column('Total Refunded', width=110, anchor='e')
    users_tree.column('Available', width=100, anchor='e')
    users_tree.column('Payments', width=80, anchor='center')

    users_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def load_users_with_paid_fines(search_term=""):
        """Load all users who have paid fines"""
        for item in users_tree.get_children():
            users_tree.delete(item)

        if not ORIGINAL_LIBRARY_AVAILABLE:
            print("ERROR: Library module not available")
            messagebox.showerror(_("common.error"), "Library database module is not available.\nPlease ensure all dependencies are installed.", parent=refund_main_dialog)
            return

        try:
            conn = get_db_connection()
            if not conn:
                print("ERROR: Could not get database connection")
                messagebox.showerror(_("common.error"), "Database connection failed", parent=refund_main_dialog)
                return

            cursor = conn.cursor()

            print(f"Loading users with paid fines (search: '{search_term}')...")

            # Build search query
            if search_term:
                cursor.execute('''
                    SELECT p.student_id,
                           s.first_name, s.last_name, s.email_address,
                           SUM(p.amount) as total_paid,
                           COALESCE((SELECT SUM(ur.amount) FROM unified_refunds ur
                                     WHERE ur.student_id = p.student_id AND ur.source_type = 'library'), 0) as total_refunded,
                           COUNT(DISTINCT p.payment_id) as payment_count
                    FROM payments p
                    JOIN students s ON p.student_id = s.student_id
                    WHERE p.source_type = 'library'
                    AND p.status = 'completed'
                    AND (p.student_id LIKE ? OR s.first_name LIKE ? OR s.last_name LIKE ? OR s.email_address LIKE ?)
                    GROUP BY p.student_id, s.first_name, s.last_name, s.email_address
                    HAVING (total_paid - total_refunded) > 0
                    ORDER BY s.last_name, s.first_name
                ''', (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'))
            else:
                cursor.execute('''
                    SELECT p.student_id,
                           s.first_name, s.last_name, s.email_address,
                           SUM(p.amount) as total_paid,
                           COALESCE((SELECT SUM(ur.amount) FROM unified_refunds ur
                                     WHERE ur.student_id = p.student_id AND ur.source_type = 'library'), 0) as total_refunded,
                           COUNT(DISTINCT p.payment_id) as payment_count
                    FROM payments p
                    JOIN students s ON p.student_id = s.student_id
                    WHERE p.source_type = 'library'
                    AND p.status = 'completed'
                    GROUP BY p.student_id, s.first_name, s.last_name, s.email_address
                    HAVING (total_paid - total_refunded) > 0
                    ORDER BY s.last_name, s.first_name
                ''')

            users = cursor.fetchall()
            conn.close()

            print(f"Query returned {len(users)} users")

            if not users:
                print("WARNING: No users with paid fines found!")
                messagebox.showinfo("No Data", "No users with paid fines found in the database.", parent=refund_main_dialog)
                return

            for user_id, first_name, last_name, email, total_paid, total_refunded, payment_count in users:
                full_name = f"{first_name} {last_name}"
                available = total_paid - total_refunded
                print(f"  Adding user: {user_id} - {full_name} - {payment_count} payments, \u00a3{available:.2f} available")
                users_tree.insert('', 'end', values=(
                    user_id, full_name, email or 'N/A',
                    f"\u00a3{total_paid:.2f}", f"\u00a3{total_refunded:.2f}", f"\u00a3{available:.2f}",
                    payment_count
                ))

            print(f"Successfully loaded {len(users)} users into tree")

        except Exception as e:
            print(f"EXCEPTION in load_users_with_paid_fines: {e}")
            import traceback
            traceback.print_exc()
            messagebox.showerror(_("common.error"), f"Failed to load users: {str(e)}", parent=refund_main_dialog)

    def search_users():
        search_term = search_var.get().strip()
        load_users_with_paid_fines(search_term)

    def show_user_refund_details():
        selection = users_tree.selection()
        if not selection:
            messagebox.showwarning(_("common.warning"), "Please select a user first", parent=refund_main_dialog)
            return

        user_id = users_tree.item(selection[0])['values'][0]
        refund_main_dialog.destroy()
        self._show_user_refund_details(user_id)

    ttk.Button(search_row, text="Search", command=search_users).pack(side=tk.LEFT, padx=5)
    ttk.Button(search_row, text="Show All", command=lambda: load_users_with_paid_fines("")).pack(side=tk.LEFT, padx=5)

    # Buttons
    btn_frame = ttk.Frame(refund_main_dialog)
    btn_frame.pack(fill=tk.X, padx=10, pady=10)

    ttk.Button(btn_frame, text="View Refund Details", command=show_user_refund_details,
      style='Accent.TButton').pack(side=tk.LEFT, padx=5)
    ttk.Button(btn_frame, text=_("common.close"), command=refund_main_dialog.destroy).pack(side=tk.RIGHT, padx=5)

    # Load users on start
    print("About to load users with paid fines...")
    load_users_with_paid_fines()
    print("Finished initial load")
    search_entry.focus()


def _show_user_refund_details(self, user_id):
    """Show refund details dialog for a specific user"""
    print(f"\n_show_user_refund_details called for user_id: {user_id}")
    print(f"ORIGINAL_LIBRARY_AVAILABLE: {ORIGINAL_LIBRARY_AVAILABLE}")

    try:
        if ORIGINAL_LIBRARY_AVAILABLE:
            print("Attempting to connect to database...")
            conn = get_db_connection()
            if not conn:
                print("ERROR: Database connection failed")
                messagebox.showerror(_("common.error"), "Database connection unavailable")
                return

            cursor = conn.cursor()
            print("Database connection successful")

            # Get user's paid fines that can be refunded from payments table
            print(f"Querying payments for user {user_id}...")
            cursor.execute('''
                SELECT p.payment_id, p.reference_id, NULL as book_id, p.notes,
                       p.amount,  p.payment_method, p.payment_date,
                       COALESCE((SELECT SUM(ur.amount) FROM unified_refunds ur
                                 WHERE ur.source_type = 'library'
                                 AND ur.reference_id = CAST(p.payment_id AS TEXT)), 0) as refund_amount
                FROM payments p
                WHERE p.student_id = ?
                AND p.source_type = 'library'
                AND p.status = 'completed'
                AND (p.amount - COALESCE((SELECT SUM(ur.amount) FROM unified_refunds ur
                                          WHERE ur.source_type = 'library'
                                          AND ur.reference_id = CAST(p.payment_id AS TEXT)), 0)) > 0
                ORDER BY p.payment_date DESC
            ''', (user_id,))

            paid_fines = cursor.fetchall()
            print(f"Query returned {len(paid_fines)} refundable payments")

            # Get user name
            cursor.execute('SELECT first_name, last_name FROM students WHERE student_id = ?', (user_id,))
            user_info = cursor.fetchone()
            user_name = f"{user_info[0]} {user_info[1]}" if user_info else user_id
            print(f"User name: {user_name}")

            conn.close()

            if not paid_fines:
                print("WARNING: No refundable payments found for this user")
                messagebox.showinfo("No Paid Fines", "This user has no paid fines available to refund")
                return

            # Create refund dialog
            refund_dialog = tk.Toplevel()
            refund_dialog.title("Refund Library Fine")
            refund_dialog.geometry("900x700")
            refund_dialog.transient(self.master)
            refund_dialog.grab_set()

            # Header
            header_frame = ttk.Frame(refund_dialog)
            header_frame.pack(fill=tk.X, padx=10, pady=10)
            ttk.Label(header_frame, text="Refund Library Fine",
                     font=('Arial', 14, 'bold')).pack()
            ttk.Label(header_frame, text=f"User: {user_name} (ID: {user_id})",
                     font=('Arial', 11)).pack()

            # Paid fines selection
            selection_frame = ttk.LabelFrame(refund_dialog, text="Select Paid Fine to Refund", padding=10)
            selection_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            columns = ('Payment ID', 'Loan ID', 'Book Title', 'Paid Amount', 'Refunded', 'Available', 'Method', 'Date')
            fines_tree = ttk.Treeview(selection_frame, columns=columns, show='headings', height=8)

            for col in columns:
                fines_tree.heading(col, text=col)
            fines_tree.column('Payment ID', width=80, anchor='center')
            fines_tree.column('Loan ID', width=80, anchor='center')
            fines_tree.column('Book Title', width=200)
            fines_tree.column('Paid Amount', width=90, anchor='e')
            fines_tree.column('Refunded', width=80, anchor='e')
            fines_tree.column('Available', width=80, anchor='e')
            fines_tree.column('Method', width=120)
            fines_tree.column('Date', width=150, anchor='center')

            print(f"Populating tree with {len(paid_fines)} payments...")
            for payment_id, loan_id, book_id, notes, payment_amount, payment_method, payment_date, refund_amount in paid_fines:
                refund_amount = refund_amount or 0.0
                available = payment_amount - refund_amount
                # Extract book title from notes field
                book_title = notes[:30] if notes else 'N/A'
                print(f"  - Payment {payment_id}: \u00a3{available:.2f} available")
                fines_tree.insert('', 'end', values=(
                    payment_id, loan_id, book_title,
                    f"\u00a3{payment_amount:.2f}", f"\u00a3{refund_amount:.2f}", f"\u00a3{available:.2f}",
                    payment_method, payment_date
                ))

            fines_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            print("Tree populated and packed successfully")

            # Refund details frame
            details_frame = ttk.LabelFrame(refund_dialog, text="Refund Details", padding=10)
            details_frame.pack(fill=tk.X, padx=10, pady=10)

            ttk.Label(details_frame, text="Refund Amount (\u00a3):").grid(row=0, column=0, sticky='w', pady=5)
            refund_amount_var = tk.StringVar()
            ttk.Entry(details_frame, textvariable=refund_amount_var, width=15).grid(row=0, column=1, sticky='w', pady=5)

            ttk.Label(details_frame, text="Refund Method:").grid(row=1, column=0, sticky='w', pady=5)
            refund_method_var = tk.StringVar(value="Cash")
            method_options = ["Cash", "Card", "Student Finance Account"]
            method_combo = ttk.Combobox(details_frame, textvariable=refund_method_var,
                                       values=method_options, state='readonly', width=22)
            method_combo.grid(row=1, column=1, sticky='w', pady=5)

            ttk.Label(details_frame, text="Refund Reason:").grid(row=2, column=0, sticky='w', pady=5)
            reason_text = tk.Text(details_frame, height=3, width=35)
            reason_text.grid(row=2, column=1, pady=5)

            # Show finance account balance if available
            if FINANCE_ACCOUNT_AVAILABLE:
                balance = get_student_finance_account_balance(user_id)
                if balance is not None:
                    ttk.Label(details_frame, text=f"\U0001f4b0 Current Finance Account Balance: \u00a3{balance:.2f}",
                             font=('Arial', 9), foreground='green').grid(row=3, column=0, columnspan=2, pady=5)

            def process_refund():
                selected = fines_tree.selection()
                if not selected:
                    messagebox.showwarning(_("common.warning"), "Please select a paid fine to refund", parent=refund_dialog)
                    return

                refund_amount_str = refund_amount_var.get().strip()
                refund_method = refund_method_var.get()
                refund_reason = reason_text.get("1.0", tk.END).strip()

                if not refund_amount_str or not refund_reason:
                    messagebox.showwarning(_("common.warning"), "Please fill in all fields", parent=refund_dialog)
                    return

                try:
                    refund_amount = float(refund_amount_str)
                    if refund_amount <= 0:
                        messagebox.showwarning(_("common.warning"), "Refund amount must be greater than 0", parent=refund_dialog)
                        return
                except ValueError:
                    messagebox.showwarning(_("common.warning"), "Please enter a valid amount", parent=refund_dialog)
                    return

                # Process the refund
                values = fines_tree.item(selected[0])['values']
                payment_id = values[0]
                loan_id = values[1]
                book_title = values[2]
                paid_amount = float(values[3].replace('\u00a3', ''))
                already_refunded = float(values[4].replace('\u00a3', ''))
                available = float(values[5].replace('\u00a3', ''))

                # Validate refund amount doesn't exceed available amount
                if refund_amount > available:
                    messagebox.showwarning(_("common.warning"),
                        f"Refund amount (\u00a3{refund_amount:.2f}) cannot exceed available amount (\u00a3{available:.2f})",
                        parent=refund_dialog)
                    return

                success = self._process_library_fine_refund(
                    user_id=user_id,
                    payment_id=payment_id,
                    loan_id=loan_id,
                    book_title=book_title,
                    refund_amount=refund_amount,
                    refund_method=refund_method,
                    refund_reason=refund_reason
                )

                if success:
                    messagebox.showinfo(_("common.success"),
                        f"Refund of \u00a3{refund_amount:.2f} processed successfully!\n\n"
                        f"Method: {refund_method}\n"
                        f"User ID: {user_id}", parent=refund_dialog)
                    refund_dialog.destroy()
                    self.load_user_fines()
                else:
                    messagebox.showerror(_("common.error"), "Failed to process refund", parent=refund_dialog)

            # Buttons
            btn_frame = ttk.Frame(refund_dialog)
            btn_frame.pack(fill=tk.X, padx=10, pady=10)

            ttk.Button(btn_frame, text="Process Refund", command=process_refund).pack(side=tk.LEFT, padx=5)
            ttk.Button(btn_frame, text=_("common.cancel"), command=refund_dialog.destroy).pack(side=tk.RIGHT, padx=5)

        else:
            print("WARNING: ORIGINAL_LIBRARY_AVAILABLE is False - showing demo message")
            messagebox.showinfo(_("common.demo"), f"Demo: Refund fine for {user_id}")

    except Exception as e:
        print(f"EXCEPTION in _show_user_refund_details: {e}")
        import traceback
        traceback.print_exc()
        messagebox.showerror(_("common.error"), f"Failed to open refund dialog: {str(e)}")


def _process_library_fine_refund(self, user_id, payment_id, loan_id, book_title, refund_amount, refund_method, refund_reason):
    """Process a library fine refund with multiple payment methods"""
    try:
        conn = get_db_connection()
        if not conn:
            return False

        cursor = conn.cursor()
        current_datetime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        current_date = datetime.now().strftime('%Y-%m-%d')

        # Handle refund based on method
        if refund_method == "Student Finance Account":
            # Credit the student's finance account
            if FINANCE_ACCOUNT_AVAILABLE:
                # Ensure account exists
                ensure_student_finance_account_exists(user_id)

                # Get current balance
                current_balance = get_student_finance_account_balance(user_id) or 0.0

                # Add refund to student finance account
                from education_system.university_system.modules.shared.utils.finance_integration import top_up_student_finance_account

                result = top_up_student_finance_account(
                    student_id=user_id,
                    amount=refund_amount,
                    description=f"Library fine refund (Loan {loan_id})",
                    payment_method="Refund Credit",
                    processed_by=get_current_user_id() if ORIGINAL_LIBRARY_AVAILABLE else 'System'
                )

                if not result or not result.get('success'):
                    conn.close()
                    return False

                new_balance = result.get('new_balance', current_balance + refund_amount)
            else:
                conn.close()
                return False

        # Record refund in unified_refunds table
        processed_by = get_current_user_id() if ORIGINAL_LIBRARY_AVAILABLE else 'System'
        cursor.execute('''
            INSERT INTO unified_refunds
            (source_type, reference_type, reference_id, student_id, amount,
             currency, refund_type, refund_method, refund_reference, reason,
             status, department, processed_by, requested_by, notes, created_at)
            VALUES ('library', 'payment', ?, ?, ?, 'GBP', 'library_fine', ?, ?, ?, 'completed',
                    'Library', ?, ?, ?, ?)
        ''', (
            str(payment_id), user_id, refund_amount,
            refund_method.lower().replace(' ', '_'),
            f"FINE_REFUND_{payment_id}",
            refund_reason, processed_by, processed_by,
            f"Book: {book_title}; Refund {refund_amount:.2f} via {refund_method}",
            current_datetime
        ))
        local_refund_row_id = cursor.lastrowid

        # Auto-post local refund to GL (cash has moved). Never raises.
        # Note: record_refund_to_finance below also creates a SEPARATE row
        # which is itself hooked at the central helper — pre-existing
        # duplication for library-fine refunds, tracked separately.
        try:
            from education_system.university_system.modules.domain.finance.ledger import notify_ledger
            notify_ledger('refund', local_refund_row_id, posted_by=str(processed_by or 'library_fine'))
        except Exception as _e:
            import logging
            logging.getLogger(__name__).warning("ledger hook failed: %s", _e)

        # Note: a duplicate call to record_refund_to_finance was removed here.
        # That central helper writes a SECOND row to the same unified_refunds
        # table the local INSERT above already targets, double-posting in the
        # GL. The local row has the full library context (book title, loan
        # reference); finance integration is now via the GL hook on the
        # local INSERT.
        refund_id = local_refund_row_id

        conn.commit()
        conn.close()

        # Send refund receipt email
        if EMAIL_SERVICE_AVAILABLE:
            self._send_refund_receipt_email(
                user_id=user_id,
                refund_amount=refund_amount,
                refund_method=refund_method,
                book_title=book_title,
                refund_reason=refund_reason,
                loan_id=loan_id
            )

        # Log the action
        if ORIGINAL_LIBRARY_AVAILABLE:
            log_audit_event(get_current_user_id(),
                          f"GUI: Processed library fine refund \u00a3{refund_amount:.2f} for user {user_id} (Loan {loan_id}) via {refund_method}",
                          "book_loans", user_id)

        return True

    except Exception as e:
        print(f"Error processing refund: {e}")
        import traceback
        traceback.print_exc()
        if 'conn' in locals():
            conn.close()
        return False


def _send_refund_receipt_email(self, user_id, refund_amount, refund_method, book_title, refund_reason, loan_id):
    """Send email receipt for library fine refund"""
    try:
        conn = get_db_connection()
        if not conn:
            return False

        cursor = conn.cursor()
        cursor.execute('SELECT first_name, last_name, email_address FROM students WHERE student_id = ?', (user_id,))
        user_info = cursor.fetchone()
        conn.close()

        if not user_info or not user_info[2]:
            return False

        first_name, last_name, email = user_info
        full_name = f"{first_name} {last_name}"

        # Render email from template
        from education_system.university_system.infrastructure.email.template_utils import render_template

        receipt_number = f"LIB-REFUND-{loan_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        refund_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        refund_message = f"Your student finance account has been credited with \u00a3{refund_amount:.2f}." if refund_method == "Student Finance Account" else f"Your refund has been processed using {refund_method}."

        subject, body = render_template('library/refund_receipt', {
            'student_name': full_name,
            'receipt_number': receipt_number,
            'refund_date': refund_date,
            'refund_amount': f'{refund_amount:.2f}',
            'refund_method': refund_method,
            'book_title': book_title,
            'refund_reason': refund_reason,
            'refund_message': refund_message
        })

        # Fallback if template not found
        if not subject or not body:
            subject = "Library Fine Refund Receipt"
            body = f"""Dear {full_name},

This email confirms your library fine refund has been processed.

REFUND DETAILS
Receipt Number:  {receipt_number}
Refund Date:     {refund_date}
Refund Amount:   \u00a3{refund_amount:.2f}
Refund Method:   {refund_method}

BOOK DETAILS:
Book Title:      {book_title}

REASON:
{refund_reason}

{refund_message}

If you have any questions about this refund, please contact the library.

Best regards,
University Library System
"""

        send_email_as_system(
            recipient_email=email,
            subject=subject,
            body=body,
            system_name="Library System"
        )
        return True

    except Exception as e:
        print(f"Error sending refund receipt email: {e}")
        return False
