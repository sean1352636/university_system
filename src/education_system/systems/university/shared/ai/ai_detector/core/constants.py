"""Shared names for the AI detector: the logger, the database path and which
optional libraries are installed.

Availability is checked with ``importlib.util.find_spec`` — nothing heavy
(torch, transformers, spaCy, OpenCV, scikit-learn) is imported here, so
opening the detector or taking a reading does not pay for libraries a
feature may never use. Each feature imports what it needs when it runs.
"""

import importlib.util

# Configure logging first using the centralized logging config
from education_system.systems.university.infrastructure.logging.log_config import configure_logging

logger = configure_logging(name="ai_detector")

from education_system.systems.university.infrastructure.database.db import sqlite3, DatabaseManager  # noqa: E402,F401
from education_system.paths import UNIVERSITY_DEFAULT_DB_PATH  # noqa: E402

# Re-exported under its historic unprefixed name — ai_detector modules import
# DEFAULT_DB_PATH from here (see detector/database_mixin.py).
DEFAULT_DB_PATH = UNIVERSITY_DEFAULT_DB_PATH


def _installed(*modules) -> bool:
    try:
        return all(importlib.util.find_spec(m) is not None for m in modules)
    except (ImportError, ValueError):
        return False


REQUESTS_AVAILABLE = _installed("requests")
ML_AVAILABLE = _installed("numpy", "sklearn")
LANG_DETECT_AVAILABLE = _installed("langdetect")
SPACY_AVAILABLE = _installed("spacy")
TRANSFORMERS_AVAILABLE = _installed("transformers", "torch")
OCR_AVAILABLE = _installed("PIL", "pytesseract")
OPENCV_AVAILABLE = _installed("cv2")
