"""Methods create_overview_section through delete_fine."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import finance_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class LibraryFinanceManager:
    def create_overview_section(self, parent):
        """Create financial overview section"""
        metrics_frame = tk.Frame(parent, bg='white')
        metrics_frame.pack(fill='x', padx=10, pady=10)

        self.create_metric_card(metrics_frame, "Outstanding Fines", "£0.00", self.colors['danger'])
        self.create_metric_card(metrics_frame, "Collected This Month", "£0.00", self.colors['success'])
        self.create_metric_card(metrics_frame, "Total Revenue (YTD)", "£0.00", self.colors['info'])
        self.create_metric_card(metrics_frame, "Total Refunds", "£0.00", self.colors['warning'])
        self.create_metric_card(metrics_frame, "Book Investment", "£0.00", self.colors['library'])

        self.overview_chart_frame = tk.Frame(parent, bg='white')
        self.overview_chart_frame.pack(fill='both', expand=True, padx=10, pady=10)

        tk.Button(parent, text=_t('gui.academics.library.finance_parts.libraryfinancemanager_create_overview_section.buttons.refresh_overview', default="Refresh Overview"), command=self.refresh_overview,
                  bg=self.colors['secondary'], fg='white', font=('Arial', 11, 'bold'),
                  padx=20, pady=8).pack(pady=10)

        self.root.after(100, self.refresh_overview)

    def create_metric_card(self, parent, title, value, color):
        """Create a metric display card"""
        card = tk.Frame(parent, bg=color, relief='raised', bd=2)
        card.pack(side='left', fill='both', expand=True, padx=5, pady=5)

        tk.Label(card, text=title, bg=color, fg='white', font=('Arial', 11, 'bold')).pack(pady=5)
        label = tk.Label(card, text=value, bg=color, fg='white', font=('Arial', 20, 'bold'))
        label.pack(pady=10)

        attr_name = title.lower().replace(' ', '_').replace('(', '').replace(')', '').replace('-', '_')
        setattr(self, f"{attr_name}_label", label)

    def load_all_fines(self):
        """Load all outstanding fines"""
        try:
            for item in self.fines_tree.get_children():
                self.fines_tree.delete(item)

            from education_system.systems.university.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT bl.loan_id, bl.user_id, s.first_name || ' ' || s.last_name as name,
                       bl.book_id, b.title,
                       CAST(julianday('now') - julianday(bl.due_date) as INTEGER) as days_overdue,
                       bl.fine_amount, bl.status
                FROM book_loans bl
                JOIN books b ON bl.book_id = b.book_id
                LEFT JOIN students s ON bl.user_id = s.student_id
                WHERE bl.fine_amount >= 0.01
                ORDER BY bl.fine_amount DESC
            ''')

            fines = cursor.fetchall()
            total_fines = 0
            count = 0

            for fine in fines:
                loan_id, user_id, name, book_id, title, days_overdue, fine_amount, status = fine
                total_fines += fine_amount
                count += 1
                self.fines_tree.insert('', 'end', values=(
                    loan_id, user_id, name or 'N/A', book_id, title[:40] if title else 'N/A',
                    days_overdue, f"£{fine_amount:.2f}", status
                ))

            conn.close()
            self.fines_summary_label.config(text=f"Total Outstanding Fines: £{total_fines:,.2f} | Total Items: {count}")

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to load fines:\n{str(e)}")

    def search_fines(self):
        """Search fines by user ID or name"""
        search_term = self.search_var.get().strip()
        if not search_term:
            self.load_all_fines()
            return

        try:
            for item in self.fines_tree.get_children():
                self.fines_tree.delete(item)

            from education_system.systems.university.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT bl.loan_id, bl.user_id, s.first_name || ' ' || s.last_name as name,
                       bl.book_id, b.title,
                       CAST(julianday('now') - julianday(bl.due_date) as INTEGER) as days_overdue,
                       bl.fine_amount, bl.status
                FROM book_loans bl
                JOIN books b ON bl.book_id = b.book_id
                LEFT JOIN students s ON bl.user_id = s.student_id
                WHERE bl.fine_amount >= 0.01
                  AND (bl.user_id LIKE ? OR s.first_name || ' ' || s.last_name LIKE ?)
                ORDER BY bl.fine_amount DESC
            ''', (f'%{search_term}%', f'%{search_term}%'))

            fines = cursor.fetchall()
            total_fines = 0
            count = 0

            for fine in fines:
                loan_id, user_id, name, book_id, title, days_overdue, fine_amount, status = fine
                total_fines += fine_amount
                count += 1
                self.fines_tree.insert('', 'end', values=(
                    loan_id, user_id, name or 'N/A', book_id, title[:40] if title else 'N/A',
                    days_overdue, f"£{fine_amount:.2f}", status
                ))

            conn.close()
            self.fines_summary_label.config(text=f"Search Results - Total Fines: £{total_fines:,.2f} | Items: {count}")

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to search fines:\n{str(e)}")

    def create_fine_dialog(self):
        """Dialog to create a new fine"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t('gui.academics.library.finance_parts.libraryfinancemanager_create_overview_section.windows.create_new_fine', default="Create New Fine"))
        dialog.geometry("400x300")
        dialog.transient(self.root)

        tk.Label(dialog, text=_t('gui.academics.library.finance_parts.libraryfinancemanager_create_overview_section.labels.loan_id', default="Loan ID:"), font=('Arial', 10)).grid(row=0, column=0, padx=10, pady=10, sticky='e')
        loan_id_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=loan_id_var, width=30).grid(row=0, column=1, padx=10, pady=10)

        tk.Label(dialog, text=_t('gui.academics.library.finance_parts.libraryfinancemanager_create_overview_section.labels.fine_amount', default="Fine Amount (£):"), font=('Arial', 10)).grid(row=1, column=0, padx=10, pady=10, sticky='e')
        amount_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=amount_var, width=30).grid(row=1, column=1, padx=10, pady=10)

        def create():
            loan_id = loan_id_var.get().strip()
            amount_str = amount_var.get().strip()

            if not loan_id or not amount_str:
                messagebox.showwarning(_t('gui.academics.library.finance_parts.libraryfinancemanager_create_overview_section.dialogs.input_required', default="Input Required"), _t('gui.academics.library.finance_parts.libraryfinancemanager_create_overview_section.dialogs.please_fill_all_fields', default="Please fill all fields."), parent=dialog)
                return

            try:
                amount = float(amount_str)
                if amount <= 0:
                    messagebox.showwarning(_t('gui.academics.library.finance_parts.libraryfinancemanager_create_overview_section.dialogs.invalid_amount', default="Invalid Amount"), _t('gui.academics.library.finance_parts.libraryfinancemanager_create_overview_section.dialogs.fine_amount_must_be_greater_than_0', default="Fine amount must be greater than 0."), parent=dialog)
                    return

                from education_system.systems.university.infrastructure.database.db import get_connection
                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('UPDATE book_loans SET fine_amount = ? WHERE loan_id = ?', (amount, loan_id))
                if cursor.rowcount == 0:
                    messagebox.showerror(_("common.error"), f"Loan ID {loan_id} not found.", parent=dialog)
                    conn.close()
                    return

                cursor.execute('''
                    SELECT bl.user_id, b.title, bl.due_date,
                           CAST((julianday('now') - julianday(bl.due_date)) AS INTEGER) as days_overdue
                    FROM book_loans bl JOIN books b ON bl.book_id = b.book_id WHERE bl.loan_id = ?
                ''', (loan_id,))
                loan_details = cursor.fetchone()
                conn.commit()
                conn.close()

                if loan_details:
                    user_id, book_title, due_date, days_overdue = loan_details
                    user_info = self.get_user_email(user_id)
                    if user_info:
                        self.send_fine_notification_email(user_info, amount, book_title, due_date, max(days_overdue, 0))

                messagebox.showinfo(_("common.success"), f"Fine of £{amount:.2f} created for Loan ID {loan_id}.", parent=dialog)
                dialog.destroy()
                self.load_all_fines()

            except ValueError:
                messagebox.showwarning(_t('gui.academics.library.finance_parts.libraryfinancemanager_create_overview_section.dialogs.invalid_input', default="Invalid Input"), _t('gui.academics.library.finance_parts.libraryfinancemanager_create_overview_section.dialogs.please_enter_a_valid_amount', default="Please enter a valid amount."), parent=dialog)
            except Exception as e:
                messagebox.showerror(_("common.error"), f"Failed to create fine:\n{str(e)}", parent=dialog)

        tk.Button(dialog, text=_t('gui.academics.library.finance_parts.libraryfinancemanager_create_overview_section.buttons.create_fine', default="Create Fine"), command=create, bg=self.colors['success'], fg='white',
                  font=('Arial', 10, 'bold'), padx=20, pady=8).grid(row=2, column=0, columnspan=2, pady=20)

    def edit_fine_dialog(self):
        """Dialog to edit an existing fine"""
        selection = self.fines_tree.selection()
        if not selection:
            messagebox.showwarning(_t('gui.academics.library.finance_parts.libraryfinancemanager_create_overview_section.dialogs.no_selection', default="No Selection"), _t('gui.academics.library.finance_parts.libraryfinancemanager_create_overview_section.dialogs.please_select_a_fine_to_edit', default="Please select a fine to edit."))
            return

        values = self.fines_tree.item(selection[0])['values']
        loan_id = values[0]
        current_amount = float(str(values[6]).replace('£', ''))

        dialog = tk.Toplevel(self.root)
        dialog.title(_t('gui.academics.library.finance_parts.libraryfinancemanager_create_overview_section.windows.edit_fine', default="Edit Fine"))
        dialog.geometry("400x250")
        dialog.transient(self.root)

        tk.Label(dialog, text=f"Loan ID: {loan_id}", font=('Arial', 11, 'bold')).pack(pady=10)
        tk.Label(dialog, text=f"Current Fine: £{current_amount:.2f}", font=('Arial', 10)).pack(pady=5)
        tk.Label(dialog, text=_t('gui.academics.library.finance_parts.libraryfinancemanager_create_overview_section.labels.new_fine_amount', default="New Fine Amount (£):"), font=('Arial', 10)).pack(pady=5)
        amount_var = tk.StringVar(value=str(current_amount))
        ttk.Entry(dialog, textvariable=amount_var, width=30).pack(pady=5)

        def update():
            amount_str = amount_var.get().strip()
            if not amount_str:
                messagebox.showwarning(_t('gui.academics.library.finance_parts.libraryfinancemanager_create_overview_section.dialogs.input_required', default="Input Required"), _t('gui.academics.library.finance_parts.libraryfinancemanager_create_overview_section.dialogs.please_enter_an_amount', default="Please enter an amount."), parent=dialog)
                return
            try:
                amount = float(amount_str)
                if amount < 0:
                    messagebox.showwarning(_t('gui.academics.library.finance_parts.libraryfinancemanager_create_overview_section.dialogs.invalid_amount', default="Invalid Amount"), _t('gui.academics.library.finance_parts.libraryfinancemanager_create_overview_section.dialogs.fine_amount_cannot_be_negative', default="Fine amount cannot be negative."), parent=dialog)
                    return

                from education_system.systems.university.infrastructure.database.db import get_connection
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute('UPDATE book_loans SET fine_amount = ? WHERE loan_id = ?', (amount, loan_id))
                conn.commit()
                conn.close()

                messagebox.showinfo(_("common.success"), f"Fine updated to £{amount:.2f}.", parent=dialog)
                dialog.destroy()
                self.load_all_fines()
            except ValueError:
                messagebox.showwarning(_t('gui.academics.library.finance_parts.libraryfinancemanager_create_overview_section.dialogs.invalid_input', default="Invalid Input"), _t('gui.academics.library.finance_parts.libraryfinancemanager_create_overview_section.dialogs.please_enter_a_valid_amount', default="Please enter a valid amount."), parent=dialog)
            except Exception as e:
                messagebox.showerror(_("common.error"), f"Failed to update fine:\n{str(e)}", parent=dialog)

        tk.Button(dialog, text=_t('gui.academics.library.finance_parts.libraryfinancemanager_create_overview_section.buttons.update_fine', default="Update Fine"), command=update, bg=self.colors['warning'], fg='white',
                  font=('Arial', 10, 'bold'), padx=20, pady=8).pack(pady=20)

    def delete_fine(self):
        """Delete (waive) a fine"""
        selection = self.fines_tree.selection()
        if not selection:
            messagebox.showwarning(_t('gui.academics.library.finance_parts.libraryfinancemanager_create_overview_section.dialogs.no_selection', default="No Selection"), _t('gui.academics.library.finance_parts.libraryfinancemanager_create_overview_section.dialogs.please_select_a_fine_to_delete', default="Please select a fine to delete."))
            return

        values = self.fines_tree.item(selection[0])['values']
        loan_id = values[0]
        fine_amount = values[6]

        if not messagebox.askyesno(_t('gui.academics.library.finance_parts.libraryfinancemanager_create_overview_section.dialogs.confirm_deletion', default="Confirm Deletion"),
            f"Are you sure you want to waive this fine?\n\nLoan ID: {loan_id}\nAmount: {fine_amount}"):
            return

        try:
            from education_system.systems.university.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT bl.user_id, b.title FROM book_loans bl
                JOIN books b ON bl.book_id = b.book_id WHERE bl.loan_id = ?
            ''', (loan_id,))
            loan_details = cursor.fetchone()

            cursor.execute('UPDATE book_loans SET fine_amount = 0 WHERE loan_id = ?', (loan_id,))
            conn.commit()
            conn.close()

            if loan_details:
                user_id, book_title = loan_details
                user_info = self.get_user_email(user_id)
                fine_amount_value = float(str(fine_amount).replace('£', ''))
                if user_info:
                    self.send_fine_waived_email(user_info, fine_amount_value, book_title)

            messagebox.showinfo(_("common.success"), _t('gui.academics.library.finance_parts.libraryfinancemanager_create_overview_section.dialogs.fine_waived_successfully', default="Fine waived successfully."))
            self.load_all_fines()

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to delete fine:\n{str(e)}")
