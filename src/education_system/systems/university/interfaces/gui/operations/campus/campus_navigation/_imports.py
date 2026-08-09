"""Shared imports for Campus Navigation GUI modules."""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from typing import Optional, Dict, List
import math

from education_system.systems.university.domain.operations.campus.campus_navigation.services.navigation_service import (
    NavigationService
)
from education_system.systems.university.infrastructure.shared_context import get_auth
from education_system.systems.university.infrastructure.i18n import get_text as get_translation

_t = get_translation
