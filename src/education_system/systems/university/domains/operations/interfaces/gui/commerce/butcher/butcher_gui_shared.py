"""Shared imports and module state for the split implementation."""

import tkinter as tk

from tkinter import ttk, messagebox, simpledialog

import logging

from datetime import datetime, timedelta

from typing import Optional, List

from education_system.systems.university.infrastructure.i18n import get_text as _t

from education_system.systems.university.infrastructure.database.db import get_db_connection, get_connection, transaction

from education_system.systems.university.infrastructure.activity_logger import log_activity

logger = logging.getLogger(__name__)

try:
    from education_system.systems.university.infrastructure.email.email_service import send_email
    from education_system.systems.university.infrastructure.email.template_utils import render_template
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False
    def send_email(*args, **kwargs): return False
    render_template = None

__all__ = [name for name in globals() if not name.startswith("__") and name != "__all__"]
