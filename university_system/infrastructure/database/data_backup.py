# Standard library imports
import base64
import csv
import datetime
import gzip
import hashlib
import json
import logging
import os
import pickle
import shutil
import smtplib
import tempfile
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import xml.etree.ElementTree as ET
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from university_system.modules.shared.constants.paths import PROJECT_ROOT, DATA_DIR, BACKUP_DIR, DEFAULT_DB_PATH

# Third-party imports
import boto3
import croniter
import ftplib
import pandas as pd
import paramiko
import requests
import schedule
from botocore.exceptions import NoCredentialsError
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# Local application imports
from university_system.infrastructure.database.db import DatabaseManager, get_connection
# If you actually need the stdlib sqlite3, import it explicitly; avoid shadowing by any local module
from university_system.infrastructure.database.db import sqlite3
from university_system.utils.logging.log_config import configure_logging
from university_system.utils.logging.log_config import get_log_file
from university_system.infrastructure.email.template_utils import render_template
from university_system.modules.shared.utils.sql_safety import (
    validate_table_name,
    SQLIdentifierError,
)
from university_system.modules.shared.utils.i18n import get_text as _t, init_i18n

init_i18n()

# Import immutable audit logging for compliance
try:
    from university_system.infrastructure.security.audit_helpers import (
        safe_log_security_event,
        get_gui_context,
    )
    from university_system.infrastructure.security.immutable_audit_log import AuditAction
    IMMUTABLE_AUDIT_AVAILABLE = True
except ImportError:
    IMMUTABLE_AUDIT_AVAILABLE = False

# Enhanced default configuration
DEFAULT_CONFIG = {
    "backup_directory": str(BACKUP_DIR),
    "scheduled_backup_time": "02:00",
    "backup_frequency": "daily",
    "max_backups": 10,
    "auto_backup_enabled": True,
    # Security settings
    "encryption_enabled": False,
    "encryption_password": "",
    "secure_deletion": False,
    "verify_integrity": True,
    # Compression settings
    "compression_enabled": True,
    "compression_format": "gzip",  # gzip, zip
    "compression_level": 6,
    # Cloud storage settings
    "cloud_enabled": False,
    "cloud_provider": "aws",  # aws, google, azure
    "aws_bucket": "",
    "aws_access_key": "",
    "aws_secret_key": "",
    "aws_region": "us-east-1",
    # Remote storage settings
    "remote_enabled": False,
    "remote_type": "ftp",  # ftp, sftp
    "remote_host": "",
    "remote_username": "",
    "remote_password": "",
    "remote_path": "/backups",
    # Backup types
    "backup_type": "full",  # full, incremental, differential
    "enable_incremental": False,
    "enable_selective": False,
    "selective_tables": [],
    # Notifications
    "email_notifications": False,
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "email_username": "",
    "email_password": "",
    "notification_recipients": [],
    "slack_webhook": "",
    "discord_webhook": "",
    # Storage management
    "storage_quota_gb": 10,
    "enable_deduplication": False,
    # Advanced features
    "cron_schedule": "",
    "enable_change_detection": False,
    "parallel_backup": False,
    "max_threads": 4,
    "bandwidth_limit_mbps": 0,  # 0 = unlimited
    # Retention policies
    "retention_policy": {
        "daily_keep": 7,
        "weekly_keep": 4,
        "monthly_keep": 12,
        "yearly_keep": 5
    },
    # Validation
    "auto_validate": False,
    "validation_frequency": "weekly",
    # Export settings
    "export_formats": ["csv", "json", "xml"],
    # Templates
    "backup_templates": {}
}

# Global variables
backup_thread = None
stop_flag = False
config = DEFAULT_CONFIG.copy()
backup_history = []
last_full_backup = None
encryption_key = None

# Ensure log directory exists
 # directory creation centralized in log_config.get_log_dir()

# Configure logging
logger = configure_logging(name=__name__)
    
class BackupMetadata:
    """Class to handle backup metadata and tracking"""
    
    def __init__(self):
        self.metadata_file = str(DATA_DIR / "backup_metadata.json")
        self.metadata = self.load_metadata()
    
    def load_metadata(self):
        """Load backup metadata from file"""
        if os.path.exists(self.metadata_file):
            try:
                with open(self.metadata_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in metadata file: {e}")
                return {"backups": [], "last_full": None, "statistics": {}}
            except (OSError, IOError) as e:
                logger.error(f"Error reading metadata file: {e}")
                return {"backups": [], "last_full": None, "statistics": {}}
        return {"backups": [], "last_full": None, "statistics": {}}
    
    def save_metadata(self):
        """Save backup metadata to file"""
        try:
            with open(self.metadata_file, 'w') as f:
                json.dump(self.metadata, f, indent=4)
        except (OSError, IOError) as e:
            logger.error(f"Error writing metadata file: {e}")
        except (TypeError, ValueError) as e:
            logger.error(f"Error serializing metadata to JSON: {e}")
    
    def add_backup(self, backup_info):
        """Add backup information to metadata"""
        self.metadata["backups"].append(backup_info)
        if backup_info.get("type") == "full":
            self.metadata["last_full"] = backup_info["path"]
        self.save_metadata()
    
    def get_backups(self, backup_type=None, limit=None):
        """Get backup list with optional filtering"""
        backups = self.metadata["backups"]
        if backup_type:
            backups = [b for b in backups if b.get("backup_type") == backup_type]
        if limit:
            backups = backups[-limit:]
        return backups
    
    def update_statistics(self, stats):
        """Update backup statistics"""
        self.metadata["statistics"].update(stats)
        self.save_metadata()

metadata_manager = BackupMetadata()

# Security functions
def generate_encryption_key(password: str) -> bytes:
    """Generate encryption key from password"""
    password_bytes = password.encode()
    salt = b'backup_salt_12345'  # In production, use random salt
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password_bytes))
    return key

def encrypt_file(file_path: str, password: str) -> str:
    """Encrypt a file and return the encrypted file path"""
    try:
        key = generate_encryption_key(password)
        fernet = Fernet(key)

        encrypted_path = file_path + '.encrypted'

        with open(file_path, 'rb') as original_file:
            original_data = original_file.read()

        encrypted_data = fernet.encrypt(original_data)

        with open(encrypted_path, 'wb') as encrypted_file:
            encrypted_file.write(encrypted_data)

        # Remove original file if secure deletion is enabled
        if config["secure_deletion"]:
            secure_delete_file(file_path)
        else:
            os.remove(file_path)

        return encrypted_path
    except (OSError, IOError) as e:
        logger.error(f"File I/O error during encryption: {e}")
        return None
    except (ValueError, TypeError) as e:
        logger.error(f"Encryption error (invalid key or data): {e}")
        return None

def decrypt_file(encrypted_path: str, password: str, output_path: str = None) -> str:
    """Decrypt a file and return the decrypted file path"""
    from cryptography.fernet import InvalidToken
    try:
        key = generate_encryption_key(password)
        fernet = Fernet(key)

        if output_path is None:
            output_path = encrypted_path.replace('.encrypted', '')

        with open(encrypted_path, 'rb') as encrypted_file:
            encrypted_data = encrypted_file.read()

        decrypted_data = fernet.decrypt(encrypted_data)

        with open(output_path, 'wb') as decrypted_file:
            decrypted_file.write(decrypted_data)

        return output_path
    except (OSError, IOError) as e:
        logger.error(f"File I/O error during decryption: {e}")
        return None
    except InvalidToken as e:
        logger.error(f"Decryption failed - invalid password or corrupted data: {e}")
        return None
    except (ValueError, TypeError) as e:
        logger.error(f"Decryption error (invalid key format): {e}")
        return None

def calculate_file_hash(file_path: str) -> str:
    """Calculate SHA-256 hash of a file"""
    hash_sha256 = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    except (OSError, IOError) as e:
        logger.error(f"Error reading file for hash calculation: {e}")
        return None

def verify_backup_integrity(backup_path: str, expected_hash: str = None) -> bool:
    """Verify backup file integrity"""
    try:
        current_hash = calculate_file_hash(backup_path)
        if expected_hash:
            return current_hash == expected_hash
        return current_hash is not None
    except (OSError, IOError) as e:
        logger.error(f"Error reading backup file for integrity check: {e}")
        return False

def secure_delete_file(file_path: str, passes: int = 3):
    """Securely delete a file by overwriting it multiple times"""
    try:
        if not os.path.exists(file_path):
            return

        file_size = os.path.getsize(file_path)

        with open(file_path, "r+b") as file:
            for _ in range(passes):
                file.seek(0)
                file.write(os.urandom(file_size))
                file.flush()
                os.fsync(file.fileno())

        os.remove(file_path)
        logger.info(f"Securely deleted file: {file_path}")
    except (OSError, IOError) as e:
        logger.error(f"Error securely deleting file: {e}")
    except PermissionError as e:
        logger.error(f"Permission denied while securely deleting file: {e}")

# Compression functions
def compress_file(file_path: str, compression_format: str = "gzip", level: int = 6) -> str:
    """Compress a file using specified format"""
    try:
        if compression_format == "gzip":
            compressed_path = file_path + ".gz"
            with open(file_path, 'rb') as f_in:
                with gzip.open(compressed_path, 'wb', compresslevel=level) as f_out:
                    shutil.copyfileobj(f_in, f_out)
        
        elif compression_format == "zip":
            compressed_path = file_path + ".zip"
            with zipfile.ZipFile(compressed_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=level) as zipf:
                zipf.write(file_path, os.path.basename(file_path))
        
        else:
            from university_system.infrastructure.exceptions import InvalidInputError
            raise InvalidInputError(
                f"Unsupported compression format: {compression_format}",
                code="INVALID_COMPRESSION_FORMAT",
                details={'format': compression_format, 'supported': ['gzip', 'bz2', 'lzma', 'zip']}
            )

        # Remove original file
        os.remove(file_path)

        return compressed_path
    except (OSError, IOError) as e:
        logger.error(f"File I/O error during compression: {e}")
        return None
    except (zipfile.BadZipFile, gzip.BadGzipFile) as e:
        logger.error(f"Compression format error: {e}")
        return None

def decompress_file(compressed_path: str, output_path: str = None) -> str:
    """Decompress a file"""
    try:
        if compressed_path.endswith('.gz'):
            if output_path is None:
                output_path = compressed_path[:-3]  # Remove .gz extension

            with gzip.open(compressed_path, 'rb') as f_in:
                with open(output_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)

        elif compressed_path.endswith('.zip'):
            if output_path is None:
                output_path = os.path.splitext(compressed_path)[0]

            with zipfile.ZipFile(compressed_path, 'r') as zipf:
                zipf.extractall(os.path.dirname(output_path))
                # Assume single file in zip
                extracted_files = zipf.namelist()
                if extracted_files:
                    extracted_path = os.path.join(os.path.dirname(output_path), extracted_files[0])
                    if extracted_path != output_path:
                        shutil.move(extracted_path, output_path)

        return output_path
    except (OSError, IOError) as e:
        logger.error(f"File I/O error during decompression: {e}")
        return None
    except zipfile.BadZipFile as e:
        logger.error(f"Invalid ZIP file: {e}")
        return None
    except gzip.BadGzipFile as e:
        logger.error(f"Invalid GZIP file: {e}")
        return None

