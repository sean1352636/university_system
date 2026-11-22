"""
Helper functions and utilities.
"""

import json
import logging
import os
import mimetypes

from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.infrastructure.sql_safety import validate_identifier  # nosec B608
from education_system.systems.university.infrastructure.logging.log_config import get_log_file

from education_system.systems.university.domains.student_support.domain.student_support.config import (
    SUPPORT_CATEGORIES, TICKET_PRIORITIES
)
from education_system.systems.university.domains.student_support.domain.student_support import store
from education_system.systems.university.domains.student_support.domain.student_support.schema import normalize_status, status_label
from education_system.systems.university.domains.student_support.domain.student_support import auth as _auth_mod
from education_system.systems.university.domains.student_support.domain.student_support.utils.audit import audit_action

logger = logging.getLogger(__name__)

DEFAULT_PREFERENCES = {
    'email_notifications': True,
    'in_app_notifications': True,
    'push_notifications': True,
    'digest_frequency': 'daily',
    'theme': 'light',
    'language': 'en',
    'timezone': 'UTC',
}
_TYPED_PREFERENCES = tuple(DEFAULT_PREFERENCES)


def _preferences_key(user_id=None):
    """The ``user_preferences.user_id`` for a person: the local users.id of the
    signed-in user (resolved by username; the e-mail preferences use the same
    key), or ``user_id`` when one is given."""
    if user_id is not None and str(user_id).strip():
        return str(user_id)
    user = _auth_mod.user_of()
    if not user:
        raise ValueError("User ID required")
    who = _auth_mod.current_requester(user)
    return str(who.users_id if who.users_id is not None else who.username)


def get_user_preferences(user_id=None):
    """The user's notification and display preferences (defaults when they
    have none saved). Reading never writes a row."""
    key = _preferences_key(user_id)
    prefs = dict(DEFAULT_PREFERENCES)
    try:
        with store.reading() as conn:
            if not conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' "
                                "AND name = 'user_preferences'").fetchone():
                return prefs
            row = conn.execute('SELECT * FROM user_preferences WHERE user_id = ?', (key,)).fetchone()
    except Exception as e:
        logger.error(f"Error getting user preferences: {e}")
        return prefs
    if row is None:
        return prefs
    row = dict(row)
    for name in _TYPED_PREFERENCES:
        if row.get(name) is not None:
            prefs[name] = bool(row[name]) if name.endswith('_notifications') else row[name]
    try:
        prefs.update(json.loads(row.get('preferences_json') or '{}'))
    except (TypeError, ValueError):
        logger.warning("user_preferences.preferences_json for %s is not valid JSON", key)
    return prefs


