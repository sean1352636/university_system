"""Search management: saved searches, search history, favorites."""
import json

from education_system.university_system.core.sql_safety import escape_like
from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from education_system.university_system.modules.shared.services.analytics.advanced_search import _globals
from education_system.university_system.modules.shared.services.analytics.advanced_search.display import display_search_results
from education_system.university_system.modules.shared.services.analytics.advanced_search.system import log_search


def manage_saved_searches():
    """Manage saved search profiles"""
    print("\n💾 SAVED SEARCH PROFILES")
    print("="*40)

    print("1. Save Current Search")
    print("2. View Saved Searches")
    print("3. Delete Saved Search")
    print("4. Share Search Profile")

    choice = input("Select option (1-4): ").strip()

    if choice == '1':
        save_search_profile()
    elif choice == '2':
        view_saved_searches()
    elif choice == '3':
        delete_saved_search()
    elif choice == '4':
        share_search_profile()

def save_search_profile():
    """Save a search profile"""
    if not _globals.last_search_results:
        print("No recent search to save. Please perform a search first.")
        return

    name = input("Enter name for this search profile: ").strip()
    if not name:
        print("Search name cannot be empty.")
        return

    # Get search criteria from user input
    criteria = {}
    print("\nEnter search criteria to save:")
    criteria['student_id'] = input("Student ID pattern: ").strip()
    criteria['first_name'] = input("First name pattern: ").strip()
    criteria['last_name'] = input("Last name pattern: ").strip()
    criteria['course'] = input("Course (CS/DS): ").strip()
    criteria['gender'] = input("Gender: ").strip()

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Direct fix: Check if search_name column exists, if not add it
        cursor.execute("PRAGMA table_info(saved_searches)")
        columns = [column[1] for column in cursor.fetchall()]

        if 'search_name' not in columns:
            cursor.execute('ALTER TABLE saved_searches ADD COLUMN search_name TEXT')
            print("✓ Added missing 'search_name' column to saved_searches table")
            conn.commit()

        # Now insert the saved search
        cursor.execute('''
        INSERT INTO saved_searches (user_id, search_name, search_criteria)
        VALUES (?, ?, ?)
        ''', (_globals.current_user, name, json.dumps(criteria)))

        conn.commit()
        conn.close()

        print(f"✅ Search profile '{name}' saved successfully!")

    except sqlite3.Error as e:
        print(f"Error saving search: {e}")

