"""Extracted function implementation."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import student_analytics_view_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def compare_draft_versions(self):
    """Compare multiple drafts to detect suspicious jumps in quality"""
    if not hasattr(self, '_draft_files') or not self._draft_files:
        messagebox.showwarning(_t('gui.academics.ai_detector.student_analytics_view_parts.compare_draft_versions.dialogs.warning', default="Warning"), _t('gui.academics.ai_detector.student_analytics_view_parts.compare_draft_versions.dialogs.please_load_draft_files_first', default="Please load draft files first"))
        return

    try:
        self.update_status("Comparing draft versions...")
        self.enhanced_results_text.delete('1.0', tk.END)

        drafts = []
        for file_path in self._draft_files:
            text = self._extract_text_from_file(file_path)
            if text:
                drafts.append({
                    'file': os.path.basename(file_path),
                    'text': text,
                    'word_count': len(text.split()),
                    'avg_word_length': sum(len(w) for w in text.split()) / max(len(text.split()), 1),
                    'unique_words': len(set(text.lower().split()))
                })

        if len(drafts) < 2:
            self.enhanced_results_text.insert('1.0', "Need at least 2 readable drafts for comparison")
            return

        result = "Draft Version Comparison\n"
        result += "=" * 50 + "\n\n"

        quality_jumps = []
        for i, draft in enumerate(drafts):
            result += f"Draft {i+1}: {draft['file']}\n"
            result += f"  Word Count: {draft['word_count']}\n"
            result += f"  Avg Word Length: {draft['avg_word_length']:.1f}\n"
            result += f"  Unique Words: {draft['unique_words']}\n\n"

            if i > 0:
                prev = drafts[i-1]
                word_jump = (draft['word_count'] - prev['word_count']) / max(prev['word_count'], 1) * 100
                vocab_jump = (draft['unique_words'] - prev['unique_words']) / max(prev['unique_words'], 1) * 100

                if word_jump > 100 or vocab_jump > 50:
                    quality_jumps.append((i, word_jump, vocab_jump))

        result += "-" * 50 + "\n"
        result += "Analysis:\n\n"

        if quality_jumps:
            result += "WARNING: Suspicious quality jumps detected!\n\n"
            for draft_num, word_jump, vocab_jump in quality_jumps:
                result += f"Between Draft {draft_num} and {draft_num+1}:\n"
                result += f"  Word count increase: {word_jump:.0f}%\n"
                result += f"  Vocabulary increase: {vocab_jump:.0f}%\n\n"
            result += "Recommend investigation - possible external assistance or AI usage.\n"
        else:
            result += "No suspicious quality jumps detected.\n"
            result += "Draft progression appears natural.\n"

        self.enhanced_results_text.insert('1.0', result)
        self.update_status("Draft comparison complete")
    except Exception as e:
        messagebox.showerror(_t('gui.academics.ai_detector.student_analytics_view_parts.compare_draft_versions.dialogs.error', default="Error"), f"Failed to compare drafts: {str(e)}")
