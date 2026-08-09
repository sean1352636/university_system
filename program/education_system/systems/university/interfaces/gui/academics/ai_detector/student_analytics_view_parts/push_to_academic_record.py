"""Extracted function implementation."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import student_analytics_view_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def push_to_academic_record(self):
    """Push confirmed violations to student academic record system"""
    submission_id = self.push_submission_var.get().strip()
    if not submission_id:
        messagebox.showwarning(_t('gui.academics.ai_detector.student_analytics_view_parts.push_to_academic_record.dialogs.warning', default="Warning"), _t('gui.academics.ai_detector.student_analytics_view_parts.push_to_academic_record.dialogs.please_enter_a_submission_id', default="Please enter a submission ID"))
        return

    system = self.academic_system_var.get()

    if not messagebox.askyesno(_t('gui.academics.ai_detector.student_analytics_view_parts.push_to_academic_record.dialogs.confirm_push', default="Confirm Push"),
                               f"This will push the violation record for submission {submission_id} "
                               f"to the {system} academic record system.\n\n"
                               "This action will create a permanent record. Continue?"):
        return

    try:
        conn = sqlite3.connect(DEFAULT_DB_PATH)
        cursor = conn.cursor()

        # Get submission details
        cursor.execute('''
            SELECT student_id, student_name, ai_probability, analysis_date
            FROM ai_analysis_history WHERE submission_id = ?
        ''', (submission_id,))
        submission = cursor.fetchone()

        if not submission:
            messagebox.showerror(_t('gui.academics.ai_detector.student_analytics_view_parts.push_to_academic_record.dialogs.error', default="Error"), _t('gui.academics.ai_detector.student_analytics_view_parts.push_to_academic_record.dialogs.submission_not_found', default="Submission not found"))
            conn.close()
            return

        # Create violation record
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ai_violation_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                submission_id TEXT,
                student_id TEXT,
                student_name TEXT,
                ai_score REAL,
                pushed_to TEXT,
                pushed_by TEXT,
                pushed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            INSERT INTO ai_violation_records (submission_id, student_id, student_name, ai_score, pushed_to, pushed_by)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            submission_id,
            submission[0],
            submission[1],
            submission[2],
            system,
            self.auth.current_user.get('username', 'Unknown') if self.auth and self.auth.current_user else 'Unknown'
        ))

        # Log activity
        cursor.execute('''
            INSERT INTO ai_activity_log (username, action, details)
            VALUES (?, 'push_violation', ?)
        ''', (
            self.auth.current_user.get('username', 'Unknown') if self.auth and self.auth.current_user else 'Unknown',
            f'Pushed violation for submission {submission_id} to {system}'
        ))

        conn.commit()
        conn.close()

        messagebox.showinfo(_t('gui.academics.ai_detector.student_analytics_view_parts.push_to_academic_record.dialogs.success', default="Success"),
                          f"Violation record pushed to {system}\n\n"
                          f"Student: {submission[1]}\n"
                          f"AI Score: {submission[2]:.1f}%")
        self.update_status(f"Violation pushed to {system}")
    except Exception as e:
        messagebox.showerror(_t('gui.academics.ai_detector.student_analytics_view_parts.push_to_academic_record.dialogs.error', default="Error"), f"Failed to push record: {str(e)}")
