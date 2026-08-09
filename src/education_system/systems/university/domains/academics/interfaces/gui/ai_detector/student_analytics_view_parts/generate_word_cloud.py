"""Extracted function implementation."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import student_analytics_view_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def generate_word_cloud(self):
    """Generate word cloud from flagged vs clean submissions"""
    try:
        self.update_status("Generating word analysis...")
        self.analytics_results_text.delete('1.0', tk.END)

        conn = sqlite3.connect(DEFAULT_DB_PATH)
        try:
            cursor = conn.cursor()

            # Get flagged submissions (high AI score)
            cursor.execute('''
                SELECT text_content FROM ai_analysis_history
                WHERE ai_probability > 70 AND text_content IS NOT NULL
                LIMIT 50
            ''')
            flagged_texts = [row[0] for row in cursor.fetchall()]

            # Get clean submissions (low AI score)
            cursor.execute('''
                SELECT text_content FROM ai_analysis_history
                WHERE ai_probability < 30 AND text_content IS NOT NULL
                LIMIT 50
            ''')
            clean_texts = [row[0] for row in cursor.fetchall()]
        finally:
            conn.close()

        def get_word_freq(texts):
            words = {}
            stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
                         'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
                         'would', 'could', 'should', 'may', 'might', 'must', 'shall',
                         'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from',
                         'as', 'into', 'through', 'during', 'before', 'after', 'above',
                         'below', 'between', 'under', 'again', 'further', 'then', 'once',
                         'and', 'but', 'if', 'or', 'because', 'until', 'while', 'although',
                         'this', 'that', 'these', 'those', 'it', 'its', 'they', 'them',
                         'their', 'what', 'which', 'who', 'whom', 'whose', 'where', 'when',
                         'why', 'how', 'all', 'each', 'every', 'both', 'few', 'more',
                         'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only',
                         'own', 'same', 'so', 'than', 'too', 'very', 'can', 'just', 'also'}
            for text in texts:
                for word in text.lower().split():
                    word = ''.join(c for c in word if c.isalpha())
                    if word and len(word) > 3 and word not in stop_words:
                        words[word] = words.get(word, 0) + 1
            return sorted(words.items(), key=lambda x: -x[1])[:30]

        flagged_words = get_word_freq(flagged_texts)
        clean_words = get_word_freq(clean_texts)

        result = "Word Frequency Analysis\n"
        result += "=" * 50 + "\n\n"

        result += "Top Words in HIGH-RISK Submissions:\n"
        result += "-" * 40 + "\n"
        for word, count in flagged_words[:15]:
            result += f"  {word:<20} {count}\n"

        result += "\nTop Words in LOW-RISK Submissions:\n"
        result += "-" * 40 + "\n"
        for word, count in clean_words[:15]:
            result += f"  {word:<20} {count}\n"

        # Find unique words
        flagged_set = set(w for w, c in flagged_words)
        clean_set = set(w for w, c in clean_words)

        unique_flagged = flagged_set - clean_set
        unique_clean = clean_set - flagged_set

        result += f"\nWords unique to high-risk: {', '.join(list(unique_flagged)[:10])}\n"
        result += f"Words unique to low-risk: {', '.join(list(unique_clean)[:10])}\n"

        self.analytics_results_text.insert('1.0', result)
        self.update_status("Word analysis complete")
    except Exception as e:
        messagebox.showerror(_t('gui.academics.ai_detector.student_analytics_view_parts.generate_word_cloud.dialogs.error', default="Error"), f"Failed to generate word cloud: {str(e)}")
