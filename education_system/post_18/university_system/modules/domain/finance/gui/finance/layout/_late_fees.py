"""Late fees management mixin for LayoutManager."""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from education_system.post_18.university_system.infrastructure.database.db import get_connection
from education_system.post_18.university_system.infrastructure.auth import get_global_auth
from education_system.post_18.university_system.core.i18n import get_text as _


class LateFeesMixin:
    """Late fees: apply, waive, calculate overdue, refresh."""

    def create_late_fees_tab(self):
        """Create late fees management tab"""
        late_fees_frame = tk.Frame(self.content_frame, bg='white')
        self.tab_frames['late_fees'] = late_fees_frame

        # Title
        title_label = tk.Label(late_fees_frame, text=_("finance_gui.tabs.late_fees.title"),
                               font=('Arial', 18, 'bold'), bg='white')
        title_label.pack(pady=10)

        # Toolbar
        toolbar = tk.Frame(late_fees_frame, bg='white')
        toolbar.pack(fill='x', padx=10, pady=10)

        tk.Button(toolbar, text=_("finance_gui.buttons.apply_late_fee"), command=self._apply_late_fee,
                 bg=self.colors['warning'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)
        tk.Button(toolbar, text=_("finance_gui.buttons.waive_late_fee"), command=self._waive_late_fee,
                 bg=self.colors['success'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)
        tk.Button(toolbar, text=_("finance_gui.buttons.calculate_overdue"), command=self._calculate_overdue_fees,
                 bg=self.colors['danger'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)
        tk.Button(toolbar, text=_("finance_gui.buttons.refresh"), command=self._refresh_late_fees,
                 bg=self.colors['secondary'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='right', padx=5)

        # Late fees table
        table_frame = tk.Frame(late_fees_frame)
        table_frame.pack(fill='both', expand=True, padx=10, pady=10)

        columns = ('late_fee_id', 'student_fee_id', 'amount', 'days_overdue', 'calculation_method',
                   'applied_date', 'waived', 'waiver_reason')
        self.late_fees_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=15)

        for col in columns:
            self.late_fees_tree.heading(col, text=col.replace('_', ' ').title())
            self.late_fees_tree.column(col, width=100)

        # Scrollbars
        v_scroll = ttk.Scrollbar(table_frame, orient='vertical', command=self.late_fees_tree.yview)
        h_scroll = ttk.Scrollbar(table_frame, orient='horizontal', command=self.late_fees_tree.xview)
        self.late_fees_tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        self.late_fees_tree.grid(row=0, column=0, sticky='nsew')
        v_scroll.grid(row=0, column=1, sticky='ns')
        h_scroll.grid(row=1, column=0, sticky='ew')

        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        # Load data
        self.root.after(100, self._refresh_late_fees)

    def _apply_late_fee(self):
        """Apply a late fee to overdue student fee"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.dialogs.apply_late_fee"))
        dialog.geometry("500x400")
        dialog.transient(self.root)

        tk.Label(dialog, text=_("finance_gui.dialogs.apply_late_fee"), font=('Arial', 14, 'bold')).pack(pady=10)

        form_frame = tk.Frame(dialog)
        form_frame.pack(padx=20, pady=10, fill='both', expand=True)

        tk.Label(form_frame, text=_("finance_gui.labels.student_fee_id")).grid(row=0, column=0, sticky='w', pady=5)
        student_fee_id_entry = tk.Entry(form_frame, width=30)
        student_fee_id_entry.grid(row=0, column=1, pady=5)

        tk.Label(form_frame, text=_("finance_gui.labels.late_fee_amount")).grid(row=1, column=0, sticky='w', pady=5)
        amount_entry = tk.Entry(form_frame, width=30)
        amount_entry.grid(row=1, column=1, pady=5)

        tk.Label(form_frame, text=_("finance_gui.labels.calculation_method")).grid(row=2, column=0, sticky='w', pady=5)
        method_var = tk.StringVar(value="fixed")
        method_combo = ttk.Combobox(form_frame, textvariable=method_var,
                                    values=['fixed', 'percentage', 'daily'],
                                    state='readonly', width=27)
        method_combo.grid(row=2, column=1, pady=5)

        tk.Label(form_frame, text=_("finance_gui.labels.days_overdue")).grid(row=3, column=0, sticky='w', pady=5)
        days_entry = tk.Entry(form_frame, width=30)
        days_entry.grid(row=3, column=1, pady=5)

        def save_late_fee():
            try:
                student_fee_id = int(student_fee_id_entry.get())
                amount = float(amount_entry.get())
                method = method_var.get()
                days_overdue = int(days_entry.get())

                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                    INSERT INTO late_fees
                    (student_fee_id, late_fee_amount, calculation_method, days_overdue,
                     applied_date, waived, created_at)
                    VALUES (?, ?, ?, ?, date('now'), 0, datetime('now'))
                ''', (student_fee_id, amount, method, days_overdue))

                conn.commit()
                conn.close()

                messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.messages.late_fee_applied"))
                dialog.destroy()
                self._refresh_late_fees()
            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.messages.failed_apply_late_fee", error=str(e)))

        btn_frame = tk.Frame(dialog)
        btn_frame.pack(pady=20)
        tk.Button(btn_frame, text=_("finance_gui.buttons.save"), command=save_late_fee, bg=self.colors['success'],
                 fg='white', padx=20, pady=5).pack(side='left', padx=5)
        tk.Button(btn_frame, text=_("finance_gui.buttons.cancel"), command=dialog.destroy, bg=self.colors['danger'],
                 fg='white', padx=20, pady=5).pack(side='left', padx=5)

    def _waive_late_fee(self):
        """Waive a selected late fee"""
        selection = self.late_fees_tree.selection()
        if not selection:
            messagebox.showwarning(_("finance_gui.messages.no_selection"), _("finance_gui.messages.select_late_fee_waive"))
            return

        reason = simpledialog.askstring(_("finance_gui.dialogs.waive_late_fee"), _("finance_gui.messages.enter_waiver_reason"))
        if not reason:
            return

        try:
            auth = get_global_auth()
            late_fee_id = self.late_fees_tree.item(selection[0])['values'][0]
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE late_fees
                SET waived = 1, waiver_reason = ?, waived_date = date('now'), waived_by = ?
                WHERE late_fee_id = ?
            ''', (reason, auth.current_user.get('username', 'admin'), late_fee_id))
            conn.commit()
            conn.close()
            messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.messages.late_fee_waived"))
            self._refresh_late_fees()
        except Exception as e:
            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.messages.failed_waive_late_fee", error=str(e)))

    def _calculate_overdue_fees(self):
        """Calculate and apply late fees for all overdue student fees"""
        if not messagebox.askyesno(_("finance_gui.dialogs.confirm"), _("finance_gui.messages.confirm_calculate_overdue")):
            return

        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Find overdue fees without late fees
            cursor.execute('''
                SELECT sf.student_fee_id, sf.amount,
                       julianday('now') - julianday(sf.due_date) as days_overdue
                FROM student_fees sf
                WHERE sf.status = 'unpaid'
                AND sf.due_date < date('now')
                AND NOT EXISTS (
                    SELECT 1 FROM late_fees lf
                    WHERE lf.student_fee_id = sf.student_fee_id
                )
            ''')

            overdue_fees = cursor.fetchall()
            count = 0

            for fee_id, amount, days_overdue in overdue_fees:
                if days_overdue > 0:
                    # Apply 5% late fee
                    late_fee_amount = amount * 0.05
                    cursor.execute('''
                        INSERT INTO late_fees
                        (student_fee_id, late_fee_amount, calculation_method, days_overdue,
                         applied_date, waived, created_at)
                        VALUES (?, ?, 'percentage', ?, date('now'), 0, datetime('now'))
                    ''', (fee_id, late_fee_amount, int(days_overdue)))
                    count += 1

            conn.commit()
            conn.close()

            messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.messages.late_fees_applied_count", count=count))
            self._refresh_late_fees()
        except Exception as e:
            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.messages.failed_calculate_overdue", error=str(e)))

    def _refresh_late_fees(self):
        """Refresh late fees list"""
        try:
            # Clear existing items
            for item in self.late_fees_tree.get_children():
                self.late_fees_tree.delete(item)

            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT late_fee_id, student_fee_id, late_fee_amount, days_overdue,
                       calculation_method, applied_date, waived, waiver_reason
                FROM late_fees
                ORDER BY applied_date DESC
                LIMIT 500
            ''')

            for row in cursor.fetchall():
                self.late_fees_tree.insert('', 'end', values=tuple(row))

            conn.close()
        except Exception as e:
            print(f"Error refreshing late fees: {e}")
