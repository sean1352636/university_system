"""Payment recording dialogs and payment detail views"""

from education_system.university_system.modules.domain.finance.gui.finance.transaction_manager._imports import (
    tk, ttk, messagebox, simpledialog, _, datetime, get_connection, get_auth,
)


class PaymentRecordingMixin:
    """Mixin for payment recording and viewing"""

    def show_payment_dialog(self):
        """Show payment recording dialog"""
        # Simple payment dialog using built-in dialogs
        student_id = simpledialog.askstring(_("finance_gui.transaction_manager.dialog_payment_title"), _("finance_gui.transaction_manager.enter_student_id"))
        if student_id:
            amount = simpledialog.askfloat(_("finance_gui.transaction_manager.dialog_payment_title"), _("finance_gui.transaction_manager.enter_payment_amount"))
            if amount:
                method = simpledialog.askstring(_("finance_gui.transaction_manager.dialog_payment_title"), _("finance_gui.transaction_manager.payment_method_prompt"), initialvalue="card")
                if method:
                    try:
                        # Get authentication for audit trail
                        from education_system.university_system.infrastructure.shared_context import get_auth
                        auth = get_auth()
                        username = 'system'
                        if auth and hasattr(auth, 'is_logged_in') and auth.is_logged_in():
                            user = auth.get_current_user()
                            username = user.get('username', 'system') if user else 'system'

                        # Save payment to database
                        conn = get_connection()
                        cursor = conn.cursor()

                        # Verify student exists
                        cursor.execute('SELECT COUNT(*) FROM students WHERE student_id = ?', (student_id,))
                        if cursor.fetchone()[0] == 0:
                            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.student_not_found", student_id=student_id))
                            conn.close()
                            return

                        # Insert payment record
                        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        payment_date = datetime.now().strftime('%Y-%m-%d')
                        cursor.execute('''
                            INSERT INTO payments
                            (student_id, amount, payment_method, payment_date, status, created_by, created_at)
                            VALUES (?, ?, ?, ?, 'completed', ?, ?)
                        ''', (student_id, amount, method, payment_date, username, now))

                        payment_id = cursor.lastrowid

                        # Auto-allocate to outstanding fees
                        cursor.execute('''
                            SELECT sf.student_fee_id, ft.fee_name, sf.amount,
                                   COALESCE(SUM(pa.amount), 0) as paid_amount,
                                   (sf.amount - COALESCE(SUM(pa.amount), 0)) as outstanding
                            FROM student_fees sf
                            JOIN fee_types ft ON sf.fee_type_id = ft.fee_type_id
                            LEFT JOIN payment_allocations pa ON sf.student_fee_id = pa.student_fee_id
                            WHERE sf.student_id = ? AND sf.status != 'paid'
                            GROUP BY sf.student_fee_id
                            HAVING outstanding > 0
                            ORDER BY sf.due_date
                        ''', (student_id,))

                        fees = cursor.fetchall()
                        remaining = amount
                        allocations = []

                        for fee in fees:
                            if remaining <= 0:
                                break
                            fee_id, fee_name, total_amount, paid, outstanding = fee
                            allocation = min(remaining, outstanding)

                            # Create allocation
                            cursor.execute('''
                                INSERT INTO payment_allocations (payment_id, student_fee_id, amount, created_at)
                                VALUES (?, ?, ?, ?)
                            ''', (payment_id, fee_id, allocation, now))

                            # Update fee status
                            new_paid = paid + allocation
                            new_status = 'paid' if new_paid >= total_amount else 'partial'
                            cursor.execute('''
                                UPDATE student_fees SET status = ?, updated_at = ?
                                WHERE student_fee_id = ?
                            ''', (new_status, now, fee_id))

                            remaining -= allocation
                            allocations.append(f"\u00a3{allocation:.2f} \u2192 {fee_name}")

                        # Handle overpayment as credit
                        if remaining > 0:
                            cursor.execute('''
                                INSERT INTO student_credits
                                (student_id, credit_amount, remaining_amount, credit_source, description, created_by, created_at, updated_at)
                                VALUES (?, ?, ?, 'overpayment', ?, ?, ?, ?)
                            ''', (student_id, remaining, remaining, f'Overpayment from payment ID {payment_id}', username, now, now))
                            allocations.append(f"\u00a3{remaining:.2f} \u2192 Student Credit")

                        conn.commit()
                        conn.close()

                        # Success message with allocations
                        msg = _("finance_gui.transaction_manager.payment_recorded", amount=amount, student_id=student_id) + "\n"
                        if allocations:
                            msg += "\n" + _("finance_gui.transaction_manager.allocated_label") + "\n" + "\n".join(allocations)
                        messagebox.showinfo(_("finance_gui.messages.success"), msg)

                        self.refresh_payments()
                    except Exception as e:
                        messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.failed_record_payment", error=str(e)))
                        import traceback
                        traceback.print_exc()
            self.refresh_dashboard()


    def gui_record_payment(self):
        """GUI wrapper for record_payment - Enhanced with auto-fill and service selection"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.transaction_manager.record_payment_title"))
        dialog.geometry("900x750")
        dialog.transient(self.root)
        dialog.grab_set()

        # Create main container with canvas for scrolling
        main_container = tk.Frame(dialog)
        main_container.pack(fill='both', expand=True)

        # Create canvas
        canvas = tk.Canvas(main_container, bg='white', highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_container, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Pack canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Mouse wheel scrolling support
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", on_mousewheel)

        # Create notebook for tabs inside scrollable frame
        notebook = ttk.Notebook(scrollable_frame)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)

        # Basic payment tab
        basic_tab = ttk.Frame(notebook, padding="15")
        notebook.add(basic_tab, text=_("finance_gui.transaction_manager.basic_payment_tab"))

        # Auto-fill with current user details
        auth = get_auth()
        current_user_id = ""
        current_user_name = ""
        if auth and hasattr(auth, 'current_user') and auth.current_user:
            current_user_id = auth.current_user.get('student_id') or auth.current_user.get('user_id', '')
            first_name = auth.current_user.get('first_name', '')
            last_name = auth.current_user.get('last_name', '')
            current_user_name = f"{first_name} {last_name}".strip()

        # Current user info display
        if current_user_id:
            user_info_frame = ttk.LabelFrame(basic_tab, text="Current User", padding="10")
            user_info_frame.pack(fill='x', pady=(0, 10))
            ttk.Label(user_info_frame, text=f"ID: {current_user_id}  |  Name: {current_user_name}",
                     font=('Arial', 10, 'bold')).pack()

        # Student ID with auto-fill button
        student_id_frame = ttk.Frame(basic_tab)
        student_id_frame.pack(fill='x', pady=5)
        ttk.Label(student_id_frame, text=_("finance_gui.transaction_manager.student_id_label"), font=('Arial', 12)).pack(side='left')
        student_id_var = tk.StringVar(value=current_user_id if current_user_id else "")
        student_entry = ttk.Entry(student_id_frame, textvariable=student_id_var, font=('Arial', 12), width=20)
        student_entry.pack(side='left', padx=5)
        if current_user_id:
            ttk.Button(student_id_frame, text="Use My ID",
                      command=lambda: student_id_var.set(current_user_id)).pack(side='left', padx=5)

        # Payment Purpose Dropdown - All Services
        ttk.Label(basic_tab, text="Payment For:", font=('Arial', 12, 'bold')).pack(pady=(15, 5))
        purpose_var = tk.StringVar(value="General Fee Payment")

        # Comprehensive list of all services/purposes in the system
        payment_purposes = [
            "=== Academic Services ===",
            "Tuition Fees",
            "Course Materials",
            "Lab Fees",
            "Exam Fees",
            "Library Fines",
            "Late Submission Penalty",
            "Academic Transcript",
            "Certificate Fee",
            "=== Food & Dining ===",
            "Restaurant - Meal",
            "Cafe - Coffee/Snacks",
            "Takeaway - Food Order",
            "Bar - Beverages",
            "Grocery - Shopping",
            "=== Health & Wellness ===",
            "Dentist - Dental Treatment",
            "Doctor - Medical Consultation",
            "Gym - Membership",
            "Pharmacy - Medication",
            "=== Personal Services ===",
            "Barber - Haircut",
            "Nail Bar - Manicure/Pedicure",
            "=== Retail & Shopping ===",
            "Butcher - Meat Products",
            "Music Shop - Instruments/Equipment",
            "Phone Shop - Mobile/Accessories",
            "Charity Shop - Donations/Purchases",
            "Shop Management - General Store",
            "=== Entertainment ===",
            "Cinema - Movie Tickets",
            "Betting Shop - Wagers",
            "=== Transportation ===",
            "Taxi - Ride Fare",
            "Car Rental - Vehicle Hire",
            "Train Station - Train Tickets",
            "=== Accommodation ===",
            "Housing - Rent Payment",
            "Accommodation Deposit",
            "=== Other Services ===",
            "Legal Services",
            "Student Union - Membership/Events",
            "Club/Society Fee",
            "Printing Services",
            "General Fee Payment",
            "Other"
        ]

        purpose_combo = ttk.Combobox(basic_tab, textvariable=purpose_var,
                                     values=payment_purposes,
                                     font=('Arial', 11), width=35)
        purpose_combo.pack(pady=5)

        # Amount
        ttk.Label(basic_tab, text=_("finance_gui.transaction_manager.payment_amount_label"), font=('Arial', 12)).pack(pady=5)
        amount_var = tk.StringVar()
        ttk.Entry(basic_tab, textvariable=amount_var, font=('Arial', 12), width=20).pack(pady=5)

        # Payment method with Student Finance Account option
        ttk.Label(basic_tab, text=_("finance_gui.transaction_manager.payment_method_label"), font=('Arial', 12)).pack(pady=5)
        method_var = tk.StringVar(value="Card")
        method_combo = ttk.Combobox(basic_tab, textvariable=method_var,
                                   values=["Student Finance Account", "Card", "Cash", "Bank Transfer", "Cheque", "Online"],
                                   state='readonly', font=('Arial', 12))
        method_combo.pack(pady=5)

        # Show balance when Student Finance Account is selected
        balance_label_var = tk.StringVar(value="")
        balance_label = ttk.Label(basic_tab, textvariable=balance_label_var, font=('Arial', 10), foreground='blue')
        balance_label.pack(pady=2)

        def update_balance_display(*args):
            if method_var.get() == "Student Finance Account" and student_id_var.get():
                try:
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute('SELECT balance FROM student_finance_accounts WHERE student_id = ?',
                                 (student_id_var.get(),))
                    result = cursor.fetchone()
                    balance = result[0] if result else 0.0
                    balance_label_var.set(f"Account Balance: \u00a3{balance:,.2f}")
                    conn.close()
                except Exception as e:
                    balance_label_var.set(f"Error checking balance: {e}")
            else:
                balance_label_var.set("")

        method_var.trace('w', update_balance_display)
        student_id_var.trace('w', update_balance_display)

        # Payment date
        ttk.Label(basic_tab, text=_("finance_gui.transaction_manager.payment_date_label"), font=('Arial', 12)).pack(pady=5)
        date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(basic_tab, textvariable=date_var, font=('Arial', 12), width=20).pack(pady=5)

        # Transaction ID
        ttk.Label(basic_tab, text=_("finance_gui.transaction_manager.transaction_id_label"), font=('Arial', 12)).pack(pady=5)
        trans_id_var = tk.StringVar()
        ttk.Entry(basic_tab, textvariable=trans_id_var, font=('Arial', 12), width=30).pack(pady=5)

        # Notes
        ttk.Label(basic_tab, text=_("finance_gui.transaction_manager.notes_label"), font=('Arial', 12)).pack(pady=5)
        notes_text = tk.Text(basic_tab, height=3, width=50, font=('Arial', 10))
        notes_text.pack(pady=5)
        # Auto-fill notes with payment purpose
        if purpose_var.get() and purpose_var.get() != "General Fee Payment":
            notes_text.insert("1.0", f"Payment for: {purpose_var.get()}")

        def record_payment():
            try:
                # Validate inputs
                if not all([student_id_var.get(), amount_var.get(), method_var.get(), date_var.get()]):
                    messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.required_fields_missing"))
                    return

                student_id = student_id_var.get().strip()
                amount = float(amount_var.get())
                payment_method = method_var.get()
                payment_date = date_var.get().strip()
                transaction_id = trans_id_var.get().strip()
                purpose = purpose_var.get()
                notes_input = notes_text.get("1.0", tk.END).strip()

                # Combine purpose and notes
                notes = f"Payment for: {purpose}"
                if notes_input and notes_input != notes:
                    notes += f"\n{notes_input}"

                if amount <= 0:
                    messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.amount_greater_zero"))
                    return

                # Get authentication
                auth = get_auth()
                username = 'system'
                if auth and hasattr(auth, 'is_logged_in') and auth.is_logged_in():
                    user = auth.get_current_user()
                    username = user.get('username', 'system') if user else 'system'

                # Call original function logic
                conn = get_connection()
                cursor = conn.cursor()

                # Check if student exists
                cursor.execute('SELECT COUNT(*) FROM students WHERE student_id = ?', (student_id,))
                if cursor.fetchone()[0] == 0:
                    messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.student_not_found", student_id=student_id))
                    conn.close()
                    return

                # Handle Student Finance Account payment
                if payment_method == "Student Finance Account":
                    # Check balance
                    cursor.execute('SELECT account_id, balance FROM student_finance_accounts WHERE student_id = ?',
                                 (student_id,))
                    result = cursor.fetchone()

                    if not result:
                        messagebox.showerror(_("finance_gui.messages.error"),
                                           "Student finance account not found. Please create an account first.")
                        conn.close()
                        return

                    account_id, balance = result

                    if balance < amount:
                        messagebox.showerror(_("finance_gui.messages.error"),
                                           f"Insufficient balance. Available: \u00a3{balance:.2f}, Required: \u00a3{amount:.2f}")
                        conn.close()
                        return

                    # Deduct from student finance account
                    new_balance = balance - amount
                    cursor.execute('''
                        UPDATE student_finance_accounts
                        SET balance = ?, updated_at = datetime('now')
                        WHERE student_id = ?
                    ''', (new_balance, student_id))

                    # Record transaction in finance account history
                    cursor.execute('''
                        INSERT INTO student_finance_transactions
                        (account_id, student_id, transaction_type, amount, balance_before, balance_after,
                         description, processed_by)
                        VALUES (?, ?, 'payment', ?, ?, ?, ?, ?)
                    ''', (account_id, student_id, amount, balance, new_balance, notes, username))

                # Record payment
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute('''
                INSERT INTO payments
                (student_id, amount, payment_method, payment_date, transaction_id, notes, created_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (student_id, amount, payment_method, payment_date, transaction_id, notes,
                      username, now))

                payment_id = cursor.lastrowid

                # Auto-allocate to outstanding fees
                cursor.execute('''
                SELECT sf.student_fee_id, ft.fee_name, sf.amount,
                       COALESCE(SUM(pa.amount), 0) as paid_amount,
                       (sf.amount - COALESCE(SUM(pa.amount), 0)) as outstanding
                FROM student_fees sf
                JOIN fee_types ft ON sf.fee_type_id = ft.fee_type_id
                LEFT JOIN payment_allocations pa ON sf.student_fee_id = pa.student_fee_id
                WHERE sf.student_id = ? AND sf.status != 'paid'
                GROUP BY sf.student_fee_id
                HAVING outstanding > 0
                ORDER BY sf.due_date
                ''', (student_id,))

                outstanding_fees = cursor.fetchall()
                remaining_payment = amount
                allocated_fees = []

                for fee in outstanding_fees:
                    if remaining_payment <= 0:
                        break

                    fee_id, fee_name, total_amount, paid_amount, outstanding = fee
                    allocation_amount = min(remaining_payment, outstanding)

                    # Create payment allocation
                    cursor.execute('''
                    INSERT INTO payment_allocations
                    (payment_id, student_fee_id, amount, created_at)
                    VALUES (?, ?, ?, ?)
                    ''', (payment_id, fee_id, allocation_amount, now))

                    # Update fee status
                    new_paid_amount = paid_amount + allocation_amount
                    new_status = 'paid' if new_paid_amount >= total_amount else 'partial'

                    cursor.execute('''
                    UPDATE student_fees
                    SET status = ?, updated_at = ?
                    WHERE student_fee_id = ?
                    ''', (new_status, now, fee_id))

                    remaining_payment -= allocation_amount
                    allocated_fees.append(f"\u00a3{allocation_amount:.2f} to {fee_name}")

                # Handle overpayment as credit
                if remaining_payment > 0:
                    cursor.execute('''
                    INSERT INTO student_credits
                    (student_id, credit_amount, remaining_amount, credit_source, description, created_by, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (student_id, remaining_payment, remaining_payment, 'overpayment',
                          f'Overpayment from payment ID {payment_id}', username, now, now))

                conn.commit()
                conn.close()

                # Show success message with allocation details
                allocation_msg = "\n".join(allocated_fees) if allocated_fees else _("finance_gui.transaction_manager.no_outstanding_fees")
                if remaining_payment > 0:
                    allocation_msg += "\n\n" + _("finance_gui.transaction_manager.overpayment_credit", amount=remaining_payment)

                messagebox.showinfo(_("finance_gui.messages.success"),
                                   _("finance_gui.transaction_manager.payment_success") + "\n" +
                                   _("finance_gui.transaction_manager.payment_id_label") + f" {payment_id}\n" +
                                   _("finance_gui.transaction_manager.amount_label_display") + f" \u00a3{amount:.2f}\n\n" +
                                   _("finance_gui.transaction_manager.allocations_label") + f"\n{allocation_msg}")

                dialog.destroy()
                self.update_status(f"Payment of \u00a3{amount:.2f} recorded for student {student_id}")

            except ValueError:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.invalid_amount"))
            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.failed_record_payment", error=str(e)))

        # Buttons
        button_frame = ttk.Frame(basic_tab)
        button_frame.pack(pady=20)

        ttk.Button(button_frame, text=_("finance_gui.transaction_manager.btn_record"), command=record_payment).pack(side='left', padx=10)
        ttk.Button(button_frame, text=_("finance_gui.transaction_manager.btn_cancel"), command=dialog.destroy).pack(side='left', padx=10)


    def view_payment_details(self):
        """View selected payment details"""
        selection = self.payments_tree.selection()
        if not selection:
            messagebox.showwarning(_("finance_gui.messages.no_selection"), _("finance_gui.transaction_manager.no_selection_view"))
            return

        payment_id = self.payments_tree.item(selection[0])['values'][0]

        # Create details dialog
        from education_system.university_system.modules.domain.finance.gui.finance.invoice_manager import PaymentDetailsDialog
        dialog = PaymentDetailsDialog(self.root, payment_id)
        self.root.wait_window(dialog.dialog)


    def process_refund(self):
        """Process refund for selected payment"""
        selection = self.payments_tree.selection()
        if not selection:
            messagebox.showwarning(_("finance_gui.messages.no_selection"), _("finance_gui.transaction_manager.no_selection_refund"))
            return

        payment_data = self.payments_tree.item(selection[0])['values']
        payment_id = payment_data[0]
        student_id = payment_data[1]
        amount = float(payment_data[2])

        # Show refund dialog
        from education_system.university_system.modules.domain.finance.gui.finance.invoice_manager import RefundDialog
        dialog = RefundDialog(self.root, payment_id, student_id, amount)
        self.root.wait_window(dialog.dialog)
        if dialog.result:
            self.refresh_payments()
            self.refresh_dashboard()


    def load_payment_history(self, student_id, tree_widget):
        """Load payment history for a student"""
        if not student_id:
            return

        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT p.payment_id, p.amount, p.payment_method, p.payment_date, p.transaction_id
            FROM payments p
            WHERE p.student_id = ? AND p.status = 'completed'
            ORDER BY p.payment_date DESC
            ''', (student_id,))

            payments = cursor.fetchall()

            # Clear existing items
            for item in tree_widget.get_children():
                tree_widget.delete(item)

            # Add payment data
            for payment in payments:
                payment_id, amount, method, date, transaction_id = payment
                trans_id = transaction_id if transaction_id else "N/A"
                tree_widget.insert('', 'end', values=(payment_id, f"\u00a3{amount:.2f}", method, date, trans_id))

            conn.close()

        except Exception as e:
            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.failed_load_payment_history", error=str(e)))
