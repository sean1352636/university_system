#!/usr/bin/env python3
"""Widen ``auth.db``'s MFA schema and migrate the university's MFA rows into it.

Background
----------
The multi-method MFA service was promoted out of the university system into
``platform/identity/auth/mfa/``. It was written against the university
database, whose MFA tables are wider than the shared auth database's, and
which has five tables ``auth.db`` lacks entirely. Before every system can
share one MFA store, ``auth.db`` has to be able to hold that shape.

What this does
--------------
1. Adds the missing columns to the five shared MFA tables (all nullable or
   defaulted, so existing rows are unaffected).
2. Creates the five university-only tables.
3. Copies durable MFA enrolment state across, **mapping user ids by
   username** — ``student_records.db`` and ``auth.db`` use independent id
   sequences, so the same number means different people in each (``admin``
   is 1 in the university database and 19 in auth). Rows whose owner cannot
   be resolved are reported and skipped, never guessed at.

Deliberately not copied: ``mfa_otp_codes``. Those are one-time codes with a
ten-minute expiry, so migrating them has no value, and the column holding
them in cleartext is not reproduced in auth.db.

Idempotent: columns are added only when absent, tables use CREATE TABLE IF
NOT EXISTS, and rows are matched before insert, so a second run is a no-op.

Usage
-----
    python tools/migrate_mfa_to_auth_db.py --dry-run
    python tools/migrate_mfa_to_auth_db.py --apply
    python tools/migrate_mfa_to_auth_db.py --apply --target /tmp/copy.db
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TARGET = REPO_ROOT / "var" / "data" / "platform" / "db_files" / "auth.db"
DEFAULT_SOURCE = REPO_ROOT / "var" / "data" / "university" / "db_files" / "student_records.db"

# Columns the promoted service needs that auth.db lacks. Every one is
# nullable or defaulted: ALTER TABLE ADD COLUMN cannot add a NOT NULL column
# without a default to a populated table, and more importantly existing rows
# must stay valid.
#
# The university declares several of these ``DEFAULT CURRENT_TIMESTAMP``,
# which SQLite rejects in ALTER TABLE ("Cannot add a column with non-constant
# default"), so they are added plain nullable here. Safe because none of them
# is ever read: the only timestamp the service orders or filters on is
# ``mfa_otp_codes.created_at``, which auth.db already has with its own
# default. New rows simply carry NULL where the university's carry a time.
#
# ``mfa_user_settings.id`` is intentionally absent: it is an AUTOINCREMENT PK
# in the university table, SQLite cannot add a PK by ALTER, and the service
# never reads it — every statement keys on user_id via ON CONFLICT(user_id),
# which auth.db already satisfies with user_id as its primary key.
ADD_COLUMNS: dict[str, list[tuple[str, str]]] = {
    "mfa_methods": [
        ("secret_key", "TEXT"),
        ("phone_number", "TEXT"),
        ("email", "TEXT"),
        ("created_at", "TIMESTAMP"),
        ("updated_at", "TIMESTAMP"),
    ],
    "mfa_otp_codes": [
        # Nullable, unlike the university's NOT NULL original: the service
        # now writes '' here and matches on code_hash. No cleartext codes.
        ("code", "TEXT"),
        ("used_at", "TIMESTAMP"),
    ],
    "mfa_recovery_codes": [
        ("used_at", "TIMESTAMP"),
        ("generated_at", "TIMESTAMP"),
        ("expires_at", "TIMESTAMP"),
    ],
    "mfa_user_settings": [
        ("mfa_enabled", "INTEGER DEFAULT 0"),
        ("backup_codes_generated", "INTEGER DEFAULT 0"),
        ("enforcement_deadline", "TIMESTAMP"),
        ("bypass_until", "TIMESTAMP"),
        ("last_successful_verification", "TIMESTAMP"),
        ("created_at", "TIMESTAMP"),
        ("mfa_status", "TEXT DEFAULT 'disabled'"),
        ("disabled_at", "TIMESTAMP"),
    ],
    "webauthn_credentials": [
        ("credential_name", "TEXT DEFAULT 'Security Key'"),
        ("aaguid", "TEXT"),
        ("transports", "TEXT"),
        ("is_discoverable", "BOOLEAN DEFAULT 0"),
        ("is_active", "BOOLEAN DEFAULT 1"),
        ("last_used_at", "TIMESTAMP"),
    ],
}

#: Tables copied verbatim (DDL taken from the source DB) when absent.
CREATE_TABLES = [
    "mfa_enforcement_policies",
    "mfa_trusted_devices",
    "mfa_verification_attempts",
    "webauthn_challenges",
    "evaluation_mfa_gates",
]

#: Durable, user-scoped state worth carrying over. Order matters only for
#: readability — there are no FKs between them in auth.db.
MIGRATE_USER_TABLES = [
    "mfa_methods",
    "mfa_recovery_codes",
    "mfa_user_settings",
    "mfa_verification_attempts",
]

#: Not user-scoped; copied wholesale if the target is empty.
MIGRATE_GLOBAL_TABLES = ["evaluation_mfa_gates"]

#: Columns identifying "the same row" for re-run safety. ``INSERT OR IGNORE``
#: alone is not enough: it only suppresses *constraint* violations, so tables
#: without a unique index (recovery codes, verification attempts) silently
#: duplicated on a second run. Duplicated recovery codes are a security bug —
#: consuming one leaves its twin usable — so every migrated table is matched
#: on a natural key before insert.
NATURAL_KEYS: dict[str, list[str]] = {
    "mfa_methods": ["user_id", "method_type"],
    "mfa_recovery_codes": ["user_id", "code_hash"],
    "mfa_user_settings": ["user_id"],
    "mfa_verification_attempts": ["user_id", "method_type", "attempted_at"],
}


def columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')]


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def build_user_map(src: sqlite3.Connection, dst: sqlite3.Connection) -> tuple[dict[int, int], list[int]]:
    """Map university user ids to auth.db user ids, by username.

    Returns ``(mapping, unresolved)``. A university id that has no username,
    or whose username is absent from auth.db, lands in *unresolved* and is
    never guessed at — a wrong mapping would attach someone's second factor
    to a different account.
    """
    uids: set[int] = set()
    for table in MIGRATE_USER_TABLES:
        if table_exists(src, table):
            uids |= {r[0] for r in src.execute(f'SELECT DISTINCT user_id FROM "{table}"')}

    mapping: dict[int, int] = {}
    unresolved: list[int] = []
    for uid in sorted(uids):
        username = None
        for table in ("users", "user_accounts"):
            if not table_exists(src, table):
                continue
            row = src.execute(f"SELECT username FROM {table} WHERE id = ?", (uid,)).fetchone()
            if row and row[0]:
                username = row[0]
                break
        if username is None:
            unresolved.append(uid)
            continue
        row = dst.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if row is None:
            unresolved.append(uid)
            continue
        mapping[uid] = row[0]
    return mapping, unresolved


def migrate(target: Path, source: Path, apply: bool) -> int:
    verb = "APPLY" if apply else "DRY-RUN"
    print(f"[{verb}] target={target}")
    print(f"[{verb}] source={source}\n")

    if not target.exists():
        print(f"error: target database not found: {target}", file=sys.stderr)
        return 2
    if not source.exists():
        print(f"error: source database not found: {source}", file=sys.stderr)
        return 2

    dst = sqlite3.connect(str(target))
    src = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    dst.execute("PRAGMA foreign_keys = OFF")

    try:
        # ── 1. widen existing tables ──────────────────────────────────
        print("== columns ==")
        added = 0
        for table, cols in ADD_COLUMNS.items():
            if not table_exists(dst, table):
                print(f"  {table}: absent from target, skipped")
                continue
            have = columns(dst, table)
            for name, decl in cols:
                if name in have:
                    continue
                print(f"  {table}.{name} += {decl}")
                if apply:
                    dst.execute(f'ALTER TABLE "{table}" ADD COLUMN {name} {decl}')
                added += 1
        print(f"  {added} column(s) {'added' if apply else 'to add'}\n")

        # ── 2. create missing tables ──────────────────────────────────
        print("== tables ==")
        created = 0
        for table in CREATE_TABLES:
            if table_exists(dst, table):
                continue
            row = src.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone()
            if not row or not row[0]:
                print(f"  {table}: no DDL in source, skipped")
                continue
            print(f"  CREATE {table}")
            if apply:
                dst.execute(row[0])
            created += 1
        print(f"  {created} table(s) {'created' if apply else 'to create'}\n")

        if not apply and created:
            print("(dry run: row migration below assumes the tables above exist)\n")

        # ── 3. map users ──────────────────────────────────────────────
        print("== user id mapping (by username) ==")
        mapping, unresolved = build_user_map(src, dst)
        for uni_id, auth_id in sorted(mapping.items()):
            name = src.execute("SELECT username FROM users WHERE id=?", (uni_id,)).fetchone()
            print(f"  uni {uni_id:<5} -> auth {auth_id:<5} ({name[0] if name else '?'})")
        if unresolved:
            print(f"  UNRESOLVED (skipped): {unresolved}")
        print()

        # ── 4. copy rows ──────────────────────────────────────────────
        print("== rows ==")
        copied = skipped = 0
        for table in MIGRATE_USER_TABLES:
            if not (table_exists(src, table) and (apply or table_exists(dst, table))):
                print(f"  {table}: not present in both, skipped")
                continue
            if not table_exists(dst, table):
                print(f"  {table}: target table pending creation, skipped in dry run")
                continue
            shared = [c for c in columns(src, table) if c in columns(dst, table) and c != "id"]
            placeholders = ",".join("?" * len(shared))
            collist = ",".join(f'"{c}"' for c in shared)
            uid_idx = shared.index("user_id")

            key_cols = [c for c in NATURAL_KEYS.get(table, ["user_id"]) if c in shared]
            where = " AND ".join(f'"{c}" IS ?' for c in key_cols)
            key_idx = [shared.index(c) for c in key_cols]

            t_copied = t_skipped = t_present = 0
            for row in src.execute(f'SELECT {collist} FROM "{table}"'):
                values = list(row)
                uni_uid = values[uid_idx]
                if uni_uid not in mapping:
                    t_skipped += 1
                    continue
                values[uid_idx] = mapping[uni_uid]
                # Already migrated by an earlier run? Leave it alone.
                if dst.execute(
                    f'SELECT 1 FROM "{table}" WHERE {where} LIMIT 1',
                    [values[i] for i in key_idx],
                ).fetchone():
                    t_present += 1
                    continue
                if apply:
                    dst.execute(
                        f'INSERT OR IGNORE INTO "{table}" ({collist}) VALUES ({placeholders})',
                        values,
                    )
                t_copied += 1
            copied += t_copied
            skipped += t_skipped
            print(f"  {table:<28} copy {t_copied:<4} skip {t_skipped:<4} already-present {t_present}")

        for table in MIGRATE_GLOBAL_TABLES:
            if not (table_exists(src, table) and table_exists(dst, table)):
                continue
            if dst.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]:
                print(f"  {table:<28} target not empty, left alone")
                continue
            shared = [c for c in columns(src, table) if c in columns(dst, table)]
            collist = ",".join(f'"{c}"' for c in shared)
            rows = list(src.execute(f'SELECT {collist} FROM "{table}"'))
            if apply:
                dst.executemany(
                    f'INSERT OR IGNORE INTO "{table}" ({collist}) '
                    f'VALUES ({",".join("?" * len(shared))})',
                    rows,
                )
            copied += len(rows)
            print(f"  {table:<28} copy {len(rows):<4} (global)")

        print(f"\n  {copied} row(s) {'copied' if apply else 'to copy'}, {skipped} skipped\n")

        if apply:
            dst.commit()
            problems = dst.execute("PRAGMA integrity_check").fetchone()[0]
            print(f"integrity_check: {problems}")
            print("committed.")
        else:
            dst.rollback()
            print("dry run — nothing written.")
        return 0
    finally:
        src.close()
        dst.close()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--target", type=Path, default=DEFAULT_TARGET,
                   help="auth database to widen (default: the live auth.db)")
    p.add_argument("--source", type=Path, default=DEFAULT_SOURCE,
                   help="university database to read MFA rows from")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="report changes, write nothing")
    mode.add_argument("--apply", action="store_true", help="perform the migration")
    args = p.parse_args(argv)
    return migrate(args.target, args.source, apply=args.apply)


if __name__ == "__main__":
    raise SystemExit(main())
