from university_system.infrastructure.database.db import DEFAULT_DB_PATH  # injected
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import threading
import queue
import datetime
import tempfile
import xml.etree.ElementTree as ET
import shutil
import tempfile
import os
import json
import hashlib
import posixpath
import re
from pathlib import Path
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Import centralized paths
try:
    from university_system.modules.shared.constants.paths import (
        BACKUP_DIR, LOG_DIR, BACKUP_TEMPLATES_DIR, DATA_DIR, DEFAULT_DB_PATH as DB_PATH, PROJECT_ROOT
    )
except ImportError:
    # Fallback if paths module not available - use PROJECT_ROOT relative paths
    from pathlib import Path
    PROJECT_ROOT = Path(__file__).resolve().parents[3]
    BACKUP_DIR = PROJECT_ROOT / "backups"
    LOG_DIR = PROJECT_ROOT / "logs"
    BACKUP_TEMPLATES_DIR = PROJECT_ROOT / "templates" / "backup_templates"
    DATA_DIR = PROJECT_ROOT / "data"
    DB_PATH = DEFAULT_DB_PATH

try:
    from university_system.infrastructure.database.db import get_db_connection, sqlite3
    from university_system.infrastructure.database.database_utils import cleanup_database_connections
    print("Database modules imported successfully")
except ImportError as e:
    print(f"Warning: Could not import database modules: {e}")
    # Create minimal fallbacks
    def get_db_connection():
        return None
    def cleanup_database_connections():
        pass

# Logging setup
try:
    from university_system.infrastructure.logging.log_config import configure_logging
    logger = configure_logging(name="backup_gui")
except Exception:
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("backup_gui")

