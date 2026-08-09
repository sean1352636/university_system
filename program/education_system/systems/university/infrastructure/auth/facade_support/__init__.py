"""Shared dependencies for the authentication façade."""

from typing import Optional, Dict, List, Any, Union, Tuple

import json

import traceback

import logging

from education_system.systems.university.infrastructure.database.db import sqlite3, DatabaseManager

import hashlib

import secrets

import re

import os

import time

from datetime import datetime, timedelta

try:
    import pyotp
except ImportError:
    pyotp = None

import io

import base64

import contextlib

import threading

from pathlib import Path

from education_system.systems.university.infrastructure.database.db import get_connection

import sys

from education_system import paths

from education_system.systems.university.infrastructure import defaults

from education_system.systems.university.infrastructure.sql_safety import (
    validate_column_definition,
    SQLIdentifierError,
)

from education_system.systems.university.infrastructure.exceptions import (
    AuthenticationError,
    InvalidCredentialsError,
    SessionExpiredError,
    PermissionDeniedError,
    MFARequiredError,
    ValidationError,
    InvalidInputError,
    DatabaseError,
)

logger = logging.getLogger(__name__)

from education_system.systems.university.infrastructure.i18n import get_text

try:
    from education_system.systems.university.infrastructure.activity_logger import (
        set_user, log_login, log_logout, log_activity, log_access
    )
    ACTIVITY_LOGGER_AVAILABLE = True
except ImportError:
    ACTIVITY_LOGGER_AVAILABLE = False

try:
    from education_system.systems.university.infrastructure.security.audit_helpers import safe_log_security_event
    from education_system.systems.university.infrastructure.security.immutable_audit_log import AuditAction
    IMMUTABLE_AUDIT_AVAILABLE = True
except ImportError:
    IMMUTABLE_AUDIT_AVAILABLE = False

try:
    from education_system.systems.university.infrastructure.security.security_alerts import (
        alert_account_lockout,
    )
    SECURITY_ALERTS_AVAILABLE = True
except ImportError:
    SECURITY_ALERTS_AVAILABLE = False

try:
    from education_system.systems.university.infrastructure.auth.mfa_enforcement import (
        enforce_mfa_on_login,
    )
    MFA_ENFORCEMENT_AVAILABLE = True
except ImportError:
    MFA_ENFORCEMENT_AVAILABLE = False

from education_system.systems.university.infrastructure.auth.optional_dependencies import (
    get_chatbot,
    get_chatbot_class,
    get_voice_interface,
    is_chatbot_available,
    is_voice_interface_available,
    OptionalDependencyError,
    ChatbotInterface,
    VoiceInterface,
)

from education_system.systems.university.infrastructure.auth.core_utils.constants import ROLES, PERMISSIONS
