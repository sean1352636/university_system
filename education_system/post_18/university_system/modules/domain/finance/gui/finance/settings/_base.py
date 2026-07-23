"""SettingsManager class composed from domain-specific mixins."""

import os
import warnings
import logging

from education_system.post_18.university_system.infrastructure.database.db import DEFAULT_DB_PATH  # injected
from education_system.post_18.university_system.infrastructure.auth import UserAuth, get_global_auth
from education_system.post_18.university_system.infrastructure.shared_context import get_auth
from education_system.post_18.university_system.infrastructure.database.db import get_connection

from cryptography.fernet import Fernet

try:
    from education_system.post_18.university_system.infrastructure.logging.log_config import configure_logging, get_log_file
except ImportError:
    def configure_logging(name=None):
        """Fallback logging configuration."""
        return logging.getLogger(name or __name__)

    def get_log_file(name):
        """Fallback log file path resolution."""
        from education_system.post_18.university_system.core import paths
        return str(paths.LOG_DIR / name)

# ---------------------------------------------------------------------------
# Module-level constants (preserved for backward compatibility)
# ---------------------------------------------------------------------------

# Global variables for backward compatibility
auth = get_global_auth()  # Use centralized auth instance
ENCRYPTION_KEY = Fernet.generate_key()
cipher_suite = Fernet(ENCRYPTION_KEY)

# Payment gateway configurations (from original file)
PAYMENT_GATEWAYS = {
    'stripe': {
        'public_key': os.getenv('STRIPE_PUBLIC_KEY', ''),
        'secret_key': os.getenv('STRIPE_SECRET_KEY', ''),
        'webhook_secret': os.getenv('STRIPE_WEBHOOK_SECRET', '')
    },
    'paypal': {
        'client_id': os.getenv('PAYPAL_CLIENT_ID', ''),
        'client_secret': os.getenv('PAYPAL_CLIENT_SECRET', ''),
        'environment': os.getenv('PAYPAL_ENVIRONMENT', 'sandbox')
    }
}

# WARNING: Never commit real API keys to version control!
# Set these environment variables in your deployment environment
from education_system.post_18.university_system.modules.domain.finance.gui.finance.settings.currency import SUPPORTED_CURRENCIES  # noqa: E402 – re-export
# Load exchange API key from environment variable
EXCHANGE_API_KEY = os.getenv('EXCHANGE_API_KEY', '')

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

log_path = get_log_file("app.log")
os.makedirs(os.path.dirname(log_path), exist_ok=True)


logger = configure_logging(name=__name__)
warnings.filterwarnings('ignore')

# ---------------------------------------------------------------------------
# Mixin imports
# ---------------------------------------------------------------------------

from education_system.post_18.university_system.modules.domain.finance.gui.finance.settings.general_settings import GeneralSettingsMixin  # noqa: E402
from education_system.post_18.university_system.modules.domain.finance.gui.finance.settings.currency import CurrencyMixin  # noqa: E402
from education_system.post_18.university_system.modules.domain.finance.gui.finance.settings.notifications import NotificationsMixin  # noqa: E402
from education_system.post_18.university_system.modules.domain.finance.gui.finance.settings.financial_aid import FinancialAidMixin  # noqa: E402
from education_system.post_18.university_system.modules.domain.finance.gui.finance.settings.scholarships import ScholarshipsMixin  # noqa: E402
from education_system.post_18.university_system.modules.domain.finance.gui.finance.settings.admin import AdminMixin  # noqa: E402
from education_system.post_18.university_system.modules.domain.finance.gui.finance.settings.reports import ReportsMixin  # noqa: E402


class SettingsManager(
    GeneralSettingsMixin,
    CurrencyMixin,
    NotificationsMixin,
    FinancialAidMixin,
    ScholarshipsMixin,
    AdminMixin,
    ReportsMixin,
):
    """System settings and configuration"""

    def __init__(self, gui):
        """Initialize manager with reference to main GUI"""
        self.gui = gui
        self.root = gui.root
        self.conn = gui.conn
        self.auth = getattr(gui, 'auth', get_global_auth())
        try:
            self.finance_system = gui.finance_system
        except Exception:
            self.finance_system = None

    def update_status(self, message):
        """Update status bar message - delegates to GUI layout"""
        try:
            if hasattr(self.gui, 'layout') and hasattr(self.gui.layout, 'update_status'):
                self.gui.layout.update_status(message)
            elif hasattr(self.gui, 'update_status'):
                self.gui.update_status(message)
        except Exception:
            pass  # Silently ignore if status update fails
