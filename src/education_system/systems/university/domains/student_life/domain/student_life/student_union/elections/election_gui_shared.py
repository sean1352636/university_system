"""Shared imports and module state for the split implementation."""

import os

import sys

if 'education_system' not in sys.modules:
    _here = os.path.abspath(os.path.dirname(__file__))
    while _here and not os.path.isdir(
            os.path.join(_here, 'education_system')):
        _parent = os.path.dirname(_here)
        if _parent == _here:
            break
        _here = _parent
    if _here and _here not in sys.path:
        sys.path.insert(0, _here)

import sqlite3

import tkinter as tk

from datetime import datetime

from tkinter import messagebox, simpledialog, ttk

from education_system.paths import UNIVERSITY_DEFAULT_DB_PATH

# The split modules under election_gui_parts/ pick their globals up from this
# module wholesale, and they were written against the pre-consolidation name.
# The paths consolidation renamed it to UNIVERSITY_DEFAULT_DB_PATH and updated
# the import here but not the consumer, so election_gui_parts/database.py died
# with "NameError: name 'DEFAULT_DB_PATH' is not defined" the moment the
# elections hub was opened. Keep the alias — do not delete it.
DEFAULT_DB_PATH = UNIVERSITY_DEFAULT_DB_PATH

PRIMARY = "#1e3a8a"

ACCENT = "#3b82f6"

SUCCESS = "#16a34a"

DANGER = "#dc2626"

WARN = "#d97706"

BG = "#f1f5f9"

CARD = "#ffffff"

TEXT = "#0f172a"

MUTED = "#64748b"

__all__ = [name for name in globals() if not name.startswith("__") and name != "__all__"]
