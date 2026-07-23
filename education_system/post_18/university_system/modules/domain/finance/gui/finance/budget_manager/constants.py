"""Budget manager constants and shared setup"""

import os
import logging
import warnings
from cryptography.fernet import Fernet

# Import authentication - REQUIRED (no fallback for security)
from education_system.post_18.university_system.infrastructure.auth import UserAuth, get_global_auth
from education_system.post_18.university_system.infrastructure.shared_context import get_auth

# Import database utilities - use centralized connection management
from education_system.post_18.university_system.infrastructure.database.db import get_connection

# Import optional modules with fallbacks for non-critical functionality
try:
    from education_system.post_18.university_system.infrastructure.email.email_service import send_email
except ImportError:
    def send_email(*args, **kwargs):
        """Fallback stub when email service is unavailable."""
        return True

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

# Import finance functions from common_imports module (explicit imports)
from education_system.post_18.university_system.modules.domain.finance.gui.finance.common_imports import (
    # Budget management
    budget_approval_workflow,
    budget_performance_trends,
    budget_vs_actual_analysis,
    category_performance_report,
    create_budget_plan,
    variance_analysis_report,
    # Budget categories
    create_budget_category,
    deactivate_budget_category,
    edit_budget_category,
    update_actual_amounts,
    view_budget_categories,
)

# Configure logging
log_path = get_log_file("app.log")
os.makedirs(os.path.dirname(log_path), exist_ok=True)


logger = configure_logging(name=__name__)
warnings.filterwarnings('ignore')

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
SUPPORTED_CURRENCIES = ['GBP', 'USD', 'EUR', 'CAD', 'AUD']
# Load exchange API key from environment variable
EXCHANGE_API_KEY = os.getenv('EXCHANGE_API_KEY', '')