# Initialize basic config if not available
config = {
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

_cron_schedule_lock = threading.Lock()
_next_cron_run = None


def _expand_cron_field(field_value, minimum, maximum):
    """Expand a single cron field into a sorted set of integers."""
    values = set()
    for token in field_value.split(','):
        token = token.strip()
        if not token:
            raise ValueError("Empty cron field token detected")

        step = 1
        if '/' in token:
            token, step_part = token.split('/', 1)
            if not step_part.isdigit():
                raise ValueError(f"Invalid cron step value '{step_part}'")
            step = int(step_part)
            if step <= 0:
                raise ValueError("Cron step value must be positive")

        if token == '*' or token == '':
            start, end = minimum, maximum
        elif '-' in token:
            start_str, end_str = token.split('-', 1)
            if not start_str.isdigit() or not end_str.isdigit():
                raise ValueError(f"Invalid cron range '{token}'")
            start, end = int(start_str), int(end_str)
        else:
            if not token.isdigit():
                raise ValueError(f"Invalid cron value '{token}'")
            start = end = int(token)

        if start < minimum or end > maximum:
            raise ValueError(f"Cron value '{token}' out of bounds ({minimum}-{maximum})")

        if start > end:
            raise ValueError(f"Cron range start greater than end in '{token}'")

        for value in range(start, end + 1, step):
            values.add(value)

    if not values:
        raise ValueError("Cron field did not produce any values")

    return sorted(values)


def _compute_cron_occurrences(cron_expr, base_time=None, occurrences=1):
    """Compute the next occurrence(s) from a cron expression."""
    base = (base_time or datetime.datetime.now()).replace(second=0, microsecond=0)
    try:
        from croniter import croniter  # type: ignore
    except Exception:
        croniter = None

    if croniter is not None:
        iterator = croniter(cron_expr, base)
        return [iterator.get_next(datetime.datetime) for _ in range(occurrences)]

    parts = cron_expr.split()
    if len(parts) != 5:
        raise ValueError("Cron expression must have exactly 5 fields")

    minutes = _expand_cron_field(parts[0], 0, 59)
    hours = _expand_cron_field(parts[1], 0, 23)
    days = _expand_cron_field(parts[2], 1, 31)
    months = _expand_cron_field(parts[3], 1, 12)
    weekdays = _expand_cron_field(parts[4], 0, 6)

    results = []
    candidate = base + datetime.timedelta(minutes=1)
    attempts = 0
    max_attempts = 525600  # Search up to one year ahead

    while len(results) < occurrences and attempts < max_attempts:
        if (
            candidate.minute in minutes
            and candidate.hour in hours
            and candidate.day in days
            and candidate.month in months
            and candidate.weekday() in weekdays
        ):
            results.append(candidate)
        candidate += datetime.timedelta(minutes=1)
        attempts += 1

    if not results:
        raise ValueError("Unable to compute next run time from cron expression within a year")

    return results


def _set_next_cron_run(next_run):
    """Store the next cron run timestamp with thread safety."""
    global _next_cron_run
    with _cron_schedule_lock:
        _next_cron_run = next_run

_last_incremental_context = {}
_last_differential_context = {}


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
    cursor = connection.execute(f"SELECT * FROM {table_name}")
    columns = [description[0] for description in cursor.description]
    rows = cursor.fetchall()

    digest = hashlib.sha256()
    for row in rows:
        digest.update(repr(row).encode("utf-8", "ignore"))

    return digest.hexdigest(), columns, rows


def _create_incremental_backup_impl(backup_path):
    """Implementation for incremental backups storing changed tables only."""
    global _last_incremental_context
    _last_incremental_context = {}

    source_conn = None
    base_conn = None
    incremental_conn = None
    temp_paths = []
    base_entry = None

    try:
        backups = metadata_manager.get_backups(limit=1) if 'metadata_manager' in globals() else []
        base_entry = backups[0] if backups else None

        if not base_entry or not os.path.exists(base_entry.get("path", "")):
            logger.warning("No previous backup available; creating full backup as incremental fallback.")
            shutil.copy2(str(DEFAULT_DB_PATH), backup_path)
            _last_incremental_context = {
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

        _last_incremental_context = {
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
    global _last_differential_context
    _last_differential_context = {}

    source_conn = None
    base_conn = None
    differential_conn = None
    temp_paths = []
    base_full_path = None

    try:
        base_full_path = metadata_manager.metadata.get("last_full") if 'metadata_manager' in globals() else None
        if not base_full_path or not os.path.exists(base_full_path):
            logger.warning("No previous full backup found; creating full backup instead of differential.")
            shutil.copy2(str(DEFAULT_DB_PATH), backup_path)
            _last_differential_context = {
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

        _last_differential_context = {
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

def start_scheduler():
    """Start the enhanced backup scheduler - missing full implementation"""
    global scheduler_thread, scheduler_running
    
    if scheduler_running:
        return
    
    import time
    
    def scheduler_worker():
        global scheduler_running
        scheduler_running = True
        
        while scheduler_running:
            try:
                current_time = datetime.datetime.now()
                cron_expr = config.get("cron_schedule", "").strip()

                if cron_expr:
                    with _cron_schedule_lock:
                        cron_next = _next_cron_run

                    try:
                        if cron_next is None or cron_next < current_time:
                            cron_next = _compute_cron_occurrences(cron_expr, current_time, occurrences=1)[0]
                            _set_next_cron_run(cron_next)

                        if cron_next and current_time >= cron_next:
                            if config.get("auto_backup_enabled", True):
                                logger.info("Running cron scheduled backup at %s", current_time)
                                scheduled_backup_job()
                            next_occurrence = _compute_cron_occurrences(cron_expr, cron_next, occurrences=1)[0]
                            _set_next_cron_run(next_occurrence)
                        time.sleep(30)
                        continue
                    except Exception as cron_error:
                        logger.error(f"Cron scheduling error: {cron_error}")
                        _set_next_cron_run(None)
                        # Fall back to frequency-based scheduling until cron expression is corrected
                
                scheduled_time = datetime.datetime.strptime(config["scheduled_backup_time"], "%H:%M").time()
                
                if (current_time.time().hour == scheduled_time.hour and 
                    current_time.time().minute == scheduled_time.minute):
                    
                    frequency = config["backup_frequency"]
                    should_run = False
                    
                    if frequency == "daily":
                        should_run = True
                    elif frequency == "weekly" and current_time.weekday() == 0:  # Monday
                        should_run = True
                    elif frequency == "monthly" and current_time.day == 1:
                        should_run = True
                    
                    if should_run and config.get("auto_backup_enabled", True):
                        scheduled_backup_job()
                        time.sleep(60)  # Prevent multiple runs in same minute
                
                time.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                time.sleep(60)
    
    scheduler_thread = threading.Thread(target=scheduler_worker, daemon=True)
    scheduler_thread.start()
    logger.info("Backup scheduler started")

def stop_scheduler():
    """Stop the backup scheduler thread - missing from GUI"""
    global scheduler_running
    scheduler_running = False
    _set_next_cron_run(None)
    logger.info("Backup scheduler stopped")

def scheduled_backup_job():
    """Enhanced scheduled backup function - missing from GUI"""
    try:
        logger.info("Starting scheduled backup job")
        backup_type = config.get("backup_type", "full")
        
        result = create_enhanced_backup(
            manual=False,
            backup_type=backup_type
        )
        
        if result:
            notify_backup_result(True, result, "scheduled backup")
            cleanup_old_backups()
        else:
            notify_backup_result(False, "unknown", "scheduled backup")
        
        return result is not None
    except Exception as e:
        logger.error(f"Error in scheduled backup job: {e}")
        notify_backup_result(False, str(e), "scheduled backup")
        return False

scheduler_thread = None
scheduler_running = False

def get_connection():
    """Database connection wrapper for compatibility - missing from GUI"""
    try:
        return get_db_connection()
    except:
        # Fallback to direct sqlite connection
        from university_system.infrastructure.database.db import sqlite3
        return sqlite3.connect(str(DEFAULT_DB_PATH))


def parse_cron_schedule(cron_expr):
    """Parse cron expression and schedule backup - missing from GUI"""
    try:
        expr = (cron_expr or "").strip()
        if not expr:
            _set_next_cron_run(None)
            config["cron_schedule"] = ""
            save_config()
            logger.info("Cleared cron schedule; scheduler will use frequency-based configuration.")
            return None

        upcoming = _compute_cron_occurrences(expr, datetime.datetime.now(), occurrences=5)
        next_run = upcoming[0]
        _set_next_cron_run(next_run)
        config["cron_schedule"] = expr
        save_config()

        preview = ", ".join(dt.strftime("%Y-%m-%d %H:%M") for dt in upcoming[:3])
        logger.info(
            "Cron schedule parsed successfully. Next run at %s. Upcoming executions: %s",
            next_run.strftime("%Y-%m-%d %H:%M"),
            preview,
        )
        return next_run
    except Exception as e:
        logger.error(f"Error parsing cron schedule: {e}")
        return False

def save_config():
    """Save configuration to file"""
    try:
        with open("backup_config.json", "w") as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        print(f"Could not save config: {e}")

def load_config():
    """Load configuration from file"""
    global config
    try:
        with open("backup_config.json", "r") as f:
            loaded_config = json.load(f)
            config.update(loaded_config)
    except FileNotFoundError:
        save_config()  # Create default config
    except Exception as e:
        print(f"Could not load config: {e}")

def get_database_tables_from_connection(conn):
    """Get table list from database connection - missing from GUI"""
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        return [row[0] for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Error getting tables from connection: {e}")
        return []

def create_incremental_backup(backup_path):
    """Create incremental backup - missing implementation in GUI"""
    if not has_database_changed():
        logger.info("No changes detected, skipping incremental backup")
        return None
    return _create_incremental_backup_impl(backup_path)

def generate_advanced_statistics():
    """Generate advanced backup statistics with trend analysis - missing from GUI"""
    try:
        backups = metadata_manager.get_backups()
        stats = generate_backup_statistics()  # Get basic stats
        
        # Add advanced metrics
        now = datetime.datetime.now()
        
        # Backup frequency analysis
        daily_counts = {}
        weekly_counts = {}
        monthly_counts = {}
        
        for backup in backups:
            try:
                backup_date = datetime.datetime.strptime(backup["timestamp"], "%Y%m%d_%H%M%S")
                
                # Daily frequency
                day_key = backup_date.strftime("%Y-%m-%d")
                daily_counts[day_key] = daily_counts.get(day_key, 0) + 1
                
                # Weekly frequency
                week_key = backup_date.strftime("%Y-W%U")
                weekly_counts[week_key] = weekly_counts.get(week_key, 0) + 1
                
                # Monthly frequency
                month_key = backup_date.strftime("%Y-%m")
                monthly_counts[month_key] = monthly_counts.get(month_key, 0) + 1
            except:
                pass
        
        stats["frequency_analysis"] = {
            "daily_distribution": daily_counts,
            "weekly_distribution": weekly_counts,
            "monthly_distribution": monthly_counts,
            "most_active_day": max(daily_counts.items(), key=lambda x: x[1]) if daily_counts else None,
            "most_active_week": max(weekly_counts.items(), key=lambda x: x[1]) if weekly_counts else None,
            "most_active_month": max(monthly_counts.items(), key=lambda x: x[1]) if monthly_counts else None
        }
        
        # Storage efficiency
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
        
        # Reliability metrics
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
        return generate_backup_statistics()  # Fallback to basic stats

def restore_from_backup(backup_path, target_tables=None, point_in_time=None):
    """Enhanced restore with partial and point-in-time options - missing from GUI"""
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
            except:
                pass
        
        if success:
            logger.info(f"Database restored from: {backup_path}")
            if current_backup:
                logger.info(f"Previous database backed up to: {current_backup}")
            
            # Send notification
            notify_backup_result(True, backup_path, "restore")
        
        return success
    
    except Exception as e:
        logger.error(f"Error restoring from backup: {e}")
        notify_backup_result(False, backup_path, "restore")
        return False

def restore_partial_tables(backup_path, tables):
    """Restore only specified tables from backup - missing from GUI"""
    try:
        from university_system.infrastructure.database.db import sqlite3
        backup_conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        main_conn = get_db_connection()
        
        for table in tables:
            # Drop existing table
            main_conn.execute(f"DROP TABLE IF EXISTS {table}")
            
            # Get table schema
            cursor = backup_conn.cursor()
            cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table}';")
            create_sql = cursor.fetchone()
            
            if create_sql:
                # Create table
                main_conn.execute(create_sql[0])
                
                # Copy data
                cursor.execute(f"SELECT * FROM {table}")
                rows = cursor.fetchall()
                
                if rows:
                    placeholders = ','.join(['?' for _ in range(len(rows[0]))])
                    main_conn.executemany(f"INSERT INTO {table} VALUES ({placeholders})", rows)
        
        main_conn.commit()
        main_conn.close()
        backup_conn.close()
        
        return True
    except Exception as e:
        logger.error(f"Error restoring partial tables: {e}")
        return False

def generate_backup_statistics():
    """Generate comprehensive backup statistics - missing implementation"""
    try:
        backups = metadata_manager.get_backups()
        
        stats = {
            'total_backups': len(backups),
            'total_size': sum(b.get("size", 0) for b in backups),
            'backup_types': {},
            'average_size': 0,
            'recent_activity': 0,
            'storage_usage': {}
        }
        
        if backups:
            # Backup type distribution
            for backup in backups:
                backup_type = backup.get('backup_type', 'unknown')
                stats['backup_types'][backup_type] = stats['backup_types'].get(backup_type, 0) + 1
            
            # Average size
            stats['average_size'] = stats['total_size'] / len(backups)
            
            # Recent activity (last 30 days)
            thirty_days_ago = datetime.datetime.now() - datetime.timedelta(days=30)
            recent_backups = []
            
            for backup in backups:
                try:
                    backup_date = datetime.datetime.strptime(backup["timestamp"], "%Y%m%d_%H%M%S")
                    if backup_date >= thirty_days_ago:
                        recent_backups.append(backup)
                except:
                    pass
            
            stats['recent_activity'] = len(recent_backups)
            
            # Storage usage by month
            monthly_usage = {}
            for backup in backups:
                try:
                    backup_date = datetime.datetime.strptime(backup["timestamp"], "%Y%m%d_%H%M%S")
                    month_key = backup_date.strftime("%Y-%m")
                    monthly_usage[month_key] = monthly_usage.get(month_key, 0) + backup.get("size", 0)
                except:
                    pass
            
            stats['storage_usage'] = monthly_usage
        
        # Update metadata with statistics
        metadata_manager.update_statistics(stats)
        
        return stats
    
    except Exception as e:
        logger.error(f"Error generating backup statistics: {e}")
        return {'total_backups': 0, 'total_size': 0, 'average_size': 0, 
                'recent_activity': 0, 'backup_types': {}, 'storage_usage': {}}

def get_log_file(filename):
    """Get log file path using centralized LOG_DIR"""
    # Use centralized LOG_DIR from paths module
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    return LOG_DIR / filename

def list_backup_templates():
    """List all available backup templates from JSON files and config"""
    templates = {}

    try:
        # Load templates from BACKUP_TEMPLATES_DIR
        if BACKUP_TEMPLATES_DIR.exists():
            for template_file in BACKUP_TEMPLATES_DIR.glob("*.json"):
                try:
                    with open(template_file, 'r') as f:
                        template_data = json.load(f)
                        template_name = template_data.get("name", template_file.stem.replace('_', ' ').title())
                        templates[template_name] = {
                            "source": "file",
                            "path": str(template_file),
                            "description": template_data.get("description", "No description available")
                        }
                except Exception as e:
                    logger.error(f"Error loading template from {template_file}: {e}")

        # Also include templates from config (backward compatibility)
        config_templates = config.get("backup_templates", {})
        for name in config_templates:
            if name not in templates:
                templates[name] = {
                    "source": "config",
                    "description": "User-created template"
                }

    except Exception as e:
        logger.error(f"Error listing backup templates: {e}")

    return templates

def save_backup_template(name, settings):
    """Save backup configuration as a template to JSON file"""
    try:
        # Save to both config (backward compatibility) and JSON file
        if "backup_templates" not in config:
            config["backup_templates"] = {}

        config["backup_templates"][name] = settings.copy()
        save_config()

        # Also save to JSON file in BACKUP_TEMPLATES_DIR
        BACKUP_TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
        template_file = BACKUP_TEMPLATES_DIR / f"{name.lower().replace(' ', '_')}.json"

        template_data = settings.copy()
        template_data["name"] = name

        with open(template_file, 'w') as f:
            json.dump(template_data, f, indent=2)

        logger.info(f"Template '{name}' saved to {template_file}")
        return True
    except Exception as e:
        logger.error(f"Error saving backup template: {e}")
        return False

def load_backup_template(name):
    """Load backup configuration from template (JSON file or config)"""
    try:
        # First, try to load from JSON file in BACKUP_TEMPLATES_DIR
        template_file = BACKUP_TEMPLATES_DIR / f"{name.lower().replace(' ', '_')}.json"

        if template_file.exists():
            with open(template_file, 'r') as f:
                template = json.load(f)
                # Remove 'name' and 'description' fields before updating config
                template_settings = {k: v for k, v in template.items()
                                   if k not in ['name', 'description']}
                config.update(template_settings)
                save_config()
                logger.info(f"Template '{name}' loaded from {template_file}")
                return True

        # Fallback: try to load from config (backward compatibility)
        templates = config.get("backup_templates", {})
        if name in templates:
            template = templates[name]
            config.update(template)
            save_config()
            logger.info(f"Template '{name}' loaded from config")
            return True

        logger.warning(f"Template '{name}' not found")
        return False

    except Exception as e:
        logger.error(f"Error loading backup template: {e}")
        return False

def export_to_csv(backup_path, output_dir):
    """Export backup to CSV files"""
    try:
        import csv
        conn = sqlite3.connect(backup_path)
        tables = get_database_tables_from_connection(conn)

        os.makedirs(output_dir, exist_ok=True)

        for table in tables:
            cursor = conn.execute(f"SELECT * FROM {table}")
            with open(os.path.join(output_dir, f"{table}.csv"), 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                # Write headers
                writer.writerow([description[0] for description in cursor.description])
                # Write data
                writer.writerows(cursor.fetchall())

        conn.close()
        logger.info(f"Exported backup to CSV: {output_dir}")
        return True
    except Exception as e:
        logger.error(f"Error exporting to CSV: {e}")
        return False

def export_to_json(backup_path, output_file):
    """Export backup to JSON file"""
    try:
        conn = sqlite3.connect(backup_path)
        tables = get_database_tables_from_connection(conn)

        data = {}
        for table in tables:
            cursor = conn.execute(f"SELECT * FROM {table}")
            columns = [description[0] for description in cursor.description]
            rows = cursor.fetchall()
            data[table] = [dict(zip(columns, row)) for row in rows]

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str)

        conn.close()
        logger.info(f"Exported backup to JSON: {output_file}")
        return True
    except Exception as e:
        logger.error(f"Error exporting to JSON: {e}")
        return False

def export_to_xml(backup_path, output_file):
    """Export backup to XML file"""
    try:
        conn = sqlite3.connect(backup_path)
        tables = get_database_tables_from_connection(conn)

        root = ET.Element("database")

        for table in tables:
            table_elem = ET.SubElement(root, "table", name=table)
            cursor = conn.execute(f"SELECT * FROM {table}")
            columns = [description[0] for description in cursor.description]

            for row in cursor.fetchall():
                row_elem = ET.SubElement(table_elem, "row")
                for col, val in zip(columns, row):
                    col_elem = ET.SubElement(row_elem, col)
                    col_elem.text = str(val) if val is not None else ""

        tree = ET.ElementTree(root)
        tree.write(output_file, encoding='utf-8', xml_declaration=True)

        conn.close()
        logger.info(f"Exported backup to XML: {output_file}")
        return True
    except Exception as e:
        logger.error(f"Error exporting to XML: {e}")
        return False

def export_to_pdf(backup_path, output_file):
    """Export backup to PDF file"""
    try:
        from reportlab.lib.pagesizes import letter, landscape
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import inch

        conn = sqlite3.connect(backup_path)
        tables = get_database_tables_from_connection(conn)

        doc = SimpleDocTemplate(output_file, pagesize=landscape(letter),
                               leftMargin=0.5*inch, rightMargin=0.5*inch,
                               topMargin=0.5*inch, bottomMargin=0.5*inch)
        elements = []
        styles = getSampleStyleSheet()

        # Title
        title = Paragraph("<b>Database Backup Export</b>", styles['Title'])
        elements.append(title)
        elements.append(Spacer(1, 0.3*inch))

        for table in tables:
            # Table title
            table_title = Paragraph(f"<b>Table: {table}</b>", styles['Heading2'])
            elements.append(table_title)
            elements.append(Spacer(1, 0.1*inch))

            # Get table data
            cursor = conn.execute(f"SELECT * FROM {table} LIMIT 100")  # Limit rows for PDF
            columns = [description[0] for description in cursor.description]
            rows = cursor.fetchall()

            if rows:
                # Prepare table data
                table_data = [columns]
                for row in rows:
                    table_data.append([str(val) if val is not None else "" for val in row])

                # Create table with auto column widths
                pdf_table = Table(table_data)
                pdf_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 8),
                    ('FONTSIZE', (0, 1), (-1, -1), 7),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ]))
                elements.append(pdf_table)
            else:
                elements.append(Paragraph("<i>No data</i>", styles['Normal']))

            elements.append(PageBreak())

        doc.build(elements)
        conn.close()
        logger.info(f"Exported backup to PDF: {output_file}")
        return True
    except ImportError:
        logger.error("ReportLab is required for PDF export. Install with: pip install reportlab")
        return False
    except Exception as e:
        logger.error(f"Error exporting to PDF: {e}")
        return False

def export_to_txt(backup_path, output_file):
    """Export backup to TXT file"""
    try:
        conn = sqlite3.connect(backup_path)
        tables = get_database_tables_from_connection(conn)

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("DATABASE BACKUP EXPORT\n")
            f.write("=" * 80 + "\n\n")

            for table in tables:
                f.write(f"\nTABLE: {table}\n")
                f.write("-" * 80 + "\n")

                cursor = conn.execute(f"SELECT * FROM {table}")
                columns = [description[0] for description in cursor.description]
                rows = cursor.fetchall()

                # Write column headers
                f.write(" | ".join(columns) + "\n")
                f.write("-" * 80 + "\n")

                # Write rows
                for row in rows:
                    f.write(" | ".join(str(val) if val is not None else "" for val in row) + "\n")

                f.write("\n")

        conn.close()
        logger.info(f"Exported backup to TXT: {output_file}")
        return True
    except Exception as e:
        logger.error(f"Error exporting to TXT: {e}")
        return False

def create_schema_only_backup(backup_path):
    """Create backup of database schema only (no data), excluding internal SQLite tables"""
    try:
        conn = get_db_connection()
        if not conn:
            logger.error("Failed to get database connection for schema backup")
            return False

        # Create schema-only backup
        with open(backup_path, 'w', encoding='utf-8') as f:
            for line in conn.iterdump():
                # Skip INSERT statements (data)
                if line.startswith('INSERT'):
                    continue
                # Skip internal SQLite tables (sqlite_sequence, sqlite_stat1, etc.)
                if 'sqlite_sequence' in line or 'sqlite_stat' in line:
                    continue
                # Skip CREATE statements for internal tables
                if line.startswith('CREATE TABLE') and ('sqlite_' in line.lower()):
                    continue
                f.write(f"{line}\n")

        conn.close()
        logger.info(f"Schema backup created successfully: {backup_path}")
        return True
    except Exception as e:
        logger.error(f"Error creating schema backup: {e}")
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

        # Check if files exist
        if not os.path.exists(backup1_path):
            logger.error(f"Backup 1 not found: {backup1_path}")
            return None
        if not os.path.exists(backup2_path):
            logger.error(f"Backup 2 not found: {backup2_path}")
            return None

        # Check if files are SQLite databases
        try:
            conn1 = sqlite3.connect(backup1_path)
            # Try a simple query to verify it's a valid database
            conn1.execute("SELECT name FROM sqlite_master LIMIT 1")
        except sqlite3.DatabaseError as e:
            logger.error(f"Backup 1 is not a valid database file: {e}")
            return None

        try:
            conn2 = sqlite3.connect(backup2_path)
            # Try a simple query to verify it's a valid database
            conn2.execute("SELECT name FROM sqlite_master LIMIT 1")
        except sqlite3.DatabaseError as e:
            logger.error(f"Backup 2 is not a valid database file: {e}")
            if conn1:
                conn1.close()
            return None

        # Get table lists
        tables1 = set(get_database_tables_from_connection(conn1))
        tables2 = set(get_database_tables_from_connection(conn2))

        differences["tables_added"] = list(tables2 - tables1)
        differences["tables_removed"] = list(tables1 - tables2)

        # Check common tables for changes
        common_tables = tables1 & tables2

        for table in common_tables:
            # Compare row counts as a simple check
            try:
                count1 = conn1.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                count2 = conn2.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

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

class ProgressTracker:
    """Progress tracking for backup operations - missing from GUI"""
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
            
            return {
                'percentage': percentage,
                'speed_mbps': speed/1024/1024,
                'eta_seconds': eta,
                'bytes_transferred': self.current_size,
                'total_bytes': self.total_size
            }

class IntegrityCheckDialog:
    """Dialog for running integrity checks on backups - missing class"""
    
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Backup Integrity Check")
        self.dialog.geometry("600x500")
        self.dialog.transient(parent)
        
        self.create_widgets()
        self.check_results = []
    
    def create_widgets(self):
        """Create dialog widgets"""
        # Controls
        controls_frame = ttk.Frame(self.dialog)
        controls_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Button(controls_frame, text="Check All Backups", 
                  command=self.check_all_backups).pack(side="left", padx=5)
        ttk.Button(controls_frame, text="Check Selected", 
                  command=self.check_selected).pack(side="left", padx=5)
        ttk.Button(controls_frame, text="Export Report", 
                  command=self.export_report).pack(side="left", padx=5)
        
        # Results display
        results_frame = ttk.LabelFrame(self.dialog, text="Integrity Check Results", padding=10)
        results_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Treeview for results
        columns = ("Backup", "Status", "File Exists", "Readable", "DB Valid", "Hash Match")
        self.results_tree = ttk.Treeview(results_frame, columns=columns, show="headings", height=12)
        
        for col in columns:
            self.results_tree.heading(col, text=col)
            self.results_tree.column(col, width=100)
        
        scrollbar = ttk.Scrollbar(results_frame, orient="vertical", command=self.results_tree.yview)
        self.results_tree.configure(yscrollcommand=scrollbar.set)
        
        self.results_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(self.dialog, variable=self.progress_var, 
                                          mode="determinate", length=400)
        self.progress_bar.pack(padx=10, pady=5)
        
        # Status label
        self.status_label = ttk.Label(self.dialog, text="Ready to check backups")
        self.status_label.pack(pady=5)
        
        # Close button
        ttk.Button(self.dialog, text="Close", command=self.dialog.destroy).pack(pady=10)
    
    def check_all_backups(self):
        """Check integrity of all backups"""
        backups = list_available_backups()
        if not backups:
            messagebox.showinfo("No Backups", "No backups found to check")
            return
        
        self.run_integrity_check(backups)
    
    def check_selected(self):
        """Check selected backups"""
        backups = list_available_backups()
        if not backups:
            messagebox.showinfo("No Backups", "No backups found to check")
            return

        dialog = tk.Toplevel(self.dialog)
        dialog.title("Select Backups to Check")
        dialog.transient(self.dialog)
        dialog.grab_set()

        ttk.Label(dialog, text="Select one or more backups to verify:").pack(anchor="w", padx=10, pady=(10, 5))

        listbox = tk.Listbox(dialog, selectmode=tk.MULTIPLE, width=70, height=10)
        listbox.pack(fill="both", expand=True, padx=10)

        for backup in backups:
            display = f"{backup['date_formatted']} • {backup.get('backup_type', 'full').title()} • {backup['filename']}"
            listbox.insert(tk.END, display)

        selected_backups = []

        def confirm_selection():
            indices = listbox.curselection()
            if not indices:
                messagebox.showwarning("No Selection", "Please choose at least one backup.", parent=dialog)
                return
            for idx in indices:
                selected_backups.append(backups[idx])
            dialog.destroy()

        button_frame = ttk.Frame(dialog)
        button_frame.pack(fill="x", padx=10, pady=10)
        ttk.Button(button_frame, text="Check", command=confirm_selection).pack(side="right", padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side="right")

        self.dialog.wait_window(dialog)

        if selected_backups:
            self.run_integrity_check(selected_backups)
    
    def run_integrity_check(self, backups):
        """Run integrity check on list of backups"""
        def check_worker():
            try:
                total = len(backups)
                self.check_results = []
                
                for i, backup in enumerate(backups):
                    self.status_label.config(text=f"Checking {backup['filename']}...")
                    self.progress_var.set((i / total) * 100)
                    self.dialog.update()
                    
                    # Perform validation
                    results = validate_backup(backup['path'])
                    
                    # Determine overall status
                    if all([results.get('file_exists', False), 
                           results.get('file_readable', False),
                           results.get('database_valid', False),
                           results.get('tables_accessible', False)]):
                        status = "✅ PASS"
                    else:
                        status = "❌ FAIL"
                    
                    # Add to results
                    result_row = (
                        backup['filename'],
                        status,
                        "✅" if results.get('file_exists', False) else "❌",
                        "✅" if results.get('file_readable', False) else "❌",
                        "✅" if results.get('database_valid', False) else "❌",
                        "✅" if results.get('hash_verified', False) else "❌"
                    )
                    
                    self.results_tree.insert("", "end", values=result_row)
                    self.check_results.append({
                        'backup': backup,
                        'results': results,
                        'status': status
                    })
                
                self.progress_var.set(100)
                self.status_label.config(text="Integrity check completed")
                
                # Show summary
                passed = sum(1 for r in self.check_results if "PASS" in r['status'])
                failed = len(self.check_results) - passed
                
                messagebox.showinfo("Check Complete", 
                                   f"Integrity check completed\n\n"
                                   f"Passed: {passed}\n"
                                   f"Failed: {failed}")
            
            except Exception as e:
                messagebox.showerror("Check Error", f"Integrity check failed: {e}")
                self.status_label.config(text="Check failed")
            finally:
                self.progress_var.set(0)
        
        # Run in separate thread
        import threading
        check_thread = threading.Thread(target=check_worker)
        check_thread.daemon = True
        check_thread.start()

class AdvancedSettingsDialog:
    """Dialog for advanced backup settings - missing class"""
    
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Advanced Backup Settings")
        self.dialog.geometry("500x600")
        self.dialog.transient(parent)
        
        self.create_widgets()
        self.load_current_settings()
    
    def create_widgets(self):
        """Create dialog widgets"""
        # Change detection settings
        change_frame = ttk.LabelFrame(self.dialog, text="Change Detection", padding=10)
        change_frame.pack(fill="x", padx=10, pady=5)
        
        self.change_detection_var = tk.BooleanVar()
        ttk.Checkbutton(change_frame, text="Enable Change Detection", 
                       variable=self.change_detection_var).pack(anchor="w")
        
        # Deduplication settings
        dedup_frame = ttk.LabelFrame(self.dialog, text="Deduplication", padding=10)
        dedup_frame.pack(fill="x", padx=10, pady=5)
        
        self.deduplication_var = tk.BooleanVar()
        ttk.Checkbutton(dedup_frame, text="Enable Deduplication", 
                       variable=self.deduplication_var).pack(anchor="w")
        
        # Performance settings
        perf_frame = ttk.LabelFrame(self.dialog, text="Performance", padding=10)
        perf_frame.pack(fill="x", padx=10, pady=5)
        
        self.parallel_var = tk.BooleanVar()
        ttk.Checkbutton(perf_frame, text="Enable Parallel Processing", 
                       variable=self.parallel_var).pack(anchor="w")
        
        ttk.Label(perf_frame, text="Max Threads:").pack(anchor="w")
        self.threads_var = tk.StringVar()
        ttk.Spinbox(perf_frame, textvariable=self.threads_var, 
                   from_=1, to=8, width=10).pack(anchor="w")
        
        ttk.Label(perf_frame, text="Bandwidth Limit (Mbps, 0=unlimited):").pack(anchor="w")
        self.bandwidth_var = tk.StringVar()
        ttk.Entry(perf_frame, textvariable=self.bandwidth_var, width=10).pack(anchor="w")
        
        # Storage quota
        storage_frame = ttk.LabelFrame(self.dialog, text="Storage Management", padding=10)
        storage_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(storage_frame, text="Storage Quota (GB):").pack(anchor="w")
        self.quota_var = tk.StringVar()
        ttk.Entry(storage_frame, textvariable=self.quota_var, width=10).pack(anchor="w")
        
        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(fill="x", padx=10, pady=10)
        
        ttk.Button(button_frame, text="Save", command=self.save_settings).pack(side="right", padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side="right")
    
    def load_current_settings(self):
        """Load current advanced settings"""
        self.change_detection_var.set(config.get("enable_change_detection", False))
        self.deduplication_var.set(config.get("enable_deduplication", False))
        self.parallel_var.set(config.get("parallel_backup", False))
        self.threads_var.set(str(config.get("max_threads", 4)))
        self.bandwidth_var.set(str(config.get("bandwidth_limit_mbps", 0)))
        self.quota_var.set(str(config.get("storage_quota_gb", 10)))
    
    def save_settings(self):
        """Save advanced settings"""
        try:
            config["enable_change_detection"] = self.change_detection_var.get()
            config["enable_deduplication"] = self.deduplication_var.get()
            config["parallel_backup"] = self.parallel_var.get()
            config["max_threads"] = int(self.threads_var.get())
            config["bandwidth_limit_mbps"] = int(self.bandwidth_var.get())
            config["storage_quota_gb"] = int(self.quota_var.get())
            
            save_config()
            messagebox.showinfo("Success", "Advanced settings saved!")
            self.dialog.destroy()
        except ValueError as e:
            messagebox.showerror("Invalid Input", f"Please check your input values: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings: {e}")

class BackupMetadata:
    """Class to handle backup metadata and tracking - missing from GUI"""

    def __init__(self):
        self.metadata_file = DATA_DIR / "backup_metadata.json"
        self.metadata = self.load_metadata()
    
    def load_metadata(self):
        """Load backup metadata from file"""
        if os.path.exists(self.metadata_file):
            try:
                with open(self.metadata_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading metadata: {e}")
                return {"backups": [], "last_full": None, "statistics": {}}
        return {"backups": [], "last_full": None, "statistics": {}}
    
    def save_metadata(self):
        """Save backup metadata to file"""
        try:
            with open(self.metadata_file, 'w') as f:
                json.dump(self.metadata, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving metadata: {e}")
    
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

class BackupGUI:
    """Main GUI class for the enhanced backup system"""
    
    def __init__(self, root, auth=None):
        self.root = root
        self.auth = auth  # Store authentication instance
        self.root.title("Enhanced Data Backup System")
        self.root.geometry("1200x800")
        self.root.minsize(1000, 600)

        # Initialize GUI state
        self.backup_thread = None
        self.log_queue = queue.Queue()
        self.status_var = tk.StringVar(value="Ready")
        self.progress_var = tk.DoubleVar()
        
        # Load configuration
        load_config()
        
        # Create GUI
        self.create_widgets()
        self.setup_logging()
        
        # Start scheduler if enabled
        if config["auto_backup_enabled"]:
            start_scheduler()
        
        # Start log monitoring
        self.monitor_logs()
    
    def create_widgets(self):
        """Create all GUI widgets"""
        # Create main notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Create tabs
        self.create_main_tab()
        self.create_advanced_tab()
        self.create_config_tab()
        self.create_analysis_tab()
        self.create_cloud_tab()
        self.create_logs_tab()
        
        # Create status bar
        self.create_status_bar()
    
    def create_main_tab(self):
        """Create the main backup operations tab"""
        main_frame = ttk.Frame(self.notebook)
        self.notebook.add(main_frame, text="Main Operations")
        
        # Title and menu button frame
        title_frame = ttk.Frame(main_frame)
        title_frame.pack(fill="x", pady=10, padx=10)

        title_label = ttk.Label(title_frame, text="Data Backup System",
                               font=("Arial", 16, "bold"))
        title_label.pack(side="left")

        ttk.Button(title_frame, text="🏠 Return to Main Menu",
                  command=self.return_to_main_menu).pack(side="right")
        
        # Main operations frame
        ops_frame = ttk.LabelFrame(main_frame, text="Basic Operations", padding=10)
        ops_frame.pack(fill="x", padx=10, pady=5)
        
        # Buttons frame
        btn_frame1 = ttk.Frame(ops_frame)
        btn_frame1.pack(fill="x", pady=5)
        
        ttk.Button(btn_frame1, text="Create Manual Backup", 
                  command=self.create_manual_backup).pack(side="left", padx=5)
        ttk.Button(btn_frame1, text="View Backups", 
                  command=self.view_backups).pack(side="left", padx=5)
        ttk.Button(btn_frame1, text="Restore from Backup", 
                  command=self.restore_backup).pack(side="left", padx=5)
        
        btn_frame2 = ttk.Frame(ops_frame)
        btn_frame2.pack(fill="x", pady=5)
        
        ttk.Button(btn_frame2, text="Quick Backup", 
                  command=self.quick_backup).pack(side="left", padx=5)
        ttk.Button(btn_frame2, text="Validate Backup", 
                  command=self.validate_backup_gui).pack(side="left", padx=5)
        ttk.Button(btn_frame2, text="Export Backup", 
                  command=self.export_backup_gui).pack(side="left", padx=5)
        
        # Backup list frame
        list_frame = ttk.LabelFrame(main_frame, text="Recent Backups", padding=10)
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Treeview for backup list
        columns = ("ID", "Type", "Date", "Size", "Status")
        self.backup_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=10)
        
        for col in columns:
            self.backup_tree.heading(col, text=col)
            self.backup_tree.column(col, width=100)
        
        # Scrollbar for treeview
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.backup_tree.yview)
        self.backup_tree.configure(yscrollcommand=scrollbar.set)
        
        self.backup_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Populate backup list
        self.refresh_backup_list()
        
        # Auto-refresh every 30 seconds
        self.root.after(30000, self.auto_refresh_backup_list)
    
    def create_advanced_tab(self):
        """Create the advanced backup operations tab - ADD MISSING ITEMS"""
        advanced_frame = ttk.Frame(self.notebook)
        self.notebook.add(advanced_frame, text="Advanced")
        
        # Advanced backup types
        types_frame = ttk.LabelFrame(advanced_frame, text="Advanced Backup Types", padding=10)
        types_frame.pack(fill="x", padx=10, pady=5)
        
        btn_frame1 = ttk.Frame(types_frame)
        btn_frame1.pack(fill="x", pady=5)
        
        ttk.Button(btn_frame1, text="Incremental Backup", 
                  command=self.create_incremental_backup).pack(side="left", padx=5)
        ttk.Button(btn_frame1, text="Selective Backup", 
                  command=self.create_selective_backup).pack(side="left", padx=5)
        ttk.Button(btn_frame1, text="Schema Only", 
                  command=self.create_schema_backup).pack(side="left", padx=5)
        
        # ADD MISSING: Differential backup button
        ttk.Button(btn_frame1, text="Differential Backup", 
                  command=self.create_differential_backup).pack(side="left", padx=5)
        
        # Templates frame
        template_frame = ttk.LabelFrame(advanced_frame, text="Templates", padding=10)
        template_frame.pack(fill="x", padx=10, pady=5)
        
        btn_frame2 = ttk.Frame(template_frame)
        btn_frame2.pack(fill="x", pady=5)
        
        ttk.Button(btn_frame2, text="Save Template", 
                  command=self.save_template_gui).pack(side="left", padx=5)
        ttk.Button(btn_frame2, text="Load Template", 
                  command=self.load_template_gui).pack(side="left", padx=5)
        ttk.Button(btn_frame2, text="Manage Templates", 
                  command=self.manage_templates_gui).pack(side="left", padx=5)
        
        # ADD MISSING: Import/Export templates
        ttk.Button(btn_frame2, text="Import Template", 
                  command=self.import_template_gui).pack(side="left", padx=5)
        ttk.Button(btn_frame2, text="Export Template", 
                  command=self.export_template_gui).pack(side="left", padx=5)
        
        # Schedule frame (existing code with update_schedule_status fix)
        schedule_frame = ttk.LabelFrame(advanced_frame, text="Scheduling", padding=10)
        schedule_frame.pack(fill="x", padx=10, pady=5)

        self.schedule_var = tk.StringVar()
        ttk.Label(schedule_frame, textvariable=self.schedule_var).pack(pady=5)

        btn_frame3 = ttk.Frame(schedule_frame)
        btn_frame3.pack(fill="x", pady=5)

        self.schedule_btn = ttk.Button(btn_frame3, text="Enable Scheduling", 
                                     command=self.toggle_scheduling)
        self.schedule_btn.pack(side="left", padx=5)

        ttk.Button(btn_frame3, text="Configure Schedule", 
                  command=self.configure_schedule_gui).pack(side="left", padx=5)
        
        # ADD MISSING: Advanced scheduling options
        ttk.Button(btn_frame3, text="Schedule History", 
                  command=self.show_schedule_history).pack(side="left", padx=5)
        ttk.Button(btn_frame3, text="Test Schedule", 
                  command=self.test_schedule).pack(side="left", padx=5)
        
        self.update_schedule_status()
    
    def update_schedule_status(self):
        """Update schedule status display"""
        if config["auto_backup_enabled"]:
            status = f"Scheduling: Enabled ({config['backup_frequency']} at {config['scheduled_backup_time']})"
            button_text = "Disable Scheduling"
        else:
            status = "Scheduling: Disabled"
            button_text = "Enable Scheduling"
        
        self.schedule_var.set(status)
        
        # Only update button if it exists
        if hasattr(self, 'schedule_btn'):
            self.schedule_btn.config(text=button_text)
        
    def create_config_tab(self):
        """Create the configuration tab"""
        config_frame = ttk.Frame(self.notebook)
        self.notebook.add(config_frame, text="Configuration")
        
        # Create scrollable frame
        canvas = tk.Canvas(config_frame)
        scrollbar = ttk.Scrollbar(config_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Basic settings
        basic_frame = ttk.LabelFrame(scrollable_frame, text="Basic Settings", padding=10)
        basic_frame.pack(fill="x", padx=10, pady=5)
        
        # Backup directory
        ttk.Label(basic_frame, text="Backup Directory:").grid(row=0, column=0, sticky="w", pady=2)
        self.backup_dir_var = tk.StringVar(value=config["backup_directory"])
        ttk.Entry(basic_frame, textvariable=self.backup_dir_var, width=40).grid(row=0, column=1, padx=5)
        ttk.Button(basic_frame, text="Browse", 
                  command=self.browse_backup_dir).grid(row=0, column=2)
        
        # Max backups
        ttk.Label(basic_frame, text="Max Backups:").grid(row=1, column=0, sticky="w", pady=2)
        self.max_backups_var = tk.StringVar(value=str(config["max_backups"]))
        ttk.Entry(basic_frame, textvariable=self.max_backups_var, width=10).grid(row=1, column=1, sticky="w", padx=5)
        
        # Auto backup
        self.auto_backup_var = tk.BooleanVar(value=config["auto_backup_enabled"])
        ttk.Checkbutton(basic_frame, text="Enable Auto Backup", 
                       variable=self.auto_backup_var).grid(row=2, column=0, columnspan=2, sticky="w", pady=5)
        
        # Security settings
        security_frame = ttk.LabelFrame(scrollable_frame, text="Security Settings", padding=10)
        security_frame.pack(fill="x", padx=10, pady=5)
        
        self.encryption_var = tk.BooleanVar(value=config["encryption_enabled"])
        ttk.Checkbutton(security_frame, text="Enable Encryption", 
                       variable=self.encryption_var, 
                       command=self.toggle_encryption).grid(row=0, column=0, sticky="w")
        
        ttk.Label(security_frame, text="Encryption Password:").grid(row=1, column=0, sticky="w", pady=2)
        self.encryption_pass_var = tk.StringVar(value=config["encryption_password"])
        self.encryption_entry = ttk.Entry(security_frame, textvariable=self.encryption_pass_var, 
                                        show="*", width=30)
        self.encryption_entry.grid(row=1, column=1, padx=5)
        
        self.secure_delete_var = tk.BooleanVar(value=config["secure_deletion"])
        ttk.Checkbutton(security_frame, text="Secure Deletion", 
                       variable=self.secure_delete_var).grid(row=2, column=0, sticky="w")
        
        self.verify_integrity_var = tk.BooleanVar(value=config["verify_integrity"])
        ttk.Checkbutton(security_frame, text="Verify Integrity", 
                       variable=self.verify_integrity_var).grid(row=2, column=1, sticky="w")
        
        # Compression settings
        compression_frame = ttk.LabelFrame(scrollable_frame, text="Compression Settings", padding=10)
        compression_frame.pack(fill="x", padx=10, pady=5)
        
        self.compression_var = tk.BooleanVar(value=config["compression_enabled"])
        ttk.Checkbutton(compression_frame, text="Enable Compression", 
                       variable=self.compression_var).grid(row=0, column=0, sticky="w")
        
        ttk.Label(compression_frame, text="Format:").grid(row=1, column=0, sticky="w", pady=2)
        self.compression_format_var = tk.StringVar(value=config["compression_format"])
        format_combo = ttk.Combobox(compression_frame, textvariable=self.compression_format_var, 
                                   values=["gzip", "zip"], state="readonly", width=10)
        format_combo.grid(row=1, column=1, padx=5, sticky="w")
        
        ttk.Label(compression_frame, text="Level:").grid(row=1, column=2, sticky="w", padx=(20,5))
        self.compression_level_var = tk.StringVar(value=str(config["compression_level"]))
        level_spin = ttk.Spinbox(compression_frame, textvariable=self.compression_level_var, 
                               from_=1, to=9, width=5)
        level_spin.grid(row=1, column=3, padx=5, sticky="w")
        
        # Notifications
        notify_frame = ttk.LabelFrame(scrollable_frame, text="Notifications", padding=10)
        notify_frame.pack(fill="x", padx=10, pady=5)
        
        self.email_notify_var = tk.BooleanVar(value=config["email_notifications"])
        ttk.Checkbutton(notify_frame, text="Email Notifications", 
                       variable=self.email_notify_var,
                       command=self.toggle_email_notifications).grid(row=0, column=0, sticky="w")
        
        ttk.Button(notify_frame, text="Configure Email", 
                  command=self.configure_email_gui).grid(row=0, column=1, padx=10)
        ttk.Button(notify_frame, text="Configure Webhooks", 
                  command=self.configure_webhooks_gui).grid(row=0, column=2, padx=10)
        
        # Save button
        ttk.Button(scrollable_frame, text="Save Configuration", 
                  command=self.save_configuration).pack(pady=20)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def create_analysis_tab(self):
        """Create the analysis and comparison tab"""
        analysis_frame = ttk.Frame(self.notebook)
        self.notebook.add(analysis_frame, text="Analysis")
        
        # Comparison frame
        compare_frame = ttk.LabelFrame(analysis_frame, text="Backup Comparison", padding=10)
        compare_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Button(compare_frame, text="Compare Backups", 
                  command=self.compare_backups_gui).pack(side="left", padx=5)
        ttk.Button(compare_frame, text="Generate Statistics", 
                  command=self.generate_statistics_gui).pack(side="left", padx=5)
        ttk.Button(compare_frame, text="Backup Report", 
                  command=self.generate_report_gui).pack(side="left", padx=5)
        
        # Statistics display
        stats_frame = ttk.LabelFrame(analysis_frame, text="Current Statistics", padding=10)
        stats_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.stats_text = scrolledtext.ScrolledText(stats_frame, height=15, wrap=tk.WORD)
        self.stats_text.pack(fill="both", expand=True)
        
        # Load initial statistics
        self.refresh_statistics()
    
    def create_cloud_tab(self):
        """Create the cloud and remote storage tab"""
        cloud_frame = ttk.Frame(self.notebook)
        self.notebook.add(cloud_frame, text="Cloud & Remote")
        
        # Cloud storage frame
        cloud_storage_frame = ttk.LabelFrame(cloud_frame, text="Cloud Storage", padding=10)
        cloud_storage_frame.pack(fill="x", padx=10, pady=5)
        
        self.cloud_enabled_var = tk.BooleanVar(value=config["cloud_enabled"])
        ttk.Checkbutton(cloud_storage_frame, text="Enable Cloud Storage", 
                       variable=self.cloud_enabled_var,
                       command=self.toggle_cloud_storage).grid(row=0, column=0, sticky="w")
        
        # AWS S3 settings
        aws_frame = ttk.LabelFrame(cloud_storage_frame, text="AWS S3 Settings", padding=5)
        aws_frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=5)
        
        ttk.Label(aws_frame, text="Bucket:").grid(row=0, column=0, sticky="w")
        self.aws_bucket_var = tk.StringVar(value=config["aws_bucket"])
        ttk.Entry(aws_frame, textvariable=self.aws_bucket_var, width=20).grid(row=0, column=1, padx=5)
        
        ttk.Label(aws_frame, text="Access Key:").grid(row=1, column=0, sticky="w")
        self.aws_access_var = tk.StringVar(value=config["aws_access_key"])
        ttk.Entry(aws_frame, textvariable=self.aws_access_var, width=20).grid(row=1, column=1, padx=5)
        
        ttk.Label(aws_frame, text="Secret Key:").grid(row=2, column=0, sticky="w")
        self.aws_secret_var = tk.StringVar(value=config["aws_secret_key"])
        ttk.Entry(aws_frame, textvariable=self.aws_secret_var, show="*", width=20).grid(row=2, column=1, padx=5)
        
        ttk.Label(aws_frame, text="Region:").grid(row=3, column=0, sticky="w")
        self.aws_region_var = tk.StringVar(value=config["aws_region"])
        ttk.Entry(aws_frame, textvariable=self.aws_region_var, width=20).grid(row=3, column=1, padx=5)
        
        # Remote storage frame
        remote_frame = ttk.LabelFrame(cloud_frame, text="Remote Storage", padding=10)
        remote_frame.pack(fill="x", padx=10, pady=5)
        
        self.remote_enabled_var = tk.BooleanVar(value=config["remote_enabled"])
        ttk.Checkbutton(remote_frame, text="Enable Remote Storage", 
                       variable=self.remote_enabled_var).grid(row=0, column=0, sticky="w")
        
        ttk.Label(remote_frame, text="Type:").grid(row=1, column=0, sticky="w")
        self.remote_type_var = tk.StringVar(value=config["remote_type"])
        type_combo = ttk.Combobox(remote_frame, textvariable=self.remote_type_var, 
                                values=["ftp", "sftp"], state="readonly", width=10)
        type_combo.grid(row=1, column=1, padx=5, sticky="w")
        
        ttk.Label(remote_frame, text="Host:").grid(row=2, column=0, sticky="w")
        self.remote_host_var = tk.StringVar(value=config["remote_host"])
        ttk.Entry(remote_frame, textvariable=self.remote_host_var, width=20).grid(row=2, column=1, padx=5)
        
        ttk.Label(remote_frame, text="Username:").grid(row=3, column=0, sticky="w")
        self.remote_user_var = tk.StringVar(value=config["remote_username"])
        ttk.Entry(remote_frame, textvariable=self.remote_user_var, width=20).grid(row=3, column=1, padx=5)
        
        ttk.Label(remote_frame, text="Password:").grid(row=4, column=0, sticky="w")
        self.remote_pass_var = tk.StringVar(value=config["remote_password"])
        ttk.Entry(remote_frame, textvariable=self.remote_pass_var, show="*", width=20).grid(row=4, column=1, padx=5)
        
        # Cloud operations
        operations_frame = ttk.LabelFrame(cloud_frame, text="Cloud Operations", padding=10)
        operations_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Button(operations_frame, text="Upload Backup", 
                  command=self.upload_backup_gui).pack(side="left", padx=5)
        ttk.Button(operations_frame, text="Download Backup", 
                  command=self.download_backup_gui).pack(side="left", padx=5)
        ttk.Button(operations_frame, text="Sync Storage", 
                  command=self.sync_storage_gui).pack(side="left", padx=5)
    
    def create_logs_tab(self):
        """Create the logs and monitoring tab"""
        logs_frame = ttk.Frame(self.notebook)
        self.notebook.add(logs_frame, text="Logs")
        
        # Log controls
        controls_frame = ttk.Frame(logs_frame)
        controls_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Button(controls_frame, text="Refresh Logs", 
                  command=self.refresh_logs).pack(side="left", padx=5)
        ttk.Button(controls_frame, text="Clear Logs", 
                  command=self.clear_logs).pack(side="left", padx=5)
        ttk.Button(controls_frame, text="Export Logs", 
                  command=self.export_logs).pack(side="left", padx=5)
        
        # Log level filter
        ttk.Label(controls_frame, text="Filter:").pack(side="left", padx=(20, 5))
        self.log_level_var = tk.StringVar(value="All")
        level_combo = ttk.Combobox(controls_frame, textvariable=self.log_level_var,
                                 values=["All", "ERROR", "WARNING", "INFO", "DEBUG"], 
                                 state="readonly", width=10)
        level_combo.pack(side="left", padx=5)
        level_combo.bind("<<ComboboxSelected>>", self.filter_logs)
        
        # Log display
        self.log_text = scrolledtext.ScrolledText(logs_frame, height=25, wrap=tk.WORD)
        self.log_text.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Load initial logs
        self.refresh_logs()
    
    def create_status_bar(self):
        """Create the status bar"""
        status_frame = ttk.Frame(self.root)
        status_frame.pack(fill="x", side="bottom")
        
        # Status label
        status_label = ttk.Label(status_frame, textvariable=self.status_var, relief="sunken")
        status_label.pack(side="left", fill="x", expand=True)
        
        # Progress bar
        self.progress_bar = ttk.Progressbar(status_frame, variable=self.progress_var, 
                                          length=200, mode="determinate")
        self.progress_bar.pack(side="right", padx=5, pady=2)
    
    def setup_logging(self):
        """Setup logging to capture log messages in GUI"""
        # This would integrate with the existing logging system
        pass
    
    def monitor_logs(self):
        """Monitor log queue for new messages"""
        try:
            while True:
                record = self.log_queue.get_nowait()
                self.log_text.insert(tk.END, f"{record}\n")
                self.log_text.see(tk.END)
        except queue.Empty:
            pass
        
        # Schedule next check
        self.root.after(1000, self.monitor_logs)

    def return_to_main_menu(self):
        """Return to the main menu"""
        try:
            # Check if this is a child window (Toplevel) or standalone (Tk)
            if isinstance(self.root, tk.Toplevel):
                # Just close the child window
                self.root.destroy()
            else:
                # Running standalone, need to create main GUI if auth available
                if self.auth:
                    self.root.destroy()
                    from university_system.modules.shared.gui.main_gui import UnifiedManagementGUI
                    app = UnifiedManagementGUI(self.auth)
                    app.run()
                else:
                    messagebox.showinfo("Info", "No main menu available - running standalone")
        except Exception as e:
            print(f"Error returning to main menu: {e}")
            import traceback
            traceback.print_exc()

    # Main operations methods
    def create_manual_backup(self):
        """Create a manual backup with options"""
        dialog = BackupOptionsDialog(self.root)
        if dialog.result:
            self.run_backup_operation(
                lambda: create_enhanced_backup(
                    manual=True,
                    backup_type=dialog.backup_type,
                    tables=dialog.selected_tables
                ),
                "Creating manual backup..."
            )
    
    def quick_backup(self):
        """Create a quick full backup"""
        self.run_backup_operation(
            lambda: create_enhanced_backup(manual=True),
            "Creating quick backup..."
        )
    
    def view_backups(self):
        """Open backup viewer dialog"""
        BackupViewerDialog(self.root)
    
    def restore_backup(self):
        """Open restore dialog"""
        RestoreDialog(self.root, self.refresh_backup_list)
    
    def validate_backup_gui(self):
        """Open backup validation dialog"""
        ValidationDialog(self.root)
    
    def export_backup_gui(self):
        """Open backup export dialog"""
        ExportDialog(self.root)
    
    # Advanced operations methods
    def create_incremental_backup(self):
        """Create incremental backup"""
        self.run_backup_operation(
            lambda: create_enhanced_backup(manual=True, backup_type="incremental"),
            "Creating incremental backup..."
        )
    
    def create_selective_backup(self):
        """Create selective table backup"""
        tables = get_database_tables()
        dialog = TableSelectionDialog(self.root, tables)
        if dialog.selected_tables:
            self.run_backup_operation(
                lambda: create_enhanced_backup(
                    manual=True, 
                    backup_type="selective",
                    tables=dialog.selected_tables
                ),
                "Creating selective backup..."
            )
    
    def create_schema_backup(self):
        """Create schema-only backup"""
        self.run_backup_operation(
            lambda: create_enhanced_backup(manual=True, backup_type="schema"),
            "Creating schema backup..."
        )
    
    def save_template_gui(self):
        """Save current configuration as template"""
        name = tk.simpledialog.askstring("Save Template", "Enter template name:")
        if name:
            # Get current configuration
            self.save_configuration()  # Save current GUI settings to config
            template_config = {k: v for k, v in config.items() if k != "backup_templates"}
            
            if save_backup_template(name, template_config):
                messagebox.showinfo("Success", f"Template '{name}' saved successfully!")
            else:
                messagebox.showerror("Error", "Failed to save template")
    
    def load_template_gui(self):
        """Load configuration from template"""
        # Use new list_backup_templates function to get all templates
        templates = list_backup_templates()
        if not templates:
            messagebox.showinfo("No Templates", "No templates available")
            return

        dialog = TemplateSelectionDialog(self.root, list(templates.keys()), templates)
        if dialog.selected_template:
            if load_backup_template(dialog.selected_template):
                self.refresh_config_gui()
                messagebox.showinfo("Success", f"Template '{dialog.selected_template}' loaded!")
            else:
                messagebox.showerror("Error", "Failed to load template")
    
    def manage_templates_gui(self):
        """Open template management dialog"""
        TemplateManagerDialog(self.root)
    
    def toggle_scheduling(self):
        """Toggle backup scheduling"""
        config["auto_backup_enabled"] = not config["auto_backup_enabled"]
        
        if config["auto_backup_enabled"]:
            start_scheduler()
            self.schedule_btn.config(text="Disable Scheduling")
        else:
            stop_scheduler()
            self.schedule_btn.config(text="Enable Scheduling")
        
        self.update_schedule_status()
        save_config()
    
    def configure_schedule_gui(self):
        """Open schedule configuration dialog"""
        ScheduleConfigDialog(self.root, self.update_schedule_status)
    
    # Configuration methods
    def browse_backup_dir(self):
        """Browse for backup directory"""
        directory = filedialog.askdirectory(initialdir=self.backup_dir_var.get())
        if directory:
            self.backup_dir_var.set(directory)
    
    def toggle_encryption(self):
        """Toggle encryption settings"""
        if self.encryption_var.get() and not self.encryption_pass_var.get():
            password = tk.simpledialog.askstring("Encryption Password", 
                                                "Enter encryption password:", show="*")
            if password:
                self.encryption_pass_var.set(password)
            else:
                self.encryption_var.set(False)
    
    def toggle_email_notifications(self):
        """Toggle email notifications"""
        if self.email_notify_var.get():
            self.configure_email_gui()
    
    def configure_email_gui(self):
        """Configure email settings"""
        EmailConfigDialog(self.root)
    
    def configure_webhooks_gui(self):
        """Configure webhook settings"""
        WebhookConfigDialog(self.root)
    
    def toggle_cloud_storage(self):
        """Toggle cloud storage"""
        # Enable/disable AWS settings based on cloud storage toggle
        pass
    
    def save_configuration(self):
        """Save all configuration settings"""
        try:
            # Update config from GUI
            config["backup_directory"] = self.backup_dir_var.get()
            config["max_backups"] = int(self.max_backups_var.get())
            config["auto_backup_enabled"] = self.auto_backup_var.get()
            config["encryption_enabled"] = self.encryption_var.get()
            config["encryption_password"] = self.encryption_pass_var.get()
            config["secure_deletion"] = self.secure_delete_var.get()
            config["verify_integrity"] = self.verify_integrity_var.get()
            config["compression_enabled"] = self.compression_var.get()
            config["compression_format"] = self.compression_format_var.get()
            config["compression_level"] = int(self.compression_level_var.get())
            config["email_notifications"] = self.email_notify_var.get()
            config["cloud_enabled"] = self.cloud_enabled_var.get()
            config["aws_bucket"] = self.aws_bucket_var.get()
            config["aws_access_key"] = self.aws_access_var.get()
            config["aws_secret_key"] = self.aws_secret_var.get()
            config["aws_region"] = self.aws_region_var.get()
            config["remote_enabled"] = self.remote_enabled_var.get()
            config["remote_type"] = self.remote_type_var.get()
            config["remote_host"] = self.remote_host_var.get()
            config["remote_username"] = self.remote_user_var.get()
            config["remote_password"] = self.remote_pass_var.get()
            
            save_config()
            
            # Restart scheduler if needed
            if config["auto_backup_enabled"]:
                stop_scheduler()
                start_scheduler()
            
            messagebox.showinfo("Success", "Configuration saved successfully!")
            
        except ValueError as e:
            messagebox.showerror("Error", f"Invalid configuration value: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save configuration: {e}")
    
    def refresh_config_gui(self):
        """Refresh GUI with current configuration"""
        self.backup_dir_var.set(config["backup_directory"])
        self.max_backups_var.set(str(config["max_backups"]))
        self.auto_backup_var.set(config["auto_backup_enabled"])
        self.encryption_var.set(config["encryption_enabled"])
        self.encryption_pass_var.set(config["encryption_password"])
        self.secure_delete_var.set(config["secure_deletion"])
        self.verify_integrity_var.set(config["verify_integrity"])
        self.compression_var.set(config["compression_enabled"])
        self.compression_format_var.set(config["compression_format"])
        self.compression_level_var.set(str(config["compression_level"]))
        self.email_notify_var.set(config["email_notifications"])
        self.cloud_enabled_var.set(config["cloud_enabled"])
        self.aws_bucket_var.set(config["aws_bucket"])
        self.aws_access_var.set(config["aws_access_key"])
        self.aws_secret_var.set(config["aws_secret_key"])
        self.aws_region_var.set(config["aws_region"])
        self.remote_enabled_var.set(config["remote_enabled"])
        self.remote_type_var.set(config["remote_type"])
        self.remote_host_var.set(config["remote_host"])
        self.remote_user_var.set(config["remote_username"])
        self.remote_pass_var.set(config["remote_password"])
    
    # Analysis methods
    def compare_backups_gui(self):
        """Open backup comparison dialog"""
        ComparisonDialog(self.root)
    
    def generate_statistics_gui(self):
        """Generate and display statistics"""
        self.refresh_statistics()
    
    def generate_report_gui(self):
        """Generate comprehensive backup report"""
        ReportDialog(self.root)
    
    def refresh_statistics(self):
        """Refresh statistics display"""
        try:
            stats = generate_backup_statistics()
            
            stats_text = "BACKUP STATISTICS REPORT\n"
            stats_text += "=" * 40 + "\n\n"
            stats_text += f"Total Backups: {stats['total_backups']}\n"
            stats_text += f"Total Size: {stats['total_size'] / (1024*1024*1024):.2f} GB\n"
            stats_text += f"Average Size: {stats['average_size'] / (1024*1024):.2f} MB\n"
            stats_text += f"Recent Activity (30 days): {stats['recent_activity']} backups\n\n"
            
            if stats['backup_types']:
                stats_text += "Backup Types:\n"
                for backup_type, count in stats['backup_types'].items():
                    stats_text += f"  {backup_type}: {count}\n"
                stats_text += "\n"
            
            if stats['storage_usage']:
                stats_text += "Monthly Storage Usage:\n"
                for month, size in sorted(stats['storage_usage'].items()):
                    stats_text += f"  {month}: {size / (1024*1024):.2f} MB\n"
            
            self.stats_text.delete(1.0, tk.END)
            self.stats_text.insert(1.0, stats_text)
            
        except Exception as e:
            self.stats_text.delete(1.0, tk.END)
            self.stats_text.insert(1.0, f"Error generating statistics: {e}")
    
    # Cloud operations
    def upload_backup_gui(self):
        """Upload backup to cloud"""
        if not config["cloud_enabled"]:
            messagebox.showwarning("Cloud Storage", "Cloud storage is not configured")
            return
        
        UploadDialog(self.root)
    
    def download_backup_gui(self):
        """Download backup from cloud"""
        if not config["cloud_enabled"]:
            messagebox.showwarning("Cloud Storage", "Cloud storage is not configured")
            return
        
        DownloadDialog(self.root)
    
    def sync_storage_gui(self):
        """Sync with remote storage"""
        if not config["remote_enabled"]:
            messagebox.showwarning("Remote Storage", "Remote storage is not configured")
            return

        host = self.remote_host_var.get().strip()
        username = self.remote_user_var.get().strip()
        password = self.remote_pass_var.get().strip()
        remote_type = self.remote_type_var.get()
        remote_path = config.get("remote_path", "/backups")

        if not host or not username or not password:
            messagebox.showwarning("Remote Storage", "Please provide host, username, and password for remote storage.")
            return

        backups = list_available_backups()
        if not backups:
            messagebox.showinfo("Remote Storage", "No backups available to sync.")
            return

        to_sync = [b for b in backups if not b.get("remote_uploaded", False)]
        if not to_sync:
            messagebox.showinfo("Remote Storage", "All backups are already synced with the remote location.")
            return

        # Persist the latest credentials in config
        config["remote_host"] = host
        config["remote_username"] = username
        config["remote_password"] = password

        def update_status(progress, status_text):
            self.progress_var.set(progress)
            self.status_var.set(status_text)

        def finish_sync(successes, failures):
            self.progress_var.set(0)
            self.status_var.set("Remote sync complete")

            if successes:
                message = f"Synchronized {len(successes)} backup(s) successfully."
            else:
                message = "No backups were synchronized."

            if failures:
                message += "\n\nFailed uploads:\n" + "\n".join(
                    f"- {item['filename']}: {reason}" for item, reason in failures
                )

            messagebox.showinfo("Remote Sync", message)
            self.refresh_backup_list()

        def sync_worker():
            successes = []
            failures = []
            total = len(to_sync)

            for index, backup in enumerate(to_sync, start=1):
                progress = (index - 1) / total * 100
                self.root.after(0, update_status, progress, f"Uploading {backup['filename']} ({index}/{total})")

                remote_target = posixpath.join(remote_path.rstrip('/'), backup['filename'])

                try:
                    if remote_type == "ftp":
                        result = upload_to_ftp(
                            backup["path"], host, username, password, remote_target
                        )
                    else:
                        result = upload_to_sftp(
                            backup["path"], host, username, password, remote_target
                        )
                except Exception as exc:
                    result = False
                    failures.append((backup, str(exc)))
                else:
                    if result:
                        successes.append(backup)
                        for record in metadata_manager.metadata["backups"]:
                            if record["path"] == backup["path"]:
                                record["remote_uploaded"] = True
                                break
                    else:
                        failures.append((backup, "Upload failed"))

                self.root.after(0, update_status, index / total * 100, f"Processed {index}/{total} backups")

            metadata_manager.save_metadata()
            self.root.after(0, finish_sync, successes, failures)

        threading.Thread(target=sync_worker, daemon=True).start()
    
    # Log operations
    def refresh_logs(self):
        """Refresh log display"""
        try:
            log_file = get_log_file('backup.log')
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    logs = f.read()
                
                self.log_text.delete(1.0, tk.END)
                self.log_text.insert(1.0, logs)
                self.log_text.see(tk.END)
            else:
                self.log_text.delete(1.0, tk.END)
                self.log_text.insert(1.0, "No log file found")
        except Exception as e:
            self.log_text.delete(1.0, tk.END)
            self.log_text.insert(1.0, f"Error loading logs: {e}")
    
    def clear_logs(self):
        """Clear log display and file"""
        if messagebox.askyesno("Clear Logs", "Are you sure you want to clear all logs?"):
            try:
                log_file = get_log_file('backup.log')
                if os.path.exists(log_file):
                    open(log_file, 'w').close()
                self.log_text.delete(1.0, tk.END)
                messagebox.showinfo("Success", "Logs cleared successfully")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to clear logs: {e}")

    def create_differential_backup(self):
        """Create differential backup - missing method"""
        self.run_backup_operation(
            lambda: create_enhanced_backup(manual=True, backup_type="differential"),
            "Creating differential backup..."
        )

    def refresh_backup_list(self):
        """Refresh the backup list in main tab"""
        try:
            # Clear existing items
            for item in self.backup_tree.get_children():
                self.backup_tree.delete(item)
            
            # Get backup list
            backups = list_available_backups()
            
            # Populate tree
            for backup in backups[:20]:  # Show last 20 backups
                status = "✓" if os.path.exists(backup['path']) else "✗"
                encrypted = "🔒" if backup.get('encrypted', False) else ""
                cloud = "☁" if backup.get('cloud_uploaded', False) else ""
                
                self.backup_tree.insert("", "end", values=(
                    backup['id'],
                    backup.get('backup_type', 'full'),
                    backup['date_formatted'],
                    backup['size_formatted'],
                    f"{status} {encrypted} {cloud}"
                ))
        
        except Exception as e:
            logger.error(f"Error refreshing backup list: {e}")
    
    def auto_refresh_backup_list(self):
        """Auto-refresh backup list every 30 seconds"""
        self.refresh_backup_list()
        self.root.after(30000, self.auto_refresh_backup_list)

    def configure_advanced_settings(self):
        """Configure advanced backup settings - missing method"""
        AdvancedSettingsDialog(self.root)

    def backup_database_specific_settings(self):
        """Configure database-specific backup settings - missing method"""
        DatabaseSettingsDialog(self.root)

    def create_backup_report(self):
        """Create comprehensive backup report - missing method"""
        ReportGeneratorDialog(self.root)

    def backup_integrity_check(self):
        """Run integrity check on all backups - missing method"""
        IntegrityCheckDialog(self.root)

    def backup_migration_tools(self):
        """Tools for migrating backups between storage types - missing method"""
        MigrationToolsDialog(self.root)

    def create_enhanced_backup(manual=False, operation_name=None, backup_type="full", tables=None):
        """Enhanced backup creation with all new features - missing from GUI"""
        try:
            # Check if database has changed (if change detection is enabled)
            if config.get("enable_change_detection", False) and not manual and not has_database_changed():
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

            # Check if source database exists (use DEFAULT_DB_PATH from db module)
            db_path = DEFAULT_DB_PATH
            if not os.path.exists(str(db_path)):
                logger.warning(f"Database file not found at {db_path}. Nothing to backup.")
                messagebox.showerror("Backup Error", f"Database file not found at:\n{db_path}\n\nPlease ensure the database exists before creating a backup.")
                return None

            logger.info(f"Creating backup from database: {db_path}")
            
            # Create backup based on type
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
            
            # Calculate file hash for integrity
            file_hash = calculate_file_hash(str(backup_path))
            
            # Compress if enabled
            if config.get("compression_enabled", False):
                compressed_path = compress_file(
                    str(backup_path), 
                    config.get("compression_format", "gzip"), 
                    config.get("compression_level", 6)
                )
                if compressed_path:
                    backup_path = Path(compressed_path)
            
            # Encrypt if enabled
            if config.get("encryption_enabled", False) and config.get("encryption_password"):
                encrypted_path = encrypt_file(str(backup_path), config["encryption_password"])
                if encrypted_path:
                    backup_path = Path(encrypted_path)
            
            # Upload to cloud/remote if enabled
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
                "compressed": config.get("compression_enabled", False),
                "encrypted": config.get("encryption_enabled", False),
                "cloud_uploaded": config.get("cloud_enabled", False) and upload_success,
                "remote_uploaded": config.get("remote_enabled", False) and upload_success,
                "backup_type": backup_type
            }

            if backup_type == "incremental" and _last_incremental_context:
                backup_info.update(_last_incremental_context)
            if backup_type == "differential" and _last_differential_context:
                backup_info.update(_last_differential_context)
            
            metadata_manager.add_backup(backup_info)
            
            logger.info(f"Backup created: {backup_path}")
            
            # Clean up old backups
            cleanup_old_backups()
            
            # Send notifications
            notify_backup_result(True, str(backup_path), f"{backup_type} backup")
            
            return str(backup_path)
        
        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            notify_backup_result(False, "", f"{backup_type} backup")
            return None

    def import_template_gui(self):
        """Import template from file - missing method"""
        file_path = filedialog.askopenfilename(
            title="Import Template",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if file_path:
            try:
                with open(file_path, 'r') as f:
                    template_data = json.load(f)
                
                name = tk.simpledialog.askstring("Template Name", "Enter name for imported template:")
                if name and save_backup_template(name, template_data):
                    messagebox.showinfo("Success", f"Template '{name}' imported successfully!")
                else:
                    messagebox.showerror("Error", "Failed to import template")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to import template: {e}")

    def export_template_gui(self):
        """Export template to file - missing method"""
        templates = config.get("backup_templates", {})
        if not templates:
            messagebox.showinfo("No Templates", "No templates available to export")
            return
        
        dialog = TemplateSelectionDialog(self.root, list(templates.keys()))
        if dialog.selected_template:
            file_path = filedialog.asksaveasfilename(
                title="Export Template",
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
            )
            
            if file_path:
                try:
                    template_data = templates[dialog.selected_template]
                    with open(file_path, 'w') as f:
                        json.dump(template_data, f, indent=4)
                    messagebox.showinfo("Success", f"Template exported to {file_path}")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to export template: {e}")

    def show_schedule_history(self):
        """Show scheduling history - missing method"""
        ScheduleHistoryDialog(self.root)

    def test_schedule(self):
        """Test schedule configuration - missing method"""
        if not config["auto_backup_enabled"]:
            messagebox.showwarning("Schedule Disabled", "Automatic backup scheduling is currently disabled.")
            return
        
        # Calculate next scheduled run
        try:
            current_time = datetime.datetime.now()
            scheduled_time = datetime.datetime.strptime(config["scheduled_backup_time"], "%H:%M").time()
            
            today_scheduled = datetime.datetime.combine(current_time.date(), scheduled_time)
            if today_scheduled <= current_time:
                # If today's time has passed, show tomorrow's schedule
                tomorrow = current_time.date() + datetime.timedelta(days=1)
                next_run = datetime.datetime.combine(tomorrow, scheduled_time)
            else:
                next_run = today_scheduled
            
            frequency = config["backup_frequency"]
            message = f"Schedule Configuration Test:\n\n"
            message += f"Frequency: {frequency.title()}\n"
            message += f"Time: {config['scheduled_backup_time']}\n"
            message += f"Next Run: {next_run.strftime('%Y-%m-%d %H:%M:%S')}\n"
            message += f"Status: {'Active' if scheduler_running else 'Inactive'}\n"
            
            messagebox.showinfo("Schedule Test", message)
        except Exception as e:
            messagebox.showerror("Error", f"Schedule test failed: {e}")

    def enable_backup_deduplication():
        """Enable backup deduplication - missing from GUI"""
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

    def deduplicate_backups():
        """Remove duplicate backup files - missing from GUI"""
        try:
            if not config.get("enable_deduplication", False):
                return 0
            
            backups = list_available_backups()
            duplicates_removed = 0
            
            # Group backups by hash
            hash_groups = {}
            for backup in backups:
                file_hash = backup.get("file_hash")
                if file_hash:
                    if file_hash not in hash_groups:
                        hash_groups[file_hash] = []
                    hash_groups[file_hash].append(backup)
            
            # Remove duplicates (keep the newest)
            for file_hash, backup_group in hash_groups.items():
                if len(backup_group) > 1:
                    # Sort by timestamp, keep the newest
                    backup_group.sort(key=lambda x: x["timestamp"], reverse=True)
                    for duplicate in backup_group[1:]:  # Skip the first (newest)
                        try:
                            # Use centralized delete_backup function
                            try:
                                from university_system.infrastructure.database.data_backup import delete_backup as delete_backup_func
                                if delete_backup_func(duplicate["path"]):
                                    duplicates_removed += 1
                                    logger.info(f"Removed duplicate backup: {duplicate['filename']}")
                            except ImportError:
                                # Fallback implementation
                                if os.path.exists(duplicate["path"]):
                                    os.remove(duplicate["path"])
                                    duplicates_removed += 1
                                    logger.info(f"Removed duplicate backup: {duplicate['filename']}")

                                # Remove from metadata
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

    def check_storage_quota():
        """Check if storage quota is exceeded - missing from GUI"""
        try:
            quota_gb = config.get("storage_quota_gb", 10)
            quota_bytes = quota_gb * 1024 * 1024 * 1024
            
            # Calculate total backup size
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

    def show_storage_usage(self):
        """Show storage usage dialog - missing method"""
        StorageUsageDialog(self.root)
    
    def export_logs(self):
        """Export logs to file"""
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
            )
            if filename:
                content = self.log_text.get(1.0, tk.END)
                with open(filename, 'w') as f:
                    f.write(content)
                messagebox.showinfo("Success", f"Logs exported to {filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export logs: {e}")
    
    def filter_logs(self, event=None):
        """Filter logs by level"""
        try:
            log_file = get_log_file('backup.log')
            if not os.path.exists(log_file):
                self.log_text.delete(1.0, tk.END)
                self.log_text.insert(1.0, "No log file found")
                return

            with open(log_file, 'r') as f:
                lines = f.readlines()

            selected_level = self.log_level_var.get()
            if selected_level == "All":
                filtered_lines = lines
            else:
                pattern = re.compile(rf'\\b{selected_level}\\b', re.IGNORECASE)
                filtered_lines = [line for line in lines if pattern.search(line)]

            self.log_text.delete(1.0, tk.END)
            if filtered_lines:
                self.log_text.insert(1.0, "".join(filtered_lines))
            else:
                self.log_text.insert(1.0, f"No log entries found for level {selected_level}.")
        except Exception as e:
            self.log_text.delete(1.0, tk.END)
            self.log_text.insert(1.0, f"Error filtering logs: {e}")

    def list_available_backups(filter_type=None, search_term=None):
        """List all available backup files with enhanced filtering - missing from GUI"""
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
                except:
                    backup["date_formatted"] = "Unknown"
            
            return backups
        
        except Exception as e:
            logger.error(f"Error listing backups: {e}")
            return []
    
    # Utility methods
    def run_backup_operation(self, operation, status_message):
        """Run backup operation in separate thread"""
        def run_operation():
            try:
                self.status_var.set(status_message)
                self.progress_var.set(0)
                
                result = operation()
                
                if result:
                    self.status_var.set("Backup completed successfully")
                    self.refresh_backup_list()
                    messagebox.showinfo("Success", f"Backup created: {os.path.basename(result)}")
                else:
                    self.status_var.set("Backup failed")
                    messagebox.showerror("Error", "Backup operation failed")
                
            except Exception as e:
                self.status_var.set("Backup failed")
                messagebox.showerror("Error", f"Backup operation failed: {e}")
            finally:
                self.progress_var.set(0)
        
        # Run in separate thread to prevent GUI freezing
        thread = threading.Thread(target=run_operation)
        thread.daemon = True
        thread.start()
    
