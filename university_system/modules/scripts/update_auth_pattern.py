#!/usr/bin/env python3
"""
Script to update all Python files in university_system to use centralized auth system.
Replaces local auth patterns with imports from user_authentication.
"""

import os
import re
from pathlib import Path

# Template for the new auth pattern (from student_support.py lines 35-51)
NEW_AUTH_PATTERN = """# Import auth instance management from user_authentication
try:
    from university_system.infrastructure.auth.user_authentication import get_current_user, set_auth_instance
    HAS_AUTH = True
except ImportError:
    HAS_AUTH = False
    get_current_user = lambda: None
    set_auth_instance = lambda x: None

auth = None

def set_auth(auth_instance):
    global auth
    auth = auth_instance
    # Also set it in the global auth instance if available
    if HAS_AUTH:
        set_auth_instance(auth_instance)"""

# Get the project root dynamically
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent

# Files to update (relative to project root)
FILES_TO_UPDATE = [
    PROJECT_ROOT / "modules/interfaces/gui/finance_reporting_gui.py",
    PROJECT_ROOT / "modules/interfaces/gui/main_gui.py",
    PROJECT_ROOT / "modules/domain/academics/services/academic_calendar.py",
    PROJECT_ROOT / "modules/restaurant/customer/reservation_system.py",
    PROJECT_ROOT / "modules/domain/academics/services/library.py",
    PROJECT_ROOT / "infrastructure/email/admin.py",
    PROJECT_ROOT / "modules/core/services/restaurant_misc/connection.py",
    PROJECT_ROOT / "modules/core/services/student_union_misc/context_setup.py",
    PROJECT_ROOT / "modules/interfaces/gui/library_gui.py",
    PROJECT_ROOT / "modules/interfaces/cli/main.py",
    PROJECT_ROOT / "modules/domain/housing/services/accommodation.py",
    PROJECT_ROOT / "modules/domain/student_affairs/student_union/clubs/club_management.py",
    PROJECT_ROOT / "modules/domain/student_affairs/student_union/administration/student_union_core.py",
    PROJECT_ROOT / "modules/domain/commerce/services/restaurant_management.py",
    PROJECT_ROOT / "modules/core/services/restaurant_misc/context.py",
    PROJECT_ROOT / "modules/domain/commerce/services/shop_management.py",
    PROJECT_ROOT / "modules/finance/finance_misc/context.py",
    PROJECT_ROOT / "modules/domain/student_affairs/student_union/administration/admin_management.py",
    PROJECT_ROOT / "modules/domain/student_affairs/student_union/administration/finance_oversight.py",
    PROJECT_ROOT / "modules/domain/student_affairs/student_union/elections/election_management.py",
    PROJECT_ROOT / "modules/domain/student_affairs/student_union/events/event_management.py",
    PROJECT_ROOT / "modules/domain/student_affairs/student_union/facilities/facility_management.py",
    PROJECT_ROOT / "modules/restaurant/staff/staff_administration.py",
    PROJECT_ROOT / "modules/restaurant/operations/order_processing.py",
    PROJECT_ROOT / "modules/restaurant/operations/inventory_management.py",
    PROJECT_ROOT / "modules/restaurant/operations/financial_reporting.py",
    PROJECT_ROOT / "modules/restaurant/menu/menu_management.py",
    PROJECT_ROOT / "modules/restaurant/customer/loyalty_program.py",
    PROJECT_ROOT / "modules/restaurant/operations/restaurant_core.py",
    PROJECT_ROOT / "modules/domain/mobility/services/trip_management.py",
    PROJECT_ROOT / "modules/shared/utils/state.py",
    PROJECT_ROOT / "modules/finance/reporting/financial_reports.py",
    PROJECT_ROOT / "modules/domain/mobility/services/parking_management.py",
    PROJECT_ROOT / "modules/domain/student_affairs/services/alumni_management.py",
    PROJECT_ROOT / "modules/domain/student_affairs/services/internship_management.py",
    PROJECT_ROOT / "modules/domain/housing/services/housing_accommodation.py",
]

