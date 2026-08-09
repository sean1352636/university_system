"""Extracted function implementation."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import student_analytics_view_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def create_integrations_view(self, parent):
    """Create integrations view"""
    integrations_frame = ttk.Frame(parent)
    integrations_frame.pack(fill="both", expand=True)

    # Main card
    integrations_card = ttk.Frame(integrations_frame, style='Card.TFrame')
    integrations_card.pack(fill='both', expand=True, padx=10, pady=10)

    ttk.Label(integrations_card, text=_t('gui.academics.ai_detector.student_analytics_view_parts.create_integrations_view.labels.external_integrations', default="External Integrations"), style='Title.TLabel').pack(anchor='w', padx=15, pady=15)

    # Plagiarism Checker Integration
    plagiarism_frame = ttk.LabelFrame(integrations_card, text=_t('gui.academics.ai_detector.student_analytics_view_parts.create_integrations_view.labels.plagiarism_checker_integration', default="Plagiarism Checker Integration"), padding=15)
    plagiarism_frame.pack(fill='x', padx=15, pady=(0, 15))

    plag_row1 = ttk.Frame(plagiarism_frame)
    plag_row1.pack(fill='x', pady=2)
    ttk.Label(plag_row1, text=_t('gui.academics.ai_detector.student_analytics_view_parts.create_integrations_view.labels.service', default="Service:")).pack(side='left')
    self.plagiarism_service_var = tk.StringVar(value=_t('gui.academics.ai_detector.student_analytics_view_parts.create_integrations_view.values.turnitin', default="Turnitin"))
    ttk.Combobox(plag_row1, textvariable=self.plagiarism_service_var,
                values=["Turnitin", "Copyleaks", "Grammarly", "PlagScan"],
                width=15, state='readonly').pack(side='left', padx=(5, 15))

    ttk.Label(plag_row1, text=_t('gui.academics.ai_detector.student_analytics_view_parts.create_integrations_view.labels.api_key', default="API Key:")).pack(side='left')
    self.plagiarism_api_var = tk.StringVar()
    ttk.Entry(plag_row1, textvariable=self.plagiarism_api_var, width=30, show='*').pack(side='left', padx=(5, 0))

    plag_buttons = ttk.Frame(plagiarism_frame)
    plag_buttons.pack(fill='x', pady=(10, 0))
    ttk.Button(plag_buttons, text=_t('gui.academics.ai_detector.student_analytics_view_parts.create_integrations_view.buttons.save_configuration', default="Save Configuration"),
              command=self._save_plagiarism_config).pack(side='left', padx=(0, 10))
    ttk.Button(plag_buttons, text=_t('gui.academics.ai_detector.student_analytics_view_parts.create_integrations_view.buttons.test_connection', default="Test Connection"),
              command=self._test_plagiarism_connection).pack(side='left', padx=(0, 10))
    ttk.Button(plag_buttons, text=_t('gui.academics.ai_detector.student_analytics_view_parts.create_integrations_view.buttons.sync_results', default="Sync Results"),
              command=self.sync_with_plagiarism_checker).pack(side='left')

    # Academic Record Integration
    academic_frame = ttk.LabelFrame(integrations_card, text=_t('gui.academics.ai_detector.student_analytics_view_parts.create_integrations_view.labels.academic_record_system', default="Academic Record System"), padding=15)
    academic_frame.pack(fill='x', padx=15, pady=(0, 15))

    acad_row1 = ttk.Frame(academic_frame)
    acad_row1.pack(fill='x', pady=2)
    ttk.Label(acad_row1, text=_t('gui.academics.ai_detector.student_analytics_view_parts.create_integrations_view.labels.system', default="System:")).pack(side='left')
    self.academic_system_var = tk.StringVar(value=_t('gui.academics.ai_detector.student_analytics_view_parts.create_integrations_view.values.internal', default="Internal"))
    ttk.Combobox(acad_row1, textvariable=self.academic_system_var,
                values=["Internal", "Banner", "PeopleSoft", "Ellucian"],
                width=15, state='readonly').pack(side='left', padx=(5, 15))

    self.auto_push_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(acad_row1, text=_t('gui.academics.ai_detector.student_analytics_view_parts.create_integrations_view.buttons.auto_push_confirmed_violations', default="Auto-push confirmed violations"),
                   variable=self.auto_push_var).pack(side='left')

    acad_row2 = ttk.Frame(academic_frame)
    acad_row2.pack(fill='x', pady=2)
    ttk.Label(acad_row2, text=_t('gui.academics.ai_detector.student_analytics_view_parts.create_integrations_view.labels.submission_id', default="Submission ID:")).pack(side='left')
    self.push_submission_var = tk.StringVar()
    ttk.Entry(acad_row2, textvariable=self.push_submission_var, width=20).pack(side='left', padx=(5, 10))
    ttk.Button(acad_row2, text=_t('gui.academics.ai_detector.student_analytics_view_parts.create_integrations_view.buttons.push_to_academic_record', default="Push to Academic Record"),
              command=self.push_to_academic_record).pack(side='left')

    # Integration Status
    status_frame = ttk.LabelFrame(integrations_card, text=_t('gui.academics.ai_detector.student_analytics_view_parts.create_integrations_view.labels.integration_status', default="Integration Status"), padding=15)
    status_frame.pack(fill='x', padx=15, pady=(0, 15))

    columns = ('service', 'status', 'last_sync', 'records')
    self.integration_tree = ttk.Treeview(status_frame, columns=columns, show='headings', height=4)
    self.integration_tree.heading('service', text=_t('gui.academics.ai_detector.student_analytics_view_parts.create_integrations_view.headings.service', default='Service'))
    self.integration_tree.heading('status', text=_t('gui.academics.ai_detector.student_analytics_view_parts.create_integrations_view.headings.status', default='Status'))
    self.integration_tree.heading('last_sync', text=_t('gui.academics.ai_detector.student_analytics_view_parts.create_integrations_view.headings.last_sync', default='Last Sync'))
    self.integration_tree.heading('records', text=_t('gui.academics.ai_detector.student_analytics_view_parts.create_integrations_view.headings.records', default='Records'))

    self.integration_tree.column('service', width=150)
    self.integration_tree.column('status', width=100)
    self.integration_tree.column('last_sync', width=150)
    self.integration_tree.column('records', width=80)

    self.integration_tree.pack(fill='x')

    # Load integration status
    self._load_integration_status()
