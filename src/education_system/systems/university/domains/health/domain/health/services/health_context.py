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
from education_system.systems.university.domains.health.infrastructure.health.storage import sqlite3
import statistics
import threading
import time
from collections import defaultdict
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import requests

from education_system.systems.university.infrastructure.auth import UserAuth
from education_system.systems.university.infrastructure.database.data_backup import backup_before_operation
from education_system.systems.university.domains.health.infrastructure.health.storage import DatabaseManager, get_connection
from education_system.systems.university.infrastructure.email import (
    send_appointment_confirmation,
    send_health_notification,
)
from education_system.systems.university.infrastructure.logging.log_config import configure_logging
# Import get_log_file helper for audit logging.
# Without this import a NameError would be raised when computing log_path below.
from education_system.systems.university.infrastructure.logging.log_config import get_log_file

log_path = get_log_file("app.log")
os.makedirs(os.path.dirname(log_path), exist_ok=True)


audit_logger = logging.getLogger(__name__)

# Sensitive fields are sealed with the one managed key
# (infrastructure/health/field_crypto). A key made per process here used to
# encrypt data no later process could read.
from education_system.systems.university.domains.health.infrastructure.health import field_crypto
cipher_suite = field_crypto.cipher()

# Import helper functions from other health_misc modules
# These will be available to all modules importing context
def get_user_student_id(auth):
    """Get the student_id for the currently logged-in user."""
    from education_system.systems.university.domains.health.domain.health.services import contacts
    return contacts.get_user_student_id(auth)

def ensure_templates_schema():
    """Ensure the templates schema exists."""
    from education_system.systems.university.domains.health.domain.health.services import health_db_backup
    return health_db_backup.ensure_templates_schema()
