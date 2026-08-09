"""Extracted function implementation."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import student_analytics_view_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def bulk_student_analysis(self):
    """Analyze all submissions from a class/cohort at once"""
    # Ask for course/cohort selection
    course = simpledialog.askstring(_t('gui.academics.ai_detector.student_analytics_view_parts.bulk_student_analysis.dialogs.bulk_analysis', default="Bulk Analysis"),
                                    _t('gui.academics.ai_detector.student_analytics_view_parts.bulk_student_analysis.dialogs.enter_course_name_or_id_to_analyze', default="Enter course name or ID to analyze:"),
                                    parent=self.root)
    if not course:
        return

    try:
        self.update_status("Running bulk analysis...")
        self.student_results_text.delete('1.0', tk.END)

        conn = sqlite3.connect(DEFAULT_DB_PATH)
        try:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT student_id, student_name, COUNT(*) as submissions,
                       AVG(ai_probability) as avg_score,
                       MAX(ai_probability) as max_score,
                       SUM(CASE WHEN ai_probability > 80 THEN 1 ELSE 0 END) as high_risk
                FROM ai_analysis_history
                WHERE course_name LIKE ?
                GROUP BY student_id
                ORDER BY avg_score DESC
            ''', (f'%{course}%',))
            students = cursor.fetchall()
        finally:
            conn.close()

        result = f"Bulk Analysis - {course}\n"
        result += "=" * 50 + "\n\n"

        if not students:
            result += "No submissions found for this course.\n"
            self.student_results_text.insert('1.0', result)
            return

        result += f"Total Students: {len(students)}\n\n"
        result += f"{'Student':<20} {'Subs':<6} {'Avg':<8} {'Max':<8} {'High Risk':<10}\n"
        result += "-" * 60 + "\n"

        high_risk_students = []
        for student_id, name, subs, avg, max_score, high_risk in students:
            display_name = (name or student_id)[:18]
            result += f"{display_name:<20} {subs:<6} {avg:>5.1f}%  {max_score:>5.1f}%  {high_risk:<10}\n"

            if avg > 60 or high_risk > 0:
                high_risk_students.append(name or student_id)

        result += "\n" + "-" * 60 + "\n"
        result += f"High-Risk Students: {len(high_risk_students)}\n"
        if high_risk_students:
            result += "Students requiring review:\n"
            for s in high_risk_students[:10]:
                result += f"  - {s}\n"

        self.student_results_text.insert('1.0', result)
        self.update_status("Bulk analysis complete")
    except Exception as e:
        messagebox.showerror(_t('gui.academics.ai_detector.student_analytics_view_parts.bulk_student_analysis.dialogs.error', default="Error"), f"Failed to run bulk analysis: {str(e)}")