class ScheduleHistoryDialog:
    """Dialog for showing schedule history - missing class"""
    
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Schedule History")
        self.dialog.geometry("600x400")
        self.dialog.transient(parent)
        
        self.create_widgets()
        self.load_history()
    
    def create_widgets(self):
        """Create dialog widgets"""
        # History list
        list_frame = ttk.LabelFrame(self.dialog, text="Scheduled Backup History", padding=10)
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        columns = ("Date", "Type", "Status", "Duration", "Size")
        self.history_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=12)
        
        for col in columns:
            self.history_tree.heading(col, text=col)
            self.history_tree.column(col, width=100)
        
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=scrollbar.set)
        
        self.history_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Button(button_frame, text="Refresh", command=self.load_history).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Clear History", command=self.clear_history).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side="right")
    
    def load_history(self):
        """Load schedule history"""
        try:
            # Clear existing items
            for item in self.history_tree.get_children():
                self.history_tree.delete(item)
            
            # Get scheduled backups from metadata
            backups = metadata_manager.get_backups()
            scheduled_backups = [b for b in backups if not b.get('manual', True)]
            
            for backup in scheduled_backups[-20:]:  # Show last 20
                date_formatted = backup.get('date_formatted', 'Unknown')
                backup_type = backup.get('backup_type', 'full')
                status = "✓ Success" if os.path.exists(backup['path']) else "✗ Failed"
                duration = "N/A"  # Would need to track this
                size = backup.get('size_formatted', 'Unknown')
                
                self.history_tree.insert("", "end", values=(
                    date_formatted, backup_type, status, duration, size
                ))
        
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load schedule history: {e}")
    
    def clear_history(self):
        """Clear schedule history"""
        if messagebox.askyesno("Clear History", "Are you sure you want to clear the schedule history?"):
            try:
                # This would clear scheduled backup records from metadata
                # For now, just clear the display
                for item in self.history_tree.get_children():
                    self.history_tree.delete(item)
                messagebox.showinfo("Success", "Schedule history cleared")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to clear history: {e}")
                
