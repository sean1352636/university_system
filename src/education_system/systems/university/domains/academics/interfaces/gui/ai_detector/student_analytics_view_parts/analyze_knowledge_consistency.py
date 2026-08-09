"""Extracted function implementation."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import student_analytics_view_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def analyze_knowledge_consistency(self):
    """Check if demonstrated knowledge matches student's course level"""
    student_id = self.style_student_var.get().strip()
    if not student_id:
        messagebox.showwarning(_t('gui.academics.ai_detector.student_analytics_view_parts.analyze_knowledge_consistency.dialogs.warning', default="Warning"), _t('gui.academics.ai_detector.student_analytics_view_parts.analyze_knowledge_consistency.dialogs.please_enter_a_student_id', default="Please enter a student ID"))
        return

    try:
        self.update_status("Analyzing knowledge consistency...")
        self.enhanced_results_text.delete('1.0', tk.END)

        conn = sqlite3.connect(DEFAULT_DB_PATH)
        try:
            cursor = conn.cursor()

            # Get student's course enrollments
            cursor.execute('''
                SELECT DISTINCT c.course_name, c.level
                FROM enrollments e
                JOIN courses c ON e.course_id = c.id
                JOIN users u ON e.student_id = u.id
                WHERE u.username = ? OR u.id = ?
            ''', (student_id, student_id))
            courses = cursor.fetchall()

            # Get student's submissions
            cursor.execute('''
                SELECT text_content, course_name, ai_probability
                FROM ai_analysis_history
                WHERE student_id = ?
                ORDER BY analysis_date DESC
                LIMIT 5
            ''', (student_id,))
            submissions = cursor.fetchall()

        finally:
            conn.close()

        result = f"Knowledge Consistency Analysis - Student {student_id}\n"
        result += "=" * 50 + "\n\n"

        if courses:
            result += "Enrolled Courses:\n"
            for course_name, level in courses:
                result += f"  - {course_name} (Level: {level or 'N/A'})\n"
            result += "\n"
        else:
            result += "No course enrollment data found.\n\n"

        if submissions:
            result += "Recent Submissions Analysis:\n"
            result += "-" * 40 + "\n"

            for i, (text, course, ai_prob) in enumerate(submissions, 1):
                if text:
                    # Analyze vocabulary complexity
                    words = text.split()
                    unique_ratio = len(set(words)) / max(len(words), 1)
                    avg_length = sum(len(w) for w in words) / max(len(words), 1)

                    # Complex words (>3 syllables approximation)
                    complex_words = sum(1 for w in words if len(w) > 8)
                    complexity_ratio = complex_words / max(len(words), 1)

                    result += f"\nSubmission {i} ({course or 'Unknown Course'}):\n"
                    result += f"  Vocabulary Diversity: {unique_ratio:.2%}\n"
                    result += f"  Avg Word Length: {avg_length:.1f}\n"
                    result += f"  Complex Word Ratio: {complexity_ratio:.2%}\n"
                    result += f"  AI Detection Score: {ai_prob:.1f}%\n"

                    if complexity_ratio > 0.15 and ai_prob > 50:
                        result += "  WARNING: Unusually complex vocabulary with high AI score\n"

            result += "\n" + "-" * 40 + "\n"
            result += "\nConsistency Assessment:\n"
            result += "Review submissions for vocabulary beyond expected course level.\n"
        else:
            result += "No submission history found.\n"

        self.enhanced_results_text.insert('1.0', result)
        self.update_status("Knowledge consistency analysis complete")
    except Exception as e:
        messagebox.showerror(_t('gui.academics.ai_detector.student_analytics_view_parts.analyze_knowledge_consistency.dialogs.error', default="Error"), f"Failed to analyze consistency: {str(e)}")
