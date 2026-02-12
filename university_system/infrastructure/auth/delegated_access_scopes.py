"""
Delegated Access Scopes

Defines the available delegation scopes that map to specific permissions.
Each scope represents a category of access that can be granted to a delegate.
"""

DELEGATION_SCOPES = {
    'view_grades': {
        'description': 'View academic grades and transcripts',
        'permissions': ['view_own_grades', 'view_own_transcript'],
    },
    'view_finances': {
        'description': 'View financial information and fee statements',
        'permissions': ['view_own_finances', 'view_fees'],
    },
    'view_health': {
        'description': 'View health records and appointments',
        'permissions': ['view_own_health_record'],
    },
    'view_attendance': {
        'description': 'View attendance records',
        'permissions': ['view_own_attendance'],
    },
    'view_timetable': {
        'description': 'View class timetable and schedules',
        'permissions': ['view_own_timetable'],
    },
    'make_payments': {
        'description': 'Make payments on behalf of the student',
        'permissions': ['make_payments'],
    },
    'communicate_staff': {
        'description': 'Communicate with staff and teachers',
        'permissions': ['send_emails', 'message_teachers'],
    },
}


def get_scope_permissions(scope_keys):
    """
    Get the combined list of permissions for the given scope keys.

    Parameters:
        scope_keys (list): List of scope key strings

    Returns:
        list: Combined list of permission strings
    """
    permissions = []
    for key in scope_keys:
        scope = DELEGATION_SCOPES.get(key)
        if scope:
            permissions.extend(scope['permissions'])
    return list(set(permissions))


def get_all_scope_keys():
    """Return all available scope keys."""
    return list(DELEGATION_SCOPES.keys())


def get_scope_descriptions():
    """Return a dict mapping scope keys to their descriptions."""
    return {key: scope['description'] for key, scope in DELEGATION_SCOPES.items()}