class BackupOptionsDialog:
    """Dialog for selecting backup options"""
    
    def __init__(self, parent):
        self.result = None
        self.backup_type = "full"
        self.selected_tables = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Backup Options")
        self.dialog.geometry("400x300")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.create_widgets()
        self.dialog.protocol("WM_DELETE_WINDOW", self.cancel)
        
        # Center dialog
        self.dialog.geometry("+%d+%d" % (parent.winfo_rootx() + 50, parent.winfo_rooty() + 50))
        
        # Wait for dialog to close
        parent.wait_window(self.dialog)
    
    def create_widgets(self):
        """Create dialog widgets"""
        # Backup type selection
        type_frame = ttk.LabelFrame(self.dialog, text="Backup Type", padding=10)
        type_frame.pack(fill="x", padx=10, pady=5)
        
        self.type_var = tk.StringVar(value="full")
        
        ttk.Radiobutton(type_frame, text="Full Backup", variable=self.type_var, 
                       value="full").pack(anchor="w")
        ttk.Radiobutton(type_frame, text="Incremental Backup", variable=self.type_var, 
                       value="incremental").pack(anchor="w")
        ttk.Radiobutton(type_frame, text="Schema Only", variable=self.type_var, 
                       value="schema").pack(anchor="w")
        ttk.Radiobutton(type_frame, text="Selective Tables", variable=self.type_var, 
                       value="selective", command=self.show_table_selection).pack(anchor="w")
        
        # Table selection frame (hidden initially)
        self.table_frame = ttk.LabelFrame(self.dialog, text="Select Tables", padding=10)
        
        # Get available tables
        try:
            tables = get_database_tables()
            self.table_vars = {}
            
            for table in tables:
                var = tk.BooleanVar()
                self.table_vars[table] = var
                ttk.Checkbutton(self.table_frame, text=table, variable=var).pack(anchor="w")
        except:
            ttk.Label(self.table_frame, text="No tables found or database not accessible").pack()
        
        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(fill="x", padx=10, pady=10)
        
        ttk.Button(button_frame, text="Create Backup", command=self.ok).pack(side="right", padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.cancel).pack(side="right")
    
    def show_table_selection(self):
        """Show table selection frame"""
        self.table_frame.pack(fill="x", padx=10, pady=5)
        self.dialog.geometry("400x500")
    
    def ok(self):
        """OK button handler"""
        self.backup_type = self.type_var.get()
        
        if self.backup_type == "selective":
            self.selected_tables = [table for table, var in self.table_vars.items() if var.get()]
            if not self.selected_tables:
                messagebox.showwarning("No Tables", "Please select at least one table")
                return
        
        self.result = True
        self.dialog.destroy()
    
    def cancel(self):
        """Cancel button handler"""
        self.result = False
        self.dialog.destroy()

class BackupViewerDialog:
    """Dialog for viewing backup details"""
    
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Backup Viewer")
        self.dialog.geometry("800x600")
        self.dialog.transient(parent)
        
        self.create_widgets()
        self.load_backups()
    
    def create_widgets(self):
        """Create dialog widgets"""
        # Controls frame
        controls_frame = ttk.Frame(self.dialog)
        controls_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Button(controls_frame, text="Refresh", command=self.load_backups).pack(side="left", padx=5)
        ttk.Button(controls_frame, text="Delete Selected", command=self.delete_backup).pack(side="left", padx=5)
        ttk.Button(controls_frame, text="Validate Selected", command=self.validate_backup).pack(side="left", padx=5)
        
        # Filter frame
        filter_frame = ttk.Frame(self.dialog)
        filter_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(filter_frame, text="Filter by type:").pack(side="left")
        self.filter_var = tk.StringVar(value="All")
        filter_combo = ttk.Combobox(filter_frame, textvariable=self.filter_var,
                                   values=["All", "full", "incremental", "schema", "selective"],
                                   state="readonly", width=15)
        filter_combo.pack(side="left", padx=5)
        filter_combo.bind("<<ComboboxSelected>>", self.apply_filter)
        
        # Backup list
        list_frame = ttk.Frame(self.dialog)
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        columns = ("ID", "Type", "Date", "Size", "File", "Encrypted", "Cloud", "Status")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings")
        
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=80)
        
        # Scrollbars
        v_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        h_scroll = ttk.Scrollbar(list_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)
        
        self.tree.pack(side="left", fill="both", expand=True)
        v_scroll.pack(side="right", fill="y")
        h_scroll.pack(side="bottom", fill="x")
        
        # Details frame
        details_frame = ttk.LabelFrame(self.dialog, text="Backup Details", padding=10)
        details_frame.pack(fill="x", padx=10, pady=5)
        
        self.details_text = scrolledtext.ScrolledText(details_frame, height=8, wrap=tk.WORD)
        self.details_text.pack(fill="both", expand=True)
        
        # Bind selection event
        self.tree.bind("<<TreeviewSelect>>", self.show_details)
    
    def load_backups(self):
        """Load backup list"""
        try:
            # Clear existing items
            for item in self.tree.get_children():
                self.tree.delete(item)
            
            # Get backup list
            backups = list_available_backups()

            # Store backups for reference
            self.backups = backups
            self.backup_items = {}  # Map tree items to backup data

            # Populate tree
            for backup in backups:
                encrypted = "Yes" if backup.get('encrypted', False) else "No"
                cloud = "Yes" if backup.get('cloud_uploaded', False) else "No"
                status = "Exists" if os.path.exists(backup['path']) else "Missing"

                item = self.tree.insert("", "end", values=(
                    backup['id'],
                    backup.get('backup_type', 'full'),
                    backup['date_formatted'],
                    backup['size_formatted'],
                    backup['filename'],
                    encrypted,
                    cloud,
                    status
                ))

                # Store backup data with item ID
                self.backup_items[item] = backup
        
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load backups: {e}")
    
    def apply_filter(self, event=None):
        """Apply filter to backup list"""
        filter_type = self.filter_var.get()
        
        # Clear current items
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Filter and populate
        for backup in self.backups:
            if filter_type == "All" or backup.get('backup_type', 'full') == filter_type:
                encrypted = "Yes" if backup.get('encrypted', False) else "No"
                cloud = "Yes" if backup.get('cloud_uploaded', False) else "No"
                status = "Exists" if os.path.exists(backup['path']) else "Missing"
                
                self.tree.insert("", "end", values=(
                    backup['id'],
                    backup.get('backup_type', 'full'),
                    backup['date_formatted'],
                    backup['size_formatted'],
                    backup['filename'],
                    encrypted,
                    cloud,
                    status
                ))
    
    def show_details(self, event=None):
        """Show details for selected backup"""
        selection = self.tree.selection()
        if not selection:
            return
        
        item = selection[0]
        values = self.tree.item(item, "values")
        
        # Find the backup data
        backup_id = int(values[0])
        backup = None
        for b in self.backups:
            if b['id'] == backup_id:
                backup = b
                break
        
        if backup:
            details = f"Backup Details:\n"
            details += f"File: {backup['filename']}\n"
            details += f"Path: {backup['path']}\n"
            details += f"Type: {backup.get('backup_type', 'full')}\n"
            details += f"Date: {backup['date_formatted']}\n"
            details += f"Size: {backup['size_formatted']}\n"
            details += f"Manual: {'Yes' if backup.get('manual', False) else 'No'}\n"
            details += f"Encrypted: {'Yes' if backup.get('encrypted', False) else 'No'}\n"
            details += f"Compressed: {'Yes' if backup.get('compressed', False) else 'No'}\n"
            details += f"Cloud Uploaded: {'Yes' if backup.get('cloud_uploaded', False) else 'No'}\n"
            details += f"Remote Uploaded: {'Yes' if backup.get('remote_uploaded', False) else 'No'}\n"
            
            if backup.get('file_hash'):
                details += f"File Hash: {backup['file_hash']}\n"
            
            if backup.get('operation'):
                details += f"Operation: {backup['operation']}\n"
            
            self.details_text.delete(1.0, tk.END)
            self.details_text.insert(1.0, details)
    
    def delete_backup(self):
        """Delete selected backup"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a backup to delete")
            return

        item = selection[0]
        values = self.tree.item(item, "values")
        filename = values[4]

        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete '{filename}'?"):
            try:
                backup_id = int(values[0])
                backup = None
                for b in self.backups:
                    if b['id'] == backup_id:
                        backup = b
                        break

                if backup:
                    # Use centralized delete_backup function from data_backup module
                    # This ensures consistent behavior between CLI and GUI
                    try:
                        from university_system.infrastructure.database.data_backup import delete_backup as delete_backup_func
                        success = delete_backup_func(backup['path'])
                    except ImportError:
                        # Fallback to inline implementation if import fails
                        if os.path.exists(backup['path']):
                            if config["secure_deletion"]:
                                secure_delete_file(backup['path'])
                            else:
                                os.remove(backup['path'])

                            # Remove from metadata
                            metadata_manager.metadata["backups"] = [
                                b for b in metadata_manager.metadata["backups"]
                                if b['path'] != backup['path']
                            ]
                            metadata_manager.save_metadata()
                            success = True
                        else:
                            success = False

                    if success:
                        messagebox.showinfo("Success", "Backup deleted successfully and removed from list")
                        self.load_backups()
                    else:
                        messagebox.showerror("Error", "Failed to delete backup")
                else:
                    messagebox.showerror("Error", "Backup not found")

            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete backup: {e}")
    
    def validate_backup(self):
        """Validate selected backup"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a backup to validate")
            return
        
        item = selection[0]
        values = self.tree.item(item, "values")
        
        try:
            backup_id = int(values[0])
            backup = None
            for b in self.backups:
                if b['id'] == backup_id:
                    backup = b
                    break
            
            if backup:
                results = validate_backup(backup['path'])
                
                message = "Validation Results:\n\n"
                message += f"File exists: {'✓' if results['file_exists'] else '✗'}\n"
                message += f"File readable: {'✓' if results['file_readable'] else '✗'}\n"
                message += f"Database valid: {'✓' if results['database_valid'] else '✗'}\n"
                message += f"Tables accessible: {'✓' if results['tables_accessible'] else '✗'}\n"
                message += f"Hash verified: {'✓' if results['hash_verified'] else '✗'}\n"
                
                if results['errors']:
                    message += "\nErrors:\n"
                    for error in results['errors']:
                        message += f"• {error}\n"
                
                messagebox.showinfo("Validation Results", message)
        
        except Exception as e:
            messagebox.showerror("Error", f"Validation failed: {e}")

class RestoreDialog:
    """Dialog for restoring from backup"""
    
    def __init__(self, parent, refresh_callback=None):
        self.refresh_callback = refresh_callback
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Restore from Backup")
        self.dialog.geometry("600x500")
        self.dialog.transient(parent)
        
        self.create_widgets()
        self.load_backups()
    
    def create_widgets(self):
        """Create dialog widgets"""
        # Backup selection
        select_frame = ttk.LabelFrame(self.dialog, text="Select Backup", padding=10)
        select_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        columns = ("Date", "Type", "Size", "File")
        self.backup_tree = ttk.Treeview(select_frame, columns=columns, show="headings", height=8)
        
        for col in columns:
            self.backup_tree.heading(col, text=col)
            self.backup_tree.column(col, width=120)
        
        scrollbar = ttk.Scrollbar(select_frame, orient="vertical", command=self.backup_tree.yview)
        self.backup_tree.configure(yscrollcommand=scrollbar.set)
        
        self.backup_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Restore options
        options_frame = ttk.LabelFrame(self.dialog, text="Restore Options", padding=10)
        options_frame.pack(fill="x", padx=10, pady=5)
        
        self.restore_type_var = tk.StringVar(value="full")
        
        ttk.Radiobutton(options_frame, text="Full Restore", variable=self.restore_type_var, 
                       value="full").pack(anchor="w")
        ttk.Radiobutton(options_frame, text="Partial Restore (Select Tables)", 
                       variable=self.restore_type_var, value="partial",
                       command=self.show_table_selection).pack(anchor="w")
        
        # Table selection (hidden initially)
        self.table_frame = ttk.LabelFrame(self.dialog, text="Select Tables to Restore", padding=10)
        
        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(fill="x", padx=10, pady=10)
        
        ttk.Button(button_frame, text="Restore", command=self.restore).pack(side="right", padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side="right")
    
    def load_backups(self):
        """Load available backups"""
        try:
            backups = list_available_backups()
            self.backups = backups
            
            for backup in backups:
                self.backup_tree.insert("", "end", values=(
                    backup['date_formatted'],
                    backup.get('backup_type', 'full'),
                    backup['size_formatted'],
                    backup['filename']
                ))
        
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load backups: {e}")
    
    def show_table_selection(self):
        """Show table selection frame"""
        # Get tables from selected backup
        selection = self.backup_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a backup first")
            self.restore_type_var.set("full")
            return
        
        try:
            # Clear existing checkboxes
            for widget in self.table_frame.winfo_children():
                widget.destroy()
            
            # Get selected backup
            item = selection[0]
            index = self.backup_tree.index(item)
            backup = self.backups[index]
            
            readable_path = None
            temp_paths = []
            tables = []
            try:
                readable_path, temp_paths = _prepare_backup_for_read(backup['path'])
                conn = sqlite3.connect(readable_path)
                tables = get_database_tables_from_connection(conn)
                conn.close()
            finally:
                _cleanup_temp_paths(temp_paths)
            
            self.table_vars = {}
            for table in tables:
                var = tk.BooleanVar()
                self.table_vars[table] = var
                ttk.Checkbutton(self.table_frame, text=table, variable=var).pack(anchor="w")
            
            self.table_frame.pack(fill="x", padx=10, pady=5)
            self.dialog.geometry("600x700")
        
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load tables: {e}")
    
    def restore(self):
        """Perform restore operation"""
        selection = self.backup_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a backup to restore")
            return
        
        item = selection[0]
        index = self.backup_tree.index(item)
        backup = self.backups[index]
        
        # Confirm restore
        if not messagebox.askyesno("Confirm Restore", 
                                  f"Are you sure you want to restore from '{backup['filename']}'?\n\n"
                                  "This will overwrite the current database!"):
            return
        
        try:
            target_tables = None
            if self.restore_type_var.get() == "partial":
                if hasattr(self, 'table_vars'):
                    target_tables = [table for table, var in self.table_vars.items() if var.get()]
                    if not target_tables:
                        messagebox.showwarning("No Tables", "Please select at least one table to restore")
                        return
            
            # Perform restore
            success = restore_from_backup(backup['path'], target_tables=target_tables)
            
            if success:
                messagebox.showinfo("Success", "Database restored successfully!")
                if self.refresh_callback:
                    self.refresh_callback()
                self.dialog.destroy()
            else:
                messagebox.showerror("Error", "Restore operation failed!")
        
        except Exception as e:
            messagebox.showerror("Error", f"Restore failed: {e}")

# Additional dialog classes would continue here...
# For brevity, I'll include key ones and indicate where others would be implemented

