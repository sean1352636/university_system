"""Service for linking parent accounts across systems when students transfer.

When a student transfers between education systems (e.g. primary -> secondary),
this service helps ensure their parent's account is also linked to the new
system so the parent retains access.
"""

import sqlite3
from pathlib import Path

from education_system.shared.auth.db import AUTH_DB_FILE, connect as auth_connect


def _default_db_path(system):
    """Resolve the default database path for a given system."""
    shared_dir = Path(__file__).resolve().parent.parent  # .../shared
    edu_root = shared_dir.parent  # .../education_system

    path_map = {
        "primary": edu_root / "primary_school" / "data" / "db_files" / "primary_school.db",
        "secondary": edu_root / "secondary_school" / "data" / "db_files" / "secondary_school.db",
        "school": edu_root / "secondary_school" / "data" / "db_files" / "secondary_school.db",
        "college": edu_root / "college_system" / "data" / "db_files" / "sixthform.db",
        "university": edu_root / "university_system" / "data" / "db_files" / "student_records.db",
    }
    return path_map.get(system)


def _table_exists(conn, table_name):
    """Check whether *table_name* exists in the SQLite database."""
    row = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    return row[0] > 0


def _get_columns(conn, table_name):
    """Return the set of column names for *table_name*."""
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {r[1] for r in rows}


