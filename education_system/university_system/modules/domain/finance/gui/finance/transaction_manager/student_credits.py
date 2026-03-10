"""Student credit management GUI"""

from education_system.university_system.modules.domain.finance.gui.finance.transaction_manager._imports import (
    tk, ttk, messagebox, _, sys, io, datetime, get_connection,
    add_student_credit, apply_credit_to_fees, view_credit_history,
    view_student_credits, auth,
)
from tkinter.scrolledtext import ScrolledText


class StudentCreditsMixin:
    """Mixin for student credit management"""

    def gui_apply_credit_to_fees(self):
        """GUI wrapper for apply_credit_to_fees"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.transaction_manager.apply_credit_title"))
        dialog.geometry("500x350")
        dialog.transient(self.root)
        dialog.grab_set()

        form_frame = ttk.LabelFrame(dialog, text=_("finance_gui.transaction_manager.credit_application_frame"), padding=20)
        form_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # Student ID
        ttk.Label(form_frame, text=_("finance_gui.transaction_manager.student_id_label")).pack(anchor='w', pady=5)
        student_id_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=student_id_var).pack(anchor='w', fill='x', pady=5)

        # Credit ID
        ttk.Label(form_frame, text=_("finance_gui.transaction_manager.credit_id_label")).pack(anchor='w', pady=5)
        credit_id_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=credit_id_var).pack(anchor='w', fill='x', pady=5)

        # Amount to apply
        ttk.Label(form_frame, text=_("finance_gui.transaction_manager.amount_to_apply_label")).pack(anchor='w', pady=5)
        amount_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=amount_var).pack(anchor='w', fill='x', pady=5)

        def apply_credit():
            try:
                student_id = student_id_var.get().strip()
                credit_id = int(credit_id_var.get())
                amount = float(amount_var.get())

                if not all([student_id, credit_id, amount > 0]):
                    messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.all_fields_required"))
                    return

                apply_credit_to_fees(student_id, credit_id, amount)
                messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.transaction_manager.credit_applied_success"))
                dialog.destroy()

            except ValueError:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.invalid_credit_id_amount"))
            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.apply_credit_failed", error=str(e)))

        ttk.Button(form_frame, text=_("finance_gui.transaction_manager.btn_apply_credit"), command=apply_credit).pack(pady=20)


    def gui_view_credit_history(self):
        """GUI wrapper for view_credit_history"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.transaction_manager.view_credit_history_title"))
        dialog.geometry("700x500")
        dialog.transient(self.root)
        dialog.grab_set()

        # Student ID input
        input_frame = ttk.Frame(dialog, padding=10)
        input_frame.pack(fill='x')

        ttk.Label(input_frame, text=_("finance_gui.transaction_manager.student_id_label")).pack(side='left', padx=5)
        student_id_var = tk.StringVar()
        ttk.Entry(input_frame, textvariable=student_id_var, width=15).pack(side='left', padx=5)

        def show_history():
            student_id = student_id_var.get().strip()
            if not student_id:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.student_id_required"))
                return

            try:
                old_stdout = sys.stdout
                sys.stdout = mystdout = io.StringIO()

                view_credit_history(student_id)

                output = mystdout.getvalue()
                sys.stdout = old_stdout

                history_text.delete('1.0', tk.END)
                history_text.insert('1.0', output)

            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.view_credit_history_failed", error=str(e)))

        ttk.Button(input_frame, text=_("finance_gui.transaction_manager.btn_view_history"), command=show_history).pack(side='left', padx=10)

        # History display
        history_text = ScrolledText(dialog, height=20, width=80, font=('Courier', 10))
        history_text.pack(fill='both', expand=True, padx=10, pady=10)


    def gui_view_student_credits(self):
        """GUI wrapper for view_student_credits"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.transaction_manager.view_credits_title"))
        dialog.geometry("600x400")
        dialog.transient(self.root)
        dialog.grab_set()

        # Student ID input
        input_frame = ttk.Frame(dialog, padding=10)
        input_frame.pack(fill='x')

        ttk.Label(input_frame, text=_("finance_gui.transaction_manager.student_id_label")).pack(side='left', padx=5)
        student_id_var = tk.StringVar()
        ttk.Entry(input_frame, textvariable=student_id_var, width=15).pack(side='left', padx=5)

        def show_credits():
            student_id = student_id_var.get().strip()
            if not student_id:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.student_id_required"))
                return

            try:
                old_stdout = sys.stdout
                sys.stdout = mystdout = io.StringIO()

                view_student_credits(student_id)

                output = mystdout.getvalue()
                sys.stdout = old_stdout

                credits_text.delete('1.0', tk.END)
                credits_text.insert('1.0', output)

            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.view_credits_failed", error=str(e)))

        ttk.Button(input_frame, text=_("finance_gui.transaction_manager.btn_view_credits"), command=show_credits).pack(side='left', padx=10)

        # Credits display
        credits_text = ScrolledText(dialog, height=20, width=70, font=('Courier', 10))
        credits_text.pack(fill='both', expand=True, padx=10, pady=10)


    def gui_add_student_credit(self):
        """GUI wrapper for add_student_credit"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.transaction_manager.add_credit_title"))
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()

        form_frame = ttk.LabelFrame(dialog, text=_("finance_gui.transaction_manager.credit_details_frame"), padding=20)
        form_frame.pack(fill='x', padx=20, pady=20)

        # Student ID
        ttk.Label(form_frame, text=_("finance_gui.transaction_manager.student_id_label")).pack(anchor='w', pady=5)
        student_id_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=student_id_var).pack(anchor='w', fill='x', pady=5)

        # Credit amount
        ttk.Label(form_frame, text=_("finance_gui.transaction_manager.credit_amount_label")).pack(anchor='w', pady=5)
        amount_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=amount_var).pack(anchor='w', fill='x', pady=5)

        # Credit source
        ttk.Label(form_frame, text=_("finance_gui.transaction_manager.credit_source_label")).pack(anchor='w', pady=5)
        source_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=source_var).pack(anchor='w', fill='x', pady=5)

        # Description
        ttk.Label(form_frame, text=_("finance_gui.transaction_manager.description_label")).pack(anchor='w', pady=5)
        desc_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=desc_var).pack(anchor='w', fill='x', pady=5)

        def add_credit():
            try:
                student_id = student_id_var.get().strip()
                amount = float(amount_var.get())
                source = source_var.get().strip()
                description = desc_var.get().strip()

                if not all([student_id, amount > 0, source]):
                    messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.all_fields_required"))
                    return

                add_student_credit(student_id, amount, source, description)
                messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.transaction_manager.credit_added_success"))
                dialog.destroy()

            except ValueError:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.invalid_amount"))
            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.add_credit_failed", error=str(e)))

        ttk.Button(form_frame, text=_("finance_gui.transaction_manager.btn_add_credit"), command=add_credit).pack(pady=20)


    def gui_manage_student_credits(self):
        """GUI wrapper for student credits management"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.transaction_manager.manage_credits_title"))
        dialog.geometry("900x600")
        dialog.transient(self.root)
        dialog.grab_set()

        # Create notebook for different credit operations
        notebook = ttk.Notebook(dialog)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)

        # View credits tab
        view_tab = ttk.Frame(notebook)
        notebook.add(view_tab, text=_("finance_gui.transaction_manager.tab_view_credits"))

        # Student selection for viewing
        search_frame = ttk.LabelFrame(view_tab, text=_("finance_gui.transaction_manager.student_search_frame"), padding=10)
        search_frame.pack(fill='x', padx=10, pady=5)

        ttk.Label(search_frame, text=_("finance_gui.transaction_manager.student_id_label")).pack(side='left', padx=5)
        view_student_var = tk.StringVar()
        ttk.Entry(search_frame, textvariable=view_student_var, width=15).pack(side='left', padx=5)
        ttk.Button(search_frame, text=_("finance_gui.transaction_manager.btn_load_credits"),
                  command=lambda: self.load_student_credits(view_student_var.get(), credits_tree)).pack(side='left', padx=10)

        # Credits display
        credits_frame = ttk.LabelFrame(view_tab, text=_("finance_gui.transaction_manager.active_credits_frame"), padding=10)
        credits_frame.pack(fill='both', expand=True, padx=10, pady=5)

        columns = ('Credit ID', 'Amount', 'Remaining', 'Source', 'Description', 'Expires', 'Created')
        credits_tree = ttk.Treeview(credits_frame, columns=columns, show='headings', height=12)

        for col in columns:
            credits_tree.heading(col, text=col)
            width = 150 if col in ['Description'] else 100
            credits_tree.column(col, width=width, anchor='center')

        credits_scroll = ttk.Scrollbar(credits_frame, orient='vertical', command=credits_tree.yview)
        credits_tree.configure(yscrollcommand=credits_scroll.set)

        credits_tree.pack(side='left', fill='both', expand=True)
        credits_scroll.pack(side='right', fill='y')

        # Add credit tab
        add_tab = ttk.Frame(notebook)
        notebook.add(add_tab, text=_("finance_gui.transaction_manager.tab_add_credit"))

        add_frame = ttk.LabelFrame(add_tab, text=_("finance_gui.transaction_manager.add_new_credit_frame"), padding=20)
        add_frame.pack(fill='x', padx=20, pady=20)

        # Student ID for adding credit
        ttk.Label(add_frame, text=_("finance_gui.transaction_manager.student_id_label"), font=('Arial', 12)).pack(anchor='w', pady=5)
        add_student_var = tk.StringVar()
        ttk.Entry(add_frame, textvariable=add_student_var, font=('Arial', 12), width=20).pack(anchor='w', pady=5)

        # Credit amount
        ttk.Label(add_frame, text=_("finance_gui.transaction_manager.credit_amount_pound_label"), font=('Arial', 12)).pack(anchor='w', pady=(15, 5))
        credit_amount_var = tk.StringVar()
        ttk.Entry(add_frame, textvariable=credit_amount_var, font=('Arial', 12), width=15).pack(anchor='w', pady=5)

        # Credit source
        ttk.Label(add_frame, text=_("finance_gui.transaction_manager.credit_source_label"), font=('Arial', 12)).pack(anchor='w', pady=(15, 5))
        source_var = tk.StringVar(value="adjustment")
        source_combo = ttk.Combobox(add_frame, textvariable=source_var,
                                   values=["overpayment", "refund", "scholarship", "adjustment", "goodwill", "other"],
                                   state='readonly', font=('Arial', 12))
        source_combo.pack(anchor='w', pady=5)

        # Description
        ttk.Label(add_frame, text=_("finance_gui.transaction_manager.description_label"), font=('Arial', 12)).pack(anchor='w', pady=(15, 5))
        desc_entry_var = tk.StringVar()
        ttk.Entry(add_frame, textvariable=desc_entry_var, font=('Arial', 12), width=50).pack(anchor='w', pady=5)

        # Expiry date
        ttk.Label(add_frame, text=_("finance_gui.transaction_manager.expiry_date_label"), font=('Arial', 12)).pack(anchor='w', pady=(15, 5))
        expiry_var = tk.StringVar()
        ttk.Entry(add_frame, textvariable=expiry_var, font=('Arial', 12), width=15).pack(anchor='w', pady=5)

        def add_credit():
            try:
                student_id = add_student_var.get().strip()
                credit_amount = float(credit_amount_var.get())
                credit_source = source_var.get()
                description = desc_entry_var.get().strip()
                expiry_date = expiry_var.get().strip()

                if not all([student_id, credit_amount > 0, credit_source]):
                    messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.student_amount_source_required"))
                    return

                # Validate expiry date if provided
                if expiry_date:
                    try:
                        datetime.strptime(expiry_date, '%Y-%m-%d')
                    except ValueError:
                        messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.invalid_date_format"))
                        return
                else:
                    expiry_date = None

                # Check if student exists
                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('SELECT COUNT(*) FROM students WHERE student_id = ?', (student_id,))
                if cursor.fetchone()[0] == 0:
                    messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.student_not_found", student_id=student_id))
                    conn.close()
                    return

                # Create the credit
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute('''
                INSERT INTO student_credits
                (student_id, credit_amount, remaining_amount, credit_source, description,
                 expiry_date, created_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (student_id, credit_amount, credit_amount, credit_source, description,
                      expiry_date, auth.current_user['username'], now, now))

                credit_id = cursor.lastrowid
                conn.commit()
                conn.close()

                messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.transaction_manager.credit_added_with_id", credit_id=credit_id))

                # Clear form
                add_student_var.set("")
                credit_amount_var.set("")
                desc_entry_var.set("")
                expiry_var.set("")

                self.update_status(f"Credit of \u00a3{credit_amount:.2f} added for student {student_id}")

            except ValueError:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.invalid_credit_amount"))
            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.add_credit_failed", error=str(e)))

        ttk.Button(add_frame, text=_("finance_gui.transaction_manager.btn_add_credit"), command=add_credit).pack(anchor='w', pady=20)


    def load_student_credits(self, student_id, tree_widget):
        """Load student credits into tree widget"""
        if not student_id:
            return

        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT credit_id, credit_amount, remaining_amount, credit_source, description,
                   expiry_date, created_at, status
            FROM student_credits
            WHERE student_id = ? AND status = 'active'
            ORDER BY created_at DESC
            ''', (student_id,))

            credits = cursor.fetchall()

            # Clear existing items
            for item in tree_widget.get_children():
                tree_widget.delete(item)

            total_credits = 0
            for credit in credits:
                credit_id, amount, remaining, source, description, expiry, created, status = credit
                expiry_str = expiry if expiry else "No expiry"
                desc_str = description if description else "N/A"

                tree_widget.insert('', 'end', values=(
                    credit_id, f"\u00a3{amount:.2f}", f"\u00a3{remaining:.2f}",
                    source, desc_str, expiry_str, created
                ))
                total_credits += remaining

            # Update status with total
            if credits:
                self.update_status(f"Student {student_id} has \u00a3{total_credits:.2f} in active credits")
            else:
                self.update_status(f"No active credits found for student {student_id}")

            conn.close()

        except Exception as e:
            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.load_credits_failed", error=str(e)))