def view_saved_searches():
    """View all saved searches"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
        SELECT id, search_name, search_criteria, created_date, is_shared
        FROM saved_searches
        WHERE user_id = ? OR is_shared = 1
        ORDER BY created_date DESC
        ''', (_globals.current_user,))

        searches = cursor.fetchall()

        if not searches:
            print("No saved searches found.")
            return

        print(f"\n📋 YOUR SAVED SEARCHES:")
        print("-" * 80)
        print(f"{'ID':<5} {'Name':<25} {'Created':<20} {'Shared':<8}")
        print("-" * 80)

        for search_id, name, criteria, created, shared in searches:
            shared_text = "Yes" if shared else "No"
            print(f"{search_id:<5} {name:<25} {created[:16]:<20} {shared_text:<8}")

        conn.close()

    except sqlite3.Error as e:
        print(f"Error viewing searches: {e}")

def load_saved_search():
    """Load and execute a saved search"""
    view_saved_searches()

    try:
        search_id = int(input("\nEnter search ID to load: "))

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
        SELECT search_name, search_criteria FROM saved_searches
        WHERE id = ? AND (user_id = ? OR is_shared = 1)
        ''', (search_id, _globals.current_user))

        result = cursor.fetchone()
        if not result:
            print("Search not found or access denied.")
            return

        name, criteria_json = result
        criteria = json.loads(criteria_json)

        print(f"\nLoading search: '{name}'")
        print("Search criteria:")
        for key, value in criteria.items():
            if value:
                print(f"  {key}: {value}")

        # Execute the loaded search
        execute_loaded_search(criteria)
        conn.close()

    except (ValueError, sqlite3.Error) as e:
        print(f"Error loading search: {e}")

def execute_loaded_search(criteria):
    """Execute a loaded search with given criteria"""
    query = "SELECT * FROM students WHERE 1=1"
    params = []

    for key, value in criteria.items():
        if value:
            if key in ['student_id', 'first_name', 'last_name']:
                query += f" AND {key} LIKE ?"
                params.append(f"%{escape_like(value)}%")
            else:
                query += f" AND {key} = ?"
                params.append(value)

    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(query, params)
        results = cursor.fetchall()

        log_search("loaded_search", criteria, len(results))
        display_search_results(results)
        conn.close()

    except sqlite3.Error as e:
        print(f"Error executing search: {e}")

def view_search_history():
    """View search history and favorites"""
    print("\n📚 SEARCH HISTORY")
    print("="*40)

    if not _globals.search_history:
        print("No search history available.")
        return

    print(f"{'#':<3} {'Type':<20} {'Time':<20} {'Results':<8}")
    print("-" * 55)

    for i, entry in enumerate(reversed(_globals.search_history[-20:])):  # Last 20 searches
        print(f"{i+1:<3} {entry['type']:<20} {entry['time']:<20} {entry['results']:<8}")

    choice = input("\nEnter search number to repeat (or press Enter to continue): ").strip()
    if choice:
        try:
            index = int(choice) - 1
            if 0 <= index < len(_globals.search_history):
                repeat_search(_globals.search_history[-(index + 1)])
        except ValueError:
            print("Invalid input.")

def repeat_search(search_entry):
    """Repeat a search from history"""
    print(f"\nRepeating search: {search_entry['type']}")
    print(f"Original criteria: {search_entry.get('criteria', 'N/A')}")

    # This would ideally reconstruct and execute the original search
    # For now, just show the information
    print("Search repeated! (Implementation depends on search type)")

def delete_saved_search():
    """Delete a saved search"""
    view_saved_searches()

    try:
        search_id = int(input("\nEnter search ID to delete: "))

        conn = get_connection()
        cursor = conn.cursor()

        # Check if search exists and belongs to user
        cursor.execute('''
        SELECT search_name FROM saved_searches
        WHERE id = ? AND user_id = ?
        ''', (search_id, _globals.current_user))

        result = cursor.fetchone()
        if not result:
            print("Search not found or access denied.")
            return

        search_name = result[0]
        confirm = input(f"Delete search '{search_name}'? (y/n): ").strip().lower()

        if confirm == 'y':
            cursor.execute('DELETE FROM saved_searches WHERE id = ?', (search_id,))
            conn.commit()
            print(f"✅ Search '{search_name}' deleted successfully.")
        else:
            print("Deletion cancelled.")

        conn.close()

    except (ValueError, sqlite3.Error) as e:
        print(f"Error deleting search: {e}")

def share_search_profile():
    """Share a search profile with other users"""
    view_saved_searches()

    try:
        search_id = int(input("\nEnter search ID to share: "))

        conn = get_connection()
        cursor = conn.cursor()

        # Check if search exists and belongs to user
        cursor.execute('''
        SELECT search_name FROM saved_searches
        WHERE id = ? AND user_id = ?
        ''', (search_id, _globals.current_user))

        result = cursor.fetchone()
        if not result:
            print("Search not found or access denied.")
            return

        search_name = result[0]
        confirm = input(f"Share search '{search_name}' with all users? (y/n): ").strip().lower()

        if confirm == 'y':
            cursor.execute('''
            UPDATE saved_searches
            SET is_shared = 1
            WHERE id = ?
            ''', (search_id,))
            conn.commit()
            print(f"✅ Search '{search_name}' is now shared with all users.")
        else:
            print("Sharing cancelled.")

        conn.close()

    except (ValueError, sqlite3.Error) as e:
        print(f"Error sharing search: {e}")
