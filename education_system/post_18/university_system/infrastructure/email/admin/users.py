"""User search and listing functions."""

from __future__ import annotations

from education_system.post_18.university_system.core.sql_safety import escape_like
from education_system.post_18.university_system.infrastructure.email.admin._imports import (
    execute_db_operation,
    handle_exception,
    log_event,
)


@handle_exception
def search_users(auth, search_term):
    """Search for users by username, first name, or last name using auth users table"""
    if not auth or not auth.current_user:
        log_event('error', "Must be logged in to search for users")
        return []

    def _search_users(cursor):
        search_pattern = f"%{escape_like(search_term)}%"

        # Use the auth users table structure
        cursor.execute('''
        SELECT id, username, first_name, last_name, email, role
        FROM users
        WHERE username LIKE ? OR first_name LIKE ? OR last_name LIKE ?
        ORDER BY username
        LIMIT 50
        ''', (search_pattern, search_pattern, search_pattern))

        users = []
        for row in cursor.fetchall():
            users.append({
                'id': row[0],
                'username': row[1],
                'first_name': row[2],
                'last_name': row[3],
                'email': row[4],
                'role': row[5],
                'full_name': f"{row[2]} {row[3]}"
            })

        return users

    try:
        return execute_db_operation(_search_users)
    except Exception as e:
        log_event('error', f"Error searching users: {e}")
        return []



@handle_exception
def list_all_users(auth, page=1, limit=10, role_filter=None):
    """List all users with pagination using auth users table"""
    if not auth or not auth.current_user:
        log_event('error', "Must be logged in to list users")
        return {'users': [], 'total_count': 0, 'page': page, 'limit': limit, 'total_pages': 0}

    def _list_users(cursor):
        # Build query with optional role filter
        where_clause = ""
        params = []

        if role_filter:
            where_clause = "WHERE u.role = ?"
            params.append(role_filter)

        # Get total count
        cursor.execute('SELECT COUNT(*) FROM users u ' + where_clause, params)
        total_count = cursor.fetchone()[0]

        # Calculate offset
        offset = (page - 1) * limit
        total_pages = (total_count + limit - 1) // limit if limit > 0 else 1

        # Get users for current page
        cursor.execute('''
        SELECT u.id, u.username, u.first_name, u.last_name, u.email, u.role
        FROM users u ''' + where_clause + '''
        ORDER BY u.first_name, u.last_name, u.username
        LIMIT ? OFFSET ?
        ''', params + [limit, offset])

        users = []
        for row in cursor.fetchall():
            users.append({
                'id': row[0],
                'username': row[1],
                'first_name': row[2],
                'last_name': row[3],
                'email': row[4],
                'role': row[5],
                'full_name': f"{row[2]} {row[3]}".strip()
            })

        return {
            'users': users,
            'total_count': total_count,
            'page': page,
            'limit': limit,
            'total_pages': total_pages
        }

    try:
        return execute_db_operation(_list_users)
    except Exception as e:
        log_event('error', f"Error listing users: {e}")
        return {'users': [], 'total_count': 0, 'page': page, 'limit': limit, 'total_pages': 0}
