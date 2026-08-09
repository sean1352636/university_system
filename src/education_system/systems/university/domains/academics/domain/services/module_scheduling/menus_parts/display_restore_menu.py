"""Extracted function implementation."""

from .. import menus_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def display_restore_menu(scheduler):
    """Display restore menu"""
    scheduler.list_backups()

    if input("\nProceed with restore? (y/n): ").lower() != 'y':
        return

    backup_name = input("Enter backup name to restore: ").strip()
    if backup_name:
        scheduler.restore_backup(backup_name)
