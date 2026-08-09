"""Extracted function implementation."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import student_analytics_view_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def detect_copy_paste_patterns(self):
    """Identify copy-paste behavior from metadata and formatting anomalies"""
    text = ""
    if hasattr(self, 'text_input'):
        text = self.text_input.get('1.0', tk.END).strip()

    if not text:
        messagebox.showwarning(_t('gui.academics.ai_detector.student_analytics_view_parts.detect_copy_paste_patterns.dialogs.warning', default="Warning"), _t('gui.academics.ai_detector.student_analytics_view_parts.detect_copy_paste_patterns.dialogs.please_enter_text_in_the_text_analysis_view_first', default="Please enter text in the Text Analysis view first"))
        return

    try:
        self.update_status("Detecting copy-paste patterns...")
        self.enhanced_results_text.delete('1.0', tk.END)

        indicators = {
            'formatting_inconsistency': 0,
            'font_hints': 0,
            'spacing_anomalies': 0,
            'style_shifts': 0,
            'citation_gaps': 0
        }

        # Check for multiple spaces (common in copy-paste)
        multiple_spaces = text.count('  ')
        indicators['spacing_anomalies'] = min(multiple_spaces / 10, 1.0)

        # Check for inconsistent line breaks
        weird_breaks = text.count('\r\n') + text.count('\n\n\n')
        indicators['formatting_inconsistency'] = min(weird_breaks / 5, 1.0)

        # Check for sudden style shifts (different sentence patterns)
        sentences = text.replace('!', '.').replace('?', '.').split('.')
        if len(sentences) > 5:
            lengths = [len(s.split()) for s in sentences if s.strip()]
            avg_length = sum(lengths) / max(len(lengths), 1)
            variance = sum((l - avg_length)**2 for l in lengths) / max(len(lengths), 1)
            if variance > 100:
                indicators['style_shifts'] = 0.7

        # Check for reference format inconsistencies
        ref_patterns = ['et al', 'pp.', 'vol.', 'retrieved from', 'accessed']
        ref_count = sum(1 for p in ref_patterns if p.lower() in text.lower())
        if ref_count > 0 and ref_count < 3:
            indicators['citation_gaps'] = 0.5

        copy_paste_score = sum(indicators.values()) / len(indicators) * 100

        result = "Copy-Paste Pattern Detection\n"
        result += "=" * 50 + "\n\n"
        result += f"Copy-Paste Probability: {copy_paste_score:.1f}%\n\n"
        result += "Detected Indicators:\n"
        result += f"  Formatting Inconsistency: {indicators['formatting_inconsistency']:.0%}\n"
        result += f"  Font/Style Hints: {indicators['font_hints']:.0%}\n"
        result += f"  Spacing Anomalies: {indicators['spacing_anomalies']:.0%}\n"
        result += f"  Style Shifts: {indicators['style_shifts']:.0%}\n"
        result += f"  Citation Gaps: {indicators['citation_gaps']:.0%}\n\n"

        if copy_paste_score > 40:
            result += "WARNING: High likelihood of copy-paste from external sources.\n"
        elif copy_paste_score > 20:
            result += "NOTICE: Some copy-paste indicators present.\n"
        else:
            result += "No significant copy-paste patterns detected.\n"

        self.enhanced_results_text.insert('1.0', result)
        self.update_status("Copy-paste detection complete")
    except Exception as e:
        messagebox.showerror(_t('gui.academics.ai_detector.student_analytics_view_parts.detect_copy_paste_patterns.dialogs.error', default="Error"), f"Failed to detect patterns: {str(e)}")
