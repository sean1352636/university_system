"""Shared path factory for all education subsystems.

Provides a ``SystemPaths`` dataclass and a ``get_system_paths()`` factory
that returns correctly configured paths for any subsystem, eliminating the
need for each subsystem to define its own paths module from scratch.

Each subsystem's ``core/paths.py`` can use this factory and then add any
system-specific paths on top.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List


@dataclass
class SystemPaths:
    """Standard directory layout for an education subsystem."""

    system_root: Path
    db_name: str

    # Derived paths (computed in __post_init__)
    project_root: Path = field(init=False)
    data_dir: Path = field(init=False)
    db_dir: Path = field(init=False)
    db_file: Path = field(init=False)
    config_dir: Path = field(init=False)
    logs_dir: Path = field(init=False)
    locales_dir: Path = field(init=False)

    def __post_init__(self):
        self.project_root = self.system_root.parent
        self.data_dir = self.system_root / "data"
        self.db_dir = self.data_dir / "db_files"
        self.db_file = self.db_dir / self.db_name
        self.config_dir = self.data_dir / "config"
        self.logs_dir = self.system_root / "logs"
        self.locales_dir = self.data_dir / "locales"

    @property
    def required_dirs(self) -> List[Path]:
        """Directories that must exist at startup."""
        return [self.db_dir, self.config_dir, self.logs_dir]

    def ensure_directories(self) -> None:
        """Create all required directories if they don't exist."""
        for d in self.required_dirs:
            d.mkdir(parents=True, exist_ok=True)


def get_system_paths(core_file: str, db_name: str) -> SystemPaths:
    """Create a ``SystemPaths`` instance for a subsystem.

    Parameters
    ----------
    core_file:
        Pass ``__file__`` from the calling subsystem's ``core/paths.py``.
        The system root is derived as the grandparent of this file
        (``core/paths.py`` -> ``core/`` -> ``<system_root>/``).
    db_name:
        Filename for the subsystem's SQLite database (e.g. ``"sixthform.db"``).
    """
    system_root = Path(core_file).resolve().parent.parent
    return SystemPaths(system_root=system_root, db_name=db_name)
