"""Split from staff_features.py — see package __init__.py for public API."""
from __future__ import annotations

import json
import logging
import secrets
import sqlite3
import tkinter as tk
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any, Callable, Iterable, Optional

from education_system.systems.university.domain.academics.services.attendance.absence_tracking.admin_features import (
    safe, audit, _combo_dialog, _show_table, _export_rows_to_csv,
    _get_setting, _set_setting, ensure_support_tables,
    pick_date, pick_date_range,
)

try:
    from education_system.systems.university.infrastructure.logging.log_config import configure_logging
    logger = configure_logging(name="absence_tracker.staff")
except Exception:
    logger = logging.getLogger("absence_tracker.staff")
    if not logger.handlers:
        logger.addHandler(logging.StreamHandler())
        logger.setLevel(logging.INFO)

from .context import StaffContext
from .prefs import StaffPrefs
from .widgets.module_picker import ModulePicker
from .widgets.staff_picker import StaffPicker
from .services import (
    RollCallService, RosterService, RequestReviewService,
    AnalyticsService, CommunicationService, PastoralService,
    AssessmentIntegrationService, CollaborationService,
    ConfigurationService, ProductivityService, LeaveService,
)

@dataclass
class StaffServices:
    """Aggregates every service the Staff Tools tab needs."""
    roll_call: RollCallService
    roster: RosterService
    requests: RequestReviewService
    analytics: AnalyticsService
    communication: CommunicationService
    pastoral: PastoralService
    assessment: AssessmentIntegrationService
    collaboration: CollaborationService
    configuration: ConfigurationService
    productivity: ProductivityService
    leave: LeaveService

    @classmethod
    def for_context(cls, ctx: StaffContext) -> "StaffServices":
        picker = ModulePicker(ctx)
        staff_picker = StaffPicker(ctx)
        return cls(
            roll_call     = RollCallService(ctx, picker, staff_picker),
            roster        = RosterService(ctx, picker),
            requests      = RequestReviewService(ctx),
            analytics     = AnalyticsService(ctx, picker),
            communication = CommunicationService(ctx, picker),
            pastoral      = PastoralService(ctx),
            assessment    = AssessmentIntegrationService(ctx, picker),
            collaboration = CollaborationService(ctx, picker, staff_picker),
            configuration = ConfigurationService(ctx, picker),
            productivity  = ProductivityService(ctx, picker),
            leave         = LeaveService(ctx),
        )
