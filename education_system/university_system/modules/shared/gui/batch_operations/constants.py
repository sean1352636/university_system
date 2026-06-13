"""
Batch Operations GUI - Constants and Shared Imports

All shared imports and configuration constants used across
the batch_operations package.
"""

from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH  # injected
# Standard library imports
import os
DEFAULT_BATCH_DB = os.environ.get('BATCHDEFAULT_DB_PATH', str(DEFAULT_DB_PATH))

import csv
import datetime
import re
import json
import shutil
import time
import threading
import zipfile
import logging
import pickle
import random
from io import StringIO
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any, Callable
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor

# Import path constants
from education_system.university_system.core.paths import DATA_DIR, BACKUP_DIR

# Configuration file paths
GUI_SETTINGS_PATH = DATA_DIR / "gui_settings.json"
EXTERNAL_DB_CONFIG_PATH = DATA_DIR / "external_db_config.json"
EXTERNAL_API_CONFIG_PATH = DATA_DIR / "external_api_config.json"
IMPORT_HISTORY_PATH = DATA_DIR / "import_history.json"

# GUI imports
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from tkinter.ttk import Progressbar, Notebook
import queue

# Third-party imports
import pandas as pd
import hashlib
import schedule
import requests
from flask import Flask, request, jsonify
from fuzzywuzzy import fuzz

# i18n support
from education_system.university_system.core.i18n import get_text as _t

# Configure logging first, before other application imports
from education_system.university_system.infrastructure.logging.log_config import configure_logging, get_log_file

# Setup logging
log_path = get_log_file("modules_system.log")
os.makedirs(os.path.dirname(log_path), exist_ok=True)

# Use only configure_logging, not both basicConfig and configure_logging
logger = configure_logging(name=__name__)

# Application imports (after logging is configured)
from education_system.university_system.infrastructure.database.db import sqlite3, DatabaseManager, ensure_parent_dir
from education_system.university_system.modules.domain.academics.services.modules import (
    compulsory_module_1,
    compulsory_module_2,
    optional_module_1,
    optional_module_2,
    optional_module_3,
    optional_module_4,
    CS_optional_module_1,
    CS_optional_module_2,
    CS_optional_module_3,
    CS_optional_module_4,
    DS_optional_module_1,
    DS_optional_module_2,
    DS_optional_module_3,
    DS_optional_module_4,
)
