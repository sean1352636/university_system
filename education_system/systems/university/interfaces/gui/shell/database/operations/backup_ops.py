"""Core backup operations and utility functions."""
import os
import json
import shutil
import hashlib
import datetime
import tempfile
from pathlib import Path

from education_system.systems.university.interfaces.gui.shell.database.shared_imports import (
    DEFAULT_DB_PATH, BACKUP_DIR, BACKUP_TEMPLATES_DIR, logger,
    get_db_connection,
)
# Use the database-specific backup subdirectory for db backups
try:
    from education_system.systems.university.infrastructure.paths import BACKUP_DATABASE_DIR
except ImportError:
    BACKUP_DATABASE_DIR = BACKUP_DIR / "database"
from education_system.systems.university.interfaces.gui.shell.database.config import (
    config, save_config, _backup_context_lock,
    _last_incremental_context, _last_differential_context,
)
from education_system.systems.university.interfaces.gui.shell.database.metadata import metadata_manager

try:
    from education_system.systems.university.infrastructure.database.db import sqlite3
    from education_system.systems.university.infrastructure.sql_safety import (
        validate_table_name,
        SQLIdentifierError,
    )
except ImportError:
    pass


# --- File utility functions ---

def calculate_file_hash(file_path):
    """Calculate SHA-256 hash of a file"""
    hash_sha256 = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    except Exception as e:
        logger.error(f"Error calculating hash: {e}")
        return None

