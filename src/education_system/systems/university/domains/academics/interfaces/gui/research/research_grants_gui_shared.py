"""Shared imports and module state for the split implementation."""

import tkinter as tk

from tkinter import ttk, messagebox, scrolledtext

from datetime import datetime

from typing import Optional

import random

import string

from education_system.systems.university.infrastructure.database.db import get_connection, transaction

from education_system.systems.university.infrastructure.shared_context import get_auth

from education_system.systems.university.infrastructure.activity_logger import log_activity

from education_system.systems.university.domains.academics.domain.research.services.research_grants_core import (
    ResearchProjectManager,
    GrantApplicationManager,
    PublicationManager,
    MilestoneManager,
    EquipmentManager,
    EthicsReviewManager
)

from education_system.systems.university.infrastructure.i18n import (
    get_text as _, init_i18n, get_current_language, get_current_language_name
)

from education_system.systems.university.infrastructure.utils.gui_language_selector import show_gui_language_selector

init_i18n()

__all__ = ['ResearchGrantsGUI', 'launch_research_grants_gui']

__all__ = [name for name in globals() if not name.startswith("__") and name != "__all__"]