# Cloud storage functions
def upload_to_aws_s3(file_path: str, bucket: str, key: str) -> bool:
    """Upload file to AWS S3"""
    from botocore.exceptions import ClientError, ParamValidationError
    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=config["aws_access_key"],
            aws_secret_access_key=config["aws_secret_key"],
            region_name=config["aws_region"]
        )

        s3_client.upload_file(file_path, bucket, key)
        logger.info(f"Uploaded {file_path} to S3: s3://{bucket}/{key}")
        return True
    except NoCredentialsError:
        logger.error("AWS credentials not found")
        return False
    except ClientError as e:
        logger.error(f"AWS S3 client error: {e}")
        return False
    except ParamValidationError as e:
        logger.error(f"Invalid AWS S3 parameters: {e}")
        return False
    except (OSError, IOError) as e:
        logger.error(f"Error reading file for S3 upload: {e}")
        return False

def download_from_aws_s3(bucket: str, key: str, download_path: str) -> bool:
    """Download file from AWS S3"""
    from botocore.exceptions import ClientError, ParamValidationError
    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=config["aws_access_key"],
            aws_secret_access_key=config["aws_secret_key"],
            region_name=config["aws_region"]
        )

        s3_client.download_file(bucket, key, download_path)
        logger.info(f"Downloaded s3://{bucket}/{key} to {download_path}")
        return True
    except NoCredentialsError:
        logger.error("AWS credentials not found for download")
        return False
    except ClientError as e:
        logger.error(f"AWS S3 client error during download: {e}")
        return False
    except ParamValidationError as e:
        logger.error(f"Invalid AWS S3 parameters: {e}")
        return False
    except (OSError, IOError) as e:
        logger.error(f"Error writing downloaded file: {e}")
        return False

# Remote storage functions
def upload_to_ftp(file_path: str, host: str, username: str, password: str, remote_path: str) -> bool:
    """Upload file to FTP server"""
    try:
        with ftplib.FTP(host) as ftp:
            ftp.login(username, password)
            ftp.cwd(remote_path)

            with open(file_path, 'rb') as file:
                ftp.storbinary(f'STOR {os.path.basename(file_path)}', file)

        logger.info(f"Uploaded {file_path} to FTP: {host}{remote_path}")
        return True
    except ftplib.all_errors as e:
        logger.error(f"FTP error during upload: {e}")
        return False
    except (OSError, IOError) as e:
        logger.error(f"Error reading file for FTP upload: {e}")
        return False

def upload_to_sftp(file_path: str, host: str, username: str, password: str, remote_path: str) -> bool:
    """Upload file to SFTP server"""
    try:
        with paramiko.SSHClient() as ssh:
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(host, username=username, password=password)

            with ssh.open_sftp() as sftp:
                remote_file_path = f"{remote_path}/{os.path.basename(file_path)}"
                sftp.put(file_path, remote_file_path)

        logger.info(f"Uploaded {file_path} to SFTP: {host}{remote_path}")
        return True
    except paramiko.AuthenticationException as e:
        logger.error(f"SFTP authentication failed: {e}")
        return False
    except paramiko.SSHException as e:
        logger.error(f"SSH/SFTP connection error: {e}")
        return False
    except (OSError, IOError) as e:
        logger.error(f"Error reading file for SFTP upload: {e}")
        return False

# Notification functions
def send_email_notification(subject: str, message: str, recipients: list):
    """Send email notification"""
    try:
        if not config["email_notifications"] or not recipients:
            return

        from university_system.infrastructure.email.smtp import send_email_via_smtp
        from datetime import datetime

        # Send to first recipient with others as CC
        recipient_email = recipients[0]
        cc = recipients[1:] if len(recipients) > 1 else None

        current_time = datetime.now().isoformat()
        success = send_email_via_smtp(
            recipient_email=recipient_email,
            subject=subject,
            body=message,
            cc=cc,
            bcc=None,
            attachments=None,
            current_time=current_time
        )

        if success:
            logger.info(f"Email notification sent to {recipients}")
        else:
            logger.error(f"Failed to send email notification to {recipients}")
    except smtplib.SMTPException as e:
        logger.error(f"SMTP error sending email notification: {e}")
    except (OSError, IOError) as e:
        logger.error(f"Network error sending email notification: {e}")

def send_slack_notification(message: str):
    """Send Slack notification"""
    try:
        if not config["slack_webhook"]:
            return

        payload = {"text": message}
        response = requests.post(config["slack_webhook"], json=payload, timeout=30)

        if response.status_code == 200:
            logger.info("Slack notification sent successfully")
        else:
            logger.error(f"Error sending Slack notification: {response.status_code}")
    except requests.exceptions.Timeout as e:
        logger.error(f"Slack notification timed out: {e}")
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Connection error sending Slack notification: {e}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error sending Slack notification: {e}")

def send_discord_notification(message: str):
    """Send Discord notification"""
    try:
        if not config["discord_webhook"]:
            return

        payload = {"content": message}
        response = requests.post(config["discord_webhook"], json=payload, timeout=30)

        if response.status_code == 204:
            logger.info("Discord notification sent successfully")
        else:
            logger.error(f"Error sending Discord notification: {response.status_code}")
    except requests.exceptions.Timeout as e:
        logger.error(f"Discord notification timed out: {e}")
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Connection error sending Discord notification: {e}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error sending Discord notification: {e}")

def notify_backup_result(success: bool, backup_path: str, operation: str):
    """Send notifications about backup results"""
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    if success:
        subject, message = render_template('backup_success', {
            'operation': operation,
            'backup_path': backup_path,
            'timestamp': timestamp
        })
        slack_msg = f"✅ Backup Success: {operation}\nFile: {backup_path}"
    else:
        subject, message = render_template('backup_failed', {
            'operation': operation,
            'timestamp': timestamp
        })
        slack_msg = f"❌ Backup Failed: {operation}\nCheck logs for details."

    send_email_notification(subject, message, config["notification_recipients"])
    send_slack_notification(slack_msg)
    send_discord_notification(slack_msg)

# Advanced backup functions
def get_database_tables() -> list:
    """Get list of all tables in the database"""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]
            return tables
    except sqlite3.Error as e:
        logger.error(f"Database error getting tables: {e}")
        return []
    except (OSError, IOError) as e:
        logger.error(f"I/O error accessing database: {e}")
        return []

def validate_table_name(table_name: str, connection=None) -> bool:
    """
    Validate that a table name exists in the database to prevent SQL injection.

    Args:
        table_name: The table name to validate
        connection: Optional database connection to use for validation

    Returns:
        bool: True if table name is valid, False otherwise

    Raises:
        ValueError: If table name is invalid
    """
    if connection:
        cursor = connection.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        valid_tables = [row[0] for row in cursor.fetchall()]
    else:
        valid_tables = get_database_tables()

    if table_name not in valid_tables:
        raise ValueError(f"Invalid table name: {table_name}. Not found in database.")

    return True

def create_selective_backup(tables: list, backup_path: str) -> bool:
    """Create backup of selected tables only"""
    source_conn = None
    backup_conn = None
    try:
        source_conn = get_connection()
        backup_conn = get_connection(db_path=backup_path, row_factory=False)

        for table in tables:
            # Validate table name to prevent SQL injection
            validate_table_name(table, source_conn)

            # Copy table structure - using parameterized query
            cursor = source_conn.cursor()
            cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?;", (table,))
            create_sql = cursor.fetchone()

            if create_sql:
                backup_conn.execute(create_sql[0])

                # Copy table data - table name validated above via validate_table_name
                # Use bracket quoting for additional safety
                validated_table = validate_table_name(table, conn=source_conn)
                cursor.execute(f"SELECT * FROM [{validated_table}]")
                rows = cursor.fetchall()

                if rows:
                    placeholders = ','.join(['?' for _ in range(len(rows[0]))])
                    backup_conn.executemany(f"INSERT INTO [{validated_table}] VALUES ({placeholders})", rows)

        backup_conn.commit()
        return True
    except ValueError as ve:
        logger.error(f"Invalid table name in selective backup: {ve}")
        return False
    except sqlite3.Error as e:
        logger.error(f"Database error creating selective backup: {e}")
        return False
    except (OSError, IOError) as e:
        logger.error(f"I/O error creating selective backup: {e}")
        return False
    finally:
        # Ensure connections are always closed
        if backup_conn:
            try:
                backup_conn.close()
            except sqlite3.Error as e:
                logger.warning(f"Error closing backup connection: {e}")
        if source_conn:
            try:
                source_conn.close()
            except sqlite3.Error as e:
                logger.warning(f"Error closing source connection: {e}")

def create_schema_only_backup(backup_path: str) -> bool:
    """Create backup of database schema only (no data)"""
    source_conn = None
    backup_conn = None
    try:
        source_conn = get_connection()
        backup_conn = get_connection(db_path=backup_path, row_factory=False)

        cursor = source_conn.cursor()
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table';")

        for row in cursor.fetchall():
            if row[0]:
                backup_conn.execute(row[0])

        backup_conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"Database error creating schema backup: {e}")
        return False
    except (OSError, IOError) as e:
        logger.error(f"I/O error creating schema backup: {e}")
        return False
    finally:
        # Ensure connections are always closed
        if backup_conn:
            try:
                backup_conn.close()
            except sqlite3.Error as e:
                logger.warning(f"Error closing backup connection: {e}")
        if source_conn:
            try:
                source_conn.close()
            except sqlite3.Error as e:
                logger.warning(f"Error closing source connection: {e}")

def has_database_changed() -> bool:
    """Check if database has changed since last backup"""
    try:
        if not os.path.exists(str(DEFAULT_DB_PATH)):
            return False

        current_hash = calculate_file_hash(str(DEFAULT_DB_PATH))

        # Check if we have a previous hash stored
        last_backup = metadata_manager.get_backups(limit=1)
        if last_backup and "file_hash" in last_backup[0]:
            return current_hash != last_backup[0]["file_hash"]

        return True  # If no previous backup, assume changed
    except (OSError, IOError) as e:
        logger.error(f"Error accessing database file for change detection: {e}")
        return True
    except (KeyError, IndexError, TypeError) as e:
        logger.error(f"Error reading backup metadata: {e}")
        return True

def create_incremental_backup(backup_path: str) -> bool:
    """Create incremental backup (changes since last full backup)"""
    try:
        # This is a simplified incremental backup
        # In a real implementation, you'd track changes at the record level

        last_full = metadata_manager.metadata.get("last_full")
        if not last_full or not os.path.exists(last_full):
            logger.warning("No previous full backup found. Creating full backup instead.")
            return False

        # For SQLite, we'll create a backup and compare sizes
        # This is a basic implementation - more sophisticated tracking would be needed
        from university_system.infrastructure.database.db import get_connection
        # Get the database path from the connection
        with get_connection() as conn:
            if hasattr(conn, 'execute'):
                db_path = conn.execute("PRAGMA database_list").fetchone()[2]
            else:
                db_path = str(DEFAULT_DB_PATH)

        shutil.copy2(db_path, backup_path)
        return True

    except sqlite3.Error as e:
        logger.error(f"Database error creating incremental backup: {e}")
        return False
    except (OSError, IOError) as e:
        logger.error(f"I/O error creating incremental backup: {e}")
        return False
    except shutil.Error as e:
        logger.error(f"File copy error creating incremental backup: {e}")
        return False

