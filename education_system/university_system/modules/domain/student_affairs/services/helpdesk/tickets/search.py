from education_system.university_system.core.sql_safety import escape_like
from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)


def advanced_search_tickets(auth):
    if not auth or not auth.current_user:
        print("You must be logged in to search tickets.")
        return

    print("\nAdvanced Ticket Search")
    print("=====================")

    # Build search criteria
    criteria = {}

    # Text search
    search_text = input("Search text (subject/message): ").strip()
    if search_text:
        criteria['text'] = search_text

    # Status filter
    print("\nStatus filter:")
    print("1. All statuses")
    print("2. Open only")
    print("3. In progress only")
    print("4. Resolved only")
    print("5. Closed only")

    status_choice = input("Select status filter (1-5): ").strip()
    status_map = {'2': 'open', '3': 'in progress', '4': 'resolved', '5': 'closed'}
    if status_choice in status_map:
        criteria['status'] = status_map[status_choice]

    # Priority filter
    print("\nPriority filter:")
    print("1. All priorities")
    print("2. Low only")
    print("3. Medium only")
    print("4. High only")

    priority_choice = input("Select priority filter (1-4): ").strip()
    priority_map = {'2': 'low', '3': 'medium', '4': 'high'}
    if priority_choice in priority_map:
        criteria['priority'] = priority_map[priority_choice]

    # Category filter
    categories = ["Technical Support", "Academic Inquiry", "Financial Services", "Account Access", "Other"]
    print(f"\nCategory filter:")
    print("0. All categories")
    for i, cat in enumerate(categories, 1):
        print(f"{i}. {cat}")

    cat_choice = input("Select category (0-5): ").strip()
    try:
        cat_idx = int(cat_choice)
        if 1 <= cat_idx <= len(categories):
            criteria['category'] = categories[cat_idx - 1]
    except ValueError as e:
        logger.debug(f"Invalid category selection input: {e}")

    # Date range
    start_date = input("Start date (YYYY-MM-DD, or press Enter to skip): ").strip()
    if start_date:
        try:
            datetime.strptime(start_date, '%Y-%m-%d')
            criteria['start_date'] = start_date
        except ValueError:
            print("Invalid date format, skipping date filter.")

    end_date = input("End date (YYYY-MM-DD, or press Enter to skip): ").strip()
    if end_date:
        try:
            datetime.strptime(end_date, '%Y-%m-%d')
            criteria['end_date'] = end_date
        except ValueError:
            print("Invalid date format, skipping date filter.")

    # Assigned user filter (admin only)
    if auth.check_permission('view_all_tickets'):
        assigned_user = input("Assigned to username (or press Enter to skip): ").strip()
        if assigned_user:
            criteria['assigned_user'] = assigned_user

    # Save search option
    save_search = input("Save this search? (y/n): ").strip().lower()
    if save_search == 'y':
        search_name = input("Enter search name: ").strip()
        if search_name:
            save_search_criteria(auth.current_user['id'], search_name, criteria)

    # Execute search
    results = execute_search(auth, criteria)
    display_search_results(auth, results)

def save_search_criteria(user_id, name, criteria):
    """Save search criteria for later use"""
    conn = get_connection()
    cursor = conn.cursor()

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute('''
    INSERT INTO saved_searches (user_id, name, search_criteria, created_at)
    VALUES (?, ?, ?, ?)
    ''', (user_id, name, json.dumps(criteria), now))

    conn.commit()
    conn.close()
    print(f"Search '{name}' saved successfully!")

def load_saved_searches(auth):
    """Load and execute saved searches"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
    SELECT search_id, name, search_criteria
    FROM saved_searches
    WHERE user_id = ?
    ORDER BY created_at DESC
    ''', (auth.current_user['id'],))

    searches = cursor.fetchall()

    if not searches:
        print("No saved searches found.")
        conn.close()
        return

    print("\nSaved Searches:")
    for i, search in enumerate(searches, 1):
        print(f"{i}. {search[1]}")

    choice = input("Select search to execute (or press Enter to cancel): ").strip()

    try:
        idx = int(choice) - 1
        if 0 <= idx < len(searches):
            search_id, name, criteria_json = searches[idx]
            criteria = json.loads(criteria_json)

            print(f"\nExecuting search: {name}")
            results = execute_search(auth, criteria)
            display_search_results(auth, results)
    except (ValueError, json.JSONDecodeError):
        print("Invalid selection or corrupted search data.")

    conn.close()

def execute_search(auth, criteria):
    """Execute search with given criteria"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Build query
    where_conditions = []
    params = []

    # Check permissions
    if not auth.check_permission('view_all_tickets'):
        where_conditions.append("t.user_id = ?")
        params.append(auth.current_user['id'])

    # Text search
    if 'text' in criteria:
        where_conditions.append("(t.subject LIKE ? OR t.message LIKE ?)")
        text_param = f"%{escape_like(criteria['text'])}%"
        params.extend([text_param, text_param])

    # Status filter
    if 'status' in criteria:
        where_conditions.append("t.status = ?")
        params.append(criteria['status'])

    # Priority filter
    if 'priority' in criteria:
        where_conditions.append("t.priority = ?")
        params.append(criteria['priority'])

    # Category filter
    if 'category' in criteria:
        where_conditions.append("t.category = ?")
        params.append(criteria['category'])

    # Date range
    if 'start_date' in criteria:
        where_conditions.append("DATE(t.created_at) >= ?")
        params.append(criteria['start_date'])

    if 'end_date' in criteria:
        where_conditions.append("DATE(t.created_at) <= ?")
        params.append(criteria['end_date'])

    # Assigned user
    if 'assigned_user' in criteria:
        where_conditions.append("u2.username = ?")
        params.append(criteria['assigned_user'])

    # Build final query
    where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"

    query = f'''
    SELECT t.*, u1.username as submitter, u2.username as assignee
    FROM support_tickets t
    JOIN users u1 ON t.user_id = u1.id
    LEFT JOIN users u2 ON t.assigned_to = u2.id
    WHERE {where_clause}
    ORDER BY t.updated_at DESC
    '''

    cursor.execute(query, params)
    results = cursor.fetchall()

    conn.close()
    return results

def display_search_results(auth, results):
    """Display search results"""
    if not results:
        print("\nNo tickets found matching your search criteria.")
        return

    print(f"\nSearch Results ({len(results)} tickets found):")
    print("=" * 120)
    print(f"{'ID':<5} {'Subject':<30} {'From':<15} {'Assigned':<15} {'Status':<12} {'Priority':<8} {'Updated':<20}")
    print("=" * 120)

    for ticket in results:
        assignee = ticket['assignee'] or 'Unassigned'
        print(f"{ticket['ticket_id']:<5} {ticket['subject'][:28]:<30} {ticket['submitter'][:13]:<15} "
              f"{assignee[:13]:<15} {ticket['status'].upper():<12} {ticket['priority'].upper():<8} "
              f"{ticket['updated_at']:<20}")

    print("=" * 100)

    # Ask if user wants to view a specific ticket
    ticket_choice = input("\nEnter ticket number to view details (or press Enter to return): ")

    if ticket_choice:
        try:
            ticket_id = int(ticket_choice)
            from education_system.university_system.modules.domain.student_affairs.services.helpdesk.tickets.display import view_ticket_detail_enhanced
            view_ticket_detail_enhanced(auth, ticket_id)
        except ValueError:
            print("Invalid ticket number.")
