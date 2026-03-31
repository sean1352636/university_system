"""Payment plan management GUI"""

from education_system.university_system.modules.domain.finance.gui.finance.transaction_manager._imports import (
    tk, ttk, messagebox, _, datetime, timedelta, get_connection, auth,
)
from tkinter.scrolledtext import ScrolledText


class PaymentPlansMixin:
    """Mixin for payment plan management"""

    def create_payment_plans_tab(self):
        """Create payment plans management tab"""
        tab = tk.Frame(self.gui.layout.content_frame, bg='white')
        self.gui.layout.tab_frames['payment_plans'] = tab

        # Main frame
        main_frame = ttk.Frame(tab, padding=20)
        main_frame.pack(fill='both', expand=True)

        # Buttons frame
        button_frame = ttk.LabelFrame(main_frame, text=_("finance_gui.transaction_manager.payment_plan_management_frame"), padding=15)
        button_frame.pack(fill='x', pady=(0, 20))

        buttons = [
            (_("finance_gui.transaction_manager.btn_create_plan"), self.gui_create_payment_plan),
            (_("finance_gui.transaction_manager.btn_view_active_plans"), self.gui_view_active_payment_plans),
            (_("finance_gui.transaction_manager.btn_modify_plan"), self.gui_modify_payment_plan),
            (_("finance_gui.transaction_manager.btn_process_plan_payment"), self.gui_process_payment_plan_payment),
            (_("finance_gui.transaction_manager.btn_cancel_plan"), self.gui_cancel_payment_plan)
        ]

        for i, (text, command) in enumerate(buttons):
            btn = ttk.Button(button_frame, text=text, command=command, width=25)
            btn.grid(row=i//3, column=i%3, padx=10, pady=5, sticky='ew')

        # Plans display frame
        display_frame = ttk.LabelFrame(main_frame, text=_("finance_gui.transaction_manager.active_plans_frame"), padding=15)
        display_frame.pack(fill='both', expand=True)

        # Treeview for plans
        columns = ('Plan ID', 'Student', 'Template', 'Total', 'Remaining', 'Next Due')
        self.plans_tree = ttk.Treeview(display_frame, columns=columns, show='headings', height=10)

        for col in columns:
            self.plans_tree.heading(col, text=col)
            self.plans_tree.column(col, width=120, anchor='center')

        # Scrollbars for treeview
        plans_v_scroll = ttk.Scrollbar(display_frame, orient='vertical', command=self.plans_tree.yview)
        plans_h_scroll = ttk.Scrollbar(display_frame, orient='horizontal', command=self.plans_tree.xview)
        self.plans_tree.configure(yscrollcommand=plans_v_scroll.set, xscrollcommand=plans_h_scroll.set)

        self.plans_tree.pack(side='left', fill='both', expand=True)
        plans_v_scroll.pack(side='right', fill='y')
        plans_h_scroll.pack(side='bottom', fill='x')

        # Load initial data
        self.refresh_payment_plans()


    def gui_create_payment_plan(self):
        """GUI for creating payment plans"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.transaction_manager.create_plan_title"))
        dialog.geometry("600x700")
        dialog.transient(self.root)
        dialog.grab_set()

        # Student selection
        student_frame = ttk.LabelFrame(dialog, text=_("finance_gui.transaction_manager.student_info_frame"), padding=15)
        student_frame.pack(fill='x', padx=20, pady=10)

        ttk.Label(student_frame, text=_("finance_gui.transaction_manager.student_id_label"), font=('Arial', 12)).pack(anchor='w')
        student_id_var = tk.StringVar()
        student_entry = ttk.Entry(student_frame, textvariable=student_id_var, font=('Arial', 12))
        student_entry.pack(anchor='w', pady=5, fill='x')

        # Outstanding fees display
        fees_frame = ttk.LabelFrame(dialog, text=_("finance_gui.transaction_manager.outstanding_fees_frame"), padding=15)
        fees_frame.pack(fill='both', expand=True, padx=20, pady=10)

        fees_text = ScrolledText(fees_frame, height=6, font=('Courier', 10))
        fees_text.pack(fill='both', expand=True)

        def load_outstanding_fees():
            student_id = student_id_var.get().strip()
            if not student_id:
                return

            try:
                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                SELECT sf.student_fee_id, ft.fee_name, sf.amount, sf.status, sf.due_date
                FROM student_fees sf
                JOIN fee_types ft ON sf.fee_type_id = ft.fee_type_id
                WHERE sf.student_id = ? AND sf.status != 'paid'
                ORDER BY sf.due_date
                ''', (student_id,))

                outstanding_fees = cursor.fetchall()

                fees_text.delete('1.0', tk.END)

                if not outstanding_fees:
                    fees_text.insert('1.0', f"No outstanding fees found for student {student_id}")
                    total_outstanding_var.set("0.00")
                    conn.close()
                    return

                total_outstanding = sum(fee[2] for fee in outstanding_fees)
                total_outstanding_var.set(f"{total_outstanding:.2f}")

                fees_content = f"Outstanding Fees for Student {student_id}:\n"
                fees_content += "=" * 60 + "\n"

                for fee_id, fee_name, amount, status, due_date in outstanding_fees:
                    fees_content += f"{fee_name:<30} \u00a3{amount:>8.2f}  Due: {due_date}\n"

                fees_content += "=" * 60 + "\n"
                fees_content += f"Total Outstanding: \u00a3{total_outstanding:.2f}"

                fees_text.insert('1.0', fees_content)
                conn.close()

            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.load_fees_failed", error=str(e)))

        ttk.Button(student_frame, text=_("finance_gui.transaction_manager.btn_load_outstanding_fees"),
                  command=load_outstanding_fees).pack(anchor='w', pady=5)

        # Plan configuration
        plan_frame = ttk.LabelFrame(dialog, text=_("finance_gui.transaction_manager.plan_config_frame"), padding=15)
        plan_frame.pack(fill='x', padx=20, pady=10)

        # Load payment plan templates
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
            SELECT template_id, template_name, description, number_of_installments,
                   installment_frequency, setup_fee, interest_rate
            FROM payment_plan_templates
            WHERE is_active = 1
            ORDER BY number_of_installments
            ''')
            templates = cursor.fetchall()
            conn.close()
        except Exception:
            templates = []

        ttk.Label(plan_frame, text=_("finance_gui.transaction_manager.plan_template_label"), font=('Arial', 12)).pack(anchor='w')
        template_var = tk.StringVar()
        template_combo = ttk.Combobox(plan_frame, textvariable=template_var, state='readonly', width=50)

        template_values = []
        self.template_data = {}

        for template in templates:
            template_id, name, desc, installments, frequency, setup_fee, interest_rate = template
            display_text = f"{name} - {installments} {frequency} payments (Setup: \u00a3{setup_fee:.2f}, Interest: {interest_rate}%)"
            template_values.append(display_text)
            self.template_data[display_text] = template

        template_combo['values'] = template_values
        template_combo.pack(anchor='w', pady=5, fill='x')

        # Plan summary
        summary_frame = ttk.LabelFrame(plan_frame, text=_("finance_gui.transaction_manager.plan_summary_frame"), padding=10)
        summary_frame.pack(fill='x', pady=10)

        total_outstanding_var = tk.StringVar(value="0.00")
        ttk.Label(summary_frame, text=_("finance_gui.transaction_manager.outstanding_amount_label")).pack(side='left')
        ttk.Label(summary_frame, textvariable=total_outstanding_var, font=('Arial', 12, 'bold')).pack(side='left')

        def calculate_plan_summary():
            selected_template = template_var.get()
            if not selected_template or selected_template not in self.template_data:
                return

            try:
                outstanding = float(total_outstanding_var.get())
                if outstanding <= 0:
                    return

                template_info = self.template_data[selected_template]
                *_unused, num_installments, frequency, setup_fee, interest_rate = template_info

                principal_amount = outstanding
                interest_amount = principal_amount * (interest_rate / 100)
                total_with_interest = principal_amount + interest_amount + setup_fee
                installment_amount = total_with_interest / num_installments

                summary_text = f"""
    Plan Details:
    - Principal: \u00a3{principal_amount:.2f}
    - Setup Fee: \u00a3{setup_fee:.2f}
    - Interest ({interest_rate}%): \u00a3{interest_amount:.2f}
    - Total Amount: \u00a3{total_with_interest:.2f}
    - Installments: {num_installments}
    - Amount per installment: \u00a3{installment_amount:.2f}
    """
                plan_summary_text.delete('1.0', tk.END)
                plan_summary_text.insert('1.0', summary_text)

            except ValueError as e:
                # Invalid input for calculation, silently ignore
                print(f"Debug: Plan summary calculation failed: {e}")

        template_combo.bind('<<ComboboxSelected>>', lambda e: calculate_plan_summary())

        plan_summary_text = tk.Text(summary_frame, height=8, width=50, font=('Courier', 9))
        plan_summary_text.pack(fill='x', pady=5)

        def create_payment_plan():
            try:
                student_id = student_id_var.get().strip()
                selected_template = template_var.get()

                if not all([student_id, selected_template]):
                    messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.student_template_required"))
                    return

                if selected_template not in self.template_data:
                    messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.invalid_template"))
                    return

                outstanding = float(total_outstanding_var.get())
                if outstanding <= 0:
                    messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.no_outstanding_for_plan"))
                    return

                # Get template details
                template_info = self.template_data[selected_template]
                template_id, template_name, _desc, num_installments, frequency, setup_fee, interest_rate = template_info

                # Calculate plan details
                principal_amount = outstanding
                interest_amount = principal_amount * (interest_rate / 100)
                total_with_interest = principal_amount + interest_amount + setup_fee
                installment_amount = total_with_interest / num_installments

                # Create the payment plan
                conn = get_connection()
                cursor = conn.cursor()

                now = datetime.now()
                start_date = now.strftime('%Y-%m-%d')

                # Calculate next due date based on frequency
                if frequency == 'weekly':
                    next_due = now + timedelta(weeks=1)
                elif frequency == 'monthly':
                    next_due = now + timedelta(days=30)
                elif frequency == 'quarterly':
                    next_due = now + timedelta(days=90)
                else:
                    next_due = now + timedelta(days=30)

                next_due_date = next_due.strftime('%Y-%m-%d')

                cursor.execute('''
                INSERT INTO student_payment_plans
                (student_id, template_id, total_amount, remaining_amount, start_date,
                 next_due_date, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (student_id, template_id, total_with_interest, total_with_interest,
                      start_date, next_due_date, now.strftime('%Y-%m-%d %H:%M:%S'),
                      now.strftime('%Y-%m-%d %H:%M:%S')))

                payment_plan_id = cursor.lastrowid

                # Create installments
                current_due_date = next_due
                for i in range(num_installments):
                    cursor.execute('''
                    INSERT INTO payment_plan_installments
                    (payment_plan_id, installment_number, amount, due_date, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ''', (payment_plan_id, i + 1, installment_amount, current_due_date.strftime('%Y-%m-%d'),
                          now.strftime('%Y-%m-%d %H:%M:%S'), now.strftime('%Y-%m-%d %H:%M:%S')))

                    # Calculate next due date
                    if frequency == 'weekly':
                        current_due_date += timedelta(weeks=1)
                    elif frequency == 'monthly':
                        current_due_date += timedelta(days=30)
                    elif frequency == 'quarterly':
                        current_due_date += timedelta(days=90)

                conn.commit()
                conn.close()

                messagebox.showinfo(_("finance_gui.messages.success"),
                                   _("finance_gui.transaction_manager.plan_created_success") + "\n" +
                                   _("finance_gui.transaction_manager.plan_id_label") + f" {payment_plan_id}\n" +
                                   _("finance_gui.transaction_manager.template_label") + f" {template_name}\n" +
                                   _("finance_gui.transaction_manager.total_amount_label") + f" \u00a3{total_with_interest:.2f}\n" +
                                   _("finance_gui.transaction_manager.first_installment_label", amount=installment_amount, date=next_due_date))

                dialog.destroy()
                self.refresh_payment_plans()
                self.update_status(f"Payment plan created for student {student_id}")

            except ValueError:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.invalid_numerical_values"))
            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.create_plan_failed", error=str(e)))

        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=20)

        ttk.Button(button_frame, text=_("finance_gui.transaction_manager.btn_create_payment_plan"), command=create_payment_plan).pack(side='left', padx=10)
        ttk.Button(button_frame, text=_("finance_gui.transaction_manager.btn_cancel"), command=dialog.destroy).pack(side='left', padx=10)


    def gui_view_active_payment_plans(self):
        """Refresh and display active payment plans"""
        self.refresh_payment_plans()
        self.show_tab('payment_plans')  # Switch to Payment Plans tab
        messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.transaction_manager.plans_refreshed"))


    def refresh_payment_plans(self):
        """Refresh payment plans display"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT spp.payment_plan_id, spp.student_id, s.first_name, s.last_name,
                   spp.total_amount, spp.remaining_amount, spp.status, spp.next_due_date,
                   ppt.template_name, ppt.number_of_installments
            FROM student_payment_plans spp
            JOIN students s ON spp.student_id = s.student_id
            JOIN payment_plan_templates ppt ON spp.template_id = ppt.template_id
            WHERE spp.status = 'active'
            ORDER BY spp.next_due_date
            ''')

            plans = cursor.fetchall()

            # Clear existing items
            for item in self.plans_tree.get_children():
                self.plans_tree.delete(item)

            # Add plan data
            for plan in plans:
                plan_id, student_id, first_name, last_name, total, remaining, status, next_due, template, installments = plan
                student_name = f"{first_name} {last_name}"

                self.plans_tree.insert('', 'end', values=(
                    plan_id, student_name, template,
                    f"\u00a3{total:.2f}", f"\u00a3{remaining:.2f}", next_due
                ))

            conn.close()

        except Exception as e:
            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.refresh_plans_failed", error=str(e)))


    def gui_process_payment_plan_payment(self):
        """GUI for processing payment plan payments"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.transaction_manager.process_plan_payment_title"))
        dialog.geometry("700x600")
        dialog.transient(self.root)
        dialog.grab_set()

        # Student selection
        student_frame = ttk.LabelFrame(dialog, text=_("finance_gui.transaction_manager.student_selection_frame"), padding=15)
        student_frame.pack(fill='x', padx=20, pady=10)

        ttk.Label(student_frame, text=_("finance_gui.transaction_manager.student_id_label"), font=('Arial', 12)).pack(anchor='w')
        student_id_var = tk.StringVar()
        ttk.Entry(student_frame, textvariable=student_id_var, font=('Arial', 12)).pack(anchor='w', pady=5)

        def load_payment_plans():
            student_id = student_id_var.get().strip()
            if not student_id:
                return

            try:
                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                SELECT spp.payment_plan_id, ppt.template_name, spp.remaining_amount,
                       spp.next_due_date, spp.status
                FROM student_payment_plans spp
                JOIN payment_plan_templates ppt ON spp.template_id = ppt.template_id
                WHERE spp.student_id = ? AND spp.status = 'active'
                ORDER BY spp.next_due_date
                ''', (student_id,))

                plans = cursor.fetchall()

                # Clear existing items
                for item in plan_tree.get_children():
                    plan_tree.delete(item)

                for plan in plans:
                    plan_id, template, remaining, next_due, status = plan
                    plan_tree.insert('', 'end', values=(
                        plan_id, template, f"\u00a3{remaining:.2f}", next_due, status
                    ))

                conn.close()

            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.load_plans_failed", error=str(e)))

        ttk.Button(student_frame, text=_("finance_gui.transaction_manager.btn_load_plans"), command=load_payment_plans).pack(anchor='w', pady=5)

        # Payment plans display
        plans_frame = ttk.LabelFrame(dialog, text=_("finance_gui.transaction_manager.active_plans_frame"), padding=15)
        plans_frame.pack(fill='both', expand=True, padx=20, pady=10)

        columns = ('Plan ID', 'Template', 'Remaining', 'Next Due', 'Status')
        plan_tree = ttk.Treeview(plans_frame, columns=columns, show='headings', height=8)

        for col in columns:
            plan_tree.heading(col, text=col)
            plan_tree.column(col, width=120, anchor='center')

        plan_tree.pack(fill='both', expand=True)

        # Payment details
        payment_frame = ttk.LabelFrame(dialog, text=_("finance_gui.transaction_manager.payment_details_frame"), padding=15)
        payment_frame.pack(fill='x', padx=20, pady=10)

        ttk.Label(payment_frame, text=_("finance_gui.transaction_manager.payment_amount_pound_label"), font=('Arial', 12)).pack(anchor='w')
        amount_var = tk.StringVar()
        ttk.Entry(payment_frame, textvariable=amount_var, font=('Arial', 12)).pack(anchor='w', pady=5)

        ttk.Label(payment_frame, text=_("finance_gui.transaction_manager.payment_method_select_label"), font=('Arial', 12)).pack(anchor='w')
        method_var = tk.StringVar(value="Card")
        method_combo = ttk.Combobox(payment_frame, textvariable=method_var,
                                   values=["Card", "Cash", "Bank Transfer", "Cheque"],
                                   state='readonly', font=('Arial', 12))
        method_combo.pack(anchor='w', pady=5)

        def process_payment():
            selection = plan_tree.selection()
            if not selection:
                messagebox.showwarning(_("finance_gui.messages.no_selection"), _("finance_gui.transaction_manager.select_plan_prompt"))
                return

            try:
                plan_id = plan_tree.item(selection[0])['values'][0]
                payment_amount = float(amount_var.get())
                payment_method = method_var.get()

                if payment_amount <= 0:
                    messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.amount_greater_zero"))
                    return

                conn = get_connection()
                cursor = conn.cursor()

                # Get plan details
                cursor.execute('''
                SELECT student_id, remaining_amount, template_id
                FROM student_payment_plans
                WHERE payment_plan_id = ?
                ''', (plan_id,))

                plan_data = cursor.fetchone()
                if not plan_data:
                    messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.plan_not_found"))
                    conn.close()
                    return

                student_id, remaining_amount, template_id = plan_data

                if payment_amount > remaining_amount:
                    if not messagebox.askyesno(_("finance_gui.transaction_manager.overpayment_title"),
                                              _("finance_gui.transaction_manager.overpayment_confirm", payment=payment_amount, remaining=remaining_amount)):
                        conn.close()
                        return

                # Record the payment
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute('''
                INSERT INTO payments
                (student_id, amount, payment_method, payment_date, status, notes, created_by, created_at)
                VALUES (?, ?, ?, ?, 'completed', ?, ?, ?)
                ''', (student_id, payment_amount, payment_method,
                      datetime.now().strftime('%Y-%m-%d'),
                      f'Payment plan installment for plan {plan_id}',
                      auth.current_user['username'], now))

                payment_id = cursor.lastrowid

                # Update payment plan
                new_remaining = max(0, remaining_amount - payment_amount)
                new_status = 'completed' if new_remaining == 0 else 'active'

                # Calculate next due date (simplified - monthly)
                if new_remaining > 0:
                    next_due = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
                else:
                    next_due = None

                cursor.execute('''
                UPDATE student_payment_plans
                SET remaining_amount = ?, status = ?, next_due_date = ?, updated_at = ?
                WHERE payment_plan_id = ?
                ''', (new_remaining, new_status, next_due, now, plan_id))

                conn.commit()
                conn.close()

                messagebox.showinfo(_("finance_gui.messages.success"),
                                   _("finance_gui.transaction_manager.plan_payment_success") + "\n" +
                                   _("finance_gui.transaction_manager.payment_id_label") + f" {payment_id}\n" +
                                   _("finance_gui.transaction_manager.remaining_balance_label", amount=new_remaining))

                dialog.destroy()
                self.refresh_payment_plans()

            except ValueError:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.invalid_payment_amount"))
            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.process_payment_failed", error=str(e)))

        ttk.Button(payment_frame, text=_("finance_gui.transaction_manager.btn_process_payment"), command=process_payment).pack(pady=20)


    def gui_modify_payment_plan(self):
        """GUI for modifying payment plans"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.transaction_manager.modify_plan_title"))
        dialog.geometry("600x500")
        dialog.transient(self.root)
        dialog.grab_set()

        # Plan selection
        selection_frame = ttk.LabelFrame(dialog, text=_("finance_gui.transaction_manager.select_plan_frame"), padding=15)
        selection_frame.pack(fill='x', padx=20, pady=10)

        ttk.Label(selection_frame, text=_("finance_gui.transaction_manager.student_id_label"), font=('Arial', 12)).pack(anchor='w')
        student_id_var = tk.StringVar()
        ttk.Entry(selection_frame, textvariable=student_id_var, font=('Arial', 12)).pack(anchor='w', pady=5)

        def load_student_plans():
            student_id = student_id_var.get().strip()
            if not student_id:
                return

            try:
                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                SELECT spp.payment_plan_id, spp.total_amount, spp.remaining_amount,
                       spp.status, ppt.template_name
                FROM student_payment_plans spp
                JOIN payment_plan_templates ppt ON spp.template_id = ppt.template_id
                WHERE spp.student_id = ? AND spp.status = 'active'
                ''', (student_id,))

                plans = cursor.fetchall()

                # Clear existing items
                for item in plans_tree.get_children():
                    plans_tree.delete(item)

                for plan in plans:
                    plan_id, total, remaining, status, template = plan
                    plans_tree.insert('', 'end', values=(
                        plan_id, template, f"\u00a3{total:.2f}", f"\u00a3{remaining:.2f}", status
                    ))

                conn.close()

            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.load_plans_failed", error=str(e)))

        ttk.Button(selection_frame, text=_("finance_gui.transaction_manager.btn_load_plans"), command=load_student_plans).pack(anchor='w', pady=5)

        # Plans display
        plans_frame = ttk.LabelFrame(dialog, text=_("finance_gui.transaction_manager.active_plans_frame"), padding=15)
        plans_frame.pack(fill='both', expand=True, padx=20, pady=10)

        columns = ('Plan ID', 'Template', 'Total', 'Remaining', 'Status')
        plans_tree = ttk.Treeview(plans_frame, columns=columns, show='headings', height=6)

        for col in columns:
            plans_tree.heading(col, text=col)
            plans_tree.column(col, width=100, anchor='center')

        plans_tree.pack(fill='both', expand=True)

        # Modification options
        modify_frame = ttk.LabelFrame(dialog, text=_("finance_gui.transaction_manager.modifications_frame"), padding=15)
        modify_frame.pack(fill='x', padx=20, pady=10)

        def suspend_plan():
            selection = plans_tree.selection()
            if not selection:
                messagebox.showwarning(_("finance_gui.messages.no_selection"), _("finance_gui.transaction_manager.select_plan_to_suspend"))
                return

            plan_id = plans_tree.item(selection[0])['values'][0]
            if messagebox.askyesno(_("finance_gui.transaction_manager.confirm_title"), _("finance_gui.transaction_manager.suspend_confirm", plan_id=plan_id)):
                try:
                    conn = get_connection()
                    cursor = conn.cursor()

                    cursor.execute('''
                    UPDATE student_payment_plans
                    SET status = 'suspended', updated_at = ?
                    WHERE payment_plan_id = ?
                    ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), plan_id))

                    conn.commit()
                    conn.close()

                    messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.transaction_manager.plan_suspended_success"))
                    load_student_plans()

                except Exception as e:
                    messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.suspend_plan_failed", error=str(e)))

        ttk.Button(modify_frame, text=_("finance_gui.transaction_manager.btn_suspend_plan"), command=suspend_plan).pack(side='left', padx=10)
        ttk.Button(modify_frame, text=_("finance_gui.transaction_manager.btn_cancel_plan_action"),
                  command=lambda: self.cancel_selected_plan(plans_tree)).pack(side='left', padx=10)
        ttk.Button(modify_frame, text=_("finance_gui.transaction_manager.btn_close"), command=dialog.destroy).pack(side='right', padx=10)


    def cancel_selected_plan(self, tree_widget):
        """Cancel selected payment plan"""
        selection = tree_widget.selection()
        if not selection:
            messagebox.showwarning(_("finance_gui.messages.no_selection"), _("finance_gui.transaction_manager.select_plan_to_cancel"))
            return

        plan_id = tree_widget.item(selection[0])['values'][0]

        if messagebox.askyesno(_("finance_gui.transaction_manager.confirm_cancel_title"),
                              _("finance_gui.transaction_manager.cancel_confirm", plan_id=plan_id)):
            try:
                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                UPDATE student_payment_plans
                SET status = 'cancelled', updated_at = ?
                WHERE payment_plan_id = ?
                ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), plan_id))

                conn.commit()
                conn.close()

                messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.transaction_manager.plan_cancelled_success"))
                self.refresh_payment_plans()

            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.cancel_plan_failed", error=str(e)))


    def gui_cancel_payment_plan(self):
        """GUI for cancelling payment plans"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.transaction_manager.cancel_plan_dialog_title"))
        dialog.geometry("600x400")
        dialog.transient(self.root)
        dialog.grab_set()

        # Student selection
        student_frame = ttk.LabelFrame(dialog, text=_("finance_gui.transaction_manager.find_plan_frame"), padding=15)
        student_frame.pack(fill='x', padx=20, pady=10)

        ttk.Label(student_frame, text=_("finance_gui.transaction_manager.student_id_label"), font=('Arial', 12)).pack(anchor='w')
        student_id_var = tk.StringVar()
        ttk.Entry(student_frame, textvariable=student_id_var, font=('Arial', 12)).pack(anchor='w', pady=5)

        def load_cancellable_plans():
            student_id = student_id_var.get().strip()
            if not student_id:
                return

            try:
                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                SELECT spp.payment_plan_id, ppt.template_name, spp.total_amount,
                       spp.remaining_amount, spp.start_date, spp.status
                FROM student_payment_plans spp
                JOIN payment_plan_templates ppt ON spp.template_id = ppt.template_id
                WHERE spp.student_id = ? AND spp.status IN ('active', 'suspended')
                ORDER BY spp.start_date DESC
                ''', (student_id,))

                plans = cursor.fetchall()

                # Clear existing items
                for item in cancel_tree.get_children():
                    cancel_tree.delete(item)

                for plan in plans:
                    plan_id, template, total, remaining, start_date, status = plan
                    cancel_tree.insert('', 'end', values=(
                        plan_id, template, f"\u00a3{total:.2f}",
                        f"\u00a3{remaining:.2f}", start_date, status
                    ))

                conn.close()

            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.load_plans_failed", error=str(e)))

        ttk.Button(student_frame, text=_("finance_gui.transaction_manager.btn_find_plans"), command=load_cancellable_plans).pack(anchor='w', pady=5)

        # Plans display
        plans_frame = ttk.LabelFrame(dialog, text=_("finance_gui.transaction_manager.payment_plans_frame"), padding=15)
        plans_frame.pack(fill='both', expand=True, padx=20, pady=10)

        columns = ('Plan ID', 'Template', 'Total', 'Remaining', 'Start Date', 'Status')
        cancel_tree = ttk.Treeview(plans_frame, columns=columns, show='headings', height=8)

        for col in columns:
            cancel_tree.heading(col, text=col)
            cancel_tree.column(col, width=100, anchor='center')

        cancel_tree.pack(fill='both', expand=True)

        # Cancellation reason
        reason_frame = ttk.LabelFrame(dialog, text=_("finance_gui.transaction_manager.cancellation_details_frame"), padding=15)
        reason_frame.pack(fill='x', padx=20, pady=10)

        ttk.Label(reason_frame, text=_("finance_gui.transaction_manager.cancellation_reason_label"), font=('Arial', 12)).pack(anchor='w')
        reason_text = tk.Text(reason_frame, height=3, width=50, font=('Arial', 10))
        reason_text.pack(fill='x', pady=5)

        def cancel_plan():
            selection = cancel_tree.selection()
            if not selection:
                messagebox.showwarning(_("finance_gui.messages.no_selection"), _("finance_gui.transaction_manager.select_plan_to_cancel"))
                return

            reason = reason_text.get("1.0", tk.END).strip()
            if not reason:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.reason_required"))
                return

            plan_data = cancel_tree.item(selection[0])['values']
            plan_id = plan_data[0]
            remaining_amount = float(plan_data[3].replace('\u00a3', ''))

            if messagebox.askyesno(_("finance_gui.transaction_manager.confirm_cancel_title"),
                                  _("finance_gui.transaction_manager.cancel_confirm_detailed", plan_id=plan_id, remaining=remaining_amount)):
                try:
                    self.cancel_selected_plan(cancel_tree)
                    dialog.destroy()

                except Exception as e:
                    messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.cancel_plan_failed", error=str(e)))

        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text=_("finance_gui.transaction_manager.btn_cancel_plan_action"), command=cancel_plan).pack(side='left', padx=10)
        ttk.Button(button_frame, text=_("finance_gui.transaction_manager.btn_close"), command=dialog.destroy).pack(side='left', padx=10)
