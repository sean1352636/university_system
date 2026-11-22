"""Restaurant "User Management" menu: who has access and what they can do."""
from __future__ import annotations

from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.plugins.campus_commerce.domain.services.restaurant.operations import (
    user_access,
)


def _choose(items, label, describe):
    """Numbered pick from *items*; None if the person backs out."""
    for number, item in enumerate(items, 1):
        print(f"{number}. {describe(item)}")
    answer = input(f"{label} (number, Enter to cancel): ").strip()
    if answer.isdigit() and 1 <= int(answer) <= len(items):
        return items[int(answer) - 1]
    if answer:
        print("That isn't one of the numbers listed.")
    return None


def _show_users(auth) -> list:
    rows = user_access.list_access(auth)
    if not rows:
        print("\nNobody has restaurant access yet.")
        return rows
    print(f"\n{'Login':<20}{'Name':<24}{'Staff member':<24}{'Role':<12}{'Status':<26}Granted")
    print("-" * 118)
    for row in rows:
        granted = f"{row['granted_by']} {row['granted_at'][:10]}".strip()
        print(f"{row['username'][:19]:<20}{row['name'][:23]:<24}{row['staff_name'][:23]:<24}"
              f"{row['role']:<12}{row['state'][:25]:<26}{granted}")
    return rows


def _choose_role():
    for role in user_access.ROLES:
        allowed = ", ".join(sorted(user_access.ROLE_PERMISSIONS[role]))
        print(f"  {role}: {allowed}")
    return _choose(list(user_access.ROLES), "Role", str)


def _grant(auth) -> None:
    staff = user_access.staff_available(auth)
    if not staff:
        print("\nNo active staff member is free to link. Add them in Staff Management first.")
        return
    logins = user_access.find_logins(auth, input("Search logins (Enter for all): "))
    if not logins:
        print("No staff logins match.")
        return
    login = _choose(logins, "Login", lambda l: f"{l['username']}  {l['name']}")
    if login is None:
        return
    member = _choose(staff, "Staff member",
                     lambda s: f"{s['name']} (ID {s['staff_id']}, {s['role']})")
    if member is None:
        return
    role = _choose_role()
    if role is None:
        return
    user_access.grant_access(auth, login["username"], member["staff_id"], role)
    print(f"{login['username']} now has {role} access, linked to {member['name']}.")


def _active_user(auth):
    rows = [row for row in user_access.list_access(auth) if row["active"]]
    if not rows:
        print("\nNobody has active access.")
        return None
    return _choose(rows, "User", lambda r: f"{r['username']}  {r['role']}  ({r['staff_name']})")


def _change_role(auth) -> None:
    user = _active_user(auth)
    role = _choose_role() if user else None
    if role:
        user_access.change_role(auth, user["username"], role)
        print(f"{user['username']} is now {role}.")


def _remove(auth) -> None:
    user = _active_user(auth)
    if not user:
        return
    reason = input("Reason (optional): ")
    if input(f"Remove access for {user['username']}? Their staff record is kept. (y/N): "
             ).strip().lower() == "y":
        user_access.remove_access(auth, user["username"], reason)
        print(f"Access removed for {user['username']}.")


def _history(auth) -> None:
    rows = user_access.access_history(auth, input("Login (Enter for everyone): ").strip() or None)
    if not rows:
        print("\nNo access changes recorded.")
        return
    print(f"\n{'When':<21}{'Changed by':<20}{'Action':<20}{'Login':<20}Change")
    print("-" * 110)
    for row in rows:
        print(f"{row['timestamp']:<21}{row['user_id'][:19]:<20}{row['action']:<20}"
              f"{(row['record_id'] or '')[:19]:<20}{row['new_values'] or ''}")


def _staff_records(auth) -> None:
    from education_system.systems.university.plugins.campus_commerce.domain.services.restaurant.staff.staff_administration import (
        display_staff_management,
    )
    display_staff_management()


OPTIONS = (
    ("1", "View users", _show_users),
    ("2", "Grant access", _grant),
    ("3", "Change a role", _change_role),
    ("4", "Remove access", _remove),
    ("5", "Access history", _history),
    ("6", "Staff records", _staff_records),
)


def run_menu(auth) -> None:
    if not user_access.can_manage(auth):
        print("Only an administrator or restaurant Manager can manage users.")
        return
    while True:
        print("\n" + "=" * 50 + "\nUSER MANAGEMENT\n" + "=" * 50)
        for key, label, _action in OPTIONS:
            print(f"{key}. {label}")
        print("0. Return")
        choice = input("Enter your choice: ").strip()
        if choice == "0":
            return
        for key, _label, action in OPTIONS:
            if choice == key:
                try:
                    action(auth)
                except user_access.AccessError as exc:
                    print(f"\n{exc}")
                except sqlite3.Error as exc:
                    print(f"\nCould not complete that: {exc}")
                break
        else:
            print("Invalid choice.")
