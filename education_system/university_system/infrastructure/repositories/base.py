"""Base repository interfaces and abstract classes.

This module defines the foundation for the Repository pattern implementation,
providing abstract base classes and common interfaces that all repositories
must implement.

The Repository pattern provides:
- Abstraction over data access
- Domain-centric data retrieval interface
- Unit of Work integration potential
- Easy testing through interface-based design
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import (
    Any,
    Callable,
    Generic,
    Iterable,
    Iterator,
    Optional,
    TypeVar,
    Union,
)

# Type variable for entity ID (usually str or int)
ID = TypeVar("ID")

# Type variable for entity type
T = TypeVar("T", bound="Entity")


@dataclass
class Entity:
    """Base class for all domain entities.

    Entities are objects with a distinct identity that persists over time.
    Unlike value objects, two entities are equal if they have the same
    identity, regardless of their attributes.

    Attributes:
        id: The unique identifier for this entity.
        created_at: Timestamp when the entity was created.
        updated_at: Timestamp when the entity was last updated.
    """

    id: Optional[str] = None
    created_at: Optional[datetime] = field(default=None, compare=False)
    updated_at: Optional[datetime] = field(default=None, compare=False)

    def __post_init__(self) -> None:
        """Set timestamps if not provided."""
        now = datetime.now()
        if self.created_at is None:
            self.created_at = now
        if self.updated_at is None:
            self.updated_at = now

    def mark_updated(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = datetime.now()


class Repository(ABC, Generic[T, ID]):
    """Abstract base class for all repositories.

    A Repository mediates between the domain and data mapping layers,
    acting like an in-memory collection of domain objects. It provides
    methods to add, remove, and retrieve entities.

    Generic Parameters:
        T: The type of entity this repository manages.
        ID: The type of the entity's identifier.

    Example:
        class StudentRepository(Repository[Student, str]):
            def get_by_id(self, student_id: str) -> Student | None:
                ...
    """

    @abstractmethod
    def get_by_id(self, entity_id: ID) -> Optional[T]:
        """Retrieve an entity by its unique identifier.

        Args:
            entity_id: The unique identifier of the entity.

        Returns:
            The entity if found, None otherwise.
        """
        ...

    @abstractmethod
    def get_all(self, limit: Optional[int] = None, offset: int = 0) -> list[T]:
        """Retrieve all entities with optional pagination.

        Args:
            limit: Maximum number of entities to return (None for all).
            offset: Number of entities to skip.

        Returns:
            List of entities.
        """
        ...

    @abstractmethod
    def save(self, entity: T) -> T:
        """Persist an entity (insert or update).

        If the entity has no ID, it will be inserted.
        If the entity has an ID, it will be updated.

        Args:
            entity: The entity to persist.

        Returns:
            The persisted entity (may have updated fields like ID).
        """
        ...

    @abstractmethod
    def delete(self, entity_id: ID) -> bool:
        """Delete an entity by its identifier.

        Args:
            entity_id: The unique identifier of the entity to delete.

        Returns:
            True if the entity was deleted, False if it didn't exist.
        """
        ...

    @abstractmethod
    def exists(self, entity_id: ID) -> bool:
        """Check if an entity exists.

        Args:
            entity_id: The unique identifier to check.

        Returns:
            True if an entity with this ID exists.
        """
        ...

    @abstractmethod
    def count(self) -> int:
        """Count all entities in the repository.

        Returns:
            The total number of entities.
        """
        ...


class QueryableRepository(Repository[T, ID], ABC):
    """Extended repository with query capabilities.

    Provides additional methods for more complex queries beyond
    basic CRUD operations.
    """

    @abstractmethod
    def find_by(self, **criteria: Any) -> list[T]:
        """Find entities matching the given criteria.

        Args:
            **criteria: Field-value pairs to match.

        Returns:
            List of matching entities.
        """
        ...

    @abstractmethod
    def find_one_by(self, **criteria: Any) -> Optional[T]:
        """Find a single entity matching the given criteria.

        Args:
            **criteria: Field-value pairs to match.

        Returns:
            The first matching entity, or None.
        """
        ...


class BatchRepository(Repository[T, ID], ABC):
    """Repository with batch operation support.

    Provides methods for efficient bulk operations.
    """

    @abstractmethod
    def save_many(self, entities: Iterable[T]) -> list[T]:
        """Persist multiple entities at once.

        Args:
            entities: Iterable of entities to persist.

        Returns:
            List of persisted entities.
        """
        ...

    @abstractmethod
    def delete_many(self, entity_ids: Iterable[ID]) -> int:
        """Delete multiple entities at once.

        Args:
            entity_ids: Iterable of entity IDs to delete.

        Returns:
            Number of entities deleted.
        """
        ...


class SpecificationPattern(ABC, Generic[T]):
    """Base class for the Specification pattern.

    Specifications encapsulate query logic as first-class objects,
    enabling complex queries to be composed and reused.

    Example:
        class ActiveStudentSpec(SpecificationPattern[Student]):
            def is_satisfied_by(self, student: Student) -> bool:
                return student.status == 'Active'
    """

    @abstractmethod
    def is_satisfied_by(self, entity: T) -> bool:
        """Check if an entity satisfies this specification.

        Args:
            entity: The entity to check.

        Returns:
            True if the entity satisfies the specification.
        """
        ...

    def and_(self, other: "SpecificationPattern[T]") -> "AndSpecification[T]":
        """Combine with another specification using AND."""
        return AndSpecification(self, other)

    def or_(self, other: "SpecificationPattern[T]") -> "OrSpecification[T]":
        """Combine with another specification using OR."""
        return OrSpecification(self, other)

    def not_(self) -> "NotSpecification[T]":
        """Negate this specification."""
        return NotSpecification(self)


class AndSpecification(SpecificationPattern[T]):
    """Specification combining two specifications with AND."""

    def __init__(
        self,
        left: SpecificationPattern[T],
        right: SpecificationPattern[T],
    ) -> None:
        self.left = left
        self.right = right

    def is_satisfied_by(self, entity: T) -> bool:
        return self.left.is_satisfied_by(entity) and self.right.is_satisfied_by(entity)


class OrSpecification(SpecificationPattern[T]):
    """Specification combining two specifications with OR."""

    def __init__(
        self,
        left: SpecificationPattern[T],
        right: SpecificationPattern[T],
    ) -> None:
        self.left = left
        self.right = right

    def is_satisfied_by(self, entity: T) -> bool:
        return self.left.is_satisfied_by(entity) or self.right.is_satisfied_by(entity)


class NotSpecification(SpecificationPattern[T]):
    """Specification negating another specification."""

    def __init__(self, spec: SpecificationPattern[T]) -> None:
        self.spec = spec

    def is_satisfied_by(self, entity: T) -> bool:
        return not self.spec.is_satisfied_by(entity)


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    # Core types
    "Entity",
    "Repository",
    # Extended interfaces
    "QueryableRepository",
    "BatchRepository",
    # Specification pattern
    "SpecificationPattern",
    "AndSpecification",
    "OrSpecification",
    "NotSpecification",
]
