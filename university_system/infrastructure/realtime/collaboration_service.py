"""
Real-Time Collaboration Service

Enables collaborative document editing and real-time content synchronization.
"""

import logging
from typing import Dict, List, Optional, Set
from datetime import datetime
from enum import Enum
from .websocket_manager import get_websocket_manager, MessageType

logger = logging.getLogger(__name__)


class DocumentType(str, Enum):
    """Document types"""
    ASSIGNMENT = "assignment"
    NOTES = "notes"
    PROJECT = "project"
    WHITEBOARD = "whiteboard"


class OperationType(str, Enum):
    """Operational transformation types"""
    INSERT = "insert"
    DELETE = "delete"
    REPLACE = "replace"
    FORMAT = "format"


class CollaborationService:
    """
    Service for real-time collaborative document editing.

    Uses operational transformation for conflict resolution and
    maintains document state synchronization across users.
    """

    def __init__(self):
        """Initialize collaboration service"""
        self.ws_manager = get_websocket_manager()

        # document_id -> document data
        self.documents: Dict[str, dict] = {}

        # document_id -> set of user_ids (collaborators)
        self.document_collaborators: Dict[str, Set[str]] = {}

        # document_id -> list of operations
        self.operation_history: Dict[str, List[dict]] = {}

        # document_id -> cursor positions
        # {user_id: {"position": int, "selection": [start, end]}}
        self.cursors: Dict[str, Dict[str, dict]] = {}

    async def create_document(
        self,
        document_id: str,
        document_type: DocumentType,
        owner_id: str,
        title: str,
        initial_content: str = "",
        metadata: Optional[dict] = None
    ) -> dict:
        """
        Create a new collaborative document.

        Args:
            document_id: Unique document identifier
            document_type: Type of document
            owner_id: Document owner user ID
            title: Document title
            initial_content: Initial document content
            metadata: Additional metadata

        Returns:
            Document data dictionary
        """
        document = {
            "document_id": document_id,
            "type": document_type.value,
            "owner_id": owner_id,
            "title": title,
            "content": initial_content,
            "version": 0,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "metadata": metadata or {}
        }

        self.documents[document_id] = document
        self.document_collaborators[document_id] = {owner_id}
        self.operation_history[document_id] = []
        self.cursors[document_id] = {}

        logger.info(f"Document {document_id} created by {owner_id}")
        return document

    async def join_document(self, document_id: str, user_id: str) -> Optional[dict]:
        """
        Join a document for collaboration.

        Args:
            document_id: Document identifier
            user_id: User identifier

        Returns:
            Current document state or None if failed
        """
        if document_id not in self.documents:
            logger.warning(f"Document {document_id} not found")
            return None

        # Add collaborator
        if document_id not in self.document_collaborators:
            self.document_collaborators[document_id] = set()
        self.document_collaborators[document_id].add(user_id)

        # Initialize cursor position
        if document_id not in self.cursors:
            self.cursors[document_id] = {}
        self.cursors[document_id][user_id] = {
            "position": 0,
            "selection": None
        }

        # Join WebSocket room
        await self.ws_manager.join_room(user_id, f"doc_{document_id}")

        # Notify other collaborators
        await self._broadcast_collaborator_update(
            document_id,
            user_id,
            "joined",
            exclude_user=user_id
        )

        logger.info(f"User {user_id} joined document {document_id}")
        return self.documents[document_id]

    async def leave_document(self, document_id: str, user_id: str):
        """
        Leave a document collaboration session.

        Args:
            document_id: Document identifier
            user_id: User identifier
        """
        if document_id in self.document_collaborators:
            self.document_collaborators[document_id].discard(user_id)

        # Remove cursor
        if document_id in self.cursors and user_id in self.cursors[document_id]:
            del self.cursors[document_id][user_id]

        # Leave WebSocket room
        await self.ws_manager.leave_room(user_id, f"doc_{document_id}")

        # Notify other collaborators
        await self._broadcast_collaborator_update(
            document_id,
            user_id,
            "left"
        )

        logger.info(f"User {user_id} left document {document_id}")

    async def apply_operation(
        self,
        document_id: str,
        user_id: str,
        operation_type: OperationType,
        position: int,
        content: Optional[str] = None,
        length: Optional[int] = None
    ) -> bool:
        """
        Apply an edit operation to a document.

        Args:
            document_id: Document identifier
            user_id: User making the edit
            operation_type: Type of operation
            position: Position in document
            content: Content for insert/replace operations
            length: Length for delete/replace operations

        Returns:
            True if operation applied successfully
        """
        if document_id not in self.documents:
            return False

        document = self.documents[document_id]
        current_content = document["content"]

        # Apply operation
        try:
            if operation_type == OperationType.INSERT:
                new_content = (
                    current_content[:position] +
                    (content or "") +
                    current_content[position:]
                )
            elif operation_type == OperationType.DELETE:
                new_content = (
                    current_content[:position] +
                    current_content[position + (length or 0):]
                )
            elif operation_type == OperationType.REPLACE:
                new_content = (
                    current_content[:position] +
                    (content or "") +
                    current_content[position + (length or 0):]
                )
            else:
                new_content = current_content

            # Update document
            document["content"] = new_content
            document["version"] += 1
            document["updated_at"] = datetime.utcnow().isoformat()

            # Store operation
            operation = {
                "user_id": user_id,
                "type": operation_type.value,
                "position": position,
                "content": content,
                "length": length,
                "timestamp": datetime.utcnow().isoformat(),
                "version": document["version"]
            }
            self.operation_history[document_id].append(operation)

            # Broadcast to collaborators
            await self._broadcast_document_update(document_id, operation, user_id)

            return True

        except Exception as e:
            logger.error(f"Error applying operation to document {document_id}: {e}")
            return False

    async def update_cursor(
        self,
        document_id: str,
        user_id: str,
        position: int,
        selection: Optional[List[int]] = None
    ):
        """
        Update cursor position for a user.

        Args:
            document_id: Document identifier
            user_id: User identifier
            position: Cursor position
            selection: Optional selection range [start, end]
        """
        if document_id not in self.cursors:
            self.cursors[document_id] = {}

        self.cursors[document_id][user_id] = {
            "position": position,
            "selection": selection,
            "updated_at": datetime.utcnow().isoformat()
        }

        # Broadcast cursor update
        cursor_update = {
            "type": MessageType.DOCUMENT_UPDATE,
            "document_id": document_id,
            "update_type": "cursor",
            "user_id": user_id,
            "position": position,
            "selection": selection,
            "timestamp": datetime.utcnow().isoformat()
        }

        await self.ws_manager.send_to_room(
            f"doc_{document_id}",
            cursor_update,
            exclude_users={user_id}
        )

    def get_document(self, document_id: str) -> Optional[dict]:
        """
        Get document data.

        Args:
            document_id: Document identifier

        Returns:
            Document data or None
        """
        return self.documents.get(document_id)

    def get_collaborators(self, document_id: str) -> Set[str]:
        """
        Get active collaborators for a document.

        Args:
            document_id: Document identifier

        Returns:
            Set of user IDs
        """
        return self.document_collaborators.get(document_id, set()).copy()

    def get_operation_history(
        self,
        document_id: str,
        since_version: Optional[int] = None,
        limit: int = 100
    ) -> List[dict]:
        """
        Get operation history for a document.

        Args:
            document_id: Document identifier
            since_version: Get operations after this version
            limit: Maximum number of operations to return

        Returns:
            List of operation dictionaries
        """
        if document_id not in self.operation_history:
            return []

        operations = self.operation_history[document_id]

        if since_version is not None:
            operations = [
                op for op in operations
                if op["version"] > since_version
            ]

        return operations[-limit:]

    async def _broadcast_document_update(
        self,
        document_id: str,
        operation: dict,
        exclude_user: str
    ):
        """
        Broadcast document update to collaborators.

        Args:
            document_id: Document identifier
            operation: Operation data
            exclude_user: User ID to exclude from broadcast
        """
        update_message = {
            "type": MessageType.DOCUMENT_UPDATE,
            "document_id": document_id,
            "update_type": "operation",
            "operation": operation,
            "timestamp": datetime.utcnow().isoformat()
        }

        await self.ws_manager.send_to_room(
            f"doc_{document_id}",
            update_message,
            exclude_users={exclude_user}
        )

    async def _broadcast_collaborator_update(
        self,
        document_id: str,
        user_id: str,
        action: str,
        exclude_user: Optional[str] = None
    ):
        """
        Broadcast collaborator join/leave events.

        Args:
            document_id: Document identifier
            user_id: User who joined/left
            action: "joined" or "left"
            exclude_user: Optional user ID to exclude
        """
        collaborator_update = {
            "type": MessageType.DOCUMENT_UPDATE,
            "document_id": document_id,
            "update_type": "collaborator",
            "user_id": user_id,
            "action": action,
            "timestamp": datetime.utcnow().isoformat()
        }

        exclude_users = {exclude_user} if exclude_user else None
        await self.ws_manager.send_to_room(
            f"doc_{document_id}",
            collaborator_update,
            exclude_users=exclude_users
        )


# Global collaboration service instance
_collaboration_service: Optional[CollaborationService] = None


def get_collaboration_service() -> CollaborationService:
    """
    Get the global collaboration service instance.

    Returns:
        CollaborationService instance
    """
    global _collaboration_service
    if _collaboration_service is None:
        _collaboration_service = CollaborationService()
    return _collaboration_service
