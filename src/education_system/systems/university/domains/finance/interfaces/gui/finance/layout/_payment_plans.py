"""Payment plans management mixin for LayoutManager."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.systems.university.infrastructure.i18n import get_text as _
from education_system.systems.university.domains.finance.domain.billing.payment_plan_service import (
    FREQUENCIES,
    PLAN_STATUSES,
    create_scheduled_plan,
    delete_payment_plan,
    get_payment_plan,
    list_payment_plans,
    update_payment_plan,
)


class PaymentPlansMixin:
    """Payment plans: create, edit, delete, refresh."""

    def create_payment_plans_tab(self):
        """Create payment plans tab"""
        plans_frame = tk.Frame(self.content_frame, bg='white')
        self.tab_frames['payment_plans'] = plans_frame

        # Title
        title_label = tk.Label(plans_frame, text=_("finance_gui.tabs.payment_plans.title"),
                               font=('Arial', 18, 'bold'), bg='white')
        title_label.pack(pady=10)

        # Toolbar
        toolbar = tk.Frame(plans_frame, bg='white')
        toolbar.pack(fill='x', padx=10, pady=10)

        tk.Button(toolbar, text=_("finance_gui.payment_plans.create_plan"), command=self._create_payment_plan,
                 bg=self.colors['success'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)
        tk.Button(toolbar, text=_("finance_gui.payment_plans.edit_plan"), command=self._edit_payment_plan,
                 bg=self.colors['warning'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)
        tk.Button(toolbar, text=_("finance_gui.payment_plans.delete_plan"), command=self._delete_payment_plan,
                 bg=self.colors['danger'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)
        tk.Button(toolbar, text=_("finance_gui.buttons.refresh"), command=self._refresh_payment_plans,
                 bg=self.colors['secondary'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='right', padx=5)

        # Plans table
        table_frame = tk.Frame(plans_frame)
        table_frame.pack(fill='both', expand=True, padx=10, pady=10)

        columns = ('plan_id', 'student_id', 'total_amount', 'installments', 'frequency', 'status', 'start_date')
        self.payment_plans_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=15)

        for col in columns:
            self.payment_plans_tree.heading(col, text=col.replace('_', ' ').title())
            self.payment_plans_tree.column(col, width=120)

        # Scrollbars
        v_scroll = ttk.Scrollbar(table_frame, orient='vertical', command=self.payment_plans_tree.yview)
        h_scroll = ttk.Scrollbar(table_frame, orient='horizontal', command=self.payment_plans_tree.xview)
        self.payment_plans_tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        self.payment_plans_tree.grid(row=0, column=0, sticky='nsew')
        v_scroll.grid(row=0, column=1, sticky='ns')
        h_scroll.grid(row=1, column=0, sticky='ew')

        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        # Load data
        self.root.after(100, self._refresh_payment_plans)

    def _create_payment_plan(self):
        """Create new payment plan"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.dialogs.create_payment_plan"))
        dialog.geometry("500x400")
        dialog.transient(self.root)

        tk.Label(dialog, text=_("finance_gui.dialogs.create_payment_plan"), font=('Arial', 14, 'bold')).pack(pady=10)

        form_frame = tk.Frame(dialog)
        form_frame.pack(padx=20, pady=10, fill='both', expand=True)

        tk.Label(form_frame, text=_("finance_gui.labels.student_id") + ":").grid(row=0, column=0, sticky='w', pady=5)
        student_id_entry = tk.Entry(form_frame, width=30)
        student_id_entry.grid(row=0, column=1, pady=5)

        tk.Label(form_frame, text=_("finance_gui.labels.total_amount") + ":").grid(row=1, column=0, sticky='w', pady=5)
        amount_entry = tk.Entry(form_frame, width=30)
        amount_entry.grid(row=1, column=1, pady=5)

        tk.Label(form_frame, text=_("finance_gui.labels.num_installments") + ":").grid(row=2, column=0, sticky='w', pady=5)
        installments_entry = tk.Entry(form_frame, width=30)
        installments_entry.grid(row=2, column=1, pady=5)

        tk.Label(form_frame, text=_("finance_gui.labels.frequency") + ":").grid(row=3, column=0, sticky='w', pady=5)
        frequency_var = tk.StringVar(value=_t('gui.finance.finance.layout.payment_plans.values.monthly', default="monthly"))
        frequency_combo = ttk.Combobox(form_frame, textvariable=frequency_var,
                                      values=list(FREQUENCIES),
                                      state='readonly', width=27)
        frequency_combo.grid(row=3, column=1, pady=5)

        def save_plan():
            try:
                student_id = student_id_entry.get()
                total_amount = float(amount_entry.get())
                installments = int(installments_entry.get())
                frequency = frequency_var.get()

                # Shared with the Finance CLI: validates the student, writes the
                # plan and its equal-installment schedule in one transaction.
                create_scheduled_plan(student_id, total_amount, installments, frequency)

                messagebox.showinfo(_("common.success"), _("finance_gui.messages.payment_plan_created"))
                dialog.destroy()
                self._refresh_payment_plans()
            except Exception as e:
                messagebox.showerror(_("common.error"), _("finance_gui.messages.failed_create_payment_plan", error=str(e)))

        btn_frame = tk.Frame(dialog)
        btn_frame.pack(pady=20)
        tk.Button(btn_frame, text=_("finance_gui.buttons.save"), command=save_plan, bg=self.colors['success'],
                 fg='white', padx=20, pady=5).pack(side='left', padx=5)
        tk.Button(btn_frame, text=_("finance_gui.buttons.cancel"), command=dialog.destroy, bg=self.colors['danger'],
                 fg='white', padx=20, pady=5).pack(side='left', padx=5)

    def _edit_payment_plan(self):
        """Edit selected payment plan"""
        selection = self.payment_plans_tree.selection()
        if not selection:
            messagebox.showwarning(_("finance_gui.messages.no_selection"), _("finance_gui.messages.select_payment_plan_edit"))
            return
        plan_id = self.payment_plans_tree.item(selection[0])['values'][0]
        plan = get_payment_plan(plan_id)
        if plan is None:
            messagebox.showerror(_("common.error"), _t('gui.finance.finance.layout.payment_plans.dialogs.plan_not_found', default="Payment plan not found."))
            return

        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.dialogs.edit_plan"))
        dialog.geometry("500x380")
        dialog.transient(self.root)

        tk.Label(dialog, text=f"{_('finance_gui.dialogs.edit_plan')} #{plan_id}", font=('Arial', 14, 'bold')).pack(pady=10)

        form_frame = tk.Frame(dialog)
        form_frame.pack(padx=20, pady=10, fill='both', expand=True)

        tk.Label(form_frame, text=_("finance_gui.labels.total_amount") + ":").grid(row=0, column=0, sticky='w', pady=5)
        amount_var = tk.StringVar(value=f"{float(plan['total_amount'] or 0):.2f}")
        tk.Entry(form_frame, textvariable=amount_var, width=30).grid(row=0, column=1, pady=5)

        tk.Label(form_frame, text=_t('gui.finance.finance.layout.payment_plans.labels.next_due_date', default="Next Due Date:")).grid(row=1, column=0, sticky='w', pady=5)
        due_var = tk.StringVar(value=plan['next_due_date'] or '')
        tk.Entry(form_frame, textvariable=due_var, width=30).grid(row=1, column=1, pady=5)

        tk.Label(form_frame, text=_t('gui.finance.finance.layout.payment_plans.labels.status', default="Status:")).grid(row=2, column=0, sticky='w', pady=5)
        status_var = tk.StringVar(value=plan['status'] or 'active')
        ttk.Combobox(form_frame, textvariable=status_var, values=list(PLAN_STATUSES),
                     state='readonly', width=27).grid(row=2, column=1, pady=5)

        tk.Label(form_frame, text=_t('gui.finance.finance.layout.payment_plans.labels.add_note', default="Add Note:")).grid(row=3, column=0, sticky='w', pady=5)
        notes_entry = tk.Entry(form_frame, width=30)
        notes_entry.grid(row=3, column=1, pady=5)

        def save_changes():
            try:
                total_amount = float(amount_var.get())
                # Shared with the Finance CLI: re-bases the remaining balance
                # and validates the date/status.
                update_payment_plan(plan_id, total_amount=total_amount,
                                    next_due_date=due_var.get().strip() or None,
                                    status=status_var.get(),
                                    notes=notes_entry.get().strip() or None)
                messagebox.showinfo(_("common.success"), _t('gui.finance.finance.layout.payment_plans.dialogs.plan_updated', default="Payment plan updated."))
                dialog.destroy()
                self._refresh_payment_plans()
            except Exception as e:
                messagebox.showerror(_("common.error"), str(e))

        btn_frame = tk.Frame(dialog)
        btn_frame.pack(pady=20)
        tk.Button(btn_frame, text=_("finance_gui.buttons.save"), command=save_changes, bg=self.colors['success'],
                 fg='white', padx=20, pady=5).pack(side='left', padx=5)
        tk.Button(btn_frame, text=_("finance_gui.buttons.cancel"), command=dialog.destroy, bg=self.colors['danger'],
                 fg='white', padx=20, pady=5).pack(side='left', padx=5)

    def _delete_payment_plan(self):
        """Delete selected payment plan"""
        selection = self.payment_plans_tree.selection()
        if not selection:
            messagebox.showwarning(_("finance_gui.messages.no_selection"), _("finance_gui.messages.select_payment_plan_delete"))
            return

        if messagebox.askyesno(_("finance_gui.dialogs.confirm_delete"), _("finance_gui.messages.confirm_delete_payment_plan")):
            try:
                plan_id = self.payment_plans_tree.item(selection[0])['values'][0]
                # Shared with the Finance CLI: removes the schedule too, and
                # refuses once an installment has been paid.
                delete_payment_plan(plan_id)
                messagebox.showinfo(_("common.success"), _("finance_gui.messages.payment_plan_deleted"))
                self._refresh_payment_plans()
            except Exception as e:
                messagebox.showerror(_("common.error"), _("finance_gui.messages.failed_delete_payment_plan", error=str(e)))

    def _refresh_payment_plans(self):
        """Refresh payment plans list"""
        try:
            # Clear existing items
            for item in self.payment_plans_tree.get_children():
                self.payment_plans_tree.delete(item)

            for plan in list_payment_plans(limit=500):
                self.payment_plans_tree.insert('', 'end', values=(
                    plan['plan_id'], plan['student_id'], plan['total_amount'],
                    plan['installments'], plan['frequency'], plan['status'], plan['start_date'],
                ))
        except Exception as e:
            print(f"Error refreshing payment plans: {e}")
