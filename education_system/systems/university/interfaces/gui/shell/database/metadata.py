"""Backup metadata and progress tracking."""
import os
import json
import time

from education_system.systems.university.interfaces.gui.shell.database.shared_imports import (
    DATA_DIR, logger,
)


class ProgressTracker:
    """Progress tracking for backup operations"""
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


class BackupMetadata:
    """Class to handle backup metadata and tracking"""

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
