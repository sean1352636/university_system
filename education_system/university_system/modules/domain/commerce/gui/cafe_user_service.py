"""
Cafe System - User service mixin
Handles user setup, display, and finance account management
"""

import tkinter as tk
from tkinter import messagebox

from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.modules.shared.utils.i18n import get_text as _t

from .cafe_system_gui import get_db_connection


class CafeUserMixin:
    """Mixin for user management and finance account operations"""

    def setup_current_user(self):
        """Setup current user from authentication system"""
        try:
            if self.auth and hasattr(self.auth, 'current_user') and self.auth.current_user:
                auth_user = self.auth.current_user

                if isinstance(auth_user, dict):
                    self.current_user = {
                        "username": auth_user.get('username', 'Unknown'),
                        "role": auth_user.get('role', 'user'),
                        "permissions": auth_user.get('permissions', []),
                        "student_id": auth_user.get('student_id'),
                        "id": auth_user.get('id'),
                        "email": auth_user.get('email'),
                        "first_name": auth_user.get('first_name'),
                        "last_name": auth_user.get('last_name')
                    }
                else:
                    self.current_user = {
                        "username": getattr(auth_user, 'username', 'Unknown'),
                        "role": getattr(auth_user, 'role', 'user'),
                        "permissions": getattr(auth_user, 'permissions', []),
                        "student_id": getattr(auth_user, 'student_id', None),
                        "id": getattr(auth_user, 'id', None),
                        "email": getattr(auth_user, 'email', None),
                        "first_name": getattr(auth_user, 'first_name', None),
                        "last_name": getattr(auth_user, 'last_name', None)
                    }

                # Fetch full user details from database (users table)
                self._fetch_user_details_from_db()

                print(f"✓ Cafe System: Using authenticated user {self.current_user['username']} ({self.current_user['role']})")
            else:
                self.current_user = {
                    "username": "cafe_staff",
                    "role": "staff",
                    "permissions": []
                }
                print("ℹ Cafe System: No authenticated user - using default staff context")
        except Exception as e:
            print(f"✗ Error setting up current user: {e}")
            self.current_user = {
                "username": "cafe_staff",
                "role": "staff",
                "permissions": []
            }

    def _fetch_user_details_from_db(self):
        """Fetch user details from database (users table)"""
        try:
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()

            # Get user details from users table by username or id
            username = self.current_user.get('username')
            user_id = self.current_user.get('id')

            if username:
                cursor.execute('''
                    SELECT id, username, email, first_name, last_name, role, student_id
                    FROM users WHERE username = ?
                ''', (username,))
            elif user_id:
                cursor.execute('''
                    SELECT id, username, email, first_name, last_name, role, student_id
                    FROM users WHERE id = ?
                ''', (user_id,))
            else:
                conn.close()
                return

            result = cursor.fetchone()
            conn.close()

            if result:
                db_id, db_username, db_email, db_first, db_last, db_role, db_student_id = result

                # Update current_user with database values
                self.current_user['id'] = db_id
                self.current_user['username'] = db_username
                self.current_user['email'] = db_email
                self.current_user['first_name'] = db_first
                self.current_user['last_name'] = db_last
                self.current_user['role'] = db_role
                self.current_user['student_id'] = db_student_id

                # Build full name
                if db_first or db_last:
                    self.current_user['full_name'] = f"{db_first or ''} {db_last or ''}".strip()
                else:
                    self.current_user['full_name'] = db_username

        except Exception as e:
            print(f"Warning: Could not fetch user details from database: {e}")

    def _ensure_finance_account_exists(self, account_id):
        """Ensure a finance account exists for the given ID, create if not"""
        try:
            conn = get_db_connection()
            if not conn:
                return False

            cursor = conn.cursor()

            # Check if account exists
            cursor.execute('SELECT account_id FROM student_finance_accounts WHERE student_id = ?', (account_id,))
            if cursor.fetchone() is None:
                # Create new finance account with 0 balance
                cursor.execute('''
                    INSERT INTO student_finance_accounts (student_id, balance, currency, account_status)
                    VALUES (?, 0.00, 'GBP', 'active')
                ''', (account_id,))
                conn.commit()
                print(f"Created finance account for: {account_id}")

            conn.close()
            return True
        except Exception as e:
            print(f"Error creating finance account: {e}")
            return False

    def get_current_user_display_info(self):
        """Get formatted display string for current user info"""
        if not self.current_user:
            return "No user logged in"

        # Get student ID
        student_id = self.current_user.get('student_id') or self.current_user.get('id') or 'N/A'

        # Get name - try full_name first, then construct from first/last, then username
        name = self.current_user.get('full_name')
        if not name:
            first = self.current_user.get('first_name', '')
            last = self.current_user.get('last_name', '')
            if first or last:
                name = f"{first} {last}".strip()
            else:
                name = self.current_user.get('username', 'Unknown')

        # Get email
        email = self.current_user.get('email', 'No email')

        return f"ID: {student_id}  |  Name: {name}  |  Email: {email}"

    def refresh_user_display(self):
        """Refresh the user info display label"""
        if hasattr(self, 'user_info_label'):
            user_display = self.get_current_user_display_info()
            self.user_info_label.config(text=user_display)
