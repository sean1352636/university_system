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

from ._shared import ROLES

def display_role_management_menu(auth):
    """Display the role management menu"""
    while True:
        if not auth.check_session() or not auth.check_permission('manage_roles'):
            print("You don't have permission to access Role Management.")
            return

        print("\nRole Management:")
        print("===============")
        print("1. List All Roles")
        print("2. Create New Role")
        print("3. View Role Details")
        print("4. Edit Role")
        print("5. Delete Role")
        print("6. Manage Role Permissions")
        print("7. List All Permissions")
        print("8. Create New Permission")
        print("9. Back")

        choice = input("\nEnter your choice (1-9): ")

        if choice == '1':
            # List all roles
            roles = auth.list_roles()

            if roles:
                print("\nAll Roles:")
                print("=" * 70)
                print(f"{'ID':<5} {'Role Name':<15} {'Description':<30} {'Users':<10}")
                print("-" * 70)

                for role in roles:
                    print(f"{role['id']:<5} {role['role_name']:<15} {role['description'][:28]:<30} {role['user_count']:<10}")

                print("=" * 70)

        elif choice == '2':
            # Create new role
            print("\nCreate New Role:")
            role_name = input("Role Name: ")
            description = input("Description: ")

            # Get permissions
            conn = auth._create_configured_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT id, permission_name, description FROM permissions ORDER BY permission_name')
            all_permissions = cursor.fetchall()
            conn.close()

            if all_permissions:
                print("\nSelect permissions (comma-separated numbers, blank for none):")
                for i, perm in enumerate(all_permissions, 1):
                    perm_id, perm_name, perm_desc = perm
                    print(f"{i}. {perm_name} - {perm_desc}")

                perm_choices = input("\nPermissions: ")

                selected_permissions = []
                if perm_choices:
                    try:
                        indices = [int(idx.strip()) - 1 for idx in perm_choices.split(',')]
                        selected_permissions = [all_permissions[idx][1] for idx in indices if 0 <= idx < len(all_permissions)]
                    except ValueError:
                        print("Invalid input. No permissions will be added.")

                auth.create_role(role_name, description, selected_permissions)
            else:
                auth.create_role(role_name, description)

        elif choice == '3':
            # View role details
            role_id = input("Enter role ID to view: ")

            try:
                role_id = int(role_id)
                role = auth.get_role(role_id=role_id)

                if role:
                    print("\nRole Details:")
                    print("=" * 60)
                    print(f"ID: {role['id']}")
                    print(f"Name: {role['role_name']}")
                    print(f"Description: {role['description']}")
                    print(f"Created: {role['created_at']}")
                    print(f"Updated: {role['updated_at']}")
                    print(f"Users with this role: {role['user_count']}")

                    print("\nPermissions:")
                    for perm in role['permissions']:
                        print(f"- {perm}")

                    print("=" * 60)

            except ValueError:
                print("Invalid role ID. Please enter a number.")

        elif choice == '4':
            # Edit role
            role_id = input("Enter role ID to edit: ")

            try:
                role_id = int(role_id)
                role = auth.get_role(role_id=role_id)

                if role:
                    # Check if this is a default role
                    if role['role_name'] in ROLES:
                        print(f"Cannot edit default role '{role['role_name']}'.")
                        continue

                    print("\nEdit Role:")
                    print(f"Current Name: {role['role_name']}")
                    print(f"Current Description: {role['description']}")

                    print("\nEnter new values (leave blank to keep current):")
                    new_name = input("New Name: ")
                    new_description = input("New Description: ")

                    # Build update dictionary
                    updates = {}
                    if new_name:
                        updates['role_name'] = new_name
                    if new_description:
                        updates['description'] = new_description

                    if updates:
                        auth.update_role(role_id, **updates)
                    else:
                        print("No changes made.")

            except ValueError:
                print("Invalid role ID. Please enter a number.")

        elif choice == '5':
            # Delete role
            role_id = input("Enter role ID to delete: ")

            try:
                role_id = int(role_id)
                role = auth.get_role(role_id=role_id)

                if role:
                    # Check if this is a default role
                    if role['role_name'] in ROLES:
                        print(f"Cannot delete default role '{role['role_name']}'.")
                        continue

                    # Check if any users have this role
                    if role['user_count'] > 0:
                        print(f"Cannot delete role '{role['role_name']}' because it is assigned to {role['user_count']} user(s).")
                        continue

                    # Confirm deletion
                    confirm = input(f"Are you sure you want to delete role '{role['role_name']}'? (y/n): ").lower()

                    if confirm == 'y':
                        auth.delete_role(role_id)

            except ValueError:
                print("Invalid role ID. Please enter a number.")

        elif choice == '6':
            # Manage role permissions
            role_id = input("Enter role ID to manage permissions: ")

            try:
                role_id = int(role_id)
                role = auth.get_role(role_id=role_id)

                if role:
                    # Check if this is a default role
                    if role['role_name'] in ROLES:
                        print(f"Cannot modify permissions for default role '{role['role_name']}'.")
                        continue

                    while True:
                        print(f"\nPermissions for role '{role['role_name']}':")
                        print("=" * 60)

                        # Get all permissions
                        conn = auth._create_configured_connection()
                        cursor = conn.cursor()
                        cursor.execute('SELECT permission_name FROM permissions ORDER BY permission_name')
                        all_permissions = [row[0] for row in cursor.fetchall()]
                        conn.close()

                        # Check which permissions the role has
                        role_permissions = role['permissions']

                        for i, perm in enumerate(all_permissions, 1):
                            status = "✓" if perm in role_permissions else " "
                            print(f"{i:2}. [{status}] {perm}")

                        print("\n1. Add permission")
                        print("2. Remove permission")
                        print("3. Back")

                        perm_choice = input("\nEnter choice (1-3): ")

                        if perm_choice == '1':
                            # Add permission
                            perm_number = input("Enter permission number to add: ")

                            try:
                                perm_index = int(perm_number) - 1
                                if 0 <= perm_index < len(all_permissions):
                                    perm_name = all_permissions[perm_index]
                                    auth.add_role_permission(role_id, perm_name)
                                    # Refresh role data
                                    role = auth.get_role(role_id=role_id)
                                else:
                                    print("Invalid permission number.")
                            except ValueError:
                                print("Please enter a number.")

                        elif perm_choice == '2':
                            # Remove permission
                            perm_number = input("Enter permission number to remove: ")

                            try:
                                perm_index = int(perm_number) - 1
                                if 0 <= perm_index < len(all_permissions):
                                    perm_name = all_permissions[perm_index]
                                    auth.remove_role_permission(role_id, perm_name)
                                    # Refresh role data
                                    role = auth.get_role(role_id=role_id)
                                else:
                                    print("Invalid permission number.")
                            except ValueError:
                                print("Please enter a number.")

                        elif perm_choice == '3':
                            break
                        else:
                            print("Invalid choice.")

            except ValueError:
                print("Invalid role ID. Please enter a number.")

        elif choice == '7':
            # List all permissions
            permissions = auth.list_permissions()

            if permissions:
                print("\nAll Permissions:")
                print("=" * 80)
                print(f"{'ID':<5} {'Permission Name':<30} {'Description':<45}")
                print("-" * 80)

                for perm in permissions:
                    print(f"{perm['id']:<5} {perm['permission_name']:<30} {perm['description'][:43]:<45}")

                print("=" * 80)

        elif choice == '8':
            # Create new permission
            print("\nCreate New Permission:")
            print("Note: Permission names should be lowercase with underscores (e.g., view_reports)")
            permission_name = input("Permission Name: ")
            description = input("Description: ")

            auth.create_permission(permission_name, description)

        elif choice == '9':
            return
        else:
            print("Invalid choice. Please try again.")

# ============================================================================
# My Account Menu
# ============================================================================

