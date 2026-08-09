"""Extracted function implementation."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import student_analytics_view_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def flag_student_for_review(self):
    """Manually flag student for academic integrity review"""
    student_id = self.mgmt_student_var.get().strip()
    if not student_id:
        messagebox.showwarning(_t('gui.academics.ai_detector.student_analytics_view_parts.flag_student_for_review.dialogs.warning', default="Warning"), _t('gui.academics.ai_detector.student_analytics_view_parts.flag_student_for_review.dialogs.please_enter_a_student_id', default="Please enter a student ID"))
        return

    # Get flag reason
    reason = simpledialog.askstring(_t('gui.academics.ai_detector.student_analytics_view_parts.flag_student_for_review.dialogs.flag_student', default="Flag Student"),
                                    _t('gui.academics.ai_detector.student_analytics_view_parts.flag_student_for_review.dialogs.enter_reason_for_flagging_this_student', default="Enter reason for flagging this student:"),
                                    parent=self.root)
    if not reason:
        return

    try:
        conn = sqlite3.connect(DEFAULT_DB_PATH)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ai_student_flags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                flag_reason TEXT,
                flagged_by TEXT,
                flagged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'active',
                resolved_at TIMESTAMP,
                resolution_notes TEXT
            )
        ''')

        flagged_by = "Unknown"
        if self.auth and hasattr(self.auth, 'current_user') and self.auth.current_user:
            flagged_by = self.auth.current_user.get('username', 'Unknown')

        cursor.execute('''
            INSERT INTO ai_student_flags (student_id, flag_reason, flagged_by)
            VALUES (?, ?, ?)
        ''', (student_id, reason, flagged_by))

        conn.commit()
        conn.close()

        messagebox.showinfo(_t('gui.academics.ai_detector.student_analytics_view_parts.flag_student_for_review.dialogs.success', default="Success"), f"Student {student_id} flagged for review.")
        self.update_status(f"Student {student_id} flagged")
    except Exception as e:
        messagebox.showerror(_t('gui.academics.ai_detector.student_analytics_view_parts.flag_student_for_review.dialogs.error', default="Error"), f"Failed to flag student: {str(e)}")
