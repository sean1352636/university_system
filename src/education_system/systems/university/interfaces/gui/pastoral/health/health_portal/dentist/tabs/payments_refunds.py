
from education_system.systems.university.infrastructure.i18n import get_text as _t
from .. import *  # shared compatibility dependencies

class PaymentsRefundsTabMixin:
        def create_payments_refunds_tab(self):
            """Function 26: Create payments and refunds management tab (admin/staff only)."""
            tab = ttk.Frame(self.notebook, padding="10")
            self.notebook.add(tab, text=_t("dentist.labels.payments_refunds"))

            # Header
            header_frame = ttk.Frame(tab)
            header_frame.pack(fill=tk.X, pady=(0, 10))
            ttk.Label(header_frame, text=_t("dentist.labels.refunds_title"),
                     font=('Arial', 12, 'bold')).pack(anchor=tk.W)
            ttk.Label(header_frame, text=_t("dentist.labels.only_appointment_payments"),
                     font=('Arial', 9, 'italic'), foreground='gray').pack(anchor=tk.W)

            # Search frame
            search_frame = ttk.LabelFrame(tab, text=_t("dentist.labels.search_payments"), padding="10")
            search_frame.pack(fill=tk.X, pady=(0, 10))

            ttk.Label(search_frame, text=_t("dentist.labels.patient_id_name")).grid(row=0, column=0, sticky=tk.W, padx=5)
            self.payment_search_var = tk.StringVar()
            ttk.Entry(search_frame, textvariable=self.payment_search_var, width=30).grid(row=0, column=1, padx=5)
            ttk.Button(search_frame, text=_t("dentist.btn.search"), command=self._refresh_payments_list).grid(row=0, column=2, padx=5)
            ttk.Button(search_frame, text=_t("dentist.btn.show_all"),
                      command=lambda: [self.payment_search_var.set(''), self._refresh_payments_list()]).grid(row=0, column=3, padx=5)

            # Payments list
            list_frame = ttk.LabelFrame(tab, text=_t("dentist.labels.appointment_payments_only"), padding="5")
            list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

            columns = ('transaction_id', 'reference', 'date', 'user_id', 'patient', 'type', 'amount', 'method', 'status')
            self.payments_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=12)

            self.payments_tree.heading('transaction_id', text=_t('dentist.columns.id'))
            self.payments_tree.heading('reference', text=_t('dentist.columns.reference'))
            self.payments_tree.heading('date', text=_t('dentist.columns.date'))
            self.payments_tree.heading('user_id', text=_t('dentist.columns.user_id'))
            self.payments_tree.heading('patient', text=_t('dentist.columns.patient_num'))
            self.payments_tree.heading('type', text=_t('dentist.columns.type'))
            self.payments_tree.heading('amount', text=_t('dentist.columns.amount_gbp'))
            self.payments_tree.heading('method', text=_t('dentist.columns.payment_method'))
            self.payments_tree.heading('status', text=_t('dentist.columns.status'))

            self.payments_tree.column('transaction_id', width=50)
            self.payments_tree.column('reference', width=150)
            self.payments_tree.column('date', width=100)
            self.payments_tree.column('user_id', width=100)
            self.payments_tree.column('patient', width=80)
            self.payments_tree.column('type', width=100)
            self.payments_tree.column('amount', width=80)
            self.payments_tree.column('method', width=100)
            self.payments_tree.column('status', width=80)

            scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.payments_tree.yview)
            self.payments_tree.configure(yscrollcommand=scrollbar.set)
            self.payments_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            # Button frame
            button_frame = ttk.Frame(tab)
            button_frame.pack(fill=tk.X)

            ttk.Button(button_frame, text=_t("dentist.btn.process_refund"), command=self._process_payment_refund).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text=_t("dentist.btn.view_details"), command=self._view_payment_details).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text=_t("dentist.btn.export_csv"), command=self._export_payments_csv).pack(side=tk.LEFT, padx=5)

            # Load payments
            self._refresh_payments_list()

        def _refresh_payments_list(self):
            """Refresh the payments list from database - ONLY APPOINTMENTS."""
            for item in self.payments_tree.get_children():
                self.payments_tree.delete(item)

            try:
                from education_system.systems.university.infrastructure.database.db import get_connection
                with get_connection() as conn:
                    search_term = self.payment_search_var.get().strip()

                    # Only show appointments (transaction_type = 'appointment')
                    if search_term:
                        cursor = conn.execute('''
                            SELECT
                                dt.transaction_id,
                                dt.reference_number,
                                dt.created_at,
                                dt.student_id,
                                COALESCE(dp.patient_number, 'N/A') as patient_number,
                                dt.transaction_type,
                                dt.amount,
                                dt.payment_method,
                                dt.status
                            FROM transactions dt
                            LEFT JOIN dentist_patients dp ON dt.customer_id = dp.patient_id
                            WHERE dt.source_type = 'dentist' AND dt.transaction_type = 'appointment'
                              AND (dt.student_id LIKE ? OR dp.patient_number LIKE ? OR dp.user_name LIKE ?)
                            ORDER BY dt.created_at DESC
                        ''', (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'))
                    else:
                        cursor = conn.execute('''
                            SELECT
                                dt.transaction_id,
                                dt.reference_number,
                                dt.created_at,
                                dt.student_id,
                                COALESCE(dp.patient_number, 'N/A') as patient_number,
                                dt.transaction_type,
                                dt.amount,
                                dt.payment_method,
                                dt.status
                            FROM transactions dt
                            LEFT JOIN dentist_patients dp ON dt.customer_id = dp.patient_id
                            WHERE dt.source_type = 'dentist' AND dt.transaction_type = 'appointment'
                            ORDER BY dt.created_at DESC
                            LIMIT 100
                        ''')

                    for row in cursor.fetchall():
                        values = list(row)
                        # Ensure all 9 columns
                        while len(values) < 9:
                            values.append('N/A')
                        # Format amount
                        if values[6] and values[6] != 'N/A':
                            try:
                                values[6] = f"{float(values[6]):.2f}"
                            except (ValueError, TypeError):
                                pass
                        self.payments_tree.insert('', tk.END, values=values)

            except Exception as e:
                messagebox.showerror(_t("dentist.msg_titles.error"), f"Failed to load payments: {e}")

        def _view_payment_details(self):
            """View detailed payment information."""
            selection = self.payments_tree.selection()
            if not selection:
                messagebox.showwarning(_t("dentist.msg_titles.no_selection"), _t('gui.pastoral.health.health_portal.dentist.tabs.payments_refunds.dialogs.please_select_a_payment_to_view_details', default="Please select a payment to view details"))
                return

            try:
                values = self.payments_tree.item(selection[0])['values']
                if len(values) < 9:
                    messagebox.showerror(_t("dentist.msg_titles.data_error"), _t('gui.pastoral.health.health_portal.dentist.tabs.payments_refunds.dialogs.payment_record_is_incomplete', default="Payment record is incomplete"))
                    return

                details = f"""PAYMENT DETAILS
    ==================
    Transaction ID: {values[0]}
    Reference: {values[1]}
    Date: {values[2]}
    User ID: {values[3]}
    Patient Number: {values[4]}
    Transaction Type: {values[5]}
    Amount: GBP {values[6]}
    Payment Method: {values[7]}
    Status: {values[8]}
    """
                messagebox.showinfo(_t("dentist.msg_titles.payment_details"), details)
            except Exception as e:
                messagebox.showerror(_t("dentist.msg_titles.error"), f"Error viewing payment details: {e}")