# Export functions
def export_to_csv(backup_path: str, output_dir: str) -> bool:
    """Export backup to CSV files"""
    conn = None
    try:
        conn = get_connection(db_path=backup_path, row_factory=False)
        tables = get_database_tables()

        os.makedirs(output_dir, exist_ok=True)

        for table in tables:
            # Validate table name to prevent SQL injection
            validated_table = validate_table_name(table, conn)
            df = pd.read_sql_query(f"SELECT * FROM [{validated_table}]", conn)
            csv_path = os.path.join(output_dir, f"{table}.csv")
            df.to_csv(csv_path, index=False)

        logger.info(f"Exported backup to CSV files in {output_dir}")
        return True
    except ValueError as ve:
        logger.error(f"Invalid table name in CSV export: {ve}")
        return False
    except sqlite3.Error as e:
        logger.error(f"Database error exporting to CSV: {e}")
        return False
    except (OSError, IOError) as e:
        logger.error(f"I/O error exporting to CSV: {e}")
        return False
    except pd.errors.DatabaseError as e:
        logger.error(f"Pandas database error exporting to CSV: {e}")
        return False
    finally:
        if conn:
            try:
                conn.close()
            except sqlite3.Error as e:
                logger.warning(f"Error closing connection: {e}")

def export_to_json(backup_path: str, output_file: str) -> bool:
    """Export backup to JSON file"""
    conn = None
    try:
        conn = get_connection(db_path=backup_path, row_factory=False)
        data = {}

        tables = get_database_tables()
        for table in tables:
            # Validate table name to prevent SQL injection
            validated_table = validate_table_name(table, conn)

            cursor = conn.cursor()
            # Table name validated above - safe to use in query with bracket quoting
            cursor.execute(f"SELECT * FROM [{validated_table}]")
            columns = [description[0] for description in cursor.description]
            rows = cursor.fetchall()

            data[table] = [dict(zip(columns, row)) for row in rows]

        with open(output_file, 'w') as f:
            json.dump(data, f, indent=4, default=str)

        logger.info(f"Exported backup to JSON: {output_file}")
        return True
    except ValueError as ve:
        logger.error(f"Invalid table name in JSON export: {ve}")
        return False
    except sqlite3.Error as e:
        logger.error(f"Database error exporting to JSON: {e}")
        return False
    except (OSError, IOError) as e:
        logger.error(f"I/O error exporting to JSON: {e}")
        return False
    except (TypeError, json.JSONDecodeError) as e:
        logger.error(f"JSON serialization error: {e}")
        return False
    finally:
        if conn:
            try:
                conn.close()
            except sqlite3.Error as e:
                logger.warning(f"Error closing connection: {e}")

def export_to_xml(backup_path: str, output_file: str) -> bool:
    """Export backup to XML file"""
    conn = None
    try:
        conn = get_connection(db_path=backup_path, row_factory=False)
        root = ET.Element("database")

        tables = get_database_tables()
        for table_name in tables:
            # Validate table name to prevent SQL injection
            validated_table = validate_table_name(table_name, conn)

            table_elem = ET.SubElement(root, "table", name=table_name)

            cursor = conn.cursor()
            # Table name validated above - safe to use in query with bracket quoting
            cursor.execute(f"SELECT * FROM [{validated_table}]")
            columns = [description[0] for description in cursor.description]
            rows = cursor.fetchall()

            for row in rows:
                row_elem = ET.SubElement(table_elem, "row")
                for col, val in zip(columns, row):
                    col_elem = ET.SubElement(row_elem, col)
                    col_elem.text = str(val) if val is not None else ""

        tree = ET.ElementTree(root)
        tree.write(output_file, encoding='utf-8', xml_declaration=True)

        logger.info(f"Exported backup to XML: {output_file}")
        return True
    except ValueError as ve:
        logger.error(f"Invalid table name in XML export: {ve}")
        return False
    except sqlite3.Error as e:
        logger.error(f"Database error exporting to XML: {e}")
        return False
    except (OSError, IOError) as e:
        logger.error(f"I/O error exporting to XML: {e}")
        return False
    except ET.ParseError as e:
        logger.error(f"XML parsing error: {e}")
        return False
    finally:
        if conn:
            try:
                conn.close()
            except sqlite3.Error as e:
                logger.warning(f"Error closing connection: {e}")

# Progress tracking
class ProgressTracker:
    def __init__(self, total_size: int):
        self.total_size = total_size
        self.current_size = 0
        self.start_time = time.time()
    
    def update(self, bytes_transferred: int):
        self.current_size += bytes_transferred
        elapsed = time.time() - self.start_time
        if elapsed > 0:
            speed = self.current_size / elapsed
            percentage = (self.current_size / self.total_size) * 100
            eta = (self.total_size - self.current_size) / speed if speed > 0 else 0
            
            print(f"\rProgress: {percentage:.1f}% ({self.current_size}/{self.total_size} bytes) "
                  f"Speed: {speed/1024/1024:.1f} MB/s ETA: {eta:.0f}s", end="")

# Enhanced backup creation
def create_enhanced_backup(manual=False, operation_name=None, backup_type="full", tables=None):
    """Enhanced backup creation with all new features"""
    try:
        # Check if database has changed (if change detection is enabled)
        if config["enable_change_detection"] and not manual and not has_database_changed():
            logger.info("No changes detected since last backup. Skipping backup.")
            return None
        
        # Ensure backup directory exists
        backup_dir = ensure_backup_directory()
        
        # Generate backup filename
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if operation_name:
            filename = f"student_records_before_{operation_name}_{timestamp}.db"
        elif manual:
            filename = f"student_records_manual_{backup_type}_{timestamp}.db"
        else:
            filename = f"student_records_scheduled_{backup_type}_{timestamp}.db"
        
        backup_path = backup_dir / filename
        
        # Check if source database exists
        if not os.path.exists(str(DEFAULT_DB_PATH)):
            logger.warning("Database file not found. Nothing to backup.")
            return None

        # Progress tracking
        if config.get("show_progress", True):
            db_size = os.path.getsize(str(DEFAULT_DB_PATH))
            progress = ProgressTracker(db_size)
        
        # Create backup based on type
        success = False
        if backup_type == "schema":
            success = create_schema_only_backup(str(backup_path))
        elif backup_type == "selective" and tables:
            success = create_selective_backup(tables, str(backup_path))
        elif backup_type == "incremental":
            success = create_incremental_backup(str(backup_path))
        else:  # full backup
            from university_system.infrastructure.database.db import get_connection
            # Get the database path from the connection
            with get_connection() as conn:
                if hasattr(conn, 'execute'):
                    db_path = conn.execute("PRAGMA database_list").fetchone()[2]
                else:
                    db_path = str(DEFAULT_DB_PATH)

            shutil.copy2(db_path, backup_path)
            success = True
        
        if not success:
            logger.error("Backup creation failed")
            return None
        
        # Calculate file hash for integrity
        file_hash = calculate_file_hash(str(backup_path))
        
        # Compress if enabled
        if config["compression_enabled"]:
            compressed_path = compress_file(
                str(backup_path), 
                config["compression_format"], 
                config["compression_level"]
            )
            if compressed_path:
                backup_path = Path(compressed_path)
        
        # Encrypt if enabled
        if config["encryption_enabled"] and config["encryption_password"]:
            encrypted_path = encrypt_file(str(backup_path), config["encryption_password"])
            if encrypted_path:
                backup_path = Path(encrypted_path)
        
        # Upload to cloud/remote if enabled
        upload_success = True
        if config["cloud_enabled"]:
            if config["cloud_provider"] == "aws":
                upload_success = upload_to_aws_s3(
                    str(backup_path),
                    config["aws_bucket"],
                    f"backups/{backup_path.name}"
                )
        
        if config["remote_enabled"]:
            if config["remote_type"] == "ftp":
                upload_success = upload_to_ftp(
                    str(backup_path),
                    config["remote_host"],
                    config["remote_username"],
                    config["remote_password"],
                    config["remote_path"]
                )
            elif config["remote_type"] == "sftp":
                upload_success = upload_to_sftp(
                    str(backup_path),
                    config["remote_host"],
                    config["remote_username"],
                    config["remote_password"],
                    config["remote_path"]
                )
        
        # Record backup metadata
        backup_info = {
            "path": str(backup_path),
            "filename": backup_path.name,
            "type": backup_type,
            "manual": manual,
            "operation": operation_name,
            "timestamp": timestamp,
            "size": os.path.getsize(backup_path),
            "file_hash": file_hash,
            "compressed": config["compression_enabled"],
            "encrypted": config["encryption_enabled"],
            "cloud_uploaded": config["cloud_enabled"] and upload_success,
            "remote_uploaded": config["remote_enabled"] and upload_success,
            "backup_type": backup_type
        }
        
        metadata_manager.add_backup(backup_info)

        logger.info(f"Backup created: {backup_path}")

        # Immutable audit log for backup creation
        if IMMUTABLE_AUDIT_AVAILABLE:
            user_id, _ = get_gui_context()
            safe_log_security_event(
                action=AuditAction.BACKUP_CREATE,
                user_id=user_id or 'system',
                resource_type='database_backup',
                resource_id=backup_path.name,
                details={
                    'backup_type': backup_type,
                    'manual': manual,
                    'operation': operation_name,
                    'size_bytes': backup_info['size'],
                    'compressed': backup_info['compressed'],
                    'encrypted': backup_info['encrypted'],
                    'cloud_uploaded': backup_info.get('cloud_uploaded', False),
                }
            )

        # Clean up old backups
        cleanup_old_backups()
        
        # Send notifications
        notify_backup_result(True, str(backup_path), f"{backup_type} backup")

        return str(backup_path)

    except sqlite3.Error as e:
        logger.error(f"Database error creating backup: {e}")
        notify_backup_result(False, "", f"{backup_type} backup")
        return None
    except (OSError, IOError) as e:
        logger.error(f"I/O error creating backup: {e}")
        notify_backup_result(False, "", f"{backup_type} backup")
        return None
    except shutil.Error as e:
        logger.error(f"File copy error creating backup: {e}")
        notify_backup_result(False, "", f"{backup_type} backup")
        return None
    except (KeyError, TypeError) as e:
        logger.error(f"Configuration error creating backup: {e}")
        notify_backup_result(False, "", f"{backup_type} backup")
        return None

# Load and save configuration (enhanced)
def load_config():
    """Load backup configuration from file"""
    global config

    config_path = DATA_DIR / "backup_config.json"
    if config_path.exists():
        try:
            with open(config_path, "r") as f:
                loaded_config = json.load(f)
                # Update default config with loaded values
                config.update(loaded_config)
            logger.info("Backup configuration loaded successfully")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in backup configuration: {e}")
            logger.info("Using default configuration")
        except (OSError, IOError) as e:
            logger.error(f"Error reading backup configuration file: {e}")
            logger.info("Using default configuration")
    else:
        logger.info("No configuration file found. Using default configuration.")
        save_config()  # Create default config file

def save_config():
    """Save current backup configuration to file"""
    try:
        config_path = DATA_DIR / "backup_config.json"
        with open(config_path, "w") as f:
            json.dump(config, f, indent=4)
        logger.info("Backup configuration saved successfully")
    except (OSError, IOError) as e:
        logger.error(f"Error writing backup configuration file: {e}")
    except (TypeError, ValueError) as e:
        logger.error(f"Error serializing backup configuration: {e}")

