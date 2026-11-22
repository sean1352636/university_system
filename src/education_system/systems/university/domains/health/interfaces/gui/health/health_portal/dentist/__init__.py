
import tkinter as tk
from tkinter import ttk
from education_system.systems.university.domains.health.interfaces.gui.health._dialogs import messagebox, simpledialog
from datetime import datetime
from typing import Optional, Dict, List

from education_system.systems.university.infrastructure.i18n import get_text as _t
from education_system.systems.university.infrastructure.activity_logger import log_activity

# Authentication imports
try:
    from education_system.systems.university.infrastructure.shared_context import get_auth
    AUTH_AVAILABLE = True
except ImportError:
    AUTH_AVAILABLE = False
    get_auth = None
# shared_context has no placeholder auth class any more, so nothing is rejected on type.
_DummyAuth = None

from education_system.systems.university.domains.health.domain.health.dentist.services.dentist_core import (
    PatientManager, AppointmentManager, TreatmentManager, PrescriptionManager,
    TransactionManager, ReportManager, init_dentist_db,
    TREATMENT_TYPES, DENTIST_STAFF, APPOINTMENT_SLOTS
)

try:
    from education_system.systems.university.infrastructure.email.email_service import send_email
    from education_system.systems.university.infrastructure.email.template_utils import render_template
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False
    def send_email(*args, **kwargs): return False
    render_template = None



def _send_dentist_email(recipient: str, subject: str, body: str, show_success: bool = False) -> bool:
    """Helper function to send emails with proper error handling and logging."""
    if not EMAIL_AVAILABLE:
        print(f"[Dentist] Email service not available - not sent to {recipient}: {subject}")
        return False
    if not recipient:
        print(f"[Dentist] No recipient email provided for: {subject}")
        return False
    try:
        result = send_email(recipient, subject, body)
        if result:
            log_activity('email_sent', 'dentist', details={'to': recipient, 'subject': subject})
            print(f"[Dentist] Email sent successfully to {recipient}: {subject}")
            return True
        else:
            print(f"[Dentist] Email send returned False for {recipient}: {subject}")
            return False
    except Exception as e:
        print(f"[Dentist] Email send error for {recipient}: {e}")
        log_activity('email_failed', 'dentist', details={'to': recipient, 'subject': subject, 'error': str(e)})
        return False

__all__ = [name for name in globals() if not name.startswith("__")]
