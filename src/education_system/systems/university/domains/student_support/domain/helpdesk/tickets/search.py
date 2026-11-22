from education_system.systems.university.infrastructure.database.db import get_connection
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
    status_map = {'2': 'open', '3': 'in_progress', '4': 'resolved', '5': 'closed'}
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
    print("\nCategory filter:")
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
            from education_system.systems.university.domains.student_support.domain.helpdesk.tickets.cli_support import local_user_id
            save_search_criteria(local_user_id(auth), search_name, criteria)

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
    from education_system.systems.university.domains.student_support.domain.helpdesk.tickets.cli_support import local_user_id
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
    SELECT search_id, name, search_criteria
    FROM saved_searches
    WHERE user_id = ?
    ORDER BY created_at DESC
    ''', (local_user_id(auth),))

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
    """The tickets matching ``criteria`` that the signed-in person may see
    (support staff: their scope; anyone else: the tickets they raised),
    through the ticket service. A confidential ticket's text is the
    service's placeholder unless the viewer raised it."""
    from education_system.systems.university.domains.student_support.domain.helpdesk.tickets.service import (
        iter_tickets,
    )
    from education_system.systems.university.domains.student_support.domain.student_support import (
        auth as support_auth,
    )
    filters = {}
    if criteria.get('text'):
        filters['search'] = criteria['text']
    for key in ('status', 'priority', 'category'):
        if criteria.get(key):
            filters[key] = criteria[key]
    if criteria.get('start_date'):
        filters['date_from'] = criteria['start_date']
    if criteria.get('end_date'):
        filters['date_to'] = f"{criteria['end_date']} 23:59:59"
    if criteria.get('assigned_user'):
        filters['assigned_to'] = criteria['assigned_user']
    mine = not support_auth.is_case_worker(auth)
    try:
        results = list(iter_tickets(auth, filters, mine=mine))
    except (PermissionError, ValueError) as e:
        print(e)
        return []
    results.sort(key=lambda t: str(t.get('updated_at') or ''), reverse=True)
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

    from education_system.systems.university.domains.student_support.domain.helpdesk.tickets.cli_support import (
        status_label, tier_badge,
    )
    for ticket in results:
        assignee = str(ticket.get('assigned_to') or 'Unassigned')
        submitter = str(ticket.get('requester_username') or ticket.get('student_id') or '-')
        subject = (tier_badge(ticket) + ' ' if tier_badge(ticket) else '') + str(ticket.get('subject') or '')
        print(f"{ticket['ticket_id']:<5} {subject[:28]:<30} {submitter[:13]:<15} "
              f"{assignee[:13]:<15} {status_label(ticket)[:12]:<12} "
              f"{str(ticket.get('priority') or '').upper()[:8]:<8} "
              f"{str(ticket.get('updated_at') or ''):<20}")

    print("=" * 100)

    # Ask if user wants to view a specific ticket
    ticket_choice = input("\nEnter ticket number to view details (or press Enter to return): ")

    if ticket_choice:
        try:
            ticket_id = int(ticket_choice)
            from education_system.systems.university.domains.student_support.domain.helpdesk.tickets.display import view_ticket_detail_enhanced
            view_ticket_detail_enhanced(auth, ticket_id)
        except ValueError:
            print("Invalid ticket number.")
