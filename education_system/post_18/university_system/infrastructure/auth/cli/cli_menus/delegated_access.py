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

def _display_delegated_access_menu(auth):
    """Display delegated access sub-menu"""
    while True:
        if not auth.check_session():
            return

        user = auth.current_user
        role = user.get('role', '')

        print("\nDelegated Access:")
        print("=================")

        if role == 'student':
            print("1. View My Delegations (Granted)")
            print("2. Grant Access to Someone")
            print("3. Revoke a Delegation")
            print("4. View Delegation Requests")
            print("5. Back")

            choice = input("\nEnter your choice (1-5): ")

            if choice == '1':
                delegations = auth.get_delegations_for_user(direction='granted')
                if delegations:
                    print("\nActive Delegations (you granted):")
                    for d in delegations:
                        print(f"  #{d.get('id')} -> User {d.get('delegate_user_id')} | Scopes: {d.get('scope_keys')} | Expires: {d.get('expires_at', 'Never')}")
                else:
                    print("No active delegations.")

            elif choice == '2':
                delegate_id = input("Enter user ID to grant access to: ").strip()
                print("\nAvailable scopes: view_grades, view_finances, view_health, view_attendance, view_timetable, make_payments, communicate_staff")
                scopes = input("Enter scope keys (comma-separated): ").strip()
                relationship = input("Relationship (e.g., parent, guardian): ").strip() or None
                expires = input("Expiry date (YYYY-MM-DD, blank for no expiry): ").strip() or None
                try:
                    scope_keys = [s.strip() for s in scopes.split(',') if s.strip()]
                    result = auth.create_delegation(int(delegate_id), scope_keys, relationship, expires)
                    if result.get('success'):
                        print(f"Delegation created (ID: {result.get('delegation_id')})")
                    else:
                        print(f"Failed: {result.get('error')}")
                except ValueError:
                    print("Invalid input.")

            elif choice == '3':
                delegation_id = input("Enter delegation ID to revoke: ").strip()
                try:
                    result = auth.revoke_delegation(int(delegation_id))
                    if result.get('success'):
                        print("Delegation revoked.")
                    else:
                        print(f"Failed: {result.get('error')}")
                except ValueError:
                    print("Invalid delegation ID.")

            elif choice == '4':
                requests = auth.get_delegation_requests(direction='incoming')
                if requests:
                    print("\nPending Delegation Requests:")
                    for r in requests:
                        print(f"  #{r.get('id')} from User {r.get('requester_user_id')} | Relationship: {r.get('relationship')} | Scopes: {r.get('requested_scope_keys')}")
                    action = input("\nApprove or Reject? (a/r/n): ").strip().lower()
                    if action in ('a', 'r'):
                        req_id = input("Request ID: ").strip()
                        try:
                            if action == 'a':
                                result = auth.approve_delegation_request(int(req_id))
                            else:
                                reason = input("Reason (optional): ").strip() or None
                                result = auth.reject_delegation_request(int(req_id), reason)
                            print(f"Result: {'Success' if result.get('success') else result.get('error')}")
                        except ValueError:
                            print("Invalid ID.")
                else:
                    print("No pending requests.")

            elif choice == '5':
                return

        elif role == 'parent':
            print("1. View My Delegations (Received)")
            print("2. Request Access to a Student")
            print("3. View My Requests")
            print("4. Act as Delegate")
            print("5. Stop Acting as Delegate")
            print("6. Back")

            choice = input("\nEnter your choice (1-6): ")

            if choice == '1':
                delegations = auth.get_delegations_for_user(direction='received')
                if delegations:
                    print("\nActive Delegations (granted to you):")
                    for d in delegations:
                        print(f"  #{d.get('id')} from User {d.get('grantor_user_id')} | Scopes: {d.get('scope_keys')} | Expires: {d.get('expires_at', 'Never')}")
                else:
                    print("No active delegations.")

            elif choice == '2':
                target_id = input("Enter student user ID: ").strip()
                relationship = input("Relationship (parent/guardian): ").strip()
                print("\nAvailable scopes: view_grades, view_finances, view_health, view_attendance, view_timetable, make_payments, communicate_staff")
                scopes = input("Enter requested scope keys (comma-separated): ").strip()
                reason = input("Reason for request: ").strip() or None
                try:
                    scope_keys = [s.strip() for s in scopes.split(',') if s.strip()]
                    result = auth.create_delegation_request(int(target_id), relationship, scope_keys, reason)
                    if result.get('success'):
                        print(f"Request submitted (ID: {result.get('request_id')})")
                    else:
                        print(f"Failed: {result.get('error')}")
                except ValueError:
                    print("Invalid input.")

            elif choice == '3':
                requests = auth.get_delegation_requests(direction='outgoing')
                if requests:
                    print("\nMy Delegation Requests:")
                    for r in requests:
                        print(f"  #{r.get('id')} to User {r.get('target_user_id')} | Status: {r.get('status')}")
                else:
                    print("No requests found.")

            elif choice == '4':
                delegations = auth.get_delegations_for_user(direction='received')
                if delegations:
                    for d in delegations:
                        print(f"  #{d.get('id')} from User {d.get('grantor_user_id')} | Scopes: {d.get('scope_keys')}")
                    target_id = input("Enter grantor user ID to act on behalf of: ").strip()
                    try:
                        auth.session_manager.current_user['acting_as_delegate_for'] = int(target_id)
                        print(f"Now acting as delegate for user {target_id}. Your permissions are scoped.")
                    except (ValueError, TypeError):
                        print("Invalid user ID.")
                else:
                    print("No delegations available.")

            elif choice == '5':
                if user.get('acting_as_delegate_for'):
                    auth.session_manager.current_user['acting_as_delegate_for'] = None
                    print("Stopped acting as delegate.")
                else:
                    print("You are not currently acting as a delegate.")

            elif choice == '6':
                return

        else:
            # Admin or other roles
            print("1. View All Delegations")
            print("2. View Delegation Requests")
            print("3. Expire Overdue Delegations")
            print("4. Back")

            choice = input("\nEnter your choice (1-4): ")

            if choice == '1':
                user_id_input = input("Enter user ID (blank for all): ").strip()
                user_id = int(user_id_input) if user_id_input else None
                delegations = auth.get_delegations_for_user(user_id, direction='granted')
                if delegations:
                    print("\nDelegations:")
                    for d in delegations:
                        print(f"  #{d.get('id')} | Grantor: {d.get('grantor_user_id')} -> Delegate: {d.get('delegate_user_id')} | Active: {d.get('is_active')}")
                else:
                    print("No delegations found.")

            elif choice == '2':
                requests = auth.get_delegation_requests(status='pending')
                if requests:
                    print("\nPending Delegation Requests:")
                    for r in requests:
                        print(f"  #{r.get('id')} | Requester: {r.get('requester_user_id')} -> Target: {r.get('target_user_id')}")
                else:
                    print("No pending requests.")

            elif choice == '3':
                result = auth.expire_delegations()
                if result.get('success'):
                    print(f"Expired {result.get('expired_count', 0)} delegation(s).")
                else:
                    print(f"Failed: {result.get('error')}")

            elif choice == '4':
                return


# ============================================================================
# Chatbot Integration Menu
# ============================================================================

