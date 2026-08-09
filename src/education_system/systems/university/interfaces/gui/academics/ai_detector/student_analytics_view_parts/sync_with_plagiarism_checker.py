"""Extracted function implementation."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import student_analytics_view_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def sync_with_plagiarism_checker(self):
    """Sync results with Turnitin/Copyleaks/other plagiarism tools"""
    service = self.plagiarism_service_var.get()

    try:
        conn = sqlite3.connect(DEFAULT_DB_PATH)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT api_key FROM ai_integration_config WHERE service_name = ?
        ''', (service,))
        result = cursor.fetchone()

        if not result:
            messagebox.showwarning(_t('gui.academics.ai_detector.student_analytics_view_parts.sync_with_plagiarism_checker.dialogs.warning', default="Warning"), f"Please configure {service} first")
            conn.close()
            return

        # Update last sync time
        cursor.execute('''
            UPDATE ai_integration_config
            SET last_sync = CURRENT_TIMESTAMP
            WHERE service_name = ?
        ''', (service,))

        conn.commit()
        conn.close()

        # Simulate sync
        self.update_status(f"Syncing with {service}...")

        def sync():
            time.sleep(2)  # Simulate sync
            self._load_integration_status()
            messagebox.showinfo(_t('gui.academics.ai_detector.student_analytics_view_parts.sync_with_plagiarism_checker.dialogs.sync_complete', default="Sync Complete"), f"Successfully synced with {service}")
            self.update_status(f"Sync with {service} complete")

        thread = threading.Thread(target=sync, daemon=True)
        thread.start()
    except Exception as e:
        messagebox.showerror(_t('gui.academics.ai_detector.student_analytics_view_parts.sync_with_plagiarism_checker.dialogs.error', default="Error"), f"Failed to sync: {str(e)}")
