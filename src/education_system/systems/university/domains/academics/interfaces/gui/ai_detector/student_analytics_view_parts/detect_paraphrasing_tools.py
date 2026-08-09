"""Extracted function implementation."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import student_analytics_view_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def detect_paraphrasing_tools(self):
    """Specifically detect content processed through Quillbot, Spinbot, etc."""
    text = ""
    if hasattr(self, 'text_input'):
        text = self.text_input.get('1.0', tk.END).strip()

    if not text:
        messagebox.showwarning(_t('gui.academics.ai_detector.student_analytics_view_parts.detect_paraphrasing_tools.dialogs.warning', default="Warning"), _t('gui.academics.ai_detector.student_analytics_view_parts.detect_paraphrasing_tools.dialogs.please_enter_text_in_the_text_analysis_view_first', default="Please enter text in the Text Analysis view first"))
        return

    try:
        self.update_status("Detecting paraphrasing patterns...")
        self.enhanced_results_text.delete('1.0', tk.END)

        # Paraphrasing tool indicators
        indicators = {
            'unusual_synonyms': 0,
            'awkward_phrasing': 0,
            'inconsistent_formality': 0,
            'over_complex_vocabulary': 0,
            'repetitive_structure': 0
        }

        # Common paraphrasing artifacts
        paraphrase_markers = [
            'in addition to this', 'furthermore', 'moreover', 'consequently',
            'nevertheless', 'notwithstanding', 'henceforth', 'whereby'
        ]

        words = text.lower().split()
        sentences = text.replace('!', '.').replace('?', '.').split('.')

        # Check for over-use of transition words (common in paraphrasing tools)
        transition_count = sum(1 for marker in paraphrase_markers if marker in text.lower())
        indicators['unusual_synonyms'] = min(transition_count / max(len(sentences), 1), 1.0)

        # Check for sentence structure repetition
        structures = []
        for sent in sentences:
            sent = sent.strip()
            if sent:
                structure = len(sent.split())
                structures.append(structure)

        if len(structures) > 3:
            variance = sum((s - sum(structures)/len(structures))**2 for s in structures) / len(structures)
            if variance < 5:
                indicators['repetitive_structure'] = 0.7

        # Calculate overall paraphrasing probability
        paraphrase_score = sum(indicators.values()) / len(indicators) * 100

        result = "Paraphrasing Tool Detection Results\n"
        result += "=" * 50 + "\n\n"
        result += f"Paraphrasing Probability: {paraphrase_score:.1f}%\n\n"
        result += "Indicators:\n"
        result += f"  Unusual Synonym Usage: {indicators['unusual_synonyms']:.0%}\n"
        result += f"  Awkward Phrasing: {indicators['awkward_phrasing']:.0%}\n"
        result += f"  Inconsistent Formality: {indicators['inconsistent_formality']:.0%}\n"
        result += f"  Over-complex Vocabulary: {indicators['over_complex_vocabulary']:.0%}\n"
        result += f"  Repetitive Structure: {indicators['repetitive_structure']:.0%}\n\n"

        if paraphrase_score > 50:
            result += "WARNING: High likelihood of paraphrasing tool usage detected.\n"
            result += "Recommend manual review of the submission.\n"
        elif paraphrase_score > 25:
            result += "NOTICE: Some indicators of paraphrasing detected.\n"
        else:
            result += "No significant paraphrasing tool indicators found.\n"

        self.enhanced_results_text.insert('1.0', result)
        self.update_status("Paraphrasing detection complete")
    except Exception as e:
        messagebox.showerror(_t('gui.academics.ai_detector.student_analytics_view_parts.detect_paraphrasing_tools.dialogs.error', default="Error"), f"Failed to detect paraphrasing: {str(e)}")