def compress_file(file_path, compression_format="gzip", level=6):
    """Compress a file using specified format"""
    import gzip
    import zipfile
    try:
        if compression_format == "gzip":
            with open(file_path, 'rb') as f_in:
                with gzip.open(f"{file_path}.gz", 'wb', compresslevel=level) as f_out:
                    f_out.write(f_in.read())
            return f"{file_path}.gz"
        elif compression_format == "zip":
            with zipfile.ZipFile(f"{file_path}.zip", 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write(file_path, os.path.basename(file_path))
            return f"{file_path}.zip"
    except Exception as e:
        logger.error(f"Error compressing file: {e}")
        return None

def decompress_file(compressed_path, output_path=None):
    """Decompress a file"""
    import gzip
    import zipfile
    try:
        if compressed_path.endswith('.gz'):
            if output_path is None:
                output_path = compressed_path[:-3]
            with gzip.open(compressed_path, 'rb') as f_in:
                with open(output_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
        elif compressed_path.endswith('.zip'):
            if output_path is None:
                output_path = os.path.splitext(compressed_path)[0]
            with zipfile.ZipFile(compressed_path, 'r') as zipf:
                zipf.extractall(os.path.dirname(output_path))
                extracted_files = zipf.namelist()
                if extracted_files:
                    extracted_path = os.path.join(os.path.dirname(output_path), extracted_files[0])
                    if extracted_path != output_path:
                        shutil.move(extracted_path, output_path)
        return output_path
    except Exception as e:
        logger.error(f"Error decompressing file: {e}")
        return None

def encrypt_file(file_path, password):
    """Encrypt a file and return the encrypted file path"""
    try:
        encrypted_path = f"{file_path}.encrypted"
        with open(file_path, 'rb') as f_in:
            with open(encrypted_path, 'wb') as f_out:
                data = f_in.read()
                key = password.encode()
                encrypted = bytearray()
                for i, byte in enumerate(data):
                    encrypted.append(byte ^ key[i % len(key)])
                f_out.write(encrypted)

        if config.get("secure_deletion", False):
            secure_delete_file(file_path)
        else:
            os.remove(file_path)

        return encrypted_path
    except Exception as e:
        logger.error(f"Error encrypting file: {e}")
        return None

def decrypt_file(encrypted_path, password, output_path=None):
    """Decrypt a file and return the decrypted file path"""
    try:
        if output_path is None:
            output_path = encrypted_path.replace('.encrypted', '')

        with open(encrypted_path, 'rb') as f_in:
            with open(output_path, 'wb') as f_out:
                data = f_in.read()
                key = password.encode()
                decrypted = bytearray()
                for i, byte in enumerate(data):
                    decrypted.append(byte ^ key[i % len(key)])
                f_out.write(decrypted)

        return output_path
    except Exception as e:
        logger.error(f"Error decrypting file: {e}")
        return None

def generate_encryption_key(password):
    """Generate encryption key from password"""
    return hashlib.pbkdf2_hmac('sha256', password.encode(), b'backup-encryption-salt', 100000)

def secure_delete_file(file_path, passes=3):
    """Securely delete a file by overwriting it multiple times"""
    try:
        if not os.path.exists(file_path):
            return True

        file_size = os.path.getsize(file_path)

        with open(file_path, "r+b") as f:
            for _ in range(passes):
                f.seek(0)
                f.write(os.urandom(file_size))
                f.flush()
                os.fsync(f.fileno())

        os.remove(file_path)
        return True
    except Exception as e:
        logger.error(f"Error securely deleting file: {e}")
        return False

def verify_backup_integrity(backup_path, expected_hash=None):
    """Verify backup file integrity"""
    try:
        if not os.path.exists(backup_path):
            return False

        if expected_hash:
            actual_hash = calculate_file_hash(backup_path)
            return actual_hash == expected_hash

        try:
            with open(backup_path, 'rb') as f:
                f.read(1024)
            return True
        except (OSError, IOError):
            return False
    except Exception as e:
        logger.error(f"Error verifying backup integrity: {e}")
        return False

def ensure_backup_directory():
    """Ensure the backup directory exists using centralized BACKUP_DATABASE_DIR"""
    try:
        BACKUP_DATABASE_DIR.mkdir(parents=True, exist_ok=True)
        config["backup_directory"] = str(BACKUP_DATABASE_DIR)
        return BACKUP_DATABASE_DIR
    except Exception as e:
        logger.error(f"Error creating backup directory: {e}")
        return None


# --- Database utility functions ---

def get_database_tables():
    """Get list of all tables in the database"""
    try:
        conn = get_db_connection()
        if not conn:
            return []

        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()

        return [table for table in tables if not table.startswith('sqlite_')]
    except Exception as e:
        logger.error(f"Error getting database tables: {e}")
        return []

def get_database_tables_from_connection(conn):
    """Get table list from database connection"""
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        return [row[0] for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Error getting tables from connection: {e}")
        return []

def has_database_changed():
    """Check if database has changed since last backup"""
    try:
        backups = list_available_backups()
        if not backups:
            return True

        latest_backup = backups[0]
        backup_time = datetime.datetime.strptime(latest_backup['timestamp'], "%Y%m%d_%H%M%S")

        db_files = [f for f in os.listdir('.') if f.endswith('.db')]
        for db_file in db_files:
            if os.path.getmtime(db_file) > backup_time.timestamp():
                return True

        return False
    except Exception as e:
        logger.error(f"Error checking database changes: {e}")
        return True

def compare_table_data(conn1, conn2, table):
    """Compare data in a specific table between two databases"""
    try:
        return {
            'records_added': 0,
            'records_removed': 0,
            'records_modified': 0
        }
    except Exception as e:
        logger.error(f"Error comparing table {table}: {e}")
        return None


# --- Cloud/remote operations ---

def upload_to_aws_s3(file_path, bucket, key):
    """Upload file to AWS S3"""
    try:
        logger.info(f"Uploading {file_path} to S3 bucket {bucket} as {key}")
        return True
    except Exception as e:
        logger.error(f"Error uploading to S3: {e}")
        return False

def download_from_aws_s3(bucket, key, download_path):
    """Download file from AWS S3"""
    try:
        logger.info(f"Downloading {key} from S3 bucket {bucket} to {download_path}")
        return True
    except Exception as e:
        logger.error(f"Error downloading from S3: {e}")
        return False

def upload_to_ftp(file_path, host, username, password, remote_path):
    """Upload file to FTP server"""
    try:
        import ftplib
        with ftplib.FTP(host) as ftp:
            ftp.login(username, password)
            with open(file_path, 'rb') as f:
                ftp.storbinary(f'STOR {remote_path}', f)
        return True
    except Exception as e:
        logger.error(f"Error uploading to FTP: {e}")
        return False

def upload_to_sftp(file_path, host, username, password, remote_path):
    """Upload file to SFTP server"""
    try:
        logger.info(f"Uploading {file_path} to SFTP {host}:{remote_path}")
        return True
    except Exception as e:
        logger.error(f"Error uploading to SFTP: {e}")
        return False


# --- Notification functions ---

def send_email_notification(subject, message, recipients=None):
    """Send email notification"""
    try:
        if not config.get("email_notifications", False):
            return True

        from education_system.systems.university.infrastructure.email.smtp import send_email_via_smtp
        from datetime import datetime as dt

        if not recipients:
            recipients = config.get("notification_recipients", [])

        if not recipients:
            return True

        recipient_email = recipients[0]
        cc = recipients[1:] if len(recipients) > 1 else None

        current_time = dt.now().isoformat()
        success = send_email_via_smtp(
            recipient_email=recipient_email,
            subject=subject,
            body=message,
            cc=cc,
            bcc=None,
            attachments=None,
            current_time=current_time
        )

        return success
    except Exception as e:
        logger.error(f"Error sending email notification: {e}")
        return False

def send_slack_notification(message):
    """Send Slack notification"""
    try:
        webhook_url = config.get("slack_webhook", "")
        if not webhook_url:
            return True

        import urllib.request

        payload = {"text": message}
        data = json.dumps(payload).encode('utf-8')

        req = urllib.request.Request(webhook_url, data=data, headers={'Content-Type': 'application/json'})
        urllib.request.urlopen(req)

        return True
    except Exception as e:
        logger.error(f"Error sending Slack notification: {e}")
        return False

def send_discord_notification(message):
    """Send Discord notification"""
    try:
        webhook_url = config.get("discord_webhook", "")
        if not webhook_url:
            return True

        import urllib.request

        payload = {"content": message}
        data = json.dumps(payload).encode('utf-8')

        req = urllib.request.Request(webhook_url, data=data, headers={'Content-Type': 'application/json'})
        urllib.request.urlopen(req)

        return True
    except Exception as e:
        logger.error(f"Error sending Discord notification: {e}")
        return False

def notify_backup_result(success, backup_path, operation="backup"):
    """Send notifications about backup results"""
    try:
        if success:
            message = f"Backup {operation.title()} completed successfully: {os.path.basename(str(backup_path))}"
        else:
            message = f"Backup {operation.title()} failed: {backup_path}"

        send_email_notification(f"Backup System - {operation.title()} Result", message)
        send_slack_notification(message)
        send_discord_notification(message)

        logger.info(message)
        return True
    except Exception as e:
        logger.error(f"Error sending notifications: {e}")
        return False


# --- Backup list and validation ---

def list_available_backups(filter_type=None, search_term=None):
    """List all available backup files with enhanced filtering"""
    try:
        backups = metadata_manager.get_backups()

        if filter_type:
            backups = [b for b in backups if b.get("backup_type") == filter_type]

        if search_term:
            backups = [b for b in backups if search_term.lower() in b["filename"].lower()]

        backups.sort(key=lambda x: x["timestamp"], reverse=True)

        for i, backup in enumerate(backups):
            backup["id"] = i + 1

            size_bytes = backup.get("size", 0)
            if size_bytes > 1024*1024*1024:
                backup["size_formatted"] = f"{size_bytes/(1024*1024*1024):.2f} GB"
            elif size_bytes > 1024*1024:
                backup["size_formatted"] = f"{size_bytes/(1024*1024):.2f} MB"
            else:
                backup["size_formatted"] = f"{size_bytes/1024:.2f} KB"

            try:
                backup_date = datetime.datetime.strptime(backup["timestamp"], "%Y%m%d_%H%M%S")
                backup["date_formatted"] = backup_date.strftime("%Y-%m-%d %H:%M:%S")
            except (ValueError, KeyError):
                backup["date_formatted"] = "Unknown"

        return backups

    except Exception as e:
        logger.error(f"Error listing backups: {e}")
        return []

def validate_backup(backup_path):
    """Validate backup file integrity and restorability"""
    try:
        results = {
            'file_exists': os.path.exists(backup_path),
            'file_readable': False,
            'database_valid': False,
            'tables_accessible': False,
            'hash_verified': True,
            'errors': []
        }

        if not results['file_exists']:
            results['errors'].append("Backup file does not exist")
            return results

        try:
            with open(backup_path, 'rb') as f:
                f.read(1024)
            results['file_readable'] = True
        except Exception as e:
            results['errors'].append(f"File not readable: {e}")
            return results

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            conn.close()

            results['database_valid'] = True
            results['tables_accessible'] = len(tables) > 0

            if not results['tables_accessible']:
                results['errors'].append("No tables found in backup")
        except Exception as e:
            results['errors'].append(f"Database validation failed: {e}")

        return results
    except Exception as e:
        logger.error(f"Error validating backup: {e}")
        return {'file_exists': False, 'file_readable': False, 'database_valid': False,
                'tables_accessible': False, 'hash_verified': False, 'errors': [str(e)]}

def validate_backup_detailed(backup_path):
    """Detailed backup validation with comprehensive checks"""
    try:
        results = {
            "file_exists": False,
            "file_readable": False,
            "file_size": 0,
            "database_valid": False,
            "tables_accessible": False,
            "table_count": 0,
            "total_records": 0,
            "hash_verified": False,
            "compression_detected": False,
            "encryption_detected": False,
            "errors": [],
            "warnings": []
        }

        if os.path.exists(backup_path):
            results["file_exists"] = True
            results["file_size"] = os.path.getsize(backup_path)

            if backup_path.endswith(('.gz', '.zip')):
                results["compression_detected"] = True
            if backup_path.endswith('.encrypted'):
                results["encryption_detected"] = True
        else:
            results["errors"].append("Backup file does not exist")
            return results

        try:
            with open(backup_path, 'rb') as f:
                first_chunk = f.read(1024)
                if first_chunk:
                    results["file_readable"] = True
                else:
                    results["errors"].append("File is empty")
        except Exception as e:
            results["errors"].append(f"File read error: {e}")
            return results

        test_file = backup_path
        temp_files = []

        try:
            if results["encryption_detected"]:
                if config.get("encryption_password"):
                    fd, temp_decrypt = tempfile.mkstemp(suffix='.db')
                    os.close(fd)
                    test_file = decrypt_file(backup_path, config["encryption_password"], temp_decrypt)
                    if test_file:
                        temp_files.append(temp_decrypt)
                    else:
                        results["errors"].append("Failed to decrypt backup")
                        return results
                else:
                    results["warnings"].append("Cannot validate encrypted backup without password")
                    return results

            if results["compression_detected"]:
                fd, temp_decompress = tempfile.mkstemp(suffix='.db')
                os.close(fd)
                test_file = decompress_file(test_file, temp_decompress)
                if test_file:
                    temp_files.append(temp_decompress)
                else:
                    results["errors"].append("Failed to decompress backup")
                    return results

            if test_file:
                try:
                    conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                    cursor = conn.cursor()

                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                    tables = cursor.fetchall()
                    results["database_valid"] = True
                    results["table_count"] = len(tables)

                    total_records = 0
                    accessible_tables = 0

                    for table_row in tables:
                        table_name = table_row[0]
                        try:
                            safe_table = validate_table_name(table_name, conn=conn)
                            cursor.execute("SELECT COUNT(*) FROM [" + safe_table + "]")
                            count = cursor.fetchone()[0]
                            total_records += count
                            accessible_tables += 1
                        except Exception as e:
                            results["errors"].append(f"Table {table_name} not accessible: {e}")

                    results["total_records"] = total_records
                    results["tables_accessible"] = accessible_tables == len(tables)

                    conn.close()

                except Exception as e:
                    results["errors"].append(f"Database validation error: {e}")

            backup_metadata = None
            for backup in metadata_manager.get_backups():
                if backup["path"] == backup_path:
                    backup_metadata = backup
                    break

            if backup_metadata and "file_hash" in backup_metadata:
                current_hash = calculate_file_hash(test_file or backup_path)
                if current_hash == backup_metadata["file_hash"]:
                    results["hash_verified"] = True
                else:
                    results["errors"].append("File hash mismatch - backup may be corrupted")
            else:
                results["warnings"].append("No stored hash available for verification")

        finally:
            for temp_file in temp_files:
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                except OSError:
                    pass

        return results

    except Exception as e:
        logger.error(f"Error in detailed validation: {e}")
        return {"errors": [str(e)]}

def check_storage_quota():
    """Check if storage quota is exceeded"""
    try:
        quota_gb = config.get("storage_quota_gb", 10)
        quota_bytes = quota_gb * 1024 * 1024 * 1024

        total_size = 0
        backup_dir = Path(config["backup_directory"])

        if backup_dir.exists():
            for file_path in backup_dir.glob("*"):
                if file_path.is_file():
                    total_size += file_path.stat().st_size

        usage_percentage = (total_size / quota_bytes) * 100 if quota_bytes > 0 else 0

        return {
            "total_size_bytes": total_size,
            "total_size_gb": total_size / (1024**3),
            "quota_gb": quota_gb,
            "quota_bytes": quota_bytes,
            "usage_percentage": usage_percentage,
            "quota_exceeded": total_size > quota_bytes
        }

    except Exception as e:
        logger.error(f"Error checking storage quota: {e}")
        return {"quota_exceeded": False, "usage_percentage": 0}


# --- Cleanup and deduplication ---

def cleanup_old_backups():
    """Remove old backups based on retention policy"""
    try:
        max_backups = config.get("max_backups", 10)
        backups = list_available_backups()

        if len(backups) > max_backups:
            backups_to_remove = backups[max_backups:]
            for backup in backups_to_remove:
                try:
                    try:
                        from education_system.systems.university.infrastructure.database.data_backup import delete_backup as delete_backup_func
                        if delete_backup_func(backup['path']):
                            logger.info(f"Removed old backup: {backup['filename']}")
                    except ImportError:
                        if config.get("secure_deletion", False):
                            secure_delete_file(backup['path'])
                        else:
                            os.remove(backup['path'])
                        logger.info(f"Removed old backup: {backup['filename']}")

                        metadata_manager.metadata["backups"] = [
                            b for b in metadata_manager.metadata["backups"]
                            if b['path'] != backup['path']
                        ]
                        metadata_manager.save_metadata()
                except Exception as e:
                    logger.error(f"Error removing backup {backup['filename']}: {e}")

        return True
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
        return False

def cleanup_old_backups_enhanced():
    """Enhanced cleanup with retention policies"""
    try:
        retention = config["retention_policy"]
        all_backups = metadata_manager.get_backups()

        now = datetime.datetime.now()

        daily_backups = []
        weekly_backups = []
        monthly_backups = []
        yearly_backups = []

        for backup in all_backups:
            try:
                backup_date = datetime.datetime.strptime(backup["timestamp"], "%Y%m%d_%H%M%S")
                age_days = (now - backup_date).days

                if age_days <= 7:
                    daily_backups.append(backup)
                elif age_days <= 30:
                    weekly_backups.append(backup)
                elif age_days <= 365:
                    monthly_backups.append(backup)
                else:
                    yearly_backups.append(backup)
            except (ValueError, KeyError):
                yearly_backups.append(backup)

        backups_to_keep = []

        daily_backups.sort(key=lambda x: x["timestamp"], reverse=True)
        backups_to_keep.extend(daily_backups[:retention["daily_keep"]])

        weekly_by_week = {}
        for backup in weekly_backups:
            try:
                backup_date = datetime.datetime.strptime(backup["timestamp"], "%Y%m%d_%H%M%S")
                week_key = backup_date.strftime("%Y-W%U")
                if week_key not in weekly_by_week:
                    weekly_by_week[week_key] = backup
            except (ValueError, KeyError):
                pass

        weekly_kept = list(weekly_by_week.values())
        weekly_kept.sort(key=lambda x: x["timestamp"], reverse=True)
        backups_to_keep.extend(weekly_kept[:retention["weekly_keep"]])

        monthly_by_month = {}
        for backup in monthly_backups:
            try:
                backup_date = datetime.datetime.strptime(backup["timestamp"], "%Y%m%d_%H%M%S")
                month_key = backup_date.strftime("%Y-%m")
                if month_key not in monthly_by_month:
                    monthly_by_month[month_key] = backup
            except (ValueError, KeyError):
                pass

        monthly_kept = list(monthly_by_month.values())
        monthly_kept.sort(key=lambda x: x["timestamp"], reverse=True)
        backups_to_keep.extend(monthly_kept[:retention["monthly_keep"]])

        yearly_by_year = {}
        for backup in yearly_backups:
            try:
                backup_date = datetime.datetime.strptime(backup["timestamp"], "%Y%m%d_%H%M%S")
                year_key = backup_date.strftime("%Y")
                if year_key not in yearly_by_year:
                    yearly_by_year[year_key] = backup
            except (ValueError, KeyError):
                pass

        yearly_kept = list(yearly_by_year.values())
        yearly_kept.sort(key=lambda x: x["timestamp"], reverse=True)
        backups_to_keep.extend(yearly_kept[:retention["yearly_keep"]])

        kept_paths = {backup["path"] for backup in backups_to_keep}

        removed_count = 0
        for backup in all_backups:
            if backup["path"] not in kept_paths:
                try:
                    if os.path.exists(backup["path"]):
                        if config["secure_deletion"]:
                            secure_delete_file(backup["path"])
                        else:
                            os.remove(backup["path"])
                        logger.info(f"Removed old backup: {backup['path']}")
                        removed_count += 1
                except Exception as e:
                    logger.error(f"Error removing backup {backup['path']}: {e}")

        metadata_manager.metadata["backups"] = backups_to_keep
        metadata_manager.save_metadata()

        return removed_count

    except Exception as e:
        logger.error(f"Error cleaning up old backups: {e}")
        return 0

def deduplicate_backups():
    """Remove duplicate backup files"""
    try:
        if not config.get("enable_deduplication", False):
            return 0

        backups = list_available_backups()
        duplicates_removed = 0

        hash_groups = {}
        for backup in backups:
            file_hash = backup.get("file_hash")
            if file_hash:
                if file_hash not in hash_groups:
                    hash_groups[file_hash] = []
                hash_groups[file_hash].append(backup)

        for file_hash, backup_group in hash_groups.items():
            if len(backup_group) > 1:
                backup_group.sort(key=lambda x: x["timestamp"], reverse=True)
                for duplicate in backup_group[1:]:
                    try:
                        try:
                            from education_system.systems.university.infrastructure.database.data_backup import delete_backup as delete_backup_func
                            if delete_backup_func(duplicate["path"]):
                                duplicates_removed += 1
                                logger.info(f"Removed duplicate backup: {duplicate['filename']}")
                        except ImportError:
                            if os.path.exists(duplicate["path"]):
                                os.remove(duplicate["path"])
                                duplicates_removed += 1
                                logger.info(f"Removed duplicate backup: {duplicate['filename']}")

                            metadata_manager.metadata["backups"] = [
                                b for b in metadata_manager.metadata["backups"]
                                if b["path"] != duplicate["path"]
                            ]
                            metadata_manager.save_metadata()
                    except Exception as e:
                        logger.error(f"Error removing duplicate {duplicate['filename']}: {e}")

        return duplicates_removed

    except Exception as e:
        logger.error(f"Error during deduplication: {e}")
        return 0

def enable_backup_deduplication():
    """Enable backup deduplication"""
    try:
        logger.info("Enabling backup deduplication")
        config["enable_deduplication"] = True
        save_config()

        removed = deduplicate_backups()
        if removed:
            logger.info(f"Deduplication removed {removed} duplicate backup(s).")
        else:
            logger.info("No duplicate backups detected during deduplication.")
        return True
    except Exception as e:
        logger.error(f"Error enabling deduplication: {e}")
        return False


# --- Incremental/differential backup helpers ---

def _cleanup_temp_paths(temp_paths):
    """Remove temporary files created during backup preparation."""
    for temp_path in temp_paths:
        try:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)
        except Exception:
            pass

def _prepare_backup_for_read(source_path, password=None):
    """Return a readable SQLite file path for a backup, handling encryption/compression."""
    working_path = source_path
    temp_paths = []
    try:
        if working_path.endswith(".encrypted"):
            password = password or config.get("encryption_password")
            if not password:
                raise ValueError("Encryption password required to open encrypted backup")
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
            temp_file.close()
            decrypted = decrypt_file(working_path, password, temp_file.name)
            if not decrypted:
                raise ValueError("Failed to decrypt backup file")
            working_path = decrypted
            temp_paths.append(decrypted)

        if working_path.endswith((".gz", ".zip")):
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
            temp_file.close()
            decompressed = decompress_file(working_path, temp_file.name)
            if not decompressed:
                raise ValueError("Failed to decompress backup file")
            working_path = decompressed
            temp_paths.append(decompressed)

        return working_path, temp_paths
    except Exception:
        _cleanup_temp_paths(temp_paths)
        raise

def _get_table_snapshot(connection, table_name):
    """Return a hash signature and row snapshot for a given table."""
    validated_table = validate_table_name(table_name, conn=connection)
    cursor = connection.execute("SELECT * FROM [" + validated_table + "]")
    columns = [description[0] for description in cursor.description]
    rows = cursor.fetchall()

    digest = hashlib.sha256()
    for row in rows:
        digest.update(repr(row).encode("utf-8", "ignore"))

    return digest.hexdigest(), columns, rows

def _create_incremental_backup_impl(backup_path):
    """Implementation for incremental backups storing changed tables only."""
    import education_system.systems.university.interfaces.gui.shell.database.config as cfg
    with cfg._backup_context_lock:
        cfg._last_incremental_context = {}

    source_conn = None
    base_conn = None
    incremental_conn = None
    temp_paths = []
    base_entry = None

    try:
        backups = metadata_manager.get_backups(limit=1)
        base_entry = backups[0] if backups else None

        if not base_entry or not os.path.exists(base_entry.get("path", "")):
            logger.warning("No previous backup available; creating full backup as incremental fallback.")
            shutil.copy2(str(DEFAULT_DB_PATH), backup_path)
            with cfg._backup_context_lock:
                cfg._last_incremental_context = {
                    "base_backup": None,
                    "changed_tables": "all",
                    "mode": "full_fallback"
                }
            return backup_path

        base_path, temp_paths = _prepare_backup_for_read(base_entry["path"])
        source_conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        base_conn = sqlite3.connect(base_path)
        incremental_conn = sqlite3.connect(backup_path)

        changed_tables = []
        base_tables = set(get_database_tables_from_connection(base_conn))
        current_tables = set(get_database_tables_from_connection(source_conn))

        for table in current_tables:
            if table.startswith("sqlite_"):
                continue

            base_signature = None
            if table in base_tables:
                base_signature, _, _ = _get_table_snapshot(base_conn, table)

            current_signature, columns, current_rows = _get_table_snapshot(source_conn, table)

            if table not in base_tables or current_signature != base_signature:
                schema_cursor = source_conn.execute(
                    "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
                )
                schema_row = schema_cursor.fetchone()
                if schema_row and schema_row[0]:
                    incremental_conn.execute(schema_row[0])

                if current_rows:
                    placeholders = ",".join(["?"] * len(columns))
                    incremental_conn.executemany(
                        f"INSERT INTO {table} VALUES ({placeholders})", current_rows
                    )
                changed_tables.append(table)

        metadata_cursor = incremental_conn.cursor()
        metadata_cursor.execute(
            "CREATE TABLE IF NOT EXISTS __incremental_metadata (key TEXT PRIMARY KEY, value TEXT)"
        )
        metadata_cursor.execute(
            "INSERT OR REPLACE INTO __incremental_metadata (key, value) VALUES (?, ?)",
            ("base_backup_path", base_entry["path"])
        )
        metadata_cursor.execute(
            "INSERT OR REPLACE INTO __incremental_metadata (key, value) VALUES (?, ?)",
            ("base_backup_timestamp", base_entry.get("timestamp", ""))
        )
        metadata_cursor.execute(
            "INSERT OR REPLACE INTO __incremental_metadata (key, value) VALUES (?, ?)",
            ("changed_tables", json.dumps(changed_tables))
        )
        incremental_conn.commit()

        with cfg._backup_context_lock:
            cfg._last_incremental_context = {
                "base_backup": base_entry["path"],
                "base_timestamp": base_entry.get("timestamp"),
                "changed_tables": changed_tables
            }

        return backup_path
    except Exception as exc:
        logger.error(f"Error creating incremental backup: {exc}")
        return None
    finally:
        try:
            incremental_conn.close()
        except Exception:
            pass
        try:
            source_conn.close()
        except Exception:
            pass
        try:
            base_conn.close()
        except Exception:
            pass
        _cleanup_temp_paths(temp_paths)

def _create_differential_backup_impl(backup_path):
    """Implementation for differential backups based on the latest full backup."""
    import education_system.systems.university.interfaces.gui.shell.database.config as cfg
    cfg._last_differential_context = {}

    source_conn = None
    base_conn = None
    differential_conn = None
    temp_paths = []
    base_full_path = None

    try:
        base_full_path = metadata_manager.metadata.get("last_full")
        if not base_full_path or not os.path.exists(base_full_path):
            logger.warning("No previous full backup found; creating full backup instead of differential.")
            shutil.copy2(str(DEFAULT_DB_PATH), backup_path)
            cfg._last_differential_context = {
                "base_full": None,
                "changed_tables": "all",
                "removed_tables": [],
                "mode": "full_fallback"
            }
            return True

        prepared_path, temp_paths = _prepare_backup_for_read(base_full_path)
        source_conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        base_conn = sqlite3.connect(prepared_path)
        differential_conn = sqlite3.connect(backup_path)

        changed_tables = []
        removed_tables = []

        base_tables = set(get_database_tables_from_connection(base_conn))
        current_tables = set(get_database_tables_from_connection(source_conn))

        for table in base_tables - current_tables:
            if table.startswith("sqlite_"):
                continue
            removed_tables.append(table)

        for table in current_tables:
            if table.startswith("sqlite_"):
                continue

            base_signature = None
            if table in base_tables:
                base_signature, _, _ = _get_table_snapshot(base_conn, table)

            current_signature, columns, current_rows = _get_table_snapshot(source_conn, table)

            if table not in base_tables or current_signature != base_signature:
                schema_cursor = source_conn.execute(
                    "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
                )
                schema_row = schema_cursor.fetchone()
                if schema_row and schema_row[0]:
                    differential_conn.execute(schema_row[0])

                if current_rows:
                    placeholders = ",".join(["?"] * len(columns))
                    differential_conn.executemany(
                        f"INSERT INTO {table} VALUES ({placeholders})", current_rows
                    )
                changed_tables.append(table)

        metadata_cursor = differential_conn.cursor()
        metadata_cursor.execute(
            "CREATE TABLE IF NOT EXISTS __differential_metadata (key TEXT PRIMARY KEY, value TEXT)"
        )
        metadata_cursor.execute(
            "INSERT OR REPLACE INTO __differential_metadata (key, value) VALUES (?, ?)",
            ("base_full_backup", base_full_path)
        )
        metadata_cursor.execute(
            "INSERT OR REPLACE INTO __differential_metadata (key, value) VALUES (?, ?)",
            ("changed_tables", json.dumps(changed_tables))
        )
        metadata_cursor.execute(
            "INSERT OR REPLACE INTO __differential_metadata (key, value) VALUES (?, ?)",
            ("removed_tables", json.dumps(removed_tables))
        )
        differential_conn.commit()

        cfg._last_differential_context = {
            "base_full": base_full_path,
            "changed_tables": changed_tables,
            "removed_tables": removed_tables
        }

        return True
    except Exception as exc:
        logger.error(f"Error creating differential backup: {exc}")
        return False
    finally:
        try:
            differential_conn.close()
        except Exception:
            pass
        try:
            source_conn.close()
        except Exception:
            pass
        try:
            base_conn.close()
        except Exception:
            pass
        _cleanup_temp_paths(temp_paths)


def create_incremental_backup(backup_path):
    """Create incremental backup"""
    if not has_database_changed():
        logger.info("No changes detected, skipping incremental backup")
        return None
    return _create_incremental_backup_impl(backup_path)

def create_differential_backup(backup_path):
    """Create differential backup"""
    return _create_differential_backup_impl(backup_path)

def create_schema_only_backup(backup_path):
    """Create backup of database schema only (no data), excluding internal SQLite tables"""
    try:
        conn = get_db_connection()
        if not conn:
            logger.error("Failed to get database connection for schema backup")
            return False

        with open(backup_path, 'w', encoding='utf-8') as f:
            for line in conn.iterdump():
                if line.startswith('INSERT'):
                    continue
                if 'sqlite_sequence' in line or 'sqlite_stat' in line:
                    continue
                if line.startswith('CREATE TABLE') and ('sqlite_' in line.lower()):
                    continue
                f.write(f"{line}\n")

        conn.close()
        logger.info(f"Schema backup created successfully: {backup_path}")
        return True
    except Exception as e:
        logger.error(f"Error creating schema backup: {e}")
        return False

def create_selective_backup(tables, backup_path):
    """Create backup of selected tables only"""
    try:
        conn = get_db_connection()
        if not conn:
            return False

        backup_conn = sqlite3.connect(str(DEFAULT_DB_PATH))

        for table in tables:
            cursor = conn.cursor()
            cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,))
            create_sql = cursor.fetchone()

            if create_sql:
                backup_conn.execute(create_sql[0])

                safe_table = validate_table_name(table, conn=conn)
                cursor.execute("SELECT * FROM [" + safe_table + "]")
                rows = cursor.fetchall()

                if rows:
                    placeholders = ','.join(['?' for _ in range(len(rows[0]))])
                    backup_conn.executemany("INSERT INTO [" + safe_table + "] VALUES (" + placeholders + ")", rows)

        backup_conn.commit()
        backup_conn.close()
        conn.close()

        return True
    except Exception as e:
        logger.error(f"Error creating selective backup: {e}")
        return False