def ensure_backup_directory():
    """Ensure the backup directory exists"""
    backup_dir = Path(config["backup_directory"])
    if not backup_dir.exists():
        backup_dir.mkdir(parents=True)
        logger.info(f"Created backup directory: {backup_dir}")
    return backup_dir

# Enhanced cleanup with retention policies
def delete_backup(backup_path: str) -> bool:
    """
    Delete a specific backup file and remove it from metadata.

    Args:
        backup_path: Path to the backup file to delete

    Returns:
        bool: True if deletion was successful, False otherwise
    """
    try:
        # Remove the file
        if os.path.exists(backup_path):
            if config["secure_deletion"]:
                secure_delete_file(backup_path)
            else:
                os.remove(backup_path)
            logger.info(f"Deleted backup: {backup_path}")
        else:
            logger.warning(f"Backup file not found: {backup_path}")

        # Remove from metadata
        all_backups = metadata_manager.get_backups()
        updated_backups = [b for b in all_backups if b["path"] != backup_path]

        if len(updated_backups) < len(all_backups):
            metadata_manager.metadata["backups"] = updated_backups
            metadata_manager.save_metadata()
            logger.info(f"Removed backup from metadata: {backup_path}")
            return True
        else:
            logger.warning(f"Backup not found in metadata: {backup_path}")
            return False

    except (OSError, IOError) as e:
        logger.error(f"I/O error deleting backup {backup_path}: {e}")
        return False
    except PermissionError as e:
        logger.error(f"Permission denied deleting backup {backup_path}: {e}")
        return False

def cleanup_old_backups():
    """Remove old backups based on retention policy"""
    try:
        backup_dir = Path(config["backup_directory"])
        retention = config["retention_policy"]

        # Get all backup files grouped by type
        all_backups = metadata_manager.get_backups()
        
        now = datetime.datetime.now()
        
        # Group backups by age
        daily_backups = []
        weekly_backups = []
        monthly_backups = []
        yearly_backups = []
        
        for backup in all_backups:
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
        
        # Apply retention policy
        backups_to_keep = []
        
        # Keep recent daily backups
        daily_backups.sort(key=lambda x: x["timestamp"], reverse=True)
        backups_to_keep.extend(daily_backups[:retention["daily_keep"]])
        
        # Keep weekly backups (one per week)
        weekly_by_week = {}
        for backup in weekly_backups:
            backup_date = datetime.datetime.strptime(backup["timestamp"], "%Y%m%d_%H%M%S")
            week_key = backup_date.strftime("%Y-W%U")
            if week_key not in weekly_by_week:
                weekly_by_week[week_key] = backup
        
        weekly_kept = list(weekly_by_week.values())
        weekly_kept.sort(key=lambda x: x["timestamp"], reverse=True)
        backups_to_keep.extend(weekly_kept[:retention["weekly_keep"]])
        
        # Similar logic for monthly and yearly
        # (Implementation simplified for brevity)
        
        # Remove backups not in keep list
        kept_paths = {backup["path"] for backup in backups_to_keep}
        
        for backup in all_backups:
            if backup["path"] not in kept_paths:
                try:
                    if os.path.exists(backup["path"]):
                        if config["secure_deletion"]:
                            secure_delete_file(backup["path"])
                        else:
                            os.remove(backup["path"])
                        logger.info(f"Removed old backup: {backup['path']}")
                except (OSError, IOError, PermissionError) as e:
                    logger.error(f"Error removing backup {backup['path']}: {e}")

        # Update metadata
        metadata_manager.metadata["backups"] = backups_to_keep
        metadata_manager.save_metadata()

    except (KeyError, TypeError) as e:
        logger.error(f"Configuration error cleaning up old backups: {e}")
    except (ValueError, AttributeError) as e:
        logger.error(f"Data error cleaning up old backups: {e}")

# Enhanced backup listing
def list_available_backups(filter_type=None, search_term=None):
    """List all available backup files with enhanced filtering"""
    try:
        backups = metadata_manager.get_backups()
        
        # Apply filters
        if filter_type:
            backups = [b for b in backups if b.get("backup_type") == filter_type]
        
        if search_term:
            backups = [b for b in backups if search_term.lower() in b["filename"].lower()]
        
        # Sort by timestamp (newest first)
        backups.sort(key=lambda x: x["timestamp"], reverse=True)
        
        # Add calculated fields
        for i, backup in enumerate(backups):
            backup["id"] = i + 1
            
            # Format size
            size_bytes = backup.get("size", 0)
            if size_bytes > 1024*1024*1024:
                backup["size_formatted"] = f"{size_bytes/(1024*1024*1024):.2f} GB"
            elif size_bytes > 1024*1024:
                backup["size_formatted"] = f"{size_bytes/(1024*1024):.2f} MB"
            else:
                backup["size_formatted"] = f"{size_bytes/1024:.2f} KB"
            
            # Format date
            try:
                backup_date = datetime.datetime.strptime(backup["timestamp"], "%Y%m%d_%H%M%S")
                backup["date_formatted"] = backup_date.strftime("%Y-%m-%d %H:%M:%S")
            except (ValueError, KeyError, TypeError) as e:
                logger.debug(f"Failed to parse backup timestamp: {e}")
                backup["date_formatted"] = "Unknown"
        
        return backups

    except (KeyError, TypeError, AttributeError) as e:
        logger.error(f"Error processing backup metadata: {e}")
        return []
    except (ValueError) as e:
        logger.error(f"Error parsing backup data: {e}")
        return []

# Enhanced restore functionality
def restore_from_backup(backup_path, target_tables=None, point_in_time=None):
    """Enhanced restore with partial and point-in-time options"""
    try:
        # Verify the backup file exists
        if not os.path.exists(backup_path):
            logger.error(f"Backup file not found: {backup_path}")
            return False
        
        # Create a backup of the current database
        current_backup = create_enhanced_backup(manual=True, operation_name="restore")
        
        # Prepare the restore file
        restore_file = backup_path
        temp_files = []
        
        # Decrypt if needed
        if backup_path.endswith('.encrypted'):
            if not config["encryption_password"]:
                logger.error("Encryption password required for encrypted backup")
                return False
            
            temp_decrypt = tempfile.mktemp(suffix='.db')
            restore_file = decrypt_file(backup_path, config["encryption_password"], temp_decrypt)
            temp_files.append(temp_decrypt)
            
            if not restore_file:
                logger.error("Failed to decrypt backup file")
                return False
        
        # Decompress if needed
        if restore_file.endswith(('.gz', '.zip')):
            temp_decompress = tempfile.mktemp(suffix='.db')
            restore_file = decompress_file(restore_file, temp_decompress)
            temp_files.append(temp_decompress)
            
            if not restore_file:
                logger.error("Failed to decompress backup file")
                return False
        
        # Perform restore
        if target_tables:
            # Partial restore - only specified tables
            success = restore_partial_tables(restore_file, target_tables)
        else:
            # Full restore
            shutil.copy2(restore_file, str(DEFAULT_DB_PATH))
            success = True
        
        # Clean up temporary files
        for temp_file in temp_files:
            try:
                os.remove(temp_file)
            except (OSError, FileNotFoundError) as e:
                logger.debug(f"Failed to remove temporary file {temp_file}: {e}")
                pass
        
        if success:
            logger.info(f"Database restored from: {backup_path}")
            if current_backup:
                logger.info(f"Previous database backed up to: {current_backup}")

            # Immutable audit log for backup restore
            if IMMUTABLE_AUDIT_AVAILABLE:
                user_id, _ = get_gui_context()
                safe_log_security_event(
                    action=AuditAction.BACKUP_RESTORE,
                    user_id=user_id or 'system',
                    resource_type='database_backup',
                    resource_id=os.path.basename(backup_path),
                    details={
                        'source_path': backup_path,
                        'target_tables': target_tables,
                        'point_in_time': str(point_in_time) if point_in_time else None,
                        'previous_backup': current_backup,
                    }
                )

            # Send notification
            notify_backup_result(True, backup_path, "restore")

        return success

    except sqlite3.Error as e:
        logger.error(f"Database error restoring from backup: {e}")
        notify_backup_result(False, backup_path, "restore")
        return False
    except (OSError, IOError) as e:
        logger.error(f"I/O error restoring from backup: {e}")
        notify_backup_result(False, backup_path, "restore")
        return False
    except shutil.Error as e:
        logger.error(f"File copy error restoring from backup: {e}")
        notify_backup_result(False, backup_path, "restore")
        return False

def restore_partial_tables(backup_path, tables):
    """Restore only specified tables from backup"""
    try:
        backup_conn = get_connection(db_path=backup_path, row_factory=False)
        main_conn = get_connection()

        for table in tables:
            # Validate table name to prevent SQL injection
            validated_table = validate_table_name(table, backup_conn)

            # Drop existing table - table name validated above, use bracket quoting
            main_conn.execute(f"DROP TABLE IF EXISTS [{validated_table}]")

            # Get table schema - using parameterized query
            cursor = backup_conn.cursor()
            cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?;", (table,))
            create_sql = cursor.fetchone()

            if create_sql:
                # Create table
                main_conn.execute(create_sql[0])

                # Copy data - table name validated above, use bracket quoting
                cursor.execute(f"SELECT * FROM [{validated_table}]")
                rows = cursor.fetchall()

                if rows:
                    placeholders = ','.join(['?' for _ in range(len(rows[0]))])
                    main_conn.executemany(f"INSERT INTO [{validated_table}] VALUES ({placeholders})", rows)
        
        main_conn.commit()
        main_conn.close()
        backup_conn.close()

        return True
    except ValueError as ve:
        logger.error(f"Invalid table name in partial restore: {ve}")
        return False
    except sqlite3.Error as e:
        logger.error(f"Database error restoring partial tables: {e}")
        return False
    except (OSError, IOError) as e:
        logger.error(f"I/O error restoring partial tables: {e}")
        return False

# Enhanced scheduling with cron support
def parse_cron_schedule(cron_expr):
    """Parse cron expression and schedule backup"""
    try:
        # Use croniter to parse cron expressions
        from croniter import croniter
        
        def cron_backup_job():
            if config["auto_backup_enabled"]:
                logger.info(f"Running cron scheduled backup at {datetime.datetime.now()}")
                create_enhanced_backup(manual=False)
        
        # Schedule using cron expression
        schedule.clear()
        
        # This is a simplified implementation
        # In a full implementation, you'd use a proper cron scheduler
        cron = croniter(cron_expr, datetime.datetime.now())
        next_run = cron.get_next(datetime.datetime)
        
        logger.info(f"Next backup scheduled for: {next_run}")

        # For demo purposes, we'll just log the schedule
        # Real implementation would use a proper cron daemon

    except ValueError as e:
        logger.error(f"Invalid cron expression: {e}")
    except ImportError as e:
        logger.error(f"croniter module not available: {e}")

