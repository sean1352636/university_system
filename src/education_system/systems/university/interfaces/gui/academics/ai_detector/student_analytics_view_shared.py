"""Shared imports and module state for the split implementation."""

import json

import os

import threading

import time

import random

from datetime import datetime

import tkinter as tk

from tkinter import ttk, messagebox, filedialog, simpledialog, scrolledtext

from education_system.systems.university.infrastructure.database.db import DEFAULT_DB_PATH, sqlite3

from education_system.systems.university.infrastructure.auth import UserAuth

from education_system.systems.university.infrastructure.shared_context import get_auth

try:
    from education_system.systems.university.infrastructure.ai.ai_detector.detector import AIDetector
    _AI_DETECTOR_IMPORT_ERROR = None
except Exception as import_error:
    AIDetector = None
    _AI_DETECTOR_IMPORT_ERROR = import_error

try:
    import textract
    TEXTRACT_AVAILABLE = True
except ImportError:
    TEXTRACT_AVAILABLE = False

try:
    from pypdf import PdfReader
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False

try:
    import docx
    PYTHON_DOCX_AVAILABLE = True
except ImportError:
    PYTHON_DOCX_AVAILABLE = False

from education_system.systems.university.infrastructure.i18n import get_text, _

__all__ = [name for name in globals() if not name.startswith("__") and name != "__all__"]
