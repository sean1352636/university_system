"""Split from cli_menus.py — assembled in package __init__.py."""
from __future__ import annotations

import sys
import json
import logging
import random
import secrets
import string
from pathlib import Path
from datetime import datetime

from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from education_system.post_18.university_system.core.exceptions import (
    AuthenticationError,
    InvalidCredentialsError,
    DatabaseError,
)

logger = logging.getLogger("education_system.post_18.university_system.infrastructure.auth.cli.cli_menus")

def _display_account_linking_menu(auth):
    """Display account linking sub-menu"""
    while True:
        if not auth.check_session():
            return

        user = auth.current_user
        print("\nAccount Linking:")
        print("================")
        print("1. View Linked Accounts")
        print("2. Create Link Request")
        print("3. View Pending Link Requests")
        print("4. Switch Active Role")
        print("5. Revert to Original Role")
        print("6. Unlink Account")
        print("7. Back")

        choice = input("\nEnter your choice (1-7): ")

        if choice == '1':
            linked = auth.get_linked_accounts()
            if linked:
                print("\nLinked Accounts:")
                print("=" * 70)
                for acc in linked:
                    print(f"  Link #{acc.get('id')}: {acc.get('primary_username', 'N/A')} <-> {acc.get('secondary_username', 'N/A')} (Active: {acc.get('is_active')})")
                print("=" * 70)
            else:
                print("No linked accounts found.")

        elif choice == '2':
            target = input("Enter user ID to link with: ").strip()
            reason = input("Reason for linking (optional): ").strip() or None
            try:
                result = auth.create_link_request(int(target), reason)
                if result.get('success'):
                    print(f"Link request created (ID: {result.get('request_id')})")
                else:
                    print(f"Failed: {result.get('error')}")
            except ValueError:
                print("Invalid user ID.")

        elif choice == '3':
            direction = input("View (i)ncoming or (o)utgoing requests? [i]: ").strip().lower()
            direction = 'outgoing' if direction == 'o' else 'incoming'
            requests = auth.get_link_requests(status='pending', direction=direction)
            if requests:
                print(f"\n{direction.title()} Link Requests:")
                for req in requests:
                    print(f"  Request #{req.get('id')}: from user {req.get('requesting_user_id')} to user {req.get('target_user_id')} - {req.get('status')}")

                if direction == 'incoming':
                    action = input("\nApprove or Reject a request? (a/r/n): ").strip().lower()
                    if action in ('a', 'r'):
                        req_id = input("Enter request ID: ").strip()
                        try:
                            if action == 'a':
                                result = auth.approve_link_request(int(req_id))
                            else:
                                reason = input("Rejection reason (optional): ").strip() or None
                                result = auth.reject_link_request(int(req_id), reason)
                            print(f"{'Approved' if action == 'a' else 'Rejected'}: {result.get('success')}")
                        except ValueError:
                            print("Invalid request ID.")
            else:
                print("No pending requests.")

        elif choice == '4':
            linked = auth.get_linked_accounts()
            if linked:
                for acc in linked:
                    print(f"  Link #{acc.get('id')}: {acc.get('primary_username')} <-> {acc.get('secondary_username')}")
                link_id = input("Enter link ID to switch to: ").strip()
                try:
                    result = auth.switch_active_role(int(link_id))
                    if result.get('success'):
                        print(f"Switched to role: {result.get('new_role')}")
                    else:
                        print(f"Failed: {result.get('error')}")
                except ValueError:
                    print("Invalid link ID.")
            else:
                print("No linked accounts to switch to.")

        elif choice == '5':
            result = auth.revert_role()
            if result.get('success'):
                print(f"Reverted to original role: {result.get('role')}")
            else:
                print(f"Failed: {result.get('error')}")

        elif choice == '6':
            link_id = input("Enter link ID to unlink: ").strip()
            try:
                confirm = input("Are you sure? (y/n): ").lower()
                if confirm == 'y':
                    result = auth.unlink_account(int(link_id))
                    if result.get('success'):
                        print("Account unlinked.")
                    else:
                        print(f"Failed: {result.get('error')}")
            except ValueError:
                print("Invalid link ID.")

        elif choice == '7':
            return
        else:
            print("Invalid choice.")


# ============================================================================
# WebAuthn Menu
# ============================================================================