# Backup comparison and analysis
def compare_backups(backup1_path, backup2_path):
    """Compare two backup files and return differences"""
    try:
        differences = {
            "tables_added": [],
            "tables_removed": [],
            "tables_modified": [],
            "record_changes": {}
        }

        conn1 = get_connection(db_path=backup1_path, row_factory=False)
        conn2 = get_connection(db_path=backup2_path, row_factory=False)
        
        # Get table lists
        tables1 = set(get_database_tables_from_connection(conn1))
        tables2 = set(get_database_tables_from_connection(conn2))
        
        differences["tables_added"] = list(tables2 - tables1)
        differences["tables_removed"] = list(tables1 - tables2)
        
        # Check common tables for changes
        common_tables = tables1 & tables2
        
        for table in common_tables:
            changes = compare_table_data(conn1, conn2, table)
            if changes["records_added"] or changes["records_removed"] or changes["records_modified"]:
                differences["tables_modified"].append(table)
                differences["record_changes"][table] = changes
        
        conn1.close()
        conn2.close()

        return differences

    except sqlite3.Error as e:
        logger.error(f"Database error comparing backups: {e}")
        return None
    except (OSError, IOError) as e:
        logger.error(f"I/O error comparing backups: {e}")
        return None

def get_database_tables_from_connection(conn):
    """Get table list from database connection"""
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    return [row[0] for row in cursor.fetchall()]

def compare_table_data(conn1, conn2, table):
    """Compare data in a specific table between two databases"""
    try:
        # Validate table name to prevent SQL injection
        validated_table = validate_table_name(table, conn1)
        validate_table_name(table, conn2)

        changes = {
            "records_added": 0,
            "records_removed": 0,
            "records_modified": 0
        }

        # Get row counts (simplified comparison)
        cursor1 = conn1.cursor()
        cursor2 = conn2.cursor()

        # Table name validated above - use bracket quoting for safety
        cursor1.execute(f"SELECT COUNT(*) FROM [{validated_table}]")
        count1 = cursor1.fetchone()[0]

        cursor2.execute(f"SELECT COUNT(*) FROM [{validated_table}]")
        count2 = cursor2.fetchone()[0]

        # This is a simplified comparison
        # A full implementation would compare actual record contents
        if count2 > count1:
            changes["records_added"] = count2 - count1
        elif count1 > count2:
            changes["records_removed"] = count1 - count2

        return changes

    except ValueError as ve:
        logger.error(f"Invalid table name comparing table data: {ve}")
        return {"records_added": 0, "records_removed": 0, "records_modified": 0}
    except sqlite3.Error as e:
        logger.error(f"Database error comparing table data: {e}")
        return {"records_added": 0, "records_removed": 0, "records_modified": 0}

# Backup validation
def validate_backup(backup_path):
    """Validate backup file integrity and restorability"""
    try:
        validation_results = {
            "file_exists": False,
            "file_readable": False,
            "database_valid": False,
            "tables_accessible": False,
            "hash_verified": False,
            "errors": []
        }
        
        # Check if file exists
        if os.path.exists(backup_path):
            validation_results["file_exists"] = True
        else:
            validation_results["errors"].append("Backup file does not exist")
            return validation_results
        
        # Check if file is readable
        try:
            with open(backup_path, 'rb') as f:
                f.read(1024)  # Try to read first 1KB
            validation_results["file_readable"] = True
        except (OSError, IOError, PermissionError) as e:
            validation_results["errors"].append(f"File read error: {e}")
            return validation_results
        
        # For encrypted/compressed files, we'd need to process them first
        test_file = backup_path
        temp_files = []
        
        try:
            # Handle encrypted files
            if backup_path.endswith('.encrypted'):
                if config["encryption_password"]:
                    temp_decrypt = tempfile.mktemp(suffix='.db')
                    test_file = decrypt_file(backup_path, config["encryption_password"], temp_decrypt)
                    temp_files.append(temp_decrypt)
                else:
                    validation_results["errors"].append("Cannot validate encrypted backup without password")
                    return validation_results
            
            # Handle compressed files
            if test_file and test_file.endswith(('.gz', '.zip')):
                temp_decompress = tempfile.mktemp(suffix='.db')
                test_file = decompress_file(test_file, temp_decompress)
                temp_files.append(temp_decompress)
            
            if not test_file:
                validation_results["errors"].append("Failed to prepare backup file for validation")
                return validation_results
            
            # Test database connectivity
            try:
                conn = get_connection(db_path=test_file, row_factory=False)
                cursor = conn.cursor()
                
                # Try to get table list
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = cursor.fetchall()
                
                validation_results["database_valid"] = True
                
                # Try to access each table
                table_errors = []
                for table_row in tables:
                    table_name = table_row[0]
                    try:
                        # Validate table name to prevent SQL injection
                        validated_table = validate_table_name(table_name, conn)
                        # Table name validated above - use bracket quoting for safety
                        cursor.execute(f"SELECT COUNT(*) FROM [{validated_table}]")
                        cursor.fetchone()
                    except ValueError as ve:
                        table_errors.append(f"Invalid table {table_name}: {ve}")
                    except sqlite3.Error as e:
                        table_errors.append(f"Table {table_name}: {e}")
                
                if not table_errors:
                    validation_results["tables_accessible"] = True
                else:
                    validation_results["errors"].extend(table_errors)
                
                conn.close()

            except sqlite3.Error as e:
                validation_results["errors"].append(f"Database validation error: {e}")
            
            # Verify file hash if available
            backup_metadata = None
            for backup in metadata_manager.get_backups():
                if backup["path"] == backup_path:
                    backup_metadata = backup
                    break
            
            if backup_metadata and "file_hash" in backup_metadata:
                current_hash = calculate_file_hash(test_file)
                if current_hash == backup_metadata["file_hash"]:
                    validation_results["hash_verified"] = True
                else:
                    validation_results["errors"].append("File hash mismatch - backup may be corrupted")
            
        finally:
            # Clean up temporary files
            for temp_file in temp_files:
                try:
                    os.remove(temp_file)
                except (OSError, FileNotFoundError) as e:
                    logger.debug(f"Failed to remove temporary file {temp_file}: {e}")
                    pass
        
        return validation_results

    except (OSError, IOError) as e:
        logger.error(f"I/O error validating backup: {e}")
        return {"errors": [str(e)]}
    except (KeyError, TypeError) as e:
        logger.error(f"Data error validating backup: {e}")
        return {"errors": [str(e)]}

# Backup templates
def save_backup_template(name, settings):
    """Save backup configuration as a template"""
    try:
        if "backup_templates" not in config:
            config["backup_templates"] = {}
        
        config["backup_templates"][name] = settings
        save_config()
        logger.info(f"Backup template '{name}' saved")
        return True
    except (KeyError, TypeError) as e:
        logger.error(f"Error saving backup template - invalid data: {e}")
        return False

def load_backup_template(name):
    """Load backup configuration from template"""
    try:
        if name in config.get("backup_templates", {}):
            template = config["backup_templates"][name]
            # Apply template settings to current config
            for key, value in template.items():
                if key in config:
                    config[key] = value
            logger.info(f"Backup template '{name}' loaded")
            return True
        else:
            logger.error(f"Backup template '{name}' not found")
            return False
    except (KeyError, TypeError) as e:
        logger.error(f"Error loading backup template - invalid data: {e}")
        return False

# Statistics and reporting
def generate_backup_statistics():
    """Generate comprehensive backup statistics"""
    try:
        backups = metadata_manager.get_backups()
        
        stats = {
            "total_backups": len(backups),
            "total_size": sum(b.get("size", 0) for b in backups),
            "backup_types": {},
            "success_rate": 0,
            "average_size": 0,
            "storage_usage": {},
            "recent_activity": []
        }
        
        if backups:
            # Backup type distribution
            for backup in backups:
                backup_type = backup.get("backup_type", "unknown")
                stats["backup_types"][backup_type] = stats["backup_types"].get(backup_type, 0) + 1
            
            # Average size
            stats["average_size"] = stats["total_size"] / len(backups)
            
            # Recent activity (last 30 days)
            thirty_days_ago = datetime.datetime.now() - datetime.timedelta(days=30)
            recent_backups = []
            
            for backup in backups:
                try:
                    backup_date = datetime.datetime.strptime(backup["timestamp"], "%Y%m%d_%H%M%S")
                    if backup_date >= thirty_days_ago:
                        recent_backups.append(backup)
                except (ValueError, KeyError, TypeError) as e:
                    logger.debug(f"Failed to parse backup timestamp for statistics: {e}")
                    pass
            
            stats["recent_activity"] = len(recent_backups)
            
            # Storage usage by month
            monthly_usage = {}
            for backup in backups:
                try:
                    backup_date = datetime.datetime.strptime(backup["timestamp"], "%Y%m%d_%H%M%S")
                    month_key = backup_date.strftime("%Y-%m")
                    monthly_usage[month_key] = monthly_usage.get(month_key, 0) + backup.get("size", 0)
                except (ValueError, KeyError, TypeError) as e:
                    logger.debug(f"Failed to calculate monthly usage for backup: {e}")
                    pass
            
            stats["storage_usage"] = monthly_usage
        
        # Update metadata with statistics
        metadata_manager.update_statistics(stats)

        return stats

    except (KeyError, TypeError, AttributeError) as e:
        logger.error(f"Error processing backup data for statistics: {e}")
        return {}
    except ZeroDivisionError as e:
        logger.error(f"Error calculating backup statistics: {e}")
        return {}

# Enhanced scheduled backup job
def scheduled_backup_job():
    """Enhanced scheduled backup function"""
    try:
        if not config["auto_backup_enabled"]:
            return
        
        logger.info(f"Running scheduled backup at {datetime.datetime.now()}")
        
        # Determine backup type based on schedule
        backup_type = "full"
        if config["enable_incremental"]:
            # Simple logic: full backup once a week, incremental otherwise
            now = datetime.datetime.now()
            if now.weekday() == 0:  # Monday
                backup_type = "full"
            else:
                backup_type = "incremental"
        
        # Create backup
        backup_path = create_enhanced_backup(
            manual=False, 
            backup_type=backup_type
        )
        
        if backup_path:
            logger.info(f"Scheduled backup completed: {backup_path}")
        else:
            logger.error("Scheduled backup failed")
        
        # Auto-validate if enabled
        if config["auto_validate"] and backup_path:
            validation_results = validate_backup(backup_path)
            if validation_results.get("errors"):
                logger.warning(f"Backup validation issues: {validation_results['errors']}")
                notify_backup_result(False, backup_path, "validation")

    except (KeyError, TypeError) as e:
        logger.error(f"Configuration error in scheduled backup job: {e}")
    except (OSError, IOError) as e:
        logger.error(f"I/O error in scheduled backup job: {e}")

# Enhanced start scheduler
def start_scheduler():
    """Start the enhanced backup scheduler"""
    global backup_thread, stop_flag
    
    # Set up the schedule based on configuration
    backup_time = config["scheduled_backup_time"]
    frequency = config["backup_frequency"]
    cron_schedule = config.get("cron_schedule", "")
    
    # Clear any existing jobs
    schedule.clear()
    
    # Use cron schedule if provided
    if cron_schedule:
        try:
            parse_cron_schedule(cron_schedule)
        except (ValueError, ImportError) as e:
            logger.error(f"Invalid cron schedule, falling back to simple schedule: {e}")
    
    # Schedule based on frequency
    if frequency == "daily":
        schedule.every().day.at(backup_time).do(scheduled_backup_job)
    elif frequency == "weekly":
        schedule.every().monday.at(backup_time).do(scheduled_backup_job)
    elif frequency == "monthly":
        schedule.every().day.at(backup_time).do(lambda: 
            scheduled_backup_job() if datetime.datetime.now().day == 1 else None)
    
    # Define the scheduler loop
    def run_scheduler():
        while not stop_flag:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    
    # Start the scheduler in a new thread
    stop_flag = False
    backup_thread = threading.Thread(target=run_scheduler)
    backup_thread.daemon = True
    backup_thread.start()
    
    logger.info(f"Enhanced backup scheduler started. Frequency: {frequency}, Time: {backup_time}")

