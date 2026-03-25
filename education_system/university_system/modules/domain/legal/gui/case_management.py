"""Case Management mixin for the Legal Services GUI."""

from education_system.university_system.modules.domain.legal.gui._imports import (
    tk, ttk, messagebox, scrolledtext, traceback,
    CaseManager, ConsultationManager, DocumentManager, PaymentManager,
    CASE_TYPES, CASE_STATUSES,
    _t, logger,
)


class CaseManagementMixin:
    """Case management tab: list, create, update, view details, close."""

    def create_case_management_tab(self):
        """Create case management tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("legal.tabs.case_management", default="Case Management"))

        # Split into left (list) and right (form/details)
        paned = ttk.PanedWindow(tab, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Left: Case listings
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=1)

        ttk.Label(
            left_frame,
            text=_t("legal.active_cases", default="Active Cases"),
            font=('Arial', 12, 'bold')
        ).pack(pady=5)

        # Filters
        filter_frame = ttk.LabelFrame(left_frame, text=_t("legal.filters", default="Filters"), padding="5")
        filter_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(filter_frame, text=_t("legal.labels.status", default="Status") + ":").grid(row=0, column=0, sticky=tk.W, padx=2)
        self.case_status_filter = ttk.Combobox(
            filter_frame,
            values=[_t("common.all", default="All")] + [_t(f"legal.status.{s}", default=s) for s in CASE_STATUSES],
            state='readonly', width=15
        )
        self.case_status_filter.set(_t("common.all", default="All"))
        self.case_status_filter.grid(row=0, column=1, padx=2)
        self.case_status_filter.bind('<<ComboboxSelected>>', lambda e: self.load_cases())

        ttk.Label(filter_frame, text=_t("legal.labels.case_type", default="Type") + ":").grid(row=0, column=2, sticky=tk.W, padx=2)
        self.case_type_filter = ttk.Combobox(
            filter_frame,
            values=[_t("common.all", default="All")] + [_t(f"legal.case_types.{t}", default=t) for t in CASE_TYPES],
            state='readonly', width=18
        )
        self.case_type_filter.set(_t("common.all", default="All"))
        self.case_type_filter.grid(row=0, column=3, padx=2)
        self.case_type_filter.bind('<<ComboboxSelected>>', lambda e: self.load_cases())

        # Search
        ttk.Label(filter_frame, text=_t("common.search", default="Search") + ":").grid(row=1, column=0, sticky=tk.W, padx=2, pady=5)
        self.case_search_entry = ttk.Entry(filter_frame, width=30)
        self.case_search_entry.grid(row=1, column=1, columnspan=2, padx=2, pady=5, sticky=tk.EW)
        ttk.Button(filter_frame, text=_t("common.search", default="Search"), command=self.load_cases).grid(row=1, column=3, padx=5, pady=5)

        # Cases list
        list_frame = ttk.Frame(left_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Treeview for cases
        columns = ('case_number', 'client', 'type', 'status', 'priority')
        self.cases_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)

        self.cases_tree.heading('case_number', text=_t("legal.labels.case_number", default="Case #"))
        self.cases_tree.heading('client', text=_t("legal.labels.client_name", default="Client"))
        self.cases_tree.heading('type', text=_t("legal.labels.case_type", default="Type"))
        self.cases_tree.heading('status', text=_t("legal.labels.status", default="Status"))
        self.cases_tree.heading('priority', text=_t("legal.labels.priority", default="Priority"))

        self.cases_tree.column('case_number', width=150)
        self.cases_tree.column('client', width=120)
        self.cases_tree.column('type', width=100)
        self.cases_tree.column('status', width=80)
        self.cases_tree.column('priority', width=70)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.cases_tree.yview)
        self.cases_tree.configure(yscrollcommand=scrollbar.set)

        self.cases_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.cases_tree.bind('<<TreeviewSelect>>', self.on_case_select)

        # Action buttons for cases
        btn_frame = ttk.Frame(left_frame)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(btn_frame, text=_t("legal.btn.view_details", default="View Details"), command=self.view_case_details).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text=_t("legal.btn.update_case", default="Update Case"), command=self.update_case_status).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text=_t("legal.btn.close_case", default="Close Case"), command=self.close_case).pack(side=tk.LEFT, padx=2)

        # Right: Case creation form (for staff/admin)
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=1)

        if self.user_role in ['admin', 'staff', 'lawyer']:
            form_frame = ttk.LabelFrame(right_frame, text=_t("legal.create_new_case", default="Create New Case"), padding="10")
            form_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

            # Get current user details
            user_name, user_email = self._get_user_details_from_db()
            user_id = self.current_user.get('student_id') or self.current_user.get('username', '')

            # Client Name
            ttk.Label(form_frame, text=_t("legal.labels.client_name", default="Client Name") + " *:").grid(row=0, column=0, sticky=tk.W, pady=3)
            self.client_name_entry = ttk.Entry(form_frame, width=35)
            self.client_name_entry.insert(0, user_name)
            self.client_name_entry.grid(row=0, column=1, pady=3, sticky=tk.EW)

            # Client ID
            ttk.Label(form_frame, text=_t("legal.labels.client_id", default="Client ID") + " *:").grid(row=1, column=0, sticky=tk.W, pady=3)
            self.client_id_entry = ttk.Entry(form_frame, width=35)
            self.client_id_entry.insert(0, user_id)
            self.client_id_entry.grid(row=1, column=1, pady=3, sticky=tk.EW)

            # Client Email
            ttk.Label(form_frame, text=_t("legal.labels.client_email", default="Client Email") + ":").grid(row=2, column=0, sticky=tk.W, pady=3)
            self.client_email_entry = ttk.Entry(form_frame, width=35)
            self.client_email_entry.insert(0, user_email)
            self.client_email_entry.grid(row=2, column=1, pady=3, sticky=tk.EW)

            # Case Type
            ttk.Label(form_frame, text=_t("legal.labels.case_type", default="Case Type") + " *:").grid(row=3, column=0, sticky=tk.W, pady=3)
            self.case_type_combo = ttk.Combobox(form_frame, values=CASE_TYPES, state='readonly', width=33)
            self.case_type_combo.set('consultation')
            self.case_type_combo.grid(row=3, column=1, pady=3, sticky=tk.EW)

            # Case Title
            ttk.Label(form_frame, text=_t("legal.labels.case_title", default="Case Title") + " *:").grid(row=4, column=0, sticky=tk.W, pady=3)
            self.case_title_entry = ttk.Entry(form_frame, width=35)
            self.case_title_entry.grid(row=4, column=1, pady=3, sticky=tk.EW)

            # Description
            ttk.Label(form_frame, text=_t("legal.labels.description", default="Description") + ":").grid(row=5, column=0, sticky=tk.NW, pady=3)
            self.case_desc_text = scrolledtext.ScrolledText(form_frame, width=35, height=5)
            self.case_desc_text.grid(row=5, column=1, pady=3, sticky=tk.EW)

            # Priority
            ttk.Label(form_frame, text=_t("legal.labels.priority", default="Priority") + ":").grid(row=6, column=0, sticky=tk.W, pady=3)
            self.priority_combo = ttk.Combobox(form_frame, values=['low', 'normal', 'high', 'urgent'], state='readonly', width=33)
            self.priority_combo.set('normal')
            self.priority_combo.grid(row=6, column=1, pady=3, sticky=tk.EW)

            # Assigned Lawyer
            ttk.Label(form_frame, text=_t("legal.labels.assigned_lawyer", default="Assigned Lawyer") + ":").grid(row=7, column=0, sticky=tk.W, pady=3)
            self.lawyer_entry = ttk.Entry(form_frame, width=35)
            self.lawyer_entry.grid(row=7, column=1, pady=3, sticky=tk.EW)

            form_frame.columnconfigure(1, weight=1)

            ttk.Button(
                form_frame,
                text=_t("legal.btn.create_case", default="Create Case"),
                command=self.create_new_case
            ).grid(row=8, column=1, pady=15, sticky=tk.E)

        else:
            # Student view - case details
            details_frame = ttk.LabelFrame(right_frame, text=_t("legal.case_details", default="Case Details"), padding="10")
            details_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

            self.case_details_text = scrolledtext.ScrolledText(details_frame, wrap=tk.WORD, state='disabled')
            self.case_details_text.pack(fill=tk.BOTH, expand=True)

        # Load cases
        self.load_cases()

    def create_new_case(self):
        """Create a new legal case"""
        try:
            # Get form values
            client_name = self.client_name_entry.get().strip()
            client_id = self.client_id_entry.get().strip()
            client_email = self.client_email_entry.get().strip()
            case_type = self.case_type_combo.get()
            case_title = self.case_title_entry.get().strip()
            case_description = self.case_desc_text.get('1.0', tk.END).strip()
            priority = self.priority_combo.get()
            assigned_lawyer = self.lawyer_entry.get().strip()

            # Validation
            if not all([client_name, client_id, case_type, case_title]):
                messagebox.showwarning(
                    _t("common.warning", default="Warning"),
                    _t("legal.errors.fill_required", default="Please fill all required fields")
                )
                return

            # Create case
            case_id = CaseManager.create_case(
                client_id=client_id,
                client_name=client_name,
                client_email=client_email,
                case_type=case_type,
                case_title=case_title,
                case_description=case_description,
                priority=priority,
                assigned_lawyer=assigned_lawyer if assigned_lawyer else None,
                created_by=self.current_user.get('username')
            )

            if case_id:
                # Get case number for display
                case = CaseManager.get_case(case_id)
                case_number = case['case_number'] if case else str(case_id)

                messagebox.showinfo(
                    _t("common.success", default="Success"),
                    _t("legal.messages.case_created", default="Legal case created successfully. Case #: {case_number}").format(case_number=case_number)
                )

                # Clear form
                self.client_name_entry.delete(0, tk.END)
                self.client_id_entry.delete(0, tk.END)
                self.client_email_entry.delete(0, tk.END)
                self.case_title_entry.delete(0, tk.END)
                self.case_desc_text.delete('1.0', tk.END)
                self.lawyer_entry.delete(0, tk.END)
                self.case_type_combo.set('consultation')
                self.priority_combo.set('normal')

                # Reload cases
                self.load_cases()
            else:
                messagebox.showerror(
                    _t("common.error", default="Error"),
                    _t("legal.errors.create_case_failed", default="Failed to create case")
                )

        except Exception as e:
            messagebox.showerror(
                _t("common.error", default="Error"),
                _t("legal.errors.create_case_failed", default="Failed to create case: {error}").format(error=str(e))
            )
            print(f"Error creating case: {traceback.format_exc()}")

    def update_case_status(self):
        """Update the selected case status"""
        if not self.selected_case:
            messagebox.showwarning(
                _t("common.warning", default="Warning"),
                _t("legal.errors.no_case_selected", default="Please select a case first")
            )
            return

        try:
            # Create update dialog
            dialog = tk.Toplevel(self.window)
            dialog.title(_t("legal.btn.update_case", default="Update Case"))
            dialog.geometry("400x300")
            dialog.transient(self.window)
            dialog.grab_set()

            ttk.Label(dialog, text=f"Case: {self.selected_case['case_number']}", font=('Arial', 12, 'bold')).pack(pady=10)

            # Status
            ttk.Label(dialog, text=_t("legal.labels.status", default="Status") + ":").pack(anchor=tk.W, padx=20)
            status_combo = ttk.Combobox(dialog, values=CASE_STATUSES, state='readonly', width=30)
            status_combo.set(self.selected_case.get('status', 'open'))
            status_combo.pack(pady=5)

            # Priority
            ttk.Label(dialog, text=_t("legal.labels.priority", default="Priority") + ":").pack(anchor=tk.W, padx=20)
            priority_combo = ttk.Combobox(dialog, values=['low', 'normal', 'high', 'urgent'], state='readonly', width=30)
            priority_combo.set(self.selected_case.get('priority', 'normal'))
            priority_combo.pack(pady=5)

            # Assigned Lawyer
            ttk.Label(dialog, text=_t("legal.labels.assigned_lawyer", default="Assigned Lawyer") + ":").pack(anchor=tk.W, padx=20)
            lawyer_entry = ttk.Entry(dialog, width=33)
            lawyer_entry.insert(0, self.selected_case.get('assigned_lawyer', '') or '')
            lawyer_entry.pack(pady=5)

            def save_updates():
                updates = {
                    'status': status_combo.get(),
                    'priority': priority_combo.get(),
                    'assigned_lawyer': lawyer_entry.get().strip() or None
                }

                if CaseManager.update_case(self.selected_case['case_id'], **updates):
                    messagebox.showinfo(
                        _t("common.success", default="Success"),
                        _t("legal.messages.case_updated", default="Case updated successfully")
                    )
                    dialog.destroy()
                    self.load_cases()
                else:
                    messagebox.showerror(
                        _t("common.error", default="Error"),
                        _t("legal.errors.update_failed", default="Failed to update case")
                    )

            ttk.Button(dialog, text=_t("common.save", default="Save"), command=save_updates).pack(pady=20)

        except Exception as e:
            messagebox.showerror(
                _t("common.error", default="Error"),
                str(e)
            )

    def view_case_details(self):
        """Display full case details in a dialog"""
        if not self.selected_case:
            messagebox.showwarning(
                _t("common.warning", default="Warning"),
                _t("legal.errors.no_case_selected", default="Please select a case first")
            )
            return

        try:
            case = CaseManager.get_case(self.selected_case['case_id'])
            if not case:
                messagebox.showerror(_t("common.error", default="Error"), "Case not found")
                return

            # Get related data
            consultations = ConsultationManager.get_all_consultations({'case_id': case['case_id']}) if case.get('case_id') else []
            documents = DocumentManager.get_case_documents(case['case_id']) if case.get('case_id') else []
            payments = PaymentManager.get_all_payments({'case_id': case['case_id']}) if case.get('case_id') else []

            # Create details window
            dialog = tk.Toplevel(self.window)
            dialog.title(f"Case Details - {case['case_number']}")
            dialog.geometry("700x600")
            dialog.transient(self.window)

            # Notebook for sections
            notebook = ttk.Notebook(dialog)
            notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Overview tab
            overview_tab = ttk.Frame(notebook)
            notebook.add(overview_tab, text=_t("common.overview"))

            details_text = scrolledtext.ScrolledText(overview_tab, wrap=tk.WORD)
            details_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

            details = f"""
