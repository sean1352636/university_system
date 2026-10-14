"""Compatibility façade for the split implementation."""

from . import backup_gui_shared as _shared
from .backup_gui_shared import *  # noqa: F401,F403

from .backup_gui_parts import backupgui_init as _part_1_1
from .backup_gui_parts import backupgui_create_logs_tab as _part_1_2
from .backup_gui_parts import backupgui_download_backup_gui as _part_1_3
from .backup_gui_parts import backupgui_enable_backup_deduplication as _part_1_4
class BackupGUI(_part_1_1.BackupGUI, _part_1_2.BackupGUI, _part_1_3.BackupGUI, _part_1_4.BackupGUI):
    """Main GUI class for the enhanced backup system"""
_shared.BackupGUI = BackupGUI
_shared.__all__.append("BackupGUI") if "BackupGUI" not in _shared.__all__ else None

from .backup_gui_parts import reportgeneratordialog as _part_2
ReportGeneratorDialog = _part_2.ReportGeneratorDialog
_shared.ReportGeneratorDialog = ReportGeneratorDialog
_shared.__all__.append("ReportGeneratorDialog") if "ReportGeneratorDialog" not in _shared.__all__ else None

from .backup_gui_parts import databasesettingsdialog as _part_3
DatabaseSettingsDialog = _part_3.DatabaseSettingsDialog
_shared.DatabaseSettingsDialog = DatabaseSettingsDialog
_shared.__all__.append("DatabaseSettingsDialog") if "DatabaseSettingsDialog" not in _shared.__all__ else None

from .backup_gui_parts import migrationtoolsdialog as _part_4
MigrationToolsDialog = _part_4.MigrationToolsDialog
_shared.MigrationToolsDialog = MigrationToolsDialog
_shared.__all__.append("MigrationToolsDialog") if "MigrationToolsDialog" not in _shared.__all__ else None

_exports = {name: globals()[name] for name in ['BackupGUI', 'DatabaseSettingsDialog', 'MigrationToolsDialog', 'ReportGeneratorDialog']}
for _module in [_part_1_1, _part_1_2, _part_1_3, _part_1_4, _part_2, _part_3, _part_4]:
    _module.__dict__.update(_exports)


# Keep extracted callables synchronized with compatibility-module globals.
for _module in [_part_1_1, _part_1_2, _part_1_3, _part_1_4, _part_2, _part_3, _part_4]:
    _module.__dict__.update({name: value for name, value in globals().items() if not name.startswith("__")})

__all__ = ['BackupGUI', 'DatabaseSettingsDialog', 'MigrationToolsDialog', 'ReportGeneratorDialog']
