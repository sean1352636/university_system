"""Extracted function implementation."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import student_analytics_view_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def compare_students(self):
    """Side-by-side comparison of two students' writing patterns"""
    student1 = self.compare_student1_var.get().strip()
    student2 = self.compare_student2_var.get().strip()

    if not student1 or not student2:
        messagebox.showwarning(_t('gui.academics.ai_detector.student_analytics_view_parts.compare_students.dialogs.warning', default="Warning"), _t('gui.academics.ai_detector.student_analytics_view_parts.compare_students.dialogs.please_enter_both_student_ids', default="Please enter both student IDs"))
        return

    try:
        self.update_status("Comparing students...")
        self.student_results_text.delete('1.0', tk.END)

        conn = sqlite3.connect(DEFAULT_DB_PATH)
        try:
            cursor = conn.cursor()

            comparisons = {}
            for student_id in [student1, student2]:
                cursor.execute('''
                    SELECT COUNT(*), AVG(ai_probability),
                           AVG(LENGTH(text_content))
                    FROM ai_analysis_history
                    WHERE student_id = ?
                ''', (student_id,))
                stats = cursor.fetchone()

                # Get writing fingerprint if exists
                cursor.execute('''
                    SELECT fingerprint_data FROM ai_writing_fingerprints
                    WHERE student_id = ?
                ''', (student_id,))
                fingerprint = cursor.fetchone()

                comparisons[student_id] = {
                    'submissions': stats[0] if stats else 0,
                    'avg_ai_score': stats[1] if stats and stats[1] else 0,
                    'avg_length': stats[2] if stats and stats[2] else 0,
                    'fingerprint': json.loads(fingerprint[0]) if fingerprint else None
                }

        finally:
            conn.close()

        result = "Student Comparison\n"
        result += "=" * 50 + "\n\n"

        result += f"{'Metric':<30} {'Student 1':<15} {'Student 2':<15}\n"
        result += "-" * 60 + "\n"

        c1, c2 = comparisons[student1], comparisons[student2]

        result += f"{'Total Submissions':<30} {c1['submissions']:<15} {c2['submissions']:<15}\n"
        result += f"{'Avg AI Score':<30} {c1['avg_ai_score']:.1f}%{'':<10} {c2['avg_ai_score']:.1f}%\n"
        result += f"{'Avg Text Length':<30} {c1['avg_length']:.0f}{'':<10} {c2['avg_length']:.0f}\n"

        if c1['fingerprint'] and c2['fingerprint']:
            f1, f2 = c1['fingerprint'], c2['fingerprint']
            result += "\nWriting Style Comparison:\n"
            result += "-" * 40 + "\n"
            result += f"{'Avg Sentence Length':<30} {f1.get('avg_sentence_length', 0):.1f}{'':<10} {f2.get('avg_sentence_length', 0):.1f}\n"
            result += f"{'Vocabulary Richness':<30} {f1.get('vocabulary_richness', 0):.2%}{'':<6} {f2.get('vocabulary_richness', 0):.2%}\n"

            # Calculate similarity
            similarity = 0
            if f1.get('avg_sentence_length') and f2.get('avg_sentence_length'):
                diff = abs(f1['avg_sentence_length'] - f2['avg_sentence_length'])
                similarity += max(0, 1 - diff/20) * 50

            if f1.get('vocabulary_richness') and f2.get('vocabulary_richness'):
                diff = abs(f1['vocabulary_richness'] - f2['vocabulary_richness'])
                similarity += max(0, 1 - diff) * 50

            result += f"\nWriting Style Similarity: {similarity:.0f}%\n"
            if similarity > 80:
                result += "WARNING: Very similar writing styles detected!\n"

        self.student_results_text.insert('1.0', result)
        self.update_status("Comparison complete")
    except Exception as e:
        messagebox.showerror(_t('gui.academics.ai_detector.student_analytics_view_parts.compare_students.dialogs.error', default="Error"), f"Failed to compare students: {str(e)}")
