"""Constants, imports, and configuration for the enhanced reporting GUI.

This module centralises the shared state that was previously scattered
across the top of ``core.py``.  Every other standalone or mixin module
should import from here rather than duplicating the setup.
"""

from education_system.systems.university.infrastructure.database.db import sqlite3, get_connection
from education_system.systems.university.infrastructure import paths
import logging
import hashlib
import pickle
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import time
import schedule
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from tkinter.scrolledtext import ScrolledText
import threading
import webbrowser
import os
from datetime import datetime, timedelta
import json

# Import i18n module for internationalization
from education_system.systems.university.infrastructure.i18n import (
    init_i18n,
    get_text as _t,
    set_language,
    get_current_language,
    get_current_language_name,
    get_available_languages,
    get_available_language_list,
)
from education_system.systems.university.infrastructure.utils.gui_language_selector import (
    show_gui_language_selector,
    create_language_menu_button,
)

try:
    import pandas as pd
except ImportError:
    pd = None
    logging.warning("Pandas not available, some features will be limited")

# Use centralized path configuration
DB_PATH = str(paths.DEFAULT_DB_PATH)
DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH

# Configure logger for this module
logger = logging.getLogger(__name__)


def get_db_connection():
    """Get database connection using the centralized connection function"""
    try:
        conn = get_connection()
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        logging.error(f"Database connection error: {e}")
        return None


# Import existing functionality (backward compatible)
try:
    from education_system.systems.university.services.analytics.enhanced_reporting import (
        AdvancedScheduledReport, AdvancedVisualization, CacheManager,
        DataQualityMonitor, PredictiveAnalytics, ReportTemplate, SystemConfig,
        CONFIG as _SERVICE_CONFIG, cleanup_old_reports, create_advanced_visualization,
        create_enhanced_bar_chart, create_enhanced_data_table,
        create_enhanced_line_chart, create_enhanced_pie_chart,
        create_interactive_chart, create_standard_chart,
        delete_template_from_db, display_enhanced_reporting_menu,
        generate_enhanced_excel_report, generate_enhanced_pdf_report,
        generate_enhanced_section, generate_interactive_report,
        generate_predictions_section, generate_quality_section, generate_report,
        generate_statistical_summary, get_benchmark_data, get_correlation_data,
        get_original_section_data_complete, get_section_dataframe, get_template,
        get_trend_data, load_scheduled_reports, load_templates,
        run_system_maintenance, save_scheduled_reports, save_template,
        save_template_dict, serialize_dataframe, show_performance_monitor,
        start_scheduler
    )
    ENHANCED_AVAILABLE = True
except ImportError:
    ENHANCED_AVAILABLE = False
    _SERVICE_CONFIG = {}
    print("Enhanced reporting not available, using basic functionality")


# Local CONFIG dict — falls back to empty when enhanced is not available
CONFIG = {
    'database': DB_PATH,
    'reports_dir': str(paths.REPORTS_DIR),
    'templates_dir': str(paths.REPORT_TEMPLATES_DIR),
    'cache_dir': str(paths.REPORT_CACHE_DIR),
    'email': {
        'enabled': False,
        'smtp_server': 'localhost',
        'smtp_port': 587,
        'use_tls': True,
        'from_address': 'reports@company.com'
    }
} if ENHANCED_AVAILABLE else {}

# Set up logging


def get_log_file(filename):
    """Get path to log file"""
    return str(paths.LOG_DIR / filename)
