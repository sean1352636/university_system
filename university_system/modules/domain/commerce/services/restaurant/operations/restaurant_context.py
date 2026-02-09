"""Shared imports and globals for restaurant operations helpers."""

from __future__ import annotations

import csv
import hashlib
import logging
import os
import qrcode
import random
import re
import smtplib
from university_system.infrastructure.database.db import sqlite3
import threading
import time
import warnings
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import matplotlib.pyplot as plt
import pandas as pd
from PIL import Image
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from university_system.infrastructure.auth import UserAuth, display_auth_menu
from university_system.infrastructure.database.data_backup import backup_before_operation, display_backup_menu
from university_system.infrastructure.database.db import DatabaseManager, get_connection as get_db_connection
from university_system.infrastructure.email import send_confirmation_email
from university_system.utils.logging.log_config import configure_logging
# Import get_log_file helper for audit logging.
from university_system.utils.logging.log_config import get_log_file

log_path = get_log_file("restaurant_system.log")
os.makedirs(os.path.dirname(log_path), exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(log_path), logging.StreamHandler()],
)

logger = configure_logging(name=__name__)
warnings.filterwarnings("ignore")

from university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
DATABASE_FILE = str(DEFAULT_DB_PATH)

# Use centralized auth management
from university_system.infrastructure.shared_context import (
    get_auth,
    set_auth as set_global_auth,
    get_current_user,
    check_permission,
)

# Backward compatibility - get auth instance
auth: UserAuth | None = get_auth()

# Helper functions for cross-module dependencies
def init_db():
    """Initialize the database."""
    from . import connection
    return connection.init_db()

def set_auth(auth_instance):
    """Set the global auth instance."""
    global auth
    auth = auth_instance
    set_global_auth(auth_instance)

def display_main_menu(auth_obj):
    """Display the main menu."""
    from . import connection
    return connection.display_main_menu(auth_obj)

def expense_analytics():
    """Show expense analytics."""
    from . import exports
    return exports.expense_analytics()

def export_expense_report():
    """Export expense report."""
    from . import exports
    return exports.export_expense_report()

def analyze_query_performance():
    """Analyze query performance."""
    from . import maintenance
    return maintenance.analyze_query_performance()

def optimize_table_structure():
    """Optimize table structure."""
    from . import maintenance
    return maintenance.optimize_table_structure()

def export_payroll_report():
    """Export payroll report."""
    from . import exports
    return exports.export_payroll_report()

def user_management():
    """Manage users."""
    from . import users
    return users.user_management()

def system_maintenance():
    """System maintenance."""
    from . import maintenance
    return maintenance.system_maintenance()

def view_audit_logs():
    """View audit logs."""
    from . import audit
    return audit.view_audit_logs()

def manage_notifications():
    """Manage notifications."""
    from . import notifications
    return notifications.manage_notifications()

def system_backup():
    """System backup."""
    from . import backup
    return backup.system_backup()

def database_optimization():
    """Database optimization."""
    from . import maintenance
    return maintenance.database_optimization()

def view_user_activity_logs():
    """View user activity logs."""
    from . import audit
    return audit.view_user_activity_logs()
