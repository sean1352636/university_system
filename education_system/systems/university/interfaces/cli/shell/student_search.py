"""
Student search operations for CLI system.

Handles student search by various criteria and advanced filtering.
"""

import re

from education_system.systems.university.interfaces.cli.shell.imports import (
    logging, sqlite3, datetime, DB_PATH, logger, _t,
    log_search, get_auth
)
import education_system.systems.university.interfaces.cli.shell.student_operations as _student_ops
from education_system.systems.university.interfaces.cli.shell.student_operations import display_student_record

def get_db_connection():
    """Get database connection"""
    return sqlite3.connect(DB_PATH)


def search_student_by_first_name():
    auth = _student_ops.auth or get_auth()

    # Check permissions
    if not auth.check_permission('view_any_student'):
        print("You don't have permission to search student records.")
        return

    conn = get_db_connection()
    if not conn:
        return

    cursor = conn.cursor()

    # Get search term from user
    search_term = input("Enter student's first name: ")

    # Validate search term
    if not search_term:
        print("Error: You must enter a search term.")
        conn.close()
        return
    if not re.match("^[a-zA-Z]+$", search_term):
        print("Error: Search term must contain only letters.")
        conn.close()
        return

    # Search for student records
    cursor.execute('''
    SELECT * FROM students WHERE LOWER(first_name) = LOWER(?)
    ''', (search_term,))

    matches = cursor.fetchall()

    # Display search results
    if len(matches) == 0:
        print(f"No records found for search term '{search_term}'.")
    elif len(matches) == 1:
        display_student_record(matches[0])
    else:
        print(f"Multiple records found for search term '{search_term}':")
        for i, match in enumerate(matches):
            print(f"{i+1}.")
            display_student_record(match)

        choice = input("Enter the number of the record you want to display: ")
        try:
            index = int(choice) - 1
            if index < 0 or index >= len(matches):
                raise ValueError
            display_student_record(matches[index])
        except (ValueError, IndexError):
            print("Error: Invalid choice.")

    conn.close()


def search_student_by_last_name():
    auth = _student_ops.auth or get_auth()

    # Check permissions
    if not auth.check_permission('view_any_student'):
        print("You don't have permission to search student records.")
        return

    conn = get_db_connection()
    if not conn:
        return

    cursor = conn.cursor()

    # Get search term from user
    search_term = input("Enter student's last name: ")

    # Validate search term
    if not search_term:
        print("Error: You must enter a search term.")
        conn.close()
        return
    if not re.match("^[a-zA-Z]+$", search_term):
        print("Error: Search term must contain only letters.")
        conn.close()
        return

    # Search for student records
    cursor.execute('''
    SELECT * FROM students WHERE LOWER(last_name) = LOWER(?)
    ''', (search_term,))

    matches = cursor.fetchall()

    # Display search results
    if len(matches) == 0:
        print(f"No records found for search term '{search_term}'.")
    elif len(matches) == 1:
        display_student_record(matches[0])
    else:
        print(f"Multiple records found for search term '{search_term}':")
        for i, match in enumerate(matches):
            print(f"{i+1}.")
            display_student_record(match)

        choice = input("Enter the number of the record you want to display: ")
        try:
            index = int(choice) - 1
            if index < 0 or index >= len(matches):
                raise ValueError
            display_student_record(matches[index])
        except (ValueError, IndexError):
            print("Error: Invalid choice.")

    conn.close()


def search_student_by_student_id():
    auth = _student_ops.auth or get_auth()

    # Check permissions
    # Different behavior based on roles/permissions
    if not (auth.check_permission('view_any_student') or auth.check_permission('view_own_record')):
        print("You don't have permission to search student records.")
        return

    conn = get_db_connection()
    if not conn:
        return

    cursor = conn.cursor()

    # For students with view_own_record permission only
    if not auth.check_permission('view_any_student') and auth.check_permission('view_own_record'):
        # Get the student ID associated with this user - updated for new database structure
        cursor.execute('''
        SELECT student_id FROM users WHERE id = ?
        ''', (auth.current_user['id'],))

        result = cursor.fetchone()
        if result and result[0]:
            student_id = result[0]

            # Fetch and display just this student's record
            cursor.execute('''
            SELECT * FROM students WHERE student_id = ?
            ''', (student_id,))

            student = cursor.fetchone()
            if student:
                display_student_record(student)
            else:
                print("Your student record was not found.")
        else:
            print("No student ID associated with your account.")

        conn.close()
        return

    # For staff/admin with view_any_student permission
    # Get search term from user
    search_term = input("Enter student's ID: ")

    # Validate search term
    if not search_term:
        print("Error: You must enter a search term.")
        conn.close()
        return
    if not re.match("^[0-9]+$", search_term):
        print("Error: Search term must contain only digits.")
        conn.close()
        return

    # Search for student records
    cursor.execute('''
    SELECT * FROM students WHERE student_id = ?
    ''', (search_term,))

    match = cursor.fetchone()

    # Display search results
    if not match:
        print(f"No records found for search term '{search_term}'.")
    else:
        display_student_record(match)

    conn.close()


def search_student_by_registration_date():
    auth = _student_ops.auth or get_auth()

    # Check permissions
    if not auth.check_permission('view_any_student'):
        print("You don't have permission to search student records.")
        return

    conn = get_db_connection()
    if not conn:
        return

    cursor = conn.cursor()

    # Get search term from user
    search_date = input("Enter date (YYYY-MM-DD): ")

    # Validate search term
    if not search_date or not re.match("^[0-9]{4}-[0-9]{2}-[0-9]{2}$", search_date):
        print("Error: Date must be in the format YYYY-MM-DD.")
        conn.close()
        return

    # Search for student records
    cursor.execute('''
    SELECT * FROM students WHERE registration_datetime LIKE ?
    ''', (f"{search_date}%",))

    matches = cursor.fetchall()

    # Display search results
    if len(matches) == 0:
        print(f"No records found for date '{search_date}'.")
    elif len(matches) == 1:
        display_student_record(matches[0])
    else:
        print(f"Multiple records found for date '{search_date}':")
        for i, match in enumerate(matches):
            print(f"{i+1}.")
            display_student_record(match)

        choice = input("Enter the number of the record you want to display: ")
        try:
            index = int(choice) - 1
            if index < 0 or index >= len(matches):
                raise ValueError
            display_student_record(matches[index])
        except (ValueError, IndexError):
            print("Error: Invalid choice.")

    conn.close()


__all__ = [
    'search_student_by_first_name',
    'search_student_by_last_name',
    'search_student_by_student_id',
    'search_student_by_registration_date',
]
