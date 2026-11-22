"""Extracted backwards-compatible UserAuth methods."""
from ...facade_support import *

class AuthBootstrapDefaultAccountsMixin:
    def _create_default_accounts_if_needed(self, cursor, conn, target_usernames: Optional[set[str]] = None):
        """Ensure baseline system accounts exist, creating them when missing."""

        admin_password = defaults.DEFAULT_ADMIN_PASSWORD
        staff_password = defaults.DEFAULT_STAFF_PASSWORD
        student_password = defaults.DEFAULT_STUDENT_PASSWORD

        default_accounts = {
            defaults.DEFAULT_ADMIN_USERNAME: {
                'username': defaults.DEFAULT_ADMIN_USERNAME,
                'password': admin_password,
                'first_name': defaults.DEFAULT_ADMIN_FIRST_NAME,
                'last_name': defaults.DEFAULT_ADMIN_LAST_NAME,
                'email': defaults.DEFAULT_ADMIN_EMAIL,
                'role': 'admin',
                'student_id': None
            },
            defaults.DEFAULT_STAFF_USERNAME: {
                'username': defaults.DEFAULT_STAFF_USERNAME,
                'password': staff_password,
                'first_name': defaults.DEFAULT_STAFF_FIRST_NAME,
                'last_name': defaults.DEFAULT_STAFF_LAST_NAME,
                'email': defaults.DEFAULT_STAFF_EMAIL,
                'role': 'staff',
                'student_id': None
            },
            defaults.DEFAULT_STUDENT_USERNAME: {
                'username': defaults.DEFAULT_STUDENT_USERNAME,
                'password': student_password,
                'first_name': defaults.DEFAULT_STUDENT_FIRST_NAME,
                'last_name': defaults.DEFAULT_STUDENT_LAST_NAME,
                'email': defaults.DEFAULT_STUDENT_EMAIL,
                'role': 'student',
                'student_id': defaults.DEFAULT_STUDENT_ID
            }
        }

        # Filter by target_usernames if provided
        if target_usernames:
            default_accounts = {k: v for k, v in default_accounts.items() if k in target_usernames}

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        for username, account_info in default_accounts.items():
            # Check if account already exists
            cursor.execute('SELECT id FROM user_accounts WHERE username = ?', (username,))
            if cursor.fetchone():
                # Account exists. Re-hashing the default password here costs a
                # full PBKDF2 (1,000,000 iterations, ~2s) on EVERY startup and
                # was the single largest contributor to launch time (~6.8s for
                # the three default accounts). Skip it by default; opt in with
                # EDU_SYNC_DEFAULT_PASSWORDS=1 to force the dev-convenience
                # "reset default passwords on boot" behaviour.
                # Default passwords are seeded in the shared auth (EDU_DEV_SEED);
                # the university keeps no password copy to re-sync.
                # Check for role inconsistencies, user_id mismatch, and missing user profiles
                cursor.execute(
                    'SELECT id, role FROM users WHERE username = ?', (username,),
                )
                user_row = cursor.fetchone()
                if user_row:
                    user_id, existing_role = user_row
                    if existing_role != account_info['role']:
                        logging.warning(
                            f"Fixing role for '{username}': "
                            f"'{existing_role}' -> '{account_info['role']}'"
                        )
                        try:
                            cursor.execute(
                                'UPDATE users SET role = ?, updated_at = ? WHERE id = ?',
                                (account_info['role'], timestamp, user_id),
                            )
                        except sqlite3.Error as exc:
                            logging.error(
                                f"Failed to update role for user '{username}': {exc}"
                            )

                    # Fix user_id FK mismatch in user_accounts
                    cursor.execute(
                        'SELECT user_id FROM user_accounts WHERE username = ?',
                        (username,),
                    )
                    acct_row = cursor.fetchone()
                    if acct_row and acct_row[0] != user_id:
                        logging.warning(
                            f"Fixing user_id for '{username}' in user_accounts: "
                            f"{acct_row[0]} -> {user_id}"
                        )
                        try:
                            cursor.execute(
                                'UPDATE user_accounts SET user_id = ?, updated_at = ? WHERE username = ?',
                                (user_id, timestamp, username),
                            )
                        except sqlite3.Error as exc:
                            logging.error(
                                f"Failed to fix user_id for '{username}': {exc}"
                            )
                else:
                    # User record missing but account exists — create user profile
                    try:
                        cursor.execute(
                            '''INSERT INTO users
                               (username, first_name, last_name, email, role,
                                student_id, created_at, updated_at)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                            (username, account_info['first_name'],
                             account_info['last_name'], account_info['email'],
                             account_info['role'], account_info['student_id'],
                             timestamp, timestamp),
                        )
                        new_user_id = cursor.lastrowid
                        cursor.execute(
                            'UPDATE user_accounts SET user_id = ? WHERE username = ?',
                            (new_user_id, username),
                        )
                        logging.info(
                            f"Created missing user profile for '{username}'"
                        )
                    except sqlite3.Error as exc:
                        logging.error(
                            f"Failed to create user record for '{username}': {exc}"
                        )
                continue  # Account already exists

            # Create user record
            cursor.execute('''
            INSERT OR IGNORE INTO users (username, first_name, last_name, email, role, student_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                account_info['username'],
                account_info['first_name'],
                account_info['last_name'],
                account_info['email'],
                account_info['role'],
                account_info['student_id'],
                timestamp,
                timestamp
            ))

            # Get user_id
            cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
            user_result = cursor.fetchone()
            if not user_result:
                continue

            user_id = user_result[0]

            salt, password_hash = "", ""  # passwords are kept only in the shared auth (auth.db)

            # Create account
            cursor.execute('''
            INSERT INTO user_accounts (username, password_hash, salt, user_id, created_at, updated_at, is_active)
            VALUES (?, ?, ?, ?, ?, ?, 1)
            ''', (username, password_hash, salt, user_id, timestamp, timestamp))

            logging.info(f"Created default {username} account")

        conn.commit()

    def fix_missing_accounts(self):
        """Fix users that exist in users table but not in user_accounts table"""
        try:
            conn = self._create_configured_connection()
            cursor = conn.cursor()

            logger.info("Checking for users without accounts...")

            # Find users without accounts
            cursor.execute('''
            SELECT u.id, u.username, u.email, u.first_name, u.last_name, u.role
            FROM users u
            LEFT JOIN user_accounts ua ON u.id = ua.user_id
            WHERE ua.user_id IS NULL
            ''')

            orphaned_users = cursor.fetchall()

            if not orphaned_users:
                logger.info("No orphaned users found.")
                conn.close()
                return True

            logger.info(f"Found {len(orphaned_users)} users without accounts. Creating accounts...")

            for user_id, username, email, first_name, last_name, role in orphaned_users:
                # Create the account record (no local password)
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                salt, password_hash = "", ""  # passwords are kept only in the shared auth (auth.db)

                cursor.execute('''
                INSERT INTO user_accounts
                (username, password_hash, salt, user_id, created_at, updated_at, password_reset_required)
                VALUES (?, ?, ?, ?, ?, ?, 1)
                ''', (username, password_hash, salt, user_id, timestamp, timestamp))

                identifier = username or email or f"user-{user_id}"
                logger.info(f"Created account record for {identifier} (sign-in is in the shared auth)")

            conn.commit()
            conn.close()
            logger.info("All missing accounts created successfully!")
            return True

        except Exception as e:
            logging.error(f"Error fixing missing accounts: {e}")
            return False

    def ensure_staff_account_exists(self):
        """Report whether staff accounts exist."""
        staff_username = defaults.DEFAULT_STAFF_USERNAME
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''
                    SELECT ua.id
                    FROM user_accounts ua
                    WHERE ua.username = ?
                    ''',
                    (staff_username,),
                )
                if cursor.fetchone():
                    logger.info("Staff account already exists")
                    return True

                self._create_default_accounts_if_needed(cursor, conn, target_usernames={staff_username})

                cursor.execute(
                    '''
                    SELECT ua.id
                    FROM user_accounts ua
                    WHERE ua.username = ?
                    ''',
                    (staff_username,),
                )
                if cursor.fetchone():
                    logger.info(f"Staff account created successfully (username: {staff_username})")
                    return True

                logging.warning("Staff account could not be created automatically.")
                return False
        except Exception as exc:
            logging.error(f"Error verifying staff account presence: {exc}")
            return False

    def verify_default_accounts(self):
        """Summarise presence of core role accounts."""
        logger.info("Account role summary")
        try:
            conn = self._create_configured_connection()
            cursor = conn.cursor()
            cursor.execute(
                '''
                SELECT u.role, COUNT(ua.id) AS account_count
                FROM user_accounts ua
                JOIN users u ON ua.user_id = u.id
                GROUP BY u.role
                '''
            )
            role_counts = {role: count for role, count in cursor.fetchall()}

            required_roles = ['admin', 'staff', 'student']
            missing_roles = []

            for role in required_roles:
                count = role_counts.get(role, 0)
                if count == 0:
                    logger.warning(f"No active accounts found for role '{role}'.")
                    missing_roles.append(role)
                else:
                    logger.info(f"{count} account(s) found for role '{role}'.")

            other_roles = {role: count for role, count in role_counts.items() if role not in required_roles}
            if other_roles:
                logger.info("Additional roles detected:")
                for role, count in sorted(other_roles.items()):
                    logger.info(f"{role}: {count} account(s)")

            if missing_roles:
                logger.warning("Provision accounts for missing roles using the administration interface.")
                return False

            logger.info("Core roles are represented.")
            return True
        except sqlite3.Error as exc:
            logger.error(f"Unable to summarise account roles: {exc}")
            return False
        finally:
            conn.close()
