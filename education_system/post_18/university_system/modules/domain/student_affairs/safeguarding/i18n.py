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

_LANG_NAMES = {
    "en": "English",
    "es": "Español",
    "fr": "Français",
    "de": "Deutsch",
    "zh": "中文",
    "ar": "العربية",
    "pt": "Português",
    "pl": "Polski",
    "ur": "اردو",
    "cy": "Cymraeg",
}
_I18N_READY = False


def _ensure_i18n_loaded():
    global _I18N_READY
    if _I18N_READY:
        return
    try:
        from education_system.post_18.university_system.core.i18n import init_i18n

        init_i18n()
        _I18N_READY = True
    except Exception:
        logger.debug("Shared i18n unavailable; tr() will fall back to keys", exc_info=True)


def tr(key: str, lang: str = "en", **kwargs) -> str:
    """Translate ``safeguarding.<key>`` in *lang* with English fallback.

    Translations live in ``university_system/data/locales/<lang>/safeguarding/
    safeguarding.json`` and are loaded via the shared i18n engine.
    """
    _ensure_i18n_loaded()
    full_key = f"safeguarding.{key}"
    try:
        from education_system.shared.i18n.core import _translations, _ensure_loaded

        _ensure_loaded()
        for code in (lang, "en"):
            node = _translations.get(code) or {}
            for part in full_key.split("."):
                if isinstance(node, dict):
                    node = node.get(part)
                else:
                    node = None
                    break
                if node is None:
                    break
            if isinstance(node, str):
                try:
                    return node.format(**kwargs) if kwargs else node
                except (KeyError, IndexError):
                    return node
    except Exception:
        logger.debug("tr() lookup failed for %s", full_key, exc_info=True)
    return key


__all__ = ["_LANG_NAMES", "_I18N_READY", "_ensure_i18n_loaded", "tr"]
