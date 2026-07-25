"""UsersInternalMixin — extracted from chat.py."""
from __future__ import annotations

from education_system.systems.university.infrastructure.email.admin._imports import (
    datetime,
    execute_db_operation,
    handle_exception,
    log_event,
)


class UsersInternalMixin:
    """Methods grouped from the original _ChatMixin."""

    def _get_or_create_system_user_id(self, cursor, fallback_user_id):
        """Find or lazily create a 'system' bot user. Returns its id, or
        fallback_user_id if the users table doesn't accept the insert.

        The application `users` table has varying NOT NULL shapes across
        deployments (university: first_name/last_name/email/role NOT NULL;
        school: just username/role/password_hash NOT NULL), so we discover
        columns at runtime and supply safe defaults for any of them."""
        try:
            cursor.execute("PRAGMA table_info(users)")
            cols = {row[1] for row in cursor.fetchall()}
        except Exception:
            return fallback_user_id
        if 'username' not in cols:
            return fallback_user_id
        # Prefer the explicit service_account flag if the column exists.
        try:
            if 'service_account' in cols:
                cursor.execute(
                    "SELECT id FROM users WHERE COALESCE(service_account, 0) = 1 "
                    "ORDER BY id LIMIT 1"
                )
                row = cursor.fetchone()
                if row:
                    return row[0]
            cursor.execute("SELECT id FROM users WHERE username = 'system' LIMIT 1")
            row = cursor.fetchone()
            if row:
                # Ensure the flag is set on a pre-existing 'system' user.
                if 'service_account' in cols:
                    cursor.execute(
                        "UPDATE users SET service_account = 1 WHERE id = ?",
                        (row[0],),
                    )
                return row[0]
        except Exception:
            return fallback_user_id
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        candidates = {
            'username': 'system',
            'first_name': 'System',
            'last_name': 'Bot',
            'display_name': 'System',
            'email': 'system@localhost',
            'role': 'system',
            'password_hash': '!locked!',
            'is_active': 0,
            'service_account': 1,
            'created_at': now,
            'updated_at': now,
        }
        used = {k: v for k, v in candidates.items() if k in cols}
        if not used:
            return fallback_user_id
        col_list = list(used.keys())
        sql = (
            f"INSERT INTO users ({', '.join(col_list)}) "
            f"VALUES ({', '.join('?' for _ in col_list)})"
        )
        try:
            cursor.execute(sql, [used[c] for c in col_list])
            new_id = cursor.lastrowid
            if new_id:
                return new_id
        except Exception:
            pass
        # If the insert failed (e.g., a NOT NULL we don't know about),
        # one last attempt: did a parallel writer create it meanwhile?
        try:
            cursor.execute("SELECT id FROM users WHERE username = 'system' LIMIT 1")
            row = cursor.fetchone()
            if row:
                return row[0]
        except Exception:
            pass
        return fallback_user_id

    @handle_exception
    def get_module_info(self, module_code):
        """Return {code, name, description, instructor, assignments:[...]} for
        a module. Best-effort; returns None if the academics tables aren't
        present."""
        if not module_code:
            return None

        def _get(cursor):
            try:
                cursor.execute(
                    '''SELECT module_code, module_name, description,
                              COALESCE(instructor_id, '')
                       FROM modules WHERE module_code = ?''',
                    (module_code,),
                )
                row = cursor.fetchone()
            except Exception:
                return None
            if not row:
                return None
            info = {
                'code': row[0], 'name': row[1],
                'description': row[2] or '', 'instructor': row[3] or '',
            }
            try:
                cursor.execute(
                    '''SELECT id, title, due_date, max_marks, assignment_type
                       FROM assignments
                       WHERE module_code = ? AND COALESCE(is_active, 1) = 1
                       ORDER BY due_date ASC LIMIT 50''',
                    (module_code,),
                )
                info['assignments'] = [
                    {'id': r[0], 'title': r[1], 'due_date': r[2],
                     'max_marks': r[3], 'type': r[4]}
                    for r in cursor.fetchall()
                ]
            except Exception:
                info['assignments'] = []
            return info

        try:
            return execute_db_operation(_get)
        except Exception as e:
            log_event('error', f"Error getting module info: {e}")
            return None

    @handle_exception
    def list_staff_teams(self):
        """Return distinct staff departments (used as team mentions)
        with member count. Best-effort against staff_profiles."""
        def _list(cursor):
            try:
                cursor.execute(
                    '''SELECT department, COUNT(*)
                       FROM staff_profiles
                       WHERE department IS NOT NULL AND TRIM(department) != ''
                       GROUP BY department ORDER BY department'''
                )
                return [{'name': r[0], 'member_count': r[1]}
                        for r in cursor.fetchall()]
            except Exception:
                return []

        try:
            return execute_db_operation(_list)
        except Exception as e:
            log_event('error', f"Error listing staff teams: {e}")
            return []

    @handle_exception
    def get_team_members(self, team_name):
        """Return user dicts for staff in a given department (case-insensitive)."""
        if not team_name:
            return []

        def _get(cursor):
            out = []
            try:
                cursor.execute(
                    '''SELECT sp.user_id, sp.job_title,
                              COALESCE(u.username, ''),
                              COALESCE(u.first_name, ''), COALESCE(u.last_name, ''),
                              COALESCE(u.email, '')
                       FROM staff_profiles sp
                       LEFT JOIN users u
                         ON CAST(u.id AS TEXT) = sp.user_id
                            OR u.username = sp.user_id
                       WHERE LOWER(sp.department) = LOWER(?)
                       ORDER BY u.first_name, u.last_name''',
                    (team_name,),
                )
            except Exception:
                return []
            for r in cursor.fetchall():
                full = f"{r[3]} {r[4]}".strip()
                out.append({
                    'user_id_str': r[0],
                    'job_title': r[1] or '',
                    'username': r[2] or '',
                    'full_name': full or (r[2] or ''),
                    'email': r[5] or '',
                })
            return out

        try:
            return execute_db_operation(_get)
        except Exception as e:
            log_event('error', f"Error getting team members: {e}")
            return []

    # ------------------------------------------------------------------
    # Generic entity linkage: events, clubs, residences, advisor OH, etc.
    # ------------------------------------------------------------------

    @handle_exception
    def get_user_profile(self, user_id):
        """Return a profile snapshot for any user the current user can see.
        Joins users + staff_profiles (department/job_title/manager) and the
        student_id if available."""
        if not self.auth or not self.auth.current_user:
            return None

        def _get(cursor):
            cursor.execute(
                '''SELECT id, COALESCE(username, ''),
                          COALESCE(first_name, ''), COALESCE(last_name, ''),
                          COALESCE(email, ''), COALESCE(role, '')
                   FROM users WHERE id = ?''',
                (user_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            full = f"{row[2]} {row[3]}".strip()
            profile = {
                'user_id': row[0], 'username': row[1],
                'full_name': full or row[1], 'email': row[4],
                'role': row[5],
            }
            try:
                cursor.execute(
                    '''SELECT department, job_title, employment_type,
                              office_location, phone_extension, manager_id, bio,
                              expertise_areas
                       FROM staff_profiles
                       WHERE user_id = ? OR user_id = ?''',
                    (str(user_id), profile['username']),
                )
                sp = cursor.fetchone()
                if sp:
                    profile['staff'] = {
                        'department': sp[0], 'job_title': sp[1],
                        'employment_type': sp[2], 'office': sp[3],
                        'phone_ext': sp[4], 'manager_id': sp[5],
                        'bio': sp[6], 'expertise': sp[7],
                    }
            except Exception:
                profile['staff'] = None
            try:
                cursor.execute(
                    'SELECT student_id FROM students WHERE user_id = ?',
                    (user_id,),
                )
                sr = cursor.fetchone()
                if sr:
                    profile['student_id'] = sr[0]
            except Exception:
                pass
            return profile

        try:
            return execute_db_operation(_get)
        except Exception as e:
            log_event('error', f"Error getting user profile: {e}")
            return None

    @handle_exception
    def resolve_username_to_id(self, username):
        """Best-effort lookup. Returns user_id or None."""
        if not username:
            return None
        u = username.lstrip('@')

        def _q(cursor):
            cursor.execute('SELECT id FROM users WHERE username = ?', (u,))
            r = cursor.fetchone()
            return r[0] if r else None

        try:
            return execute_db_operation(_q)
        except Exception:
            return None

    def _emit_notification(self, cursor, user_id, title, message,
                           ntype='chat', data=None):
        """Best-effort INSERT into the central notifications table. The schema
        of `notifications` has been migrated multiple times in this repo, so
        we discover the actual columns at runtime and only fill what exists."""
        if not user_id:
            return
        try:
            cursor.execute("PRAGMA table_info(notifications)")
            cols = {row[1] for row in cursor.fetchall()}
        except Exception:
            return
        if not cols:
            return
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        # Candidate values keyed by column name. Each is set only if the
        # column actually exists in the deployed table. Two real shapes:
        #   - university `notifications` (student_records.db): channel +
        #     priority NOT NULL, source_system/source_id, metadata, created_at
        #   - school `notifications` (primary_school.db et al.): notification_type,
        #     link, created_at
        candidates = {
            'user_id': str(user_id),
            'recipient_id': str(user_id),
            'recipient_type': 'user',
            'channel': 'in_app',
            'priority': 'normal',
            'title': (title or '')[:200],
            'message': (message or '')[:500],
            'notification_type': ntype,
            'type': ntype,
            'source_system': 'chat',
            'source_id': (data or '')[:80],
            'metadata': (data or '')[:500],
            'link': (data or '')[:500],
            'data': (data or '')[:500],
            'is_read': 0,
            'is_archived': 0,
            'sent': 0,
            'created_datetime': now,
            'created_date': now,
            'created_at': now,
        }
        used = {k: v for k, v in candidates.items() if k in cols}
        if 'user_id' not in used and 'recipient_id' not in used:
            return
        col_list = list(used.keys())
        placeholders = ', '.join('?' for _ in col_list)
        sql = (
            f"INSERT INTO notifications ({', '.join(col_list)}) "
            f"VALUES ({placeholders})"
        )
        try:
            cursor.execute(sql, [used[c] for c in col_list])
        except Exception:
            # Don't propagate. Likely NOT NULL on a column we don't know about.
            pass

    def _emit_chat_mention_notifications(self, cursor, room_id, sender_id,
                                         sender_name, content, message_id):
        """Scan content for @user mentions and push a notification to each
        addressee (skip the sender)."""
        if not content:
            return
        import re
        seen = set()
        for m in re.finditer(r'@(\w+)', content):
            handle = m.group(1)
            if handle.startswith('team:'):
                continue
            if handle in seen:
                continue
            seen.add(handle)
            cursor.execute('SELECT id FROM users WHERE username = ?', (handle,))
            row = cursor.fetchone()
            if not row or row[0] == sender_id:
                continue
            self._emit_notification(
                cursor, row[0],
                f"{sender_name} mentioned you in chat",
                (content[:140] + '…') if len(content) > 140 else content,
                ntype='chat_mention',
                data=f"room={room_id};message={message_id}",
            )

