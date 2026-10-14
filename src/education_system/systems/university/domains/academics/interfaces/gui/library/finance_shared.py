"""Shared imports and module state for the split implementation."""

import tkinter as tk

from tkinter import ttk, messagebox, filedialog, simpledialog

from education_system.systems.university.infrastructure.i18n import get_text as _, init_i18n

init_i18n()

from tkinter.scrolledtext import ScrolledText

import threading

import queue

import os

import sys

from datetime import datetime, timedelta

import json

from education_system.systems.university.infrastructure.database.db import sqlite3

from typing import Dict, List, Optional, Any

import logging

import urllib.request

import urllib.parse

import urllib.error

from education_system.systems.university.infrastructure.exceptions import (
    DatabaseError,
    QueryError,
    ValidationError,
    InvalidInputError,
    FileError,
    UniversityFileNotFoundError
)

try:
    # Import from modular library package
    from education_system.systems.university.domains.academics.domain.services.library.settings import (
        auth, get_current_user_id, set_auth, get_library_settings, update_library_setting
    )
    from education_system.systems.university.domains.academics.domain.services.library.menu import display_library_menu
    from education_system.systems.university.domains.academics.domain.services.library.barcode import (
        generate_barcode, generate_qr_code, process_scanned_barcode
    )
    from education_system.systems.university.domains.academics.domain.services.library.reports import (
        generate_circulation_report, generate_library_statistics_export, generate_user_activity_report
    )
    from education_system.systems.university.domains.academics.domain.services.library.database import (
        get_db_connection, init_library_db, log_audit_event
    )
    from education_system.systems.university.domains.academics.domain.services.library.backup import (
        quick_system_health_check, restore_from_backup
    )
    from education_system.systems.university.domains.academics.domain.services.library.reading_lists import view_reading_list_details
    ORIGINAL_LIBRARY_AVAILABLE = True
except ImportError:
    print("Warning: Original library module not found. GUI will use standalone functions.")
    ORIGINAL_LIBRARY_AVAILABLE = False

try:
    from education_system.systems.university.infrastructure.auth import UserAuth, set_auth_instance
    from education_system.systems.university.infrastructure.shared_context import get_auth, get_current_user
    SHARED_AUTH_AVAILABLE = True
except ImportError:
    print("Warning: Shared authentication system not found.")
    SHARED_AUTH_AVAILABLE = False
    # Provide fallback functions
    def get_auth():
        return None
    def get_current_user():
        return None
    def set_auth_instance(auth_instance):
        return None

from education_system.paths import UNIVERSITY_DEFAULT_DB_PATH

DATABASE_FILE = str(UNIVERSITY_DEFAULT_DB_PATH)

# finance_parts/get_db_connection.py takes its globals from this module and
# still uses the pre-consolidation name. Same breakage as the student-union
# elections hub: it only fires on the fallback branch (when the standalone
# `library` package is unavailable), so it has been latent rather than loud.
# Keep the alias — do not delete it.
DEFAULT_DB_PATH = UNIVERSITY_DEFAULT_DB_PATH

try:
    from education_system.systems.university.domains.finance.infrastructure.finance_integration import (
        process_student_finance_account_payment,
        get_student_finance_account_balance,
        get_student_info,
        LOW_BALANCE_THRESHOLD,
        ensure_student_finance_account_exists,
        top_up_student_finance_account
    )
    FINANCE_ACCOUNT_AVAILABLE = True
except ImportError:
    FINANCE_ACCOUNT_AVAILABLE = False
    print("Warning: Student finance account integration not available")

# Matplotlib, resolved on first use rather than at import.
#
# Two chart dialogs under finance_parts/ are the only readers of these names in
# the whole package, and they are opened by hand. Importing matplotlib.pyplot
# costs ~1.3s, and this module is reached from library/__init__, so that was
# paid by anything that touched the library package — including the Student
# Records window, which embeds LibrarySummaryFrame and draws no charts at all.
#
# Access these through the module (``_shared.Figure``), never as a bare global
# after the finance_parts globals() splice: PEP 562's __getattr__ is only
# consulted for attribute access, and the splice copies __dict__ before these
# names exist. The two readers were updated to do exactly that.
_MATPLOTLIB_NAMES = {
    "plt": ("matplotlib.pyplot", None),
    "FigureCanvasTkAgg": ("matplotlib.backends.backend_tkagg", "FigureCanvasTkAgg"),
    "Figure": ("matplotlib.figure", "Figure"),
}


def _resolve_matplotlib() -> None:
    """Bind plt / FigureCanvasTkAgg / Figure, or None for all three if absent.

    All-or-nothing, mirroring the try/except block this replaced:
    MATPLOTLIB_AVAILABLE stays the single flag callers check.
    """
    import importlib

    resolved: dict[str, object] = {}
    try:
        for name, (module_name, attr) in _MATPLOTLIB_NAMES.items():
            module = importlib.import_module(module_name)
            resolved[name] = module if attr is None else getattr(module, attr)
    except (ImportError, AttributeError):
        resolved = dict.fromkeys(_MATPLOTLIB_NAMES, None)
        resolved["MATPLOTLIB_AVAILABLE"] = False
        print("Warning: Matplotlib not available for library finance charts")
    else:
        resolved["MATPLOTLIB_AVAILABLE"] = True
    globals().update(resolved)


def __getattr__(name: str):
    if name in _MATPLOTLIB_NAMES or name == "MATPLOTLIB_AVAILABLE":
        _resolve_matplotlib()
        return globals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_MATPLOTLIB_NAMES) | {"MATPLOTLIB_AVAILABLE"})

try:
    from education_system.systems.university.infrastructure.email.email_service import send_email_as_system
    EMAIL_SERVICE_AVAILABLE = True
except ImportError:
    EMAIL_SERVICE_AVAILABLE = False
    def send_email_as_system(*args, **kwargs):
        return False
    print("Warning: Email service not available for library finance")

_AUDIT_LOG_COLUMNS_CACHE: Optional[List[str]] = None

_STUDENT_COLUMNS_CACHE: Optional[List[str]] = None

from education_system.systems.university.domains.academics.interfaces.gui.library.base import LibraryGUI

__all__ = [name for name in globals() if not name.startswith("__") and name != "__all__"]
