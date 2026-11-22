"""Shared imports and module state for the split implementation."""

import logging

import os

import re

import sqlite3

import sys

import tempfile

import webbrowser

import tkinter as tk

from tkinter import ttk, scrolledtext
from education_system.platform.delivery.gui.parented_dialogs import messagebox

from datetime import datetime, timedelta

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

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_PHONE_RE = re.compile(r"^[0-9\s()+\-]{7,}$")

_ID_RE = re.compile(r"^[A-Za-z0-9\-]+$")

from education_system.systems.university.domains.health.domain.health.first_aid.first_aid_service import (  # noqa: E402
    CAMPUS_NUMBER_KEYS,
    EMERGENCY_CONTACTS,
    IncidentDB,
    campus_numbers,
    emergency_contacts,
    set_campus_number,
)

__all__ = [name for name in globals() if not name.startswith("__") and name != "__all__"]