def stop_scheduler():
    """Stop the backup scheduler thread"""
    global stop_flag
    
    if backup_thread and backup_thread.is_alive():
        stop_flag = True
        backup_thread.join(timeout=1)
        logger.info("Backup scheduler stopped")

# Enhanced configuration menu
def configure_backups():
    """Enhanced backup configuration with all new options"""
    global config

    while True:
        print("\n" + _t("data_backup.config_title") + ":")
        print("=" * 50)

        # Basic settings
        print("\n" + _t("data_backup.basic_settings") + ":")
        print(f"1.  {_t('data_backup.backup_directory')}: {config['backup_directory']}")
        print(f"2.  {_t('data_backup.scheduled_time')}: {config['scheduled_backup_time']}")
        print(f"3.  {_t('data_backup.frequency')}: {config['backup_frequency']}")
        print(f"4.  {_t('data_backup.max_backups')}: {config['max_backups']}")
        print(f"5.  {_t('data_backup.auto_backup')}: {_t('data_backup.enabled') if config['auto_backup_enabled'] else _t('data_backup.disabled')}")

        # Security settings
        print(f"\n{_t('data_backup.security_settings')}:")
        print(f"6.  {_t('data_backup.encryption')}: {_t('data_backup.enabled') if config['encryption_enabled'] else _t('data_backup.disabled')}")
        print(f"7.  {_t('data_backup.secure_deletion')}: {_t('data_backup.enabled') if config['secure_deletion'] else _t('data_backup.disabled')}")
        print(f"8.  {_t('data_backup.integrity_verification')}: {_t('data_backup.enabled') if config['verify_integrity'] else _t('data_backup.disabled')}")

        # Compression settings
        print(f"\n{_t('data_backup.compression_settings')}:")
        print(f"9.  {_t('data_backup.compression')}: {_t('data_backup.enabled') if config['compression_enabled'] else _t('data_backup.disabled')}")
        print(f"10. {_t('data_backup.compression_format')}: {config['compression_format']}")
        print(f"11. {_t('data_backup.compression_level')}: {config['compression_level']}")

        # Cloud/Remote settings
        print(f"\n{_t('data_backup.cloud_remote_storage')}:")
        print(f"12. {_t('data_backup.cloud_storage')}: {_t('data_backup.enabled') if config['cloud_enabled'] else _t('data_backup.disabled')}")
        print(f"13. {_t('data_backup.remote_storage')}: {_t('data_backup.enabled') if config['remote_enabled'] else _t('data_backup.disabled')}")

        # Backup types
        print(f"\n{_t('data_backup.backup_types')}:")
        print(f"14. {_t('data_backup.enable_incremental')}: {_t('common.yes') if config['enable_incremental'] else _t('common.no')}")
        print(f"15. {_t('data_backup.enable_selective')}: {_t('common.yes') if config['enable_selective'] else _t('common.no')}")

        # Notifications
        print(f"\n{_t('data_backup.notifications')}:")
        print(f"16. {_t('data_backup.email_notifications')}: {_t('data_backup.enabled') if config['email_notifications'] else _t('data_backup.disabled')}")
        print(f"17. {_t('data_backup.configure_webhooks')}")

        # Advanced features
        print(f"\n{_t('data_backup.advanced_features')}:")
        print(f"18. {_t('data_backup.change_detection')}: {_t('data_backup.enabled') if config['enable_change_detection'] else _t('data_backup.disabled')}")
        print(f"19. {_t('data_backup.parallel_backup')}: {_t('data_backup.enabled') if config['parallel_backup'] else _t('data_backup.disabled')}")
        print(f"20. {_t('data_backup.auto_validation')}: {_t('data_backup.enabled') if config['auto_validate'] else _t('data_backup.disabled')}")
        print(f"21. {_t('data_backup.configure_retention')}")
        print(f"22. {_t('data_backup.configure_cron')}")

        # Templates
        print(f"\n{_t('data_backup.templates')}:")
        print(f"23. {_t('data_backup.save_template')}")
        print(f"24. {_t('data_backup.load_template')}")
        print(f"25. {_t('data_backup.manage_templates')}")

        print(f"\n26. {_t('data_backup.save_return')}")

        choice = input("\n" + _t("data_backup.enter_choice") + " (1-26): ")

        # Basic settings
        if choice == '1':
            new_dir = input(_t("data_backup.enter_new_directory") + ": ")
            if new_dir:
                config["backup_directory"] = new_dir
                ensure_backup_directory()

        elif choice == '2':
            while True:
                new_time = input(_t("data_backup.enter_backup_time") + ": ")
                try:
                    datetime.datetime.strptime(new_time, "%H:%M")
                    config["scheduled_backup_time"] = new_time
                    break
                except ValueError:
                    print(_t("data_backup.invalid_time_format"))

        elif choice == '3':
            print(_t("data_backup.frequency_options") + ":")
            print("1. " + _t("data_backup.daily"))
            print("2. " + _t("data_backup.weekly"))
            print("3. " + _t("data_backup.monthly"))
            freq_choice = input(_t("data_backup.choose_option") + " (1-3): ")

            freq_map = {'1': 'daily', '2': 'weekly', '3': 'monthly'}
            if freq_choice in freq_map:
                config["backup_frequency"] = freq_map[freq_choice]

        elif choice == '4':
            try:
                max_backups = int(input(_t("data_backup.enter_max_backups") + ": "))
                if max_backups > 0:
                    config["max_backups"] = max_backups
            except ValueError:
                print(_t("data_backup.enter_valid_number"))
        
        elif choice == '5':
            config["auto_backup_enabled"] = not config["auto_backup_enabled"]
        
        # Security settings
        elif choice == '6':
            config["encryption_enabled"] = not config["encryption_enabled"]
            if config["encryption_enabled"] and not config["encryption_password"]:
                password = input(_t("data_backup.enter_encryption_password") + ": ")
                config["encryption_password"] = password

        elif choice == '7':
            config["secure_deletion"] = not config["secure_deletion"]

        elif choice == '8':
            config["verify_integrity"] = not config["verify_integrity"]

        # Compression settings
        elif choice == '9':
            config["compression_enabled"] = not config["compression_enabled"]

        elif choice == '10':
            print(_t("data_backup.compression_formats") + ":")
            print("1. " + _t("data_backup.gzip"))
            print("2. " + _t("data_backup.zip"))
            format_choice = input(_t("data_backup.choose_option") + " (1-2): ")

            if format_choice == '1':
                config["compression_format"] = "gzip"
            elif format_choice == '2':
                config["compression_format"] = "zip"

        elif choice == '11':
            try:
                level = int(input(_t("data_backup.enter_compression_level") + ": "))
                if 1 <= level <= 9:
                    config["compression_level"] = level
            except ValueError:
                print(_t("data_backup.invalid_level"))

        # Cloud/Remote settings
        elif choice == '12':
            configure_cloud_storage()

        elif choice == '13':
            configure_remote_storage()

        # Backup types
        elif choice == '14':
            config["enable_incremental"] = not config["enable_incremental"]

        elif choice == '15':
            config["enable_selective"] = not config["enable_selective"]
            if config["enable_selective"]:
                tables = get_database_tables()
                print(_t("data_backup.available_tables") + ": " + ", ".join(tables))
                selected = input(_t("data_backup.enter_table_names") + ": ").split(",")
                config["selective_tables"] = [t.strip() for t in selected if t.strip()]

        # Notifications
        elif choice == '16':
            configure_email_notifications()

        elif choice == '17':
            configure_webhooks()

        # Advanced features
        elif choice == '18':
            config["enable_change_detection"] = not config["enable_change_detection"]

        elif choice == '19':
            config["parallel_backup"] = not config["parallel_backup"]
            if config["parallel_backup"]:
                try:
                    threads = int(input(_t("data_backup.enter_max_threads") + ": "))
                    if 1 <= threads <= 8:
                        config["max_threads"] = threads
                except ValueError:
                    print(_t("data_backup.enter_valid_number"))

        elif choice == '20':
            config["auto_validate"] = not config["auto_validate"]

        elif choice == '21':
            configure_retention_policy()

        elif choice == '22':
            cron_expr = input(_t("data_backup.enter_cron") + ": ")
            config["cron_schedule"] = cron_expr

        # Templates
        elif choice == '23':
            name = input(_t("data_backup.enter_template_name") + ": ")
            if name:
                template_config = {k: v for k, v in config.items() if k != "backup_templates"}
                save_backup_template(name, template_config)

        elif choice == '24':
            templates = config.get("backup_templates", {})
            if templates:
                print(_t("data_backup.available_templates") + ":")
                for i, name in enumerate(templates.keys(), 1):
                    print(f"{i}. {name}")

                choice_template = input(_t("data_backup.enter_template_number") + ": ")
                try:
                    idx = int(choice_template) - 1
                    template_name = list(templates.keys())[idx]
                    load_backup_template(template_name)
                except (ValueError, IndexError):
                    print(_t("chat_rooms.invalid_selection"))
            else:
                print(_t("data_backup.no_templates"))

        elif choice == '25':
            manage_templates()

        elif choice == '26':
            save_config()

            # Restart scheduler with new settings
            stop_scheduler()
            if config["auto_backup_enabled"]:
                start_scheduler()

            break

        else:
            print(_t("data_backup.invalid_choice"))

def configure_cloud_storage():
    """Configure cloud storage settings"""
    config["cloud_enabled"] = not config["cloud_enabled"]

    if config["cloud_enabled"]:
        print(_t("data_backup.cloud_providers") + ":")
        print("1. " + _t("data_backup.aws_s3"))
        print("2. " + _t("data_backup.google_cloud"))
        print("3. " + _t("data_backup.azure"))

        provider_choice = input(_t("data_backup.choose_provider") + " (1-3): ")

        if provider_choice == '1':
            config["cloud_provider"] = "aws"
            config["aws_bucket"] = input(_t("data_backup.enter_bucket_name") + ": ")
            config["aws_access_key"] = input(_t("data_backup.enter_access_key") + ": ")
            config["aws_secret_key"] = input(_t("data_backup.enter_secret_key") + ": ")
            config["aws_region"] = input(_t("data_backup.enter_region") + ": ") or "us-east-1"

def configure_remote_storage():
    """Configure remote storage settings"""
    config["remote_enabled"] = not config["remote_enabled"]

    if config["remote_enabled"]:
        print(_t("data_backup.remote_types") + ":")
        print("1. " + _t("data_backup.ftp"))
        print("2. " + _t("data_backup.sftp"))

        type_choice = input(_t("data_backup.choose_remote_type") + " (1-2): ")

        if type_choice == '1':
            config["remote_type"] = "ftp"
        elif type_choice == '2':
            config["remote_type"] = "sftp"

        config["remote_host"] = input(_t("data_backup.enter_hostname") + ": ")
        config["remote_username"] = input(_t("data_backup.enter_username") + ": ")
        config["remote_password"] = input(_t("data_backup.enter_password") + ": ")
        config["remote_path"] = input(_t("data_backup.enter_remote_path") + ": ") or "/backups"

