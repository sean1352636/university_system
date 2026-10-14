"""Encryption key generation and the key-inventory viewer."""
import logging

logger = logging.getLogger(__name__)

import os

from cryptography.fernet import Fernet

from education_system.systems.university.domains.pastoral.infrastructure.health.storage import sqlite3
from education_system.systems.university.domains.pastoral.domain.health.services import get_connection

from .schema import _first_existing_column, ensure_security_schema

def get_or_create_encryption_key():
    """Get or create encryption key for sensitive data"""
    key_file = 'health_encryption.key'
    if os.path.exists(key_file):
        with open(key_file, 'rb') as f:
            return f.read()
    else:
        key = Fernet.generate_key()
        with open(key_file, 'wb') as f:
            f.write(key)
        os.chmod(key_file, 0o600)
        return key


def encryption_key_management(auth):
    """
    Show key inventory. Handles schemas with/without algorithm/status.
    """
    ensure_security_schema()
    conn = get_connection()
    try:
        c = conn.cursor()

        key_id     = _first_existing_column(conn, "encryption_keys", ["key_id", "id", "kid"])
        algorithm  = _first_existing_column(conn, "encryption_keys", ["algorithm", "algo", "type", "key_type"])
        created_at = _first_existing_column(conn, "encryption_keys", ["created_at", "created", "timestamp"])
        status_col = _first_existing_column(conn, "encryption_keys", ["status", "is_active"])

        cols = [key_id, algorithm, created_at, status_col]
        sel  = ", ".join("[" + c + "]" for c in cols)
        sql  = "SELECT " + sel + " FROM [encryption_keys] ORDER BY [" + created_at + "] DESC"
        rows = c.execute(sql).fetchall()

        print("\nEncryption Keys:")
        if not rows:
            print("- (none)")
        else:
            for row in rows:
                kid, algo, c_at, st = row
                # normalize status
                s = str(st).strip().lower()
                if s in ("1","true","on","enabled","active"):
                    s_disp = "active"
                elif s in ("0","false","off","disabled","inactive"):
                    s_disp = "inactive"
                else:
                    s_disp = st if st is not None else "—"
                print(f"- {kid}: {algo or 'unknown'}, created {c_at or '—'} [{s_disp}]")

        input("\nPress Enter to return...")

    except sqlite3.OperationalError as e:
        print(f"Encryption key view unavailable: {e}")
        input("\nPress Enter to return...")
    finally:
        try:
            conn.close()
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)