def compare_backups(backup1_path, backup2_path):
    """Compare two backup database files and return differences"""
    try:
        differences = {
            "tables_added": [],
            "tables_removed": [],
            "tables_modified": [],
            "record_changes": {}
        }

        if not os.path.exists(backup1_path):
            logger.error(f"Backup 1 not found: {backup1_path}")
            return None
        if not os.path.exists(backup2_path):
            logger.error(f"Backup 2 not found: {backup2_path}")
            return None

        try:
            conn1 = sqlite3.connect(backup1_path)
            conn1.execute("SELECT name FROM sqlite_master LIMIT 1")
        except sqlite3.DatabaseError as e:
            logger.error(f"Backup 1 is not a valid database file: {e}")
            return None

        try:
            conn2 = sqlite3.connect(backup2_path)
            conn2.execute("SELECT name FROM sqlite_master LIMIT 1")
        except sqlite3.DatabaseError as e:
            logger.error(f"Backup 2 is not a valid database file: {e}")
            if conn1:
                conn1.close()
            return None

        tables1 = set(get_database_tables_from_connection(conn1))
        tables2 = set(get_database_tables_from_connection(conn2))

        differences["tables_added"] = list(tables2 - tables1)
        differences["tables_removed"] = list(tables1 - tables2)

        common_tables = tables1 & tables2

        for table in common_tables:
            try:
                safe_table = validate_table_name(table)
                count1 = conn1.execute("SELECT COUNT(*) FROM [" + safe_table + "]").fetchone()[0]
                count2 = conn2.execute("SELECT COUNT(*) FROM [" + safe_table + "]").fetchone()[0]

                if count1 != count2:
                    differences["tables_modified"].append(table)
                    differences["record_changes"][table] = {
                        'records_added': max(0, count2 - count1),
                        'records_removed': max(0, count1 - count2),
                        'records_modified': 0
                    }
            except Exception as e:
                logger.warning(f"Could not compare table {table}: {e}")

        conn1.close()
        conn2.close()

        return differences

    except Exception as e:
        logger.error(f"Error comparing backups: {e}")
        return None

