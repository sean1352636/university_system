"""Shared imports and module state for the split implementation."""

from __future__ import annotations

import json

from datetime import datetime, timedelta, date

from typing import Any, Dict, List, Optional, Tuple

from education_system.systems.university.infrastructure.database.db import get_connection

from education_system.systems.university.services.feature_gui_factory import create_gui_launcher

from education_system.systems.university.infrastructure.i18n import (
    get_text as _t,
    get_current_language,
)

from education_system.systems.university.infrastructure.utils.language_selector import (
    display_language_menu_option,
)

try:
    from education_system.systems.university.infrastructure.email.email_service import send_email
    from education_system.systems.university.infrastructure.email.template_utils import render_template
    HAS_EMAIL = True
except ImportError:
    HAS_EMAIL = False
    def send_email(*args, **kwargs):
        print(_t("early_warning.messages.email_not_available", default="Email would be sent (email service not available)"))
    def render_template(template_name, vars):
        return f"Template: {template_name}", "Email body would be here"

__all__ = [
    'RiskAssessmentManager',
    'IndicatorManager',
    'InterventionManager',
    'CoachingManager',
    'TutoringManager',
    'display_early_warning_menu',
    'launch_early_warning_gui',
]

__all__ = [name for name in globals() if not name.startswith("__") and name != "__all__"]
