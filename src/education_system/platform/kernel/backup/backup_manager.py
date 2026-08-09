"""Shared backup/restore manager for SQLite databases."""

import os
import shutil
import gzip
import hashlib
import hmac
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

_DEV_ENVIRONMENTS = ("development", "dev", "local", "test", "testing")


def _is_dev() -> bool:
    return os.getenv("APP_ENV", "production").strip().lower() in _DEV_ENVIRONMENTS


def _integrity_key() -> bytes | None:
    """Key for signing backup metadata, or None if none is configured."""
    key = (
        os.environ.get("BACKUP_INTEGRITY_KEY")
        or os.environ.get("BACKUP_ENCRYPTION_KEY")
        or os.environ.get("ENCRYPTION_KEY")
        or os.environ.get("API_SECRET_KEY")
    )
    return key.encode() if key else None


def _meta_signature(meta: dict, key: bytes) -> str:
    """Deterministic HMAC over the security-relevant metadata fields."""
    material = "|".join(
        str(meta.get(f, ""))
        for f in ("source", "backup", "timestamp", "compressed", "encrypted",
                  "size_bytes", "checksum_sha256")
    )
    return hmac.new(key, material.encode(), hashlib.sha256).hexdigest()


def backup(db_path, backup_dir, compress=True, label=None, encrypt=False, encryption_key=None):
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

    if encrypt:
        # Fail closed: if encryption is requested we must not silently leave a
        # plaintext copy of a database full of personal data on disk. A missing
        # key or missing library is an error, not a downgrade.
        try:
            from cryptography.fernet import Fernet
        except ImportError as exc:
            os.remove(backup_path)
            raise RuntimeError(
                "Backup encryption requested but the cryptography package is "
                "not installed; refusing to write an unencrypted backup."
            ) from exc
        key = (encryption_key or os.environ.get("BACKUP_ENCRYPTION_KEY")
               or os.environ.get("ENCRYPTION_KEY"))
        if not key:
            os.remove(backup_path)
            raise RuntimeError(
                "Backup encryption requested but no key available. Set "
                "BACKUP_ENCRYPTION_KEY (or ENCRYPTION_KEY)."
            )
        fernet = Fernet(key.encode() if isinstance(key, str) else key)
        with open(backup_path, "rb") as f:
            data = f.read()
        encrypted = fernet.encrypt(data)
        enc_path = backup_path + ".enc"
        with open(os.open(enc_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "wb") as f:
            f.write(encrypted)
        os.remove(backup_path)
        backup_path = enc_path
        backup_name = os.path.basename(enc_path)
        logger.info("Backup encrypted: %s", enc_path)

    checksum = _file_checksum(backup_path)
    meta = {
        "source": db_path,
        "backup": backup_path,
        "timestamp": timestamp,
        "compressed": compress,
        "encrypted": encrypt,
        "size_bytes": os.path.getsize(backup_path),
        "checksum_sha256": checksum,
    }
    # Sign the metadata so the integrity record cannot be rewritten alongside a
    # tampered backup. A bare checksum sitting next to the file it attests is
    # forgeable; an HMAC is not without the key.
    key = _integrity_key()
    if key is not None:
        meta["integrity_hmac"] = _meta_signature(meta, key)
    elif not _is_dev():
        os.remove(backup_path)
        raise RuntimeError(
            "No backup integrity key available in production. Set "
            "BACKUP_INTEGRITY_KEY (or ENCRYPTION_KEY/API_SECRET_KEY)."
        )
    meta_path = backup_path + ".meta.json"
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)
    try:
        os.chmod(backup_path, 0o600)
    except OSError:
        pass

    logger.info("Backup created: %s (%s bytes)", backup_path, meta["size_bytes"])
    return backup_path


