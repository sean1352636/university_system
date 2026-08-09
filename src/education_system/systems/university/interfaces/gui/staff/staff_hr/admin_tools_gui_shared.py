"""Shared imports and module state for the split implementation."""

import tkinter as tk

from tkinter import ttk, messagebox, filedialog

from datetime import datetime, timedelta

import json

import os

try:
    from education_system.systems.university.infrastructure.database.db import get_connection, transaction
    from education_system.systems.university.infrastructure.activity_logger import log_activity
    from education_system import paths
except ImportError:
    from education_system.systems.university.infrastructure.database.db import get_connection, transaction
    from education_system.systems.university.infrastructure.activity_logger import log_activity
    from education_system import paths

from education_system.systems.university.infrastructure.sql_safety import escape_like

__all__ = [name for name in globals() if not name.startswith("__") and name != "__all__"]
