"""Shared imports and module state for the split implementation."""

import tkinter as tk

from tkinter import ttk, messagebox, scrolledtext, simpledialog, filedialog

from education_system.systems.university.infrastructure.database.db import sqlite3

from education_system import paths

from datetime import datetime, timedelta

import hashlib

import json

import sys

import os

import logging

from typing import Dict, List, Optional, Tuple, Any

import threading

import queue

from education_system.systems.university.infrastructure.email.template_utils import render_template

from education_system.systems.university.infrastructure.auth import UserAuth

from education_system.systems.university.infrastructure.shared_context import get_auth

from education_system.systems.university.infrastructure.i18n import (
    init_i18n,
    get_text as _t,
    set_language,
    get_current_language,
    get_current_language_name,
    get_available_languages,
)

from education_system.systems.university.infrastructure.utils.gui_language_selector import show_gui_language_selector

DEFAULT_DB_PATH = paths.UNIVERSITY_DEFAULT_DB_PATH

try:
    from education_system.systems.university.domains.finance.infrastructure.finance_integration import (
        process_student_finance_account_payment,
        get_student_finance_account_balance,
        get_student_info,
        LOW_BALANCE_THRESHOLD
    )
    FINANCE_ACCOUNT_AVAILABLE = True
except ImportError:
    FINANCE_ACCOUNT_AVAILABLE = False
    print("Warning: Student finance account integration not available")

try:
    # Import CLI components to maintain backwards compatibility. If available,
    # include the full database initializer so the GUI can create the
    # comprehensive schema when running stand-alone.
    from education_system.systems.university.infrastructure.database.db import get_connection
    from education_system.systems.university.domains.student_life.domain.student_life.student_union.administration.student_union_core import init_student_union_db
    CLI_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    print("Warning: CLI system not available. Some features may be limited.")
    student_union_cli = None
    init_student_union_db = None
    CLI_AVAILABLE = False

logger = logging.getLogger(__name__)

__all__ = [name for name in globals() if not name.startswith("__") and name != "__all__"]
