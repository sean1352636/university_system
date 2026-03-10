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

def generate_barcode(book_id: str) -> str:
    """Generate a unique barcode for a book"""
    # Simple barcode generation - in production, use proper barcode library
    import hashlib
    hash_object = hashlib.md5(book_id.encode())
    barcode = hash_object.hexdigest()[:12].upper()
    return f"LIB{barcode}"


def generate_qr_code(book_id: str, title: str) -> str:
    """Generate QR code for a book"""
    try:
        # Create QR code data
        qr_data = f"LIBRARY_BOOK:{book_id}:{title}"
        
        # Generate QR code
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(qr_data)
        qr.make(fit=True)
        
        # Create QR code image
        qr_img = qr.make_image(fill_color="black", back_color="white")
        
        # Save QR code
        qr_path = QR_CODES_DIR / f"book_{book_id}.png"
        qr_img.save(str(qr_path))
        
        return qr_path
    except Exception as e:
        logging.error(f"Error generating QR code: {e}")
        return None


def scan_barcode():
   """Handle barcode scanning interface"""
   print("\nBarcode Scanner Interface:")
   print("=========================")
   print("1. Manual barcode entry")
   print("2. Simulate barcode scan")
   print("3. Batch barcode processing")
   print("4. Return to menu")
   
   choice = input("Enter your choice (1-4): ").strip()
   
   if choice == '4':
       return None
   
   try:
       if choice == '1':
           # Manual entry
           barcode = input("Enter barcode: ").strip()
           return process_scanned_barcode(barcode)
       
       elif choice == '2':
           # Simulate scan
           print("Simulating barcode scan...")
           print("In a real implementation, this would interface with barcode scanner hardware")
           barcode = input("Enter simulated barcode data: ").strip()
           return process_scanned_barcode(barcode)
       
       elif choice == '3':
           # Batch processing
           print("Batch barcode processing:")
           barcodes = []
           
           print("Enter barcodes (press Enter on empty line to finish):")
           while True:
               barcode = input("Barcode: ").strip()
               if not barcode:
                   break
               barcodes.append(barcode)
           
           results = []
           for barcode in barcodes:
               result = process_scanned_barcode(barcode)
               results.append(result)
           
           return results
   
   except Exception as e:
       print(f"Error scanning barcode: {e}")
       return None


def process_scanned_barcode(barcode):
   """Process a scanned barcode and return item information"""
   conn = get_db_connection()
   if not conn:
       return None
   
   cursor = conn.cursor()
   
   try:
       # Check if it's a book barcode
       cursor.execute('''
       SELECT book_id, title, author, status 
       FROM books 
       WHERE barcode = ?
       ''', (barcode,))
       
       book = cursor.fetchone()
       
       if book:
           book_id, title, author, status = book
           result = {
               'type': 'book',
               'id': book_id,
               'title': title,
               'author': author,
               'status': status,
               'barcode': barcode
           }
           
           print(f"📚 Book found: {title} by {author}")
           print(f"   ID: {book_id}, Status: {status}")
           
           conn.close()
           return result
       
       # Check if it's a user ID barcode (library card)
       cursor.execute('''
       SELECT student_id, first_name, last_name 
       FROM students 
       WHERE student_id = ? OR student_id = ?
       ''', (barcode, barcode.replace('LIB', '').lstrip('0')))
       
       user = cursor.fetchone()
       
       if user:
           student_id, first_name, last_name = user
           result = {
               'type': 'user',
               'id': student_id,
               'name': f"{first_name} {last_name}",
               'barcode': barcode
           }
           
           print(f"👤 User found: {first_name} {last_name}")
           print(f"   Student ID: {student_id}")
           
           conn.close()
           return result
       
       # Unknown barcode
       print(f"❌ No item found for barcode: {barcode}")
       conn.close()
       return None
       
   except sqlite3.Error as e:
       logging.error(f"Error processing barcode: {e}")
       conn.close()
       return None


