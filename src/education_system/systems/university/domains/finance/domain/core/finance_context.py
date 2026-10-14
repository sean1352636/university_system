"""Shared context and heavy imports for finance miscellaneous helpers."""

from __future__ import annotations

import base64
import csv
import hashlib
import hmac
import importlib
import json
import logging
import os
from education_system.systems.university.infrastructure.database.db import sqlite3
import threading
import time
import warnings
from datetime import datetime, timedelta
from io import BytesIO

import smtplib
import ssl

# ---------------------------------------------------------------------------
# Optional third-party dependencies — resolved on first use, not at import.
# ---------------------------------------------------------------------------
# This module is a shared namespace, and importing it used to drag in the whole
# analytics stack eagerly. seaborn (→ scipy.stats), matplotlib.pyplot,
# sklearn.ensemble and pandas came to ~6.4s between them, with flask (0.8s),
# joblib (0.6s), reportlab (0.5s) and requests (0.4s) on top.
#
# Nothing here needs any of them at import time, but finance_context sits under
# finance_integration — which 118 Operations modules, 56 Pastoral modules and a
# cluster in Academics import directly — so that cost was paid on paths with no
# interest in plotting or ML at all. Opening a student record in the GUI took
# ~9s on the first open of a session purely because its Library tab reaches
# this module.
#
# PEP 562's module ``__getattr__`` resolves a name on first access and caches
# it in ``globals()``, so later lookups never reach the hook. A missing
# optional dependency caches as ``None``, exactly as the old
# ``try/except ImportError`` blocks left it, so callers checking
# ``if plt is None`` behave identically. Names are grouped to mirror those
# blocks: flask and reportlab were all-or-nothing, and one missing member still
# leaves the whole group ``None``.
#
# Two things to know before adding to this:
#   * ``from finance_context import plt`` still works — the import machinery
#     falls back to ``getattr`` on the module. A bare ``import *`` would not
#     see these names, as they are absent from ``globals()`` until touched.
#     Nothing in the tree star-imports this module (checked across src/).
#   * Module ``__getattr__`` is NOT consulted for a bare global lookup *inside*
#     this module. Code added here must import these in the function body
#     rather than reading the module global, or it will hit NameError.

_LAZY_GROUPS: tuple[dict[str, tuple[str, str | None]], ...] = (
    {"joblib": ("joblib", None)},
    {"plt": ("matplotlib.pyplot", None)},
    {"np": ("numpy", None)},
    {"pd": ("pandas", None)},
    {"qrcode": ("qrcode", None)},
    {"requests": ("requests", None)},
    {"schedule": ("schedule", None)},
    {"sns": ("seaborn", None)},
    {"Fernet": ("cryptography.fernet", "Fernet")},
    {
        "Flask": ("flask", "Flask"),
        "jsonify": ("flask", "jsonify"),
        "request": ("flask", "request"),
    },
    {
        "VerticalBarChart": ("reportlab.graphics.charts.barcharts", "VerticalBarChart"),
        "Pie": ("reportlab.graphics.charts.piecharts", "Pie"),
        "Drawing": ("reportlab.graphics.shapes", "Drawing"),
        "reportlab_colors": ("reportlab.lib", "colors"),
        "letter": ("reportlab.lib.pagesizes", "letter"),
        "landscape": ("reportlab.lib.pagesizes", "landscape"),
        "ParagraphStyle": ("reportlab.lib.styles", "ParagraphStyle"),
        "getSampleStyleSheet": ("reportlab.lib.styles", "getSampleStyleSheet"),
        "inch": ("reportlab.lib.units", "inch"),
        "Image": ("reportlab.platypus", "Image"),
        "PageBreak": ("reportlab.platypus", "PageBreak"),
        "Paragraph": ("reportlab.platypus", "Paragraph"),
        "SimpleDocTemplate": ("reportlab.platypus", "SimpleDocTemplate"),
        "Spacer": ("reportlab.platypus", "Spacer"),
        "Table": ("reportlab.platypus", "Table"),
        "TableStyle": ("reportlab.platypus", "TableStyle"),
    },
    {
        "IsolationForest": ("sklearn.ensemble", "IsolationForest"),
        "StandardScaler": ("sklearn.preprocessing", "StandardScaler"),
    },
)