@audit_action("update_preferences")
def update_user_preferences(preferences, user_id=None):
    """Save the user's preferences. Keys without a column of their own are
    merged into ``preferences_json`` (the e-mail preferences keep theirs)."""
    key = _preferences_key(user_id)
    preferences = dict(preferences or {})
    known = {name: preferences.get(name, DEFAULT_PREFERENCES[name]) for name in _TYPED_PREFERENCES}
    extra = {k: v for k, v in preferences.items() if k not in known and k != 'preferences_json'
             and k != 'user_id'}
    with store.writing() as conn:
        row = conn.execute('SELECT preferences_json FROM user_preferences WHERE user_id = ?',
                           (key,)).fetchone()
        merged = {}
        if row and row[0]:
            try:
                merged = json.loads(row[0])
            except (TypeError, ValueError):
                merged = {}
        merged.update(extra)
        values = [known[n] for n in _TYPED_PREFERENCES] + [json.dumps(merged)]
        if row is not None:
            conn.execute('''
            UPDATE user_preferences SET
                email_notifications = ?, in_app_notifications = ?, push_notifications = ?,
                digest_frequency = ?, theme = ?, language = ?, timezone = ?, preferences_json = ?
            WHERE user_id = ?''', values + [key])
        else:
            conn.execute('''
            INSERT INTO user_preferences (
                email_notifications, in_app_notifications, push_notifications,
                digest_frequency, theme, language, timezone, preferences_json, user_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', values + [key])
    logger.info(f"User preferences updated for user {key}")
    return True


def setup_enhanced_logging():
    """
    Set up file and console handlers for the student support logger.

    Not called on import (it adds handlers each time it runs); call it once
    from an entry point that wants support logs in their own files.
    """
    support_logger = logging.getLogger(__name__)
    support_logger.setLevel(logging.DEBUG)

    file_handler = logging.FileHandler(get_log_file("app.log"))
    file_handler.setLevel(logging.INFO)

    error_handler = logging.FileHandler(get_log_file("app.log"))
    error_handler.setLevel(logging.ERROR)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s')
    file_handler.setFormatter(formatter)
    error_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    support_logger.addHandler(file_handler)
    support_logger.addHandler(error_handler)
    support_logger.addHandler(console_handler)

    return support_logger


def get_user_preferences_safe(support_instance=None, user_id=None):
    """Preferences that never raise (defaults on any problem)."""
    try:
        return get_user_preferences(user_id)
    except Exception as e:
        logger.warning(f"Error getting user preferences: {e}")
        return dict(DEFAULT_PREFERENCES)


def manage_preferences(support):
    """Manage user preferences"""
    try:
        print("\n⚙️ USER PREFERENCES")
        print("="*40)

        # Get current preferences
        current_prefs = support.get_user_preferences()

        print("Current Settings:")
        print(f"📧 Email Notifications: {'✅' if current_prefs.get('email_notifications', True) else '❌'}")
        print(f"🔔 In-App Notifications: {'✅' if current_prefs.get('in_app_notifications', True) else '❌'}")
        print(f"📱 Push Notifications: {'✅' if current_prefs.get('push_notifications', True) else '❌'}")
        print(f"📅 Digest Frequency: {current_prefs.get('digest_frequency', 'daily')}")
        print(f"🎨 Theme: {current_prefs.get('theme', 'light')}")
        print(f"🌍 Language: {current_prefs.get('language', 'en')}")
        print(f"🕐 Timezone: {current_prefs.get('timezone', 'UTC')}")

        print("\nWhat would you like to change?")
        print("1. Email Notifications")
        print("2. In-App Notifications")
        print("3. Push Notifications")
        print("4. Digest Frequency")
        print("5. Theme")
        print("6. Language")
        print("7. Timezone")
        print("8. Save and Exit")
        print("9. Cancel")

        updated_prefs = current_prefs.copy()

        while True:
            choice = input("\nSelect option: ").strip()

            if choice == '1':
                updated_prefs['email_notifications'] = input("Enable email notifications? (y/n): ").lower() == 'y'
            elif choice == '2':
                updated_prefs['in_app_notifications'] = input("Enable in-app notifications? (y/n): ").lower() == 'y'
            elif choice == '3':
                updated_prefs['push_notifications'] = input("Enable push notifications? (y/n): ").lower() == 'y'
            elif choice == '4':
                print("Digest frequency options: immediate, daily, weekly")
                freq = input("Enter frequency: ").strip()
                if freq in ['immediate', 'daily', 'weekly']:
                    updated_prefs['digest_frequency'] = freq
            elif choice == '5':
                print("Theme options: light, dark")
                theme = input("Enter theme: ").strip()
                if theme in ['light', 'dark']:
                    updated_prefs['theme'] = theme
            elif choice == '6':
                updated_prefs['language'] = input("Enter language code (e.g., en, es, fr): ").strip() or 'en'
            elif choice == '7':
                updated_prefs['timezone'] = input("Enter timezone (e.g., UTC, EST, PST): ").strip() or 'UTC'
            elif choice == '8':
                # Save preferences
                support.update_user_preferences(updated_prefs)
                print("✅ Preferences saved successfully!")
                break
            elif choice == '9':
                print("❌ Changes cancelled.")
                break
            else:
                print("❌ Invalid choice.")

    except Exception as e:
        print(f"❌ Error managing preferences: {e}")

    input("\nPress Enter to continue...")

def validate_ticket_permissions(ticket, current_user):
    """True if ``current_user`` may see ``ticket`` (see ``auth.can_view_ticket``)."""
    return _auth_mod.can_view_ticket(current_user, ticket)

def format_ticket_status_display(status):
    """Format ticket status for display with emoji"""
    status_emojis = {
        'open': '🔓',
        'in_progress': '⏳',
        'waiting_on_student': '⏸️',
        'escalated': '🚨',
        'resolved': '✅',
        'closed': '🔒',
    }
    key = normalize_status(status, default='')
    return f"{status_emojis.get(key, '❓')} {status_label(status)}"

def format_priority_display(priority):
    """Format ticket priority for display with emoji"""
    priority_emojis = {
        'Critical': '🔴',
        'Urgent': '🟠',
        'High': '🟡',
        'Medium': '🔵',
        'Low': '🟢'
    }
    return f"{priority_emojis.get(priority, '⚪')} {priority}"

def format_file_size(size_bytes):
    """Format file size in human readable format"""
    if size_bytes == 0:
        return "0B"

    size_names = ["B", "KB", "MB", "GB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1

    return f"{size_bytes:.1f}{size_names[i]}"

def truncate_text(text, max_length=100):
    """Truncate text to specified length with ellipsis"""
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."

def handle_support_error(error, context=""):
    """Standard error handling for support operations"""
    error_msg = str(error)

    if "PermissionError" in str(type(error)):
        return f"❌ Permission denied: {error_msg}"
    elif "ValueError" in str(type(error)):
        return f"❌ Invalid input: {error_msg}"
    elif "FileNotFoundError" in str(type(error)):
        return f"❌ File not found: {error_msg}"
    else:
        logger.error(f"Unexpected error in {context}: {error}")
        return "❌ An unexpected error occurred. Please try again or contact support."

# Patch for the EnhancedStudentSupport class to use safe preferences method

def display_faq_list(faqs, title):
    """Display a list of FAQs"""
    print(f"\n❓ {title}")
    print("="*50)

    if not faqs:
        print("📭 No FAQs found.")
        return

    for i, faq in enumerate(faqs[:10], 1):  # Show first 10
        views = faq.get('view_count', 0)
        votes = faq.get('helpful_votes', 0)
        print(f"{i}. Q: {faq['question']}")
        print(f"   👁️ {views} views | 👍 {votes} helpful")

    if len(faqs) > 10:
        print(f"\n... and {len(faqs) - 10} more FAQs")

    # View FAQ option
    view_choice = input(f"\nView FAQ (1-{min(len(faqs), 10)}) or press Enter to go back: ").strip()
    if view_choice.isdigit() and 1 <= int(view_choice) <= min(len(faqs), 10):
        faq = faqs[int(view_choice) - 1]
        display_full_faq(faq)

def display_full_faq(faq):
    """Display full FAQ with answer"""
    print(f"\n❓ {faq['question']}")
    print("="*60)
    print(f"📂 Category: {faq['category']}")
    print(f"👁️ Views: {faq.get('view_count', 0)}")
    print(f"👍 Helpful: {faq.get('helpful_votes', 0)}")

    print("\n💡 Answer:")
    print("-" * 40)
    print(faq['answer'])
    print("-" * 40)

    # Actions
    print("\n🔧 Actions:")
    print("1. Mark as helpful")
    print("2. Back")

    action = input("Choose action: ").strip()

    if action == '1':
        print("✅ Marked as helpful. Thank you for your feedback!")

def display_enhanced_faqs(support):
    """Display enhanced FAQ interface"""
    try:
        print("\n❓ FREQUENTLY ASKED QUESTIONS")
        print("="*50)

        # Get FAQ categories
        conn = store.connect(row_factory=False)
        cursor = conn.cursor()

        # Check if faqs table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='faqs'")
        if not cursor.fetchone():
            print("📭 No FAQs available (table not found).")
            conn.close()
            return

        cursor.execute('SELECT DISTINCT category FROM faqs ORDER BY category')
        categories = [row[0] for row in cursor.fetchall()]
        conn.close()

        if not categories:
            print("📭 No FAQs available.")
            return

        print("📂 Categories:")
        print("0. All Categories")
        for i, category in enumerate(categories, 1):
            print(f"{i}. {category}")

        print(f"{len(categories) + 1}. Search FAQs")
        print(f"{len(categories) + 2}. Back")

        choice = input("\nSelect option: ").strip()

        if choice == '0':
            # Show all FAQs
            faqs = support._search_faqs('', None)
            display_faq_list(faqs, "All FAQs")
        elif choice.isdigit() and 1 <= int(choice) <= len(categories):
            # Show FAQs in category
            category = categories[int(choice) - 1]
            faqs = support._search_faqs('', {'category': category})
            display_faq_list(faqs, f"{category} FAQs")
        elif choice == str(len(categories) + 1):
            # Search FAQs
            search_query = input("Enter search query: ").strip()
            if search_query:
                faqs = support._search_faqs(search_query, None)
                display_faq_list(faqs, f"Search Results for '{search_query}'")
        elif choice == str(len(categories) + 2):
            return
        else:
            print("❌ Invalid choice.")

    except Exception as e:
        print(f"❌ Error displaying FAQs: {e}")

    input("\nPress Enter to continue...")

def display_resource_list(resources, title):
    """Display a list of support resources"""
    print(f"\n📋 {title}")
    print("="*50)

    if not resources:
        print("📭 No resources found.")
        return

    for i, resource in enumerate(resources[:10], 1):  # Show first 10
        access_count = resource.get('access_count', 0)
        print(f"{i}. 📄 {resource['title']}")
        print(f"   📂 Category: {resource['category']}")
        print(f"   👁️ {access_count} accesses")
        print(f"   📝 {resource['description'][:80]}...")

    if len(resources) > 10:
        print(f"\n... and {len(resources) - 10} more resources")

    # View resource option
    view_choice = input(f"\nView resource (1-{min(len(resources), 10)}) or press Enter to go back: ").strip()
    if view_choice.isdigit() and 1 <= int(view_choice) <= min(len(resources), 10):
        resource = resources[int(view_choice) - 1]
        display_full_resource(resource)

def display_full_resource(resource):
    """Display full resource details"""
    print(f"\n📄 {resource['title']}")
    print("="*60)
    print(f"📂 Category: {resource['category']}")
    print(f"✏️ Created by: {resource['created_by']}")
    print(f"📅 Created: {resource['created_datetime']}")
    print(f"👁️ Accesses: {resource.get('access_count', 0)}")

    if resource.get('tags'):
        try:
            tags = json.loads(resource['tags']) if isinstance(resource['tags'], str) else resource['tags']
            if tags:
                print(f"🏷️ Tags: {', '.join(tags)}")
        except (json.JSONDecodeError, TypeError):
            pass

    print("\n📝 Description:")
    print("-" * 40)
    print(resource['description'])
    print("-" * 40)

    if resource.get('url'):
        print(f"🔗 URL: {resource['url']}")

    if resource.get('file_path'):
        print(f"📁 File: {resource['file_path']}")

def display_enhanced_resources(support):
    """Display enhanced resources interface"""
    try:
        print("\n📋 SUPPORT RESOURCES")
        print("="*50)

        # Get resource categories
        conn = store.connect(row_factory=False)
        cursor = conn.cursor()

        # Check if support_resources table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='support_resources'")
        if not cursor.fetchone():
            print("📭 No resources available (table not found).")
            conn.close()
            return

        cursor.execute('SELECT DISTINCT category FROM support_resources ORDER BY category')
        categories = [row[0] for row in cursor.fetchall()]
        conn.close()

        if not categories:
            print("📭 No resources available.")
            return

        print("📂 Categories:")
        print("0. All Categories")
        for i, category in enumerate(categories, 1):
            print(f"{i}. {category}")

        print(f"{len(categories) + 1}. Featured Resources")
        print(f"{len(categories) + 2}. Search Resources")
        print(f"{len(categories) + 3}. Back")

        choice = input("\nSelect option: ").strip()

        if choice == '0':
            # Show all resources
            resources = support._search_resources('', None)
            display_resource_list(resources, "All Resources")
        elif choice.isdigit() and 1 <= int(choice) <= len(categories):
            # Show resources in category
            category = categories[int(choice) - 1]
            resources = support._search_resources('', {'category': category})
            display_resource_list(resources, f"{category} Resources")
        elif choice == str(len(categories) + 1):
            # Featured resources
            conn = store.connect(row_factory=False)
            try:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM support_resources WHERE is_featured = 1 ORDER BY access_count DESC')
                resources = [dict(row) for row in cursor.fetchall()]
            finally:
                conn.close()
            display_resource_list(resources, "Featured Resources")
        elif choice == str(len(categories) + 2):
            # Search resources
            search_query = input("Enter search query: ").strip()
            if search_query:
                resources = support._search_resources(search_query, None)
                display_resource_list(resources, f"Search Results for '{search_query}'")
        elif choice == str(len(categories) + 3):
            return
        else:
            print("❌ Invalid choice.")

    except Exception as e:
        print(f"❌ Error displaying resources: {e}")

    input("\nPress Enter to continue...")

def apply_student_support_fixes():
    """Make sure the user_preferences table has every column it needs."""
    fix_user_preferences_table()

# Integration with existing CLI

def fix_user_preferences_table():
    """Fix the user_preferences table schema"""
    try:
        conn = store.connect(row_factory=False)
        cursor = conn.cursor()

        # Check if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_preferences'")
        if not cursor.fetchone():
            # Create the table with proper schema
            cursor.execute('''
            CREATE TABLE user_preferences (
                user_id TEXT PRIMARY KEY,
                email_notifications BOOLEAN DEFAULT 1,
                in_app_notifications BOOLEAN DEFAULT 1,
                push_notifications BOOLEAN DEFAULT 1,
                digest_frequency TEXT DEFAULT 'daily',
                theme TEXT DEFAULT 'light',
                language TEXT DEFAULT 'en',
                timezone TEXT DEFAULT 'UTC',
                preferences_json TEXT
            )
            ''')
            print("✅ Created user_preferences table")
        else:
            # Check existing columns
            cursor.execute("PRAGMA table_info(user_preferences)")
            existing_columns = [column[1] for column in cursor.fetchall()]

            required_columns = {
                'email_notifications': 'BOOLEAN DEFAULT 1',
                'in_app_notifications': 'BOOLEAN DEFAULT 1',
                'push_notifications': 'BOOLEAN DEFAULT 1',
                'digest_frequency': 'TEXT DEFAULT "daily"',
                'theme': 'TEXT DEFAULT "light"',
                'language': 'TEXT DEFAULT "en"',
                'timezone': 'TEXT DEFAULT "UTC"',
                'preferences_json': 'TEXT'
            }

            for column_name, column_def in required_columns.items():
                if column_name not in existing_columns:
                    try:
                        safe_col = validate_identifier(column_name, "column")
                        cursor.execute('ALTER TABLE user_preferences ADD COLUMN ' + safe_col + ' ' + column_def)
                        print(f"Added column '{column_name}' to user_preferences table")
                    except Exception as e:
                        print(f"Could not add column '{column_name}': {e}")

        conn.commit()
        conn.close()
        print("✅ User preferences table schema fixed")

    except Exception as e:
        print(f"❌ Error fixing user_preferences table: {e}")

# Enhanced get_user_preferences method to handle missing columns gracefully

def _choose_category_and_priority(support, title, description):
    """Ask for a category (with the suggested one marked) and a priority;
    ``(None, None)`` when the category choice is invalid."""
    from education_system.systems.university.domains.student_support.domain.student_support.automation.sentiment_analysis import (
        _suggest_category,
    )
    suggested_category = _suggest_category(title + " " + description)

    print("\nCategories:")
    for i, cat in enumerate(SUPPORT_CATEGORIES, 1):
        marker = " 🤖 (Suggested)" if cat == suggested_category else ""
        print(f"{i}. {cat}{marker}")

    category_choice = input(f"\nSelect category (1-{len(SUPPORT_CATEGORIES)}): ").strip()
    try:
        category_index = int(category_choice) - 1
        if not 0 <= category_index < len(SUPPORT_CATEGORIES):
            print("❌ Invalid category.")
            return None, None
        category = SUPPORT_CATEGORIES[category_index]
    except ValueError:
        print("❌ Invalid category.")
        return None, None

    print("\nPriorities:")
    for i, pri in enumerate(TICKET_PRIORITIES, 1):
        print(f"{i}. {pri}")

    priority = 'Medium'
    priority_choice = input(f"\nSelect priority (1-{len(TICKET_PRIORITIES)}) [default: Medium]: ").strip()
    if priority_choice.isdigit() and 1 <= int(priority_choice) <= len(TICKET_PRIORITIES):
        priority = TICKET_PRIORITIES[int(priority_choice) - 1]
    return category, priority


def create_enhanced_ticket(support):
    """Create a new ticket with enhanced features"""
    from education_system.systems.university.domains.student_support.domain.student_support.core.ticket_manager import display_ticket_details_enhanced
    try:
        print("\n🎫 CREATE SUPPORT TICKET")
        print("="*40)

        # The ticket is raised for the signed-in person (resolved by username).
        who = _auth_mod.current_requester()
        student_id = who.student_id or who.username

        # Show templates option
        templates = support.get_ticket_templates()
        if templates:
            print("📋 Available Templates:")
            print("0. Create from scratch")
            for i, template in enumerate(templates, 1):
                print(f"{i}. {template['name']} ({template['category']})")

            template_choice = input("\nSelect template (0 for scratch): ").strip()

            if template_choice.isdigit() and 1 <= int(template_choice) <= len(templates):
                template = templates[int(template_choice) - 1]
                title = template['subject_template']
                description = template['message_template']
                category = template['category']
                priority = template['priority']

                print(f"\n📝 Using template: {template['name']}")
                print("You can modify the pre-filled content:")

                title = input(f"Title [{title}]: ").strip() or title
                print("Description (press Enter twice to finish):")
                print(f"Current: {description}")
                print("Additional/Modified content:")

                lines = []
                while True:
                    line = input()
                    if not line and (not lines or not lines[-1]):
                        break
                    lines.append(line)

                if lines:
                    description = '\n'.join(lines)
            else:
                # Create from scratch
                title = input("Title: ").strip()
                if not title:
                    print("❌ Title is required.")
                    return

                print("Description (press Enter twice to finish):")
                lines = []
                while True:
                    line = input()
                    if not line and (not lines or not lines[-1]):
                        break
                    lines.append(line)

                description = '\n'.join(lines)
                if not description:
                    print("❌ Description is required.")
                    return

                category, priority = _choose_category_and_priority(support, title, description)
                if category is None:
                    return
        else:
            # No templates available, create from scratch
            title = input("Title: ").strip()
            if not title:
                print("❌ Title is required.")
                return

            print("Description (press Enter twice to finish):")
            lines = []
            while True:
                line = input()
                if not line and (not lines or not lines[-1]):
                    break
                lines.append(line)

            description = '\n'.join(lines)
            if not description:
                print("❌ Description is required.")
                return

            category, priority = _choose_category_and_priority(support, title, description)
            if category is None:
                return

        # Tags
        tags_input = input("\nTags (comma-separated, optional): ").strip()
        tags = [tag.strip() for tag in tags_input.split(',')] if tags_input else []

        # File attachments
        attachments = []
        attach_more = input("\nAdd file attachment? (y/n): ").lower() == 'y'
        while attach_more:
            file_path = input("File path: ").strip()
            if file_path and os.path.exists(file_path):
                try:
                    with open(file_path, 'rb') as f:
                        file_data = f.read()

                    attachments.append({
                        'filename': os.path.basename(file_path),
                        'data': file_data,
                        'mime_type': mimetypes.guess_type(file_path)[0]
                    })
                    print(f"✅ Added {os.path.basename(file_path)}")
                except Exception as e:
                    print(f"❌ Error reading file: {e}")
            else:
                print("❌ File not found.")

            attach_more = input("Add another file? (y/n): ").lower() == 'y'

        # Create ticket
        print("\n🎫 Creating ticket...")
        ticket_id = support.create_support_ticket(
            student_id, title, description, category, priority,
            attachments=attachments, tags=tags
        )

        print(f"✅ Support ticket #{ticket_id} created successfully!")

        # Show ticket details
        view_choice = input("\nView ticket details? (y/n): ").lower()
        if view_choice == 'y':
            display_ticket_details_enhanced(support, ticket_id)

    except Exception as e:
        print(f"❌ Error creating ticket: {e}")

    input("\nPress Enter to continue...")
