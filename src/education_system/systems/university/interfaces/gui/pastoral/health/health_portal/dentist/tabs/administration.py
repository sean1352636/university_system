
from education_system.systems.university.infrastructure.i18n import get_text as _t
from .. import *  # shared compatibility dependencies

class AdministrationTabMixin:
        def create_admin_tab(self):
            """Function 18: Create admin tab."""
            tab = ttk.Frame(self.notebook, padding="10")
            self.notebook.add(tab, text=_t("dentist.tabs.admin"))
            # Today's appointments
            today_frame = ttk.LabelFrame(tab, text=_t("dentist.todays_appointments"), padding="5")
            today_frame.pack(fill=tk.X, pady=(0, 10))
            columns = ('time', 'patient', 'dentist', 'treatment', 'status')
            self.today_tree = ttk.Treeview(today_frame, columns=columns, show='headings', height=6)
            for col in columns:
                self.today_tree.heading(col, text=col.title())
                self.today_tree.column(col, width=100)
            self.today_tree.pack(fill=tk.BOTH, expand=True)
            ttk.Button(today_frame, text=_t("dentist.btn.refresh_today"), command=self._refresh_today).pack(pady=5)
            # Reports
            report_frame = ttk.LabelFrame(tab, text=_t("dentist.reports.title"), padding="10")
            report_frame.pack(fill=tk.X, pady=(0, 10))
            ttk.Label(report_frame, text=_t("dentist.labels.report_type") + ":").grid(row=0, column=0, sticky=tk.W)
            self.report_type_var = tk.StringVar(value=_t('gui.pastoral.health.health_portal.dentist.tabs.administration.values.daily', default='daily'))
            ttk.Combobox(report_frame, textvariable=self.report_type_var, values=['daily', 'monthly'], width=20).grid(row=0, column=1, padx=5)
            ttk.Button(report_frame, text=_t("dentist.btn.generate_report"), command=self.generate_admin_report).grid(row=0, column=2, padx=5)
            ttk.Button(report_frame, text=_t("dentist.btn.email_report"), command=self.email_admin_report).grid(row=0, column=3, padx=5)
            # Report output
            output_frame = ttk.LabelFrame(tab, text=_t("dentist.report_output"), padding="5")
            output_frame.pack(fill=tk.BOTH, expand=True)
            self.report_text = tk.Text(output_frame, height=10, wrap=tk.WORD)
            self.report_text.pack(fill=tk.BOTH, expand=True)
            self._refresh_today()