def restore(backup_path, db_path, encryption_key=None):
    """Restore a database from a backup file.

    Handles encrypted (.enc), compressed (.gz), and plain backups.
    """
    if not os.path.exists(backup_path):
        raise FileNotFoundError(f"Backup not found: {backup_path}")

    # Verify integrity before touching the live database. Restoring a tampered
    # or truncated backup over a good database is itself a data-loss event.
    verification = verify_backup(backup_path)
    if not verification.get("valid"):
        raise ValueError(
            f"Refusing to restore: backup integrity check failed "
            f"({verification.get('error', 'checksum/signature mismatch')})"
        )

    if os.path.exists(db_path):
        safety = db_path + ".pre_restore"
        shutil.copy2(db_path, safety)
        logger.info("Pre-restore safety copy: %s", safety)

    source_path = backup_path

    # Handle encrypted backups
    if backup_path.endswith(".enc"):
        try:
            from cryptography.fernet import Fernet
            key = encryption_key or os.environ.get("BACKUP_ENCRYPTION_KEY") or os.environ.get("ENCRYPTION_KEY")
            if not key:
                raise ValueError("Encrypted backup requires an encryption key")
            fernet = Fernet(key.encode() if isinstance(key, str) else key)
            with open(backup_path, "rb") as f:
                encrypted_data = f.read()
            decrypted = fernet.decrypt(encrypted_data)
            # Write decrypted data to a temp file
            source_path = backup_path + ".dec"
            with open(source_path, "wb") as f:
                f.write(decrypted)
            logger.info("Backup decrypted for restore")
        except ImportError:
            raise ImportError("cryptography package required to restore encrypted backups")

    try:
        if source_path.endswith(".gz") or (source_path.endswith(".dec") and backup_path.endswith(".gz.enc")):
            with gzip.open(source_path, "rb") as f_in, open(db_path, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
        else:
            shutil.copy2(source_path, db_path)
    finally:
        # Clean up temp decrypted file
        if source_path != backup_path and os.path.exists(source_path):
            os.remove(source_path)

    logger.info("Database restored from %s to %s", backup_path, db_path)


def verify_backup(backup_path):
    """Verify backup integrity using the signed checksum metadata."""
    meta_path = backup_path + ".meta.json"
    if not os.path.exists(meta_path):
        return {"valid": False, "error": "No metadata file found"}
    with open(meta_path) as f:
        meta = json.load(f)

    # If the metadata was signed, verify the signature first: an attacker who
    # can rewrite the backup can also rewrite an unsigned checksum to match.
    stored_sig = meta.get("integrity_hmac")
    key = _integrity_key()
    if stored_sig:
        if key is None:
            return {"valid": False, "error": "integrity key unavailable to verify signature"}
        if not hmac.compare_digest(stored_sig, _meta_signature(meta, key)):
            return {"valid": False, "error": "metadata signature mismatch"}
    elif not _is_dev():
        # A production backup with no signature cannot be trusted.
        return {"valid": False, "error": "backup metadata is unsigned"}

    actual = _file_checksum(backup_path)
    expected = meta.get("checksum_sha256") or ""
    valid = hmac.compare_digest(actual, expected)
    return {"valid": valid, "expected": expected, "actual": actual}


def list_backups(backup_dir):
    """List all backups in a directory."""
    if not os.path.exists(backup_dir):
        return []
    backups = []
    for name in sorted(os.listdir(backup_dir), reverse=True):
        if name.endswith((".db", ".db.gz", ".db.enc", ".db.gz.enc", ".enc")) and not name.endswith(".pre_restore"):
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
    # Only ever remove backup artefacts — not arbitrary files that happen to
    # share the directory. Each backup and its sidecars go together.
    backup_suffixes = (".db", ".db.gz", ".db.enc", ".db.gz.enc", ".enc")
    for name in os.listdir(backup_dir):
        if not (name.endswith(backup_suffixes) and not name.endswith(".pre_restore")):
            continue
        path = os.path.join(backup_dir, name)
        if os.path.getmtime(path) < cutoff:
            os.remove(path)
            for sidecar in (path + ".meta.json",):
                if os.path.exists(sidecar):
                    os.remove(sidecar)
            removed += 1
    logger.info("Cleaned up %d old backups from %s", removed, backup_dir)
    return removed


def _file_checksum(filepath):
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()
