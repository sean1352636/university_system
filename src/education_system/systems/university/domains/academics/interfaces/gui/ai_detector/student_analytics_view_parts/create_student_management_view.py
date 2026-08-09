"""Extracted function implementation."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import student_analytics_view_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def create_student_management_view(self, parent):
    """Create student management view"""
    student_frame = ttk.Frame(parent)
    student_frame.pack(fill="both", expand=True)

    # Main card
    student_card = ttk.Frame(student_frame, style='Card.TFrame')
    student_card.pack(fill='both', expand=True, padx=10, pady=10)

    ttk.Label(student_card, text=_t('gui.academics.ai_detector.student_analytics_view_parts.create_student_management_view.labels.student_management', default="Student Management"), style='Title.TLabel').pack(anchor='w', padx=15, pady=15)

    # Student Profile Section
    profile_frame = ttk.LabelFrame(student_card, text=_t('gui.academics.ai_detector.student_analytics_view_parts.create_student_management_view.labels.student_profile', default="Student Profile"), padding=15)
    profile_frame.pack(fill='x', padx=15, pady=(0, 15))

    profile_row = ttk.Frame(profile_frame)
    profile_row.pack(fill='x')
    ttk.Label(profile_row, text=_t('gui.academics.ai_detector.student_analytics_view_parts.create_student_management_view.labels.student_id', default="Student ID:")).pack(side='left')
    self.mgmt_student_var = tk.StringVar()
    ttk.Entry(profile_row, textvariable=self.mgmt_student_var, width=20).pack(side='left', padx=(5, 10))
    ttk.Button(profile_row, text=_t('gui.academics.ai_detector.student_analytics_view_parts.create_student_management_view.buttons.view_profile', default="View Profile"),
              command=self.view_student_profile).pack(side='left', padx=(0, 10))
    ttk.Button(profile_row, text=_t('gui.academics.ai_detector.student_analytics_view_parts.create_student_management_view.buttons.flag_for_review', default="Flag for Review"),
              command=self.flag_student_for_review).pack(side='left', padx=(0, 10))
    ttk.Button(profile_row, text=_t('gui.academics.ai_detector.student_analytics_view_parts.create_student_management_view.buttons.view_progression', default="View Progression"),
              command=self.view_student_progression).pack(side='left')

    # Student Comparison Section
    compare_frame = ttk.LabelFrame(student_card, text=_t('gui.academics.ai_detector.student_analytics_view_parts.create_student_management_view.labels.compare_students', default="Compare Students"), padding=15)
    compare_frame.pack(fill='x', padx=15, pady=(0, 15))

    compare_row = ttk.Frame(compare_frame)
    compare_row.pack(fill='x')
    ttk.Label(compare_row, text=_t('gui.academics.ai_detector.student_analytics_view_parts.create_student_management_view.labels.student_1', default="Student 1:")).pack(side='left')
    self.compare_student1_var = tk.StringVar()
    ttk.Entry(compare_row, textvariable=self.compare_student1_var, width=15).pack(side='left', padx=(5, 10))
    ttk.Label(compare_row, text=_t('gui.academics.ai_detector.student_analytics_view_parts.create_student_management_view.labels.student_2', default="Student 2:")).pack(side='left')
    self.compare_student2_var = tk.StringVar()
    ttk.Entry(compare_row, textvariable=self.compare_student2_var, width=15).pack(side='left', padx=(5, 10))
    ttk.Button(compare_row, text=_t('gui.academics.ai_detector.student_analytics_view_parts.create_student_management_view.buttons.compare', default="Compare"),
              command=self.compare_students).pack(side='left')

    # Report Generation Section
    report_frame = ttk.LabelFrame(student_card, text=_t('gui.academics.ai_detector.student_analytics_view_parts.create_student_management_view.labels.reports', default="Reports"), padding=15)
    report_frame.pack(fill='x', padx=15, pady=(0, 15))

    report_row = ttk.Frame(report_frame)
    report_row.pack(fill='x')
    ttk.Button(report_row, text=_t('gui.academics.ai_detector.student_analytics_view_parts.create_student_management_view.buttons.generate_report_card', default="Generate Report Card"),
              command=self.generate_student_report_card).pack(side='left', padx=(0, 10))
    ttk.Button(report_row, text=_t('gui.academics.ai_detector.student_analytics_view_parts.create_student_management_view.buttons.bulk_student_analysis', default="Bulk Student Analysis"),
              command=self.bulk_student_analysis).pack(side='left')

    # Student Results Display
    results_frame = ttk.LabelFrame(student_card, text=_t('gui.academics.ai_detector.student_analytics_view_parts.create_student_management_view.labels.student_information', default="Student Information"), padding=15)
    results_frame.pack(fill='both', expand=True, padx=15, pady=(0, 15))

    self.student_results_text = scrolledtext.ScrolledText(results_frame, height=12, wrap=tk.WORD)
    self.student_results_text.pack(fill='both', expand=True)