def configure_email_notifications():
    """Configure email notification settings"""
    config["email_notifications"] = not config["email_notifications"]

    if config["email_notifications"]:
        config["smtp_server"] = input(_t("data_backup.enter_smtp_server") + ": ") or "smtp.gmail.com"
        try:
            config["smtp_port"] = int(input(_t("data_backup.enter_smtp_port") + ": ") or "587")
        except ValueError:
            config["smtp_port"] = 587

        config["email_username"] = input(_t("data_backup.enter_email_username") + ": ")
        config["email_password"] = input(_t("data_backup.enter_email_password") + ": ")

        recipients = input(_t("data_backup.enter_recipients") + ": ")
        config["notification_recipients"] = [r.strip() for r in recipients.split(",") if r.strip()]

def configure_webhooks():
    """Configure webhook settings"""
    print(_t("data_backup.webhook_config") + ":")
    print("1. " + _t("data_backup.slack_webhook"))
    print("2. " + _t("data_backup.discord_webhook"))
    print("3. " + _t("data_backup.clear_webhooks"))

    choice = input(_t("data_backup.choose_option") + " (1-3): ")

    if choice == '1':
        config["slack_webhook"] = input(_t("data_backup.enter_slack_url") + ": ")
    elif choice == '2':
        config["discord_webhook"] = input(_t("data_backup.enter_discord_url") + ": ")
    elif choice == '3':
        config["slack_webhook"] = ""
        config["discord_webhook"] = ""

def configure_retention_policy():
    """Configure backup retention policy"""
    print(_t("data_backup.retention_policy") + ":")
    policy = config["retention_policy"]
    print(f"{_t('data_backup.daily_keep')}: {policy['daily_keep']}")
    print(f"{_t('data_backup.weekly_keep')}: {policy['weekly_keep']}")
    print(f"{_t('data_backup.monthly_keep')}: {policy['monthly_keep']}")
    print(f"{_t('data_backup.yearly_keep')}: {policy['yearly_keep']}")

    try:
        policy["daily_keep"] = int(input(_t("data_backup.enter_daily_keep") + ": ") or policy["daily_keep"])
        policy["weekly_keep"] = int(input(_t("data_backup.enter_weekly_keep") + ": ") or policy["weekly_keep"])
        policy["monthly_keep"] = int(input(_t("data_backup.enter_monthly_keep") + ": ") or policy["monthly_keep"])
        policy["yearly_keep"] = int(input(_t("data_backup.enter_yearly_keep") + ": ") or policy["yearly_keep"])
    except ValueError:
        print(_t("data_backup.invalid_keeping_current"))

def manage_templates():
    """Manage backup templates"""
    templates = config.get("backup_templates", {})

    while True:
        print("\n" + _t("data_backup.template_management") + ":")
        if templates:
            for i, name in enumerate(templates.keys(), 1):
                print(f"{i}. {name}")
            print(f"{len(templates) + 1}. " + _t("data_backup.delete_template"))
            print(f"{len(templates) + 2}. " + _t("data_backup.return"))
        else:
            print(_t("data_backup.no_templates"))
            print("1. " + _t("data_backup.return"))

        choice = input(_t("data_backup.enter_choice") + ": ")

        if not templates and choice == '1':
            break
        elif templates:
            if choice == str(len(templates) + 1):
                # Delete template
                template_name = input(_t("data_backup.enter_template_delete") + ": ")
                if template_name in templates:
                    del config["backup_templates"][template_name]
                    templates = config["backup_templates"]
                    print(_t("data_backup.template_deleted", name=template_name))
                else:
                    print(_t("data_backup.template_not_found"))
            elif choice == str(len(templates) + 2):
                break
            else:
                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(templates):
                        template_name = list(templates.keys())[idx]
                        template = templates[template_name]

                        print("\n" + _t("data_backup.template_settings", name=template_name))
                        for key, value in template.items():
                            print(f"  {key}: {value}")

                        action = input("\n" + _t("data_backup.load_this_template") + " (y/n): ")
                        if action.lower() == 'y':
                            load_backup_template(template_name)
                            break
                except (ValueError, IndexError):
                    print(_t("chat_rooms.invalid_selection"))

