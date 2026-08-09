"""Extracted function implementation."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import student_analytics_view_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def cluster_similar_submissions(self):
    """Use ML clustering to find suspiciously similar submissions"""
    try:
        self.update_status("Clustering submissions...")
        self.analytics_results_text.delete('1.0', tk.END)

        conn = sqlite3.connect(DEFAULT_DB_PATH)
        try:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT submission_id, student_id, student_name, text_content, ai_probability
                FROM ai_analysis_history
                WHERE text_content IS NOT NULL AND LENGTH(text_content) > 100
                ORDER BY analysis_date DESC
                LIMIT 100
            ''')
            submissions = cursor.fetchall()
        finally:
            conn.close()

        if len(submissions) < 5:
            self.analytics_results_text.insert('1.0', "Insufficient submissions for clustering.")
            return

        # Simple similarity detection based on word overlap
        def get_word_set(text):
            words = set(w.lower() for w in text.split() if len(w) > 4)
            return words

        def jaccard_similarity(set1, set2):
            intersection = len(set1 & set2)
            union = len(set1 | set2)
            return intersection / union if union > 0 else 0

        # Find similar pairs
        similar_pairs = []
        word_sets = [(s[0], s[1], s[2], get_word_set(s[3]), s[4]) for s in submissions]

        for i in range(len(word_sets)):
            for j in range(i + 1, len(word_sets)):
                sim = jaccard_similarity(word_sets[i][3], word_sets[j][3])
                if sim > 0.4:  # 40% similarity threshold
                    similar_pairs.append((
                        word_sets[i][2] or word_sets[i][1],
                        word_sets[j][2] or word_sets[j][1],
                        sim,
                        word_sets[i][4],
                        word_sets[j][4]
                    ))

        result = "Submission Clustering Analysis\n"
        result += "=" * 50 + "\n\n"
        result += f"Submissions Analyzed: {len(submissions)}\n"
        result += f"Similar Pairs Found: {len(similar_pairs)}\n\n"

        if similar_pairs:
            result += "Suspiciously Similar Submissions:\n"
            result += "-" * 50 + "\n"

            similar_pairs.sort(key=lambda x: -x[2])
            for s1, s2, sim, ai1, ai2 in similar_pairs[:20]:
                result += f"\n{s1[:20]:<20} vs {s2[:20]:<20}\n"
                result += f"  Similarity: {sim:.0%} | AI Scores: {ai1:.0f}%, {ai2:.0f}%\n"

            result += "\n" + "-" * 50 + "\n"
            result += "\nWARNING: High similarity may indicate:\n"
            result += "  - Collaboration without permission\n"
            result += "  - Shared AI-generated content\n"
            result += "  - Plagiarism\n"
        else:
            result += "No suspiciously similar submissions found.\n"

        self.analytics_results_text.insert('1.0', result)
        self.update_status("Clustering complete")
    except Exception as e:
        messagebox.showerror(_t('gui.academics.ai_detector.student_analytics_view_parts.cluster_similar_submissions.dialogs.error', default="Error"), f"Failed to cluster submissions: {str(e)}")
