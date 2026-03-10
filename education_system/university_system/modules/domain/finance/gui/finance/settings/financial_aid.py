"""Financial aid management: applications, disbursements, aid types, and loans."""

import sys
import io
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from tkinter.scrolledtext import ScrolledText
from datetime import datetime

from education_system.university_system.modules.shared.utils.i18n import get_text as _
from education_system.university_system.infrastructure.database.db import get_connection

from education_system.university_system.modules.domain.finance.gui.finance.common_imports import (
    create_aid_type,
    deactivate_aid_type,
    edit_aid_type,
    manage_aid_types,
    view_aid_types,
    process_loan_payment,
    review_pending_aid_applications,
    track_loan_repayments,
    view_aid_application_detail,
)


class FinancialAidMixin:
    """Financial aid tab, aid-type CRUD, disbursement, and loan tracking."""

    def create_aid_tab(self):
        """Create financial aid tab"""
        aid_frame = tk.Frame(self.gui.layout.content_frame, bg='white')
        self.gui.layout.tab_frames['aid'] = aid_frame

        # Aid toolbar
        toolbar = tk.Frame(aid_frame, bg='white')
        toolbar.pack(fill='x', padx=10, pady=5)

        new_aid_buttons = [
            (_("finance_gui.settings.manage_aid_types_title"), self.gui_manage_aid_types),
            (_("finance_gui.settings.edit_aid_type_title"), self.gui_edit_aid_type),
            (_("finance_gui.settings.deactivate_aid_type_title"), self.gui_deactivate_aid_type),
            (_("finance_gui.settings.review_pending_aid_title"), self.gui_review_pending_aid_applications),
            (_("finance_gui.settings.process_loan_payment_title"), self.gui_process_loan_payment),
            (_("finance_gui.settings.view_aid_application_title"), self.gui_view_aid_application_detail),
        ]

        tk.Button(toolbar, text=_("finance_gui.settings.aid_toolbar_new_application"), command=self.new_aid_application,
                 bg=self.gui.layout.colors['success'], fg='white').pack(side='left', padx=5)
        tk.Button(toolbar, text=_("finance_gui.settings.aid_toolbar_review_applications"), command=self.review_aid_applications,
                 bg=self.gui.layout.colors['warning'], fg='white').pack(side='left', padx=5)
        tk.Button(toolbar, text=_("finance_gui.settings.aid_toolbar_disburse_aid"), command=self.disburse_aid,
                 bg=self.gui.layout.colors['secondary'], fg='white').pack(side='left', padx=5)
        tk.Button(toolbar, text=_("finance_gui.settings.aid_toolbar_track_repayments"), command=self.track_loan_repayments,
                 bg=self.gui.layout.colors['dark'], fg='white').pack(side='left', padx=5)

        # Aid content with tabs
        aid_notebook = ttk.Notebook(aid_frame)
        aid_notebook.pack(fill='both', expand=True, padx=10, pady=10)

        # Applications tab
        apps_frame = ttk.Frame(aid_notebook)
        aid_notebook.add(apps_frame, text=_("finance_gui.settings.applications_tab"))

        self.aid_apps_tree = ttk.Treeview(apps_frame,
                                         columns=('aid_id', 'student', 'type', 'amount', 'status'),
                                         show='headings')
        for col in self.aid_apps_tree['columns']:
            self.aid_apps_tree.heading(col, text=col.replace('_', ' ').title())
        self.aid_apps_tree.pack(fill='both', expand=True, padx=5, pady=5)

        # Aid types tab
        types_frame = ttk.Frame(aid_notebook)
        aid_notebook.add(types_frame, text=_("finance_gui.settings.aid_types_tab"))

        self.aid_types_tree = ttk.Treeview(types_frame,
                                          columns=('type_id', 'name', 'category', 'max_amount'),
                                          show='headings')
        for col in self.aid_types_tree['columns']:
            self.aid_types_tree.heading(col, text=col.replace('_', ' ').title())
        self.aid_types_tree.pack(fill='both', expand=True, padx=5, pady=5)

        # Load aid data
        self.refresh_financial_aid()


    def new_aid_application(self):
        """Create new aid application"""
        student_id = simpledialog.askstring(_("finance_gui.settings.financial_aid_title"), _("finance_gui.settings.enter_student_id_prompt"))
        if student_id:
            aid_type = simpledialog.askstring(_("finance_gui.settings.financial_aid_title"), _("finance_gui.settings.enter_aid_type_prompt"))
            if aid_type:
                amount = simpledialog.askfloat(_("finance_gui.settings.financial_aid_title"), _("finance_gui.settings.enter_aid_amount_prompt"))
                if amount:
                    messagebox.showinfo(_("finance_gui.settings.success_title"), _("finance_gui.settings.aid_application_created", amount=f"\u00a3{amount:.2f}", student_id=student_id))
                    self.refresh_financial_aid()


    def review_aid_applications(self):
        """Review pending aid applications"""
        try:
            old_stdout = sys.stdout
            sys.stdout = mystdout = io.StringIO()

            review_pending_aid_applications()

            output = mystdout.getvalue()
            sys.stdout = old_stdout

            self.show_text_window(_("finance_gui.settings.aid_applications_review_title"), output)

        except Exception as e:
            sys.stdout = old_stdout
            messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.failed_review_applications", error=str(e)))


    def disburse_aid(self):
        """Disburse financial aid"""
        # Create disbursement dialog
        disburse_dialog = tk.Toplevel(self.root)
        disburse_dialog.title(_("finance_gui.settings.disburse_aid_title"))
        disburse_dialog.geometry("700x600")
        disburse_dialog.transient(self.root)

        ttk.Label(disburse_dialog, text=_("finance_gui.settings.disburse_aid_heading"),
                 font=('TkDefaultFont', 14, 'bold')).pack(pady=10)

        # Student selection
        selection_frame = ttk.LabelFrame(disburse_dialog, text=_("finance_gui.settings.student_selection_frame"), padding=15)
        selection_frame.pack(fill='x', padx=10, pady=10)

        ttk.Label(selection_frame, text=_("finance_gui.settings.student_id_label_form")).grid(row=0, column=0, sticky='w', pady=5)
        student_id_var = tk.StringVar()
        student_id_entry = ttk.Entry(selection_frame, textvariable=student_id_var, width=30)
        student_id_entry.grid(row=0, column=1, pady=5, padx=5)

        ttk.Label(selection_frame, text=_("finance_gui.settings.student_name_label_form")).grid(row=1, column=0, sticky='w', pady=5)
        student_name_label = ttk.Label(selection_frame, text="", foreground='blue')
        student_name_label.grid(row=1, column=1, sticky='w', pady=5, padx=5)

        def lookup_student():
            student_id = student_id_var.get().strip()
            if student_id:
                # Lookup student (mock implementation)
                student_name_label.config(text=_("finance_gui.settings.student_prefix", student_id=student_id))
                aid_details_frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Button(selection_frame, text=_("finance_gui.settings.lookup_student_btn"), command=lookup_student).grid(row=0, column=2, padx=5)

        # Aid details
        aid_details_frame = ttk.LabelFrame(disburse_dialog, text=_("finance_gui.settings.aid_details_frame"), padding=15)

        form_frame = ttk.Frame(aid_details_frame)
        form_frame.pack(fill='x')

        ttk.Label(form_frame, text=_("finance_gui.settings.aid_type_label_form")).grid(row=0, column=0, sticky='w', pady=5)
        aid_type_var = tk.StringVar(value="Grant")
        aid_type_combo = ttk.Combobox(form_frame, textvariable=aid_type_var,
                                      values=['Grant', 'Scholarship', 'Loan', 'Emergency Aid', 'Bursary'],
                                      width=28, state='readonly')
        aid_type_combo.grid(row=0, column=1, pady=5, padx=5)

        ttk.Label(form_frame, text=_("finance_gui.settings.amount_label_form")).grid(row=1, column=0, sticky='w', pady=5)
        amount_var = tk.StringVar()
        amount_entry = ttk.Entry(form_frame, textvariable=amount_var, width=30)
        amount_entry.grid(row=1, column=1, pady=5, padx=5)

        ttk.Label(form_frame, text=_("finance_gui.settings.payment_method_label_form")).grid(row=2, column=0, sticky='w', pady=5)
        method_var = tk.StringVar(value="Bank Transfer")
        method_combo = ttk.Combobox(form_frame, textvariable=method_var,
                                    values=['Bank Transfer', 'Cheque', 'Fee Reduction', 'Direct Credit'],
                                    width=28, state='readonly')
        method_combo.grid(row=2, column=1, pady=5, padx=5)

        ttk.Label(form_frame, text=_("finance_gui.settings.reference_label_form")).grid(row=3, column=0, sticky='w', pady=5)
        reference_var = tk.StringVar()
        reference_entry = ttk.Entry(form_frame, textvariable=reference_var, width=30)
        reference_entry.grid(row=3, column=1, pady=5, padx=5)

        ttk.Label(form_frame, text=_("finance_gui.settings.notes_label_form")).grid(row=4, column=0, sticky='nw', pady=5)
        notes_text = tk.Text(form_frame, height=4, width=30)
        notes_text.grid(row=4, column=1, pady=5, padx=5)

        # Disbursement summary
        summary_frame = ttk.LabelFrame(aid_details_frame, text=_("finance_gui.settings.disbursement_summary_frame"))
        summary_frame.pack(fill='x', pady=10)

        summary_label = ttk.Label(summary_frame, text="", font=('Courier', 9))
        summary_label.pack(padx=10, pady=10)

        def update_summary():
            try:
                amount = float(amount_var.get() or 0)
                summary_text = f"""
    Student ID:       {student_id_var.get()}
    Aid Type:         {aid_type_var.get()}
    Amount:           \u00a3{amount:,.2f}
    Payment Method:   {method_var.get()}
    Reference:        {reference_var.get() or 'N/A'}
    """
                summary_label.config(text=summary_text)
            except ValueError:
                summary_label.config(text=_("finance_gui.settings.invalid_amount_msg"))

        # Update summary when values change
        amount_var.trace('w', lambda *args: update_summary())
        aid_type_var.trace('w', lambda *args: update_summary())
        method_var.trace('w', lambda *args: update_summary())

        def process_disbursement():
            student_id = student_id_var.get().strip()
            if not student_id:
                messagebox.showwarning(_("finance_gui.settings.student_required_warning_title"), _("finance_gui.settings.student_required_warning_msg"), parent=disburse_dialog)
                return

            try:
                amount = float(amount_var.get())
                if amount <= 0:
                    raise ValueError(_("finance_gui.settings.amount_greater_zero"))
            except ValueError as e:
                messagebox.showwarning(_("finance_gui.settings.invalid_amount_warning_title"), str(e), parent=disburse_dialog)
                return

            if not reference_var.get().strip():
                messagebox.showwarning(_("finance_gui.settings.reference_required_warning_title"), _("finance_gui.settings.reference_required_warning_msg"), parent=disburse_dialog)
                return

            if messagebox.askyesno(_("finance_gui.settings.confirm_disbursement_title"),
                                  _("finance_gui.settings.confirm_disbursement_msg", amount=f"\u00a3{amount:,.2f}", aid_type=aid_type_var.get(), student_id=student_id),
                                  parent=disburse_dialog):
                # Process disbursement (mock implementation)
                messagebox.showinfo(_("finance_gui.settings.success_title"),
                                  _("finance_gui.settings.disbursement_success_msg", amount=f"\u00a3{amount:,.2f}", reference=reference_var.get()),
                                  parent=disburse_dialog)
                disburse_dialog.destroy()
                if hasattr(self, 'refresh_financial_aid'):
                    self.refresh_financial_aid()

        # Buttons
        button_frame = ttk.Frame(disburse_dialog)
        button_frame.pack(pady=15)

        ttk.Button(button_frame, text=_("finance_gui.settings.process_disbursement_btn"), command=process_disbursement).pack(side='left', padx=5)
        ttk.Button(button_frame, text=_("finance_gui.settings.btn_cancel"), command=disburse_dialog.destroy).pack(side='left', padx=5)


    def track_loan_repayments(self):
        """Track loan repayments"""
        try:
            old_stdout = sys.stdout
            sys.stdout = mystdout = io.StringIO()

            track_loan_repayments()

            output = mystdout.getvalue()
            sys.stdout = old_stdout

            self.show_text_window(_("finance_gui.settings.loan_repayments_title"), output)

        except Exception as e:
            sys.stdout = old_stdout
            messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.failed_track_repayments", error=str(e)))

    # ==================== BUDGET METHODS ====================


    def refresh_financial_aid(self):
        """Refresh financial aid data"""
        def refresh_thread():
            try:
                conn = get_connection()
                cursor = conn.cursor()

                # Get aid applications
                cursor.execute('''
                SELECT sfa.aid_id, s.first_name || ' ' || s.last_name as student_name,
                       fat.aid_name, sfa.awarded_amount, sfa.status
                FROM student_financial_aid sfa
                JOIN students s ON sfa.student_id = s.student_id
                JOIN financial_aid_types fat ON sfa.aid_type_id = fat.aid_type_id
                ORDER BY sfa.application_date DESC
                ''')

                aid_applications = cursor.fetchall()

                # Get aid types
                cursor.execute('''
                SELECT aid_type_id, aid_name, aid_category, max_amount
                FROM financial_aid_types
                WHERE is_active = 1
                ORDER BY aid_category, aid_name
                ''')

                aid_types = cursor.fetchall()
                conn.close()

                self.root.after(0, lambda: self.update_financial_aid_data(aid_applications, aid_types))

            except Exception as e:
                print(f"Error refreshing financial aid: {e}")

        refresh_thread()


    def update_financial_aid_data(self, aid_applications, aid_types):
        """Update financial aid data in UI"""
        # Update aid applications
        for item in self.aid_apps_tree.get_children():
            self.aid_apps_tree.delete(item)

        for app in aid_applications:
            aid_id, student_name, aid_name, amount, status = app
            display_data = (aid_id, student_name, aid_name, f"\u00a3{amount:.2f}", status)
            self.aid_apps_tree.insert('', 'end', values=display_data)

        # Update aid types
        for item in self.aid_types_tree.get_children():
            self.aid_types_tree.delete(item)

        for aid_type in aid_types:
            type_id, name, category, max_amount = aid_type
            max_amt_str = f"\u00a3{max_amount:.2f}" if max_amount else "Unlimited"
            display_data = (type_id, name, category, max_amt_str)
            self.aid_types_tree.insert('', 'end', values=display_data)


    def gui_manage_financial_aid(self):
        """Switch to financial aid tab"""
        self.show_tab('aid')


    def gui_manage_aid_types(self):
        """GUI wrapper for manage_aid_types"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.settings.manage_aid_types_title"))
        dialog.geometry("800x600")
        dialog.transient(self.root)
        dialog.grab_set()

        try:
            old_stdout = sys.stdout
            sys.stdout = mystdout = io.StringIO()

            manage_aid_types()

            output = mystdout.getvalue()
            sys.stdout = old_stdout

            text_widget = ScrolledText(dialog, height=25, width=90, font=('Courier', 10))
            text_widget.pack(fill='both', expand=True, padx=10, pady=10)
            text_widget.insert('1.0', output)

            ttk.Button(dialog, text=_("finance_gui.settings.btn_close"), command=dialog.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.failed_manage_aid_types", error=str(e)))


    def gui_edit_aid_type(self):
        """GUI wrapper for edit_aid_type"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.settings.edit_aid_type_title"))
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()

        form_frame = ttk.LabelFrame(dialog, text=_("finance_gui.settings.edit_aid_type_frame"), padding=20)
        form_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # Aid type ID
        ttk.Label(form_frame, text=_("finance_gui.settings.aid_type_id_label")).pack(anchor='w', pady=5)
        aid_id_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=aid_id_var).pack(anchor='w', fill='x', pady=5)

        # New name
        ttk.Label(form_frame, text=_("finance_gui.settings.new_name_label")).pack(anchor='w', pady=5)
        name_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=name_var).pack(anchor='w', fill='x', pady=5)

        # New max amount
        ttk.Label(form_frame, text=_("finance_gui.settings.new_max_amount_label")).pack(anchor='w', pady=5)
        amount_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=amount_var).pack(anchor='w', fill='x', pady=5)

        def edit_aid():
            try:
                aid_id = int(aid_id_var.get())
                new_name = name_var.get().strip()
                new_max_amount = float(amount_var.get()) if amount_var.get().strip() else None

                if not aid_id:
                    messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.aid_type_id_required"))
                    return

                edit_aid_type(aid_id, new_name, new_max_amount)
                messagebox.showinfo(_("finance_gui.settings.success_title"), _("finance_gui.settings.aid_type_updated"))
                dialog.destroy()

            except ValueError:
                messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.invalid_id_or_amount"))
            except Exception as e:
                messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.failed_edit_aid_type", error=str(e)))

        ttk.Button(form_frame, text=_("finance_gui.settings.update_aid_type_btn"), command=edit_aid).pack(pady=20)


    def gui_deactivate_aid_type(self):
        """GUI wrapper for deactivate_aid_type"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.settings.deactivate_aid_type_title"))
        dialog.geometry("400x200")
        dialog.transient(self.root)
        dialog.grab_set()

        form_frame = ttk.LabelFrame(dialog, text=_("finance_gui.settings.deactivate_aid_type_frame"), padding=20)
        form_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # Aid type ID
        ttk.Label(form_frame, text=_("finance_gui.settings.aid_type_id_to_deactivate")).pack(anchor='w', pady=5)
        aid_id_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=aid_id_var).pack(anchor='w', fill='x', pady=5)

        def deactivate_aid():
            try:
                aid_id = int(aid_id_var.get())

                if messagebox.askyesno(_("finance_gui.settings.confirm_title"), _("finance_gui.settings.confirm_deactivate_aid", aid_id=aid_id)):
                    deactivate_aid_type(aid_id)
                    messagebox.showinfo(_("finance_gui.settings.success_title"), _("finance_gui.settings.aid_type_deactivated"))
                    dialog.destroy()

            except ValueError:
                messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.invalid_aid_type_id"))
            except Exception as e:
                messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.failed_deactivate_aid_type", error=str(e)))

        ttk.Button(form_frame, text=_("finance_gui.settings.deactivate_btn"), command=deactivate_aid).pack(pady=20)


    def gui_review_pending_aid_applications(self):
        """GUI wrapper for review_pending_aid_applications"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.settings.review_pending_aid_title"))
        dialog.geometry("800x600")
        dialog.transient(self.root)
        dialog.grab_set()

        try:
            old_stdout = sys.stdout
            sys.stdout = mystdout = io.StringIO()

            review_pending_aid_applications()

            output = mystdout.getvalue()
            sys.stdout = old_stdout

            text_widget = ScrolledText(dialog, height=25, width=90, font=('Courier', 10))
            text_widget.pack(fill='both', expand=True, padx=10, pady=10)
            text_widget.insert('1.0', output)

            ttk.Button(dialog, text=_("finance_gui.settings.btn_close"), command=dialog.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.failed_review_pending_applications", error=str(e)))


    def gui_process_loan_payment(self):
        """GUI wrapper for process_loan_payment"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.settings.process_loan_payment_title"))
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()

        form_frame = ttk.LabelFrame(dialog, text=_("finance_gui.settings.loan_payment_details_frame"), padding=20)
        form_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # Loan ID
        ttk.Label(form_frame, text=_("finance_gui.settings.loan_id_label")).pack(anchor='w', pady=5)
        loan_id_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=loan_id_var).pack(anchor='w', fill='x', pady=5)

        # Payment amount
        ttk.Label(form_frame, text=_("finance_gui.settings.payment_amount_label")).pack(anchor='w', pady=5)
        amount_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=amount_var).pack(anchor='w', fill='x', pady=5)

        # Payment method
        ttk.Label(form_frame, text=_("finance_gui.settings.payment_method_label_form")).pack(anchor='w', pady=5)
        method_var = tk.StringVar(value="bank_transfer")
        method_combo = ttk.Combobox(form_frame, textvariable=method_var,
                                   values=["bank_transfer", "direct_debit", "check", "online"])
        method_combo.pack(anchor='w', fill='x', pady=5)

        def process_payment():
            try:
                loan_id = int(loan_id_var.get())
                amount = float(amount_var.get())
                method = method_var.get()

                if not all([loan_id, amount > 0, method]):
                    messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.all_fields_required"))
                    return

                process_loan_payment(loan_id, amount, method)
                messagebox.showinfo(_("finance_gui.settings.success_title"), _("finance_gui.settings.loan_payment_processed"))
                dialog.destroy()

            except ValueError:
                messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.invalid_loan_id_or_amount"))
            except Exception as e:
                messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.failed_process_loan_payment", error=str(e)))

        ttk.Button(form_frame, text=_("finance_gui.settings.process_payment_btn"), command=process_payment).pack(pady=20)


    def gui_view_aid_application_detail(self):
        """GUI wrapper for view_aid_application_detail"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.settings.view_aid_application_title"))
        dialog.geometry("700x500")
        dialog.transient(self.root)
        dialog.grab_set()

        # Application ID input
        input_frame = ttk.Frame(dialog, padding=10)
        input_frame.pack(fill='x')

        ttk.Label(input_frame, text=_("finance_gui.settings.application_id_label")).pack(side='left', padx=5)
        app_id_var = tk.StringVar()
        ttk.Entry(input_frame, textvariable=app_id_var, width=15).pack(side='left', padx=5)

        def show_details():
            app_id = app_id_var.get().strip()
            if not app_id:
                messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.application_id_required"))
                return

            try:
                app_id_int = int(app_id)
                old_stdout = sys.stdout
                sys.stdout = mystdout = io.StringIO()

                view_aid_application_detail(app_id_int)

                output = mystdout.getvalue()
                sys.stdout = old_stdout

                details_text.delete('1.0', tk.END)
                details_text.insert('1.0', output)

            except ValueError:
                messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.invalid_application_id"))
            except Exception as e:
                messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.failed_view_application_details", error=str(e)))

        ttk.Button(input_frame, text=_("finance_gui.settings.view_details_btn"), command=show_details).pack(side='left', padx=10)

        # Details display
        details_text = ScrolledText(dialog, height=20, width=80, font=('Courier', 10))
        details_text.pack(fill='both', expand=True, padx=10, pady=10)


    def gui_track_loan_repayments(self):
        """GUI wrapper for track_loan_repayments"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.settings.track_loan_repayments_title"))
        dialog.geometry("800x600")
        dialog.transient(self.root)
        dialog.grab_set()

        try:
            old_stdout = sys.stdout
            sys.stdout = mystdout = io.StringIO()

            track_loan_repayments()

            output = mystdout.getvalue()
            sys.stdout = old_stdout

            text_widget = ScrolledText(dialog, height=25, width=90, font=('Courier', 10))
            text_widget.pack(fill='both', expand=True, padx=10, pady=10)
            text_widget.insert('1.0', output)

            ttk.Button(dialog, text=_("finance_gui.settings.btn_close"), command=dialog.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.failed_track_repayments", error=str(e)))


    def gui_view_aid_types(self):
        """GUI wrapper for view_aid_types"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.settings.view_aid_types_title"))
        dialog.geometry("700x500")
        dialog.transient(self.root)
        dialog.grab_set()

        try:
            old_stdout = sys.stdout
            sys.stdout = mystdout = io.StringIO()

            view_aid_types()

            output = mystdout.getvalue()
            sys.stdout = old_stdout

            text_widget = ScrolledText(dialog, height=25, width=80, font=('Courier', 10))
            text_widget.pack(fill='both', expand=True, padx=10, pady=10)
            text_widget.insert('1.0', output)

            ttk.Button(dialog, text=_("finance_gui.settings.btn_close"), command=dialog.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.failed_view_aid_types", error=str(e)))


    def gui_create_aid_type(self):
        """GUI wrapper for create_aid_type"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.settings.create_aid_type_title"))
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()

        form_frame = ttk.LabelFrame(dialog, text=_("finance_gui.settings.aid_type_details_frame"), padding=20)
        form_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # Aid name
        ttk.Label(form_frame, text=_("finance_gui.settings.aid_type_name_label")).pack(anchor='w', pady=5)
        name_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=name_var).pack(anchor='w', fill='x', pady=5)

        # Category
        ttk.Label(form_frame, text=_("finance_gui.settings.category_label")).pack(anchor='w', pady=5)
        category_var = tk.StringVar()
        category_combo = ttk.Combobox(form_frame, textvariable=category_var,
                                     values=["scholarship", "grant", "loan", "work_study"])
        category_combo.pack(anchor='w', fill='x', pady=5)

        # Max amount
        ttk.Label(form_frame, text=_("finance_gui.settings.max_amount_label")).pack(anchor='w', pady=5)
        amount_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=amount_var).pack(anchor='w', fill='x', pady=5)

        # Description
        ttk.Label(form_frame, text=_("finance_gui.settings.description_label")).pack(anchor='w', pady=5)
        desc_text = tk.Text(form_frame, height=4, width=50)
        desc_text.pack(anchor='w', fill='both', expand=True, pady=5)

        def create_aid():
            try:
                name = name_var.get().strip()
                category = category_var.get().strip()
                max_amount = float(amount_var.get()) if amount_var.get().strip() else None
                description = desc_text.get("1.0", tk.END).strip()

                if not all([name, category]):
                    messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.name_and_category_required"))
                    return

                create_aid_type(name, category, max_amount, description)
                messagebox.showinfo(_("finance_gui.settings.success_title"), _("finance_gui.settings.aid_type_created"))
                dialog.destroy()

            except ValueError:
                messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.invalid_max_amount"))
            except Exception as e:
                messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.failed_create_aid_type", error=str(e)))

        ttk.Button(form_frame, text=_("finance_gui.settings.create_aid_type_btn"), command=create_aid).pack(pady=20)
