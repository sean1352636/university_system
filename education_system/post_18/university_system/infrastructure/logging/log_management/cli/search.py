"""Advanced search CLI functions."""

import os
import json
from datetime import datetime

try:
    import pandas as pd  # type: ignore
except Exception:
    pd = None  # type: ignore

try:
    from tabulate import tabulate  # type: ignore
except Exception:
    def tabulate(data, headers=(), tablefmt=None):  # pragma: no cover
        lines = []
        if headers:
            lines.append(','.join(str(h) for h in headers))
        for row in data:
            lines.append(','.join(str(col) for col in row))
        return '\n'.join(lines)

from education_system.post_18.university_system.infrastructure.database.db import DEFAULT_DB_PATH as _DB_PATH
from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from education_system.post_18.university_system.core.paths import LOG_DIR


def advanced_search_menu(log_manager, auth):
    """Advanced search menu"""
    print("\n\U0001f50d ADVANCED LOG SEARCH")
    print("="*30)

    print("Enter search criteria (leave blank to skip):")

    filters = {}

    date_from = input("From date (YYYY-MM-DD): ")
    if date_from:
        try:
            datetime.strptime(date_from, "%Y-%m-%d")
            filters['date_from'] = date_from
        except ValueError:
            print("Invalid date format")
            return

    date_to = input("To date (YYYY-MM-DD): ")
    if date_to:
        try:
            datetime.strptime(date_to, "%Y-%m-%d")
            filters['date_to'] = date_to
        except ValueError:
            print("Invalid date format")
            return

    user_id = input("User ID: ")
    if user_id:
        filters['user_id'] = user_id

    username = input("Username (supports partial match): ")
    if username:
        filters['username'] = username

    action = input("Action (login, logout, create, read, update, delete): ")
    if action:
        filters['action'] = action

    module = input("Module: ")
    if module:
        filters['module'] = module

    status = input("Status (success, failure): ")
    if status:
        filters['status'] = status

    search_text = input("Search in details: ")
    if search_text:
        filters['search_text'] = search_text

    max_results = input("Maximum results (default: 100): ")
    try:
        max_results = int(max_results) if max_results else 100
    except ValueError:
        max_results = 100

    print("\nSearching logs...")

    results = log_manager.db.search_logs(filters, limit=max_results)

    if not results:
        print("No logs found matching the criteria.")
        return

    # Display results
    print(f"\nFound {len(results)} logs:")
    print("="*80)

    headers = ["Time", "User", "Action", "Module", "Status", "Details"]
    table_data = []

    for log in results[:20]:  # Show first 20
        details = log.get('details', '')
        if len(details) > 40:
            details = details[:37] + '...'

        table_data.append([
            log.get('timestamp', '')[:16],  # Truncate timestamp
            f"{log.get('username', '')}",
            log.get('action', ''),
            log.get('module', ''),
            log.get('status', ''),
            details
        ])

    print(tabulate(table_data, headers=headers, tablefmt="grid"))

    if len(results) > 20:
        print(f"\n... and {len(results) - 20} more results")

    # Options
    print("\nOptions:")
    print("1. Export results")
    print("2. Save search")
    print("3. View more details")
    print("4. Return")

    choice = input("Choose option: ")

    if choice == '1':
        export_search_results(results, filters)
    elif choice == '2':
        save_search(log_manager, auth, filters)
    elif choice == '3':
        view_detailed_results(results)


def export_search_results(results, filters):
    """Export search results"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    print("\nExport format:")
    print("1. CSV")
    print("2. JSON")
    print("3. Excel")

    format_choice = input("Choose format: ")

    export_dir = LOG_DIR / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    export_dir = str(export_dir)

    if format_choice == '1':
        filename = os.path.join(export_dir, f"search_results_{timestamp}.csv")
        df = pd.DataFrame(results)
        df.to_csv(filename, index=False)
    elif format_choice == '2':
        filename = os.path.join(export_dir, f"search_results_{timestamp}.json")
        with open(filename, 'w') as f:
            json.dump({"filters": filters, "results": results}, f, indent=2)
    elif format_choice == '3':
        filename = os.path.join(export_dir, f"search_results_{timestamp}.xlsx")
        df = pd.DataFrame(results)
        df.to_excel(filename, index=False)
    else:
        print("Invalid format choice")
        return

    print(f"Results exported to: {filename}")


def save_search(log_manager, auth, filters):
    """Save search filters for later use"""
    name = input("Enter name for this search: ")
    if not name:
        print("Search name is required")
        return

    try:
        conn = sqlite3.connect(str(_DB_PATH))
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO saved_searches (name, user_id, search_params)
            VALUES (?, ?, ?)
        ''', (name, auth.current_user['id'], json.dumps(filters)))

        conn.commit()
        conn.close()

        print(f"Search '{name}' saved successfully!")
    except Exception as e:
        print(f"Error saving search: {e}")


def view_detailed_results(results):
    """View detailed results"""
    if not results:
        return

    print("\nDetailed Results:")
    print("="*60)

    for i, log in enumerate(results[:10], 1):  # Show first 10 in detail
        print(f"\n{i}. Log Entry:")
        print(f"   Timestamp: {log.get('timestamp', 'N/A')}")
        print(f"   User: {log.get('username', 'N/A')} (ID: {log.get('user_id', 'N/A')})")
        print(f"   Role: {log.get('role', 'N/A')}")
        print(f"   Action: {log.get('action', 'N/A')}")
        print(f"   Module: {log.get('module', 'N/A')}")
        print(f"   Status: {log.get('status', 'N/A')}")
        print(f"   Details: {log.get('details', 'N/A')}")
        if log.get('ip_address'):
            print(f"   IP Address: {log.get('ip_address')}")
        print("-" * 50)

    if len(results) > 10:
        print(f"\n... and {len(results) - 10} more entries")

    input("\nPress Enter to continue...")


def saved_searches_menu(log_manager, auth):
    """Saved searches management"""
    print("\n\U0001f4be SAVED SEARCHES")
    print("="*20)

    try:
        conn = sqlite3.connect(str(_DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM saved_searches
            WHERE user_id = ?
            ORDER BY created_at DESC
        ''', (auth.current_user['id'],))

        searches = cursor.fetchall()
        conn.close()

        if not searches:
            print("No saved searches found.")
            return

        print("\nYour saved searches:")
        for i, search in enumerate(searches, 1):
            print(f"{i}. {search['name']} (created: {search['created_at'][:19]})")

        print(f"\n{len(searches)+1}. Return")

        choice = input("Select search to run: ")

        try:
            choice_num = int(choice)
            if 1 <= choice_num <= len(searches):
                selected_search = searches[choice_num - 1]
                filters = json.loads(selected_search['search_params'])

                print(f"\nRunning search: {selected_search['name']}")
                results = log_manager.db.search_logs(filters, limit=100)

                if results:
                    print(f"Found {len(results)} results")
                    view_detailed_results(results[:5])  # Show first 5
                else:
                    print("No results found")

        except ValueError:
            print("Invalid choice")

    except Exception as e:
        print(f"Error accessing saved searches: {e}")

    input("\nPress Enter to continue...")
