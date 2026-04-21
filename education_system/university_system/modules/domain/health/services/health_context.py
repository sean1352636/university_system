"""Shared imports and state for health portal helpers."""

from __future__ import annotations

import csv
import hashlib
import hmac
import json
import logging
import os
import random
import shutil
import smtplib
from education_system.university_system.infrastructure.database.db import sqlite3
import statistics
import threading
import time
from collections import defaultdict
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import requests
from cryptography.fernet import Fernet

from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.infrastructure.database.data_backup import backup_before_operation
from education_system.university_system.infrastructure.database.db import DatabaseManager, get_connection
from education_system.university_system.infrastructure.email import (
    send_appointment_confirmation,
    send_health_notification,
)
from education_system.university_system.infrastructure.logging.log_config import configure_logging
# Import get_log_file helper for audit logging.
# Without this import a NameError would be raised when computing log_path below.
from education_system.university_system.infrastructure.logging.log_config import get_log_file

log_path = get_log_file("health_portal_audit.log")
os.makedirs(os.path.dirname(log_path), exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(log_path), logging.StreamHandler()],
)

audit_logger = logging.getLogger(__name__)

ENCRYPTION_KEY = Fernet.generate_key()
cipher_suite = Fernet(ENCRYPTION_KEY)

# Import helper functions from other health_misc modules
# These will be available to all modules importing context
def get_user_student_id(auth):
    """Get the student_id for the currently logged-in user."""
    from education_system.university_system.modules.domain.health.services import contacts
    return contacts.get_user_student_id(auth)

def ensure_templates_schema():
    """Ensure the templates schema exists."""
    from education_system.university_system.modules.domain.health.services import health_db_backup
    return health_db_backup.ensure_templates_schema()
