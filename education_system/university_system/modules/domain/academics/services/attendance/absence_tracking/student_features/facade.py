"""Split from student_features.py — see package __init__.py for public API."""
from __future__ import annotations

import calendar
import csv
import functools
import json
import logging
import sqlite3
import tkinter as tk
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any, Callable, Iterable, Optional

from education_system.university_system.modules.domain.academics.services.attendance.absence_tracking.admin_features import (
    safe, audit, _combo_dialog, _show_table, _export_rows_to_csv,
    _get_setting, _set_setting, ensure_support_tables,
    pick_date, pick_date_range,
)

try:
    from education_system.university_system.infrastructure.logging.log_config import configure_logging
    logger = configure_logging(name="absence_tracker.student")
except Exception:
    logger = logging.getLogger("absence_tracker.student")
    if not logger.handlers:
        logger.addHandler(logging.StreamHandler())
        logger.setLevel(logging.INFO)

from .context import StudentContext
from .prefs import StudentPrefs
from .widgets.module_picker import ModulePicker
from .services import (
    AttendanceVisibilityService, RequestService, NotificationService,
    PlanningService, SupportService, SocialService, AppealsService,
    IntegrationsService, CustomisationService,
)

@dataclass
class StudentServices:
    """Aggregates every service the Student Tools tab needs."""
    visibility: AttendanceVisibilityService
    requests: RequestService
    notifications: NotificationService
    planning: PlanningService
    support: SupportService
    social: SocialService
    appeals: AppealsService
    integrations: IntegrationsService
    customisation: CustomisationService

    @classmethod
    def for_context(cls, ctx: StudentContext) -> "StudentServices":
        prefs = StudentPrefs(ctx.db)
        picker = ModulePicker(ctx)
        return cls(
            visibility    = AttendanceVisibilityService(ctx, prefs),
            requests      = RequestService(ctx, prefs, picker),
            notifications = NotificationService(ctx, prefs),
            planning      = PlanningService(ctx, picker),
            support       = SupportService(ctx, picker),
            social        = SocialService(ctx, picker),
            appeals       = AppealsService(ctx),
            integrations  = IntegrationsService(ctx),
            customisation = CustomisationService(ctx, prefs),
        )
