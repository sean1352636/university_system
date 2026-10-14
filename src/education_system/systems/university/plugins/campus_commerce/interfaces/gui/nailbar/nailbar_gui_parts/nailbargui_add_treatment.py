"""Methods add_treatment through refresh_refunds_list."""

from .. import nailbar_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class NailBarGUI:
    def add_treatment(self):
        """Add a new treatment"""
        name = self.treatment_name_var.get().strip()
        category_display = self.treatment_category_combo.get()
        duration_str = self.treatment_duration_var.get().strip()
        price_str = self.treatment_price_var.get().strip()
        description = self.treatment_desc_text.get("1.0", tk.END).strip()

        if not name or not category_display or not price_str:
            messagebox.showerror(_t("common.error"), _t("nailbar.errors.fill_required"))
            return

        try:
            duration = int(duration_str) if duration_str else 45
            price = float(price_str)

            categories = self._get_categories()
            category = next((k for k, v in categories.items() if v == category_display), 'manicure')

            from education_system.systems.university.plugins.campus_commerce.domain.nailbar.services.nailbar_core import TreatmentManager
            treatment_id = TreatmentManager.add_treatment(
                name=name, category=category, price=price,
                duration_minutes=duration, description=description
            )

            log_activity('create', 'nailbar_treatment', treatment_id=treatment_id,
                        user_id=self.current_user.get('user_id'))

            messagebox.showinfo(_t("common.success"), _t("nailbar.messages.treatment_added"))
            self._clear_treatment_form()
            self._load_treatments()

        except ValueError:
            messagebox.showerror(_t("common.error"), _t("nailbar.errors.invalid_number"))
        except Exception as e:
            messagebox.showerror(_t("common.error"), str(e))

    def update_treatment(self):
        """Update selected treatment"""
        selected = self.treatments_tree.selection()
        if not selected:
            messagebox.showwarning(_t("common.warning"), _t("nailbar.errors.select_treatment"))
            return

        item = self.treatments_tree.item(selected[0])
        treatment_id = item['values'][0]

        name = self.treatment_name_var.get().strip()
        category_display = self.treatment_category_combo.get()
        duration_str = self.treatment_duration_var.get().strip()
        price_str = self.treatment_price_var.get().strip()

        if not name or not price_str:
            messagebox.showerror(_t("common.error"), _t("nailbar.errors.fill_required"))
            return

        try:
            duration = int(duration_str) if duration_str else 45
            price = float(price_str)

            categories = self._get_categories()
            category = next((k for k, v in categories.items() if v == category_display), 'manicure')

            from education_system.systems.university.plugins.campus_commerce.domain.nailbar.services.nailbar_core import TreatmentManager
            TreatmentManager.update_treatment(
                treatment_id, name=name, category=category,
                price=price, duration_minutes=duration
            )

            log_activity('update', 'nailbar_treatment', treatment_id=treatment_id,
                        user_id=self.current_user.get('user_id'))

            messagebox.showinfo(_t("common.success"), _t("nailbar.messages.treatment_updated"))
            self._load_treatments()

        except ValueError:
            messagebox.showerror(_t("common.error"), _t("nailbar.errors.invalid_number"))
        except Exception as e:
            messagebox.showerror(_t("common.error"), str(e))

    def _clear_treatment_form(self):
        """Clear treatment form"""
        self.treatment_name_var.set("")
        self.treatment_category_combo.set("")
        self.treatment_duration_var.set("45")
        self.treatment_price_var.set("")
        self.treatment_desc_text.delete("1.0", tk.END)

    def add_technician(self):
        """Add a new technician"""
        name = self.tech_name_var.get().strip()
        emp_id = self.tech_emp_id_var.get().strip()
        specialties = self.tech_specialties_var.get().strip()
        certification = self.tech_cert_var.get().strip()
        phone = self.tech_phone_var.get().strip()
        email = self.tech_email_var.get().strip()

        if not name:
            messagebox.showerror(_t("common.error"), _t("nailbar.errors.fill_required"))
            return

        try:
            from education_system.systems.university.plugins.campus_commerce.domain.nailbar.services.nailbar_core import TechnicianManager
            tech_id = TechnicianManager.add_technician(
                name=name, employee_id=emp_id, specialties=specialties,
                certification=certification, phone=phone, email=email
            )

            log_activity('create', 'nailbar_technician', technician_id=tech_id,
                        user_id=self.current_user.get('user_id'))

            messagebox.showinfo(_t("common.success"), _t("nailbar.messages.technician_added"))
            self._clear_technician_form()
            self._load_technicians()

        except Exception as e:
            messagebox.showerror(_t("common.error"), str(e))

    def _clear_technician_form(self):
        """Clear technician form"""
        self.tech_name_var.set("")
        self.tech_emp_id_var.set("")
        self.tech_specialties_var.set("")
        self.tech_cert_var.set("")
        self.tech_phone_var.set("")
        self.tech_email_var.set("")

    def generate_admin_report(self):
        """Generate admin report"""
        try:
            from education_system.systems.university.plugins.campus_commerce.domain.nailbar.services.nailbar_core import ReportManager
            report = ReportManager.generate_admin_report()

            self.report_text.delete("1.0", tk.END)
            self.report_text.insert("1.0", report)

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("nailbar.errors.report_failed").format(error=str(e)))

    def email_admin_report(self):
        """Email admin report"""
        report_content = self.report_text.get("1.0", tk.END).strip()

        if not report_content:
            self.generate_admin_report()
            report_content = self.report_text.get("1.0", tk.END).strip()

        try:
            from education_system.systems.university.infrastructure.email.email_service import send_email
            from education_system.systems.university.infrastructure.email.template_utils import render_template

            with get_db_connection() as conn:
                admin = conn.execute(
                    "SELECT email FROM users WHERE role = 'admin' AND email IS NOT NULL LIMIT 1"
                ).fetchone()

            if admin and admin['email']:
                # Use JSON template for email
                subject, body = render_template('commerce/nailbar/admin_report', {
                    'report_date': datetime.now().strftime('%Y-%m-%d'),
                    'report_content': report_content
                })

                send_email(
                    recipient_email=admin['email'],
                    subject=subject,
                    body=body
                )

                log_activity('email', 'nailbar_report', user_id=self.current_user.get('user_id'))
                messagebox.showinfo(_t("common.success"), _t("nailbar.messages.report_emailed"))
            else:
                messagebox.showwarning(_t("common.warning"), _t("nailbar.errors.no_admin_email"))

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("nailbar.errors.email_failed").format(error=str(e)))

    def create_refunds_tab(self):
        """Create the refunds management tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_t("nailbar.labels.refunds"))

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(header_frame, text=_t("nailbar.labels.transaction_refunds"),
                 font=('Helvetica', 14, 'bold')).pack(side=tk.LEFT)

        # Search frame
        search_frame = ttk.LabelFrame(tab, text=_t("nailbar.labels.search_transactions"), padding="10")
        search_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(search_frame, text=_t("nailbar.labels.search_by")).pack(side=tk.LEFT, padx=5)
        self.refunds_search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.refunds_search_var, width=30)
        search_entry.pack(side=tk.LEFT, padx=5)

        ttk.Button(search_frame, text=_t("nailbar.btn.search"), command=self.refresh_refunds_list).pack(side=tk.LEFT, padx=2)
        ttk.Button(search_frame, text=_t("nailbar.btn.show_all"), command=lambda: [self.refunds_search_var.set(''), self.refresh_refunds_list()]).pack(side=tk.LEFT, padx=2)

        # Transactions table
        trans_frame = ttk.Frame(tab)
        trans_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        columns = ('transaction_id', 'appointment_id', 'date', 'customer', 'amount', 'payment_method', 'status')
        self.refunds_tree = ttk.Treeview(trans_frame, columns=columns, show='headings', height=15)

        self.refunds_tree.heading('transaction_id', text=_t('nailbar.columns.transaction_id'))
        self.refunds_tree.heading('appointment_id', text=_t('nailbar.columns.appointment_id'))
        self.refunds_tree.heading('date', text=_t('nailbar.columns.date'))
        self.refunds_tree.heading('customer', text=_t('nailbar.columns.customer'))
        self.refunds_tree.heading('amount', text=_t('nailbar.columns.amount'))
        self.refunds_tree.heading('payment_method', text=_t('nailbar.columns.payment_method'))
        self.refunds_tree.heading('status', text=_t('nailbar.columns.status'))

        self.refunds_tree.column('transaction_id', width=120)
        self.refunds_tree.column('appointment_id', width=120)
        self.refunds_tree.column('date', width=150)
        self.refunds_tree.column('customer', width=120)
        self.refunds_tree.column('amount', width=100)
        self.refunds_tree.column('payment_method', width=120)
        self.refunds_tree.column('status', width=100)

        scrollbar = ttk.Scrollbar(trans_frame, orient=tk.VERTICAL, command=self.refunds_tree.yview)
        self.refunds_tree.configure(yscrollcommand=scrollbar.set)

        self.refunds_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Buttons
        button_frame = ttk.Frame(tab)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text=_t("nailbar.btn.process_refund"), command=self.process_nailbar_refund).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t("nailbar.btn.view_details"), command=self.view_refund_transaction_details).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t("nailbar.btn.export_csv"), command=self.export_refunds_to_csv).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t("nailbar.btn.refresh"), command=self.refresh_refunds_list).pack(side=tk.LEFT, padx=5)

        # Initial load
        self.refresh_refunds_list()

    def refresh_refunds_list(self):
        """Refresh the refunds list with all transactions"""
        # Clear existing items
        for item in self.refunds_tree.get_children():
            self.refunds_tree.delete(item)

        try:
            with get_db_connection() as conn:
                search_term = self.refunds_search_var.get().strip()

                if search_term:
                    query = '''
                        SELECT transaction_id, reference_id as appointment_id, created_at, customer_id,
                               amount, payment_method, status
                        FROM transactions
                        WHERE source_type = 'nail_bar' AND (transaction_id LIKE ? OR reference_id LIKE ? OR customer_id LIKE ?)
                        ORDER BY created_at DESC
                        LIMIT 500
                    '''
                    search_pattern = f'%{search_term}%'
                    cursor = conn.execute(query, (search_pattern, search_pattern, search_pattern))
                else:
                    query = '''
                        SELECT transaction_id, reference_id as appointment_id, created_at, customer_id,
                               amount, payment_method, status
                        FROM transactions
                        WHERE source_type = 'nail_bar'
                        ORDER BY created_at DESC
                        LIMIT 500
                    '''
                    cursor = conn.execute(query)

                transactions = cursor.fetchall()

                for trans in transactions:
                    trans_id, appt_id, created_at, customer_id, amount, payment_method, status = trans

                    # Format payment method
                    payment_display = payment_method.replace('_', ' ').title() if payment_method else 'N/A'

                    # Format status
                    status_display = status.upper() if status else 'COMPLETED'

                    self.refunds_tree.insert('', tk.END, values=(
                        trans_id,
                        appt_id or 'N/A',
                        created_at,
                        customer_id or 'N/A',
                        f"£{amount:.2f}",
                        payment_display,
                        status_display
                    ))

        except Exception as e:
            messagebox.showerror(_t("nailbar.msg_titles.database_error"), f"Error loading transactions: {e}")
            logger.error(f"Error loading transactions: {e}")