def print_barcode_labels(book_ids):
   """Print barcode labels for books"""
   auth = get_auth()

   if not auth or not auth.current_user:
       print("You must be logged in to print labels.")
       return
   
   if not auth.check_permission('manage_books'):
       print("You don't have permission to print labels.")
       return
   
   conn = get_db_connection()
   if not conn:
       return
   
   cursor = conn.cursor()
   
   try:
       # Get book information
       book_data = []
       
       for book_id in book_ids:
           cursor.execute('''
           SELECT book_id, title, author, barcode, category
           FROM books
           WHERE book_id = ?
           ''', (book_id,))
           
           book = cursor.fetchone()
           if book:
               book_data.append(book)
       
       if not book_data:
           print("No valid books found for label printing.")
           return
       
       # Generate label file
       timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
       label_filename = f"barcode_labels_{timestamp}.txt"
       
       with open(label_filename, 'w') as f:
           f.write("LIBRARY BARCODE LABELS\n")
           f.write("=" * 50 + "\n\n")
           
           for book_id, title, author, barcode, category in book_data:
               f.write(f"Book ID: {book_id}\n")
               f.write(f"Title: {title}\n")
               f.write(f"Author: {author}\n")
               f.write(f"Category: {category}\n")
               f.write(f"Barcode: {barcode}\n")
               f.write(f"[{barcode}]")  # Barcode representation
               f.write("\n" + "-" * 30 + "\n\n")
       
       print(f"✅ Barcode labels generated: {label_filename}")
       print(f"Labels created for {len(book_data)} books")
       print("In a real implementation, this would send to a label printer.")
       
       log_audit_event(get_current_user_id(), 
                      f"Generated barcode labels for {len(book_data)} books", 
                      "books")
       
       conn.close()
       
   except Exception as e:
       logging.error(f"Error printing barcode labels: {e}")
       print(f"Error generating labels: {e}")
       conn.close()


def generate_library_cards():
    """Generate library cards for users"""
    auth = get_auth()

    if not auth or not auth.current_user:
        print("You must be logged in to generate library cards.")
        return
    
    if not auth.check_permission('manage_users'):
        print("You don't have permission to generate library cards.")
        return
    
    print("\nLibrary Card Generator:")
    print("======================")
    print("1. Generate card for specific user")
    print("2. Bulk generate cards")
    print("3. Re-generate lost card")
    
    choice = input("Select option (1-3): ").strip()
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if choice == '1':
            # Single user card
            user_id = input("Enter User/Student ID: ").strip()
            
            # Get user information
            cursor.execute('''
            SELECT first_name, last_name, grade_level, email 
            FROM students WHERE student_id = ?
            ''', (user_id,))
            
            user_info = cursor.fetchone()
            
            if not user_info:
                print("User not found.")
                return
            
            first_name, last_name, grade_level, email = user_info
            
            # Generate library card
            card_data = generate_library_card_data(user_id, first_name, last_name, grade_level)
            
            card_filename = f"library_card_{user_id}.png"
            create_library_card_image(card_data, card_filename)
            
            print(f"✅ Library card generated: {card_filename}")
            
        elif choice == '2':
            # Bulk generation
            print("Bulk card generation feature would:")
            print("1. Query all active users")
            print("2. Generate cards for users without them")
            print("3. Create a batch PDF with multiple cards")
            print("4. Track card generation status")
            
            print("This feature requires additional implementation.")
            
        elif choice == '3':
            # Re-generate lost card
            user_id = input("Enter User ID for replacement card: ").strip()
            
            # Mark old card as invalid and generate new one
            print(f"Re-generating library card for {user_id}")
            print("Old card would be marked as invalid in the system.")
            
        conn.close()
        
    except Exception as e:
        print(f"Error generating library cards: {e}")


