import os
import mimetypes
import re
import logging

logger = logging.getLogger(__name__)


def handle_file_attachments(ticket_id, reply_id, user_id, auth=None, public=True):
    """Offer to attach files to a ticket (``auth``: the signed-in person —
    left out, the support session's; ``public=False`` keeps them to the
    staff working the ticket). ``reply_id`` / ``user_id`` are kept for older
    callers: the ticket service records the uploader by username."""
    while True:
        attach_file = input("\nWould you like to attach a file? (y/n): ").strip().lower()
        if attach_file == 'n':
            break
        elif attach_file == 'y':
            file_path = input("Enter file path: ").strip()
            if os.path.exists(file_path):
                if add_attachment(ticket_id, reply_id, file_path, user_id, auth=auth, public=public):
                    print("File attached successfully!")
                else:
                    print("Failed to attach file.")
            else:
                print("File not found.")
        else:
            print("Please enter 'y' or 'n'.")

def add_attachment(ticket_id, reply_id, file_path, user_id=None, auth=None, public=True):
    """Attach the file at ``file_path`` to a ticket through the ticket
    service (which checks access, type and size, stores it under the upload
    folder and records it). Returns True on success."""
    from education_system.systems.university.domains.student_support.domain.student_support import (
        service,
    )
    try:
        with open(file_path, 'rb') as f:
            data = f.read()
        mime_type, _ = mimetypes.guess_type(file_path)
        service.add_attachment(auth, ticket_id, os.path.basename(file_path), data,
                               public=public, mime_type=mime_type)
        return True
    except (PermissionError, ValueError, OSError) as e:
        print(f"Error uploading file: {e}")
        return False

def suggest_knowledge_base_articles(ticket_id, content):
    """Suggest self-help from both knowledge bases (Student Support articles
    and FAQs, and the Helpdesk knowledge base) for a ticket's words
    (``student_support.deflection``). Returns the suggestions."""
    from education_system.systems.university.domains.student_support.domain.student_support import (
        deflection,
    )
    try:
        suggestions = deflection.suggest(content, limit=3)
    except Exception as e:
        logger.debug("No self-help suggestions for ticket %s: %s", ticket_id, e)
        return []
    if suggestions:
        print("\nSuggested articles that might help:")
        for item in suggestions:
            print(f"- {item['title']}" + (f": {item['snippet'][:80]}" if item.get('snippet') else ''))
    return suggestions

def extract_keywords(text):
    """Extract relevant keywords from text"""
    # Remove common words and extract meaningful terms
    stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'can', 'cant', 'cannot', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her', 'us', 'them', 'my', 'your', 'his', 'its', 'our', 'their'}

    # Simple word extraction
    words = re.findall(r'\b[a-zA-Z]{3,}\b', text)
    keywords = [word for word in words if word.lower() not in stop_words]

    # Return most frequent keywords
    from collections import Counter
    word_counts = Counter(keywords)
    return [word for word, count in word_counts.most_common(10)]
