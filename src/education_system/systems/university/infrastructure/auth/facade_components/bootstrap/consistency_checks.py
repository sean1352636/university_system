"""Extracted backwards-compatible UserAuth methods."""
from ...facade_support import *

class AuthBootstrapConsistencyChecksMixin:
    def fix_database_consistency(self):
        """Fix database consistency issues between users and user_accounts tables"""
        if not self.current_user or 'manage_users' not in self.current_user.get('permissions', []):
            logger.warning("You don't have permission to fix database issues.")
            return False

        try:
            conn = self._create_configured_connection()
            cursor = conn.cursor()

            logger.info("Checking database consistency...")

            # Find orphaned user records (users without accounts)
            cursor.execute('''
                SELECT u.id, u.username, u.email, u.first_name, u.last_name, u.role, u.student_id
                FROM users u
                LEFT JOIN user_accounts ua ON u.id = ua.user_id
                WHERE ua.user_id IS NULL
            ''')

            orphaned_users = cursor.fetchall()

            if orphaned_users:
                logger.info(f"Found {len(orphaned_users)} users without accounts. Creating accounts...")

                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                for user in orphaned_users:
                    user_id, username, email, first_name, last_name, role, student_id = user

                    # Check if an account with this username already exists
                    cursor.execute('SELECT id, user_id FROM user_accounts WHERE username = ?', (username,))
                    existing_account = cursor.fetchone()

                    if existing_account:
                        logger.info(f"Account for '{username}' already exists, skipping...")
                        continue

                    # Generate a temporary password
                    temp_password = self._generate_temp_password()
                    salt, password_hash = self._hash_password(temp_password)

                    try:
                        cursor.execute('''
                            INSERT INTO user_accounts
                            (username, password_hash, salt, user_id, created_at, updated_at, password_reset_required)
                            VALUES (?, ?, ?, ?, ?, ?, 1)
                        ''', (username, password_hash, salt, user_id, timestamp, timestamp))

                        logger.info(f"Created account for {username} with temporary password")
                    except sqlite3.IntegrityError as e:
                        logger.error(f"Failed to create account for {username}: {e}")

            # Find orphaned account records (accounts without users)
            cursor.execute('''
                SELECT ua.id, ua.username, ua.user_id
                FROM user_accounts ua
                LEFT JOIN users u ON ua.user_id = u.id
                WHERE u.id IS NULL
            ''')

            orphaned_accounts = cursor.fetchall()

            if orphaned_accounts:
                logger.info(f"Found {len(orphaned_accounts)} accounts without user profiles.")
                logger.info("These orphaned accounts will be removed to maintain database integrity...")

                for account in orphaned_accounts:
                    account_id, username, user_id = account

                    # Check if a user with this username already exists
                    cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
                    existing_user = cursor.fetchone()

                    if existing_user:
                        # User exists, update the account to point to the correct user
                        logger.info(f"Updating orphaned account '{username}' to link with existing user")
                        cursor.execute('''
                            UPDATE user_accounts
                            SET user_id = ?
                            WHERE id = ?
                        ''', (existing_user[0], account_id))
                    else:
                        # No matching user exists, delete the orphaned account
                        logger.info(f"Deleting orphaned account '{username}' (no matching user found)")
                        cursor.execute('DELETE FROM user_accounts WHERE id = ?', (account_id,))

            conn.commit()
            conn.close()

            logger.info("Database consistency check completed!")
            return True

        except sqlite3.Error as e:
            logger.error(f"Database error while fixing consistency: {e}")
            return False