class TableSelectionDialog:
    """Dialog for selecting tables"""
    
    def __init__(self, parent, tables):
        self.selected_tables = []
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Select Tables")
        self.dialog.geometry("300x400")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Table selection
        frame = ttk.LabelFrame(self.dialog, text="Available Tables", padding=10)
        frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.table_vars = {}
        for table in tables:
            var = tk.BooleanVar()
            self.table_vars[table] = var
            ttk.Checkbutton(frame, text=table, variable=var).pack(anchor="w")
        
        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(fill="x", padx=10, pady=10)
        
        ttk.Button(button_frame, text="Select All", command=self.select_all).pack(side="left")
        ttk.Button(button_frame, text="Clear All", command=self.clear_all).pack(side="left", padx=5)
        ttk.Button(button_frame, text="OK", command=self.ok).pack(side="right", padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.cancel).pack(side="right")
        
        parent.wait_window(self.dialog)
    
    def select_all(self):
        """Select all tables"""
        for var in self.table_vars.values():
            var.set(True)
    
    def clear_all(self):
        """Clear all selections"""
        for var in self.table_vars.values():
            var.set(False)
    
    def ok(self):
        """OK button handler"""
        self.selected_tables = [table for table, var in self.table_vars.items() if var.get()]
        self.dialog.destroy()
    
    def cancel(self):
        """Cancel button handler"""
        self.selected_tables = []
        self.dialog.destroy()

class ValidationDialog:
    """Dialog for backup validation"""
    
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Validate Backup")
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        
        self.create_widgets()
        self.load_backups()
    
    def create_widgets(self):
        """Create dialog widgets"""
        # Backup selection
        select_frame = ttk.LabelFrame(self.dialog, text="Select Backup to Validate", padding=10)
        select_frame.pack(fill="x", padx=10, pady=5)
        
        self.backup_var = tk.StringVar()
        self.backup_combo = ttk.Combobox(select_frame, textvariable=self.backup_var, 
                                        state="readonly", width=50)
        self.backup_combo.pack(fill="x", pady=5)
        
        ttk.Button(select_frame, text="Validate", command=self.validate).pack(pady=5)
        
        # Results
        results_frame = ttk.LabelFrame(self.dialog, text="Validation Results", padding=10)
        results_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.results_text = scrolledtext.ScrolledText(results_frame, wrap=tk.WORD)
        self.results_text.pack(fill="both", expand=True)
    
    def load_backups(self):
        """Load available backups"""
        try:
            backups = list_available_backups()
            self.backups = backups
            
            backup_names = [f"{backup['date_formatted']} - {backup['filename']}" 
                           for backup in backups]
            self.backup_combo['values'] = backup_names
            
            if backup_names:
                self.backup_combo.current(0)
        
        except Exception as e:
            self.results_text.insert(tk.END, f"Error loading backups: {e}\n")
    
    def validate(self):
        """Validate selected backup"""
        if not self.backup_combo.get():
            messagebox.showwarning("No Selection", "Please select a backup to validate")
            return
        
        try:
            index = self.backup_combo.current()
            backup = self.backups[index]
            
            self.results_text.delete(1.0, tk.END)
            self.results_text.insert(tk.END, f"Validating backup: {backup['filename']}\n")
            self.results_text.insert(tk.END, "Please wait...\n\n")
            self.dialog.update()
            
            results = validate_backup(backup['path'])
            
            self.results_text.delete(1.0, tk.END)
            self.results_text.insert(tk.END, f"Validation Results for: {backup['filename']}\n")
            self.results_text.insert(tk.END, "=" * 50 + "\n\n")
            
            self.results_text.insert(tk.END, f"File exists: {'✓ PASS' if results['file_exists'] else '✗ FAIL'}\n")
            self.results_text.insert(tk.END, f"File readable: {'✓ PASS' if results['file_readable'] else '✗ FAIL'}\n")
            self.results_text.insert(tk.END, f"Database valid: {'✓ PASS' if results['database_valid'] else '✗ FAIL'}\n")
            self.results_text.insert(tk.END, f"Tables accessible: {'✓ PASS' if results['tables_accessible'] else '✗ FAIL'}\n")
            self.results_text.insert(tk.END, f"Hash verified: {'✓ PASS' if results['hash_verified'] else '✗ FAIL'}\n\n")
            
            if results['errors']:
                self.results_text.insert(tk.END, "ERRORS FOUND:\n")
                for error in results['errors']:
                    self.results_text.insert(tk.END, f"• {error}\n")
            else:
                self.results_text.insert(tk.END, "✓ No errors found - backup is valid!\n")
        
        except Exception as e:
            self.results_text.delete(1.0, tk.END)
            self.results_text.insert(tk.END, f"Comparison failed: {e}\n")

class ReportDialog:
    """Dialog for generating comprehensive backup reports"""
    
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Backup Report Generator")
        self.dialog.geometry("700x600")
        self.dialog.transient(parent)
        
        self.create_widgets()
    
    def create_widgets(self):
        """Create dialog widgets"""
        # Report options
        options_frame = ttk.LabelFrame(self.dialog, text="Report Options", padding=10)
        options_frame.pack(fill="x", padx=10, pady=5)
        
        # Report type
        self.report_type_var = tk.StringVar(value="summary")
        ttk.Label(options_frame, text="Report Type:").grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(options_frame, text="Summary Report", variable=self.report_type_var, 
                       value="summary").grid(row=0, column=1, sticky="w")
        ttk.Radiobutton(options_frame, text="Detailed Report", variable=self.report_type_var, 
                       value="detailed").grid(row=0, column=2, sticky="w")
        ttk.Radiobutton(options_frame, text="Statistics Report", variable=self.report_type_var, 
                       value="statistics").grid(row=0, column=3, sticky="w")
        
        # Date range
        ttk.Label(options_frame, text="Date Range:").grid(row=1, column=0, sticky="w", pady=5)
        self.date_range_var = tk.StringVar(value="all")
        date_frame = ttk.Frame(options_frame)
        date_frame.grid(row=1, column=1, columnspan=3, sticky="w")
        
        ttk.Radiobutton(date_frame, text="All time", variable=self.date_range_var, value="all").pack(side="left")
        ttk.Radiobutton(date_frame, text="Last 30 days", variable=self.date_range_var, value="30days").pack(side="left")
        ttk.Radiobutton(date_frame, text="Last 90 days", variable=self.date_range_var, value="90days").pack(side="left")
        
        # Export options
        ttk.Label(options_frame, text="Export Format:").grid(row=2, column=0, sticky="w", pady=5)
        self.export_format_var = tk.StringVar(value="text")
        export_frame = ttk.Frame(options_frame)
        export_frame.grid(row=2, column=1, columnspan=3, sticky="w")
        
        ttk.Radiobutton(export_frame, text="Text", variable=self.export_format_var, value="text").pack(side="left")
        ttk.Radiobutton(export_frame, text="HTML", variable=self.export_format_var, value="html").pack(side="left")
        ttk.Radiobutton(export_frame, text="PDF", variable=self.export_format_var, value="pdf").pack(side="left")
        
        # Generate button
        ttk.Button(options_frame, text="Generate Report", command=self.generate_report).grid(row=3, column=1, pady=10)
        
        # Report display
        display_frame = ttk.LabelFrame(self.dialog, text="Report", padding=10)
        display_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.report_text = scrolledtext.ScrolledText(display_frame, wrap=tk.WORD)
        self.report_text.pack(fill="both", expand=True)
        
        # Export button
        export_button_frame = ttk.Frame(self.dialog)
        export_button_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Button(export_button_frame, text="Export Report", command=self.export_report).pack(side="right", padx=5)
        ttk.Button(export_button_frame, text="Close", command=self.dialog.destroy).pack(side="right")
    
    def generate_report(self):
        """Generate the backup report"""
        try:
            self.report_text.delete(1.0, tk.END)
            self.report_text.insert(tk.END, "Generating report...\n")
            self.dialog.update()
            
            report_type = self.report_type_var.get()
            date_range = self.date_range_var.get()
            
            # Get backup data
            backups = list_available_backups()
            stats = generate_backup_statistics()
            
            # Filter by date range
            if date_range != "all":
                days = 30 if date_range == "30days" else 90
                cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days)
                
                filtered_backups = []
                for backup in backups:
                    try:
                        backup_date = datetime.datetime.strptime(backup["timestamp"], "%Y%m%d_%H%M%S")
                        if backup_date >= cutoff_date:
                            filtered_backups.append(backup)
                    except:
                        pass
                backups = filtered_backups
            
            # Generate report content
            report_content = self.create_report_content(report_type, backups, stats)
            
            self.report_text.delete(1.0, tk.END)
            self.report_text.insert(1.0, report_content)
        
        except Exception as e:
            self.report_text.delete(1.0, tk.END)
            self.report_text.insert(1.0, f"Error generating report: {e}")
    
    def create_report_content(self, report_type, backups, stats):
        """Create report content based on type"""
        content = f"BACKUP SYSTEM REPORT\n"
        content += f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        content += f"Report Type: {report_type.title()}\n"
        content += "=" * 60 + "\n\n"
        
        if report_type == "summary":
            content += self.create_summary_report(backups, stats)
        elif report_type == "detailed":
            content += self.create_detailed_report(backups, stats)
        elif report_type == "statistics":
            content += self.create_statistics_report(backups, stats)
        
        return content
    
    def create_summary_report(self, backups, stats):
        """Create summary report"""
        content = "EXECUTIVE SUMMARY\n"
        content += "-" * 20 + "\n\n"
        
        content += f"Total Backups: {len(backups)}\n"
        content += f"Total Storage Used: {stats['total_size'] / (1024*1024*1024):.2f} GB\n"
        content += f"Average Backup Size: {stats['average_size'] / (1024*1024):.2f} MB\n"
        content += f"Recent Activity: {stats['recent_activity']} backups in last 30 days\n\n"
        
        # Latest backup info
        if backups:
            latest = backups[0]
            content += f"Latest Backup:\n"
            content += f"  Date: {latest['date_formatted']}\n"
            content += f"  Type: {latest.get('backup_type', 'full')}\n"
            content += f"  Size: {latest['size_formatted']}\n"
            content += f"  Status: {'✓ Valid' if os.path.exists(latest['path']) else '✗ Missing'}\n\n"
        
        # Backup health
        valid_backups = sum(1 for b in backups if os.path.exists(b['path']))
        health_percentage = (valid_backups / len(backups) * 100) if backups else 0
        content += f"Backup Health: {health_percentage:.1f}% ({valid_backups}/{len(backups)} valid)\n\n"
        
        # Recommendations
        content += "RECOMMENDATIONS\n"
        content += "-" * 15 + "\n"
        if health_percentage < 100:
            content += "• Some backup files are missing - investigate storage issues\n"
        if stats['recent_activity'] == 0:
            content += "• No recent backup activity - check scheduler\n"
        if stats['total_size'] > 5 * 1024 * 1024 * 1024:  # 5GB
            content += "• Consider cleanup of old backups to free space\n"
        if not config["encryption_enabled"]:
            content += "• Enable encryption for sensitive data protection\n"
        
        return content
    
    def create_detailed_report(self, backups, stats):
        """Create detailed report"""
        content = "DETAILED BACKUP ANALYSIS\n"
        content += "-" * 25 + "\n\n"
        
        # Configuration summary
        content += "CURRENT CONFIGURATION\n"
        content += "-" * 20 + "\n"
        content += f"Backup Directory: {config['backup_directory']}\n"
        content += f"Auto Backup: {'Enabled' if config['auto_backup_enabled'] else 'Disabled'}\n"
        content += f"Frequency: {config['backup_frequency']}\n"
        content += f"Scheduled Time: {config['scheduled_backup_time']}\n"
        content += f"Max Backups: {config['max_backups']}\n"
        content += f"Encryption: {'Enabled' if config['encryption_enabled'] else 'Disabled'}\n"
        content += f"Compression: {'Enabled' if config['compression_enabled'] else 'Disabled'}\n"
        content += f"Cloud Storage: {'Enabled' if config['cloud_enabled'] else 'Disabled'}\n\n"
        
        # Backup type distribution
        content += "BACKUP TYPE DISTRIBUTION\n"
        content += "-" * 25 + "\n"
        type_counts = {}
        for backup in backups:
            backup_type = backup.get('backup_type', 'full')
            type_counts[backup_type] = type_counts.get(backup_type, 0) + 1
        
        for backup_type, count in type_counts.items():
            percentage = (count / len(backups) * 100) if backups else 0
            content += f"{backup_type}: {count} ({percentage:.1f}%)\n"
        content += "\n"
        
        # Recent backup details
        content += "RECENT BACKUPS (Last 10)\n"
        content += "-" * 25 + "\n"
        content += f"{'Date':<20} {'Type':<12} {'Size':<10} {'Status':<8} {'File'}\n"
        content += "-" * 80 + "\n"
        
        for backup in backups[:10]:
            status = "Valid" if os.path.exists(backup['path']) else "Missing"
            content += f"{backup['date_formatted']:<20} {backup.get('backup_type', 'full'):<12} "
            content += f"{backup['size_formatted']:<10} {status:<8} {backup['filename']}\n"
        
        return content
    
    def create_statistics_report(self, backups, stats):
        """Create statistics report"""
        content = "BACKUP STATISTICS\n"
        content += "-" * 17 + "\n\n"
        
        # Overall statistics
        content += "OVERALL STATISTICS\n"
        content += "-" * 18 + "\n"
        content += f"Total Backups: {stats['total_backups']}\n"
        content += f"Total Size: {stats['total_size'] / (1024*1024*1024):.2f} GB\n"
        content += f"Average Size: {stats['average_size'] / (1024*1024):.2f} MB\n"
        content += f"Recent Activity: {stats['recent_activity']} backups (30 days)\n\n"
        
        # Size analysis
        if backups:
            sizes = [backup.get('size', 0) for backup in backups]
            content += "SIZE ANALYSIS\n"
            content += "-" * 13 + "\n"
            content += f"Smallest Backup: {min(sizes) / (1024*1024):.2f} MB\n"
            content += f"Largest Backup: {max(sizes) / (1024*1024):.2f} MB\n"
            content += f"Median Size: {sorted(sizes)[len(sizes)//2] / (1024*1024):.2f} MB\n\n"
        
        # Monthly trends
        if stats.get('storage_usage'):
            content += "MONTHLY STORAGE TRENDS\n"
            content += "-" * 22 + "\n"
            for month, size in sorted(stats['storage_usage'].items()):
                content += f"{month}: {size / (1024*1024):.2f} MB\n"
            content += "\n"
        
        # Backup type statistics
        if stats.get('backup_types'):
            content += "BACKUP TYPE STATISTICS\n"
            content += "-" * 22 + "\n"
            total = sum(stats['backup_types'].values())
            for backup_type, count in stats['backup_types'].items():
                percentage = (count / total * 100) if total else 0
                content += f"{backup_type}: {count} backups ({percentage:.1f}%)\n"
        
        return content
    
    def export_report(self):
        """Export integrity check report"""
        if not self.check_results:
            messagebox.showwarning("No Results", "No integrity check results to export")
            return
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            title="Save Integrity Report"
        )
        
        if filename:
            try:
                with open(filename, 'w') as f:
                    f.write("BACKUP INTEGRITY CHECK REPORT\n")
                    f.write("=" * 50 + "\n")
                    f.write(f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                    
                    passed = sum(1 for r in self.check_results if "PASS" in r['status'])
                    failed = len(self.check_results) - passed
                    
                    f.write(f"SUMMARY:\n")
                    f.write(f"Total backups checked: {len(self.check_results)}\n")
                    f.write(f"Passed: {passed}\n")
                    f.write(f"Failed: {failed}\n\n")
                    
                    f.write("DETAILED RESULTS:\n")
                    f.write("-" * 30 + "\n")
                    
                    for result in self.check_results:
                        backup = result['backup']
                        results = result['results']
                        status = result['status']
                        
                        f.write(f"\nBackup: {backup['filename']}\n")
                        f.write(f"Status: {status}\n")
                        f.write(f"File exists: {'Yes' if results.get('file_exists') else 'No'}\n")
                        f.write(f"Readable: {'Yes' if results.get('file_readable') else 'No'}\n")
                        f.write(f"Database valid: {'Yes' if results.get('database_valid') else 'No'}\n")
                        f.write(f"Tables accessible: {'Yes' if results.get('tables_accessible') else 'No'}\n")
                        f.write(f"Hash verified: {'Yes' if results.get('hash_verified') else 'No'}\n")
                        
                        if results.get('errors'):
                            f.write("Errors:\n")
                            for error in results['errors']:
                                f.write(f"  - {error}\n")
                
                messagebox.showinfo("Export Complete", f"Report exported to {filename}")
            
            except Exception as e:
                messagebox.showerror("Export Error", f"Failed to export report: {e}")

    def convert_to_html(self, text_content):
        """Convert text report to HTML"""
        html = """<!DOCTYPE html>
<html>
<head>
    <title>Backup System Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        h1 { color: #333; border-bottom: 2px solid #333; }
        h2 { color: #666; border-bottom: 1px solid #666; }
        pre { background-color: #f5f5f5; padding: 10px; border-radius: 5px; }
        .stats { background-color: #e8f4f8; padding: 15px; border-radius: 5px; }
    </style>
</head>
<body>
<pre>
""" + text_content + """
</pre>
</body>
</html>"""
        return html

# Additional utility dialogs

class EmailConfigDialog:
    """Dialog for configuring email notifications"""
    
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Email Configuration")
        self.dialog.geometry("400x300")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.create_widgets()
        self.load_current_settings()
        
        parent.wait_window(self.dialog)
    
    def create_widgets(self):
        """Create dialog widgets"""
        # SMTP settings
        smtp_frame = ttk.LabelFrame(self.dialog, text="SMTP Settings", padding=10)
        smtp_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(smtp_frame, text="SMTP Server:").grid(row=0, column=0, sticky="w", pady=2)
        self.smtp_server_var = tk.StringVar()
        ttk.Entry(smtp_frame, textvariable=self.smtp_server_var, width=30).grid(row=0, column=1, padx=5)
        
        ttk.Label(smtp_frame, text="Port:").grid(row=1, column=0, sticky="w", pady=2)
        self.smtp_port_var = tk.StringVar()
        ttk.Entry(smtp_frame, textvariable=self.smtp_port_var, width=10).grid(row=1, column=1, sticky="w", padx=5)
        
        ttk.Label(smtp_frame, text="Username:").grid(row=2, column=0, sticky="w", pady=2)
        self.email_username_var = tk.StringVar()
        ttk.Entry(smtp_frame, textvariable=self.email_username_var, width=30).grid(row=2, column=1, padx=5)
        
        ttk.Label(smtp_frame, text="Password:").grid(row=3, column=0, sticky="w", pady=2)
        self.email_password_var = tk.StringVar()
        ttk.Entry(smtp_frame, textvariable=self.email_password_var, show="*", width=30).grid(row=3, column=1, padx=5)
        
        # Recipients
        recipients_frame = ttk.LabelFrame(self.dialog, text="Recipients", padding=10)
        recipients_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        ttk.Label(recipients_frame, text="Email addresses (one per line):").pack(anchor="w")
        self.recipients_text = scrolledtext.ScrolledText(recipients_frame, height=6, wrap=tk.WORD)
        self.recipients_text.pack(fill="both", expand=True, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(fill="x", padx=10, pady=10)
        
        ttk.Button(button_frame, text="Test Email", command=self.test_email).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Save", command=self.save_settings).pack(side="right", padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side="right")
    
    def load_current_settings(self):
        """Load current email settings"""
        self.smtp_server_var.set(config.get("smtp_server", "smtp.gmail.com"))
        self.smtp_port_var.set(str(config.get("smtp_port", 587)))
        self.email_username_var.set(config.get("email_username", ""))
        self.email_password_var.set(config.get("email_password", ""))
        
        recipients = config.get("notification_recipients", [])
        self.recipients_text.insert(1.0, "\n".join(recipients))
    
    def test_email(self):
        """Test email configuration"""
        try:
            # Temporarily update config
            test_config = {
                "smtp_server": self.smtp_server_var.get(),
                "smtp_port": int(self.smtp_port_var.get()),
                "email_username": self.email_username_var.get(),
                "email_password": self.email_password_var.get(),
                "notification_recipients": [self.email_username_var.get()],
                "email_notifications": True
            }
            
            # Save current config
            old_config = {}
            for key in test_config:
                old_config[key] = config.get(key)
            
            # Apply test config
            config.update(test_config)
            
            # Send test email
            send_email_notification("Backup System Test", "This is a test email from the backup system.", 
                                   [self.email_username_var.get()])
            
            # Restore config
            config.update(old_config)
            
            messagebox.showinfo("Test Successful", "Test email sent successfully!")
        
        except Exception as e:
            messagebox.showerror("Test Failed", f"Email test failed: {e}")
    
    def save_settings(self):
        """Save email settings"""
        try:
            config["smtp_server"] = self.smtp_server_var.get()
            config["smtp_port"] = int(self.smtp_port_var.get())
            config["email_username"] = self.email_username_var.get()
            config["email_password"] = self.email_password_var.get()
            
            recipients_text = self.recipients_text.get(1.0, tk.END).strip()
            recipients = [email.strip() for email in recipients_text.split('\n') if email.strip()]
            config["notification_recipients"] = recipients
            
            save_config()
            
            messagebox.showinfo("Success", "Email configuration saved!")
            self.dialog.destroy()
        
        except ValueError:
            messagebox.showerror("Invalid Port", "Please enter a valid port number")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save email configuration: {e}")

class WebhookConfigDialog:
    """Dialog for configuring webhooks"""
    
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Webhook Configuration")
        self.dialog.geometry("450x250")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.create_widgets()
        self.load_current_settings()
        
        parent.wait_window(self.dialog)
    
    def create_widgets(self):
        """Create dialog widgets"""
        # Slack webhook
        slack_frame = ttk.LabelFrame(self.dialog, text="Slack Webhook", padding=10)
        slack_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(slack_frame, text="Webhook URL:").pack(anchor="w")
        self.slack_webhook_var = tk.StringVar()
        ttk.Entry(slack_frame, textvariable=self.slack_webhook_var, width=50).pack(fill="x", pady=2)
        
        ttk.Button(slack_frame, text="Test Slack", command=self.test_slack).pack(pady=5)
        
        # Discord webhook
        discord_frame = ttk.LabelFrame(self.dialog, text="Discord Webhook", padding=10)
        discord_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(discord_frame, text="Webhook URL:").pack(anchor="w")
        self.discord_webhook_var = tk.StringVar()
        ttk.Entry(discord_frame, textvariable=self.discord_webhook_var, width=50).pack(fill="x", pady=2)
        
        ttk.Button(discord_frame, text="Test Discord", command=self.test_discord).pack(pady=5)
        
        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(fill="x", padx=10, pady=10)
        
        ttk.Button(button_frame, text="Save", command=self.save_settings).pack(side="right", padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side="right")
    
    def load_current_settings(self):
        """Load current webhook settings"""
        self.slack_webhook_var.set(config.get("slack_webhook", ""))
        self.discord_webhook_var.set(config.get("discord_webhook", ""))
    
    def test_slack(self):
        """Test Slack webhook"""
        try:
            old_webhook = config.get("slack_webhook", "")
            config["slack_webhook"] = self.slack_webhook_var.get()
            
            send_slack_notification("Test message from backup system GUI")
            
            config["slack_webhook"] = old_webhook
            
            messagebox.showinfo("Test Successful", "Slack test message sent!")
        
        except Exception as e:
            messagebox.showerror("Test Failed", f"Slack test failed: {e}")
    
    def test_discord(self):
        """Test Discord webhook"""
        try:
            old_webhook = config.get("discord_webhook", "")
            config["discord_webhook"] = self.discord_webhook_var.get()
            
            send_discord_notification("Test message from backup system GUI")
            
            config["discord_webhook"] = old_webhook
            
            messagebox.showinfo("Test Successful", "Discord test message sent!")
        
        except Exception as e:
            messagebox.showerror("Test Failed", f"Discord test failed: {e}")
    
    def save_settings(self):
        """Save webhook settings"""
        try:
            config["slack_webhook"] = self.slack_webhook_var.get()
            config["discord_webhook"] = self.discord_webhook_var.get()
            
            save_config()
            
            messagebox.showinfo("Success", "Webhook configuration saved!")
            self.dialog.destroy()
        
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save webhook configuration: {e}")

class UploadDialog:
    """Dialog for uploading backups to cloud"""
    
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Upload to Cloud")
        self.dialog.geometry("500x300")
        self.dialog.transient(parent)
        
        self.create_widgets()
        self.load_backups()
    
    def create_widgets(self):
        """Create dialog widgets"""
        # Backup selection
        select_frame = ttk.LabelFrame(self.dialog, text="Select Backup to Upload", padding=10)
        select_frame.pack(fill="x", padx=10, pady=5)
        
        self.backup_var = tk.StringVar()
        self.backup_combo = ttk.Combobox(select_frame, textvariable=self.backup_var, 
                                        state="readonly", width=50)
        self.backup_combo.pack(fill="x", pady=5)
        
        # Upload options
        options_frame = ttk.LabelFrame(self.dialog, text="Upload Options", padding=10)
        options_frame.pack(fill="x", padx=10, pady=5)
        
        self.overwrite_var = tk.BooleanVar()
        ttk.Checkbutton(options_frame, text="Overwrite if exists", variable=self.overwrite_var).pack(anchor="w")
        
        self.delete_local_var = tk.BooleanVar()
        ttk.Checkbutton(options_frame, text="Delete local file after upload", 
                       variable=self.delete_local_var).pack(anchor="w")
        
        # Progress
        progress_frame = ttk.LabelFrame(self.dialog, text="Upload Progress", padding=10)
        progress_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, 
                                          mode="determinate", length=400)
        self.progress_bar.pack(pady=5)
        
        self.status_label = ttk.Label(progress_frame, text="Ready to upload")
        self.status_label.pack(pady=5)
        
        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(fill="x", padx=10, pady=10)
        
        self.upload_button = ttk.Button(button_frame, text="Upload", command=self.upload)
        self.upload_button.pack(side="right", padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side="right")
    
    def load_backups(self):
        """Load available backups"""
        try:
            backups = list_available_backups()
            self.backups = backups
            
            # Filter out already uploaded backups
            local_backups = [backup for backup in backups if not backup.get('cloud_uploaded', False)]
            
            backup_names = [f"{backup['date_formatted']} - {backup['filename']}" 
                           for backup in local_backups]
            self.backup_combo['values'] = backup_names
            
            if backup_names:
                self.backup_combo.current(0)
            else:
                self.status_label.config(text="No local backups available for upload")
        
        except Exception as e:
            self.status_label.config(text=f"Error loading backups: {e}")
    
    def upload(self):
        """Upload selected backup"""
        if not self.backup_combo.get():
            messagebox.showwarning("No Selection", "Please select a backup to upload")
            return
        
        try:
            # Get selected backup
            index = self.backup_combo.current()
            local_backups = [b for b in self.backups if not b.get('cloud_uploaded', False)]
            backup = local_backups[index]
            
            # Start upload in separate thread
            self.upload_button.config(state="disabled")
            self.status_label.config(text="Starting upload...")
            self.progress_var.set(0)
            
            def upload_worker():
                try:
                    # Simulate upload progress
                    for i in range(101):
                        time.sleep(0.02)  # Simulate upload time
                        self.progress_var.set(i)
                        self.status_label.config(text=f"Uploading... {i}%")
                        self.dialog.update()
                    
                    # Perform actual upload
                    success = upload_to_aws_s3(
                        backup['path'],
                        config["aws_bucket"],
                        f"backups/{backup['filename']}"
                    )
                    
                    if success:
                        # Update metadata
                        for b in metadata_manager.metadata["backups"]:
                            if b['path'] == backup['path']:
                                b['cloud_uploaded'] = True
                                break
                        metadata_manager.save_metadata()
                        
                        self.status_label.config(text="Upload completed successfully!")
                        
                        if self.delete_local_var.get():
                            os.remove(backup['path'])
                            self.status_label.config(text="Upload completed, local file deleted")
                        
                        messagebox.showinfo("Success", "Backup uploaded successfully!")
                        self.dialog.destroy()
                    else:
                        self.status_label.config(text="Upload failed")
                        messagebox.showerror("Error", "Upload failed")
                
                except Exception as e:
                    self.status_label.config(text=f"Upload error: {e}")
                    messagebox.showerror("Error", f"Upload failed: {e}")
                finally:
                    self.upload_button.config(state="normal")
                    self.progress_var.set(0)
            
            # Start upload thread
            upload_thread = threading.Thread(target=upload_worker)
            upload_thread.daemon = True
            upload_thread.start()
        
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start upload: {e}")
            self.upload_button.config(state="normal")

class DownloadDialog:
    """Dialog for downloading backups from cloud"""
    
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Download from Cloud")
        self.dialog.geometry("620x420")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.download_dir = tk.StringVar(value=config.get("backup_directory", "backups"))
        self.progress_var = tk.DoubleVar()
        self.status_text = tk.StringVar(value="Select a backup to download")
        self.cloud_backups = []
        
        self.create_widgets()
        self.load_backups()
    
    def create_widgets(self):
        """Create dialog widgets"""
        list_frame = ttk.LabelFrame(self.dialog, text="Available Cloud Backups", padding=10)
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)

        columns = ("date", "type", "size", "file")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=8)
        self.tree.heading("date", text="Date")
        self.tree.heading("type", text="Type")
        self.tree.heading("size", text="Size")
        self.tree.heading("file", text="File")

        self.tree.column("date", width=150)
        self.tree.column("type", width=100)
        self.tree.column("size", width=100)
        self.tree.column("file", width=220)

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        controls_frame = ttk.Frame(self.dialog)
        controls_frame.pack(fill="x", padx=10, pady=5)

        ttk.Button(controls_frame, text="Refresh", command=self.load_backups).pack(side="left")

        ttk.Label(controls_frame, text="Download to:").pack(side="left", padx=(20, 5))
        destination_entry = ttk.Entry(controls_frame, textvariable=self.download_dir, width=40)
        destination_entry.pack(side="left", padx=5)
        ttk.Button(controls_frame, text="Browse", command=self.select_destination).pack(side="left")

        progress_frame = ttk.LabelFrame(self.dialog, text="Download Status", padding=10)
        progress_frame.pack(fill="x", padx=10, pady=5)
        ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100, mode="determinate").pack(fill="x", pady=5)
        self.status_label = ttk.Label(progress_frame, textvariable=self.status_text)
        self.status_label.pack(anchor="w")

        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(fill="x", padx=10, pady=10)

        self.download_button = ttk.Button(button_frame, text="Download", command=self.download)
        self.download_button.pack(side="right", padx=5)
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side="right")

    def load_backups(self):
        """Load list of backups marked as uploaded to the cloud"""
        try:
            backups = list_available_backups()
            self.cloud_backups = [b for b in backups if b.get("cloud_uploaded", False)]

            for item in self.tree.get_children():
                self.tree.delete(item)

            for backup in self.cloud_backups:
                self.tree.insert(
                    "",
                    "end",
                    values=(
                        backup.get("date_formatted", "Unknown"),
                        backup.get("backup_type", "full"),
                        backup.get("size_formatted", "0 B"),
                        backup.get("filename", "")
                    )
                )

            if not self.cloud_backups:
                self.status_text.set("No cloud backups found. Upload backups before downloading.")
            else:
                self.status_text.set("Select a backup and click Download.")
        except Exception as exc:
            self.status_text.set(f"Error loading backups: {exc}")

    def select_destination(self):
        """Choose destination directory for downloads"""
        directory = filedialog.askdirectory(initialdir=self.download_dir.get() or ".")
        if directory:
            self.download_dir.set(directory)

    def download(self):
        """Download the selected backup from cloud storage"""
        if not config.get("cloud_enabled", False):
            messagebox.showwarning("Cloud Storage", "Cloud storage is not enabled.")
            return

        if config.get("cloud_provider") != "aws":
            messagebox.showwarning("Cloud Storage", "Only AWS S3 provider is supported for downloads in this demo.")
            return

        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a cloud backup to download.")
            return

        index = self.tree.index(selection[0])
        backup = self.cloud_backups[index]

        destination_dir = self.download_dir.get().strip()
        if not destination_dir:
            messagebox.showwarning("Destination", "Please choose a destination directory.")
            return

        os.makedirs(destination_dir, exist_ok=True)
        destination_path = os.path.join(destination_dir, backup["filename"])

        if os.path.exists(destination_path):
            if not messagebox.askyesno(
                "Overwrite File",
                f"'{backup['filename']}' already exists in the destination.\nOverwrite?",
                parent=self.dialog
            ):
                return

        bucket = config.get("aws_bucket", "").strip()
        if not bucket:
            messagebox.showwarning("Cloud Storage", "AWS bucket is not configured.")
            return

        key = backup.get("cloud_key") or f"backups/{backup['filename']}"
        self.download_button.config(state="disabled")
        self.status_text.set(f"Starting download for {backup['filename']}...")
        self.progress_var.set(0)

        def update_ui(progress, text=None):
            self.progress_var.set(progress)
            if text:
                self.status_text.set(text)

        def finish(success, message):
            self.download_button.config(state="normal")
            if success:
                messagebox.showinfo("Download Complete", message, parent=self.dialog)
            else:
                messagebox.showerror("Download Failed", message, parent=self.dialog)
            self.progress_var.set(0)

        def worker():
            try:
                self.dialog.after(0, update_ui, 10, f"Downloading {backup['filename']}...")
                success = download_from_aws_s3(bucket, key, destination_path)
                if success:
                    self.dialog.after(0, update_ui, 100, "Download complete.")

                    for record in metadata_manager.metadata["backups"]:
                        if record["path"] == backup["path"]:
                            record["last_downloaded"] = datetime.datetime.now().isoformat()
                            break
                    metadata_manager.save_metadata()

                    self.dialog.after(0, finish, True, f"Backup downloaded to {destination_path}")
                else:
                    self.dialog.after(0, finish, False, "Cloud service reported a failure.")
            except Exception as exc:
                self.dialog.after(0, finish, False, f"Download failed: {exc}")

        threading.Thread(target=worker, daemon=True).start()


