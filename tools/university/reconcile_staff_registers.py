#!/usr/bin/env python3
"""Make ``staff`` the canonical register of people who work here.

The university kept three disconnected staff registers — ``staff`` (HR),
``users`` (logins) and ``instructors`` (teaching) — with no overlap at
all. Ten people existed in HR with no login and no teaching profile, so
the Research Portal listed staff the rest of the system had never heard
of.

This gives every staff member a login, and every teaching staff member
an ``instructors`` row linked back by ``instructors.staff_id``.
``instructors.id`` is untouched: eight tables hold foreign keys to it.

    # see what would change (default — writes nothing)
    python -m tools.university.reconcile_staff_registers

    # do it, backing the database up first
    python -m tools.university.reconcile_staff_registers --apply

Idempotent: running it twice provisions nothing the second time.
Accounts are created with a random password and flagged to change it on
first sign-in.
"""

from __future__ import annotations

import argparse
import shutil
import sys


def _backup() -> str:
    """Copy the database into the maintenance backup directory."""
    from education_system.systems.university.infrastructure.database.db import (
        DEFAULT_DB_PATH,
    )
    from education_system.paths import maintenance_backup_dir

    # create=True makes the directory and applies the retention rule, which
    # is the house convention for a repair script's pre-change copy.
    target_dir = maintenance_backup_dir("staff_register_reconcile", create=True)
    target = target_dir / "student_records.db"
    shutil.copy(str(DEFAULT_DB_PATH), str(target))
    return str(target)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true",
                        help="make the changes (default is a dry run)")
    parser.add_argument("--no-backup", action="store_true",
                        help="skip the pre-change backup (not recommended)")
    args = parser.parse_args(argv)

    from education_system.systems.university.services.staff_provisioning import (
        reconcile, unlinked_staff,
    )

    before = unlinked_staff()
    totals = before["totals"]
    print("Registers before:")
    print(f"  staff (active) : {totals.get('staff', '?')}")
    print(f"  users          : {totals.get('users', '?')}")
    print(f"  instructors    : {totals.get('instructors', '?')}")
    print()
    print(f"Staff with no login          : {len(before['without_login'])}")
    for m in before["without_login"]:
        print(f"    {m['username']:<18} {m['name']}")
    print(f"Teaching staff with no profile: {len(before['without_instructor'])}")
    for m in before["without_instructor"]:
        print(f"    {m['username']:<18} {m['name']}")

    if not before["without_login"] and not before["without_instructor"]:
        print("\nNothing to do — the registers are already in step.")
        return 0

    if not args.apply:
        print("\nDry run — nothing was changed.")
        print("Re-run with --apply to provision the accounts and profiles.")
        return 0

    if not args.no_backup:
        try:
            print(f"\nBackup written to {_backup()}")
        except Exception as exc:
            print(f"\nCould not write a backup: {exc}", file=sys.stderr)
            print("Refusing to continue. Pass --no-backup to override.",
                  file=sys.stderr)
            return 1

    result = reconcile(apply=True)

    print("\nLogins provisioned:")
    for entry in result["logins"]:
        state = "ok" if entry.get("shared_ok") else "FAILED"
        print(f"    {entry.get('username',''):<18} {entry.get('name','')}  [{state}]")
    print("Instructor profiles provisioned:")
    for entry in result["instructors"]:
        state = entry.get("instructor_id") or "FAILED"
        print(f"    {entry.get('username',''):<18} {entry.get('name','')}  [id {state}]")

    after = unlinked_staff()
    print("\nRemaining out of step:")
    print(f"  without login      : {len(after['without_login'])}")
    print(f"  without instructor : {len(after['without_instructor'])}")
    print("\nAccounts were created with a random password and must be reset "
          "on first sign-in.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
