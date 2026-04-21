"""Backup metadata tracking and persistence."""

import json
import os

from education_system.university_system.core.paths import DATA_DIR
from education_system.university_system.infrastructure.logging.log_config import configure_logging

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
