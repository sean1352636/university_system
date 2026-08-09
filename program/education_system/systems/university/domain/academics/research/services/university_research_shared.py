"""Shared imports and module state for the split implementation."""

import logging

import os

import sqlite3

import sys

import tkinter as tk

from datetime import datetime, date

from pathlib import Path

from tkinter import ttk, messagebox, filedialog, simpledialog

if 'education_system' not in sys.modules:
    _here = os.path.abspath(os.path.dirname(__file__))
    while _here and not os.path.isdir(os.path.join(_here, 'education_system')):
        _parent = os.path.dirname(_here)
        if _parent == _here:
            break
        _here = _parent
    if _here and _here not in sys.path:
        sys.path.insert(0, _here)

logger = logging.getLogger(__name__)

try:
    from education_system.systems.university.infrastructure.logging.log_config import configure_logging
    configure_logging(name=__name__)
except Exception:
    logger.debug("Central log config unavailable; falling back to default handlers", exc_info=True)

_LEGACY_DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "university_research.db")

PALETTE = {
    # 8.117.65 — flattened to the main GUI's neutral clam-default look.
    # Pre-8.117.65 the portal had a navy header bar (#1f3a68), white
    # panel cards, and a saturated blue accent button — visually
    # disconnected from every other workspace tab.
    "bg": "#f0f0f0",
    "panel": "#f0f0f0",
    "header": "#f0f0f0",
    "accent": "#3c5a99",
    "accent_soft": "#e1e1e1",
    "text": "#000000",
    "muted": "#555555",
    "success": "#1f7a3c",
    "warn": "#b0620a",
    "danger": "#b3261e",
    "border": "#cccccc",
}

__all__ = [name for name in globals() if not name.startswith("__") and name != "__all__"]