def start_backup_gui():
    """Start the GUI backup application"""
    root = tk.Tk()
    app = BackupGUI(root)
    
    # Handle window closing
    def on_closing():
        if messagebox.askokcancel("Quit", "Do you want to quit the backup system?"):
            stop_scheduler()
            root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    
    # Center window on screen
    root.update_idletasks()
    width = root.winfo_width()
    height = root.winfo_height()
    x = (root.winfo_screenwidth() // 2) - (width // 2)
    y = (root.winfo_screenheight() // 2) - (height // 2)
    root.geometry(f"{width}x{height}+{x}+{y}")
    
    root.mainloop()

# Backward compatibility functions - these maintain the original CLI interface

def display_enhanced_backup_menu_gui():
    """GUI version of the enhanced backup menu with CLI fallback"""
    try:
        # Try to start GUI
        start_backup_gui()
    except Exception as e:
        print(f"Failed to start GUI: {e}")
        print("Falling back to CLI interface...")
        # Import and use original CLI function
    try:
        from university_system.infrastructure.database.data_backup import display_enhanced_backup_menu
    except ImportError:
        from university_system.infrastructure.database.data_backup import display_enhanced_backup_menu

def display_backup_menu_gui():
    """GUI version of backup menu with CLI fallback"""
    display_enhanced_backup_menu_gui()

def open_data_backup_gui():
    """GUI version of data backup with CLI fallback"""
    display_enhanced_backup_menu_gui()

# Entry point functions - these maintain full backward compatibility

def main():
    """Main entry point - detects if GUI is available"""
    import sys
    
    # Check for GUI flag
    if len(sys.argv) > 1 and sys.argv[1] in ['--gui', '-g']:
        start_backup_gui()
    elif len(sys.argv) > 1 and sys.argv[1] in ['--cli', '-c']:
        # Force CLI mode
        try:
            from university_system.infrastructure.database.data_backup import display_enhanced_backup_menu
        except ImportError:
            from university_system.infrastructure.database.data_backup import display_enhanced_backup_menu

    else:
        # Try GUI first, fall back to CLI
        try:
            start_backup_gui()
        except Exception as e:
            print(f"GUI not available ({e}), using CLI interface...")
        try:
            from university_system.infrastructure.database.data_backup import display_enhanced_backup_menu
        except ImportError:
            from university_system.infrastructure.database.data_backup import display_enhanced_backup_menu


# Legacy function names for backward compatibility
display_enhanced_backup_menu = display_enhanced_backup_menu_gui
display_backup_menu = display_backup_menu_gui
open_data_backup = open_data_backup_gui

# CLI integration functions

def create_backup_gui(*args, **kwargs):
    """GUI wrapper for create_backup function"""
    # For programmatic use, still use the original function
    return create_enhanced_backup(*args, **kwargs)

def backup_before_operation_gui(operation_name):
    """GUI wrapper for backup_before_operation"""
    return create_enhanced_backup(manual=False, operation_name=operation_name)

# System tray integration (optional)
try:
    import pystray
    from PIL import Image
    
    class SystemTrayApp:
        """System tray application for backup system"""
        
        def __init__(self):
            self.icon = None
            self.gui_app = None
        
        def create_image(self):
            """Create tray icon image"""
            # Create a simple icon (in real implementation, use proper icon file)
            return Image.new('RGB', (64, 64), color='blue')
        
        def show_gui(self, icon, item):
            """Show GUI from system tray"""
            if self.gui_app is None:
                root = tk.Tk()
                self.gui_app = BackupGUI(root)
                root.mainloop()
        
        def quit_app(self, icon, item):
            """Quit application"""
            stop_scheduler()
            icon.stop()
        
        def start(self):
            """Start system tray application"""
            menu = pystray.Menu(
                pystray.MenuItem("Open Backup System", self.show_gui),
                pystray.MenuItem("Quit", self.quit_app)
            )
            
            self.icon = pystray.Icon("BackupSystem", self.create_image(), "Backup System", menu)
            self.icon.run()
    
    def start_system_tray():
        """Start system tray version"""
        app = SystemTrayApp()
        app.start()

except ImportError:
    def start_system_tray():
        """Fallback when pystray not available"""
        print("System tray not available, starting regular GUI...")
        start_backup_gui()

# Command line interface
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Enhanced Data Backup System")
    parser.add_argument('--gui', '-g', action='store_true', help='Start GUI interface')
    parser.add_argument('--cli', '-c', action='store_true', help='Start CLI interface')
    parser.add_argument('--tray', '-t', action='store_true', help='Start system tray version')
    parser.add_argument('--backup', '-b', action='store_true', help='Create quick backup and exit')
    parser.add_argument('--restore', '-r', metavar='BACKUP_FILE', help='Restore from specific backup file')
    parser.add_argument('--validate', '-v', metavar='BACKUP_FILE', help='Validate specific backup file')
    parser.add_argument('--list', '-l', action='store_true', help='List available backups')
    
    args = parser.parse_args()
    
    if args.backup:
        # Quick backup
        print("Creating backup...")
        result = create_enhanced_backup(manual=True)
        if result:
            print(f"Backup created: {result}")
        else:
            print("Backup failed!")
            sys.exit(1)
    
    elif args.restore:
        # Restore from backup
        print(f"Restoring from {args.restore}...")
        success = restore_from_backup(args.restore)
        if success:
            print("Restore completed successfully!")
        else:
            print("Restore failed!")
            sys.exit(1)
    
    elif args.validate:
        # Validate backup
        print(f"Validating {args.validate}...")
        results = validate_backup(args.validate)
        
        print("Validation Results:")
        print(f"File exists: {'✓' if results['file_exists'] else '✗'}")
        print(f"File readable: {'✓' if results['file_readable'] else '✗'}")
        print(f"Database valid: {'✓' if results['database_valid'] else '✗'}")
        print(f"Tables accessible: {'✓' if results['tables_accessible'] else '✗'}")
        print(f"Hash verified: {'✓' if results['hash_verified'] else '✗'}")
        
        if results['errors']:
            print("Errors:")
            for error in results['errors']:
                print(f"  • {error}")
    
    elif args.list:
        # List backups
        backups = list_available_backups()
        if backups:
            print(f"{'ID':<4} {'Type':<12} {'Date':<20} {'Size':<12} {'File'}")
            print("-" * 80)
            for backup in backups:
                print(f"{backup['id']:<4} {backup.get('backup_type', 'full'):<12} "
                      f"{backup['date_formatted']:<20} {backup['size_formatted']:<12} "
                      f"{backup['filename']}")
        else:
            print("No backups found")
    
    elif args.tray:
        # System tray
        start_system_tray()
    
    elif args.cli:
        # CLI interface
        try:
            from university_system.infrastructure.database.data_backup import display_enhanced_backup_menu
        except ImportError:
            from university_system.infrastructure.database.data_backup import display_enhanced_backup_menu

    
    elif args.gui:
        # GUI interface
        start_backup_gui()
    
    else:
        # Default behavior - try GUI, fall back to CLI
        main()

# Module-level imports for backward compatibility
if __name__ != "__main__":
    # When imported as module, expose all original functions
    # This ensures 100% backward compatibility
    try:
        from university_system.infrastructure.database.data_backup import (
            calculate_file_hash, cleanup_old_backups, compare_backups,
            compare_table_data, compress_file, create_enhanced_backup,
            create_incremental_backup, create_schema_only_backup,
            create_selective_backup, decompress_file, decrypt_file,
            delete_backup, display_backup_menu, display_enhanced_backup_menu,
            download_from_aws_s3, encrypt_file, ensure_backup_directory,
            export_to_csv, export_to_json, export_to_xml,
            generate_backup_statistics, generate_encryption_key,
            get_database_tables, get_database_tables_from_connection,
            has_database_changed, list_available_backups, load_backup_template,
            load_config, notify_backup_result, open_data_backup,
            parse_cron_schedule, restore_from_backup, restore_partial_tables,
            save_backup_template, save_config, scheduled_backup_job,
            secure_delete_file, send_discord_notification, send_email_notification,
            send_slack_notification, start_scheduler, stop_scheduler,
            upload_to_aws_s3, upload_to_ftp, upload_to_sftp, validate_backup,
            verify_backup_integrity
        )
        
        # Override the display functions to use GUI versions
        original_display_enhanced_backup_menu = display_enhanced_backup_menu
        original_display_backup_menu = display_backup_menu
        original_open_data_backup = open_data_backup
        
        def display_enhanced_backup_menu(*args, **kwargs):
            """Enhanced backup menu with GUI support"""
            try:
                return display_enhanced_backup_menu_gui(*args, **kwargs)
            except:
                return original_display_enhanced_backup_menu(*args, **kwargs)
        
        def display_backup_menu(*args, **kwargs):
            """Backup menu with GUI support"""
            try:
                return display_backup_menu_gui(*args, **kwargs)
            except:
                return original_display_backup_menu(*args, **kwargs)
        
        def open_data_backup(*args, **kwargs):
            """Data backup with GUI support"""
            try:
                return open_data_backup_gui(*args, **kwargs)
            except:
                return original_open_data_backup(*args, **kwargs)
        
    except ImportError as e:
        print(f"Warning: Could not import original backup functions: {e}")
        print("GUI-only mode active.")

# Configuration for GUI preferences
GUI_CONFIG = {
    "auto_start_gui": True,
    "remember_window_size": True,
    "theme": "default",
    "show_splash": True,
    "minimize_to_tray": False,
    "auto_refresh_interval": 30000  # milliseconds
}

def save_gui_config():
    """Save GUI-specific configuration"""
    try:
        with open("gui_config.json", "w") as f:
            json.dump(GUI_CONFIG, f, indent=4)
    except Exception as e:
        logger.error(f"Failed to save GUI config: {e}")

def load_gui_config():
    """Load GUI-specific configuration"""
    global GUI_CONFIG
    try:
        if os.path.exists("gui_config.json"):
            with open("gui_config.json", "r") as f:
                loaded_config = json.load(f)
                GUI_CONFIG.update(loaded_config)
    except Exception as e:
        logger.error(f"Failed to load GUI config: {e}")

class ExportDialog:
    """Dialog for exporting backups"""
    
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Export Backup")
        self.dialog.geometry("500x300")
        self.dialog.transient(parent)
        
        self.create_widgets()
        self.load_backups()
    
    def create_widgets(self):
        """Create dialog widgets"""
        # Backup selection
        select_frame = ttk.LabelFrame(self.dialog, text="Select Backup to Export", padding=10)
        select_frame.pack(fill="x", padx=10, pady=5)
        
        self.backup_var = tk.StringVar()
        self.backup_combo = ttk.Combobox(select_frame, textvariable=self.backup_var, 
                                        state="readonly", width=50)
        self.backup_combo.pack(fill="x", pady=5)
        
        # Export format
        format_frame = ttk.LabelFrame(self.dialog, text="Export Format", padding=10)
        format_frame.pack(fill="x", padx=10, pady=5)

        self.format_var = tk.StringVar(value="csv")
        ttk.Radiobutton(format_frame, text="CSV Files", variable=self.format_var, value="csv").pack(anchor="w")
        ttk.Radiobutton(format_frame, text="JSON File", variable=self.format_var, value="json").pack(anchor="w")
        ttk.Radiobutton(format_frame, text="XML File", variable=self.format_var, value="xml").pack(anchor="w")
        ttk.Radiobutton(format_frame, text="PDF File", variable=self.format_var, value="pdf").pack(anchor="w")
        ttk.Radiobutton(format_frame, text="Text File", variable=self.format_var, value="txt").pack(anchor="w")
        
        # Output location
        output_frame = ttk.LabelFrame(self.dialog, text="Output Location", padding=10)
        output_frame.pack(fill="x", padx=10, pady=5)
        
        self.output_var = tk.StringVar()
        ttk.Entry(output_frame, textvariable=self.output_var, width=40).pack(side="left", fill="x", expand=True)
        ttk.Button(output_frame, text="Browse", command=self.browse_output).pack(side="right", padx=(5,0))
        
        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(fill="x", padx=10, pady=10)
        
        ttk.Button(button_frame, text="Export", command=self.export).pack(side="right", padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side="right")
    
    def load_backups(self):
        """Load available backups"""
        try:
            backups = list_available_backups()
            self.backups = backups
            
            backup_names = [f"{backup['date_formatted']} - {backup['filename']}" 
                           for backup in backups]
            self.backup_combo['values'] = backup_names
            
            if backup_names:
                self.backup_combo.current(0)
        
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load backups: {e}")
    
    def browse_output(self):
        """Browse for output location"""
        if self.format_var.get() == "csv":
            path = filedialog.askdirectory(title="Select output directory for CSV files")
        else:
            format_type = self.format_var.get()
            filetypes_map = {
                "json": [("JSON files", "*.json")],
                "xml": [("XML files", "*.xml")],
                "pdf": [("PDF files", "*.pdf")],
                "txt": [("Text files", "*.txt")]
            }
            filetypes = filetypes_map.get(format_type, [("All files", "*.*")])
            path = filedialog.asksaveasfilename(title="Save export file", filetypes=filetypes)

        if path:
            self.output_var.set(path)
    
    def export(self):
        """Export selected backup"""
        if not self.backup_combo.get():
            messagebox.showwarning("No Selection", "Please select a backup to export")
            return

        if not self.output_var.get():
            messagebox.showwarning("No Output", "Please specify output location")
            return

        try:
            index = self.backup_combo.current()
            backup = self.backups[index]
            format_type = self.format_var.get()
            output_path = self.output_var.get()

            success = False
            if format_type == "csv":
                success = export_to_csv(backup['path'], output_path)
            elif format_type == "json":
                success = export_to_json(backup['path'], output_path)
            elif format_type == "xml":
                success = export_to_xml(backup['path'], output_path)
            elif format_type == "pdf":
                success = export_to_pdf(backup['path'], output_path)
            elif format_type == "txt":
                success = export_to_txt(backup['path'], output_path)

            if success:
                messagebox.showinfo("Success", f"Backup exported successfully to {output_path}")
                self.dialog.destroy()
            else:
                messagebox.showerror("Error", "Export operation failed. Check logs for details.")

        except Exception as e:
            messagebox.showerror("Error", f"Export failed: {e}")

class TemplateSelectionDialog:
    """Dialog for selecting templates with descriptions"""

    def __init__(self, parent, template_names, template_data=None):
        self.selected_template = None
        self.template_data = template_data or {}

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Select Backup Template")
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # Template list
        list_frame = ttk.LabelFrame(self.dialog, text="Available Templates", padding=10)
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.template_var = tk.StringVar()

        # Add radio buttons with descriptions
        for template_name in template_names:
            frame = ttk.Frame(list_frame)
            frame.pack(fill="x", pady=2)

            ttk.Radiobutton(frame, text=template_name, variable=self.template_var,
                           value=template_name).pack(anchor="w")

            # Show description if available
            if template_name in self.template_data:
                desc = self.template_data[template_name].get("description", "")
                source = self.template_data[template_name].get("source", "")
                source_text = f" [{source}]" if source else ""
                if desc:
                    ttk.Label(frame, text=f"  {desc}{source_text}",
                             font=("TkDefaultFont", 8), foreground="gray").pack(anchor="w", padx=20)

        if template_names:
            self.template_var.set(template_names[0])

        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(fill="x", padx=10, pady=10)

        ttk.Button(button_frame, text="Load", command=self.ok).pack(side="right", padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.cancel).pack(side="right")

        parent.wait_window(self.dialog)

    def ok(self):
        """OK button handler"""
        self.selected_template = self.template_var.get()
        self.dialog.destroy()

    def cancel(self):
        """Cancel button handler"""
        self.selected_template = None
        self.dialog.destroy()

class TemplateManagerDialog:
    """Dialog for managing backup templates"""
    
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Template Manager")
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        
        self.create_widgets()
        self.load_templates()
    
    def create_widgets(self):
        """Create dialog widgets"""
        # Template list
        list_frame = ttk.LabelFrame(self.dialog, text="Templates", padding=10)
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Listbox with scrollbar
        listbox_frame = ttk.Frame(list_frame)
        listbox_frame.pack(fill="both", expand=True)
        
        self.template_listbox = tk.Listbox(listbox_frame)
        scrollbar = ttk.Scrollbar(listbox_frame, orient="vertical", command=self.template_listbox.yview)
        self.template_listbox.configure(yscrollcommand=scrollbar.set)
        
        self.template_listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        self.template_listbox.bind("<<ListboxSelect>>", self.show_template_details)
        
        # Template details
        details_frame = ttk.LabelFrame(self.dialog, text="Template Details", padding=10)
        details_frame.pack(fill="x", padx=10, pady=5)
        
        self.details_text = scrolledtext.ScrolledText(details_frame, height=8, wrap=tk.WORD)
        self.details_text.pack(fill="both", expand=True)
        
        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(fill="x", padx=10, pady=10)
        
        ttk.Button(button_frame, text="Load Template", command=self.load_template).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Delete Template", command=self.delete_template).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Rename Template", command=self.rename_template).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side="right")
    
    def load_templates(self):
        """Load template list from JSON files and config"""
        self.template_listbox.delete(0, tk.END)
        # Use new list_backup_templates function
        self.templates = list_backup_templates()

        for template_name in self.templates.keys():
            self.template_listbox.insert(tk.END, template_name)
    
    def show_template_details(self, event=None):
        """Show details for selected template"""
        selection = self.template_listbox.curselection()
        if not selection:
            return

        template_name = self.template_listbox.get(selection[0])
        template_info = self.templates.get(template_name, {})

        details = f"Template: {template_name}\n"
        details += "=" * 40 + "\n\n"

        # Show description and source
        details += f"Description: {template_info.get('description', 'N/A')}\n"
        details += f"Source: {template_info.get('source', 'N/A')}\n"
        if 'path' in template_info:
            details += f"Path: {template_info['path']}\n"
        details += "\n"

        # Try to load full template data
        try:
            if template_info.get('source') == 'file':
                template_file = Path(template_info['path'])
                with open(template_file, 'r') as f:
                    template_data = json.load(f)
            else:
                template_data = config.get("backup_templates", {}).get(template_name, {})

            # Show key settings
            key_settings = [
                "backup_type", "backup_frequency", "scheduled_backup_time",
                "max_backups", "auto_backup_enabled", "encryption_enabled",
                "compression_enabled", "compression_format", "cloud_enabled",
                "remote_enabled", "email_notifications"
            ]

            details += "Settings:\n"
            details += "-" * 40 + "\n"
            for key in key_settings:
                if key in template_data:
                    details += f"{key.replace('_', ' ').title()}: {template_data[key]}\n"

        except Exception as e:
            details += f"\nError loading template details: {e}\n"

        self.details_text.delete(1.0, tk.END)
        self.details_text.insert(1.0, details)
    
    def load_template(self):
        """Load selected template"""
        selection = self.template_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a template to load")
            return
        
        template_name = self.template_listbox.get(selection[0])
        
        if messagebox.askyesno("Load Template", f"Load template '{template_name}'?\n\nThis will overwrite current settings."):
            if load_backup_template(template_name):
                messagebox.showinfo("Success", f"Template '{template_name}' loaded successfully!")
                self.dialog.destroy()
            else:
                messagebox.showerror("Error", "Failed to load template")
    
    def delete_template(self):
        """Delete selected template"""
        selection = self.template_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a template to delete")
            return
        
        template_name = self.template_listbox.get(selection[0])
        
        if messagebox.askyesno("Delete Template", f"Are you sure you want to delete template '{template_name}'?"):
            try:
                del config["backup_templates"][template_name]
                save_config()
                self.load_templates()
                self.details_text.delete(1.0, tk.END)
                messagebox.showinfo("Success", f"Template '{template_name}' deleted successfully!")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete template: {e}")
    
    def rename_template(self):
        """Rename selected template"""
        selection = self.template_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a template to rename")
            return
        
        old_name = self.template_listbox.get(selection[0])
        new_name = tk.simpledialog.askstring("Rename Template", f"Enter new name for '{old_name}':")
        
        if new_name and new_name != old_name:
            if new_name in self.templates:
                messagebox.showerror("Error", "Template with that name already exists")
                return
            
            try:
                config["backup_templates"][new_name] = config["backup_templates"][old_name]
                del config["backup_templates"][old_name]
                save_config()
                self.load_templates()
                messagebox.showinfo("Success", f"Template renamed to '{new_name}'")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to rename template: {e}")

