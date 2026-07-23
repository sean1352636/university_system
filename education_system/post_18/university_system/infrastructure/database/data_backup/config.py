"""Backup configuration, defaults, and global state."""

import json
import logging
import threading
from pathlib import Path

from education_system.post_18.university_system.core.paths import DATA_DIR, BACKUP_DATABASE_DIR
from education_system.post_18.university_system.core.i18n import get_text as _t, init_i18n
from education_system.post_18.university_system.infrastructure.logging.log_config import configure_logging

init_i18n()

logger = configure_logging(name=__name__)

# Enhanced default configuration
DEFAULT_CONFIG = {
    "backup_directory": str(BACKUP_DATABASE_DIR),
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


def _active_config() -> dict:
    import sys

    package = sys.modules.get("education_system.post_18.university_system.infrastructure.database.data_backup")
    package_config = getattr(package, "config", None)
    if isinstance(package_config, dict):
        return package_config
    return config


def _config_path() -> Path:
    return Path(DATA_DIR) / "backup_config.json"


def load_config():
    """Load backup configuration from file"""
    global config

    active_config = _active_config()
    config_path = _config_path()
    if config_path.exists():
        try:
            with open(config_path, "r") as f:
                loaded_config = json.load(f)
                # Update default config with loaded values
                active_config.update(loaded_config)
                config = active_config
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
        config_path = _config_path()
        with open(config_path, "w") as f:
            json.dump(_active_config(), f, indent=4)
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
