"""Repository and unit-of-work contracts for university core domains."""

from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Any, Protocol, TypeVar

T = TypeVar("T")


class Repository(Protocol[T]):
    def get(self, identifier: str | int) -> T | None: ...

    def add(self, entity: T) -> str | int: ...


class UnitOfWork(Protocol):
    connection: Any

    def __enter__(self) -> "UnitOfWork": ...

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> bool: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...


UnitOfWorkFactory = type[AbstractContextManager[UnitOfWork]]

__all__ = ["Repository", "UnitOfWork", "UnitOfWorkFactory"]
