"""Extracted function implementation."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import student_analytics_view_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def _save_plagiarism_config(self):
    """Save plagiarism checker configuration"""
    try:
        service = self.plagiarism_service_var.get()
        api_key = self.plagiarism_api_var.get()

        if not api_key:
            messagebox.showwarning(_t('gui.academics.ai_detector.student_analytics_view_parts.save_plagiarism_config.dialogs.warning', default="Warning"), _t('gui.academics.ai_detector.student_analytics_view_parts.save_plagiarism_config.dialogs.please_enter_an_api_key', default="Please enter an API key"))
            return

        conn = sqlite3.connect(DEFAULT_DB_PATH)
        try:
            cursor = conn.cursor()

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ai_integration_config (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    service_name TEXT UNIQUE,
                    api_key TEXT,
                    enabled INTEGER DEFAULT 1,
                    last_sync TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            cursor.execute('''
                INSERT OR REPLACE INTO ai_integration_config (service_name, api_key, enabled)
                VALUES (?, ?, 1)
            ''', (service, api_key))

            conn.commit()
        finally:
            conn.close()

        messagebox.showinfo(_t('gui.academics.ai_detector.student_analytics_view_parts.save_plagiarism_config.dialogs.success', default="Success"), f"{service} configuration saved")
        self._load_integration_status()
        self.update_status(f"{service} configured")
    except Exception as e:
        messagebox.showerror(_t('gui.academics.ai_detector.student_analytics_view_parts.save_plagiarism_config.dialogs.error', default="Error"), f"Failed to save configuration: {str(e)}")
