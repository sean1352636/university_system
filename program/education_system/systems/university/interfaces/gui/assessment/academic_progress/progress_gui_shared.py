"""Shared imports and module state for the split implementation."""

import tkinter as tk

from tkinter import ttk, messagebox, scrolledtext

from datetime import datetime, timedelta

from typing import Optional, Dict, List

import matplotlib

matplotlib.use('TkAgg')

from education_system.systems.university.domain.assessment.academic_progress.services.progress_service import ProgressService

from education_system.systems.university.infrastructure.database.db import get_connection

from education_system.systems.university.infrastructure.shared_context import get_auth

from education_system.systems.university.infrastructure.i18n import get_text as get_translation

try:
    from education_system.systems.university.domain.assessment.grading.grade_calculation import (
        calculate_student_gpa, letter_to_gpa,
    )
except ImportError:
    calculate_student_gpa = None
    letter_to_gpa = None

_t = get_translation

import tkinter.simpledialog

__all__ = [name for name in globals() if not name.startswith("__") and name != "__all__"]
