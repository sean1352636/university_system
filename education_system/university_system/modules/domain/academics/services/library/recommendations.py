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
from education_system.university_system.modules.shared.constants.paths import QR_CODES_DIR, BACKUP_DIR
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
from education_system.university_system.utils.logging.log_config import configure_logging

# CONSOLIDATED DATABASE FILE - Using the same database as main system
from education_system.university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
from education_system.university_system.modules.shared.utils.finance_integration import record_payment_to_finance
from education_system.university_system.modules.shared.utils.i18n import (
    get_text,
    get_current_language,
)
from education_system.university_system.modules.shared.utils.language_selector import (
    display_language_menu_option,
)
DATABASE_FILE = str(DEFAULT_DB_PATH)

# Configure logging
logger = configure_logging(name=__name__)

def get_similar_books(book_id: str, category: str, author: str, limit: int = 5) -> List:
    """Get similar books based on category and author"""
    try:
        conn = get_db_connection()
        if not conn:
            return []

        cursor = conn.cursor()

        # Find books by same author or in same category
        cursor.execute('''
        SELECT book_id, title, author, category,
               CASE
                   WHEN author = ? THEN 2
                   WHEN category = ? THEN 1
                   ELSE 0
               END as similarity_score
        FROM books
        WHERE book_id != ? AND (author = ? OR category = ?)
        ORDER BY similarity_score DESC, title
        LIMIT ?
        ''', (author, category, book_id, author, category, limit))

        similar_books = cursor.fetchall()
        conn.close()

        return similar_books

    except sqlite3.Error as e:
        logging.error(f"Error getting similar books: {e}")
        return []


