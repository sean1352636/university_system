"""
Shared imports and feature flags for the Activity Logger GUI.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import threading
import time
import json
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import queue
import webbrowser
from pathlib import Path

# Import matplotlib for charts
try:
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    import matplotlib.dates as mdates
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("Matplotlib not available. Charts will be disabled.")

# Import the original logger (ensure backward compatibility)
try:
    from education_system.post_18.university_system.modules.shared.utils.simple_activity_logger import (
        EnhancedActivityLogger, LogLevel, SecurityLevel, OutputFormat,
        logger, plugin_manager, create_default_config,
        SlackNotificationPlugin, MetricsCollectionPlugin,
        EmailNotificationPlugin, AuditTrailPlugin,
        log_activity, log_login, log_logout
    )
    LOGGER_AVAILABLE = True
except ImportError:
    LOGGER_AVAILABLE = False
    print("Warning: simple_activity_logger module not found. GUI will run in demo mode.")

# Import i18n for internationalization
try:
    from education_system.post_18.university_system.core.i18n import (
        get_text as _t,
        init_i18n,
        get_current_language,
        get_current_language_name
    )
    from education_system.post_18.university_system.modules.shared.utils.gui_language_selector import show_gui_language_selector
    I18N_AVAILABLE = True
except ImportError:
    I18N_AVAILABLE = False
    def _t(key, **kwargs):
        """Fallback translation function"""
        return key.split('.')[-1].replace('_', ' ').title()
    def get_current_language():
        return 'en'
    def get_current_language_name():
        return 'English'
    def init_i18n(lang):
        pass
    def show_gui_language_selector(parent):
        pass
    print("Warning: i18n module not found. GUI will run in English only.")
