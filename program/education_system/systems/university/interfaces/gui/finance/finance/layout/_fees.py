"""Fees management mixin for LayoutManager."""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

from education_system.systems.university.infrastructure.database.db import get_connection
from education_system.systems.university.infrastructure.i18n import get_text as _


class FeesMixin:
    """Fees tab: assign, record payment, waive, refresh."""

    def create_fees_tab(self):
        """Create fees management tab"""
        fees_frame = tk.Frame(self.content_frame, bg='white')
        self.tab_frames['fees'] = fees_frame

        # Title
        title_label = tk.Label(fees_frame, text=_("finance_gui.tabs.fees.title"),
                               font=('Arial', 18, 'bold'), bg='white')
        title_label.pack(pady=10)

        # Toolbar
        toolbar = tk.Frame(fees_frame, bg='white')
        toolbar.pack(fill='x', padx=10, pady=10)

        tk.Button(toolbar, text=_("finance_gui.buttons.assign_fee"), command=self._assign_fee,
                 bg=self.colors['success'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)
        tk.Button(toolbar, text=_("finance_gui.buttons.record_payment"), command=self._record_fee_payment,
                 bg=self.colors['info'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)
        tk.Button(toolbar, text=_("finance_gui.buttons.waive_fee"), command=self._waive_fee,
                 bg=self.colors['warning'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)
        tk.Button(toolbar, text=_("finance_gui.buttons.refresh"), command=self._refresh_fees,
                 bg=self.colors['secondary'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='right', padx=5)

        # Fees table
        table_frame = tk.Frame(fees_frame)
        table_frame.pack(fill='both', expand=True, padx=10, pady=10)

        columns = ('student_fee_id', 'student_id', 'fee_type', 'amount', 'currency', 'status', 'due_date')
        self.fees_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=15)

        for col in columns:
            self.fees_tree.heading(col, text=col.replace('_', ' ').title())
            self.fees_tree.column(col, width=120)

        # Scrollbars
        v_scroll = ttk.Scrollbar(table_frame, orient='vertical', command=self.fees_tree.yview)
        h_scroll = ttk.Scrollbar(table_frame, orient='horizontal', command=self.fees_tree.xview)
        self.fees_tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        self.fees_tree.grid(row=0, column=0, sticky='nsew')
        v_scroll.grid(row=0, column=1, sticky='ns')
        h_scroll.grid(row=1, column=0, sticky='ew')

        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        # Load data
        self.root.after(100, self._refresh_fees)

    def _assign_fee(self):
        """Assign a fee to a student"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.dialogs.assign_fee"))
        dialog.geometry("500x450")
        dialog.transient(self.root)

        tk.Label(dialog, text=_("finance_gui.dialogs.assign_student_fee"), font=('Arial', 14, 'bold')).pack(pady=10)

        form_frame = tk.Frame(dialog)
        form_frame.pack(padx=20, pady=10, fill='both', expand=True)

        tk.Label(form_frame, text=_("finance_gui.labels.student_id") + ":").grid(row=0, column=0, sticky='w', pady=5)
        student_id_entry = tk.Entry(form_frame, width=30)
        student_id_entry.grid(row=0, column=1, pady=5)

        tk.Label(form_frame, text=_("finance_gui.labels.fee_type") + ":").grid(row=1, column=0, sticky='w', pady=5)
        fee_type_var = tk.StringVar()
        fee_type_combo = ttk.Combobox(form_frame, textvariable=fee_type_var, state='readonly', width=27)
        fee_type_combo.grid(row=1, column=1, pady=5)

        # Load fee types
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT fee_type_id, fee_name FROM fee_types WHERE is_late_fee = 0")
            fee_types = cursor.fetchall()
            conn.close()
            fee_type_combo['values'] = [f"{ft[0]} - {ft[1]}" for ft in fee_types]
        except Exception as e:
            print(f"Error loading fee types: {e}")

        tk.Label(form_frame, text=_("finance_gui.labels.amount") + ":").grid(row=2, column=0, sticky='w', pady=5)
        amount_entry = tk.Entry(form_frame, width=30)
        amount_entry.grid(row=2, column=1, pady=5)

        tk.Label(form_frame, text=_("finance_gui.labels.currency") + ":").grid(row=3, column=0, sticky='w', pady=5)
        currency_var = tk.StringVar(value="GBP")
        currency_combo = ttk.Combobox(form_frame, textvariable=currency_var,
                                     values=['GBP', 'USD', 'EUR', 'CAD', 'AUD'],
                                     state='readonly', width=27)
        currency_combo.grid(row=3, column=1, pady=5)

        tk.Label(form_frame, text=_("finance_gui.labels.due_date") + ":").grid(row=4, column=0, sticky='w', pady=5)
        due_date_entry = tk.Entry(form_frame, width=30)
        due_date_entry.insert(0, datetime.now().strftime("%Y-%m-%d"))
        due_date_entry.grid(row=4, column=1, pady=5)

        def save_fee():
            try:
                student_id = student_id_entry.get().strip()
                if not student_id:
                    messagebox.showerror(_("common.error"), _("finance_gui.messages.student_id_required"))
                    return

                fee_type_str = fee_type_var.get()
                if not fee_type_str:
                    messagebox.showerror(_("common.error"), _("finance_gui.messages.select_fee_type"))
                    return

                fee_type_id = int(fee_type_str.split(' - ')[0])
                amount = float(amount_entry.get())
                currency = currency_var.get()
                due_date = due_date_entry.get()

                conn = get_connection()
                cursor = conn.cursor()

                # Check if student exists
                cursor.execute('SELECT COUNT(*) FROM students WHERE student_id = ?', (student_id,))
                if cursor.fetchone()[0] == 0:
                    conn.close()
                    messagebox.showerror(_("common.error"), _("finance_gui.messages.student_not_found", student_id=student_id))
                    return

                cursor.execute('''
                    INSERT INTO student_fees
                    (student_id, fee_type_id, amount, currency, status, due_date, created_at)
                    VALUES (?, ?, ?, ?, 'unpaid', ?, datetime('now'))
                ''', (student_id, fee_type_id, amount, currency, due_date))
                fee_row_id = cursor.lastrowid

                conn.commit()
                conn.close()

                # Auto-post AR + revenue to GL (never raises)
                try:
                    from education_system.systems.university.domain.finance.ledger import notify_ledger
                    notify_ledger('fee_assignment', fee_row_id, posted_by='fees_tab')
                except Exception as _e:
                    import logging
                    logging.getLogger(__name__).warning("ledger hook failed: %s", _e)

                messagebox.showinfo(_("common.success"), _("finance_gui.messages.fee_assigned"))
                dialog.destroy()
                self._refresh_fees()
            except ValueError:
                messagebox.showerror(_("common.error"), _("finance_gui.messages.invalid_amount"))
            except Exception as e:
                messagebox.showerror(_("common.error"), _("finance_gui.messages.failed_assign_fee", error=str(e)))

        btn_frame = tk.Frame(dialog)
        btn_frame.pack(pady=20)
        tk.Button(btn_frame, text=_("finance_gui.buttons.save"), command=save_fee, bg=self.colors['success'],
                 fg='white', padx=20, pady=5).pack(side='left', padx=5)
        tk.Button(btn_frame, text=_("finance_gui.buttons.cancel"), command=dialog.destroy, bg=self.colors['danger'],
                 fg='white', padx=20, pady=5).pack(side='left', padx=5)

    def _record_fee_payment(self):
        """Record a payment — single form with student dropdown and outstanding fees"""
        payment_dialog = tk.Toplevel(self.root)
        payment_dialog.title(_("finance_gui.dialogs.record_payment_for_fee", fee_id=""))
        payment_dialog.geometry("550x520")
        payment_dialog.transient(self.root)
        payment_dialog.grab_set()

        ttk.Label(payment_dialog, text="Record Fee Payment",
                 font=('Arial', 14, 'bold')).pack(pady=(10, 5))

        form_frame = ttk.Frame(payment_dialog, padding=10)
        form_frame.pack(fill='both', expand=True, padx=10)

        # --- Row 0: Student dropdown ---
        ttk.Label(form_frame, text=_("finance_gui.labels.student_id") + ":").grid(
            row=0, column=0, sticky='w', pady=5, padx=5)

        students = []
        student_id_map = {}
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT student_id, first_name, last_name FROM students
                ORDER BY last_name, first_name
            ''')
            for row in cursor.fetchall():
                display = f"{row[0]} - {row[1]} {row[2]}"
                students.append(display)
                student_id_map[display] = row[0]
            conn.close()
        except Exception as e:
            print(f"Error loading students: {e}")

        student_var = tk.StringVar()
        student_combo = ttk.Combobox(form_frame, textvariable=student_var,
                                     values=students, state='readonly', width=35)
        student_combo.grid(row=0, column=1, pady=5, padx=5)

        # --- Row 1: Outstanding fee dropdown (populated on student select) ---
        ttk.Label(form_frame, text=_("finance_gui.labels.fee_name") + ":").grid(
            row=1, column=0, sticky='w', pady=5, padx=5)

        fee_var = tk.StringVar()
        fee_combo = ttk.Combobox(form_frame, textvariable=fee_var, state='readonly', width=35)
        fee_combo.grid(row=1, column=1, pady=5, padx=5)

        # Store fee data keyed by display string
        fee_data_map = {}
        amount_due_label = ttk.Label(form_frame, text="", font=('Arial', 10, 'bold'))
        amount_due_label.grid(row=2, column=0, columnspan=2, sticky='w', padx=5)

        def on_student_selected(event=None):
            """Load outstanding fees for the selected student."""
            fee_combo.set('')
            fee_combo['values'] = []
            fee_data_map.clear()
            amount_due_label.config(text='')
            amount_var.set('')

            selected = student_var.get()
            sid = student_id_map.get(selected)
            if not sid:
                return

            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT sf.student_fee_id, ft.fee_name, sf.amount, sf.status
                    FROM student_fees sf
                    LEFT JOIN fee_types ft ON sf.fee_type_id = ft.fee_type_id
                    WHERE sf.student_id = ? AND sf.status IN ('unpaid', 'partial', 'overdue')
                    ORDER BY sf.due_date
                ''', (sid,))
                fee_displays = []
                for row in cursor.fetchall():
                    fee_id = row[0]
                    name = row[1] or 'Fee'
                    amt = float(row[2]) if row[2] is not None else 0.0
                    status = row[3] or 'unpaid'
                    display = f"#{fee_id} - {name} (\u00a3{amt:.2f}) [{status}]"
                    fee_displays.append(display)
                    fee_data_map[display] = {'fee_id': fee_id, 'amount': amt}
                conn.close()

                fee_combo['values'] = fee_displays
                if fee_displays:
                    fee_combo.current(0)
                    on_fee_selected()
                else:
                    amount_due_label.config(text="No outstanding fees for this student.")
            except Exception as e:
                print(f"Error loading fees: {e}")

        def on_fee_selected(event=None):
            """Update amount field when a fee is selected."""
            selected_fee = fee_var.get()
            data = fee_data_map.get(selected_fee)
            if data:
                amount_due_label.config(text=f"Amount Due: \u00a3{data['amount']:.2f}")
                amount_var.set(f"{data['amount']:.2f}")

        student_combo.bind('<<ComboboxSelected>>', on_student_selected)
        fee_combo.bind('<<ComboboxSelected>>', on_fee_selected)

        # --- Row 3: Payment amount ---
        ttk.Label(form_frame, text=_("finance_gui.labels.payment_amount") + ":").grid(
            row=3, column=0, sticky='w', pady=5, padx=5)
        amount_var = tk.StringVar()
        amount_entry = ttk.Entry(form_frame, textvariable=amount_var, width=20, font=('Arial', 11))
        amount_entry.grid(row=3, column=1, sticky='w', pady=5, padx=5)

        # --- Row 4: Payment method ---
        ttk.Label(form_frame, text=_("finance_gui.labels.payment_method") + ":").grid(
            row=4, column=0, sticky='w', pady=5, padx=5)
        method_var = tk.StringVar(value="card")
        method_combo = ttk.Combobox(form_frame, textvariable=method_var,
                                     values=["card", "cash", "bank_transfer", "cheque", "online"],
                                     state='readonly', width=20)
        method_combo.grid(row=4, column=1, sticky='w', pady=5, padx=5)

        # --- Row 5: Notes ---
        ttk.Label(form_frame, text=_("finance_gui.labels.notes_optional") + ":").grid(
            row=5, column=0, sticky='nw', pady=5, padx=5)
        notes_text = tk.Text(form_frame, height=3, width=35, font=('Arial', 10))
        notes_text.grid(row=5, column=1, pady=5, padx=5)

        # Pre-select student if a fee row is selected in the main tree
        if self.fees_tree.selection():
            fee_values = self.fees_tree.item(self.fees_tree.selection()[0])['values']
            preselect_sid = str(fee_values[1])
            for display, sid in student_id_map.items():
                if sid == preselect_sid:
                    student_combo.set(display)
                    on_student_selected()
                    # Try to pre-select the specific fee
                    preselect_fee_id = fee_values[0]
                    for fd, data in fee_data_map.items():
                        if data['fee_id'] == preselect_fee_id:
                            fee_combo.set(fd)
                            on_fee_selected()
                            break
                    break

        def save_payment():
            selected_student = student_var.get()
            selected_fee = fee_var.get()

            if not selected_student:
                messagebox.showwarning(_("finance_gui.messages.warning"), "Please select a student.")
                return
            if not selected_fee:
                messagebox.showwarning(_("finance_gui.messages.warning"), "Please select a fee.")
                return

            student_id = student_id_map.get(selected_student)
            data = fee_data_map.get(selected_fee)
            if not data:
                messagebox.showerror(_("finance_gui.messages.error"), "Invalid fee selection.")
                return

            fee_id = data['fee_id']
            fee_amount = data['amount']

            try:
                payment_amount = float(amount_var.get())
                payment_method = method_var.get()
                notes = notes_text.get('1.0', tk.END).strip()

                if payment_amount <= 0:
                    messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.messages.payment_amount_positive"))
                    return

                # Get authentication for audit trail
                from education_system.systems.university.infrastructure.shared_context import get_auth
                auth = get_auth()
                username = 'system'
                if auth and hasattr(auth, 'is_logged_in') and auth.is_logged_in():
                    user = auth.get_current_user()
                    username = user.get('username', 'system') if user else 'system'

                conn = get_connection()
                cursor = conn.cursor()

                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                payment_date = datetime.now().strftime('%Y-%m-%d')

                # Insert payment record
                cursor.execute('''
                    INSERT INTO payments
                    (student_id, amount, payment_method, payment_date, status, notes, created_by, created_at)
                    VALUES (?, ?, ?, ?, 'completed', ?, ?, ?)
                ''', (student_id, payment_amount, payment_method, payment_date, notes, username, now))

                payment_id = cursor.lastrowid

                # Create payment allocation
                cursor.execute('''
                    INSERT INTO payment_allocations (payment_id, student_fee_id, amount, created_at)
                    VALUES (?, ?, ?, ?)
                ''', (payment_id, fee_id, payment_amount, now))

                # Get current paid amount for this fee
                cursor.execute('''
                    SELECT COALESCE(SUM(amount), 0) FROM payment_allocations
                    WHERE student_fee_id = ?
                ''', (fee_id,))
                total_paid = cursor.fetchone()[0]

                # Update fee status
                new_status = 'paid' if total_paid >= fee_amount else 'partial'

                cursor.execute('''
                    UPDATE student_fees SET status = ?, updated_at = ?
                    WHERE student_fee_id = ?
                ''', (new_status, now, fee_id))

                conn.commit()
                conn.close()

                # Auto-post to GL (never raises)
                try:
                    from education_system.systems.university.domain.finance.ledger import notify_ledger
                    notify_ledger('payment', payment_id, posted_by=username)
                except Exception as _e:
                    import logging
                    logging.getLogger(__name__).warning("ledger hook failed: %s", _e)

                messagebox.showinfo(_("finance_gui.messages.success"),
                                  f"{_('finance_gui.messages.payment_recorded', amount=payment_amount)}\n"
                                  f"{_('finance_gui.labels.fee_status')}: {new_status.title()}")
                payment_dialog.destroy()
                self._refresh_fees()

            except ValueError:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.messages.invalid_payment_amount"))
            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.messages.failed_record_payment", error=str(e)))
                import traceback
                traceback.print_exc()

        # Buttons
        btn_frame = ttk.Frame(payment_dialog)
        btn_frame.pack(pady=10)

        ttk.Button(btn_frame, text=_("finance_gui.buttons.record_payment"), command=save_payment).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=_("finance_gui.buttons.cancel"), command=payment_dialog.destroy).pack(side='left', padx=5)

    def _waive_fee(self):
        """Waive a selected fee"""
        selection = self.fees_tree.selection()
        if not selection:
            messagebox.showwarning(_("finance_gui.messages.no_selection"), _("finance_gui.messages.select_fee_waive"))
            return

        if messagebox.askyesno(_("finance_gui.dialogs.confirm_waive"), _("finance_gui.messages.confirm_waive_fee")):
            try:
                fee_id = self.fees_tree.item(selection[0])['values'][0]
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("UPDATE student_fees SET status = 'waived' WHERE student_fee_id = ?", (fee_id,))
                conn.commit()
                conn.close()
                messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.messages.fee_waived"))
                self._refresh_fees()
            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.messages.failed_waive_fee", error=str(e)))

    def _refresh_fees(self):
        """Refresh fees list"""
        try:
            # Clear existing items
            for item in self.fees_tree.get_children():
                self.fees_tree.delete(item)

            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT sf.student_fee_id, sf.student_id, ft.fee_name, sf.amount,
                       sf.currency, sf.status, sf.due_date
                FROM student_fees sf
                LEFT JOIN fee_types ft ON sf.fee_type_id = ft.fee_type_id
                ORDER BY sf.created_at DESC
                LIMIT 500
            ''')

            for row in cursor.fetchall():
                values = list(row)
                # Format amount (index 3) for display
                try:
                    values[3] = f"{float(values[3]):.2f}" if values[3] is not None else "0.00"
                except (ValueError, TypeError):
                    values[3] = "0.00"
                self.fees_tree.insert('', 'end', values=values)

            conn.close()
        except Exception as e:
            print(f"Error refreshing fees: {e}")
