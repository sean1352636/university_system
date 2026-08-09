"""Extracted function implementation."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import student_analytics_view_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def _load_draft_files(self):
    """Load draft files for comparison"""
    files = filedialog.askopenfilenames(
        title=_t('gui.academics.ai_detector.student_analytics_view_parts.load_draft_files.dialogs.select_draft_files_in_order', default="Select Draft Files (in order)"),
        filetypes=[("Text files", "*.txt"), ("Word docs", "*.docx"), ("All files", "*.*")]
    )
    if files:
        self._draft_files = list(files)
        self.draft_files_var.set(f"{len(files)} drafts loaded")
