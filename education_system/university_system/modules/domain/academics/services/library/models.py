from education_system.university_system.infrastructure.database.db import sqlite3, DatabaseManager, get_connection as get_db_conn
from education_system.university_system.infrastructure.shared_context import get_auth
import os
import re
import csv
import pandas as pd
import random
import json
import qrcode
import requests
from datetime import datetime, timedelta
from education_system.university_system.core.paths import QR_CODES_DIR, BACKUP_DIR
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from education_system.university_system.infrastructure.email import (
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
import matplotlib.pyplot as plt
import seaborn as sns
import shutil
from typing import Any, List, Dict, Optional, Tuple
import logging
from education_system.university_system.infrastructure.logging.log_config import configure_logging

# CONSOLIDATED DATABASE FILE - Using the same database as main system
from education_system.university_system.core.paths import DEFAULT_DB_PATH
from education_system.university_system.modules.shared.utils.finance_integration import record_payment_to_finance
from education_system.university_system.core.i18n import (
    get_text,
    get_current_language,
)
from education_system.university_system.modules.shared.utils.language_selector import (
    display_language_menu_option,
)
DATABASE_FILE = str(DEFAULT_DB_PATH)

# Configure logging
logger = configure_logging(name=__name__)

class Book:
    def __init__(
        self,
        book_id: str,
        title: str,
        author: str,
        isbn: str,
        publisher: str,
        category: str,
        year_published: int,
        description: str,
        location: str,
        status: str,
        added_date: str,
        last_updated: str,
        reading_level: Optional[str] = None,
        tags: Optional[List[str]] = None,
        cover_image_path: Optional[str] = None,
        digital_copy_path: Optional[str] = None,
    ) -> None:
        self.book_id = book_id
        self.title = title
        self.author = author
        self.isbn = isbn
        self.publisher = publisher
        self.category = category
        self.year_published = year_published
        self.description = description
        self.location = location
        self.status = status  # 'available', 'checked_out', 'reserved', 'lost', 'damaged'
        self.added_date = added_date
        self.last_updated = last_updated
        self.reading_level = reading_level
        self.tags = tags or []
        self.cover_image_path = cover_image_path
        self.digital_copy_path = digital_copy_path


class BookLoan:
    def __init__(
        self,
        loan_id: str,
        book_id: str,
        user_id: str,
        checkout_date: str,
        due_date: str,
        return_date: Optional[str],
        status: str,
        fine_amount: float,
        renewal_count: int = 0,
        reading_progress: int = 0,
    ) -> None:
        self.loan_id = loan_id
        self.book_id = book_id
        self.user_id = user_id
        self.checkout_date = checkout_date
        self.due_date = due_date
        self.return_date = return_date
        self.status = status  # 'active', 'returned', 'overdue', 'lost'
        self.fine_amount = fine_amount
        self.renewal_count = renewal_count
        self.reading_progress = reading_progress


class BookReservation:
    def __init__(
        self,
        reservation_id: str,
        book_id: str,
        user_id: str,
        reservation_date: str,
        expiry_date: str,
        status: str,
        priority_order: int = 1,
    ) -> None:
        self.reservation_id = reservation_id
        self.book_id = book_id
        self.user_id = user_id
        self.reservation_date = reservation_date
        self.expiry_date = expiry_date
        self.status = status
        self.priority_order = priority_order


class BookReview:
    def __init__(
        self,
        review_id: str,
        book_id: str,
        user_id: str,
        rating: int,
        review_text: str,
        review_date: str,
        status: str = 'pending',
    ) -> None:
        self.review_id = review_id
        self.book_id = book_id
        self.user_id = user_id
        self.rating = rating
        self.review_text = review_text
        self.review_date = review_date
        self.status = status  # 'pending', 'approved', 'rejected'


class ReadingList:
    def __init__(
        self,
        list_id: str,
        name: str,
        description: str,
        creator_id: str,
        created_date: str,
        is_public: bool = False,
        is_collaborative: bool = False,
    ) -> None:
        self.list_id = list_id
        self.name = name
        self.description = description
        self.creator_id = creator_id
        self.created_date = created_date
        self.is_public = is_public
        self.is_collaborative = is_collaborative