def find_auth_pattern(content):
    """
    Find the old auth pattern in the content.
    Returns: (start_pos, end_pos, matched_text) or (None, None, None)
    """
    # Pattern 1: Simple "auth = None" followed by optional blank lines and "def set_auth"
    pattern1 = re.compile(
        r'^(# Global auth.*?\n)?auth = None\n+(?:def set_auth\([^)]+\):.*?(?=\n(?:[a-zA-Z]|#|$)))',
        re.MULTILINE | re.DOTALL
    )

    match = pattern1.search(content)
    if match:
        return match.start(), match.end(), match.group(0)

    # Pattern 2: Just "auth = None" without set_auth function
    pattern2 = re.compile(r'^(# Global auth.*?\n)?auth = None\n', re.MULTILINE)
    match = pattern2.search(content)
    if match:
        # Check if there's a set_auth function within next 200 characters
        next_section = content[match.end():match.end()+500]
        set_auth_pattern = re.compile(r'def set_auth\([^)]+\):.*?(?=\n(?:[a-zA-Z]|#|class |def [^s]|$))', re.DOTALL)
        set_auth_match = set_auth_pattern.search(next_section)

        if set_auth_match:
            return match.start(), match.end() + set_auth_match.end(), content[match.start():match.end() + set_auth_match.end()]
        else:
            return match.start(), match.end(), match.group(0)

    return None, None, None

def update_file(filepath):
    """
    Update a single file with the new auth pattern.
    Returns: (success, message)
    """
    try:
        # Convert to Path object if string
        filepath = Path(filepath)

        # Check if file exists
        if not filepath.exists():
            return False, f"File not found: {filepath}"

        # Read the file
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check if already updated (has the new pattern)
        if 'from university_system.infrastructure.auth.user_authentication import get_current_user, set_auth_instance' in content:
            return True, f"Already updated (skipped)"

        # Find the old auth pattern
        start_pos, end_pos, old_pattern = find_auth_pattern(content)

        if start_pos is None:
            # Try to find just "auth = None"
            auth_none_pattern = re.compile(r'^auth = None\s*$', re.MULTILINE)
            match = auth_none_pattern.search(content)
            if match:
                start_pos = match.start()
                end_pos = match.end()
                old_pattern = match.group(0)
            else:
                return False, f"Could not find auth pattern"

        # Replace the old pattern with the new one
        new_content = content[:start_pos] + NEW_AUTH_PATTERN + content[end_pos:]

        # Write the updated content back
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)

        return True, "Updated successfully"

    except Exception as e:
        return False, f"Error: {str(e)}"

def main():
    """Main function to update all files."""
    print("="*70)
    print("UPDATING AUTH PATTERNS IN UNIVERSITY SYSTEM")
    print("="*70)
    print()

    results = {
        'success': [],
        'skipped': [],
        'failed': []
    }

    for filepath in FILES_TO_UPDATE:
        filename = filepath.name
        print(f"Processing: {filename}...", end=" ")

        success, message = update_file(filepath)

        if success:
            if "skipped" in message.lower():
                results['skipped'].append((filename, message))
                print(f"SKIPPED - {message}")
            else:
                results['success'].append((filename, message))
                print(f"SUCCESS - {message}")
        else:
            results['failed'].append((filename, message))
            print(f"FAILED - {message}")

    # Print summary
    print()
    print("="*70)
    print("SUMMARY")
    print("="*70)
    print(f"Total files processed: {len(FILES_TO_UPDATE)}")
    print(f"Successfully updated: {len(results['success'])}")
    print(f"Already updated (skipped): {len(results['skipped'])}")
    print(f"Failed: {len(results['failed'])}")
    print()

    if results['failed']:
        print("FAILED FILES:")
        print("-"*70)
        for filename, message in results['failed']:
            print(f"  - {filename}: {message}")
        print()

    if results['success']:
        print("SUCCESSFULLY UPDATED FILES:")
        print("-"*70)
        for filename, message in results['success']:
            print(f"  - {filename}")
        print()

if __name__ == "__main__":
    main()
