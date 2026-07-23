"""Late fee calculation, waiving, and reporting"""

import tkinter as tk
from tkinter import ttk, messagebox
from education_system.post_18.university_system.core.i18n import get_text as _
from datetime import datetime
import threading

from education_system.post_18.university_system.infrastructure.database.db import get_connection

from education_system.post_18.university_system.modules.domain.finance.gui.finance.expense_manager._imports import (
    auth,
)


class LateFeesMixin:
    """Late fee management methods"""

    def create_late_fees_tab(self):
        """Create late fees management tab"""
        tab = tk.Frame(self.content_frame, bg='white')
        self.tab_frames['late_fees'] = tab

        main_frame = ttk.Frame(tab, padding=20)
        main_frame.pack(fill='both', expand=True)

        # Control buttons
        control_frame = ttk.LabelFrame(main_frame, text=_("expense_manager.labels.late_fee_management"), padding=15)
        control_frame.pack(fill='x', pady=(0, 20))

        ttk.Button(control_frame, text=_("expense_manager.buttons.calculate_late_fees"),
                  command=self.gui_calculate_late_fees, width=25).grid(row=0, column=0, padx=10, pady=5)
        ttk.Button(control_frame, text=_("expense_manager.buttons.waive_late_fee"),
                  command=self.gui_waive_late_fee, width=25).grid(row=0, column=1, padx=10, pady=5)
        ttk.Button(control_frame, text=_("expense_manager.buttons.late_fee_report"),
                  command=self.gui_late_fee_report, width=25).grid(row=0, column=2, padx=10, pady=5)

        # Late fees display
        display_frame = ttk.LabelFrame(main_frame, text=_("expense_manager.labels.outstanding_late_fees"), padding=15)
        display_frame.pack(fill='both', expand=True)

        columns = (_("expense_manager.columns.student_id"), _("expense_manager.columns.student_name"), _("expense_manager.columns.fee_type"), _("expense_manager.columns.days_overdue"), _("expense_manager.columns.late_fee"), _("expense_manager.columns.applied_date"), _("expense_manager.columns.status"))
        self.late_fees_tree = ttk.Treeview(display_frame, columns=columns, show='headings', height=12)

        for col in columns:
            self.late_fees_tree.heading(col, text=col)
            self.late_fees_tree.column(col, width=100, anchor='center')

        # Scrollbars
        late_v_scroll = ttk.Scrollbar(display_frame, orient='vertical', command=self.late_fees_tree.yview)
        late_h_scroll = ttk.Scrollbar(display_frame, orient='horizontal', command=self.late_fees_tree.xview)
        self.late_fees_tree.configure(yscrollcommand=late_v_scroll.set, xscrollcommand=late_h_scroll.set)

        self.late_fees_tree.pack(side='left', fill='both', expand=True)
        late_v_scroll.pack(side='right', fill='y')
        late_h_scroll.pack(side='bottom', fill='x')

        self.refresh_late_fees()

    def calculate_late_fees(self):
        """Calculate late fees"""
        if messagebox.askyesno(_("expense_manager.dialogs.calculate_late_fees_title"), _("expense_manager.dialogs.confirm_late_fees")):
            try:
                # Call the backend implementation instead
                result = self.calculate_late_fees_backend()
                self.refresh_fees()
                self.update_status(_("expense_manager.messages.late_fees_calculated", count=result['count'], total=result['total']))
            except Exception as e:
                messagebox.showerror(_("common.error"), _("expense_manager.errors.failed_calculate_late_fees", error=str(e)))

    def gui_calculate_late_fees(self):
        """GUI wrapper for calculating late fees"""
        if messagebox.askyesno(_("common.confirm"), _("expense_manager.dialogs.confirm_late_fees")):
            try:
                # Call the original function logic in a thread to avoid blocking UI
                def calculate_fees():
                    self.update_status(_("expense_manager.status.calculating_late_fees"))
                    result = self.calculate_late_fees_backend()

                    messagebox.showinfo(_("expense_manager.dialogs.calculate_late_fees_title"),
                                       _("expense_manager.messages.late_fees_calculated", count=result['count'], total=result['total']))

                    self.refresh_late_fees()
                    self.update_status(_("expense_manager.status.late_fees_calculation_completed"))

                thread = threading.Thread(target=calculate_fees)
                thread.daemon = True
                thread.start()

            except Exception as e:
                messagebox.showerror(_("common.error"), _("expense_manager.errors.failed_calculate_late_fees", error=e))

    def calculate_late_fees_backend(self):
        """Backend function for late fee calculation"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            current_date = datetime.now().date()

            # Find overdue fees
            cursor.execute('''
            SELECT sf.student_fee_id, sf.student_id, sf.amount, sf.due_date, sf.status,
                   ft.fee_name, ft.late_fee_calculation, ft.late_fee_amount, ft.grace_period_days,
                   s.first_name, s.last_name
            FROM student_fees sf
            JOIN fee_types ft ON sf.fee_type_id = ft.fee_type_id
            JOIN students s ON sf.student_id = s.student_id
            WHERE sf.status IN ('unpaid', 'partial')
            AND sf.due_date IS NOT NULL
            AND date(sf.due_date) < date('now')
            AND ft.late_fee_amount > 0
            ''')

            overdue_fees = cursor.fetchall()
            late_fees_applied = 0
            total_late_fees = 0

            for fee_data in overdue_fees:
                (student_fee_id, student_id, amount, due_date, status, fee_name,
                 calculation_method, late_fee_amount, grace_period_days, first_name, last_name) = fee_data

                # Parse due date
                due_date_obj = datetime.strptime(due_date, '%Y-%m-%d').date()
                days_overdue = (current_date - due_date_obj).days

                # Apply grace period
                if grace_period_days and days_overdue <= grace_period_days:
                    continue

                effective_days_overdue = days_overdue - (grace_period_days or 0)

                # Check if late fee already applied for this period
                cursor.execute('''
                SELECT COUNT(*) FROM late_fees
                WHERE student_fee_id = ? AND applied_date = ?
                ''', (student_fee_id, current_date.strftime('%Y-%m-%d')))

                if cursor.fetchone()[0] > 0:
                    continue  # Late fee already applied today

                # Calculate late fee based on method
                calculated_late_fee = 0

                if calculation_method == 'fixed':
                    calculated_late_fee = late_fee_amount
                elif calculation_method == 'percentage':
                    calculated_late_fee = amount * (late_fee_amount / 100)
                elif calculation_method == 'daily':
                    calculated_late_fee = late_fee_amount * effective_days_overdue

                if calculated_late_fee > 0:
                    # Apply late fee
                    cursor.execute('''
                    INSERT INTO late_fees
                    (student_fee_id, late_fee_amount, calculation_method, days_overdue, applied_date, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ''', (student_fee_id, calculated_late_fee, calculation_method, effective_days_overdue,
                          current_date.strftime('%Y-%m-%d'), datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

                    late_fees_applied += 1
                    total_late_fees += calculated_late_fee

            conn.commit()
            conn.close()

            return {'count': late_fees_applied, 'total': total_late_fees}

        except Exception as e:
            raise Exception(f"Failed to calculate late fees: {e}")

    def refresh_late_fees(self):
        """Refresh late fees display"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT s.student_id, s.first_name, s.last_name, ft.fee_name,
                   lf.days_overdue, lf.late_fee_amount, lf.applied_date,
                   CASE WHEN lf.waived = 1 THEN 'Waived' ELSE 'Active' END as status
            FROM late_fees lf
            JOIN student_fees sf ON lf.student_fee_id = sf.student_fee_id
            JOIN students s ON sf.student_id = s.student_id
            JOIN fee_types ft ON sf.fee_type_id = ft.fee_type_id
            ORDER BY lf.applied_date DESC
            ''')

            late_fees = cursor.fetchall()

            # Clear existing items
            for item in self.late_fees_tree.get_children():
                self.late_fees_tree.delete(item)

            # Add late fee data
            for fee in late_fees:
                student_id, first_name, last_name, fee_name, days_overdue, amount, applied_date, status = fee
                student_name = f"{first_name} {last_name}"

                self.late_fees_tree.insert('', 'end', values=(
                    student_id, student_name, fee_name, days_overdue,
                    f"\u00a3{amount:.2f}", applied_date, status
                ))

            conn.close()

        except Exception as e:
            messagebox.showerror(_("common.error"), _("expense_manager.errors.failed_load_late_fees", error=e))

    def gui_waive_late_fee(self):
        """GUI for waiving late fees"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("expense_manager.dialogs.waive_late_fee_title"))
        dialog.geometry("600x500")
        dialog.transient(self.root)
        dialog.grab_set()

        # Student selection
        student_frame = ttk.LabelFrame(dialog, text=_("expense_manager.labels.student_selection"), padding=15)
        student_frame.pack(fill='x', padx=20, pady=10)

        ttk.Label(student_frame, text=_("expense_manager.labels.student_id"), font=('Arial', 12)).pack(anchor='w')
        student_id_var = tk.StringVar()
        ttk.Entry(student_frame, textvariable=student_id_var, font=('Arial', 12), width=20).pack(anchor='w', pady=5)

        def load_student_late_fees():
            student_id = student_id_var.get().strip()
            if not student_id:
                return

            try:
                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                SELECT lf.late_fee_id, lf.late_fee_amount, lf.applied_date, lf.waived,
                       ft.fee_name, sf.amount
                FROM late_fees lf
                JOIN student_fees sf ON lf.student_fee_id = sf.student_fee_id
                JOIN fee_types ft ON sf.fee_type_id = ft.fee_type_id
                WHERE sf.student_id = ? AND lf.waived = 0
                ORDER BY lf.applied_date DESC
                ''', (student_id,))

                late_fees = cursor.fetchall()

                # Clear existing items
                for item in waive_tree.get_children():
                    waive_tree.delete(item)

                if not late_fees:
                    messagebox.showinfo(_("common.info"), _("expense_manager.messages.no_late_fees_found", student_id=student_id))
                    conn.close()
                    return

                # Add late fee data
                for fee in late_fees:
                    late_fee_id, amount, applied_date, waived, fee_name, original_amount = fee
                    waive_tree.insert('', 'end', values=(
                        late_fee_id, fee_name, f"\u00a3{amount:.2f}", applied_date
                    ))

                conn.close()

            except Exception as e:
                messagebox.showerror(_("common.error"), _("expense_manager.errors.failed_load_late_fees", error=e))

        ttk.Button(student_frame, text=_("expense_manager.buttons.load_late_fees"), command=load_student_late_fees).pack(anchor='w', pady=5)

        # Late fees display
        fees_frame = ttk.LabelFrame(dialog, text=_("expense_manager.labels.active_late_fees"), padding=15)
        fees_frame.pack(fill='both', expand=True, padx=20, pady=10)

        columns = (_("expense_manager.columns.late_fee_id"), _("expense_manager.columns.fee_name"), _("expense_manager.columns.amount"), _("expense_manager.columns.applied_date"))
        waive_tree = ttk.Treeview(fees_frame, columns=columns, show='headings', height=8)

        for col in columns:
            waive_tree.heading(col, text=col)
            waive_tree.column(col, width=120, anchor='center')

        waive_tree.pack(fill='both', expand=True)

        # Waiver details
        waiver_frame = ttk.LabelFrame(dialog, text=_("expense_manager.labels.waiver_details"), padding=15)
        waiver_frame.pack(fill='x', padx=20, pady=10)

        ttk.Label(waiver_frame, text=_("expense_manager.labels.reason_for_waiving"), font=('Arial', 12)).pack(anchor='w')
        reason_text = tk.Text(waiver_frame, height=3, width=50, font=('Arial', 10))
        reason_text.pack(fill='x', pady=5)

        def waive_selected_fees():
            selected_items = waive_tree.selection()
            if not selected_items:
                messagebox.showerror(_("common.error"), _("expense_manager.errors.select_late_fees"))
                return

            reason = reason_text.get("1.0", tk.END).strip()
            if not reason:
                messagebox.showerror(_("common.error"), _("expense_manager.errors.waiver_reason_required"))
                return

            try:
                conn = get_connection()
                cursor = conn.cursor()

                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                total_waived = 0

                for item in selected_items:
                    values = waive_tree.item(item)['values']
                    late_fee_id = values[0]
                    amount = float(values[2].replace('\u00a3', ''))

                    cursor.execute('''
                    UPDATE late_fees
                    SET waived = 1, waived_by = ?, waived_date = ?, waiver_reason = ?
                    WHERE late_fee_id = ?
                    ''', (auth.current_user['username'], now, reason, late_fee_id))

                    total_waived += amount

                conn.commit()
                conn.close()

                messagebox.showinfo(_("common.success"), _("expense_manager.messages.late_fees_waived", amount=total_waived))
                dialog.destroy()
                self.refresh_late_fees()
                self.update_status(_("expense_manager.status.late_fees_waived_status", amount=total_waived))

            except Exception as e:
                messagebox.showerror(_("common.error"), _("expense_manager.errors.failed_waive_late_fees", error=e))

        def waive_all_fees():
            if not waive_tree.get_children():
                messagebox.showerror(_("common.error"), _("expense_manager.errors.no_late_fees_to_waive"))
                return

            if messagebox.askyesno(_("common.confirm"), _("expense_manager.dialogs.confirm_waive_all")):
                # Select all items
                for item in waive_tree.get_children():
                    waive_tree.selection_add(item)
                waive_selected_fees()

        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text=_("expense_manager.buttons.waive_selected"), command=waive_selected_fees).pack(side='left', padx=10)
        ttk.Button(button_frame, text=_("expense_manager.buttons.waive_all"), command=waive_all_fees).pack(side='left', padx=10)
        ttk.Button(button_frame, text=_("common.cancel"), command=dialog.destroy).pack(side='left', padx=10)

    # Currency Management Functions

    def gui_late_fee_report(self):
        """Generate late fee report"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT s.student_id, s.first_name, s.last_name, ft.fee_name,
                   lf.late_fee_amount, lf.applied_date, lf.days_overdue,
                   CASE WHEN lf.waived = 1 THEN 'Waived' ELSE 'Active' END as status
            FROM late_fees lf
            JOIN student_fees sf ON lf.student_fee_id = sf.student_fee_id
            JOIN students s ON sf.student_id = s.student_id
            JOIN fee_types ft ON sf.fee_type_id = ft.fee_type_id
            ORDER BY lf.applied_date DESC
            LIMIT 100
            ''')

            late_fees = cursor.fetchall()

            if not late_fees:
                report_content = _("expense_manager.report.no_late_fees")
            else:
                report_content = f"""{_("expense_manager.report.title")}
{'=' * 100}
{_("expense_manager.report.header_student_id"):<12} {_("expense_manager.report.header_student_name"):<20} {_("expense_manager.report.header_fee_type"):<20} {_("expense_manager.report.header_late_fee"):<10} {_("expense_manager.report.header_applied"):<12} {_("expense_manager.report.header_days"):<5} {_("expense_manager.report.header_status"):<8}
{'-' * 100}
"""

                total_late_fees = 0
                active_late_fees = 0

                for fee in late_fees:
                    student_id, first_name, last_name, fee_name, amount, applied_date, days_overdue, status = fee
                    student_name = f"{first_name} {last_name}"

                    report_content += f"{student_id:<12} {student_name:<20} {fee_name:<20} \u00a3{amount:<9.2f} {applied_date:<12} {days_overdue:<5} {status:<8}\n"

                    total_late_fees += amount
                    if status == 'Active':
                        active_late_fees += amount

                report_content += f"""{'-' * 100}
{_("expense_manager.report.total_late_fees", amount=total_late_fees)}
{_("expense_manager.report.active_late_fees", amount=active_late_fees)}
{_("expense_manager.report.waived_late_fees", amount=total_late_fees - active_late_fees)}
{'=' * 100}
"""

            # Display in reports tab or create new window
            self.show_tab('reports')  # Reports tab
            self.report_text.delete('1.0', tk.END)
            self.report_text.insert('1.0', report_content)

            conn.close()
            self.update_status(_("expense_manager.status.late_fee_report_generated"))

        except Exception as e:
            messagebox.showerror(_("common.error"), _("expense_manager.errors.failed_generate_report", error=e))
