"""SQLite database connection with optional encryption at rest.

Uses pysqlcipher3 when available and SQLITE_ENCRYPTION_KEY is set.
Falls back to standard sqlite3 transparently when encryption is not configured.
"""

import logging
import os
import sqlite3
import time
from pathlib import Path

logger = logging.getLogger(__name__)

_HAS_SQLCIPHER = False
_sqlcipher = None

try:
    import pysqlcipher3.dbapi2 as _sqlcipher
    _HAS_SQLCIPHER = True
except ImportError:
    try:
        from sqlcipher3 import dbapi2 as _sqlcipher
        _HAS_SQLCIPHER = True
    except ImportError:
        pass


def get_encryption_key() -> str | None:
    """Load the SQLite encryption key from environment."""
    return os.environ.get("SQLITE_ENCRYPTION_KEY")


def is_encryption_available() -> bool:
    """Check if database encryption at rest is available."""
    return _HAS_SQLCIPHER and bool(get_encryption_key())


def encrypted_connect(
    db_path: str,
    max_retries: int = 3,
    retry_delay: float = 0.2,
    encryption_key: str | None = None,
) -> sqlite3.Connection:
    """Open a SQLite connection with optional encryption.

    If pysqlcipher3/sqlcipher3 is installed AND an encryption key is
    available (via parameter or SQLITE_ENCRYPTION_KEY env var), the
    database is opened with AES-256 encryption.  Otherwise falls back
    to standard unencrypted sqlite3.

    Returns a sqlite3.Connection (or sqlcipher equivalent, same API).
    """
    key = encryption_key or get_encryption_key()
    use_encryption = _HAS_SQLCIPHER and bool(key)

    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    for attempt in range(max_retries):
        try:
            if use_encryption:
                conn = _sqlcipher.connect(db_path, timeout=30)
                conn.execute(f"PRAGMA key = '{key}'")
                # Verify the key works
                conn.execute("SELECT count(*) FROM sqlite_master")
                logger.debug("Encrypted connection opened: %s", db_path)
            else:
                conn = sqlite3.connect(db_path, timeout=30)

            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA busy_timeout=5000")

            # Secure file permissions
            try:
                p = Path(db_path)
                if p.exists():
                    os.chmod(p, 0o600)
            except OSError:
                pass

            return conn

        except Exception as e:
            if "database is locked" in str(e) and attempt < max_retries - 1:
                logger.warning(
                    "Database locked, retrying in %.1fs (attempt %d/%d)",
                    retry_delay, attempt + 1, max_retries,
                )
                time.sleep(retry_delay)
                retry_delay *= 2
            elif use_encryption and "file is not a database" in str(e).lower():
                # Key mismatch or unencrypted DB — fall back to plain sqlite3
                logger.warning(
                    "Encrypted open failed for %s (wrong key or unencrypted DB). "
                    "Falling back to unencrypted connection.", db_path,
                )
                conn = sqlite3.connect(db_path, timeout=30)
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA foreign_keys=ON")
                return conn
            else:
                raise


def encrypt_existing_database(db_path: str, encryption_key: str) -> bool:
    """Encrypt an existing unencrypted SQLite database.

    Creates a new encrypted copy, then replaces the original.
    Returns True on success.
    """
    if not _HAS_SQLCIPHER:
        logger.error("pysqlcipher3 not installed — cannot encrypt database")
        return False

    import shutil
    import tempfile

    src = Path(db_path)
    if not src.exists():
        logger.error("Database not found: %s", db_path)
        return False

    try:
        # Open the unencrypted database
        plain_conn = sqlite3.connect(str(src))

        # Create encrypted copy in temp file
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".db")
        os.close(tmp_fd)

        enc_conn = _sqlcipher.connect(tmp_path)
        enc_conn.execute(f"PRAGMA key = '{encryption_key}'")

        # Copy all data
        plain_conn.backup(enc_conn)

        plain_conn.close()
        enc_conn.close()

        # Replace original with encrypted version
        backup_path = str(src) + ".unencrypted.bak"
        shutil.copy2(str(src), backup_path)
        shutil.move(tmp_path, str(src))

        logger.info("Database encrypted: %s (backup at %s)", db_path, backup_path)
        return True

    except Exception as e:
        logger.error("Failed to encrypt database %s: %s", db_path, e)
        if Path(tmp_path).exists():
            os.unlink(tmp_path)
        return False


def check_encryption_status(db_path: str) -> dict:
    """Check whether a database file is encrypted.

    Returns a dict with 'encrypted' (bool), 'engine' (str), and 'path'.
    """
    result = {"path": db_path, "encrypted": False, "engine": "sqlite3"}

    if not Path(db_path).exists():
        result["error"] = "file not found"
        return result

    # Try opening with plain sqlite3
    try:
        conn = sqlite3.connect(db_path)
        conn.execute("SELECT count(*) FROM sqlite_master")
        conn.close()
        result["encrypted"] = False
        result["engine"] = "sqlite3"
        return result
    except Exception:
        pass

    # If plain open failed, it might be encrypted
    if _HAS_SQLCIPHER:
        key = get_encryption_key()
        if key:
            try:
                conn = _sqlcipher.connect(db_path)
                conn.execute(f"PRAGMA key = '{key}'")
                conn.execute("SELECT count(*) FROM sqlite_master")
                conn.close()
                result["encrypted"] = True
                result["engine"] = "sqlcipher"
                return result
            except Exception:
                pass

    result["error"] = "unable to open (encrypted with unknown key or corrupt)"
    return result
