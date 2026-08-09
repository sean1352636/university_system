"""Shared imports and module state for the split implementation."""

import tkinter as tk

from tkinter import ttk, messagebox, scrolledtext

from datetime import datetime

from typing import Optional

import threading

from education_system.systems.university.infrastructure.auth import UserAuth

from education_system.systems.university.infrastructure.i18n import get_text as _, init_i18n

init_i18n()

from education_system.systems.university.domain.academics.services.degree_audit.degree_audit_core import (
    DegreeProgramManager,
    DegreeProgressManager,
    WhatIfScenarioManager,
    AdvisingAppointmentManager,
    GraduationAuditManager
)

from education_system.systems.university.domain.academics.services.degree_audit.db_schema import initialize_degree_audit_database

from education_system.systems.university.infrastructure.database.db import get_connection

from education_system.systems.university.infrastructure.activity_logger import log_activity

__all__ = ['DegreeAuditGUI', 'launch_degree_audit_gui']

__all__ = [name for name in globals() if not name.startswith("__") and name != "__all__"]
