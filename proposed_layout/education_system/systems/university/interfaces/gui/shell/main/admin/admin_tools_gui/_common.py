"""Shared imports, paths, logger, and JSON helpers for the admin_tools_gui package."""

# Admin tools GUI - 14 admin-only features
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import logging
import os
import json
import csv
from datetime import datetime, timedelta
from education_system.systems.university.interfaces.gui.shell.main._tk_callback_filter import install_clean_close as _install_clean_close

from education_system.systems.university.infrastructure.paths import (
    PROJECT_ROOT, DATA_DIR, CONFIG_DIR, DB_DIR, LOG_DIR, EMAIL_CONFIG_FILE,
    SAVED_REPORTS_FILE, API_SERVER_CONFIG_FILE, LICENSES_FILE, DR_CONFIG_FILE,
    SCHEDULED_REPORTS_FILE, EMAIL_TEMPLATE_MAPPING_FILE,
    UPLOAD_DIR, BACKUP_DIR, EMAIL_TEMPLATES_DIR,
)
from education_system.systems.university.infrastructure.i18n import get_text as _t

logger = logging.getLogger(__name__)

# `from ._common import *` skips underscore-prefixed names by default,
# which would drop `_t` and `_install_clean_close` — the two things
# every sibling actually relies on. Be explicit so the wildcard import
# pulls them in.
__all__ = [
    # stdlib re-exports
    "tk", "ttk", "messagebox", "filedialog",
    "logging", "os", "json", "csv",
    "datetime", "timedelta",
    # local helpers
    "_install_clean_close", "_t", "logger",
    # path constants
    "PROJECT_ROOT", "DATA_DIR", "CONFIG_DIR", "DB_DIR", "LOG_DIR",
    "EMAIL_CONFIG_FILE", "SAVED_REPORTS_FILE",
    "API_SERVER_CONFIG_FILE", "LICENSES_FILE", "DR_CONFIG_FILE",
    "SCHEDULED_REPORTS_FILE", "EMAIL_TEMPLATE_MAPPING_FILE",
    "UPLOAD_DIR", "BACKUP_DIR", "EMAIL_TEMPLATES_DIR",
]


def _ensure_dir(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)


def _load_json(path, default=None):
    try:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return default if default is not None else {}


def _save_json(path, data):
    _ensure_dir(path)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