CASE DETAILS
{'='*60}

Case Number:     {case['case_number']}
Status:          {case['status'].upper()}
Priority:        {case['priority'].upper()}

CLIENT INFORMATION
{'-'*40}
Name:            {case['client_name']}
ID:              {case['client_id']}
Email:           {case.get('client_email', 'N/A')}

CASE INFORMATION
{'-'*40}
Type:            {case['case_type']}
Title:           {case['case_title']}

Description:
{case.get('case_description', 'No description provided')}

ASSIGNMENT
{'-'*40}
Assigned Lawyer: {case.get('assigned_lawyer', 'Not assigned')}
Created By:      {case.get('created_by', 'Unknown')}
Created At:      {case.get('created_at', 'Unknown')}
Updated At:      {case.get('updated_at', 'Unknown')}

FINANCIAL SUMMARY
{'-'*40}
Total Fees:      GBP {case.get('total_fees', 0):.2f}
Amount Paid:     GBP {case.get('amount_paid', 0):.2f}
Balance Due:     GBP {(case.get('total_fees', 0) - case.get('amount_paid', 0)):.2f}
"""
            details_text.insert('1.0', details)
            details_text.config(state='disabled')

            # Consultations tab
            consult_tab = ttk.Frame(notebook)
            notebook.add(consult_tab, text=f"Consultations ({len(consultations)})")

            consult_text = scrolledtext.ScrolledText(consult_tab, wrap=tk.WORD)
            consult_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

            if consultations:
                consult_info = "CONSULTATIONS\n" + "="*60 + "\n\n"
                for c in consultations:
                    consult_info += f"Date: {c['scheduled_date']} at {c['scheduled_time']}\n"
                    consult_info += f"Type: {c['consultation_type']} | Duration: {c['duration_minutes']} min\n"
                    consult_info += f"Fee: GBP {c['fee']:.2f} | Payment: {c['payment_status']}\n"
                    consult_info += f"Status: {c['status']}\n"
                    consult_info += "-"*40 + "\n\n"
            else:
                consult_info = "No consultations scheduled for this case."
            consult_text.insert('1.0', consult_info)
            consult_text.config(state='disabled')

            # Documents tab
            docs_tab = ttk.Frame(notebook)
            notebook.add(docs_tab, text=f"Documents ({len(documents)})")

            docs_text = scrolledtext.ScrolledText(docs_tab, wrap=tk.WORD)
            docs_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

            if documents:
                docs_info = "DOCUMENTS\n" + "="*60 + "\n\n"
                for d in documents:
                    docs_info += f"Name: {d['document_name']}\n"
                    docs_info += f"Type: {d['document_type']} | Version: {d['version']}\n"
                    docs_info += f"Created: {d['created_at']} by {d.get('created_by', 'Unknown')}\n"
                    docs_info += "-"*40 + "\n\n"
            else:
                docs_info = "No documents attached to this case."
            docs_text.insert('1.0', docs_info)
            docs_text.config(state='disabled')

            # Payments tab
            payments_tab = ttk.Frame(notebook)
            notebook.add(payments_tab, text=f"Payments ({len(payments)})")

            payments_text = scrolledtext.ScrolledText(payments_tab, wrap=tk.WORD)
            payments_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

            if payments:
                payments_info = "PAYMENT HISTORY\n" + "="*60 + "\n\n"
                for p in payments:
                    payments_info += f"Date: {p['created_at']}\n"
                    payments_info += f"Amount: GBP {p['amount']:.2f} | Method: {p['payment_method']}\n"
                    payments_info += f"Type: {p['payment_type']} | Status: {p['status']}\n"
                    payments_info += f"Reference: {p['transaction_reference']}\n"
                    payments_info += "-"*40 + "\n\n"
            else:
                payments_info = "No payments recorded for this case."
            payments_text.insert('1.0', payments_info)
            payments_text.config(state='disabled')

            # Close button
            ttk.Button(dialog, text=_t("common.close", default="Close"), command=dialog.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror(_t("common.error", default="Error"), str(e))
            print(f"Error viewing case details: {traceback.format_exc()}")

    def close_case(self):
        """Close the selected case"""
        if not self.selected_case:
            messagebox.showwarning(
                _t("common.warning", default="Warning"),
                _t("legal.errors.no_case_selected", default="Please select a case first")
            )
            return

        if self.selected_case.get('status') == 'closed':
            messagebox.showinfo(
                _t("common.info", default="Info"),
                _t("legal.messages.case_already_closed", default="This case is already closed")
            )
            return

        # Confirm closure
        if not messagebox.askyesno(
            _t("common.confirm", default="Confirm"),
            _t("legal.confirm.close_case", default="Are you sure you want to close case {case_number}?").format(
                case_number=self.selected_case['case_number']
            )
        ):
            return

        try:
            if CaseManager.close_case(self.selected_case['case_id'], closed_by=self.current_user.get('username')):
                messagebox.showinfo(
                    _t("common.success", default="Success"),
                    _t("legal.messages.case_closed", default="Case closed successfully")
                )
                self.load_cases()
            else:
                messagebox.showerror(
                    _t("common.error", default="Error"),
                    _t("legal.errors.close_failed", default="Failed to close case")
                )

        except Exception as e:
            messagebox.showerror(_t("common.error", default="Error"), str(e))

    def load_cases(self):
        """Load cases into the treeview"""
        try:
            # Clear existing items
            for item in self.cases_tree.get_children():
                self.cases_tree.delete(item)

            # Build filters
            filters = {}
            status_filter = self.case_status_filter.get()
            type_filter = self.case_type_filter.get()
            search = self.case_search_entry.get().strip()

            if status_filter != _t("common.all", default="All"):
                # Map display value back to database value
                for s in CASE_STATUSES:
                    if _t(f"legal.status.{s}", default=s) == status_filter:
                        filters['status'] = s
                        break

            if type_filter != _t("common.all", default="All"):
                for t in CASE_TYPES:
                    if _t(f"legal.case_types.{t}", default=t) == type_filter:
                        filters['case_type'] = t
                        break

            if search:
                filters['search'] = search

            # Get cases
            self.cases_data = CaseManager.get_all_cases(filters)

            # Populate treeview
            for case in self.cases_data:
                self.cases_tree.insert('', tk.END, values=(
                    case['case_number'],
                    case['client_name'],
                    case['case_type'],
                    case['status'],
                    case['priority']
                ))

        except Exception as e:
            print(f"Error loading cases: {e}")

    def on_case_select(self, event):
        """Handle case selection"""
        selected = self.cases_tree.selection()
        if selected:
            item = self.cases_tree.item(selected[0])
            case_number = item['values'][0]
            self.selected_case = next((c for c in self.cases_data if c['case_number'] == case_number), None)