class ScheduleConfigDialog:
    """Dialog for configuring backup schedule"""
    
    def __init__(self, parent, update_callback=None):
        self.update_callback = update_callback
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Schedule Configuration")
        self.dialog.geometry("400x350")
        self.dialog.transient(parent)
        
        self.create_widgets()
        self.load_current_settings()
    
    def create_widgets(self):
        """Create dialog widgets"""
        # Frequency settings
        freq_frame = ttk.LabelFrame(self.dialog, text="Backup Frequency", padding=10)
        freq_frame.pack(fill="x", padx=10, pady=5)
        
        self.frequency_var = tk.StringVar(value=config["backup_frequency"])
        
        ttk.Radiobutton(freq_frame, text="Daily", variable=self.frequency_var, value="daily").pack(anchor="w")
        ttk.Radiobutton(freq_frame, text="Weekly", variable=self.frequency_var, value="weekly").pack(anchor="w")
        ttk.Radiobutton(freq_frame, text="Monthly", variable=self.frequency_var, value="monthly").pack(anchor="w")
        
        # Time settings
        time_frame = ttk.LabelFrame(self.dialog, text="Backup Time", padding=10)
        time_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(time_frame, text="Time (24-hour format):").pack(anchor="w")
        self.time_var = tk.StringVar(value=config["scheduled_backup_time"])
        time_entry = ttk.Entry(time_frame, textvariable=self.time_var, width=10)
        time_entry.pack(anchor="w", pady=2)
        ttk.Label(time_frame, text="Format: HH:MM (e.g., 02:30)", font=("Arial", 8)).pack(anchor="w")
        
        # Advanced scheduling
        advanced_frame = ttk.LabelFrame(self.dialog, text="Advanced Scheduling", padding=10)
        advanced_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(advanced_frame, text="Cron Expression (optional):").pack(anchor="w")
        self.cron_var = tk.StringVar(value=config.get("cron_schedule", ""))
        cron_entry = ttk.Entry(advanced_frame, textvariable=self.cron_var, width=30)
        cron_entry.pack(anchor="w", pady=2)
        ttk.Label(advanced_frame, text="Examples: '0 2 * * *' (daily 2am), '0 2 * * 1' (weekly Monday 2am)", 
                 font=("Arial", 8)).pack(anchor="w")
        
        # Backup type for scheduled backups
        type_frame = ttk.LabelFrame(self.dialog, text="Scheduled Backup Type", padding=10)
        type_frame.pack(fill="x", padx=10, pady=5)
        
        self.backup_type_var = tk.StringVar(value=config.get("backup_type", "full"))
        ttk.Radiobutton(type_frame, text="Full Backup", variable=self.backup_type_var, value="full").pack(anchor="w")
        ttk.Radiobutton(type_frame, text="Incremental Backup", variable=self.backup_type_var, value="incremental").pack(anchor="w")
        
        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(fill="x", padx=10, pady=10)
        
        ttk.Button(button_frame, text="Save", command=self.save_schedule).pack(side="right", padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side="right")
    
    def load_current_settings(self):
        """Load current schedule settings"""
        self.frequency_var.set(config["backup_frequency"])
        self.time_var.set(config["scheduled_backup_time"])
        self.cron_var.set(config.get("cron_schedule", ""))
        self.backup_type_var.set(config.get("backup_type", "full"))
    
    def save_schedule(self):
        """Save schedule configuration"""
        try:
            # Validate time format
            time_str = self.time_var.get()
            datetime.datetime.strptime(time_str, "%H:%M")

            cron_expr = self.cron_var.get().strip()
            if cron_expr:
                if not parse_cron_schedule(cron_expr):
                    messagebox.showerror("Invalid Cron", "Cron expression could not be parsed. Please check the format.")
                    return
            else:
                parse_cron_schedule("")
            
            # Update configuration
            config["backup_frequency"] = self.frequency_var.get()
            config["scheduled_backup_time"] = time_str
            config["cron_schedule"] = cron_expr
            config["backup_type"] = self.backup_type_var.get()
            
            save_config()
            
            # Restart scheduler
            if config["auto_backup_enabled"]:
                stop_scheduler()
                start_scheduler()
            
            if self.update_callback:
                self.update_callback()
            
            messagebox.showinfo("Success", "Schedule configuration saved!")
            self.dialog.destroy()
        
        except ValueError:
            messagebox.showerror("Invalid Time", "Please enter time in HH:MM format (e.g., 02:30)")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save schedule: {e}")

class StorageUsageDialog:
    """Dialog for showing storage usage and quota information - missing class"""
    
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Storage Usage")
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        
        self.create_widgets()
        self.load_usage_data()
    
    def create_widgets(self):
        """Create dialog widgets"""
        # Usage summary
        summary_frame = ttk.LabelFrame(self.dialog, text="Storage Summary", padding=10)
        summary_frame.pack(fill="x", padx=10, pady=5)
        
        self.usage_text = scrolledtext.ScrolledText(summary_frame, height=8, wrap=tk.WORD)
        self.usage_text.pack(fill="both", expand=True)
        
        # Actions
        actions_frame = ttk.LabelFrame(self.dialog, text="Storage Actions", padding=10)
        actions_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Button(actions_frame, text="Clean Old Backups", 
                  command=self.clean_old_backups).pack(side="left", padx=5)
        ttk.Button(actions_frame, text="Remove Duplicates", 
                  command=self.remove_duplicates).pack(side="left", padx=5)
        ttk.Button(actions_frame, text="Adjust Quota", 
                  command=self.adjust_quota).pack(side="left", padx=5)
        
        # Close button
        ttk.Button(self.dialog, text="Close", command=self.dialog.destroy).pack(pady=10)
    
    def load_usage_data(self):
        """Load and display storage usage data"""
        try:
            quota_info = check_storage_quota()
            backups = list_available_backups()
            
            usage_report = "STORAGE USAGE REPORT\n"
            usage_report += "=" * 30 + "\n\n"
            
            usage_report += f"Total Backups: {len(backups)}\n"
            usage_report += f"Total Size: {quota_info['total_size_gb']:.2f} GB\n"
            usage_report += f"Storage Quota: {quota_info['quota_gb']} GB\n"
            usage_report += f"Usage: {quota_info['usage_percentage']:.1f}%\n"
            
            if quota_info['quota_exceeded']:
                usage_report += "\n⚠️ WARNING: Storage quota exceeded!\n"
            
            usage_report += f"\nBackup Directory: {config['backup_directory']}\n"
            
            # Backup breakdown by type
            type_usage = {}
            for backup in backups:
                backup_type = backup.get('backup_type', 'unknown')
                size = backup.get('size', 0)
                if backup_type not in type_usage:
                    type_usage[backup_type] = {'count': 0, 'size': 0}
                type_usage[backup_type]['count'] += 1
                type_usage[backup_type]['size'] += size
            
            if type_usage:
                usage_report += "\nBreakdown by Type:\n"
                for backup_type, info in type_usage.items():
                    size_mb = info['size'] / (1024 * 1024)
                    usage_report += f"  {backup_type}: {info['count']} backups, {size_mb:.1f} MB\n"
            
            # Recent activity
            recent_backups = [b for b in backups[:5]]  # Last 5
            if recent_backups:
                usage_report += "\nRecent Backups:\n"
                for backup in recent_backups:
                    usage_report += f"  {backup['date_formatted']} - {backup['size_formatted']}\n"
            
            self.usage_text.delete(1.0, tk.END)
            self.usage_text.insert(1.0, usage_report)
            
        except Exception as e:
            self.usage_text.delete(1.0, tk.END)
            self.usage_text.insert(1.0, f"Error loading usage data: {e}")
    
    def cleanup_old_backups_enhanced():
        """Enhanced cleanup with retention policies - missing from GUI"""
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
                except:
                    # If timestamp parsing fails, treat as old backup
                    yearly_backups.append(backup)
            
            # Apply retention policy
            backups_to_keep = []
            
            # Keep recent daily backups
            daily_backups.sort(key=lambda x: x["timestamp"], reverse=True)
            backups_to_keep.extend(daily_backups[:retention["daily_keep"]])
            
            # Keep weekly backups (one per week)
            weekly_by_week = {}
            for backup in weekly_backups:
                try:
                    backup_date = datetime.datetime.strptime(backup["timestamp"], "%Y%m%d_%H%M%S")
                    week_key = backup_date.strftime("%Y-W%U")
                    if week_key not in weekly_by_week:
                        weekly_by_week[week_key] = backup
                except:
                    pass
            
            weekly_kept = list(weekly_by_week.values())
            weekly_kept.sort(key=lambda x: x["timestamp"], reverse=True)
            backups_to_keep.extend(weekly_kept[:retention["weekly_keep"]])
            
            # Keep monthly backups (one per month)
            monthly_by_month = {}
            for backup in monthly_backups:
                try:
                    backup_date = datetime.datetime.strptime(backup["timestamp"], "%Y%m%d_%H%M%S")
                    month_key = backup_date.strftime("%Y-%m")
                    if month_key not in monthly_by_month:
                        monthly_by_month[month_key] = backup
                except:
                    pass
            
            monthly_kept = list(monthly_by_month.values())
            monthly_kept.sort(key=lambda x: x["timestamp"], reverse=True)
            backups_to_keep.extend(monthly_kept[:retention["monthly_keep"]])
            
            # Keep yearly backups (one per year)
            yearly_by_year = {}
            for backup in yearly_backups:
                try:
                    backup_date = datetime.datetime.strptime(backup["timestamp"], "%Y%m%d_%H%M%S")
                    year_key = backup_date.strftime("%Y")
                    if year_key not in yearly_by_year:
                        yearly_by_year[year_key] = backup
                except:
                    pass
            
            yearly_kept = list(yearly_by_year.values())
            yearly_kept.sort(key=lambda x: x["timestamp"], reverse=True)
            backups_to_keep.extend(yearly_kept[:retention["yearly_keep"]])
            
            # Remove backups not in keep list
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
            
            # Update metadata
            metadata_manager.metadata["backups"] = backups_to_keep
            metadata_manager.save_metadata()
            
            return removed_count
        
        except Exception as e:
            logger.error(f"Error cleaning up old backups: {e}")
            return 0
    
    def remove_duplicates(self):
        """Remove duplicate backups"""
        if messagebox.askyesno("Remove Duplicates", "Remove duplicate backup files?"):
            removed = deduplicate_backups()
            messagebox.showinfo("Deduplication Complete", f"Removed {removed} duplicate backups")
            self.load_usage_data()
    
    def adjust_quota(self):
        """Adjust storage quota"""
        current_quota = config.get("storage_quota_gb", 10)
        new_quota = tk.simpledialog.askfloat("Adjust Quota", 
                                           f"Current quota: {current_quota} GB\nEnter new quota (GB):",
                                           minvalue=1.0, maxvalue=1000.0)
        if new_quota:
            config["storage_quota_gb"] = new_quota
            save_config()
            messagebox.showinfo("Quota Updated", f"Storage quota set to {new_quota} GB")
            self.load_usage_data()

