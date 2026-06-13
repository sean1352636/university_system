"""Advanced text search: regex, wildcard, full-text, and phonetic search."""
import re

from education_system.university_system.core.sql_safety import escape_like
from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from education_system.university_system.core.sql_safety import (
    validate_field_for_query,
    SQLIdentifierError,
)
from education_system.university_system.modules.shared.services.analytics.advanced_search.display import display_search_results
from education_system.university_system.modules.shared.services.analytics.advanced_search.system import log_search
from education_system.university_system.modules.shared.services.analytics.advanced_search.admin import audit_log


@audit_log
def advanced_text_search():
    """Advanced text search with regex and wildcard support"""
    print("\n🔍 ADVANCED TEXT SEARCH")
    print("="*40)

    print("Search Options:")
    print("1. Regular Expression Search")
    print("2. Wildcard Pattern Search")
    print("3. Search All Text Fields")
    print("4. Phonetic Name Search")

    choice = input("Select option (1-4): ").strip()

    if choice == '1':
        regex_search()
    elif choice == '2':
        wildcard_search()
    elif choice == '3':
        search_all_fields()
    elif choice == '4':
        phonetic_search()
    else:
        print("Invalid choice.")

def regex_search():
    """Search using regular expressions"""
    pattern = input("Enter regex pattern: ").strip()
    field = input("Search in field (first_name/last_name/email/student_id): ").strip()

    if field not in ['first_name', 'last_name', 'email', 'student_id']:
        print("Invalid field name.")
        return

    try:
        compiled_pattern = re.compile(pattern, re.IGNORECASE)

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(f"SELECT * FROM students")
        all_students = cursor.fetchall()

        results = []
        field_index = {
            'student_id': 0, 'email': 1, 'first_name': 3, 'last_name': 5
        }[field]

        for student in all_students:
            if student[field_index] and compiled_pattern.search(student[field_index]):
                results.append(student)

        log_search("regex_search", {"pattern": pattern, "field": field}, len(results))
        display_search_results(results)
        conn.close()

    except re.error as e:
        print(f"Invalid regex pattern: {e}")
    except sqlite3.Error as e:
        print(f"Database error: {e}")

def wildcard_search():
    """Search using wildcard patterns (* and ?)"""
    pattern = input("Enter wildcard pattern (* = any chars, ? = single char): ").strip()
    field = input("Search in field (first_name/last_name/email/student_id): ").strip()

    # Convert wildcard to SQL LIKE pattern
    sql_pattern = pattern.replace('*', '%').replace('?', '_')

    VALID_WILDCARD_FIELDS = {'first_name', 'last_name', 'email', 'student_id'}
    try:
        field = validate_field_for_query(field, VALID_WILDCARD_FIELDS, field_type="search field")
    except SQLIdentifierError:
        print("Invalid field name.")
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        query = f"SELECT * FROM students WHERE {field} LIKE ?"
        cursor.execute(query, (sql_pattern,))
        results = cursor.fetchall()

        log_search("wildcard_search", {"pattern": pattern, "field": field}, len(results))
        display_search_results(results)
        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")

def search_all_fields():
    """Search across all text fields simultaneously"""
    search_term = input("Enter search term: ").strip()

    try:
        conn = get_connection()
        cursor = conn.cursor()

        query = '''
        SELECT * FROM students WHERE
        student_id LIKE ? OR
        email LIKE ? OR
        first_name LIKE ? OR
        middle_name LIKE ? OR
        last_name LIKE ?
        '''

        search_pattern = f"%{escape_like(search_term)}%"
        params = [search_pattern] * 5

        cursor.execute(query, params)
        results = cursor.fetchall()

        log_search("search_all_fields", {"term": search_term}, len(results))
        display_search_results(results)
        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")

def phonetic_search():
    """Search using phonetic matching (Soundex algorithm)"""
    name = input("Enter name for phonetic search: ").strip()

    def soundex(word):
        """Simple Soundex implementation"""
        if not word:
            return "0000"

        word = word.upper()
        result = word[0]

        mapping = {
            'BFPV': '1', 'CGJKQSXZ': '2', 'DT': '3',
            'L': '4', 'MN': '5', 'R': '6'
        }

        for char in word[1:]:
            for key, value in mapping.items():
                if char in key:
                    if result[-1] != value:
                        result += value
                    break

        result = result.replace('0', '')
        return (result + '0000')[:4]

    target_soundex = soundex(name)

    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM students")
        all_students = cursor.fetchall()

        results = []
        for student in all_students:
            if (soundex(student[3]) == target_soundex or  # first_name
                soundex(student[5]) == target_soundex):   # last_name
                results.append(student)

        print(f"\nPhonetic matches for '{name}' (Soundex: {target_soundex}):")
        log_search("phonetic_search", {"name": name}, len(results))
        display_search_results(results)
        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
