from .. import *  # shared compatibility dependencies

class ToolbarMixin:
        def create_widgets(self):
            """Function 2: Create all GUI widgets."""
            if not self._is_embedded:
                self.root.title(_t("dentist.window_title"))
            header = ttk.Frame(self.root, padding="10")
            header.pack(fill=tk.X)
            ttk.Label(header, text=_t("dentist.title"), font=('Arial', 16, 'bold')).pack(side=tk.LEFT)
            ttk.Label(header, text=f"User: {self.user_id} | Role: {self.user_role}").pack(side=tk.RIGHT)
            self.notebook = ttk.Notebook(self.root)
            self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
            self.create_appointments_tab()
            self.create_treatments_tab()
            self.create_records_tab()
            if self.user_role in ('admin', 'staff'):
                self.create_admin_tab()
                self.create_payments_refunds_tab()
            footer = ttk.Frame(self.root, padding="10")
            footer.pack(fill=tk.X)
            ttk.Button(footer, text=_t("common.refresh"), command=self.refresh_all_data).pack(side=tk.LEFT, padx=5)
            ttk.Button(footer, text=_t("common.close"), command=self.return_to_homescreen).pack(side=tk.RIGHT, padx=5)

        def refresh_all_data(self):
            """Function 5: Refresh all data."""
            self._load_patient()
            self._refresh_appointments_list()
            self._refresh_treatments_list()
            messagebox.showinfo(_t("dentist.window_title"), _t("dentist.messages.data_refreshed"))