def generate_library_card_data(user_id: str, first_name: str, last_name: str, grade_level: str) -> Dict:
    """Generate data for library card"""
    card_number = f"LIB{user_id.zfill(6)}"
    issue_date = datetime.now().strftime('%Y-%m-%d')
    expiry_date = (datetime.now() + timedelta(days=365)).strftime('%Y-%m-%d')
    
    return {
        'card_number': card_number,
        'user_id': user_id,
        'full_name': f"{first_name} {last_name}",
        'grade_level': grade_level,
        'issue_date': issue_date,
        'expiry_date': expiry_date,
        'barcode': generate_barcode(user_id),
        'qr_code_data': f"LIBRARY_USER:{user_id}:{card_number}"
    }


def create_library_card_image(card_data: Dict, filename: str):
    """Create library card image using PIL or fallback to text file."""
    try:
        # Try to use PIL for actual image generation
        from PIL import Image, ImageDraw, ImageFont
        import qrcode
        import io
        import base64

        # Card dimensions (3.5" x 2.25" at 300 DPI)
        card_width, card_height = 1050, 675

        # Create a new image with white background
        card = Image.new('RGB', (card_width, card_height), 'white')
        draw = ImageDraw.Draw(card)

        # Define colors
        header_color = (0, 73, 144)  # University blue
        text_color = (0, 0, 0)

        # Draw header background
        draw.rectangle([0, 0, card_width, 120], fill=header_color)

        # Try to load fonts (fallback to default if not available)
        try:
            title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
            name_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
            text_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
        except (OSError, IOError) as e:
            logger.warning(f"Failed to load TrueType fonts, using default: {e}")
            title_font = ImageFont.load_default()
            name_font = ImageFont.load_default()
            text_font = ImageFont.load_default()

        # Draw title
        draw.text((20, 30), "UNIVERSITY LIBRARY", fill='white', font=title_font)
        draw.text((20, 60), "Student ID Card", fill='white', font=text_font)

        # Draw student information
        y_position = 150
        draw.text((20, y_position), f"Name: {card_data['full_name']}", fill=text_color, font=name_font)
        y_position += 40
        draw.text((20, y_position), f"Card Number: {card_data['card_number']}", fill=text_color, font=text_font)
        y_position += 30
        draw.text((20, y_position), f"User ID: {card_data['user_id']}", fill=text_color, font=text_font)
        y_position += 30
        draw.text((20, y_position), f"Grade: {card_data.get('grade_level', 'N/A')}", fill=text_color, font=text_font)
        y_position += 30
        draw.text((20, y_position), f"Valid Until: {card_data['expiry_date']}", fill=text_color, font=text_font)

        # Generate QR code for card number
        qr = qrcode.QRCode(version=1, box_size=8, border=1)
        qr.add_data(card_data['card_number'])
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white")

        # Resize and paste QR code
        qr_img = qr_img.resize((150, 150))
        card.paste(qr_img, (card_width - 170, card_height - 170))

        # Add barcode text
        draw.text((card_width - 170, card_height - 15), card_data['barcode'][:10], fill=text_color, font=text_font)

        # Draw border
        draw.rectangle([0, 0, card_width-1, card_height-1], outline=header_color, width=3)

        # Save the image
        card.save(filename, 'PNG', quality=95)
        print(f"✅ Library card image created: {filename}")

        return True

    except ImportError:
        # Fallback to text file if PIL not available
        print("PIL not available, creating text file instead...")

        # Create a simple text file as fallback
        with open(filename.replace('.png', '.txt'), 'w') as f:
            f.write("UNIVERSITY LIBRARY CARD\n")
            f.write("=" * 30 + "\n\n")
            f.write(f"Name: {card_data['full_name']}\n")
            f.write(f"Card Number: {card_data['card_number']}\n")
            f.write(f"User ID: {card_data['user_id']}\n")
            f.write(f"Grade: {card_data.get('grade_level', 'N/A')}\n")
            f.write(f"Issue Date: {card_data['issue_date']}\n")
            f.write(f"Expiry Date: {card_data['expiry_date']}\n")
            f.write(f"Barcode: {card_data['barcode']}\n\n")
            f.write("Note: Install PIL/Pillow for image generation\n")

        print(f"📄 Library card text file created: {filename.replace('.png', '.txt')}")
        return False

    except Exception as e:
        print(f"❌ Error creating library card: {e}")
        return False