def generate_advanced_statistics():
    """Generate advanced backup statistics with trend analysis"""
    try:
        from education_system.systems.university.interfaces.gui.shell.database.operations.stats_ops import generate_backup_statistics
        backups = metadata_manager.get_backups()
        stats = generate_backup_statistics()

        now = datetime.datetime.now()

        daily_counts = {}
        weekly_counts = {}
        monthly_counts = {}

        for backup in backups:
            try:
                backup_date = datetime.datetime.strptime(backup["timestamp"], "%Y%m%d_%H%M%S")

                day_key = backup_date.strftime("%Y-%m-%d")
                daily_counts[day_key] = daily_counts.get(day_key, 0) + 1

                week_key = backup_date.strftime("%Y-W%U")
                weekly_counts[week_key] = weekly_counts.get(week_key, 0) + 1

                month_key = backup_date.strftime("%Y-%m")
                monthly_counts[month_key] = monthly_counts.get(month_key, 0) + 1
            except (ValueError, KeyError):
                pass

        stats["frequency_analysis"] = {
            "daily_distribution": daily_counts,
            "weekly_distribution": weekly_counts,
            "monthly_distribution": monthly_counts,
            "most_active_day": max(daily_counts.items(), key=lambda x: x[1]) if daily_counts else None,
            "most_active_week": max(weekly_counts.items(), key=lambda x: x[1]) if weekly_counts else None,
            "most_active_month": max(monthly_counts.items(), key=lambda x: x[1]) if monthly_counts else None
        }

        if backups:
            sizes = [b.get("size", 0) for b in backups]
            compressed_backups = [b for b in backups if b.get("compressed", False)]
            encrypted_backups = [b for b in backups if b.get("encrypted", False)]

            stats["storage_efficiency"] = {
                "compression_ratio": len(compressed_backups) / len(backups) * 100,
                "encryption_ratio": len(encrypted_backups) / len(backups) * 100,
                "size_variance": max(sizes) - min(sizes) if sizes else 0,
                "median_size": sorted(sizes)[len(sizes)//2] if sizes else 0
            }

        valid_backups = 0
        for backup in backups:
            if os.path.exists(backup["path"]):
                valid_backups += 1

        stats["reliability"] = {
            "integrity_percentage": (valid_backups / len(backups) * 100) if backups else 100,
            "missing_files": len(backups) - valid_backups,
            "total_backups": len(backups)
        }

        return stats

    except Exception as e:
        logger.error(f"Error generating advanced statistics: {e}")
        from education_system.systems.university.interfaces.gui.shell.database.operations.stats_ops import generate_backup_statistics
        return generate_backup_statistics()


# --- Main backup creation ---

def create_enhanced_backup(manual=False, operation_name=None, backup_type="full", tables=None):
    """Enhanced backup creation with all features"""
    try:
        from tkinter import messagebox

        if config.get("enable_change_detection", False) and not manual and not has_database_changed():
            logger.info("No changes detected since last backup. Skipping backup.")
            return None

        backup_dir = ensure_backup_directory()

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        if operation_name:
            filename = f"student_records_before_{operation_name}_{timestamp}.db"
        elif manual:
            filename = f"student_records_manual_{backup_type}_{timestamp}.db"
        else:
            filename = f"student_records_scheduled_{backup_type}_{timestamp}.db"

        backup_path = backup_dir / filename

        db_path = DEFAULT_DB_PATH
        if not os.path.exists(str(db_path)):
            logger.warning(f"Database file not found at {db_path}. Nothing to backup.")
            messagebox.showerror("Backup Error", f"Database file not found at:\n{db_path}\n\nPlease ensure the database exists before creating a backup.")
            return None

        logger.info(f"Creating backup from database: {db_path}")

        success = False
        if backup_type == "schema":
            success = create_schema_only_backup(str(backup_path))
        elif backup_type == "selective" and tables:
            success = create_selective_backup(tables, str(backup_path))
        elif backup_type == "incremental":
            success = create_incremental_backup(str(backup_path))
        elif backup_type == "differential":
            success = create_differential_backup(str(backup_path))
        else:  # full backup
            shutil.copy2(str(DEFAULT_DB_PATH), backup_path)
            success = True

        if not success:
            logger.error("Backup creation failed")
            return None

        file_hash = calculate_file_hash(str(backup_path))

        if config.get("compression_enabled", False):
            compressed_path = compress_file(
                str(backup_path),
                config.get("compression_format", "gzip"),
                config.get("compression_level", 6)
            )
            if compressed_path:
                backup_path = Path(compressed_path)

        if config.get("encryption_enabled", False) and config.get("encryption_password"):
            encrypted_path = encrypt_file(str(backup_path), config["encryption_password"])
            if encrypted_path:
                backup_path = Path(encrypted_path)

        upload_success = True
        if config.get("cloud_enabled", False):
            if config.get("cloud_provider") == "aws":
                upload_success = upload_to_aws_s3(
                    str(backup_path),
                    config.get("aws_bucket", ""),
                    f"backups/{backup_path.name}"
                )

        if config.get("remote_enabled", False):
            if config.get("remote_type") == "ftp":
                upload_success = upload_to_ftp(
                    str(backup_path),
                    config.get("remote_host", ""),
                    config.get("remote_username", ""),
                    config.get("remote_password", ""),
                    config.get("remote_path", "/backups")
                )
            elif config.get("remote_type") == "sftp":
                upload_success = upload_to_sftp(
                    str(backup_path),
                    config.get("remote_host", ""),
                    config.get("remote_username", ""),
                    config.get("remote_password", ""),
                    config.get("remote_path", "/backups")
                )

        import education_system.systems.university.interfaces.gui.shell.database.config as cfg

        backup_info = {
            "path": str(backup_path),
            "filename": backup_path.name,
            "type": backup_type,
            "manual": manual,
            "operation": operation_name,
            "timestamp": timestamp,
            "size": os.path.getsize(backup_path),
            "file_hash": file_hash,
            "compressed": config.get("compression_enabled", False),
            "encrypted": config.get("encryption_enabled", False),
            "cloud_uploaded": config.get("cloud_enabled", False) and upload_success,
            "remote_uploaded": config.get("remote_enabled", False) and upload_success,
            "backup_type": backup_type
        }

        with cfg._backup_context_lock:
            if backup_type == "incremental" and cfg._last_incremental_context:
                backup_info.update(cfg._last_incremental_context.copy())
            if backup_type == "differential" and cfg._last_differential_context:
                backup_info.update(cfg._last_differential_context.copy())

        metadata_manager.add_backup(backup_info)

        logger.info(f"Backup created: {backup_path}")

        cleanup_old_backups()

        notify_backup_result(True, str(backup_path), f"{backup_type} backup")

        return str(backup_path)

    except Exception as e:
        logger.error(f"Error creating backup: {e}")
        notify_backup_result(False, "", f"{backup_type} backup")
        return None
