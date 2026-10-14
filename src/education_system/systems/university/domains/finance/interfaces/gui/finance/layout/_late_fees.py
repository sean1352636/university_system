"""Late fees management mixin for LayoutManager."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from education_system.systems.university.infrastructure.auth import get_global_auth
from education_system.systems.university.infrastructure.i18n import get_text as _
from education_system.systems.university.domains.finance.domain.billing.late_fees import (
    CALCULATION_METHODS,
    apply_late_fee,
    apply_overdue_late_fees,
    list_late_fees,
    waive_late_fee_by_id,
)


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
        method_var = tk.StringVar(value=_t('gui.finance.finance.layout.late_fees.values.fixed', default="fixed"))
        method_combo = ttk.Combobox(form_frame, textvariable=method_var,
                                    values=list(CALCULATION_METHODS),
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

                # Shared with the Finance CLI: validates the student fee and amount.
                apply_late_fee(student_fee_id, amount, method, days_overdue)

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
            username = 'admin'
            if auth and getattr(auth, 'current_user', None):
                username = auth.current_user.get('username', 'admin')
            # Shared with the Finance CLI: refuses an already-waived fee and
            # writes the audit row.
            waive_late_fee_by_id(late_fee_id, reason, waived_by=username)
            messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.messages.late_fee_waived"))
            self._refresh_late_fees()
        except Exception as e:
            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.messages.failed_waive_late_fee", error=str(e)))

    def _calculate_overdue_fees(self):
        """Calculate and apply late fees for all overdue student fees"""
        if not messagebox.askyesno(_("finance_gui.dialogs.confirm"), _("finance_gui.messages.confirm_calculate_overdue")):
            return

        try:
            # Shared with the Finance CLI: 5% on every overdue fee that has no
            # late fee yet.
            count = apply_overdue_late_fees()['applied']

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

            for fee in list_late_fees(limit=500):
                self.late_fees_tree.insert('', 'end', values=(
                    fee['late_fee_id'], fee['student_fee_id'], fee['late_fee_amount'],
                    fee['days_overdue'], fee['calculation_method'], fee['applied_date'],
                    fee['waived'], fee['waiver_reason'],
                ))
        except Exception as e:
            print(f"Error refreshing late fees: {e}")