class ParentContinuityService:
    """Link parent accounts to new systems when students transfer."""

    # Map of system key to its canonical student table name
    _STUDENT_TABLES = {
        "primary": "pupils",
        "secondary": "students",
        "school": "students",
        "college": "students",
        "university": "students",
    }

    def __init__(self, auth_db_path=None):
        self._auth_db = auth_db_path or str(AUTH_DB_FILE)

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _auth_conn(self):
        """Open a connection to the shared auth database."""
        return auth_connect(self._auth_db)

    def _system_conn(self, system):
        """Open a read-only connection to a system DB. Returns None if missing."""
        path = _default_db_path(system)
        if not path or not path.exists():
            return None
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        return conn

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def find_parent_accounts(self, student_name, source_system):
        """Look up parent info from the source system DB for *student_name*.

        Returns a list of dicts with keys:
            student_name, parent_name, parent_email, parent_phone,
            matched_user_id (int or None if no auth user matches)
        """
        results = []
        table = self._STUDENT_TABLES.get(source_system)
        if not table:
            return results

        conn = self._system_conn(source_system)
        if not conn:
            return results

        try:
            if not _table_exists(conn, table):
                return results

            cols = _get_columns(conn, table)

            # Build name expression
            name_expr = self._name_expr(cols)
            if not name_expr:
                return results

            # Identify parent columns that may exist
            parent_name_col = self._find_col(cols, [
                "parent_name", "guardian_name", "parent_guardian",
                "emergency_contact_name", "contact_name",
            ])
            parent_email_col = self._find_col(cols, [
                "parent_email", "guardian_email", "emergency_contact_email",
                "contact_email",
            ])
            parent_phone_col = self._find_col(cols, [
                "parent_phone", "guardian_phone", "emergency_contact_phone",
                "contact_phone", "parent_contact",
            ])

            if not parent_name_col and not parent_email_col:
                return results

            like_pattern = f"%{student_name.strip()}%"
            select_parts = [f"{name_expr} AS student_name"]
            if parent_name_col:
                select_parts.append(f"{parent_name_col} AS parent_name")
            if parent_email_col:
                select_parts.append(f"{parent_email_col} AS parent_email")
            if parent_phone_col:
                select_parts.append(f"{parent_phone_col} AS parent_phone")

            sql = (
                f"SELECT {', '.join(select_parts)} FROM {table} "
                f"WHERE {name_expr} LIKE ? LIMIT 50"
            )
            rows = conn.execute(sql, (like_pattern,)).fetchall()

            for r in rows:
                rk = r.keys()
                p_name = r["parent_name"] if "parent_name" in rk else ""
                p_email = r["parent_email"] if "parent_email" in rk else ""
                p_phone = r["parent_phone"] if "parent_phone" in rk else ""

                if not p_name and not p_email:
                    continue

                # Check if a matching user exists in the auth DB
                matched_id = self._match_auth_user(p_name, p_email)

                results.append({
                    "student_name": r["student_name"],
                    "parent_name": p_name or "",
                    "parent_email": p_email or "",
                    "parent_phone": p_phone or "",
                    "matched_user_id": matched_id,
                })
        except Exception:
            pass
        finally:
            conn.close()

        return results

    def link_parent_to_system(self, parent_user_id, dest_system, role="parent"):
        """Add an entry to user_systems so the parent has access to *dest_system*.

        Returns True on success, False if the user or system is invalid.
        """
        conn = self._auth_conn()
        try:
            # Verify user exists
            user = conn.execute(
                "SELECT id FROM users WHERE id = ?", (parent_user_id,)
            ).fetchone()
            if not user:
                return False

            conn.execute(
                """INSERT OR IGNORE INTO user_systems
                   (user_id, system_key, role) VALUES (?, ?, ?)""",
                (parent_user_id, dest_system, role),
            )
            conn.commit()
            return True
        except Exception:
            return False
        finally:
            conn.close()

    def get_unlinked_parents(self, dest_system):
        """Find students in *dest_system* who have a previous_system_id and
        whose parent accounts exist in the source system but NOT in
        *dest_system*.

        Returns a list of dicts:
            student_name, parent_name, parent_email, source_system,
            parent_user_id, link_status ('unlinked')
        """
        results = []
        table = self._STUDENT_TABLES.get(dest_system)
        if not table:
            return results

        conn = self._system_conn(dest_system)
        if not conn:
            return results

        try:
            if not _table_exists(conn, table):
                return results

            cols = _get_columns(conn, table)
            if "previous_system_id" not in cols:
                return results

            name_expr = self._name_expr(cols)
            if not name_expr:
                return results

            # Get students who transferred in
            rows = conn.execute(
                f"SELECT {name_expr} AS student_name, previous_system_id "
                f"FROM {table} WHERE previous_system_id IS NOT NULL "
                f"AND previous_system_id != ''"
            ).fetchall()

            # Determine source system (one level back)
            system_order = ["primary", "secondary", "college", "university"]
            # Normalise key
            norm_dest = dest_system if dest_system != "school" else "secondary"
            dest_idx = system_order.index(norm_dest) if norm_dest in system_order else -1
            source_system = system_order[dest_idx - 1] if dest_idx > 0 else None

            if not source_system:
                return results

            for r in rows:
                student_name = r["student_name"]
                parents = self.find_parent_accounts(student_name, source_system)
                for p in parents:
                    uid = p.get("matched_user_id")
                    if uid and not self._has_system_access(uid, dest_system):
                        results.append({
                            "student_name": student_name,
                            "parent_name": p["parent_name"],
                            "parent_email": p["parent_email"],
                            "source_system": source_system,
                            "parent_user_id": uid,
                            "link_status": "unlinked",
                        })
        except Exception:
            pass
        finally:
            conn.close()

        return results

    # ------------------------------------------------------------------
    # private helpers
    # ------------------------------------------------------------------

    def _match_auth_user(self, name, email):
        """Try to find a user in the auth DB matching by email or display_name.

        Returns the user id or None.
        """
        conn = self._auth_conn()
        try:
            if email:
                row = conn.execute(
                    "SELECT id FROM users WHERE email = ? AND is_active = 1",
                    (email,),
                ).fetchone()
                if row:
                    return row["id"]

            if name:
                row = conn.execute(
                    "SELECT id FROM users WHERE display_name = ? AND is_active = 1",
                    (name,),
                ).fetchone()
                if row:
                    return row["id"]

            return None
        except Exception:
            return None
        finally:
            conn.close()

    def _has_system_access(self, user_id, system_key):
        """Check if a user already has access to a given system."""
        conn = self._auth_conn()
        try:
            row = conn.execute(
                "SELECT id FROM user_systems WHERE user_id = ? AND system_key = ?",
                (user_id, system_key),
            ).fetchone()
            return row is not None
        except Exception:
            return False
        finally:
            conn.close()

    @staticmethod
    def _name_expr(columns):
        """Build a SQL expression for student full name."""
        if "full_name" in columns:
            return "full_name"
        if "name" in columns:
            return "name"
        if "first_name" in columns and "last_name" in columns:
            return "(first_name || ' ' || last_name)"
        if "forename" in columns and "surname" in columns:
            return "(forename || ' ' || surname)"
        if "first_name" in columns and "surname" in columns:
            return "(first_name || ' ' || surname)"
        if "forename" in columns and "last_name" in columns:
            return "(forename || ' ' || last_name)"
        return None

    @staticmethod
    def _find_col(columns, candidates):
        """Return the first matching column name from candidates, or None."""
        for c in candidates:
            if c in columns:
                return c
        return None