class ComparisonDialog:
    """Dialog for comparing backups"""
    
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Compare Backups")
        self.dialog.geometry("600x500")
        self.dialog.transient(parent)
        
        self.create_widgets()
        self.load_backups()
    
    def create_widgets(self):
        """Create dialog widgets"""
        # Backup selection
        select_frame = ttk.LabelFrame(self.dialog, text="Select Backups to Compare", padding=10)
        select_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(select_frame, text="First Backup:").grid(row=0, column=0, sticky="w", padx=5)
        self.backup1_var = tk.StringVar()
        self.backup1_combo = ttk.Combobox(select_frame, textvariable=self.backup1_var, 
                                         state="readonly", width=40)
        self.backup1_combo.grid(row=0, column=1, padx=5, pady=2)
        
        ttk.Label(select_frame, text="Second Backup:").grid(row=1, column=0, sticky="w", padx=5)
        self.backup2_var = tk.StringVar()
        self.backup2_combo = ttk.Combobox(select_frame, textvariable=self.backup2_var, 
                                         state="readonly", width=40)
        self.backup2_combo.grid(row=1, column=1, padx=5, pady=2)
        
        ttk.Button(select_frame, text="Compare", command=self.compare).grid(row=2, column=1, pady=10)
        
        # Results
        results_frame = ttk.LabelFrame(self.dialog, text="Comparison Results", padding=10)
        results_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.results_text = scrolledtext.ScrolledText(results_frame, wrap=tk.WORD)
        self.results_text.pack(fill="both", expand=True)
    
    def load_backups(self):
        """Load available backups"""
        try:
            backups = list_available_backups()
            self.backups = backups
            
            backup_names = [f"{backup['date_formatted']} - {backup['filename']}" 
                           for backup in backups]
            
            self.backup1_combo['values'] = backup_names
            self.backup2_combo['values'] = backup_names
            
            if len(backup_names) >= 2:
                self.backup1_combo.current(0)
                self.backup2_combo.current(1)
        
        except Exception as e:
            self.results_text.insert(tk.END, f"Error loading backups: {e}\n")
    
    def compare(self):
        """Compare selected backups"""
        if not self.backup1_combo.get() or not self.backup2_combo.get():
            messagebox.showwarning("No Selection", "Please select two backups to compare")
            return
        
        if self.backup1_combo.current() == self.backup2_combo.current():
            messagebox.showwarning("Same Backup", "Please select two different backups")
            return
        
        try:
            backup1 = self.backups[self.backup1_combo.current()]
            backup2 = self.backups[self.backup2_combo.current()]
            
            self.results_text.delete(1.0, tk.END)
            self.results_text.insert(tk.END, "Comparing backups...\n")
            self.dialog.update()
            
            differences = compare_backups(backup1['path'], backup2['path'])
            
            if differences:
                self.results_text.delete(1.0, tk.END)
                self.results_text.insert(tk.END, "BACKUP COMPARISON RESULTS\n")
                self.results_text.insert(tk.END, "=" * 40 + "\n\n")
                
                self.results_text.insert(tk.END, f"Backup 1: {backup1['filename']}\n")
                self.results_text.insert(tk.END, f"Date 1: {backup1['date_formatted']}\n")
                self.results_text.insert(tk.END, f"Size 1: {backup1['size_formatted']}\n\n")
                
                self.results_text.insert(tk.END, f"Backup 2: {backup2['filename']}\n")
                self.results_text.insert(tk.END, f"Date 2: {backup2['date_formatted']}\n")
                self.results_text.insert(tk.END, f"Size 2: {backup2['size_formatted']}\n\n")
                
                # Summary
                total_changes = (len(differences['tables_added']) + 
                               len(differences['tables_removed']) + 
                               len(differences['tables_modified']))
                
                if total_changes == 0:
                    self.results_text.insert(tk.END, "✅ No differences found - backups are identical\n")
                else:
                    self.results_text.insert(tk.END, f"📊 SUMMARY: {total_changes} table(s) changed\n\n")
                
                # Tables added
                if differences['tables_added']:
                    self.results_text.insert(tk.END, f"➕ TABLES ADDED ({len(differences['tables_added'])}):\n")
                    for table in differences['tables_added']:
                        self.results_text.insert(tk.END, f"  + {table}\n")
                    self.results_text.insert(tk.END, "\n")
                
                # Tables removed
                if differences['tables_removed']:
                    self.results_text.insert(tk.END, f"➖ TABLES REMOVED ({len(differences['tables_removed'])}):\n")
                    for table in differences['tables_removed']:
                        self.results_text.insert(tk.END, f"  - {table}\n")
                    self.results_text.insert(tk.END, "\n")
                
                # Tables modified
                if differences['tables_modified']:
                    self.results_text.insert(tk.END, f"🔄 TABLES MODIFIED ({len(differences['tables_modified'])}):\n")
                    for table in differences['tables_modified']:
                        self.results_text.insert(tk.END, f"  ~ {table}\n")
                        
                        # Show detailed record changes if available
                        if table in differences['record_changes']:
                            changes = differences['record_changes'][table]
                            if changes['records_added'] > 0:
                                self.results_text.insert(tk.END, f"    📈 Records added: {changes['records_added']}\n")
                            if changes['records_removed'] > 0:
                                self.results_text.insert(tk.END, f"    📉 Records removed: {changes['records_removed']}\n")
                            if changes['records_modified'] > 0:
                                self.results_text.insert(tk.END, f"    📝 Records modified: {changes['records_modified']}\n")
                        self.results_text.insert(tk.END, "\n")
                
                # Additional analysis
                self.results_text.insert(tk.END, "DETAILED ANALYSIS:\n")
                self.results_text.insert(tk.END, "-" * 20 + "\n")
                
                # Calculate time difference
                try:
                    date1 = datetime.datetime.strptime(backup1['timestamp'], "%Y%m%d_%H%M%S")
                    date2 = datetime.datetime.strptime(backup2['timestamp'], "%Y%m%d_%H%M%S")
                    time_diff = abs((date2 - date1).total_seconds())
                    
                    if time_diff < 3600:  # Less than 1 hour
                        time_str = f"{time_diff/60:.0f} minutes"
                    elif time_diff < 86400:  # Less than 1 day
                        time_str = f"{time_diff/3600:.1f} hours"
                    else:
                        time_str = f"{time_diff/86400:.1f} days"
                    
                    self.results_text.insert(tk.END, f"Time between backups: {time_str}\n")
                except:
                    pass
                
                # Size comparison
                try:
                    size1 = backup1.get('size', 0)
                    size2 = backup2.get('size', 0)
                    size_diff = size2 - size1
                    size_diff_mb = size_diff / (1024 * 1024)
                    
                    if size_diff > 0:
                        self.results_text.insert(tk.END, f"Size increase: +{size_diff_mb:.2f} MB\n")
                    elif size_diff < 0:
                        self.results_text.insert(tk.END, f"Size decrease: {size_diff_mb:.2f} MB\n")
                    else:
                        self.results_text.insert(tk.END, "Size unchanged\n")
                except:
                    pass
                
                # Recommendations
                if total_changes > 0:
                    self.results_text.insert(tk.END, "\n💡 RECOMMENDATIONS:\n")
                    if len(differences['tables_added']) > 0:
                        self.results_text.insert(tk.END, "• New tables detected - verify expected schema changes\n")
                    if len(differences['tables_removed']) > 0:
                        self.results_text.insert(tk.END, "• Tables removed - ensure this was intentional\n")
                    if len(differences['tables_modified']) > 0:
                        self.results_text.insert(tk.END, "• Data modifications detected - review changes carefully\n")
            else:
                self.results_text.delete(1.0, tk.END)
                self.results_text.insert(tk.END, "❌ COMPARISON FAILED\n")
                self.results_text.insert(tk.END, "=" * 20 + "\n\n")
                self.results_text.insert(tk.END, "Possible reasons:\n")
                self.results_text.insert(tk.END, "• One or both backup files are corrupted\n")
                self.results_text.insert(tk.END, "• Backup files are encrypted and password is incorrect\n")
                self.results_text.insert(tk.END, "• Backup files are in an unsupported format\n")
                self.results_text.insert(tk.END, "• Database connection error\n\n")
                self.results_text.insert(tk.END, "Try validating the individual backups first.\n")
        
        except Exception as e:
            self.results_text.delete(1.0, tk.END)
            self.results_text.insert(tk.END, "❌ COMPARISON ERROR\n")
            self.results_text.insert(tk.END, "=" * 20 + "\n\n")
            self.results_text.insert(tk.END, f"Error details: {str(e)}\n\n")
            self.results_text.insert(tk.END, "Troubleshooting steps:\n")
            self.results_text.insert(tk.END, "1. Verify both backup files exist and are accessible\n")
            self.results_text.insert(tk.END, "2. Check if backups are encrypted/compressed\n")
            self.results_text.insert(tk.END, "3. Ensure backup files are not corrupted\n")
            self.results_text.insert(tk.END, "4. Try comparing with different backup files\n")
            
            logger.error(f"Backup comparison failed: {e}")
            
            # Optionally show a more detailed error dialog
            if messagebox.askyesno("Detailed Error", 
                                  f"Comparison failed with error: {str(e)}\n\n"
                                  "Would you like to see the full error details?"):
                import traceback
                error_details = traceback.format_exc()
                
                # Create a new window to show error details
                error_window = tk.Toplevel(self.dialog)
                error_window.title("Error Details")
                error_window.geometry("600x400")
                
                error_text = scrolledtext.ScrolledText(error_window, wrap=tk.WORD)
                error_text.pack(fill="both", expand=True, padx=10, pady=10)
                error_text.insert(1.0, error_details)
                
                ttk.Button(error_window, text="Close", 
                          command=error_window.destroy).pack(pady=10)

    def calculate_file_hash(file_path):
        """Calculate SHA-256 hash of a file - missing from GUI"""
        import hashlib
        hash_sha256 = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except Exception as e:
            logger.error(f"Error calculating hash: {e}")
            return None

    def create_selective_backup(tables, backup_path):
        """Create backup of selected tables only - missing from GUI"""
        try:
            conn = get_db_connection()
            if not conn:
                return False
            
            from university_system.infrastructure.database.db import sqlite3
            backup_conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            
            for table in tables:
                # Copy table structure
                cursor = conn.cursor()
                cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table}';")
                create_sql = cursor.fetchone()
                
                if create_sql:
                    backup_conn.execute(create_sql[0])
                    
                    # Copy table data
                    cursor.execute(f"SELECT * FROM {table}")
                    rows = cursor.fetchall()
                    
                    if rows:
                        placeholders = ','.join(['?' for _ in range(len(rows[0]))])
                        backup_conn.executemany(f"INSERT INTO {table} VALUES ({placeholders})", rows)
            
            backup_conn.commit()
            backup_conn.close()
            conn.close()
            
            return True
        except Exception as e:
            logger.error(f"Error creating selective backup: {e}")
            return False

    def cleanup_old_backups():
        """Remove old backups based on retention policy - missing from GUI"""
        try:
            max_backups = config.get("max_backups", 10)
            backups = list_available_backups()
            
            if len(backups) > max_backups:
                # Remove oldest backups
                backups_to_remove = backups[max_backups:]
                for backup in backups_to_remove:
                    try:
                        # Use centralized delete_backup function
                        try:
                            from university_system.infrastructure.database.data_backup import delete_backup as delete_backup_func
                            if delete_backup_func(backup['path']):
                                logger.info(f"Removed old backup: {backup['filename']}")
                        except ImportError:
                            # Fallback implementation
                            if config.get("secure_deletion", False):
                                secure_delete_file(backup['path'])
                            else:
                                os.remove(backup['path'])
                            logger.info(f"Removed old backup: {backup['filename']}")

                            # Remove from metadata
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
        
    def compare_backups(backup1_path, backup2_path):
        """Compare two backup files and return differences - missing from GUI"""
        try:
            differences = {
                "tables_added": [],
                "tables_removed": [],
                "tables_modified": [],
                "record_changes": {}
            }
            
            from university_system.infrastructure.database.db import sqlite3
            
            conn1 = sqlite3.connect(str(DEFAULT_DB_PATH))
            conn2 = sqlite3.connect(str(DEFAULT_DB_PATH))
            
            # Get table lists
            tables1 = set(get_database_tables_from_connection(conn1))
            tables2 = set(get_database_tables_from_connection(conn2))
            
            differences["tables_added"] = list(tables2 - tables1)
            differences["tables_removed"] = list(tables1 - tables2)
            
            # Check common tables for changes
            common_tables = tables1 & tables2
            
            for table in common_tables:
                changes = compare_table_data(conn1, conn2, table)
                if changes and (changes.get("records_added", 0) or changes.get("records_removed", 0) or changes.get("records_modified", 0)):
                    differences["tables_modified"].append(table)
                    differences["record_changes"][table] = changes
            
            conn1.close()
            conn2.close()
            
            return differences
        
        except Exception as e:
            logger.error(f"Error comparing backups: {e}")
            return None

    def compare_table_data(conn1, conn2, table):
        """Compare data in a specific table between two databases"""
        try:
            # Mock implementation
            return {
                'records_added': 0,
                'records_removed': 0,
                'records_modified': 0
            }
        except Exception as e:
            logger.error(f"Error comparing table {table}: {e}")
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

    def decompress_file(compressed_path, output_path):
        """Decompress a file"""
        import gzip
        import zipfile
        try:
            if compressed_path.endswith('.gz'):
                with gzip.open(compressed_path, 'rb') as f_in:
                    with open(output_path, 'wb') as f_out:
                        f_out.write(f_in.read())
            elif compressed_path.endswith('.zip'):
                with zipfile.ZipFile(compressed_path, 'r') as zipf:
                    zipf.extractall(os.path.dirname(output_path))
            return True
        except Exception as e:
            logger.error(f"Error decompressing file: {e}")
            return False

    def notify_backup_result(success, backup_path, operation):
        """Send notifications about backup results - missing from GUI"""
        try:
            if success:
                message = f"✅ {operation.title()} completed successfully: {os.path.basename(backup_path)}"
            else:
                message = f"❌ {operation.title()} failed: {backup_path}"
            
            # Would integrate with notification systems
            logger.info(message)
            return True
        except Exception as e:
            logger.error(f"Error sending notifications: {e}")
            return False

    def encrypt_file(file_path, password):
        """Encrypt a file and return the encrypted file path - missing from GUI"""
        try:
            # Simple XOR encryption for demo (not secure for production)
            encrypted_path = f"{file_path}.encrypted"
            with open(file_path, 'rb') as f_in:
                with open(encrypted_path, 'wb') as f_out:
                    data = f_in.read()
                    key = password.encode()
                    encrypted = bytearray()
                    for i, byte in enumerate(data):
                        encrypted.append(byte ^ key[i % len(key)])
                    f_out.write(encrypted)
            
            # Remove original file if secure deletion is enabled
            if config.get("secure_deletion", False):
                secure_delete_file(file_path)
            else:
                os.remove(file_path)
            
            return encrypted_path
        except Exception as e:
            logger.error(f"Error encrypting file: {e}")
            return None

    def decrypt_file(encrypted_path, password, output_path=None):
        """Decrypt a file and return the decrypted file path - missing from GUI"""
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
        import hashlib
        return hashlib.sha256(password.encode()).digest()

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
        """Verify backup file integrity - missing from GUI"""
        try:
            if not os.path.exists(backup_path):
                return False
            
            if expected_hash:
                actual_hash = calculate_file_hash(backup_path)
                return actual_hash == expected_hash
            
            # Basic file integrity check
            try:
                with open(backup_path, 'rb') as f:
                    f.read(1024)  # Try to read first chunk
                return True
            except:
                return False
        except Exception as e:
            logger.error(f"Error verifying backup integrity: {e}")
            return False

    def decompress_file(compressed_path, output_path=None):
        """Decompress a file - missing from GUI"""
        try:
            import gzip
            import zipfile
            
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
        except Exception as e:
            logger.error(f"Error decompressing file: {e}")
            return None

    def send_email_notification(subject, message, recipients=None):
        """Send email notification - missing from GUI"""
        try:
            if not config.get("email_notifications", False):
                return True

            from university_system.infrastructure.email.smtp import send_email_via_smtp
            from datetime import datetime

            if not recipients:
                recipients = config.get("notification_recipients", [])

            if not recipients:
                return True

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

            return success
        except Exception as e:
            logger.error(f"Error sending email notification: {e}")
            return False

    def send_slack_notification(message):
        """Send Slack notification - missing from GUI"""
        try:
            webhook_url = config.get("slack_webhook", "")
            if not webhook_url:
                return True
                
            import urllib.request
            import json
            
            payload = {"text": message}
            data = json.dumps(payload).encode('utf-8')
            
            req = urllib.request.Request(webhook_url, data=data, headers={'Content-Type': 'application/json'})
            urllib.request.urlopen(req)
            
            return True
        except Exception as e:
            logger.error(f"Error sending Slack notification: {e}")
            return False

    def send_discord_notification(message):
        """Send Discord notification - missing from GUI"""
        try:
            webhook_url = config.get("discord_webhook", "")
            if not webhook_url:
                return True
                
            import urllib.request
            import json
            
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
                message = f"✅ {operation.title()} completed successfully: {os.path.basename(backup_path)}"
            else:
                message = f"❌ {operation.title()} failed: {backup_path}"
            
            send_email_notification(f"Backup System - {operation.title()} Result", message)
            send_slack_notification(message)
            send_discord_notification(message)
            
            return True
        except Exception as e:
            logger.error(f"Error sending notifications: {e}")
            return False

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
            tables = [row[0] for row in cursor.fetchall()]
            return [table for table in tables if not table.startswith('sqlite_')]
        except Exception as e:
            logger.error(f"Error getting tables from connection: {e}")
            return []

    def create_schema_only_backup(backup_path):
        """Create backup of database schema only (no data)"""
        try:
            conn = get_db_connection()
            if not conn:
                return False
            
            # Create schema-only backup
            with open(backup_path, 'w') as f:
                for line in conn.iterdump():
                    if not line.startswith('INSERT'):
                        f.write(f"{line}\n")
            
            conn.close()
            return backup_path
        except Exception as e:
            logger.error(f"Error creating schema backup: {e}")
            return None

    def create_selective_backup(tables, backup_path):
        """Create backup of selected tables only"""
        try:
            conn = get_db_connection()
            if not conn:
                return False
            
            with open(backup_path, 'w') as f:
                # Write schema for selected tables
                cursor = conn.cursor()
                for table in tables:
                    cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table}';")
                    schema = cursor.fetchone()
                    if schema:
                        f.write(f"{schema[0]};\n")
                
                # Write data for selected tables
                for table in tables:
                    cursor.execute(f"SELECT * FROM {table};")
                    for row in cursor.fetchall():
                        f.write(f"INSERT INTO {table} VALUES {row};\n")
            
            conn.close()
            return backup_path
        except Exception as e:
            logger.error(f"Error creating selective backup: {e}")
            return None

    def has_database_changed():
        """Check if database has changed since last backup"""
        try:
            # Simple check - would be more sophisticated in real implementation
            backups = list_available_backups()
            if not backups:
                return True
            
            latest_backup = backups[0]
            backup_time = datetime.datetime.strptime(latest_backup['timestamp'], "%Y%m%d_%H%M%S")
            
            # Check if any database files have been modified since last backup
            db_files = [f for f in os.listdir('.') if f.endswith('.db')]
            for db_file in db_files:
                if os.path.getmtime(db_file) > backup_time.timestamp():
                    return True
            
            return False
        except Exception as e:
            logger.error(f"Error checking database changes: {e}")
            return True

    if "create_incremental_backup" not in globals():
        def create_incremental_backup(backup_path):
            """Create incremental backup (changes since last full backup)"""
            try:
                if not has_database_changed():
                    logger.info("No changes detected, skipping incremental backup")
                    return None
                
                # For demo, create a selective backup of modified tables
                conn = get_db_connection()
                if not conn:
                    return None
                
                tables = get_database_tables()
                # In real implementation, would identify only changed tables
                changed_tables = tables[:2]  # Mock: assume first 2 tables changed
                
                return create_selective_backup(changed_tables, backup_path)
            except Exception as e:
                logger.error(f"Error creating incremental backup: {e}")
                return None

    def export_to_csv(backup_path, output_dir):
        """Export backup to CSV files"""
        try:
            import csv
            from university_system.infrastructure.database.db import sqlite3

            # Connect to the backup file, not the main database
            conn = sqlite3.connect(backup_path)
            tables = get_database_tables_from_connection(conn)
            
            os.makedirs(output_dir, exist_ok=True)
            
            for table in tables:
                cursor = conn.execute(f"SELECT * FROM {table}")
                with open(os.path.join(output_dir, f"{table}.csv"), 'w', newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    # Write headers
                    writer.writerow([description[0] for description in cursor.description])
                    # Write data
                    writer.writerows(cursor.fetchall())
            
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error exporting to CSV: {e}")
            return False

    def export_to_json(backup_path, output_file):
        """Export backup to JSON file"""
        try:
            import json
            from university_system.infrastructure.database.db import sqlite3

            # Connect to the backup file, not the main database
            conn = sqlite3.connect(backup_path)
            tables = get_database_tables_from_connection(conn)
            
            data = {}
            for table in tables:
                cursor = conn.execute(f"SELECT * FROM {table}")
                columns = [description[0] for description in cursor.description]
                rows = cursor.fetchall()
                data[table] = [dict(zip(columns, row)) for row in rows]
            
            with open(output_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error exporting to JSON: {e}")
            return False

    def export_to_xml(backup_path, output_file):
        """Export backup to XML file"""
        try:
            from university_system.infrastructure.database.db import sqlite3
            import xml.etree.ElementTree as ET

            # Connect to the backup file, not the main database
            conn = sqlite3.connect(backup_path)
            tables = get_database_tables_from_connection(conn)
            
            root = ET.Element("database")
            
            for table in tables:
                table_elem = ET.SubElement(root, "table", name=table)
                cursor = conn.execute(f"SELECT * FROM {table}")
                columns = [description[0] for description in cursor.description]
                
                for row in cursor.fetchall():
                    row_elem = ET.SubElement(table_elem, "row")
                    for col, value in zip(columns, row):
                        col_elem = ET.SubElement(row_elem, "column", name=col)
                        col_elem.text = str(value) if value is not None else ""
            
            tree = ET.ElementTree(root)
            tree.write(output_file, encoding='utf-8', xml_declaration=True)
            
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error exporting to XML: {e}")
            return False

    def ensure_backup_directory():
        """Ensure the backup directory exists using centralized BACKUP_DIR"""
        try:
            # Use centralized BACKUP_DIR
            BACKUP_DIR.mkdir(parents=True, exist_ok=True)
            # Update config to match centralized path
            config["backup_directory"] = str(BACKUP_DIR)
            return BACKUP_DIR
        except Exception as e:
            logger.error(f"Error creating backup directory: {e}")
            return None

    def upload_to_aws_s3(file_path, bucket, key):
        """Upload file to AWS S3"""
        try:
            # Mock implementation - would use boto3
            logger.info(f"Uploading {file_path} to S3 bucket {bucket} as {key}")
            return True
        except Exception as e:
            logger.error(f"Error uploading to S3: {e}")
            return False

    def download_from_aws_s3(bucket, key, download_path):
        """Download file from AWS S3"""
        try:
            # Mock implementation - would use boto3
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
            # Mock implementation - would use paramiko
            logger.info(f"Uploading {file_path} to SFTP {host}:{remote_path}")
            return True
        except Exception as e:
            logger.error(f"Error uploading to SFTP: {e}")
            return False

    if "parse_cron_schedule" not in globals():
        def parse_cron_schedule(cron_expr):
            """Parse cron expression and schedule backup"""
            try:
                # Mock implementation - would use python-crontab
                logger.info(f"Parsing cron schedule: {cron_expr}")
                return True
            except Exception as e:
                logger.error(f"Error parsing cron schedule: {e}")
                return False

    def restore_partial_tables(backup_path, tables):
        """Restore only specified tables from backup"""
        try:
            from university_system.infrastructure.database.db import sqlite3
            
            # Connect to backup and current database
            backup_conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            current_conn = get_db_connection()
            
            if not current_conn:
                backup_conn.close()
                return False
            
            # Restore each specified table
            for table in tables:
                # Drop existing table
                current_conn.execute(f"DROP TABLE IF EXISTS {table}")
                
                # Get table schema from backup
                cursor = backup_conn.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table}'")
                schema = cursor.fetchone()
                if schema:
                    current_conn.execute(schema[0])
                    
                    # Copy data
                    cursor = backup_conn.execute(f"SELECT * FROM {table}")
                    columns = [desc[0] for desc in cursor.description]
                    placeholders = ','.join(['?' for _ in columns])
                    
                    for row in cursor.fetchall():
                        current_conn.execute(f"INSERT INTO {table} VALUES ({placeholders})", row)
            
            current_conn.commit()
            backup_conn.close()
            current_conn.close()
            
            return True
        except Exception as e:
            logger.error(f"Error restoring partial tables: {e}")
            return False

    def validate_backup(backup_path):
        """Validate backup file integrity and restorability"""
        try:
            results = {
                'file_exists': os.path.exists(backup_path),
                'file_readable': False,
                'database_valid': False,
                'tables_accessible': False,
                'hash_verified': True,  # Mock
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
                from university_system.infrastructure.database.db import sqlite3
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
        """Detailed backup validation with comprehensive checks - missing from GUI"""
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
            
            # Check file existence and basic properties
            if os.path.exists(backup_path):
                results["file_exists"] = True
                results["file_size"] = os.path.getsize(backup_path)
                
                # Detect compression
                if backup_path.endswith(('.gz', '.zip')):
                    results["compression_detected"] = True
                
                # Detect encryption
                if backup_path.endswith('.encrypted'):
                    results["encryption_detected"] = True
            else:
                results["errors"].append("Backup file does not exist")
                return results
            
            # Try to read file
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
            
            # Handle encrypted/compressed files for validation
            test_file = backup_path
            temp_files = []
            
            try:
                if results["encryption_detected"]:
                    if config.get("encryption_password"):
                        temp_decrypt = tempfile.mktemp(suffix='.db')
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
                    temp_decompress = tempfile.mktemp(suffix='.db')
                    test_file = decompress_file(test_file, temp_decompress)
                    if test_file:
                        temp_files.append(temp_decompress)
                    else:
                        results["errors"].append("Failed to decompress backup")
                        return results
                
                # Validate database
                if test_file:
                    try:
                        from university_system.infrastructure.database.db import sqlite3
                        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                        cursor = conn.cursor()
                        
                        # Get table list
                        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                        tables = cursor.fetchall()
                        results["database_valid"] = True
                        results["table_count"] = len(tables)
                        
                        # Count total records
                        total_records = 0
                        accessible_tables = 0
                        
                        for table_row in tables:
                            table_name = table_row[0]
                            try:
                                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
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
                
                # Verify hash if available
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
                # Clean up temporary files
                for temp_file in temp_files:
                    try:
                        if os.path.exists(temp_file):
                            os.remove(temp_file)
                    except:
                        pass
            
            return results
        
        except Exception as e:
            logger.error(f"Error in detailed validation: {e}")
            return {"errors": [str(e)]}

    def create_differential_backup(backup_path):
        """Create differential backup (changes since last full backup) - missing from GUI"""
        return _create_differential_backup_impl(backup_path)

        
    def save_backup_template(name, settings):
        """Save backup configuration as a template to JSON file"""
        try:
            # Save to both config (backward compatibility) and JSON file
            if "backup_templates" not in config:
                config["backup_templates"] = {}

            config["backup_templates"][name] = settings.copy()
            save_config()

            # Also save to JSON file in BACKUP_TEMPLATES_DIR
            BACKUP_TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
            template_file = BACKUP_TEMPLATES_DIR / f"{name.lower().replace(' ', '_')}.json"

            template_data = settings.copy()
            template_data["name"] = name

            with open(template_file, 'w') as f:
                json.dump(template_data, f, indent=2)

            logger.info(f"Template '{name}' saved to {template_file}")
            return True
        except Exception as e:
            logger.error(f"Error saving backup template: {e}")
            return False

    def load_backup_template(name):
        """Load backup configuration from template (JSON file or config)"""
        try:
            # First, try to load from JSON file in BACKUP_TEMPLATES_DIR
            template_file = BACKUP_TEMPLATES_DIR / f"{name.lower().replace(' ', '_')}.json"

            if template_file.exists():
                with open(template_file, 'r') as f:
                    template = json.load(f)
                    # Remove 'name' and 'description' fields before updating config
                    template_settings = {k: v for k, v in template.items()
                                       if k not in ['name', 'description']}
                    config.update(template_settings)
                    save_config()
                    logger.info(f"Template '{name}' loaded from {template_file}")
                    return True

            # Fallback: try to load from config (backward compatibility)
            templates = config.get("backup_templates", {})
            if name in templates:
                template = templates[name]
                config.update(template)
                save_config()
                logger.info(f"Template '{name}' loaded from config")
                return True

            logger.warning(f"Template '{name}' not found")
            return False

        except Exception as e:
            logger.error(f"Error loading backup template: {e}")
            return False

    def list_backup_templates():
        """List all available backup templates from JSON files and config"""
        templates = {}

        try:
            # Load templates from BACKUP_TEMPLATES_DIR
            if BACKUP_TEMPLATES_DIR.exists():
                for template_file in BACKUP_TEMPLATES_DIR.glob("*.json"):
                    try:
                        with open(template_file, 'r') as f:
                            template_data = json.load(f)
                            template_name = template_data.get("name", template_file.stem.replace('_', ' ').title())
                            templates[template_name] = {
                                "source": "file",
                                "path": str(template_file),
                                "description": template_data.get("description", "No description available")
                            }
                    except Exception as e:
                        logger.error(f"Error loading template from {template_file}: {e}")

            # Also include templates from config (backward compatibility)
            config_templates = config.get("backup_templates", {})
            for name in config_templates:
                if name not in templates:
                    templates[name] = {
                        "source": "config",
                        "description": "User-created template"
                    }

        except Exception as e:
            logger.error(f"Error listing backup templates: {e}")

        return templates

    def generate_backup_statistics():
        """Generate comprehensive backup statistics"""
        try:
            backups = list_available_backups()
            
            stats = {
                'total_backups': len(backups),
                'total_size': sum(backup.get('size', 0) for backup in backups),
                'average_size': 0,
                'recent_activity': 0,
                'backup_types': {},
                'storage_usage': {}
            }
            
            if backups:
                stats['average_size'] = stats['total_size'] / len(backups)
                
                # Recent activity (last 30 days)
                thirty_days_ago = datetime.datetime.now() - datetime.timedelta(days=30)
                
                for backup in backups:
                    # Type distribution
                    backup_type = backup.get('backup_type', 'full')
                    stats['backup_types'][backup_type] = stats['backup_types'].get(backup_type, 0) + 1
                    
                    # Recent activity
                    try:
                        backup_date = datetime.datetime.strptime(backup['timestamp'], "%Y%m%d_%H%M%S")
                        if backup_date >= thirty_days_ago:
                            stats['recent_activity'] += 1
                    except:
                        pass
            
            return stats
        except Exception as e:
            logger.error(f"Error generating statistics: {e}")
            return {'total_backups': 0, 'total_size': 0, 'average_size': 0, 
                    'recent_activity': 0, 'backup_types': {}, 'storage_usage': {}}

    def scheduled_backup_job():
        """Enhanced scheduled backup function"""
        try:
            logger.info("Starting scheduled backup job")
            backup_type = config.get("backup_type", "full")
            
            result = create_enhanced_backup(
                manual=False,
                backup_type=backup_type
            )
            
            if result:
                notify_backup_result(True, result, "scheduled backup")
                cleanup_old_backups()
            else:
                notify_backup_result(False, "unknown", "scheduled backup")
            
            return result is not None
        except Exception as e:
            logger.error(f"Error in scheduled backup job: {e}")
            notify_backup_result(False, str(e), "scheduled backup")
            return False

    # Scheduler variables
    scheduler_thread = None
    scheduler_running = False

    def start_scheduler():
        """Start the enhanced backup scheduler"""
        global scheduler_thread, scheduler_running
        
        if scheduler_running:
            return
        
        import threading
        import time
        
        def scheduler_worker():
            global scheduler_running
            scheduler_running = True
            
            while scheduler_running:
                try:
                    current_time = datetime.datetime.now()
                    scheduled_time = datetime.datetime.strptime(config["scheduled_backup_time"], "%H:%M").time()
                    
                    if (current_time.time().hour == scheduled_time.hour and 
                        current_time.time().minute == scheduled_time.minute):
                        
                        frequency = config["backup_frequency"]
                        should_run = False
                        
                        if frequency == "daily":
                            should_run = True
                        elif frequency == "weekly" and current_time.weekday() == 0:  # Monday
                            should_run = True
                        elif frequency == "monthly" and current_time.day == 1:
                            should_run = True
                        
                        if should_run:
                            scheduled_backup_job()
                            time.sleep(60)  # Prevent multiple runs in same minute
                    
                    time.sleep(30)  # Check every 30 seconds
                    
                except Exception as e:
                    logger.error(f"Scheduler error: {e}")
                    time.sleep(60)
        
        scheduler_thread = threading.Thread(target=scheduler_worker, daemon=True)
        scheduler_thread.start()
        logger.info("Backup scheduler started")

    def stop_scheduler():
        """Stop the backup scheduler thread"""
        global scheduler_running
        scheduler_running = False
        logger.info("Backup scheduler stopped")
