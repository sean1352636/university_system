import base64
import hashlib
import json
import logging
import os
import re
import secrets
import shutil
import sqlite3
import sys
import tkinter as tk
import webbrowser
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from tkinter import ttk, messagebox, scrolledtext, filedialog

logger = logging.getLogger(__name__)

from education_system.systems.university.domain.safeguarding.config import (
    _DRAFT_DIR,
)
from education_system.systems.university.domain.safeguarding.crypto import (
    _ensure_dirs,
)


def _draft_path(username: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", username or "anon")
    return os.path.join(_DRAFT_DIR, f"{safe}.draft.json")


def save_draft(username: str, payload: dict) -> None:
    if not username:
        return
    _ensure_dirs()
    try:
        with open(_draft_path(username), "w", encoding="utf-8") as f:
            json.dump(payload, f)
    except OSError:
        logger.debug("Failed to save draft for %s", username, exc_info=True)


def load_draft(username: str) -> dict:
    try:
        with open(_draft_path(username), "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except (OSError, ValueError):
        return {}


def clear_draft(username: str) -> None:
    p = _draft_path(username)
    if os.path.exists(p):
        try:
            os.remove(p)
        except OSError:
            pass


__all__ = ["_draft_path", "save_draft", "load_draft", "clear_draft"]
