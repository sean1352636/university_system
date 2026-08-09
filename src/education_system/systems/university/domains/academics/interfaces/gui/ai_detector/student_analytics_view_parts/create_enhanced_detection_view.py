"""Extracted function implementation."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import student_analytics_view_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def create_enhanced_detection_view(self, parent):
    """Create enhanced detection analysis view"""
    detection_frame = ttk.Frame(parent)
    detection_frame.pack(fill="both", expand=True)

    # Main card
    detection_card = ttk.Frame(detection_frame, style='Card.TFrame')
    detection_card.pack(fill='both', expand=True, padx=10, pady=10)

    ttk.Label(detection_card, text=_t('gui.academics.ai_detector.student_analytics_view_parts.create_enhanced_detection_view.labels.enhanced_detection_analysis', default="Enhanced Detection Analysis"), style='Title.TLabel').pack(anchor='w', padx=15, pady=15)

    # Writing Style Analysis Section
    style_frame = ttk.LabelFrame(detection_card, text=_t('gui.academics.ai_detector.student_analytics_view_parts.create_enhanced_detection_view.labels.writing_style_analysis', default="Writing Style Analysis"), padding=15)
    style_frame.pack(fill='x', padx=15, pady=(0, 15))

    style_row = ttk.Frame(style_frame)
    style_row.pack(fill='x', pady=2)
    ttk.Label(style_row, text=_t('gui.academics.ai_detector.student_analytics_view_parts.create_enhanced_detection_view.labels.student_id', default="Student ID:")).pack(side='left')
    self.style_student_var = tk.StringVar()
    ttk.Entry(style_row, textvariable=self.style_student_var, width=20).pack(side='left', padx=(5, 10))
    ttk.Button(style_row, text=_t('gui.academics.ai_detector.student_analytics_view_parts.create_enhanced_detection_view.buttons.create_writing_fingerprint', default="Create Writing Fingerprint"),
              command=self.analyze_writing_style_fingerprint).pack(side='left', padx=(0, 10))
    ttk.Button(style_row, text=_t('gui.academics.ai_detector.student_analytics_view_parts.create_enhanced_detection_view.buttons.analyze_knowledge_consistency', default="Analyze Knowledge Consistency"),
              command=self.analyze_knowledge_consistency).pack(side='left')

    # Paraphrasing & AI Detection Section
    para_frame = ttk.LabelFrame(detection_card, text=_t('gui.academics.ai_detector.student_analytics_view_parts.create_enhanced_detection_view.labels.paraphrasing_ai_artifact_detection', default="Paraphrasing & AI Artifact Detection"), padding=15)
    para_frame.pack(fill='x', padx=15, pady=(0, 15))

    para_buttons = ttk.Frame(para_frame)
    para_buttons.pack(fill='x')
    ttk.Button(para_buttons, text=_t('gui.academics.ai_detector.student_analytics_view_parts.create_enhanced_detection_view.buttons.detect_paraphrasing_tools', default="Detect Paraphrasing Tools"),
              command=self.detect_paraphrasing_tools).pack(side='left', padx=(0, 10))
    ttk.Button(para_buttons, text=_t('gui.academics.ai_detector.student_analytics_view_parts.create_enhanced_detection_view.buttons.analyze_prompt_artifacts', default="Analyze Prompt Artifacts"),
              command=self.analyze_prompt_artifacts).pack(side='left', padx=(0, 10))
    ttk.Button(para_buttons, text=_t('gui.academics.ai_detector.student_analytics_view_parts.create_enhanced_detection_view.buttons.detect_translation_artifacts', default="Detect Translation Artifacts"),
              command=self.detect_translation_artifacts).pack(side='left')

    # Draft Comparison Section
    draft_frame = ttk.LabelFrame(detection_card, text=_t('gui.academics.ai_detector.student_analytics_view_parts.create_enhanced_detection_view.labels.draft_version_analysis', default="Draft & Version Analysis"), padding=15)
    draft_frame.pack(fill='x', padx=15, pady=(0, 15))

    ttk.Label(draft_frame, text=_t('gui.academics.ai_detector.student_analytics_view_parts.create_enhanced_detection_view.labels.upload_multiple_draft_versions_to_compare_quality_progression', default="Upload multiple draft versions to compare quality progression:")).pack(anchor='w')
    draft_buttons = ttk.Frame(draft_frame)
    draft_buttons.pack(fill='x', pady=(10, 0))
    ttk.Button(draft_buttons, text=_t('gui.academics.ai_detector.student_analytics_view_parts.create_enhanced_detection_view.buttons.load_draft_files', default="Load Draft Files"),
              command=self._load_draft_files).pack(side='left', padx=(0, 10))
    ttk.Button(draft_buttons, text=_t('gui.academics.ai_detector.student_analytics_view_parts.create_enhanced_detection_view.buttons.compare_draft_versions', default="Compare Draft Versions"),
              command=self.compare_draft_versions).pack(side='left')

    self.draft_files_var = tk.StringVar(value=_t('gui.academics.ai_detector.student_analytics_view_parts.create_enhanced_detection_view.values.no_drafts_loaded', default="No drafts loaded"))
    ttk.Label(draft_frame, textvariable=self.draft_files_var,
             foreground=self.colors['text_secondary']).pack(anchor='w', pady=(5, 0))

    # Copy-Paste & Reference Section
    copy_frame = ttk.LabelFrame(detection_card, text=_t('gui.academics.ai_detector.student_analytics_view_parts.create_enhanced_detection_view.labels.copy_paste_reference_analysis', default="Copy-Paste & Reference Analysis"), padding=15)
    copy_frame.pack(fill='x', padx=15, pady=(0, 15))

    copy_buttons = ttk.Frame(copy_frame)
    copy_buttons.pack(fill='x')
    ttk.Button(copy_buttons, text=_t('gui.academics.ai_detector.student_analytics_view_parts.create_enhanced_detection_view.buttons.detect_copy_paste_patterns', default="Detect Copy-Paste Patterns"),
              command=self.detect_copy_paste_patterns).pack(side='left', padx=(0, 10))
    ttk.Button(copy_buttons, text=_t('gui.academics.ai_detector.student_analytics_view_parts.create_enhanced_detection_view.buttons.verify_reference_authenticity', default="Verify Reference Authenticity"),
              command=self.analyze_reference_authenticity).pack(side='left')

    # Results Display
    results_frame = ttk.LabelFrame(detection_card, text=_t('gui.academics.ai_detector.student_analytics_view_parts.create_enhanced_detection_view.labels.analysis_results', default="Analysis Results"), padding=15)
    results_frame.pack(fill='both', expand=True, padx=15, pady=(0, 15))

    self.enhanced_results_text = scrolledtext.ScrolledText(results_frame, height=10, wrap=tk.WORD)
    self.enhanced_results_text.pack(fill='both', expand=True)
