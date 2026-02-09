from university_system.infrastructure.database.db import sqlite3, DatabaseManager, get_connection as get_db_conn
from university_system.infrastructure.shared_context import get_auth
import os
import re
import csv
import pandas as pd
import random
import json
import qrcode
import requests
from datetime import datetime, timedelta
from university_system.modules.shared.constants.paths import QR_CODES_DIR, BACKUP_DIR
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from university_system.infrastructure.email import (
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
from university_system.utils.logging.log_config import configure_logging

# CONSOLIDATED DATABASE FILE - Using the same database as main system
from university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
from university_system.modules.shared.utils.finance_integration import record_payment_to_finance
from university_system.modules.shared.utils.i18n import (
    get_text,
    get_current_language,
)
from university_system.modules.shared.utils.language_selector import (
    display_language_menu_option,
)
DATABASE_FILE = str(DEFAULT_DB_PATH)

# Configure logging
logger = configure_logging(name=__name__)

def rate_and_review_book(book_id: str = None):
    """Rate and review a book"""
    auth = get_auth()

    if not auth or not auth.current_user:
        print(get_text("auth.login_required", action=get_text("review.title")))
        return
    
    conn = get_db_connection()
    if not conn:
        return
        
    cursor = conn.cursor()
    
    try:
        if book_id is None:
            book_id = input(get_text("review.enter_book_id") + ": ").strip()

        # Check if book exists
        cursor.execute('SELECT title, author FROM books WHERE book_id = ?', (book_id,))
        book = cursor.fetchone()

        if not book:
            print(get_text("review.not_found", book_id=book_id))
            conn.close()
            return
        
        title, author = book
        # FIXED: Use the helper function to get user_id safely
        user_id = get_current_user_id()
                
        # Check if user has already reviewed this book
        cursor.execute('''
        SELECT review_id, rating, review_text FROM book_reviews 
        WHERE book_id = ? AND user_id = ?
        ''', (book_id, user_id))
        
        existing_review = cursor.fetchone()
        
        if existing_review:
            print(get_text("review.already_reviewed", rating=existing_review[1]))
            update = input(get_text("review.update_prompt") + " " + get_text("common.yes_no_prompt") + ": ").strip().lower()
            if update != 'y':
                conn.close()
                return
        
        print("\n" + get_text("review.reviewing", title=title, author=author))

        # Get rating
        while True:
            try:
                rating = int(input(get_text("review.enter_rating") + ": ").strip())
                if 1 <= rating <= 5:
                    break
                print(get_text("review.rating_range_error"))
            except ValueError:
                print(get_text("review.rating_invalid"))
        
        # Get review text
        review_text = input(get_text("review.enter_review") + ": ").strip()

        # Moderate review text
        if review_text:
            moderation_result = moderate_review_content(review_text)
            if not moderation_result['approved']:
                print(get_text("review.inappropriate_content", reason=moderation_result['reason']))
                review_text = input(get_text("review.enter_revised") + ": ").strip()
        
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        if existing_review:
            # Update existing review
            cursor.execute('''
            UPDATE book_reviews
            SET rating = ?, review_text = ?, review_date = ?, status = 'pending'
            WHERE review_id = ?
            ''', (rating, review_text, now, existing_review[0]))

            print("✅ " + get_text("review.review_updated"))
        else:
            # Create new review
            cursor.execute('''
            INSERT INTO book_reviews 
            (book_id, user_id, rating, review_text, review_date, status)
            VALUES (?, ?, ?, ?, ?, 'pending')
            ''', (book_id, user_id, rating, review_text, now))
            
            review_id = cursor.lastrowid
            print("✅ " + get_text("review.review_submitted"))
            
            # Award points for reviewing
            cursor.execute('''
            INSERT INTO user_achievements 
            (user_id, achievement_type, achievement_name, description, earned_date, points)
            VALUES (?, 'review', 'Book Reviewer', 'Submitted a book review', ?, 5)
            ''', (user_id, now))
        
        conn.commit()
        
        # Check if review moderation is enabled
        cursor.execute('SELECT setting_value FROM library_settings WHERE setting_name = "review_moderation"')
        moderation_enabled = cursor.fetchone()[0].lower() == 'true'
        
        if moderation_enabled:
            print(get_text("review.pending_moderation"))
        else:
            # Auto-approve if moderation is disabled
            if not existing_review:
                cursor.execute('''
                UPDATE book_reviews SET status = 'approved' 
                WHERE review_id = ?
                ''', (review_id,))
                conn.commit()
            print(get_text("review.review_visible"))

    except sqlite3.Error as e:
        conn.rollback()
        print(get_text("review.error", error=str(e)))
    
    conn.close()


def moderate_review_content(text: str) -> Dict:
    """Simple content moderation for reviews"""
    inappropriate_words = [
        'spam', 'fake', 'scam', 'inappropriate', 'offensive'
        # Add more as needed
    ]
    
    text_lower = text.lower()
    
    for word in inappropriate_words:
        if word in text_lower:
            return {
                'approved': False,
                'reason': f'Contains inappropriate word: {word}'
            }
    
    # Check for excessive caps
    if len([c for c in text if c.isupper()]) > len(text) * 0.7:
        return {
            'approved': False,
            'reason': 'Excessive use of capital letters'
        }
    
    return {'approved': True, 'reason': 'Content approved'}


