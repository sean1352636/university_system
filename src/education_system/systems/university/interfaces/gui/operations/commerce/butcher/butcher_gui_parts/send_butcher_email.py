"""Extracted function implementation."""

from .. import butcher_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def _send_butcher_email(recipient: str, subject: str, body: str, show_success: bool = False) -> bool:
    """Helper function to send emails with proper error handling and logging."""
    if not EMAIL_AVAILABLE:
        print(f"[Butcher] Email service not available - would send to {recipient}: {subject}")
        return False
    if not recipient:
        print(f"[Butcher] No recipient email provided for: {subject}")
        return False
    try:
        result = send_email(recipient, subject, body)
        if result:
            log_activity('email_sent', 'butcher', details={'to': recipient, 'subject': subject})
            print(f"[Butcher] Email sent successfully to {recipient}: {subject}")
            return True
        else:
            print(f"[Butcher] Email send returned False for {recipient}: {subject}")
            return False
    except Exception as e:
        print(f"[Butcher] Email send error for {recipient}: {e}")
        log_activity('email_failed', 'butcher', details={'to': recipient, 'subject': subject, 'error': str(e)})
        return False
