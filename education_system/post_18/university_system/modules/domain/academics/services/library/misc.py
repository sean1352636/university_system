from education_system.post_18.university_system.infrastructure.database.db import sqlite3, DatabaseManager, get_connection as get_db_conn
from education_system.post_18.university_system.infrastructure.shared_context import get_auth
import os
import re
import csv
import random
import json
import requests
from datetime import datetime, timedelta
from education_system.post_18.university_system.core.paths import QR_CODES_DIR, BACKUP_DIR
from education_system.post_18.university_system.infrastructure.email import (
    send_book_checkout_confirmation,
    send_book_return_reminder,
    send_overdue_notification,
)
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import hashlib
import uuid
from collections import defaultdict
import shutil
from typing import Any, List, Dict, Optional, Tuple
import logging
from education_system.post_18.university_system.infrastructure.logging.log_config import configure_logging

# CONSOLIDATED DATABASE FILE - Using the same database as main system
from education_system.post_18.university_system.core.paths import DEFAULT_DB_PATH
from education_system.post_18.university_system.modules.shared.utils.finance_integration import record_payment_to_finance
from education_system.post_18.university_system.core.i18n import (
    get_text,
    get_current_language,
)
from education_system.post_18.university_system.modules.shared.utils.language_selector import (
    display_language_menu_option,
)
from education_system.post_18.university_system.modules.domain.academics.services.library.database import repair_database, init_library_db
DATABASE_FILE = str(DEFAULT_DB_PATH)

# Configure logging
logger = configure_logging(name=__name__)

if __name__ == "__main__":
    # First verify and repair database if needed
    if repair_database():
        print(get_text("library.db_ready"))
    else:
        print(get_text("library.db_repair_failed"))
    # Initialize the enhanced library database
    init_library_db()
