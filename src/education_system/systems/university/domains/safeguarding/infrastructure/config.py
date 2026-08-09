"""
University Portal Safeguarding System
--------------------------------------
A GUI application that screens messages/posts submitted through a
university portal for safeguarding concerns (self-harm, bullying,
harassment, exploitation, academic distress, etc.) and routes flagged
content to the appropriate support team.

Auth: piggybacks on the main university auth — when launched as a
subprocess from the unified main GUI, EDU_AUTH_* env vars carry the
logged-in user's identity. There is no in-app login screen. Users
with role=='student' see the submission form; everyone else (staff,
instructor, admin, dsl, ...) gets the staff review console.

Persistence: rows live in the dedicated classified safeguarding database.
General student-record connections cannot query this storage.

Logging: routed through the shared rotating `app.log` via
`infrastructure.logging.log_config.configure_logging`.

NOTE: This is an educational/demonstration tool. A real safeguarding
system requires trained professionals, robust NLP (not keyword matching),
compliance with GDPR/Data Protection law, and integration with
institutional safeguarding policy.
"""

import base64
import hashlib
import json
import logging
import os
import re
import secrets
import shutil
import sys
from datetime import datetime, timedelta
from difflib import SequenceMatcher

# When the main GUI launches us as a subprocess, the child Python is
# invoked directly on this file's path with no PYTHONPATH set, so
# `education_system` isn't importable. Walk up from this file until we
# find the dir that contains the `education_system` package and put
# that on sys.path. No-op when imported normally.
if "education_system" not in sys.modules:
    _here = os.path.abspath(os.path.dirname(__file__))
    while _here and not os.path.isdir(os.path.join(_here, "education_system")):
        _parent = os.path.dirname(_here)
        if _parent == _here:
            break
        _here = _parent
    if _here and _here not in sys.path:
        sys.path.insert(0, _here)


logger = logging.getLogger(__name__)

try:
    from education_system.systems.university.infrastructure.logging.log_config import (
        configure_logging,
    )

    configure_logging(name=__name__)
except Exception:
    logger.debug("Central log config unavailable; falling back to default handlers", exc_info=True)

_LEGACY_DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "safeguarding.db")
_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
try:
    from education_system.paths import VAR_DIR
    from education_system.platform.governance.security.secrets import (
        DevelopmentFileSecretProvider,
    )

    _SAFEGUARDING_RUNTIME_DIR = os.fspath(VAR_DIR / "data" / "university" / "safeguarding")
    _DEFAULT_KEY_FILE = os.fspath(
        DevelopmentFileSecretProvider(
            VAR_DIR / "data" / "university" / "safeguarding" / "secrets"
        ).path_for("safeguard.key")
    )
except ImportError:
    # Direct-script compatibility. Resolve outside the package tree even when
    # the shared path module is unavailable.
    _SAFEGUARDING_RUNTIME_DIR = os.path.abspath(
        os.path.join(
            _MODULE_DIR,
            "..", "..", "..", "..", "..", "..",
            "var", "data", "university", "safeguarding",
        )
    )
    _DEFAULT_KEY_FILE = os.path.join(
        _SAFEGUARDING_RUNTIME_DIR, "secrets", "safeguard.key"
    )

_SAFEGUARDING_RUNTIME_DIR = os.environ.get(
    "EDUCATION_SAFEGUARDING_DATA_DIR",
    _SAFEGUARDING_RUNTIME_DIR,
)
_SECURE_DIR = os.path.join(_SAFEGUARDING_RUNTIME_DIR, "secure_uploads")
_KEY_FILE = os.environ.get(
    "EDUCATION_SAFEGUARDING_KEY_FILE",
    _DEFAULT_KEY_FILE,
)
_DRAFT_DIR = os.path.join(_SAFEGUARDING_RUNTIME_DIR, "drafts")
SUPPORT_RESOURCES = """If you are struggling right now, please reach out:

  • Samaritans (UK)   116 123  — free, 24/7
  • Nightline (student peer support)  — nightline.ac.uk
  • University Wellbeing Service      — contact via portal
  • Emergency services                — 999 / 112

You are not alone. Speaking to someone can help."""

__all__ = [
    "_LEGACY_DB_FILE",
    "_MODULE_DIR",
    "_SAFEGUARDING_RUNTIME_DIR",
    "_SECURE_DIR",
    "_KEY_FILE",
    "_DRAFT_DIR",
    "SUPPORT_RESOURCES",
]
