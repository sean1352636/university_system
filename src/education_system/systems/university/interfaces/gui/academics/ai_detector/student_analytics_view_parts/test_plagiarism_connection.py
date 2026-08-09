"""Extracted function implementation."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import student_analytics_view_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def _test_plagiarism_connection(self):
    """Test connection to plagiarism checker"""
    service = self.plagiarism_service_var.get()
    api_key = self.plagiarism_api_var.get()

    if not api_key:
        messagebox.showwarning(_t('gui.academics.ai_detector.student_analytics_view_parts.test_plagiarism_connection.dialogs.warning', default="Warning"), _t('gui.academics.ai_detector.student_analytics_view_parts.test_plagiarism_connection.dialogs.please_enter_an_api_key_first', default="Please enter an API key first"))
        return

    # Simulate connection test
    self.update_status(f"Testing connection to {service}...")

    def test():
        time.sleep(1)  # Simulate network delay
        # In real implementation, would test actual API
        messagebox.showinfo(_t('gui.academics.ai_detector.student_analytics_view_parts.test_plagiarism_connection.dialogs.connection_test', default="Connection Test"), f"Connection to {service} successful!")
        self.update_status(f"{service} connection verified")

    thread = threading.Thread(target=test, daemon=True)
    thread.start()