_LAZY_MEMBERS: dict[str, dict[str, tuple[str, str | None]]] = {
    name: group for group in _LAZY_GROUPS for name in group
}


def _resolve_group(group: dict[str, tuple[str, str | None]]) -> None:
    """Import every name in *group*, or bind them all to None on failure."""
    resolved: dict[str, object] = {}
    try:
        for name, (module_name, attr) in group.items():
            module = importlib.import_module(module_name)
            resolved[name] = module if attr is None else getattr(module, attr)
    except (ImportError, AttributeError):
        resolved = dict.fromkeys(group, None)
    globals().update(resolved)


def _lazy(name: str):
    """Read a lazy name from this module, resolving it if not yet bound."""
    if name in globals():
        return globals()[name]
    return __getattr__(name)


def _build_app() -> None:
    """Create the shared Flask app on first access to ``app``.

    Was ``app = Flask(__name__) if Flask else None`` at module scope, which
    made importing this module import flask (~0.8s). Nothing imports ``app``
    from here, so the object is now built on demand instead.
    """
    flask_cls = _lazy("Flask")
    globals()["app"] = flask_cls(__name__) if flask_cls else None


def _build_encryption() -> None:
    """Generate the per-process Fernet key and cipher on first access.

    ENCRYPTION_KEY and cipher_suite are a pair, so both are bound together
    whichever one is asked for first. As before, the key is generated once per
    process and both fall back to None when cryptography is unavailable or
    key generation fails.
    """
    fernet = _lazy("Fernet")
    key = None
    cipher = None
    if fernet:
        try:
            generated = fernet.generate_key()
        except Exception:
            generated = None
        if isinstance(generated, bytes):
            key = generated
            try:
                cipher = fernet(key)
            except Exception:
                cipher = None
    globals()["ENCRYPTION_KEY"] = key
    globals()["cipher_suite"] = cipher


_DERIVED = {
    "app": _build_app,
    "ENCRYPTION_KEY": _build_encryption,
    "cipher_suite": _build_encryption,
}


def __getattr__(name: str):
    group = _LAZY_MEMBERS.get(name)
    if group is not None:
        _resolve_group(group)
        return globals()[name]
    builder = _DERIVED.get(name)
    if builder is not None:
        builder()
        return globals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_LAZY_MEMBERS) | set(_DERIVED))


from education_system.systems.university.infrastructure.auth import UserAuth
from education_system.systems.university.infrastructure.database.db import get_connection
from education_system.systems.university.infrastructure.email import send_email
from education_system.systems.university.infrastructure.logging.log_config import configure_logging

# Configure logging
logger = configure_logging(name=__name__)
warnings.filterwarnings("ignore")

# The shared Flask app for webhook-style integrations (``app``) and the
# encryption pair (``ENCRYPTION_KEY`` / ``cipher_suite``) are built on first
# access — see _build_app and _build_encryption above.

# Payment gateway configurations
PAYMENT_GATEWAYS = {
    "stripe": {
        "public_key": os.getenv('STRIPE_PUBLIC_KEY', ''),
        "secret_key": os.getenv('STRIPE_SECRET_KEY', ''),
        "webhook_secret": os.getenv('STRIPE_WEBHOOK_SECRET', ''),
    },
    "paypal": {
        "client_id": os.getenv('PAYPAL_CLIENT_ID', ''),
        "client_secret": os.getenv('PAYPAL_CLIENT_SECRET', ''),
        "environment": os.getenv('PAYPAL_ENVIRONMENT', 'sandbox'),
    },
}

# WARNING: Never commit real API keys to version control!
# Set these environment variables in your deployment environment
SUPPORTED_CURRENCIES = ["GBP", "USD", "EUR", "CAD", "AUD"]
BASE_CURRENCY = "GBP"
# Load exchange API key from environment variable
EXCHANGE_API_KEY = os.getenv('EXCHANGE_API_KEY', '')

# Use centralized auth management
from education_system.systems.university.infrastructure.shared_context import (
    get_auth,
    set_auth,
    get_current_user,
    check_permission,
)

# Backward compatibility - auth will be initialized lazily
# Don't call get_auth() at module level to avoid warnings
auth = None
