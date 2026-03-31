"""Shared imports for integration marketplace core modules."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import secrets
import tempfile
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.modules.shared.feature_gui_factory import create_gui_launcher
from education_system.university_system.modules.shared.constants import paths
from education_system.university_system.modules.shared.utils.i18n import get_text, _
from education_system.university_system.core.sql_safety import validate_identifier  # nosec B608

# Try to import optional dependencies
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

try:
    import openpyxl
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False
