"""Shared backup/restore manager for SQLite databases."""

import os
import shutil
import gzip
import hashlib
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def backup(db_path, backup_dir, compress=True, label=None):
    """Create a backup of a SQLite database.

    Returns the backup file path.
    """
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database not found: {db_path}")
    os.makedirs(backup_dir, exist_ok=True)

    db_name = os.path.splitext(os.path.basename(db_path))[0]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = f"_{label}" if label else ""
    ext = ".db.gz" if compress else ".db"
    backup_name = f"{db_name}{suffix}_{timestamp}{ext}"
    backup_path = os.path.join(backup_dir, backup_name)

    if compress:
        with open(db_path, "rb") as f_in, gzip.open(backup_path, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
    else:
        shutil.copy2(db_path, backup_path)

    checksum = _file_checksum(backup_path)
    meta = {
        "source": db_path,
        "backup": backup_path,
        "timestamp": timestamp,
        "compressed": compress,
        "size_bytes": os.path.getsize(backup_path),
        "checksum_sha256": checksum,
    }
    meta_path = backup_path + ".meta.json"
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)

    logger.info("Backup created: %s (%s bytes)", backup_path, meta["size_bytes"])
    return backup_path


def restore(backup_path, db_path):
    """Restore a database from a backup file."""
    if not os.path.exists(backup_path):
        raise FileNotFoundError(f"Backup not found: {backup_path}")

    if os.path.exists(db_path):
        safety = db_path + ".pre_restore"
        shutil.copy2(db_path, safety)
        logger.info("Pre-restore safety copy: %s", safety)

    if backup_path.endswith(".gz"):
        with gzip.open(backup_path, "rb") as f_in, open(db_path, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
    else:
        shutil.copy2(backup_path, db_path)

    logger.info("Database restored from %s to %s", backup_path, db_path)


def verify_backup(backup_path):
    """Verify backup integrity using stored checksum."""
    meta_path = backup_path + ".meta.json"
    if not os.path.exists(meta_path):
        return {"valid": False, "error": "No metadata file found"}
    with open(meta_path) as f:
        meta = json.load(f)
    actual = _file_checksum(backup_path)
    valid = actual == meta.get("checksum_sha256")
    return {"valid": valid, "expected": meta.get("checksum_sha256"), "actual": actual}


def list_backups(backup_dir):
    """List all backups in a directory."""
    if not os.path.exists(backup_dir):
        return []
    backups = []
    for name in sorted(os.listdir(backup_dir), reverse=True):
        if name.endswith((".db", ".db.gz")) and not name.endswith(".pre_restore"):
            path = os.path.join(backup_dir, name)
            meta_path = path + ".meta.json"
            meta = {}
            if os.path.exists(meta_path):
                with open(meta_path) as f:
                    meta = json.load(f)
            backups.append({
                "filename": name,
                "path": path,
                "size_bytes": os.path.getsize(path),
                "timestamp": meta.get("timestamp", ""),
                "source": meta.get("source", ""),
            })
    return backups


def cleanup_old_backups(backup_dir, retention_days=30):
    """Remove backups older than retention_days."""
    if not os.path.exists(backup_dir):
        return 0
    cutoff = datetime.now().timestamp() - (retention_days * 86400)
    removed = 0
    for name in os.listdir(backup_dir):
        path = os.path.join(backup_dir, name)
        if os.path.getmtime(path) < cutoff:
            os.remove(path)
            removed += 1
    logger.info("Cleaned up %d old backups from %s", removed, backup_dir)
    return removed


def _file_checksum(filepath):
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()
