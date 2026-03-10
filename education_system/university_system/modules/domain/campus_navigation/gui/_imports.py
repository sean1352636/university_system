"""Shared imports for Campus Navigation GUI modules."""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from typing import Optional, Dict, List
import math

from education_system.university_system.modules.domain.campus_navigation.services.navigation_service import (
    NavigationService
)
from education_system.university_system.infrastructure.shared_context import get_auth
from education_system.university_system.infrastructure.localization import get_translation

_t = get_translation
