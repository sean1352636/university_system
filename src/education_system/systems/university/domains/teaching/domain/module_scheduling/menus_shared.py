"""Shared imports and module state for the split implementation."""

from education_system.systems.university.infrastructure.database.db import get_connection

from education_system.systems.university.infrastructure.i18n import get_text

from education_system.systems.university.infrastructure.utils.language_selector import display_language_menu_option

from education_system import paths

from education_system.systems.university.domains.teaching.domain.module_scheduling.constants import DAYS_OF_WEEK, TIME_SLOTS, SESSION_TYPES, ROOM_TYPES

from education_system.systems.university.domains.teaching.domain.module_scheduling.core import ModuleScheduler

import os

from datetime import datetime

try:
    from education_system.systems.university.services.feature_gui_factory import create_gui_launcher

    launch_timetable_optimizer_gui = create_gui_launcher(
        title="Smart Timetable Optimizer",
        description="""AI-powered class scheduling with conflict detection and optimization.

Features:
• Smart scheduling algorithm
• Room allocation optimization
• Instructor workload balancing
• Student preference integration
• Conflict detection & resolution
• Visual timetable display
• Template management
• Batch import/export
• Analytics & reports
• Holiday management
• Calendar integration (iCal)
• Notification system
• Data validation
• Backup & restore""",
        cli_instruction="Use CLI: Smart Timetable Optimizer"
    )
except ImportError:
    # Fallback if factory not available
    def launch_timetable_optimizer_gui(root, auth):
        from tkinter import messagebox
        messagebox.showinfo("Timetable Optimizer", "Please use the CLI: Enhanced Module Scheduling System")

__all__ = [name for name in globals() if not name.startswith("__") and name != "__all__"]
