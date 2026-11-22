# Auto-generated module (split from student_crud_gui.py)
import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import logging
import random
import secrets
import json
import csv
from education_system.systems.university.infrastructure.database.db import sqlite3
from datetime import datetime
from education_system.platform.delivery.gui.tk_callback_filter import install_clean_close as _install_clean_close

from education_system.systems.university.infrastructure.i18n import get_text as _t
from education_system.systems.university.infrastructure.database.db import get_db_connection, get_connection, transaction
from education_system.systems.university.infrastructure.sql_safety import (
    validate_table_name,
    validate_column_name,
    SQLIdentifierError,
)

logger = logging.getLogger("education_system.systems.university.domains.learners.interfaces.gui.students.student_crud_gui")

try:
    from education_system.systems.university.infrastructure.activity_logger import log_activity
    ACTIVITY_LOGGER_AVAILABLE = True
except ImportError:
    ACTIVITY_LOGGER_AVAILABLE = False

def _create_visa_record_for_new_student(student_id, email_address, first_name,
                                         nationality, passport_number,
                                         visa_expiry_date, brp_number, module_codes,
                                         details=None):
    """Kept for existing imports; the logic is front-end agnostic now
    (``services/student_provisioning.create_visa_record``) so the CLI can
    use it without tkinter."""
    from education_system.systems.university.services.student_provisioning import (
        create_visa_record,
    )
    create_visa_record(student_id, email_address, first_name, nationality, passport_number,
                       visa_expiry_date, brp_number, module_codes, details=details)