# Enhanced backup menu with all new features
def display_enhanced_backup_menu():
    """Display the enhanced backup menu"""
    # Load configuration
    load_config()

    # Start scheduler if auto backup is enabled
    if config["auto_backup_enabled"]:
        start_scheduler()

    while True:
        print("\n" + "="*60)
        print("           " + _t("data_backup.title"))
        print("="*60)
        print(_t("data_backup.basic_operations") + ":")
        print("1.  " + _t("data_backup.create_manual"))
        print("2.  " + _t("data_backup.view_available"))
        print("3.  " + _t("data_backup.delete_backup"))
        print("4.  " + _t("data_backup.restore_from"))
        print("5.  " + _t("data_backup.configure_settings"))

        print("\n" + _t("data_backup.advanced_types") + ":")
        print("6.  " + _t("data_backup.create_incremental"))
        print("7.  " + _t("data_backup.create_selective"))
        print("8.  " + _t("data_backup.create_schema"))

        print("\n" + _t("data_backup.analysis_comparison") + ":")
        print("9.  " + _t("data_backup.compare_backups"))
        print("10. " + _t("data_backup.validate_backup"))
        print("11. " + _t("data_backup.generate_stats"))

        print("\n" + _t("data_backup.export_import") + ":")
        print("12. " + _t("data_backup.export_backup"))
        print("13. " + _t("data_backup.partial_restore"))

        print("\n" + _t("data_backup.cloud_remote") + ":")
        print("14. " + _t("data_backup.upload_cloud"))
        print("15. " + _t("data_backup.download_cloud"))
        print("16. " + _t("data_backup.sync_remote"))

        print("\n" + _t("data_backup.templates_automation") + ":")
        print("17. " + _t("data_backup.quick_backup"))
        print("18. " + _t("data_backup.schedule_custom"))

        print("\n19. " + _t("data_backup.view_log"))
        print("20. " + _t("data_backup.return_main"))

        choice = input("\n" + _t("data_backup.enter_choice") + " (1-20): ")
        
        if choice == '1':
            # Create manual backup with options
            print("\n" + _t("data_backup.backup_type") + ":")
            print("1. " + _t("data_backup.full_backup"))
            print("2. " + _t("data_backup.incremental_backup"))
            print("3. " + _t("data_backup.schema_only"))
            print("4. " + _t("data_backup.selective_tables"))

            backup_type_choice = input(_t("data_backup.choose_backup_type") + " (1-4): ")

            backup_type = "full"
            tables = None

            if backup_type_choice == '2':
                backup_type = "incremental"
            elif backup_type_choice == '3':
                backup_type = "schema"
            elif backup_type_choice == '4':
                backup_type = "selective"
                available_tables = get_database_tables()
                print(_t("data_backup.available_tables") + ": " + ", ".join(available_tables))
                selected = input(_t("data_backup.enter_table_names") + ": ").split(",")
                tables = [t.strip() for t in selected if t.strip() in available_tables]

            backup_path = create_enhanced_backup(
                manual=True,
                backup_type=backup_type,
                tables=tables
            )

            if backup_path:
                print(_t("data_backup.backup_created", path=backup_path))

            input(_t("common.press_enter"))

        elif choice == '2':
            # Enhanced backup listing with filtering
            print("\n" + _t("data_backup.filter_options") + ":")
            print("1. " + _t("data_backup.show_all"))
            print("2. " + _t("data_backup.filter_by_type"))
            print("3. " + _t("data_backup.search_by_name"))

            filter_choice = input(_t("data_backup.choose_option") + " (1-3): ")

            filter_type = None
            search_term = None

            if filter_choice == '2':
                filter_type = input(_t("data_backup.enter_backup_type") + ": ")
            elif filter_choice == '3':
                search_term = input(_t("data_backup.enter_search_term") + ": ")

            backups = list_available_backups(filter_type=filter_type, search_term=search_term)

            if not backups:
                print(_t("data_backup.no_backups_found"))
            else:
                print("\n" + _t("data_backup.available_backups") + ":")
                print("-" * 120)
                print(f"{_t('common.id'):<4} {_t('common.type'):<12} {_t('common.date'):<20} {_t('common.size'):<12} {_t('data_backup.encrypted'):<10} {_t('data_backup.cloud'):<6} {_t('data_backup.filename')}")
                print("-" * 120)

                for backup in backups:
                    print(f"{backup['id']:<4} "
                          f"{backup.get('backup_type', 'full'):<12} "
                          f"{backup['date_formatted']:<20} "
                          f"{backup['size_formatted']:<12} "
                          f"{_t('common.yes') if backup.get('encrypted', False) else _t('common.no'):<10} "
                          f"{_t('common.yes') if backup.get('cloud_uploaded', False) else _t('common.no'):<6} "
                          f"{backup['filename']}")

            input("\n" + _t("common.press_enter"))

        elif choice == '3':
            # Delete backup
            backups = list_available_backups()

            if not backups:
                print(_t("data_backup.no_backups_found"))
            else:
                print("\n" + _t("data_backup.available_backups") + ":")
                print("-" * 120)
                print(f"{_t('common.id'):<4} {_t('common.type'):<12} {_t('common.date'):<20} {_t('common.size'):<12} {_t('data_backup.filename')}")
                print("-" * 120)

                for backup in backups:
                    print(f"{backup['id']:<4} "
                          f"{backup.get('backup_type', 'full'):<12} "
                          f"{backup['date_formatted']:<20} "
                          f"{backup['size_formatted']:<12} "
                          f"{backup['filename']}")

                try:
                    backup_id = int(input("\n" + _t("data_backup.enter_backup_id_delete") + ": "))
                    if backup_id == 0:
                        print(_t("data_backup.deletion_cancelled"))
                    elif 1 <= backup_id <= len(backups):
                        backup = backups[backup_id - 1]

                        confirm = input(_t("data_backup.confirm_delete", filename=backup['filename']) + " (yes/no): ")
                        if confirm.lower() in ['yes', 'y']:
                            success = delete_backup(backup['path'])
                            if success:
                                print(_t("data_backup.deleted_success", filename=backup['filename']))
                            else:
                                print(_t("data_backup.failed_delete", filename=backup['filename']))
                        else:
                            print(_t("data_backup.deletion_cancelled"))
                    else:
                        print(_t("data_backup.invalid_backup_id"))
                except ValueError:
                    print(_t("data_backup.enter_valid_number"))

            input("\n" + _t("common.press_enter"))

        elif choice == '4':
            # Enhanced restore with options
            backups = list_available_backups()

            if not backups:
                print(_t("data_backup.no_backups_found"))
            else:
                print("\n" + _t("data_backup.available_backups") + ":")
                for i, backup in enumerate(backups, 1):
                    print(f"{i}. {backup['filename']} ({backup['date_formatted']})")

                try:
                    backup_id = int(input("\n" + _t("data_backup.enter_backup_id_restore") + ": "))
                    if backup_id == 0:
                        continue
                    elif 1 <= backup_id <= len(backups):
                        backup = backups[backup_id - 1]

                        print("\n" + _t("data_backup.restore_options") + ":")
                        print("1. " + _t("data_backup.full_restore"))
                        print("2. " + _t("data_backup.partial_restore_option"))

                        restore_choice = input(_t("data_backup.choose_option") + " (1-2): ")

                        target_tables = None
                        if restore_choice == '2':
                            available_tables = get_database_tables()
                            print(_t("data_backup.available_tables") + ": " + ", ".join(available_tables))
                            selected = input(_t("data_backup.enter_table_names") + ": ").split(",")
                            target_tables = [t.strip() for t in selected if t.strip()]

                        confirm = input(_t("data_backup.confirm_restore", filename=backup['filename']) + " (y/n): ")
                        if confirm.lower() == 'y':
                            success = restore_from_backup(
                                backup['path'],
                                target_tables=target_tables
                            )
                            print(_t("data_backup.restore_successful") if success else _t("data_backup.restore_failed"))
                    else:
                        print(_t("data_backup.invalid_backup_id"))
                except ValueError:
                    print(_t("data_backup.enter_valid_number"))

            input("\n" + _t("common.press_enter"))

        elif choice == '5':
            configure_backups()

        elif choice == '6':
            # Create incremental backup
            backup_path = create_enhanced_backup(manual=True, backup_type="incremental")
            if backup_path:
                print(_t("data_backup.backup_created", path=backup_path))
            input(_t("common.press_enter"))

        elif choice == '7':
            # Create selective backup
            tables = get_database_tables()
            print(_t("data_backup.available_tables") + ": " + ", ".join(tables))
            selected = input(_t("data_backup.enter_table_names") + ": ").split(",")
            selected_tables = [t.strip() for t in selected if t.strip() in tables]

            if selected_tables:
                backup_path = create_enhanced_backup(
                    manual=True,
                    backup_type="selective",
                    tables=selected_tables
                )
                if backup_path:
                    print(_t("data_backup.backup_created", path=backup_path))
            input(_t("common.press_enter"))

        elif choice == '8':
            # Create schema-only backup
            backup_path = create_enhanced_backup(manual=True, backup_type="schema")
            if backup_path:
                print(_t("data_backup.backup_created", path=backup_path))
            input(_t("common.press_enter"))

        elif choice == '9':
            # Compare backups
            backups = list_available_backups()
            if len(backups) < 2:
                print(_t("data_backup.need_two_backups"))
            else:
                print(_t("data_backup.select_first_backup") + ":")
                for i, backup in enumerate(backups, 1):
                    print(f"{i}. {backup['filename']}")

                try:
                    id1 = int(input(_t("data_backup.enter_first_id") + ": ")) - 1
                    id2 = int(input(_t("data_backup.enter_second_id") + ": ")) - 1

                    if 0 <= id1 < len(backups) and 0 <= id2 < len(backups) and id1 != id2:
                        differences = compare_backups(backups[id1]['path'], backups[id2]['path'])
                        if differences:
                            print("\n" + _t("data_backup.comparison_results") + ":")
                            print(f"{_t('data_backup.tables_added')}: {len(differences['tables_added'])}")
                            print(f"{_t('data_backup.tables_removed')}: {len(differences['tables_removed'])}")
                            print(f"{_t('data_backup.tables_modified')}: {len(differences['tables_modified'])}")
                    else:
                        print(_t("data_backup.invalid_backup_ids"))
                except ValueError:
                    print(_t("data_backup.enter_valid_numbers"))

            input("\n" + _t("common.press_enter"))

        elif choice == '10':
            # Validate backup
            backups = list_available_backups()
            if not backups:
                print(_t("data_backup.no_backups_found"))
            else:
                print(_t("data_backup.select_backup_validate") + ":")
                for i, backup in enumerate(backups, 1):
                    print(f"{i}. {backup['filename']}")

                try:
                    backup_id = int(input(_t("data_backup.enter_choice") + ": ")) - 1
                    if 0 <= backup_id < len(backups):
                        print(_t("data_backup.validating"))
                        results = validate_backup(backups[backup_id]['path'])

                        print("\n" + _t("data_backup.validation_results") + ":")
                        print(f"{_t('data_backup.file_exists')}: {'✓' if results['file_exists'] else '✗'}")
                        print(f"{_t('data_backup.file_readable')}: {'✓' if results['file_readable'] else '✗'}")
                        print(f"{_t('data_backup.database_valid')}: {'✓' if results['database_valid'] else '✗'}")
                        print(f"{_t('data_backup.tables_accessible')}: {'✓' if results['tables_accessible'] else '✗'}")
                        print(f"{_t('data_backup.hash_verified')}: {'✓' if results['hash_verified'] else '✗'}")

                        if results['errors']:
                            print("\n" + _t("data_backup.errors_found") + ":")
                            for error in results['errors']:
                                print(f"  • {error}")
                    else:
                        print(_t("data_backup.invalid_backup_id"))
                except ValueError:
                    print(_t("data_backup.enter_valid_number"))

            input("\n" + _t("common.press_enter"))

        elif choice == '11':
            # Generate statistics
            print(_t("data_backup.generating_stats"))
            stats = generate_backup_statistics()

            print("\n" + _t("data_backup.stats_report") + ":")
            print("=" * 40)
            print(f"{_t('data_backup.total_backups')}: {stats['total_backups']}")
            print(f"{_t('data_backup.total_size')}: {stats['total_size'] / (1024*1024*1024):.2f} GB")
            print(f"{_t('data_backup.average_size')}: {stats['average_size'] / (1024*1024):.2f} MB")
            print(f"{_t('data_backup.recent_activity')}: {stats['recent_activity']} backups")

            if stats['backup_types']:
                print("\n" + _t("data_backup.backup_types_label") + ":")
                for backup_type, count in stats['backup_types'].items():
                    print(f"  {backup_type}: {count}")

            input("\n" + _t("common.press_enter"))

        elif choice == '12':
            # Export backup
            backups = list_available_backups()
            if not backups:
                print(_t("data_backup.no_backups_found"))
            else:
                print(_t("data_backup.select_backup_export") + ":")
                for i, backup in enumerate(backups, 1):
                    print(f"{i}. {backup['filename']}")

                try:
                    backup_id = int(input(_t("data_backup.enter_choice") + ": ")) - 1
                    if 0 <= backup_id < len(backups):
                        backup = backups[backup_id]

                        print(_t("data_backup.export_formats") + ":")
                        print("1. " + _t("data_backup.csv"))
                        print("2. " + _t("data_backup.json"))
                        print("3. " + _t("data_backup.xml"))

                        format_choice = input(_t("data_backup.choose_format") + " (1-3): ")

                        if format_choice == '1':
                            output_dir = input(_t("data_backup.enter_output_dir") + ": ") or "csv_export"
                            export_to_csv(backup['path'], output_dir)
                        elif format_choice == '2':
                            output_file = input(_t("data_backup.enter_output_file") + ": ") or "backup_export.json"
                            export_to_json(backup['path'], output_file)
                        elif format_choice == '3':
                            output_file = input(_t("data_backup.enter_output_file") + ": ") or "backup_export.xml"
                            export_to_xml(backup['path'], output_file)
                    else:
                        print(_t("data_backup.invalid_backup_id"))
                except ValueError:
                    print(_t("data_backup.enter_valid_number"))

            input("\n" + _t("common.press_enter"))

        elif choice == '13':
            # This is handled in choice 4 (restore) with partial restore option
            print(_t("data_backup.partial_restore_hint"))
            input(_t("common.press_enter"))

        elif choice == '14':
            # Upload to cloud (if configured)
            if not config["cloud_enabled"]:
                print(_t("data_backup.cloud_not_configured"))
            else:
                print(_t("data_backup.cloud_upload_hint"))
            input(_t("common.press_enter"))

        elif choice == '15':
            # Download from cloud
            if not config["cloud_enabled"]:
                print(_t("data_backup.cloud_not_configured"))
            else:
                print(_t("data_backup.cloud_download_hint"))
            input(_t("common.press_enter"))

        elif choice == '16':
            # Sync with remote
            if not config["remote_enabled"]:
                print(_t("data_backup.remote_not_configured"))
            else:
                print(_t("data_backup.remote_sync_hint"))
            input(_t("common.press_enter"))

        elif choice == '17':
            # Quick backup using template
            templates = config.get("backup_templates", {})
            if not templates:
                print(_t("data_backup.no_templates"))
            else:
                print(_t("data_backup.available_templates") + ":")
                for i, name in enumerate(templates.keys(), 1):
                    print(f"{i}. {name}")

                try:
                    template_choice = int(input(_t("data_backup.choose_template") + ": ")) - 1
                    template_names = list(templates.keys())
                    if 0 <= template_choice < len(template_names):
                        template_name = template_names[template_choice]

                        # Save current config
                        old_config = config.copy()

                        # Load template
                        load_backup_template(template_name)

                        # Create backup
                        backup_path = create_enhanced_backup(manual=True)
                        if backup_path:
                            print(_t("data_backup.template_backup_created", path=backup_path))

                        # Restore original config
                        config.update(old_config)
                    else:
                        print(_t("data_backup.invalid_template"))
                except ValueError:
                    print(_t("data_backup.enter_valid_number"))

            input(_t("common.press_enter"))

        elif choice == '18':
            # Schedule custom backup
            print(_t("data_backup.custom_schedule_hint"))
            input(_t("common.press_enter"))

        elif choice == '19':
            # View backup log
            try:
                # Read from app.log and filter for backup-related entries
                app_log_path = get_log_file('app.log')
                if not os.path.exists(app_log_path):
                    print(_t("data_backup.no_log_found"))
                else:
                    with open(app_log_path, 'r') as f:
                        lines = f.readlines()

                    # Filter for backup-related entries
                    backup_lines = [
                        line for line in lines
                        if 'data_backup' in line.lower() or 'backup' in line.lower()
                    ]

                    if not backup_lines:
                        print("\n" + _t("data_backup.no_log_entries"))
                    else:
                        # Show last 50 backup-related lines
                        print("\n" + _t("data_backup.backup_log", count=min(50, len(backup_lines))) + ":")
                        print("-" * 80)
                        for line in backup_lines[-50:]:
                            print(line.strip())
            except (OSError, IOError) as e:
                print(_t("data_backup.error_reading_log", error=str(e)))
            except UnicodeDecodeError as e:
                print(_t("data_backup.error_reading_log", error=str(e)))

            input("\n" + _t("common.press_enter"))

        elif choice == '20':
            # Stop scheduler and return
            stop_scheduler()
            print(_t("data_backup.returning_main"))
            break
        
        else:
            print(_t("data_backup.invalid_choice"))

# Legacy compatibility functions
def create_backup(manual=False, operation_name=None):
    """Legacy function for backward compatibility"""
    return create_enhanced_backup(manual=manual, operation_name=operation_name)

def display_backup_menu():
    """Legacy function name - forward to enhanced menu"""
    return display_enhanced_backup_menu()

def backup_before_operation(operation_name):
    """Create a backup before a major operation"""
    return create_enhanced_backup(manual=False, operation_name=operation_name)

def open_data_backup(*args, **kwargs):
    """Legacy name—forward to the enhanced menu function."""
    return display_enhanced_backup_menu(*args, **kwargs)

# Initialize the module
if __name__ == "__main__":
    display_enhanced_backup_menu()
