"""Extracted function implementation."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import student_analytics_view_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def analyze_prompt_artifacts(self):
    """Detect common ChatGPT/Claude prompt response patterns and artifacts"""
    text = ""
    if hasattr(self, 'text_input'):
        text = self.text_input.get('1.0', tk.END).strip()

    if not text:
        messagebox.showwarning(_t('gui.academics.ai_detector.student_analytics_view_parts.analyze_prompt_artifacts.dialogs.warning', default="Warning"), _t('gui.academics.ai_detector.student_analytics_view_parts.analyze_prompt_artifacts.dialogs.please_enter_text_in_the_text_analysis_view_first', default="Please enter text in the Text Analysis view first"))
        return

    try:
        self.update_status("Analyzing prompt artifacts...")
        self.enhanced_results_text.delete('1.0', tk.END)

        artifacts = {
            'greeting_patterns': 0,
            'disclaimer_phrases': 0,
            'list_formatting': 0,
            'hedging_language': 0,
            'summary_endings': 0,
            'meta_references': 0
        }

        text_lower = text.lower()

        # Check for common AI greeting patterns
        greetings = ['certainly!', 'of course!', 'great question', 'happy to help',
                    'i\'d be glad to', 'absolutely!', 'sure thing']
        artifacts['greeting_patterns'] = sum(1 for g in greetings if g in text_lower) / len(greetings)

        # Check for disclaimer phrases
        disclaimers = ['it\'s important to note', 'it should be noted', 'keep in mind',
                      'please note', 'as an ai', 'i cannot', 'i don\'t have access']
        artifacts['disclaimer_phrases'] = sum(1 for d in disclaimers if d in text_lower) / len(disclaimers)

        # Check for list formatting (common in AI outputs)
        list_indicators = text.count('1.') + text.count('2.') + text.count('- ') + text.count('* ')
        artifacts['list_formatting'] = min(list_indicators / 10, 1.0)

        # Check for hedging language
        hedging = ['generally', 'typically', 'usually', 'often', 'may', 'might',
                  'could', 'potentially', 'it depends', 'in some cases']
        hedge_count = sum(1 for h in hedging if h in text_lower)
        artifacts['hedging_language'] = min(hedge_count / 20, 1.0)

        # Check for summary endings
        endings = ['in conclusion', 'to summarize', 'in summary', 'overall',
                  'to sum up', 'in essence', 'the key takeaway']
        artifacts['summary_endings'] = sum(1 for e in endings if e in text_lower) / len(endings)

        # Check for meta-references
        meta_refs = ['this text', 'this response', 'this answer', 'as mentioned above',
                    'as discussed', 'the following']
        artifacts['meta_references'] = sum(1 for m in meta_refs if m in text_lower) / len(meta_refs)

        # Calculate overall artifact score
        artifact_score = sum(artifacts.values()) / len(artifacts) * 100

        result = "AI Prompt Artifact Analysis\n"
        result += "=" * 50 + "\n\n"
        result += f"Artifact Detection Score: {artifact_score:.1f}%\n\n"
        result += "Detected Patterns:\n"
        result += f"  Greeting Patterns: {artifacts['greeting_patterns']:.0%}\n"
        result += f"  Disclaimer Phrases: {artifacts['disclaimer_phrases']:.0%}\n"
        result += f"  List Formatting: {artifacts['list_formatting']:.0%}\n"
        result += f"  Hedging Language: {artifacts['hedging_language']:.0%}\n"
        result += f"  Summary Endings: {artifacts['summary_endings']:.0%}\n"
        result += f"  Meta-references: {artifacts['meta_references']:.0%}\n\n"

        if artifact_score > 40:
            result += "HIGH ALERT: Strong AI prompt-response patterns detected.\n"
        elif artifact_score > 20:
            result += "MODERATE: Some AI-like patterns detected.\n"
        else:
            result += "LOW: Few AI prompt artifacts detected.\n"

        self.enhanced_results_text.insert('1.0', result)
        self.update_status("Prompt artifact analysis complete")
    except Exception as e:
        messagebox.showerror(_t('gui.academics.ai_detector.student_analytics_view_parts.analyze_prompt_artifacts.dialogs.error', default="Error"), f"Failed to analyze artifacts: {str(e)}")