def get_book_recommendations(user_id: str, limit: int = 10) -> List:
    """Generate personalized book recommendations"""
    try:
        conn = get_db_connection()
        if not conn:
            return []

        cursor = conn.cursor()

        # Get user's borrowing history
        cursor.execute('''
        SELECT DISTINCT b.category, b.author
        FROM book_loans bl
        JOIN books b ON bl.book_id = b.book_id
        WHERE bl.user_id = ?
        ''', (user_id,))

        user_history = cursor.fetchall()

        if not user_history:
            # No history, recommend popular books
            cursor.execute('''
            SELECT b.book_id, b.title, b.author, b.category, b.status,
                   COUNT(bl.loan_id) as loan_count
            FROM books b
            LEFT JOIN book_loans bl ON b.book_id = bl.book_id
            WHERE b.status = 'available'
            GROUP BY b.book_id
            ORDER BY loan_count DESC, b.title
            LIMIT ?
            ''', (limit,))
        else:
            # Recommend based on preferences
            categories = [item[0] for item in user_history]
            authors = [item[1] for item in user_history]

            # Build recommendation query
            category_conditions = " OR ".join(["b.category = ?" for _ in categories])
            author_conditions = " OR ".join(["b.author = ?" for _ in authors])

            query = f'''
            SELECT DISTINCT b.book_id, b.title, b.author, b.category, b.status,
                   CASE
                       WHEN {author_conditions} THEN 2
                       WHEN {category_conditions} THEN 1
                       ELSE 0
                   END as recommendation_score
            FROM books b
            LEFT JOIN book_loans bl ON b.book_id = bl.book_id
            WHERE b.book_id NOT IN (
                SELECT DISTINCT book_id FROM book_loans WHERE user_id = ?
            ) AND b.status = 'available'
            ORDER BY recommendation_score DESC, b.title
            LIMIT ?
            '''

            params = authors + categories + [user_id, limit]
            cursor.execute(query, params)

        recommendations = cursor.fetchall()

        # Store recommendations in database for tracking
        for rec in recommendations:
            cursor.execute('''
            INSERT OR REPLACE INTO book_recommendations
            (user_id, book_id, recommendation_type, confidence_score, generated_date, status)
            VALUES (?, ?, 'personalized', 0.8, ?, 'pending')
            ''', (user_id, rec[0], datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

        conn.commit()
        conn.close()

        return recommendations

    except sqlite3.Error as e:
        logging.error(f"Error generating recommendations: {e}")
        return []


def train_recommendation_model():
   """Train the book recommendation model"""
   auth = get_auth()

   if not auth or not auth.current_user:
       print("You must be logged in to train recommendation model.")
       return

   if not auth.check_permission('system_config'):
       print("You don't have permission to train recommendation model.")
       return

   print("\nTraining Recommendation Model:")
   print("=============================")

   conn = get_db_connection()
   if not conn:
       return

   cursor = conn.cursor()

   try:
       # Analyze user borrowing patterns
       cursor.execute('''
       SELECT user_id, book_id, reading_progress,
              CASE WHEN return_date IS NOT NULL THEN 1 ELSE 0 END as completed
       FROM book_loans
       WHERE checkout_date >= date('now', '-1 year')
       ''')

       user_book_interactions = cursor.fetchall()

       # Analyze book similarities
       cursor.execute('''
       SELECT b1.book_id as book1, b2.book_id as book2,
              CASE WHEN b1.author = b2.author THEN 2 ELSE 0 END +
              CASE WHEN b1.category = b2.category THEN 1 ELSE 0 END +
              CASE WHEN b1.reading_level = b2.reading_level THEN 1 ELSE 0 END as similarity_score
       FROM books b1
       CROSS JOIN books b2
       WHERE b1.book_id != b2.book_id
       AND (b1.author = b2.author OR b1.category = b2.category OR b1.reading_level = b2.reading_level)
       ''')

       book_similarities = cursor.fetchall()

       # Update recommendation scores
       print("Updating recommendation scores...")

       # Clear existing recommendations
       cursor.execute('DELETE FROM book_recommendations')

       # Generate new recommendations based on patterns
       recommendations_generated = 0

       # User-based recommendations
       for user_id, _, _, _ in user_book_interactions:
           # Get user's preferred categories and authors
           cursor.execute('''
           SELECT b.category, b.author, COUNT(*) as frequency
           FROM book_loans bl
           JOIN books b ON bl.book_id = b.book_id
           WHERE bl.user_id = ? AND bl.reading_progress >= 70
           GROUP BY b.category, b.author
           ORDER BY frequency DESC
           LIMIT 5
           ''', (user_id,))

           preferences = cursor.fetchall()

           for category, author, frequency in preferences:
               # Find similar books not yet read by user
               cursor.execute('''
               SELECT book_id FROM books
               WHERE (category = ? OR author = ?)
AND book_id NOT IN (
                   SELECT book_id FROM book_loans WHERE user_id = ?
               )
               AND status = 'available'
               LIMIT 3
               ''', (category, author, user_id))

               recommended_books = cursor.fetchall()

               for (book_id,) in recommended_books:
                   confidence_score = min(0.9, frequency * 0.2)

                   cursor.execute('''
                   INSERT INTO book_recommendations
                   (user_id, book_id, recommendation_type, confidence_score, generated_date, status)
                   VALUES (?, ?, 'user_based', ?, ?, 'pending')
                   ''', (user_id, book_id, confidence_score, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

                   recommendations_generated += 1

       # Item-based recommendations
       for book1, book2, similarity_score in book_similarities:
           if similarity_score >= 2:  # High similarity threshold
               # Find users who liked book1 and recommend book2
               cursor.execute('''
               SELECT DISTINCT user_id FROM book_loans
               WHERE book_id = ? AND reading_progress >= 80
               ''', (book1,))

               users_who_liked = cursor.fetchall()

               for (user_id,) in users_who_liked:
                   # Check if user hasn't read book2
                   cursor.execute('''
                   SELECT COUNT(*) FROM book_loans
                   WHERE user_id = ? AND book_id = ?
                   ''', (user_id, book2))

                   if cursor.fetchone()[0] == 0:
                       confidence_score = similarity_score * 0.3

                       cursor.execute('''
                       INSERT OR IGNORE INTO book_recommendations
                       (user_id, book_id, recommendation_type, confidence_score, generated_date, status)
                       VALUES (?, ?, 'item_based', ?, ?, 'pending')
                       ''', (user_id, book2, confidence_score, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

                       recommendations_generated += 1

       conn.commit()
       conn.close()

       print(f"✅ Recommendation model training completed!")
       print(f"Generated {recommendations_generated} new recommendations")

       log_audit_event(get_current_user_id(),
                      f"Trained recommendation model - generated {recommendations_generated} recommendations",
                      "book_recommendations")

   except sqlite3.Error as e:
       logging.error(f"Error training recommendation model: {e}")
       print(f"Error training model: {e}")
       conn.close()


def update_recommendation_scores():
   """Update recommendation confidence scores based on user feedback"""
   conn = get_db_connection()
   if not conn:
       return

   cursor = conn.cursor()

   try:
       # Update scores based on clicks
       cursor.execute('''
       UPDATE book_recommendations
       SET confidence_score = confidence_score + 0.1
       WHERE clicked = 1 AND confidence_score < 0.9
       ''')

       # Update scores based on actual checkouts
       cursor.execute('''
       UPDATE book_recommendations
       SET confidence_score = confidence_score + 0.3
       WHERE book_id IN (
           SELECT DISTINCT bl.book_id
           FROM book_loans bl
           WHERE bl.user_id = book_recommendations.user_id
           AND bl.checkout_date > book_recommendations.generated_date
       )
       AND confidence_score < 0.9
       ''')

       # Decrease scores for old unclicked recommendations
       cursor.execute('''
       UPDATE book_recommendations
       SET confidence_score = confidence_score - 0.05
       WHERE clicked = 0
       AND generated_date < date('now', '-30 days')
       AND confidence_score > 0.1
       ''')

       # Remove very low confidence recommendations
       cursor.execute('''
       DELETE FROM book_recommendations
       WHERE confidence_score < 0.1
       AND generated_date < date('now', '-60 days')
       ''')

       deleted_count = cursor.rowcount

       conn.commit()
       conn.close()

       print(f"✅ Recommendation scores updated")
       print(f"Removed {deleted_count} low-confidence recommendations")

   except sqlite3.Error as e:
       logging.error(f"Error updating recommendation scores: {e}")
       conn.close()


