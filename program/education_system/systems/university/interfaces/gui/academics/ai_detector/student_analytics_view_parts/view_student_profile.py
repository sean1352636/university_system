"""Extracted function implementation."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import student_analytics_view_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def view_student_profile(self):
    """Comprehensive view of student's submission history, risk level, and patterns"""
    student_id = self.mgmt_student_var.get().strip()
    if not student_id:
        messagebox.showwarning(_t('gui.academics.ai_detector.student_analytics_view_parts.view_student_profile.dialogs.warning', default="Warning"), _t('gui.academics.ai_detector.student_analytics_view_parts.view_student_profile.dialogs.please_enter_a_student_id', default="Please enter a student ID"))
        return

    try:
        self.update_status("Loading student profile...")
        self.student_results_text.delete('1.0', tk.END)

        conn = sqlite3.connect(DEFAULT_DB_PATH)
        try:
            cursor = conn.cursor()

            # Get student info
            cursor.execute('''
                SELECT username, first_name, last_name, email
                FROM users WHERE username = ? OR id = ?
            ''', (student_id, student_id))
            student = cursor.fetchone()

            # Get submission history
            cursor.execute('''
                SELECT COUNT(*), AVG(ai_probability),
                       MAX(ai_probability), MIN(ai_probability),
                       SUM(CASE WHEN ai_probability > 80 THEN 1 ELSE 0 END)
                FROM ai_analysis_history
                WHERE student_id = ?
            ''', (student_id,))
            stats = cursor.fetchone()

            # Get recent submissions
            cursor.execute('''
                SELECT submission_id, course_name, ai_probability, analysis_date
                FROM ai_analysis_history
                WHERE student_id = ?
                ORDER BY analysis_date DESC
                LIMIT 10
            ''', (student_id,))
            recent = cursor.fetchall()

            # Get any flags
            cursor.execute('''
                SELECT flag_reason, flagged_by, flagged_at
                FROM ai_student_flags
                WHERE student_id = ?
                ORDER BY flagged_at DESC
            ''', (student_id,))
            flags = cursor.fetchall()

        finally:
            conn.close()

        result = f"Student Profile: {student_id}\n"
        result += "=" * 50 + "\n\n"

        if student:
            result += f"Name: {student[1] or ''} {student[2] or ''}\n"
            result += f"Username: {student[0]}\n"
            result += f"Email: {student[3] or 'N/A'}\n\n"

        if stats and stats[0]:
            total, avg, max_score, min_score, high_risk = stats
            result += "Submission Statistics:\n"
            result += "-" * 40 + "\n"
            result += f"Total Submissions: {total}\n"
            result += f"Average AI Score: {avg:.1f}%\n"
            result += f"Highest Score: {max_score:.1f}%\n"
            result += f"Lowest Score: {min_score:.1f}%\n"
            result += f"High-Risk Submissions: {high_risk}\n"

            # Risk level assessment
            if high_risk / max(total, 1) > 0.5:
                risk_level = "HIGH"
            elif high_risk / max(total, 1) > 0.2:
                risk_level = "MEDIUM"
            else:
                risk_level = "LOW"
            result += f"\nOverall Risk Level: {risk_level}\n"
        else:
            result += "No submission history found.\n"

        if flags:
            result += "\n" + "-" * 40 + "\n"
            result += "Active Flags:\n"
            for reason, flagged_by, flagged_at in flags:
                result += f"  - {reason} (by {flagged_by}, {flagged_at})\n"

        if recent:
            result += "\n" + "-" * 40 + "\n"
            result += "Recent Submissions:\n"
            for sub_id, doc_name, ai_prob, date in recent:
                result += f"  {date}: {doc_name or sub_id} - {ai_prob:.1f}%\n"

        self.student_results_text.insert('1.0', result)
        self.update_status("Profile loaded")
    except Exception as e:
        messagebox.showerror(_t('gui.academics.ai_detector.student_analytics_view_parts.view_student_profile.dialogs.error', default="Error"), f"Failed to load profile: {str(e)}")
