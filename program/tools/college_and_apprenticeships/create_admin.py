#!/usr/bin/env python3
"""Grant apprenticeships access to accounts in the shared auth database.

The apprenticeships system does not appear in the login picker until an
account holds a ``user_systems`` row for it. This grants that row.

Preferred over ``EDU_DEV_SEED=true`` on an established database: the seed
flag re-creates *every* missing weak demo account across all systems,
which is a lot of collateral on a database with real users in it. This
touches only the accounts you name.

Usage
-----
    # See who currently has access (read-only)
    python program/tools/college_and_apprenticeships/create_admin.py --list

    # Grant a role to an existing account
    python .../create_admin.py --user alice --role admin
    python .../create_admin.py --user bob --role end_point_assessor

    # Create the five demo logins (dev machines only — weak passwords)
    python .../create_admin.py --demo

Roles: admin, staff, apprentice, employer, end_point_assessor
"""

from __future__ import annotations

import argparse
import getpass
import sys

from education_system.platform.identity.auth.db import connect
from education_system.platform.identity.auth.password_manager import hash_password
from education_system.systems.apprenticeships import config

SYSTEM_KEY = "apprenticeships"

# Mirrors the entries in platform/identity/auth/schema.py so a machine
# seeded either way ends up with the same logins.
DEMO_ACCOUNTS = [
    ("admin5", "admin1234", "Apprenticeships Administrator", "admin"),
    ("tutor1", "tutor1234", "Apprenticeship Tutor", "staff"),
    ("apprentice1", "apprentice1234", "Demo Apprentice", "apprentice"),
    ("employer1", "employer1234", "Employer Manager", "employer"),
    ("assessor1", "assessor1234", "End-Point Assessor", "end_point_assessor"),
]


def list_access() -> int:
    """Print every account that can currently reach the system."""
    conn = connect()
    try:
        rows = conn.execute(
            """SELECT u.username, us.role, u.is_active, u.must_change_password
                 FROM users u
                 JOIN user_systems us ON us.user_id = u.id
                WHERE us.system_key = ?
                ORDER BY us.role, u.username""",
            (SYSTEM_KEY,),
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        print("\n  No account has apprenticeships access yet.")
        print("  Grant one with --user <name> --role <role>, or --demo.\n")
        return 0

    print(f"\n  {len(rows)} account(s) with apprenticeships access:\n")
    print(f"    {'username':<20} {'role':<20} {'active':<8} must change pw")
    print("    " + "-" * 66)
    for row in rows:
        print(f"    {row['username']:<20} {row['role']:<20} "
              f"{'yes' if row['is_active'] else 'NO':<8} "
              f"{'yes' if row['must_change_password'] else 'no'}")
    print()
    return 0


def grant(username: str, role: str) -> int:
    """Give an existing account a role in this system."""
    if role not in config.ROLES:
        print(f"  Role must be one of: {', '.join(config.ROLES)}", file=sys.stderr)
        return 2

    conn = connect()
    try:
        user = conn.execute(
            "SELECT id, username FROM users WHERE username = ?", (username,)
        ).fetchone()
        if user is None:
            print(f"  No account named {username!r}. Create it in the platform "
                  f"first, or use --demo for the throwaway logins.", file=sys.stderr)
            return 1

        existing = conn.execute(
            "SELECT role FROM user_systems WHERE user_id = ? AND system_key = ?",
            (user["id"], SYSTEM_KEY),
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE user_systems SET role = ? WHERE user_id = ? AND system_key = ?",
                (role, user["id"], SYSTEM_KEY),
            )
            action = f"changed from {existing['role']!r} to {role!r}"
        else:
            conn.execute(
                "INSERT INTO user_systems (user_id, system_key, role) VALUES (?, ?, ?)",
                (user["id"], SYSTEM_KEY, role),
            )
            action = f"granted {role!r}"
        conn.commit()
    finally:
        conn.close()

    print(f"\n  {username}: {action} on the apprenticeships system.")
    _linking_hint(role)
    return 0


def create_demo() -> int:
    """Create the five demo logins. Development machines only."""
    print("\n  These accounts use weak, publicly documented passwords.")
    print("  Never do this on a shared or internet-facing deployment.")
    answer = input("  Continue? (y/N): ").strip().lower()
    if not answer.startswith("y"):
        print("  Cancelled.\n")
        return 1

    conn = connect()
    created, updated = [], []
    try:
        for username, password, display_name, role in DEMO_ACCOUNTS:
            row = conn.execute(
                "SELECT id FROM users WHERE username = ?", (username,)
            ).fetchone()
            if row is None:
                cursor = conn.execute(
                    """INSERT INTO users
                           (username, password_hash, display_name, email,
                            password_changed_at, must_change_password)
                       VALUES (?, ?, ?, ?, datetime('now'), 0)""",
                    (username, hash_password(password), display_name,
                     f"{username}@apprenticeships.local"),
                )
                user_id = cursor.lastrowid
                created.append(username)
            else:
                user_id = row["id"]
                updated.append(username)
            conn.execute(
                """INSERT OR IGNORE INTO user_systems (user_id, system_key, role)
                   VALUES (?, ?, ?)""",
                (user_id, SYSTEM_KEY, role),
            )
        conn.commit()
    finally:
        conn.close()

    if created:
        print(f"\n  Created: {', '.join(created)}")
    if updated:
        print(f"  Already existed (access granted): {', '.join(updated)}")
    print("\n  Sign in with:")
    for username, password, _display, role in DEMO_ACCOUNTS:
        print(f"    {username:<14} {password:<16} {role}")
    print()
    print("  Note: tutor1, apprentice1 and employer1 also need linking to a")
    print("  staff / apprentice / employer-manager record before their screens")
    print("  show anything — see below.\n")
    return 0


def _linking_hint(role: str) -> None:
    """Explain the second half of provisioning for scoped roles.

    An auth grant gets someone through the door; the scoped roles also
    need a record in *this* system carrying their username, or their
    screens correctly show nothing.
    """
    hints = {
        "staff": "a staff record with username set (Admin → Staff & Caseloads → New Staff)",
        "apprentice": "an apprentice record with username set (Admin → Apprentices → New)",
        "employer": "an employer manager with username set (Admin → Employers → Managers)",
    }
    hint = hints.get(role)
    if hint:
        print(f"  Next: link the login to {hint}.")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Grant apprenticeships access in the shared auth database.",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--list", action="store_true",
                       help="show accounts that already have access")
    group.add_argument("--user", help="existing account to grant a role to")
    group.add_argument("--demo", action="store_true",
                       help="create the five demo logins (dev machines only)")
    parser.add_argument("--role", default="admin",
                        help=f"one of: {', '.join(config.ROLES)} (default: admin)")
    args = parser.parse_args()

    if args.list:
        return list_access()
    if args.demo:
        return create_demo()
    return grant(args.user, args.role)


if __name__ == "__main__":
    raise SystemExit(main())
