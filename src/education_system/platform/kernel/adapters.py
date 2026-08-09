"""Supported local adapters for platform ports."""

from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

from education_system.paths import VAR_DIR


@dataclass(frozen=True)
class EnvironmentConfiguration:
    def get(self, name: str, default: str | None = None) -> str | None:
        return os.environ.get(name, default)


@dataclass(frozen=True)
class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


@dataclass(frozen=True)
class ClassifiedStorage:
    """Keep special-category data in physically distinct database files."""

    root: Path = VAR_DIR / "data" / "university"

    def database_path(self, classification: str) -> Path:
        names = {
            "general": "student/student_records.db",
            "health": "health/health_records.db",
            "safeguarding": "safeguarding/safeguarding_records.db",
        }
        try:
            relative = names[classification]
        except KeyError as exc:
            raise ValueError(f"Unknown storage classification: {classification}") from exc
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        return path


class UniversityDatabaseAdapter:
    @contextmanager
    def transaction(self) -> Iterator[Any]:
        from education_system.systems.university.infrastructure.database.db import transaction

        with transaction() as connection:
            yield connection


__all__ = [
    "ClassifiedStorage",
    "EnvironmentConfiguration",
    "SystemClock",
    "UniversityDatabaseAdapter",
]
