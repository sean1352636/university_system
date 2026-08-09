"""Extracted function implementation."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import student_analytics_view_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def view_student_progression(self):
    """Track how student's writing has evolved over time"""
    student_id = self.mgmt_student_var.get().strip()
    if not student_id:
        messagebox.showwarning(_t('gui.academics.ai_detector.student_analytics_view_parts.view_student_progression.dialogs.warning', default="Warning"), _t('gui.academics.ai_detector.student_analytics_view_parts.view_student_progression.dialogs.please_enter_a_student_id', default="Please enter a student ID"))
        return

    try:
        self.update_status("Loading progression data...")
        self.student_results_text.delete('1.0', tk.END)

        conn = sqlite3.connect(DEFAULT_DB_PATH)
        try:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT analysis_date, ai_probability, document_name,
                       LENGTH(text_content) as length
                FROM ai_analysis_history
                WHERE student_id = ?
                ORDER BY analysis_date
            ''', (student_id,))
            submissions = cursor.fetchall()
        finally:
            conn.close()

        result = f"Writing Progression - Student {student_id}\n"
        result += "=" * 50 + "\n\n"

        if not submissions:
            result += "No submission history found.\n"
            self.student_results_text.insert('1.0', result)
            return

        result += f"{'Date':<12} {'AI Score':<10} {'Length':<10} Document\n"
        result += "-" * 60 + "\n"

        scores = []
        for date, ai_prob, doc_name, length in submissions:
            scores.append(ai_prob)
            date_str = date[:10] if date else "N/A"
            result += f"{date_str:<12} {ai_prob:>6.1f}%   {length or 0:>8}   {doc_name or 'Untitled'}\n"

        result += "\n" + "-" * 60 + "\n"
        result += "Trend Analysis:\n\n"

        if len(scores) >= 3:
            # Calculate trend
            first_half = sum(scores[:len(scores)//2]) / (len(scores)//2)
            second_half = sum(scores[len(scores)//2:]) / (len(scores) - len(scores)//2)
            trend = second_half - first_half

            if trend > 10:
                result += "CONCERNING: AI detection scores are INCREASING over time.\n"
                result += f"Average increase: {trend:.1f}%\n"
            elif trend < -10:
                result += "POSITIVE: AI detection scores are DECREASING over time.\n"
                result += f"Average decrease: {abs(trend):.1f}%\n"
            else:
                result += "STABLE: AI detection scores remain relatively consistent.\n"

            # Detect sudden changes
            for i in range(1, len(scores)):
                if abs(scores[i] - scores[i-1]) > 30:
                    result += f"\nALERT: Sudden change detected between submissions {i} and {i+1}\n"
        else:
            result += "Not enough submissions for trend analysis.\n"

        self.student_results_text.insert('1.0', result)
        self.update_status("Progression loaded")
    except Exception as e:
        messagebox.showerror(_t('gui.academics.ai_detector.student_analytics_view_parts.view_student_progression.dialogs.error', default="Error"), f"Failed to load progression: {str(e)}")
