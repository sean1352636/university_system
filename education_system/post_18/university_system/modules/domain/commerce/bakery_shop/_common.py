"""
University Bakery Shop Management System
A GUI application built with tkinter for managing a university bakery.

Auth: piggybacks on the main university auth — when launched as a
subprocess from the unified main GUI, EDU_AUTH_* env vars carry the
logged-in user's identity. The role-based discount tier is derived
from EDU_AUTH_ROLE (student → 10%, staff → 15%, admin → admin
console). There is no in-app login.

Persistence: orders live in the central `student_records.db` table
`bakery_orders`. The legacy `bakery_orders.json` sidecar file is
removed on startup.

Logging: routed through the shared rotating `app.log` via
`infrastructure.logging.log_config.configure_logging`.
"""

import json
import logging
import os
import sqlite3
import sys
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import ttk, messagebox, simpledialog


# When the main GUI launches us as a subprocess, the child Python is
# invoked directly on this file's path with no PYTHONPATH set, so
# `education_system` isn't importable. Walk up from this file until we
# find the dir that contains the `education_system` package and put
# that on sys.path. No-op when imported normally.
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
    from education_system.post_18.university_system.infrastructure.logging.log_config import configure_logging
    configure_logging(name=__name__)
except Exception:
    logger.debug("Central log config unavailable; falling back to default handlers", exc_info=True)


# ---------------------------------------------------------------------------
# AUTH BOOTSTRAP
# ---------------------------------------------------------------------------
def _get_current_user():
    user_id = os.environ.get('EDU_AUTH_USER_ID') or ''
    username = os.environ.get('EDU_AUTH_USERNAME') or ''
    role = os.environ.get('EDU_AUTH_ROLE') or ''
    email = os.environ.get('EDU_AUTH_EMAIL') or ''
    perms_raw = os.environ.get('EDU_AUTH_PERMISSIONS') or ''
    if user_id or username:
        return {
            'id': user_id or None,
            'user_id': user_id or None,
            'username': username,
            'role': role,
            'email': email,
            'permissions': [p for p in perms_raw.split(',') if p],
        }
    try:
        from education_system.post_18.university_system.infrastructure.auth import get_global_auth
        ga = get_global_auth()
        if ga and getattr(ga, 'current_user', None):
            return ga.current_user
    except Exception:
        logger.debug("get_global_auth fallback failed", exc_info=True)
    return None


def _bakery_user_type(role: str) -> str:
    """Map an EDU_AUTH role onto the bakery's discount-tier model:
    Admin / Staff / Student / Guest."""
    r = (role or '').lower()
    if r in ('admin', 'administrator', 'superadmin'):
        return 'Admin'
    if r in ('staff', 'instructor', 'lecturer', 'faculty', 'manager', 'hr'):
        return 'Staff'
    if r in ('student',):
        return 'Student'
    return 'Guest'


# Legacy sidecar files this module used to write — superseded by the
# central student_records.db.
_LEGACY_JSON_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "bakery_orders.json")


# ---------------------------------------------------------------------------
# Catalog vocab & helpers
# ---------------------------------------------------------------------------
ALLERGEN_VOCAB = [
    "gluten", "wheat", "milk", "eggs", "soy", "nuts", "peanuts",
    "almonds", "sesame", "fish", "shellfish", "celery", "mustard",
    "sulphites", "lupin", "molluscs",
]

DIETARY_VOCAB = [
    "vegan", "vegetarian", "halal", "kosher", "gluten-free",
    "dairy-free", "nut-free", "low-sugar", "high-fibre",
]

IMAGES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images")


def _i18n(key, default=None, **fmt):
    """Translate `key` via the university i18n module if available.
    Falls back to `default` (or the key) — never raises."""
    try:
        from education_system.post_18.university_system.core.i18n import get_text
        text = get_text(key)
        if text and text != key:
            return text.format(**fmt) if fmt else text
    except Exception:
        pass
    base = default if default is not None else key
    try:
        return base.format(**fmt) if fmt else base
    except Exception:
        return base


def _mk(*kvs):
    """Build a product info dict from interleaved key/value args.
    Keeps the catalog table-style readable across many fields."""
    if len(kvs) % 2:
        raise ValueError("_mk requires an even number of args")
    return {kvs[i]: kvs[i + 1] for i in range(0, len(kvs), 2)}


# Loyalty rules: 1 point per £1 spent. Redemption: 100 pts = £1 off.
LOYALTY_POINTS_PER_POUND = 1
LOYALTY_POINTS_PER_GBP_REDEEM = 100
PUNCH_CARD_CATEGORIES = {"Beverages": 10}  # buy 10, 10th free
FIRST_PURCHASE_DISCOUNT_PCT = 0.15
REFERRAL_BONUS_GBP = 2.0
BIRTHDAY_DISCOUNT_PCT = 0.20

# UK VAT defaults. Bread/cakes/cookies are mostly zero-rated; hot drinks
# attract standard rate. Admins can override at the line item via the
# product metadata field `vat_rate`.
VAT_RATES = {
    "Breads":    0.00,
    "Pastries":  0.00,
    "Cakes":     0.00,
    "Cookies":   0.00,
    "Beverages": 0.20,
}

# Phase-6 themes. Keys match self.colors. Switching theme rebuilds the UI.
THEMES = {
    "classic": {
        "primary":   "#8B4513", "secondary": "#D2691E", "accent": "#FFD700",
        "background":"#FFF8E7", "card": "#FFFFFF",       "text": "#3E2723",
        "success":   "#4CAF50", "danger":   "#D32F2F",
    },
    "dark": {
        "primary":   "#D2A678", "secondary": "#A0522D", "accent": "#FFD56B",
        "background":"#1E1A16", "card": "#2C2620",       "text": "#FFF3D0",
        "success":   "#7DCB7A", "danger":   "#FF6B6B",
    },
    "high_contrast": {
        "primary":   "#000000", "secondary": "#444444", "accent": "#FFFF00",
        "background":"#FFFFFF", "card": "#FFFFFF",      "text": "#000000",
        "success":   "#006400", "danger":   "#B00000",
    },
}

FEEDBACK_CATEGORIES = [
    "Compliment", "Complaint", "Suggestion",
    "Product quality", "Customer service", "Other",
]

REFUND_REASON_CATEGORIES = [
    "Wrong item received",
    "Item missing from order",
    "Allergy / dietary concern",
    "Quality / freshness issue",
    "Did not collect",
    "Customer changed mind",
    "Other",
]


def _remove_legacy_files():
    here = os.path.dirname(os.path.abspath(__file__))
    targets = [
        _LEGACY_JSON_FILE,
        os.path.abspath("bakery_orders.json"),
    ]
    if os.path.isdir(here):
        for fname in os.listdir(here):
            if fname.endswith(('.db', '.db-wal', '.db-shm', '.db-journal')):
                targets.append(os.path.join(here, fname))
    for path in set(targets):
        if os.path.exists(path):
            try:
                os.remove(path)
                logger.info("Removed legacy bakery file: %s", path)
            except OSError:
                logger.warning("Could not remove legacy file %s", path,
                               exc_info=True)




# Names exported via `from ._common import *` — includes underscore-
# prefixed helpers (which `*` would normally skip without __all__).
__all__ = [n for n in dir() if not n.startswith("__")]
