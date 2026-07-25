from education_system.systems.university.infrastructure.sql_safety import escape_like
from education_system.systems.university.infrastructure.database.db import sqlite3, get_connection
from datetime import datetime
import os
import hashlib
import mimetypes
import re
import logging

logger = logging.getLogger(__name__)


def handle_file_attachments(ticket_id, reply_id, user_id):
    """Handle file attachments for tickets or replies"""
    while True:
        attach_file = input("\nWould you like to attach a file? (y/n): ").strip().lower()
        if attach_file == 'n':
            break
        elif attach_file == 'y':
            file_path = input("Enter file path: ").strip()
            if os.path.exists(file_path):
                if add_attachment(ticket_id, reply_id, file_path, user_id):
                    print("File attached successfully!")
                else:
                    print("Failed to attach file.")
            else:
                print("File not found.")
        else:
            print("Please enter 'y' or 'n'.")

def add_attachment(ticket_id, reply_id, file_path, user_id):
    """Add a file attachment to a ticket or reply"""
    try:
        # Create attachments directory if it doesn't exist
        upload_dir = "attachments"
        if not os.path.exists(upload_dir):
            os.makedirs(upload_dir)

        # Get file information
        original_filename = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        mime_type, _ = mimetypes.guess_type(file_path)

        # Check file size (limit to 10MB)
        if file_size > 10 * 1024 * 1024:
            print("Error: File size exceeds 10MB limit.")
            return False

        # Check file type
        allowed_types = [
            'image/', 'text/', 'application/pdf', 'application/msword',
            'application/vnd.openxmlformats-officedocument',
            'application/zip', 'application/x-zip-compressed'
        ]

        if mime_type and not any(mime_type.startswith(t) for t in allowed_types):
            print(f"Error: File type {mime_type} not allowed.")
            return False

        # Generate unique filename
        file_hash = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                file_hash.update(chunk)

        file_extension = os.path.splitext(original_filename)[1]
        unique_filename = f"{file_hash.hexdigest()}{file_extension}"
        upload_path = os.path.join(upload_dir, unique_filename)

        # Copy file to upload directory
        import shutil
        shutil.copy2(file_path, upload_path)

        # Save attachment record
        conn = get_connection()
        cursor = conn.cursor()

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
        INSERT INTO ticket_attachments
        (ticket_id, reply_id, filename, original_filename, file_size, mime_type,
         file_hash, uploaded_by, file_path, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (ticket_id, reply_id, unique_filename, original_filename, file_size,
              mime_type, file_hash.hexdigest(), user_id, upload_path, now))

        conn.commit()
        conn.close()
        return True

    except Exception as e:
        print(f"Error uploading file: {e}")
        return False

def suggest_knowledge_base_articles(ticket_id, content):
    """Suggest relevant knowledge base articles based on ticket content"""
    conn = get_connection()
    cursor = conn.cursor()

    # Simple keyword matching for suggestions
    keywords = extract_keywords(content.lower())

    if keywords:
        # Search for articles with matching keywords
        keyword_conditions = []
        params = []

        for keyword in keywords[:5]:  # Limit to top 5 keywords
            keyword_conditions.append("(title LIKE ? OR content LIKE ? OR search_keywords LIKE ?)")
            params.extend([f"%{escape_like(keyword)}%", f"%{escape_like(keyword)}%", f"%{escape_like(keyword)}%"])

        if keyword_conditions:
            query = f'''
            SELECT article_id, title, category
            FROM knowledge_base
            WHERE status = 'published' AND ({" OR ".join(keyword_conditions)})
            ORDER BY helpful_votes DESC, views DESC
            LIMIT 3
            '''

            cursor.execute(query, params)
            articles = cursor.fetchall()

            if articles:
                print("\nSuggested knowledge base articles that might help:")
                for article in articles:
                    print(f"- {article[1]} (Category: {article[2]})")

                # Store suggestions in ticket
                article_ids = [str(a[0]) for a in articles]
                cursor.execute('''
                UPDATE support_tickets
                SET knowledge_base_articles = ?
                WHERE ticket_id = ?
                ''', (','.join(article_ids), ticket_id))

                conn.commit()

    conn.close()

def extract_keywords(text):
    """Extract relevant keywords from text"""
    # Remove common words and extract meaningful terms
    stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'can', 'cant', 'cannot', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her', 'us', 'them', 'my', 'your', 'his', 'her', 'its', 'our', 'their'}

    # Simple word extraction
    words = re.findall(r'\b[a-zA-Z]{3,}\b', text)
    keywords = [word for word in words if word.lower() not in stop_words]

    # Return most frequent keywords
    from collections import Counter
    word_counts = Counter(keywords)
    return [word for word, count in word_counts.most_common(10)]
