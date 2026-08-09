"""Extracted function implementation."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import student_analytics_view_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def detect_translation_artifacts(self):
    """Identify text that was written in another language and translated"""
    text = ""
    if hasattr(self, 'text_input'):
        text = self.text_input.get('1.0', tk.END).strip()

    if not text:
        messagebox.showwarning(_t('gui.academics.ai_detector.student_analytics_view_parts.detect_translation_artifacts.dialogs.warning', default="Warning"), _t('gui.academics.ai_detector.student_analytics_view_parts.detect_translation_artifacts.dialogs.please_enter_text_in_the_text_analysis_view_first', default="Please enter text in the Text Analysis view first"))
        return

    try:
        self.update_status("Detecting translation artifacts...")
        self.enhanced_results_text.delete('1.0', tk.END)

        indicators = {
            'word_order_anomalies': 0,
            'article_misuse': 0,
            'preposition_errors': 0,
            'literal_translations': 0,
            'cultural_markers': 0
        }

        text_lower = text.lower()
        words = text_lower.split()

        # Check for missing/incorrect articles
        article_patterns = ['the the', 'a a', 'an an']
        for pattern in article_patterns:
            if pattern in text_lower:
                indicators['article_misuse'] += 0.3

        # Check for literal translation markers
        literal_markers = ['it makes that', 'it gives that', 'to have hunger',
                          'to have cold', 'to make attention', 'it rains cats and dogs']
        for marker in literal_markers:
            if marker in text_lower:
                indicators['literal_translations'] += 0.2

        # Check for unusual preposition usage
        prep_issues = ['in the morning of', 'by foot', 'in the bus', 'on the phone to']
        for issue in prep_issues:
            if issue in text_lower:
                indicators['preposition_errors'] += 0.2

        # Check sentence structure anomalies (e.g., adjective placement)
        sentences = text.split('.')
        for sent in sentences:
            words_in_sent = sent.split()
            # Check for adjective after noun patterns (common in Romance languages)
            for i in range(len(words_in_sent) - 1):
                if words_in_sent[i].endswith('tion') and words_in_sent[i+1] in ['beautiful', 'important', 'big']:
                    indicators['word_order_anomalies'] += 0.1

        # Calculate translation probability
        translation_score = min(sum(indicators.values()) / len(indicators) * 100, 100)

        result = "Translation Artifact Detection\n"
        result += "=" * 50 + "\n\n"
        result += f"Translation Probability: {translation_score:.1f}%\n\n"
        result += "Detected Indicators:\n"
        result += f"  Word Order Anomalies: {indicators['word_order_anomalies']:.0%}\n"
        result += f"  Article Misuse: {indicators['article_misuse']:.0%}\n"
        result += f"  Preposition Errors: {indicators['preposition_errors']:.0%}\n"
        result += f"  Literal Translations: {indicators['literal_translations']:.0%}\n"
        result += f"  Cultural Markers: {indicators['cultural_markers']:.0%}\n\n"

        if translation_score > 30:
            result += "NOTICE: Text may have been translated from another language.\n"
        else:
            result += "No significant translation artifacts detected.\n"

        self.enhanced_results_text.insert('1.0', result)
        self.update_status("Translation detection complete")
    except Exception as e:
        messagebox.showerror(_t('gui.academics.ai_detector.student_analytics_view_parts.detect_translation_artifacts.dialogs.error', default="Error"), f"Failed to detect translation: {str(e)}")
